"""Gate (D96): render quality defects that the geometry gates do not see - z-fighting, smeared UVs, the engine vertex
limit and collision without a visible surface.

    python assets/blender/test_quality.py [--only A,B] [--jobs 4] [--report] [--selftest]

Per model, every graphical (Resolution) LOD:
  zfight    two faces facing the same way in the same plane (closer than zfix.ZF_EPS) that overlap by more than
            zfix.ZF_AREA: the GPU cannot order them and they flicker in game (CT-13 "glitched textures"). Measured
            after zfix.resolve(), which the exporter runs on every Resolution LOD: what is left could not be resolved.
  smear     a textured face whose UVs collapse in one direction (ratio < SMEAR_RATIO) over more than SMEAR_EXT:
            the texture is stretched into streaks (a single texel row across a sill top, a slab edge).
  vertices  render vertices after the binarizer splits points per normal and UV (= what the engine counts, WIN-06:
            65,535 is a hard limit, the model is dropped with "Too many vertices") must stay <= VERTEX_LIMIT.
Geometry LOD:
  ghost     a collision face with no render surface within GHOST_DIST over more than GHOST_AREA: an invisible wall
            or an oversized collision box (the player bumps into air).
Exit 1 on any failure. The vertex rule is measured on what the exporter writes (proxy parts included, D96).
"""
import math
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import skyspec as S  # noqa: E402
from skygeo import LOD_GEOMETRY, LOD_RES  # noqa: E402

SMEAR_RATIO = 0.03     # smallest / largest UV scale of a face
SMEAR_EXT = 0.06       # m: extent of the face along the collapsed direction that makes a visible streak
SMEAR_MIN = 0.1        # UV per metre along the stretched direction: under this a texture is a streak (a 4 cm trim with
                       # steel at 3 m per tile along it is a normal tiling, not a smear - D96)
ZF_MAX_LAYERS = 3      # zfix layers (x 4 mm) a part may be pushed out before it reads as a step
ZF_MAX_LAYERS_DEBRIS = 10   # loose debris chunks (< 0.8 m) piled at random: 4 cm on a rubble lump does not read
DEBRIS = {"rubble", "brick", "concrete", "rust", "trash"}
VERTEX_LIMIT = 60000   # render vertices per LOD (engine hard limit 65,535; margin for the binarizer's own splits)
GHOST_DIST = 0.2       # m: a collision face this far from every render face is not seen (glass sits up to 14 cm in a wall)
GHOST_AREA = 0.5       # m2 of unseen collision surface per component (the user asked about "big collisions")
GHOST_WALL = 2.0       # m2 a wall (>= 2 m tall) may keep unseen: one broken window keeps its collision pane (vanilla)
GHOST_FRAC = 0.02      # and more than this share of the component (a sliver along a 110 m2 curtain wall is not a wall)
GHOST_LOW = 1.25       # m: a component this low whose top is seen is a rail / desk / bench: one box over bars or legs
NO_TEX = {"lamp", "lamp_cool"}
ACCEPTED = {}          # (model, check) -> reason


# ------------------------------------------------------------------ face arrays
def face_arrays(lod):
    """Triangulated faces: (tris N x 3 x 3, face index per tri, normals per face, polys list)."""
    polys = [np.asarray([lod.verts[i] for i in f[0]], float) for f in lod.faces]
    tris, owner = [], []
    for k, p in enumerate(polys):
        for j in range(1, len(p) - 1):
            tris.append((p[0], p[j], p[j + 1]))
            owner.append(k)
    return np.asarray(tris, float).reshape(-1, 3, 3), np.asarray(owner, int), polys


from zfix import ZF_AREA, ZF_EPS, area2, basis, ccw, clip, newell, zfight  # noqa: E402,F401


def smear(lod):
    """[(extent m, material, centre)]: UVs collapse along a direction the face actually extends in."""
    out = []
    for idx, mat, uv in lod.faces:
        if not uv or not mat or mat in NO_TEX or len(idx) < 3:
            continue
        p = np.asarray([lod.verts[i] for i in idx], float)
        t = np.asarray(uv, float)
        n = newell(p)
        if n is None:
            continue
        u, v = basis(n)
        q = np.stack([p @ u, p @ v], 1)
        e = q[1:] - q[0]
        f = t[1:] - t[0]
        # least-squares 2x2 map (metres -> UV) over all corners
        M, *_ = np.linalg.lstsq(e, f, rcond=None)
        sv = np.linalg.svd(M.T, compute_uv=True)
        s = sv[1]
        if s[0] < 1e-9:
            continue
        if s[1] / s[0] < SMEAR_RATIO and s[1] < SMEAR_MIN:
            d = sv[2][1]                                  # direction (in face 2D) with the smallest UV change
            dp = np.array([-d[1], d[0]])
            area = 0.5 * abs(sum(q[i - 1][0] * q[i][1] - q[i][0] * q[i - 1][1] for i in range(len(q))))
            ext = float(area / max(1e-9, np.ptp(q @ dp)))  # mean chord along d (a sheared strip is thin, not tall)
            if ext > SMEAR_EXT:
                out.append((ext, mat, tuple(np.round(p.mean(0), 2))))
    return out


def render_vertices(lod):
    """What the binarizer keeps: one vertex per distinct (point, normal, UV); the native writer's own normals."""
    import p3dwriter as W
    if hasattr(W, "render_vertex_count"):
        return W.render_vertex_count(lod)
    s = set()
    for idx, _mat, uv in W._faces(lod):
        n = tuple(round(c, 3) for c in W._newell([lod.verts[i] for i in idx]))
        uvs = uv if uv else [(0.0, 0.0)] * len(idx)
        for vi, tt in zip(idx, uvs):
            s.add((vi, n, round(tt[0], 5), round(tt[1], 5)))
    return len(s)


def _tri_keys(tris, h, spacing):
    """Unique voxel keys (h m cells) of points on every triangle, at most `spacing` apart (barycentric grids, triangles
    grouped by subdivision level, reduced to unique keys group by group to bound memory)."""
    e = np.stack([np.linalg.norm(tris[:, 1] - tris[:, 0], axis=1), np.linalg.norm(tris[:, 2] - tris[:, 1], axis=1),
                  np.linalg.norm(tris[:, 0] - tris[:, 2], axis=1)], 1).max(1)
    k = np.maximum(1, np.ceil(e / spacing)).astype(int)
    k = 2 ** np.ceil(np.log2(k)).astype(int)
    keys = []
    for kk in np.unique(k):
        idx = np.nonzero(k == kk)[0]
        ii, jj = np.meshgrid(np.arange(kk + 1), np.arange(kk + 1), indexing="ij")
        m = ii + jj <= kk
        u, v = (ii[m] / kk)[None, :, None], (jj[m] / kk)[None, :, None]
        step = max(1, int(2e6 // max(1, m.sum())))
        for c0 in range(0, len(idx), step):
            sel = tris[idx[c0:c0 + step]]
            a, b, c = sel[:, 0][:, None, :], sel[:, 1][:, None, :], sel[:, 2][:, None, :]
            pts = (a + u * (b - a) + v * (c - a)).reshape(-1, 3)
            keys.append(np.unique(_keys(np.floor(pts / h).astype(np.int64))))
    return np.unique(np.concatenate(keys)) if keys else np.zeros(0, np.int64)


def _keys(ix):
    return (ix[:, 0] + 50000) * 10 ** 10 + (ix[:, 1] + 50000) * 10 ** 5 + (ix[:, 2] + 50000)


NEIGH = np.array([(a, b, c) for a in (-1, 0, 1) for b in (-1, 0, 1) for c in (-1, 0, 1)], np.int64)


def ghosts(geo, res, step=0.15, h=0.1):
    """[(component, unseen m2, centre)]: collision surface with no render surface near it (voxels of h m: a sample
    is seen when a render voxel is in its 3 x 3 x 3 neighbourhood, i.e. within ~h..2h = 8-16 cm). All components are
    sampled in one batch (sample -> component id) so the 27 neighbour lookups run once per model."""
    tris, _own, _p = face_arrays(res)
    if not len(tris):
        return []
    rkeys = _tri_keys(tris, h, h)
    comp_of = {}
    names = []
    for name, vs in geo.groups.items():
        if name.startswith("Component"):
            ci = len(names)
            names.append(name)
            for v in vs:
                comp_of[v] = ci
    ftris, fcomp, fnorm = [], [], []
    for fidx, _m, _uv in geo.faces:
        c = comp_of.get(fidx[0])
        if c is None:
            continue
        p = [geo.verts[i] for i in fidx]
        n = newell(np.asarray(p, float))
        if n is None:
            continue
        if n[2] < -0.9 and max(q[2] for q in p) < 0.05:
            continue                                         # resting on the ground: nobody sees under it
        cen = np.mean([geo.verts[i] for i in geo.groups[names[c]]], 0)
        if n @ (np.mean(p, 0) - cen) < 0:                    # outward normal of the convex component
            n = -n
        for j in range(1, len(p) - 1):
            ftris.append((p[0], p[j], p[j + 1]))
            fcomp.append(c)
            fnorm.append(n)
    if not ftris:
        return []
    ft = np.asarray(ftris, float)
    fcomp = np.asarray(fcomp)
    area_c = np.bincount(fcomp, weights=0.5 * np.linalg.norm(np.cross(ft[:, 1] - ft[:, 0], ft[:, 2] - ft[:, 0]), axis=1),
                         minlength=len(names))
    e = np.stack([np.linalg.norm(ft[:, 1] - ft[:, 0], axis=1), np.linalg.norm(ft[:, 2] - ft[:, 1], axis=1),
                  np.linalg.norm(ft[:, 0] - ft[:, 2], axis=1)], 1).max(1)
    k = 2 ** np.ceil(np.log2(np.maximum(1, np.ceil(e / step)))).astype(int)
    fnorm = np.asarray(fnorm)
    pts_all, comp_all, nrm_all = [], [], []
    for kk in np.unique(k):
        idx = np.nonzero(k == kk)[0]
        ii, jj = np.meshgrid(np.arange(kk + 1), np.arange(kk + 1), indexing="ij")
        m = ii + jj <= kk
        u, v = (ii[m] / kk)[None, :, None], (jj[m] / kk)[None, :, None]
        a, b, c = ft[idx, 0][:, None, :], ft[idx, 1][:, None, :], ft[idx, 2][:, None, :]
        pts_all.append((a + u * (b - a) + v * (c - a)).reshape(-1, 3))
        comp_all.append(np.repeat(fcomp[idx], m.sum()))
        nrm_all.append(np.repeat(fnorm[idx], m.sum(), axis=0))
    pts = np.concatenate(pts_all)
    comp = np.concatenate(comp_all)
    nrm = np.concatenate(nrm_all)

    def seen_at(q):
        ix = np.floor(q / h).astype(np.int64)
        ukeys, inv = np.unique(_keys(ix), return_inverse=True)
        uix = np.stack([ukeys // 10 ** 10 - 50000, ukeys // 10 ** 5 % 10 ** 5 - 50000, ukeys % 10 ** 5 - 50000], 1)
        useen = np.zeros(len(ukeys), bool)
        for o in NEIGH:
            useen |= np.isin(_keys(uix + o), rkeys)
        return useen[inv.ravel()]
    seen = seen_at(pts)
    ext = np.array([min(np.ptp([geo.verts[i] for i in geo.groups[n]], 0)) for n in names])
    half = np.minimum(0.6, ext[comp] / 2)[:, None]
    full = np.minimum(0.6, ext[comp] * 0.95)[:, None]
    for t in (0.15, 0.3, None, "full"):           # a thick solid round thin glass / trim / a shelf back / boards on its
        rest = ~seen                              # far face is seen (D96): drawn inside or on the other side of the solid
        if rest.any():
            d = half[rest] if t is None else full[rest] if t == "full" else np.minimum(t, half[rest])
            seen[rest] = seen_at(pts[rest] - nrm[rest] * d)
    for b in getattr(geo, "kept_panes", ()):      # a broken window of a damaged building keeps its pane (vanilla);
        lo_, hi_ = np.array(b[:3]) - 0.05, np.array(b[3:]) + 0.05     # the generator records each one (D96)
        seen |= np.all((pts > lo_) & (pts < hi_), axis=1)
    rest = np.nonzero(~seen)[0]
    if len(rest):                                 # a joint against the next collision piece (a wall cut into cells) is
        q = pts[rest] + nrm[rest] * 0.02          # inside the wall: nobody sees it (D96)
        lo = np.array([np.min([geo.verts[i] for i in geo.groups[n]], 0) for n in names]) - 0.005
        hi = np.array([np.max([geo.verts[i] for i in geo.groups[n]], 0) for n in names]) + 0.005
        inner = np.zeros(len(rest), bool)
        for ci in range(len(names)):
            m = (comp[rest] != ci) & ~inner
            if m.any():
                inner[m] = np.all((q[m] > lo[ci]) & (q[m] < hi[ci]), axis=1)
        seen[rest[inner]] = True
    miss = ~seen
    zlo = np.array([min(geo.verts[i][2] for i in geo.groups[n]) for n in names])
    zhi = np.array([max(geo.verts[i][2] for i in geo.groups[n]) for n in names])
    top = (nrm[:, 2] > 0.9) & (pts[:, 2] >= zhi[comp] - 0.02)
    top_n = np.bincount(comp[top], minlength=len(names))
    top_seen = np.bincount(comp[top & seen], minlength=len(names))
    tot = np.bincount(comp, minlength=len(names))
    bad = np.bincount(comp[miss], minlength=len(names))
    out = []
    for ci, name in enumerate(names):
        if tot[ci] == 0:
            continue
        if zhi[ci] - zlo[ci] <= GHOST_LOW and top_n[ci] and top_seen[ci] >= 0.5 * top_n[ci]:
            continue                             # rail over bars, desk over legs: you see what stops you (D96)
        unseen = area_c[ci] * bad[ci] / tot[ci]
        lim = GHOST_WALL if zhi[ci] - zlo[ci] >= 2.0 else GHOST_AREA
        if unseen > lim and unseen > GHOST_FRAC * area_c[ci]:
            c = pts[miss & (comp == ci)].mean(0)
            out.append((name, round(float(unseen), 2), tuple(np.round(c, 2))))
    return out


def inside(poly, p):
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        if (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]) < -1e-9:
            return False
    return True


# ------------------------------------------------------------------ driver
_BUILDERS = {}


def builders():
    if not _BUILDERS:
        for modname in ("build_kit", "build_props", "build_landmarks", "build_creatures", "build_underground",
                        "build_vehicles", "build_streetprops", "build_city", "build_floors", "build_towera"):
            m = __import__(modname)
            mods = m.modules() if hasattr(m, "modules") else {"TowerA_" + k: v for k, v in m.MODULES.items()}
            for n, (fn, _p, _f) in mods.items():
                _BUILDERS[n] = fn
    return _BUILDERS


def export_units(lods):
    """The LOD lists the exporter writes for this model: the model itself plus any proxy parts (D96)."""
    import skygeo
    if hasattr(skygeo, "split_for_export"):
        return skygeo.split_for_export(list(lods), "x")
    return [("main", list(lods))]


def scan(name, checks):
    t = time.time()
    lods = builders()[name]()
    import zfix
    zfix.resolve_lods(lods)                      # what export_p3d writes (D96)
    deep = []
    for l in lods:
        worst = [(lay, size, mat) for lay, size, mat in getattr(l, "zfix_layer_map", {}).values()
                 if lay > (ZF_MAX_LAYERS_DEBRIS if mat in DEBRIS and size < 0.8 else ZF_MAX_LAYERS)]
        if worst:
            deep.append((l.name, max(worst)))
    res = [l for l in lods if l.lod == LOD_RES]
    fails, notes = [], []
    if "zfight" in checks:
        for l in res:
            h = zfight(l)
            if h:
                tot = sum(a for a, *_ in h)
                h.sort(reverse=True)
                fails.append(("zfight", "%s %s: %d overlapping coplanar pairs (%.2f m2), largest %.3f m2 %s/%s at %s"
                              % (name, l.name, len(h), tot, h[0][0], h[0][1], h[0][2], h[0][3])))
    for ln, (lay, size, mat) in deep:          # a part pushed this far out is a visible step: fix it at the source
        fails.append(("zfight", "%s %s: z-fight layering pushed a %.2f m %s part out %d layers (%.0f mm) - fix the overlap "
                      "in the generator" % (name, ln, size, mat, lay, lay * zfix.DELTA * 1000)))
    if "smear" in checks:
        for l in res:
            h = smear(l)
            if h:
                h.sort(reverse=True)
                mats = {}
                for e, m, _c in h:
                    mats[m] = mats.get(m, 0) + 1
                fails.append(("smear", "%s %s: %d smeared faces, widest %.2f m (%s at %s); by material %s"
                              % (name, l.name, len(h), h[0][0], h[0][1], h[0][2], sorted(mats.items(), key=lambda x: -x[1])[:5])))
    if "vertices" in checks:
        for unit, ls in export_units(lods):
            for l in ls:
                if l.lod == LOD_RES:
                    nv = render_vertices(l)
                    if nv > VERTEX_LIMIT:
                        fails.append(("vertices", "%s %s %s: %d render vertices > %d" % (name, unit, l.name, nv, VERTEX_LIMIT)))
    if "ghost" in checks:
        geo = next((l for l in lods if l.lod == LOD_GEOMETRY), None)
        r0 = min(res, key=lambda l: l.distance) if res else None
        if geo is not None and r0 is not None:
            for comp, a, c in ghosts(geo, r0):
                fails.append(("ghost", "%s %s: %.2f m2 of collision with no render surface within %.2f m, around %s"
                              % (name, comp, a, GHOST_DIST, c)))
    return name, fails, notes, time.time() - t


def selftest():
    from skygeo import Lod
    ok = True

    def chk(c, m):
        nonlocal ok
        print("  %s %s" % ("ok  " if c else "FAIL", m))
        ok = ok and c
    a = Lod("res0", LOD_RES)
    a.box(0, 1, 0, 0.2, 0, 1, mat="paint", uv=None)
    a.quad([(0.2, -0.0005, 0.2), (0.8, -0.0005, 0.2), (0.8, -0.0005, 0.8), (0.2, -0.0005, 0.8)], (0, -1, 0), "decal_grime")
    chk(len(zfight(a)) == 1, "decal 0.5 mm off a wall is a z-fight")
    b = Lod("res0", LOD_RES)
    b.box(0, 1, 0, 0.2, 0, 1, mat="paint")
    b.quad([(0.2, -0.004, 0.2), (0.8, -0.004, 0.2), (0.8, -0.004, 0.8), (0.2, -0.004, 0.8)], (0, -1, 0), "decal_grime")
    chk(not zfight(b), "decal 4 mm proud is not")
    c = Lod("res0", LOD_RES)
    c.box(0, 1, 0, 0.2, 0, 1, mat="paint")
    c.box(1, 2, 0, 0.2, 0, 1, mat="stone")
    chk(not zfight(c), "two wall pieces side by side (touching edges) are not")
    d = Lod("res0", LOD_RES)
    d.box(0, 1, 0, 0.2, 0, 1, mat="paint")
    d.box(0.5, 1.5, 0, 0.3, 0, 1, mat="stone")
    chk(len(zfight(d)) >= 1, "two overlapping boxes sharing a front plane are")
    e = Lod("res0", LOD_RES)
    e.quad([(0, 0, 0), (1, 0, 0), (1, 0.15, 0), (0, 0.15, 0)], (0, 0, 1), "paint", uv=lambda pts, n: [(p[0], 0.5) for p in pts])
    chk(len(smear(e)) == 1, "a 15 cm deep face with constant V is smeared")
    f = Lod("res0", LOD_RES)
    f.quad([(0, 0, 0), (1, 0, 0), (1, 0.15, 0), (0, 0.15, 0)], (0, 0, 1), "paint", uv=lambda pts, n: [(p[0], p[1]) for p in pts])
    chk(not smear(f), "a properly mapped face is not")
    g = Lod("geo", LOD_GEOMETRY)
    g.box(0, 1, 0, 1, 0, 1)
    g.box(3, 4, 0, 1, 0, 1)
    r = Lod("res0", LOD_RES)
    r.box(0, 1, 0, 1, 0, 1, mat="paint")
    gh = ghosts(g, r)
    chk(len(gh) == 1 and gh[0][0] == "Component02", "a collision box with no render box is a ghost, the matched one is not")
    g2 = Lod("geo", LOD_GEOMETRY)
    g2.box(0, 1, 0, 1, 0, 1)
    r2 = Lod("res0", LOD_RES)
    r2.box(-0.05, 1.05, -0.05, 1.05, -0.05, 1.05, mat="paint")                  # render 5 cm proud: still seen
    chk(not ghosts(g2, r2), "a collision box 5 cm inside its render box is not a ghost")
    g3 = Lod("geo", LOD_GEOMETRY)
    g3.box(0, 2, 0, 0.08, 0, 1.05)                                              # guard rail
    g3.box(4, 6, 0, 0.08, 0, 2.5)                                               # wall, only its top drawn
    r3 = Lod("res0", LOD_RES)
    r3.box(0, 2, 0, 0.08, 0.99, 1.05, mat="metal")
    r3.box(4, 6, 0, 0.08, 2.44, 2.5, mat="metal")
    gh3 = ghosts(g3, r3)
    chk([c for c, *_ in gh3] == ["Component02"], "a rail over bars is not a ghost, a 2.5 m wall with only a top is")
    print("QUALITY SELFTEST:", "PASS" if ok else "FAILED")
    return ok


def main():
    argv = sys.argv[1:]
    if "--selftest" in argv:
        return 0 if selftest() else 1
    if not selftest():
        return 1
    checks = argv[argv.index("--checks") + 1].split(",") if "--checks" in argv else ["zfight", "smear", "vertices", "ghost"]
    b = builders()
    names = argv[argv.index("--only") + 1].split(",") if "--only" in argv else [n for n in b if n in S.KIT or n.startswith("TowerA_")]
    jobs = int(argv[argv.index("--jobs") + 1]) if "--jobs" in argv else 1
    t0 = time.time()
    fails = []
    if jobs > 1:
        import multiprocessing as mp
        results = []
        with mp.get_context("fork").Pool(jobs, maxtasksperchild=1) as pool:     # fresh worker per model (memory)
            for r in pool.imap_unordered(_scan, [(n, checks) for n in names]):
                results.append(r)
                if "--report" in argv:
                    print("  done %d/%d %s (%.0fs) %d" % (len(results), len(names), r[0], r[3], len(r[1])), flush=True)
    else:
        results = [scan(n, checks) for n in names]
    by = {}
    for n, f, _notes, dt in sorted(results):
        for kind, line in f:
            if (n, kind) in ACCEPTED:
                print("  accepted", line, "-", ACCEPTED[(n, kind)])
                continue
            fails.append(line)
            by[kind] = by.get(kind, 0) + 1
        if "--report" in argv:
            print("  scanned %s (%.1fs)%s" % (n, dt, " - %d" % len(f) if f else ""), flush=True)
    for f in fails:
        print("  FAIL", f)
    print("QUALITY TEST: %s (%d models, %s, %.0fs)" % ("%d FAILED" % len(fails) if fails else "PASS", len(names),
                                                     by or "clean", time.time() - t0))
    return 1 if fails else 0


def _scan(a):
    return scan(*a)


if __name__ == "__main__":
    sys.exit(main())
