"""D62 creature assets (ROADMAP ideas 5, 8, 9, 11) - plain Python or any Blender.

    python build_creatures.py -- --out <mods/SKY_Skyline/addons> [--only Kennel,RatNest]

DayZ animals need a skeleton, animations and an AI graph made in Workbench; the procedural pipeline
cannot make those (D62). So the creatures here are static, carried by server scripts:
- Kennel (item, sky_items): a deployable wooden doghouse with its guard dog lying in front. Placed like a
  vanilla sea chest; it guards its stash while the owner is offline and barks at intruders (SKY_Kennel.c).
- RatNest (kit, sky_street): a heap of rags, paper and gnawed rubbish with rats on and around it; the
  server bites players who stand in it and gnaws base parts nearby (SKY_Rats.c).
- HorseCarcass (kit, sky_street): a dead horse, half hide, half bone - horses are blocked (no rig), this
  is the only horse in the city.
Frame: front = -Y, origin = footprint centre at ground level.
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import build_city as C  # noqa: E402
import detail as DT  # noqa: E402
import skyspec as S  # noqa: E402
from build_kit import KIT_MATS  # noqa: E402
from skygeo import (LOD_FIREGEO, LOD_GEOMETRY, LOD_MEMORY, LOD_RES, LOD_SHADOW, LOD_VIEWGEO, Lod, UVBand,  # noqa: E402
                    UVWorld, run_cli)

kw_for, h01 = C.kw_for, C.h01
UV_WALNUT, UV_RUBBLE = C.UV_WALNUT, C.UV_RUBBLE
FUR = UVBand(S.MATERIALS["fur"]["bands"]["tan"], 0.5)                 # D65: procedural fur sheet (gen_textures.fur)
FUR_SADDLE = UVBand(S.MATERIALS["fur"]["bands"]["saddle"], 0.5)
FUR_GREY = UVBand(S.MATERIALS["fur"]["bands"]["rat"], 0.25)
FUR_HORSE = UVBand(S.MATERIALS["fur"]["bands"]["chestnut"], 1.0)
UV_TRASH = UVWorld(S.MATERIALS["trash"]["sheet_m"])
DARK = DT.paint_uv("slate")
BONE = DT.paint_uv("white")


def limb(lod, p0, p1, r0, r1, n=8, mat=None, uv=None):
    """Convex frustum between two points (body segments, legs, necks, tails)."""
    d = [p1[i] - p0[i] for i in range(3)]
    ln = math.sqrt(sum(v * v for v in d)) or 1.0
    d = [v / ln for v in d]
    a = (0, 0, 1) if abs(d[2]) < 0.9 else (1, 0, 0)
    u = [d[1] * a[2] - d[2] * a[1], d[2] * a[0] - d[0] * a[2], d[0] * a[1] - d[1] * a[0]]
    un = math.sqrt(sum(v * v for v in u))
    u = [v / un for v in u]
    w = [d[1] * u[2] - d[2] * u[1], d[2] * u[0] - d[0] * u[2], d[0] * u[1] - d[1] * u[0]]
    verts = []
    for (p, r) in ((p0, r0), (p1, r1)):
        for k in range(n):
            c, s = math.cos(2 * math.pi * k / n), math.sin(2 * math.pi * k / n)
            verts.append(tuple(p[i] + r * (c * u[i] + s * w[i]) for i in range(3)))
    faces = [tuple(range(n)), tuple(range(n, 2 * n))] + [(k, (k + 1) % n, n + (k + 1) % n, n + k) for k in range(n)]
    lod.solid(verts, faces, mat, uv)


def blob(lod, c, rx, ry, rz, n=8, mat=None, uv=None):
    """Squashed octagonal bipyramid-ish ellipsoid (3 rings): heads, haunches, rubbish lumps."""
    verts = []
    for (z, f) in ((-0.7, 0.72), (0.0, 1.0), (0.7, 0.72)):
        for k in range(n):
            a = 2 * math.pi * k / n
            verts.append((c[0] + rx * f * math.cos(a), c[1] + ry * f * math.sin(a), c[2] + rz * z))
    verts += [(c[0], c[1], c[2] - rz), (c[0], c[1], c[2] + rz)]
    b, t = 3 * n, 3 * n + 1
    faces = []
    for ring in range(2):
        for k in range(n):
            i0, i1 = ring * n + k, ring * n + (k + 1) % n
            faces.append((i0, i1, i1 + n, i0 + n))
    faces += [(k, (k + 1) % n, b) for k in range(n)] + [(2 * n + k, 2 * n + (k + 1) % n, t) for k in range(n)]
    lod.solid(verts, faces, mat, uv)


def dog(lod, x, y, z, yaw=0.0, detail=True, mat="fur", uv=FUR):
    """German-shepherd-sized dog lying on its belly, head up, facing -Y (rotated by yaw)."""
    ca, sa = math.cos(yaw), math.sin(yaw)

    def P(px, py, pz):
        return (x + px * ca - py * sa, y + px * sa + py * ca, z + pz)
    mid = detail == "mid"                                                           # D73: mid LOD (kennel Res1)
    if mid:
        detail = False
    n = 8 if detail else (6 if mid else 5)
    limb(lod, P(0, 0.42, 0.2), P(0, -0.12, 0.24), 0.17, 0.19, n, mat, uv)          # torso
    blob(lod, P(0, 0.42, 0.18), 0.18, 0.16, 0.16, n, mat, uv)                       # haunch
    if detail:                                                                       # dark saddle (shepherd)
        limb(lod, P(0, 0.35, 0.31), P(0, -0.05, 0.36), 0.1, 0.11, n, "fur", FUR_SADDLE)
    limb(lod, P(0, -0.12, 0.3), P(0, -0.3, 0.48), 0.1, 0.075, n, mat, uv)           # neck
    blob(lod, P(0, -0.34, 0.5), 0.09, 0.11, 0.08, n, mat, uv)                       # skull
    if mid:                                                                          # muzzle, ears, legs, tail: low sides
        limb(lod, P(0, -0.42, 0.48), P(0, -0.55, 0.45), 0.05, 0.035, 4, mat, uv)
        for s in (-1, 1):
            limb(lod, P(s * 0.05, -0.31, 0.55), P(s * 0.07, -0.29, 0.66), 0.035, 0.008, 3, mat, uv)
            limb(lod, P(s * 0.1, -0.12, 0.08), P(s * 0.1, -0.42, 0.04), 0.045, 0.035, 4, mat, uv)
            limb(lod, P(s * 0.16, 0.42, 0.08), P(s * 0.13, 0.18, 0.04), 0.05, 0.035, 4, mat, uv)
        limb(lod, P(0, 0.56, 0.18), P(0.18, 0.8, 0.04), 0.045, 0.02, 4, mat, uv)
        return
    if not detail:
        return
    limb(lod, P(0, -0.42, 0.48), P(0, -0.55, 0.45), 0.05, 0.035, 6, mat, uv)        # muzzle
    blob(lod, P(0, -0.565, 0.455), 0.022, 0.018, 0.018, 5, "paint", DARK)           # nose
    for s in (-1, 1):
        limb(lod, P(s * 0.05, -0.31, 0.55), P(s * 0.07, -0.29, 0.66), 0.035, 0.008, 4, mat, uv)    # ears
        limb(lod, P(s * 0.1, -0.12, 0.08), P(s * 0.1, -0.42, 0.04), 0.045, 0.035, 6, mat, uv)      # forelegs
        limb(lod, P(s * 0.16, 0.42, 0.08), P(s * 0.13, 0.18, 0.04), 0.05, 0.035, 6, mat, uv)       # hind legs
        blob(lod, P(s * 0.06, -0.39, 0.5), 0.012, 0.01, 0.01, 4, "paint", DARK)    # eyes
    limb(lod, P(0, 0.56, 0.18), P(0.18, 0.8, 0.04), 0.045, 0.02, 6, mat, uv)        # tail on the ground


def rat(lod, x, y, z, yaw, detail=True):
    ca, sa = math.cos(yaw), math.sin(yaw)

    def P(px, py, pz):
        return (x + px * ca - py * sa, y + px * sa + py * ca, z + pz)
    blob(lod, P(0, 0.0, 0.04), 0.035, 0.08, 0.035, 6 if detail else 4, "fur", FUR_GREY)
    if detail:
        limb(lod, P(0, -0.07, 0.045), P(0, -0.13, 0.035), 0.025, 0.008, 5, "fur", FUR_GREY)
        limb(lod, P(0, 0.07, 0.03), P(0.05, 0.22, 0.005), 0.008, 0.003, 4, "paint", DT.paint_uv("terracotta"))


def nest_rats(name, count, r):
    out = []
    for i in range(count):
        a = 2 * math.pi * h01(name, "ra", i)
        d = r * (0.3 + 0.9 * h01(name, "rd", i))
        out.append((d * math.cos(a), d * math.sin(a), 2 * math.pi * h01(name, "ry", i)))
    return out


# ================================================================== kennel (item)
def build_kennel():
    """1.0 x 1.3 m wooden doghouse (pitched felt roof, arched door, name board), a dog lying in front,
    a chain to a ring bolt, an enamel bowl. Item LODs (Res0..Res2, Geometry with mass, Fire, View, Memory
    with ce_center / ce_radius like the keycard and the vanilla sea chest it inherits from)."""
    r0, r1, r2 = Lod("res0", LOD_RES, 0.0), Lod("res1", LOD_RES, 1.0), Lod("res2", LOD_RES, 2.0)
    geo, fire, view, mem = Lod("geo", LOD_GEOMETRY), Lod("fire", LOD_FIREGEO), Lod("view", LOD_VIEWGEO), Lod("mem", LOD_MEMORY)
    shadow = Lod("shadow", LOD_SHADOW)
    hx, y0, y1, zw, zr = 0.5, 0.0, 1.0, 0.75, 1.05                  # house: x +-0.5, y 0..1.0, walls 0.75, ridge 1.05
    wood = UV_WALNUT
    for L in (r0, r1):
        L.box(-hx, hx, y0, y1, 0.0, 0.06, mat="wood", uv=wood)                       # floor
        L.box(-hx, hx, y1 - 0.04, y1, 0.06, zw, mat="wood", uv=wood)                 # back
        for sx in (-1, 1):
            L.box(sx * hx - (0.04 if sx > 0 else 0), sx * hx + (0.04 if sx < 0 else 0), y0, y1, 0.06, zw, mat="wood", uv=wood)
        L.box(-hx, -0.17, y0, y0 + 0.04, 0.06, zw, mat="wood", uv=wood)              # front, door gap
        L.box(0.17, hx, y0, y0 + 0.04, 0.06, zw, mat="wood", uv=wood)
        L.box(-0.17, 0.17, y0, y0 + 0.04, 0.55, zw, mat="wood", uv=wood)
        for s in ((-1, 1) if L is r1 else ()):                                        # Res1 roof slopes (Res0: shingles)
            L.solid([(0, y0 - 0.08, zr), (s * (hx + 0.08), y0 - 0.08, zw - 0.06), (0, y1 + 0.08, zr), (s * (hx + 0.08), y1 + 0.08, zw - 0.06),
                     (0, y0 - 0.08, zr + 0.03), (s * (hx + 0.08), y0 - 0.08, zw - 0.03), (0, y1 + 0.08, zr + 0.03),
                     (s * (hx + 0.08), y1 + 0.08, zw - 0.03)],
                    [(0, 1, 3, 2), (4, 5, 7, 6), (0, 1, 5, 4), (2, 3, 7, 6), (0, 2, 6, 4), (1, 3, 7, 5)], "paint", DARK)
    for L in (r0, r1):                                                               # gables (front + back)
        for (ya, yb) in ((y0, y0 + 0.04), (y1 - 0.04, y1)):
            L.solid([(-hx, ya, zw), (hx, ya, zw), (0, ya, zr), (-hx, yb, zw), (hx, yb, zw), (0, yb, zr)],
                    [(0, 1, 2), (3, 4, 5), (0, 1, 4, 3), (1, 2, 5, 4), (2, 0, 3, 5)], "wood", wood)
    r0.box(-0.22, 0.22, y0 - 0.01, y0, 0.78, 0.9, mat="paint", uv=DT.paint_uv("beige"))   # name board
    # D70 close-up pass (ASSET_QUALITY_GUIDE section 8): wooden shingle courses with a ridge board, corner
    # boards, a door frame, straw spilling out of the door and a gnawed bone by the bowl.
    for sgn in (-1, 1):
        for c in range(3):                                                            # 3 overlapping courses per slope
            t0, t1 = c / 3.0, (c + 1) / 3.0 + 0.06
            xa, xb = sgn * (hx + 0.08) * (1 - t0), sgn * (hx + 0.08) * (1 - min(t1, 1.0))
            za, zb = (zw - 0.06) + (zr - zw + 0.06) * t0, (zw - 0.06) + (zr - zw + 0.06) * min(t1, 1.0)
            th = 0.025
            r0.solid([(xa, y0 - 0.08, za), (xb, y0 - 0.08, zb), (xa, y1 + 0.08, za), (xb, y1 + 0.08, zb),
                      (xa, y0 - 0.08, za + th), (xb, y0 - 0.08, zb + th), (xa, y1 + 0.08, za + th), (xb, y1 + 0.08, zb + th)],
                     [(0, 1, 3, 2), (4, 5, 7, 6), (0, 1, 5, 4), (2, 3, 7, 6), (0, 2, 6, 4), (1, 3, 7, 5)], "wood", UV_WALNUT)
    r0.box(-0.04, 0.04, y0 - 0.1, y1 + 0.1, zr - 0.01, zr + 0.06, mat="wood", uv=wood)      # ridge board
    for sx in (-1, 1):                                                                # corner boards
        for yy in (y0, y1):
            r0.box(sx * hx - 0.03, sx * hx + 0.03, yy - 0.03, yy + 0.03, 0.0, zw, mat="wood", uv=wood)
    for xx in (-0.19, 0.17):                                                          # door frame
        r0.box(xx, xx + 0.02, y0 - 0.025, y0, 0.06, 0.57, mat="wood", uv=wood)
    r0.box(-0.19, 0.19, y0 - 0.025, y0, 0.55, 0.58, mat="wood", uv=wood)
    for i in range(6):                                                                # straw spilling out
        a = 0.6 * (h01("Kennel", "straw", i) - 0.5)
        sx0 = -0.12 + 0.24 * h01("Kennel", "sx", i)
        limb(r0, (sx0, y0 + 0.1, 0.07), (sx0 + 0.25 * math.sin(a), y0 - 0.12 - 0.08 * h01("Kennel", "sl", i), 0.03), 0.012, 0.004, 3,
             "fur", FUR)
    limb(r0, (0.25, -0.62, 0.025), (0.4, -0.7, 0.025), 0.018, 0.018, 4, "paint", DT.paint_uv("white"))   # bone
    for e in ((0.25, -0.62), (0.4, -0.7)):
        blob(r0, (e[0], e[1], 0.03), 0.03, 0.03, 0.025, 4, "paint", DT.paint_uv("white"))
    dog(r0, 0.0, -0.75, 0.0, 0.0, True)
    dog(r1, 0.0, -0.75, 0.0, 0.0, "mid")                                              # D73: mid-detail dog
    r0.prism(0.42, -0.45, 0.11, 0.0, 0.06, n=12, mat="paint", uv=DT.paint_uv("white"))   # enamel bowl
    r1.prism(0.42, -0.45, 0.11, 0.0, 0.06, n=6, mat="paint", uv=DT.paint_uv("white"))    # Res1: bowl + name board (perf L)
    r1.box(-0.22, 0.22, y0 - 0.01, y0, 0.78, 0.9, mat="paint", uv=DT.paint_uv("beige"))
    r0.prism(0.42, -0.45, 0.085, 0.06, 0.065, n=12, mat="metal", uv=DT.UV_STEEL)
    links = 9
    for i in range(links):                                                            # chain: ring bolt -> collar
        t0, t1 = i / links, (i + 1) / links
        p0 = (-0.35 + 0.35 * t0, 0.02 - 0.45 * t0, 0.25 * (1 - t0) + 0.02)
        p1 = (-0.35 + 0.35 * t1, 0.02 - 0.45 * t1, 0.25 * (1 - t1) + 0.02)
        limb(r0, p0, p1, 0.008, 0.008, 4, "metal", DT.UV_STEEL)
    r2.box(-hx, hx, y0, y1, 0.0, zw, mat="wood", uv=wood)
    r2.solid([(-hx, y0, zw), (hx, y0, zw), (0, y0, zr), (-hx, y1, zw), (hx, y1, zw), (0, y1, zr)],
             [(0, 1, 2), (3, 4, 5), (0, 1, 4, 3), (1, 2, 5, 4), (2, 0, 3, 5)], "paint", DARK)
    blob(r2, (0.0, -0.75, 0.2), 0.2, 0.45, 0.2, 4, "fur", FUR)
    for L in (geo, fire, view, shadow):                                              # simple convex hulls
        kw = {"mat": "pen_wood"} if L is fire else {}
        L.box(-hx, hx, y0, y1, 0.0, zw, **kw)
        L.solid([(-hx, y0, zw), (hx, y0, zw), (0, y0, zr), (-hx, y1, zw), (hx, y1, zw), (0, y1, zr)],
                [(0, 1, 2), (3, 4, 5), (0, 1, 4, 3), (1, 2, 5, 4), (2, 0, 3, 5)], **kw)
    geo.props.update({"autocenter": "0"})
    geo.mass = 40.0
    mem.point("ce_center", (0.0, 0.0, 0.4))
    mem.point("ce_radius", (0.9, 0.0, 0.4))
    mem.point("bark", (0.0, -0.95, 0.5))
    return [r0, r1, r2, shadow, geo, view, fire, mem]


# ================================================================== rat nest (kit)
def build_rat_nest():
    """2.4 m heap of rags, paper and gnawed rubbish against nothing in particular, 9 rats on and round it,
    droppings. Low (0.6 m): it blocks nobody; Geometry = the heap only (a step, not a wall)."""
    name = "RatNest"
    L = C.city_lods(C.Ruin(name, 0))
    for i, (x, y, rx, ry, h) in enumerate([(0.0, 0.0, 0.9, 0.7, 0.45), (0.5, 0.35, 0.5, 0.45, 0.3), (-0.55, 0.25, 0.45, 0.4, 0.28),
                                            (0.2, -0.5, 0.45, 0.35, 0.22)]):
        for k in ("res0", "res1", "res2", "geo", "fire", "view"):
            n = 10 if k == "res0" else (6 if k in ("res1", "geo") else 5)
            mat, uv = ("trash", UV_TRASH) if i % 2 == 0 else ("rubble", UV_RUBBLE)
            kw = kw_for(k, mat, uv, "wood")
            L[k].lod.solid(*_heap(x, y, rx, ry, h, n), **kw) if k in ("res0", "res1", "res2") else \
                L[k].lod.solid(*_heap(x, y, rx, ry, h, 5), **({"mat": "pen_wood"} if k == "fire" else {}))
    L["res3"].lod.solid(*_heap(0.0, 0.0, 1.1, 0.9, 0.45, 4), mat="trash", uv=UV_TRASH)
    L["shadow"].lod.solid(*_heap(0.0, 0.0, 1.0, 0.8, 0.4, 5))
    for i, (x, y, yaw) in enumerate(nest_rats(name, 9, 1.2)):
        z = 0.0 if math.hypot(x, y) > 0.9 else 0.25
        rat(L["res0"].lod, x, y, z, yaw, True)
        if i < 4:
            rat(L["res1"].lod, x, y, z, yaw, False)
    for i in range(14):                                                              # droppings / shredded paper
        a, d = 2 * math.pi * h01(name, "da", i), 0.8 + 0.6 * h01(name, "dd", i)
        L["res0"].lod.box(d * math.cos(a) - 0.02, d * math.cos(a) + 0.02, d * math.sin(a) - 0.01, d * math.sin(a) + 0.01, 0.0, 0.01,
                          mat="paint", uv=DARK)
    L["mem"].lod.point("nest", (0.0, 0.0, 0.3))
    return C._finish(L, 80.0)


def _heap(x, y, rx, ry, h, n):
    verts = [(x + rx * math.cos(2 * math.pi * k / n), y + ry * math.sin(2 * math.pi * k / n), 0.0) for k in range(n)]
    verts += [(x + 0.55 * rx * math.cos(2 * math.pi * (k + 0.5) / n), y + 0.55 * ry * math.sin(2 * math.pi * (k + 0.5) / n), 0.6 * h)
              for k in range(n)]
    verts.append((x, y, h))
    faces = [tuple(range(n))]
    for k in range(n):
        faces.append((k, (k + 1) % n, n + k))
        faces.append(((k + 1) % n, n + (k + 1) % n, n + k))
        faces.append((n + k, n + (k + 1) % n, 2 * n))
    return verts, faces


# ================================================================== horse carcass (kit)
def build_horse_carcass():
    """Dead horse on its side, 2.4 m: hide over the hindquarters and neck, ribs picked clean in the middle,
    skull, legs stiff out. Geometry = torso + neck (cover to crouch behind)."""
    name = "HorseCarcass"
    L = C.city_lods(C.Ruin(name, 0))
    hide = FUR_HORSE
    for k in ("res0", "res1", "res2"):
        lod, n = L[k].lod, (10 if k == "res0" else 6 if k == "res1" else 4)
        blob(lod, (0.0, 0.55, 0.3), 0.32, 0.45, 0.3, n, "fur", hide)               # hindquarters
        limb(lod, (0.0, -0.45, 0.3), (0.0, -0.95, 0.42), 0.22, 0.16, n, "fur", hide)   # neck
        blob(lod, (0.05, -1.15, 0.24), 0.12, 0.26, 0.11, n, "paint", BONE)            # skull
        if k == "res2":
            limb(lod, (0.0, 0.3, 0.3), (0.0, -0.45, 0.3), 0.3, 0.26, 4, "paint", BONE)
            continue
        limb(lod, (0.0, 0.35, 0.3), (0.0, -0.5, 0.3), 0.06, 0.06, 6, "paint", BONE)  # spine
        for i in range(9 if k == "res0" else 4):                                      # ribs: arcs of 3 struts
            yy = 0.25 - i * (0.7 / (8 if k == "res0" else 3))
            pts = [(0.0, yy, 0.58), (0.22, yy, 0.45), (0.3, yy, 0.22), (0.22, yy, 0.03)]
            for a, b in zip(pts, pts[1:]):
                limb(lod, a, b, 0.018, 0.018, 4, "paint", BONE)
        for (y0, y1) in ((0.6, 0.5), (0.5, 0.3), (-0.4, -0.5), (-0.5, -0.3)):          # legs out to +X
            limb(lod, (0.15, y0, 0.25), (1.1, y1, 0.08), 0.07, 0.04, 6 if k == "res0" else 4, "fur", hide)
            if k == "res0":
                blob(lod, (1.14, y1, 0.07), 0.05, 0.05, 0.06, 6, "paint", DARK)        # hooves
    limb(L["res0"].lod, (0.0, 0.95, 0.35), (-0.15, 1.35, 0.1), 0.05, 0.02, 6, "paint", DARK)   # tail
    for k in ("geo", "fire", "view", "shadow"):
        kw = {"mat": "pen_wood"} if k == "fire" else {}
        L[k].lod.solid(*_hull(), **kw)
    L["res3"].lod.box(-0.3, 0.3, -1.2, 1.0, 0.0, 0.55, mat="fur", uv=hide)
    L["mem"].lod.point("center", (0.0, 0.0, 0.0))
    return C._finish(L, 400.0)


def _hull():
    v = [(-0.32, -0.95, 0.0), (0.32, -0.95, 0.0), (0.32, 1.0, 0.0), (-0.32, 1.0, 0.0),
         (-0.25, -0.95, 0.6), (0.25, -0.95, 0.6), (0.25, 1.0, 0.6), (-0.25, 1.0, 0.6)]
    return v, [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]


BUILDERS = {"Kennel": (build_kennel, "sky_items", "sky_kennel.p3d")}


def modules():
    out = dict(BUILDERS)
    for n, fn in (("RatNest", build_rat_nest), ("HorseCarcass", build_horse_carcass)):
        e = S.KIT[n]
        out[n] = (fn, e["pbo"], e["p3d"])
    return out


if __name__ == "__main__":
    run_cli(modules(), KIT_MATS, "build_stats_creatures.json")
