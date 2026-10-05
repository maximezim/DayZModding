"""Parametric generator for Tower A modules + keycard (run headless in Blender 4.2).

    blender -b --factory-startup -P build_towera.py -- --out <mods/SKY_Skyline/addons> [--only core,lobby]

Requires ARMATOOLBOX_PATH (folder containing the ArmaToolbox package).
Writes MLOD P3Ds into <out>/sky_towera and <out>/sky_items and a stats JSON
(triangles per LOD) next to them. All dimensions come from assets/skyspec.py.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import skyspec as S  # noqa: E402
from skygeo import (LOD_FIREGEO, LOD_GEOMETRY, LOD_MEMORY, LOD_RES, LOD_ROADWAY,  # noqa: E402
                    LOD_SHADOW, LOD_VIEWGEO, Lod, UVBand, UVFit, UVWorld, export_p3d,
                    floor_quads_with_hole, slab_with_hole, wall_x, wall_y)

HW, HD = S.TOWER_A["footprint"][0] / 2, S.TOWER_A["footprint"][1] / 2
CORE_HOLE = (S.CORE["x"][0], S.CORE["x"][1], S.CORE["y"][0], S.CORE["y"][1])
CT = S.CURTAIN_T

# Material table for Arma Toolbox: visual materials + penetration + roadway surfaces.
MATS = {k: {"co": v["co"], "rvmat": v["rvmat"]} for k, v in S.MATERIALS.items()}
for k, (path, _verified) in S.PENETRATION.items():
    MATS["pen_" + k] = {"co": "", "rvmat": path}
MATS["road_int"] = {"co": S.ROADWAY_INT, "rvmat": ""}
MATS["road_ext"] = {"co": S.ROADWAY_EXT, "rvmat": ""}
MATS["keycard"] = {"co": S.PREFIX_ITEMS + "\\data\\sky_keycard_t1_co.paa",
                   "rvmat": S.PREFIX_ITEMS + "\\data\\sky_keycard.rvmat"}

UV_CONC_PANEL = UVBand(S.MATERIALS["concrete"]["bands"]["panel"], 3.0)
UV_CONC_REVEAL = UVBand(S.MATERIALS["concrete"]["bands"]["reveal"], 3.0)
UV_ALU = UVBand(S.MATERIALS["metal"]["bands"]["alu"], 3.0)
UV_STEEL = UVBand(S.MATERIALS["metal"]["bands"]["steel"], 1.0)
UV_PAINT = UVBand(S.MATERIALS["metal"]["bands"]["painted"], 2.0)
UV_TILE = UVWorld(3.0)
UV_CARPET = UVWorld(4.0)
UV_WALL = UVWorld(4.0)
UV_GLASS = UVWorld(3.0)


def std_lods():
    return {
        "res0": Lod("res0", LOD_RES, 0.0), "res1": Lod("res1", LOD_RES, 1.0),
        "res2": Lod("res2", LOD_RES, 2.0), "res3": Lod("res3", LOD_RES, 3.0),
        "shadow": Lod("shadow", LOD_SHADOW), "geo": Lod("geo", LOD_GEOMETRY),
        "view": Lod("view", LOD_VIEWGEO), "fire": Lod("fire", LOD_FIREGEO),
        "road": Lod("road", LOD_ROADWAY), "mem": Lod("mem", LOD_MEMORY),
    }


def building_props(L, mass):
    # Same Geometry properties as Bohemia's Test_Building sample + autocenter=0
    # so stacked modules share an exact origin convention.
    L["geo"].props.update({"class": "house", "map": "building", "autocenter": "0"})
    L["geo"].mass = mass


# ------------------------------------------------------------------ facade
def _segments(span0, span1, holes):
    """Split [span0, span1] around hole intervals."""
    cuts = sorted(holes)
    out, cur = [], span0
    for h0, h1 in cuts:
        if h0 > cur:
            out.append((cur, h0))
        cur = max(cur, h1)
    if cur < span1:
        out.append((cur, span1))
    return out


def facade(L, z0, z1, entrances=(), transom=None):
    """Curtain wall on all four sides of the footprint.
    entrances: [(side, a0, a1, top)] openings with no glass below `top`."""
    sides = {
        "S": ("x", -HD, (0, -1, 0)), "N": ("x", HD, (0, 1, 0)),
        "W": ("y", -HW, (-1, 0, 0)), "E": ("y", HW, (1, 0, 0)),
    }
    for side, (axis, plane, out) in sides.items():
        span = HW if axis == "x" else HD
        ent = [(a0, a1, top) for (s, a0, a1, top) in entrances if s == side]
        sgn = 1 if plane > 0 else -1
        g_in, g_out = plane - sgn * CT, plane            # glass box extent across the wall
        gp = plane - sgn * CT / 2                         # glass plane

        def rect(a0, a1, b0, b1):
            if axis == "x":
                return [(a0, gp, b0), (a1, gp, b0), (a1, gp, b1), (a0, gp, b1)]
            return [(gp, a0, b0), (gp, a1, b0), (gp, a1, b1), (gp, a0, b1)]

        def sbox(lod, a0, a1, b0, b1, d0, d1, **kw):
            lo, hi = min(d0, d1), max(d0, d1)
            if axis == "x":
                lod.box(a0, a1, lo, hi, b0, b1, **kw)
            else:
                lod.box(lo, hi, a0, a1, b0, b1, **kw)

        # Glass: full-height panes between entrances, glass above entrances.
        pieces = [(a0, a1, z0, z1) for (a0, a1) in _segments(-span, span, [(e[0], e[1]) for e in ent])]
        pieces += [(e[0], e[1], e[2], z1) for e in ent if e[2] < z1]
        for a0, a1, b0, b1 in pieces:
            q = rect(a0, a1, b0, b1)
            L["res0"].quad(q, out, "glass", UV_GLASS, double=True)
            L["res1"].quad(q, out, "glass", UV_GLASS)
            L["res2"].quad(q, out, "glassfar", UV_GLASS)
            sbox(L["geo"], a0, a1, b0, b1, g_in, g_out)
            sbox(L["fire"], a0, a1, b0, b1, g_in, g_out, mat="pen_glass")
        # Mullions: 1.5 m in res0, 3.0 m in res1 (skip inside entrances).
        for lod_key, step in (("res0", 1.5), ("res1", 3.0)):
            a = -span
            while a <= span + 1e-6:
                inside = any(e[0] + 1e-3 < a < e[1] - 1e-3 for e in ent)
                b_start = max([e[2] for e in ent if e[0] - 1e-3 <= a <= e[1] + 1e-3] or [z0]) if inside else z0
                if not inside or b_start < z1:
                    sbox(L[lod_key], a - S.MULLION_W / 2, a + S.MULLION_W / 2, b_start, z1,
                         plane - sgn * (CT + 0.02), plane + sgn * 0.04, mat="metal", uv=UV_ALU)
                a += step
        if transom is not None:
            for lod_key in ("res0", "res1"):
                sbox(L[lod_key], -span, span, transom - 0.05, transom + 0.05,
                     plane - sgn * (CT + 0.02), plane + sgn * 0.04, mat="metal", uv=UV_ALU)
        # Res3: one opaque-looking glass quad per side (single sided).
        L["res3"].quad(rect(-span, span, z0, z1), out, "glassfar", UV_GLASS)


def floor_slab(L, top_mat, top_uv, road_mat, mass_unused=None, z=0.0):
    """Slab (z-0.3..z) with the core hole: concrete body, separate top surface."""
    for k in ("res0", "res1"):
        slab_with_hole(L[k], HW, HD, CORE_HOLE, z - S.SLAB_T, z, mat="concrete", uv=UV_CONC_REVEAL, skip=("+z",))
        floor_quads_with_hole(L[k], HW, HD, CORE_HOLE, z, mat=top_mat, uv=top_uv)
    slab_with_hole(L["res2"], HW, HD, CORE_HOLE, z - S.SLAB_T, z, mat="concrete", uv=UV_CONC_REVEAL)
    slab_with_hole(L["geo"], HW, HD, CORE_HOLE, z - S.SLAB_T, z)
    slab_with_hole(L["view"], HW, HD, CORE_HOLE, z - S.SLAB_T, z)
    slab_with_hole(L["fire"], HW, HD, CORE_HOLE, z - S.SLAB_T, z, mat="pen_concrete")
    slab_with_hole(L["shadow"], HW, HD, CORE_HOLE, z - S.SLAB_T, z)
    floor_quads_with_hole(L["road"], HW, HD, CORE_HOLE, z, mat=road_mat, uv=UV_TILE)
    # Occluder planes: the four slab pieces.
    hx0, hx1, hy0, hy1 = CORE_HOLE
    for i, (x0, x1, y0, y1) in enumerate([(-HW, HW, -HD, hy0), (-HW, HW, hy1, HD), (-HW, hx0, hy0, hy1), (hx1, HW, hy0, hy1)]):
        L["view"].occluder([(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)], "occluder_%03d" % (i + 1))


def lights(L, z):
    for i, (x, y) in enumerate([(-7.5, -7.5), (7.5, -7.5), (-7.5, 7.5), (7.5, 7.5)]):
        L["mem"].point("light_%d" % (i + 1), (x, y, z))


# ------------------------------------------------------------------ modules
def build_floor_office():
    L = std_lods()
    wt = S.FLOOR_H - S.SLAB_T
    floor_slab(L, "carpet", UV_CARPET, "road_int")
    facade(L, 0.0, wt)
    # One enclosed office in the SW quadrant (partitions, door opening on its north wall).
    t = S.WALL_T / 2
    for k in ("res0", "res1", "geo", "view", "fire"):
        kw = {"mat": "wall", "uv": UV_WALL} if k.startswith("res") else ({"mat": "pen_masonry"} if k == "fire" else {})
        wall_x(L[k], -HW + CT, -6.0 + t, -6.0 - t, -6.0 + t, 0.0, wt, openings=[(-8.5, -7.5, 0.0, 2.1)], **kw)
        wall_y(L[k], -6.0 - t, -6.0 + t, -HD + CT, -6.0 - t, 0.0, wt, **kw)
    lights(L, wt - 0.1)
    L["mem"].point("floor_center", (0.0, -8.0, 0.05))
    building_props(L, 40000.0)
    # Res3 caps: slab edge band so the far LOD reads as a stack of floors.
    L["res3"].box(-HW, HW, -HD, HD, -S.SLAB_T, 0.0, mat="concrete", uv=UV_CONC_REVEAL, skip=("+z", "-z"))
    return list(L.values())


def build_lobby():
    L = std_lods()
    h = S.TOWER_A["lobby_h"]
    wt = h - S.SLAB_T
    floor_slab(L, "tile", UV_TILE, "road_int")
    # Foundation skirt so sloped terrain never shows a gap under the podium.
    skirt = [(-HW, HW, -HD, -HD + 0.3), (-HW, HW, HD - 0.3, HD), (-HW, -HW + 0.3, -HD + 0.3, HD - 0.3),
             (HW - 0.3, HW, -HD + 0.3, HD - 0.3)]
    for k in ("res0", "res1", "res2"):
        for (x0, x1, y0, y1) in skirt:
            L[k].box(x0, x1, y0, y1, -2.5, -S.SLAB_T, mat="concrete", uv=UV_CONC_PANEL, skip=("+z", "-z"))
    # Res3: outer face of each skirt side only.
    for (x0, x1, y0, y1), keep in zip(skirt, ("-y", "+y", "-x", "+x")):
        L["res3"].box(x0, x1, y0, y1, -2.5, -S.SLAB_T, mat="concrete", uv=UV_CONC_PANEL,
                      skip=tuple(f for f in ("-x", "+x", "-y", "+y", "-z", "+z") if f != keep))
    # Skirt is solid too: on sloped sites nobody walks/shoots/looks under the slab.
    for k in ("geo", "view", "fire"):
        kw = {"mat": "pen_concrete"} if k == "fire" else {}
        for (x0, x1, y0, y1) in skirt:
            L[k].box(x0, x1, y0, y1, -2.5, -S.SLAB_T, **kw)
    facade(L, 0.0, wt, entrances=[("S", -1.5, 1.5, 3.0)], transom=3.0)
    L["res3"].box(-HW, HW, -HD, HD, -S.SLAB_T, 0.0, mat="concrete", uv=UV_CONC_REVEAL, skip=("+z", "-z"))
    # Reception desk.
    for k in ("res0", "res1"):
        L[k].box(-1.8, 1.8, -8.2, -7.4, 0.0, 1.1, mat="metal", uv=UV_PAINT)
    L["geo"].box(-1.8, 1.8, -8.2, -7.4, 0.0, 1.1)
    L["fire"].box(-1.8, 1.8, -8.2, -7.4, 0.0, 1.1, mat="pen_wood")
    # Security room (NE corner) with the keycard door on its west wall.
    d = S.KEYCARD_DOOR
    rx0, rx1 = S.SECURITY_ROOM["x"]
    ry0, ry1 = S.SECURITY_ROOM["y"]
    t = S.WALL_T / 2
    room_h = 3.0
    hy0 = d["hinge"][1]
    hy1 = hy0 + d["width"]
    for k in ("res0", "res1", "geo", "view", "fire"):
        kw = {"mat": "concrete", "uv": UV_CONC_PANEL} if k.startswith("res") else ({"mat": "pen_concrete"} if k == "fire" else {})
        wall_y(L[k], rx0 - t, rx0 + t, ry0 - t, ry1, 0.0, room_h, openings=[(hy0, hy1, 0.0, d["height"])], **kw)
        wall_x(L[k], rx0 + t, rx1, ry0 - t, ry0 + t, 0.0, room_h, **kw)
        L[k].box(rx0 - t, rx1, ry0 - t, ry1, room_h, room_h + 0.2, **kw)
    # Door leaf (bone/selection/component = door_sec), hinge on the south jamb.
    dx = d["hinge"][0]
    sel = [d["name"]]
    for k in ("res0", "res1"):
        L[k].box(dx - 0.025, dx + 0.025, hy0 + 0.01, hy1 - 0.01, 0.0, d["height"] - 0.01, mat="metal", uv=UV_STEEL, sel=sel)
        L[k].box(dx - 0.2, dx - t, hy1 + 0.15, hy1 + 0.3, 1.1, 1.3, mat="metal", uv=UV_STEEL)   # card reader
    L["geo"].box(dx - 0.025, dx + 0.025, hy0 + 0.01, hy1 - 0.01, 0.0, d["height"] - 0.01, sel=sel)
    L["view"].box(dx - 0.025, dx + 0.025, hy0 + 0.01, hy1 - 0.01, 0.0, d["height"] - 0.01, sel=sel)
    L["fire"].box(dx - 0.025, dx + 0.025, hy0 + 0.01, hy1 - 0.01, 0.0, d["height"] - 0.01, mat="pen_metal", sel=sel)
    L["shadow"].box(rx0 - t, rx1, ry0 - t, ry1, 0.0, room_h + 0.2)
    m = L["mem"]
    m.point(d["name"] + "_axis", (dx, hy0, 0.0))
    m.point(d["name"] + "_axis", (dx, hy0, d["height"]))
    m.point(d["name"] + "_action", (dx - 0.4, (hy0 + hy1) / 2, 1.1))
    m.point(d["name"], (dx, (hy0 + hy1) / 2, 1.05))
    lights(L, wt - 0.2)
    m.point("entrance", (0.0, -HD - 1.0, 0.0))
    building_props(L, 60000.0)
    return list(L.values())


def build_roof_helipad():
    L = std_lods()
    floor_slab(L, "concrete", UV_CONC_PANEL, "road_ext")
    par = 1.1
    for k in ("res0", "res1", "res2", "geo", "view", "fire", "res3", "shadow"):
        kw = {"mat": "concrete", "uv": UV_CONC_REVEAL} if k.startswith("res") else ({"mat": "pen_concrete"} if k == "fire" else {})
        for (x0, x1, y0, y1) in [(-HW, HW, -HD, -HD + 0.25), (-HW, HW, HD - 0.25, HD),
                                 (-HW, -HW + 0.25, -HD + 0.25, HD - 0.25), (HW - 0.25, HW, -HD + 0.25, HD - 0.25)]:
            L[k].box(x0, x1, y0, y1, 0.0, par, **kw)
    # Helipad marking decal (6.5 m square north of the core).
    pad = (-3.25, 3.25, 4.9, 11.4)
    for k in ("res0", "res1"):
        L[k].hquad(pad[0], pad[1], pad[2], pad[3], 0.01, mat="roofmark", uv=UVFit(*pad))
    m = L["mem"]
    m.point("heli_pad", (0.0, (pad[2] + pad[3]) / 2, 0.05))
    for i, (x, y) in enumerate(S.ROOF_DROPS):
        m.point("roof_drop_%d" % (i + 1), (x, y, 0.05))
    building_props(L, 30000.0)
    return list(L.values())


def _step_skip(i, n, back):
    """Faces of stair step i hidden by its neighbours: sides (walls), bottom
    (inside the previous step) and back (inside the next step)."""
    skip = ["-x", "+x"]
    if i > 0:
        skip.append("-z")
    if i < n - 1:
        skip.append(back)
    return tuple(skip)


def build_core():
    L = std_lods()
    C = S.CORE
    x0, x1 = C["x"]
    y0, y1 = C["y"]
    w = S.WALL_T
    stops = S.elevator_stops()
    top = S.core_height()
    ix0, ix1, iy0, iy1 = x0 + w, x1 - w, y0 + w, y1 - w            # interior
    sd0, sd1 = C["stair_door_x"]
    ed = C["door_w"] / 2

    def solid_kw(k):
        if k.startswith("res"):
            return {"mat": "concrete", "uv": UV_CONC_PANEL}
        return {"mat": "pen_concrete"} if k == "fire" else {}

    # Outer walls with openings at every stop (res0/res1/geo/view/fire).
    south_open = [(sd0, sd1, s, s + 2.2) for s in stops]
    north_open = [(-ed, ed, s, s + C["door_h"]) for s in stops]
    for k in ("res0", "res1", "res2", "geo", "view", "fire"):
        kw = solid_kw(k)
        # Res2 is seen from outside only: emit the outer face of each wall piece (+ jambs).
        far = (lambda side: {"skip": (side, "+z", "-z")}) if k == "res2" else (lambda side: {})
        wall_x(L[k], x0, x1, y0, iy0, 0.0, top, openings=south_open, **kw, **far("+y"))
        wall_x(L[k], x0, x1, iy1, y1, 0.0, top, openings=north_open, **kw, **far("-y"))
        wall_y(L[k], x0, ix0, iy0, iy1, 0.0, top, **kw, **far("+x"))
        wall_y(L[k], ix1, x1, iy0, iy1, 0.0, top, **kw, **far("-x"))
        if k == "res2":
            L[k].box(x0, x1, y0, y1, top, top + S.SLAB_T, **kw)
            continue
        # Stair / elevator divider and the cap.
        sy = C["stair_y"][1]
        wall_x(L[k], ix0, ix1, sy - w, sy, 0.0, top, **kw)
        L[k].box(x0, x1, y0, y1, top, top + S.SLAB_T, **kw)
        L[k].box(ix0, ix1, iy0, iy1, -S.SLAB_T, 0.0, **kw)               # ground slab
    # Far LODs: closed shell (doors read as closed from distance).
    L["res3"].box(x0, x1, y0, y1, 0.0, top + S.SLAB_T, mat="concrete", uv=UV_CONC_PANEL, skip=("-z",))
    L["shadow"].box(x0, x1, y0, y1, 0.0, top + S.SLAB_T)

    # ---- stairs: 0 -> roof stop, sections of FLOOR_H with a mid landing.
    riser_n = 10
    half = S.FLOOR_H / 2
    yA0, yA1 = iy0 + 1.2, -0.25          # flight run (y), landing depth 1.2 at the door side
    tread = (yA1 - yA0) / riser_n
    xa = (ix0, -0.15)                     # flight A (up, +y)
    xb = (0.15, ix1)                      # flight B (up, -y)
    n_sections = int(round(stops[-1] / S.FLOOR_H))
    for sec in range(n_sections):
        z0 = sec * S.FLOOR_H
        zm = z0 + half
        zt = z0 + S.FLOOR_H
        # Landings: top landing (door side) and mid landing (divider side).
        for k in ("res0", "res1", "geo", "fire"):
            kw = {"mat": "concrete", "uv": UV_CONC_REVEAL} if k.startswith("res") else ({"mat": "pen_concrete"} if k == "fire" else {})
            L[k].box(ix0, ix1, iy0, yA0, zt - 0.2, zt, **kw)
            L[k].box(ix0, ix1, yA1, C["stair_y"][1] - w, zm - 0.2, zm, **kw)
        L["road"].hquad(ix0, ix1, iy0, yA0, zt, mat="road_int", uv=UV_TILE)
        L["road"].hquad(ix0, ix1, yA1, C["stair_y"][1] - w, zm, mat="road_int", uv=UV_TILE)
        # Flights: steps in res0, ramps elsewhere.
        for i in range(riser_n):
            ya = yA0 + i * tread
            L["res0"].box(xa[0], xa[1], ya, ya + tread, z0 + (i + 1) * half / riser_n - 0.25, z0 + (i + 1) * half / riser_n,
                          mat="concrete", uv=UV_CONC_REVEAL, skip=_step_skip(i, riser_n, "+y"))
            yb = yA1 - (i + 1) * tread
            L["res0"].box(xb[0], xb[1], yb, yb + tread, zm + (i + 1) * half / riser_n - 0.25, zm + (i + 1) * half / riser_n,
                          mat="concrete", uv=UV_CONC_REVEAL, skip=_step_skip(i, riser_n, "-y"))
        L["res1"].ramp(xa[0], xa[1], yA0, yA1, z0, zm, mat="concrete", uv=UV_CONC_REVEAL)
        L["res1"].ramp(xb[0], xb[1], yA1, yA0, zm, zt, mat="concrete", uv=UV_CONC_REVEAL)
        L["geo"].wedge(xa[0], xa[1], yA0, yA1, z0 - 0.25, z0, zm)
        L["geo"].wedge(xb[0], xb[1], yA1, yA0, zm - 0.25, zm, zt)
        L["fire"].wedge(xa[0], xa[1], yA0, yA1, z0 - 0.25, z0, zm, mat="pen_concrete")
        L["fire"].wedge(xb[0], xb[1], yA1, yA0, zm - 0.25, zm, zt, mat="pen_concrete")
        L["road"].ramp(xa[0], xa[1], yA0, yA1, z0, zm, mat="road_int", uv=UV_TILE)
        L["road"].ramp(xb[0], xb[1], yA1, yA0, zm, zt, mat="road_int", uv=UV_TILE)
        L["mem"].point("light_stair_%d" % sec, (0.0, iy0 + 0.6, zt - 0.4))
    # Well wall between the flights: one continuous wall (fewer components than one per storey).
    for k in ("res0", "res1", "geo", "fire"):
        kw = {"mat": "concrete", "uv": UV_CONC_REVEAL} if k.startswith("res") else ({"mat": "pen_concrete"} if k == "fire" else {})
        L[k].box(-0.15, 0.15, yA0, yA1, 0.0, stops[-1], **kw)
    # Ground-floor stair landing is the core ground slab.
    L["road"].hquad(ix0, ix1, iy0, yA0, 0.0, mat="road_int", uv=UV_TILE)

    # ---- elevator: one cab per stop (teleport-style), sliding doors on the north face.
    cx0, cx1 = C["cab_x"]
    ey0 = C["elev_y"][0]
    for k in ("res0", "res1", "geo", "view", "fire"):
        kw = {"mat": "metal", "uv": UV_ALU} if k.startswith("res") else ({"mat": "pen_metal"} if k == "fire" else {})
        L[k].box(ix0, cx0, ey0, iy1, 0.0, top, **kw)                 # shaft side fills (cab side walls)
        L[k].box(cx1, ix1, ey0, iy1, 0.0, top, **kw)
    for i, s in enumerate(stops):
        ch = C["cab_h"]
        for k in ("res0", "res1", "geo", "view", "fire"):
            kw = {"mat": "metal", "uv": UV_ALU} if k.startswith("res") else ({"mat": "pen_metal"} if k == "fire" else {})
            L[k].box(ix0, ix1, ey0, iy1, s + ch, s + ch + 0.2, **kw)   # cab ceiling
            if s > 0:
                L[k].box(ix0, ix1, ey0, iy1, s - S.SLAB_T, s, **kw)    # cab floor
        for k in ("res0", "res1"):
            L[k].hquad(cx0, cx1, ey0, iy1, s + 0.005, mat="tile", uv=UV_TILE)
        L["road"].hquad(cx0, cx1, ey0, iy1, s, mat="road_int", uv=UV_TILE)
        # Door panels: two leaves sliding apart along X.
        for leaf, (a0, a1, sign) in (("a", (-ed, 0.0, -1)), ("b", (0.0, ed, 1))):
            name = "elev_door_l%d_%s" % (i, leaf)
            for k in ("res0", "res1", "geo", "view", "fire"):
                kw = {"mat": "metal", "uv": UV_STEEL} if k.startswith("res") else ({"mat": "pen_metal"} if k == "fire" else {})
                L[k].box(a0, a1, iy1 + 0.03, iy1 + 0.09, s, s + C["door_h"] - 0.005, sel=[name], **kw)
            L["mem"].point(name + "_axis", (0.0, iy1 + 0.06, s + 1.0))
            # Slide direction is an unverified assumption: skyspec.ELEVATOR_SLIDE_SIGN.
            L["mem"].point(name + "_axis", (sign * S.ELEVATOR_SLIDE_SIGN * (ed + 0.01), iy1 + 0.06, s + 1.0))
        # Panel (inside, east cab wall) and call button (outside, north face).
        for k in ("res0",):
            L[k].box(cx1 - 0.05, cx1, 3.4, 3.7, s + 1.0, s + 1.5, mat="metal", uv=UV_STEEL)
            L[k].box(0.85, 1.05, y1, y1 + 0.03, s + 1.1, s + 1.4, mat="metal", uv=UV_STEEL)
        m = L["mem"]
        m.point("elev_panel_l%d" % i, (cx1 - 0.1, 3.55, s + 1.25))
        m.point("elev_call_l%d" % i, (0.95, y1 + 0.15, s + 1.25))
        m.point("elev_cab_l%d" % i, (0.0, (ey0 + iy1) / 2, s + 0.05))
        m.point("light_cab_l%d" % i, (0.0, (ey0 + iy1) / 2, s + ch - 0.1))
    # Occluders: the four outer wall planes.
    for i, pts in enumerate([
        [(x0, y0, 0), (x0, y1, 0), (x0, y1, top), (x0, y0, top)],
        [(x1, y0, 0), (x1, y1, 0), (x1, y1, top), (x1, y0, top)],
    ]):
        L["view"].occluder(pts, "occluder_%03d" % (i + 1))
    building_props(L, 120000.0)
    return list(L.values())


def build_keycard():
    """85.6 x 54 x 2 mm card. hiddenSelection 'camo' carries the tier texture."""
    w, d, t = 0.0856, 0.054, 0.002
    r0, r1 = Lod("res0", LOD_RES, 0.0), Lod("res1", LOD_RES, 1.0)
    geo, fire, mem = Lod("geo", LOD_GEOMETRY), Lod("fire", LOD_FIREGEO), Lod("mem", LOD_MEMORY)
    x0, x1, y0, y1 = -w / 2, w / 2, -d / 2, d / 2
    for L in (r0, r1):
        L.box(x0, x1, y0, y1, 0.0, t, mat="keycard", uv=UVFit(x0, x1, y0, y1), sel=["camo"])
    geo.box(x0, x1, y0, y1, 0.0, t)
    geo.mass = 0.05
    fire.box(x0, x1, y0, y1, 0.0, t, mat="pen_metal")
    mem.point("ce_center", (0.0, 0.0, t / 2))
    mem.point("ce_radius", (w / 2, 0.0, t / 2))
    return [r0, r1, geo, fire, mem]


MODULES = {
    "lobby": (build_lobby, "sky_towera", S.P3D[S.CLASS_LOBBY]),
    "floor": (build_floor_office, "sky_towera", S.P3D[S.CLASS_FLOOR]),
    "roof": (build_roof_helipad, "sky_towera", S.P3D[S.CLASS_ROOF]),
    "core": (build_core, "sky_towera", S.P3D[S.CLASS_CORE]),
    "keycard": (build_keycard, "sky_items", "sky_keycard.p3d"),
}


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = argv[argv.index("--out") + 1]
    only = argv[argv.index("--only") + 1].split(",") if "--only" in argv else list(MODULES)
    stats = {}
    for key in only:
        fn, pbo, fname = MODULES[key]
        lods = fn()
        path = os.path.join(out, pbo, fname)
        stats[fname] = export_p3d(lods, MATS, path)
        print("EXPORTED", path, stats[fname])
    with open(os.path.join(out, "..", "assets", "build_stats.json"), "w") as fh:
        json.dump(stats, fh, indent=1, sort_keys=True)


if __name__ == "__main__":
    main()
