"""Gate (D82, hull test 2b): slits in Fire Geometry where the model looks solid, any part shape (the D74 hull
test only checks axis-aligned boxes). The Fire LOD and the opaque Res0 are projected along X, Y and Z onto a
1 cm grid; a pixel no Fire part covers, that a 5 cm closing of the Fire fills, and that Res0 draws solid is a
gap bullets pass through while the player sees a wall. Gaps the render shows open (bars, A-frame legs) are not
deceptive and pass. Designed openings are wider than 5 cm; door leaves are skipped (they need clearance).

    python assets/blender/test_slits.py [--only A,B] [--city] [--report] [--selftest]
"""
import os
import sys
import time

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import skyspec as S  # noqa: E402

PX = 0.01          # m per pixel
GAP = 0.05         # widest gap that counts as a slit (= D74 limit for props)
SOLID = 0.07       # D83: the render must be wider than this to look like cover (6 cm window frames and jambs in an
                   # open window are detail - thin-detail rule - not a wall hiding a slit)
MIN_PX = 30        # ignore specks: a slit must cover at least this many pixels (30 cm2)
ACCEPTED = {        # name -> reason (reviewed)
    "Fair_FerrisWheel": "the wheel rim and spokes are render-only tubes (24 cm rim, 32-segment rings; collision "
                        "would add hundreds of parts); where they cross the A-frame legs the test sees a covered "
                        "gap. Open lattice 1.5-28 m up, no cover value (D82)",
    ("City_OfficeTall_Damaged", "X", (-9.05, 0.0, -8.9, 2.65), 400): "curtain-wall mullions are render-only aluminium (2 x 8 cm wide, 16 cm deep: under the "
                               "0.2 m thin-detail rule, no cover in reality either); with a broken shopfront pane the "
                               "corner mullion is seen end-on between Fire panes 3 cm apart. Fire on every mullion "
                               "would add ~2 parts per bay and storey (D83)",
}


def _accepted(n, an, r):
    """Reason if the finding is accepted: a whole model by name (render-only lattices), or a (name, axis, box
    (u0, v0, u1, v1), max cm2) key that covers exactly this finding (sec review D83 M: never a whole model)."""
    if n in ACCEPTED:
        return ACCEPTED[n]
    area, (u0, v0), (u1, v1) = r
    for k, why in ACCEPTED.items():
        if isinstance(k, tuple) and k[0] == n and k[1] == an and area <= k[3] and \
                k[2][0] <= u0 and k[2][1] <= v0 and u1 <= k[2][2] and v1 <= k[2][3]:
            return why
    return None


def fire_tris(lod):
    doors = set()
    for g, v in lod.groups.items():
        if not g.startswith("Component"):
            doors |= set(v)
    out = []
    for idx, _m, _uv in lod.faces:
        if doors and any(i in doors for i in idx):
            continue
        p = [lod.verts[i] for i in idx]
        for k in range(1, len(p) - 1):
            out.append((p[0], p[k], p[k + 1]))
    return np.array(out, np.float64).reshape(-1, 3, 3)


def raster(P, lo, w, h):
    img = Image.new("L", (int(w), int(h)), 0)
    d = ImageDraw.Draw(img)
    for tri in P:
        d.polygon([((x - lo[0]) / PX, (y - lo[1]) / PX) for x, y in tri], fill=255, outline=255)
    return img


DEPTH = 0.1        # D83: Fire / render parts within the render's solid span along the ray (front face to back face,
#                    so a Fire box set back inside a thick wall counts - sec review M) +- this bound a slit
WIN = 12           # local window half-size (px) for the depth check
SAMPLES = 40       # gap pixels checked per connected gap region (sec review H: per region, never across regions)


class _Near:
    """Triangle bounds precomputed once per view: projected box and depth range."""

    def __init__(self, T, o, axis):
        P = T[:, :, o]
        self.T, self.u0, self.u1 = T, P[:, :, 0].min(1), P[:, :, 0].max(1)
        self.v0, self.v1 = P[:, :, 1].min(1), P[:, :, 1].max(1)
        self.d0, self.d1 = T[:, :, axis].min(1), T[:, :, axis].max(1)

    def at(self, u, v):
        r = (WIN + 1) * PX
        return np.nonzero((self.u0 <= u + r) & (self.u1 >= u - r) & (self.v0 <= v + r) & (self.v1 >= v - r))[0]

    def depth(self, idx, a, b):
        return self.T[idx[(self.d0[idx] <= b) & (self.d1[idx] >= a)]]


def _gap_at(F, Rl, o, u, v):
    k = int(round(GAP / PX)) | 1
    lo = np.array([u - WIN * PX, v - WIN * PX])
    n = 2 * WIN + 1
    if not len(Rl):
        return False
    hit = raster(F[:, :, o], lo, n, n) if len(F) else Image.new("L", (n, n), 0)
    closed = hit.filter(ImageFilter.MaxFilter(k)).filter(ImageFilter.MinFilter(k))
    solid = raster(Rl[:, :, o], lo, n, n).filter(ImageFilter.MinFilter(int(round(SOLID / PX)) | 1))
    c = (WIN, WIN)
    return hit.getpixel(c) == 0 and closed.getpixel(c) > 0 and solid.getpixel(c) > 0


def _regions(gap):
    """8-connected regions of a boolean image -> list of (ys, xs) arrays (flood fill; no scipy on the build box)."""
    pts = set(zip(*np.nonzero(gap)))
    out = []
    while pts:
        st = [pts.pop()]
        comp = []
        while st:
            y, x = st.pop()
            comp.append((y, x))
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    q = (y + dy, x + dx)
                    if q in pts:
                        pts.remove(q)
                        st.append(q)
        a = np.array(comp)
        out.append((a[:, 0], a[:, 1]))
    return out


def _spans(Rc, axis, u, v):
    """Solid render spans along the ray through (u, v): entering face to exiting face (open render meshes pair
    each entering hit with the next exit, as in the concealment gate)."""
    from test_conceal import intervals
    if not len(Rc):
        return []
    lo, hi = Rc.reshape(-1, 3).min(0), Rc.reshape(-1, 3).max(0)
    return [(float(a), float(b)) for a, b in intervals(Rc, axis, u, v, lo, hi)]


def confirm(T, R, axis, gap, lo):
    """Keep projected gap regions that are still a gap among the Fire and render parts at the depth of a render
    surface covering them. A whole-model projection pairs parts metres apart (a stair wall and a gable pier)
    around a thin frame between them; those are not slits (D83 triage of the 14 city advisories). Each connected
    gap region is sampled on its own and kept whole if any sample confirms (sec review H)."""
    o = [i for i in range(3) if i != axis]
    NF, NR = _Near(T, o, axis), _Near(R, o, axis)
    out = np.zeros_like(gap)
    for ys, xs in _regions(gap):
        idx = np.linspace(0, len(ys) - 1, min(len(ys), SAMPLES)).round().astype(int)
        for j in idx:
            u, v = lo[0] + (xs[j] + 0.5) * PX, lo[1] + (ys[j] + 0.5) * PX
            fi, ri = NF.at(u, v), NR.at(u, v)
            cover = ri[(NR.u0[ri] <= u) & (NR.u1[ri] >= u) & (NR.v0[ri] <= v) & (NR.v1[ri] >= v)]
            spans = _spans(R[cover], axis, u, v) or \
                sorted({(round(float(NR.d0[i]), 2), round(float(NR.d1[i]), 2)) for i in cover})
            if any(_gap_at(NF.depth(fi, d0 - DEPTH, d1 + DEPTH), NR.depth(ri, d0 - DEPTH, d1 + DEPTH), o, u, v)
                   for d0, d1 in spans):
                out[ys, xs] = True
                break
    return out


def slits(T, axis, R):
    o = [i for i in range(3) if i != axis]
    P = T[:, :, o]
    lo = P.reshape(-1, 2).min(0) - 2 * GAP
    hi = P.reshape(-1, 2).max(0) + 2 * GAP
    w, h = np.maximum(1, np.ceil((hi - lo) / PX).astype(int))
    if w * h > 9_000_000:                                   # > 30 x 30 m: landmarks use the voxel tests instead
        return None
    img = raster(P, lo, w, h)
    k = int(round(GAP / PX)) | 1
    closed = img.filter(ImageFilter.MaxFilter(k)).filter(ImageFilter.MinFilter(k))
    hit = np.asarray(img) > 0
    # looks solid: the render eroded by the slit width, so thin render-only bars (spokes, wires) crossing an open
    # gap do not count as a surface; a wall or panel wider than 5 cm does
    solid = np.asarray(raster(R[:, :, o], lo, w, h).filter(ImageFilter.MinFilter(int(round(SOLID / PX)) | 1))) > 0
    gap = (np.asarray(closed) > 0) & ~hit & solid
    if gap.sum() < MIN_PX:
        return []
    gap = confirm(T, R, axis, gap, lo)                        # D83: the gap must exist at the depth of the surface
    if gap.sum() < MIN_PX:
        return []
    ys, xs = np.nonzero(gap)
    return [(int(gap.sum()), (round(float(lo[0] + xs.min() * PX), 2), round(float(lo[1] + ys.min() * PX), 2)),
             (round(float(lo[0] + xs.max() * PX), 2), round(float(lo[1] + ys.max() * PX), 2)))]


def _box(x0, x1, y0, y1, z0, z1):
    v = [(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
    out = []
    c = np.mean(v, 0)
    for a, b, cc, d in ((0, 1, 3, 2), (4, 5, 7, 6), (0, 1, 5, 4), (2, 3, 7, 6), (0, 2, 6, 4), (1, 3, 7, 5)):
        q = [v[a], v[b], v[cc], v[d]]
        n = np.cross(np.subtract(q[1], q[0]), np.subtract(q[2], q[0]))
        if np.dot(n, np.mean(q, 0) - c) < 0:                  # outward faces, like the exported models
            q = q[::-1]
        out += [(q[0], q[1], q[2]), (q[0], q[2], q[3])]
    return out


def selftest():
    """Synthetic cases (D83): a 3 cm slit between two Fire boxes under one render wall must be found; a thin
    render frame between Fire parts 8 m apart in depth (the D82 projection artefact) must not."""
    F = np.array(_box(0, 0.2, -1, -0.015, 0, 2) + _box(0, 0.2, 0.015, 1, 0, 2))
    R = np.array(_box(0, 0.2, -1, 1, 0, 2))
    F2 = np.array(_box(-9, -8.7, -0.675, 0.675, 0, 2) + _box(-1.45, -1.3, -5.7, -0.73, 0, 2))
    R2 = np.array(_box(-8.93, -8.87, -0.735, -0.675, 0, 2) + _box(-9, -8.7, -0.675, 0.675, 0, 2))
    # a real slit next to a large artefact region in the same view must still be found (sec review H)
    F3 = np.concatenate([F2, F + np.array([0.0, 3.0, 0.0])])
    R3 = np.concatenate([R2, R + np.array([0.0, 3.0, 0.0])])
    # Fire set back 0.3 m behind the visible render face of a thick wall (sec review M)
    F4 = np.array(_box(0.3, 0.5, -1, -0.015, 0, 2) + _box(0.3, 0.5, 0.015, 1, 0, 2))     # out of reach of both faces
    R4 = np.array(_box(0, 0.8, -1, 1, 0, 2))
    ok = bool(slits(F, 0, R)) and not slits(F2, 0, R2) and bool(slits(F3, 0, R3)) and bool(slits(F4, 0, R4))
    print("SLIT SELFTEST:", "PASS" if ok else "FAILED")
    return 0 if ok else 1


def main():
    if "--selftest" in sys.argv[1:]:
        return selftest()
    builders = {}
    for modname in ("build_kit", "build_props", "build_landmarks", "build_creatures", "build_underground", "build_vehicles",
                    "build_streetprops", "build_city", "build_floors"):
        m = __import__(modname)
        for n, (fn, _p, _f) in m.modules().items():
            builders[n] = fn
    argv = sys.argv[1:]
    city = "--city" in argv                                    # city buildings + floor / roof modules (sec D82 M6)
    names = argv[argv.index("--only") + 1].split(",") if "--only" in argv else \
        [n for n in builders if n in S.KIT and S.KIT[n]["collide"]
         and (city or (not S.KIT[n].get("city") and S.KIT[n]["category"] not in ("floor", "roof")))]
    t0, fails, skipped = time.time(), [], 0
    for n in names:
        lods = {l.name: l for l in builders[n]()}
        if "fire" not in lods:
            continue
        T = fire_tris(lods["fire"])
        if not len(T):
            continue
        sys.path.insert(0, HERE)
        from test_conceal import tris as opaque                       # same see-through list as the concealment gate
        R = opaque(lods["res0"])
        for axis, an in ((0, "X"), (1, "Y"), (2, "Z")):
            r = slits(T, axis, R)
            if r is None:
                skipped += 1
                continue
            if r:
                line = "%s: %d cm2 of slits seen along %s, around %s..%s (projected)" % (n, r[0][0], an, r[0][1], r[0][2])
                why = _accepted(n, an, r[0])
                (print("  accepted", line, "-", why) if why else fails.append(line))
    # D83: city and module findings block too (the depth check removed the D82 projection artefacts)
    advisory = []
    for f in fails:
        print("  FAIL", f)
    print("SLIT TEST: %s (%d models, %d advisory, %d large views skipped, %.0fs)" % (
        "%d FAILED" % len(fails) if fails else "PASS", len(names), len(advisory), skipped, time.time() - t0))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
