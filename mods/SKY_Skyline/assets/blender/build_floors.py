"""Generator for SKY floor / roof variants (batch 4) - run headless in Blender 4.2.

    blender -b --factory-startup -P build_floors.py -- --out <mods/SKY_Skyline/addons> [--only Floor_Hotel]

Built on Tower A's helpers (build_towera.floor_slab / facade / lights /
building_props) and the SAME core footprint and stacking: origin = slab top,
FLOOR_H storeys, core hole for the unchanged Land_SKY_TowerA_Core. Every layout
keeps the core's stair door (south face) and elevator door (north face) clear
(checked by test_kit.py).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import build_towera as T  # noqa: E402
import skyspec as S  # noqa: E402
from build_kit import KIT_MATS  # noqa: E402
from skygeo import UVBand, UVRect, wall_x, wall_y, run_cli  # noqa: E402

HW, HD, CT = T.HW, T.HD, T.CT
WT = S.FLOOR_H - S.SLAB_T
HT = S.WALL_T / 2
UV_BRICKWALL = T.UV_WALL
UV_LOUVRE = UVBand(S.MATERIALS["metal"]["bands"]["steel"], 1.0)
# Roof-drop points for the garden / mechanical roofs: the helipad's (+-8, +-8) fall inside
# planters / plant units here, so use the open strips east and west of the core.
ROOF_DROPS_CLEAR = [(-8.0, -2.0, 0.05), (8.0, -2.0, 0.05), (-8.0, 2.0, 0.05), (8.0, 2.0, 0.05)]


def partitions(L, walls, mat="wall", uv=None, pen="masonry"):
    """walls: [("x"|"y", fixed, a0, a1, openings[(o0, o1)])] full-height, door openings 2.1 m."""
    for k in ("res0", "res1", "geo", "view", "fire"):
        kw = {"mat": mat, "uv": uv or T.UV_WALL} if k.startswith("res") else ({"mat": "pen_" + pen} if k == "fire" else {})
        for axis, c, a0, a1, ops in walls:
            o = [(o0, o1, 0.0, 2.1) for (o0, o1) in ops]
            if axis == "x":
                wall_x(L[k], a0, a1, c - HT, c + HT, 0.0, WT, openings=o, **kw)
            else:
                wall_y(L[k], c - HT, c + HT, a0, a1, 0.0, WT, openings=o, **kw)


def build_floor_apartments():
    """4 apartments (one per quadrant) around a central hall that wraps the core."""
    L = T.std_lods()
    T.floor_slab(L, "tile", T.UV_TILE, "road_int")
    T.facade(L, 0.0, WT)
    e = HW - CT
    partitions(L, [
        # hall boundary: ring 2.5 m outside the core (core x +-3, y +-4.5)
        ("x", -7.0, -e, e, [(-1.5, -0.3), (-8.0, -7.0), (7.0, 8.0)]),       # south hall wall; door to core stair side
        ("x", 7.0, -e, e, [(-8.0, -7.0), (7.0, 8.0)]),                       # north hall wall
        ("y", -5.5, -7.0 + HT, 7.0 - HT, [(-1.0, 0.0)]),                       # west hall wall
        ("y", 5.5, -7.0 + HT, 7.0 - HT, [(0.0, 1.0)]),                         # east hall wall
        # party walls between apartments
        ("y", 0.0, -e, -7.0 - HT, []), ("y", 0.0, 7.0 + HT, e, []),
        ("x", 0.0, -e, -5.5 - HT, []), ("x", 0.0, 5.5 + HT, e, []),
    ])
    T.lights(L, WT - 0.1)
    L["mem"].point("floor_center", (0.0, -6.0, 0.05))
    T.building_props(L, 40000.0)
    L["res3"].box(-HW, HW, -HD, HD, -S.SLAB_T, 0.0, mat="concrete", uv=T.UV_CONC_REVEAL, skip=("+z", "-z"))
    return list(L.values())


def build_floor_hotel():
    """Corridor ring around the core with guest rooms on the facade side."""
    L = T.std_lods()
    T.floor_slab(L, "carpet", T.UV_CARPET, "road_int")
    T.facade(L, 0.0, WT)
    e = HW - CT
    doors_s = [(-9.5, -8.5), (-4.5, -3.5), (3.5, 4.5), (8.5, 9.5)]
    doors_n = [(-9.5, -8.5), (-4.5, -3.5), (3.5, 4.5), (8.5, 9.5)]
    walls = [
        ("x", -6.5, -e, e, doors_s), ("x", 6.5, -e, e, doors_n),               # room fronts, corridor 2 m from core
        ("y", -5.0, -6.5 + HT, 6.5 - HT, [(-1.0, 1.0)]), ("y", 5.0, -6.5 + HT, 6.5 - HT, [(-1.0, 1.0)]),
    ]
    for x in (-6.0, 0.0, 6.0):                                                  # room separations
        walls.append(("y", x, -e, -6.5 - HT, []))
        walls.append(("y", x, 6.5 + HT, e, []))
    partitions(L, walls)
    T.lights(L, WT - 0.1)
    L["mem"].point("floor_center", (0.0, -5.75, 0.05))
    T.building_props(L, 40000.0)
    L["res3"].box(-HW, HW, -HD, HD, -S.SLAB_T, 0.0, mat="concrete", uv=T.UV_CONC_REVEAL, skip=("+z", "-z"))
    return list(L.values())


def louvre_facade(L, z0, z1):
    """Mechanical floor: opaque metal louvre band instead of glass (no alpha)."""
    sides = [((-HW, HW), "y", -HD, (0, -1, 0)), ((-HW, HW), "y", HD, (0, 1, 0)),
             ((-HD, HD), "x", -HW, (-1, 0, 0)), ((-HD, HD), "x", HW, (1, 0, 0))]
    for (a0, a1), axis, c, out in sides:
        sgn = 1 if c > 0 else -1
        d0, d1 = sorted((c, c - sgn * CT))
        box = (a0, a1, d0, d1, z0, z1) if axis == "y" else (d0, d1, a0, a1, z0, z1)
        for k in ("res0", "res1", "res2"):
            L[k].box(*box, mat="metal", uv=UV_LOUVRE, skip=("+z", "-z"))
        for k in ("geo", "view"):
            L[k].box(*box)
        L["fire"].box(*box, mat="pen_metal")


def build_floor_mechanical():
    L = T.std_lods()
    T.floor_slab(L, "concrete", T.UV_CONC_PANEL, "road_int")
    louvre_facade(L, 0.0, WT)
    units = [(-10.5, -6.0, -10.5, -7.5), (6.0, 10.5, -10.5, -7.5), (-10.5, -6.0, 7.5, 10.5), (6.0, 10.5, 7.5, 10.5)]
    for (x0, x1, y0, y1) in units:                                              # plant units
        for k in ("res0", "res1", "geo", "view", "fire"):
            kw = {"mat": "metal", "uv": T.UV_STEEL} if k.startswith("res") else ({"mat": "pen_metal"} if k == "fire" else {})
            L[k].box(x0, x1, y0, y1, 0.0, 2.2, **kw)
    for k in ("res0",):                                                         # duct runs
        L[k].box(-10.5, 10.5, -11.0, -10.6, 2.6, 3.0, mat="metal", uv=T.UV_ALU)
        L[k].box(-10.5, 10.5, 10.6, 11.0, 2.6, 3.0, mat="metal", uv=T.UV_ALU)
    T.lights(L, WT - 0.1)
    L["mem"].point("floor_center", (0.0, -6.0, 0.05))
    T.building_props(L, 45000.0)
    # Res3: one band for slab + louvre storey (budget 24 tris, like Tower A's floor)
    L["res3"].box(-HW, HW, -HD, HD, -S.SLAB_T, WT, mat="metal", uv=UV_LOUVRE, skip=("+z", "-z"))
    return list(L.values())


def roof_base(L, top_mat, top_uv, road):
    T.floor_slab(L, top_mat, top_uv, road)
    for k in ("res0", "res1", "res2", "geo", "view", "fire", "res3", "shadow"):
        kw = {"mat": "concrete", "uv": T.UV_CONC_REVEAL} if k.startswith("res") else ({"mat": "pen_concrete"} if k == "fire" else {})
        for (x0, x1, y0, y1) in [(-HW, HW, -HD, -HD + 0.25), (-HW, HW, HD - 0.25, HD),
                                 (-HW, -HW + 0.25, -HD + 0.25, HD - 0.25), (HW - 0.25, HW, -HD + 0.25, HD - 0.25)]:
            L[k].box(x0, x1, y0, y1, 0.0, 1.1, **kw)


def build_roof_garden():
    L = T.std_lods()
    roof_base(L, "paver", T.UVWorld(3.0), "road_ext")
    beds = [(-11.0, -6.0, -11.0, -6.5), (6.0, 11.0, -11.0, -6.5), (-11.0, -6.0, 6.5, 11.0), (6.0, 11.0, 6.5, 11.0)]
    for (x0, x1, y0, y1) in beds:
        for k in ("res0", "res1", "geo", "fire"):                                # planters (not in Res2: budget)
            kw = {"mat": "concrete", "uv": T.UV_CONC_REVEAL} if k.startswith("res") else ({"mat": "pen_concrete"} if k == "fire" else {})
            L[k].box(x0, x1, y0, y1, 0.0, 0.5, skip=("-z",) if k.startswith("res") else (), **kw)
        cx = (x0 + x1) / 2
        for k in ("res0",):                                                     # shrub cards (Res0 only: budget)
            L[k].quad([(x0 + 0.3, (y0 + y1) / 2, 0.5), (x1 - 0.3, (y0 + y1) / 2, 0.5), (x1 - 0.3, (y0 + y1) / 2, 2.0),
                       (x0 + 0.3, (y0 + y1) / 2, 2.0)], (0, -1, 0), "foliage",
                      UVRect(0, 2, (x0 + 0.3, 0.5), (x1 - 0.3, 2.0)), double=True)
            L[k].quad([(cx, y0 + 0.3, 0.5), (cx, y1 - 0.3, 0.5), (cx, y1 - 0.3, 2.0), (cx, y0 + 0.3, 2.0)], (1, 0, 0),
                      "foliage", UVRect(1, 2, (y0 + 0.3, 0.5), (y1 - 0.3, 2.0)), double=True)
    for i in range(len(S.ROOF_DROPS)):
        L["mem"].point("roof_drop_%d" % (i + 1), ROOF_DROPS_CLEAR[i])
    T.building_props(L, 32000.0)
    return list(L.values())


def build_roof_mechanical():
    L = T.std_lods()
    roof_base(L, "concrete", T.UV_CONC_PANEL, "road_ext")
    units = [(-10.0, -6.0, -10.0, -6.5, 1.8), (6.0, 10.0, -10.0, -6.5, 1.8), (-9.0, -5.0, 6.5, 10.0, 2.4), (5.0, 9.0, 6.5, 10.0, 1.5)]
    for (x0, x1, y0, y1, h) in units:
        for k in ("res0", "res1", "geo", "view", "fire"):                      # HVAC units (not in Res2: budget)
            kw = {"mat": "metal", "uv": T.UV_STEEL} if k.startswith("res") else ({"mat": "pen_metal"} if k == "fire" else {})
            L[k].box(x0, x1, y0, y1, 0.0, h, skip=("-z",) if k.startswith("res") else (), **kw)
        for k in ("res0",):                                                      # fan housings
            L[k].prism((x0 + x1) / 2, (y0 + y1) / 2, 0.6, h, h + 0.3, n=10, mat="metal", uv=T.UV_ALU)
    for i in range(len(S.ROOF_DROPS)):
        L["mem"].point("roof_drop_%d" % (i + 1), ROOF_DROPS_CLEAR[i])
    T.building_props(L, 34000.0)
    return list(L.values())


BUILDERS = {
    "Floor_Apartments": build_floor_apartments, "Floor_Hotel": build_floor_hotel,
    "Floor_Mechanical": build_floor_mechanical, "Roof_Garden": build_roof_garden,
    "Roof_Mechanical": build_roof_mechanical,
}


def modules():
    return {n: (BUILDERS[n], e["pbo"], e["p3d"]) for n, e in S.KIT.items() if n in BUILDERS}


if __name__ == "__main__":
    run_cli(modules(), KIT_MATS, "build_stats_kit.json")
