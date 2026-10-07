"""Gate (D82, hull test 2b): slits in Fire Geometry where the model looks solid, any part shape (the D74 hull
test only checks axis-aligned boxes). The Fire LOD and the opaque Res0 are projected along X, Y and Z onto a
1 cm grid; a pixel no Fire part covers, that a 5 cm closing of the Fire fills, and that Res0 draws solid is a
gap bullets pass through while the player sees a wall. Gaps the render shows open (bars, A-frame legs) are not
deceptive and pass. Designed openings are wider than 5 cm; door leaves are skipped (they need clearance).

    python assets/blender/test_slits.py [--only A,B] [--city] [--report]
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
MIN_PX = 30        # ignore specks: a slit must cover at least this many pixels (30 cm2)
ACCEPTED = {        # name -> reason (reviewed)
    "Fair_FerrisWheel": "the wheel rim and spokes are render-only tubes (24 cm rim, 32-segment rings; collision "
                        "would add hundreds of parts); where they cross the A-frame legs the test sees a covered "
                        "gap. Open lattice 1.5-28 m up, no cover value (D82)",
}


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
    solid = np.asarray(raster(R[:, :, o], lo, w, h).filter(ImageFilter.MinFilter(k))) > 0
    gap = (np.asarray(closed) > 0) & ~hit & solid
    if gap.sum() < MIN_PX:
        return []
    ys, xs = np.nonzero(gap)
    return [(int(gap.sum()), (round(float(lo[0] + xs.min() * PX), 2), round(float(lo[1] + ys.min() * PX), 2)),
             (round(float(lo[0] + xs.max() * PX), 2), round(float(lo[1] + ys.max() * PX), 2)))]


def main():
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
                (print("  accepted", line, "-", ACCEPTED[n]) if n in ACCEPTED else fails.append(line))
    # city / module findings are report-only for now (D82: 3-5 cm render-vs-Fire mismatches at partition ends, seen
    # through open windows; triage in D83); kit models block
    advisory = [f for f in fails if S.KIT.get(f.split(":")[0], {}).get("city")
                or S.KIT.get(f.split(":")[0], {}).get("category") in ("floor", "roof")]
    fails = [f for f in fails if f not in advisory]
    for f in advisory:
        print("  ADVISORY", f)
    for f in fails:
        print("  FAIL", f)
    print("SLIT TEST: %s (%d models, %d advisory, %d large views skipped, %.0fs)" % (
        "%d FAILED" % len(fails) if fails else "PASS", len(names), len(advisory), skipped, time.time() - t0))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
