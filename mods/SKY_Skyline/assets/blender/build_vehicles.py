"""D64 vehicles: wreck bodies for the city and intact reference bodies for a vehicle modeller.

    python build_vehicles.py -- --out <mods/SKY_Skyline/addons> [--only Wreck_CityBus,Wreck_GarbageTruck]
    python build_vehicles.py -- --reference <mods/SKY_Skyline/vehicles/reference>

DayZ cannot drive a car whose model does not match the skeleton, selections, memory points and simulation
config of a vanilla CarScript (D64): those come from the vanilla model.cfg / P3D, which are not in the
script sources, so a drivable bus or garbage truck is handed to a modeller (vehicles/VEHICLE_SPEC.md).
This generator gives them a head start and gives the city its wrecks:
- `body()` builds a parametric Soviet-era vehicle body (city bus LiAZ-style, rear-loader garbage truck on a
  ZiL-like cab): panels with window bands, real octagonal wheels on axles, bumpers, lamps, mirrors,
  wipers, roof gear; the wreck state adds rust, dents, missing panels, broken glass, flat tyres;
- kit wrecks (sky_street): Wreck_CityBus (new), Wreck_GarbageTruck (rebuilt from the D61 box model);
- reference bodies (intact, Res LODs + Memory only) with the selection / memory point names listed in
  VEHICLE_SPEC.md, for the modeller to rig against the vanilla skeleton they pick.
Frame: front = -Y, origin = centre at ground level.
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
from build_kit import KIT_MATS, _sec, tyre  # noqa: E402
from skygeo import UVBand, UVWorld, export_p3d, run_cli  # noqa: E402

kw_for, h01 = C.kw_for, C.h01
UV_GLASS, UV_RUBBLE = C.UV_GLASS, C.UV_RUBBLE
UV_TRASH = UVWorld(S.MATERIALS["trash"]["sheet_m"])


def rust_band(b):
    return UVBand(S.MATERIALS["rust"]["bands"][b], 1.0)


def fair_band(b):
    return UVBand(S.MATERIALS["fair"]["bands"][b], 1.0)


SPECS = {
    # length, width, body height, floor (bottom of body), cab length (0 = integral), axles (y), paint
    "CityBus": {"len": 11.4, "wid": 2.5, "top": 3.0, "floor": 0.45, "cab": 0.0, "axles": (-3.1, 2.2),
                "paint": ("fair", "yellow"), "trim": ("fair", "white"), "wheel_r": 0.5, "doors": (-4.6, -0.6, 3.6)},
    "GarbageTruck": {"len": 8.8, "wid": 2.5, "top": 3.4, "floor": 0.7, "cab": 2.1, "axles": (-3.3, 1.2, 2.6),
                     "paint": ("rust", "green"), "trim": ("paint", "white"), "wheel_r": 0.5, "doors": ()},
}


def uv_of(pair):
    kind, band = pair
    if kind == "fair":
        return "fair", fair_band(band)
    if kind == "rust":
        return "rust", rust_band(band)
    return "paint", DT.paint_uv(band)


def wheel(L, keys, x_out, y, r, sx, flat, twin=False, sel=()):
    """D97: kit tyre (round, sagging when flat) with a steel rim, hub cap and wheel nuts (Res0); a twin rear wheel adds
    the inner tyre. x_out = outer face of the tyre, sx = side (-1 / +1)."""
    w = 0.3
    x_in = x_out - sx * w
    R = {k: L[k].lod for k in keys}
    tyre(R, keys, x_in, y, r=r, zc=r, width=w, flat=(0.13 if flat else 0.03), n=18)
    if twin:
        tyre({"res0": L["res0"].lod}, ("res0",), x_in - sx * 0.31, y, r=r, zc=r, width=w, flat=(0.13 if flat else 0.03), n=18)
    if "res0" not in keys:
        return
    r0 = L["res0"].lod
    xr = x_in + sx * (w + 0.006)                                             # rim face (tyre() puts the rim there)
    cap = [(y + 0.11 * math.cos(2 * math.pi * k / 12), r + 0.11 * math.sin(2 * math.pi * k / 12)) for k in range(12)]
    r0.extrude_x(cap, *sorted((xr - sx * 0.01, xr + sx * 0.035)), mat="metal", uv=DT.UV_STEEL, sel=list(sel))
    for k in range(5):                                                       # wheel nuts (perf L4: 5)
        a = 2 * math.pi * k / 5
        cy, cz = y + 0.17 * math.cos(a), r + 0.17 * math.sin(a)
        r0.box(*sorted((xr - sx * 0.005, xr + sx * 0.022)), cy - 0.018, cy + 0.018, cz - 0.018, cz + 0.018,
               mat="metal", uv=DT.UV_STEEL, sel=list(sel))


def section(w, zb, zt, belt=(), r_top=0.3, n_top=4, crown=0.0, r_bot=0.0):
    """D97: closed (x, z) body section - flat sides from zb to zt - r_top with extra side points at the `belt` heights
    (window sills / heads: a glazing band is then one loft segment), rounded top corners under a crowned roof and an
    optional bottom chamfer. Returns (points, seg) where seg(j, side) is the loft segment index of the j-th right-side
    segment (counted from the bottom) on side +1 / -1."""
    right = ([(w - r_bot, zb), (w, zb + r_bot)] if r_bot > 0 else [(w, zb)])
    right += [(w, z) for z in belt]
    for j in range(n_top + 1):
        a = (math.pi / 2) * j / n_top
        right.append((w - r_top + r_top * math.cos(a), zt - r_top + r_top * math.sin(a)))
    pts = right + [(0.0, zt + crown)] + [(-x, z) for x, z in reversed(right)]
    n = len(pts)
    off = 1 if r_bot > 0 else 0

    def seg(j, side):
        j += off
        return j if side > 0 else n - 2 - j
    return pts, seg


def ring(pts, y, f=1.0, dz=0.0, x0=0.0):
    """Section points at station y, x scaled by f about x0 (rounded plan corners); dz lowers the upper half."""
    zm = (min(p[1] for p in pts) + max(p[1] for p in pts)) / 2
    return [(x0 + (x - x0) * f, y, z + (dz if z > zm else 0.0)) for x, z in pts]


def arch(L, keys, sx, w, ay, R, zc, depth, mat, uv, pmat, puv):
    """D97: wheel arch in a flat body side at x = sx * w: spandrel plates turning the rectangular opening (ay +- R,
    up to zc + R) into a half-round arch, a dark well (half-round tunnel + inner wall) `depth` deep."""
    m = 8
    for k in keys:
        lod = L[k].lod
        steps = m if k == "res0" else 4
        for i in range(steps):
            a0, a1 = math.pi * i / steps, math.pi * (i + 1) / steps
            p = [(ay + R * math.cos(a), zc + R * math.sin(a)) for a in (a0, a1)]

            def proj(a):
                c, s_ = math.cos(a), math.sin(a)
                t = min(R / abs(c) if abs(c) > 1e-6 else 9.0, R / s_ if s_ > 1e-6 else 9.0)
                return (ay + t * c, zc + t * s_)
            q = [proj(a0), proj(a1)]
            prof = [p[0], p[1], q[1], q[0]]
            if abs(q[0][0] - p[0][0]) + abs(q[0][1] - p[0][1]) + abs(q[1][0] - p[1][0]) + abs(q[1][1] - p[1][1]) > 0.01:
                lod.extrude_x(prof, *sorted((sx * (w - 0.05), sx * w)), mat=pmat, uv=puv)
            xa, xb = sx * (w - 0.05), sx * (w - depth)                           # well ceiling (faces the wheel)
            lod.quad([(xa, p[0][0], p[0][1]), (xb, p[0][0], p[0][1]), (xb, p[1][0], p[1][1]), (xa, p[1][0], p[1][1])],
                     (0, ay - (p[0][0] + p[1][0]) / 2, zc - (p[0][1] + p[1][1]) / 2), mat, uv)
            tri = [(sx * (w - depth), ay, zc), (sx * (w - depth), p[0][0], p[0][1]), (sx * (w - depth), p[1][0], p[1][1])]
            lod.quad(tri, (sx, 0, 0), mat, uv)                                    # inner wall


def bus_body(L, wreck, name, sel):
    sp = SPECS["CityBus"]
    ln, w, top, fl = sp["len"], sp["wid"] / 2, sp["top"], sp["floor"]
    hy = ln / 2
    S_ = (lambda s: [s] if sel else [])
    r0, r1 = L["res0"].lod, L["res1"].lod
    upper_m, upper_uv = "rust", rust_band("beige")                 # faded cream over a terracotta skirt (LiAZ two-tone)
    lower_m, lower_uv = "rust", rust_band("terracotta")
    dark = DT.paint_uv("slate")
    zs, zm, zg, zh = 1.12, 1.62, 2.56, 2.97                        # skirt top, window sill, window head, roof corner top
    door_side = -1                                                 # kerb side for right-hand traffic (front = -Y)
    pil = [-4.95 + i * (5.25 + 4.95) / 8 for i in range(9)]        # window pillars (8 bays)
    ends = [(-hy, 0.90, -0.06), (-hy + 0.04, 0.965, -0.02), (-hy + 0.14, 1.0, 0.0)]
    stations = ends + [(y, 1.0, 0.0) for y in pil] + [(-y, f, dz) for (y, f, dz) in reversed(ends)]
    # ---- upper shell (glazing band = loft segments: no floating panes), Res0 / Res1
    for lod, nt in ((r0, 5), (r1, 2)):
        pts, seg = section(w, zs, zh, belt=(zm, zg), r_top=0.36, n_top=nt, crown=0.04)
        glass = {}
        for i in range(len(stations) - 1):
            for sx in (-1, 1):
                glass[(i, seg(1, sx))] = "glassfar"
        lod.loft([ring(pts, y, f, dz) for y, f, dz in stations], mat=upper_m, uv=upper_uv, mats=glass, sel=S_("body"))
    # ---- lower skirt between the wheel arches (flat sides: arches, doors and rust patches sit on them)
    axles = sp["axles"]
    R = 0.62
    cuts = [(-hy, None)] + [(ay - R, ay + R) for ay in axles] + [(None, hy)]
    spans = []
    for (a, b), (c, d) in zip(cuts, cuts[1:]):
        spans.append((a if b is None else b, c if c is not None else d))
    for lod, rb in ((r0, 0.06), (r1, 0.0)):
        pts, _seg = section(w, fl, zs, belt=(0.93,), r_top=0.001, n_top=1, r_bot=rb)
        for (y0, y1) in spans:
            st = [(y0, 1.0, 0.0), (y1, 1.0, 0.0)]
            if abs(y0 + hy) < 1e-6:
                st = [(y, f, 0.0) for y, f, _dz in ends] + [(y1, 1.0, 0.0)]
            if abs(y1 - hy) < 1e-6:
                st = [(y0, 1.0, 0.0)] + [(-y, f, 0.0) for y, f, _dz in reversed(ends)]
            lod.loft([ring(pts, y, f, 0.0) for y, f, _dz in st], mat=lower_m, uv=lower_uv, sel=S_("body"))
    for ay in axles:
        for sx in (-1, 1):
            arch(L, ("res0",), sx, w, ay, R, sp["wheel_r"], 0.74 if ay > 0 else 0.42, "rust", rust_band("burnt"),
                 lower_m, lower_uv)
            r1.quad([(sx * (w - 0.42), ay - R, fl), (sx * (w - 0.42), ay + R, fl), (sx * (w - 0.42), ay + R, zs),
                     (sx * (w - 0.42), ay - R, zs)], (sx, 0, 0), "rust", rust_band("burnt"))
    # ---- window pillars, rubber seals, drip rail, rub strip (Res0)
    for sx in (-1, 1):
        xo = sx * w
        for i, y in enumerate(pil):
            if sx == door_side and any(abs(y - d) < 0.66 for d in sp["doors"]):
                continue                                                          # the door leaf is the pillar there
            r0.box(*sorted((xo - sx * 0.01, xo + sx * 0.018)), y - 0.05, y + 0.05, zm - 0.04, zg + 0.03,
                   mat=upper_m, uv=upper_uv)
        for (za, zb_) in ((zm - 0.012, zm + 0.012), (zg - 0.012, zg + 0.012)):
            r0.box(*sorted((xo, xo + sx * 0.012)), pil[0], pil[-1], za, zb_, mat="paint", uv=dark)
        r0.box(*sorted((xo, xo + sx * 0.03)), -hy + 0.3, hy - 0.3, zg + 0.06, zg + 0.09, mat="metal", uv=DT.UV_STEEL)
        for (y0, y1) in spans:
            r0.box(*sorted((xo, xo + sx * 0.016)), y0 + 0.08, y1 - 0.08, 0.91, 0.95, mat="metal", uv=DT.UV_STEEL)
        if sel:                                                                     # reference: named glass faces
            q = [(sx * (w + 0.003), pil[0], zm), (sx * (w + 0.003), pil[-1], zm), (sx * (w + 0.003), pil[-1], zg),
                 (sx * (w + 0.003), pil[0], zg)]
            r0.quad(q, (sx, 0, 0), "glass", UV_GLASS, sel=["glass"])
    # ---- broken panes (wreck): dark cabin behind jagged shards
    if wreck:
        for sx in (-1, 1):
            for i in range(len(pil) - 1):
                if h01(name, "win", sx, i) >= 0.45:
                    continue
                a, b = pil[i] + 0.06, pil[i + 1] - 0.06
                x = sx * (w + 0.004)
                q = [(x, a, zm + 0.02), (x, b, zm + 0.02), (x, b, zg - 0.02), (x, a, zg - 0.02)]
                r0.quad(q, (sx, 0, 0), "paint", dark)
                x2 = sx * (w + 0.007)
                k = h01(name, "shard", sx, i)
                r0.quad([(x2, a, zm + 0.02), (x2, b, zm + 0.02), (x2, b, zm + 0.12 + 0.2 * k), (x2, a + 0.3, zm + 0.3 - 0.15 * k)],
                        (sx, 0, 0), "glassfar", UV_GLASS)
                r0.quad([(x2, b - 0.25 - 0.2 * k, zg - 0.02), (x2, b, zg - 0.02), (x2, b, zg - 0.35 - 0.2 * k)],
                        (sx, 0, 0), "glassfar", UV_GLASS)
    # ---- doors (kerb side): two-leaf folding doors, glazed; a wreck has one leaf gone
    for di, dy in enumerate(sp["doors"]):
        xo = door_side * w
        for li, (a, b) in enumerate(((dy - 0.6, dy - 0.01), (dy + 0.01, dy + 0.6))):
            gone = wreck and h01(name, "door", di, li) < 0.3
            if gone:
                r0.quad([(door_side * (w + 0.006), a, fl + 0.05), (door_side * (w + 0.006), b, fl + 0.05),
                         (door_side * (w + 0.006), b, zg), (door_side * (w + 0.006), a, zg)], (door_side, 0, 0), "paint", dark)
                continue
            r0.box(*sorted((xo - door_side * 0.01, xo + door_side * 0.022)), a, b, fl + 0.05, zg, mat=upper_m, uv=upper_uv,
                   sel=S_("door_%d" % di))
            xg = door_side * (w + 0.0235)
            for (za, zb_) in ((fl + 0.2, 0.95), (1.05, zg - 0.08)):
                r0.quad([(xg, a + 0.07, za), (xg, b - 0.07, za), (xg, b - 0.07, zb_), (xg, a + 0.07, zb_)], (door_side, 0, 0),
                        "glassfar", UV_GLASS, sel=S_("door_%d" % di))
        r1.quad([(door_side * (w + 0.01), dy - 0.6, fl + 0.05), (door_side * (w + 0.01), dy + 0.6, fl + 0.05),
                 (door_side * (w + 0.01), dy + 0.6, zg), (door_side * (w + 0.01), dy - 0.6, zg)], (door_side, 0, 0), "paint", dark)
    # ---- front: two-pane windscreen in rubber, destination box, quad headlamps, grille, bumper, wipers, mirrors
    yf = -hy
    for (xa, xb) in ((-1.0, -0.03), (0.03, 1.0)):
        broken = wreck and h01(name, "screen", xa) < 0.5
        q = [(xa, yf - 0.005, 1.3), (xb, yf - 0.005, 1.3), (xb, yf - 0.005, zg), (xa, yf - 0.005, zg)]
        r0.quad(q, (0, -1, 0), "paint" if broken else "glassfar", dark if broken else UV_GLASS, sel=S_("glass"))
        if broken:
            r0.quad([(xa, yf - 0.008, 1.3), (xb, yf - 0.008, 1.3), (xb - 0.3, yf - 0.008, 1.55), (xa, yf - 0.008, 1.75)],
                    (0, -1, 0), "glassfar", UV_GLASS)
        r1.quad(q, (0, -1, 0), "glassfar", UV_GLASS)
    for (xa, xb, za, zb_) in ((-1.02, 1.02, 1.27, 1.3), (-1.02, 1.02, zg, zg + 0.03), (-0.03, 0.03, 1.3, zg),
                              (-1.02, -1.0, 1.3, zg), (1.0, 1.02, 1.3, zg)):
        r0.box(xa, xb, yf - 0.012, yf + 0.01, za, zb_, mat="paint", uv=dark)
    r0.box(-0.75, 0.75, yf - 0.03, yf + 0.01, zg + 0.07, zg + 0.3, mat="paint", uv=dark)                 # destination box
    r0.quad([(-0.7, yf - 0.032, zg + 0.1), (0.7, yf - 0.032, zg + 0.1), (0.7, yf - 0.032, zg + 0.27), (-0.7, yf - 0.032, zg + 0.27)],
            (0, -1, 0), "glassfar", UV_GLASS)
    for sx in (-1, 1):
        for xc in (0.78, 0.98):
            rr = 0.085
            prof = [(sx * xc + rr * math.cos(2 * math.pi * k / 12), 0.8 + rr * math.sin(2 * math.pi * k / 12)) for k in range(12)]
            smashed = wreck and h01(name, "lamp", sx, xc) < 0.4
            r0.extrude_y(prof, yf - 0.03, yf + 0.01, mat="paint" if smashed else ("glassfar" if wreck else "lamp"),
                         uv=dark if smashed else UV_GLASS, sel=S_("light_front"))
        r0.box(sx * 1.05 - 0.06, sx * 1.05 + 0.06, yf - 0.02, yf + 0.01, 0.98, 1.04, mat="fair", uv=fair_band("yellow"))
    for i in range(5):                                                                 # grille slats
        z = 0.6 + i * 0.07
        r0.box(-0.45, 0.45, yf - 0.025, yf + 0.01, z, z + 0.035, mat="metal", uv=DT.UV_STEEL)
    r0.box(-0.26, 0.26, yf - 0.03, yf + 0.01, 0.98, 1.1, mat="paint", uv=DT.paint_uv("white"))          # number plate
    bump = [(0.0, 0.34), (-0.08, 0.36), (-0.12, 0.43), (-0.08, 0.51), (0.0, 0.53)]
    for (y, s_) in ((yf, 1), (hy, -1)):
        r0.extrude_x([(y + s_ * a, b) for a, b in bump], -1.15, 1.15, mat="metal", uv=DT.UV_STEEL)
        r1.box(-1.15, 1.15, min(y, y - s_ * 0.12), max(y, y - s_ * 0.12), 0.34, 0.53, mat="metal", uv=DT.UV_STEEL)
    for sx in (-1, 1):
        C.tube(r0, (sx * 0.1, yf - 0.012, 1.34), (sx * 0.85, yf - 0.012, 1.42), 0.012, "metal", DT.UV_STEEL, n=6)   # wipers
        C.tube(r0, (sx * 1.1, yf + 0.12, 2.45), (sx * 1.42, yf - 0.25, 2.4), 0.02, "metal", DT.UV_STEEL, n=8)    # mirrors
        r0.box(*sorted((sx * 1.36, sx * 1.48)), yf - 0.3, yf - 0.22, 1.9, 2.4, mat="paint", uv=dark, sel=S_("mirror"))
    # ---- rear: window, engine louvres, tail lamps
    yr = hy
    q = [(-0.8, yr + 0.005, 2.05), (0.8, yr + 0.005, 2.05), (0.8, yr + 0.005, zg), (-0.8, yr + 0.005, zg)]
    r0.quad(q, (0, 1, 0), "glassfar", UV_GLASS, sel=S_("glass"))
    r1.quad(q, (0, 1, 0), "glassfar", UV_GLASS)
    for i in range(8):
        z = 0.62 + i * 0.1
        r0.box(-0.85, 0.85, yr - 0.01, yr + 0.03, z, z + 0.045, mat=lower_m, uv=lower_uv)
    for sx in (-1, 1):
        r0.box(sx * 1.0 - 0.1, sx * 1.0 + 0.1, yr - 0.01, yr + 0.02, 0.62, 1.02, mat="fair", uv=fair_band("red"),
               sel=S_("light_rear"))
    # ---- roof: hatches, vent domes
    for yy in (-2.5, 1.5):
        r0.box(-0.42, 0.42, yy - 0.42, yy + 0.42, zh + 0.02, zh + 0.1, mat="metal", uv=DT.UV_STEEL)
    for yy in (-0.5, 3.5):
        r0.prism(0.0, yy, 0.2, zh + 0.02, zh + 0.09, n=12, mat="metal", uv=DT.UV_STEEL)
    # ---- wheels in their wells (twin rears)
    for i, ay in enumerate(axles):
        for sx in (-1, 1):
            flat = wreck and h01(name, "tyre", i, sx) < 0.6
            wl = "wheel_%d_%d" % (1 if sx < 0 else 2, i + 1)
            wheel(L, ("res0", "res1"), sx * (w - 0.05), ay, sp["wheel_r"], sx, flat, twin=ay > 0, sel=S_(wl))
    # ---- underbody (Res0): axles, exhaust, wreck rust patches on the skirt
    for ay in axles:
        r0.box(-w + 0.4, w - 0.4, ay - 0.07, ay + 0.07, 0.43, 0.57, mat="metal", uv=DT.UV_STEEL)
    C.tube(r0, (0.6, 1.0, 0.38), (0.6, 5.5, 0.38), 0.05, "metal", DT.UV_STEEL, n=8)
    if wreck:
        for i in range(8):
            sx = -1 if h01(name, "rsx", i) < 0.5 else 1
            span = spans[int(h01(name, "rss", i) * len(spans)) % len(spans)]
            ln_ = 0.4 + 0.5 * h01(name, "rsl", i)
            if span[1] - span[0] < ln_ + 0.3:
                continue
            y0 = span[0] + 0.15 + (span[1] - span[0] - ln_ - 0.3) * h01(name, "rs", i)
            if sx == door_side and any(abs(y0 + ln_ / 2 - d) < 0.9 for d in sp["doors"]):
                continue
            x = sx * (w + 0.004)
            r0.quad([(x, y0, fl + 0.08), (x, y0 + ln_, fl + 0.08), (x, y0 + ln_, 0.88), (x, y0, 0.88)], (sx, 0, 0),
                    "rust", rust_band("rust"))
    # ---- far LODs, collision (unchanged hull: body box from the floor + the wheels)
    L["res2"].lod.box(-w, w, -hy, hy, fl, top, mat=upper_m, uv=upper_uv)
    for ay in axles:                                                         # wheels (6-gon) under the body
        for sx in (-1, 1):
            prof = [(ay + 0.5 * math.cos(2 * math.pi * k / 6), 0.5 + 0.5 * math.sin(2 * math.pi * k / 6)) for k in range(6)]
            L["res2"].lod.extrude_x(prof, *sorted((sx * (w - 0.05), sx * (w - 0.35))), mat="rust", uv=rust_band("burnt"))
    for sx in (-1, 1):                                                       # glazing band (silhouette of the windows)
        x = sx * (w + 0.01)
        L["res2"].lod.quad([(x, -hy + 0.2, zm), (x, hy - 0.2, zm), (x, hy - 0.2, zg), (x, -hy + 0.2, zg)], (sx, 0, 0),
                           "glassfar", UV_GLASS)
    for y, s_ in ((-hy - 0.01, -1), (hy + 0.01, 1)):
        L["res2"].lod.quad([(-1.0, y, 1.3), (1.0, y, 1.3), (1.0, y, zg), (-1.0, y, zg)], (0, s_, 0), "glassfar", UV_GLASS)
        L["res2"].lod.box(-1.15, 1.15, min(y, y + s_ * 0.1), max(y, y + s_ * 0.1), 0.34, 0.53, mat="metal", uv=DT.UV_STEEL)
    L["res3"].lod.box(-w, w, -hy, hy, 0.0, top, mat=upper_m, uv=upper_uv)            # grounded (perf L2)
    b = (-w, w, -hy, hy, fl, top - 0.15)
    for k in ("geo", "fire", "view"):
        L[k].lod.box(*b, **kw_for(k, None, None, "metal"))
    L["shadow"].lod.box(*b)
    collide_wheels(L, axles, w, sp["wheel_r"], fl, sel, twin=lambda i, ay: ay > 0)


def collide_wheels(L, axles, w, r, fl, sel, twin=lambda i, ay: False):
    for i, ay in enumerate(axles):
        for sx in (-1, 1):
            x0_, x1_ = sorted((sx * (w - 0.05), sx * (w - 0.35)))
            c0, c1 = sorted((sx * (w - 0.05), sx * (w - (0.66 if twin(i, ay) else 0.35))))   # twin rears: both tyres
            for k in ("geo", "fire", "shadow"):                              # shadow: wheel contact (perf L3)
                L[k].lod.box(c0, c1, ay - r * 0.8, ay + r * 0.8, 0.0, max(r * 1.6, fl + 0.2),     # up to the body (D74:
                             **({"mat": "pen_metal"} if k == "fire" else {}))                     # no slit under it)
            if sel:
                wl = "wheel_%d_%d" % (1 if sx < 0 else 2, i + 1)
                mem = L["mem"].lod
                mem.point(wl + "_axis", ((x0_ + x1_) / 2 - sx * 0.2, ay, r))
                mem.point(wl + "_axis", ((x0_ + x1_) / 2 + sx * 0.2, ay, r))
                mem.point(wl + "_damper", ((x0_ + x1_) / 2, ay, r + 0.35))
                mem.point(wl + "_damper_land", ((x0_ + x1_) / 2, ay, r))


def sec_at(xc, hw, y, z0, z1, n):
    return [(xc + x, yy, z) for x, yy, z in _sec(y, hw, z0, z1, n)]


def truck_body(L, wreck, name, sel):
    sp = SPECS["GarbageTruck"]
    ln, hx, top, fl = sp["len"], sp["wid"] / 2, sp["top"], sp["floor"]
    hy = ln / 2
    S_ = (lambda s: [s] if sel else [])
    r0, r1 = L["res0"].lod, L["res1"].lod
    cab_m, cab_uv = "rust", rust_band("green")
    body_m, body_uv = "rust", rust_band("grey")
    dark = DT.paint_uv("slate")
    yb0, yb1 = -2.25, hy - 0.9                                      # compactor body
    # ---- bonnet + front wings (ZiL-like short-nose cab)
    for lod, n in ((r0, 16), (r1, 8)):
        lod.loft([sec_at(0.0, 0.58, -4.32, 0.80, 1.44, n), sec_at(0.0, 0.62, -4.28, 0.78, 1.50, n),
                  sec_at(0.0, 0.62, -3.40, 0.78, 1.53, n)], mat=cab_m, uv=cab_uv, sel=S_("body"))
        for sx in (-1, 1):
            xc = sx * 0.90
            wing = [(-4.30, 0.26, 0.66, 1.24), (-4.26, 0.28, 0.62, 1.30), (-3.86, 0.28, 0.62, 1.30),
                    (-3.84, 0.28, 1.06, 1.30), (-2.95, 0.28, 1.06, 1.28), (-2.80, 0.26, 1.10, 1.22)]
            lod.loft([sec_at(xc, hw, y, z0, z1, n) for y, hw, z0, z1 in wing], mat=cab_m, uv=cab_uv, sel=S_("body"))
    # ---- cab: raked windscreen (loft span 1-2 glazed), door windows (span 3-4)
    cab_st = [(-3.42, 1.08, 1.50, 1.66, 0.08), (-3.36, 1.10, 1.55, 1.70, 0.10), (-3.08, 1.10, 1.62, 2.62, 0.2),
              (-2.95, 1.10, 1.62, 2.62, 0.2), (-2.40, 1.10, 1.62, 2.62, 0.2), (-2.32, 1.08, 1.62, 2.60, 0.18)]
    for lod, nt in ((r0, 4), (r1, 2)):
        rings, glass = [], {}
        for y, w_, belt, zt, rt in cab_st:
            pts, seg = section(w_, 0.95, zt, belt=(belt,), r_top=rt, n_top=nt, crown=0.02)
            rings.append([(x, y, z) for x, z in pts])
        n = len(rings[0])
        for k in range(n):                                          # windscreen: every segment above the belt
            if seg(0, 1) < k < seg(0, -1):
                glass[(1, k)] = "glassfar"
        for sx in (-1, 1):
            glass[(3, seg(1, sx))] = "glassfar"                    # door windows
        lod.loft(rings, mat=cab_m, uv=cab_uv, mats=glass, sel=S_("body"))
    if sel:
        for sx in (-1, 1):
            r0.quad([(sx * 1.103, -2.95, 1.62), (sx * 1.103, -2.40, 1.62), (sx * 1.103, -2.40, 2.42), (sx * 1.103, -2.95, 2.42)],
                    (sx, 0, 0), "glass", UV_GLASS, sel=["glass"])
    # grille, headlamps, bumper, cab details
    r0.box(-0.55, 0.55, -4.345, -4.30, 0.84, 1.38, mat="paint", uv=dark)
    for i in range(9):
        x = -0.48 + i * 0.12
        r0.box(x - 0.018, x + 0.018, -4.37, -4.345, 0.87, 1.35, mat="metal", uv=DT.UV_STEEL)
    for sx in (-1, 1):
        rr = 0.11
        prof = [(sx * 0.92 + rr * math.cos(2 * math.pi * k / 14), 1.0 + rr * math.sin(2 * math.pi * k / 14)) for k in range(14)]
        smashed = wreck and h01(name, "lamp", sx) < 0.5
        r0.extrude_y(prof, -4.33, -4.27, mat="paint" if smashed else ("glassfar" if wreck else "lamp"),
                     uv=dark if smashed else UV_GLASS, sel=S_("light_front"))
        bez = [(sx * 0.92 + 0.135 * math.cos(2 * math.pi * k / 14), 1.0 + 0.135 * math.sin(2 * math.pi * k / 14)) for k in range(14)]
        r0.extrude_y(bez, -4.318, -4.26, mat="metal", uv=DT.UV_STEEL)
        r0.box(sx * 0.92 - 0.05, sx * 0.92 + 0.05, -4.31, -4.27, 0.78, 0.84, mat="fair", uv=fair_band("yellow"))   # indicator
    bump = [(-4.28, 0.48), (-4.40, 0.50), (-4.44, 0.58), (-4.40, 0.68), (-4.28, 0.70)]
    r0.extrude_x(bump, -1.22, 1.22, mat="metal", uv=DT.UV_STEEL)
    r1.box(-1.22, 1.22, -4.44, -4.28, 0.48, 0.70, mat="metal", uv=DT.UV_STEEL)
    r0.box(-0.26, 0.26, -4.42, -4.39, 0.53, 0.65, mat="paint", uv=DT.paint_uv("white"))             # number plate
    for sx in (-1, 1):
        for y in (-2.95, -2.40):                                                        # door shut lines
            r0.box(*sorted((sx * 1.098, sx * 1.106)), y - 0.006, y + 0.006, 1.0, 2.40, mat="paint", uv=dark)
        r0.box(*sorted((sx * 1.1, sx * 1.125)), -2.55, -2.45, 1.48, 1.52, mat="metal", uv=DT.UV_STEEL)      # handle
        r0.box(*sorted((sx * 0.95, sx * 1.2)), -2.95, -2.45, 0.62, 0.66, mat="metal", uv=DT.UV_STEEL)      # step
        C.tube(r0, (sx * 1.08, -3.15, 2.2), (sx * 1.42, -3.3, 2.15), 0.015, "metal", DT.UV_STEEL, n=8)
        r0.box(*sorted((sx * 1.38, sx * 1.47)), -3.34, -3.26, 1.72, 2.2, mat="paint", uv=dark, sel=S_("mirror"))
        C.tube(r0, (sx * 0.08, -3.33, 1.76), (sx * 0.52, -3.22, 2.08), 0.01, "metal", DT.UV_STEEL, n=6)  # wipers
    r0.prism(0.0, -2.85, 0.09, 2.63, 2.78, n=12, mat="glassfar" if wreck else "lamp", uv=UV_GLASS)        # beacon
    r0.prism(0.0, -2.85, 0.12, 2.62, 2.65, n=12, mat="metal", uv=DT.UV_STEEL)
    for x in (-0.35, 0.0, 0.35):
        r0.box(x - 0.05, x + 0.05, -3.1, -3.04, 2.63, 2.67, mat="fair", uv=fair_band("yellow"))           # marker lamps
    # ---- compactor body: rounded top edges, ribs, sills; hopper with the loading mouth and lift rams
    for lod, nt in ((r0, 3), (r1, 1)):
        pts, _seg = section(1.30, 1.02, top, r_top=0.12, n_top=nt)
        lod.loft([ring(pts, y) for y in (yb0, yb1)], mat=body_m, uv=body_uv, sel=S_("body"))
    for sx in (-1, 1):
        xo = sx * 1.30
        for i in range(10):
            y = yb0 + 0.3 + i * (yb1 - yb0 - 0.6) / 9
            r0.box(*sorted((xo - sx * 0.01, xo + sx * 0.045)), y - 0.035, y + 0.035, 1.05, top - 0.12, mat=body_m, uv=body_uv)
        r0.box(*sorted((xo - sx * 0.01, xo + sx * 0.05)), yb0, yb1, 1.02, 1.12, mat="metal", uv=DT.UV_STEEL)
        r0.box(*sorted((xo - sx * 0.01, xo + sx * 0.04)), yb0, yb1, top - 0.14, top - 0.08, mat="metal", uv=DT.UV_STEEL)
    hop = [(yb1, 0.85), (hy, 0.85), (hy, 2.0), (hy - 0.35, 2.95), (yb1, 3.2)]
    for lod in (r0, r1):
        lod.extrude_x(hop, -1.18, 1.18, mat=body_m, uv=body_uv, sel=S_("body"))
    r0.box(-1.12, 1.12, hy - 0.02, hy + 0.06, 0.85, 1.0, mat="metal", uv=DT.UV_STEEL)                 # loading sill
    r0.quad([(-1.0, hy + 0.005, 1.02), (1.0, hy + 0.005, 1.02), (1.0, hy + 0.005, 1.9), (-1.0, hy + 0.005, 1.9)],
            (0, 1, 0), "trash" if wreck else "paint", UV_TRASH if wreck else dark)                     # packer mouth
    for (xa, xb, za, zb_) in ((-1.12, -1.0, 1.0, 1.92), (1.0, 1.12, 1.0, 1.92), (-1.12, 1.12, 1.9, 2.0)):
        r0.box(xa, xb, hy - 0.02, hy + 0.05, za, zb_, mat="metal", uv=DT.UV_STEEL)
    for sx in (-1, 1):
        C.tube(r0, (sx * 1.24, yb1 + 0.08, 1.0), (sx * 1.24, hy - 0.45, 2.75), 0.055, "metal", DT.UV_STEEL, n=10)
        C.tube(r0, (sx * 1.24, hy - 0.62, 2.25), (sx * 1.24, hy - 0.45, 2.75), 0.03, "metal", DT.UV_STEEL, n=8)
        r0.box(sx * 1.05 - 0.1, sx * 1.05 + 0.1, hy + 0.06, hy + 0.08, 0.58, 0.7, mat="fair", uv=fair_band("red"),
               sel=S_("light_rear"))
        r0.box(*sorted((sx * 0.95, sx * 1.2)), 3.13, 3.15, 0.22, 0.85, mat="rust", uv=rust_band("burnt"))   # mudflaps
    r0.box(-1.2, 1.2, hy - 0.1, hy + 0.06, 0.55, 0.7, mat="metal", uv=DT.UV_STEEL)                     # rear step bumper
    # ---- chassis (Res0): rails, subframe, fuel tank, battery box, exhaust
    for sx in (-1, 1):
        r0.box(*sorted((sx * 0.45, sx * 0.56)), -4.2, hy - 0.1, 0.56, 0.76, mat="metal", uv=DT.UV_STEEL)
        r0.box(*sorted((sx * 0.56, sx * 0.76)), yb0, yb1, 0.76, 1.02, mat="metal", uv=DT.UV_STEEL)
    tank = [(-0.85 + 0.24 * math.cos(2 * math.pi * k / 12), 0.55 + 0.24 * math.sin(2 * math.pi * k / 12)) for k in range(12)]
    r0.extrude_y(tank, -2.2, -1.3, mat=cab_m, uv=cab_uv)
    r0.box(0.62, 1.1, -2.2, -1.6, 0.42, 0.74, mat="rust", uv=rust_band("slate"))
    C.tube(r0, (0.35, -3.0, 0.5), (0.35, 0.6, 0.45), 0.045, "metal", DT.UV_STEEL, n=8)
    for ay in sp["axles"]:
        r0.box(-0.85, 0.85, ay - 0.07, ay + 0.07, 0.43, 0.57, mat="metal", uv=DT.UV_STEEL)
    # ---- wheels (single front, twin rears) + wreck dressing
    for i, ay in enumerate(sp["axles"]):
        for sx in (-1, 1):
            flat = wreck and h01(name, "tyre", i, sx) < 0.6
            wl = "wheel_%d_%d" % (1 if sx < 0 else 2, i + 1)
            wheel(L, ("res0", "res1"), sx * (hx - 0.03 if i else 1.12), ay, sp["wheel_r"], sx, flat, twin=i > 0, sel=S_(wl))
    if wreck:
        for i in range(6):                                                 # rust runs between the ribs
            sx = -1 if h01(name, "rsx", i) < 0.5 else 1
            k = int(h01(name, "rsk", i) * 9)
            y0 = yb0 + 0.3 + k * (yb1 - yb0 - 0.6) / 9 + 0.06
            y1 = y0 + (yb1 - yb0 - 0.6) / 9 - 0.12
            x = sx * 1.304
            zt_ = 1.6 + 1.2 * h01(name, "rsz", i)
            r0.quad([(x, y0, 1.14), (x, y1, 1.14), (x, y1, zt_), (x, y0, zt_)], (sx, 0, 0), "rust", rust_band("rust"))
        for i in range(6):
            bx = -1.2 + 2.4 * h01(name, "bag", i)
            by = hy + 0.3 + 0.9 * h01(name, "bagy", i)
            rr = 0.25 + 0.15 * h01(name, "bagr", i)
            r0.prism(bx, by, rr, 0.0, min(0.22, rr * 0.7), n=8, mat="trash", uv=UV_TRASH)   # slumped bags: <= 22 cm
            # high, too low to hide a head in (D79 concealment gate); render only, no slits or footprint creep
        L["mem"].lod.point("search", (0.0, hy + 0.9, 0.0))
    # ---- far LODs + collision following the new shapes (sec: every drawn volume has collision and Fire)
    cab_prof = [(-3.42, 0.9), (-2.30, 0.9), (-2.30, 2.64), (-3.08, 2.64), (-3.42, 1.68)]   # down to the wheel boxes (D74)
    for lod in (L["res2"].lod,):
        lod.box(-1.18, 1.18, -4.32, -3.42, 0.62, 1.30, mat=cab_m, uv=cab_uv)
        lod.extrude_x(cab_prof, -1.1, 1.1, mat=cab_m, uv=cab_uv)
        lod.box(-1.30, 1.30, yb0, yb1, 1.02, top, mat=body_m, uv=body_uv)
        lod.extrude_x(hop, -1.18, 1.18, mat=body_m, uv=body_uv)
        lod.box(-0.8, 0.8, -4.0, 3.9, 0.3, 1.02, mat="rust", uv=rust_band("burnt"))     # chassis
        for i, ay in enumerate(sp["axles"]):                                 # wheels (perf M1: no Res1 -> Res2 pop)
            for sx in (-1, 1):
                prof = [(ay + 0.5 * math.cos(2 * math.pi * k / 6), 0.5 + 0.5 * math.sin(2 * math.pi * k / 6)) for k in range(6)]
                xo = sx * (hx - 0.03 if i else 1.12)
                lod.extrude_x(prof, *sorted((xo, xo - sx * (0.61 if i else 0.3))), mat="rust", uv=rust_band("burnt"))
    L["res3"].lod.box(-hx, hx, -hy, hy, 0.0, top, mat=body_m, uv=body_uv)
    for k in ("geo", "fire", "view", "shadow"):
        kw = kw_for(k, None, None, "metal") if k != "shadow" else {}
        g = L[k].lod
        g.box(-1.18, 1.18, -4.32, -3.42, 0.62, 1.30, **kw)                 # wings + bonnet front
        g.box(-0.62, 0.62, -4.30, -3.42, 1.30, 1.52, **kw)                 # bonnet top
        g.extrude_x(cab_prof, -1.1, 1.1, **kw)                               # cab (raked windscreen)
        g.box(-hx - 0.05, hx + 0.05, -2.30, yb1, fl + 0.2, top, **kw)        # D74: no slit behind the cab
        g.extrude_x([(y, max(z, fl)) for y, z in hop], -1.18, 1.18, **kw)  # hopper
        if k != "view":                                                    # fuel tank + battery box up to the body
            g.box(-1.1, -0.6, -2.2, -1.3, 0.31, fl + 0.2, **kw)           # (D79: no drawn volume without collision)
            g.box(0.62, 1.1, -2.2, -1.6, 0.42, fl + 0.2, **kw)
    collide_wheels(L, sp["axles"], hx - 0.03, sp["wheel_r"], fl, sel, twin=lambda i, ay: i > 0)


def body(L, kind, wreck, name, sel=False):
    """Parametric body into the RLod dict L (Res0..Res3, Geometry, Fire, View, Shadow, Memory). D97: lofted bodies
    (rounded roofs, wraparound glazing, real wheel wells, fascia detail); collision follows the drawn shapes."""
    (bus_body if kind == "CityBus" else truck_body)(L, wreck, name, sel)
    L["mem"].lod.point("center", (0.0, 0.0, 0.0))


def build_wreck(kind):
    name = "Wreck_" + kind
    L = C.city_lods(C.Ruin(name, 0))
    body(L, kind, True, name)
    return C._finish(L, 9000.0 if kind == "GarbageTruck" else 11000.0)


def build_reference(kind):
    """Intact body with the spec's selection / memory names (VEHICLE_SPEC.md) - modeller reference only."""
    name = "Ref_" + kind
    L = C.city_lods(C.Ruin(name, 0))
    body(L, kind, False, name, sel=True)
    return [L[k].lod for k in ("res0", "res1", "res2", "res3", "mem")]


BUILDERS = {"Wreck_CityBus": lambda: build_wreck("CityBus"), "Wreck_GarbageTruck": lambda: build_wreck("GarbageTruck")}


def modules():
    return {n: (BUILDERS[n], e["pbo"], e["p3d"]) for n, e in S.KIT.items() if n in BUILDERS}


def write_references(out):
    os.makedirs(out, exist_ok=True)
    for kind in SPECS:
        path = os.path.join(out, "sky_ref_%s.p3d" % kind.lower())
        print("REFERENCE", path, export_p3d(build_reference(kind), KIT_MATS, path))


if __name__ == "__main__":
    if "--reference" in sys.argv:
        write_references(sys.argv[sys.argv.index("--reference") + 1])
    else:
        run_cli(modules(), KIT_MATS, "build_stats_vehicles.json")
