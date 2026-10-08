"""D67 street props: bus stop, Morris advertising column, Soviet phone booth - plain Python or any Blender.

    python build_streetprops.py -- --out <mods/SKY_Skyline/addons> [--only BusStop,AdColumn,PhoneBooth]

Placed by sky_layout `streets.furniture` (bus_stops_every / ads_every / phones_every) on the -X sidewalk,
open side towards the carriageway. Frame: front (open side) = -Y, origin = centre at sidewalk level.
Same LOD conventions as build_landmarks (Res0 detail, Res1 forms, Res2/Res3 silhouette, simple collision).
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
from skygeo import UVBand, UVRect, run_cli  # noqa: E402

kw_for, h01 = C.kw_for, C.h01
UV_GLASS, UV_CONC, UV_RUBBLE = C.UV_GLASS, C.UV_CONC, C.UV_RUBBLE
RUST_GREY = UVBand(S.MATERIALS["rust"]["bands"]["grey"], 1.0)
RUST_GREEN = UVBand(S.MATERIALS["rust"]["bands"]["green"], 1.0)
SOLID = ("res0", "res1", "geo", "fire", "view")


def L_new(name):
    return C.city_lods(C.Ruin(name, 0))


def sign_band(L, sign, pts, facing, axes, lo, hi, flip=False):
    v0, v1 = S.SIGN_BAND[sign]
    uv = (0, 1 - v1, 1, 1 - v0) if not flip else (1, 1 - v1, 0, 1 - v0)
    L["res0"].lod.quad(pts, facing, S.SIGN_MAT[sign], UVRect(axes[0], axes[1], lo, hi, uv))


def build_bus_stop():
    """3.6 m Soviet bus shelter: four square posts, a sloped corrugated roof with a fascia, a back wall
    of (partly smashed) glass panes in steel frames, solid side panels, a painted slatted bench, a
    timetable board, the route sign on its own pole, a bin, a graffiti tag on a side panel. Five Res0
    sections (rust, paint, signs3, glassfar, decal_graffiti) to stay in the medium budget."""
    name = "BusStop"
    L = L_new(name)
    hx, d = 1.8, 1.4
    y_back, y_front = d / 2, -d / 2
    z_roof = 2.45
    for (x, y) in ((-hx, y_back), (hx, y_back), (-hx, y_front + 0.15), (hx, y_front + 0.15)):        # posts
        for k in SOLID:
            L[k].box(x - 0.04, x + 0.04, y - 0.04, y + 0.04, 0.0, z_roof + (0.12 if y > 0 else 0.0), **kw_for(k, "rust", RUST_GREY, "metal"))
    roof = [(-hx - 0.15, y_front - 0.2, z_roof - 0.02), (hx + 0.15, y_front - 0.2, z_roof - 0.02),
            (-hx - 0.15, y_back + 0.15, z_roof + 0.12), (hx + 0.15, y_back + 0.15, z_roof + 0.12)]
    top = [(p[0], p[1], p[2] + 0.06) for p in roof]
    faces = [(0, 1, 3, 2), (4, 5, 7, 6), (0, 1, 5, 4), (2, 3, 7, 6), (0, 2, 6, 4), (1, 3, 7, 5)]
    for k in ("res0", "res1", "res2", "geo", "fire", "view", "shadow"):
        kw = kw_for(k, "rust", RUST_GREEN, "metal") if k not in ("shadow",) else {}
        L[k].lod.solid(roof + top, faces, **kw)
    for i in range(12):                                                           # corrugation ribs (Res0)
        xx = -hx - 0.1 + i * (2 * hx + 0.2) / 11
        C.bar(L["res0"].lod, (xx, y_front - 0.2, z_roof + 0.045), (xx, y_back + 0.15, z_roof + 0.185), 0.012, "rust", RUST_GREEN)
    L["res0"].box(-hx - 0.15, hx + 0.15, y_front - 0.22, y_front - 0.18, z_roof - 0.22, z_roof + 0.02, mat="paint",
                  uv=DT.paint_uv("white"))                                         # fascia
    sign_band(L, "line1", [(-0.9, y_front - 0.225, z_roof - 0.2), (0.9, y_front - 0.225, z_roof - 0.2),
                            (0.9, y_front - 0.225, z_roof - 0.02), (-0.9, y_front - 0.225, z_roof - 0.02)], (0, -1, 0), (0, 2),
              (-0.9, z_roof - 0.2), (0.9, z_roof - 0.02))
    # back wall: 3 glass panes in frames, the middle one smashed
    for i in range(3):
        a, b = -hx + 0.05 + i * (2 * hx - 0.1) / 3, -hx + 0.05 + (i + 1) * (2 * hx - 0.1) / 3
        L["res0"].box(a, b, y_back - 0.03, y_back + 0.03, 0.25, 0.3, mat="rust", uv=RUST_GREY)
        L["res0"].box(a, b, y_back - 0.03, y_back + 0.03, 2.1, 2.15, mat="rust", uv=RUST_GREY)
        L["res0"].box(b - 0.025, b + 0.025, y_back - 0.03, y_back + 0.03, 0.25, 2.15, mat="rust", uv=RUST_GREY)
        z_top = 2.1 if i != 1 else 0.75
        L["res0"].quad([(a, y_back, 0.3), (b, y_back, 0.3), (b, y_back, z_top), (a, y_back, z_top)], (0, -1, 0), "glassfar", UV_GLASS,
                       double=True)
    for k in ("geo", "fire"):                                                     # glass: no View box (see-through)
        L[k].box(-hx, hx, y_back - 0.03, y_back + 0.03, 0.25, 2.15, **({"mat": "pen_glass"} if k == "fire" else {}))
    for sx in (-1, 1):                                                            # side panels
        for k in SOLID:
            L[k].box(sx * hx - 0.02, sx * hx + 0.02, y_front + 0.18, y_back, 0.3, 2.0, **kw_for(k, "paint", DT.paint_uv("sage"), "metal"))
    gx = -hx - 0.025
    L["res0"].quad([(gx, y_front + 0.35, 0.6), (gx, y_back - 0.1, 0.6), (gx, y_back - 0.1, 1.6), (gx, y_front + 0.35, 1.6)],
                   (-1, 0, 0), "decal_graffiti", UVRect(1, 2, (y_front + 0.35, 0.6), (y_back - 0.1, 1.6), (1, 0, 0, 1)))
    # bench (slats on two brackets) + timetable board + route sign pole
    for i in range(4):
        yy = y_back - 0.55 + i * 0.1
        L["res0"].box(-1.4, 1.4, yy, yy + 0.08, 0.45, 0.48, mat="paint", uv=DT.paint_uv("sage"))
    for xx in (-1.2, 1.2):
        L["res0"].box(xx - 0.03, xx + 0.03, y_back - 0.6, y_back - 0.05, 0.0, 0.45, mat="rust", uv=RUST_GREY)
    for k in ("res1", "geo", "fire"):
        L[k].box(-1.4, 1.4, y_back - 0.6, y_back - 0.15, 0.0, 0.48, **kw_for(k, "paint", DT.paint_uv("sage"), "metal"))
    L["res0"].box(hx - 0.7, hx - 0.15, y_back - 0.045, y_back - 0.035, 1.3, 1.75, mat="paint", uv=DT.paint_uv("white"))
    L["res0"].prism(hx + 0.35, y_front + 0.1, 0.03, 0.0, 2.6, n=6, mat="rust", uv=RUST_GREY)
    for k in ("geo", "fire"):
        L[k].prism(hx + 0.35, y_front + 0.1, 0.04, 0.0, 2.6, n=4, **({"mat": "pen_metal"} if k == "fire" else {}))
    L["res0"].extrude_x([(y_front + 0.1 + 0.22 * math.cos(2 * math.pi * k / 12), 2.35 + 0.22 * math.sin(2 * math.pi * k / 12))
                         for k in range(12)], hx + 0.33, hx + 0.37, mat="paint", uv=DT.paint_uv("white"))
    L["res0"].prism(-hx + 0.4, y_back - 0.9, 0.18, 0.0, 0.6, n=8, mat="rust", uv=RUST_GREEN)                     # bin
    for k in ("geo", "fire", "view"):                                             # D79: a head fits inside -> it collides
        L[k].prism(-hx + 0.4, y_back - 0.9, 0.18, 0.0, 0.6, n=6, **kw_for(k, "rust", RUST_GREEN, "metal"))
    L["res2"].box(-hx, hx, y_front, y_back, 0.0, 2.5, mat="rust", uv=RUST_GREY, skip=("-y",))
    L["res3"].box(-hx, hx, y_front, y_back, 0.0, 2.5, mat="rust", uv=RUST_GREY)
    L["mem"].lod.point("center", (0.0, 0.0, 0.0))
    C.search_point(L, -hx + 0.4, y_back - 1.45, 0.0)                              # D68: search the bin (table trash)
    return C._finish(L, 600.0)


def build_ad_column():
    """Morris advertising column: stepped concrete plinth, a 2.6 m drum wrapped in torn posters (the
    original billboard designs), a moulded cornice and a domed cap with a finial."""
    name = "AdColumn"
    L = L_new(name)
    r = 0.55
    for k in ("res0", "res1", "res2", "geo", "fire", "view", "shadow"):
        far = k in ("res2", "shadow")                                             # 6-sided drum, no plinth (D67 perf L)
        if not far:
            L[k].prism(0.0, 0.0, r + 0.12, 0.0, 0.18, n=16 if k == "res0" else 8, **kw_for(k, "concrete", UV_CONC, "concrete"))
        kw2 = kw_for(k, "paint", DT.paint_uv("sage"), "concrete") if k != "shadow" else {}
        L[k].prism(0.0, 0.0, r, 0.0 if far else 0.18, 2.8, n=20 if k == "res0" else (6 if far else 8), **kw2)
    n = 20                                                                        # poster wrap: 4 sheets round the drum
    for i in range(n):
        a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
        p0 = (r * 1.004 * math.cos(a0), r * 1.004 * math.sin(a0))
        p1 = (r * 1.004 * math.cos(a1), r * 1.004 * math.sin(a1))
        z_top = 2.55 if h01(name, "torn", i) > 0.2 else 1.6 + 0.6 * h01(name, "tz", i)
        u0, u1 = (i % 5) / 5.0, (i % 5 + 1) / 5.0
        mid = ((a0 + a1) / 2)
        L["res0"].lod.quad([(p0[0], p0[1], 0.45), (p1[0], p1[1], 0.45), (p1[0], p1[1], z_top), (p0[0], p0[1], z_top)],
                           (math.cos(mid), math.sin(mid), 0), "billboard",
                           lambda pts, nrm, u0=u0, u1=u1, z_top=z_top: [(u0, 0.0), (u1, 0.0), (u1, (z_top - 0.45) / 2.1),
                                                                        (u0, (z_top - 0.45) / 2.1)])   # v up, u read from outside
    for (rr, z0, z1) in ((r + 0.08, 2.8, 2.88), (r + 0.12, 2.88, 2.96), (r + 0.06, 2.96, 3.0)):           # cornice
        L["res0"].prism(0.0, 0.0, rr, z0, z1, n=20, mat="paint", uv=DT.paint_uv("sage"))
    for (rr, z0, z1) in ((r, 3.0, 3.12), (0.42, 3.12, 3.22), (0.26, 3.22, 3.3), (0.1, 3.3, 3.36)):           # dome
        L["res0"].prism(0.0, 0.0, rr, z0, z1, n=16, mat="metal", uv=RUST_GREEN)
    L["res0"].prism(0.0, 0.0, 0.025, 3.36, 3.6, n=6, mat="metal", uv=DT.UV_STEEL)
    L["res1"].prism(0.0, 0.0, r + 0.1, 2.8, 3.3, n=8, mat="metal", uv=RUST_GREEN)
    L["res3"].prism(0.0, 0.0, r, 0.0, 3.2, n=4, mat="paint", uv=DT.paint_uv("sage"))
    L["mem"].lod.point("center", (0.0, 0.0, 0.0))
    return C._finish(L, 2500.0)


def build_phone_booth():
    """Soviet street phone booth (taxofon): steel frame, glass on three sides (one pane gone), a door
    frame on the open -Y side, a red roof cap with the phone pictogram band, the coin phone inside with
    its handset hanging on the cord."""
    name = "PhoneBooth"
    L = L_new(name)
    hw, h = 0.45, 2.25
    for (x, y) in ((-hw, -hw), (hw, -hw), (-hw, hw), (hw, hw)):
        for k in SOLID:
            L[k].box(x - 0.03, x + 0.03, y - 0.03, y + 0.03, 0.0, h, **kw_for(k, "metal", DT.UV_PAINT, "metal"))
    for k in ("res0", "res1", "res2", "geo", "fire", "view", "shadow"):
        kw = kw_for(k, "fair", UVBand(S.MATERIALS["fair"]["bands"]["red"], 1.0), "metal") if k != "shadow" else {}
        L[k].box(-hw - 0.05, hw + 0.05, -hw - 0.05, hw + 0.05, h, h + 0.22, **kw)
        if k != "shadow":
            L[k].box(-hw, hw, -hw, hw, 0.0, 0.06, **kw_for(k, "concrete", UV_CONC, "concrete"))
    panes = [((-hw, hw, hw, hw), (0, 1, 0)), ((-hw, -hw, -hw, hw), (-1, 0, 0)), ((hw, hw, -hw, hw), (1, 0, 0))]
    gone = min(2, int(h01(name, "pane", 0) * 3))                                 # exactly one pane smashed out
    for i, ((x0, x1, y0, y1), f) in enumerate(panes):
        if i != gone:
            L["res0"].lod.quad([(x0, y0, 0.9), (x1, y1, 0.9), (x1, y1, h - 0.1), (x0, y0, h - 0.1)], f, "glassfar", UV_GLASS, double=True)
        L["res0"].lod.quad([(x0, y0, 0.08), (x1, y1, 0.08), (x1, y1, 0.85), (x0, y0, 0.85)], f, "fair",
                           UVBand(S.MATERIALS["fair"]["bands"]["red"], 1.0), double=True)
    for k in ("geo", "fire", "view"):                                             # View: lower panels only, glass is see-through
        for i, ((x0, x1, y0, y1), f) in enumerate(panes):
            top = 0.85 if (k == "view" or i == gone) else h
            L[k].box(min(x0, x1) - 0.01, max(x0, x1) + 0.01, min(y0, y1) - 0.01, max(y0, y1) + 0.01, 0.06, top,
                     **({"mat": "pen_glass"} if k == "fire" else {}))
    L["res0"].box(-0.16, 0.16, hw - 0.12, hw - 0.04, 1.2, 1.6, mat="metal", uv=DT.UV_STEEL)                     # phone
    L["res0"].box(-0.05, 0.05, hw - 0.16, hw - 0.12, 1.3, 1.5, mat="metal", uv=DT.UV_STEEL)
    C.bar(L["res0"].lod, (0.1, hw - 0.12, 1.35), (0.15, hw - 0.3, 0.9), 0.006, "metal", DT.UV_STEEL)   # cord
    L["res0"].box(0.11, 0.2, hw - 0.36, hw - 0.28, 0.82, 0.9, mat="metal", uv=DT.UV_STEEL)             # handset
    sign_band(L, "line1", [(-0.4, -hw - 0.055, h + 0.04), (0.4, -hw - 0.055, h + 0.04), (0.4, -hw - 0.055, h + 0.18),
                            (-0.4, -hw - 0.055, h + 0.18)], (0, -1, 0), (0, 2), (-0.4, h + 0.04), (0.4, h + 0.18))
    L["res3"].box(-hw, hw, -hw, hw, 0.0, h + 0.2, mat="fair", uv=UVBand(S.MATERIALS["fair"]["bands"]["red"], 1.0))
    L["mem"].lod.point("center", (0.0, 0.0, 0.0))
    return C._finish(L, 300.0)


BUILDERS = {"BusStop": build_bus_stop, "AdColumn": build_ad_column, "PhoneBooth": build_phone_booth}

import aobake  # noqa: E402

for _n in S.AO_PROPS:                                     # D87: baked AO on UV set 1 (skyspec.AO_PROPS, P55)
    if _n in BUILDERS:
        BUILDERS[_n] = aobake.with_ao(BUILDERS[_n], S.AO_PROPS[_n])


def modules():
    return {n: (BUILDERS[n], e["pbo"], e["p3d"]) for n, e in S.KIT.items() if n in BUILDERS}


if __name__ == "__main__":
    run_cli(modules(), KIT_MATS, "build_stats_streetprops.json")
