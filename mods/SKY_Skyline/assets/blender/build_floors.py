"""Generator for SKY floor / roof variants (batch 4) - run headless in Blender 4.2.

    blender -b --factory-startup -P build_floors.py -- --out <mods/SKY_Skyline/addons> [--only Floor_Hotel]

Built on Tower A's helpers (build_towera.floor_slab / facade / lights /
building_props) and the SAME core footprint and stacking: origin = slab top,
FLOOR_H storeys, core hole for the unchanged Land_SKY_TowerA_Core. Every layout
keeps the core's stair door (south face) and elevator door (north face) clear
(checked by test_kit.py).
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import build_towera as T  # noqa: E402
import detail as DT  # noqa: E402
import skyspec as S  # noqa: E402
from build_kit import KIT_MATS  # noqa: E402
from skygeo import UVBand, UVRect, wall_x, wall_y, run_cli  # noqa: E402

HW, HD, CT = T.HW, T.HD, T.CT
WT = S.FLOOR_H - S.SLAB_T
HT = S.WALL_T / 2
UV_BRICKWALL = T.UV_WALL
UV_LOUVRE = UVBand(S.MATERIALS["metal"]["bands"]["steel"], 1.0)


def interior(L, walls, ceiling_mat="wall"):
    """Finish layer (D53): plaster ceiling, oak architraves on every door, walnut skirting."""
    DT.ceiling(L, WT - S.DETAIL["ceiling_drop"], mat=ceiling_mat, uv=T.UV_WALL if ceiling_mat == "wall" else None)
    DT.door_trims(L, walls, HT)
    DT.skirting(L, walls, HT)


def skin_of(name):
    return S.FACADE[S.KIT[name]["cls"]].split("_", 1)[1]          # ribbon_brick -> brick


def partitions(L, walls, mat="wall", uv=None, pen="masonry"):
    """walls: [("x"|"y", fixed, a0, a1, openings[(o0, o1)])] full-height, door openings 2.1 m."""
    for k in ("res0", "res1", "geo", "view", "fire"):
        kw = {"mat": mat, "uv": uv or T.UV_WALL} if k.startswith("res") else ({"mat": "pen_" + pen} if k == "fire" else {})
        for axis, c, a0, a1, ops in walls:
            o = [(o0, o1, 0.0, 2.1) for (o0, o1) in ops]   # lintels in every LOD (security re-gate N2)
            if axis == "x":
                wall_x(L[k], a0, a1, c - HT, c + HT, 0.0, WT, openings=o, **kw)
            else:
                wall_y(L[k], c - HT, c + HT, a0, a1, 0.0, WT, openings=o, **kw)


def build_floor_apartments():
    """4 apartments (one per quadrant) around a central hall that wraps the core."""
    L = T.std_lods()
    T.floor_slab(L, "tile", T.UV_TILE, "road_int")
    DT.ribbon_facade(L, 0.0, WT, skin_of("Floor_Apartments"))
    e = HW - CT
    walls = [
        # hall boundary: ring 2.5 m outside the core (core x +-3, y +-4.5)
        # every apartment gets 2 doors from the hall (security batch-4 H1: SE/NW were sealed);
        # (-8, -7) / (7, 8) are internal doors between the two wings of one apartment
        ("x", -7.0, -e, e, [(-1.5, -0.3), (0.3, 1.5), (-8.0, -7.0), (7.0, 8.0)]),   # south hall wall: SW, SE
        ("x", 7.0, -e, e, [(-1.5, -0.3), (0.3, 1.5), (-8.0, -7.0), (7.0, 8.0)]),    # north hall wall: NW, NE
        ("y", -5.5, -7.0 + HT, 7.0 - HT, [(-1.2, -0.2), (0.2, 1.2)]),               # west hall wall: SW, NW
        ("y", 5.5, -7.0 + HT, 7.0 - HT, [(-1.2, -0.2), (0.2, 1.2)]),                # east hall wall: SE, NE
        # party walls between apartments
        ("y", 0.0, -e, -7.0 - HT, []), ("y", 0.0, 7.0 + HT, e, []),
        ("x", 0.0, -e, -5.5 - HT, []), ("x", 0.0, 5.5 + HT, e, []),
    ]
    partitions(L, walls)
    interior(L, walls)
    T.lights(L, WT - 0.1)
    L["mem"].point("floor_center", (0.0, -6.0, 0.05))
    T.building_props(L, 40000.0)
    DT.ribbon_far(L, 0.0, WT, skin_of("Floor_Apartments"))
    return list(L.values())


def build_floor_hotel():
    """Corridor around the core (x +-5, y +-6.5) with 4 guest rooms off it on the north and south
    sides, 2 suites east / west, and 4 corner rooms reached through the suites (connecting rooms)."""
    L = T.std_lods()
    T.floor_slab(L, "carpet", T.UV_CARPET, "road_int")
    DT.ribbon_facade(L, 0.0, WT, skin_of("Floor_Hotel"))
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
    interior(L, walls)
    T.lights(L, WT - 0.1)
    L["mem"].point("floor_center", (0.0, -5.75, 0.05))
    T.building_props(L, 40000.0)
    DT.ribbon_far(L, 0.0, WT, skin_of("Floor_Hotel"))
    return list(L.values())


def louvre_facade(L, z0, z1):
    """Mechanical floor: opaque metal louvre band instead of glass (no alpha)."""
    # E/W bands stop inside the N/S bands: no coplanar overlap at the corners (QA batch-4 L5)
    sides = [((-HW, HW), "y", -HD, (0, -1, 0)), ((-HW, HW), "y", HD, (0, 1, 0)),
             ((-HD + CT, HD - CT), "x", -HW, (-1, 0, 0)), ((-HD + CT, HD - CT), "x", HW, (1, 0, 0))]
    for (a0, a1), axis, c, out in sides:
        sgn = 1 if c > 0 else -1
        d0, d1 = sorted((c, c - sgn * CT))
        box = (a0, a1, d0, d1, z0, z1) if axis == "y" else (d0, d1, a0, a1, z0, z1)
        for k in ("res1", "res2"):
            L[k].box(*box, mat="metal", uv=UV_LOUVRE, skip=("+z", "-z"))
        for k in ("geo", "view"):
            L[k].box(*box)
        L["fire"].box(*box, mat="pen_metal")
        # Res0 (D53): dark backing set 0.1 m in, horizontal blades, concrete sill / head bands,
        # steel frame posts every 3 m
        sd = DT.Side({(0, -1, 0): "S", (0, 1, 0): "N", (-1, 0, 0): "W", (1, 0, 0): "E"}[out], trim=(axis == "y"))
        r0 = L["res0"]
        sd.box(r0, a0, a1, z0, z1, 0.1, CT, mat="metal", uv=T.UV_PAINT, skip=("+z", "-z"))
        sd.box(r0, a0, a1, z0, z0 + 0.3, 0.0, 0.1, mat="concrete", uv=T.UV_CONC_REVEAL, skip=("-z", sd.in_key))
        sd.box(r0, a0, a1, z1 - 0.3, z1, 0.0, 0.1, mat="concrete", uv=T.UV_CONC_REVEAL, skip=("+z", sd.in_key))
        zb = z0 + 0.3 + S.DETAIL["louvre_step"] / 2
        while zb < z1 - 0.3:
            sd.box(r0, a0, a1, zb - 0.02, zb + 0.02, 0.0, 0.1, mat="metal", uv=UV_LOUVRE, skip=(sd.in_key,) + sd.end_keys)
            zb += S.DETAIL["louvre_step"]
        n = int(round((a1 - a0) / 3.0))
        for i in range(1, n):
            a = a0 + i * (a1 - a0) / n
            sd.box(r0, a - 0.05, a + 0.05, z0 + 0.3, z1 - 0.3, -0.02, 0.1, mat="metal", uv=T.UV_STEEL, skip=("-z", "+z", sd.in_key))


def build_floor_mechanical():
    L = T.std_lods()
    T.floor_slab(L, "concrete", T.UV_CONC_PANEL, "road_int")
    louvre_facade(L, 0.0, WT)
    units = [(-10.5, -6.0, -10.5, -7.5), (6.0, 10.5, -10.5, -7.5), (-10.5, -6.0, 7.5, 10.5), (6.0, 10.5, 7.5, 10.5)]
    for (x0, x1, y0, y1) in units:                                              # plant units
        for k in ("res0", "res1", "geo", "view", "fire"):
            kw = {"mat": "metal", "uv": T.UV_STEEL} if k.startswith("res") else ({"mat": "pen_metal"} if k == "fire" else {})
            L[k].box(x0, x1, y0, y1, 0.0, WT, **kw)      # full height: not climbable (security batch-4 M2)
        # control panel on the face toward the room centre + concrete plinth (Res0, D53)
        DT.atlas_panel(L["res0"], x0, x1, y0, y1, 2.0, "+y" if y0 < 0 else "-y", size=(0.9, 0.9))
        L["res0"].box(x0 - 0.05, x1 + 0.05, y0 - 0.05, y1 + 0.05, 0.0, 0.1, mat="concrete", uv=T.UV_CONC_REVEAL,
                      skip=("-z",))
    for k in ("res0",):                                                         # duct runs
        L[k].box(-10.5, 10.5, -11.0, -10.6, 2.6, 3.0, mat="metal", uv=T.UV_ALU)
        L[k].box(-10.5, 10.5, 10.6, 11.0, 2.6, 3.0, mat="metal", uv=T.UV_ALU)
    # pipe runs under the soffit along the core (above head height: visual only, D53)
    oct_ = [(0.1 * math.cos(i * math.pi / 4), 0.1 * math.sin(i * math.pi / 4)) for i in range(8)]
    for y in (-5.6, -5.3, 5.3, 5.6):
        for xa, xb in ((-10.5, -3.3), (3.3, 10.5)):
            L["res0"].extrude_x([(y + a, 2.85 + b) for a, b in oct_], xa, xb, mat="metal", uv=T.UV_PAINT)
    T.lights(L, WT - 0.1)
    L["mem"].point("floor_center", (0.0, -6.0, 0.05))
    T.building_props(L, 45000.0)
    # Res3: one band for slab + louvre storey (budget 24 tris, like Tower A's floor)
    L["res3"].box(-HW, HW, -HD, HD, -S.SLAB_T, WT, mat="metal", uv=UV_LOUVRE, skip=("+z", "-z"))
    return list(L.values())


def roof_base(L, top_mat, top_uv, road):
    T.floor_slab(L, top_mat, top_uv, road)
    for k in ("res0", "res1", "res2", "geo", "view", "fire", "shadow"):
        kw = {"mat": "concrete", "uv": T.UV_CONC_REVEAL} if k.startswith("res") else ({"mat": "pen_concrete"} if k == "fire" else {})
        if k.startswith("res"):
            kw["skip"] = ("-z",)                                                # sits on the slab (perf L3)
        for (x0, x1, y0, y1) in [(-HW, HW, -HD, -HD + 0.25), (-HW, HW, HD - 0.25, HD),
                                 (-HW, -HW + 0.25, -HD + 0.25, HD - 0.25), (HW - 0.25, HW, -HD + 0.25, HD - 0.25)]:
            L[k].box(x0, x1, y0, y1, 0.0, 1.1, **kw)
    DT.coping(L, 1.1, 0.25)                                                     # D53
    # Res3: outer parapet band + a lid at the WALKABLE level z = 0 (not on the parapet top: a
    # lid at 1.1 m would hide prone players at range, security batch-4 re-gate N1). Closes the
    # hollow look from above (perf batch-4 M2); 10 tris, 1 section.
    L["res3"].box(-HW, HW, -HD, HD, -S.SLAB_T, 1.1, mat="concrete", uv=T.UV_CONC_REVEAL, skip=("+z", "-z"))
    L["res3"].hquad(-HW, HW, -HD, HD, 0.0, mat="concrete", uv=T.UV_CONC_REVEAL)


def garden_pergola(L, x0, x1, y0, y1, h=2.5):
    """Four timber posts (collide), two beams and joists every 0.6 m (visual), oak deck."""
    for x in (x0, x1):
        for y in (y0, y1):
            L["res0"].prism(x, y, 0.08, 0.0, h, n=8, mat="wood", uv=DT.UV_OAK)
            L["res1"].prism(x, y, 0.08, 0.0, h, n=4, mat="wood", uv=DT.UV_OAK)
            L["geo"].prism(x, y, 0.08, 0.0, h, n=4)
            L["fire"].prism(x, y, 0.08, 0.0, h, n=4, mat="pen_wood")
    for y in (y0, y1):
        for k in ("res0", "res1"):
            L[k].box(x0 - 0.3, x1 + 0.3, y - 0.06, y + 0.06, h, h + 0.2, mat="wood", uv=DT.UV_OAK)
    x = x0 - 0.2
    while x <= x1 + 0.2 + 1e-6:
        L["res0"].box(x - 0.03, x + 0.03, y0 - 0.3, y1 + 0.3, h + 0.2, h + 0.32, mat="wood", uv=DT.UV_OAK)
        x += 0.6
    for k in ("res0", "res1"):
        L[k].hquad(x0 - 0.3, x1 + 0.3, y0 - 0.3, y1 + 0.3, 0.005, mat="wood", uv=DT.UV_OAK)


def build_roof_garden():
    L = T.std_lods()
    roof_base(L, "paver", T.UVWorld(3.0), "road_ext")
    # planters >= 1.2 m inside the parapet (security batch-4 L3)
    beds = [(-10.5, -6.0, -10.5, -6.5), (6.0, 10.5, -10.5, -6.5), (-10.5, -6.0, 6.5, 10.5), (6.0, 10.5, 6.5, 10.5)]
    for (x0, x1, y0, y1) in beds:
        for k in ("res0", "res1", "geo", "view", "fire"):                        # planters (not in Res2: budget)
            kw = {"mat": "concrete", "uv": T.UV_CONC_REVEAL} if k.startswith("res") else ({"mat": "pen_concrete"} if k == "fire" else {})
            L[k].box(x0, x1, y0, y1, 0.0, 0.5, skip=("-z",) if k.startswith("res") else (), **kw)
        cx = (x0 + x1) / 2
        for k in ("res0",):                                                     # shrub cards (Res0 only: budget)
            L[k].quad([(x0 + 0.3, (y0 + y1) / 2, 0.5), (x1 - 0.3, (y0 + y1) / 2, 0.5), (x1 - 0.3, (y0 + y1) / 2, 2.0),
                       (x0 + 0.3, (y0 + y1) / 2, 2.0)], (0, -1, 0), "foliage",
                      UVRect(0, 2, (x0 + 0.3, 0.5), (x1 - 0.3, 2.0)), double=True)
            L[k].quad([(cx, y0 + 0.3, 0.5), (cx, y1 - 0.3, 0.5), (cx, y1 - 0.3, 2.0), (cx, y0 + 0.3, 2.0)], (1, 0, 0),
                      "foliage", UVRect(1, 2, (y0 + 0.3, 0.5), (y1 - 0.3, 2.0)), double=True)
    # benches (north) and a timber pergola over a deck (south), clear of loot points, roof drops
    # and the core's stair door zone (D53)
    for x0, x1 in ((-4.9, -3.1), (3.1, 4.9)):
        DT.bench(L, x0, x1, 9.3, 9.8)
    garden_pergola(L, -2.8, 2.8, -11.0, -8.6)
    for i, (x, y) in enumerate(S.ROOF_DROPS_CLEAR):                         # D33, shared with sky_layout
        L["mem"].point("roof_drop_%d" % (i + 1), (x, y, 0.05))
    T.building_props(L, 32000.0)
    return list(L.values())


def build_roof_mechanical():
    L = T.std_lods()
    roof_base(L, "concrete", T.UV_CONC_PANEL, "road_ext")
    units = [(-10.0, -6.0, -10.0, -6.5, 1.8), (6.0, 10.0, -10.0, -6.5, 1.8), (-9.0, -5.0, 6.5, 10.0, 2.4), (5.0, 9.0, 6.5, 10.0, 1.5)]
    for (x0, x1, y0, y1, h) in units:                                       # HVAC units (not in Res2: budget)
        DT.unit(L, x0, x1, y0, y1, h, grille="+y" if y0 < 0 else "-y")
    # water tank on the west strip (clear of the roof drops at (-8, +-2)) + antenna mast (D53)
    for k, n in (("res0", 16), ("res1", 8), ("geo", 8), ("view", 8), ("fire", 8)):
        kw = {"mat": "metal", "uv": T.UV_PAINT} if k.startswith("res") else ({"mat": "pen_metal"} if k == "fire" else {})
        L[k].prism(-10.4, 0.0, 0.7, 0.0, 2.6, n=n, **kw)
    L["res0"].prism(-10.4, 0.0, 0.5, 2.6, 2.75, n=12, mat="metal", uv=T.UV_STEEL)
    DT.mast(L, 10.8, 0.0, 5.0)
    for i, (x, y) in enumerate(S.ROOF_DROPS_CLEAR):                         # D33, shared with sky_layout
        L["mem"].point("roof_drop_%d" % (i + 1), (x, y, 0.05))
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
