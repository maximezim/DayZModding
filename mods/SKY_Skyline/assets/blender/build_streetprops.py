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


def rrect(ax, ay, r, z, cx=0.0, cy=0.0, n=3):
    """D105: rounded-rectangle ring (half sizes ax, ay, corner radius r, n points per corner), CCW from +X+Y."""
    pts = []
    for qx, qy, a0 in ((1, 1, 0.0), (-1, 1, 90.0), (-1, -1, 180.0), (1, -1, 270.0)):
        for j in range(n):
            a = math.radians(a0 + 90.0 * j / (n - 1))
            pts.append((cx + qx * (ax - r) + r * math.cos(a), cy + qy * (ay - r) + r * math.sin(a), z))
    return pts


SHARDS = (((0.0, 0.0), (0.42, 0.0), (0.18, 0.2), (0.0, 0.34)),         # D105: convex glass shards left in a smashed
          ((0.68, 0.0), (1.0, 0.0), (1.0, 0.24), (0.84, 0.16)),       # frame, (u along the pane, v up) in 0..1
          ((0.0, 0.8), (0.14, 0.86), (0.3, 1.0), (0.0, 1.0)))


def shards(lod, x0, y0, x1, y1, z0, z1, f):
    """D105: jagged glass left in a smashed pane's frame (both bottom corners, one top corner), double-sided."""
    for sh in SHARDS:
        lod.quad([(x0 + (x1 - x0) * u, y0 + (y1 - y0) * u, z0 + (z1 - z0) * v) for (u, v) in sh], f, "glass", UV_GLASS,
                 double=True)


def build_bus_stop():
    """3.6 m Soviet bus shelter (D105 close-up pass): four square steel posts on base plates,
    a sloped corrugated roof with a fascia, a rear gutter and a downpipe, a back wall of dirty glass panes in
    steel frames (the middle one smashed, shards left in the frame), framed side panels, a slatted bench with
    rounded slats on cast brackets, a framed timetable, the route sign on its own pole, a lofted bin with a
    rolled rim, a graffiti tag on a side panel. Collision unchanged."""
    name = "BusStop"
    L = L_new(name)
    hx, d = 1.8, 1.4
    y_back, y_front = d / 2, -d / 2
    z_roof = 2.45
    for (x, y) in ((-hx, y_back), (hx, y_back), (-hx, y_front + 0.15), (hx, y_front + 0.15)):        # posts
        top = z_roof + (0.12 if y > 0 else 0.0)
        for k in SOLID:
            L[k].box(x - 0.04, x + 0.04, y - 0.04, y + 0.04, 0.0, top, **kw_for(k, "rust", RUST_GREY, "metal"))
        L["res0"].box(x - 0.09, x + 0.09, y - 0.09, y + 0.09, 0.0, 0.012, mat="rust", uv=RUST_GREY, skip=("-z",))   # base plate
    roof = [(-hx - 0.15, y_front - 0.2, z_roof - 0.02), (hx + 0.15, y_front - 0.2, z_roof - 0.02),
            (-hx - 0.15, y_back + 0.15, z_roof + 0.12), (hx + 0.15, y_back + 0.15, z_roof + 0.12)]
    top = [(p[0], p[1], p[2] + 0.06) for p in roof]
    faces = [(0, 1, 3, 2), (4, 5, 7, 6), (0, 1, 5, 4), (2, 3, 7, 6), (0, 2, 6, 4), (1, 3, 7, 5)]
    for k in ("res0", "res1", "res2", "geo", "fire", "view", "shadow"):
        kw = kw_for(k, "rust", RUST_GREEN, "metal") if k not in ("shadow",) else {}
        L[k].lod.solid(roof + top, faces, **kw)
    for i in range(12):                                                           # corrugation ribs: open ridges on the roof
        xx = -hx - 0.1 + i * (2 * hx + 0.2) / 11                                  # top (4 triangles each, perf M)
        a0, a1 = (y_front - 0.2, z_roof + 0.04), (y_back + 0.15, z_roof + 0.18)
        for sx in (-1, 1):
            L["res0"].lod.quad([(xx + sx * 0.015, a0[0], a0[1]), (xx + sx * 0.015, a1[0], a1[1]), (xx, a1[0], a1[1] + 0.012),
                                (xx, a0[0], a0[1] + 0.012)], (sx, -0.05, 0.6), "rust", RUST_GREEN)
    L["res0"].box(-hx - 0.15, hx + 0.15, y_front - 0.22, y_front - 0.18, z_roof - 0.22, z_roof + 0.02, mat="paint",
                  uv=DT.paint_uv("white"))                                         # fascia
    sign_band(L, "line1", [(-0.9, y_front - 0.225, z_roof - 0.2), (0.9, y_front - 0.225, z_roof - 0.2),
                            (0.9, y_front - 0.225, z_roof - 0.02), (-0.9, y_front - 0.225, z_roof - 0.02)], (0, -1, 0), (0, 2),
              (-0.9, z_roof - 0.2), (0.9, z_roof - 0.02))
    yg, zg = y_back + 0.2, z_roof + 0.09                                          # rear gutter + downpipe (Res0)
    C.tube(L["res0"].lod, (-hx - 0.15, yg, zg), (hx + 0.15, yg, zg), 0.05, "rust", RUST_GREY, n=8)
    C.tube(L["res0"].lod, (hx - 0.1, yg, zg - 0.05), (hx - 0.1, yg, 0.15), 0.04, "rust", RUST_GREY, n=8)
    C.tube(L["res0"].lod, (hx - 0.1, yg, 0.15), (hx - 0.1, yg - 0.25, 0.05), 0.04, "rust", RUST_GREY, n=8)    # shoe
    # back wall: 3 glass panes in frames, the middle one smashed (shards left in the frame)
    for i in range(3):
        a, b = -hx + 0.05 + i * (2 * hx - 0.1) / 3, -hx + 0.05 + (i + 1) * (2 * hx - 0.1) / 3
        L["res0"].box(a, b, y_back - 0.03, y_back + 0.03, 0.25, 0.3, mat="rust", uv=RUST_GREY)
        L["res0"].box(a, b, y_back - 0.03, y_back + 0.03, 2.1, 2.15, mat="rust", uv=RUST_GREY)
        L["res0"].box(b - 0.025, b + 0.025, y_back - 0.03, y_back + 0.03, 0.25, 2.15, mat="rust", uv=RUST_GREY)
        if i != 1:
            L["res0"].quad([(a, y_back, 0.3), (b, y_back, 0.3), (b, y_back, 2.1), (a, y_back, 2.1)], (0, -1, 0), "glass", UV_GLASS,
                           double=True)
        else:
            shards(L["res0"].lod, a + 0.025, y_back, b - 0.025, y_back, 0.3, 2.1, (0, -1, 0))
    for k in ("geo", "fire"):                                                     # glass: no View box (see-through); the smashed
        for i in (0, 2):                                                          # middle pane is open (review L3; 12 components)
            a, b = -hx + i * 2 * hx / 3, -hx + (i + 1) * 2 * hx / 3
            L[k].box(a, b, y_back - 0.03, y_back + 0.03, 0.25, 2.15, **({"mat": "pen_glass"} if k == "fire" else {}))
    for sx in (-1, 1):                                                            # side panels in steel frames
        for k in SOLID:
            L[k].box(sx * hx - 0.02, sx * hx + 0.02, y_front + 0.18, y_back, 0.3, 2.0, **kw_for(k, "paint", DT.paint_uv("sage"), "metal"))
        x0, x1 = sx * hx - 0.03, sx * hx + 0.03
        L["res0"].box(x0, x1, y_front + 0.16, y_front + 0.22, 0.28, 2.02, mat="rust", uv=RUST_GREY)         # front stile
        for (z0, z1) in ((0.27, 0.32), (1.98, 2.03)):                                                     # rails
            L["res0"].box(x0, x1, y_front + 0.22, y_back - 0.04, z0, z1, mat="rust", uv=RUST_GREY)
    gx = -hx - 0.025
    L["res0"].quad([(gx, y_front + 0.35, 0.6), (gx, y_back - 0.1, 0.6), (gx, y_back - 0.1, 1.6), (gx, y_front + 0.35, 1.6)],
                   (-1, 0, 0), "decal_graffiti", UVRect(1, 2, (y_front + 0.35, 0.6), (y_back - 0.1, 1.6), (1, 0, 0, 1)))
    # bench: rounded slats on cast brackets
    slat = [(0.0, 0.0), (0.075, 0.0), (0.08, 0.012), (0.075, 0.03), (0.0, 0.03), (-0.005, 0.012)]
    for i in range(4):
        yy = y_back - 0.55 + i * 0.1
        L["res0"].extrude_x([(yy + py, 0.45 + pz) for (py, pz) in slat], -1.4, 1.4, mat="paint", uv=DT.paint_uv("sage"))
    arm = [(y_back - 0.6, 0.41), (y_back - 0.6, 0.45), (y_back - 0.1, 0.45), (y_back - 0.1, 0.4), (y_back - 0.2, 0.36),
           (y_back - 0.48, 0.36)]                                                 # cast bracket = two convex pieces
    leg = [(y_back - 0.38, 0.0), (y_back - 0.18, 0.0), (y_back - 0.25, 0.38), (y_back - 0.33, 0.38)]
    for xx in (-1.2, 1.2):
        L["res0"].extrude_x(arm, xx - 0.025, xx + 0.025, mat="rust", uv=RUST_GREY)
        L["res0"].extrude_x(leg, xx - 0.02, xx + 0.02, mat="rust", uv=RUST_GREY)
    for k in ("res1", "geo", "fire"):
        L[k].box(-1.4, 1.4, y_back - 0.6, y_back - 0.15, 0.0, 0.48, **kw_for(k, "paint", DT.paint_uv("sage"), "metal"))
    # timetable in a frame
    L["res0"].box(hx - 0.72, hx - 0.13, y_back - 0.05, y_back - 0.035, 1.28, 1.77, mat="rust", uv=RUST_GREY)
    L["res0"].box(hx - 0.7, hx - 0.15, y_back - 0.055, y_back - 0.05, 1.3, 1.75, mat="paint", uv=DT.paint_uv("white"))
    # route sign: pole with a cap, round plate with a rim
    C.tube(L["res0"].lod, (hx + 0.35, y_front + 0.1, 0.0), (hx + 0.35, y_front + 0.1, 2.6), 0.03, "rust", RUST_GREY, n=8)
    L["res0"].prism(hx + 0.35, y_front + 0.1, 0.036, 2.6, 2.63, n=8, mat="rust", uv=RUST_GREY)
    for k in ("geo", "fire"):
        L[k].prism(hx + 0.35, y_front + 0.1, 0.04, 0.0, 2.6, n=4, **({"mat": "pen_metal"} if k == "fire" else {}))
    disc = [(y_front + 0.1 + 0.22 * math.cos(2 * math.pi * k / 16), 2.35 + 0.22 * math.sin(2 * math.pi * k / 16)) for k in range(16)]
    L["res0"].extrude_x(disc, hx + 0.33, hx + 0.37, mat="paint", uv=DT.paint_uv("white"))
    # bin: lofted tapered drum with a rolled rim on two straps
    bx_, by_ = -hx + 0.4, y_back - 0.9
    rings = [[(bx_ + r_ * math.cos(2 * math.pi * j / 12), by_ + r_ * math.sin(2 * math.pi * j / 12), z_) for j in range(12)]
             for (z_, r_) in ((0.08, 0.15), (0.6, 0.18))]
    L["res0"].loft(rings, mat="rust", uv=RUST_GREEN)
    L["res0"].prism(bx_, by_, 0.195, 0.58, 0.62, n=12, mat="rust", uv=RUST_GREEN)
    for sy in (-1, 1):
        L["res0"].box(bx_ - 0.02, bx_ + 0.02, by_ + sy * 0.15 - 0.01, by_ + sy * 0.15 + 0.01, 0.0, 0.1, mat="rust", uv=RUST_GREY)
    for k in ("geo", "fire", "view"):                                             # D79: a head fits inside -> it collides
        L[k].prism(bx_, by_, 0.18, 0.0, 0.6, n=6, **kw_for(k, "rust", RUST_GREEN, "metal"))
    L["res2"].box(-hx, hx, y_front, y_back, 0.0, 2.5, mat="rust", uv=RUST_GREY, skip=("-y", "+y"))   # review M2: no opaque back
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
    """Soviet street phone booth (taxofon), D105 close-up pass: round corner posts with transom rails, red kick
    panels, transparent dirty glass on three sides (one pane smashed, shards left in the frame), a door header
    and threshold on the open -Y side, a lofted red roof cap with the phone sign on three sides, a steel back
    plate with the coin phone (keypad, coin slot, cradle), the handset hanging on its armoured cord, a shelf
    with a phone book. Collision unchanged."""
    name = "PhoneBooth"
    L = L_new(name)
    hw, h = 0.45, 2.25
    red = UVBand(S.MATERIALS["fair"]["bands"]["red"], 1.0)
    for (x, y) in ((-hw, -hw), (hw, -hw), (-hw, hw), (hw, hw)):
        C.tube(L["res0"].lod, (x, y, 0.06), (x, y, h), 0.032, "metal", DT.UV_PAINT, n=8)
        for k in SOLID[1:]:
            L[k].box(x - 0.03, x + 0.03, y - 0.03, y + 0.03, 0.0, h, **kw_for(k, "metal", DT.UV_PAINT, "metal"))
    # roof cap: lofted rounded box with a drip lip (Res0); boxes elsewhere
    rings = [rrect(hw + 0.07, hw + 0.07, 0.05, h), rrect(hw + 0.07, hw + 0.07, 0.05, h + 0.03),
             rrect(hw + 0.05, hw + 0.05, 0.04, h + 0.035), rrect(hw + 0.05, hw + 0.05, 0.04, h + 0.19),
             rrect(hw - 0.02, hw - 0.02, 0.03, h + 0.24)]
    L["res0"].loft(rings, mat="fair", uv=red)
    for k in ("res1", "res2", "geo", "fire", "view", "shadow"):
        kw = kw_for(k, "fair", red, "metal") if k != "shadow" else {}
        L[k].box(-hw - 0.05, hw + 0.05, -hw - 0.05, hw + 0.05, h, h + 0.22, **kw)
    for k in ("res0", "res1", "res2", "geo", "fire", "view"):
        L[k].box(-hw, hw, -hw, hw, 0.0, 0.06, **kw_for(k, "concrete", UV_CONC, "concrete"))
    L["res0"].box(-hw + 0.04, hw - 0.04, -hw + 0.04, hw - 0.04, 0.06, 0.068, mat="metal", uv=DT.UV_STEEL, skip=("-z",))  # floor plate
    panes = [((-hw, hw, hw, hw), (0, 1, 0)), ((-hw, -hw, -hw, hw), (-1, 0, 0)), ((hw, hw, -hw, hw), (1, 0, 0))]
    gone = 1 + min(1, int(h01(name, "pane", 0) * 2))                             # one SIDE pane smashed (review M1: the back
                                                                                 # pane carries the phone plate)
    for i, ((x0, x1, y0, y1), f) in enumerate(panes):
        if i != gone:
            L["res0"].lod.quad([(x0, y0, 0.9), (x1, y1, 0.9), (x1, y1, h - 0.1), (x0, y0, h - 0.1)], f, "glass", UV_GLASS, double=True)
        else:
            shards(L["res0"].lod, x0, y0, x1, y1, 0.9, h - 0.1, f)
        ax, ay = (0.02, 0.0) if x0 == x1 else (0.0, 0.02)                         # frame rails across the pane plane
        L["res0"].box(min(x0, x1) - ax * 0.4, max(x0, x1) + ax * 0.4, min(y0, y1) - ay * 0.4, max(y0, y1) + ay * 0.4,
                      0.08, 0.87, mat="fair", uv=red, skip=("-z", "+z"))           # kick panel: a 16 mm sheet, ends in the rails
        for (z0, z1) in ((0.06, 0.1), (0.85, 0.9), (h - 0.1, h - 0.06)):
            L["res0"].box(min(x0, x1) - ax + (0.03 if x0 != x1 else 0), max(x0, x1) + ax - (0.03 if x0 != x1 else 0),
                          min(y0, y1) - ay + (0.03 if y0 != y1 else 0), max(y0, y1) + ay - (0.03 if y0 != y1 else 0),
                          z0, z1, mat="metal", uv=DT.UV_PAINT)
    L["res0"].box(-hw + 0.03, hw - 0.03, -hw - 0.02, -hw + 0.02, h - 0.12, h - 0.04, mat="metal", uv=DT.UV_PAINT)   # door header
    L["res0"].box(-hw + 0.03, hw - 0.03, -hw - 0.02, -hw + 0.02, 0.06, 0.085, mat="metal", uv=DT.UV_STEEL)    # threshold
    for k in ("geo", "fire", "view"):                                             # View: lower panels only, glass is see-through
        for i, ((x0, x1, y0, y1), f) in enumerate(panes):
            top = 0.9 if (k == "view" or i == gone) else h                       # review L4: View up to the rail top
            L[k].box(min(x0, x1) - 0.01, max(x0, x1) + 0.01, min(y0, y1) - 0.01, max(y0, y1) + 0.01, 0.06, top,
                     **({"mat": "pen_glass"} if k == "fire" else {}))
    # phone on a steel back plate in front of the back pane (that pane is never the smashed one)
    yb = hw - 0.02
    L["res0"].box(-0.22, 0.22, yb - 0.015, yb, 0.95, 1.8, mat="metal", uv=DT.UV_STEEL)
    body = [(yb - 0.015, 1.18), (yb - 0.11, 1.18), (yb - 0.13, 1.22), (yb - 0.13, 1.5), (yb - 0.09, 1.62), (yb - 0.015, 1.64)]
    L["res0"].extrude_x(body, -0.13, 0.13, mat="metal", uv=DT.UV_PAINT)
    L["res0"].box(-0.07, 0.07, yb - 0.134, yb - 0.128, 1.25, 1.4, mat="metal", uv=DT.UV_STEEL)         # keypad plate
    for r_ in range(4):                                                          # keypad rows (one raised strip per row)
        L["res0"].box(-0.055, 0.055, yb - 0.14, yb - 0.134, 1.265 + r_ * 0.034, 1.285 + r_ * 0.034, mat="metal", uv=DT.UV_PAINT)
    L["res0"].box(0.08, 0.11, yb - 0.134, yb - 0.128, 1.42, 1.48, mat="metal", uv=DT.UV_STEEL)          # coin slot
    L["res0"].box(-0.11, -0.04, yb - 0.134, yb - 0.128, 1.43, 1.47, mat="metal", uv=DT.UV_STEEL)        # display window (dark steel: 5 sections)
    L["res0"].box(-0.17, -0.13, yb - 0.1, yb - 0.04, 1.3, 1.52, mat="metal", uv=DT.UV_STEEL)            # empty cradle
    cord = [(0.1, yb - 0.1, 1.2), (0.12, yb - 0.2, 1.05), (0.15, yb - 0.27, 0.95)]
    for a_, b_ in zip(cord, cord[1:]):
        C.tube(L["res0"].lod, a_, b_, 0.008, "metal", DT.UV_STEEL, n=6)
    hs0, hs1 = (0.15, yb - 0.28, 0.93), (0.17, yb - 0.31, 0.72)                  # handset hanging, ear cup / mouthpiece
    C.tube(L["res0"].lod, hs0, hs1, 0.018, "metal", DT.UV_PAINT, n=8)
    for (cx_, cy_, cz_) in (hs0, hs1):
        L["res0"].prism(cx_, cy_ - 0.01, 0.032, cz_ - 0.025, cz_ + 0.025, n=8, mat="metal", uv=DT.UV_PAINT)
    L["res0"].box(-0.3, 0.3, yb - 0.32, yb - 0.015, 0.92, 0.95, mat="metal", uv=DT.UV_STEEL)            # shelf
    L["res0"].box(-0.25, 0.0, yb - 0.27, yb - 0.08, 0.95, 0.99, mat="metal", uv=DT.UV_PAINT)  # phone book
    for k in ("res1",):
        L[k].box(-0.16, 0.16, hw - 0.12, hw - 0.04, 1.2, 1.6, mat="metal", uv=DT.UV_STEEL)
    sign_band(L, "phone", [(-0.4, -hw - 0.055, h + 0.04), (0.4, -hw - 0.055, h + 0.04), (0.4, -hw - 0.055, h + 0.18),
                            (-0.4, -hw - 0.055, h + 0.18)], (0, -1, 0), (0, 2), (-0.4, h + 0.04), (0.4, h + 0.18))
    for sx in (-1, 1):                                                           # the sign on both sides of the cap
        xs = sx * (hw + 0.055)
        sign_band(L, "phone", [(xs, -0.4 * sx, h + 0.04), (xs, 0.4 * sx, h + 0.04), (xs, 0.4 * sx, h + 0.18), (xs, -0.4 * sx, h + 0.18)],
                  (sx, 0, 0), (1, 2), (-0.4, h + 0.04), (0.4, h + 0.18), flip=(sx < 0))
    L["res3"].box(-hw, hw, -hw, hw, 0.0, h + 0.2, mat="fair", uv=red)
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
