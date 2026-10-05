"""Generator for the SKY kit (street kit + props) - run headless in Blender 4.2.

    blender -b --factory-startup -P build_kit.py -- --out <mods/SKY_Skyline/addons> [--only StreetLight,Dumpster]

Same pipeline as build_towera.py (skygeo Lod -> Arma Toolbox MLOD). Every asset
is registered in skyspec.KIT (class, p3d, PBO, budget category). Builders return
Res0/Res1/Res2 + Geometry + Fire Geometry (+ View / Roadway / Memory where useful).
Requires ARMATOOLBOX_PATH.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import skyspec as S  # noqa: E402
from build_towera import MATS, UV_ALU, UV_CONC_PANEL, UV_CONC_REVEAL, UV_GLASS, UV_STEEL  # noqa: E402
from skygeo import (LOD_FIREGEO, LOD_GEOMETRY, LOD_MEMORY, LOD_RES, LOD_ROADWAY, LOD_VIEWGEO,  # noqa: E402
                    Lod, UVBand, UVRect, UVWorld, run_cli)

UV_ASPHALT = UVWorld(4.0)
UV_PAVER = UVWorld(3.0)
B_RUST = S.MATERIALS["rust"]["bands"]
UV_GREEN, UV_GREY, UV_RUST, UV_BURNT = (UVBand(B_RUST[k], 2.0) for k in ("green", "grey", "rust", "burnt"))
B_MARK = S.MATERIALS["roadmark"]["bands"]
ST = S.STREET


def props_lods(view=False, road=False, mem=False):
    L = {"res0": Lod("res0", LOD_RES, 0.0), "res1": Lod("res1", LOD_RES, 1.0), "res2": Lod("res2", LOD_RES, 2.0),
         "geo": Lod("geo", LOD_GEOMETRY), "fire": Lod("fire", LOD_FIREGEO)}
    if view:
        L["view"] = Lod("view", LOD_VIEWGEO)
    if road:
        L["road"] = Lod("road", LOD_ROADWAY)
    if mem:
        L["mem"] = Lod("mem", LOD_MEMORY)
    return L


def finish(L, mass):
    # Same Geometry convention as Tower A (Test_Building sample) minus map=building:
    # props are not drawn as buildings on the in-game map (decision D5).
    L["geo"].props.update({"class": "house", "autocenter": "0"})
    L["geo"].mass = mass
    return list(L.values())


def solid_all(L, keys, fn, pen=None, vis=None):
    """Call fn(lod, **kw) for each LOD key with the right material kwargs."""
    for k in keys:
        if k.startswith("res"):
            fn(L[k], **(vis or {}))
        elif k == "fire":
            fn(L[k], mat="pen_" + pen) if pen else fn(L[k])
        else:
            fn(L[k])


def line_quad(L, keys, x0, x1, y0, y1, band, along="y", repeat=1.0, z=0.006):
    """Road paint strip: tiles `repeat` times along its length, V = paint band."""
    v0, v1 = 1.0 - B_MARK[band][1], 1.0 - B_MARK[band][0]
    if along == "y":
        uv = UVRect(1, 0, (y0, x0), (y1, x1), (0.0, v0, repeat, v1))
    else:
        uv = UVRect(0, 1, (x0, y0), (x1, y1), (0.0, v0, repeat, v1))
    for k in keys:
        L[k].hquad(x0, x1, y0, y1, z, mat="roadmark", uv=uv)


# ------------------------------------------------------------------ roads (12 m grid)
def asphalt_boxes(L, rects, z0=-ST["slab_t"]):
    for (x0, x1, y0, y1) in rects:
        for k in ("res0", "res1"):
            L[k].box(x0, x1, y0, y1, z0, 0.0, mat="asphalt", uv=UV_ASPHALT, skip=("-z",))
        L["res2"].hquad(x0, x1, y0, y1, 0.0, mat="asphalt", uv=UV_ASPHALT)
        L["geo"].box(x0, x1, y0, y1, z0, 0.0)
        L["fire"].box(x0, x1, y0, y1, z0, 0.0, mat="pen_concrete")
        L["road"].hquad(x0, x1, y0, y1, 0.0, mat="road_asphalt", uv=UV_ASPHALT)


def build_road(crossing=False):
    L = props_lods(road=True)
    h = ST["tile"] / 2
    w = ST["carriageway"] / 2
    asphalt_boxes(L, [(-w, w, -h, h)])
    line_quad(L, ("res0", "res1"), -0.075, 0.075, -h, h, "dashed", repeat=1.0)
    for x in (-w + 0.2, w - 0.35):
        line_quad(L, ("res0",), x, x + 0.15, -h, h, "solid", repeat=1.0)
    if crossing:
        line_quad(L, ("res0", "res1"), -w, w, -1.5, 1.5, "crosswalk", along="x", repeat=1.0, z=0.007)
    return finish(L, 20000.0)


def build_intersection(t_junction=False):
    L = props_lods(road=True)
    h = ST["tile"] / 2
    w = ST["carriageway"] / 2
    rects = [(-w, w, -h, h), (w, h, -w, w)]
    if not t_junction:
        rects.append((-h, -w, -w, w))
    asphalt_boxes(L, rects)
    # crosswalks on every road entry, inside the 2 m arm
    line_quad(L, ("res0", "res1"), -w, w, w, h, "crosswalk", along="x")
    line_quad(L, ("res0", "res1"), -w, w, -h, -w, "crosswalk", along="x")
    line_quad(L, ("res0", "res1"), w, h, -w, w, "crosswalk", along="y")
    if not t_junction:
        line_quad(L, ("res0", "res1"), -h, -w, -w, w, "crosswalk", along="y")
    else:
        sidewalk_slab(L, -h, -w, -h, h, curb_side="+x")
    return finish(L, 30000.0)


def sidewalk_slab(L, x0, x1, y0, y1, curb_side="+x", curb2=None):
    top = ST["curb_h"]
    z0 = -ST["slab_t"]
    for k in ("res0", "res1"):
        L[k].box(x0, x1, y0, y1, z0, top, mat="concrete", uv=UV_CONC_REVEAL, skip=("-z", "+z"))
        L[k].hquad(x0, x1, y0, y1, top, mat="paver", uv=UV_PAVER)
    L["res2"].hquad(x0, x1, y0, y1, top, mat="paver", uv=UV_PAVER)
    L["geo"].box(x0, x1, y0, y1, z0, top)
    L["fire"].box(x0, x1, y0, y1, z0, top, mat="pen_concrete")
    L["road"].hquad(x0, x1, y0, y1, top, mat="road_ext", uv=UV_PAVER)
    for side in [curb_side] + ([curb2] if curb2 else []):     # curb stone band on the road side(s)
        if side == "+x":
            r = (x1 - 0.15, x1, y0, y1)
        elif side == "-x":
            r = (x0, x0 + 0.15, y0, y1)
        elif side == "+y":
            r = (x0, x1, y1 - 0.15, y1)
        else:
            r = (x0, x1, y0, y0 + 0.15)
        L["res0"].box(r[0], r[1], r[2], r[3], top - 0.001, top + 0.02, mat="concrete", uv=UV_CONC_REVEAL, skip=("-z",))


def build_sidewalk():
    L = props_lods(road=True)
    h = ST["tile"] / 2
    s = ST["sidewalk"] / 2
    sidewalk_slab(L, -s, s, -h, h, curb_side="+x")
    return finish(L, 8000.0)


def build_sidewalk_corner():
    L = props_lods(road=True)
    s = ST["sidewalk"] / 2
    sidewalk_slab(L, -s, s, -s, s, curb_side="+x", curb2="+y")
    return finish(L, 1500.0)


def build_curb():
    L = props_lods()
    prof = [(0.0, -0.3), (0.15, -0.3), (0.15, 0.12), (0.12, 0.17), (0.0, 0.17)]
    for k in ("res0", "res1"):
        L[k].extrude_y(prof, -1.5, 1.5, mat="concrete", uv=UV_CONC_REVEAL)
    L["res2"].box(0.0, 0.15, -1.5, 1.5, -0.3, 0.17, mat="concrete", uv=UV_CONC_REVEAL, skip=("-z",))
    L["geo"].extrude_y(prof, -1.5, 1.5)
    L["fire"].extrude_y(prof, -1.5, 1.5, mat="pen_concrete")
    return finish(L, 300.0)


def build_manhole():
    L = props_lods()
    uv = UVRect(0, 1, (-0.4, -0.4), (0.4, 0.4), S.atlas_uv("manhole"))
    for k, n in (("res0", 12), ("res1", 8), ("res2", 6)):
        L[k].prism(0.0, 0.0, 0.4, 0.0, 0.02, n=n, mat="atlas", uv=uv)
    L["geo"].prism(0.0, 0.0, 0.4, 0.0, 0.02, n=8)
    L["fire"].prism(0.0, 0.0, 0.4, 0.0, 0.02, n=8, mat="pen_metal")
    return finish(L, 90.0)


# ------------------------------------------------------------------ street furniture
def build_streetlight():
    L = props_lods(mem=True)
    for k, n in (("res0", 8), ("res1", 6), ("res2", 4)):
        L[k].prism(0.0, 0.0, 0.08, 0.0, 8.0, n=n, mat="rust", uv=UV_GREY)
    for k in ("res0", "res1"):
        L[k].prism(0.0, 0.0, 0.16, 0.0, 0.45, n=8, mat="rust", uv=UV_GREY)
        L[k].box(0.0, 1.6, -0.04, 0.04, 7.8, 7.88, mat="rust", uv=UV_GREY)
        L[k].box(1.2, 1.8, -0.17, 0.17, 7.7, 7.85, mat="rust", uv=UV_GREY, skip=("-z",))
        L[k].hquad(1.22, 1.78, -0.15, 0.15, 7.699, mat="lamp", uv=UVWorld(1.0), up=False)
    L["res2"].box(0.0, 1.8, -0.1, 0.1, 7.7, 7.88, mat="rust", uv=UV_GREY)
    L["geo"].prism(0.0, 0.0, 0.16, 0.0, 0.45, n=8)
    L["geo"].prism(0.0, 0.0, 0.08, 0.45, 8.0, n=6)
    L["fire"].prism(0.0, 0.0, 0.08, 0.0, 8.0, n=6, mat="pen_metal")
    L["fire"].box(1.2, 1.8, -0.17, 0.17, 7.7, 7.85, mat="pen_metal")
    L["mem"].point("light", (1.5, 0.0, 7.6))
    L["mem"].point("light_dir", (1.5, 0.0, 6.6))
    return finish(L, 250.0)


def build_trafficlight():
    L = props_lods()
    face = UVRect(0, 2, (4.62, 4.62), (4.93, 5.58), S.atlas_uv("traffic"))
    for k, n in (("res0", 8), ("res1", 6), ("res2", 4)):
        L[k].prism(0.0, 0.0, 0.1, 0.0, 5.8, n=n, mat="rust", uv=UV_GREY)
    for k in ("res0", "res1"):
        L[k].box(0.0, 5.0, -0.05, 0.05, 5.6, 5.75, mat="rust", uv=UV_GREY)
        L[k].box(4.6, 4.95, -0.17, 0.17, 4.6, 5.6, mat="rust", uv=UV_BURNT)
        L[k].quad([(4.62, -0.171, 4.62), (4.93, -0.171, 4.62), (4.93, -0.171, 5.58), (4.62, -0.171, 5.58)],
                  (0, -1, 0), "atlas", face)
    L["res0"].box(-0.3, -0.1, -0.12, 0.12, 2.4, 3.0, mat="rust", uv=UV_BURNT)       # pedestrian head
    L["res2"].box(0.0, 5.0, -0.1, 0.1, 5.5, 5.75, mat="rust", uv=UV_GREY)
    L["geo"].prism(0.0, 0.0, 0.1, 0.0, 5.8, n=6)
    L["fire"].prism(0.0, 0.0, 0.1, 0.0, 5.8, n=6, mat="pen_metal")
    L["fire"].box(4.6, 4.95, -0.17, 0.17, 4.6, 5.6, mat="pen_metal")
    return finish(L, 300.0)


JERSEY = [(-0.3, 0.0), (0.3, 0.0), (0.1, 0.3), (0.08, 0.8), (-0.08, 0.8), (-0.1, 0.3)]


def build_barrier_concrete():
    L = props_lods(view=True)
    for k in ("res0", "res1"):
        L[k].extrude_y(JERSEY, -1.5, 1.5, mat="concrete", uv=UV_CONC_REVEAL)
    L["res2"].extrude_y([(-0.3, 0.0), (0.3, 0.0), (0.08, 0.8), (-0.08, 0.8)], -1.5, 1.5, mat="concrete", uv=UV_CONC_REVEAL)
    L["geo"].extrude_y(JERSEY, -1.5, 1.5)
    L["view"].extrude_y(JERSEY, -1.5, 1.5)
    L["fire"].extrude_y(JERSEY, -1.5, 1.5, mat="pen_concrete")
    return finish(L, 2000.0)


def build_barrier_steel():
    L = props_lods()
    vis = {"mat": "rust", "uv": UV_GREY}
    for k in ("res0", "res1"):
        for z0, z1 in ((0.15, 0.2), (1.05, 1.1)):
            L[k].box(-0.025, 0.025, -1.2, 1.2, z0, z1, **vis)
        for y in (-1.2, 1.15):
            L[k].box(-0.025, 0.025, y, y + 0.05, 0.05, 1.1, **vis)
            L[k].box(-0.35, 0.35, y, y + 0.05, 0.0, 0.05, **vis)
    for i in range(1, 12):                                                  # bars, res0 only
        y = -1.2 + i * 0.2
        L["res0"].box(-0.01, 0.01, y - 0.01, y + 0.01, 0.2, 1.05, **vis)
    L["res2"].box(-0.025, 0.025, -1.2, 1.2, 0.05, 1.1, **vis)
    L["geo"].box(-0.03, 0.03, -1.2, 1.2, 0.05, 1.1)
    for y in (-1.2, 1.15):
        L["geo"].box(-0.35, 0.35, y, y + 0.05, 0.0, 0.05)
    L["fire"].box(-0.025, 0.025, -1.2, 1.2, 1.05, 1.1, mat="pen_metal")
    L["fire"].box(-0.025, 0.025, -1.2, 1.2, 0.15, 0.2, mat="pen_metal")
    return finish(L, 60.0)


def build_busstop():
    L = props_lods(view=True)
    met = {"mat": "metal", "uv": UV_ALU}
    posts = [(-1.95, -0.75), (1.87, -0.75), (-1.95, 0.67), (1.87, 0.67)]
    for k in ("res0", "res1", "geo", "fire"):
        kw = met if k.startswith("res") else ({"mat": "pen_metal"} if k == "fire" else {})
        for (x, y) in posts:
            L[k].box(x, x + 0.08, y, y + 0.08, 0.0, 2.5, **kw)
        L[k].box(-2.1, 2.1, -0.9, 0.9, 2.5, 2.6, **kw)
    L["res2"].box(-2.1, 2.1, -0.9, 0.9, 0.0, 2.6, mat="glassfar", uv=UV_GLASS, skip=("-z",))
    L["view"].box(-2.1, 2.1, -0.9, 0.9, 2.5, 2.6)
    # Glass: back + one side (double-sided in res0, single in res1); collision + fire as thin boxes.
    panes = [("y", 0.72, (-1.9, 1.85), (0.3, 2.4)), ("x", -1.9, (-0.6, 0.7), (0.3, 2.4))]
    for axis, c, (a0, a1), (z0, z1) in panes:
        if axis == "y":
            q = [(a0, c, z0), (a1, c, z0), (a1, c, z1), (a0, c, z1)]
            box = (a0, a1, c - 0.01, c + 0.01, z0, z1)
            facing = (0, 1, 0)
        else:
            q = [(c, a0, z0), (c, a1, z0), (c, a1, z1), (c, a0, z1)]
            box = (c - 0.01, c + 0.01, a0, a1, z0, z1)
            facing = (-1, 0, 0)
        L["res0"].quad(q, facing, "glass", UV_GLASS, double=True)
        L["res1"].quad(q, facing, "glass", UV_GLASS)
        L["geo"].box(*box)
        L["fire"].box(*box, mat="pen_glass")
    for k in ("res0", "res1", "geo", "fire"):
        kw = met if k.startswith("res") else ({"mat": "pen_metal"} if k == "fire" else {})
        L[k].box(-1.5, 1.5, 0.3, 0.7, 0.42, 0.47, **kw)                       # bench
    tt = UVRect(0, 2, (1.2, 1.0), (1.8, 2.0), S.atlas_uv("timetable"))
    L["res0"].box(1.2, 1.8, 0.68, 0.7, 1.0, 2.0, **met)
    L["res0"].quad([(1.2, 0.679, 1.0), (1.8, 0.679, 1.0), (1.8, 0.679, 2.0), (1.2, 0.679, 2.0)], (0, -1, 0), "atlas", tt)
    return finish(L, 800.0)


def build_dumpster():
    L = props_lods()
    for k in ("res0", "res1", "res2"):
        L[k].box(-0.9, 0.9, -0.5, 0.5, 0.15, 1.1, mat="rust", uv=UV_GREEN)
    for k in ("res0", "res1"):
        L[k].box(-0.95, 0.95, -0.55, 0.55, 1.1, 1.16, mat="rust", uv=UV_GREEN)
    for (x, y) in ((-0.75, -0.4), (0.75, -0.4), (-0.75, 0.4), (0.75, 0.4)):
        L["res0"].prism(x, y, 0.07, 0.0, 0.15, n=6, mat="rust", uv=UV_BURNT)
    L["geo"].box(-0.95, 0.95, -0.55, 0.55, 0.0, 1.16)
    L["fire"].box(-0.95, 0.95, -0.55, 0.55, 0.0, 1.16, mat="pen_metal")
    return finish(L, 400.0)


def build_planter():
    L = props_lods()
    for k in ("res0", "res1", "res2"):
        L[k].box(-0.75, 0.75, -0.75, 0.75, 0.0, 0.6, mat="concrete", uv=UV_CONC_REVEAL, skip=("-z", "+z"))
        L[k].hquad(-0.7, 0.7, -0.7, 0.7, 0.55, mat="asphalt", uv=UV_ASPHALT)
    for k in ("res0", "res1"):
        for axis in ("x", "y"):
            if axis == "x":
                q = [(-0.7, 0.0, 0.5), (0.7, 0.0, 0.5), (0.7, 0.0, 1.7), (-0.7, 0.0, 1.7)]
                uv, fac = UVRect(0, 2, (-0.7, 0.5), (0.7, 1.7)), (0, -1, 0)
            else:
                q = [(0.0, -0.7, 0.5), (0.0, 0.7, 0.5), (0.0, 0.7, 1.7), (0.0, -0.7, 1.7)]
                uv, fac = UVRect(1, 2, (-0.7, 0.5), (0.7, 1.7)), (1, 0, 0)
            L[k].quad(q, fac, "foliage", uv, double=True)
    L["geo"].box(-0.75, 0.75, -0.75, 0.75, 0.0, 0.6)
    L["fire"].box(-0.75, 0.75, -0.75, 0.75, 0.0, 0.6, mat="pen_concrete")
    return finish(L, 900.0)


def wheels(L, keys, xs, ys, r=0.3, zc=0.28, n=8, width=0.2, uv=None):
    import math
    prof = [(r * math.cos(2 * math.pi * i / n), zc + r * math.sin(2 * math.pi * i / n)) for i in range(n)]
    for k in keys:
        for x in xs:
            for y in ys:
                L[k].extrude_x([(y + py, pz) for py, pz in prof], x, x + (width if x > 0 else -width),
                               mat="rust", uv=uv or UV_BURNT)


def build_wreck_sedan():
    L = props_lods()
    cab = [(-1.1, 0.85), (1.0, 0.85), (0.6, 1.4), (-0.7, 1.4)]          # (y, z) trapezoid
    for k in ("res0", "res1", "res2"):
        L[k].box(-0.9, 0.9, -2.1, 2.1, 0.25, 0.85, mat="rust", uv=UV_RUST)
        L[k].extrude_x(cab, -0.8, 0.8, mat="rust", uv=UV_RUST)
    wheels(L, ("res0",), (0.75, -0.75), (-1.3, 1.35))
    wheels(L, ("res1",), (0.75, -0.75), (-1.3, 1.35), n=6)
    for k in ("geo", "fire"):
        kw = {"mat": "pen_metal"} if k == "fire" else {}
        L[k].box(-0.9, 0.9, -2.1, 2.1, 0.0, 0.85, **kw)
        L[k].extrude_x(cab, -0.8, 0.8, **kw)
    return finish(L, 1100.0)


def build_wreck_van():
    L = props_lods(view=True)
    cab = [(1.0, 0.9), (2.6, 0.9), (2.6, 1.5), (2.0, 2.1), (1.0, 2.1)]
    for k in ("res0", "res1", "res2"):
        L[k].box(-1.0, 1.0, -2.6, 2.6, 0.3, 0.9, mat="rust", uv=UV_BURNT)
        L[k].box(-1.05, 1.05, -2.6, 1.0, 0.9, 2.6, mat="rust", uv=UV_BURNT)
        L[k].extrude_x(cab, -1.0, 1.0, mat="rust", uv=UV_RUST)
    wheels(L, ("res0",), (0.85, -0.85), (-1.8, 1.7), r=0.35, zc=0.33)
    wheels(L, ("res1",), (0.85, -0.85), (-1.8, 1.7), r=0.35, zc=0.33, n=6)
    for k in ("geo", "fire", "view"):
        kw = {"mat": "pen_metal"} if k == "fire" else {}
        L[k].box(-1.0, 1.0, -2.6, 2.6, 0.0, 0.9, **kw)
        L[k].box(-1.05, 1.05, -2.6, 1.0, 0.9, 2.6, **kw)
        if k != "view":
            L[k].extrude_x(cab, -1.0, 1.0, **kw)
    return finish(L, 2500.0)


def build_billboard():
    L = props_lods(view=True)
    poster = UVRect(0, 2, (-3.0, 4.0), (3.0, 7.0))
    for k in ("res0", "res1", "res2", "geo", "fire"):
        kw = {"mat": "rust", "uv": UV_GREY} if k.startswith("res") else ({"mat": "pen_metal"} if k == "fire" else {})
        for x in (-2.1, 1.9):
            if k == "res2":      # far LOD: posts as single back-facing quads
                L[k].quad([(x, 0.0, 0.0), (x + 0.2, 0.0, 0.0), (x + 0.2, 0.0, 4.0), (x, 0.0, 4.0)], (0, -1, 0), **kw, double=True)
            else:
                L[k].box(x, x + 0.2, -0.1, 0.1, 0.0, 4.0, **kw)
        L[k].box(-3.0, 3.0, -0.1, 0.1, 4.0, 7.0, **kw, **({"skip": ("-y",)} if k == "res2" else {}))
    for k in ("res0", "res1", "res2"):
        L[k].quad([(-3.0, -0.101, 4.0), (3.0, -0.101, 4.0), (3.0, -0.101, 7.0), (-3.0, -0.101, 7.0)],
                  (0, -1, 0), "billboard", poster, sel=["camo"])
    L["view"].box(-3.0, 3.0, -0.1, 0.1, 4.0, 7.0)
    return finish(L, 1500.0)


BUILDERS = {
    "Road_Straight": build_road, "Road_Crossing": lambda: build_road(crossing=True),
    "Intersection_4Way": build_intersection, "Intersection_T": lambda: build_intersection(t_junction=True),
    "Sidewalk": build_sidewalk, "Sidewalk_Corner": build_sidewalk_corner, "Curb": build_curb, "Manhole": build_manhole,
    "StreetLight": build_streetlight, "TrafficLight": build_trafficlight,
    "Barrier_Concrete": build_barrier_concrete, "Barrier_Steel": build_barrier_steel, "BusStop": build_busstop,
    "Dumpster": build_dumpster, "Planter": build_planter, "Wreck_Sedan": build_wreck_sedan,
    "Wreck_Van": build_wreck_van, "Billboard": build_billboard,
}

KIT_MATS = dict(MATS)
KIT_MATS["road_asphalt"] = {"co": S.ROADWAY_ASPHALT, "rvmat": ""}


def modules():
    """{name: (builder, pbo, p3d)} for every KIT entry that has a builder here."""
    return {n: (BUILDERS[n], e["pbo"], e["p3d"]) for n, e in S.KIT.items() if n in BUILDERS}


if __name__ == "__main__":
    run_cli(modules(), KIT_MATS, "build_stats_kit.json")
