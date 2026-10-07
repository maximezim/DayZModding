"""Gate (D79, hull test 2): one-way concealment. Finds volumes a player's head could hide inside: opaque Res0
interior (seen from both horizontal ray directions) that no Fire / View Geometry covers, at least a 0.3 m cube
(a head), and within head reach (0.1-1.9 m) of something to stand on (ground, Roadway, Geometry tops).
Inside such a volume the player sees out (back faces are not drawn) while others see solid scenery and their
bullets pass the empty render. Glass, foliage, decals and lamps are see-through by design and skipped.

    python assets/blender/test_conceal.py [--only A,B] [--city] [--jobs N] [--report]

Covered means inside Geometry AND inside Fire or View (a Fire-only box still lets a head in).
Exit 1 on any finding not listed in ACCEPTED (reasoned exceptions).

Known blind spots (security D79 M4): a volume must read as inside from both horizontal ray directions (a box open
on one side is not seen); each entering face pairs with the next exiting face (nested or flipped solids are cut
short); city buildings, floor / roof modules and non-colliding decals are not scanned (their own tests cover
reachability and slabs). Keep SEE_THROUGH to alpha materials.
"""
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import skyspec as S  # noqa: E402

SEE_THROUGH = {"glass", "glassfar", "foliage", "vegetation", "decal_dirt", "decal_cracks", "decal_graffiti", "decal_grime",
               "roadmark", "windows", "windows_lit", "lamp", "lamp_cool", "fair_ca"}


def tris(lod, opaque_only=True):
    out = []
    for idx, mat, _uv in lod.faces:
        if opaque_only and (mat in SEE_THROUGH):
            continue
        p = [lod.verts[i] for i in idx]
        for k in range(1, len(p) - 1):
            out.append((p[0], p[k], p[k + 1]))
    return np.array(out, np.float64).reshape(-1, 3, 3)


def intervals(T, axis, a, b, lo, hi, closed=False):
    """Inside intervals along a ray parallel to `axis` through (a, b) on the other two axes. closed: the mesh is
    closed collision solids - count depth (touching / nested parts stay covered, D82); otherwise pair each
    entering face with the next exiting one (render LODs skip hidden faces, so depth would drift)."""
    o = [i for i in range(3) if i != axis]
    P = T[:, :, o]                                      # (n,3,2)
    q = np.array([a, b])
    v0, v1, v2 = P[:, 0], P[:, 1], P[:, 2]
    def cross(u, w): return u[:, 0] * w[:, 1] - u[:, 1] * w[:, 0]
    d = cross(v1 - v0, v2 - v0)
    ok = np.abs(d) > 1e-12
    w0 = cross(v1 - q, v2 - q) / np.where(ok, d, 1)
    w1 = cross(v2 - q, v0 - q) / np.where(ok, d, 1)
    w2 = 1 - w0 - w1
    eps = 1e-9
    hit = ok & (w0 >= -eps) & (w1 >= -eps) & (w2 >= -eps)
    if not hit.any():
        return []
    Th = T[hit]
    t = (w0[hit] * Th[:, 0, axis] + w1[hit] * Th[:, 1, axis] + w2[hit] * Th[:, 2, axis])
    n = np.cross(Th[:, 1] - Th[:, 0], Th[:, 2] - Th[:, 0])[:, axis]   # normal component along the ray
    order = np.argsort(t)
    ev = [(t[i], -1 if n[i] < 0 else 1) for i in order if abs(n[i]) > 1e-12]
    if closed:
        # one event per (t, side) - a ray on a shared triangle edge hits both triangles - exits before enters
        ev = sorted({(round(float(tt), 6), s_) for tt, s_ in ev}, key=lambda e: (e[0], -e[1]))
        out, depth, start = [], 0, None
        for tt, s_ in ev:
            if s_ < 0:
                if depth == 0:
                    start = tt
                depth += 1
            elif depth > 0:
                depth -= 1
                if depth == 0:
                    if out and abs(out[-1][1] - start) < 1e-6:
                        out[-1] = (out[-1][0], tt)                # touching parts: one interval
                    else:
                        out.append((start, tt))
        return out
    # pair each entering hit with the next exiting hit
    out, start = [], None
    for tt, s in ev:
        if s < 0 and start is None:
            start = tt
        elif s > 0 and start is not None:
            out.append((start, tt)); start = None
    return out


def span_mask(c, ivs, shrink=0.0):
    """Boolean mask of the centres c that fall inside any (a, b) interval (shrunk by `shrink` at both ends)."""
    m = np.zeros(len(c), bool)
    for a, b in ivs:
        m |= (c >= a + shrink) & (c <= b - shrink)
    return m


def covered(seg, ivs):
    a, b = seg
    c = 0.0
    for x0, x1 in ivs:
        c += max(0.0, min(b, x1) - max(a, x0))
    return c


def check(lods, minsize=0.3):  # noqa: C901
    """Voxels inside opaque Res0 volumes (seen from both horizontal ray directions) that no Fire/View interval
    covers; eroded by a minsize cube: what remains could hide a head (one-way concealment)."""
    R = tris(lods["res0"])
    C = np.concatenate([tris(lods[k], False) for k in ("fire", "view") if k in lods] or [np.zeros((0, 3, 3))])
    G = tris(lods["geo"], False) if "geo" in lods else np.zeros((0, 3, 3))
    if not len(R):
        return []
    lo, hi = R.reshape(-1, 3).min(0), R.reshape(-1, 3).max(0)
    lo = lo - 0.0137          # voxel centres off the 5 cm model grid: a ray on a face plane flips in/out (D82)
    v = 0.1
    n = np.maximum(1, np.ceil((hi - lo) / v).astype(int))
    occ = []
    # triangle bounds for row binning: a ray at (a, z) can only hit triangles whose z range holds z and whose
    # range on the other horizontal axis holds a (D82: city buildings in seconds, not hours)
    def rng(T, ax):
        return (T[:, :, ax].min(1), T[:, :, ax].max(1)) if len(T) else (np.zeros(0), np.zeros(0))
    centres = [lo[i] + (np.arange(n[i]) + 0.5) * v for i in range(3)]
    spans = []                                                  # length of the render interval each voxel sits in
    for axis in (0, 1):
        g = np.zeros(n, bool)
        ln = np.zeros(n, np.float32)
        oa = 1 - axis
        rz, cz, gz = rng(R, 2), rng(C, 2), rng(G, 2)
        for iz in range(n[2]):
            z = lo[2] + (iz + 0.5) * v
            Rz = R[(rz[0] <= z) & (rz[1] >= z)]
            if not len(Rz):
                continue
            Cz = C[(cz[0] <= z) & (cz[1] >= z)] if len(C) else C
            Gz = G[(gz[0] <= z) & (gz[1] >= z)] if len(G) else G
            ro, co, go = rng(Rz, oa), rng(Cz, oa), rng(Gz, oa)
            for ia in range(n[oa]):
                a = lo[oa] + (ia + 0.5) * v
                Ra = Rz[(ro[0] <= a) & (ro[1] >= a)]
                if not len(Ra):
                    continue
                ri = intervals(Ra, axis, a, z, lo, hi)
                if not ri:
                    continue
                Ca = Cz[(co[0] <= a) & (co[1] >= a)] if len(Cz) else Cz
                Ga = Gz[(go[0] <= a) & (go[1] >= a)] if len(Gz) else Gz
                ci = intervals(Ca, axis, a, z, lo, hi, closed=True) if len(Ca) else []
                gi = intervals(Ga, axis, a, z, lo, hi, closed=True) if len(Ga) else []          # covered = Geometry AND Fire/View (sec D79 H2)
                inside = span_mask(centres[axis], ri, 0.025)   # strictly inside: a 20 cm slab is not a 0.3 m cube (D82)
                bad = inside & ~(span_mask(centres[axis], ci) & span_mask(centres[axis], gi))
                if bad.any():
                    lens = np.zeros(len(centres[axis]), np.float32)
                    for (s0, s1) in ri:
                        walls = any(x0 <= s0 + 0.05 <= x1 for x0, x1 in gi) and any(x0 <= s1 - 0.05 <= x1 for x0, x1 in gi)
                        # a long span counts as room-scale only when its two ends are collision walls (sec D82 M3)
                        lens[(centres[axis] >= s0) & (centres[axis] <= s1)] = (s1 - s0) if walls else 0.0
                    if axis == 0:
                        g[:, ia, iz] |= bad
                        ln[:, ia, iz] = np.where(bad, lens, ln[:, ia, iz])
                    else:
                        g[ia, :, iz] |= bad
                        ln[ia, :, iz] = np.where(bad, lens, ln[ia, :, iz])
        occ.append(g)
        spans.append(ln)
    # an object is at most OBJ_MAX across on its shorter horizontal side; room-scale "inside" spans come from
    # render walls that skip hidden faces (ruin cuts, partitions) and are artefacts (D82)
    g = occ[0] & occ[1] & (np.minimum(spans[0], spans[1]) <= OBJ_MAX)
    k = int(round(minsize / v))
    if min(g.shape) < k:
        return []
    # erosion by a k-cube: a voxel survives if the k x k x k block starting there is all set
    from numpy.lib.stride_tricks import sliding_window_view
    w = sliding_window_view(g, (k, k, k)).all(axis=(-3, -2, -1))
    hits = np.argwhere(w)
    cubes = [tuple(round(float(lo[i] + (h[i] + k / 2) * v), 2) for i in range(3)) for h in hits]
    if not cubes:
        return []
    tb = (R.min(1), R.max(1))
    F = floor_tris(lods)                                     # per model (an id() cache could hand a freed model's floors on)
    cubes = [c for c in cubes if reachable(lods, c, F) and capped(R, c) and near_surface(tb, c)]
    return drop_mound_feet(lods, cubes) if cubes else cubes


def drop_mound_feet(lods, cubes, pad=0.35, most=4):
    """Clusters of at most `most` cubes at the foot of a colliding rubble mound (Geometry selection "rubble") are a
    sliver where the mound meets the floor finish: the mound collides, no head gets in (D82, reviewed in
    City_CornerShop / CornerPharmacy / Cinema _Ruined)."""
    g = lods.get("geo")
    if g is None or "rubble" not in g.groups:
        return cubes
    V = np.array(g.verts)
    rv = set(g.groups["rubble"])
    boxes = [(V[list(v)].min(0) - pad, V[list(v)].max(0) + pad, V[list(v)].min(0)[2]) for k, v in g.groups.items()
             if k.startswith("Component") and set(v) & rv]
    keep = []
    for cnt, lo, hi in clusters(cubes):
        # at the FOOT only: the cluster sits within 0.3 m of the mound's base (sec D82 M5)
        if cnt <= most and any((np.array(lo) >= a).all() and (np.array(hi) <= b).all() and hi[2] <= zb + 0.3
                               for a, b, zb in boxes):
            continue
        keep += [c for c in cubes if all(lo[i] - 1e-6 <= c[i] <= hi[i] + 1e-6 for i in range(3))]
    return keep


def near_surface(tb, c, d=0.45):
    """Some opaque render triangle within d of the cube centre (box distance): a hiding volume sits inside an
    object; open room air far from every face is a pairing artefact (D82)."""
    lo, hi = tb
    p = np.array(c)
    gap = np.maximum(0.0, np.maximum(lo - p, p - hi))
    return bool((np.sqrt((gap ** 2).sum(1)) <= d).any())


def capped(R, c, reach=0.6):
    """A real hiding volume is an object with a top: some upward-facing opaque render face lies within `reach`
    above the cube (shade top, mattress, panel). Open room air under a ceiling (faces point down) is a pairing
    artefact of render walls that skip hidden faces (D82)."""
    x, y, z = c
    P = R[:, :, :2]
    v0, v1, v2 = P[:, 0], P[:, 1], P[:, 2]
    def cross(u, w): return u[:, 0] * w[:, 1] - u[:, 1] * w[:, 0]
    q = np.array([x, y])
    d = cross(v1 - v0, v2 - v0)
    ok = np.abs(d) > 1e-12
    w0 = cross(v1 - q, v2 - q) / np.where(ok, d, 1)
    w1 = cross(v2 - q, v0 - q) / np.where(ok, d, 1)
    w2 = 1 - w0 - w1
    hit = ok & (w0 >= -1e-9) & (w1 >= -1e-9) & (w2 >= -1e-9)
    if not hit.any():
        return False
    Th = R[hit]
    t = w0[hit] * Th[:, 0, 2] + w1[hit] * Th[:, 1, 2] + w2[hit] * Th[:, 2, 2]
    nz = np.cross(Th[:, 1] - Th[:, 0], Th[:, 2] - Th[:, 0])[:, 2]
    up = t > z
    if not up.any():
        return False
    t0 = np.min(np.where(up, t, np.inf))                       # the first face(s) above: an object's top faces up,
    first = up & (t <= t0 + 1e-4)                              # a ceiling seen from open air faces down; ties (double
    return bool(t0 <= z + reach and (nz[first] > 0).any())     # sided tops, coplanar faces) count if any faces up


def floor_tris(lods):
    F = []
    for k in ("road", "geo"):
        if k in lods:
            T = tris(lods[k], False)
            if len(T):
                nz = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
                up = nz[:, 2] / (np.linalg.norm(nz, axis=1) + 1e-12) > 0.64         # walkable: < ~50 deg (sec D79 M5)
                if k == "geo":                                  # tops you can climb onto from the ground (<= 2 m);
                    up &= T[:, :, 2].max(1) <= CLIMB            # higher floors count only as Roadway
                F.append(T[up])
    return np.concatenate(F) if F else np.zeros((0, 3, 3))


def reachable(lods, c, F, reach=(0.1, 1.9)):
    """A head can be at c: some floor (ground plane z = 0, a walkable Roadway face, or a Geometry top at most CLIMB
    high) lies 0.1-1.9 m below the cube centre."""
    x, y, z = c
    if ground_plane(lods) and reach[0] <= z <= reach[1]:
        return True
    if not len(F):
        return False
    for dx, dy in ((0, 0), (0.3, 0), (-0.3, 0), (0, 0.3), (0, -0.3)):          # floors beside the cube too (overhangs)
        if any(reach[0] <= z - f <= reach[1] for f in floor_heights(F, x + dx, y + dy)):
            return True
    return False


def ground_plane(lods):
    """z = 0 counts as ground only for surface models (underground pieces sit far below it, sec D79 M5)."""
    T = tris(lods["res0"], False)
    return len(T) == 0 or T[:, :, 2].min() > -1.0


def floor_heights(F, x, y):
    P = F[:, :, :2]
    q = np.array([x, y])
    v0, v1, v2 = P[:, 0], P[:, 1], P[:, 2]
    def cross(u, w): return u[:, 0] * w[:, 1] - u[:, 1] * w[:, 0]
    d = cross(v1 - v0, v2 - v0)
    ok = np.abs(d) > 1e-12
    w0 = cross(v1 - q, v2 - q) / np.where(ok, d, 1)
    w1 = cross(v2 - q, v0 - q) / np.where(ok, d, 1)
    w2 = 1 - w0 - w1
    hit = ok & (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6)
    return list(w0[hit] * F[hit, 0, 2] + w1[hit] * F[hit, 1, 2] + w2[hit] * F[hit, 2, 2])


OBJ_MAX = 3.6          # m: widest render-only object (shorter side) the test treats as a possible hiding volume
CLIMB = 2.0           # m: highest Geometry top a player gets onto without a Roadway (vault / climb)
ACCEPTED = {}          # name -> reason (reviewed exceptions)


_BUILDERS = {}


def _builders():
    if not _BUILDERS:
        for modname in ("build_kit", "build_props", "build_landmarks", "build_creatures", "build_underground",
                        "build_vehicles", "build_streetprops", "build_city", "build_floors"):
            m = __import__(modname)
            for n, (fn, _p, _f) in m.modules().items():
                _BUILDERS[n] = fn
    return _BUILDERS


def scan(n):
    """(name, cubes, seconds) for one model."""
    t = time.time()
    lods = {l.name: l for l in _builders()[n]()}
    w = check(lods) if "fire" in lods else []
    return n, w, time.time() - t


def main():
    builders = _builders()
    argv = sys.argv[1:]
    city = "--city" in argv                                    # D82: city buildings + floor / roof modules
    jobs = int(argv[argv.index("--jobs") + 1]) if "--jobs" in argv else 1
    names = argv[argv.index("--only") + 1].split(",") if "--only" in argv else \
        [n for n in builders if n in S.KIT and S.KIT[n]["collide"]
         and (city or (not S.KIT[n].get("city") and S.KIT[n]["category"] not in ("floor", "roof")))]
    tot, fails = time.time(), []
    if jobs > 1:
        import multiprocessing as mp
        with mp.get_context("fork").Pool(jobs) as pool:
            results = pool.imap_unordered(scan, names)
            results = list(_report(results, fails, argv))
    else:
        list(_report(map(scan, names), fails, argv))
    for f in fails:
        print("  FAIL", f)
    print("CONCEALMENT TEST: %s (%d models, %.0fs)" % ("%d FAILED" % len(fails) if fails else "PASS", len(names), time.time() - tot))
    return 1 if fails else 0


def _report(results, fails, argv):
    for n, w, dt in results:
        if "--report" in argv:
            print("  scanned %s (%.0fs)%s" % (n, dt, " - %d cubes" % len(w) if w else ""), flush=True)
        if w:
            cl = clusters(w)
            line = "%s: %d hiding cubes in %d volumes, largest %d cubes %s..%s" % (n, len(w), len(cl), cl[0][0], cl[0][1], cl[0][2])
            if n in ACCEPTED:
                print("  accepted", line, "-", ACCEPTED[n], flush=True)
            else:
                fails.append(line)
                if "--report" in argv:
                    for c in cl[:6]:
                        print("    ", c, flush=True)
        yield n


def clusters(cubes, v=0.1):
    """Connected groups of hiding cubes: (count, min corner, max corner), largest first."""
    pts = [tuple(c) for c in cubes]
    seen, out = set(), []
    S_ = set(pts)
    for p in pts:
        if p in seen:
            continue
        st, comp = [p], []
        seen.add(p)
        while st:
            q = st.pop(); comp.append(q)
            for d in [(a, b, c) for a in (-1, 0, 1) for b in (-1, 0, 1) for c in (-1, 0, 1)]:
                r = tuple(round(q[i] + d[i] * v, 2) for i in range(3))
                if r in S_ and r not in seen:
                    seen.add(r); st.append(r)
        a = np.array(comp)
        out.append((len(comp), tuple(float(x) for x in np.round(a.min(0), 2)), tuple(float(x) for x in np.round(a.max(0), 2))))
    return sorted(out, reverse=True)


if __name__ == "__main__":
    sys.exit(main())
