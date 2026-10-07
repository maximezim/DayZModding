"""D63 underground kit: sewers and metro (ROADMAP ideas 18 and 22) - plain Python or any Blender.

    python build_underground.py -- --out <mods/SKY_Skyline/addons> [--only Sewer_Straight,Metro_Station]

Cut-and-cover: every piece is a closed concrete box whose roof slab top sits at z = UNDERGROUND["roof_top"]
(just under street level, z 0 = street). On a custom terrain the heightmap is trenched under the runs
(terrain/gen_terrain.py) and the pieces close the trench; streets and plazas sit on the roof. Players go
down through the stair pieces, which open at street level. Nothing here needs a terrain hole.
On a vanilla map the pieces are never placed (sky_layout refuses `underground` unless site.target is
terrain), so the street hatches of ParkingLot_Metro stay sealed (D58 surface fallback).

Frame: runs along Y (12 m modules), front = -Y, origin = centre at street level.
- Sewer: brick barrel-ish vault (chamfered), 1.0 m channel between two 1.4 m walkways, walkway at
  UNDERGROUND["sewer_floor"]. The channel water is the selection `flood`, animated up to FLOOD_RISE m
  (model.cfg translation on `flood_axis`, user source `flood`, driven by SKY_Underground.c from the rain).
- Metro: 9 m double-track tube, track bed at UNDERGROUND["metro_floor"]; station = 24 m island platform
  with columns, tiled walls, benches, signs and a stair up to a street opening.
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
from skygeo import UVBand, UVRect, UVWorld, run_cli  # noqa: E402

kw_for, h01 = C.kw_for, C.h01
UG = S.UNDERGROUND
UV_CONC, UV_REVEAL, UV_TILE, UV_RUBBLE = C.UV_CONC, C.UV_REVEAL, C.UV_TILE, C.UV_RUBBLE
UV_BRICK = UVWorld(S.MATERIALS["wall_brick"]["sheet_m"])
UV_TILES = UVWorld(1.5)
UV_RUST = UVBand(S.MATERIALS["rust"]["bands"]["rust"], 1.0)
UV_RUST_GREY = UVBand(S.MATERIALS["rust"]["bands"]["grey"], 1.0)
SOLID = ("res0", "res1", "geo", "view", "fire")
LEN = 12.0


def L_new(name):
    return C.city_lods(C.Ruin(name, 0))


def box_all(L, keys, b, mat, uv, pen="concrete", skip=()):
    for k in keys:
        kw = kw_for(k, mat, uv, pen)
        if skip and k.startswith("res"):
            kw["skip"] = skip
        L[k].box(*b, **kw)


def roof_boxes(x0, x1, y0, y1, hole):
    """Roof rectangle minus a rectangular street opening -> up to 4 boxes (x0, x1, y0, y1)."""
    if not hole:
        return [(x0, x1, y0, y1)]
    hx0, hx1, hy0, hy1 = hole
    out = [(x0, hx0, y0, y1), (hx1, x1, y0, y1), (hx0, hx1, y0, hy0), (hx0, hx1, hy1, y1)]
    return [b for b in out if b[1] - b[0] > 0.01 and b[3] - b[2] > 0.01]


def shell(L, x0, x1, y0, y1, zf, zc, wall=0.5, floor_t=0.8, inner="concrete", inner_uv=None, ends=(), hole=None):
    """Closed box round an interior (x0..x1, y0..y1, zf..zc): floor slab, two side walls, roof slab up to
    roof_top (the fill above the vault is solid concrete), optional end walls ('-y', '+y').
    Res faces of the inner side get `inner`; the roof top is plain concrete (the street sits on it)."""
    zt, zb = UG["roof_top"], zf - floor_t
    box_all(L, SOLID, (x0 - wall, x1 + wall, y0, y1, zb, zf), "concrete", UV_CONC)                  # floor slab
    for (a, b, c, d) in roof_boxes(x0 - wall, x1 + wall, y0, y1, hole):                           # roof + fill
        box_all(L, SOLID, (a, b, c, d, zc, zt), "concrete", UV_CONC)
        L["road"].hquad(a, b, c, d, zt, mat="road_ext", uv=UV_TILE)                                  # street on the roof
    for (a, b) in ((x0 - wall, x0), (x1, x1 + wall)):                                              # side walls
        box_all(L, SOLID, (a, b, y0, y1, zf, zc), inner, inner_uv or UV_CONC)
    for e in ends:
        a, b = (y0, y0 + wall) if e == "-y" else (y1 - wall, y1)
        box_all(L, SOLID, (x0, x1, a, b, zf, zc), inner, inner_uv or UV_CONC)
    for k in ("res2",):
        L[k].box(x0 - wall, x1 + wall, y0, y1, zb, zt, mat="concrete", uv=UV_CONC)
    L["res3"].box(x0 - wall, x1 + wall, y0, y1, zb, zt, mat="concrete", uv=UV_CONC)


def flood_plane(L, x0, x1, y0, y1, z):
    """Channel water: selection `flood` on Res0/Res1 (the model.cfg translation raises it)."""
    for k in ("res0", "res1"):
        L[k].lod.quad([(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)], (0, 0, 1), "glassfar", C.UV_GLASS, sel=["flood"])
    L["mem"].lod.point("flood_axis", (0.0, 0.0, z))
    L["mem"].lod.point("flood_axis", (0.0, 0.0, z + 1.0))


def lamp(L, x, y, z, along_y=True):
    w, d = (0.15, 0.5) if along_y else (0.5, 0.15)
    L["res0"].box(x - w, x + w, y - d, y + d, z - 0.08, z, mat="metal", uv=DT.UV_STEEL)
    L["res0"].box(x - w + 0.02, x + w - 0.02, y - d + 0.03, y + d - 0.03, z - 0.09, z - 0.08, mat="lamp_cool")


def pipe_run(L, x, y0, y1, z, r, mat="rust", uv=UV_RUST):
    C.bar(L["res0"].lod, (x, y0, z), (x, y1, z), r, mat, uv)
    for yy in (y0 + 1.5, (y0 + y1) / 2, y1 - 1.5):                                               # wall brackets
        L["res0"].box(x - r - 0.02, x + r + 0.02, yy - 0.04, yy + 0.04, z - r - 0.05, z + r, mat="metal", uv=DT.UV_STEEL)


def sign_quad(L, sign, x, y0, y1, z0, z1, facing_x):
    """Sign board on a wall at x (faces +X or -X): a thin steel frame + the sign sheet band (signs3)."""
    xo = x + 0.025 * facing_x
    L["res0"].box(min(x, xo), max(x, xo), y0 - 0.04, y1 + 0.04, z0 - 0.04, z1 + 0.04, mat="metal", uv=DT.UV_STEEL)
    xf = xo + 0.003 * facing_x
    pts = [(xf, y0, z0), (xf, y1, z0), (xf, y1, z1), (xf, y0, z1)]
    lo, hi = (y0, z0), (y1, z1)
    # looking at a +X-facing wall (from +X) text runs +Y; on a -X-facing wall it runs -Y (mirror U)
    v0, v1 = S.SIGN_BAND[sign]
    uvb = (0, 1 - v1, 1, 1 - v0) if facing_x > 0 else (1, 1 - v1, 0, 1 - v0)
    L["res0"].lod.quad(pts, (facing_x, 0, 0), S.SIGN_MAT[sign], UVRect(1, 2, lo, hi, uvb))


def sign_hung(L, sign, x0, x1, y, z0, z1, top):
    """Double-sided sign hung across a space (faces +-Y), on two rods from the ceiling."""
    for f in (-1, 1):
        yy = y + 0.02 * f
        pts = [(x0, yy, z0), (x1, yy, z0), (x1, yy, z1), (x0, yy, z1)]
        v0, v1 = S.SIGN_BAND[sign]                                                 # -Y face reads +X, +Y face mirrors
        uvb = (0, 1 - v1, 1, 1 - v0) if f < 0 else (1, 1 - v1, 0, 1 - v0)
        L["res0"].lod.quad(pts, (0, f, 0), S.SIGN_MAT[sign], UVRect(0, 2, (x0, z0), (x1, z1), uvb))
    L["res0"].box(x0 - 0.03, x1 + 0.03, y - 0.018, y + 0.018, z0 - 0.03, z1 + 0.03, mat="metal", uv=DT.UV_STEEL)
    for xx in (x0 + 0.2, x1 - 0.2):
        L["res0"].prism(xx, y, 0.008, z1, top, n=4, mat="metal", uv=DT.UV_STEEL)


def graffiti(L, name, x, y0, y1, z0, z1, facing_x, k):
    """Graffiti tag on a wall (decal_graffiti, alpha-blended, design A of the decal sheet) - D66."""
    if h01(name, "gf", k) > 0.55:
        return
    xf = x + 0.006 * facing_x
    uv = UVRect(1, 2, (y0, z0), (y1, z1), (0.0, 0.0, 1.0, 1.0) if facing_x > 0 else (1.0, 0.0, 0.0, 1.0))
    pts = [(xf, y0, z0), (xf, y1, z0), (xf, y1, z1), (xf, y0, z1)]
    L["res0"].quad(pts, (facing_x, 0, 0), "decal_graffiti", uv)


def cable_run(L, x, y0, y1, z, sag=0.12, n_brackets=4):
    """Two cables sagging between wall brackets (Res0)."""
    pts = [y0 + (y1 - y0) * i / n_brackets for i in range(n_brackets + 1)]
    for a, b in zip(pts, pts[1:]):
        m = (a + b) / 2
        for dz, r in ((0.0, 0.02), (-0.06, 0.014)):
            C.bar(L["res0"].lod, (x, a, z + dz), (x, m, z + dz - sag), r, "rubble", UV_RUBBLE)
            C.bar(L["res0"].lod, (x, m, z + dz - sag), (x, b, z + dz), r, "rubble", UV_RUBBLE)
        L["res0"].box(x - 0.04, x + 0.04, a - 0.03, a + 0.03, z - 0.1, z + 0.03, mat="metal", uv=DT.UV_STEEL)


# ================================================================== sewer
SW_IN, SW_CH = 1.9, 0.5                       # interior half width, channel half width
DOOR_Y = (4.0, 5.2)                           # access door span along Y (Sewer_Access +X wall = Sewer_Stair -X wall)


def sewer_section(L, name, y0, y1, side_door=None, open_x=False):
    """Sewer interior between y0 and y1 (walkways, channel, vault chamfers, pipes, lamps, grime)."""
    zf, zc = UG["sewer_floor"], UG["sewer_floor"] + UG["sewer_height"]
    ch_b = zf - 0.6
    # walkways (solid) + channel floor; the floor slab is laid by shell() below ch_b
    for sx in (-1, 1):
        a, b = sorted((sx * SW_CH, sx * SW_IN))
        box_all(L, SOLID, (a, b, y0, y1, ch_b, zf), "concrete", UV_REVEAL)
        L["road"].hquad(a, b, y0, y1, zf, mat="road_int", uv=UV_TILE)
    L["road"].hquad(-SW_CH, SW_CH, y0, y1, ch_b, mat="road_int", uv=UV_TILE)
    L["res0"].hquad(-SW_CH, SW_CH, y0, y1, ch_b + 0.005, mat="rubble", uv=UV_RUBBLE)               # silt
    # vault chamfers (Res + Geometry): 45 deg brick haunches along both walls
    for sx in (-1, 1):
        x_wall, x_in = sx * SW_IN, sx * (SW_IN - 0.6)
        verts = [(x_wall, y0, zc - 0.6), (x_wall, y0, zc), (x_in, y0, zc),
                 (x_wall, y1, zc - 0.6), (x_wall, y1, zc), (x_in, y1, zc)]
        faces = [(0, 1, 2), (3, 4, 5), (0, 1, 4, 3), (1, 2, 5, 4), (2, 0, 3, 5)]
        for k in ("res0", "res1", "geo", "fire"):
            L[k].lod.solid(verts, faces, **kw_for(k, "wall_brick", UV_BRICK, "masonry"))
    # pipes + cable tray on the walls, lamps under the crown, rungs
    pipe_run(L, -SW_IN + 0.18, y0, y1, zf + 1.6, 0.12)
    pipe_run(L, -SW_IN + 0.14, y0, y1, zf + 1.95, 0.06, "metal", DT.UV_STEEL)
    pipe_run(L, SW_IN - 0.2, y0, y1, zf + 1.75, 0.15, "rust", UV_RUST_GREY)
    L["res0"].box(SW_IN - 0.35, SW_IN - 0.05, y0, y1, zc - 0.25, zc - 0.2, mat="metal", uv=DT.UV_STEEL)
    for yy in [y0 + 3.0 + 6.0 * i for i in range(int((y1 - y0) / 6.0))]:
        lamp(L, 0.0, yy, zc, True)
    cable_run(L, SW_IN - 0.08, y0, y1, zc - 0.45, sag=0.1, n_brackets=3)          # D66 detail
    for i, sx in enumerate((-1, 1)):
        graffiti(L, name, sx * SW_IN - 0.001 * sx, y0 + 2.0 + 5.0 * i, y0 + 3.6 + 5.0 * i, zf + 0.4, zf + 1.5, -sx, i)
    # handrail along one walkway edge
    for k in ("res0",):
        L[k].lod.box(-SW_CH - 0.05, -SW_CH - 0.02, y0, y1, zf + 0.92, zf + 0.96, mat="metal", uv=DT.UV_STEEL)
        for yy in [y0 + 0.5 + 2.0 * i for i in range(int((y1 - y0) / 2.0))]:
            L[k].lod.box(-SW_CH - 0.05, -SW_CH - 0.02, yy - 0.02, yy + 0.02, zf, zf + 0.92, mat="metal", uv=DT.UV_STEEL)
    for i in range(6):                                                                            # junk in the silt
        x = -SW_CH + 0.15 + (2 * SW_CH - 0.3) * h01(name, "jx", i)
        y = y0 + (y1 - y0) * h01(name, "jy", i)
        L["res0"].box(x - 0.08, x + 0.08, y - 0.12, y + 0.12, ch_b, ch_b + 0.06, mat="trash", uv=UVWorld(S.MATERIALS["trash"]["sheet_m"]))


def rubble_mound(L, name, x0, x1, y0, y1, z0, h, n_bricks=14):
    """Collapse heap (D67): a walkable rubble ramp (solid wedge rising to the middle, Roadway over it)
    with loose bricks and a few slabs on it; z0 = the floor it lies on."""
    ym = (y0 + y1) / 2
    for (ya, yb, za, zb) in ((y0, ym, z0, z0 + h), (ym, y1, z0 + h, z0)):
        verts = [(x0, ya, z0), (x1, ya, z0), (x1, yb, z0), (x0, yb, z0), (x0, ya, za), (x1, ya, za), (x1, yb, zb), (x0, yb, zb)]
        faces = [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (2, 3, 7, 6), (0, 3, 7, 4), (1, 2, 6, 5)]
        if za == z0:
            verts = [(x0, ya, z0), (x1, ya, z0), (x1, yb, z0), (x0, yb, z0), (x1, yb, zb), (x0, yb, zb)]
            faces = [(0, 1, 2, 3), (0, 1, 4, 5), (2, 3, 5, 4), (0, 3, 5), (1, 2, 4)]
        else:
            verts = [(x0, ya, z0), (x1, ya, z0), (x1, yb, z0), (x0, yb, z0), (x1, ya, za), (x0, ya, za)]
            faces = [(0, 1, 2, 3), (2, 3, 5, 4), (0, 1, 4, 5), (0, 3, 5), (1, 2, 4)]
        for k in ("res0", "res1", "geo", "fire", "view"):
            L[k].lod.solid(verts, faces, **kw_for(k, "rubble", UV_RUBBLE, "concrete"))
        L["road"].lod.quad([(x0, ya, za), (x1, ya, za), (x1, yb, zb), (x0, yb, zb)], (0, 0, 1), "road_int", UV_TILE)
    for i in range(n_bricks):
        bx = x0 + (x1 - x0) * h01(name, "bx", i)
        by = y0 + (y1 - y0) * h01(name, "by", i)
        top = z0 + h * (1 - abs(by - ym) / ((y1 - y0) / 2))
        L["res0"].box(bx - 0.11, bx + 0.11, by - 0.06, by + 0.06, top - 0.02, top + 0.06, mat="wall_brick", uv=UV_BRICK)
    for i in range(2):
        bx = x0 + (x1 - x0) * (0.3 + 0.4 * i)
        slab = [(bx - 0.5, ym - 0.6, z0 + h * 0.4), (bx + 0.5, ym - 0.6, z0 + h * 0.4), (bx + 0.5, ym + 0.6, z0 + h * 0.9),
                (bx - 0.5, ym + 0.6, z0 + h * 0.9), (bx - 0.5, ym - 0.6, z0 + h * 0.4 + 0.15), (bx + 0.5, ym - 0.6, z0 + h * 0.4 + 0.15),
                (bx + 0.5, ym + 0.6, z0 + h * 0.9 + 0.15), (bx - 0.5, ym + 0.6, z0 + h * 0.9 + 0.15)]
        for k in ("res0", "geo", "fire", "view"):                                 # slabs are solid (D67 security L1)
            L[k].lod.solid(slab, [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (2, 3, 7, 6), (0, 3, 7, 4), (1, 2, 6, 5)],
                           **kw_for(k, "concrete", UV_CONC, "concrete"))


def build_sewer_straight(access=False, end=False, collapsed=False, flooded=False):
    name = "Sewer_End" if end else ("Sewer_Access" if access else "Sewer_Straight")
    name = "Sewer_FloodedEnd" if flooded else ("Sewer_Collapsed" if collapsed else name)
    L = L_new(name)
    hy = LEN / 2
    zf, zc = UG["sewer_floor"], UG["sewer_floor"] + UG["sewer_height"]
    shell_sewer(L, -hy, hy, door=access)
    sewer_section(L, name, -hy, hy)
    flood_plane(L, -SW_IN, SW_IN, -hy, hy, zf - 0.45)
    if end:                                                                                       # brick end wall + outfall grating
        box_all(L, SOLID, (-SW_IN, SW_IN, hy - 0.5, hy, zf - 0.6, zc), "wall_brick", UV_BRICK, "masonry")
        for i in range(9):
            xx = -SW_CH + 0.05 + i * (2 * SW_CH - 0.1) / 8
            L["res0"].box(xx - 0.015, xx + 0.015, hy - 0.62, hy - 0.5, zf - 0.6, zf + 0.6, mat="rust", uv=UV_RUST)
    if collapsed:                                                                                 # D67: part of the vault came down
        rubble_mound(L, name, -SW_CH, SW_IN, -2.6, 2.6, zf - 0.6, 1.5)
        for k in ("res0", "geo", "fire"):                                         # lamp hanging on its cable (solid, D67 sec L1)
            L[k].box(-0.25, 0.25, 0.2, 0.7, zc - 1.2, zc - 0.2, **kw_for(k, "metal", DT.UV_STEEL, "metal"))
        C.bar(L["res0"].lod, (0.0, 0.45, zc - 0.2), (0.0, 0.45, zc), 0.01, "rubble", UV_RUBBLE)
    if flooded:                                                                                   # D67: standing water to the knees
        for k in ("res0", "res1"):
            L[k].lod.quad([(-SW_IN, -hy, zf + 0.35), (SW_IN, -hy, zf + 0.35), (SW_IN, hy - 0.5, zf + 0.35), (-SW_IN, hy - 0.5, zf + 0.35)],
                          (0, 0, 1), "glassfar", C.UV_GLASS)
        for i in range(5):                                                                        # floating junk
            fx, fy = -1.5 + 3.0 * h01(name, "fx", i), -4.5 + 9.0 * h01(name, "fy", i)
            L["res0"].box(fx - 0.15, fx + 0.15, fy - 0.1, fy + 0.1, zf + 0.33, zf + 0.4, mat="trash", uv=UVWorld(S.MATERIALS["trash"]["sheet_m"]))
    L["mem"].lod.point("center", (0.0, 0.0, zf))
    if access:
        L["mem"].lod.point("access", (SW_IN + 0.25, sum(DOOR_Y) / 2, zf))
    return C._finish(L, 400000.0)


def shell_sewer(L, y0, y1, door=False, xopen=False):
    """Sewer shell: floor below the channel, roof fill, side walls (the +X wall gets a 1.2 m door at y 0 for
    the access piece; a junction opens both X walls)."""
    zf, zc = UG["sewer_floor"], UG["sewer_floor"] + UG["sewer_height"]
    zb, zt, w = zf - 1.2, UG["roof_top"], 0.5
    box_all(L, SOLID, (-SW_IN - w, SW_IN + w, y0, y1, zb, zf - 0.6), "concrete", UV_CONC)
    box_all(L, SOLID, (-SW_IN - w, SW_IN + w, y0, y1, zc, zt), "concrete", UV_CONC, skip=("+z",))
    L["res0"].hquad(-SW_IN - w, SW_IN + w, y0, y1, zt, mat="concrete", uv=UV_CONC)
    for sx in (-1, 1):
        a, b = sorted((sx * SW_IN, sx * (SW_IN + w)))
        spans = [(y0, y1)]
        if (door and sx > 0) or xopen:
            spans = [(y0, DOOR_Y[0]), (DOOR_Y[1], y1)] if door and not xopen else []
            if door and sx > 0:
                box_all(L, SOLID, (a, b, DOOR_Y[0], DOOR_Y[1], zf + 2.1, zc), "wall_brick", UV_BRICK, "masonry")   # lintel
        for (s0, s1) in spans:
            box_all(L, SOLID, (a, b, s0, s1, zf - 0.6, zc), "wall_brick", UV_BRICK, "masonry")
    L["res2"].box(-SW_IN - w, SW_IN + w, y0, y1, zb, zt, mat="concrete", uv=UV_CONC)
    L["res3"].box(-SW_IN - w, SW_IN + w, y0, y1, zb, zt, mat="concrete", uv=UV_CONC)
    L["road"].hquad(-SW_IN - w, SW_IN + w, y0, y1, zt, mat="road_ext", uv=UV_TILE)
    L["shadow"].lod.box(-SW_IN - w, SW_IN + w, y0, y1, zb, zt)


def build_sewer_junction():
    """12 x 12 m crossing: four corner masses, channels crossing in the middle, a collecting well."""
    name = "Sewer_Junction"
    L = L_new(name)
    hy = LEN / 2
    zf, zc = UG["sewer_floor"], UG["sewer_floor"] + UG["sewer_height"]
    zb, zt, w = zf - 1.2, UG["roof_top"], 0.5
    box_all(L, SOLID, (-hy, hy, -hy, hy, zb, zf - 0.6), "concrete", UV_CONC)
    box_all(L, SOLID, (-hy, hy, -hy, hy, zc, zt), "concrete", UV_CONC, skip=("+z",))
    L["res0"].hquad(-hy, hy, -hy, hy, zt, mat="concrete", uv=UV_CONC)
    for sx in (-1, 1):                                                                            # corner masses
        for sy in (-1, 1):
            xa, xb = sorted((sx * (SW_IN + w + 0.0), sx * hy))
            ya, yb = sorted((sy * (SW_IN + w), sy * hy))
            box_all(L, SOLID, (xa, xb, ya, yb, zf - 0.6, zc), "wall_brick", UV_BRICK, "masonry")
            xa, xb = sorted((sx * SW_CH, sx * (SW_IN + w)))
            ya, yb = sorted((sy * SW_CH, sy * hy))
            box_all(L, SOLID, (xa, xb, ya, yb, zf - 0.6, zf), "concrete", UV_REVEAL)                # walkways
            L["road"].hquad(xa, xb, ya, yb, zf, mat="road_int", uv=UV_TILE)
            xa, xb = sorted((sx * (SW_IN + w), sx * hy))
            ya, yb = sorted((sy * SW_CH, sy * (SW_IN + w)))
            box_all(L, SOLID, (xa, xb, ya, yb, zf - 0.6, zf), "concrete", UV_REVEAL)
            L["road"].hquad(xa, xb, ya, yb, zf, mat="road_int", uv=UV_TILE)
    for (a, b, c, d) in ((-SW_CH, SW_CH, -hy, hy), (-hy, -SW_CH, -SW_CH, SW_CH), (SW_CH, hy, -SW_CH, SW_CH)):
        L["road"].hquad(a, b, c, d, zf - 0.6, mat="road_int", uv=UV_TILE)
        L["res0"].hquad(a, b, c, d, zf - 0.595, mat="rubble", uv=UV_RUBBLE)
    for k in ("res0", "res1"):                                                                    # plank bridges over the channels
        for (a, b, c, d) in ((-SW_CH, SW_CH, -SW_IN - w, -SW_IN - w + 0.8), (-SW_IN - w, -SW_IN - w + 0.8, -SW_CH, SW_CH)):
            L[k].box(a - 0.05, b + 0.05, c, d, zf - 0.06, zf, mat="wood", uv=DT.UV_OAK)
    lamp(L, 0.0, 0.0, zc, True)
    for (a, b) in ((-hy, -SW_IN - w), (SW_IN + w, hy)):
        lamp(L, (a + b) / 2, 0.0, zc, False)
    flood_plane(L, -hy, hy, -hy, hy, zf - 0.45)
    # D78 close-up: brick pilasters at the four inner corners (solid), a grated collecting well where the
    # channels cross, pipes and cables along the arms, a dislodged walkway grating, graffiti, silt junk
    ci = SW_IN + w
    for sx in (-1, 1):
        for sy in (-1, 1):
            xa, xb = sorted((sx * (ci - 0.1), sx * (ci + 0.15)))                                     # quoin wrapping the corner
            ya, yb = sorted((sy * (ci - 0.1), sy * (ci + 0.15)))
            box_all(L, SOLID, (xa, xb, ya, yb, zf, zc), "wall_brick", UV_BRICK, "masonry")
            box_all(L, ("res0",), (xa - 0.03, xb + 0.03, ya - 0.03, yb + 0.03, zc - 0.25, zc), "concrete", UV_REVEAL)  # impost
    zb_ = zf - 0.6
    for (a, b, c, d) in ((-0.45, 0.45, -0.45, -0.39), (-0.45, 0.45, 0.39, 0.45), (-0.45, -0.39, -0.39, 0.39), (0.39, 0.45, -0.39, 0.39)):
        L["res0"].box(a, b, c, d, zb_, zb_ + 0.05, mat="metal", uv=DT.UV_STEEL, skip=("-z",))      # well kerb
    for i in range(7):                                                                             # grating bars
        gx = -0.33 + i * 0.11
        L["res0"].box(gx - 0.012, gx + 0.012, -0.39, 0.39, zb_ + 0.02, zb_ + 0.045, mat="rust", uv=UV_RUST)
    for sx in (-1, 1):                                                                             # pipes along the Y arms
        x = sx * (ci - 0.16)
        for (y0_, y1_) in ((-hy, -ci), (ci, hy)):
            C.bar(L["res0"].lod, (x, y0_, zf + 2.2), (x, y1_, zf + 2.2), 0.1, "rust", UV_RUST)               # above head height (sec D78 L3)
            C.bar(L["res0"].lod, (x + sx * 0.04, y0_, zf + 2.42), (x + sx * 0.04, y1_, zf + 2.42), 0.05, "metal", DT.UV_STEEL)
    for sy in (-1, 1):                                                                             # and along the X arms
        y = sy * (ci - 0.16)
        for (x0_, x1_) in ((-hy, -ci), (ci, hy)):
            C.bar(L["res0"].lod, (x0_, y, zf + 2.2), (x1_, y, zf + 2.2), 0.1, "rust", UV_RUST_GREY)
    cable_run(L, ci - 0.08, ci, hy, zc - 0.45, sag=0.1, n_brackets=2)
    L["res0"].solid([(1.0, -4.6, zf), (1.7, -4.6, zf), (1.7, -3.8, zf + 0.25), (1.0, -3.8, zf + 0.25),
                     (1.0, -4.6, zf + 0.03), (1.7, -4.6, zf + 0.03), (1.7, -3.8, zf + 0.28), (1.0, -3.8, zf + 0.28)],
                    [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)], "rust", UV_RUST)   # dislodged grating
    graffiti(L, name, ci - 0.001, ci + 0.6, ci + 2.4, zf + 0.4, zf + 1.6, -1, 0)
    graffiti(L, name, -ci + 0.001, -hy + 0.8, -ci - 0.6, zf + 0.3, zf + 1.4, 1, 1)
    for i in range(6):                                                                             # junk in the silt
        jx = -SW_CH + 0.1 + (2 * SW_CH - 0.2) * h01(name, "jx", i)
        jy = (2.0 + (hy - 2.5) * h01(name, "jy", i)) * (1 if i % 2 else -1)
        if i % 3 == 2:
            jx, jy = jy, jx
        L["res0"].box(jx - 0.08, jx + 0.08, jy - 0.12, jy + 0.12, zb_, zb_ + 0.06, mat="trash", uv=UVWorld(S.MATERIALS["trash"]["sheet_m"]))
    L["res2"].box(-hy, hy, -hy, hy, zb, zt, mat="concrete", uv=UV_CONC)
    L["res3"].box(-hy, hy, -hy, hy, zb, zt, mat="concrete", uv=UV_CONC)
    L["road"].hquad(-hy, hy, -hy, hy, zt, mat="road_ext", uv=UV_TILE)
    L["shadow"].lod.box(-hy, hy, -hy, hy, zb, zt)
    L["mem"].lod.point("center", (0.0, 0.0, zf))
    return C._finish(L, 800000.0)


def stair_flight(L, x0, x1, y_low, y_high, z_low, z_high, mat="concrete", uv=None, rail_x=None):
    """Straight flight rising from (y_low, z_low) to (y_high, z_high): visual steps, one solid wedge in
    Geometry/Fire, a Roadway ramp. y_high may be < y_low (rises towards -Y)."""
    n = max(2, int(round(abs(z_high - z_low) / 0.18)))
    dy, dz = (y_high - y_low) / n, (z_high - z_low) / n
    for i in range(n):
        ya, yb = sorted((y_low + i * dy, y_low + (i + 1) * dy))
        for k in ("res0", "res1"):
            L[k].box(x0, x1, ya, yb, z_low - 0.3 + i * dz, z_low + (i + 1) * dz, mat=mat, uv=uv or UV_REVEAL)
    lo, hi = sorted((y_low, y_high))
    for k in ("geo", "fire"):
        kw = {"mat": "pen_concrete"} if k == "fire" else {}
        if y_high > y_low:
            L[k].lod.solid([(x0, lo, z_low - 0.3), (x1, lo, z_low - 0.3), (x1, hi, z_high - 0.3), (x0, hi, z_high - 0.3),
                            (x0, lo, z_low), (x1, lo, z_low), (x1, hi, z_high), (x0, hi, z_high)],
                           [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (2, 3, 7, 6), (0, 3, 7, 4), (1, 2, 6, 5)], **kw)
        else:
            L[k].lod.solid([(x0, hi, z_low - 0.3), (x1, hi, z_low - 0.3), (x1, lo, z_high - 0.3), (x0, lo, z_high - 0.3),
                            (x0, hi, z_low), (x1, hi, z_low), (x1, lo, z_high), (x0, lo, z_high)],
                           [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (2, 3, 7, 6), (0, 3, 7, 4), (1, 2, 6, 5)], **kw)
    L["road"].lod.quad([(x0, y_low, z_low), (x1, y_low, z_low), (x1, y_high, z_high), (x0, y_high, z_high)], (0, 0, 1),
                       "road_int", UV_TILE)
    if rail_x is not None:
        for k in ("res0",):
            C.bar(L[k].lod, (rail_x, y_low, z_low + 0.95), (rail_x, y_high, z_high + 0.95), 0.025, "metal", DT.UV_STEEL)


def street_opening_rails(L, x0, x1, y0, y1, zt, open_side="+y"):
    """Rails round a street-level opening (3 sides), a hazard-striped frame, a small sign post."""
    sides = {"-y": (x0, x1, y0 - 0.05, y0), "+y": (x0, x1, y1, y1 + 0.05), "-x": (x0 - 0.05, x0, y0, y1), "+x": (x1, x1 + 0.05, y0, y1)}
    for s, b in sides.items():
        if s == open_side:
            continue
        C.rail(L, b[0], b[1], b[2], b[3], zt)
    L["res0"].box(x0 - 0.12, x1 + 0.12, y0 - 0.12, y1 + 0.12, zt, zt + 0.02, mat="fair", uv=UVBand(S.MATERIALS["fair"]["bands"]["yellow"], 1.0),
                  skip=("-z",))


def build_sewer_stair():
    """2.8 x 12 m stair shaft laid beside a Sewer_Access (same yaw, its centre 3.8 m to the +X side, under
    the sidewalk): street opening at -Y, flight down towards +Y, bottom landing with a 1.2 m door in the
    -X wall that meets the access door (DOOR_Y)."""
    name = "Sewer_Stair"
    L = L_new(name)
    hx, hy, w = 1.0, LEN / 2, 0.4
    zf, zt = UG["sewer_floor"], UG["roof_top"]
    zc = zf + 2.6
    # +X wall full; -X wall with the door at DOOR_Y; end walls
    box_all(L, SOLID, (hx, hx + w, -hy, hy, zf - 0.6, zt), "wall_brick", UV_BRICK, "masonry", skip=("+z",))
    for (s0, s1, z0) in ((-hy, DOOR_Y[0], zf - 0.6), (DOOR_Y[1], hy, zf - 0.6), (DOOR_Y[0], DOOR_Y[1], zf + 2.1)):
        box_all(L, SOLID, (-hx - w, -hx, s0, s1, z0, zt), "wall_brick", UV_BRICK, "masonry", skip=("+z",))
    for (a_, b_) in ((-hx - w, -hx), (hx, hx + w)):
        L["res0"].hquad(a_, b_, -hy, hy, zt, mat="concrete", uv=UV_CONC)
    box_all(L, SOLID, (-hx, hx, -hy, -hy + w, zf - 0.6, zt), "wall_brick", UV_BRICK, "masonry")              # -Y end
    box_all(L, SOLID, (-hx, hx, hy - w, hy, zf - 0.6, zt), "wall_brick", UV_BRICK, "masonry")                # +Y end
    y_top, y_bot = -hy + w, DOOR_Y[0] - 0.6
    box_all(L, SOLID, (-hx, hx, y_bot, hy - w, zf - 0.6, zf), "concrete", UV_REVEAL)                       # bottom landing
    L["road"].hquad(-hx, hx, y_bot, hy - w, zf, mat="road_int", uv=UV_TILE)
    stair_flight(L, -hx, hx, y_bot, y_top, zf, zt, rail_x=hx - 0.08)
    roof_from = 1.7                                                                                 # 2 m headroom under the roof
    box_all(L, SOLID, (-hx, hx, roof_from, hy - w, zc, zt), "concrete", UV_CONC, skip=("+z",))
    L["res0"].hquad(-hx, hx, roof_from, hy - w, zt, mat="concrete", uv=UV_CONC)
    L["road"].hquad(-hx - w, hx + w, roof_from, hy, zt, mat="road_ext", uv=UV_TILE)
    L["road"].hquad(-hx - w, -hx, -hy, roof_from, zt, mat="road_ext", uv=UV_TILE)
    L["road"].hquad(hx, hx + w, -hy, roof_from, zt, mat="road_ext", uv=UV_TILE)
    street_opening_rails(L, -hx, hx, -hy + w, roof_from, zt, open_side="-y")
    sign_quad(L, "sewer_warn", hx, -hy + 1.4, -hy + 2.6, zt - 0.9, zt - 0.6, -1)    # D66: warning inside the shaft
    sign_quad(L, "exit_l", hx, DOOR_Y[1] + 0.2, DOOR_Y[1] + 1.4, zf + 2.0, zf + 2.3, -1)
    lamp(L, 0.0, 3.5, zc, True)
    pipe_run(L, hx - 0.12, roof_from, hy - w, zc - 0.3, 0.05, "metal", DT.UV_STEEL)
    L["res2"].box(-hx - w, hx + w, -hy, hy, zf - 0.6, zt, mat="concrete", uv=UV_CONC)
    L["res3"].box(-hx - w, hx + w, -hy, hy, zf - 0.6, zt, mat="concrete", uv=UV_CONC)
    L["shadow"].lod.box(-hx - w, hx + w, -hy, hy, zf - 0.6, zt)
    L["mem"].lod.point("street", (0.0, -hy + 1.0, zt))
    L["mem"].lod.point("bottom", (0.0, sum(DOOR_Y) / 2, zf))
    return C._finish(L, 200000.0)


# ================================================================== metro
STATION_SIGNS = {"A": "st_pobedy", "B": "st_vokzal", "C": "st_stadion", "D": "st_teatr"}   # name boards (signs3), D66/D67
MT_IN = 6.0                                   # box tunnel interior half width (tracks at +-TRACK_X like the station)
TRACK_X = 4.6


def tracks(L, y0, y1, zf, xs=(-TRACK_X, TRACK_X)):
    for xc in xs:
        L["res0"].box(xc - 1.3, xc + 1.3, y0, y1, zf, zf + 0.12, mat="rubble", uv=UV_RUBBLE)          # ballast
        for i in range(int((y1 - y0) / 0.6)):
            yy = y0 + 0.3 + 0.6 * i
            L["res0"].box(xc - 1.15, xc + 1.15, yy - 0.12, yy + 0.12, zf + 0.12, zf + 0.22, mat="concrete", uv=UV_REVEAL)
        for rx in (xc - 0.72, xc + 0.72):
            L["res0"].box(rx - 0.035, rx + 0.035, y0, y1, zf + 0.22, zf + 0.36, mat="metal", uv=DT.UV_STEEL)
        L["res1"].box(xc - 1.3, xc + 1.3, y0, y1, zf, zf + 0.3, mat="rubble", uv=UV_RUBBLE)
    for k in ("geo", "fire"):
        for xc in xs:
            L[k].lod.box(xc - 1.3, xc + 1.3, y0, y1, zf, zf + 0.3, **({"mat": "pen_concrete"} if k == "fire" else {}))
    for xc in xs:
        L["road"].hquad(xc - 1.3, xc + 1.3, y0, y1, zf + 0.3, mat="road_int", uv=UV_TILE)


def build_metro_tunnel(end=False, collapsed=False):
    name = "Metro_End" if end else ("Metro_Collapsed" if collapsed else "Metro_Tunnel")
    L = L_new(name)
    hy = LEN / 2
    zf = UG["metro_floor"]
    zc = zf + UG["metro_height"]
    shell(L, -MT_IN, MT_IN, -hy, hy, zf, zc)
    L["road"].hquad(-MT_IN, MT_IN, -hy, hy, zf, mat="road_int", uv=UV_TILE)
    tracks(L, -hy, hy, zf)
    for sx in (-1, 1):                                                                            # service ledges + cables
        a, b = sorted((sx * (MT_IN - 0.7), sx * MT_IN))
        box_all(L, ("res0", "res1", "geo", "fire"), (a, b, -hy, hy, zf, zf + 0.9), "concrete", UV_REVEAL)
        L["road"].hquad(a, b, -hy, hy, zf + 0.9, mat="road_int", uv=UV_TILE)
        for i, zz in enumerate((zf + 2.2, zf + 2.4, zf + 2.6)):
            C.bar(L["res0"].lod, (sx * (MT_IN - 0.05), -hy, zz), (sx * (MT_IN - 0.05), hy, zz), 0.03, "rubble" if i else "metal",
                  UV_RUBBLE if i else DT.UV_STEEL)
    for yy in (-3.0, 3.0):
        lamp(L, -MT_IN + 0.2, yy, zf + 3.6, True)
    for i, sx in enumerate((-1, 1)):                                              # D66 detail
        graffiti(L, name, sx * MT_IN - 0.001 * sx, -3.0 + 4.0 * i, -0.6 + 4.0 * i, zf + 1.0, zf + 2.0, -sx, i)
        cable_run(L, sx * (MT_IN - 0.08), -hy, hy, zf + 3.2, sag=0.15, n_brackets=4)
    L["res0"].box(-0.1, 0.1, -hy, hy, zc - 0.3, zc, mat="metal", uv=DT.UV_STEEL)                    # catenary beam
    if end:                                                                                       # end wall + buffer stops
        box_all(L, SOLID, (-MT_IN, MT_IN, hy - 0.5, hy, zf, zc), "concrete", UV_CONC)
        for xc in (-TRACK_X, TRACK_X):
            for k in ("res0", "res1", "geo", "fire"):
                L[k].box(xc - 1.0, xc + 1.0, hy - 2.0, hy - 1.4, zf + 0.3, zf + 1.4, **kw_for(k, "fair", UVBand(S.MATERIALS["fair"]["bands"]["red"], 1.0), "metal"))
            L["res0"].box(xc - 0.9, xc + 0.9, hy - 2.06, hy - 2.0, zf + 0.9, zf + 1.2, mat="fair", uv=UVBand(S.MATERIALS["fair"]["bands"]["white"], 1.0))
    if collapsed:                                                                                 # D67: +X track buried, -X passable
        rubble_mound(L, name, 0.8, MT_IN, -4.5, 4.5, zf, 2.6, n_bricks=24)
        for k in ("res0", "geo", "fire", "view"):                                 # fallen catenary beam (solid, D67 sec L1)
            C.bar(L[k].lod, (-0.1, -hy + 1.0, zc - 0.3), (2.5, 2.0, zf + 2.2), 0.12,
                  *(("metal", DT.UV_STEEL) if k == "res0" else (("pen_metal", None) if k == "fire" else (None, None))))
    L["shadow"].lod.box(-MT_IN - 0.5, MT_IN + 0.5, -hy, hy, zf - 0.8, UG["roof_top"])
    L["mem"].lod.point("center", (0.0, 0.0, zf))
    return C._finish(L, 1500000.0)


def build_metro_station(variant="A"):
    """24 x 16 m station: two tracks at the sides, a 6 m island platform with columns, tiled walls with
    the station name, benches, bins, a ticket kiosk, and a stair up to a street opening at +Y."""
    name = "Metro_Station" + ("" if variant == "A" else "_" + variant)
    sign = STATION_SIGNS[variant]
    L = L_new(name)
    hy, hx = 12.0, 8.0
    zf = UG["metro_floor"]
    zp = zf + 1.0
    zc = zf + UG["metro_height"] + 0.8
    zt = UG["roof_top"]
    open_from = 4.0                                                                                 # stair headroom (2 m) from here
    shell(L, -hx, hx, -hy, hy, zf, zc, inner="tile", inner_uv=UV_TILES, hole=(-1.4, 1.4, open_from, hy))
    L["road"].hquad(-hx, hx, -hy, hy, zf, mat="road_int", uv=UV_TILE)
    tracks(L, -hy, hy, zf)
    for sy in (-1, 1):                                                                            # end walls round the tunnel mouths
        ya, yb = sorted((sy * hy, sy * (hy - 0.5)))
        for sx in (-1, 1):
            xa, xb = sorted((sx * MT_IN, sx * hx))
            box_all(L, SOLID, (xa, xb, ya, yb, zf, zc), "tile", UV_TILES)
        box_all(L, SOLID, (-MT_IN, MT_IN, ya, yb, zf + UG["metro_height"], zc), "tile", UV_TILES)
    box_all(L, SOLID, (-3.0, 3.0, -hy, hy, zf, zp), "concrete", UV_REVEAL)                        # platform
    L["road"].hquad(-3.0, 3.0, -hy, hy, zp, mat="road_int", uv=UV_TILE)
    for k in ("res0", "res1"):
        L[k].lod.hquad(-3.0, 3.0, -hy, hy, zp + 0.003, mat="marble", uv=UVWorld(2.0))
    for sx in (-1, 1):                                                                            # safety lines
        L["res0"].lod.box(sx * 2.75 - 0.08, sx * 2.75 + 0.08, -hy, hy, zp, zp + 0.006, mat="fair",
                          uv=UVBand(S.MATERIALS["fair"]["bands"]["yellow"], 1.0))
    # columns (2 rows), clad in tile, with lamps
    stair_y0, stair_y1 = -1.0, hy                                                                  # stair zone on the platform
    for yy in (-9.0, -5.0, -1.5):
        for xx in (-1.8, 1.8):
            box_all(L, SOLID, (xx - 0.3, xx + 0.3, yy - 0.3, yy + 0.3, zp, zc), "tile", UV_TILES)
            lamp(L, xx, yy + 1.0, zc, True)
    # stair from the platform (y -1) up to the street (y 12) at x -1.4..1.4, with a roof opening at y 8.5..12
    stair_flight(L, -1.4, 1.4, stair_y0 + 0.2, stair_y1 - 0.3, zp, zt, rail_x=1.32)
    for sx in (-1, 1):                                                                            # stair parapets
        box_all(L, SOLID, (sx * 1.4 - 0.1 * (sx < 0), sx * 1.4 + 0.1 * (sx > 0), stair_y0, stair_y1, zp, zp + 1.1),
                "tile", UV_TILES)
    street_opening_rails(L, -1.4, 1.4, open_from, hy, zt, open_side="+y")
    # benches, bins, kiosk, station signs on the track walls
    for yy in (-7.0, -3.2):
        for sx in (-1, 1):
            xx = sx * 1.0
            for k in ("res0", "res1", "geo"):
                kw = kw_for(k, "wood", DT.UV_OAK, "wood")
                L[k].box(xx - 0.25, xx + 0.25, yy - 0.9, yy + 0.9, zp + 0.42, zp + 0.48, **kw)
            L["res0"].box(xx - 0.2, xx + 0.2, yy - 0.8, yy - 0.74, zp, zp + 0.42, mat="metal", uv=DT.UV_STEEL)
            L["res0"].box(xx - 0.2, xx + 0.2, yy + 0.74, yy + 0.8, zp, zp + 0.42, mat="metal", uv=DT.UV_STEEL)
    for k in ("res0", "res1", "geo", "fire"):                                                      # ticket kiosk
        L[k].box(-1.2, 1.2, -11.6, -10.0, zp, zp + 2.4, **kw_for(k, "paint", DT.paint_uv("sage"), "wood"))
    L["res0"].box(-1.0, 1.0, -10.02, -10.0, zp + 1.0, zp + 1.8, mat="glass", uv=C.UV_GLASS)
    C.search_point(L, 0.0, -9.3, zp)                                              # D68: search the kiosk (table kiosk)
    for sx in (-1, 1):                                                            # station name boards (D66)
        for yy in (-6.0, 6.0):
            sign_quad(L, sign, sx * hx, yy - 2.0, yy + 2.0, zf + 2.8, zf + 3.3, -sx)
        for i, yy in enumerate((-9.5, -2.0, 3.0, 9.0)):
            graffiti(L, name, sx * hx - 0.001 * sx, yy - 1.0, yy + 1.0, zf + 0.6, zf + 2.4, -sx, i + (10 if sx > 0 else 0))
        cable_run(L, sx * (hx - 0.05), -hy + 0.6, hy - 0.6, zf + 4.4, n_brackets=6)
    sign_hung(L, "exit_r", -1.4, 1.4, 3.6, zp + 2.5, zp + 2.85, zc)               # over the stair foot
    for xx in (-1.8, 1.8):                                                        # line boards on the columns
        sign_quad(L, "line1", xx - 0.3 if xx < 0 else xx + 0.3, -9.35, -8.65, zp + 1.9, zp + 2.15, -1 if xx < 0 else 1)
    L["shadow"].lod.box(-hx - 0.5, hx + 0.5, -hy, hy, zf - 0.8, zt)
    L["mem"].lod.point("center", (0.0, 0.0, zp))
    L["mem"].lod.point("street", (0.0, hy - 0.5, zt))
    return C._finish(L, 3000000.0)


BUILDERS = {
    "Sewer_Straight": lambda: build_sewer_straight(False), "Sewer_Access": lambda: build_sewer_straight(True),
    "Sewer_End": lambda: build_sewer_straight(end=True),
    "Sewer_Collapsed": lambda: build_sewer_straight(collapsed=True),
    "Sewer_FloodedEnd": lambda: build_sewer_straight(end=True, flooded=True),
    "Metro_Collapsed": lambda: build_metro_tunnel(collapsed=True),
    "Metro_Station_B": lambda: build_metro_station("B"), "Metro_Station_C": lambda: build_metro_station("C"),
    "Metro_Station_D": lambda: build_metro_station("D"),
    "Sewer_Junction": build_sewer_junction, "Sewer_Stair": build_sewer_stair,
    "Metro_Tunnel": build_metro_tunnel, "Metro_End": lambda: build_metro_tunnel(True), "Metro_Station": build_metro_station,
}


def modules():
    return {n: (BUILDERS[n], e["pbo"], e["p3d"]) for n, e in S.KIT.items() if n in BUILDERS}


if __name__ == "__main__":
    run_cli(modules(), KIT_MATS, "build_stats_underground.json")
