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


CEIL = WT - S.DETAIL["ceiling_drop"]


def interior(L, walls, ceiling_mat="paint"):
    """Finish layer (D53/D55): painted plaster ceiling, oak architraves on every door, walnut skirting."""
    DT.ceiling(L, CEIL, mat=ceiling_mat, uv=DT.paint_uv("white") if ceiling_mat == "paint" else None)
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


def apartments_decor(L, e):
    """Apartment decoration (D55): oak parquet in the flats (tiles stay in the hall), pendants
    at the script-light points, hall downlights, a rug and two artworks per flat."""
    DT.floor_finish(L, [(-e, e, -e, -7.0 - HT), (-e, e, 7.0 + HT, e), (-e, -5.5 - HT, -7.0 + HT, 7.0 - HT),
                        (5.5 + HT, e, -7.0 + HT, 7.0 - HT)], "parquet", DT.UV_PARQUET)
    for sx in (-1, 1):
        for sy in (-1, 1):
            DT.pendant(L, 7.5 * sx, 7.5 * sy, CEIL, 0.75, r=0.3)
            DT.rug(L, *sorted((7.0 * sx, 10.6 * sx)), *sorted((1.0 * sy, 4.8 * sy)), band="rug_a" if sx * sy > 0 else "rug_b")
            DT.wall_art(L, HT * sx, 10.0 * sy, 1.6, 0.9, 0.9, ("+x" if sx > 0 else "-x"), "art_a" if sy > 0 else "art_b")
            DT.wall_art(L, 9.5 * sx, HT * sy, 1.6, 0.9, 0.9, ("+y" if sy > 0 else "-y"), "art_c" if sx > 0 else "art_d")
    for (x, y) in ((0.0, -5.75), (0.0, 5.75), (-4.25, 0.0), (4.25, 0.0), (-4.25, -5.75), (4.25, 5.75)):
        DT.downlight(L, x, y, CEIL)


def build_floor_apartments():
    """4 apartments (one per quadrant) around a central hall that wraps the core."""
    L = T.std_lods()
    T.floor_slab(L, "tile", T.UV_TILE, "road_int")
    DT.ribbon_facade(L, 0.0, WT, skin_of("Floor_Apartments"), window_boxes=True, inner_mat="paint",
                     inner_uv=DT.paint_uv("white"))
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
    partitions(L, walls[:4], mat="paint", uv=DT.paint_uv("beige"))          # hall ring
    partitions(L, walls[4:], mat="paint", uv=DT.paint_uv("sage"))           # party walls
    interior(L, walls)
    apartments_decor(L, e)
    T.lights(L, WT - 0.1)
    L["mem"].point("floor_center", (0.0, -6.0, 0.05))
    T.building_props(L, 40000.0)
    DT.ribbon_far(L, 0.0, WT, skin_of("Floor_Apartments"))
    return list(L.values())


def hotel_decor(L, walls):
    """Hotel decoration (D55): walnut wainscot on every wall, patterned runner round the core,
    corridor sconces, room downlights and pendants, art in every room."""
    DT.wall_band(L, walls, HT, 0.0, 0.95, "wood", DT.UV_WALNUT)
    DT.wall_band(L, walls, HT, 0.95, 1.0, "wood", DT.UV_OAK, proud=0.025)     # dado rail
    for (x0, x1, y0, y1) in ((-4.5, 4.5, -5.9, -4.95), (-4.5, 4.5, 4.95, 5.9)):
        L["res0"].hquad(x0, x1, y0, y1, 0.006, mat="textile", uv=DT.band_fit("textile", "runner", x0, x1, y0, y1, u_rep=4))
    for (x0, x1, y0, y1) in ((-4.4, -3.5, -4.95, 4.95), (3.5, 4.4, -4.95, 4.95)):
        L["res0"].hquad(x0, x1, y0, y1, 0.006, mat="textile",
                        uv=DT.band_fit("textile", "runner", y0, y1, x0, x1, axes=(1, 0), u_rep=4))
    for x in (-2.0, 2.0):
        DT.sconce(L, x, -6.5 + HT, 1.9, "+y")
        DT.sconce(L, x, 6.5 - HT, 1.9, "-y")
    for y in (-3.5, 3.5):
        DT.sconce(L, -5.0 + HT, y, 1.9, "+x")
        DT.sconce(L, 5.0 - HT, y, 1.9, "-x")
    for x in (-9.0, -3.0, 3.0, 9.0):
        for y in (-9.25, 9.25):
            DT.downlight(L, x, y, CEIL)
    for sx in (-1, 1):
        for sy in (-1, 1):
            DT.pendant(L, 7.5 * sx, 7.5 * sy, CEIL, 0.6, r=0.25)
    arts = ["art_a", "art_b", "art_c", "art_d"]
    for i, x in enumerate((-6.0, 0.0, 6.0)):
        DT.wall_art(L, x + HT, -9.0, 1.6, 0.8, 0.8, "+x", arts[i % 4])
        DT.wall_art(L, x - HT, 9.0, 1.6, 0.8, 0.8, "-x", arts[(i + 1) % 4])


def build_floor_hotel():
    """Corridor around the core (x +-5, y +-6.5) with 4 guest rooms off it on the north and south
    sides, 2 suites east / west, and 4 corner rooms reached through the suites (connecting rooms)."""
    L = T.std_lods()
    T.floor_slab(L, "carpet", T.UV_CARPET, "road_int")
    DT.ribbon_facade(L, 0.0, WT, skin_of("Floor_Hotel"), inner_mat="paint", inner_uv=DT.paint_uv("beige"))
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
    partitions(L, walls, mat="paint", uv=DT.paint_uv("beige"))
    interior(L, walls)
    hotel_decor(L, walls)
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


def mechanical_decor(L):
    """Plant floor (D55): batten lights, cable trays, two pumps on plinths (collide)."""
    for x in (-8.0, 8.0):
        for y in (-5.0, 0.0, 5.0):
            L["res0"].box(x - 0.6, x + 0.6, y - 0.06, y + 0.06, WT - 0.3, WT - 0.24, mat="lamp_cool")
    for x in (-7.2, 7.2):
        L["res0"].box(x - 0.15, x + 0.15, -9.0, 9.0, 2.95, 3.0, mat="metal", uv=T.UV_STEEL)
    for x in (-9.6, 9.6):
        for k, n in (("res0", 12), ("res1", 6)):
            L[k].box(x - 0.5, x + 0.5, -0.6, 0.6, 0.0, 0.15, mat="concrete", uv=T.UV_CONC_REVEAL, skip=("-z",))
            L[k].extrude_y([(x + 0.35 * math.cos(a * 2 * math.pi / n), 0.6 + 0.35 * math.sin(a * 2 * math.pi / n))
                            for a in range(n)], -0.5, 0.5, mat="metal", uv=T.UV_PAINT)
        L["geo"].box(x - 0.5, x + 0.5, -0.6, 0.6, 0.0, 0.95)
        L["fire"].box(x - 0.5, x + 0.5, -0.6, 0.6, 0.0, 0.95, mat="pen_metal")


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
    mechanical_decor(L)
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
    DT.roof_weathering(L)                                                       # D60


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


def garden_decor(L, beds):
    """Roof garden (D55): a tree in every planter, loungers on the deck, string lights on the
    pergola beams, bollard lights."""
    from skygeo import UVRect
    for (x0, x1, y0, y1) in beds:
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        for k in ("res0", "res1"):
            L[k].quad([(cx - 1.4, cy, 0.5), (cx + 1.4, cy, 0.5), (cx + 1.4, cy, 3.6), (cx - 1.4, cy, 3.6)], (0, -1, 0),
                      "foliage", UVRect(0, 2, (cx - 1.4, 0.5), (cx + 1.4, 3.6), (0, 0, 1, 1)), double=True)
            L[k].quad([(cx, cy - 1.4, 0.5), (cx, cy + 1.4, 0.5), (cx, cy + 1.4, 3.6), (cx, cy - 1.4, 3.6)], (1, 0, 0),
                      "foliage", UVRect(1, 2, (cy - 1.4, 0.5), (cy + 1.4, 3.6), (1, 0, 2, 1)), double=True)
    for x0, x1 in ((-2.1, -1.35), (1.35, 2.1)):
        L["res0"].box(x0, x1, -10.7, -9.0, 0.25, 0.32, mat="textile", uv=DT.band_fit("textile", "curtain", x0, x1, -10.7, -9.0))
        L["res0"].box(x0, x1, -9.35, -9.0, 0.32, 0.75, mat="wood", uv=DT.UV_OAK)
        L["res0"].box(x0 + 0.05, x1 - 0.05, -10.65, -9.05, 0.0, 0.25, mat="wood", uv=DT.UV_OAK, skip=("-z",))
        L["res1"].box(x0, x1, -10.7, -9.0, 0.0, 0.4, mat="wood", uv=DT.UV_OAK, skip=("-z",))
        L["geo"].box(x0, x1, -10.7, -9.0, 0.0, 0.35)
        L["fire"].box(x0, x1, -10.7, -9.0, 0.0, 0.35, mat="pen_wood")
    for y in (-11.0, -8.6):
        for i in range(9):
            L["res0"].prism(-2.8 + i * 0.7, y, 0.035, 2.38, 2.45, n=6, mat="lamp")
    for (x, y) in ((-3.4, -8.0), (3.4, -8.0), (-3.4, -11.4), (3.4, -11.4)):
        L["res0"].prism(x, y, 0.08, 0.0, 0.7, n=8, mat="metal", uv=T.UV_PAINT)
        L["res0"].prism(x, y, 0.07, 0.7, 0.8, n=8, mat="lamp")


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
    garden_decor(L, beds)
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
    DT.obstruction_light(L, 10.8, 0.0, 5.0)
    for i in range(8):                                                       # access ladder on the tall unit
        L["res0"].box(-7.6, -6.4, 6.42, 6.46, 0.25 + i * 0.3, 0.28 + i * 0.3, mat="metal", uv=T.UV_STEEL)
    for x in (-7.6, -6.4):
        L["res0"].box(x - 0.03, x + 0.03, 6.38, 6.46, 0.0, 2.7, mat="metal", uv=T.UV_STEEL, skip=("-z",))
    for i, (x, y) in enumerate(S.ROOF_DROPS_CLEAR):                         # D33, shared with sky_layout
        L["mem"].point("roof_drop_%d" % (i + 1), (x, y, 0.05))
    T.building_props(L, 34000.0)
    return list(L.values())


def build_roof_crown():
    """HQ landmark crown (D58): the plant roof's parapet and drop strips, plus four corner pylons
    with light strips, steel crown fins standing on the parapet and a tapered spire carried over
    the core (base above the core cap). Pylons collide; fins and spire are out of reach (Res only,
    spire + pylons in Fire)."""
    L = T.std_lods()
    roof_base(L, "concrete", T.UV_CONC_PANEL, "road_ext")
    steel, paint = T.UV_STEEL, T.UV_PAINT
    for sx in (-1, 1):                                                       # corner pylons (1.2 m, 14 m)
        for sy in (-1, 1):
            x0, x1 = sorted((sx * (HW - 0.25), sx * (HW - 1.45)))
            y0, y1 = sorted((sy * (HD - 0.25), sy * (HD - 1.45)))
            for k in ("res0", "res1", "res2", "geo", "view", "fire"):              # no shadow volume (budget)
                kw = {"mat": "metal", "uv": paint} if k.startswith("res") else ({"mat": "pen_metal"} if k == "fire" else {})
                L[k].box(x0, x1, y0, y1, 0.0, 14.0, **kw)
            fx = x0 if sx > 0 else x1                                         # light strip on the inner face
            L["res0"].box(fx - 0.03 * sx, fx, y0 + 0.4, y1 - 0.4, 1.5, 13.5, mat="lamp_cool")
            DT.obstruction_light(L, (x0 + x1) / 2, (y0 + y1) / 2, 14.0)
    for side in range(4):                                                    # crown fins on the parapet
        for i in range(7):
            a = -HW + 2.6 + i * (2 * HW - 5.2) / 6
            h = 4.0 + 5.0 * math.sin(math.pi * (i + 0.5) / 7)
            if side < 2:
                y = (HD - 0.13) * (1 if side else -1)
                b = (a - 0.1, a + 0.1, y - 0.12, y + 0.12)
            else:
                x = (HW - 0.13) * (1 if side == 3 else -1)
                b = (x - 0.12, x + 0.12, a - 0.1, a + 0.1)
            for k in ("res0", "res1"):                                             # fins: close LODs only
                L[k].box(*b, 1.15, 1.15 + h, mat="metal", uv=steel, skip=("-z",))
    zc = S.FLOOR_H + S.SLAB_T                                                # spire base: on the core cap
    for i, (r, z0, z1) in enumerate(((1.6, zc, zc + 3.0), (1.1, zc + 3.0, zc + 9.0), (0.6, zc + 9.0, zc + 17.0),
                                     (0.25, zc + 17.0, zc + 24.0))):
        for k in ("res0", "res1", "res2", "fire"):
            kw = {"mat": "metal", "uv": steel} if k.startswith("res") else ({"mat": "pen_metal"} if k == "fire" else {})
            L[k].prism(0.0, 0.0, r, z0, z1, n=12 if k == "res0" else (6 if k == "res1" else 4), **kw)

    DT.obstruction_light(L, 0.0, 0.0, zc + 24.0)
    for z in (zc + 9.0, zc + 17.0):
        L["res0"].prism(0.0, 0.0, 0.7 if z < zc + 10 else 0.3, z, z + 0.15, n=12, mat="lamp")
    L["res3"].prism(0.0, 0.0, 0.8, zc, zc + 24.0, n=4, mat="metal", uv=steel)
    for i, (x, y) in enumerate(S.ROOF_DROPS_CLEAR):                         # D33, shared with sky_layout
        L["mem"].point("roof_drop_%d" % (i + 1), (x, y, 0.05))
    T.building_props(L, 40000.0)
    return list(L.values())


def build_skybridge():
    """Enclosed glazed skybridge (D60, skyspec.SKYBRIDGE): steel box girders under a 0.15 m deck,
    glass walls between steel posts every 3 m, a metal roof, downlights; open landings with
    balustrades and 5 steps down onto each roof. Collides: deck, girders, glass walls, roof,
    balustrades, steps (Roadway: deck + one ramp per end)."""
    B = S.SKYBRIDGE
    L = T.std_lods()
    W, G, dz, dt, ch = B["half_w"], B["gap"] / 2, B["deck_z"], B["deck_t"], B["clear_h"]
    end = G + B["landing"]                      # steps end on the roof
    run = 0.3 * B["steps"]
    land = end - run                            # deck end (top step edge)
    rise = dz / (B["steps"] + 1)
    steel, conc = T.UV_STEEL, T.UV_CONC_REVEAL

    def solid_box(keys, x0, x1, y0, y1, z0, z1, mat, uv, pen, skip=()):
        for k in keys:
            if k.startswith("res"):
                L[k].box(x0, x1, y0, y1, z0, z1, mat=mat, uv=uv, skip=skip if k in ("res0", "res1") else ())
            elif k == "fire":
                L[k].box(x0, x1, y0, y1, z0, z1, mat="pen_" + pen)
            else:
                L[k].box(x0, x1, y0, y1, z0, z1)

    ALL = ("res0", "res1", "res2", "geo", "view", "fire", "shadow")
    # deck (on the parapets at both ends) + tile walking surface
    solid_box(ALL, -W, W, -land, land, dz - dt, dz, "concrete", conc, "concrete", skip=("+z",))
    for k in ("res0", "res1"):
        L[k].hquad(-W, W, -land, land, dz, mat="tile", uv=T.UV_TILE)
    L["res3"].box(-W, W, -land, land, dz - dt, dz, mat="concrete", uv=conc, skip=("+z",))
    # box girders under the span (bear on the parapets at the facades)
    for x0, x1 in ((-W, -W + 0.25), (W - 0.25, W)):
        solid_box(("res0", "res1", "res2", "geo", "view", "fire", "shadow"), x0, x1, -G - 0.25, G + 0.25, 0.45,
                  dz - dt, "metal", steel, "metal")
    # glass walls over the span, posts every 3 m (Res0 / Res1), top + bottom rails
    for sx in (-1, 1):
        xo, xi = sx * W, sx * (W - 0.05)
        gx = sx * (W - 0.025)
        x0, x1 = sorted((xo, xi))
        q = [(gx, -G, dz), (gx, G, dz), (gx, G, dz + ch), (gx, -G, dz + ch)]
        n_out = (sx, 0, 0)
        L["res0"].quad(q, n_out, "glass", T.UV_GLASS, double=True)
        L["res1"].quad(q, n_out, "glass", T.UV_GLASS, double=True)
        L["res2"].quad(q, n_out, "glassfar", T.UV_GLASS)
        L["res3"].quad(q, n_out, "glassfar", T.UV_GLASS)
        L["geo"].box(x0, x1, -G, G, dz, dz + ch)
        L["fire"].box(x0, x1, -G, G, dz, dz + ch, mat="pen_glass")
        xp0, xp1 = sorted((sx * (W + 0.04), sx * (W - 0.1)))
        for lod_key, step in (("res0", 3.0), ("res1", 6.0)):
            y = -G
            while y <= G + 1e-6:
                L[lod_key].box(xp0, xp1, y - 0.06, y + 0.06, dz, dz + ch, mat="metal", uv=T.UV_PAINT, skip=("-z", "+z"))
                y += step
        for zz in (dz, dz + ch - 0.1):
            L["res0"].box(xp0, xp1, -G, G, zz, zz + 0.1, mat="metal", uv=T.UV_PAINT, skip=("-y", "+y"))
    # roof (slight overhang) + downlights
    solid_box(ALL, -W - 0.1, W + 0.1, -G - 0.1, G + 0.1, dz + ch, dz + ch + 0.15, "metal", T.UV_PAINT, "metal")
    L["res3"].box(-W - 0.1, W + 0.1, -G - 0.1, G + 0.1, dz + ch, dz + ch + 0.15, mat="metal", uv=T.UV_PAINT, skip=("-z",))
    y = -G + 1.5
    while y < G:
        DT.downlight(L, 0.0, y, dz + ch - 0.001)
        y += 3.0
    # landings: balustrades (deck part + sloped stair part, one convex solid each) and steps
    for sy in (-1, 1):
        for sx in (-1, 1):
            x0, x1 = sorted((sx * W, sx * (W - 0.06)))
            a, b = sorted((sy * G, sy * land))
            solid_box(("res0", "res1", "geo", "fire", "view"), x0, x1, a, b, dz, dz + 1.0, "metal", T.UV_PAINT, "metal")
            ya, yb = sy * land, sy * end
            verts = [(x0, ya, dz - dt), (x1, ya, dz - dt), (x1, yb, 0.0), (x0, yb, 0.0),
                     (x0, ya, dz + 1.0), (x1, ya, dz + 1.0), (x1, yb, 1.0), (x0, yb, 1.0)]
            faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
            for k in ("res0", "res1", "geo", "view", "fire"):
                kw = {"mat": "metal", "uv": T.UV_PAINT} if k.startswith("res") else ({"mat": "pen_metal"} if k == "fire" else {})
                L[k].solid(verts, faces, **kw)
        for i in range(B["steps"]):
            a, b = sorted((sy * (land + 0.3 * i), sy * (land + 0.3 * (i + 1))))
            top = dz - (i + 1) * rise
            solid_box(("res0", "res1", "geo", "fire"), -W + 0.06, W - 0.06, a, b, 0.0, top, "concrete", conc,
                      "concrete", skip=("-z",))
        # Roadway ramp over the steps
        L["road"].ramp(-W + 0.06, W - 0.06, sy * end, sy * land, 0.0, dz, mat="road_ext", uv=T.UV_TILE)
    L["road"].hquad(-W + 0.06, W - 0.06, -land, land, dz, mat="road_ext", uv=T.UV_TILE)
    L["mem"].point("bridge_center", (0.0, 0.0, dz + 0.05))
    T.building_props(L, 30000.0)
    return list(L.values())


BUILDERS = {
    "Floor_Apartments": build_floor_apartments, "Floor_Hotel": build_floor_hotel,
    "Floor_Mechanical": build_floor_mechanical, "Roof_Garden": build_roof_garden,
    "Roof_Mechanical": build_roof_mechanical, "Roof_Crown": build_roof_crown,
    # office plan with another facade skin (D60)
    "Floor_Office_Concrete": lambda: T.build_floor_office("panel"),
    "Floor_Office_Brick": lambda: T.build_floor_office("brick"),
    "Floor_HQ": lambda: T.build_floor_office("hq"),
    "Skybridge": build_skybridge,
}


def modules():
    return {n: (BUILDERS[n], e["pbo"], e["p3d"]) for n, e in S.KIT.items() if n in BUILDERS}


if __name__ == "__main__":
    run_cli(modules(), KIT_MATS, "build_stats_kit.json")
