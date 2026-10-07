"""Generator for SKY interior props (batch 3) - run headless in Blender 4.2.

    blender -b --factory-startup -P build_props.py -- --out <mods/SKY_Skyline/addons> [--only Locker,Desk]

Same pipeline as build_kit.py. Openable parts (locker doors, vending flap,
extinguisher-cabinet door) are vanilla building Doors: bone + Geometry/View/Fire
component + memory `<name>_axis` (2 pts), `<name>_action`, `<name>` - exactly the
pattern of Bohemia's Test_Building. Their swing comes from skyspec.DOOR_SWING_SIGN
(unverified, P1) via gen_configs.py.
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import skyspec as S  # noqa: E402
from build_kit import KIT_MATS, _bar, finish, props_lods  # noqa: E402
from build_towera import UV_ALU, UV_GLASS, UV_STEEL  # noqa: E402
from skygeo import UVBand, UVRect, UVWorld, run_cli  # noqa: E402

B_WOOD = S.MATERIALS["wood"]["bands"]
UV_OAK, UV_WALNUT, UV_LAMINATE = (UVBand(B_WOOD[k], 1.5) for k in ("oak", "walnut", "laminate"))
UV_SCREEN = UVBand(B_WOOD["screen"], 1.0)
B_FAB = S.MATERIALS["fabric"]["bands"]
UV_FGREY, UV_FBLUE, UV_FBEIGE = (UVBand(B_FAB[k], 1.0) for k in ("grey", "blue", "beige"))
B_RUST = S.MATERIALS["rust"]["bands"]
_PB = S.MATERIALS["metal"]["bands"]["painted"]
UV_PAINT = UVBand((_PB[0] + 0.015, _PB[1] - 0.005), 1.0)   # D76: inset off the dark steel band edge (black faces at mip distance)


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


# ------------------------------------------------------------------ D76 close-up helpers
# Render-only detail stays thin (< 0.2 m) or inside the collision so nobody hides in a solid-looking
# volume with no Fire / View geometry (one-way concealment, security D74/D75). Collision, doors, memory
# points and loot surfaces are unchanged from batch 3.
UV_BLACK = UVBand(B_RUST["burnt"], 1.0)
UV_PWHITE = UVBand(S.MATERIALS["paint"]["bands"]["white"], 1.0)
BLACK = {"mat": "wood", "uv": UV_SCREEN}                       # dark plastic: the wood sheet's screen band (no section)


def gaps(a0, a1, n, g=0.003):
    """Split [a0, a1] into n panels with a g gap between them (door / drawer fronts)."""
    w = (a1 - a0) / n
    return [(a0 + i * w + (g / 2 if i else 0), a0 + (i + 1) * w - (g / 2 if i < n - 1 else 0)) for i in range(n)]


def build_reception_desk():
    L = props_lods(view=True)
    wood, met = {"mat": "wood", "uv": UV_WALNUT}, {"mat": "metal", "uv": UV_PAINT}
    marble = {"mat": "marble", "uv": UVWorld(2.4)}
    solid(L, ("res1", "res2", "geo", "fire"), (-1.5, 1.5, -0.4, 0.4, 0.0, 1.05), wood, "wood")       # front counter
    solid(L, ("res1", "res2", "geo", "fire"), (1.5, 2.3, -0.4, 1.2, 0.0, 0.75), wood, "wood")        # return
    solid(L, ("geo", "fire"), (-1.55, 1.55, -0.5, 0.45, 1.05, 1.1), met, "metal")                    # transaction top (loot)
    L["res1"].box(-1.55, 1.55, -0.5, 0.45, 1.05, 1.1, **marble)
    L["res1"].box(-1.5, 1.5, -0.405, -0.4, 0.0, 0.1, skip=("+y",), **met)                         # D76 mid LOD: kick band
    L["res1"].box(-0.3, 0.3, 0.22, 0.26, 1.14, 1.48, **BLACK)
    L["view"].box(-1.5, 1.5, -0.4, 0.4, 0.0, 1.05)
    r0 = L["res0"]
    # D76: plinth recess, fluted walnut front, brushed kick band, marble transaction top, return with its own top
    r0.box(-1.5, 1.5, -0.34, 0.4, 0.0, 0.08, skip=("-z",), **met)
    r0.box(-1.5, 1.5, -0.37, 0.4, 0.08, 1.05, skip=("-z", "+z"), **wood)
    for i in range(15):
        x = -1.45 + i * 0.2
        r0.box(x, x + 0.12, -0.4, -0.37, 0.12, 1.02, skip=("+y", "-z", "+z"), **wood)
    r0.box(-1.5, 1.5, -0.4, -0.37, 0.08, 0.12, skip=("+y", "-z"), **met)                            # kick band
    r0.box(-1.55, 1.55, -0.5, 0.45, 1.05, 1.1, **marble)
    r0.box(1.5, 2.3, -0.34, 1.2, 0.0, 0.08, skip=("-z", "-x"), **met)
    r0.box(1.5, 2.3, -0.4, 1.2, 0.08, 0.72, skip=("-z", "-x"), **wood)
    r0.box(1.5, 2.33, -0.42, 1.22, 0.72, 0.75, **wood)
    # staff side: monitor on a stand, keyboard, desk phone (clear of the loot points at x = +-1.0)
    r0.box(-0.3, 0.3, 0.22, 0.26, 1.16, 1.48, **BLACK)
    face_screen(L, ("res0",), -0.28, 0.28, 1.18, 1.46, 0.219, (0, -1, 0))
    face_screen(L, ("res1",), -0.28, 0.28, 1.16, 1.46, 0.219, (0, -1, 0))
    _bar(r0, (0.0, 0.3, 1.1), (0.0, 0.27, 1.2), 0.02, "metal", UV_STEEL)
    r0.box(-0.12, 0.12, 0.22, 0.4, 1.1, 1.11, **met)
    r0.box(-0.22, 0.22, 0.28, 0.42, 1.1, 1.12, **BLACK)                                              # keyboard
    r0.box(0.45, 0.63, 0.2, 0.38, 1.1, 1.15, **BLACK)                                                # desk phone
    r0.box(0.47, 0.61, 0.2, 0.25, 1.15, 1.17, **BLACK)                                               # handset
    return finish(L, 300.0)


def build_desk():
    L = props_lods()
    lam, met = {"mat": "wood", "uv": UV_LAMINATE}, {"mat": "metal", "uv": UV_PAINT}
    solid(L, ALL, (-0.8, 0.8, -0.4, 0.4, 0.72, 0.75), lam, "wood")                  # top
    for x in (-0.78, 0.76):
        solid(L, ("res1", "geo", "fire"), (x, x + 0.02, -0.38, 0.38, 0.0, 0.72), met, "metal")
    r0 = L["res0"]
    for x in (-0.78, 0.76):                                                        # D76: end panels on levelling feet
        r0.box(x, x + 0.02, -0.38, 0.38, 0.03, 0.72, skip=("+z",), **met)
        for y in (-0.34, 0.3):
            r0.box(x - 0.005, x + 0.025, y, y + 0.04, 0.0, 0.03, skip=("-z",), **BLACK)
    r0.box(-0.76, 0.76, 0.3, 0.32, 0.25, 0.72, **met)                               # modesty panel
    r0.box(-0.8, 0.8, -0.402, -0.4, 0.72, 0.75, skip=("+y",), **BLACK)              # ABS edge band
    # monitor on a stand, keyboard, mouse, cable grommet (loot points at x = +-0.5 stay clear)
    r0.box(-0.25, 0.25, 0.1, 0.13, 0.86, 1.16, **BLACK)
    face_screen(L, ("res0",), -0.235, 0.235, 0.875, 1.145, 0.099)
    _bar(r0, (0.0, 0.15, 0.75), (0.0, 0.14, 0.9), 0.018, "metal", UV_STEEL)
    r0.box(-0.1, 0.1, 0.06, 0.24, 0.75, 0.76, **met)
    r0.box(-0.22, 0.22, -0.26, -0.1, 0.75, 0.77, **BLACK)
    r0.box(0.3, 0.36, 0.0, 0.1, 0.75, 0.775, **BLACK)                               # mouse: > 0.2 m from the loot point (security D76 L)
    r0.hquad(0.565, 0.635, 0.245, 0.315, 0.752, mat="wood", uv=UV_SCREEN)            # cable grommet
    L["res1"].box(-0.25, 0.25, 0.1, 0.15, 0.75, 1.1, **met)                        # Res1 monitor block
    face_screen(L, ("res1",), -0.24, 0.24, 0.77, 1.08, 0.099)
    return finish(L, 60.0, shadow=False)                    # interior_small (perf batch-3 M3)


def build_cubicle():
    """2 x 2 m workstation: 3 fabric screens (1.4 m) + L-shaped desk."""
    L = props_lods(view=True)
    fab, lam = {"mat": "fabric", "uv": UV_FGREY}, {"mat": "wood", "uv": UV_LAMINATE}
    alu, paper = {"mat": "metal", "uv": UV_ALU}, {"mat": "paint", "uv": UV_PWHITE}
    screens = [(-0.95, 0.95, 0.95, 1.0), (-1.0, -0.95, -1.0, 1.0), (0.95, 1.0, -1.0, 1.0)]   # back between the sides (perf D76 M4)
    for (x0, x1, y0, y1) in screens:
        solid(L, ("res1", "res2", "geo", "fire", "view"), (x0, x1, y0, y1, 0.0, 1.4), fab, "wood")
        # D76: fabric panel on a 30 mm aluminium frame (top cap + base rail), feet on the open ends
        L["res0"].box(x0, x1, y0, y1, 0.06, 1.37, skip=("-z", "+z"), **fab)
        cx0, cx1 = (x0, x1) if x1 - x0 < 1.0 else (x0 + 0.004, x1 - 0.004)
        L["res0"].box(cx0 - 0.004, cx1 + 0.004, y0 - 0.004, y1 + 0.004, 1.37, 1.4, **alu)
        L["res0"].box(x0, x1, y0, y1, 0.0, 0.06, skip=("-z", "+z"), **alu)
    for (x, y, along) in ((-0.975, -1.0, "y"), (0.975, -1.0, "y")):                # feet at the open screen ends
        L["res0"].box(x - 0.15, x + 0.15, y, y + 0.06, 0.0, 0.03, skip=("-z",), **alu)
    NEAR_COL = ("res0", "res1", "geo", "fire")                                 # Res2 = screens only (perf L2)
    solid(L, NEAR_COL, (-0.95, 0.95, 0.25, 0.95, 0.72, 0.75), lam, "wood")
    solid(L, NEAR_COL, (-0.95, -0.35, -0.95, 0.25, 0.72, 0.75), lam, "wood")
    r0 = L["res0"]
    _bar(r0, (-0.4, -0.9, 0.0), (-0.4, -0.9, 0.72), 0.025, "metal", UV_ALU)      # leg at the free corner
    for x in (-0.6, 0.6):                                                         # cantilever brackets on the back screen
        r0.box(x - 0.01, x + 0.01, 0.6, 0.95, 0.66, 0.72, **alu)
    # monitor, keyboard, phone, papers; notes pinned on the screens
    r0.box(-0.25, 0.25, 0.7, 0.73, 0.88, 1.16, **BLACK)
    face_screen(L, ("res0", "res1"), -0.235, 0.235, 0.895, 1.145, 0.699)
    L["res1"].box(-0.25, 0.25, 0.7, 0.73, 0.88, 1.16, skip=("-y",), **BLACK)       # Res1 monitor body (perf D76 L)
    _bar(r0, (0.0, 0.76, 0.75), (0.0, 0.74, 0.9), 0.018, "metal", UV_STEEL)
    r0.box(-0.1, 0.1, 0.66, 0.84, 0.75, 0.76, **alu)
    r0.box(-0.22, 0.22, 0.35, 0.5, 0.75, 0.77, **BLACK)
    r0.box(0.5, 0.68, 0.6, 0.78, 0.75, 0.8, **BLACK)
    for (x0, y0, a) in ((-0.8, -0.5, 0.0), (-0.75, -0.2, 0.08), (0.35, 0.3, -0.1)):
        c, s = math.cos(a), math.sin(a)
        pts = [(x0 + dx * c - dy * s, y0 + dx * s + dy * c, 0.752) for dx, dy in ((0, 0), (0.21, 0), (0.21, 0.297), (0, 0.297))]
        r0.quad(pts, (0, 0, 1), "paint", UV_PWHITE)
    for (x, z) in ((-0.5, 1.15), (-0.32, 1.2), (0.55, 1.1)):
        r0.quad([(x, 0.948, z), (x + 0.08, 0.948, z), (x + 0.08, 0.948, z + 0.08), (x, 0.948, z + 0.08)], (0, -1, 0), "paint", UV_PWHITE)
    for z in (1.0, 1.18):
        r0.quad([(-0.948, -0.3, z), (-0.948, -0.08, z), (-0.948, -0.08, z + 0.15), (-0.948, -0.3, z + 0.15)], (1, 0, 0), "paint", UV_PWHITE)
    return finish(L, 120.0)


def build_server_rack():
    L = props_lods(view=True)
    dark = {"mat": "rust", "uv": UVBand(B_RUST["burnt"], 1.0)}
    steel = {"mat": "metal", "uv": UV_STEEL}
    solid(L, ("res2", "geo", "fire", "view"), (-0.3, 0.3, -0.5, 0.5, 0.0, 2.0), dark, "metal")
    r1 = L["res1"]                                                                # D76 mid LOD: plinth, body, cap, handle
    r1.box(-0.28, 0.28, -0.46, 0.48, 0.0, 0.08, skip=("-z",), **dark)
    r1.box(-0.3, 0.3, -0.5, 0.5, 0.08, 1.96, skip=("-z", "-y"), **dark)
    r1.box(-0.305, 0.305, -0.51, 0.505, 1.96, 2.0, skip=("-z",), **dark)
    r1.box(0.274, 0.29, -0.53, -0.5, 0.9, 1.18, skip=("+y",), **steel)
    face_atlas(L, ("res1",), "rack", -0.3, 0.3, 0.08, 1.96, -0.5)                 # replaces the front face (no 1 mm decal)
    r0 = L["res0"]
    # D76: plinth on levelling feet, carcass, overhanging top, front door frame with recessed mesh face,
    # swing handle and lock, side vent slats
    r0.box(-0.28, 0.28, -0.46, 0.48, 0.03, 0.08, skip=("-z",), **dark)
    for x in (-0.25, 0.25):
        for y in (-0.44, 0.44):
            r0.box(x - 0.02, x + 0.02, y - 0.02, y + 0.02, 0.0, 0.03, skip=("-z", "+z"), **steel)
    r0.box(-0.3, 0.3, -0.48, 0.5, 0.08, 1.96, skip=("-z", "+z", "-y"), **dark)
    r0.box(-0.305, 0.305, -0.51, 0.505, 1.96, 2.0, **dark)
    for (x0, x1) in ((-0.3, -0.27), (0.27, 0.3)):
        r0.box(x0, x1, -0.5, -0.48, 0.08, 1.96, skip=("+y", "+z"), **dark)
    r0.box(-0.27, 0.27, -0.5, -0.48, 0.08, 0.12, skip=("+y", "-z"), **dark)
    face_atlas(L, ("res0",), "rack", -0.27, 0.27, 0.12, 1.96, -0.481)
    r0.box(0.274, 0.29, -0.53, -0.5, 0.9, 1.18, **steel)                            # swing handle
    r0.prism(0.282, -0.505, 0.012, 1.22, 1.24, n=6, **steel)                        # lock barrel (stub)
    for sx in (-1, 1):
        for i in range(6):
            z = 1.55 + i * 0.05
            x0, x1 = sorted((sx * 0.3, sx * 0.31))
            r0.box(x0, x1, -0.3, 0.3, z, z + 0.02, skip=("-x" if sx > 0 else "+x",), **steel)
    return finish(L, 250.0, hull=True)


def build_vending():
    L = props_lods(view=True, mem=True)
    paint = {"mat": "rust", "uv": UVBand(B_RUST["grey"], 1.0)}
    steel = {"mat": "metal", "uv": UV_STEEL}
    solid(L, ("res2", "geo", "fire", "view"), (-0.5, 0.5, -0.4, 0.4, 0.0, 1.9), paint, "metal")
    face_atlas(L, ("res2",), "vending", -0.48, 0.48, 0.45, 1.85, -0.404)          # 4 mm: no far-LOD z-fight
    r1 = L["res1"]                                                                # D76 mid LOD: body, bezel, recessed window
    r1.box(-0.5, 0.5, -0.37, 0.4, 0.0, 1.9, skip=("-z",), **paint)
    for (x0, x1) in ((-0.5, -0.47), (0.47, 0.5)):
        r1.box(x0, x1, -0.41, -0.37, 0.0, 1.86, skip=("+y", "-z"), **paint)
    r1.box(-0.47, 0.47, -0.41, -0.37, 1.83, 1.86, skip=("+y", "-x", "+x"), **paint)
    r1.box(-0.47, 0.47, -0.405, -0.37, 0.0, 0.45, skip=("+y", "-x", "+x", "-z"), **paint)
    face_atlas(L, ("res1",), "vending", -0.47, 0.47, 0.45, 1.83, -0.386)
    r1.box(0.36, 0.45, -0.44, -0.405, 0.5, 0.58, skip=("+y",), **steel)
    # pickup flap: bottom hinge along X at z = 0.15, swings outward/down (P1 sign)
    hinged_door(L, "flap", (-0.35, 0.35, -0.43, -0.41, 0.15, 0.4), (-0.42, 0.15, -0.35, 0.35), "x",
                (0.0, -0.8, 0.3), {"mat": "metal", "uv": UV_STEEL}, "metal")
    r0 = L["res0"]
    # D76: carcass on feet, a 3 cm bezel around a recessed product window, kick plate behind the flap,
    # coin-return cup, side vent slats, rounded top edge
    for x in (-0.44, 0.44):
        for y in (-0.34, 0.34):
            r0.box(x - 0.03, x + 0.03, y - 0.03, y + 0.03, 0.0, 0.04, skip=("-z",), **steel)
    r0.box(-0.5, 0.5, -0.37, 0.4, 0.04, 1.86, skip=("-z", "+z"), **paint)
    r0.extrude_x([(-0.37, 1.86), (0.4, 1.86), (0.4, 1.88), (0.38, 1.9), (-0.35, 1.9), (-0.37, 1.88)], -0.5, 0.5, **paint)
    for (x0, x1) in ((-0.5, -0.47), (0.47, 0.5)):
        r0.box(x0, x1, -0.41, -0.37, 0.04, 1.86, skip=("+y",), **paint)
    for (z0, z1) in ((1.83, 1.86), (0.42, 0.45)):
        r0.box(-0.47, 0.47, -0.41, -0.37, z0, z1, skip=("+y", "-x", "+x"), **paint)
    face_atlas(L, ("res0",), "vending", -0.47, 0.47, 0.45, 1.83, -0.386)
    r0.box(-0.47, 0.47, -0.405, -0.37, 0.04, 0.42, skip=("+y", "-x", "+x"), **paint)   # kick plate behind the flap
    r0.box(0.36, 0.45, -0.44, -0.405, 0.5, 0.58, **steel)                          # coin-return cup
    for sx in (-1, 1):
        for i in range(5):
            z = 0.2 + i * 0.06
            x0, x1 = sorted((sx * 0.5, sx * 0.51))
            r0.box(x0, x1, 0.05, 0.35, z, z + 0.025, skip=("-x" if sx > 0 else "+x",), **steel)
    return finish(L, 300.0, hull=True)


def build_locker():
    """Bank of 3 lockers (0.3 m each), doors hinged on their left edge."""
    L = props_lods(view=True, mem=True)
    paint = {"mat": "rust", "uv": UVBand(B_RUST["grey"], 1.0)}
    steel = {"mat": "metal", "uv": UV_STEEL}
    # carcass: back, sides, top, bottom, shelves (open front)
    for b in ((-0.45, 0.45, 0.22, 0.25, 0.0, 1.8), (-0.45, -0.43, -0.25, 0.25, 0.0, 1.8),
              (0.43, 0.45, -0.25, 0.25, 0.0, 1.8), (-0.45, 0.45, -0.25, 0.25, 1.78, 1.8),
              (-0.45, 0.45, -0.25, 0.25, 0.0, 0.05)):
        solid(L, ("geo", "fire", "view"), b, paint, "metal")
    for b in ((-0.43, 0.43, 0.22, 0.25, 0.05, 1.78), (-0.45, -0.43, -0.25, 0.25, 0.05, 1.78),    # D76 render carcass:
              (0.43, 0.45, -0.25, 0.25, 0.05, 1.78), (-0.45, 0.45, -0.25, 0.25, 1.78, 1.8),     # sides between top and
              (-0.45, 0.45, -0.25, 0.25, 0.0, 0.05)):                                             # bottom (perf D76 M1)
        for k in ("res0", "res1"):
            L[k].box(*b, **paint)
    for x in (-0.15, 0.15):
        solid(L, ("res0", "res1", "geo", "fire"), (x - 0.01, x + 0.01, -0.24, 0.22, 0.05, 1.78), paint, "metal")
    solid(L, ("res0", "geo", "fire"), (-0.43, 0.43, -0.24, 0.22, 1.45, 1.47), paint, "metal")   # shelf (loot surface, QA L1)
    L["res2"].box(-0.45, 0.45, -0.25, 0.25, 0.0, 1.8, **paint)
    for i, x0 in enumerate((-0.45, -0.15, 0.15)):
        name = "locker_door%d" % (i + 1)
        hinged_door(L, name, (x0 + 0.005, x0 + 0.295, -0.27, -0.25, 0.06, 1.77),
                    (x0 + 0.005, -0.26, 0.06, 1.77), "z", (x0 + 0.15, -0.7, 1.1), paint, "metal")
        # D76 (on the door bone, so it swings with the leaf): pressed vent louvres top and bottom,
        # lift handle with hasp, card holder
        for zb in (0.14, 1.56):
            for j in range(4):
                z = zb + j * 0.035
                L["res0"].box(x0 + 0.06, x0 + 0.24, -0.278, -0.27, z, z + 0.012, skip=("+y", "-x", "+x"), sel=[name], **paint)
        L["res0"].box(x0 + 0.245, x0 + 0.275, -0.285, -0.27, 0.95, 1.12, skip=("+y",), sel=[name], **steel)
        L["res0"].box(x0 + 0.1, x0 + 0.2, -0.274, -0.27, 1.32, 1.37, skip=("+y",), sel=[name], **steel)
    L["res0"].box(-0.45, 0.45, -0.28, -0.25, 0.0, 0.05, skip=("+y", "-z"), mat="rust", uv=UV_BLACK)   # plinth
    return finish(L, 120.0, hull=True)


def build_sofa():
    L = props_lods()
    fab = {"mat": "fabric", "uv": UV_FBLUE}
    wood = {"mat": "wood", "uv": UV_WALNUT}
    solid(L, ("res1", "res2", "geo", "fire"), (-1.0, 1.0, -0.45, 0.45, 0.0, 0.42), fab, "wood")    # base + seat
    solid(L, ("res1", "res2", "geo", "fire"), (-1.0, 1.0, 0.25, 0.45, 0.42, 0.85), fab, "wood")    # back
    for x in (-1.0, 0.82):
        solid(L, ("res1", "geo", "fire"), (x, x + 0.18, -0.45, 0.25, 0.42, 0.62), fab, "wood")
    r0 = L["res0"]
    # D76: frame on tapered walnut feet, rolled arms, two seat and two back cushions with rounded edges
    for x in (-0.92, 0.92):
        for y in (-0.38, 0.38):
            r0.extrude_x([(y - 0.025, 0.0), (y + 0.025, 0.0), (y + 0.035, 0.1), (y - 0.035, 0.1)], x - 0.03, x + 0.03, **wood)
    r0.box(-0.98, 0.98, -0.44, 0.44, 0.1, 0.3, skip=("+z",), **fab)
    r0.extrude_x([(0.25, 0.3), (0.45, 0.3), (0.45, 0.8), (0.42, 0.85), (0.28, 0.85), (0.25, 0.82)], -0.82, 0.82, **fab)
    for sx in (-1, 1):
        xa, xb = sorted((sx * 1.0, sx * 0.82))
        prof = [(xa, 0.1), (xb, 0.1), (xb, 0.58), (xb - 0.03, 0.625), ((xa + xb) / 2, 0.64), (xa + 0.03, 0.625), (xa, 0.58)]
        r0.extrude_y(prof, -0.45, 0.45, **fab)
    for (x0, x1) in ((-0.815, -0.005), (0.005, 0.815)):
        r0.extrude_x([(-0.44, 0.3), (0.24, 0.3), (0.24, 0.43), (-0.41, 0.43), (-0.45, 0.39)], x0, x1, **fab)
        r0.extrude_x([(0.12, 0.43), (0.25, 0.43), (0.25, 0.8), (0.2, 0.82), (0.1, 0.76)], x0, x1, **fab)
    return finish(L, 60.0, shadow=False)                    # interior_small (perf batch-3 M3)


def build_bed():
    L = props_lods()
    wood, fab = {"mat": "wood", "uv": UV_OAK}, {"mat": "fabric", "uv": UV_FBEIGE}
    duvet = {"mat": "fabric", "uv": UV_FGREY}
    solid(L, ("res1", "res2", "geo", "fire"), (-0.7, 0.7, -1.0, 1.0, 0.0, 0.3), wood, "wood")       # frame
    solid(L, ("res1", "res2", "geo", "fire"), (-0.68, 0.68, -0.98, 1.0, 0.3, 0.5), fab, "wood")     # mattress (to the headboard, D74)
    solid(L, ("res1", "geo", "fire"), (-0.75, 0.75, 1.0, 1.06, 0.0, 1.0), wood, "wood")             # headboard
    L["res1"].box(-0.55, 0.55, 0.55, 0.9, 0.5, 0.6, **fab)
    r0 = L["res0"]
    # D76: rails on square legs, chamfered mattress, a duvet draped over the sides and turned back,
    # a soft pillow, an upholstered headboard pad
    for x in (-0.66, 0.62):
        for y in (-0.98, 0.94):
            r0.box(x, x + 0.04, y, y + 0.04, 0.0, 0.12, skip=("-z", "+z"), **wood)
    for (x0, x1, y0, y1) in ((-0.7, -0.66, -1.0, 1.0), (0.66, 0.7, -1.0, 1.0), (-0.66, 0.66, -1.0, -0.96)):
        r0.box(x0, x1, y0, y1, 0.12, 0.32, skip=("-z",), **wood)
    r0.extrude_y([(-0.68, 0.3), (0.68, 0.3), (0.68, 0.47), (0.65, 0.5), (-0.65, 0.5), (-0.68, 0.47)], -0.96, 1.0, **fab)
    r0.extrude_y([(-0.715, 0.34), (0.715, 0.34), (0.715, 0.5), (0.68, 0.535), (-0.68, 0.535), (-0.715, 0.5)], -0.985, 0.3, **duvet)
    r0.extrude_y([(-0.7, 0.5), (0.7, 0.5), (0.7, 0.545), (-0.7, 0.545)], 0.3, 0.42, **{"mat": "fabric", "uv": UV_FBLUE})   # turn-back
    r0.extrude_x([(0.55, 0.5), (0.9, 0.5), (0.93, 0.55), (0.89, 0.62), (0.57, 0.62), (0.53, 0.55)], -0.5, 0.5, **fab)
    r0.box(-0.75, 0.75, 1.0, 1.06, 0.0, 1.0, skip=("-z",), **wood)
    r0.box(-0.65, 0.65, 0.975, 1.0, 0.52, 0.92, skip=("+y",), **duvet)              # headboard pad
    return finish(L, 80.0, shadow=False)


def build_kitchenette():
    L = props_lods(view=True)
    lam, met = {"mat": "wood", "uv": UV_LAMINATE}, {"mat": "metal", "uv": UV_ALU}
    steel = {"mat": "metal", "uv": UV_STEEL}
    solid(L, ("res1", "res2", "geo", "fire", "view"), (-1.2, 0.6, -0.3, 0.3, 0.0, 0.88), lam, "wood")
    solid(L, ("res1", "geo", "fire"), (-1.22, 0.6, -0.32, 0.3, 0.88, 0.92), met, "metal")   # worktop (loot surface)
    solid(L, ("res1", "geo", "fire"), (-1.2, 0.6, 0.0, 0.3, 1.5, 2.2), lam, "wood")          # upper cabinets
    solid(L, ("res0", "res1", "res2", "geo", "fire", "view"), (0.6, 1.2, -0.3, 0.3, 0.0, 1.9), met, "metal")  # fridge
    face_atlas(L, ("res0", "res1"), "appliance", 0.62, 1.18, 0.02, 1.88, -0.304)
    for (x0, x1) in gaps(-1.2, 0.6, 3, 0.01):                                     # D76 mid LOD: fronts, splashback
        L["res1"].box(x0, x1, -0.305, -0.3, 0.1, 0.875, skip=("+y",), **lam)
        L["res1"].box(x0, x1, -0.025, 0.0, 1.5, 2.2, skip=("+y",), **lam)
    L["res1"].quad([(-1.2, 0.29, 0.92), (0.6, 0.29, 0.92), (0.6, 0.29, 1.5), (-1.2, 0.29, 1.5)], (0, -1, 0), "tile", UVWorld(1.2))
    r0 = L["res0"]
    # D76 base run: plinth recess, door + drawer fronts with 3 mm reveals, bar handles
    r0.box(-1.2, 0.6, -0.24, 0.3, 0.0, 0.1, skip=("-z", "+z"), **BLACK)
    r0.box(-1.2, 0.6, -0.28, 0.3, 0.1, 0.88, skip=("-z", "+z"), **lam)
    for (x0, x1) in gaps(-1.2, 0.6, 3):
        r0.box(x0, x1, -0.3, -0.28, 0.1, 0.685, skip=("+y",), **lam)
        r0.box(x0, x1, -0.3, -0.28, 0.688, 0.875, skip=("+y",), **lam)
        xm = (x0 + x1) / 2
        _bar(r0, (xm - 0.1, -0.32, 0.79), (xm + 0.1, -0.32, 0.79), 0.007, "metal", UV_STEEL)
        _bar(r0, (x1 - 0.05, -0.32, 0.45), (x1 - 0.05, -0.32, 0.62), 0.007, "metal", UV_STEEL)
    # worktop with a sink cut-out, recessed basin, mixer tap, tiled splashback
    hx0, hx1, hy0, hy1 = -0.85, -0.45, -0.2, 0.15
    for b in ((-1.22, hx0, -0.32, 0.3), (hx1, 0.6, -0.32, 0.3), (hx0, hx1, -0.32, hy0), (hx0, hx1, hy1, 0.3)):
        r0.box(b[0], b[1], b[2], b[3], 0.88, 0.92, **met)
    zb = 0.72
    r0.hquad(hx0, hx1, hy0, hy1, zb, mat="metal", uv=UV_STEEL)
    r0.quad([(hx0, hy0, zb), (hx1, hy0, zb), (hx1, hy0, 0.92), (hx0, hy0, 0.92)], (0, 1, 0), "metal", UV_STEEL)
    r0.quad([(hx0, hy1, zb), (hx1, hy1, zb), (hx1, hy1, 0.92), (hx0, hy1, 0.92)], (0, -1, 0), "metal", UV_STEEL)
    r0.quad([(hx0, hy0, zb), (hx0, hy1, zb), (hx0, hy1, 0.92), (hx0, hy0, 0.92)], (1, 0, 0), "metal", UV_STEEL)
    r0.quad([(hx1, hy0, zb), (hx1, hy1, zb), (hx1, hy1, 0.92), (hx1, hy0, 0.92)], (-1, 0, 0), "metal", UV_STEEL)
    r0.prism(-0.65, -0.02, 0.035, zb, zb + 0.004, n=8, **BLACK)                      # drain
    _bar(r0, (-0.65, 0.22, 0.92), (-0.65, 0.22, 1.16), 0.015, "metal", UV_STEEL)     # tap
    _bar(r0, (-0.65, 0.22, 1.16), (-0.65, 0.02, 1.13), 0.012, "metal", UV_STEEL)
    _bar(r0, (-0.65, 0.22, 1.05), (-0.55, 0.22, 1.08), 0.008, "metal", UV_STEEL)
    r0.box(-1.2, 0.6, 0.29, 0.3, 0.92, 1.5, skip=("+y",), mat="tile", uv=UVWorld(1.2))
    r0.prism(-0.25, 0.17, 0.075, 0.92, 1.1, n=8, **steel)                          # kettle (clear of the loot points)
    r0.prism(-0.25, 0.17, 0.04, 1.1, 1.13, n=8, **BLACK)
    # wall cabinets: carcass, 3 doors, under-cabinet edge, handles
    r0.box(-1.2, 0.6, 0.0, 0.3, 1.5, 2.2, skip=("+y",), **lam)
    for (x0, x1) in gaps(-1.2, 0.6, 3):
        r0.box(x0, x1, -0.02, 0.0, 1.5, 2.2, skip=("+y",), **lam)
        _bar(r0, (x0 + 0.05, -0.04, 1.54), (x0 + 0.05, -0.04, 1.7), 0.007, "metal", UV_STEEL)
    # fridge: door handles and kick grille
    for (z0, z1) in ((0.62, 0.98), (1.12, 1.5)):
        _bar(r0, (0.68, -0.33, z0), (0.68, -0.33, z1), 0.012, "metal", UV_STEEL)
    r0.box(0.64, 1.16, -0.305, -0.3, 0.02, 0.1, skip=("+y",), **BLACK)
    return finish(L, 150.0, hull=True)


def build_extinguisher_cabinet():
    """Wall cabinet (back at y = 0) with glass door hinged on the left edge."""
    L = props_lods(mem=True)
    red = {"mat": "atlas", "uv": UVRect(0, 2, (-0.2, 0.0), (0.2, 0.7), S.atlas_uv("extinguisher"))}
    paint = {"mat": "metal", "uv": UV_PAINT}
    hose = {"mat": "rust", "uv": UV_BLACK}
    for b in ((-0.2, 0.2, -0.02, 0.0, 0.0, 0.7), (-0.2, -0.18, -0.25, 0.0, 0.0, 0.7), (0.18, 0.2, -0.25, 0.0, 0.0, 0.7),
              (-0.2, 0.2, -0.25, 0.0, 0.68, 0.7), (-0.2, 0.2, -0.25, 0.0, 0.0, 0.02)):
        solid(L, ("geo", "fire"), b, paint, "metal")
    L["res2"].box(-0.2, 0.2, -0.25, 0.0, 0.0, 0.7, **paint)
    # D76 Res0 carcass without coplanar overlaps (sides between top and bottom; z-fight showed black)
    for b in ((-0.18, 0.18, -0.02, 0.0, 0.02, 0.68), (-0.2, -0.18, -0.25, 0.0, 0.02, 0.68), (0.18, 0.2, -0.25, 0.0, 0.02, 0.68),
              (-0.2, 0.2, -0.25, 0.0, 0.68, 0.7), (-0.2, 0.2, -0.25, 0.0, 0.0, 0.02)):
        for k in NEAR:
            L[k].box(*b, skip=("+y",), **paint)
    L["res1"].prism(0.0, -0.12, 0.07, 0.05, 0.55, n=6, **red)
    # D76 extinguisher: body, domed shoulder, valve head, lever, hose to a horn on a clip
    r0 = L["res0"]
    r0.prism(0.0, -0.12, 0.07, 0.04, 0.47, n=10, **red)
    r0.prism(0.0, -0.12, 0.05, 0.47, 0.51, n=10, **red)
    r0.box(-0.02, 0.02, -0.14, -0.1, 0.51, 0.57, **{"mat": "metal", "uv": UV_STEEL})
    _bar(r0, (0.0, -0.12, 0.575), (0.07, -0.12, 0.56), 0.008, "metal", UV_STEEL)
    _bar(r0, (0.02, -0.12, 0.54), (0.11, -0.13, 0.45), 0.009, "rust", UV_BLACK)
    _bar(r0, (0.11, -0.13, 0.45), (0.11, -0.13, 0.2), 0.009, "rust", UV_BLACK)
    _bar(r0, (0.11, -0.13, 0.2), (0.11, -0.13, 0.12), 0.016, "rust", UV_BLACK)
    r0.box(-0.1, 0.1, -0.03, -0.02, 0.36, 0.4, **hose)                              # wall strap
    # glass door: Geometry/Fire as a thin box, visual glass quads
    name = "cab_door"
    for k in ("geo", "fire"):
        L[k].box(-0.19, 0.19, -0.27, -0.25, 0.02, 0.68, sel=[name], **({"mat": "pen_glass"} if k == "fire" else {}))
    # visual: one blended glass quad in Res0, opaque glassfar quad in Res1 (perf batch-3 L3)
    pane = [(-0.19, -0.27, 0.02), (0.19, -0.27, 0.02), (0.19, -0.27, 0.68), (-0.19, -0.27, 0.68)]
    inner = [(-0.165, -0.27, 0.045), (0.165, -0.27, 0.045), (0.165, -0.27, 0.655), (-0.165, -0.27, 0.655)]
    L["res0"].quad(inner, (0, -1, 0), "glass", UV_GLASS, sel=[name])            # blended pane only in the frame opening
    L["res1"].quad(pane, (0, -1, 0), "glassfar", UV_GLASS, sel=[name])
    # D76 door frame and pull on the door bone (swing with the leaf)
    for b in ((-0.19, -0.165, 0.02, 0.68), (0.165, 0.19, 0.02, 0.68), (-0.165, 0.165, 0.02, 0.045), (-0.165, 0.165, 0.655, 0.68)):
        r0.box(b[0], b[1], -0.275, -0.25, b[2], b[3], skip=("+y",), sel=[name], **paint)
    r0.box(0.15, 0.165, -0.29, -0.275, 0.3, 0.42, skip=("+y",), sel=[name], **{"mat": "metal", "uv": UV_STEEL})
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
