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
from build_kit import KIT_MATS  # noqa: E402
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
    "CityBus": {"len": 11.4, "wid": 2.5, "top": 3.0, "floor": 0.45, "cab": 0.0, "axles": (-3.0, 2.8),
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


def wheel(lod, x0, x1, y, r, n=10, flat=False, mat="paint", uv=None, sel=()):
    """Tyre + rim as an n-gon extruded along X; a flat tyre is squashed at the bottom."""
    prof = []
    for k in range(n):
        a = 2 * math.pi * (k + 0.5) / n
        z = r + r * math.sin(a)
        if flat:
            z = max(z, r * 0.25)
        prof.append((y + r * math.cos(a), z))
    lod.extrude_x(prof, x0, x1, mat=mat, uv=uv or DT.paint_uv("slate"), sel=list(sel))


def body(L, kind, wreck, name, sel=False):
    """Parametric body into the RLod dict L (Res0..Res3, Geometry, Fire, View, Shadow, Memory)."""
    sp = SPECS[kind]
    ln, wd, top, fl = sp["len"], sp["wid"], sp["top"], sp["floor"]
    hy, hx = ln / 2, wd / 2
    pmat, puv = uv_of(sp["paint"])
    if wreck:                                                  # sun-faded, rust bleeding through
        pmat, puv = ("rust", rust_band("grey")) if kind == "GarbageTruck" else ("fair", fair_band("yellow"))
    tmat, tuv = uv_of(sp["trim"])
    S_ = (lambda s: [s] if sel else [])
    # ---- main volumes (Res + collision): bus = one box with a rounded roof edge; truck = cab + body
    vols = []
    if sp["cab"]:
        cy1 = -hy + sp["cab"]
        vols.append(("cab", (-hx, hx, -hy, cy1, fl, 2.9)))
        vols.append(("body", (-hx - 0.05, hx + 0.05, cy1 + 0.15, hy - 0.9, fl + 0.2, top)))
        vols.append(("hopper", (-hx + 0.1, hx - 0.1, hy - 0.9, hy, fl, top - 0.8)))
    else:
        vols.append(("body", (-hx, hx, -hy, hy, fl, top - 0.15)))
    for vname, b in vols:
        m_, u_ = (tmat, tuv) if vname == "cab" else (pmat, puv)
        for k in ("res0", "res1", "res2", "geo", "fire", "view"):
            L[k].lod.box(*b, **dict(kw_for(k, m_, u_, "metal"), sel=S_("body") if k.startswith("res") else []))
        L["shadow"].lod.box(*b)
    L["res3"].lod.box(-hx, hx, -hy, hy, fl, top, mat=pmat, uv=puv)
    if not sp["cab"]:                                         # bus roof: chamfered crown + hatches + vents
        for k in ("res0", "res1"):
            L[k].lod.solid([(-hx, -hy, top - 0.15), (hx, -hy, top - 0.15), (-hx + 0.25, -hy, top), (hx - 0.25, -hy, top),
                            (-hx, hy, top - 0.15), (hx, hy, top - 0.15), (-hx + 0.25, hy, top), (hx - 0.25, hy, top)],
                           [(0, 1, 3, 2), (4, 5, 7, 6), (0, 2, 6, 4), (1, 3, 7, 5), (2, 3, 7, 6), (0, 1, 5, 4)], tmat, tuv)
        for yy in (-2.5, 1.5):
            L["res0"].lod.box(-0.45, 0.45, yy - 0.45, yy + 0.45, top, top + 0.08, mat="metal", uv=DT.UV_STEEL)
    # ---- window bands (glass sits 2 cm proud of the side; broken = gaps + shards)
    zw0, zw1 = (fl + 1.15, top - 0.45) if not sp["cab"] else (1.75, 2.6)
    ys = ([(-hy + 0.3, hy - 0.4)] if not sp["cab"] else [(-hy + 0.2, -hy + sp["cab"] - 0.25)])
    for sx in (-1, 1):
        for (y0, y1) in ys:
            n = max(1, int((y1 - y0) / 1.25))
            for i in range(n):
                a, b = y0 + i * (y1 - y0) / n + 0.06, y0 + (i + 1) * (y1 - y0) / n - 0.06
                broken = wreck and h01(name, "win", sx, i) < 0.45
                if broken:
                    L["res0"].lod.quad([(sx * (hx + 0.005), a, zw0), (sx * (hx + 0.005), b, zw0), (sx * (hx + 0.005), b, zw0 + 0.25),
                                        (sx * (hx + 0.005), a, zw0 + 0.12)], (sx, 0, 0), "glassfar", UV_GLASS)
                    L["res0"].lod.quad([(sx * (hx + 0.003), a, zw0), (sx * (hx + 0.003), b, zw0), (sx * (hx + 0.003), b, zw1),
                                        (sx * (hx + 0.003), a, zw1)], (sx, 0, 0), "paint", DT.paint_uv("slate"))
                else:
                    L["res0"].lod.quad([(sx * (hx + 0.02), a, zw0), (sx * (hx + 0.02), b, zw0), (sx * (hx + 0.02), b, zw1),
                                        (sx * (hx + 0.02), a, zw1)], (sx, 0, 0), "glass" if not wreck else "glassfar", UV_GLASS,
                                       sel=S_("glass"))
                L["res0"].lod.box(sx * hx - 0.03 * (sx < 0), sx * hx + 0.03 * (sx > 0), b, b + 0.12, zw0 - 0.05, zw1 + 0.05,
                                  mat="metal", uv=DT.UV_STEEL)                                       # pillars
            L["res1"].lod.quad([(sx * (hx + 0.02), y0, zw0), (sx * (hx + 0.02), y1, zw0), (sx * (hx + 0.02), y1, zw1),
                                (sx * (hx + 0.02), y0, zw1)], (sx, 0, 0), "glassfar", UV_GLASS)
    # windscreen + rear window
    zf0, zf1 = (fl + 0.9, top - 0.35) if not sp["cab"] else (1.6, 2.7)
    L["res0"].lod.quad([(-hx + 0.15, -hy - 0.02, zf0), (hx - 0.15, -hy - 0.02, zf0), (hx - 0.15, -hy - 0.02, zf1),
                        (-hx + 0.15, -hy - 0.02, zf1)], (0, -1, 0), "glassfar" if wreck else "glass", UV_GLASS, sel=S_("glass"))
    L["res1"].lod.quad([(-hx + 0.15, -hy - 0.02, zf0), (hx - 0.15, -hy - 0.02, zf0), (hx - 0.15, -hy - 0.02, zf1),
                        (-hx + 0.15, -hy - 0.02, zf1)], (0, -1, 0), "glassfar", UV_GLASS)
    for sx in (-1, 1):                                                                            # wipers, mirrors
        L["res0"].lod.box(sx * 0.4 - 0.4, sx * 0.4 + 0.4, -hy - 0.04, -hy - 0.03, zf0 + 0.05, zf0 + 0.08, mat="metal", uv=DT.UV_STEEL)
        C.bar(L["res0"].lod, (sx * hx, -hy + 0.2, zf1 - 0.2), (sx * (hx + 0.35), -hy + 0.1, zf1 - 0.25), 0.015, "metal", DT.UV_STEEL)
        L["res0"].lod.box(sx * (hx + 0.3) - 0.06, sx * (hx + 0.3) + 0.06, -hy + 0.05, -hy + 0.15, zf1 - 0.65, zf1 - 0.2,
                          mat="paint", uv=DT.paint_uv("slate"), sel=S_("mirror"))
    # bumpers, lamps, grille, number plate
    for (yb, ff) in ((-hy, -1), (hy, 1)):
        L["res0"].lod.box(-hx + 0.05, hx - 0.05, yb + ff * 0.0 - (0.12 if ff < 0 else 0), yb + (0.12 if ff > 0 else 0), fl, fl + 0.3,
                          mat="metal", uv=DT.UV_STEEL)
        for sx in (-1, 1):
            lamp_m = "lamp" if not wreck else "glassfar"
            L["res0"].lod.box(sx * (hx - 0.35) - 0.14, sx * (hx - 0.35) + 0.14, yb - 0.02 * (ff < 0), yb + 0.02 * (ff > 0),
                              fl + 0.45, fl + 0.65, mat=lamp_m if ff < 0 else "fair", uv=fair_band("red") if ff > 0 else None,
                              sel=S_("light_front" if ff < 0 else "light_rear"))
    L["res0"].lod.box(-0.26, 0.26, -hy - 0.02, -hy, fl + 0.32, fl + 0.44, mat="paint", uv=DT.paint_uv("white"))
    # doors (bus: 3 folding doors on the +X side, dark gaps), cab doors (truck)
    for dy in sp["doors"]:
        L["res0"].lod.quad([(hx + 0.025, dy - 0.6, fl + 0.05), (hx + 0.025, dy + 0.6, fl + 0.05), (hx + 0.025, dy + 0.6, top - 0.4),
                            (hx + 0.025, dy - 0.6, top - 0.4)], (1, 0, 0), "paint", DT.paint_uv("slate"),
                           sel=S_("door_%d" % sp["doors"].index(dy)))
    if sp["cab"]:
        for sx in (-1, 1):
            L["res0"].lod.quad([(sx * (hx + 0.01), -hy + 0.5, 0.9), (sx * (hx + 0.01), -hy + 1.6, 0.9),
                                (sx * (hx + 0.01), -hy + 1.6, 1.7), (sx * (hx + 0.01), -hy + 0.5, 1.7)], (sx, 0, 0), tmat, tuv,
                               sel=S_("door_driver" if sx < 0 else "door_codriver"))
        L["res0"].lod.box(-hx + 0.3, hx - 0.3, -hy - 0.1, -hy, 0.9, 1.4, mat="metal", uv=DT.UV_STEEL)          # grille
    # wheels on axles (twin rears on the bus and the truck's rear axles)
    r = sp["wheel_r"]
    for i, ay in enumerate(sp["axles"]):
        for sx in (-1, 1):
            flat = wreck and h01(name, "tyre", i, sx) < 0.6
            x_out = sx * (hx - 0.02)
            x0_, x1_ = sorted((x_out, x_out - sx * 0.32))
            wl = ("wheel_%d_%d" % (1 if sx < 0 else 2, i + 1))
            wheel(L["res0"].lod, x0_, x1_, ay, r, 12, flat, sel=S_(wl))
            wheel(L["res1"].lod, x0_, x1_, ay, r, 6, flat)
            L["res0"].lod.extrude_x([(ay + r * 0.5 * math.cos(2 * math.pi * k / 8), r + r * 0.5 * math.sin(2 * math.pi * k / 8))
                                     for k in range(8)], *sorted((x_out + sx * 0.005, x_out - sx * 0.02)),
                                    mat="metal", uv=DT.UV_STEEL, sel=S_(wl))                          # hub
            for k in ("geo", "fire"):
                L[k].lod.box(x0_, x1_, ay - r * 0.8, ay + r * 0.8, 0.0 if not flat else 0.0, r * 1.6,
                             **({"mat": "pen_metal"} if k == "fire" else {}))
            if sel:
                mem = L["mem"].lod
                mem.point(wl + "_axis", ((x0_ + x1_) / 2 - sx * 0.2, ay, r))
                mem.point(wl + "_axis", ((x0_ + x1_) / 2 + sx * 0.2, ay, r))
                mem.point(wl + "_damper", ((x0_ + x1_) / 2, ay, r + 0.35))
                mem.point(wl + "_damper_land", ((x0_ + x1_) / 2, ay, r))
    # underbody (Res0): chassis rails, exhaust, fuel tank
    for sx in (-0.55, 0.55):
        L["res0"].lod.box(sx - 0.07, sx + 0.07, -hy + 0.4, hy - 0.4, 0.42, fl, mat="metal", uv=DT.UV_STEEL)
    L["res0"].lod.box(hx - 0.7, hx - 0.15, -0.4, 0.6, 0.35, fl, mat="metal", uv=DT.UV_STEEL)
    # wreck dressing: rust streaks, dents, a missing panel, bags (truck)
    if wreck:
        for i in range(6):
            yy = -hy + 0.6 + (ln - 1.2) * h01(name, "rs", i)
            sx = -1 if h01(name, "rsx", i) < 0.5 else 1
            L["res0"].lod.quad([(sx * (hx + 0.03), yy - 0.3, fl + 0.1), (sx * (hx + 0.03), yy + 0.3, fl + 0.1),
                                (sx * (hx + 0.03), yy + 0.3, fl + 1.0), (sx * (hx + 0.03), yy - 0.3, fl + 1.0)], (sx, 0, 0),
                               "rust", rust_band("rust"))
        if kind == "GarbageTruck":
            L["res0"].lod.box(-1.0, 1.0, hy - 0.05, hy, fl + 0.1, fl + 0.9, mat="trash", uv=UV_TRASH)
            for i in range(6):
                bx = -1.2 + 2.4 * h01(name, "bag", i)
                by = hy + 0.3 + 0.9 * h01(name, "bagy", i)
                rr = 0.25 + 0.15 * h01(name, "bagr", i)
                L["res0"].lod.prism(bx, by, rr, 0.0, rr * 1.2, n=8, mat="trash", uv=UV_TRASH)
            L["mem"].lod.point("search", (0.0, hy + 0.9, 0.0))
        else:
            for i in range(4):                                                                     # seats seen through the gaps
                yy = -hy + 2.0 + i * 2.2
                L["res0"].lod.box(-hx + 0.2, -hx + 0.75, yy - 0.25, yy + 0.25, fl + 0.4, fl + 1.2, mat="fabric",
                                  uv=UVBand(S.MATERIALS["fabric"]["bands"]["blue"], 1.0))
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
