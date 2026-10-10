"""Generator for the SKY kit (street kit + props) - run headless in Blender 4.2.

    blender -b --factory-startup -P build_kit.py -- --out <mods/SKY_Skyline/addons> [--only StreetLight,Dumpster]

Same pipeline as build_towera.py (skygeo Lod -> Arma Toolbox MLOD). Every asset
is registered in skyspec.KIT (class, p3d, PBO, budget category). Builders return
Res0/Res1/Res2 + Geometry + Fire Geometry (+ View / Roadway / Memory where useful).
Requires ARMATOOLBOX_PATH.
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import detail as DT  # noqa: E402
import skyspec as S  # noqa: E402
from build_towera import MATS, UV_ALU, UV_CONC_PANEL, UV_CONC_REVEAL, UV_GLASS, UV_STEEL  # noqa: E402
from skygeo import (LOD_FIREGEO, LOD_GEOMETRY, LOD_MEMORY, LOD_RES, LOD_ROADWAY, LOD_SHADOW, LOD_VIEWGEO,  # noqa: E402
                    Lod, UVBand, UVRect, UVWorld, run_cli)

UV_ASPHALT = UVWorld(4.0)
UV_PAVER = UVWorld(3.0)
B_RUST = S.MATERIALS["rust"]["bands"]
UV_GREEN, UV_GREY, UV_RUST, UV_BURNT = (UVBand(B_RUST[k], 2.0) for k in ("green", "grey", "rust", "burnt"))
B_MARK = S.MATERIALS["roadmark"]["bands"]
ST = S.STREET


def h01_kit(*key):
    """Deterministic 0..1 hash (kit pieces, D73)."""
    import zlib
    return (zlib.crc32(repr(key).encode()) & 0xFFFFFF) / float(0x1000000)


def _bar(lod, p0, p1, r, mat=None, uv=None):
    """Square-section strut between two points (same as build_city.bar; build_city imports this module)."""
    d = [p1[i] - p0[i] for i in range(3)]
    ln = math.sqrt(sum(v * v for v in d)) or 1.0
    d = [v / ln for v in d]
    a = (0, 0, 1) if abs(d[2]) < 0.9 else (1, 0, 0)
    u = [d[1] * a[2] - d[2] * a[1], d[2] * a[0] - d[0] * a[2], d[0] * a[1] - d[1] * a[0]]
    un = math.sqrt(sum(v * v for v in u))
    u = [v / un * r for v in u]
    w = [d[1] * u[2] - d[2] * u[1], d[2] * u[0] - d[0] * u[2], d[0] * u[1] - d[1] * u[0]]
    ring = [(u[0] + w[0], u[1] + w[1], u[2] + w[2]), (u[0] - w[0], u[1] - w[1], u[2] - w[2]),
            (-u[0] - w[0], -u[1] - w[1], -u[2] - w[2]), (-u[0] + w[0], -u[1] + w[1], -u[2] + w[2])]
    verts = [tuple(p0[i] + c[i] for i in range(3)) for c in ring] + [tuple(p1[i] + c[i] for i in range(3)) for c in ring]
    lod.solid(verts, [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)], mat, uv)


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


def finish(L, mass, shadow=True, hull=False):
    # Same Geometry convention as Tower A (Test_Building sample) minus map=building:
    # props are not drawn as buildings on the in-game map (decision D5).
    L["geo"].props.update({"class": "house", "autocenter": "0"})
    L["geo"].mass = mass
    if shadow and hull and "shadow" not in L:
        # Hull shadow (perf batch-3 M3): one box around the static parts + one box per
        # door leaf (named selection) so the door shadow still swings with its bone.
        sh = Lod("shadow", LOD_SHADOW)
        geo = L["geo"]
        doors = {g: v for g, v in geo.groups.items() if not g.startswith("Component")}
        moving = set().union(*doors.values()) if doors else set()

        def bbox(idx):
            pts = [geo.verts[i] for i in idx]
            return [f(p[j] for p in pts) for j in range(3) for f in (min, max)]
        sh.box(*bbox([i for i in range(len(geo.verts)) if i not in moving]))
        for g, v in sorted(doors.items()):
            sh.box(*bbox(v), sel=[g])
        L["shadow"] = sh
    elif shadow and "shadow" not in L:
        # Shadow Volume = the closed convex collision solids (watertight by construction).
        sh = Lod("shadow", LOD_SHADOW)
        sh.verts = list(L["geo"].verts)
        sh.faces = [(idx, None, None) for idx, _m, _uv in L["geo"].faces]
        # keep named (door) selections so the shadow swings with the bone; drop ComponentNN
        sh.groups = {g: set(v) for g, v in L["geo"].groups.items() if not g.startswith("Component")}
        L["shadow"] = sh
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


MARK_Z = 0.015          # paint lift above asphalt (perf batch-1 M2: 6 mm z-fought at Res1)
MARK_PERIOD = {"solid": 2.0, "dashed": 3.0, "crosswalk": 1.0}   # metres per texture repeat


def line_quad(L, keys, x0, x1, y0, y1, band, along="y", repeat=None, z=MARK_Z):
    """Road paint strip: tiles `repeat` times along its length, V = paint band."""
    v0, v1 = 1.0 - B_MARK[band][1], 1.0 - B_MARK[band][0]
    if repeat is None:
        repeat = ((y1 - y0) if along == "y" else (x1 - x0)) / MARK_PERIOD[band]
    if along == "y":
        uv = UVRect(1, 0, (y0, x0), (y1, x1), (0.0, v0, repeat, v1))
    else:
        uv = UVRect(0, 1, (x0, y0), (x1, y1), (0.0, v0, repeat, v1))
    for k in keys:
        L[k].hquad(x0, x1, y0, y1, z, mat="roadmark", uv=uv)


# ------------------------------------------------------------------ roads (12 m grid)
def skirt(L, x0, x1, y0, y1):
    """Solid apron below the WHOLE tile down to -(slab + skirt): closes the void on sloped
    ground (security M1). Exactly one extra convex box per tile in Geometry/Fire."""
    zb = -ST["slab_t"] - ST["skirt"]
    for k in ("res0", "res1"):
        L[k].box(x0, x1, y0, y1, zb, -ST["slab_t"], mat="concrete", uv=UV_CONC_REVEAL, skip=("-z", "+z"))
    L["geo"].box(x0, x1, y0, y1, zb, -ST["slab_t"])
    L["fire"].box(x0, x1, y0, y1, zb, -ST["slab_t"], mat="pen_concrete")


def asphalt_boxes(L, rects, z0=-ST["slab_t"]):
    for (x0, x1, y0, y1) in rects:
        for k in ("res0", "res1"):
            L[k].box(x0, x1, y0, y1, z0, 0.0, mat="asphalt", uv=UV_ASPHALT, skip=("-z",))
        L["res2"].hquad(x0, x1, y0, y1, 0.0, mat="asphalt", uv=UV_ASPHALT)
        L["geo"].box(x0, x1, y0, y1, -S.ROAD_GEO_THICKNESS, 0.0)      # P8 (unverified)
        L["fire"].box(x0, x1, y0, y1, z0, 0.0, mat="pen_concrete")
        L["road"].hquad(x0, x1, y0, y1, 0.0, mat="road_asphalt", uv=UV_ASPHALT)


def build_road(crossing=False):
    L = props_lods(road=True)
    h = ST["tile"] / 2
    w = ST["carriageway"] / 2
    asphalt_boxes(L, [(-w, w, -h, h)])
    skirt(L, -w, w, -h, h)
    road_marks(L, w, h, crossing)
    return finish(L, 20000.0, shadow=False)


def road_marks(L, w, h, crossing):
    spans = [(-h, -1.5), (1.5, h)] if crossing else [(-h, h)]
    for (a, b) in spans:
        line_quad(L, ("res0", "res1"), -0.075, 0.075, a, b, "dashed")
        for x in (-w + 0.35, w - 0.5):                                         # clear of the 30 cm gutter
            line_quad(L, ("res0",), x, x + 0.15, a, b, "solid")
    if crossing:
        line_quad(L, ("res0", "res1"), -w, w, -1.5, 1.5, "crosswalk", along="x")


def build_street(crossing=False, worn=False):
    """Combined 12 x 12 m tile: road + both sidewalks in one entity (perf batch-1 M1).
    D75: kerb units and gutter strips (every tile); `worn` (Street_Straight_B) adds asphalt repairs, a
    sunken paver patch and a sealed trench, so streets alternate instead of repeating one tile."""
    L = props_lods(road=True)
    h = ST["tile"] / 2
    w = ST["carriageway"] / 2
    asphalt_boxes(L, [(-w, w, -h, h)])
    skirt(L, -h, h, -h, h)
    road_marks(L, w, h, crossing)
    sidewalk_slab(L, -h, -w, -h, h, curb_side="+x", band=False)               # kerb units replace the band (D75)
    sidewalk_slab(L, w, h, -h, h, curb_side="-x", band=False)
    kerb_and_gutter(L, w, h)
    if worn:
        street_wear(L, w, h)
    return finish(L, 36000.0, shadow=False)


def kerb_and_gutter(L, w, h):
    """D75: chamfered concrete kerb along both curbs (one open profile per side: road face, chamfer, top, back
    lip; no hidden bottom/end faces, joints come from the texture), a 30 cm concrete gutter strip at the foot of
    each kerb, a paver edge band at the building line. Res0/Res1 only; collision and Roadway unchanged (the kerb
    stands 2 cm proud of the sidewalk Roadway)."""
    top = ST["curb_h"]
    for sx in (-1, 1):
        xf = sx * w - sx * 0.001                                                 # road face, 1 mm proud of the slab wall
        xc, xb = sx * w + sx * 0.03, sx * w + sx * 0.16                          # chamfer top edge, back edge
        zf, zt = top - 0.03, top + 0.02
        faces = (([(xf, -h, 0.0), (xf, h, 0.0), (xf, h, zf), (xf, -h, zf)], (-sx, 0, 0)),
                 ([(xf, -h, zf), (xf, h, zf), (xc, h, zt), (xc, -h, zt)], (-sx * 0.86, 0, 0.5)),
                 ([(xc, -h, zt), (xc, h, zt), (xb, h, zt), (xb, -h, zt)], (0, 0, 1)),
                 ([(xb, -h, top), (xb, h, top), (xb, h, zt), (xb, -h, zt)], (sx, 0, 0)))
        for k in ("res0", "res1"):
            for pts, n in faces:
                L[k].quad(pts, n, mat="concrete", uv=UVWorld(2.0))
            g0, g1 = sorted((sx * w, sx * w - sx * 0.3))                         # gutter strip on the asphalt
            L[k].hquad(g0, g1, -h, h, 0.008 if k == "res0" else MARK_Z, mat="concrete", uv=UV_CONC_REVEAL)
        e0, e1 = sorted((sx * h, sx * (h - 0.12)))                               # paver edge band
        L["res0"].hquad(e0, e1, -h, h, top + 0.003, mat="concrete", uv=UV_CONC_REVEAL)


def street_wear(L, w, h):
    """D75 Street_Straight_B: two asphalt repairs (same asphalt, turned and offset so the seam shows) and a filled
    utility trench across one lane. Res0 only (6-7 mm lifts z-fight at Res1 distance); Roadway stays flat."""
    for (x0, x1, y0, y1, ang) in ((-3.2, -0.6, -4.5, -2.1, 0.5), (0.8, 2.9, 1.5, 4.8, 1.1)):
        L["res0"].hquad(x0, x1, y0, y1, 0.006, mat="asphalt",
                        uv=UVRect(0, 1, (x0, y0), (x1, y1), (ang, ang * 0.7, ang + (x1 - x0) / 4.0, ang * 0.7 + (y1 - y0) / 4.0)))
    L["res0"].hquad(0.1, w - 0.6, -0.35, 0.35, 0.007, mat="asphalt",               # sealed trench across the east lane
                    uv=UVRect(1, 0, (-0.35, 0.1), (0.35, w - 0.6), (0.3, 0.2, 0.48, 1.2)))



def build_street_intersection():
    L = props_lods(road=True)
    h = ST["tile"] / 2
    w = ST["carriageway"] / 2
    asphalt_boxes(L, [(-w, w, -h, h), (w, h, -w, w), (-h, -w, -w, w)])
    skirt(L, -h, h, -h, h)
    for (x0, x1, y0, y1) in ((-w, w, w, h), (-w, w, -h, -w)):
        line_quad(L, ("res0", "res1"), x0, x1, y0, y1, "crosswalk", along="x")
    for (x0, x1, y0, y1) in ((w, h, -w, w), (-h, -w, -w, w)):
        line_quad(L, ("res0", "res1"), x0, x1, y0, y1, "crosswalk", along="y")
    for sx in (-1, 1):
        for sy in (-1, 1):
            x0, x1 = sorted((sx * w, sx * h))
            y0, y1 = sorted((sy * w, sy * h))
            sidewalk_slab(L, x0, x1, y0, y1, curb_side="-x" if sx > 0 else "+x", curb2="-y" if sy > 0 else "+y")
    return finish(L, 40000.0, shadow=False)


def build_intersection(t_junction=False):
    L = props_lods(road=True)
    h = ST["tile"] / 2
    w = ST["carriageway"] / 2
    rects = [(-w, w, -h, h), (w, h, -w, w)]
    if not t_junction:
        rects.append((-h, -w, -w, w))
    asphalt_boxes(L, rects)
    skirt(L, -h, h, -h, h)
    # crosswalks on every road entry, inside the 2 m arm
    line_quad(L, ("res0", "res1"), -w, w, w, h, "crosswalk", along="x")
    line_quad(L, ("res0", "res1"), -w, w, -h, -w, "crosswalk", along="x")
    line_quad(L, ("res0",), w, h, -w, w, "crosswalk", along="y")       # Res1 reduction (perf L2)
    if not t_junction:
        line_quad(L, ("res0",), -h, -w, -w, w, "crosswalk", along="y")
    else:
        sidewalk_slab(L, -h, -w, -h, h, curb_side="+x")
    return finish(L, 30000.0, shadow=False)


def sidewalk_slab(L, x0, x1, y0, y1, curb_side="+x", curb2=None, band=True):
    top = ST["curb_h"]
    z0 = -ST["slab_t"]
    for k in ("res0", "res1"):
        L[k].box(x0, x1, y0, y1, z0, top, mat="concrete", uv=UV_CONC_REVEAL, skip=("-z", "+z"))
        L[k].hquad(x0, x1, y0, y1, top, mat="paver", uv=UV_PAVER)
    L["res2"].hquad(x0, x1, y0, y1, top, mat="paver", uv=UV_PAVER)
    L["geo"].box(x0, x1, y0, y1, z0, top)
    L["fire"].box(x0, x1, y0, y1, z0, top, mat="pen_concrete")
    L["road"].hquad(x0, x1, y0, y1, top, mat="road_ext", uv=UV_PAVER)
    for side in ([curb_side] if band else []) + ([curb2] if curb2 else []):     # curb stone band on the road side(s)
        if side == "+x":
            r = (x1 - 0.15, x1, y0, y1)
        elif side == "-x":
            r = (x0, x0 + 0.15, y0, y1)
        elif side == "+y":
            r = (x0, x1, y1 - 0.15, y1)
        else:
            r = (x0, x1, y0, y0 + 0.15)
        L["res0"].box(r[0], r[1], r[2], r[3], top - 0.001, top + 0.02, mat="concrete", uv=UVWorld(2.0), skip=("-z",))   # D75: world UVs (the trim band read black on top)


def build_sidewalk():
    L = props_lods(road=True)
    h = ST["tile"] / 2
    s = ST["sidewalk"] / 2
    skirt(L, -s, s, -h, h)
    sidewalk_slab(L, -s, s, -h, h, curb_side="+x")
    return finish(L, 8000.0, shadow=False)


def build_sidewalk_corner():
    L = props_lods(road=True)
    s = ST["sidewalk"] / 2
    skirt(L, -s, s, -s, s)
    sidewalk_slab(L, -s, s, -s, s, curb_side="+x", curb2="+y")
    return finish(L, 1500.0, shadow=False)


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
    """Flat decal on the road: Res LODs + Roadway, NO Geometry/Fire (no wheel snag, perf L5)."""
    import math
    uv = UVRect(0, 1, (-0.4, -0.4), (0.4, 0.4), S.atlas_uv("manhole"))
    lods = [Lod("res0", LOD_RES, 0.0), Lod("res1", LOD_RES, 1.0), Lod("res2", LOD_RES, 2.0), Lod("road", LOD_ROADWAY)]
    for L, n in zip(lods[:2], (12, 8)):
        ring = [(0.4 * math.cos(2 * math.pi * k / n), 0.4 * math.sin(2 * math.pi * k / n)) for k in range(n)]
        for k in range(n):        # fan of triangles at z = MARK_Z
            a, b = ring[k], ring[(k + 1) % n]
            L.quad([(0.0, 0.0, MARK_Z), (a[0], a[1], MARK_Z), (b[0], b[1], MARK_Z)], (0, 0, 1), "atlas", uv)
    lods[2].hquad(-0.4, 0.4, -0.4, 0.4, MARK_Z, mat="atlas", uv=uv)
    lods[3].hquad(-0.4, 0.4, -0.4, 0.4, MARK_Z, mat="road_asphalt", uv=UV_ASPHALT)
    return lods


# ------------------------------------------------------------------ street furniture
def build_streetlight():
    """8 m Soviet street light (D73 close-up pass): bolted base plinth, tapered octagonal pole in three
    sections with collars, service hatch, curved arm in three segments, cobra-head lamp housing with a
    cracked diffuser, a sagging feed cable. Same collision, Fire and light memory points as before."""
    L = props_lods(mem=True)
    for k, n in (("res0", 8), ("res1", 6)):                                      # tapered pole, 3 sections + collars
        for i, (z0, z1, r) in enumerate(((0.45, 3.0, 0.095), (3.0, 5.6, 0.08), (5.6, 8.0, 0.065))):
            L[k].prism(0.0, 0.0, r, z0, z1, n=n, mat="rust", uv=UV_GREY)
            if k == "res0" and i:
                L[k].prism(0.0, 0.0, r + 0.025, z0 - 0.04, z0 + 0.04, n=n, mat="rust", uv=UV_RUST)
    L["res2"].prism(0.0, 0.0, 0.08, 0.0, 8.0, n=4, mat="rust", uv=UV_GREY)
    for k in ("res0", "res1"):
        L[k].prism(0.0, 0.0, 0.16, 0.0, 0.45, n=8, mat="concrete", uv=UV_CONC_REVEAL)  # plinth
    for i in range(4):                                                           # anchor bolts
        a = math.pi / 4 + i * math.pi / 2
        L["res0"].prism(0.13 * math.cos(a), 0.13 * math.sin(a), 0.015, 0.45, 0.5, n=4, mat="rust", uv=UV_RUST)
    L["res0"].box(-0.06, 0.06, -0.1, -0.09, 1.0, 1.35, mat="rust", uv=UV_BURNT)    # service hatch
    arm = [(0.0, 7.6), (0.55, 7.92), (1.15, 7.98), (1.55, 7.9)]                    # curved arm (x, z)
    for k, r in (("res0", 0.035), ("res1", 0.035)):
        for (x0, z0), (x1, z1) in zip(arm, arm[1:]):
            _bar(L[k], (x0, 0.0, z0), (x1, 0.0, z1), r, "rust", UV_GREY)
    L["res2"].box(0.0, 1.8, -0.1, 0.1, 7.7, 7.88, mat="rust", uv=UV_GREY)
    head = [(1.2, 7.72), (1.85, 7.7), (1.9, 7.78), (1.75, 7.9), (1.3, 7.92)]       # cobra head profile (x, z)
    L["res0"].extrude_y(head, -0.17, 0.17, mat="rust", uv=UV_GREY)
    L["res1"].box(1.2, 1.85, -0.17, 0.17, 7.7, 7.85, mat="rust", uv=UV_GREY, skip=("-z",))
    for k in ("res0", "res1"):
        L[k].hquad(1.22, 1.78, -0.15, 0.15, 7.699, mat="lamp", uv=UVWorld(1.0), up=False)
    L["res0"].box(1.25, 1.8, -0.13, 0.13, 7.85, 7.9, mat="rust", uv=UV_RUST)       # domed cap
    L["res0"].box(1.45, 1.55, -0.155, 0.155, 7.69, 7.693, mat="rust", uv=UV_BURNT)    # crack 6 mm under the diffuser
    pts = [(0.08, -0.02, 7.5), (0.3, -0.05, 6.9), (0.12, -0.04, 6.2)]             # sagging feed cable
    for p0, p1 in zip(pts, pts[1:]):
        _bar(L["res0"], p0, p1, 0.01, "rust", UV_BURNT)
    L["geo"].prism(0.0, 0.0, 0.16, 0.0, 0.45, n=8)
    L["geo"].prism(0.0, 0.0, 0.08, 0.45, 8.0, n=6)
    L["fire"].prism(0.0, 0.0, 0.08, 0.0, 8.0, n=6, mat="pen_metal")
    L["fire"].box(1.2, 1.8, -0.17, 0.17, 7.7, 7.85, mat="pen_metal")
    L["mem"].point("light", (1.5, 0.0, 7.6))
    L["mem"].point("light_dir", (1.5, 0.0, 6.6))
    return finish(L, 250.0)


def build_trafficlight():
    """5.8 m traffic light (D74 close-up pass): flanged foot with bolts, collared pole, push-button box,
    braced arm with its cable, signal head with backplate and three visors (atlas face), pedestrian head
    with a visor. Collision unchanged (pole + head)."""
    L = props_lods()
    face = UVRect(0, 2, (4.62, 4.62), (4.93, 5.58), S.atlas_uv("traffic"))
    for k, n in (("res0", 8), ("res1", 6), ("res2", 4)):
        L[k].prism(0.0, 0.0, 0.1, 0.0, 5.8, n=n, mat="rust", uv=UV_GREY)
    L["res0"].prism(0.0, 0.0, 0.18, 0.0, 0.04, n=8, mat="rust", uv=UV_RUST)            # foot flange
    for i in range(4):
        a = math.pi / 4 + i * math.pi / 2
        L["res0"].box(0.14 * math.cos(a) - 0.015, 0.14 * math.cos(a) + 0.015, 0.14 * math.sin(a) - 0.015,
                      0.14 * math.sin(a) + 0.015, 0.04, 0.07, mat="rust", uv=UV_RUST)
    for zz in (1.2, 3.6):
        L["res0"].prism(0.0, 0.0, 0.12, zz, zz + 0.06, n=8, mat="rust", uv=UV_RUST)   # collars
    L["res0"].box(-0.08, 0.08, -0.16, -0.1, 1.0, 1.25, mat="rust", uv=UV_BURNT)         # push-button box
    for k in ("res0", "res1"):
        L[k].box(0.0, 5.0, -0.05, 0.05, 5.6, 5.75, mat="rust", uv=UV_GREY)
        L[k].box(4.6, 4.95, -0.17, 0.17, 4.6, 5.6, mat="rust", uv=UV_BURNT)
        L[k].quad([(4.62, -0.195, 4.62), (4.93, -0.195, 4.62), (4.93, -0.195, 5.58), (4.62, -0.195, 5.58)],
                  (0, -1, 0), "atlas", face)                                     # in front of the backplate (perf L)
    _bar(L["res0"], (0.05, 0.0, 4.9), (1.8, 0.0, 5.6), 0.03, "rust", UV_GREY)        # arm brace
    for k in ("res0", "res1"):
        L[k].box(4.5, 5.05, -0.19, -0.17, 4.5, 5.7, mat="rust", uv=UV_BURNT)            # backplate (thin, in front)
    _bar(L["res1"], (0.05, 0.0, 4.9), (1.8, 0.0, 5.6), 0.03, "rust", UV_GREY)           # Res1: brace too
    for zz in (4.92, 5.22, 5.52):                                                 # visors over the three lamps
        L["res0"].box(4.63, 4.92, -0.33, -0.19, zz - 0.02, zz, mat="rust", uv=UV_BURNT)
        L["res0"].box(4.63, 4.65, -0.33, -0.19, zz - 0.22, zz, mat="rust", uv=UV_BURNT)
        L["res0"].box(4.9, 4.92, -0.33, -0.19, zz - 0.22, zz, mat="rust", uv=UV_BURNT)
    cable = [(0.0, 0.06, 5.55), (2.5, 0.07, 5.45), (4.6, 0.06, 5.55)]                 # sagging cable under the arm
    for p0, p1 in zip(cable, cable[1:]):
        _bar(L["res0"], p0, p1, 0.008, "rust", UV_BURNT)
    L["res0"].box(-0.3, -0.1, -0.12, 0.12, 2.4, 3.0, mat="rust", uv=UV_BURNT)       # pedestrian head
    L["res0"].box(-0.32, -0.08, -0.16, -0.12, 2.98, 3.02, mat="rust", uv=UV_BURNT)    # its visor
    L["res1"].box(-0.3, -0.1, -0.12, 0.12, 2.4, 3.0, mat="rust", uv=UV_BURNT)
    L["res2"].box(0.0, 5.0, -0.1, 0.1, 5.5, 5.75, mat="rust", uv=UV_GREY)
    L["res2"].box(4.6, 4.95, -0.17, 0.17, 4.6, 5.6, mat="rust", uv=UV_BURNT)             # signal head stays (perf L)
    L["geo"].prism(0.0, 0.0, 0.1, 0.0, 5.8, n=6)
    L["fire"].prism(0.0, 0.0, 0.1, 0.0, 5.8, n=6, mat="pen_metal")
    L["fire"].box(4.6, 4.95, -0.17, 0.17, 4.6, 5.6, mat="pen_metal")
    return finish(L, 300.0)


JERSEY = [(-0.3, 0.0), (0.3, 0.0), (0.1, 0.3), (0.08, 0.8), (-0.08, 0.8), (-0.1, 0.3)]


def convex_profile(prof):
    """D91: convex hull of a 2D profile, counter-clockwise like the input - for Geometry / Fire / View extrusions
    (the engine needs convex components; the jersey knee is concave by a few cm)."""
    pts = sorted(set(prof))

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def build_barrier_concrete():
    """3 m jersey barrier (D73 close-up pass): chamfered ends, chipped edges with rebar showing, a lifting
    loop, faded red / white hazard stripes on the slope, drainage slots at the foot. Collision unchanged."""
    L = props_lods(view=True)
    L["res0"].extrude_y(JERSEY, -1.45, 1.45, mat="concrete", uv=UV_CONC_REVEAL)
    for s_ in (-1, 1):                                                           # chamfered ends (Res0 only)
        prof = [(x * 0.9, z) for x, z in JERSEY]
        L["res0"].extrude_y(prof, 1.45 if s_ > 0 else -1.5, 1.5 if s_ > 0 else -1.45, mat="concrete", uv=UV_CONC_REVEAL)
    L["res1"].extrude_y(JERSEY, -1.5, 1.5, mat="concrete", uv=UV_CONC_REVEAL)    # Res1: one extrusion (perf M)
    L["res2"].extrude_y([(-0.3, 0.0), (0.3, 0.0), (0.08, 0.8), (-0.08, 0.8)], -1.5, 1.5, mat="concrete", uv=UV_CONC_REVEAL)
    for i, y in enumerate((-0.9, -0.3, 0.3, 0.9)):                               # hazard stripes (both faces)
        band = "red" if i % 2 == 0 else "white"
        for sx in (-1, 1):
            q = [(sx * 0.101, y - 0.28, 0.32), (sx * 0.101, y + 0.28, 0.32), (sx * 0.081, y + 0.28, 0.78), (sx * 0.081, y - 0.28, 0.78)]
            for k in ("res0", "res1"):                                           # stripes stay in Res1 (no pop)
                L[k].quad(q if sx > 0 else q[::-1], (sx, 0, 0.1), "fair", UVBand(S.MATERIALS["fair"]["bands"][band], 1.0))
    for y in (-1.0, 0.0, 1.0):                                                    # drainage slots (dark)
        for sx in (-1, 1):
            q = [(sx * 0.301, y - 0.15, 0.02), (sx * 0.301, y + 0.15, 0.02), (sx * 0.29, y + 0.15, 0.1), (sx * 0.29, y - 0.15, 0.1)]
            L["res0"].quad(q if sx > 0 else q[::-1], (sx, 0, 0.3), "rust", UV_BURNT)
    L["res0"].box(-0.02, 0.02, -0.12, 0.12, 0.8, 0.86, mat="rust", uv=UV_RUST)      # lifting loop
    L["res0"].box(-0.02, 0.02, -0.12, -0.08, 0.76, 0.8, mat="rust", uv=UV_RUST)
    L["res0"].box(-0.02, 0.02, 0.08, 0.12, 0.76, 0.8, mat="rust", uv=UV_RUST)
    for i, (y, z) in enumerate(((1.42, 0.7), (-1.42, 0.2))):                     # chips + rebar stubs
        L["res0"].box(-0.06, 0.06, y - 0.05, y + 0.05, z, z + 0.08, mat="concrete", uv=UV_CONC_REVEAL)
        _bar(L["res0"], (0.0, y, z + 0.04),
              (0.03, y + (0.12 if y > 0 else -0.12), z + 0.1), 0.006, "rust", UV_RUST)
    hull = convex_profile(JERSEY)                                              # D91: Geometry must be convex
    L["geo"].extrude_y(hull, -1.5, 1.5)
    L["view"].extrude_y(hull, -1.5, 1.5)
    L["fire"].extrude_y(hull, -1.5, 1.5, mat="pen_concrete")
    return finish(L, 2000.0)


def build_barrier_steel():
    """2.4 m steel crowd-control barrier. D78 close-up: round-tube frame and 11 ladder bars, flat feet with
    rubber pads, hook and eye couplers. Collision unchanged (one slab, rails in Fire: bullets pass the bars)."""
    L = props_lods()
    vis = {"mat": "rust", "uv": UV_GREY}
    steel = {"mat": "metal", "uv": UV_STEEL}
    for k in ("res1",):
        for z0, z1 in ((0.15, 0.2), (1.05, 1.1)):
            L[k].box(-0.025, 0.025, -1.2, 1.2, z0, z1, **vis)
        for y in (-1.2, 1.15):
            L[k].box(-0.025, 0.025, y, y + 0.05, 0.05, 1.1, **vis)
            L[k].box(-0.35, 0.35, y, y + 0.05, 0.0, 0.05, **vis)
    r0 = L["res0"]
    oct8 = [(0.021 * math.cos(a), 0.021 * math.sin(a)) for a in (math.pi * (i + 0.5) / 4 for i in range(8))]
    for zc in (0.175, 1.075):                                                     # top and bottom rails (42 mm tube)
        r0.extrude_y([(x, zc + z) for x, z in oct8], -1.175, 1.175, **vis)
    for yc in (-1.175, 1.175):                                                    # end posts with bent shoulders
        r0.prism(0.0, yc, 0.021, 0.06, 1.05, n=8, **vis)
        _bar(r0, (0.0, yc, 1.05), (0.0, yc * 0.985, 1.075), 0.019, "rust", UV_GREY)
        r0.box(-0.35, 0.35, yc - 0.025, yc + 0.025, 0.012, 0.03, **steel)        # flat foot
        for x in (-0.31, 0.31):
            r0.box(x - 0.03, x + 0.03, yc - 0.03, yc + 0.03, 0.0, 0.012, skip=("-z",), mat="rust", uv=UV_BURNT)   # rubber pad
        _bar(r0, (0.0, yc, 0.03), (0.0, yc, 0.07), 0.03, "metal", UV_STEEL)        # foot socket
    for i in range(1, 12):                                                        # 16 mm ladder bars
        y = -1.2 + i * 0.2
        r0.prism(0.0, y, 0.011, 0.196, 1.054, n=4, rot=math.pi / 4, **vis)          # square: reads the same (perf D78 L)
    _bar(r0, (0.0, 1.196, 0.95), (0.0, 1.24, 0.95), 0.008, "metal", UV_STEEL)     # hook (+y) and eye (-y)
    _bar(r0, (0.0, 1.24, 0.95), (0.0, 1.24, 0.88), 0.008, "metal", UV_STEEL)
    _bar(r0, (0.0, -1.196, 0.93), (0.0, -1.235, 0.93), 0.008, "metal", UV_STEEL)
    _bar(r0, (0.0, -1.235, 0.9), (0.0, -1.235, 0.96), 0.008, "metal", UV_STEEL)
    L["res2"].box(-0.025, 0.025, -1.2, 1.2, 0.05, 1.1, **vis)
    L["geo"].box(-0.03, 0.03, -1.2, 1.2, 0.05, 1.1)
    for y in (-1.2, 1.15):
        L["geo"].box(-0.35, 0.35, y, y + 0.05, 0.0, 0.05)
    L["fire"].box(-0.025, 0.025, -1.2, 1.2, 1.05, 1.1, mat="pen_metal")
    L["fire"].box(-0.025, 0.025, -1.2, 1.2, 0.15, 0.2, mat="pen_metal")
    return finish(L, 60.0)


def build_dumpster():
    """1100 L wheeled waste container (D66 upgrade): body tapering to the base, rolled top lip, two lid
    halves (one thrown open over the back), side lifting trunnions, front push handles, four castors,
    a bag poking out (the rust sheet carries the wear)."""
    L = props_lods()
    L["shadow"] = Lod("shadow", LOD_SHADOW)
    body = [(-0.8, -0.45, 0.24), (0.8, -0.45, 0.24), (0.8, 0.45, 0.24), (-0.8, 0.45, 0.24),
            (-0.9, -0.55, 1.12), (0.9, -0.55, 1.12), (0.9, 0.55, 1.12), (-0.9, 0.55, 1.12)]
    faces = [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    for k in ("res0", "res1", "res2", "geo", "fire", "shadow"):
        kw = {"mat": "rust", "uv": UV_GREEN} if k.startswith("res") else ({"mat": "pen_metal"} if k == "fire" else {})
        L[k].solid(body, faces, **kw)
    L["res0"].box(-0.93, 0.93, -0.58, 0.58, 1.12, 1.17, mat="metal", uv=DT.UV_STEEL)                            # top lip
    L["res0"].box(-0.92, 0.0, -0.57, 0.57, 1.17, 1.21, mat="rust", uv=UV_GREEN)                                 # closed lid half
    L["res0"].solid([(0.0, 0.57, 1.17), (0.92, 0.57, 1.17), (0.0, 0.62, 1.2), (0.92, 0.62, 1.2),
                     (0.0, 0.84, 0.13 + 1.17 - 0.1), (0.92, 0.84, 0.13 + 1.17 - 0.1), (0.0, 0.9, 1.2 - 0.05), (0.92, 0.9, 1.2 - 0.05)],
                    faces, "rust", UV_GREEN)                                                                      # open lid (hangs back)
    L["res1"].box(-0.92, 0.92, -0.57, 0.57, 1.12, 1.2, mat="rust", uv=UV_GREEN)
    for sx in (-1, 1):                                                           # lifting trunnions
        L["res0"].extrude_x([(0.06 * math.cos(2 * math.pi * k / 8), 0.95 + 0.06 * math.sin(2 * math.pi * k / 8)) for k in range(8)],
                            *sorted((sx * 0.9, sx * 1.0)), mat="metal", uv=DT.UV_STEEL)
    for sx in (-0.45, 0.45):                                                     # push handles (front)
        L["res0"].box(sx - 0.15, sx + 0.15, -0.66, -0.62, 1.0, 1.04, mat="metal", uv=DT.UV_STEEL)
        for ex in (-0.15, 0.15):
            L["res0"].box(sx + ex - 0.015, sx + ex + 0.015, -0.66, -0.55, 0.98, 1.04, mat="metal", uv=DT.UV_STEEL)
    for (x, y) in ((-0.68, -0.34), (0.68, -0.34), (-0.68, 0.34), (0.68, 0.34)):  # castors: fork + wheel
        L["res0"].box(x - 0.05, x + 0.05, y - 0.05, y + 0.05, 0.16, 0.24, mat="metal", uv=DT.UV_STEEL)
        L["res0"].extrude_x([(y + 0.08 * math.cos(2 * math.pi * k / 10), 0.08 + 0.08 * math.sin(2 * math.pi * k / 10)) for k in range(10)],
                            x - 0.025, x + 0.025, mat="paint", uv=DT.paint_uv("slate"))
    L["res1"].box(-0.75, 0.75, -0.4, 0.4, 0.0, 0.24, mat="metal", uv=DT.UV_STEEL)
    L["res0"].prism(0.3, 0.1, 0.22, 1.12, 1.36, n=8, mat="trash", uv=UVWorld(S.MATERIALS["trash"]["sheet_m"]))  # bag
    L["geo"].box(-0.95, 0.95, -0.6, 0.6, 1.12, 1.22)
    L["fire"].box(-0.95, 0.95, -0.6, 0.6, 1.12, 1.22, mat="pen_metal")
    return finish(L, 400.0)


def build_planter():
    """1.5 m concrete street planter (D73 close-up pass): rolled rim, chamfered foot, a crack, soil with a
    dead shrub (trunk, forked branches, a few leaf cards) gone to weeds, a cigarette-butt litter of chips."""
    L = props_lods()
    uv_soil = UVBand(S.MATERIALS["concrete"]["bands"]["board"], 1.4)
    for k in ("res0", "res1", "res2"):
        L[k].box(-0.75, 0.75, -0.75, 0.75, 0.0, 0.6, mat="concrete", uv=UV_CONC_REVEAL, skip=("-z", "+z"))
        L[k].hquad(-0.7, 0.7, -0.7, 0.7, 0.55, mat="concrete", uv=uv_soil)
    for k in ("res0", "res1"):                                                   # rolled rim + chamfered foot
        for (a0, a1, b0, b1) in ((-0.8, 0.8, -0.8, -0.68), (-0.8, 0.8, 0.68, 0.8), (-0.8, -0.68, -0.68, 0.68), (0.68, 0.8, -0.68, 0.68)):
            L[k].box(a0, a1, b0, b1, 0.6, 0.66, mat="concrete", uv=UV_CONC_REVEAL)
    for (a0, a1, b0, b1) in ((-0.79, 0.79, -0.79, -0.75), (-0.79, 0.79, 0.75, 0.79), (-0.79, -0.75, -0.75, 0.75), (0.75, 0.79, -0.75, 0.75)):
        L["res0"].box(a0, a1, b0, b1, 0.0, 0.08, mat="concrete", uv=UV_CONC_REVEAL)
    L["res0"].quad([(0.2, -0.752, 0.1), (0.24, -0.752, 0.1), (0.36, -0.752, 0.58), (0.32, -0.752, 0.58)], (0, -1, 0),
                   "concrete", uv_soil)                                          # crack (dark board band: no extra section)
    trunk = [(0.05, 0.0, 0.55), (0.02, 0.03, 0.95), (-0.05, 0.02, 1.3)]           # dead shrub
    for p0, p1 in zip(trunk, trunk[1:]):
        _bar(L["res0"], p0, p1, 0.03, "wood", DT.UV_OAK)
        _bar(L["res1"], p0, p1, 0.03, "wood", DT.UV_OAK)
    for i, (dx, dy, dz) in enumerate(((0.35, 0.1, 0.35), (-0.3, 0.25, 0.4), (0.1, -0.35, 0.3), (-0.2, -0.2, 0.45))):
        base = trunk[1] if i % 2 else trunk[2]
        _bar(L["res0"], base, (base[0] + dx, base[1] + dy, base[2] + dz), 0.012, "wood", DT.UV_OAK)
    for k in ("res0", "res1"):                                                   # what is left of the leaves
        for axis in ("x", "y"):
            if axis == "x":
                q = [(-0.55, 0.0, 0.9), (0.55, 0.0, 0.9), (0.55, 0.0, 1.65), (-0.55, 0.0, 1.65)]
                uv, fac = UVRect(0, 2, (-0.55, 0.9), (0.55, 1.65)), (0, -1, 0)
            else:
                q = [(0.0, -0.55, 0.9), (0.0, 0.55, 0.9), (0.0, 0.55, 1.65), (0.0, -0.55, 1.65)]
                uv, fac = UVRect(1, 2, (-0.55, 0.9), (0.55, 1.65)), (1, 0, 0)
            L[k].quad(q, fac, "foliage", uv, double=True)
    L["res2"].quad([(-0.55, 0.0, 0.9), (0.55, 0.0, 0.9), (0.55, 0.0, 1.65), (-0.55, 0.0, 1.65)], (0, -1, 0), "foliage",
                   UVRect(0, 2, (-0.55, 0.9), (0.55, 1.65)), double=True)        # same card as Res1, both sides (sec M)
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


def _sec(y, w, z0, z1, n=16, p=5.0):
    """Rounded-rectangle (superellipse) cross-section at station y: half width w, from z0 to z1."""
    zc, hz = (z0 + z1) / 2, (z1 - z0) / 2
    out = []
    for k in range(n):
        t = 2 * math.pi * k / n
        c, s_ = math.cos(t), math.sin(t)
        out.append((w * math.copysign(abs(c) ** (2 / p), c), y, zc + hz * math.copysign(abs(s_) ** (2 / p), s_)))
    return out


def tyre(L, keys, x, y, r=0.3, zc=0.28, width=0.2, flat=0.04, n=16):
    """D96: round tyre (smooth), sagging flat at the bottom, steel rim and hub cap inside it."""
    sx = 1 if x > 0 else -1
    prof = [(y + r * math.cos(2 * math.pi * i / n), max(zc - r + flat, zc + r * math.sin(2 * math.pi * i / n)))
            for i in range(n)]
    for k in keys:
        nn = n if k == "res0" else 8
        pr = prof if nn == n else [(y + r * math.cos(2 * math.pi * i / nn), zc + r * math.sin(2 * math.pi * i / nn)) for i in range(nn)]
        L[k].extrude_x(pr, x, x + sx * width, mat="rust", uv=UV_BURNT)
    rim = [(y + 0.62 * r * math.cos(2 * math.pi * i / 12), zc + 0.62 * r * math.sin(2 * math.pi * i / 12)) for i in range(12)]
    x1 = x + sx * (width + 0.006)
    L["res0"].extrude_x(rim, min(x1, x1 - sx * 0.03), max(x1, x1 - sx * 0.03), mat="rust", uv=UV_GREY)


def saloon_body(lod, pm, paint, n=16, glass=True):
    """D96: lofted Soviet-saloon body (original shape): rounded lower body following bonnet / waist / boot lines and
    a glasshouse with tumblehome; window bands are faces of the shell (glassfar, opaque: no see-through, sec M), so
    nothing floats on a curved panel. Smoothed by the writer."""
    st = [(-2.10, 0.80, 0.32, 0.66), (-2.06, 0.86, 0.28, 0.75), (-1.92, 0.89, 0.26, 0.80), (-1.02, 0.90, 0.25, 0.84),
          (1.15, 0.90, 0.25, 0.86), (1.96, 0.89, 0.27, 0.82), (2.06, 0.86, 0.30, 0.78), (2.10, 0.80, 0.34, 0.70)]
    lod.loft([_sec(y, w, z0, z1, n) for y, w, z0, z1 in st], mat=pm, uv=paint)

    def gh(y, zb, zt):
        # full section is 0.55 m tall; the thin end rings are the same shape scaled down (no folded faces)
        f = (zt - zb) / 0.55
        pts = [(0.80, 0.0), (0.80, 0.04), (0.75, 0.46), (0.63, 0.55), (-0.63, 0.55), (-0.75, 0.46), (-0.80, 0.04),
               (-0.80, 0.0)]
        return [(x, y, zb + z * f) for x, z in pts]
    rings = [gh(-1.00, 0.83, 0.87), gh(-0.60, 0.83, 1.38), gh(0.64, 0.83, 1.38), gh(1.00, 0.83, 0.87)]
    g = "glassfar"
    mats = {}
    if glass:
        mats = {(0, 2): g, (0, 3): g, (0, 4): g, (1, 1): g, (1, 5): g, (2, 2): g, (2, 3): g, (2, 4): g}
    lod.loft(rings, mat=pm, uv=paint, mats=mats)


def build_wreck_sedan(variant="A"):
    """Rusted Soviet saloon hulk (D73 close-up pass, original shape; D96 lofted body): rounded body following the
    bonnet, waist and boot lines, glasshouse with tumblehome and sooted glass, chipped paint over rust, chrome
    bumpers, head and tail lamps, flat tyres on steel rims, the bonnet sprung open. Collision unchanged (body + cabin)."""
    if variant == "C":
        return build_wreck_sedan_overturned()
    L = props_lods(view=True)
    col = ("beige", "slate", "terracotta", "white", "green")[int(h01_kit("sedan", "col") * 5)]
    pm, paint = "rust", UVBand(B_RUST[col], 2.0)
    if variant == "B":                                                           # D74: burnt out - scorched shell
        paint = UV_BURNT
    saloon_body(L["res0"], pm, paint)
    saloon_body(L["res1"], pm, paint, n=8)
    cab = [(-1.0, 0.86), (1.0, 0.86), (0.65, 1.38), (-0.6, 1.38)]                      # (y, z)
    L["res0"].box(-0.84, 0.84, -2.0, -1.06, 0.62, 0.79, mat="rust", uv=UV_BURNT)       # gutted engine bay (bonnet up)
    L["res0"].box(-0.3, 0.3, -1.8, -1.25, 0.72, 0.85, mat="rust", uv=UV_RUST)            # what is left of the engine
    L["res2"].box(-0.9, 0.9, -2.1, 2.1, 0.0, 0.85, mat="rust", uv=paint)
    L["res2"].extrude_x(cab, -0.8, 0.8, mat="rust", uv=paint)
    for sx in (-1, 1):                                                             # D96: dark sill skirt down to the ground
        x = sx * 0.9                                                               # (the collision box reaches the ground
        q = [(x, -2.0, 0.03), (x, 2.0, 0.03), (x, 2.0, 0.27), (x, -2.0, 0.27)]     #  under the body: no crawl space, sec)
        L["res0"].quad(q if sx > 0 else q[::-1], (sx, 0, 0), "rust", UV_BURNT)
    for y_ in (-2.08, 2.08):
        q = [(-0.88, y_, 0.03), (0.88, y_, 0.03), (0.88, y_, 0.3), (-0.88, y_, 0.3)]
        L["res0"].quad(q, (0, 1 if y_ > 0 else -1, 0), "rust", UV_BURNT)
    for sx in (-1, 1):                                                             # dark wheel arches on the flanks
        x = sx * 0.904
        for yw in (-1.3, 1.35):
            pts = [(x, yw + 0.4 * math.cos(math.pi * i / 8), 0.26 + 0.4 * math.sin(math.pi * i / 8)) for i in range(9)]
            for i in range(8):
                tri = [(x, yw, 0.26), pts[i], pts[i + 1]]
                L["res0"].quad(tri if sx > 0 else tri[::-1], (sx, 0, 0), "rust", UV_BURNT)
    bump = [(0.0, 0.30), (0.05, 0.31), (0.07, 0.36), (0.05, 0.41), (0.0, 0.42)]
    for y, s_ in ((-2.1, -1), (2.1, 1)):                                               # chrome bumpers + lamps
        L["res0"].extrude_x([(y + s_ * a, b) for a, b in bump] + [(y - s_ * 0.02, 0.42), (y - s_ * 0.02, 0.30)],
                            -0.93, 0.93, mat="metal", uv=UV_STEEL)
        for sx in (-1, 1):
            r_ = 0.075
            yy = y - 0.01 if s_ < 0 else y + 0.0
            prof = [(sx * 0.62 + r_ * math.cos(2 * math.pi * i / 12), 0.62 + r_ * math.sin(2 * math.pi * i / 12)) for i in range(12)]
            L["res0"].extrude_y([(a, b) for a, b in prof], min(yy, yy + s_ * 0.025), max(yy, yy + s_ * 0.025),
                                mat="glassfar" if s_ < 0 else "paint", uv=UV_GLASS if s_ < 0 else DT.paint_uv("terracotta"))
    L["res0"].solid([(-0.86, -1.02, 0.86), (0.86, -1.02, 0.86), (0.86, -1.04, 0.9), (-0.86, -1.04, 0.9),
                     (-0.86, -1.9, 1.15), (0.86, -1.9, 1.15), (0.86, -1.92, 1.19), (-0.86, -1.92, 1.19)],
                    [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (2, 3, 7, 6), (0, 3, 7, 4), (1, 2, 6, 5)], pm, paint)   # sprung bonnet
    for x in (0.72, -0.72):
        for y in (-1.3, 1.35):
            tyre(L, ("res0", "res1"), x, y, r=0.3, zc=0.28)
    cab_geo = [(-1.1, 0.85), (1.0, 0.85), (0.6, 1.4), (-0.7, 1.4)]                  # collision: one closed hull (sec H)
    for k in ("geo", "fire", "view"):
        kw = {"mat": "pen_metal"} if k == "fire" else {}
        L[k].box(-0.9, 0.9, -2.1, 2.1, 0.0, 0.85, **kw)
        L[k].extrude_x(cab_geo, -0.8, 0.8, **kw)
    return finish(L, 1100.0)


def build_wreck_sedan_overturned():
    """D74 Wreck_Sedan_C: the saloon on its crushed roof - flattened cabin on the ground, the body above it
    showing the rusted underside, wheels in the air. New collision: crushed cabin (0..0.55) + body
    (0.55..1.2) stacked without a gap (test_kit hull test)."""
    L = props_lods(view=True)
    paint = DT.paint_uv("white")
    cab_c = [(-1.1, 0.55), (1.0, 0.55), (0.55, 0.0), (-0.65, 0.0)]                      # (y, z), roof on the ground
    for k in ("res0", "res1"):
        L[k].box(-0.9, 0.9, -2.1, 2.1, 0.55, 1.2, mat="paint", uv=paint)
        L[k].extrude_x(cab_c, -0.78, 0.78, mat="paint", uv=paint)
    L["res2"].box(-0.9, 0.9, -2.1, 2.1, 0.0, 1.2, mat="paint", uv=paint)
    L["res0"].hquad(-0.85, 0.85, -2.05, 2.05, 1.201, mat="rust", uv=UV_BURNT)          # rusted underside
    for x0, x1 in ((-0.55, -0.45), (0.45, 0.55)):                                   # chassis rails
        L["res0"].box(x0, x1, -2.0, 2.0, 1.2, 1.3, mat="rust", uv=UV_RUST)
    L["res0"].box(-0.12, 0.12, -1.9, 1.9, 1.2, 1.26, mat="rust", uv=UV_RUST)           # exhaust / tunnel
    for sx in (-1, 1):                                                             # crushed side windows
        x = sx * 0.781
        q = [(x, -0.9, 0.05), (x, 0.85, 0.05), (x, 0.95, 0.5), (x, -1.0, 0.5)]
        L["res0"].quad(q if sx > 0 else q[::-1], (sx, 0, 0), "glassfar", UV_GLASS)
    for y, s_ in ((-2.1, -1), (2.1, 1)):                                             # bumpers (upside down)
        L["res0"].box(-0.92, 0.92, min(y, y + s_ * 0.06), max(y, y + s_ * 0.06), 0.98, 1.1, mat="metal", uv=UV_STEEL)
    prof = [(0.3 * math.cos(2 * math.pi * i / 8), 1.5 + 0.3 * math.sin(2 * math.pi * i / 8)) for i in range(8)]
    for x in (0.75, -0.75):                                                        # wheels in the air
        for y in (-1.3, 1.35):
            for k, n in (("res0", 8), ("res1", 5)):
                pr = prof if n == 8 else [(0.3 * math.cos(2 * math.pi * i / 5), 1.5 + 0.3 * math.sin(2 * math.pi * i / 5)) for i in range(5)]
                L[k].extrude_x([(y + a, b) for a, b in pr], x, x + (0.2 if x > 0 else -0.2), mat="rust", uv=UV_BURNT)
    for k in ("geo", "fire", "view"):                                           # closed block: no lying-in space under
        kw = {"mat": "pen_metal"} if k == "fire" else {}                        # the overhangs (security D74 M)
        L[k].box(-0.9, 0.9, -2.1, 2.1, 0.0, 1.2, **kw)
        for x in (0.75, -0.75):                                                 # upturned wheels stop bullets too (sec L)
            for y in (-1.3, 1.35):
                xa, xb = sorted((x, x + (0.2 if x > 0 else -0.2)))
                L[k].box(xa, xb, y - 0.3, y + 0.3, 1.2, 1.8, **kw)
    return finish(L, 1100.0)


def build_wreck_van():
    """Burnt-out box van hulk (D74 close-up pass, original shape): cab with an empty windscreen frame and
    side windows, ribbed cargo box, one rear door hanging open, bumpers, lamps, scorched paint, flat tyres.
    Collision unchanged (chassis + box + cab)."""
    L = props_lods(view=True)
    cab = [(1.0, 0.9), (2.6, 0.9), (2.6, 1.5), (2.0, 2.1), (1.0, 2.1)]
    for k in ("res0", "res1"):
        L[k].box(-1.0, 1.0, -2.6, 2.6, 0.3, 0.9, mat="rust", uv=UV_BURNT)
        L[k].box(-1.05, 1.05, -2.6, 1.0, 0.9, 2.6, mat="rust", uv=UV_BURNT)
    # D96: lofted cab (rounded bonnet, raked windscreen, cab roof curving into the box), smoothed by the writer
    secs = [(1.0, 0.99, 0.88, 2.12), (1.95, 0.99, 0.88, 2.1), (2.3, 0.98, 0.88, 1.82), (2.55, 0.94, 0.9, 1.57),
            (2.62, 0.86, 0.95, 1.5)]                                            # follows the cab collision (sec L3)
    n = 16
    glass = {(1, k): "glassfar" for k in (3, 4, 5)}                                # windscreen band (sooted, opaque)
    L["res0"].loft([_sec(y, w, z0, z1, n) for y, w, z0, z1 in secs], mat="rust", uv=UV_RUST, mats=glass)
    L["res1"].loft([_sec(y, w, z0, z1, 8) for y, w, z0, z1 in secs], mat="rust", uv=UV_RUST)
    L["res2"].box(-1.0, 1.0, -2.6, 2.6, 0.0, 0.9, mat="rust", uv=UV_BURNT)
    L["res2"].box(-1.05, 1.05, -2.6, 1.0, 0.9, 2.6, mat="rust", uv=UV_BURNT)
    L["res2"].extrude_x(cab, -1.0, 1.0, mat="rust", uv=UV_RUST)
    for i in range(7):                                                           # ribs on the cargo box
        y = -2.4 + i * 0.55
        for sx in (-1, 1):
            L["res0"].box(sx * 1.05 - (0.03 if sx < 0 else 0), sx * 1.05 + (0.03 if sx > 0 else 0), y - 0.04, y + 0.04,
                          0.95, 2.55, mat="rust", uv=UV_RUST)
    for sx in (-1, 1):                                                           # cab side windows (on the flat cab side)
        x = sx * 0.995
        q = [(x, 1.15, 1.55), (x, 1.8, 1.55), (x, 1.8, 2.0), (x, 1.15, 2.0)]
        L["res0"].quad(q if sx > 0 else q[::-1], (sx, 0, 0), "glassfar", UV_GLASS)
    L["res0"].box(-1.05, 1.05, 2.6, 2.68, 0.35, 0.5, mat="metal", uv=UV_STEEL)        # bumpers
    L["res0"].box(-1.05, 1.05, -2.68, -2.6, 0.35, 0.5, mat="metal", uv=UV_STEEL)
    for sx in (-1, 1):                                                           # lamps
        L["res0"].box(sx * 0.75 - 0.12, sx * 0.75 + 0.12, 2.6, 2.62, 0.7, 0.85, mat="glassfar", uv=UV_GLASS)
    L["res0"].quad([(-1.0, -2.61, 1.0), (0.0, -2.61, 1.0), (0.0, -2.61, 2.5), (-1.0, -2.61, 2.5)], (0, -1, 0),
                   "rust", UV_BURNT)                                              # closed rear door
    L["res0"].quad([(0.0, -2.62, 1.0), (0.3, -3.55, 1.0), (0.3, -3.55, 2.5), (0.0, -2.62, 2.5)], (0.95, -0.3, 0),
                   "rust", UV_BURNT, double=True)                                 # the other hanging open
    door = [(0.0, -2.6, 1.0), (0.3, -3.55, 1.0), (0.3, -3.55, 2.5), (0.0, -2.6, 2.5)]   # ...and solid (security D74 M)
    slab = [(x + 0.012, y + 0.004, z) for x, y, z in door] + [(x - 0.012, y - 0.004, z) for x, y, z in door]
    for k in ("geo", "fire", "view"):
        L[k].solid(slab, [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)],
                   **({"mat": "pen_metal"} if k == "fire" else {}))
    for x in (0.85, -0.85):
        for y in (-1.8, 1.7):
            tyre(L, ("res0", "res1"), x, y, r=0.35, zc=0.33)
    for k in ("geo", "fire", "view"):
        kw = {"mat": "pen_metal"} if k == "fire" else {}
        L[k].box(-1.0, 1.0, -2.6, 2.6, 0.0, 0.9, **kw)
        L[k].box(-1.05, 1.05, -2.6, 1.0, 0.9, 2.6, **kw)
        if k != "view":
            L[k].extrude_x(cab, -1.0, 1.0, **kw)
    return finish(L, 2500.0)


def build_billboard():
    """6 x 3 m billboard (D74 close-up pass): I-beam posts with a ladder, a trussed back frame, a service
    walkway with a railing, two lamp arms over the top, a framed poster (camo, variants) with one corner peeled
    back. Collision unchanged (two posts + the panel)."""
    L = props_lods(view=True)
    poster = UVRect(0, 2, (-3.0, 4.0), (3.0, 7.0))
    for x in (-2.1, 1.9):                                                        # I-beam posts (Res0), boxes (Res1)
        L["res0"].box(x, x + 0.2, -0.1, -0.08, 0.0, 4.0, mat="rust", uv=UV_GREY)
        L["res0"].box(x, x + 0.2, 0.08, 0.1, 0.0, 4.0, mat="rust", uv=UV_GREY)
        L["res0"].box(x + 0.09, x + 0.11, -0.08, 0.08, 0.0, 4.0, mat="rust", uv=UV_GREY)
        L["res0"].box(x - 0.1, x + 0.3, -0.2, 0.2, 0.0, 0.05, mat="rust", uv=UV_RUST)       # base plate
        L["res1"].box(x, x + 0.2, -0.1, 0.1, 0.0, 4.0, mat="rust", uv=UV_GREY)
        L["res2"].quad([(x, 0.0, 0.0), (x + 0.2, 0.0, 0.0), (x + 0.2, 0.0, 4.0), (x, 0.0, 4.0)], (0, -1, 0), "rust", UV_GREY, double=True)
    for x in (-2.35, -2.15):                                                     # ladder on the left post
        _bar(L["res0"], (x, 0.15, 0.3), (x, 0.15, 3.9), 0.015, "rust", UV_RUST)
    for i in range(12):
        _bar(L["res0"], (-2.35, 0.15, 0.4 + i * 0.3), (-2.15, 0.15, 0.4 + i * 0.3), 0.01, "rust", UV_RUST)
    for k in ("res0", "res1"):
        L[k].box(-3.0, 3.0, -0.1, 0.1, 4.0, 7.0, mat="rust", uv=UV_GREY)
    L["res2"].box(-3.0, 3.0, -0.1, 0.1, 4.0, 7.0, mat="rust", uv=UV_GREY, skip=("-y",))
    L["res2"].box(-3.0, 3.0, -0.75, -0.1, 3.88, 3.92, mat="rust", uv=UV_RUST)           # walkway keeps its silhouette (perf L)
    for zz in (4.4, 5.5, 6.6):                                                   # back frame rails + braces
        L["res0"].box(-3.0, 3.0, 0.1, 0.16, zz, zz + 0.08, mat="rust", uv=UV_GREY)
    for x0, x1 in ((-2.9, -1.0), (-1.0, 1.0), (1.0, 2.9)):
        _bar(L["res0"], (x0, 0.14, 4.45), (x1, 0.14, 6.65), 0.025, "rust", UV_RUST)
    for k in ("res0", "res1"):                                                   # walkway grating + top rail (Res1 too)
        L[k].box(-3.0, 3.0, -0.75, -0.1, 3.88, 3.92, mat="rust", uv=UV_RUST)
        L[k].box(-3.0, 3.0, -0.75, -0.71, 4.86, 4.9, mat="rust", uv=UV_GREY)
    for i in range(7):                                                           # railing posts + top rail
        x = -2.95 + i * 0.98
        L["res0"].box(x - 0.02, x + 0.02, -0.75, -0.71, 3.92, 4.9, mat="rust", uv=UV_GREY)
    for x in (-1.8, 1.8):                                                        # lamp arms + heads
        _bar(L["res0"], (x, 0.1, 7.0), (x, -0.9, 7.35), 0.025, "rust", UV_GREY)
        for k in ("res0", "res1"):
            L[k].box(x - 0.2, x + 0.2, -1.1, -0.8, 7.28, 7.42, mat="rust", uv=UV_BURNT)
    for k in ("res0", "res1"):                                                   # poster frame
        for (a0, a1, b0, b1) in ((-3.05, 3.05, 3.95, 4.05), (-3.05, 3.05, 6.95, 7.05), (-3.05, -2.95, 4.0, 7.0), (2.95, 3.05, 4.0, 7.0)):
            L[k].box(a0, a1, -0.14, -0.1, b0, b1, mat="rust", uv=UV_GREY)
    peel = [(2.95, -0.101, 6.3), (2.95, -0.101, 6.95), (2.2, -0.101, 6.95)]          # peeled corner: bare panel + flap
    for k in ("res0", "res1", "res2"):
        L[k].quad([(-2.95, -0.101, 4.05), (2.95, -0.101, 4.05), (2.95, -0.101, 6.3), (-2.95, -0.101, 6.3)],
                  (0, -1, 0), "billboard", poster, sel=["camo"])
        L[k].quad([(-2.95, -0.101, 6.3), (2.95, -0.101, 6.3), (2.2, -0.101, 6.95), (-2.95, -0.101, 6.95)],
                  (0, -1, 0), "billboard", poster, sel=["camo"])
    L["res0"].quad([peel[0], peel[1], peel[2], (2.6, -0.101, 6.6)], (0, -1, 0), "rust", UV_RUST)          # bare corner
    L["res0"].quad([(2.2, -0.101, 6.95), (2.95, -0.101, 6.3), (2.85, -0.45, 6.1), (2.05, -0.4, 6.7)], (0.5, -0.8, 0.2),
                   "billboard", poster, sel=["camo"], double=True)                # the flap curling forward
    for k in ("geo", "fire"):
        kw = {"mat": "pen_metal"} if k == "fire" else {}
        for x in (-2.1, 1.9):
            L[k].box(x, x + 0.2, -0.1, 0.1, 0.0, 4.0, **kw)
        L[k].box(-3.0, 3.0, -0.1, 0.1, 4.0, 7.0, **kw)
    L["view"].box(-3.0, 3.0, -0.1, 0.1, 4.0, 7.0)
    return finish(L, 1500.0)


def build_decal(mat, w, h, camo=False):
    """Render-only quad facing -Y (offset from the wall: skyspec.DECAL_OFFSET); no collision LODs."""
    uv = UVRect(0, 2, (-w / 2, 0.0), (w / 2, h))
    lods = [Lod("res0", LOD_RES, 0.0), Lod("res1", LOD_RES, 1.0), Lod("res2", LOD_RES, 2.0)]
    for L in lods:
        L.quad([(-w / 2, 0.0, 0.0), (w / 2, 0.0, 0.0), (w / 2, 0.0, h), (-w / 2, 0.0, h)], (0, -1, 0), mat, uv,
               sel=["camo"] if camo else ())
    return lods


BUILDERS = {
    "Road_Straight": build_road, "Road_Crossing": lambda: build_road(crossing=True),
    "Street_Straight": build_street, "Street_Crossing": lambda: build_street(crossing=True),
    "Street_Straight_B": lambda: build_street(worn=True),
    "Street_Intersection": build_street_intersection,
    "Intersection_4Way": build_intersection, "Intersection_T": lambda: build_intersection(t_junction=True),
    "Sidewalk": build_sidewalk, "Sidewalk_Corner": build_sidewalk_corner, "Curb": build_curb, "Manhole": build_manhole,
    "StreetLight": build_streetlight, "TrafficLight": build_trafficlight,
    "Barrier_Concrete": build_barrier_concrete, "Barrier_Steel": build_barrier_steel,
    "Dumpster": build_dumpster, "Planter": build_planter, "Wreck_Sedan": build_wreck_sedan, "Wreck_Sedan_B": lambda: build_wreck_sedan("B"),
    "Wreck_Sedan_C": lambda: build_wreck_sedan("C"),
    "Wreck_Van": build_wreck_van, "Billboard": build_billboard,
    "Decal_Dirt": lambda: build_decal("decal_dirt", *S.DECAL_SIZE["Decal_Dirt"]),
    "Decal_Cracks": lambda: build_decal("decal_cracks", *S.DECAL_SIZE["Decal_Cracks"]),
    "Decal_Graffiti": lambda: build_decal("decal_graffiti", *S.DECAL_SIZE["Decal_Graffiti"], camo=True),
}

KIT_MATS = dict(MATS)
KIT_MATS["road_asphalt"] = {"co": S.ROADWAY_ASPHALT, "rvmat": ""}


def modules():
    """{name: (builder, pbo, p3d)} for every KIT entry that has a builder here."""
    return {n: (BUILDERS[n], e["pbo"], e["p3d"]) for n, e in S.KIT.items() if n in BUILDERS}


if __name__ == "__main__":
    run_cli(modules(), KIT_MATS, "build_stats_kit.json")
