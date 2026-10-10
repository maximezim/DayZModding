"""D61 landmarks, road structures and street props (ROADMAP.md) - plain Python or any Blender.

    python build_landmarks.py -- --out <mods/SKY_Skyline/addons> [--only Fair_FerrisWheel,Bridge_Long]

Same grammar and rules as build_city.py (it reuses its helpers): Res0 carries the detail, Res1 the
big forms, Res2 / Res3 the silhouette; collision only where something is solid enough to walk into,
climb on or hide behind; every walkable surface has Roadway. Frame: front = -Y, origin = footprint
centre at ground level (z 0 = top of the ground pad). The fairground, landfill and stadium are
abandoned: rust, flaking paint, weeds and saplings, dead bulbs.
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
import build_kit as K  # noqa: E402
from build_kit import KIT_MATS, line_quad  # noqa: E402
from skygeo import UVBand, UVRect, UVWorld, run_cli  # noqa: E402

h01, bar, rail, kw_for = C.h01, C.bar, C.rail, C.kw_for
UV_TILE, UV_REVEAL, UV_CONC, UV_GLASS, UV_RUBBLE = C.UV_TILE, C.UV_REVEAL, C.UV_CONC, C.UV_GLASS, C.UV_RUBBLE
SKIRT = S.CITY_STYLE["skirt"]


def fair_uv(band, scale=1.0):
    return UVBand(S.MATERIALS["fair"]["bands"][band], scale)


RUST = UVBand(S.MATERIALS["rust"]["bands"]["rust"], 1.0)
RUST_GREEN = UVBand(S.MATERIALS["rust"]["bands"]["green"], 1.0)
RUST_GREY = UVBand(S.MATERIALS["rust"]["bands"]["grey"], 1.0)
BURNT = UVBand(S.MATERIALS["rust"]["bands"]["burnt"], 1.0)
UV_TRASH = UVWorld(S.MATERIALS["trash"]["sheet_m"])
UV_TURF = UVWorld(S.MATERIALS["turf"]["sheet_m"])
UV_ASPH = UVWorld(4.0)


def lods(name):
    return C.city_lods(C.Ruin(name, 0))


def finish(L, mass):
    return C._finish(L, mass)


def U(L):
    return {k: v.lod for k, v in L.items()}


def solid_all(L, keys, verts, faces, mat, uv, pen="metal"):
    for k in keys:
        L[k].solid(verts, faces, **kw_for(k, mat, uv, pen))


def box_all(L, keys, box, mat, uv, pen="concrete", skip=()):
    for k in keys:
        kw = kw_for(k, mat, uv, pen)
        if skip and k.startswith("res"):
            kw["skip"] = skip
        L[k].box(*box, **kw)


ALL = ("res0", "res1", "res2", "geo", "view", "fire")
VIS = ("res0", "res1", "res2")


def ground_pad(L, hw, hd, mat="concrete", uv=None, top=0.0, road="road_ext"):
    """Ground pad (-SLAB..top), Roadway, granite foundation skirt (sloped sites)."""
    C._pad(L, hw, hd, mat, uv or UV_REVEAL, top)


def weeds(L, name, x0, x1, y0, y1, n, z=0.0, cells=("grass", "weeds", "dry_grass", "burdock")):
    for i in range(n):
        x = x0 + (x1 - x0) * h01(name, "wx", i)
        y = y0 + (y1 - y0) * h01(name, "wy", i)
        C.plant_tuft(U(L), x, y, z, 0.6 + 0.8 * h01(name, "ws", i), 0.5 + 0.6 * h01(name, "wh", i),
                     cells[i % len(cells)], (name, "weed", i))


def ring_bars(lod, cx, y, cz, r, n, rad, mat, uv, a0=0.0):
    """Polygonal ring of square bars in the X-Z plane (wheel rims)."""
    pts = [(cx + r * math.cos(a0 + 2 * math.pi * i / n), y, cz + r * math.sin(a0 + 2 * math.pi * i / n)) for i in range(n)]
    for i, (a, b) in enumerate(zip(pts, pts[1:] + pts[:1])):
        bar(lod, a, b, rad - 0.007 * (i % 2), mat, uv)                     # D96: alternate 7 mm (joints z-fought)


# ================================================================== funfair (idea 1)
def build_ferris_wheel():
    """26 m Ferris wheel in the Pripyat style: twin A-frame legs, truss rims (outer + inner ring with
    lacing), 16 spokes per side, 16 yellow gondolas hanging plumb, a boarding platform with steps,
    dead bulbs on the spokes, a birch growing through the platform."""
    name = "Fair_FerrisWheel"
    L = lods(name)
    hw, hd = 8.0, 5.0
    ground_pad(L, hw, hd, "concrete", UV_CONC)
    za, R = 16.0, 13.0
    white, red, yellow = fair_uv("white"), fair_uv("red"), fair_uv("yellow")
    # boarding platform under the bottom gondola + steps (walkable)
    box_all(L, ALL, (-2.4, 2.4, -2.2, 2.2, 0.0, 0.6), "concrete", UV_CONC)
    L["road"].hquad(-2.4, 2.4, -2.2, 2.2, 0.6, mat="road_ext", uv=UV_TILE)
    for i in range(3):
        box_all(L, ("res0", "res1", "geo", "fire"), (-1.0, 1.0, -2.2 - 0.3 * (3 - i), -2.2 - 0.3 * (2 - i), 0.0, 0.2 * (i + 1)),
                "concrete", UV_CONC)
    L["road"].ramp(-1.0, 1.0, -3.1, -2.2, 0.0, 0.6, mat="road_ext", uv=UV_TILE)
    rail(L, -2.4, -1.1, -2.24, -2.2, 0.6, h=1.0)
    rail(L, 1.1, 2.4, -2.24, -2.2, 0.6, h=1.0)
    # A-frame legs (truss: two chords + lacing), feet on concrete plinths
    for sy in (-1.7, 1.7):
        for sx in (-1, 1):
            foot = (sx * 6.8, sy, 0.0)
            top = (sx * 0.5, sy * 0.85, za)
            for k in ("res0", "res1", "res2", "geo", "fire", "view"):
                kw = kw_for(k, "concrete", UV_CONC, "concrete")
                L[k].box(foot[0] - 0.6, foot[0] + 0.6, sy - 0.6, sy + 0.6, -SKIRT, 0.5, **kw)
            for off in (-0.22, 0.22):
                p0 = (foot[0] + off, foot[1], 0.5)
                p1 = (top[0] + off * 0.3, top[1], top[2])
                for k in ("res0", "res1", "res2"):
                    bar(L[k], p0, p1, 0.12 if k == "res0" else 0.16, "fair", white)
                bar(L["geo"], p0, p1, 0.14)
                bar(L["fire"], p0, p1, 0.14, "pen_metal")
            nseg = 9
            for i in range(nseg):                                                  # zig-zag lacing (Res0)
                t0, t1 = i / nseg, (i + 1) / nseg
                pa = tuple(foot[j] + (top[j] - foot[j]) * t0 + (-0.22 if i % 2 else 0.22) * (j == 0) for j in range(3))
                pb = tuple(foot[j] + (top[j] - foot[j]) * t1 + (0.22 if i % 2 else -0.22) * (j == 0) for j in range(3))
                bar(L["res0"], (pa[0], pa[1], max(pa[2], 0.5)), pb, 0.04, "fair", white)
            L["shadow"].solid(*_leg_shadow(foot, top))
    # hub + axle
    for k in ("res0", "res1", "res2", "geo", "fire", "view", "shadow"):
        nn = 16 if k == "res0" else 8
        prof = [(1.0 * math.cos(2 * math.pi * i / nn), za + 1.0 * math.sin(2 * math.pi * i / nn)) for i in range(nn)]
        L[k].extrude_y(prof, -2.0, 2.0, **(kw_for(k, "fair", red, "metal") if k != "shadow" else {}))
    # rims (outer + inner ring per side), lacing, spokes, bulbs
    for side in (-1.4, 1.4):
        ring_bars(L["res0"], 0.0, side, za, R, 32, 0.12, "fair", white)
        ring_bars(L["res0"], 0.0, side, za, R - 0.9, 32, 0.08, "fair", white)
        ring_bars(L["res1"], 0.0, side, za, R - 0.45, 16, 0.25, "fair", white)
        ring_bars(L["res2"], 0.0, side, za, R - 0.45, 8, 0.3, "fair", white)
        for i in range(32):                                                    # rim lacing
            a0, a1 = 2 * math.pi * i / 32, 2 * math.pi * (i + 1) / 32
            bar(L["res0"], (R * math.cos(a0), side, za + R * math.sin(a0)),
                ((R - 0.9) * math.cos(a1), side, za + (R - 0.9) * math.sin(a1)), 0.035, "fair", white)
        for i in range(16):
            a = 2 * math.pi * i / 16 + math.pi / 32
            p1 = ((R - 0.9) * math.cos(a), side, za + (R - 0.9) * math.sin(a))
            bar(L["res0"], (1.0 * math.cos(a), side * 0.9, za + 1.0 * math.sin(a)), p1, 0.045, "fair", white)
            if i % 2 == 0:
                bar(L["res1"], (0.0, side * 0.9, za), p1, 0.08, "fair", white)
            for j in range(1, 6):                                              # dead bulbs along the spoke
                t = j / 6.0
                bx, bz = p1[0] * t, za + (p1[2] - za) * t
                L["res0"].box(bx - 0.05, bx + 0.05, side - 0.05, side + 0.05, bz - 0.05, bz + 0.05, mat="paint",
                              uv=DT.paint_uv("white"))
    for i in range(16):                                                        # cross ties between the rims
        a = 2 * math.pi * i / 16
        p = (R * math.cos(a), 0.0, za + R * math.sin(a))
        bar(L["res0"], (p[0], -1.4, p[2]), (p[0], 1.4, p[2]), 0.06, "fair", white)
    # gondolas: pivot on the rim, cabin hangs plumb (Pripyat yellow body, red roof cap)
    for i in range(16):
        a = 2 * math.pi * i / 16 - math.pi / 2
        px, pz = R * math.cos(a), za + R * math.sin(a)
        gondola(L, px, pz, name, i)
    L["res3"].box(-7.0, 7.0, -1.8, 1.8, 0.0, 0.6, mat="concrete", uv=UV_CONC, skip=("-z",))
    for k_seg in range(8):
        a0, a1 = 2 * math.pi * k_seg / 8, 2 * math.pi * (k_seg + 1) / 8
        bar(L["res3"], (R * math.cos(a0), 0.0, za + R * math.sin(a0)), (R * math.cos(a1), 0.0, za + R * math.sin(a1)),
            0.35 - 0.007 * (k_seg % 2), "fair", white)
    for sx in (-1, 1):
        bar(L["res3"], (sx * 6.8, 0.0, 0.5), (0.0, 0.0, za), 0.3, "fair", white)
    # Chernobyl touch: a birch through the platform edge, weeds round the feet
    birch = [l for l in C.build_veg("Veg_Birch") if l.name in ("res0", "res1")]
    for l in birch:
        tgt = L[l.name].lod
        base = len(tgt.verts)
        off = tgt._prim
        tgt.verts.extend([(x + 3.4, y - 3.6, z) for (x, y, z) in l.verts])
        tgt.vprim.extend([p + off if p > 0 else p for p in l.vprim])
        tgt._prim += max(l.vprim + [0])
        for idx, mat, uv in l.faces:
            tgt.faces.append((tuple(base + i for i in idx), mat, uv))
    weeds(L, name, -hw + 0.4, hw - 0.4, -hd + 0.4, hd - 0.4, 18)
    L["mem"].lod.point("center", (0.0, 0.0, 0.0))
    return finish(L, 120000.0)


def _leg_shadow(foot, top):
    r = 0.2
    v = [(foot[0] - r, foot[1] - r, 0.5), (foot[0] + r, foot[1] - r, 0.5), (foot[0] + r, foot[1] + r, 0.5), (foot[0] - r, foot[1] + r, 0.5),
         (top[0] - r, top[1] - r, top[2]), (top[0] + r, top[1] - r, top[2]), (top[0] + r, top[1] + r, top[2]), (top[0] - r, top[1] + r, top[2])]
    return v, [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]


def gondola(L, px, pz, name, i):
    yellow, red = fair_uv("yellow"), fair_uv("red")
    w, d = 0.8, 0.7                                                              # half sizes (tangent x, axle y)
    zf = pz - 2.4                                                                # floor
    tilt = 0.12 * (h01(name, "gt", i) - 0.5)                                     # a few hang slightly askew
    bar(L["res0"], (px, -0.5, pz), (px + tilt, -0.5, zf + 2.0), 0.03, "metal", DT.UV_STEEL)
    bar(L["res0"], (px, 0.5, pz), (px + tilt, 0.5, zf + 2.0), 0.03, "metal", DT.UV_STEEL)
    cx = px + tilt
    L["res0"].box(cx - w, cx + w, -d, d, zf, zf + 0.08, mat="fair", uv=yellow)
    for (a0, a1, b0, b1) in ((cx - w, cx + w, -d, -d + 0.05), (cx - w, cx + w, d - 0.05, d), (cx - w, cx - w + 0.05, -d, d),
                             (cx + w - 0.05, cx + w, -d, d)):
        L["res0"].box(a0, a1, b0, b1, zf + 0.08, zf + 0.95, mat="fair", uv=yellow)
    for (qx, qy) in ((cx - w + 0.03, -d + 0.03), (cx + w - 0.03, -d + 0.03), (cx - w + 0.03, d - 0.03), (cx + w - 0.03, d - 0.03)):
        L["res0"].box(qx - 0.025, qx + 0.025, qy - 0.025, qy + 0.025, zf + 0.95, zf + 1.85, mat="metal", uv=DT.UV_STEEL)
    roof = [(cx - w - 0.1, -d - 0.1, zf + 1.85), (cx + w + 0.1, -d - 0.1, zf + 1.85), (cx + w + 0.1, d + 0.1, zf + 1.85),
            (cx - w - 0.1, d + 0.1, zf + 1.85), (cx, 0.0, zf + 2.2)]
    L["res0"].solid(roof, [(0, 1, 2, 3), (0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4)], mat="fair", uv=red)
    L["res0"].box(cx - w + 0.1, cx + w - 0.1, -0.2, 0.2, zf + 0.08, zf + 0.5, mat="fair", uv=yellow)          # bench
    L["res1"].box(cx - w, cx + w, -d, d, zf, zf + 0.95, mat="fair", uv=yellow)
    L["res1"].solid(roof, [(0, 1, 2, 3), (0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4)], mat="fair", uv=red)
    L["res2"].box(cx - w, cx + w, -d, d, zf, zf + 2.0, mat="fair", uv=yellow)
    for k in ("geo", "fire"):
        kw = {"mat": "pen_metal"} if k == "fire" else {}
        # every cabin: floor + four low walls + bench (D96: the high cabins were one solid block across their open
        # interior - collision with nothing drawn, test_quality ghost); boardable ones: sec D79 M3, no crawl pocket
        L[k].box(cx - w, cx + w, -d, d, zf, zf + 0.08, **kw)
        L[k].box(cx - w + 0.05, cx + w - 0.05, -0.2, 0.2, zf + 0.08, zf + 0.5, **kw)   # bench collides, wall to wall
        for (a0, a1, b0, b1) in ((cx - w, cx + w, -d, -d + 0.05), (cx - w, cx + w, d - 0.05, d),
                                 (cx - w, cx - w + 0.05, -d + 0.05, d - 0.05), (cx + w - 0.05, cx + w, -d + 0.05, d - 0.05)):
            L[k].box(a0, a1, b0, b1, zf + 0.08, zf + 0.95, **kw)
    for k in ("geo", "fire", "view"):                                            # roof collides (D79: a head fit inside it
        L[k].solid(roof, [(0, 1, 2, 3), (0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4)],  # when standing on a low cabin)
                   **({"mat": "pen_metal"} if k == "fire" else {}))
    if zf < 2.0:                                                                 # the bottom cabins can be boarded
        L["view"].box(cx - w + 0.05, cx + w - 0.05, -0.2, 0.2, zf + 0.08, zf + 0.5)
        L["road"].hquad(cx - w + 0.05, cx + w - 0.05, -d + 0.05, d - 0.05, zf + 0.08, mat="road_ext", uv=UV_TILE)


def build_carousel():
    """Chain-swing carousel: platform disc, mast, striped cone canopy, 16 swings on chains (some
    tangled), ring fence with a gate gap, control booth."""
    name = "Fair_Carousel"
    L = lods(name)
    ground_pad(L, 7.0, 7.0, "concrete", UV_CONC)
    for k in ALL:
        L[k].prism(0.0, 0.0, 4.5, 0.0, 0.4, n=24 if k == "res0" else 12, **kw_for(k, "fair", fair_uv("blue"), "metal"))
    L["road"].hquad(-3.1, 3.1, -3.1, 3.1, 0.4, mat="road_ext", uv=UV_TILE)
    for k in ALL + ("shadow",):
        L[k].prism(0.0, 0.0, 0.45, 0.4, 7.2, n=12 if k == "res0" else 6, **(kw_for(k, "fair", fair_uv("white"), "metal") if k != "shadow" else {}))
    n = 16
    for k in ("res0", "res1", "res2"):                                           # striped cone canopy
        nn = n if k != "res2" else 8
        for i in range(nn):
            a0, a1 = 2 * math.pi * i / nn, 2 * math.pi * (i + 1) / nn
            band = "red" if i % 2 else "yellow"
            q = [(5.6 * math.cos(a0), 5.6 * math.sin(a0), 7.0), (5.6 * math.cos(a1), 5.6 * math.sin(a1), 7.0),
                 (0.8 * math.cos(a1), 0.8 * math.sin(a1), 8.8), (0.8 * math.cos(a0), 0.8 * math.sin(a0), 8.8)]
            L[k].quad(q, (math.cos((a0 + a1) / 2), math.sin((a0 + a1) / 2), 0.9), "fair", fair_uv(band), double=k == "res0")
            if k == "res0":                                                       # valance
                L[k].quad([(5.6 * math.cos(a0), 5.6 * math.sin(a0), 6.4), (5.6 * math.cos(a1), 5.6 * math.sin(a1), 6.4),
                           (5.6 * math.cos(a1), 5.6 * math.sin(a1), 7.0), (5.6 * math.cos(a0), 5.6 * math.sin(a0), 7.0)],
                          (math.cos((a0 + a1) / 2), math.sin((a0 + a1) / 2), 0), "fair", fair_uv("white"), double=True)
    L["res0"].prism(0.0, 0.0, 0.9, 8.8, 9.3, n=12, mat="fair", uv=fair_uv("red"))
    L["res0"].prism(0.0, 0.0, 0.1, 9.3, 10.2, n=6, mat="metal", uv=DT.UV_STEEL)
    for j in range(8):                                                           # D96: collision is the cone shell, 8
        a0, a1 = 2 * math.pi * j / 8, 2 * math.pi * (j + 1) / 8                   # thin sector slabs (a 5.6 m cylinder hid
        top = [(5.6 * math.cos(a0), 5.6 * math.sin(a0), 7.0), (5.6 * math.cos(a1), 5.6 * math.sin(a1), 7.0),   # 150 m2 of air)
               (0.8 * math.cos(a1), 0.8 * math.sin(a1), 8.8), (0.8 * math.cos(a0), 0.8 * math.sin(a0), 8.8)]
        slab = top + [(x_, y_, z_ - 0.12) for x_, y_, z_ in top]
        for k in ("geo", "fire", "view"):
            L[k].solid(slab, [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)],
                       **({"mat": "pen_metal"} if k == "fire" else {}))
    L["res3"].prism(0.0, 0.0, 5.6, 6.4, 8.8, n=6, mat="fair", uv=fair_uv("red"))
    L["res3"].prism(0.0, 0.0, 4.5, 0.0, 0.4, n=6, mat="fair", uv=fair_uv("blue"))
    for i in range(n):                                                           # swings
        a = 2 * math.pi * (i + 0.5) / n
        tang = h01(name, "tangle", i) < 0.25
        ro = 5.1
        rs = ro + (0.6 if tang else 0.15) * h01(name, "sw", i)
        sx, sy = rs * math.cos(a), rs * math.sin(a)
        zs = 2.0 + (1.2 if tang else 0.0)
        for dd in (-0.22, 0.22):
            ox, oy = -math.sin(a) * dd, math.cos(a) * dd
            bar(L["res0"], (ro * math.cos(a) + ox, ro * math.sin(a) + oy, 6.6), (sx + ox, sy + oy, zs + 0.5), 0.008, "metal", DT.UV_STEEL)
        seat_col = ("yellow", "blue", "red", "white")[i % 4]
        L["res0"].box(sx - 0.25, sx + 0.25, sy - 0.25, sy + 0.25, zs, zs + 0.06, mat="fair", uv=fair_uv(seat_col))
        back = (sx - 0.25, sx + 0.25, sy - 0.25, sy - 0.2) if math.sin(a) < 0 else (sx - 0.25, sx + 0.25, sy + 0.2, sy + 0.25)
        L["res0"].box(*back, zs + 0.06, zs + 0.45, mat="fair", uv=fair_uv(seat_col))
    for i in range(24):                                                          # ring fence, gate gap at the front
        a0, a1 = 2 * math.pi * i / 24, 2 * math.pi * (i + 1) / 24
        if abs(math.cos((a0 + a1) / 2 + math.pi / 2)) > 0.97 and math.sin((a0 + a1) / 2) < 0:
            continue
        p0 = (6.5 * math.cos(a0), 6.5 * math.sin(a0))
        p1 = (6.5 * math.cos(a1), 6.5 * math.sin(a1))
        for k in ("res0", "res1"):
            bar(L[k], (p0[0], p0[1], 1.0), (p1[0], p1[1], 1.0), 0.03, "fair", fair_uv("white"))
        L["res0"].prism(p0[0], p0[1], 0.04, 0.0, 1.05, n=6, mat="fair", uv=fair_uv("white"))
        nx, ny = (p1[1] - p0[1]), -(p1[0] - p0[0])                               # D96: a 8 cm sheet under the top rail
        nl = math.hypot(nx, ny) or 1.0                                           # (a 1 m thick bar was a wide collar)
        nx, ny = 0.04 * nx / nl, 0.04 * ny / nl
        sheet = [(p[0] + s * nx, p[1] + s * ny, z_) for p in (p0, p1) for s in (-1, 1) for z_ in (0.0, 1.03)]
        L["geo"].solid(sheet, [(0, 1, 3, 2), (4, 5, 7, 6), (0, 2, 6, 4), (1, 3, 7, 5), (0, 1, 5, 4), (2, 3, 7, 6)])
    for k in ("res0", "res1", "geo", "fire", "view"):                            # control booth
        L[k].box(5.2, 6.4, -6.6, -5.4, 0.0, 2.3, **kw_for(k, "fair", fair_uv("yellow"), "wood"))
    L["res0"].box(5.15, 6.45, -6.65, -5.35, 2.3, 2.45, mat="fair", uv=fair_uv("red"))
    weeds(L, name, -6.6, 6.6, -6.6, 6.6, 20)
    L["mem"].lod.point("center", (0.0, 0.0, 0.0))
    return finish(L, 60000.0)


def build_bumper_cars():
    """Bumper-car pavilion: steel floor, perimeter bumper, 8 posts, flat roof with a LUNAPARK fascia,
    contact mesh under the roof, 6 abandoned cars with poles, cashier box."""
    name = "Fair_BumperCars"
    L = lods(name)
    hw, hd = 9.0, 6.0
    ground_pad(L, hw, hd, "concrete", UV_CONC)
    fx0, fx1, fy0, fy1 = -8.0, 8.0, -5.0, 5.0
    for k in ALL:
        L[k].box(fx0, fx1, fy0, fy1, 0.0, 0.25, **kw_for(k, "metal", DT.UV_STEEL, "metal"))
    L["road"].hquad(fx0, fx1, fy0, fy1, 0.25, mat="road_ext", uv=UV_TILE)
    for (a0, a1, b0, b1) in ((fx0, fx1, fy0, fy0 + 0.3), (fx0, fx1, fy1 - 0.3, fy1), (fx0, fx0 + 0.3, fy0 + 0.3, fy1 - 0.3),
                             (fx1 - 0.3, fx1, fy0 + 0.3, fy1 - 0.3)):
        if b1 - b0 < 0.5 and a0 < -1.0 < a1 and b0 < 0:                           # entrance gap in the front bumper
            for (c0, c1) in ((a0, -1.0), (1.0, a1)):
                box_all(L, ("res0", "res1", "geo", "fire"), (c0, c1, b0, b1, 0.25, 0.7), "rubble", UV_RUBBLE, "wood")
            continue
        box_all(L, ("res0", "res1", "geo", "fire"), (a0, a1, b0, b1, 0.25, 0.7), "rubble", UV_RUBBLE, "wood")
    for (px, py) in ((fx0, fy0), (0.0, fy0), (fx1, fy0), (fx0, fy1), (0.0, fy1), (fx1, fy1), (fx0, 0.0), (fx1, 0.0)):
        box_all(L, ALL, (px - 0.15, px + 0.15, py - 0.15, py + 0.15, 0.25, 4.6), "fair", fair_uv("white"), "metal")
    for k in ALL + ("shadow", "res3"):
        if k == "res3":
            L[k].box(fx0 - 0.4, fx1 + 0.4, fy0 - 0.4, fy1 + 0.4, 4.6, 5.6, mat="fair", uv=fair_uv("blue"), skip=("-z",))
            continue
        L[k].box(fx0 - 0.4, fx1 + 0.4, fy0 - 0.4, fy1 + 0.4, 4.6, 4.9, **(kw_for(k, "metal", DT.UV_PAINT, "metal") if k != "shadow" else {}))
    for k in ("res0", "res1", "res2"):                                           # fascia band
        L[k].box(fx0 - 0.45, fx1 + 0.45, fy0 - 0.45, fy0 - 0.4, 4.9, 5.6, mat="fair", uv=fair_uv("blue"))
        L[k].box(fx0 - 0.45, fx1 + 0.45, fy1 + 0.4, fy1 + 0.45, 4.9, 5.6, mat="fair", uv=fair_uv("blue"))
    for (yy, nrm) in ((fy0 - 0.452, -1), (fy1 + 0.452, 1)):
        for k in ("res0", "res1"):
            C.sign2_quad(L[k], [(-4.0, yy, 4.95), (4.0, yy, 4.95), (4.0, yy, 5.55), (-4.0, yy, 5.55)], (0, nrm, 0), "fair",
                         (0, 2), (-4.0, 4.95) if nrm < 0 else (4.0, 4.95), (4.0, 5.55) if nrm < 0 else (-4.0, 5.55))
    x = fx0 + 1.0                                                                # contact mesh
    while x < fx1:
        bar(L["res0"], (x, fy0, 4.5), (x, fy1, 4.5), 0.008, "metal", DT.UV_STEEL)
        x += 0.6
    y = fy0 + 0.6
    while y < fy1:
        bar(L["res0"], (fx0, y, 4.5), (fx1, y, 4.5), 0.008, "metal", DT.UV_STEEL)
        y += 0.6
    for i in range(6):                                                           # cars
        cx = fx0 + 1.8 + (fx1 - fx0 - 3.6) * h01(name, "carx", i)
        cy = fy0 + 1.6 + (fy1 - fy0 - 3.2) * h01(name, "cary", i)
        if abs(cx) < 1.6 and cy < fy0 + 2.5:
            cy += 2.5
        col = ("red", "yellow", "blue", "white")[i % 4]
        for k in ("res0", "res1", "geo", "fire", "view"):
            L[k].box(cx - 0.75, cx + 0.75, cy - 1.0, cy + 1.0, 0.25, 0.75, **kw_for(k, "fair", fair_uv(col), "metal"))
        L["res0"].box(cx - 0.85, cx + 0.85, cy - 1.1, cy + 1.1, 0.3, 0.5, mat="rubble", uv=UV_RUBBLE)
        for k in ("res0", "geo", "fire", "view"):                                 # seat back (collides: D79 concealment)
            L[k].box(cx - 0.5, cx + 0.5, cy - 0.1, cy + 0.6, 0.75, 1.05, **kw_for(k, "fair", fair_uv(col), "metal"))
        L["res0"].prism(cx, cy + 0.8, 0.025, 0.75, 4.5, n=4, mat="metal", uv=DT.UV_STEEL)
    for k in ("res0", "res1", "geo", "fire", "view"):                            # cashier box
        L[k].box(fx1 - 1.8, fx1 - 0.4, fy0 - 0.9 + 0.95, fy0 + 0.95, 0.25, 2.2, **kw_for(k, "fair", fair_uv("yellow"), "wood"))
    weeds(L, name, -hw + 0.3, hw - 0.3, -hd + 0.2, -hd + 0.9, 8)
    weeds(L, name + "b", fx0 + 0.6, fx1 - 0.6, fy0 + 0.6, fy1 - 0.6, 10, z=0.25, cells=("grass", "dry_grass"))
    L["mem"].lod.point("center", (0.0, 0.0, 0.0))
    return finish(L, 50000.0)


def build_booth():
    """Ticket / shooting-gallery booth: 4 x 3 m, open counter front, striped awning, TICKETS sign.
    D70: battens, corner posts, counter top, prize shelves with plush toys, tin ducks on a rail (some shot off),
    two air rifles chained to the counter, awning valance, a dead bulb string."""
    name = "Fair_Booth"
    L = lods(name)
    hw, hd = 2.0, 1.5
    ground_pad(L, hw, hd, "concrete", UV_CONC)
    for (a0, a1, b0, b1) in ((-hw, hw, hd - 0.1, hd), (-hw, -hw + 0.1, -hd, hd - 0.1), (hw - 0.1, hw, -hd, hd - 0.1)):
        box_all(L, ALL, (a0, a1, b0, b1, 0.0, 2.6), "fair", fair_uv("blue"), "wood")
    box_all(L, ALL, (-hw + 0.1, hw - 0.1, -hd, -hd + 0.5, 0.0, 1.05), "fair", fair_uv("yellow"), "wood")   # counter
    for k in ALL + ("shadow",):
        L[k].box(-hw, hw, -hd, hd, 2.6, 2.75, **(kw_for(k, "fair", fair_uv("white"), "wood") if k != "shadow" else {}))
    L["res3"].box(-hw, hw, -hd, hd, 0.0, 2.75, mat="fair", uv=fair_uv("blue"), skip=("-z",))
    for i in range(8):                                                           # striped awning
        a0, a1 = -hw + i * (2 * hw) / 8, -hw + (i + 1) * (2 * hw) / 8
        band = "red" if i % 2 else "white"
        for k in ("res0", "res1"):
            L[k].quad([(a0, -hd, 2.5), (a1, -hd, 2.5), (a1, -hd - 0.9, 2.1), (a0, -hd - 0.9, 2.1)], (0, -0.4, 0.9), "fair",
                      fair_uv(band), double=True)
    for k in ("res0", "res1"):
        C.sign2_quad(L[k], [(-1.6, -hd - 0.005, 2.62), (1.6, -hd - 0.005, 2.62), (1.6, -hd - 0.005, 2.74), (-1.6, -hd - 0.005, 2.74)],
                     (0, -1, 0), "tickets", (0, 2), (-1.6, 2.62), (1.6, 2.74))
    # D70 close-up pass: battens, corner posts, counter top, prize shelves, tin ducks on a rail, chained air rifles,
    # awning valance and a bulb string. Res0 only except the posts and the counter top (Res1).
    for sx in (-1, 1):                                                           # side battens (outside)
        for i in range(5):
            yy = -hd + 0.3 + i * 0.6
            L["res0"].box(sx * hw - (0.03 if sx < 0 else 0), sx * hw + (0.03 if sx > 0 else 0), yy - 0.04, yy + 0.04, 0.1, 2.55,
                          mat="fair", uv=fair_uv("white"), skip=("-z", "+z"))
    for i in range(7):                                                           # back battens
        xx = -hw + 0.5 + i * 0.5
        L["res0"].box(xx - 0.04, xx + 0.04, hd, hd + 0.03, 0.1, 2.55, mat="fair", uv=fair_uv("white"), skip=("-z", "+z"))
    for sx in (-1, 1):                                                           # Res1: battens as flat strips (perf M)
        for i in range(5):
            yy = -hd + 0.3 + i * 0.6
            L["res1"].quad([(sx * (hw + 0.03), yy - 0.04, 0.1), (sx * (hw + 0.03), yy + 0.04, 0.1), (sx * (hw + 0.03), yy + 0.04, 2.55),
                            (sx * (hw + 0.03), yy - 0.04, 2.55)], (sx, 0, 0), "fair", fair_uv("white"), double=True)
    for i in range(7):
        xx = -hw + 0.5 + i * 0.5
        L["res1"].quad([(xx - 0.04, hd + 0.03, 0.1), (xx + 0.04, hd + 0.03, 0.1), (xx + 0.04, hd + 0.03, 2.55), (xx - 0.04, hd + 0.03, 2.55)],
                       (0, 1, 0), "fair", fair_uv("white"), double=True)
    for sx in (-1, 1):                                                           # corner posts
        for sy in (-1, 1):
            for k in ("res0", "res1"):
                L[k].box(sx * hw - 0.07, sx * hw + 0.07, sy * hd - 0.07, sy * hd + 0.07, 0.0, 2.78, mat="fair", uv=fair_uv("red"),
                         skip=("-z",))
    box_all(L, ("res0", "res1", "res2"), (-hw + 0.05, hw - 0.05, -hd - 0.12, -hd + 0.55, 1.05, 1.1), "fair", fair_uv("white"), "wood")
    box_all(L, ("geo", "view", "fire"), (-hw + 0.1, hw - 0.1, -hd, -hd + 0.5, 1.05, 1.1), "fair", fair_uv("white"), "wood")
    # counter top: collides too, so items dropped on it rest on its top, not inside it (security review D70 L);
    # the 12 cm overhang stays visual (Geometry keeps to the 4 x 3 footprint)
    for i in range(5):                                                           # red stripes down the counter front
        xx = -hw + 0.45 + i * 0.775
        L["res1"].quad([(xx - 0.12, -hd - 0.015, 0.12), (xx + 0.12, -hd - 0.015, 0.12), (xx + 0.12, -hd - 0.015, 1.0),
                        (xx - 0.12, -hd - 0.015, 1.0)], (0, -1, 0), "fair", fair_uv("red"))   # Res1: one quad (perf M)
        L["res0"].box(xx - 0.12, xx + 0.12, -hd - 0.015, -hd, 0.12, 1.0, mat="fair", uv=fair_uv("red"), skip=("+y", "-z", "+z"))
    for zz in (1.25, 1.75):                                                      # prize shelves + plush toys
        for k in ("res0", "res1"):
            L[k].box(-hw + 0.15, hw - 0.15, hd - 0.4, hd - 0.1, zz, zz + 0.03, mat="fair", uv=fair_uv("white"))
        for i in range(5):
            if h01(name, "toy", zz, i) < 0.3:
                continue                                                         # won (or looted) long ago
            tx = -1.5 + i * 0.75 + 0.2 * h01(name, "tx", zz, i)
            s = 0.1 + 0.06 * h01(name, "ts", zz, i)
            col = ("yellow", "red", "blue", "white")[int(h01(name, "tc", zz, i) * 4)]
            for k in ("res0", "res1"):                                           # body (also Res1, perf M)
                L[k].box(tx - s, tx + s, hd - 0.33, hd - 0.15, zz + 0.03, zz + 0.03 + 2.2 * s, mat="fair", uv=fair_uv(col))
            L["res0"].box(tx - 0.6 * s, tx + 0.6 * s, hd - 0.3, hd - 0.18, zz + 0.03 + 2.2 * s, zz + 0.03 + 3.2 * s, mat="fair",
                          uv=fair_uv(col))                                       # head
    L["res0"].box(-hw + 0.2, hw - 0.2, hd - 0.6, hd - 0.56, 2.05, 2.08, mat="fair", uv=fair_uv("blue"))   # duck rail
    for i in range(7):
        if h01(name, "duck", i) < 0.25:
            continue                                                             # shot off the rail
        tx = -1.6 + i * 0.53
        L["res0"].extrude_y([(tx - 0.12, 2.08), (tx + 0.1, 2.08), (tx + 0.12, 2.18), (tx + 0.05, 2.2), (tx + 0.06, 2.3),
                             (tx - 0.02, 2.31), (tx - 0.05, 2.22), (tx - 0.13, 2.17)], hd - 0.6, hd - 0.58, mat="fair",
                            uv=fair_uv("yellow"))
    for i, xx in enumerate((-0.9, 0.7)):                                         # air rifles chained to the counter
        a = 0.25 * (h01(name, "rifle", i) - 0.5)
        C.bar(L["res0"], (xx, -hd + 0.15, 1.13), (xx + 0.75 * math.cos(a), -hd + 0.15 + 0.75 * math.sin(a), 1.13), 0.012,
              "fair", fair_uv("blue"))                                           # blued barrel (fair trim: 5 sections)
        C.bar(L["res0"], (xx - 0.3, -hd + 0.15, 1.13), (xx, -hd + 0.15, 1.13), 0.03, "fair", fair_uv("white"))   # stock
        C.bar(L["res0"], (xx - 0.15, -hd + 0.15, 1.12), (xx - 0.1, -hd + 0.25, 1.1), 0.006, "fair", fair_uv("white"))   # chain
    for i in range(8):                                                           # awning valance (scallops)
        a0, a1 = -hw + i * (2 * hw) / 8, -hw + (i + 1) * (2 * hw) / 8
        band = "red" if i % 2 else "white"
        for k in ("res0", "res1"):
            L[k].quad([(a0 + 0.08, -hd - 0.93, 1.95), (a1 - 0.08, -hd - 0.93, 1.95), (a1, -hd - 0.9, 2.1), (a0, -hd - 0.9, 2.1)],
                      (0, -1, 0), "fair", fair_uv(band), double=True)     # wound counter-clockwise seen from the front
    L["res1"].box(-hw + 0.15, hw - 0.15, -hd - 0.07, -hd + 0.01, 2.52, 2.6, mat="fair", uv=fair_uv("white"))   # Res1 bulb strip
    for i in range(10):                                                          # dead bulb string under the fascia
        bx = -hw + 0.2 + i * (2 * hw - 0.4) / 9
        L["res0"].prism(bx, -hd - 0.03, 0.035, 2.52, 2.6, n=4, mat="fair", uv=fair_uv("white"))
    weeds(L, name, -hw, hw, -hd - 0.1, -hd + 0.2, 3)
    L["mem"].lod.point("center", (0.0, 0.0, 0.0))
    return finish(L, 4000.0)


def build_gate():
    """LUNAPARK entrance: two lattice pylons, arch girder with the sign and a star, 3 turnstiles."""
    name = "Fair_Gate"
    L = lods(name)
    hw, hd = 7.0, 1.5
    ground_pad(L, hw, hd, "concrete", UV_CONC)
    for sx in (-1, 1):
        x = sx * 6.0
        box_all(L, ALL + ("shadow",), (x - 0.6, x + 0.6, -0.6, 0.6, 0.0, 7.0), "fair", fair_uv("white"), "metal")
        for zz in (1.0, 2.5, 4.0, 5.5):
            L["res0"].box(x - 0.65, x + 0.65, -0.65, 0.65, zz, zz + 0.12, mat="fair", uv=fair_uv("red"))
        L["res0"].prism(x, 0.0, 0.5, 7.0, 7.6, n=8, mat="fair", uv=fair_uv("red"))
        L["res0"].prism(x, 0.0, 0.08, 7.6, 8.4, n=6, mat="metal", uv=DT.UV_STEEL)
    for k in ALL + ("shadow", "res3"):
        if k == "res3":
            L[k].box(-6.6, 6.6, -0.3, 0.3, 5.6, 6.8, mat="fair", uv=fair_uv("yellow"))
            continue
        L[k].box(-5.4, 5.4, -0.3, 0.3, 5.6, 6.8, **(kw_for(k, "fair", fair_uv("yellow"), "metal") if k != "shadow" else {}))
    for (yy, nrm) in ((-0.31, -1), (0.31, 1)):
        for k in ("res0", "res1"):
            C.sign2_quad(L[k], [(-5.2, yy, 5.7), (5.2, yy, 5.7), (5.2, yy, 6.7), (-5.2, yy, 6.7)], (0, nrm, 0), "fair",
                         (0, 2), (-5.2, 5.7) if nrm < 0 else (5.2, 5.7), (5.2, 6.7) if nrm < 0 else (-5.2, 6.7))
    star = []
    for i in range(10):                                                          # star on top (flat, both sides)
        a = math.pi / 2 + 2 * math.pi * i / 10
        r = 1.1 if i % 2 == 0 else 0.45
        star.append((r * math.cos(a), r * math.sin(a)))
    for i in range(10):
        p, q = star[i], star[(i + 1) % 10]
        L["res0"].quad([(0.0, -0.32, 7.9), (p[0], -0.32, 7.9 + p[1]), (q[0], -0.32, 7.9 + q[1])], (0, -1, 0), "fair",
                       fair_uv("red"), double=True)
    bar(L["res0"], (0.0, 0.0, 6.8), (0.0, 0.0, 7.3), 0.05, "metal", DT.UV_STEEL)
    for tx in (-2.0, 0.0, 2.0):                                                  # turnstiles (block, walk round the side gates)
        for k in ("res0", "res1", "geo", "fire"):
            L[k].box(tx - 0.12, tx + 0.12, -0.5, 0.5, 0.0, 1.0, **kw_for(k, "metal", DT.UV_ALU, "metal"))
        for a in range(3):
            ang = 2 * math.pi * a / 3
            bar(L["res0"], (tx + 0.12, 0.0, 0.95), (tx + 0.12 + 0.55 * math.cos(ang), 0.55 * math.sin(ang), 0.95), 0.02,
                "metal", DT.UV_ALU)
    weeds(L, name, -hw, hw, -hd, hd, 8)
    L["mem"].lod.point("center", (0.0, 0.0, 0.0))
    return finish(L, 30000.0)


# ================================================================== landfill (ideas 13, 16)
def _slit(a, b, tol=0.06):
    """True when boxes a, b (x0, x1, y0, y1, z0, z1) do not overlap but come within tol on one axis while
    overlapping on the other two (the hull test's slit)."""
    gaps = [max(b[2 * i] - a[2 * i + 1], a[2 * i] - b[2 * i + 1]) for i in range(3)]
    return any(0.0 < g <= tol and all(gaps[j] < 0 for j in range(3) if j != i) for i, g in enumerate(gaps))


def trash_mound(L, x, y, rx, ry, h, key, placed=None):
    """Rubbish mound: convex elliptic frustum in the trash material (collides, walkable). placed: shared list of
    collision boxes; colliding junk that would leave a slit against one of them is left out (D79)."""
    placed = [] if placed is None else placed
    placed.append((x - rx, x + rx, y - ry, y + ry, 0.0, h))
    n = 10
    rot = h01("tm", key) * math.pi
    base = [(x + rx * math.cos(rot + 2 * math.pi * k / n), y + ry * math.sin(rot + 2 * math.pi * k / n), 0.0) for k in range(n)]
    tr = 0.3
    top = [(x + rx * tr * math.cos(rot + 2 * math.pi * k / n), y + ry * tr * math.sin(rot + 2 * math.pi * k / n), h) for k in range(n)]
    faces = [tuple(range(n)), tuple(range(n, 2 * n))] + [(k, (k + 1) % n, n + (k + 1) % n, n + k) for k in range(n)]
    for k in ("res0", "res1", "res2", "geo", "fire", "view"):
        L[k].solid(base + top, faces, **kw_for(k, "trash", UV_TRASH, "wood"))
    for k in range(n):
        L["road"].quad([base[k], base[(k + 1) % n], top[(k + 1) % n], top[k]], (0, 0, 1), "road_ext", UV_TILE)
    for k in range(1, n - 1):
        L["road"].quad([top[0], top[k], top[k + 1]], (0, 0, 1), "road_ext", UV_TILE)
    junk = []                                                                    # D96: no two pieces in one spot
    for i in range(10):                                                          # junk sticking out (Res0)
        a = 2 * math.pi * h01("tj", key, i)
        d = 0.3 + 0.6 * h01("tjd", key, i)
        kind = int(h01("tjk", key, i) * 4)
        if kind in (0, 2):                                                       # colliding junk stays well inside the
            d = min(d, 0.6)                                                      # mound (no side slit at its edge, D79)
        jx, jy = x + rx * d * math.cos(a), y + ry * d * math.sin(a)
        jz = h * (1.0 - d) * 0.9
        hr = (0.3, 0.35, 0.3, 0.6)[kind]
        fp = (jx - hr, jx + hr, jy - hr, jy + hr)
        if any(fp[0] < q[1] and q[0] < fp[1] and fp[2] < q[3] and q[2] < fp[3] for q in junk):
            continue                                                             # (two barrels in one spot z-fought)
        junk.append(fp)
        if kind in (0, 2):
            ry_ = 0.3 if kind == 0 else 0.3 * math.sin(math.pi / 3)            # hexagonal barrel: narrower in y
            jb = (jx - 0.3, jx + 0.3, jy - ry_, jy + ry_, jz, jz + (0.8 if kind == 0 else 0.85))
            if any(_slit(jb, p) for p in placed):
                continue
            placed.append(jb)
        if kind == 0:                                                            # white goods
            for k in ("res0", "geo", "fire", "view"):                             # collides: a head fits (D79)
                L[k].box(jx - 0.3, jx + 0.3, jy - 0.3, jy + 0.3, jz, jz + 0.8, **kw_for(k, "paint", DT.paint_uv("white"), "metal"))
        elif kind == 1:                                                          # tyre
            L["res0"].prism(jx, jy, 0.35, jz, jz + 0.25, n=10, mat="rubble", uv=UV_RUBBLE)
        elif kind == 2:                                                          # barrel
            L["res0"].prism(jx, jy, 0.3, jz, jz + 0.85, n=10, mat="rust", uv=RUST)
            for k in ("geo", "fire", "view"):                                     # collides: a head fits (D79)
                L[k].prism(jx, jy, 0.3, jz, jz + 0.85, n=6, **kw_for(k, "rust", RUST, "metal"))
        else:                                                                    # pallet / plank
            L["res0"].box(jx - 0.6, jx + 0.6, jy - 0.5, jy + 0.5, jz, jz + 0.14, mat="wood", uv=C.UV_LAMINATE)


def build_landfill():
    """40 x 40 m landfill: dirt pad, 7 rubbish mounds, a crushed-car stack, white goods, a compactor
    shed, perimeter fence (posts + wires) with a sign gate, weeds and saplings. Searchable mounds
    (memory points search_N); CE loot of every category (skyspec.LOOT)."""
    name = "Landfill"
    L = lods(name)
    hw = hd = 20.0
    ground_pad(L, hw, hd, "rubble", UV_RUBBLE)
    # D89 wedge check: mound 2 at x = 2.0 left a 0.34 m slot against mound 1 -> 3.0 (1.34 m, walkable)
    mounds = [(-11.0, 8.0, 7.0, 5.5, 3.6), (3.0, 11.0, 6.0, 5.0, 3.0), (12.0, 6.0, 5.5, 6.5, 4.0), (-12.0, -6.0, 5.0, 4.0, 2.4),
              (9.5, -8.0, 5.5, 4.5, 2.8), (-2.0, 1.5, 4.0, 3.5, 2.0), (-4.0, -12.5, 3.5, 3.0, 1.6)]
    mem = L["mem"].lod
    placed = []
    for i, (x, y, rx, ry, h) in enumerate(mounds):
        trash_mound(L, x, y, rx, ry, h, (name, i), placed)
        mem.point("search_%d" % (i + 1), (x, y - ry - 0.6, 0.0))
    for i in range(3):                                                           # crushed car stack
        z = i * 0.75
        for k in ("res0", "res1", "geo", "fire", "view"):
            L[k].box(13.0 - 0.1 * i, 17.0 + 0.1 * i, -16.0, -14.2, z, z + 0.7, **kw_for(k, "rust", (RUST, BURNT, RUST_GREY)[i], "metal"))
    L["road"].hquad(13.2, 16.8, -16.0, -14.2, 2.25, mat="road_ext", uv=UV_TILE)
    # compactor shed (closed, steel): back-left corner
    for k in ALL + ("shadow",):
        L[k].box(-18.6, -12.6, 13.4, 18.6, 0.0, 4.2, **(kw_for(k, "metal", DT.UV_PAINT, "metal") if k != "shadow" else {}))
    L["res0"].box(-17.6, -13.6, 13.37, 13.4, 0.0, 3.4, mat="rust", uv=RUST_GREY)
    L["res0"].box(-18.7, -12.5, 13.3, 18.7, 4.2, 4.4, mat="metal", uv=DT.UV_STEEL)
    # perimeter fence: concrete posts every 3 m, 9 wires; gate gap in the front with the sign
    gate = (-3.0, 3.0)
    for (axis, c, a0, a1) in (("x", -hd + 0.2, -hw + 0.2, hw - 0.2), ("x", hd - 0.2, -hw + 0.2, hw - 0.2),
                              ("y", -hw + 0.2, -hd + 0.2, hd - 0.2), ("y", hw - 0.2, -hd + 0.2, hd - 0.2)):
        segs = [(a0, gate[0]), (gate[1], a1)] if (axis == "x" and c < 0) else [(a0, a1)]
        for (s0, s1) in segs:
            n = max(1, int((s1 - s0) / 3.0))
            for i in range(n + 1):
                a = s0 + i * (s1 - s0) / n
                px, py = (a, c) if axis == "x" else (c, a)
                for k in ("res0", "res1", "geo", "fire"):
                    L[k].box(px - 0.08, px + 0.08, py - 0.08, py + 0.08, 0.0, 2.2, **kw_for(k, "concrete", UV_CONC, "concrete"))
            for zz in [0.15 + 0.25 * j for j in range(9)]:                   # D96: 9 strands (4 left 0.5 m gaps over
                p0 = (s0, c, zz) if axis == "x" else (c, s0, zz)
                p1 = (s1, c, zz) if axis == "x" else (c, s1, zz)
                bar(L["res0"], p0, p1, 0.006, "metal", DT.UV_STEEL)          # a collision you could not see)
            g = (s0, s1, c - 0.08, c + 0.08) if axis == "x" else (c - 0.08, c + 0.08, s0, s1)   # 16 cm (vehicles, sec L6)
            L["geo"].box(*g, 0.0, 2.2)                                           # wire fence blocks walking, not bullets
    for gx in gate:                                                              # gate posts + sign
        box_all(L, ALL, (gx - 0.15, gx + 0.15, -hd + 0.05, -hd + 0.35, 0.0, 3.0), "metal", DT.UV_PAINT, "metal")
    for k in ("res0", "res1"):
        L[k].box(gate[0], gate[1], -hd + 0.15, -hd + 0.25, 2.4, 3.0, mat="metal", uv=DT.UV_PAINT)
        C.sign2_quad(L[k], [(gate[0] + 0.1, -hd + 0.145, 2.45), (gate[1] - 0.1, -hd + 0.145, 2.45), (gate[1] - 0.1, -hd + 0.145, 2.95),
                            (gate[0] + 0.1, -hd + 0.145, 2.95)], (0, -1, 0), "landfill", (0, 2), (gate[0] + 0.1, 2.45), (gate[1] - 0.1, 2.95))
    L["res3"].box(-hw, hw, -hd, hd, -0.3, 0.0, mat="rubble", uv=UV_RUBBLE, skip=("-z",))
    for (x, y, rx, ry, h) in mounds:
        L["res3"].box(x - rx * 0.7, x + rx * 0.7, y - ry * 0.7, y + ry * 0.7, 0.0, h * 0.7, mat="trash", uv=UV_TRASH, skip=("-z",))
    weeds(L, name, -hw + 1, hw - 1, -hd + 1, hd - 1, 40, cells=("weeds", "dry_grass", "burdock", "bramble"))
    for i, (x, y) in enumerate(((-17.0, 0.0), (17.5, 15.0), (0.0, -17.0))):      # saplings at the edges
        C.sapling(U(L), x, y, 0.0, 3.0 + i, (name, "sap", i))
    mem.point("center", (0.0, 0.0, 0.0))
    return finish(L, 200000.0)


# loot points: skyspec.LOOT["Land_SKY_Landfill"]


# ================================================================== football ground (idea 21)
def build_pitch():
    """64 x 44 m ground: worn turf pitch 56 x 36, white lines (Res0 / Res1), goals with torn net
    frames, dugouts, scoreboard, perimeter rail with gaps."""
    name = "Stadium_Pitch"
    L = lods(name)
    hw, hd = 32.0, 22.0
    ground_pad(L, hw, hd, "concrete", UV_REVEAL)
    px, py = 28.0, 18.0
    for k in ("res0", "res1", "res2"):
        L[k].hquad(-px, px, -py, py, 0.005, mat="turf", uv=UV_TURF)
    white = DT.paint_uv("white")

    def line(x0, x1, y0, y1):
        for k in ("res0", "res1"):
            L[k].hquad(x0, x1, y0, y1, 0.008, mat="paint", uv=white)
    lw = 0.06
    line(-px, px, -py, -py + lw)
    line(-px, px, py - lw, py)
    line(-px, -px + lw, -py, py)
    line(px - lw, px, -py, py)
    line(-lw / 2, lw / 2, -py, py)
    for sx in (-1, 1):                                                           # penalty + goal areas, spots
        x_ = sx * px
        for (dx, dy) in ((13.0, 10.0), (4.5, 4.5)):
            xa, xb = sorted((x_, x_ - sx * dx))
            line(xa, xb, -dy, -dy + lw)
            line(xa, xb, dy - lw, dy)
            xl = x_ - sx * dx
            line(min(xl, xl + sx * lw), max(xl, xl + sx * lw), -dy, dy)
        L["res0"].hquad(x_ - sx * 9.0 - 0.12, x_ - sx * 9.0 + 0.12, -0.12, 0.12, 0.009, mat="paint", uv=white)
    for i in range(32):                                                          # centre circle
        a0, a1 = 2 * math.pi * i / 32, 2 * math.pi * (i + 1) / 32
        r0, r1 = 7.3, 7.36
        L["res0"].quad([(r0 * math.cos(a0), r0 * math.sin(a0), 0.008), (r0 * math.cos(a1), r0 * math.sin(a1), 0.008),
                        (r1 * math.cos(a1), r1 * math.sin(a1), 0.008), (r1 * math.cos(a0), r1 * math.sin(a0), 0.008)],
                       (0, 0, 1), "paint", white)
    for sx in (-1, 1):                                                           # goals
        gx = sx * px
        for gy in (-3.66, 3.66):
            for k in ("res0", "res1", "geo", "fire"):
                L[k].box(gx - 0.06, gx + 0.06, gy - 0.06, gy + 0.06, 0.0, 2.44, **kw_for(k, "paint", white, "metal"))
        for k in ("res0", "res1", "geo", "fire"):
            L[k].box(gx - 0.06, gx + 0.06, -3.72, 3.72, 2.38, 2.5, **kw_for(k, "paint", white, "metal"))
        bx = gx + sx * 1.8
        for gy in (-3.66, 3.66):
            bar(L["res0"], (gx, gy, 2.44), (bx, gy, 0.0), 0.025, "metal", DT.UV_STEEL)
        bar(L["res0"], (bx, -3.66, 0.02), (bx, 3.66, 0.02), 0.025, "metal", DT.UV_STEEL)
        for j in range(7):                                                       # torn net strands
            if h01(name, "net", sx, j) < 0.3:
                continue
            ny = -3.4 + j * 1.13
            bar(L["res0"], (gx, ny, 2.42), (bx, ny + 0.2 * (h01(name, "nt", sx, j) - 0.5), 0.1), 0.006, "paint", white)
    for sx in (-1, 1):                                                           # dugouts on the far touchline
        dx = sx * 6.0
        for k in ("res0", "res1", "geo", "fire", "view"):
            L[k].box(dx - 3.0, dx + 3.0, py + 2.4, py + 2.6, 0.0, 2.2, **kw_for(k, "metal", DT.UV_PAINT, "metal"))
            L[k].box(dx - 3.0, dx + 3.0, py + 1.2, py + 2.6, 2.2, 2.35, **kw_for(k, "metal", DT.UV_PAINT, "metal"))
        DT.bench(L, dx - 2.8, dx + 2.8, py + 1.9, py + 2.4)                       # against the back wall (D74 hull)
    for k in ("res0", "res1", "res2", "geo", "fire", "view"):                    # scoreboard
        L[k].box(-3.0, 3.0, -hd + 0.6, -hd + 0.9, 0.0, 0.3, **kw_for(k, "concrete", UV_CONC, "concrete"))
        L[k].box(-2.6, 2.6, -hd + 0.65, -hd + 0.85, 2.5, 4.5, **kw_for(k, "paint", DT.paint_uv("slate"), "metal"))
    for xx in (-2.3, 2.3):
        L["res0"].prism(xx, -hd + 0.75, 0.08, 0.3, 2.5, n=6, mat="metal", uv=DT.UV_PAINT)
    # perimeter rail round the pitch, gaps at the corners and on the halfway line
    for (axis, c, a0, a1) in (("x", -py - 2.0, -px - 2.0, px + 2.0), ("x", py + 1.0, -px - 2.0, px + 2.0)):
        for (s0, s1) in ((a0, -1.5), (1.5, a1)):
            rail(L, s0, s1, c - 0.03, c + 0.03, 0.0, h=1.0)
    for (axis_x, a0, a1) in ((-px - 2.0, -py - 2.0, py + 1.0), (px + 2.0, -py - 2.0, py + 1.0)):
        rail(L, axis_x - 0.03, axis_x + 0.03, a0 + 1.5, a1 - 1.5, 0.0, h=1.0)
    L["res3"].hquad(-hw, hw, -hd, hd, 0.0, mat="turf", uv=UV_TURF)
    weeds(L, name, -px, px, -py, py, 60, z=0.005, cells=("grass", "dry_grass", "weeds"))
    L["mem"].lod.point("center", (0.0, 0.0, 0.0))
    return finish(L, 150000.0)


def build_stand():
    """Covered stand 24 x 7: 6 concrete terraces with plastic seats (some missing), back wall,
    steel roof on columns, stairs at both ends (walkable), three ragged club flags on the roof (D68)."""
    name = "Stadium_Stand"
    L = lods(name)
    hw, hd = 12.0, 3.5
    ground_pad(L, hw, hd, "concrete", UV_CONC)
    n = 6
    for i in range(n):
        y0 = -hd + 0.5 + i * 0.9
        zt = 0.45 * (i + 1)
        ye = hd - 0.3 if i == n - 1 else y0 + 0.9                               # D96: one step each (nested boxes shared faces)
        box_all(L, ("res0", "res1", "res2", "geo", "view", "fire"), (-hw + 1.2, hw - 1.2, y0, ye, 0.0, zt), "concrete", UV_CONC)
        L["road"].hquad(-hw + 1.2, hw - 1.2, y0, y0 + 0.9, zt, mat="road_ext", uv=UV_TILE)
        # D70 mid LOD: runs of up to 6 existing seats merged into one seat-pan block; a run breaks at every missing
        # seat (same hash as Res0) and Res1 has no backrests, so the far LOD never draws cover the near LOD lacks
        # (security review D70 M: a solid row over a gap hid prone players that bullets still hit).
        run, xr, jr, j0 = None, -hw + 1.5, 0, 0
        while True:
            more = xr + 0.45 < hw - 1.4
            seat = more and h01(name, "seat", i, jr) > 0.15
            if seat and run is None:
                run, j0 = xr, jr
            if run is not None and (not seat or xr + 0.5 - run > 3.0):
                end = xr - 0.08 if not seat else xr + 0.42
                col = ("blue", "red", "white")[int(h01(name, "sc", i, j0) * 3)]   # = Res0 colour of the first seat (perf M)
                L["res1"].box(run, end, y0 + 0.35, y0 + 0.75, zt, zt + 0.42, mat="fair", uv=fair_uv(col), skip=("-z",))
                run = None
                if seat:
                    xr += 0.5
                    jr += 1
                    continue
            if not more:
                break
            xr += 0.5
            jr += 1
        x = -hw + 1.5
        j = 0
        while x + 0.45 < hw - 1.4:
            if h01(name, "seat", i, j) > 0.15:
                col = ("blue", "red", "white")[int(h01(name, "sc", i, j) * 3)]
                L["res0"].box(x, x + 0.42, y0 + 0.35, y0 + 0.75, zt + 0.37, zt + 0.43, mat="fair", uv=fair_uv(col))   # shell pan
                L["res0"].box(x + 0.17, x + 0.25, y0 + 0.5, y0 + 0.6, zt, zt + 0.37, mat="metal", uv=DT.UV_STEEL, skip=("-z", "+z"))  # pedestal
                # (D79: thin shell on a post - the old solid 0.42 m block was a render-only volume a head fit in)
                L["res0"].box(x, x + 0.42, y0 + 0.7, y0 + 0.78, zt + 0.42, zt + 0.8, mat="fair", uv=fair_uv(col))
            x += 0.5
            j += 1
    for sx in (-1, 1):                                                           # end stairs
        a0, a1 = (-hw, -hw + 1.2) if sx < 0 else (hw - 1.2, hw)
        for k in ("geo", "fire"):
            L[k].wedge(a0, a1, -hd + 0.5, hd - 0.3, -0.2, 0.0, 0.45 * n, **({"mat": "pen_concrete"} if k == "fire" else {}))
        for k in ("res0", "res1"):                                               # D96: drawn as the solid (sides too)
            L[k].wedge(a0, a1, -hd + 0.5, hd - 0.3, -0.2, 0.0, 0.45 * n, mat="concrete", uv=UV_CONC)
        L["road"].ramp(a0, a1, -hd + 0.5, hd - 0.3, 0.0, 0.45 * n, mat="road_ext", uv=UV_TILE)
    box_all(L, ALL + ("shadow",), (-hw, hw, hd - 0.3, hd, 0.0, 5.6), "concrete", UV_CONC)        # back wall
    for i in range(5):                                                           # columns + roof
        x = -hw + 0.3 + i * (2 * hw - 0.6) / 4
        box_all(L, ALL, (x - 0.15, x + 0.15, hd - 0.6, hd - 0.3, 0.0, 5.6), "metal", DT.UV_PAINT, "metal")
    roof = [(-hw, -hd - 0.5, 5.2), (hw, -hd - 0.5, 5.2), (hw, hd, 5.7), (-hw, hd, 5.7),
            (-hw, -hd - 0.5, 5.35), (hw, -hd - 0.5, 5.35), (hw, hd, 5.85), (-hw, hd, 5.85)]
    faces = [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    for k in ("res0", "res1", "res2", "res3", "geo", "fire", "view", "shadow"):
        L[k].solid(roof, faces, **(kw_for(k, "metal", DT.UV_PAINT, "metal") if k != "shadow" else {}))
    for i in range(5):                                                           # roof struts
        x = -hw + 0.3 + i * (2 * hw - 0.6) / 4
        bar(L["res0"], (x, hd - 0.45, 3.5), (x, -hd - 0.3, 5.2), 0.06, "metal", DT.UV_PAINT)
    for i, (x, col) in enumerate(((-8.0, "blue"), (0.0, "red"), (8.0, "white"))):   # D68: club flags on the roof (flag loop)
        for k in ("res0", "res1"):
            L[k].prism(x, hd - 0.15, 0.04, 5.85, 9.0, n=6 if k == "res0" else 4, mat="metal", uv=DT.UV_PAINT)
        torn = 0.35 + 0.4 * h01(name, "flag", i)                                  # ragged fly end
        segs = [(0.0, 0.0), (0.6, 0.12), (1.2, -0.05), (1.6 + torn, 0.1)]         # cloth ripples along -Y
        for j in range(len(segs) - 1):
            (u0, w0), (u1, w1) = segs[j], segs[j + 1]
            drop = 0.15 * j                                                       # sags towards the fly end
            L["res0"].quad([(x + w0, hd - 0.15 - u0, 8.9 - drop), (x + w1, hd - 0.15 - u1, 8.9 - drop - 0.15),
                            (x + w1, hd - 0.15 - u1, 8.0 - drop * 0.5), (x + w0, hd - 0.15 - u0, 8.0 - drop * 0.5 + 0.05)],
                           (1, 0, 0), "fair", fair_uv(col), double=True)
        L["res1"].quad([(x, hd - 0.15, 8.9), (x, hd - 1.75 - torn, 8.45), (x, hd - 1.75 - torn, 7.75), (x, hd - 0.15, 8.0)],
                       (1, 0, 0), "fair", fair_uv(col), double=True)                  # one flat sheet in Res1 (perf L)
    L["res3"].box(-hw, hw, -hd, hd, 0.0, 2.7, mat="concrete", uv=UV_CONC, skip=("-z",))
    weeds(L, name, -hw + 1.3, hw - 1.3, -hd + 0.6, hd - 0.4, 14, z=0.0)
    L["mem"].lod.point("center", (0.0, 0.0, 0.0))
    return finish(L, 120000.0)


def build_floodlight():
    """18 m lattice floodlight: 4 legs with bracing, ladder, head frame with 12 dead lamps."""
    name = "Stadium_Floodlight"
    L = lods(name)
    ground_pad(L, 1.0, 1.0, "concrete", UV_CONC)
    zt = 18.0
    for sx in (-1, 1):
        for sy in (-1, 1):
            p0 = (sx * 0.7, sy * 0.7, 0.0)
            p1 = (sx * 0.25, sy * 0.25, zt)
            for k in ("res0", "res1"):
                bar(L[k], p0, p1, 0.05, "metal", DT.UV_PAINT)
    for i in range(9):
        z0, z1 = 2.0 * i, 2.0 * (i + 1)
        r0, r1 = 0.7 - 0.45 * z0 / zt, 0.7 - 0.45 * z1 / zt
        for (a, b) in (((-1, -1), (1, -1)), ((1, -1), (1, 1)), ((1, 1), (-1, 1)), ((-1, 1), (-1, -1))):
            bar(L["res0"], (a[0] * r0, a[1] * r0, z0), (b[0] * r1, b[1] * r1, z1), 0.02, "metal", DT.UV_PAINT)
    for k in ("res2",):
        verts = [(-0.7, -0.7, 0.0), (0.7, -0.7, 0.0), (0.7, 0.7, 0.0), (-0.7, 0.7, 0.0),
                 (-0.25, -0.25, zt), (0.25, -0.25, zt), (0.25, 0.25, zt), (-0.25, 0.25, zt)]
        L[k].solid(verts, [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)],
                   **kw_for(k, "metal", DT.UV_PAINT, "metal"))
    for sx in (-1, 1):                                                           # D96: collision = the 4 legs (a solid
        for sy in (-1, 1):                                                       # frustum filled the open lattice)
            leg = [(cx + dx, cy + dy, z_) for (cx, cy, z_) in ((sx * 0.7, sy * 0.7, 0.0), (sx * 0.25, sy * 0.25, zt))
                   for dx in (-0.06, 0.06) for dy in (-0.06, 0.06)]
            for k in ("geo", "fire", "view", "shadow"):
                L[k].solid(leg, [(0, 1, 3, 2), (4, 5, 7, 6), (0, 1, 5, 4), (2, 3, 7, 6), (0, 2, 6, 4), (1, 3, 7, 5)],
                           **({"mat": "pen_metal"} if k == "fire" else {}))
    for k in ("res0", "res1", "res2", "geo", "fire"):                            # head frame, angled to the pitch
        L[k].box(-1.8, 1.8, -0.2, 0.2, zt, zt + 2.4, **kw_for(k, "metal", DT.UV_PAINT, "metal"))
    for i in range(4):
        for j in range(3):
            lx, lz = -1.35 + i * 0.9, zt + 0.4 + j * 0.8
            L["res0"].box(lx - 0.35, lx + 0.35, -0.42, -0.2, lz - 0.3, lz + 0.3, mat="metal", uv=DT.UV_STEEL)
            L["res0"].quad([(lx - 0.3, -0.425, lz - 0.25), (lx + 0.3, -0.425, lz - 0.25), (lx + 0.3, -0.425, lz + 0.25),
                            (lx - 0.3, -0.425, lz + 0.25)], (0, -1, 0), "glassfar", UV_GLASS)
    L["res3"].box(-0.4, 0.4, -0.4, 0.4, 0.0, zt + 2.4, mat="metal", uv=DT.UV_PAINT, skip=("-z",))
    L["mem"].lod.point("center", (0.0, 0.0, 0.0))
    return finish(L, 20000.0)


# ================================================================== car parks (idea 22)
def yb_ok(back, hd):
    """Wheel stop at this bay end would sit in the entrance booth corner (y near -hd)."""
    return back < -hd + 2.0


def lot(name, hw, hd, rows, metro=False):
    L = lods(name)
    for k in ALL:
        L[k].box(-hw, hw, -hd, hd, -S.SLAB_T, 0.0, **kw_for(k, "asphalt", UV_ASPH, "concrete"))
    L["road"].hquad(-hw, hw, -hd, hd, 0.0, mat="road_ext", uv=UV_TILE)
    sk = (-hw, hw, -hd, hd)
    for (x0, x1, y0, y1) in ((sk[0], sk[1], sk[2], sk[2] + 0.3), (sk[0], sk[1], sk[3] - 0.3, sk[3]), (sk[0], sk[0] + 0.3, sk[2] + 0.3, sk[3] - 0.3),
                             (sk[1] - 0.3, sk[1], sk[2] + 0.3, sk[3] - 0.3)):
        for k in ("res0", "res1", "geo", "fire"):
            kw = kw_for(k, "concrete", UV_CONC, "concrete")
            if k.startswith("res"):
                kw["skip"] = ("+z", "-z")
            L[k].box(x0, x1, y0, y1, -SKIRT, -S.SLAB_T, **kw)
        L["res0"].box(x0, x1, y0, y1, 0.0, 0.15, mat="concrete", uv=UV_CONC, skip=("-z",))    # kerb (visual)
    wrecks = []
    for r_i, (yc, face) in enumerate(rows):                                      # bay rows: 2.5 m bays, 5 m deep
        y0, y1 = (yc, yc + 5.0) if face > 0 else (yc - 5.0, yc)
        x = -hw + 1.0
        b = 0
        back = y0 if abs(y0) > abs(y1) else y1                                   # bay end at the lot edge
        while x + 2.5 <= hw - 1.0 + 1e-6:
            gap = h01(name, "worn", r_i, b)                                      # D78: worn lines, some broken
            if gap < 0.3:
                g0 = y0 + (y1 - y0) * (0.25 + 0.4 * gap)
                line_quad(L, ("res0",), x - 0.06, x + 0.06, y0, g0, "solid")
                line_quad(L, ("res0",), x - 0.06, x + 0.06, g0 + 0.6 + gap, y1, "solid")
            else:
                line_quad(L, ("res0",), x - 0.06, x + 0.06, y0, y1, "solid")
            line_quad(L, ("res1",), x - 0.06, x + 0.06, y0, y1, "solid")
            ws = h01(name, "stop", r_i, b)                                       # D78: concrete wheel stop (10 cm, render)
            if ws > 0.12 and not (x + 0.35 < -hw + 2.6 and yb_ok(back, hd)):
                yb = back - 0.6 * (1 if back > 0 else -1)
                sh = (ws - 0.5) * 0.3 if ws < 0.25 else 0.0                       # a few knocked askew
                L["res0"].box(x + 0.35 + sh, x + 2.15 + sh, yb - 0.075, yb + 0.075, 0.0, 0.1, mat="concrete", uv=UV_CONC, skip=("-z",))
            if h01(name, "car", r_i, b) < 0.4:
                wrecks.append((x + 1.25, (y0 + y1) / 2))
            x += 2.5
            b += 1
        line_quad(L, ("res0", "res1"), x - 0.06, x + 0.06, y0, y1, "solid")     # D78: UV per line (was 0-1 per metre)
    for (wx, wy) in wrecks:
        if wx - 0.95 < -hw + 2.6 and wy - 2.1 < -hd + 1.9:                       # bay beside the booth stays empty (D78 M2)
            continue
        C.wreck(L, wx, wy, 0.0, name, round(wx, 1), round(wy, 1))
    for i in range(int(2 * hw / 12)):                                            # lamp posts down the middle (dead)
        lx = -hw + 6.0 + i * 12.0
        for k in ("res0", "res1", "geo", "fire"):
            L[k].prism(lx, 0.0, 0.1, 0.0, 6.5, n=8 if k == "res0" else 4, **kw_for(k, "metal", DT.UV_PAINT, "metal"))
        L["res1"].box(lx - 0.15, lx + 0.15, -1.1, 1.1, 6.4, 6.55, mat="metal", uv=DT.UV_PAINT)
        # D78: twin outreach arms with cobra heads (dead lamps), base plate with bolts, service hatch
        for sy in (-1, 1):
            bar(L["res0"], (lx, 0.0, 6.2), (lx, sy * 0.9, 6.55), 0.035, "metal", DT.UV_PAINT)
            L["res0"].extrude_y([(lx - 0.13, 6.5), (lx + 0.13, 6.5), (lx + 0.1, 6.6), (lx - 0.1, 6.6)],
                                *sorted((sy * 0.85, sy * 1.35)), mat="metal", uv=DT.UV_PAINT)
            L["res0"].hquad(lx - 0.1, lx + 0.1, *sorted((sy * 0.9, sy * 1.3)), 6.494, mat="glassfar", uv=UV_GLASS, up=False)
        L["res0"].box(lx - 0.22, lx + 0.22, -0.22, 0.22, 0.0, 0.03, skip=("-z",), mat="metal", uv=DT.UV_STEEL)
        L["res0"].quad([(lx - 0.05, -0.106, 0.5), (lx + 0.05, -0.106, 0.5), (lx + 0.05, -0.106, 0.8), (lx - 0.05, -0.106, 0.8)],
                       (0, -1, 0), "metal", DT.UV_STEEL)                                   # service hatch
        L["res2"].prism(lx, 0.0, 0.1, 0.0, 6.5, n=4, mat="metal", uv=DT.UV_PAINT)       # far LOD post (perf D78 M5)
    for i in range(10):                                                          # oil stains, cracks with weeds
        sx_ = -hw + 2.0 + (2 * hw - 4.0) * h01(name, "oil", i)
        sy_ = -hd + 2.0 + (2 * hd - 4.0) * h01(name, "oily", i)
        L["res0"].hquad(sx_ - 0.6, sx_ + 0.6, sy_ - 0.9, sy_ + 0.9, 0.011, mat="decal_grime",
                        uv=UVRect(0, 1, (sx_ - 0.6, sy_ - 0.9), (sx_ + 0.6, sy_ + 0.9), DT.grime_rect("damp")))
    weeds(L, name, -hw + 0.5, hw - 0.5, -hd + 0.5, hd - 0.5, int(hw * hd / 12), cells=("grass", "dry_grass", "weeds"))
    # barrier booth at the entrance (front left)
    for k in ("res0", "res1", "geo", "fire", "view"):
        L[k].box(-hw + 0.6, -hw + 2.0, -hd + 0.5, -hd + 1.7, 0.0, 2.4, **kw_for(k, "paint", DT.paint_uv("white"), "wood"))
    L["res0"].box(-hw + 0.5, -hw + 2.1, -hd + 0.4, -hd + 1.8, 2.4, 2.55, mat="metal", uv=DT.UV_PAINT)
    for k in ("res0", "res1"):
        C.sign2_quad(L[k], [(-hw + 0.55, -hd + 0.39, 2.0), (-hw + 2.05, -hd + 0.39, 2.0), (-hw + 2.05, -hd + 0.39, 2.35),
                            (-hw + 0.55, -hd + 0.39, 2.35)], (0, -1, 0), "parking", (0, 2), (-hw + 0.55, 2.0), (-hw + 2.05, 2.35))
    bar(L["res0"], (-hw + 2.1, -hd + 1.1, 1.0), (-hw + 5.6, -hd + 1.6, 1.0), 0.04, "fair", fair_uv("red"))     # broken boom
    # D78: pay-and-display machine beside the booth (collides: 35 x 30 cm pillar)
    px, py = -hw + 2.175, -hd + 0.8                                              # flush with the booth (security D78 M2)
    for k in ("res0", "res1", "geo", "fire", "view"):
        L[k].box(px - 0.175, px + 0.175, py - 0.15, py + 0.15, 0.0, 1.55, **kw_for(k, "rust", RUST_GREY, "metal"))
    L["res0"].box(px - 0.19, px + 0.19, py - 0.165, py + 0.165, 1.55, 1.62, mat="rust", uv=RUST_GREY)          # hood
    L["res0"].quad([(px - 0.12, py - 0.157, 1.15), (px + 0.12, py - 0.157, 1.15), (px + 0.12, py - 0.157, 1.4), (px - 0.12, py - 0.157, 1.4)],
                   (0, -1, 0), "glassfar", UV_GLASS)                                                                  # dead display
    L["res0"].box(px - 0.1, px + 0.1, py - 0.17, py - 0.15, 0.9, 1.05, skip=("+y",), mat="metal", uv=DT.UV_STEEL)     # coin / ticket slot
    if metro:
        # sealed metro service head-house + floor hatch half hidden behind a burnt van (D63 opens it)
        mx, my = hw - 4.0, hd - 3.5
        for k in ALL + ("shadow",):
            L[k].box(mx - 1.6, mx + 1.6, my - 2.0, my + 2.0, 0.0, 2.8, **(kw_for(k, "concrete", UV_CONC, "concrete") if k != "shadow" else {}))
        L["res0"].box(mx - 0.5, mx + 0.5, my - 2.03, my - 2.0, 0.0, 2.1, mat="rust", uv=RUST_GREY)       # steel door
        L["res0"].box(mx + 0.8, mx + 1.4, my - 2.03, my - 2.0, 1.6, 2.4, mat="metal", uv=DT.UV_STEEL)    # grille
        L["res0"].box(mx - 1.7, mx + 1.7, my - 2.1, my + 2.1, 2.8, 2.95, mat="concrete", uv=UV_CONC)
        hx, hy = mx - 4.0, my - 1.0
        for k in ("res0", "res1"):
            L[k].hquad(hx - 0.7, hx + 0.7, hy - 0.7, hy + 0.7, 0.012, mat="metal", uv=DT.UV_STEEL)
        L["res0"].box(hx + 0.5, hx + 0.65, hy - 0.2, hy + 0.2, 0.012, 0.06, mat="rust", uv=RUST)
        C.wreck(L, hx - 1.4, hy + 0.2, 0.0, name, "van")
        L["mem"].lod.point("hatch", (hx, hy, 0.0))
    L["res3"].hquad(-hw, hw, -hd, hd, 0.0, mat="asphalt", uv=UV_ASPH)
    L["mem"].lod.point("center", (0.0, 0.0, 0.0))
    return finish(L, 80000.0)


# ================================================================== street props (ideas 15, 16, 17, 20)
def prop_lods(name):
    return lods(name)


def _bin_bucket(lod, cx, cy, z0, z1, r, n, mat, uv):
    """Tipping bucket of the Soviet street urn: tapered body (narrower at the bottom) + rolled rim."""
    ring0 = [(cx + 0.82 * r * math.cos(2 * math.pi * k / n), cy + 0.82 * r * math.sin(2 * math.pi * k / n), z0) for k in range(n)]
    ring1 = [(cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n), z1) for k in range(n)]
    faces = [tuple(range(n)), tuple(range(n, 2 * n))] + [(k, (k + 1) % n, n + (k + 1) % n, n + k) for k in range(n)]
    lod.solid(ring0 + ring1, faces, mat, uv)


def build_trash_bin():
    """Soviet street urn (D66 upgrade): a tapered steel bucket that tips on an axle between two square
    posts set in a concrete foot; rolled rim, two stiffening ribs, a hinged rain flap, bags overflowing,
    rust where the paint flaked. Search point in front (ActionSKY_Search)."""
    name = "TrashBin"
    L = prop_lods(name)
    green = UVBand(S.MATERIALS["rust"]["bands"]["green"], 1.0)
    z0, z1, r = 0.28, 0.92, 0.27
    for k in ("res0", "res1", "res2", "geo", "fire", "view"):                     # concrete foot
        L[k].box(-0.42, 0.42, -0.16, 0.16, 0.0, 0.08, **kw_for(k, "concrete", UV_CONC, "concrete"))
    L["shadow"].box(-0.4, 0.4, -0.28, 0.28, 0.08, 1.0)                             # one hull (perf budget)
    for sx in (-1, 1):                                                           # posts
        for k in ("res0", "res1", "res2", "geo", "fire", "view"):
            L[k].box(sx * 0.36 - 0.03, sx * 0.36 + 0.03, -0.03, 0.03, 0.08, 1.0, **(kw_for(k, "rust", RUST_GREY, "metal") if k != "shadow" else {}))
        L["res0"].box(sx * 0.36 - 0.04, sx * 0.36 + 0.04, -0.04, 0.04, 1.0, 1.02, mat="metal", uv=DT.UV_STEEL)          # caps
        L["res0"].prism(sx * 0.31, 0.0, 0.035, z1 - 0.12, z1 - 0.06, n=8, mat="metal", uv=DT.UV_STEEL, rot=0.0)       # pivot boss
    _bin_bucket(L["res0"].lod, 0.0, 0.0, z0, z1, r, 16, "rust", green)
    _bin_bucket(L["res1"].lod, 0.0, 0.0, z0, z1, r, 8, "rust", green)
    L["res2"].prism(0.0, 0.0, r, z0, z1, n=6, mat="rust", uv=green)
    for k in ("geo", "fire", "view"):
        L[k].prism(0.0, 0.0, r, z0, z1, n=8, **kw_for(k, "rust", green, "metal"))
    for zz in (z1 - 0.03, z0 + 0.2, z0 + 0.42):                                  # rim + ribs
        rr = r + 0.012 if zz > z1 - 0.1 else 0.82 * r + (r - 0.82 * r) * (zz - z0) / (z1 - z0) + 0.008
        L["res0"].prism(0.0, 0.0, rr, zz - 0.015, zz + 0.015, n=16, mat="metal", uv=DT.UV_STEEL)
    L["res0"].prism(0.0, 0.0, r - 0.02, z1 - 0.06, z1 + 0.05, n=12, mat="trash", uv=UV_TRASH)                  # overflow
    for i in range(3):
        a = 2 * math.pi * h01(name, "bag", i)
        L["res0"].prism(0.18 * math.cos(a), 0.18 * math.sin(a), 0.1 + 0.03 * i, z1, z1 + 0.12 + 0.03 * i, n=7, mat="trash", uv=UV_TRASH)
    L["res0"].solid([(-0.2, r - 0.02, z1 + 0.02), (0.2, r - 0.02, z1 + 0.02), (-0.2, r + 0.1, z1 + 0.32), (0.2, r + 0.1, z1 + 0.32),
                     (-0.2, r - 0.005, z1 + 0.02), (0.2, r - 0.005, z1 + 0.02), (-0.2, r + 0.115, z1 + 0.32), (0.2, r + 0.115, z1 + 0.32)],
                    [(0, 1, 3, 2), (4, 5, 7, 6), (0, 1, 5, 4), (2, 3, 7, 6), (0, 2, 6, 4), (1, 3, 7, 5)], "rust", green)   # rain flap, open
    for i in range(4):                                                           # flaked paint -> rust
        a = -math.pi / 2 + (h01(name, "rust", i) - 0.5) * 2.2
        zz = z0 + 0.05 + 0.45 * h01(name, "rz", i)
        cx, cy = (r + 0.004) * math.cos(a), (r + 0.004) * math.sin(a)
        tx, ty = -math.sin(a) * 0.06, math.cos(a) * 0.06
        L["res0"].quad([(cx - tx, cy - ty, zz), (cx + tx, cy + ty, zz), (cx + tx, cy + ty, zz + 0.1), (cx - tx, cy - ty, zz + 0.1)],
                       (math.cos(a), math.sin(a), 0), "rust", RUST)
    L["res3"].box(-0.4, 0.4, -0.27, 0.27, 0.0, 1.0, mat="rust", uv=green)
    L["mem"].lod.point("search", (0.0, -0.7, 0.0))
    return finish(L, 60.0)


def build_hydrant(wet):
    """Fire hydrant (D66 upgrade): bolted base flange on a concrete collar, fluted barrel, domed bonnet
    with a pentagon operating nut, two hose outlets and a pumper outlet with caps on chains, peeling red
    paint over rust; the wet one still has pressure: a dark wet stain round it."""
    name = "Hydrant_Wet" if wet else "Hydrant_Dry"
    L = prop_lods(name)
    red = fair_uv("red")
    for k in ("res0", "res1", "res2", "geo", "fire", "view", "shadow"):
        L[k].box(-0.3, 0.3, -0.3, 0.3, 0.0, 0.05, **(kw_for(k, "concrete", UV_CONC, "concrete") if k != "shadow" else {}))
        nn = 16 if k == "res0" else 6
        kw = kw_for(k, "fair", red, "metal") if k != "shadow" else {}
        L[k].prism(0.0, 0.0, 0.19, 0.05, 0.11, n=nn, **kw)
        L[k].prism(0.0, 0.0, 0.125, 0.11, 0.66, n=nn, **kw)
    for i in range(8):                                                           # flange bolts
        a = 2 * math.pi * i / 8
        L["res0"].prism(0.165 * math.cos(a), 0.165 * math.sin(a), 0.014, 0.11, 0.13, n=4, mat="metal", uv=DT.UV_STEEL)
    for i in range(8):                                                           # barrel flutes
        a = 2 * math.pi * (i + 0.5) / 8
        L["res0"].box(0.126 * math.cos(a) - 0.012, 0.126 * math.cos(a) + 0.012, 0.126 * math.sin(a) - 0.012,
                      0.126 * math.sin(a) + 0.012, 0.16, 0.6, mat="fair", uv=red)
    L["res0"].prism(0.0, 0.0, 0.145, 0.66, 0.71, n=16, mat="fair", uv=red)                                      # bonnet flange
    for (r_, z0, z1) in ((0.13, 0.71, 0.76), (0.1, 0.76, 0.81), (0.06, 0.81, 0.84)):                           # dome
        L["res0"].prism(0.0, 0.0, r_, z0, z1, n=14, mat="fair", uv=red)
    L["res0"].prism(0.0, 0.0, 0.026, 0.84, 0.88, n=5, mat="metal", uv=DT.UV_STEEL)                             # operating nut
    L["res1"].prism(0.0, 0.0, 0.12, 0.66, 0.84, n=6, mat="fair", uv=red)
    for (dx, dy, big) in ((0.15, 0.0, False), (-0.15, 0.0, False), (0.0, -0.15, True)):                          # outlets
        ln, rr = (0.09, 0.07) if big else (0.07, 0.045)
        zc = 0.46
        if dx:
            x0, x1 = sorted((dx * 0.8, dx * 0.8 + (ln if dx > 0 else -ln)))
            prof = [(rr * math.cos(2 * math.pi * k / 10), zc + rr * math.sin(2 * math.pi * k / 10)) for k in range(10)]
            L["res0"].extrude_x(prof, x0, x1, mat="fair", uv=red)
            cap = [(1.15 * rr * math.cos(2 * math.pi * k / 6), zc + 1.15 * rr * math.sin(2 * math.pi * k / 6)) for k in range(6)]
            c0 = x1 if dx > 0 else x0 - 0.03
            L["res0"].extrude_x(cap, c0, c0 + 0.03, mat="metal", uv=DT.UV_STEEL)
            C.bar(L["res0"].lod, (dx * 0.8, -0.02, zc - rr), ((x1 if dx > 0 else x0), -0.03, zc - rr - 0.06), 0.004, "metal", DT.UV_STEEL)
        else:
            y0, y1 = -0.12 - ln, -0.12
            prof = [(rr * math.cos(2 * math.pi * k / 12), zc + rr * math.sin(2 * math.pi * k / 12)) for k in range(12)]
            L["res0"].extrude_y(prof, y0, y1, mat="fair", uv=red)
            cap = [(1.15 * rr * math.cos(2 * math.pi * k / 6), zc + 1.15 * rr * math.sin(2 * math.pi * k / 6)) for k in range(6)]
            L["res0"].extrude_y(cap, y0 - 0.035, y0, mat="metal", uv=DT.UV_STEEL)
            C.bar(L["res0"].lod, (0.06, -0.12, zc - 0.05), (0.07, y0 - 0.02, zc - rr - 0.08), 0.004, "metal", DT.UV_STEEL)
    for i in range(5):                                                           # peeling paint -> rust
        a = 2 * math.pi * h01(name, "pr", i)
        zz = 0.15 + 0.4 * h01(name, "pz", i)
        cx, cy = 0.1265 * math.cos(a), 0.1265 * math.sin(a)
        tx, ty = -math.sin(a) * 0.03, math.cos(a) * 0.03
        L["res0"].quad([(cx - tx, cy - ty, zz), (cx + tx, cy + ty, zz), (cx + tx, cy + ty, zz + 0.07), (cx - tx, cy - ty, zz + 0.07)],
                       (math.cos(a), math.sin(a), 0), "rust", RUST)
    if wet:                                                                      # wet stain + drip (it still has pressure)
        L["res0"].hquad(-0.5, 0.5, -0.8, 0.2, 0.052, mat="decal_grime",
                        uv=UVRect(0, 1, (-0.5, -0.8), (0.5, 0.2), DT.grime_rect("damp")))
    L["res3"].prism(0.0, 0.0, 0.13, 0.0, 0.84, n=4, mat="fair", uv=red)
    L["mem"].lod.point("water", (0.0, -0.6, 0.0))
    return finish(L, 300.0)


def build_siren():
    """Civil-defence siren: 10 m steel pole with steps, a rotor with 4 horn mouths, a control box."""
    name = "SirenTower"
    L = prop_lods(name)
    ground_pad(L, 1.0, 1.0, "concrete", UV_CONC)
    zt = 10.0
    for k in ("res0", "res1", "res2", "geo", "fire", "view", "shadow"):
        nn = 12 if k == "res0" else 6
        L[k].prism(0.0, 0.0, 0.16, 0.0, zt, n=nn, **(kw_for(k, "metal", DT.UV_PAINT, "metal") if k != "shadow" else {}))
    for k in ("res0", "res1", "res2", "geo", "fire"):
        L[k].prism(0.0, 0.0, 0.45, zt, zt + 0.9, n=12 if k == "res0" else 6, **kw_for(k, "rust", RUST_GREY, "metal"))
    for a in range(4):                                                           # horn mouths
        ang = math.pi / 2 * a
        cx, cy = 0.75 * math.cos(ang), 0.75 * math.sin(ang)
        prof_r = 0.32
        L["res0"].prism(cx, cy, prof_r, zt + 0.15, zt + 0.75, n=10, mat="rust", uv=RUST_GREY, rot=ang)
        L["res0"].prism(cx * 1.05, cy * 1.05, prof_r * 0.8, zt + 0.2, zt + 0.7, n=10, mat="paint", uv=DT.paint_uv("slate"), rot=ang)
    L["res0"].prism(0.0, 0.0, 0.5, zt + 0.9, zt + 1.05, n=12, mat="metal", uv=DT.UV_STEEL)
    for k in ("res0", "res1", "geo", "fire"):                                    # control box
        L[k].box(-0.25, 0.25, -0.38, -0.13, 1.2, 1.9, **kw_for(k, "paint", DT.paint_uv("sage"), "metal"))   # on the pole (D74)
    for i in range(int((zt - 2.5) / 0.4)):                                       # step bolts (visual)
        z = 2.5 + i * 0.4
        if i % 2:
            L["res0"].box(0.16, 0.34, -0.02, 0.02, z, z + 0.03, mat="metal", uv=DT.UV_STEEL)
        else:
            L["res0"].box(-0.34, -0.16, -0.02, 0.02, z, z + 0.03, mat="metal", uv=DT.UV_STEEL)
    L["res3"].prism(0.0, 0.0, 0.3, 0.0, zt + 1.0, n=4, mat="metal", uv=DT.UV_PAINT)
    L["mem"].lod.point("siren", (0.0, 0.0, zt + 0.5))
    return finish(L, 2000.0)


# Wreck_GarbageTruck: build_vehicles.py (D64 parametric vehicle bodies)


# ================================================================== roads (ideas 2, 23)
VIA_H = 7.0          # viaduct deck top above the street


def deck(L, x0, x1, y0, y1, z, t=0.9, barriers=True, mats=("concrete", None)):
    """Road deck (box girder) with asphalt surface, lane marks, jersey barriers, drainage spouts."""
    for k in ALL + ("shadow",):
        L[k].box(x0, x1, y0, y1, z - t, z, **(kw_for(k, "concrete", UV_CONC, "concrete") if k != "shadow" else {}))
    for k in ("res0", "res1"):
        L[k].hquad(x0 + 0.5, x1 - 0.5, y0, y1, z + 0.005, mat="asphalt", uv=UV_ASPH)
    L["road"].hquad(x0, x1, y0, y1, z, mat="road_asphalt", uv=UV_ASPH)
    mark = UVRect(1, 0, (0, 0), (1, 1), (0.0, 1 - S.MATERIALS["roadmark"]["bands"]["dashed"][1], 1.0,
                                         1 - S.MATERIALS["roadmark"]["bands"]["dashed"][0]))
    for k in ("res0", "res1"):
        L[k].hquad(-0.08, 0.08, y0, y1, z + 0.01, mat="roadmark",
                   uv=UVRect(1, 0, (y0, -0.08), (y1, 0.08), (0.0, mark.uv[1], (y1 - y0) / 6.0, mark.uv[3])))
    if barriers:
        for sx in (-1, 1):
            xb = sx * (x1 - 0.25) if sx > 0 else x0 + 0.25
            prof = [(xb - 0.3, z), (xb + 0.3, z), (xb + 0.1, z + 0.25), (xb + 0.08, z + 0.85), (xb - 0.08, z + 0.85), (xb - 0.1, z + 0.25)]
            hull = K.convex_profile(prof)                                       # D91: Geometry must be convex
            for k in ("res0", "res1", "res2", "geo", "fire", "view"):
                L[k].extrude_y(prof if k.startswith("res") else hull, y0, y1, **kw_for(k, "concrete", UV_CONC, "concrete"))


def build_viaduct_straight():
    """12 m viaduct segment at VIA_H: box-girder deck, barriers, a central pier with a hammerhead cap,
    a lamp post on one side (dead)."""
    name = "Viaduct_Straight"
    L = lods(name)
    hw, hd = 6.0, 6.0
    deck(L, -5.0, 5.0, -hd, hd, VIA_H)
    for k in ALL + ("shadow",):
        kw = kw_for(k, "concrete", UV_CONC, "concrete") if k != "shadow" else {}
        L[k].box(-3.5, 3.5, -0.8, 0.8, VIA_H - 1.6, VIA_H - 0.9, **kw)          # pier cap
        L[k].box(-0.9, 0.9, -0.9, 0.9, -SKIRT, VIA_H - 1.6, **kw)               # pier
    L["res0"].box(-0.95, 0.95, -0.95, 0.95, 0.0, 1.2, mat="decal_grime",
                  uv=UVRect(0, 2, (-0.95, 0.0), (0.95, 1.2), DT.grime_rect("damp")), skip=("-z", "+z"))
    for k in ("res0", "res1"):                                                    # lamp post (dead)
        L[k].prism(4.6, 0.0, 0.08, VIA_H + 0.85, VIA_H + 8.0, n=8 if k == "res0" else 4, mat="metal", uv=DT.UV_PAINT)
    L["res0"].box(2.6, 4.6, -0.12, 0.12, VIA_H + 7.9, VIA_H + 8.0, mat="metal", uv=DT.UV_PAINT)
    L["res0"].box(2.4, 2.9, -0.2, 0.2, VIA_H + 7.75, VIA_H + 7.9, mat="metal", uv=DT.UV_STEEL)
    for i in range(3):                                                           # weeds in the gutter, runoff stains
        L["res0"].quad([(-5.0, -hd + 2 + 4 * i, VIA_H - 0.9), (-5.0, -hd + 3.5 + 4 * i, VIA_H - 0.9),
                        (-5.0, -hd + 3.5 + 4 * i, VIA_H - 0.1), (-5.0, -hd + 2 + 4 * i, VIA_H - 0.1)], (-1, 0, 0), "decal_grime",
                       UVRect(1, 2, (-hd + 2 + 4 * i, VIA_H - 0.9), (-hd + 3.5 + 4 * i, VIA_H - 0.1), DT.grime_rect("runoff")))
    C.plant_tuft(U(L), -4.3, 2.0, VIA_H, 0.8, 0.5, "dry_grass", (name, "g"))
    viaduct_detail(L, name, hd)
    L["res3"].box(-5.0, 5.0, -hd, hd, VIA_H - 0.9, VIA_H + 0.85, mat="concrete", uv=UV_CONC)
    L["res3"].box(-0.9, 0.9, -0.9, 0.9, 0.0, VIA_H - 0.9, mat="concrete", uv=UV_CONC, skip=("-z", "+z"))
    L["mem"].lod.point("center", (0.0, 0.0, VIA_H))
    return finish(L, 400000.0)


def viaduct_detail(L, name, hd):
    """D75 close-up pass (render only, collision unchanged): soffit ribs, spalled concrete with exposed rebar on the pier, steel
    expansion joints at both ends, drain spouts through the deck edge with rust streaks under them."""
    zd = VIA_H - 0.9                                                             # deck soffit
    for x in (-3.2, 0.0, 3.2):                                                   # longitudinal ribs
        for k in ("res0", "res1"):
            L[k].box(x - 0.2, x + 0.2, -hd, hd, zd - 0.45, zd, mat="concrete", uv=UV_CONC, skip=("+z",))
    for i, (z0, sy) in enumerate(((2.1, -1), (4.4, 1))):                          # spalls with rebar
        y = sy * 0.901
        L["res0"].box(-0.4, 0.3, min(y, y + sy * 0.01), max(y, y + sy * 0.01), z0, z0 + 0.5, mat="rust",
                      uv=UVBand(S.MATERIALS["rust"]["bands"]["rust"], 1.0))
        for j in range(3):
            zz = z0 + 0.1 + j * 0.15
            bar(L["res0"], (-0.38, y + sy * 0.01, zz), (0.28, y + sy * 0.01, zz), 0.01, "rust",
                UVBand(S.MATERIALS["rust"]["bands"]["rust"], 1.0))
    for y in (-hd + 0.02, hd - 0.02):                                            # expansion joints (15 mm lift: Res1)
        for k in ("res0", "res1"):
            L[k].box(-4.5, 4.5, y - 0.08, y + 0.08, VIA_H + 0.015, VIA_H + 0.021, mat="metal", uv=DT.UV_STEEL)
    for sx in (-1, 1):                                                           # drain spouts + streaks
        for y in (-3.0, 3.0):
            x = sx * 5.0
            bar(L["res0"], (x - sx * 0.1, y, VIA_H - 0.3), (x + sx * 0.35, y, VIA_H - 0.45), 0.05, "metal", DT.UV_STEEL)
            q = [(x + sx * 0.005, y - 0.5, VIA_H - 3.0), (x + sx * 0.005, y + 0.5, VIA_H - 3.0),       # D96: 1 m wide
                 (x + sx * 0.005, y + 0.5, VIA_H - 0.95), (x + sx * 0.005, y - 0.5, VIA_H - 0.95)]       # (0.5 m: 33x stretch)
            L["res0"].quad(q if sx > 0 else q[::-1], (sx, 0, 0), "decal_grime",
                           UVRect(1, 2, (y - 0.5, VIA_H - 3.0), (y + 0.5, VIA_H - 0.95), DT.grime_rect("runoff")))


def build_viaduct_ramp():
    """48 m ramp from street level to VIA_H: earth-filled between retaining walls (solid, closed),
    deck surface, barriers on the upper half, end at -Y on the street, +Y joins a viaduct segment."""
    name = "Viaduct_Ramp"
    L = lods(name)
    hw, hd = 6.0, 24.0
    y0, y1 = -hd, hd
    for k in ("geo", "fire", "view"):
        L[k].wedge(-5.0, 5.0, y0, y1, -SKIRT, 0.05, VIA_H, **({"mat": "pen_concrete"} if k == "fire" else {}))
    for k in ("res0", "res1"):
        L[k].ramp(-4.5, 4.5, y0, y1, 0.055, VIA_H + 0.005, mat="asphalt", uv=UV_ASPH)
        L[k].ramp(-5.0, -4.5, y0, y1, 0.05, VIA_H, mat="concrete", uv=UV_CONC)
        L[k].ramp(4.5, 5.0, y0, y1, 0.05, VIA_H, mat="concrete", uv=UV_CONC)
    L["res2"].ramp(-5.0, 5.0, y0, y1, 0.05, VIA_H, mat="asphalt", uv=UV_ASPH)
    L["road"].ramp(-5.0, 5.0, y0, y1, 0.05, VIA_H, mat="road_asphalt", uv=UV_ASPH)
    for sx in (-1, 1):                                                           # retaining walls (sloped top) + parapet
        xa, xb = (5.0, 5.4) if sx > 0 else (-5.4, -5.0)
        verts = [(xa, y0, -SKIRT), (xa, y1, -SKIRT), (xa, y1, VIA_H + 1.0), (xa, y0, 1.0),
                 (xb, y0, -SKIRT), (xb, y1, -SKIRT), (xb, y1, VIA_H + 1.0), (xb, y0, 1.0)]
        faces = [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
        for k in ALL + ("shadow",):
            L[k].solid(verts, faces, **(kw_for(k, "concrete", UV_CONC, "concrete") if k != "shadow" else {}))
        outer = xb if sx > 0 else xa
        for i in range(8):                                                       # grime + graffiti-free stains on the walls
            ya = y0 + i * 6.0
            za_top = 1.0 + (VIA_H) * (ya - y0) / (y1 - y0)
            L["res0"].quad([(outer + sx * 0.005, ya, 0.0), (outer + sx * 0.005, ya + 5.0, 0.0),
                            (outer + sx * 0.005, ya + 5.0, za_top * 0.6), (outer + sx * 0.005, ya, za_top * 0.6)],
                           (sx, 0, 0), "decal_grime", UVRect(1, 2, (ya, 0.0), (ya + 5.0, za_top * 0.6), DT.grime_rect("moss")))
    mark = S.MATERIALS["roadmark"]["bands"]["dashed"]
    for k in ("res0", "res1"):
        L[k].quad([(-0.08, y0, 0.065), (0.08, y0, 0.065), (0.08, y1, VIA_H + 0.015), (-0.08, y1, VIA_H + 0.015)], (0, 0, 1),
                  "roadmark", UVRect(1, 0, (y0, -0.08), (y1, 0.08), (0.0, 1 - mark[1], (y1 - y0) / 6.0, 1 - mark[0])))
    for k in ("res0", "res1", "res2"):                                           # D96: abutment face at the high end
        L[k].quad([(-5.0, y1, -SKIRT), (5.0, y1, -SKIRT), (5.0, y1, VIA_H), (-5.0, y1, VIA_H)], (0, 1, 0), "concrete", UV_CONC)
    L["res3"].ramp(-5.4, 5.4, y0, y1, 0.0, VIA_H + 1.0, mat="concrete", uv=UV_CONC)
    for i in range(6):
        C.plant_tuft(U(L), (-4.6 if i % 2 else 4.6), y0 + 3 + i * 7.5, 0.05 + VIA_H * (3 + i * 7.5) / (y1 - y0), 0.7, 0.5,
                     ("grass", "dry_grass")[i % 2], (name, "g", i))
    L["mem"].lod.point("center", (0.0, 0.0, 0.0))
    return finish(L, 800000.0)


def build_tunnel(portal=False):
    """Cut-and-cover road tunnel (above ground, ROADMAP idea 2): 0.6 m walls, 1 m roof slab at 5.5 m,
    side walkways, dead strip lights; earth berms both sides (walkable) and a paved deck on top.
    Portal: headwall with the tunnel mouth, wing walls, hazard band, sign."""
    name = "Tunnel_Portal" if portal else "Tunnel_Straight"
    L = lods(name)
    hd = 6.0                                                                     # portal = end cell with the headwall at -Y
    y0, y1 = -hd, hd
    zr0, zr1 = 5.5, 6.5
    # road surface
    for k in ("res0", "res1", "res2", "geo", "fire", "view"):
        L[k].box(-6.0, 6.0, y0, y1, -S.SLAB_T, 0.0, **kw_for(k, "asphalt", UV_ASPH, "concrete"))
    L["road"].hquad(-6.0, 6.0, y0, y1, 0.0, mat="road_asphalt", uv=UV_ASPH)
    for sx in (-1, 1):                                                           # walkways
        xa, xb = (4.6, 6.0) if sx > 0 else (-6.0, -4.6)
        box_all(L, ("res0", "res1", "geo", "fire", "view"), (xa, xb, y0, y1, 0.0, 0.25), "concrete", UV_CONC)
        L["road"].hquad(xa, xb, y0, y1, 0.25, mat="road_ext", uv=UV_TILE)
    for sx in (-1, 1):                                                           # walls
        xa, xb = (6.0, 6.6) if sx > 0 else (-6.6, -6.0)
        box_all(L, ALL + ("shadow",), (xa, xb, y0, y1, -SKIRT, zr0), "concrete", UV_CONC)   # D96: up to the slab, not
        xt = xa - 0.006 if sx > 0 else xb + 0.006                                # through it; tiles 6 mm off the wall
        for i in range(int((y1 - y0) / 2.0)):                                    # wall tiles band + stains (inside)
            ya = y0 + i * 2.0
            L["res0"].quad([(xt, ya, 0.3), (xt, ya + 2.0, 0.3), (xt, ya + 2.0, 2.4), (xt, ya, 2.4)], (-sx, 0, 0), "tile", UV_TILE)
    ys = y0 + 0.3 if portal else y0                                             # D96: the portal headwall is the first 30 cm
    box_all(L, ALL + ("shadow",), (-6.6, 6.6, ys, y1, zr0, zr1), "concrete", UV_CONC)               # roof slab
    for k in ("res0", "res1"):
        L[k].hquad(-6.0, 6.0, y0, y1, zr0 - 0.006, mat="concrete", uv=UV_CONC, up=False)
    for sx in (-1, 1):                                                           # dead strip lights
        for i in range(int((y1 - y0) / 3.0)):
            ya = y0 + 0.5 + i * 3.0
            L["res0"].box(sx * 4.0 - 0.1, sx * 4.0 + 0.1, ya, ya + 2.0, zr0 - 0.12, zr0, mat="metal", uv=DT.UV_STEEL)
    # earth berms both sides (walkable slopes up to the deck) and the paved deck on top
    for sx in (-1, 1):
        xa, xb = (6.6, 12.0) if sx > 0 else (-12.0, -6.6)
        lo, hi = (xb, xa) if sx > 0 else (xa, xb)
        verts = [(lo if sx > 0 else hi, y0, 0.0), (lo if sx > 0 else hi, y1, 0.0), (hi if sx > 0 else lo, y1, 0.0), (hi if sx > 0 else lo, y0, 0.0),
                 (hi if sx > 0 else lo, y0, zr1), (hi if sx > 0 else lo, y1, zr1)]
        faces = [(0, 1, 2, 3), (3, 2, 5, 4), (0, 3, 4), (1, 5, 2), (0, 4, 5, 1)]
        for k in ("res0", "res1", "res2", "geo", "fire", "view"):
            L[k].solid(verts, faces, **kw_for(k, "turf", UV_TURF, "concrete"))
        L["road"].quad([verts[0], verts[1], verts[5], verts[4]], (sx * 0.8, 0, 0.6), "road_ext", UV_TILE)
        U_ = U(L)
        for i in range(5):
            C.plant_tuft(U_, (xa + xb) / 2 + sx * 1.5 * (h01(name, "b", sx, i) - 0.5), y0 + 0.6 + (y1 - y0 - 1.2) * i / 4,
                         zr1 * (1 - abs((xa + xb) / 2 - (6.6 if sx > 0 else -6.6)) / 5.4), 0.8, 0.6,
                         ("grass", "weeds", "dry_grass")[i % 3], (name, "berm", sx, i))
    for k in ("res0", "res1", "res2"):
        L[k].hquad(-6.6, 6.6, y0, y1, zr1 + 0.005, mat="paver", uv=UV_TILE)
    L["road"].hquad(-6.6, 6.6, y0, y1, zr1, mat="road_ext", uv=UV_TILE)
    if portal:
        for k in ALL + ("shadow",):                                              # headwall over the mouth at -Y
            L[k].box(-6.7, 6.7, y0, y0 + 0.3, zr0 - 0.05, zr1 + 1.0,         # D96: the slab starts behind it (inside the
                     **(kw_for(k, "stone", DT.stone_uv("granite"), "concrete") if k != "shadow" else {}))   # slab it z-fought)
        for i in range(8):                                                       # hazard chevrons over the mouth
            xa = -6.0 + i * 1.5
            L["res0"].quad([(xa, y0 - 0.005, zr0 + 0.05), (xa + 0.75, y0 - 0.005, zr0 + 0.05), (xa + 0.75, y0 - 0.005, zr0 + 0.45),
                            (xa, y0 - 0.005, zr0 + 0.45)], (0, -1, 0), "fair", fair_uv("yellow" if i % 2 else "white"))
        C.sign2_quad(L["res0"], [(-3.0, y0 - 0.008, zr1 + 0.2), (3.0, y0 - 0.008, zr1 + 0.2), (3.0, y0 - 0.008, zr1 + 0.8),
                                 (-3.0, y0 - 0.008, zr1 + 0.8)], (0, -1, 0), "danger", (0, 2), (-3.0, zr1 + 0.2), (3.0, zr1 + 0.8))
        # (D96: no deck rail - the headwall rises 1 m above the deck; a rail 0.5 m behind it left a wedge slot)
    L["res3"].box(-12.0, 12.0, y0, y1, 0.0, zr1, mat="turf", uv=UV_TURF, skip=("-z",))
    L["mem"].lod.point("center", (0.0, 0.0, 0.0))
    return finish(L, 600000.0)


def build_bridge():
    """The bridge (idea 23): 96 m two-truss steel bridge, the only crossing of the river. Deck at 0
    (its abutments carry it), river piers at +-24 m. Mid-span checkpoint: jersey barriers in a
    chicane, sandbag nests, barbed wire, STOP - DANGER signs; a military convoy pile-up (the best
    loot on the map, skyspec LOOT) between them; sniper nests on the truss portals. Long open
    sightlines on both approaches."""
    name = "Bridge_Long"
    L = lods(name)
    hl, hw = 48.0, 7.0
    # deck in 12 m segments (convex parts) with asphalt + walkway kerbs
    for i in range(8):
        xa, xb = -hl + i * 12.0, -hl + (i + 1) * 12.0
        for k in ALL:
            L[k].box(xa, xb, -hw, hw, -1.2, 0.0, **kw_for(k, "concrete", UV_CONC, "concrete"))
        L["shadow"].box(xa, xb, -hw, hw, -1.2, 0.0)
    for k in ("res0", "res1"):
        L[k].hquad(-hl, hl, -5.0, 5.0, 0.005, mat="asphalt", uv=UV_ASPH)
        L[k].hquad(-hl, hl, -hw + 0.3, -5.0, 0.205, mat="concrete", uv=UV_CONC)
        L[k].hquad(-hl, hl, 5.0, hw - 0.3, 0.205, mat="concrete", uv=UV_CONC)
    L["road"].hquad(-hl, hl, -5.0, 5.0, 0.0, mat="road_asphalt", uv=UV_ASPH)
    for (b0, b1) in ((-hw + 0.3, -5.0), (5.0, hw - 0.3)):
        box_all(L, ("geo", "fire"), (-hl, hl, b0, b1, 0.0, 0.2), "concrete", UV_CONC)
        L["road"].hquad(-hl, hl, b0, b1, 0.2, mat="road_ext", uv=UV_TILE)
    # two Warren trusses (6 m deep): chords, verticals, diagonals; portal bracing over the deck
    green = RUST_GREEN
    for sy in (-hw + 0.15, hw - 0.15):
        for z in (0.2, 6.2):
            for k in ("res0", "res1", "res2"):
                bar(L[k], (-hl + 0.03, sy, z), (hl - 0.03, sy, z), 0.25 if k != "res2" else 0.35, "rust", green)  # D96: ends
                                                                         # off the deck end face
        bar(L["geo"], (-hl, sy, 6.2), (hl, sy, 6.2), 0.25)
        bar(L["fire"], (-hl, sy, 6.2), (hl, sy, 6.2), 0.25, "pen_metal")
        for i in range(17):
            x = -hl + i * 6.0
            for k in ("res0", "res1"):
                bar(L[k], (x, sy, 0.2), (x, sy, 6.2), 0.15, "rust", green)
            for k in ("geo", "fire"):
                L[k].box(x - 0.15, x + 0.15, sy - 0.15, sy + 0.15, 0.2, 6.2, **({"mat": "pen_metal"} if k == "fire" else {}))
            if i < 16:
                a, b = ((x, 0.2), (x + 6.0, 6.2)) if i % 2 == 0 else ((x, 6.2), (x + 6.0, 0.2))
                bar(L["res0"], (a[0], sy, a[1]), (b[0], sy, b[1]), 0.12 if i % 2 == 0 else 0.113, "rust", green)  # D96
                if i % 2 == 0:
                    bar(L["res1"], (a[0], sy, a[1]), (b[0], sy, b[1]), 0.15, "rust", green)
        rail(L, -hl, hl, sy - 0.5 * (1 if sy > 0 else -1) - 0.03, sy - 0.5 * (1 if sy > 0 else -1) + 0.03, 0.2, h=1.1)
    for x in (-hl, -24.0, 0.0, 24.0, hl):                                        # portal / top bracing
        bar(L["res0"], (x, -hw + 0.15, 6.2), (x, hw - 0.15, 6.2), 0.15, "rust", green)
        bar(L["res0"], (x, -hw + 0.15, 4.6), (x, 0.0, 6.2), 0.08, "rust", green)
        bar(L["res0"], (x, hw - 0.15, 4.6), (x, 0.0, 6.2), 0.08, "rust", green)
        bar(L["res1"], (x, -hw + 0.15, 6.2), (x, hw - 0.15, 6.2), 0.2, "rust", green)
    # piers in the river and abutment walls at the ends
    for x in (-24.0, 24.0):
        for k in ("res0", "res1", "res2", "geo", "fire", "view", "shadow"):
            kw = kw_for(k, "concrete", UV_CONC, "concrete") if k != "shadow" else {}
            L[k].box(x - 1.5, x + 1.5, -hw + 0.5, hw - 0.5, -14.0, -1.2, **kw)
        L["res0"].box(x - 1.55, x + 1.55, -hw + 0.45, hw - 0.45, -14.0, -9.0, mat="decal_grime",
                      uv=UVRect(0, 2, (x - 1.55, -14.0), (x + 1.55, -9.0), DT.grime_rect("damp")), skip=("-z", "+z"))
    for x in (-hl, hl):
        for k in ("res0", "res1", "res2", "geo", "fire", "view"):
            L[k].box(x - 1.0 if x < 0 else x - 1.0, x + 1.0, -hw - 0.5, hw + 0.5, -10.0, -1.2, **kw_for(k, "concrete", UV_CONC, "concrete"))
    # checkpoint chicane at mid span: jersey barriers, sandbag nests, wire, signs
    jersey = [(-6.0, -5.0, -1.0), (-3.0, 1.0, 5.0), (3.0, -5.0, -1.0), (6.0, 1.0, 5.0)]
    for (x, ya, yb) in jersey:
        prof = [(ya, 0.0), (yb, 0.0), (yb - 0.2, 0.3), (yb - 0.3, 1.0), (ya + 0.3, 1.0), (ya + 0.2, 0.3)]
        hull = K.convex_profile(prof)                                            # D91: Geometry must be convex (the
        for k in ("res0", "res1", "res2", "geo", "fire", "view"):                  # jersey knee is not; <= 9 cm off)
            pr = prof if k.startswith("res") else hull
            L[k].extrude_x([(p[0], p[1]) for p in pr], x - 0.3, x + 0.3, **kw_for(k, "concrete", UV_CONC, "concrete"))
    for (x, y) in ((-10.0, -3.5), (10.0, 3.5)):                                  # sandbag nests (half rings)
        for i in range(5):
            a0 = math.pi * i / 5
            bx, by = x + 1.6 * math.cos(a0) * (-1 if x < 0 else 1), y + 1.6 * math.sin(a0) * (1 if y < 0 else -1)
            for k in ("res0", "res1", "geo", "fire", "view"):
                L[k].box(bx - 0.5, bx + 0.5, by - 0.35, by + 0.35, 0.0, 1.1, **kw_for(k, "fabric", C.UV_FAB["beige"], "wood"))
    for (x, ya, yb) in ((-14.0, -5.0, 5.0), (14.0, -5.0, 5.0)):                  # barbed wire coils (visual)
        n = int((yb - ya) / 0.3)
        for i in range(n):
            y = ya + i * 0.3
            bar(L["res0"], (x - 0.4, y, 0.05), (x + 0.4, y + 0.15, 0.85), 0.006, "metal", DT.UV_STEEL)
            bar(L["res0"], (x + 0.4, y + 0.15, 0.85), (x - 0.4, y + 0.3, 0.05), 0.006, "metal", DT.UV_STEEL)
    for (x, nrm) in ((-16.0, -1), (16.0, 1)):
        for k in ("res0", "res1", "geo", "fire"):
            L[k].box(x - 0.05, x + 0.05, -0.05, 0.05, 0.0, 2.6, **kw_for(k, "metal", DT.UV_PAINT, "metal"))
        for k in ("res0", "res1"):
            L[k].box(x - 0.03, x + 0.03, -1.4, 1.4, 2.0, 2.6, mat="metal", uv=DT.UV_PAINT)
        C.sign2_quad(L["res0"], [(x + nrm * 0.032, -1.35 * -nrm, 2.05), (x + nrm * 0.032, 1.35 * -nrm, 2.05),
                                 (x + nrm * 0.032, 1.35 * -nrm, 2.55), (x + nrm * 0.032, -1.35 * -nrm, 2.55)], (nrm, 0, 0), "danger",
                     (1, 2), (-1.35 * -nrm, 2.05), (1.35 * -nrm, 2.55))
    # convoy pile-up between the barriers: burnt trucks / cars (static), an overturned van
    cars = [(-1.2, -2.8, 0), (1.8, 2.6, 1), (-8.0, 2.8, 2), (8.5, -3.0, 3), (-20.0, -2.5, 4), (21.0, 2.0, 5)]
    for (x, y, i) in cars:
        C.wreck(L, x, y, 0.0, name, i)
    for k in ("res0", "res1", "geo", "fire", "view"):                            # military truck hulks (box shapes)
        L[k].box(-4.5, -0.5, 2.6, 5.0, 0.4, 3.2, **kw_for(k, "rust", BURNT, "metal"))
        L[k].box(0.5, 4.5, -5.0, -2.6, 0.4, 3.0, **kw_for(k, "rust", RUST_GREEN, "metal"))
    L["res0"].box(-4.5, -0.5, 2.6, 5.0, 3.2, 3.25, mat="fabric", uv=C.UV_FAB["grey"])
    # sniper nests on the end portals (sandbags on the top chord deck), ladders
    for x in (-hl + 3.0, hl - 3.0):
        for k in ("res0", "res1", "geo", "fire", "view"):
            L[k].box(x - 1.5, x + 1.5, -2.0, 2.0, 6.3, 6.45, **kw_for(k, "wood", C.UV_OAK, "wood"))
        L["road"].hquad(x - 1.5, x + 1.5, -2.0, 2.0, 6.45, mat="road_ext", uv=UV_TILE)
        for (a0, a1, b0, b1) in ((x - 1.5, x + 1.5, -2.0, -1.6), (x - 1.5, x + 1.5, 1.6, 2.0)):
            for k in ("res0", "res1", "geo", "fire", "view"):
                L[k].box(a0, a1, b0, b1, 6.45, 7.3, **kw_for(k, "fabric", C.UV_FAB["beige"], "wood"))
        for lx in (-0.25, 0.25):
            bar(L["res0"], (x + lx, -hw + 0.6, 0.2), (x + lx, -2.0, 6.3), 0.03, "metal", DT.UV_STEEL)
        L["road"].ramp(x - 0.3, x + 0.3, -hw + 0.6, -2.0, 0.2, 6.3, mat="road_ext", uv=UV_TILE)
        # D96: a steel ship ladder - treads between the rails, collision a thin slab under them (a wedge down to the
        # ground left a 6 m invisible wall under the nest)
        ya, yb, za, zb = -hw + 0.6, -2.0, 0.2, 6.3
        n_t = int((zb - za) / 0.25)
        for i in range(1, n_t):
            f = i / n_t
            ty, tz = ya + (yb - ya) * f, za + (zb - za) * f
            L["res0"].box(x - 0.27, x + 0.27, ty - 0.07, ty + 0.07, tz - 0.03, tz, mat="metal", uv=DT.UV_STEEL)
        slab = [(xx, yy, zz) for xx in (x - 0.3, x + 0.3) for (yy, zz) in ((ya, za), (yb, zb), (yb, zb - 0.2), (ya, za - 0.2))]
        L["geo"].solid(slab, [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)])
        yb0 = ya + (yb - ya) * 0.5 / (zb - za)                                    # sec L1: closed foot (no acute slot
        L["geo"].box(x - 0.3, x + 0.3, ya, yb0, 0.0, za + 0.5)                    # between the slab and the deck)
        L["res0"].box(x - 0.3, x + 0.3, ya, yb0, 0.0, za + 0.5, mat="metal", uv=DT.UV_STEEL)
    L["res3"].box(-hl, hl, -hw, hw, -1.2, 0.2, mat="concrete", uv=UV_CONC)
    for sy in (-hw + 0.15, hw - 0.15):
        L["res3"].box(-hl, hl, sy - 0.2, sy + 0.2, 0.2, 6.2, mat="rust", uv=green, skip=("-z",))   # silhouette LOD
    L["mem"].lod.point("center", (0.0, 0.0, 0.0))
    return finish(L, 3000000.0)


# loot points: skyspec.LOOT["Land_SKY_Bridge_Long"]


BUILDERS = {
    "Fair_FerrisWheel": build_ferris_wheel, "Fair_Carousel": build_carousel, "Fair_BumperCars": build_bumper_cars,
    "Fair_Booth": build_booth, "Fair_Gate": build_gate, "Landfill": build_landfill,
    "Stadium_Pitch": build_pitch, "Stadium_Stand": build_stand, "Stadium_Floodlight": build_floodlight,
    "ParkingLot_A": lambda: lot("ParkingLot_A", 12.0, 12.0, [(-11.0, 1), (11.0, -1)]),
    "ParkingLot_B": lambda: lot("ParkingLot_B", 12.0, 6.0, [(0.5, 1)]),
    "ParkingLot_Metro": lambda: lot("ParkingLot_Metro", 12.0, 12.0, [(-11.0, 1)], metro=True),
    "TrashBin": build_trash_bin, "Hydrant_Wet": lambda: build_hydrant(True), "Hydrant_Dry": lambda: build_hydrant(False),
    "SirenTower": build_siren,
    "Viaduct_Straight": build_viaduct_straight, "Viaduct_Ramp": build_viaduct_ramp,
    "Tunnel_Straight": lambda: build_tunnel(False), "Tunnel_Portal": lambda: build_tunnel(True),
    "Bridge_Long": build_bridge,
}


def modules():
    return {n: (BUILDERS[n], e["pbo"], e["p3d"]) for n, e in S.KIT.items() if n in BUILDERS}


if __name__ == "__main__":
    run_cli(modules(), KIT_MATS, "build_stats_landmarks.json")
