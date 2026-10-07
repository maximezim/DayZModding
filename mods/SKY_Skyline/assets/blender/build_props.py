"""Generator for SKY interior props (batch 3) - run headless in Blender 4.2.

    blender -b --factory-startup -P build_props.py -- --out <mods/SKY_Skyline/addons> [--only Locker,Desk]

Same pipeline as build_kit.py. Openable parts (locker doors, vending flap,
extinguisher-cabinet door) are vanilla building Doors: bone + Geometry/View/Fire
component + memory `<name>_axis` (2 pts), `<name>_action`, `<name>` - exactly the
pattern of Bohemia's Test_Building. Their swing comes from skyspec.DOOR_SWING_SIGN
(unverified, P1) via gen_configs.py.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import skyspec as S  # noqa: E402
from build_kit import KIT_MATS, finish, props_lods  # noqa: E402
from build_towera import UV_ALU, UV_GLASS, UV_STEEL  # noqa: E402
from skygeo import UVBand, UVRect, UVWorld, run_cli  # noqa: E402

B_WOOD = S.MATERIALS["wood"]["bands"]
UV_OAK, UV_WALNUT, UV_LAMINATE = (UVBand(B_WOOD[k], 1.5) for k in ("oak", "walnut", "laminate"))
UV_SCREEN = UVBand(B_WOOD["screen"], 1.0)
B_FAB = S.MATERIALS["fabric"]["bands"]
UV_FGREY, UV_FBLUE, UV_FBEIGE = (UVBand(B_FAB[k], 1.0) for k in ("grey", "blue", "beige"))
B_RUST = S.MATERIALS["rust"]["bands"]
UV_PAINT = UVBand(S.MATERIALS["metal"]["bands"]["painted"], 1.0)


def face_atlas(L, keys, cell, x0, x1, z0, z1, y, facing=(0, -1, 0)):
    uv = UVRect(0, 2, (x0, z0), (x1, z1), S.atlas_uv(cell))
    for k in keys:
        L[k].quad([(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)], facing, "atlas", uv)


def face_screen(L, keys, x0, x1, z0, z1, y, facing=(0, -1, 0)):
    """Monitor screen on the wood sheet's screen band: no extra section (perf batch-3 L1)."""
    for k in keys:
        L[k].quad([(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)], facing, "wood", UV_SCREEN)


def solid(L, keys, box, vis, pen, sel=()):
    for k in keys:
        if k.startswith("res"):
            L[k].box(*box, sel=sel, **vis)
        elif k == "fire":
            L[k].box(*box, mat="pen_" + pen, sel=sel)
        else:
            L[k].box(*box, sel=sel)


ALL = ("res0", "res1", "res2", "geo", "fire")
NEAR = ("res0", "res1")


def hinged_door(L, name, box, hinge, axis_dir, action, vis, pen):
    """Door leaf as bone `name` in Res0/Res1/Geometry/View/Fire + memory points."""
    keys = ("res0", "res1", "geo", "fire") + (("view",) if "view" in L else ())
    solid(L, keys, box, vis, pen, sel=[name])
    hx, hy, hz0, hz1 = hinge
    if axis_dir == "z":
        L["mem"].point(name + "_axis", (hx, hy, hz0))
        L["mem"].point(name + "_axis", (hx, hy, hz1))
    else:                               # horizontal hinge along X (flaps)
        L["mem"].point(name + "_axis", (hz0, hx, hy))
        L["mem"].point(name + "_axis", (hz1, hx, hy))
    L["mem"].point(name + "_action", action)
    cx, cy, cz = [(box[0] + box[1]) / 2, (box[2] + box[3]) / 2, (box[4] + box[5]) / 2]
    L["mem"].point(name, (cx, cy, cz))


# ------------------------------------------------------------------ furniture
def build_reception_desk():
    L = props_lods(view=True)
    wood, met = {"mat": "wood", "uv": UV_WALNUT}, {"mat": "metal", "uv": UV_PAINT}
    solid(L, ALL, (-1.5, 1.5, -0.4, 0.4, 0.0, 1.05), wood, "wood")                 # front counter
    solid(L, ALL, (1.5, 2.3, -0.4, 1.2, 0.0, 0.75), wood, "wood")                  # return
    solid(L, NEAR + ("geo", "fire"), (-1.55, 1.55, -0.5, 0.45, 1.05, 1.1), met, "metal")   # transaction top (loot surface)
    L["view"].box(-1.5, 1.5, -0.4, 0.4, 0.0, 1.05)
    face_screen(L, ("res0",), -0.3, 0.3, 1.1, 1.45, 0.2, (0, 1, 0))
    return finish(L, 300.0)


def build_desk():
    L = props_lods()
    lam, met = {"mat": "wood", "uv": UV_LAMINATE}, {"mat": "metal", "uv": UV_PAINT}
    solid(L, ALL, (-0.8, 0.8, -0.4, 0.4, 0.72, 0.75), lam, "wood")                  # top
    for x in (-0.78, 0.76):
        solid(L, ("res0", "res1", "geo", "fire"), (x, x + 0.02, -0.38, 0.38, 0.0, 0.72), met, "metal")
    solid(L, ("res0",), (-0.76, 0.76, 0.3, 0.32, 0.25, 0.72), met, "metal")          # modesty panel
    solid(L, ("res0",), (-0.25, 0.25, 0.1, 0.15, 0.75, 1.1), met, "metal")          # monitor body
    face_screen(L, ("res0",), -0.24, 0.24, 0.77, 1.08, 0.099)
    return finish(L, 60.0, shadow=False)                    # interior_small (perf batch-3 M3)


def build_cubicle():
    """2 x 2 m workstation: 3 fabric screens (1.4 m) + L-shaped desk."""
    L = props_lods(view=True)
    fab, lam = {"mat": "fabric", "uv": UV_FGREY}, {"mat": "wood", "uv": UV_LAMINATE}
    screens = [(-1.0, 1.0, 0.95, 1.0), (-1.0, -0.95, -1.0, 1.0), (0.95, 1.0, -1.0, 1.0)]
    for (x0, x1, y0, y1) in screens:
        solid(L, ("res0", "res1", "res2", "geo", "fire", "view"), (x0, x1, y0, y1, 0.0, 1.4), fab, "wood")
    NEAR_COL = ("res0", "res1", "geo", "fire")                                 # Res2 = screens only (perf L2)
    solid(L, NEAR_COL, (-0.95, 0.95, 0.25, 0.95, 0.72, 0.75), lam, "wood")
    solid(L, NEAR_COL, (-0.95, -0.35, -0.95, 0.25, 0.72, 0.75), lam, "wood")
    face_screen(L, ("res0",), -0.25, 0.25, 0.77, 1.08, 0.7)
    return finish(L, 120.0)


def build_server_rack():
    L = props_lods(view=True)
    dark = {"mat": "rust", "uv": UVBand(B_RUST["burnt"], 1.0)}
    solid(L, ("res0", "res1", "res2", "geo", "fire", "view"), (-0.3, 0.3, -0.5, 0.5, 0.0, 2.0), dark, "metal")
    face_atlas(L, ("res0", "res1"), "rack", -0.28, 0.28, 0.05, 1.95, -0.501)
    return finish(L, 250.0, hull=True)


def build_vending():
    L = props_lods(view=True, mem=True)
    paint = {"mat": "rust", "uv": UVBand(B_RUST["grey"], 1.0)}
    solid(L, ("res0", "res1", "res2", "geo", "fire", "view"), (-0.5, 0.5, -0.4, 0.4, 0.0, 1.9), paint, "metal")
    face_atlas(L, ("res0", "res1", "res2"), "vending", -0.48, 0.48, 0.45, 1.85, -0.401)
    # pickup flap: bottom hinge along X at z = 0.15, swings outward/down (P1 sign)
    hinged_door(L, "flap", (-0.35, 0.35, -0.43, -0.41, 0.15, 0.4), (-0.42, 0.15, -0.35, 0.35), "x",
                (0.0, -0.8, 0.3), {"mat": "metal", "uv": UV_STEEL}, "metal")
    return finish(L, 300.0, hull=True)


def build_locker():
    """Bank of 3 lockers (0.3 m each), doors hinged on their left edge."""
    L = props_lods(view=True, mem=True)
    paint = {"mat": "rust", "uv": UVBand(B_RUST["grey"], 1.0)}
    # carcass: back, sides, top, bottom, shelves (open front)
    for b in ((-0.45, 0.45, 0.22, 0.25, 0.0, 1.8), (-0.45, -0.43, -0.25, 0.25, 0.0, 1.8),
              (0.43, 0.45, -0.25, 0.25, 0.0, 1.8), (-0.45, 0.45, -0.25, 0.25, 1.78, 1.8),
              (-0.45, 0.45, -0.25, 0.25, 0.0, 0.05)):
        solid(L, ("res0", "res1", "geo", "fire", "view"), b, paint, "metal")
    for x in (-0.15, 0.15):
        solid(L, ("res0", "res1", "geo", "fire"), (x - 0.01, x + 0.01, -0.24, 0.22, 0.05, 1.78), paint, "metal")
    solid(L, ("res0", "geo", "fire"), (-0.43, 0.43, -0.24, 0.22, 1.45, 1.47), paint, "metal")   # shelf (loot surface, QA L1)
    L["res2"].box(-0.45, 0.45, -0.25, 0.25, 0.0, 1.8, **paint)
    for i, x0 in enumerate((-0.45, -0.15, 0.15)):
        hinged_door(L, "locker_door%d" % (i + 1), (x0 + 0.005, x0 + 0.295, -0.27, -0.25, 0.06, 1.77),
                    (x0 + 0.005, -0.26, 0.06, 1.77), "z", (x0 + 0.15, -0.7, 1.1), paint, "metal")
    return finish(L, 120.0, hull=True)


def build_sofa():
    L = props_lods()
    fab = {"mat": "fabric", "uv": UV_FBLUE}
    solid(L, ALL, (-1.0, 1.0, -0.45, 0.45, 0.0, 0.42), fab, "wood")                  # base + seat
    solid(L, ALL, (-1.0, 1.0, 0.25, 0.45, 0.42, 0.85), fab, "wood")                  # back
    for x in (-1.0, 0.82):
        solid(L, ("res0", "res1", "geo", "fire"), (x, x + 0.18, -0.45, 0.25, 0.42, 0.62), fab, "wood")
    for x in (-0.95, 0.0):
        solid(L, ("res0",), (x + 0.02, x + 0.93, -0.43, 0.23, 0.42, 0.5), fab, "wood")   # cushions
    return finish(L, 60.0, shadow=False)                    # interior_small (perf batch-3 M3)


def build_bed():
    L = props_lods()
    wood, fab = {"mat": "wood", "uv": UV_OAK}, {"mat": "fabric", "uv": UV_FBEIGE}
    solid(L, ALL, (-0.7, 0.7, -1.0, 1.0, 0.0, 0.3), wood, "wood")                    # frame
    solid(L, ALL, (-0.68, 0.68, -0.98, 1.0, 0.3, 0.5), fab, "wood")                  # mattress (to the headboard, D74)
    solid(L, ("res0", "res1", "geo", "fire"), (-0.75, 0.75, 1.0, 1.06, 0.0, 1.0), wood, "wood")   # headboard
    solid(L, ("res0",), (-0.55, 0.55, 0.55, 0.9, 0.5, 0.62), fab, "wood")            # pillow
    return finish(L, 80.0, shadow=False)


def build_kitchenette():
    L = props_lods(view=True)
    lam, met = {"mat": "wood", "uv": UV_LAMINATE}, {"mat": "metal", "uv": UV_ALU}
    solid(L, ("res0", "res1", "res2", "geo", "fire", "view"), (-1.2, 0.6, -0.3, 0.3, 0.0, 0.88), lam, "wood")
    solid(L, NEAR + ("geo", "fire"), (-1.22, 0.6, -0.32, 0.3, 0.88, 0.92), met, "metal")   # worktop (loot surface)
    solid(L, ("res0",), (-0.9, -0.4, -0.25, 0.2, 0.8, 0.88), met, "metal")             # sink basin
    solid(L, ("res0", "res1", "geo", "fire"), (-1.2, 0.6, 0.0, 0.3, 1.5, 2.2), lam, "wood")   # upper cabinets
    solid(L, ("res0", "res1", "res2", "geo", "fire", "view"), (0.6, 1.2, -0.3, 0.3, 0.0, 1.9), met, "metal")  # fridge
    face_atlas(L, ("res0", "res1"), "appliance", 0.62, 1.18, 0.02, 1.88, -0.301)
    return finish(L, 150.0, hull=True)


def build_extinguisher_cabinet():
    """Wall cabinet (back at y = 0) with glass door hinged on the left edge."""
    L = props_lods(mem=True)
    red = {"mat": "atlas", "uv": UVRect(0, 2, (-0.2, 0.0), (0.2, 0.7), S.atlas_uv("extinguisher"))}
    paint = {"mat": "metal", "uv": UV_PAINT}
    for b in ((-0.2, 0.2, -0.02, 0.0, 0.0, 0.7), (-0.2, -0.18, -0.25, 0.0, 0.0, 0.7), (0.18, 0.2, -0.25, 0.0, 0.0, 0.7),
              (-0.2, 0.2, -0.25, 0.0, 0.68, 0.7), (-0.2, 0.2, -0.25, 0.0, 0.0, 0.02)):
        solid(L, ("res0", "res1", "geo", "fire"), b, paint, "metal")
    L["res2"].box(-0.2, 0.2, -0.25, 0.0, 0.0, 0.7, **paint)
    for k in NEAR:
        L[k].prism(0.0, -0.12, 0.07, 0.05, 0.55, n=8 if k == "res0" else 6, **red)    # extinguisher
    # glass door: Geometry/Fire as a thin box, visual glass quads
    name = "cab_door"
    for k in ("geo", "fire"):
        L[k].box(-0.19, 0.19, -0.27, -0.25, 0.02, 0.68, sel=[name], **({"mat": "pen_glass"} if k == "fire" else {}))
    # visual: one blended glass quad in Res0, opaque glassfar quad in Res1 (perf batch-3 L3)
    pane = [(-0.19, -0.27, 0.02), (0.19, -0.27, 0.02), (0.19, -0.27, 0.68), (-0.19, -0.27, 0.68)]
    L["res0"].quad(pane, (0, -1, 0), "glass", UV_GLASS, sel=[name])
    L["res1"].quad(pane, (0, -1, 0), "glassfar", UV_GLASS, sel=[name])
    L["mem"].point(name + "_axis", (-0.19, -0.26, 0.02))
    L["mem"].point(name + "_axis", (-0.19, -0.26, 0.68))
    L["mem"].point(name + "_action", (0.0, -0.7, 0.4))
    L["mem"].point(name, (0.0, -0.26, 0.35))
    return finish(L, 25.0, shadow=False)


BUILDERS = {
    "ReceptionDesk": build_reception_desk, "Desk": build_desk, "Cubicle": build_cubicle,
    "ServerRack": build_server_rack, "VendingMachine": build_vending, "Locker": build_locker,
    "Sofa": build_sofa, "Bed": build_bed, "Kitchenette": build_kitchenette,
    "ExtinguisherCabinet": build_extinguisher_cabinet,
}


def modules():
    return {n: (BUILDERS[n], e["pbo"], e["p3d"]) for n, e in S.KIT.items() if n in BUILDERS}


if __name__ == "__main__":
    run_cli(modules(), KIT_MATS, "build_stats_kit.json")
