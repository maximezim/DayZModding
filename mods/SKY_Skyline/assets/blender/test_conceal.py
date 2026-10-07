"""Gate (D79, hull test 2): one-way concealment. Finds volumes a player's head could hide inside: opaque Res0
interior (seen from both horizontal ray directions) that no Fire / View Geometry covers, at least a 0.3 m cube
(a head), and within head reach (0.1-1.9 m) of something to stand on (ground, Roadway, Geometry tops).
Inside such a volume the player sees out (back faces are not drawn) while others see solid scenery and their
bullets pass the empty render. Glass, foliage, decals and lamps are see-through by design and skipped.

    python assets/blender/test_conceal.py [--only A,B] [--report]

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


def intervals(T, axis, a, b, lo, hi):
    """Inside intervals along a ray parallel to `axis` through (a, b) on the other two axes."""
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
    # pair each entering hit with the next exiting hit
    out, start = [], None
    for tt, s in ev:
        if s < 0 and start is None:
            start = tt
        elif s > 0 and start is not None:
            out.append((start, tt)); start = None
    return out


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
    v = 0.1
    n = np.maximum(1, np.ceil((hi - lo) / v).astype(int))
    occ = []
    for axis in (0, 1):
        g = np.zeros(n, bool)
        oa = 1 - axis
        for ia in range(n[oa]):
            a = lo[oa] + (ia + 0.5) * v
            for iz in range(n[2]):
                z = lo[2] + (iz + 0.5) * v
                ri = intervals(R, axis, a, z, lo, hi)
                if not ri:
                    continue
                ci = intervals(C, axis, a, z, lo, hi) if len(C) else []
                gi = intervals(G, axis, a, z, lo, hi) if len(G) else []          # covered = Geometry AND Fire/View (sec D79 H2)
                for (s0, s1) in ri:
                    for ib in range(max(0, int((s0 - lo[axis]) / v)), min(n[axis], int(np.ceil((s1 - lo[axis]) / v)))):
                        c = lo[axis] + (ib + 0.5) * v
                        if s0 <= c <= s1 and not (any(x0 <= c <= x1 for x0, x1 in ci) and any(x0 <= c <= x1 for x0, x1 in gi)):
                            idx = [0, 0, 0]; idx[axis] = ib; idx[oa] = ia; idx[2] = iz
                            g[tuple(idx)] = True
        occ.append(g)
    g = occ[0] & occ[1]
    k = int(round(minsize / v))
    if min(g.shape) < k:
        return []
    # erosion by a k-cube: a voxel survives if the k x k x k block starting there is all set
    from numpy.lib.stride_tricks import sliding_window_view
    w = sliding_window_view(g, (k, k, k)).all(axis=(-3, -2, -1))
    hits = np.argwhere(w)
    cubes = [tuple(round(float(lo[i] + (h[i] + k / 2) * v), 2) for i in range(3)) for h in hits]
    return [c for c in cubes if reachable(lods, c, floors_cache(lods))]


def floors_cache(lods, _c={}):
    key = id(lods)
    if key not in _c:
        _c.clear()
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
        _c[key] = np.concatenate(F) if F else np.zeros((0, 3, 3))
    return _c[key]


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


CLIMB = 2.0           # m: highest Geometry top a player gets onto without a Roadway (vault / climb)
ACCEPTED = {}          # name -> reason (reviewed exceptions); empty: every finding is fixed


def main():
    builders = {}
    for modname in ("build_kit", "build_props", "build_landmarks", "build_creatures", "build_underground", "build_vehicles", "build_streetprops"):
        m = __import__(modname)
        for n, (fn, _p, _f) in m.modules().items():
            builders[n] = fn
    argv = sys.argv[1:]
    names = argv[argv.index("--only") + 1].split(",") if "--only" in argv else \
        [n for n in builders if n in S.KIT and S.KIT[n]["collide"] and not S.KIT[n].get("city")
         and S.KIT[n]["category"] not in ("floor", "roof")]
    tot, fails = time.time(), []
    for n in names:
        lods = {l.name: l for l in builders[n]()}
        if "fire" not in lods:
            continue
        w = check(lods)
        if not w:
            continue
        cl = clusters(w)
        line = "%s: %d hiding cubes in %d volumes, largest %d cubes %s..%s" % (n, len(w), len(cl), cl[0][0], cl[0][1], cl[0][2])
        if n in ACCEPTED:
            print("  accepted", line, "-", ACCEPTED[n])
        else:
            fails.append(line)
            if "--report" in argv:
                for c in cl[:6]:
                    print("    ", c)
    for f in fails:
        print("  FAIL", f)
    print("CONCEALMENT TEST: %s (%d models, %.0fs)" % ("%d FAILED" % len(fails) if fails else "PASS", len(names), time.time() - tot))
    return 1 if fails else 0


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
