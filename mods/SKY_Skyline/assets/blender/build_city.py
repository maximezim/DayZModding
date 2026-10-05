"""Procedural city buildings (D56) - run headless in Blender 4.2.

    blender -b --factory-startup --python-exit-code 1 -P build_city.py -- --out <mods/SKY_Skyline/addons> [--only City_Rowhouse_Intact]

One style grammar for the whole city (skyspec.CITY_STYLE / CITY_SKINS), one data record per
archetype (skyspec.CITY_ARCHETYPES), three ruin states per archetype:
  Intact   full detail, glazing, front door, interior finish and decoration, script lights
  Damaged  same shell; windows broken or boarded (seeded), soot over broken windows, cracks,
           debris on the floors; front door still there
  Ruined   all glass gone, no door, a corner of the upper storeys collapsed: floors and roof
           inside the collapse zone gone, walls cut jagged, rubble mounds (collide) below
Every primitive goes through RLod, which applies the collapse to any shape, so the same
grammar code produces all three states. Frame: front (street) = -Y, origin = footprint centre
at the ground-floor slab top. Untested engine facts are skyspec parameters (P1, P3).
Also writes assets/city_loot.json (loot points per class, read by skyspec -> CE groups).
"""
import json
import math
import os
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import detail as DT  # noqa: E402
import skyspec as S  # noqa: E402
from build_kit import KIT_MATS  # noqa: E402
from skygeo import (LOD_FIREGEO, LOD_GEOMETRY, LOD_MEMORY, LOD_RES, LOD_ROADWAY,  # noqa: E402
                    LOD_SHADOW, LOD_VIEWGEO, Lod, UVBand, UVRect, UVWorld, run_cli)

ST = S.CITY_STYLE
WT = ST["wall_t"]
PT = ST["part_t"]
SLAB = S.SLAB_T
UV_CONC = UVBand(S.MATERIALS["concrete"]["bands"]["panel"], 3.0)
UV_REVEAL = UVBand(S.MATERIALS["concrete"]["bands"]["reveal"], 3.0)
UV_RUBBLE = UVWorld(S.MATERIALS["rubble"]["sheet_m"])
UV_TILE = UVWorld(3.0)
UV_GLASS = UVWorld(3.0)
UV_CARPET = UVWorld(4.0)


def h01(*key):
    """Deterministic pseudo-random number in [0, 1) from a key (seeded procedural choices)."""
    return (zlib.crc32(repr(key).encode()) & 0xFFFFFF) / float(0x1000000)


# ================================================================== ruin layer
class Ruin:
    """state 0/1/2; region = (x0, x1, y0, y1, zc): everything inside the region above zc
    collapses (thin horizontal parts vanish, walls are cut to a jagged height)."""

    def __init__(self, name, state, region=None):
        self.name, self.state, self.region = name, state, region

    def inside(self, x, y):
        r = self.region
        return r is not None and r[0] <= x <= r[1] and r[2] <= y <= r[3]

    def cut(self, x, y):
        zc = self.region[4]
        return zc + 0.35 + 2.2 * h01(self.name, "cut", round(x, 1), round(y, 1))

    def window(self, *key):
        """Window state: glass / broken / boarded."""
        if self.state == 0:
            return "glass"
        r = h01(self.name, "win", *key)
        if self.state == 1:
            return "broken" if r < 0.35 else ("boarded" if r < 0.5 else "glass")
        return "boarded" if r < 0.2 else "broken"


class RLod:
    """Lod proxy: every primitive is split at the collapse region edges and the pieces inside
    are dropped or cut down. Unknown attributes fall through to the wrapped Lod."""

    def __init__(self, lod, ruin):
        self.lod, self.ruin = lod, ruin

    def __getattr__(self, k):
        return getattr(self.lod, k)

    def _splits(self, a0, a1, b0, b1):
        r = self.ruin.region
        xs = sorted({a0, a1} | {v for v in (r[0], r[1]) if a0 + 1e-6 < v < a1 - 1e-6})
        ys = sorted({b0, b1} | {v for v in (r[2], r[3]) if b0 + 1e-6 < v < b1 - 1e-6})
        return [(xa, xb, ya, yb) for xa, xb in zip(xs, xs[1:]) for ya, yb in zip(ys, ys[1:])]

    def _affected(self, x0, x1, y0, y1, z1):
        r = self.ruin.region
        return r is not None and z1 > r[4] + 1e-6 and x0 < r[1] and r[0] < x1 and y0 < r[3] and r[2] < y1

    def box(self, x0, x1, y0, y1, z0, z1, **kw):
        if not self._affected(x0, x1, y0, y1, z1):
            return self.lod.box(x0, x1, y0, y1, z0, z1, **kw)
        zc = self.ruin.region[4]
        for a, b, c, d in self._splits(x0, x1, y0, y1):
            cx, cy = (a + b) / 2, (c + d) / 2
            if not self.ruin.inside(cx, cy):
                self.lod.box(a, b, c, d, z0, z1, **kw)
                continue
            if z0 >= zc - 1e-6 and z1 - z0 <= 0.45:          # floors, sills, copings: fell
                continue
            cut = self.ruin.cut(cx, cy)
            if z0 < cut:
                self.lod.box(a, b, c, d, z0, min(z1, cut), **kw)

    def quad(self, pts, facing, mat=None, uv=None, sel=(), double=False):
        xs, ys, zs = ([p[i] for p in pts] for i in range(3))
        x0, x1, y0, y1, z0, z1 = min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)
        if not self._affected(x0, x1, y0, y1, z1):
            return self.lod.quad(pts, facing, mat, uv, sel, double)
        zc = self.ruin.region[4]
        flat_x, flat_y, flat_z = x1 - x0 < 1e-6, y1 - y0 < 1e-6, z1 - z0 < 1e-6
        if not (flat_x or flat_y or flat_z) or len(pts) != 4:
            c = [sum(v) / len(v) for v in (xs, ys, zs)]
            if not (self.ruin.inside(c[0], c[1]) and c[2] > self.ruin.cut(c[0], c[1])):
                self.lod.quad(pts, facing, mat, uv, sel, double)
            return
        for a, b, c, d in self._splits(x0, x1, y0, y1):
            cx, cy = (a + b) / 2, (c + d) / 2
            inside = self.ruin.inside(cx, cy)
            if flat_z:
                if inside and z0 > zc:
                    continue
                q = [(a, c, z0), (b, c, z0), (b, d, z0), (a, d, z0)]
            else:
                top = z1
                if inside:
                    top = min(z1, self.ruin.cut(cx, cy))
                    if top <= z0:
                        continue
                if flat_x:
                    q = [(x0, c, z0), (x0, d, z0), (x0, d, top), (x0, c, top)]
                else:
                    q = [(a, y0, z0), (b, y0, z0), (b, y0, top), (a, y0, top)]
            self.lod.quad(q, facing, mat, uv, sel, double)

    def hquad(self, x0, x1, y0, y1, z, mat=None, uv=None, sel=(), up=True):
        self.quad([(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)], (0, 0, 1 if up else -1), mat, uv, sel)

    def _centroid_ok(self, verts):
        c = [sum(v[i] for v in verts) / len(verts) for i in range(3)]
        return not (self.ruin.region is not None and self.ruin.inside(c[0], c[1]) and c[2] > self.ruin.cut(c[0], c[1]))

    def solid(self, verts, faces, mat=None, uv=None, sel=(), component=None):
        if self._centroid_ok(verts):
            self.lod.solid(verts, faces, mat, uv, sel, component)

    def prism(self, cx, cy, r, z0, z1, n=8, mat=None, uv=None, sel=(), component=None, rot=0.0):
        if self._centroid_ok([(cx, cy, (z0 + z1) / 2)]):
            self.lod.prism(cx, cy, r, z0, z1, n, mat, uv, sel, component, rot)

    def extrude_x(self, profile, x0, x1, **kw):
        if self._centroid_ok([((x0 + x1) / 2, profile[0][0], profile[0][1])]):
            self.lod.extrude_x(profile, x0, x1, **kw)

    def extrude_y(self, profile, y0, y1, **kw):
        if self._centroid_ok([(profile[0][0], (y0 + y1) / 2, profile[0][1])]):
            self.lod.extrude_y(profile, y0, y1, **kw)


def city_lods(ruin):
    L = {"res0": Lod("res0", LOD_RES, 0.0), "res1": Lod("res1", LOD_RES, 1.0), "res2": Lod("res2", LOD_RES, 2.0),
         "res3": Lod("res3", LOD_RES, 3.0), "shadow": Lod("shadow", LOD_SHADOW), "geo": Lod("geo", LOD_GEOMETRY),
         "view": Lod("view", LOD_VIEWGEO), "fire": Lod("fire", LOD_FIREGEO), "road": Lod("road", LOD_ROADWAY),
         "mem": Lod("mem", LOD_MEMORY)}
    return {k: RLod(v, ruin) for k, v in L.items()}


def kw_for(k, mat, uv, pen):
    if k.startswith("res"):
        return {"mat": mat, "uv": uv}
    return {"mat": "pen_" + pen} if k == "fire" else {}


def rects_minus(x0, x1, y0, y1, holes):
    """Axis-aligned rectangle minus rectangular holes -> list of rectangles (row-merged grid)."""
    hs = [(max(x0, a), min(x1, b), max(y0, c), min(y1, d)) for (a, b, c, d) in holes]
    hs = [h for h in hs if h[0] < h[1] and h[2] < h[3]]
    xs = sorted({x0, x1} | {v for h in hs for v in h[:2]})
    ys = sorted({y0, y1} | {v for h in hs for v in h[2:]})
    out = []
    for ya, yb in zip(ys, ys[1:]):
        run = None
        for xa, xb in zip(xs, xs[1:]):
            cx, cy = (xa + xb) / 2, (ya + yb) / 2
            hole = any(h[0] <= cx <= h[1] and h[2] <= cy <= h[3] for h in hs)
            if hole:
                if run:
                    out.append(run)
                    run = None
            elif run:
                run = (run[0], xb, ya, yb)
            else:
                run = (xa, xb, ya, yb)
        if run:
            out.append(run)
    return out


# ================================================================== plan
class Plan:
    """Derived geometry of one archetype in one ruin state."""

    def __init__(self, arch, state):
        A = S.CITY_ARCHETYPES[arch]
        self.arch, self.A, self.state = arch, A, state
        self.name = "City_%s_%s" % (arch, S.RUIN_STATES[state])
        self.W, self.D = A["w"], A["d"]
        self.hw, self.hd = self.W / 2, self.D / 2
        self.ix0, self.ix1, self.iy0, self.iy1 = -self.hw + WT, self.hw - WT, -self.hd + WT, self.hd - WT
        z, self.levels = 0.0, []
        for use, fh in A["levels"]:
            self.levels.append((use, fh, z))
            z += fh
        self.top = z
        self.stair = None
        if A["stair"] and len(self.levels) > 1:
            fmax = max(fh for _u, fh, _z in self.levels[:-1])
            n = math.ceil(fmax / 2 / ST["riser_max"])
            sd = 1.2 + n * ST["tread"] + 1.2
            sw = ST["stair_w"]
            x0 = {"back_left": self.ix0, "back_center": -sw / 2, "back_right": self.ix1 - sw}[A["stair"]]
            self.stair = (x0, x0 + sw, self.iy1 - sd, self.iy1)
        # front door (ground level, front side)
        bays = self.bays(-self.hw, self.hw)
        i = len(bays) // 2 if A["door_bay"] == "center" else A["door_bay"]
        c = (bays[i][0] + bays[i][1]) / 2
        dw = ST["door"][0]
        self.door = (c - dw / 2, c + dw / 2)
        self.door_bay = i
        # ruin: collapse a front corner away from the stair and the door
        self.ruin = Ruin(self.name, state)
        if state == 2:
            kc = max(1, len(self.levels) - 1)
            zc = (self.levels[kc][2] - SLAB - 0.05) if kc < len(self.levels) else self.top - SLAB - 0.05
            if len(self.levels) == 1:
                zc = self.levels[0][1] * 0.45
            self.kc = kc
            left = (self.stair is not None and self.stair[0] > 0) or (self.stair is None and self.door[0] > 0)
            xa, xb = (-self.hw - 1.0, -self.hw * 0.15) if left else (self.hw * 0.15, self.hw + 1.0)
            if self.door[1] > xa and self.door[0] < xb:            # keep the entrance standing
                xa, xb = (max(xa, self.door[1] + 0.6), xb) if not left else (xa, min(xb, self.door[0] - 0.6))
            self.ruin.region = (xa, xb, -self.hd - 1.0, self.hd * 0.35, zc)
        else:
            self.kc = None

    def bays(self, a0, a1, bay=None):
        bay = bay or self.A["bay"]
        n = max(1, int(round((a1 - a0) / bay)))
        w = (a1 - a0) / n
        return [(a0 + i * w, a0 + (i + 1) * w) for i in range(n)]

    def stair_hole(self):
        x0, x1, y0, y1 = self.stair
        return (x0, x1, y0 + 1.2, y1)

    def collapsed(self, x, y, l):
        """True if level l has no floor at (x, y) (collapse) - used for loot and tests."""
        return self.state == 2 and l >= self.kc and self.ruin.inside(x, y)

    def near_collapse(self, x, y, l, margin=3.0):
        """Ruins may seal rooms behind the rubble below / beside the collapse (D56): no loot there."""
        if self.state != 2 or l < self.kc - 1:
            return False
        r = self.ruin.region
        return r[0] - margin <= x <= r[1] + margin and r[2] - margin <= y <= r[3] + margin


# ================================================================== floor plans (per use)
def layout(P, use, l):
    """Partitions [("x"|"y", c, a0, a1, [(o0, o1)])] + rooms [(x0, x1, y0, y1, kind)] for one level."""
    ix0, ix1, iy0, iy1 = P.ix0, P.ix1, P.iy0, P.iy1
    h = PT / 2
    walls, rooms = [], []
    st = P.stair
    if st:
        sx0, sx1, sy0, sy1 = st
        if sx0 > ix0 + 1e-6:
            walls.append(("y", sx0 - h, sy0, iy1, []))
        if sx1 < ix1 - 1e-6:
            walls.append(("y", sx1 + h, sy0, iy1, []))
    if use == "house":
        sx0, sx1, sy0, sy1 = st
        walls.append(("x", sy0 - h, sx1 + PT, ix1, [(-0.45, 0.45)]))
        if l == 0:
            rooms += [(ix0, ix1, iy0, sy0 - PT, "living"), (sx1 + PT, ix1, sy0, iy1, "kitchen")]
        else:
            walls.append(("y", 0.9, iy0, sy0 - PT, [(-1.6, -0.7)]))
            rooms += [(ix0, 0.9 - h, iy0, sy0 - PT, "bedroom"), (0.9 + h, ix1, iy0, sy0 - PT, "bedroom"),
                      (sx1 + PT, ix1, sy0, iy1, "bedroom")]
    elif use == "flats":
        sx0, sx1, sy0, sy1 = st
        walls = [("y", sx0 - h, iy0, iy1, [(sy0 - 1.6, sy0 - 0.6)]), ("y", sx1 + h, iy0, iy1, [(sy0 - 1.6, sy0 - 0.6)]),
                 ("x", 0.6, ix0, sx0 - PT, [(sx0 - 2.6, sx0 - 1.7)]), ("x", 0.6, sx1 + PT, ix1, [(sx1 + 1.7, sx1 + 2.6)])]
        rooms += [(ix0, sx0 - PT, iy0, 0.6 - h, "living"), (ix0, sx0 - PT, 0.6 + h, iy1, "bedroom"),
                  (sx1 + PT, ix1, iy0, 0.6 - h, "living"), (sx1 + PT, ix1, 0.6 + h, iy1, "bedroom"),
                  (sx0, sx1, iy0, sy0, "hall")]
    elif use == "shop":
        sx0, sx1, sy0, sy1 = st
        walls.append(("x", sy0 - h, ix0, sx0 - PT, [(1.0, 2.0)]))
        rooms += [(ix0, ix1, iy0, sy0 - PT, "shop"), (ix0, sx0 - PT, sy0, iy1, "storage")]
    elif use == "flat":
        sx0, sx1, sy0, sy1 = st
        walls += [("x", sy0 - h, ix0, sx0 - PT, [(1.6, 2.5)]), ("y", 0.0, iy0, sy0 - PT, [(-1.6, -0.7)])]
        rooms += [(ix0, -h, iy0, sy0 - PT, "living"), (h, ix1, iy0, sy0 - PT, "kitchen"), (ix0, sx0 - PT, sy0, iy1, "bedroom")]
    elif use == "office_lobby":
        rooms += [(ix0, ix1, iy0, st[2] - 0.2, "lobby")]
    elif use == "office":
        walls += [("x", -4.0, ix0, -4.6, [(-6.6, -5.7)]), ("y", -4.6, iy0, -4.0 - h, []),
                  ("x", -4.0, 4.6, ix1, [(5.7, 6.6)]), ("y", 4.6, iy0, -4.0 - h, [])]
        rooms += [(ix0, -4.6 - h, iy0, -4.0 - h, "office"), (4.6 + h, ix1, iy0, -4.0 - h, "office"),
                  (ix0, ix1, -4.0 + h, st[2] - 0.2, "open_office")]
    elif use == "warehouse":
        ox = ix0 + min(5.7, 0.25 * P.W)                        # site office in the back-left corner
        oy = iy1 - min(5.0, 0.3 * P.D)
        walls += [("y", ox, oy, iy1, []), ("x", oy, ix0, ox - h, [(ix0 + 1.0, ix0 + 2.0)])]
        rooms += [(ix0, ox - h, oy + h, iy1, "site_office"), (ix0, ix1, iy0, oy - h, "warehouse")]
    elif use == "police_ground":
        sx0, sx1, sy0, sy1 = st
        walls += [("x", -1.0, ix0, ix1, [(-6.5, -5.5), (2.4, 3.4)]), ("y", -2.5, -1.0 + h, iy1, [(0.0, 0.9)]),
                  ("y", 2.0, 2.5, iy1, []), ("y", 4.57, 2.5, iy1, []), ("y", 7.13, 2.5, iy1, [])]
        rooms += [(ix0, ix1, iy0, -1.0 - h, "police_lobby"), (-2.5 + h, 2.0 - h, -1.0 + h, iy1, "office"),
                  (2.0 + h, 4.57 - h, 2.5, iy1, "cell"), (4.57 + h, 7.13 - h, 2.5, iy1, "cell"), (7.13 + h, ix1, 2.5, iy1, "cell")]
    elif use == "police_upper":
        sx0, sx1, sy0, sy1 = st
        walls += [("x", -1.5, ix0, ix1, [(-5.0, -4.1), (0.0, 0.9), (5.0, 5.9)]), ("y", -1.0, iy0, -1.5 - h, []),
                  ("y", 4.5, iy0, -1.5 - h, []), ("x", 2.8, sx1 + PT, ix1, [(-3.0, -2.1), (3.0, 3.9)]),
                  ("y", 1.0, 2.8 + h, iy1, [])]
        rooms += [(ix0, -1.0 - h, iy0, -1.5 - h, "office"), (-1.0 + h, 4.5 - h, iy0, -1.5 - h, "office"),
                  (4.5 + h, ix1, iy0, -1.5 - h, "office"), (sx1 + PT, 1.0 - h, 2.8 + h, iy1, "office"),
                  (1.0 + h, ix1, 2.8 + h, iy1, "office")]
    return walls, rooms


# ================================================================== furniture kit (baked, coherent)
UV_OAK, UV_WALNUT = DT.UV_OAK, DT.UV_WALNUT
UV_LAMINATE = UVBand(S.MATERIALS["wood"]["bands"]["laminate"], 2.0)
UV_FAB = {k: UVBand(S.MATERIALS["fabric"]["bands"][k], 1.0) for k in ("grey", "blue", "beige")}


def piece(L, box, mat, uv, pen="wood", collide=True, res1=True, view=False):
    """A furniture solid: Res0 (+Res1), one collision box, Fire."""
    L["res0"].box(*box, mat=mat, uv=uv)
    if res1:
        L["res1"].box(*box, mat=mat, uv=uv, skip=("-z",))
    if collide:
        L["geo"].box(*box)
        L["fire"].box(*box, mat="pen_" + pen)
        if view:
            L["view"].box(*box)


def bed(L, x0, x1, y0, y1, z, fabric="blue"):
    piece(L, (x0, x1, y0, y1, z, z + 0.35), "wood", UV_WALNUT)
    L["res0"].box(x0 + 0.05, x1 - 0.05, y0 + 0.05, y1 - 0.05, z + 0.35, z + 0.55, mat="fabric", uv=UV_FAB[fabric])
    hy = (y1 - 0.08, y1) if (y1 - y0) > (x1 - x0) else (y0, y0 + 0.08)
    L["res0"].box(x0, x1, hy[0], hy[1], z + 0.35, z + 1.0, mat="wood", uv=UV_WALNUT)


def wardrobe(L, x0, x1, y0, y1, z):
    piece(L, (x0, x1, y0, y1, z, z + 2.1), "wood", UV_OAK, view=True)


def kitchen_run(L, x0, x1, y0, y1, z):
    """Counter with worktop, sink and upper cabinets (wall side = the thin side touching the wall)."""
    piece(L, (x0, x1, y0, y1, z, z + 0.88), "wood", UV_LAMINATE)
    L["res0"].box(x0 - 0.02, x1 + 0.02, y0 - 0.02, y1 + 0.02, z + 0.88, z + 0.92, mat="stone", uv=DT.stone_uv("granite"))
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    L["res0"].box(cx - 0.3, cx + 0.3, cy - 0.2, cy + 0.2, z + 0.921, z + 0.93, mat="metal", uv=DT.UV_STEEL)


def table(L, x0, x1, y0, y1, z, h=0.75):
    L["res0"].box(x0, x1, y0, y1, z + h - 0.04, z + h, mat="wood", uv=UV_OAK)
    for (lx, ly) in ((x0 + 0.05, y0 + 0.05), (x1 - 0.05, y0 + 0.05), (x0 + 0.05, y1 - 0.05), (x1 - 0.05, y1 - 0.05)):
        L["res0"].box(lx - 0.03, lx + 0.03, ly - 0.03, ly + 0.03, z, z + h - 0.04, mat="metal", uv=DT.UV_PAINT,
                      skip=("-z", "+z"))
    L["res1"].box(x0, x1, y0, y1, z + h - 0.04, z + h, mat="wood", uv=UV_OAK)
    L["geo"].box(x0, x1, y0, y1, z, z + h)
    L["fire"].box(x0, x1, y0, y1, z + h - 0.04, z + h, mat="pen_wood")


def desk(L, x, y, z, rot=False):
    """1.6 x 0.8 desk with a monitor (atlas) and a chair block."""
    w, d = (0.8, 1.6) if rot else (1.6, 0.8)
    table(L, x - w / 2, x + w / 2, y - d / 2, y + d / 2, z)
    L["res0"].box(x - 0.25, x + 0.25, y - 0.05, y + 0.05, z + 0.76, z + 1.1, mat="metal", uv=DT.UV_PAINT)


def shelf_unit(L, x0, x1, y0, y1, z, h=1.9, goods=True):
    """Steel shelving with 4 shelves; goods boxes on the shelves (Res0)."""
    for (a, b) in ((x0, x0 + 0.04), (x1 - 0.04, x1)):
        L["res0"].box(a, b, y0, y1, z, z + h, mat="metal", uv=DT.UV_PAINT, skip=("-z",))
    for k in range(4):
        zz = z + 0.15 + k * (h - 0.2) / 3.5
        L["res0"].box(x0, x1, y0, y1, zz, zz + 0.03, mat="metal", uv=DT.UV_PAINT)
        if goods:
            n = max(1, int((x1 - x0) / 0.45))
            for i in range(n):
                if h01("goods", round(x0, 2), round(y0, 2), k, i) < 0.75:
                    gx = x0 + 0.08 + i * (x1 - x0 - 0.16) / n
                    L["res0"].box(gx, gx + (x1 - x0 - 0.2) / n, y0 + 0.05, y1 - 0.05, zz + 0.03, zz + 0.3,
                                  mat="textile" if (i + k) % 3 == 0 else "wood",
                                  uv=DT.band_fit("textile", "rug_a", gx, gx + 0.4, y0, y1) if (i + k) % 3 == 0 else UV_LAMINATE)
    L["res1"].box(x0, x1, y0, y1, z, z + h, mat="metal", uv=DT.UV_PAINT, skip=("-z",))
    L["geo"].box(x0, x1, y0, y1, z, z + h)
    L["fire"].box(x0, x1, y0, y1, z, z + h, mat="pen_metal")


def bars(L, axis, c, a0, a1, z0, z1, openings=()):
    """Barred wall (cells): blocks movement (Geometry), not sight or bullets (no View / Fire)."""
    segs, cur = [], a0
    for o0, o1 in sorted(openings):
        segs.append((cur, o0))
        cur = o1
    segs.append((cur, a1))
    for g0, g1 in segs:
        if g1 - g0 < 0.05:
            continue
        n = int((g1 - g0) / 0.14)
        for i in range(n + 1):
            a = g0 + i * (g1 - g0) / max(1, n)
            if axis == "x":
                L["res0"].box(a - 0.012, a + 0.012, c - 0.012, c + 0.012, z0, z1, mat="metal", uv=DT.UV_STEEL, skip=("-z", "+z"))
            else:
                L["res0"].box(c - 0.012, c + 0.012, a - 0.012, a + 0.012, z0, z1, mat="metal", uv=DT.UV_STEEL, skip=("-z", "+z"))
        for zz in (z0 + 0.05, z1 - 0.1):
            box = (g0, g1, c - 0.03, c + 0.03, zz, zz + 0.05) if axis == "x" else (c - 0.03, c + 0.03, g0, g1, zz, zz + 0.05)
            L["res0"].box(*box, mat="metal", uv=DT.UV_STEEL)
            L["res1"].box(*box, mat="metal", uv=DT.UV_STEEL)
        box = (g0, g1, c - 0.03, c + 0.03, z0, z1) if axis == "x" else (c - 0.03, c + 0.03, g0, g1, z0, z1)
        L["geo"].box(*box)


def rubble_pile(L, x, y, z, rx, ry, h, key, collide=True):
    """Collapse debris mound: convex elliptic frustum (collides) + loose chunks (Res0)."""
    n = 8
    rot = h01("rub", key) * math.pi
    base = [(x + rx * math.cos(rot + 2 * math.pi * k / n), y + ry * math.sin(rot + 2 * math.pi * k / n), z) for k in range(n)]
    tx, ty = x + 0.15 * rx * (h01("rubx", key) - 0.5), y + 0.15 * ry * (h01("ruby", key) - 0.5)
    topr = 0.35
    top = [(tx + rx * topr * math.cos(rot + 2 * math.pi * k / n), ty + ry * topr * math.sin(rot + 2 * math.pi * k / n), z + h)
           for k in range(n)]
    faces = [tuple(range(n)), tuple(range(n, 2 * n))] + [(k, (k + 1) % n, n + (k + 1) % n, n + k) for k in range(n)]
    for k in ("res0", "res1", "res2") + (("geo", "fire", "view") if collide else ()):
        kw = {"mat": "rubble", "uv": UV_RUBBLE} if k.startswith("res") else ({"mat": "pen_concrete"} if k == "fire" else {})
        L[k].solid(base + top, faces, **kw)
    for i in range(6):
        a = 2 * math.pi * h01("chunk", key, i)
        d = 0.5 + 0.6 * h01("chunkd", key, i)
        cx, cy = x + math.cos(a) * rx * d, y + math.sin(a) * ry * d
        s = 0.12 + 0.25 * h01("chunks", key, i)
        L["res0"].box(cx - s, cx + s, cy - s * 0.7, cy + s * 0.7, z, z + s * 0.8,
                      mat="brick" if i % 2 else "concrete", uv=UV_REVEAL if i % 2 == 0 else UVWorld(2.0))


# ================================================================== facades
class FSide:
    """Facade side of a W x D footprint; d = depth inward from the outer face (d < 0 outside)."""

    def __init__(self, P, key):
        hw, hd = P.hw, P.hd
        self.key = key
        self.axis, self.plane = {"S": ("x", -hd), "N": ("x", hd), "W": ("y", -hw), "E": ("y", hw)}[key]
        self.sgn = 1 if self.plane > 0 else -1
        span = hw if self.axis == "x" else hd - WT                # E/W butt into S/N
        self.a0, self.a1 = -span, span
        ax = "y" if self.axis == "x" else "x"
        self.out_key = ("+" if self.sgn > 0 else "-") + ax
        self.in_key = ("-" if self.sgn > 0 else "+") + ax
        self.out = (0, self.sgn, 0) if self.axis == "x" else (self.sgn, 0, 0)
        self.inward = tuple(-v for v in self.out)
        self.ends = ("-" + self.axis, "+" + self.axis)

    def d(self, depth):
        return self.plane - self.sgn * depth

    def box(self, lod, a0, a1, z0, z1, d0, d1, **kw):
        p, q = sorted((self.d(d0), self.d(d1)))
        if self.axis == "x":
            lod.box(a0, a1, p, q, z0, z1, **kw)
        else:
            lod.box(p, q, a0, a1, z0, z1, **kw)

    def rect(self, a0, a1, z0, z1, depth):
        c = self.d(depth)
        if self.axis == "x":
            return [(a0, c, z0), (a1, c, z0), (a1, c, z1), (a0, c, z1)]
        return [(c, a0, z0), (c, a1, z0), (c, a1, z1), (c, a0, z1)]

    def quad(self, lod, a0, a1, z0, z1, depth, inward=False, **kw):
        lod.quad(self.rect(a0, a1, z0, z1, depth), self.inward if inward else self.out, **kw)

    def uvax(self):
        return 0 if self.axis == "x" else 1


def skin_uv(P, skin):
    m = S.CITY_SKINS[skin]["mat"]
    if m == "brick":
        return DT._brick_uv("bond")
    if m == "concpanel":
        return DT._panel_uv("panel")
    if m == "render":
        return UVBand(S.MATERIALS["render"]["bands"][P.A["skin"][1] or "cream"], 4.0)
    if m == "stone":
        return DT.stone_uv("limestone")
    return UVBand(S.MATERIALS["metal"]["bands"]["alu"], 2.0)          # light aluminium cladding


def wall_piece(L, sd, a0, a1, z0, z1, mat, uv, pen, inner, keys=("res0", "res1", "view", "fire")):
    """Solid facade piece (pier / sill / head) with an interior finish face."""
    if a1 - a0 < 1e-3 or z1 - z0 < 1e-3:
        return
    for k in keys:
        kw = kw_for(k, mat, uv, pen)
        if k.startswith("res"):
            kw["skip"] = (sd.in_key,)
        sd.box(L[k], a0, a1, z0, z1, 0.0, WT, **kw)
    if inner:
        for k in ("res0", "res1"):
            sd.quad(L[k], a0, a1, z0, z1, WT, inward=True, mat=inner[0], uv=inner[1])


def window(L, P, sd, a0, a1, s0, s1, skin, key, rec, residential, frame_uv):
    """Window in an opening a0..a1 x s0..s1: glass / broken / boarded per the ruin layer."""
    state = P.ruin.window(sd.key, *key)
    r0 = L["res0"]
    ax = sd.uvax()
    if state != "broken" or P.state < 2:                                   # frame survives damage
        fw = 0.06
        fkw = {"mat": "metal", "uv": frame_uv}
        sd.box(r0, a0, a0 + fw, s0, s1, rec - 0.03, rec + 0.03, skip=("-z", "+z"), **fkw)
        sd.box(r0, a1 - fw, a1, s0, s1, rec - 0.03, rec + 0.03, skip=("-z", "+z"), **fkw)
        sd.box(r0, a0 + fw, a1 - fw, s1 - fw, s1, rec - 0.03, rec + 0.03, **fkw)
        sd.box(r0, a0 + fw, a1 - fw, s0, s0 + fw, rec - 0.03, rec + 0.03, **fkw)
        if a1 - a0 > 1.15 and state == "glass":
            m = (a0 + a1) / 2
            sd.box(r0, m - 0.03, m + 0.03, s0 + fw, s1 - fw, rec - 0.03, rec + 0.03, skip=("-z", "+z"), **fkw)
    if state == "glass":
        L["res0"].quad(sd.rect(a0, a1, s0, s1, rec), sd.out, "glass", UV_GLASS, double=True)
        L["res1"].quad(sd.rect(a0, a1, s0, s1, rec), sd.out, "glass", UV_GLASS)
        sd.box(L["fire"], a0, a1, s0, s1, rec - 0.01, rec + 0.01, mat="pen_glass")
    elif state == "boarded":
        n = 4
        for i in range(n):
            z = s0 + 0.08 + i * (s1 - s0 - 0.25) / (n - 1)
            tilt = 0.04 * (h01(P.name, "board", sd.key, key, i) - 0.5)
            for k in ("res0", "res1"):
                sd.box(L[k], a0 - 0.08, a1 + 0.08, z + tilt, z + 0.18 + tilt, -0.03, 0.0, mat="wood", uv=UV_OAK)
            sd.box(L["fire"], a0 - 0.08, a1 + 0.08, z, z + 0.18, -0.03, 0.0, mat="pen_wood")
    if state == "broken":                                                   # soot plume over the opening
        r0.quad(sd.rect(a0 - 0.3, a1 + 0.3, s1 - 0.1, s1 + 1.1, -0.006), sd.out, "decal_dirt",
                UVRect(ax, 2, (a0 - 0.3, s1 - 0.1), (a1 + 0.3, s1 + 1.1), (0, 1, 1, 0)))
        L["res0"].quad(sd.rect(a0, a1, s0, s1, WT - 0.02), sd.out, "glassfar", UV_GLASS)       # dark void
    if residential and state == "glass" and P.state == 0:                     # curtains inside
        for c0, c1 in ((a0 - 0.15, a0 + 0.3), (a1 - 0.3, a1 + 0.15)):
            uv = DT.band_fit("textile", "curtain", c0, c1, s0 - 0.6, s1 + 0.1, axes=(ax, 2), u_rep=0.8)
            sd.quad(r0, c0, c1, max(0.05, s0 - 0.6), s1 + 0.1, WT + 0.06, inward=True, mat="textile", uv=uv)
            sd.quad(r0, c0, c1, max(0.05, s0 - 0.6), s1 + 0.1, WT + 0.06, inward=False, mat="textile", uv=uv)
    return state


def facade(L, P, key, lvl):
    """One side, one level. Returns door/roller openings for the Geometry wall."""
    use, fh, z0 = P.levels[lvl]
    sd = FSide(P, key)
    A = P.A
    top = z0 + fh - SLAB
    skin = A["skin"][0]
    SK = S.CITY_SKINS[skin]
    mat, uv = SK["mat"], skin_uv(P, skin)
    pen = {"brick": "masonry", "metal": "metal"}.get(mat, "concrete")
    residential = A["group"] in ("residential", "mixed") and use not in ("shop",)
    inner = ("paint", DT.paint_uv("white")) if use not in ("warehouse",) else None
    frame_uv = DT.UV_PAINT
    shop = lvl == 0 and A.get("ground") == "shopfront" and key in A.get("shop_sides", ())
    blank = key in A.get("blank", ())
    bays = P.bays(sd.a0, sd.a1, 4.0 if skin == "metal" else None)
    openings = []
    rec = SK["recess"]
    run = []                                     # consecutive regular window bays: merged View/Fire

    def flush():
        """View / Fire for a run of window bays: one sill band, one head band, the piers."""
        if not run:
            return
        a0, a1 = run[0][0], run[-1][1]
        s0, s1 = run[0][4], run[0][5]
        piers = [(a0, run[0][2])] + [(run[j][3], run[j + 1][2]) for j in range(len(run) - 1)] + [(run[-1][3], a1)]
        for k in ("view", "fire"):
            kw = kw_for(k, mat, uv, pen)
            sd.box(L[k], a0, a1, z0, s0, 0.0, WT, **kw)
            sd.box(L[k], a0, a1, s1, top, 0.0, WT, **kw)
            for (pa, pb) in piers:
                if pb - pa > 1e-3:
                    sd.box(L[k], pa, pb, s0, s1, 0.0, WT, **kw)
        run.clear()

    for i, (b0, b1) in enumerate(bays):
        bkey = (lvl, i)
        door_here = key == "S" and lvl == 0 and (b0 <= P.door[0] <= b1)
        roller = key == "S" and lvl == 0 and i in A.get("roller_bays", ())
        if blank or shop or roller or door_here or skin in ("curtain", "metal"):
            flush()
        if blank:
            wall_piece(L, sd, b0, b1, z0, top, mat, uv, pen, inner)
            continue
        if shop:
            pier = 0.35
            glass_top = top - 0.7
            wall_piece(L, sd, b0, b0 + pier, z0, top, "stone", DT.stone_uv("granite"), "concrete", inner)
            wall_piece(L, sd, b1 - pier, b1, z0, top, "stone", DT.stone_uv("granite"), "concrete", inner)
            wall_piece(L, sd, b0 + pier, b1 - pier, glass_top, top, mat, uv, pen, inner)       # fascia
            g0, g1 = b0 + pier, b1 - pier
            if door_here:
                wall_piece(L, sd, g0, P.door[0], z0, 0.45, "stone", DT.stone_uv("granite"), "concrete", inner)
                wall_piece(L, sd, P.door[1], g1, z0, 0.45, "stone", DT.stone_uv("granite"), "concrete", inner)
                for (ga, gb) in ((g0, P.door[0]), (P.door[1], g1)):
                    if gb - ga > 0.2:
                        window(L, P, sd, ga, gb, 0.45, glass_top, skin, bkey + (ga,), 0.08, False, frame_uv)
                window(L, P, sd, P.door[0], P.door[1], ST["door"][1], glass_top, skin, bkey + ("t",), 0.08, False, frame_uv)
                openings.append((P.door[0], P.door[1], z0, z0 + ST["door"][1]))
            else:
                wall_piece(L, sd, g0, g1, z0, 0.45, "stone", DT.stone_uv("granite"), "concrete", inner)
                window(L, P, sd, g0, g1, 0.45, glass_top, skin, bkey, 0.08, False, frame_uv)
            continue
        if roller:
            w0, w1 = b0 + 0.3, b1 - 0.3
            dh = 4.5
            wall_piece(L, sd, b0, w0, z0, top, mat, uv, pen, inner)
            wall_piece(L, sd, w1, b1, z0, top, mat, uv, pen, inner)
            wall_piece(L, sd, w0, w1, z0 + dh, top, mat, uv, pen, inner)
            shutter_uv = UVBand(S.MATERIALS["metal"]["bands"]["steel"], 0.5)
            for k in ("res0", "res1", "res2", "view", "fire"):                          # closed roller shutter
                kw = kw_for(k, "metal", shutter_uv, "metal")
                sd.box(L[k], w0, w1, z0, z0 + dh, 0.12, 0.18, **kw)
            for j in range(int(dh / 0.1)):                                            # slats (Res0)
                sd.box(L["res0"], w0, w1, z0 + j * 0.1, z0 + j * 0.1 + 0.015, 0.105, 0.12, mat="metal",
                       uv=DT.UV_STEEL, skip=(sd.in_key,))
            sd.box(L["res0"], w0 - 0.1, w1 + 0.1, z0 + dh, z0 + dh + 0.45, -0.25, 0.0, mat="metal", uv=DT.UV_PAINT)
            if P.state == 2 and h01(P.name, "roller", i) < 0.6:
                pass                                                                    # shutters survive
            continue
        if skin == "curtain":
            spand = 0.9
            for (a, b) in ((b0, b0 + 0.08), (b1 - 0.08, b1)):                           # mullions
                for k in ("res0", "res1"):
                    sd.box(L[k], a, b, z0, top, -0.06, 0.1, mat="metal", uv=DT.UV_ALU, skip=("-z", "+z"))
            wall_piece(L, sd, b0 + 0.08, b1 - 0.08, top - spand + SLAB, top, "metal", DT.UV_PAINT, "metal", inner)
            if door_here:
                window(L, P, sd, b0 + 0.08, P.door[0], 0.0, top - spand + SLAB, skin, bkey + ("l",), rec, False, DT.UV_ALU)
                window(L, P, sd, P.door[1], b1 - 0.08, 0.0, top - spand + SLAB, skin, bkey + ("r",), rec, False, DT.UV_ALU)
                window(L, P, sd, P.door[0], P.door[1], ST["door"][1], top - spand + SLAB, skin, bkey + ("t",), rec, False,
                       DT.UV_ALU)
                openings.append((P.door[0], P.door[1], z0, z0 + ST["door"][1]))
            else:
                window(L, P, sd, b0 + 0.08, b1 - 0.08, z0, top - spand + SLAB, skin, bkey, rec, False, DT.UV_ALU)
            continue
        if skin == "metal":
            # ribbed cladding + clerestory strip window
            s0, s1 = z0 + fh - 2.5, z0 + fh - 1.4
            if door_here:
                d0, d1 = P.door
                wall_piece(L, sd, b0, d0, z0, s0, mat, uv, pen, inner)
                wall_piece(L, sd, d1, b1, z0, s0, mat, uv, pen, inner)
                wall_piece(L, sd, d0, d1, z0 + ST["door"][1], s0, mat, uv, pen, inner)
            else:
                wall_piece(L, sd, b0, b1, z0, s0, mat, uv, pen, inner)
            wall_piece(L, sd, b0, b1, s1, top, mat, uv, pen, inner)
            wall_piece(L, sd, b0, b0 + 0.3, s0, s1, mat, uv, pen, inner)
            wall_piece(L, sd, b1 - 0.3, b1, s0, s1, mat, uv, pen, inner)
            window(L, P, sd, b0 + 0.3, b1 - 0.3, s0, s1, skin, bkey, rec, False, DT.UV_PAINT)
            for j in range(int((b1 - b0) / 0.5)):
                a = b0 + 0.25 + j * 0.5
                if door_here and P.door[0] - 0.05 < a < P.door[1] + 0.05:
                    continue
                sd.box(L["res0"], a - 0.03, a + 0.03, z0, s0, -0.04, 0.0, mat="metal", uv=DT.UV_STEEL, skip=(sd.in_key, "-z"))
            if door_here:
                # personnel door cut into the cladding (wall pieces above stay)
                openings.append((P.door[0], P.door[1], z0, z0 + ST["door"][1]))
            continue
        # masonry window bay (brick / panel / render / stone)
        ww = min(SK["ww"], b1 - b0 - 0.5)
        c = (b0 + b1) / 2
        w0, w1 = c - ww / 2, c + ww / 2
        s0, s1 = z0 + SK["sill"], z0 + min(SK["head"], fh - SLAB - 0.35)
        if door_here:
            s0d = z0 + ST["door"][1]
            d0, d1 = P.door
            wall_piece(L, sd, b0, d0, z0, top, mat, uv, pen, inner)
            wall_piece(L, sd, d1, b1, z0, top, mat, uv, pen, inner)
            wall_piece(L, sd, d0, d1, s0d + 0.3, top, mat, uv, pen, inner)
            window(L, P, sd, d0, d1, s0d, s0d + 0.3, skin, bkey + ("t",), rec, False, frame_uv)          # transom
            openings.append((d0, d1, z0, z0 + ST["door"][1]))
            # door surround + canopy
            for k in ("res0", "res1"):
                sd.box(L[k], d0 - 0.18, d0, z0, s0d + 0.45, -0.05, 0.0, mat="stone", uv=DT.stone_uv("limestone"),
                       skip=(sd.in_key,))
                sd.box(L[k], d1, d1 + 0.18, z0, s0d + 0.45, -0.05, 0.0, mat="stone", uv=DT.stone_uv("limestone"),
                       skip=(sd.in_key,))
                sd.box(L[k], d0 - 0.4, d1 + 0.4, s0d + 0.45, s0d + 0.55, -0.9, 0.0, mat="metal", uv=DT.UV_PAINT)
            continue
        res = ("res0", "res1")
        wall_piece(L, sd, b0, w0, z0, top, mat, uv, pen, inner, keys=res)
        wall_piece(L, sd, w1, b1, z0, top, mat, uv, pen, inner, keys=res)
        wall_piece(L, sd, w0, w1, z0, s0, mat, uv, pen, inner, keys=res)
        wall_piece(L, sd, w0, w1, s1, top, mat, uv, pen, inner, keys=res)
        run.append((b0, b1, w0, w1, s0, s1))
        st = window(L, P, sd, w0, w1, s0, s1, skin, bkey, rec, residential, frame_uv)
        r0 = L["res0"]
        sd.box(r0, w0 - 0.05, w1 + 0.05, s0 - 0.06, s0 + 0.01, -0.06, rec, mat="stone", uv=DT.stone_uv("limestone"),
               skip=(sd.in_key,))
        if SK.get("soldier"):
            sd.quad(r0, w0 - 0.1, w1 + 0.1, s1, s1 + 0.22, -0.004, mat="brick", uv=DT._brick_uv("soldier"))
        else:
            sd.box(r0, w0 - 0.08, w1 + 0.08, s1, s1 + 0.12, -0.03, 0.0, mat="stone", uv=DT.stone_uv("limestone"),
                   skip=(sd.in_key,))
        if SK.get("shutters") and st != "broken":
            for (a, b) in ((w0 - 0.55, w0 - 0.03), (w1 + 0.03, w1 + 0.55)):
                sd.box(r0, a, b, s0, s1, -0.04, -0.005, mat="paint", uv=DT.paint_uv("sage"))
        if residential and st == "glass" and P.state == 0:                                  # radiator
            sd.box(r0, c - 0.5, c + 0.5, z0 + 0.15, z0 + 0.7, WT + 0.03, WT + 0.11, mat="paint", uv=DT.paint_uv("white"),
                   skip=(sd.out_key, "-z"))
        if A["group"] == "residential" and skin == "panel" and lvl > 0 and i % 2 == 1:      # french balcony rail
            for zz in (s0 + 0.15, s0 + 0.55, s0 + 0.95):
                sd.box(r0, w0 - 0.1, w1 + 0.1, zz, zz + 0.03, -0.2, -0.17, mat="metal", uv=DT.UV_STEEL)
            for a in (w0 - 0.1, (w0 + w1) / 2, w1 + 0.1):
                sd.box(r0, a - 0.015, a + 0.015, s0, s0 + 0.98, -0.2, -0.17, mat="metal", uv=DT.UV_STEEL, skip=("-z",))
    flush()
    return sd, openings


def facade_level_extras(L, P, sd, lvl, openings):
    """Geometry wall (one solid per side per level, split at door openings), Res2 outer quads,
    string course and plinth."""
    from skygeo import wall_x, wall_y
    use, fh, z0 = P.levels[lvl]
    top = z0 + fh - SLAB
    p, q = sorted((sd.d(0.0), sd.d(WT)))
    for k in ("geo", "shadow"):
        if sd.axis == "x":
            wall_x(L[k], sd.a0, sd.a1, p, q, z0, top, openings=openings if k == "geo" else ())
        else:
            wall_y(L[k], p, q, sd.a0, sd.a1, z0, top, openings=openings if k == "geo" else ())
    skin = P.A["skin"][0]
    mat = S.CITY_SKINS[skin]["mat"]
    uv = skin_uv(P, skin)
    shop = lvl == 0 and P.A.get("ground") == "shopfront" and sd.key in P.A.get("shop_sides", ())
    sd.quad(L["res2"], sd.a0, sd.a1, z0, top, 0.0, mat="glassfar" if (skin == "curtain" or shop) else mat,
            uv=UV_GLASS if (skin == "curtain" or shop) else uv)
    if mat in ("brick", "render", "stone", "concpanel") and lvl > 0:                        # string course
        sc = ST["string_course"]
        for k in ("res0", "res1"):
            sd.box(L[k], sd.a0 - (sc if sd.axis == "x" else 0), sd.a1 + (sc if sd.axis == "x" else 0),
                   z0 - SLAB - 0.02, z0 + 0.04, -sc, 0.0, mat="stone", uv=DT.stone_uv("limestone"), skip=(sd.in_key,))
    if lvl == 0 and skin not in ("metal", "curtain") and not shop:                         # plinth
        for k in ("res0", "res1"):
            segs, cur = [], sd.a0
            for (o0, o1, _a, _b) in sorted(openings):
                segs.append((cur, o0))
                cur = o1
            segs.append((cur, sd.a1))
            for a, b in segs:
                sd.box(L[k], a, b, z0, z0 + ST["plinth"], -0.04, 0.0, mat="stone", uv=DT.stone_uv("granite"),
                       skip=(sd.in_key, "-z"))


# ================================================================== shell: slabs, stairs, roof
class Shift:
    """Lod proxy that lifts every primitive by dz (reuse the floor-level detail kit on upper levels)."""

    def __init__(self, lod, dz):
        self.lod, self.dz = lod, dz

    def __getattr__(self, k):
        return getattr(self.lod, k)

    def _p(self, pts):
        return [(p[0], p[1], p[2] + self.dz) for p in pts]

    def box(self, x0, x1, y0, y1, z0, z1, **kw):
        self.lod.box(x0, x1, y0, y1, z0 + self.dz, z1 + self.dz, **kw)

    def quad(self, pts, facing, mat=None, uv=None, sel=(), double=False):
        if uv is not None:
            base_uv = uv
            uv = (lambda p, n, f=base_uv, dz=self.dz: f([(q[0], q[1], q[2] - dz) for q in p], n))
        self.lod.quad(self._p(pts), facing, mat, uv, sel, double)

    def hquad(self, x0, x1, y0, y1, z, mat=None, uv=None, sel=(), up=True):
        self.quad([(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)], (0, 0, 1 if up else -1), mat, uv, sel)

    def prism(self, cx, cy, r, z0, z1, n=8, mat=None, uv=None, sel=(), component=None, rot=0.0):
        self.lod.prism(cx, cy, r, z0 + self.dz, z1 + self.dz, n, mat, uv, sel, component, rot)

    def solid(self, verts, faces, mat=None, uv=None, sel=(), component=None):
        self.lod.solid(self._p(verts), faces, mat, uv, sel, component)

    def extrude_y(self, profile, y0, y1, **kw):
        self.lod.extrude_y([(a, b + self.dz) for a, b in profile], y0, y1, **kw)

    def extrude_x(self, profile, x0, x1, **kw):
        self.lod.extrude_x([(a, b + self.dz) for a, b in profile], x0, x1, **kw)


def lifted(L, dz):
    return {k: Shift(v, dz) for k, v in L.items()}


def slabs(L, P):
    hw, hd = P.hw, P.hd
    n = len(P.levels)
    for l, (use, fh, z) in enumerate(P.levels + [("roof", 0.0, P.top)]):
        holes = [P.stair_hole()] if (P.stair and 1 <= l < n) else []
        for (x0, x1, y0, y1) in rects_minus(-hw, hw, -hd, hd, holes):
            for k in ("res0", "res1", "res2", "geo", "view", "fire"):
                kw = kw_for(k, "concrete", UV_REVEAL, "concrete")
                L[k].box(x0, x1, y0, y1, z - SLAB, z, **kw)
            if l < n:
                L["road"].hquad(max(x0, P.ix0), min(x1, P.ix1), max(y0, P.iy0), min(y1, P.iy1), z, mat="road_int", uv=UV_TILE)
    L["shadow"].box(-hw, hw, -hd, hd, P.top - SLAB, P.top)
    sk = ST["skirt"]
    ring = [(-hw, hw, -hd, -hd + WT), (-hw, hw, hd - WT, hd), (-hw, -hw + WT, -hd + WT, hd - WT), (hw - WT, hw, -hd + WT, hd - WT)]
    for (x0, x1, y0, y1) in ring:
        for k in ("res0", "res1", "res2", "geo", "fire"):
            kw = kw_for(k, "stone", DT.stone_uv("granite"), "concrete")
            if k.startswith("res"):
                kw["skip"] = ("+z", "-z")
            L[k].box(x0, x1, y0, y1, -sk, -SLAB, **kw)


def stairs(L, P):
    if not P.stair:
        return
    x0, x1, y0, y1 = P.stair
    cx = (x0 + x1) / 2
    xa, xb = (x0, cx - 0.15), (cx + 0.15, x1)
    yA0 = y0 + 1.2
    n_lv = len(P.levels)
    for l in range(n_lv - 1):
        use, fh, z0 = P.levels[l]
        n = math.ceil(fh / 2 / ST["riser_max"])
        tread = ST["tread"]
        yA1 = yA0 + n * tread
        half = fh / 2
        zm, zt = z0 + half, z0 + fh
        for k in ("res0", "res1", "geo", "fire", "view"):
            kw = kw_for(k, "concrete", UV_REVEAL, "concrete")
            L[k].box(x0, x1, yA1, y1, zm - 0.2, zm, **kw)                       # mid landing
            L[k].box(cx - 0.15, cx + 0.15, yA0, yA1, z0, zt, **kw)              # well wall
        L["road"].hquad(x0, x1, yA1, y1, zm, mat="road_int", uv=UV_TILE)
        for i in range(n):
            ya = yA0 + i * tread
            za = z0 + (i + 1) * half / n
            L["res0"].box(xa[0], xa[1], ya, ya + tread, za - 0.25, za, mat="concrete", uv=UV_REVEAL,
                          skip=("-x", "+x") + (("-z",) if i else ()))
            L["res0"].box(xa[0], xa[1], ya, ya + 0.04, za - 0.03, za + 0.004, mat="metal", uv=DT.UV_STEEL,
                          skip=("-x", "+x", "-z"))
            yb = yA1 - (i + 1) * tread
            zb = zm + (i + 1) * half / n
            L["res0"].box(xb[0], xb[1], yb, yb + tread, zb - 0.25, zb, mat="concrete", uv=UV_REVEAL,
                          skip=("-x", "+x") + (("-z",) if i else ()))
            L["res0"].box(xb[0], xb[1], yb + tread - 0.04, yb + tread, zb - 0.03, zb + 0.004, mat="metal", uv=DT.UV_STEEL,
                          skip=("-x", "+x", "-z"))
        L["res1"].ramp(xa[0], xa[1], yA0, yA1, z0, zm, mat="concrete", uv=UV_REVEAL)
        L["res1"].ramp(xb[0], xb[1], yA1, yA0, zm, zt, mat="concrete", uv=UV_REVEAL)
        for k in ("geo", "fire"):
            kw = {"mat": "pen_concrete"} if k == "fire" else {}
            L[k].wedge(xa[0], xa[1], yA0, yA1, z0 - 0.25, z0, zm, **kw)
            L[k].wedge(xb[0], xb[1], yA1, yA0, zm - 0.25, zm, zt, **kw)
        L["road"].ramp(xa[0], xa[1], yA0, yA1, z0, zm, mat="road_int", uv=UV_TILE)
        L["road"].ramp(xb[0], xb[1], yA1, yA0, zm, zt, mat="road_int", uv=UV_TILE)
        for (xr, ya_, yb_, za_, zb_) in ((xa[1] - 0.06, yA0, yA1, z0, zm), (xb[0] + 0.06, yA1, yA0, zm, zt)):  # handrails
            ring = [(-0.025, -0.025), (0.025, -0.025), (0.025, 0.025), (-0.025, 0.025)]
            verts = [(xr + a, ya_, za_ + 0.95 + b) for a, b in ring] + [(xr + a, yb_, zb_ + 0.95 + b) for a, b in ring]
            L["res0"].solid(verts, [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)],
                            mat="metal", uv=DT.UV_STEEL)
        L["res0"].box(cx - 0.2, cx + 0.2, y1 - 0.07, y1, zt - 0.45, zt - 0.35, mat="lamp", skip=("+y",))   # bulkhead light
    # top level: guard over the open flight-A well
    _u, _fh, ztop = P.levels[-1]
    for k in ("res0", "res1", "geo", "fire"):
        kw = kw_for(k, "metal", DT.UV_PAINT, "metal")
        L[k].box(xa[0], xa[1], yA0, yA0 + 0.05, ztop, ztop + 1.0, **kw)


def front_door(L, P):
    """Hinged front door leaf (bone door_front), frame; none in the ruined state."""
    d0, d1 = P.door
    y = -P.hd + WT / 2
    dh = ST["door"][1]
    for k in ("res0", "res1"):
        sd = FSide(P, "S")
        sd.box(L[k], d0 - 0.06, d0, 0.0, dh + 0.06, 0.0, WT, mat="metal", uv=DT.UV_PAINT, skip=("-z",))
        sd.box(L[k], d1, d1 + 0.06, 0.0, dh + 0.06, 0.0, WT, mat="metal", uv=DT.UV_PAINT, skip=("-z",))
        sd.box(L[k], d0, d1, dh, dh + 0.06, 0.0, WT, mat="metal", uv=DT.UV_PAINT)
    if P.state == 2:
        return
    name = "door_front"
    leaf = (d0 + 0.01, d1 - 0.01, y - 0.025, y + 0.025, 0.0, dh - 0.01)
    wood = P.A["group"] == "residential"
    vis = {"mat": "wood", "uv": UV_WALNUT} if wood else {"mat": "metal", "uv": DT.UV_PAINT}
    for k in ("res0", "res1", "geo", "view", "fire", "shadow"):
        kw = dict(vis) if k.startswith("res") else ({"mat": "pen_wood" if wood else "pen_metal"} if k == "fire" else {})
        L[k].lod.box(*leaf, sel=[name], **kw)
    L["res0"].lod.box(d1 - 0.18, d1 - 0.1, y - 0.06, y - 0.025, 1.0, 1.1, mat="metal", uv=DT.UV_STEEL, sel=[name])   # handle
    m = L["mem"].lod
    m.point(name + "_axis", (d0 + 0.01, y, 0.0))
    m.point(name + "_axis", (d0 + 0.01, y, dh))
    m.point(name + "_action", ((d0 + d1) / 2, -P.hd + WT + 0.8, 1.1))
    m.point(name, ((d0 + d1) / 2, y, 1.1))


def partitions(L, P, walls, z0, top, band):
    from skygeo import wall_x, wall_y
    for k in ("res0", "res1", "geo", "view", "fire"):
        kw = kw_for(k, "paint", DT.paint_uv(band), "masonry")
        for axis, c, a0, a1, ops in walls:
            o = [(a, b, z0, z0 + 2.1) for (a, b) in ops]
            if axis == "x":
                wall_x(L[k], a0, a1, c - PT / 2, c + PT / 2, z0, top, openings=o, **kw)
            else:
                wall_y(L[k], c - PT / 2, c + PT / 2, a0, a1, z0, top, openings=o, **kw)
    Lz = lifted(L, z0)
    DT.door_trims(Lz, walls, PT / 2)
    DT.skirting(Lz, walls, PT / 2)


FLOOR = {"living": "parquet", "bedroom": "parquet", "kitchen": "tile", "hall": "tile", "shop": "tile", "storage": None,
         "lobby": "marble", "open_office": "carpet", "office": "carpet", "site_office": "carpet", "warehouse": None,
         "police_lobby": "tile", "cell": None}
CEIL = {"lobby": "ceiling", "open_office": "ceiling", "office": "ceiling", "shop": "ceiling", "police_lobby": "ceiling"}
WALL_BAND = {"house": "beige", "flats": "sage", "flat": "white", "shop": "white", "office_lobby": "white",
             "office": "slate", "warehouse": "white", "police_ground": "slate", "police_upper": "white"}


def finish_uv(mat):
    return {"parquet": DT.UV_PARQUET, "tile": UV_TILE, "marble": DT.UV_MARBLE, "carpet": UV_CARPET}[mat]


def interior(L, P, l):
    use, fh, z0 = P.levels[l]
    top = z0 + fh - SLAB
    walls, rooms = layout(P, use, l)
    partitions(L, P, walls, z0, top, WALL_BAND.get(use, "white"))
    hole_up = [P.stair_hole()] if (P.stair and l + 1 < len(P.levels)) else []
    stair = [P.stair] if P.stair else []
    for (x0, x1, y0, y1) in rects_minus(P.ix0, P.ix1, P.iy0, P.iy1, hole_up):        # ceiling under the next slab
        cm = "ceiling" if use in ("office_lobby", "office", "shop", "police_ground", "police_upper") else "paint"
        if use == "warehouse":
            continue
        for k in ("res0", "res1"):
            L[k].hquad(x0, x1, y0, y1, top - 0.02, mat=cm, uv=DT.UV_CEILING if cm == "ceiling" else DT.paint_uv("white"), up=False)
    for (x0, x1, y0, y1, kind) in rooms:
        fm = FLOOR.get(kind)
        if fm:
            for (a, b, c, d) in rects_minus(x0, x1, y0, y1, stair):
                for k in ("res0", "res1"):
                    L[k].hquad(a, b, c, d, z0 + 0.004, mat=fm, uv=finish_uv(fm))
        furnish(L, P, l, (x0, x1, y0, y1), kind, z0, top)
    if P.state == 1:                                                              # damage: debris, fallen tiles
        for i, (x0, x1, y0, y1, kind) in enumerate(rooms):
            if h01(P.name, "debris", l, i) < 0.6:
                cx = x0 + (x1 - x0) * (0.25 + 0.5 * h01(P.name, "dx", l, i))
                cy = y0 + (y1 - y0) * (0.25 + 0.5 * h01(P.name, "dy", l, i))
                if not (P.stair and P.stair[0] - 0.5 < cx < P.stair[1] + 0.5 and P.stair[2] - 1.5 < cy):
                    rubble_pile(L, cx, cy, z0, 0.45, 0.35, 0.25, (P.name, l, i), collide=False)


def keep_clear(P, l):
    """Zones no furniture may enter on level l: inside the front door, both sides of every
    partition opening, the stair landing and its exit (walkability, test_city)."""
    use, fh, z = P.levels[l]
    zones = []
    if l == 0:
        zones.append((P.door[0] - 0.3, P.door[1] + 0.3, P.iy0 - 0.1, P.iy0 + 1.6))
    for axis, c, _a0, _a1, ops in layout(P, use, l)[0]:
        for (o0, o1) in ops:
            zones.append((o0 - 0.2, o1 + 0.2, c - 1.1, c + 1.1) if axis == "x" else (c - 1.1, c + 1.1, o0 - 0.2, o1 + 0.2))
    if P.stair:
        sx0, sx1, sy0, sy1 = P.stair
        zones.append((sx0 - 0.3, sx1 + 0.3, sy0 - 1.6, sy1))
    if use == "police_ground":
        for (o0, o1) in ((2.9, 3.7), (5.4, 6.2), (8.0, 8.8)):                     # cell doorways
            zones.append((o0 - 0.2, o1 + 0.2, 1.4, 3.6))
    return zones


def clear(zones, box):
    x0, x1, y0, y1 = box[:4]
    return not any(x0 < b[1] and b[0] < x1 and y0 < b[3] and b[2] < y1 for b in zones)


def furnish(L, P, l, r, kind, z, top):
    """Baked furniture and fixtures per room kind (coherent kit, collides where walkable).
    Every collidable piece is skipped if it would enter a keep-clear zone (doors, stair)."""
    x0, x1, y0, y1 = r
    zones = keep_clear(P, l)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    w, d = x1 - x0, y1 - y0
    Lz = lifted(L, z)
    lit = P.state == 0
    lamp = "lamp" if lit else None
    if kind in ("living", "bedroom", "kitchen", "hall"):
        if lamp:
            DT.pendant(L, cx, cy, top - 0.02, 0.55 if kind != "hall" else 0.35, r=0.22)
        else:
            L["res0"].prism(cx, cy, 0.22, top - 0.6, top - 0.35, n=12, mat="metal", uv=DT.UV_PAINT)
    if kind == "living" and w > 2.6 and d > 2.6:
        DT.rug(Lz, cx - 1.0, cx + 1.0, cy - 0.7, cy + 0.7, "rug_b" if h01(P.name, l, cx) < 0.5 else "rug_a")
        if clear(zones, (cx - 1.5, cx + 1.5, cy - 0.5, cy + 0.5)):
            DT.coffee_table(Lz, cx - 0.4, cx + 0.4, cy - 0.3, cy + 0.3)
            DT.lounge_chair(Lz, cx - 1.0, cy, "+x")
            DT.lounge_chair(Lz, cx + 1.0, cy, "-x")
        corners = sorted([(x0 + 0.45, y0 + 0.45), (x1 - 0.45, y0 + 0.45), (x0 + 0.45, y1 - 0.45), (x1 - 0.45, y1 - 0.45)],
                         key=lambda c: -(abs(c[0]) + abs(c[1])))               # outer corners first
        for (px, py) in corners:
            if clear(zones, (px - 0.35, px + 0.35, py - 0.35, py + 0.35)):
                DT.potted_plant(Lz, px, py, collide=True)
                break
        DT.wall_art(L, cx, y1 - 0.0 if y1 < P.iy1 - 0.01 else y1, z + 1.6, 0.8, 0.8, "-y", "art_%s" % "abcd"[int(h01(P.name, l, "art", cx) * 4)])
    elif kind == "bedroom" and w > 2.2 and d > 2.6:
        bw = 1.6 if w > 3.0 else 0.95
        if clear(zones, (cx - bw / 2, cx + bw / 2, y1 - 2.1, y1)):
            bed(L, cx - bw / 2, cx + bw / 2, y1 - 2.1, y1 - 0.05, z, fabric="blue" if h01(P.name, l, cy) < 0.5 else "beige")
        if w > 3.4 and clear(zones, (x0, x0 + 0.65, y1 - 1.7, y1)) and cx - bw / 2 - (x0 + 0.65) > 0.75:
            wardrobe(L, x0 + 0.05, x0 + 0.65, y1 - 1.7, y1 - 0.05, z)
        DT.rug(Lz, cx - 0.9, cx + 0.9, y1 - 3.0, y1 - 2.2, "rug_a")
    elif kind == "kitchen" and w > 2.0:
        for (ka, kb) in ((y1 - 0.62, y1 - 0.02), (y0 + 0.02, y0 + 0.62)):
            box = (x1 - min(w - 0.2, 3.1) - 0.1, x1 - 0.1, ka, kb)
            if clear(zones, box):
                kitchen_run(L, box[0], box[1], ka, kb, z)
                break
        if d > 3.0 and clear(zones, (cx - 0.5, cx + 0.5, cy - 0.4, cy + 0.4)):
            table(L, cx - 0.5, cx + 0.5, cy - 0.4, cy + 0.4, z)
    elif kind == "shop":
        for row_y in (cy - 1.3, cy + 0.3):
            shelf_unit(L, x0 + 1.0, cx - 0.4, row_y - 0.25, row_y + 0.25, z, h=1.6)
        kitchen_run(L, x1 - 2.4, x1 - 0.4, y0 + 1.2, y0 + 1.8, z)                     # counter
        L["res0"].box(x1 - 1.6, x1 - 1.2, y0 + 1.35, y0 + 1.65, z + 0.92, z + 1.15, mat="metal", uv=DT.UV_PAINT)  # till
        if lit:
            for gx in (x0 + 2.0, cx, x1 - 2.0):
                L["res0"].hquad(gx - 0.3, gx + 0.3, cy - 0.6, cy + 0.6, top - 0.025, mat="lamp_cool", up=False)
    elif kind == "storage" and clear(zones, (x0 + 0.2, x1 - 0.2, y1 - 0.6, y1 - 0.1)):
        shelf_unit(L, x0 + 0.2, x1 - 0.2, y1 - 0.6, y1 - 0.1, z, h=2.2)
    elif kind in ("lobby", "police_lobby"):
        if kind == "lobby":
            kitchen_run(L, cx - 1.6, cx + 1.6, y0 + 3.0, y0 + 3.7, z)
            DT.potted_plant(Lz, x0 + 0.8, y0 + 0.8, big=True, r=0.45)
            DT.potted_plant(Lz, x1 - 0.8, y0 + 0.8, big=True, r=0.45)
            DT.lounge_chair(Lz, x0 + 2.0, cy, "+x")
            DT.lounge_chair(Lz, x0 + 2.0, cy + 1.2, "+x")
        else:
            kitchen_run(L, cx - 3.5, cx + 2.0, y1 - 1.3, y1 - 0.7, z)                  # front counter
            DT.bench(Lz, x0 + 0.3, x0 + 2.3, y0 + 0.2, y0 + 0.65)
            DT.potted_plant(Lz, x1 - 0.6, y0 + 0.6)
        if lit:
            for gx in (x0 + 2.5, cx, x1 - 2.5):
                L["res0"].hquad(gx - 0.3, gx + 0.3, cy - 0.6, cy + 0.6, top - 0.025, mat="lamp_cool", up=False)
    elif kind == "open_office":
        for dx in (-6.0, -3.2, 3.2, 6.0):
            for dy in (cy - 1.6, cy + 0.6):
                if x0 + 1.0 < dx < x1 - 1.0:
                    desk(L, dx, dy, z)
        DT.potted_plant(Lz, x0 + 0.5, y1 - 0.5)
        DT.potted_plant(Lz, x1 - 0.5, y1 - 0.5)
        if lit:
            for gx in (-6.0, -3.0, 3.0, 6.0):
                for gy in (cy - 2.0, cy + 1.0):
                    L["res0"].hquad(gx - 0.3, gx + 0.3, gy - 0.6, gy + 0.6, top - 0.025, mat="lamp_cool", up=False)
    elif kind in ("office", "site_office"):
        if clear(zones, (cx - 0.9, cx + 0.9, cy - 1.2, cy + 0.6)):
            desk(L, cx, cy - 0.3, z, rot=(w < d))
        for sx in ((x0 + 0.1, x0 + 1.0), (x1 - 1.0, x1 - 0.1)):
            if w > 2.4 and clear(zones, (sx[0], sx[1], y1 - 0.45, y1 - 0.05)):
                shelf_unit(L, sx[0], sx[1], y1 - 0.45, y1 - 0.05, z, h=1.9)
                break
        if lit:
            L["res0"].hquad(cx - 0.3, cx + 0.3, cy - 0.6, cy + 0.6, top - 0.025, mat="lamp_cool", up=False)
    elif kind == "warehouse":
        n_racks = max(1, int((x1 - x0 - 4.0) / 5.0))
        for i in range(n_racks):                                   # rack rows, 3.9 m aisles
            rx = x0 + 3.5 + i * 5.0
            if clear(zones, (rx, rx + 1.1, y0 + 3.0, y1 - 0.8)):
                shelf_unit(L, rx, rx + 1.1, y0 + 3.0, y1 - 0.8, z, h=4.5)
        for (px, py) in ((x0 + 2.0, y0 + 2.0), (x0 + 3.4, y0 + 2.0), (x1 - 1.5, y0 + 3.2)):
            if not clear(zones, (px - 0.6, px + 0.6, py - 0.5, py + 0.5)):
                continue
            piece(L, (px - 0.6, px + 0.6, py - 0.5, py + 0.5, z, z + 0.15), "wood", UV_OAK)       # pallets
            piece(L, (px - 0.5, px + 0.5, py - 0.4, py + 0.4, z + 0.15, z + 1.0), "textile",
                  DT.band_fit("textile", "rug_a", px - 0.5, px + 0.5, py - 0.4, py + 0.4), pen="wood", res1=False)
        if lit:
            for gx in [x0 + 3.0 + i * 6.0 for i in range(int((x1 - x0 - 2.0) / 6.0))]:
                for gy in (y0 + 3.0, y1 - 3.0):
                    L["res0"].prism(gx, gy, 0.3, top - 0.6, top - 0.5, n=12, mat="lamp_cool")
    elif kind == "cell":
        bed(L, x0 + 0.05, x0 + 0.85, y1 - 2.05, y1 - 0.05, z, fabric="grey")
        piece(L, (x1 - 0.5, x1 - 0.05, y1 - 0.55, y1 - 0.05, z, z + 0.45), "metal", DT.UV_STEEL, pen="metal")


def cells_bars(L, P, l):
    use, fh, z0 = P.levels[l]
    if use == "police_ground":
        bars(L, "x", 2.5, 2.0, P.ix1, z0, z0 + fh - SLAB, openings=[(2.9, 3.7), (5.4, 6.2), (8.0, 8.8)])


def roof(L, P):
    hw, hd, top = P.hw, P.hd, P.top
    par = ST["parapet"]
    ring = [(-hw, hw, -hd, -hd + WT), (-hw, hw, hd - WT, hd), (-hw, -hw + WT, -hd + WT, hd - WT), (hw - WT, hw, -hd + WT, hd - WT)]
    skin = P.A["skin"][0]
    mat = S.CITY_SKINS[skin]["mat"] if skin not in ("curtain",) else "concrete"
    uv = skin_uv(P, skin) if skin not in ("curtain",) else UV_CONC
    for (x0, x1, y0, y1) in ring:
        for k in ("res0", "res1", "res2", "geo", "view", "fire", "shadow"):
            kw = kw_for(k, mat, uv, "concrete")
            if k.startswith("res"):
                kw["skip"] = ("-z",)
            L[k].box(x0, x1, y0, y1, top, top + par, **kw)
        for k in ("res0", "res1"):
            L[k].box(x0 - 0.03, x1 + 0.03, y0 - 0.03, y1 + 0.03, top + par, top + par + 0.05, mat="metal", uv=DT.UV_ALU,
                     skip=("-z",))
    L["res3"].box(-hw, hw, -hd, hd, -SLAB, top + par, mat=mat if mat != "metal" else "metal", uv=uv, skip=("-z", "+z"))
    L["res3"].hquad(-hw, hw, -hd, hd, top, mat="concrete", uv=UV_CONC)
    Lt = lifted(L, top)
    g = P.A["group"]
    if g in ("residential", "mixed"):
        for (x, y) in ((-hw * 0.6, hd * 0.55), (hw * 0.5, hd * 0.55)):
            for k in ("res0", "res1", "res2"):
                L[k].box(x - 0.35, x + 0.35, y - 0.25, y + 0.25, top, top + 1.4, mat="brick", uv=DT._brick_uv("bond"),
                         skip=("-z",))
            L["res0"].box(x - 0.4, x + 0.4, y - 0.3, y + 0.3, top + 1.4, top + 1.48, mat="stone", uv=DT.stone_uv("limestone"))
        DT.mast(Lt, -hw * 0.2, -hd * 0.3, 2.5)
    else:
        DT.unit(Lt, -hw * 0.6, -hw * 0.6 + 2.2, -1.0, 1.0, 1.5, grille="+x")
        if P.W > 15:
            DT.unit(Lt, hw * 0.3, hw * 0.3 + 2.2, -hd * 0.6, -hd * 0.6 + 1.8, 1.3, grille="-x")
        DT.mast(Lt, hw - 1.0, hd - 1.0, 4.0)
        DT.obstruction_light(Lt, hw - 1.0, hd - 1.0, 4.0) if P.state == 0 else None
    if P.stair:                                                                       # stair bulkhead
        x0, x1, y0, y1 = P.stair
        for k in ("res0", "res1", "geo", "fire", "view"):
            kw = kw_for(k, "concrete", UV_CONC, "concrete")
            if k.startswith("res"):
                kw["skip"] = ("-z",)
            L[k].box(x0, x1, y0 + 1.2, y1, top, top + 2.4, **kw)
    sign = P.A.get("sign")
    if sign:
        v0, v1 = S.SIGN_BAND[sign]
        y = -hd - 0.08
        top_s = P.levels[0][1] - SLAB - 0.05
        zs0 = top_s - 0.55 if P.A.get("ground") == "shopfront" else P.levels[0][1] + 0.25
        if skin == "metal":
            zs0 = P.levels[0][1] - 1.2
        wsg = min(P.W * 0.5, 6.0)
        for k in ("res0", "res1"):
            L[k].box(-wsg / 2, wsg / 2, y, y + 0.08, zs0, zs0 + 0.5, mat="metal", uv=DT.UV_PAINT, skip=("+y",))
            L[k].quad([(-wsg / 2, y - 0.003, zs0), (wsg / 2, y - 0.003, zs0), (wsg / 2, y - 0.003, zs0 + 0.5),
                       (-wsg / 2, y - 0.003, zs0 + 0.5)], (0, -1, 0), "signs",
                      UVRect(0, 2, (-wsg / 2, zs0), (wsg / 2, zs0 + 0.5), (0, 1 - v1, 1, 1 - v0)))
        if sign == "police" and P.state == 0:
            L["res0"].prism(0.0, -hd - 0.25, 0.12, zs0 + 0.6, zs0 + 0.9, n=10, mat="lamp")
    if P.A.get("ground") == "shopfront" and P.state < 2:                              # striped awning (fabric)
        b = P.bays(-hw, hw)
        for (a0, a1) in b:
            zt = P.levels[0][1] - SLAB - 0.75
            verts = [(a0 + 0.05, -hd, zt), (a1 - 0.05, -hd, zt), (a1 - 0.05, -hd - 1.4, zt - 0.6), (a0 + 0.05, -hd - 1.4, zt - 0.6),
                     (a0 + 0.05, -hd, zt + 0.04), (a1 - 0.05, -hd, zt + 0.04), (a1 - 0.05, -hd - 1.4, zt - 0.56),
                     (a0 + 0.05, -hd - 1.4, zt - 0.56)]
            fab = "beige" if b.index((a0, a1)) % 2 else "blue"
            for k in ("res0", "res1"):
                L[k].solid(verts, [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)],
                           mat="fabric", uv=UV_FAB[fab])


def ruin_extras(L, P):
    """Damaged / ruined dressing: cracks and graffiti on the front, rubble below the collapse."""
    if P.state >= 1:
        sd = FSide(P, "S")
        for i in range(3 if P.state == 1 else 6):
            a = -P.hw + 0.8 + (P.W - 1.6) * h01(P.name, "crack", i)
            lvl = int(h01(P.name, "crackl", i) * len(P.levels))
            z = P.levels[lvl][2] + 0.4 + 1.6 * h01(P.name, "crackz", i)
            sd.quad(L["res0"], a - 0.9, a + 0.9, z, z + 1.8, -0.012, mat="decal_cracks",
                    uv=UVRect(0, 2, (a - 0.9, z), (a + 0.9, z + 1.8), (0, 0, 1, 1)))
        a = P.door[1] + 0.35 if P.door[1] + 1.4 < P.hw else P.door[0] - 1.35
        sd.quad(L["res0"], a, a + 1.0, 0.0, 0.85, -0.018, mat="decal_graffiti",       # street level, under the sills
                uv=UVRect(0, 2, (a, 0.0), (a + 1.0, 0.85), (0, 0, 1, 1)))
    if P.state == 2:
        r = P.ruin.region
        zf = P.levels[P.kc - 1][2] if P.kc - 1 < len(P.levels) else 0.0
        x0, x1 = max(r[0], P.ix0 + 0.4), min(r[1], P.ix1 - 0.4)
        y0, y1 = max(r[2], P.iy0 + 0.4), min(r[3], P.iy1 - 0.4)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        rubble_pile(L, cx, cy, zf, min(2.0, (x1 - x0) / 2.6), min(1.8, (y1 - y0) / 2.6), 1.1, (P.name, "main"))
        rubble_pile(L, x0 + 0.6, y0 + 0.6, zf, 0.7, 0.6, 0.5, (P.name, "side"))
        # charred interior walls above the rubble (soot), broken slab edge (rebar) at the cut
        for k in range(4):
            xr = x0 + (x1 - x0) * h01(P.name, "rebar", k)
            zr = P.levels[P.kc][2] if P.kc < len(P.levels) else P.top
            L["res0"].box(xr - 0.01, xr + 0.01, r[3] - 0.01, r[3] + 0.6, zr - 0.2, zr - 0.18, mat="rust",
                          uv=UVBand(S.MATERIALS["rust"]["bands"]["rust"], 1.0))


# ================================================================== memory, loot, build
def memory(L, P):
    m = L["mem"].lod
    rooms_per_level = [layout(P, u, l)[1] for l, (u, _f, _z) in enumerate(P.levels)]
    names = ["light_1", "light_2", "light_3", "light_4"]
    order = [0, 1, 2, len(P.levels) - 1]
    used = set()
    for name, l in zip(names, order):
        if l >= len(P.levels):
            l = len(P.levels) - 1
        rooms = rooms_per_level[l]
        idx = 1 if (l in used and len(rooms) > 1) else 0
        used.add(l)
        x0, x1, y0, y1, _k = rooms[idx]
        _u, fh, z = P.levels[l]
        m.point(name, ((x0 + x1) / 2, (y0 + y1) / 2, z + fh - SLAB - 0.35))
    m.point("entrance", ((P.door[0] + P.door[1]) / 2, -P.hd - 1.0, 0.0))


def comp_boxes(lod):
    out = []
    for g, v in lod.groups.items():
        if g.startswith("Component"):
            pts = [lod.verts[i] for i in v]
            out.append(tuple(f(p[j] for p in pts) for j in range(3) for f in (min, max)))
    return out


def loot_points(L, P):
    """Deterministic floor loot points: on a slab, clear of every solid, outside the stair and
    the collapse; fewer in ruins."""
    boxes = comp_boxes(L["geo"].lod)
    pts = []
    for l, (use, fh, z) in enumerate(P.levels):
        cand = []
        x = P.ix0 + 0.8
        while x < P.ix1 - 0.7:
            y = P.iy0 + 0.8
            while y < P.iy1 - 0.7:
                ok = not (P.stair and P.stair[0] - 0.4 <= x <= P.stair[1] + 0.4 and P.stair[2] - 0.4 <= y)
                ok = ok and not P.collapsed(x, y, l) and not P.near_collapse(x, y, l)
                if ok:
                    floor = any(b[0] <= x <= b[1] and b[2] <= y <= b[3] and abs(b[5] - z) < 0.03 for b in boxes)
                    hit = any(b[0] < x + 0.4 and x - 0.4 < b[1] and b[2] < y + 0.4 and y - 0.4 < b[3]
                              and b[4] < z + 1.6 and z + 0.05 < b[5] for b in boxes)
                    if floor and not hit:
                        cand.append((round(x, 2), round(y, 2), round(z, 2)))
                y += 1.3
            x += 1.3
        area = (P.ix1 - P.ix0) * (P.iy1 - P.iy0)
        n = max(2, min(8, int(area / 28)))
        if P.state == 2:
            n = max(1, n // 2)
        cand.sort(key=lambda p: h01(P.name, "loot", p))
        pts += cand[:n]
    return pts


LOOT_OUT = {}


def build(arch, state):
    P = Plan(arch, state)
    L = city_lods(P.ruin)
    slabs(L, P)
    for l in range(len(P.levels)):
        for key in ("S", "N", "W", "E"):
            sd, ops = facade(L, P, key, l)
            facade_level_extras(L, P, sd, l, ops)
        interior(L, P, l)
        cells_bars(L, P, l)
    stairs(L, P)
    front_door(L, P)
    roof(L, P)
    ruin_extras(L, P)
    memory(L, P)
    geo = L["geo"].lod
    geo.props.update({"class": "house", "map": "building", "autocenter": "0"})
    geo.mass = 15000.0 + 6000.0 * len(P.levels)
    LOOT_OUT["Land_SKY_" + P.name] = loot_points(L, P)
    return [v.lod for v in L.values()]


def _builder(arch, state):
    return lambda: build(arch, state)


BUILDERS = {"City_%s_%s" % (a, st): _builder(a, i) for a in S.CITY_ARCHETYPES for i, st in enumerate(S.RUIN_STATES)}


def modules():
    return {n: (BUILDERS[n], e["pbo"], e["p3d"]) for n, e in S.KIT.items() if n in BUILDERS}


LOOT_JSON = os.path.join(os.path.dirname(HERE), "city_loot.json")


def write_loot():
    cur = json.load(open(LOOT_JSON)) if os.path.exists(LOOT_JSON) else {}
    cur.update(LOOT_OUT)
    with open(LOOT_JSON, "w") as fh:
        json.dump(cur, fh, indent=1, sort_keys=True)
        fh.write("\n")


if __name__ == "__main__":
    run_cli(modules(), KIT_MATS, "build_stats_city.json")
    write_loot()
