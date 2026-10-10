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
# D96: every facade decal family has its own depth off the wall, >= 4 mm apart (zfix.DELTA): overlapping decals of
# different families never share a plane (z-fight, TESTING CT-13); same-family decals are placed so they do not overlap
DECAL_D = {"runoff": -0.006, "streak": -0.010, "soot": -0.014, "cracks": -0.018, "graffiti": -0.022}
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
        # D82: one cut height per CUT_CELL cell of a global grid (was per 0.1 m of each piece's centre), so a small
        # render box and the larger collision box over the same spot cut to the same height (a lintel's render
        # stayed while its collision fell - bullets through a visible wall)
        return zc + 0.35 + 2.2 * h01(self.name, "cut", math.floor(x / CUT_CELL), math.floor(y / CUT_CELL))

    def window(self, *key):
        """Window state: glass / broken / boarded."""
        if self.state == 0:
            return "glass"
        r = h01(self.name, "win", *key)
        if self.state == 1:
            return "broken" if r < 0.35 else ("boarded" if r < 0.5 else "glass")
        return "boarded" if r < 0.2 else "broken"


CUT_CELL = 5.0   # D82: ruin cut-height cell (m); 2 m and 4 m pushed ruined blocks over the geo budget


class RLod:
    """Lod proxy: every primitive is split at the collapse region edges and the pieces inside
    are dropped or cut down. Unknown attributes fall through to the wrapped Lod."""

    def __init__(self, lod, ruin):
        self.lod, self.ruin = lod, ruin

    def __getattr__(self, k):
        return getattr(self.lod, k)

    def _splits(self, a0, a1, b0, b1, z1=None):
        r = self.ruin.region
        # region edges + the CUT_CELL cut-cell lines inside the region (sec D82 H2): every piece is cut per cut cell,
        # so a long collision box and the shorter render pieces over it always get the same height
        fine = getattr(self.lod, "name", "") not in ("res3", "shadow")   # res3 / shadow: region edges only (budget); res2 cut per cell (sec review M: sniper range)
        fine = fine and (z1 is None or z1 > r[4] + 0.35 - 1e-6)   # never reaches the lowest cut: no cell lines (geo budget)
        C = CUT_CELL
        gx = {C * k for k in range(int(math.floor(max(a0, r[0]) / C)), int(math.ceil(min(a1, r[1]) / C)) + 1)} if fine else set()
        gy = {C * k for k in range(int(math.floor(max(b0, r[2]) / C)), int(math.ceil(min(b1, r[3]) / C)) + 1)} if fine else set()
        xs = sorted({a0, a1} | {v for v in {r[0], r[1]} | gx if a0 + 1e-6 < v < a1 - 1e-6 and r[0] - 1e-6 <= v <= r[1] + 1e-6})
        ys = sorted({b0, b1} | {v for v in {r[2], r[3]} | gy if b0 + 1e-6 < v < b1 - 1e-6 and r[2] - 1e-6 <= v <= r[3] + 1e-6})
        return [(xa, xb, ya, yb) for xa, xb in zip(xs, xs[1:]) for ya, yb in zip(ys, ys[1:])]

    def _affected(self, x0, x1, y0, y1, z1):
        r = self.ruin.region
        return r is not None and z1 > r[4] + 1e-6 and x0 < r[1] and r[0] < x1 and y0 < r[3] and r[2] < y1

    def box(self, x0, x1, y0, y1, z0, z1, **kw):
        if not self._affected(x0, x1, y0, y1, z1):
            return self.lod.box(x0, x1, y0, y1, z0, z1, **kw)
        zc = self.ruin.region[4]
        for a, b, c, d in self._splits(x0, x1, y0, y1, z1):
            cx, cy = (a + b) / 2, (c + d) / 2
            if not self.ruin.inside(cx, cy):
                self.lod.box(a, b, c, d, z0, z1, **kw)
                continue
            if z0 >= zc - 1e-6 and z1 - z0 <= 0.45:          # floors, sills, copings: fell
                continue
            if z0 >= zc - 1e-6 and z1 - z0 <= 1.25:
                continue                                       # D96: rails, desks, beds over the hole fell whole (a cut
                                                               # rail / desk left a collision box with nothing drawn on it)
            cut = self.ruin.cut(cx, cy)
            if z0 >= zc - 1e-6 and min(z1, cut) - z0 < 0.25:  # D72: no sliver of furniture floating over the hole
                continue
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
        for a, b, c, d in self._splits(x0, x1, y0, y1, -1e9 if flat_z else z1):   # flat quads never use the cut
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

    @staticmethod
    def _pc(profile):
        """Profile bounding-box centre (D83, sec review: profile[0] is an arbitrary corner, so a render cornice and
        its narrower collision could fall on opposite sides of a cut)."""
        u, z = [p[0] for p in profile], [p[1] for p in profile]
        return (min(u) + max(u)) / 2, (min(z) + max(z)) / 2

    def extrude_x(self, profile, x0, x1, **kw):
        if self._centroid_ok([((x0 + x1) / 2,) + self._pc(profile)]):
            self.lod.extrude_x(profile, x0, x1, **kw)

    def extrude_y(self, profile, y0, y1, **kw):
        pu, pz = self._pc(profile)
        if self._centroid_ok([(pu, (y0 + y1) / 2, pz)]):
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
        self.door, self.door_bay = None, None
        if A["door_bay"] is not None:
            i = len(bays) // 2 if A["door_bay"] == "center" else A["door_bay"]
            c = (bays[i][0] + bays[i][1]) / 2
            dw = ST["door"][0]
            self.door = (c - dw / 2, c + dw / 2)
            self.door_bay = i
            self.entry = self.door
        elif A.get("open_bays"):                                 # garages: enter through an open bay
            ob = bays[A["open_bays"][0]]
            self.entry = (ob[0] + 0.3, ob[1] - 0.3)
        else:                                                    # not enterable (substation)
            self.entry = (-0.6, 0.6)
        self.roller_h = A.get("roller_h", min(4.5, self.levels[0][1] - SLAB - 0.5))
        self.fx0, self.fx1, self.fy0, self.fy1 = S.city_footprint(A)
        y = A.get("yard")
        self.yard = (-y / 2, y / 2, -y / 2, y / 2) if y else None
        at = A.get("atrium")
        self.atrium = (-at[0] / 2, at[0] / 2, -at[1] / 2 - 1.0, at[1] / 2 - 1.0) if at else None
        # car ramps (parking): level l -> l+1 in strip A (l even, up +x) or B (l odd, up -x); the
        # slab of level l+1 is open over the ramp that rises into it (U-turn at the strip ends)
        self.ramps = []
        self.escalators = []                                     # D61 mall: (level, x0, x1, y0, y1), rising +y
        if A.get("escalators") and self.atrium:
            ax0, ax1, ay0, _ay1 = self.atrium
            for l in range(len(self.levels) - 1):
                run = self.levels[l][1] * 1.732                  # 30 degree flight
                # D87: 1.0 m off the atrium (a 0.6 m strip between balustrade and escalator was a wedge slot)
                xs = (ax1 + 1.0, ax1 + 2.6) if l % 2 == 0 else (ax0 - 2.6, ax0 - 1.0)
                self.escalators.append((l, xs[0], xs[1], ay0, ay0 + run))
        if A.get("ramps"):
            for l in range(len(self.levels) - 1):
                y0, y1 = (-3.7, -0.15) if l % 2 == 0 else (0.15, 3.7)
                self.ramps.append((l, -10.5, 10.5, y0, y1, 1 if l % 2 == 0 else -1))
        # ruin: collapse a front corner away from the stair and the door
        self.ruin = Ruin(self.name, state)
        if state == 2:
            kc = max(1, len(self.levels) - 1)
            zc = (self.levels[kc][2] - SLAB - 0.05) if kc < len(self.levels) else self.top - SLAB - 0.05
            if len(self.levels) == 1:
                zc = self.levels[0][1] * 0.45
            self.kc = kc
            left = (self.stair is not None and self.stair[0] > 0) or (self.stair is None and self.entry[0] > 0)
            xa, xb = (-self.hw - 1.0, -self.hw * 0.15) if left else (self.hw * 0.15, self.hw + 1.0)
            if self.entry[1] > xa and self.entry[0] < xb:          # keep the entrance standing
                xa, xb = (max(xa, self.entry[1] + 0.6), xb) if not left else (xa, min(xb, self.entry[0] - 0.6))
            ytop = self.hd * 0.35
            if any(u.startswith("double_") for u, _f, _z in self.levels):
                ytop = -1.25                                     # keep the corridor: rooms behind it stay reachable
            if any(u == "creche" for u, _f, _z in self.levels) and self.stair:
                ytop = self.stair[2] - 1.8 - 1.0                  # D61: same for the kindergarten corridor
            self.ruin.region = (xa, xb, min(-self.hd, self.fy0) - 1.0, ytop, zc)
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

    def holes(self, l, stair=True):
        """Openings in the slab whose top is level l (l = len(levels): roof slab)."""
        n = len(self.levels)
        out = []
        if stair and self.stair and 1 <= l < n:
            out.append(self.stair_hole())
        if self.atrium and 1 <= l < n:
            out.append(self.atrium)
        if self.yard and l >= 1:
            out.append(self.yard)
        out += [(x0, x1, y0, y1) for (k, x0, x1, y0, y1, _d) in self.ramps if k + 1 == l]
        out += [(x0, x1, y0, y1) for (k, x0, x1, y0, y1) in self.escalators if k + 1 == l]
        if self.A.get("skylight") and self.atrium and l == n:              # glass vault over the atrium (D61)
            out.append(self.atrium)
        return out

    def in_hole(self, x, y, l, margin=0.0, stair=True):
        return any(h[0] - margin <= x <= h[1] + margin and h[2] - margin <= y <= h[3] + margin
                   for h in self.holes(l, stair))

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
        walls.append(("x", sy0 - h, ix0, sx0 - PT, [(sx0 - PT - 1.6, sx0 - PT - 0.6)]))
        rooms += [(ix0, ix1, iy0, sy0 - PT, "shop"), (ix0, sx0 - PT, sy0, iy1, "storage")]
    elif use == "flat":
        sx0, sx1, sy0, sy1 = st
        walls += [("x", sy0 - h, ix0, sx0 - PT, [(sx0 - PT - 1.3, sx0 - PT - 0.4)]),
                  ("y", 0.0, iy0, sy0 - PT, [(sy0 - PT - 2.0, sy0 - PT - 1.1)])]
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
    elif use in ("corridor", "clinic_ground"):
        # corridor in front of the stair (landing exits into it), rooms off both sides
        sx0, sx1, sy0, sy1 = st
        yc0, yc1 = sy0 - 1.8, sy0
        front = P.bays(ix0, ix1, 3.6)
        if use == "clinic_ground":
            walls.append(("x", yc0 - h, ix0, ix1, [(-1.0, 1.0)]))
            rooms.append((ix0, ix1, iy0, yc0 - PT, "waiting"))
        else:
            walls.append(("x", yc0 - h, ix0, ix1, [((a + b) / 2 - 0.45, (a + b) / 2 + 0.45) for a, b in front]))
            for a, b in front[1:]:
                walls.append(("y", a, iy0, yc0 - PT, []))
            rooms += [(a + (h if i else 0), b - (h if i < len(front) - 1 else 0), iy0, yc0 - PT,
                       "exam" if P.A["group"] == "civic" and P.arch.startswith("Clinic") else "room")
                      for i, (a, b) in enumerate(front)]
        for (a0, a1) in ((ix0, sx0 - (PT if sx0 > ix0 + 1e-6 else 0)), (sx1 + (PT if sx1 < ix1 - 1e-6 else 0), ix1)):
            if a1 - a0 < 2.4:
                continue
            back = P.bays(a0, a1, 3.6)
            walls.append(("x", yc1 + h, a0, a1, [((a + b) / 2 - 0.45, (a + b) / 2 + 0.45) for a, b in back]))
            for a, b in back[1:]:
                walls.append(("y", a, yc1 + PT, iy1, []))
            kind = "dorm" if P.arch.startswith("Fire") else ("exam" if P.arch.startswith("Clinic") else "room")
            rooms += [(a + (h if i else 0), b - (h if i < len(back) - 1 else 0), yc1 + PT, iy1, kind)
                      for i, (a, b) in enumerate(back)]
    elif use == "market":
        walls.append(("x", iy1 - 4.5, ix0, ix1, [(ix1 - 3.0, ix1 - 1.8)]))
        rooms += [(ix0, ix1, iy0, iy1 - 4.5 - h, "market"), (ix0, ix1, iy1 - 4.5 + h, iy1, "storage")]
    elif use in ("firebays", "workshop", "garage", "kiosk", "shed", "gas", "cafe", "nave", "parking", "dept"):
        kind = {"firebays": "bay", "workshop": "workshop", "garage": "garage", "kiosk": "kiosk", "shed": "shed",
                "gas": "gas", "cafe": "cafe", "nave": "nave", "parking": "parking", "dept": "dept"}[use]
        rooms.append((ix0, ix1, iy0, (st[2] - 0.2) if st else iy1, kind))
    elif use == "factory":
        ox = ix0 + min(5.7, 0.25 * P.W)
        oy = iy1 - min(5.0, 0.3 * P.D)
        walls += [("y", ox, oy, iy1, []), ("x", oy, ix0, ox - h, [(ix0 + 1.0, ix0 + 2.0)])]
        rooms += [(ix0, ox - h, oy + h, iy1, "site_office"), (ix0, ix1, iy0, oy - h, "factory")]
    elif use.startswith("double_"):
        walls, rooms = layout_double(P, use[len("double_"):], l)
    elif use == "ring":
        walls, rooms = layout_ring(P, l)
    elif use == "creche":
        walls, rooms = layout_venue(P, use, l)
    elif use in ("hyper", "cinema", "bar", "changing", "mall"):
        vw, vr = layout_venue(P, use, l)
        walls += vw
        rooms += vr
    elif use == "bank_ground":
        sx0, sx1, sy0, sy1 = st
        yb = 0.6
        walls += [("x", yb, ix0, sx0 - PT, [(-4.2, -3.3), (1.5, 2.4)]), ("y", -2.6, yb + h, iy1, [])]
        rooms += [(ix0, ix1, iy0, yb - h, "banking"), (ix0, -2.6 - h, yb + h, iy1, "vault"),
                  (-2.6 + h, sx0 - PT, yb + h, iy1, "office")]
    return walls, rooms


def split_bays(a0, a1, rw, minw=2.4):
    """a0..a1 cut into rooms of about rw (at least minw wide) -> [(b0, b1)]."""
    if a1 - a0 < minw:
        return []
    n = max(1, int(round((a1 - a0) / rw)))
    while n > 1 and (a1 - a0) / n < minw:
        n -= 1
    w = (a1 - a0) / n
    return [(a0 + i * w, a0 + (i + 1) * w) for i in range(n)]


def _row(walls, rooms, segs, wall_c, y0, y1, kinds, door_w=0.9, door_x=None):
    """Rooms side by side (segs) between y0 and y1, partitions between them, doors in the wall
    at wall_c (one per room, at door_x(seg) or the room centre)."""
    h = PT / 2
    ops = []
    for i, (a, b) in enumerate(segs):
        if i:
            walls.append(("y", a, y0, y1, []))
        r0, r1 = a + (h if i else 0), b - (h if i < len(segs) - 1 else 0)
        rooms.append((r0, r1, y0, y1, kinds[i]))
        c = door_x(a, b) if door_x else (a + b) / 2
        dw = door_w[i] if isinstance(door_w, (list, tuple)) else door_w
        ops.append((c - dw / 2, c + dw / 2))
    return ops


def layout_double(P, kind, l):
    """Double-loaded corridor along X (y -1..1): rooms in front and behind, a hall from the
    corridor to the stair, a wide entry room round the front door on the ground floor."""
    ix0, ix1, iy0, iy1 = P.ix0, P.ix1, P.iy0, P.iy1
    h = PT / 2
    sx0, sx1, sy0, sy1 = P.stair
    yc0, yc1 = -1.0, 1.0
    rw = P.A.get("room_w", 3.6)
    walls, rooms = [], []
    left_ok = sx0 - PT - ix0 >= 2.4
    right_ok = ix1 - (sx1 + PT) >= 2.4
    if sx0 > ix0 + 1e-6:
        walls.append(("y", sx0 - h, yc1 + (PT if left_ok else 0.0), iy1, []))
    if sx1 < ix1 - 1e-6:
        walls.append(("y", sx1 + h, yc1 + (PT if right_ok else 0.0), iy1, []))
    for ok, a0, a1 in ((left_ok, ix0, sx0 - PT), (right_ok, sx1 + PT, ix1)):
        if not ok:
            continue
        segs = split_bays(a0, a1, rw)
        ops = _row(walls, rooms, segs, yc1 + h, yc1 + PT, iy1, [kind] * len(segs))
        walls.append(("x", yc1 + h, a0, a1, ops))
    # front row
    if l == 0:
        c = (P.entry[0] + P.entry[1]) / 2
        ew = P.A.get("entry_w", 4.0)
        e0, e1 = max(ix0, c - ew / 2), min(ix1, c + ew / 2)
        if e0 - ix0 < 2.4:
            e0 = ix0
        if ix1 - e1 < 2.4:
            e1 = ix1
        left, right = split_bays(ix0, e0, rw), split_bays(e1, ix1, rw)
        segs = left + [(e0, e1)] + right
        kinds = [kind] * len(left) + [P.A.get("entry_kind", "reception")] + [kind] * len(right)
        dws = [0.9] * len(left) + [2.0] + [0.9] * len(right)
    else:
        segs = split_bays(ix0, ix1, rw)
        kinds, dws = [kind] * len(segs), 0.9
    ops = _row(walls, rooms, segs, yc0 - h, iy0, yc0 - PT, kinds, door_w=dws)
    walls.append(("x", yc0 - h, ix0, ix1, ops))
    return walls, rooms


def layout_ring(P, l):
    """Perimeter block: a 1.6 m gallery runs round the yard; flats' rooms on the outer side of the
    four wings; the stair in the back wing opens onto the gallery; on the ground floor a passage
    leads from the front door through the front wing to the gallery and the yard gate."""
    ix0, ix1, iy0, iy1 = P.ix0, P.ix1, P.iy0, P.iy1
    h = PT / 2
    sx0, sx1, sy0, sy1 = P.stair
    g = P.yard[1] + WT                                    # yard-side face of the gallery
    R = g + 1.6                                           # room side of the gallery
    rw = P.A.get("room_w", 4.4)
    walls, rooms = [], []
    cyc = ["living", "bedroom", "kitchen"]

    def door_in_gallery(a, b):                            # door within the gallery's span
        lo, hi = max(a + 0.6, -R + 0.6), min(b - 0.6, R - 0.6)
        return (lo + hi) / 2

    def wing_x(y0, y1, wall_c, stair_gap):
        """Front / back wing rooms (x-bays); corner rooms reach into the gallery's span."""
        spans = [(ix0, ix1)] if not stair_gap else [(ix0, sx0 - PT), (sx1 + PT, ix1)]
        ops = []
        for a0, a1 in spans:
            cuts = [a0] + [v for v in (-R + 1.5, R - 1.5) if a0 + 2.4 < v < a1 - 2.4] + [a1]
            segs = []
            for c0, c1 in zip(cuts, cuts[1:]):
                segs += split_bays(c0, c1, rw) if -R + 1.5 - 1e-6 <= c0 and c1 <= R - 1.5 + 1e-6 else [(c0, c1)]
            kinds = [cyc[(i + len(rooms)) % 3] for i in range(len(segs))]
            if l == 0 and not stair_gap:                  # passage to the yard round the front door
                c = (P.entry[0] + P.entry[1]) / 2
                kinds = ["hall" if a <= c <= b else k for (a, b), k in zip(segs, kinds)]
            ops += _row(walls, rooms, segs, wall_c, y0, y1, kinds, door_x=door_in_gallery)
        if stair_gap:
            ops.append((sx0 + 0.25, sx1 - 0.25))
        return ops

    ops_s = wing_x(iy0, -R - PT, -R - h, False)
    walls.append(("x", -R - h, ix0, ix1, ops_s))
    ops_n = wing_x(R + PT, iy1, R + h, True)
    walls.append(("x", R + h, ix0, ix1, ops_n))
    walls += [("y", sx0 - h, R + PT, iy1, []), ("y", sx1 + h, R + PT, iy1, [])]
    for sgn in (-1, 1):                                   # side wings: y-bays
        xa, xb = (ix0, -R - PT) if sgn < 0 else (R + PT, ix1)
        segs = split_bays(-R, R, rw)
        ops = []
        for i, (a, b) in enumerate(segs):
            if i:
                walls.append(("x", a, xa, xb, []))
            rooms.append((xa, xb, a + (h if i else 0), b - (h if i < len(segs) - 1 else 0), cyc[(i + 1) % 3]))
            ops.append(((a + b) / 2 - 0.45, (a + b) / 2 + 0.45))
        walls.append(("y", sgn * (R + h), -R, R, ops))
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


def cushion(lod, x0, x1, y0, y1, z0, z1, mat, uv, n=12, p=3.0):
    """D96: upholstered block with rounded edges and softly tapered ends (loft of superellipse sections along its
    longer side, smoothed by the writer) - cushions, mattresses, pillows, upholstered arms and backs."""
    along_x = (x1 - x0) >= (y1 - y0)
    a0, a1, b0, b1 = (x0, x1, y0, y1) if along_x else (y0, y1, x0, x1)
    r = min(0.04, (a1 - a0) / 4)
    zc, hz = (z0 + z1) / 2, (z1 - z0) / 2
    bc, hb = (b0 + b1) / 2, (b1 - b0) / 2
    rings = []
    for (a, f) in ((a0, 0.82), (a0 + r, 1.0), (a1 - r, 1.0), (a1, 0.82)):
        ring = []
        for k in range(n):
            t = 2 * math.pi * k / n
            c, s_ = math.cos(t), math.sin(t)
            bb = bc + f * hb * math.copysign(abs(c) ** (2 / p), c)
            zz = zc + f * hz * math.copysign(abs(s_) ** (2 / p), s_)
            ring.append((a, bb, zz) if along_x else (bb, a, zz))
        rings.append(ring)
    lod.loft(rings, mat=mat, uv=uv)


def bed(L, x0, x1, y0, y1, z, fabric="blue"):
    piece(L, (x0, x1, y0, y1, z, z + 0.35), "wood", UV_WALNUT)
    # D96 sec H2: mattress + pillow stay within 0.2 m of the 0.35 m collision (D76 thin-detail rule: no prone head
    # pocket). Raising the collision instead made wedge slots between hospital-ward beds (test_city)
    cushion(L["res0"], x0 + 0.04, x1 - 0.04, y0 + 0.04, y1 - 0.04, z + 0.33, z + 0.5, "fabric", UV_FAB[fabric])   # mattress
    hy = (y1 - 0.08, y1) if (y1 - y0) > (x1 - x0) else (y0, y0 + 0.08)
    L["res0"].box(x0, x1, hy[0], hy[1], z + 0.35, z + 1.0, mat="wood", uv=UV_WALNUT)
    if (y1 - y0) > (x1 - x0):                                                 # D96: pillow at the headboard
        py0, py1 = (y1 - 0.5, y1 - 0.12) if hy[0] > y0 + 0.1 else (y0 + 0.12, y0 + 0.5)
        cushion(L["res0"], x0 + 0.12, x1 - 0.12, py0, py1, z + 0.48, z + 0.55, "fabric", UV_FAB["beige"])


def wardrobe(L, x0, x1, y0, y1, z):
    piece(L, (x0, x1, y0, y1, z, z + 2.1), "wood", UV_OAK, view=True)


def sofa(L, x0, x1, y0, y1, z, back, fabric="grey"):
    """D84 three-seat sofa: collision block to 0.6 m over the whole footprint (no head pocket), cushions, arms
    and a back rest (Res0 detail <= 0.18 m thick above it). back = the side against the wall: '+y' / '-y'."""
    fuv = UV_FAB[fabric]
    L["res0"].box(x0, x1, y0, y1, z, z + 0.42, mat="fabric", uv=fuv)
    L["res1"].box(x0, x1, y0, y1, z, z + 0.6, mat="fabric", uv=fuv, skip=("-z",))
    L["geo"].box(x0, x1, y0, y1, z, z + 0.5)            # one collision part, at the cushion top (sec review L)
    L["fire"].box(x0, x1, y0, y1, z, z + 0.5, mat="pen_wood")
    by = (y1 - 0.18, y1) if back == "+y" else (y0, y0 + 0.18)
    cushion(L["res0"], x0 + 0.02, x1 - 0.02, by[0], by[1], z + 0.38, z + 0.86, "fabric", fuv)        # D96 rounded back
    for (a, b) in ((x0, x0 + 0.16), (x1 - 0.16, x1)):
        cushion(L["res0"], a, b, y0, y1, z + 0.38, z + 0.63, "fabric", fuv)                           # arms
    n = 3 if x1 - x0 > 1.6 else 2
    cw = (x1 - x0 - 0.32) / n
    sy = (y0 + 0.04, y1 - 0.2) if back == "+y" else (y0 + 0.2, y1 - 0.04)
    for i in range(n):                                                         # seat cushions, plump, with a gap line
        a = x0 + 0.16 + i * cw
        cushion(L["res0"], a + 0.01, a + cw - 0.01, sy[0], sy[1], z + 0.4, z + 0.52, "fabric", fuv)


def tv_unit(L, x0, x1, y0, y1, z, wall):
    """D84 low cabinet with an old CRT-era flat TV on it (render-only screen, 6 cm). wall = '+y' / '-y'."""
    piece(L, (x0, x1, y0, y1, z, z + 0.5), "wood", UV_WALNUT)
    cx = (x0 + x1) / 2
    ty = (y1 - 0.12, y1 - 0.06) if wall == "+y" else (y0 + 0.06, y0 + 0.12)
    L["res0"].box(cx - 0.45, cx + 0.45, ty[0], ty[1], z + 0.56, z + 1.1, mat="metal", uv=DT.paint_uv("slate"))
    L["res0"].box(cx - 0.12, cx + 0.12, ty[0] - 0.06, ty[1] + 0.06, z + 0.5, z + 0.56, mat="metal", uv=DT.UV_STEEL)


def bookshelf(L, x0, x1, y0, y1, z, wall, key=()):
    """D84 full-height bookcase (collides like the wardrobe) with book rows as front quads (perf: no boxes)."""
    piece(L, (x0, x1, y0, y1, z, z + 1.9), "wood", UV_WALNUT, view=True)
    fy, nrm = (y0 - 0.002, (0, -1, 0)) if wall == "+y" else (y1 + 0.002, (0, 1, 0))
    for k in range(4):
        zz = z + 0.15 + k * 0.45
        nb = int((x1 - x0 - 0.1) / 0.18)
        for i in range(nb):
            if h01("books", key, k, i) < 0.2:
                continue
            bx = x0 + 0.05 + i * (x1 - x0 - 0.1) / nb
            hb = 0.22 + 0.12 * h01("bookh", key, k, i)
            band = ("terracotta", "sage", "beige", "slate", "white")[int(h01("bookc", key, k, i) * 5)]
            pts = [(bx, fy, zz), (bx + 0.16, fy, zz), (bx + 0.16, fy, zz + hb), (bx, fy, zz + hb)]
            L["res0"].quad(pts if wall == "+y" else pts[::-1], nrm, "paint", DT.paint_uv(band))


def sideboard(L, x0, x1, y0, y1, z):
    """D84 dining-room sideboard: walnut cabinet 0.85 m with a laminate top."""
    piece(L, (x0, x1, y0, y1, z, z + 0.85), "wood", UV_WALNUT)
    L["res0"].box(x0 - 0.02, x1 + 0.02, y0 - 0.02, y1 + 0.02, z + 0.85, z + 0.88, mat="wood", uv=UV_LAMINATE)


def fridge(L, x0, x1, y0, y1, z):
    """D84 kitchen fridge (collides, View blocks like the wardrobe), handle on the front."""
    piece(L, (x0, x1, y0, y1, z, z + 1.75), "paint", DT.paint_uv("white"), pen="metal", view=True)
    L["res0"].box(x0 - 0.04, x0 - 0.01, (y0 + y1) / 2 - 0.2, (y0 + y1) / 2 + 0.2, z + 0.9, z + 0.93, mat="metal",
                  uv=DT.UV_STEEL)                                                # handle on the room side (-x)


def filing_cabinet(L, x0, x1, y0, y1, z):
    """D84 four-drawer steel filing cabinet (collides: a 0.5 m block is a head pocket otherwise)."""
    piece(L, (x0, x1, y0, y1, z, z + 1.32), "paint", DT.paint_uv("slate"), pen="metal")


def kitchen_run(L, x0, x1, y0, y1, z):
    """Counter with worktop, sink and upper cabinets (wall side = the thin side touching the wall)."""
    piece(L, (x0, x1, y0, y1, z, z + 0.88), "wood", UV_LAMINATE)
    L["res0"].box(x0 - 0.02, x1 + 0.02, y0 - 0.02, y1 + 0.02, z + 0.88, z + 0.92, mat="stone", uv=DT.stone_uv("granite"))
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    L["res0"].box(cx - 0.3, cx + 0.3, cy - 0.2, cy + 0.2, z + 0.921, z + 0.93, mat="metal", uv=DT.UV_STEEL)


def table(L, x0, x1, y0, y1, z, h=0.75):
    L["res0"].box(x0, x1, y0, y1, z + h - 0.04, z + h, mat="wood", uv=UV_OAK)
    for (lx, ly) in ((x0 + 0.05, y0 + 0.05), (x1 - 0.05, y0 + 0.05), (x0 + 0.05, y1 - 0.05), (x1 - 0.05, y1 - 0.05)):
        L["res0"].prism(lx, ly, 0.03, z, z + h - 0.04, n=12, mat="metal", uv=DT.UV_PAINT)       # D96: round legs
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
    gap = (h - 0.2) / 3.5
    for k in range(4):
        zz = z + 0.15 + k * gap
        L["res0"].box(x0, x1, y0, y1, zz, zz + 0.03, mat="metal", uv=DT.UV_PAINT)
        if goods:
            n = max(1, int((x1 - x0) / 0.45))
            gh = min(0.27, gap - 0.08) if k < 3 else 0.27                      # D96: goods clear the shelf above
            for i in range(n):
                if h01("goods", round(x0, 2), round(y0, 2), k, i) < 0.75:
                    gx = x0 + 0.08 + i * (x1 - x0 - 0.16) / n
                    gy = 0.05 + 0.03 * h01("goodsy", round(x0, 2), round(y0, 2), k, i)   # not all flush at the front
                    L["res0"].box(gx, gx + (x1 - x0 - 0.2) / n, y0 + gy, y1 - gy, zz + 0.03, zz + 0.03 + gh * (0.8 + 0.2 * h01("goodsh", round(x0, 2), k, i)),
                                  mat="textile" if (i + k) % 3 == 0 else "wood",
                                  uv=DT.UVTrim(S.MATERIALS["textile"]["bands"]["rug_a"], 0.6, 0.3) if (i + k) % 3 == 0 else UV_LAMINATE)
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
    """Collapse debris mound: convex elliptic frustum (collides) + loose chunks (Res0).
    D72: never steeper than 45 deg (or low enough to vault, 0.6 m) so it is always a way out of the room it lies
    in; its Geometry carries the named selection "rubble" so test_city walks over it instead of around it."""
    n = 8
    h = min(h, max(0.6, 0.575 * min(rx, ry)))       # slope run >= (1 - top radius 0.35 - top offset 0.075) * r (sec L)
    rot = h01("rub", key) * math.pi
    base = [(x + rx * math.cos(rot + 2 * math.pi * k / n), y + ry * math.sin(rot + 2 * math.pi * k / n), z) for k in range(n)]
    tx, ty = x + 0.15 * rx * (h01("rubx", key) - 0.5), y + 0.15 * ry * (h01("ruby", key) - 0.5)
    topr = 0.35
    top = [(tx + rx * topr * math.cos(rot + 2 * math.pi * k / n), ty + ry * topr * math.sin(rot + 2 * math.pi * k / n), z + h)
           for k in range(n)]
    faces = [tuple(range(n)), tuple(range(n, 2 * n))] + [(k, (k + 1) % n, n + (k + 1) % n, n + k) for k in range(n)]
    for k in ("res0", "res1", "res2") + (("geo", "fire", "view") if collide else ()):
        kw = {"mat": "rubble", "uv": UV_RUBBLE} if k.startswith("res") else ({"mat": "pen_concrete"} if k == "fire" else {})
        if k == "geo":
            kw["sel"] = ("rubble",)
        L[k].solid(base + top, faces, **kw)
    if collide:                                                         # walkable rubble (Roadway on the slopes)
        road = L["road"]
        for k in range(n):
            road.quad([base[k], base[(k + 1) % n], top[(k + 1) % n], top[k]], (0, 0, 1), "road_ext", UV_TILE)
        for k in range(1, n - 1):
            road.quad([top[0], top[k], top[k + 1]], (0, 0, 1), "road_ext", UV_TILE)
    for i in range(6):
        a = 2 * math.pi * h01("chunk", key, i)
        d = 1.0 + 0.4 * h01("chunkd", key, i)                         # D82: round the foot, not half inside the mound
        cx, cy = x + math.cos(a) * rx * d, y + math.sin(a) * ry * d
        s = 0.12 + 0.25 * h01("chunks", key, i)
        L["res0"].box(cx - s, cx + s, cy - s * 0.7, cy + s * 0.7, z, z + min(s * 0.8, 0.18 - 0.013 * i),   # <= 18 cm (D82);
                      # D96: every chunk its own height, so neighbouring tops never share a plane (z-fight)
                      mat="brick" if i % 2 else "concrete", uv=UV_REVEAL if i % 2 == 0 else UVWorld(2.0))


# ================================================================== facades
class FSide:
    """Facade side of a W x D footprint; d = depth inward from the outer face (d < 0 outside)."""

    def __init__(self, P, key):
        hw, hd = P.hw, P.hd
        self.key = key
        if key.startswith("i"):                                   # yard sides (perimeter block): face the yard
            y = P.yard[1]
            self.axis, self.plane = {"iS": ("x", -y), "iN": ("x", y), "iW": ("y", -y), "iE": ("y", y)}[key]
            self.sgn = -1 if self.plane > 0 else 1
            span = y + WT if self.axis == "x" else y              # yard W/E butt into yard S/N
        else:
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


def side_profile(lod, sd, a0, a1, prof, **kw):
    """D96: extrude a convex (depth, z) profile along facade side sd from a0 to a1 (depth < 0 = proud of the wall):
    cornices, sills, string courses and plinths with real mouldings instead of plain boxes."""
    pts = [(sd.d(d), z) for d, z in prof]
    if sd.axis == "x":
        lod.extrude_x(pts, a0, a1, **kw)
    else:
        lod.extrude_y(pts, a0, a1, **kw)


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
    if m == "concrete":
        return UV_CONC
    return UVBand(S.MATERIALS["metal"]["bands"]["alu"], 2.0)          # light aluminium cladding


class UVWall:
    """World-scale tiling for the wall sheets (D59): u along the face, v = height (vertical faces);
    plan coordinates on horizontal faces. One `scale` (m) per sheet in both directions."""

    def __init__(self, scale):
        self.s = scale

    def __call__(self, pts, normal):
        ax = max(range(3), key=lambda i: abs(normal[i]))
        along, across = {0: (1, 2), 1: (0, 2), 2: (0, 1)}[ax]
        return [(p[along] / self.s, p[across] / self.s) for p in pts]


def wall(P, skin):
    """(material, uv) of the walls of a skin: tileable wall sheets for masonry skins (D59), the
    original sheets for metal / curtain / open."""
    w = S.CITY_SKINS[skin].get("wall")
    if not w:
        return S.CITY_SKINS[skin]["mat"], skin_uv(P, skin)
    if "%s" in w:
        w = w % (P.A["skin"][1] or "cream")
    return w, UVWall(S.MATERIALS[w]["sheet_m"])


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
        fkw = {"mat": "paint", "uv": DT.paint_uv("white")} if residential else {"mat": "metal", "uv": frame_uv}
        sd.box(r0, a0, a0 + fw, s0, s1, rec - 0.03, rec + 0.03, skip=("-z", "+z"), **fkw)
        sd.box(r0, a1 - fw, a1, s0, s1, rec - 0.03, rec + 0.03, skip=("-z", "+z"), **fkw)
        sd.box(r0, a0 + fw, a1 - fw, s1 - fw, s1, rec - 0.03, rec + 0.03, **fkw)
        sd.box(r0, a0 + fw, a1 - fw, s0, s0 + fw, rec - 0.03, rec + 0.03, **fkw)
        if a1 - a0 > 1.15 and state == "glass":
            m = (a0 + a1) / 2
            sd.box(r0, m - 0.03, m + 0.03, s0 + fw, s1 - fw, rec - 0.03, rec + 0.03, skip=("-z", "+z"), **fkw)
        if state == "glass" and (s1 - s0) > 0.9 and (a1 - a0) > 0.5:      # D96: sashes + glazing bars (Res0)
            sw = 0.045
            mids = [(a0 + a1) / 2] if a1 - a0 > 0.75 else []
            cols = [a0 + fw] + [c for m in mids for c in (m - 0.03, m + 0.03)] + [a1 - fw]
            zt = s0 + 0.7 * (s1 - s0)                                          # transom: top light over the casements
            for ca, cb in zip(cols[0::2], cols[1::2]):
                for (za, zb) in ((s0 + fw, zt - 0.025), (zt + 0.025, s1 - fw)):
                    if zb - za < 0.2:
                        continue
                    sd.box(r0, ca, ca + sw, za, zb, rec - 0.02, rec + 0.01, skip=("-z", "+z"), **fkw)
                    sd.box(r0, cb - sw, cb, za, zb, rec - 0.02, rec + 0.01, skip=("-z", "+z"), **fkw)
                    sd.box(r0, ca + sw, cb - sw, zb - sw, zb, rec - 0.02, rec + 0.01, **fkw)
                    sd.box(r0, ca + sw, cb - sw, za, za + sw, rec - 0.02, rec + 0.01, **fkw)
            sd.box(r0, a0 + fw, a1 - fw, zt - 0.025, zt + 0.025, rec - 0.03, rec + 0.03, **fkw)     # transom bar
    if state == "glass":
        L["res0"].quad(sd.rect(a0, a1, s0, s1, rec), sd.out, "glass", UV_GLASS, double=True)
        L["res1"].quad(sd.rect(a0, a1, s0, s1, rec), sd.out, "glass", UV_GLASS)
        sd.box(L["fire"], a0, a1, s0, s1, rec - 0.01, rec + 0.01, mat="pen_glass")
    elif state == "boarded":
        n = max(1, min(12, int((s1 - s0 - 0.04) / 0.24)))                # D96: a transom gets 1 board; tall bays are
                                                                         # boarded tight (4 boards left 0.6 m gaps over the collision)
        for i in range(n):
            z = s0 + 0.08 + (i * (s1 - s0 - 0.25) / (n - 1) if n > 1 else (s1 - s0 - 0.34) / 2)
            tilt = 0.04 * (h01(P.name, "board", sd.key, key, i) - 0.5)
            dd = 0.016 * (i % 2)                                   # D96: overlapping boards alternate in depth (no z-fight)
            for k in ("res0", "res1"):
                sd.box(L[k], a0 - 0.08, a1 + 0.08, z + tilt, z + 0.18 + tilt, -0.03 - dd, -dd, mat="wood", uv=UV_OAK)
            sd.box(L["fire"], a0 - 0.08, a1 + 0.08, z, z + 0.18, -0.03, 0.0, mat="pen_wood")
        # D90: the gaps between the boards show the room in Res0 / Res1; the hollow far LODs get a dark backing
        L["res1"].quad(sd.rect(a0, a1, s0, s1, WT - 0.02), sd.out, "glassvoid", UV_GLASS)
    if state == "broken":                                                   # soot plume over the opening
        sp = 0.02 if skin == "curtain" else 0.3                            # D96: curtain bays are 16 cm apart: plumes
        r0.quad(sd.rect(a0 - sp, a1 + sp, s1 - 0.1, s1 + 1.1, DECAL_D["soot"]), sd.out, "decal_dirt",   # chained 6 deep
                UVRect(ax, 2, (a0 - sp, s1 - 0.1), (a1 + sp, s1 + 1.1), (0, 1, 1, 0)))
        # dark void only for the far LODs (no interior there): `glassvoid` lives in Res1 until exterior_lod copies it
        # as glassfar, then build() strips it. D90 sec: in Res0 it was an opaque one-sided pane in a broken (open)
        # window - outside saw dark, inside saw out and shot through: one-way concealment
        L["res1"].quad(sd.rect(a0, a1, s0, s1, WT - 0.02), sd.out, "glassvoid", UV_GLASS)
    if residential and state == "glass" and P.state == 0:                     # curtains inside
        for c0, c1 in ((a0 - 0.15, a0 + 0.3), (a1 - 0.3, a1 + 0.15)):
            uv = DT.band_fit("textile", "curtain", c0, c1, s0 - 0.6, s1 + 0.1, axes=(ax, 2), u_rep=0.8)
            sd.quad(r0, c0, c1, max(0.05, s0 - 0.6), s1 + 0.1, WT + 0.06, inward=True, mat="textile", uv=uv)
            sd.quad(r0, c0, c1, max(0.05, s0 - 0.6), s1 + 0.1, WT + 0.06, inward=False, mat="textile", uv=uv)
    return state


RADIATOR_USES = ("office", "police_ground", "police_upper", "corridor", "clinic_ground", "double_exam", "double_ward",
                 "double_class", "double_office", "bank_ground")


def facade(L, P, key, lvl):
    """One side, one level. Returns door/roller openings for the Geometry wall."""
    use, fh, z0 = P.levels[lvl]
    sd = FSide(P, key)
    A = P.A
    top = z0 + fh - SLAB
    skin = A["skin"][0]
    SK = dict(S.CITY_SKINS[skin])
    if A.get("win"):                                         # per-archetype window size (church, factory)
        SK["ww"], SK["sill"], SK["head"] = A["win"]
    mat, uv = wall(P, skin)
    pen = {"brick": "masonry", "metal": "metal"}.get(SK["mat"], "concrete")
    residential = A["group"] in ("residential", "mixed") and use not in ("shop",)
    inner = ("paint", DT.paint_uv("white")) if use not in ("warehouse",) else None
    frame_uv = DT.UV_PAINT
    shop = lvl == 0 and A.get("ground") == "shopfront" and key in A.get("shop_sides", ())
    blank = key in A.get("blank", ())
    bays = P.bays(sd.a0, sd.a1, 4.0 if skin == "metal" else None)
    if key == "iS" and P.door is not None and len(bays) % 2 == 0:              # yard gate on the bay axis
        n = len(bays) + 1
        bays = [(sd.a0 + i * (sd.a1 - sd.a0) / n, sd.a0 + (i + 1) * (sd.a1 - sd.a0) / n) for i in range(n)]
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
        # front door; on a perimeter block the yard gate opposite it (opening, no leaf)
        door_here = P.door is not None and key in ("S", "iS") and lvl == 0 and (b0 <= P.door[0] <= b1)
        roller = key == "S" and lvl == 0 and i in A.get("roller_bays", ()) + A.get("open_bays", ())
        if blank or shop or roller or door_here or skin in ("curtain", "metal", "open"):
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
            dh = P.roller_h
            wall_piece(L, sd, b0, w0, z0, top, mat, uv, pen, inner)
            wall_piece(L, sd, w1, b1, z0, top, mat, uv, pen, inner)
            wall_piece(L, sd, w0, w1, z0 + dh, top, mat, uv, pen, inner)
            shutter_uv = UVBand(S.MATERIALS["metal"]["bands"]["steel"], 0.5)
            if i in A.get("open_bays", ()):                                          # shutter rolled up: a way in
                openings.append((w0, w1, z0, z0 + dh))
            else:
                for k in ("res0", "res1", "res2", "view", "fire"):                      # closed roller shutter
                    kw = kw_for(k, "metal", shutter_uv, "metal")
                    sd.box(L[k], w0, w1, z0, z0 + dh, 0.12, 0.18, **kw)
                for j in range(int(dh / 0.1)):                                        # slats (Res0)
                    sd.box(L["res0"], w0, w1, z0 + j * 0.1, z0 + j * 0.1 + 0.015, 0.105, 0.12, mat="metal",
                           uv=DT.UV_STEEL, skip=(sd.in_key,))
            sd.box(L["res0"], w0 - 0.1, w1 + 0.1, z0 + dh, z0 + dh + 0.4, -0.25, 0.0, mat="metal", uv=DT.UV_PAINT)
            continue
        if skin == "open":
            # parking deck: columns + 1.0 m spandrel (vehicle barrier), open above
            col, spn = 0.4, z0 + 1.0
            wall_piece(L, sd, b0, b0 + col, z0, top, mat, uv, pen, None)
            wall_piece(L, sd, b1 - col, b1, z0, top, mat, uv, pen, None)
            wall_piece(L, sd, b0 + col, b1 - col, z0, spn, mat, uv, pen, None)
            wall_piece(L, sd, b0 + col, b1 - col, top - 0.45, top, mat, uv, pen, None)      # downstand beam
            openings.append((b0 + col, b1 - col, spn, top - 0.45))
            for zz in (spn + 0.25, spn + 0.6):                                      # steel guard rails
                sd.box(L["res0"], b0 + col, b1 - col, zz, zz + 0.06, 0.05, 0.12, mat="metal", uv=DT.UV_PAINT)
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
                st_w = window(L, P, sd, b0 + 0.08, b1 - 0.08, z0, top - spand + SLAB, skin, bkey, rec, False, DT.UV_ALU)
                q = sd.rect(b0, b1, z0, top, 0.0)
                cx, cy = sum(p[0] for p in q) / 4, sum(p[1] for p in q) / 4
                fell = P.ruin.region is not None and P.ruin.inside(cx, cy) and z0 >= P.ruin.region[4] - 1e-6
                if st_w == "broken" or fell:                                        # D96: no glass / boards fell,
                    openings.append((b0 + 0.08, b1 - 0.08, z0, top - spand + SLAB))  # nothing drawn: no invisible pane
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
        window_streak(L, P, sd, w0, w1, s0, bkey)
        r0 = L["res0"]
        lim = DT.stone_uv("limestone")
        # D96 stone sill: weathered (sloped) top, 7 cm nose, horns into the wall either side; drip groove underneath
        side_profile(r0, sd, w0 - 0.06, w1 + 0.06, [(rec, s0 + 0.012), (-0.07, s0 - 0.008), (-0.07, s0 - 0.055),
                                                    (rec, s0 - 0.055)], mat="stone", uv=lim)
        if SK.get("soldier"):
            sd.quad(r0, w0 - 0.1, w1 + 0.1, s1, s1 + 0.22, -0.004, mat="brick", uv=DT._brick_uv("soldier"))
        elif SK["mat"] == "render":
            # D96 moulded architrave round the opening (stucco band, chamfered), keystone over the head
            ab = 0.09
            for (a, b) in ((w0 - ab, w0), (w1, w1 + ab)):
                side_profile(r0, sd, a, b, [(0.0, s0), (-0.022, s0), (-0.022, s1), (0.0, s1)], mat="stone", uv=lim)
            side_profile(r0, sd, w0 - ab, w1 + ab, [(0.0, s1), (-0.022, s1), (-0.03, s1 + ab - 0.02), (-0.03, s1 + ab),
                                                    (0.0, s1 + ab)], mat="stone", uv=lim)
            c_ = (w0 + w1) / 2
            side_profile(r0, sd, c_ - 0.09, c_ + 0.09, [(0.0, s1 - 0.02), (-0.045, s1 - 0.02), (-0.045, s1 + ab + 0.07),
                                                         (0.0, s1 + ab + 0.07)], mat="stone", uv=lim)
        else:
            sd.box(r0, w0 - 0.08, w1 + 0.08, s1, s1 + 0.12, -0.03, 0.0, mat="stone", uv=lim, skip=(sd.in_key,))
        if SK.get("shutters") and st != "broken":                           # D96 louvred shutters (facade kit)
            cell = ("shutter_sage", "shutter_brown", "shutter_blue")[int(h01(P.name, "shut") * 3)]
            ax = sd.uvax()
            for (a, b) in ((w0 - 0.55, w0 - 0.03), (w1 + 0.03, w1 + 0.55)):
                sd.box(r0, a, b, s0, s1, -0.045, -0.01, mat="facadekit",
                       uv=UVRect(ax, 2, (a, s0), (b, s1), S.facadekit_uv(cell)))
                for zz in (s0 + 0.22, s1 - 0.22):                          # strap hinges
                    hx = (w0 - 0.05, w0 - 0.25) if a < w0 else (w1 + 0.25, w1 + 0.05)
                    sd.box(r0, min(hx), max(hx), zz - 0.02, zz + 0.02, -0.052, -0.044, mat="metal", uv=DT.UV_STEEL)
        if (residential or use in RADIATOR_USES) and st == "glass" and P.state == 0:          # radiator (D89: + offices / public)
            sd.box(r0, c - 0.5, c + 0.5, z0 + 0.15, z0 + 0.7, WT + 0.03, WT + 0.11, mat="paint", uv=DT.paint_uv("white"),
                   skip=(sd.out_key, "-z"))
        if A["group"] == "residential" and skin == "panel" and lvl > 0 and i % 2 == 1:      # french balcony rail
            for zz in (s0 + 0.15, s0 + 0.55, s0 + 0.95):
                sd.box(r0, w0 - 0.1, w1 + 0.1, zz, zz + 0.03, -0.2, -0.17, mat="metal", uv=DT.UV_STEEL)
            for a in (w0 - 0.1, (w0 + w1) / 2, w1 + 0.1):
                sd.box(r0, a - 0.015, a + 0.015, s0, s0 + 0.98, -0.2, -0.17, mat="metal", uv=DT.UV_STEEL, skip=("-z",))
        if residential and lvl > 0 and P.state < 2 and not str(key).startswith("i"):   # yard sides face walkable galleries
            facade_clutter(L, P, sd, bkey, w0, w1, b0, b1, s0, s1, st, rail=(skin == "panel" and i % 2 == 1),
                           shutters=bool(SK.get("shutters")))
    flush()
    return sd, openings


def facade_clutter(L, P, sd, bkey, w0, w1, b0, b1, s0, s1, st, rail=False, shutters=False):
    """D87 lived-in facades (upper residential floors, out of reach from the street): a split-system AC unit beside
    or under the window, a satellite dish on a bracket, or laundry on a French-balcony rail. Seeded per window; most
    windows stay bare. Render-only, nothing deeper than 0.5 m off the wall. AC body and dish plate also in Res1 (no
    pop at the LOD switch, perf M); faces against the wall or hidden are skipped (perf L)."""
    r0, r1 = L["res0"], L["res1"]
    back = (sd.in_key,)
    r = h01(P.name, bkey, "clutter")
    if r < 0.10:                                                              # AC unit (0.7 x 0.45 x 0.25 m)
        if not shutters and w1 + 0.9 < b1:
            a0, z0 = w1 + 0.15, s0 + 0.15
        else:
            a0, z0 = (w0 + w1) / 2 - 0.35, s0 - 0.62                         # under the sill
        for lod in (r0, r1):
            sd.box(lod, a0, a0 + 0.7, z0, z0 + 0.45, -0.27, -0.02, mat="paint", uv=DT.paint_uv("white"), skip=back)
        sd.quad(r0, a0 + 0.08, a0 + 0.62, z0 + 0.07, z0 + 0.38, -0.272, mat="metal", uv=DT.UV_STEEL)   # grille
        for k in (a0 + 0.1, a0 + 0.6):                                        # brackets: underside + sides only
            sd.box(r0, k - 0.015, k + 0.015, z0 - 0.04, z0, -0.27, -0.02, mat="metal", uv=DT.UV_STEEL, skip=back + ("+z",))
    elif r < 0.16 and w1 + 0.85 < b1 and not shutters:                        # satellite dish (clips shutters: skipped)
        a = w1 + 0.45
        z = s1 - 0.2
        sd.box(r0, a - 0.02, a + 0.02, z - 0.02, z + 0.02, -0.3, -0.02, mat="metal", uv=DT.UV_STEEL, skip=back)  # arm
        for lod in (r0, r1):
            sd.box(lod, a - 0.28, a + 0.28, z - 0.28, z + 0.28, -0.34, -0.31, mat="paint", uv=DT.paint_uv("white"))
        sd.box(r0, a - 0.015, a + 0.015, z - 0.015, z + 0.015, -0.5, -0.34, mat="metal", uv=DT.UV_STEEL)  # LNB arm
    elif r < 0.30 and rail and st != "broken":                                # laundry on the balcony rail
        n = 2 + int(h01(P.name, bkey, "ln") * 3)
        for j in range(n):
            a = w0 + 0.05 + j * (w1 - w0 - 0.1) / n
            wj = min(0.45, (w1 - w0 - 0.1) / n - 0.05)
            hj = 0.35 + 0.25 * h01(P.name, bkey, "lh", j)
            band = ("blue", "beige", "grey")[int(h01(P.name, bkey, "lc", j) * 3)]
            sd.quad(r0, a, a + wj, s0 + 0.95 - hj, s0 + 0.95, -0.21, mat="fabric", uv=UV_FAB[band], double=True)   # 4 tris


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
    wmat, wuv = wall(P, skin)
    inner_skirting(L, P, sd, lvl, openings)
    shop = lvl == 0 and P.A.get("ground") == "shopfront" and sd.key in P.A.get("shop_sides", ())
    sd.quad(L["res2"], sd.a0, sd.a1, z0, top, 0.0, mat="glassfar" if (skin == "curtain" or shop) else wmat,
            uv=UV_GLASS if (skin == "curtain" or shop) else wuv)
    if mat in ("brick", "render", "stone", "concpanel") and lvl > 0:                        # string course
        sc = ST["string_course"]
        e = sc if sd.axis == "x" else 0
        za, zb = z0 - SLAB - 0.02, z0 + 0.04
        # D96: weathered top and a bed chamfer (Res0); a plain band in Res1
        side_profile(L["res0"], sd, sd.a0 - e, sd.a1 + e, [(0.0, za - 0.03), (-sc + 0.03, za), (-sc, za + 0.03),
                                                          (-sc, zb - 0.02), (-sc + 0.02, zb), (0.0, zb + 0.015)],
                     mat="stone", uv=DT.stone_uv("limestone"))
        sd.box(L["res1"], sd.a0 - e, sd.a1 + e, za, zb, -sc, 0.0, mat="stone", uv=DT.stone_uv("limestone"), skip=(sd.in_key,))
    if lvl == 0 and skin not in ("metal", "curtain", "open") and not shop and not sd.key.startswith("i"):   # plinth
        for k in ("res0", "res1"):
            segs, cur = [], sd.a0
            for (o0, o1, _a, _b) in sorted(openings):
                segs.append((cur, o0))
                cur = o1
            segs.append((cur, sd.a1))
            for a, b in segs:
                if k == "res0":                                          # D96: chamfered top (water runs off)
                    side_profile(L[k], sd, a, b, [(0.0, z0), (-0.04, z0), (-0.04, z0 + ST["plinth"] - 0.035),
                                                  (-0.005, z0 + ST["plinth"]), (0.0, z0 + ST["plinth"])],
                                 mat="stone", uv=DT.stone_uv("granite"))
                else:
                    sd.box(L[k], a, b, z0, z0 + ST["plinth"], -0.04, 0.0, mat="stone", uv=DT.stone_uv("granite"),
                           skip=(sd.in_key, "-z"))
    quoins(L, P, sd, lvl)


def quoins(L, P, sd, lvl):
    """D96: dressed stone quoins on the outer corners of rendered and stone buildings (alternating long / short
    blocks, 2.5 cm proud, chamfered joints by the texture), Res0. Called once per side and level (all levels)."""
    if sd.key.startswith("i") or sd.key in P.A.get("blank", ()):
        return
    skin = P.A["skin"][0]
    if S.CITY_SKINS[skin]["mat"] not in ("render", "stone"):
        return
    use, fh, z0 = P.levels[lvl]
    lim = DT.stone_uv("limestone")
    zz, i = z0 + (ST["plinth"] if lvl == 0 else 0.0), 0
    while zz + 0.3 <= z0 + fh + 1e-6:
        ln = 0.42 if (i + (lvl * 7)) % 2 == 0 else 0.26
        a0, a1 = sd.a0, sd.a1
        if sd.axis == "y":                     # W / E sides butt into the S / N walls: reach the corner, swap long / short
            ln = 0.68 - ln
            a0, a1 = a0 - WT - 0.025, a1 + WT + 0.025
        for a, b in ((a0, a0 + ln), (a1 - ln, a1)):
            sd.box(L["res0"], a, b, zz + 0.012, zz + 0.3, -0.025, 0.0, mat="stone", uv=lim, skip=(sd.in_key,))
        zz += 0.312
        i += 1


def inner_skirting(L, P, sd, lvl, openings):
    """D89: skirting along the inner face of the outer walls (the partitions had it since D55), broken at doors.
    Front + top faces only (4 tris a run), Res0; not behind shop glass, curtain / metal / open skins or warehouses."""
    use, _fh, z0 = P.levels[lvl]
    skin = P.A["skin"][0]
    if skin in ("curtain", "metal", "open") or use in ("warehouse",) or use in NO_CEILING:
        return
    if lvl == 0 and P.A.get("ground") == "shopfront" and sd.key in P.A.get("shop_sides", ()):
        return
    e = WT if sd.key.lstrip("i") in ("S", "N") else 0.0
    cur, segs = sd.a0 + e, []
    for (o0, o1, oz0, _oz1) in sorted(openings):
        if oz0 > z0 + 0.1:                                                       # openings above the floor (parking decks)
            continue
        segs.append((cur, o0))
        cur = o1
    segs.append((cur, sd.a1 - e))
    for a, b in segs:
        if b - a > 0.1:
            sd.box(L["res0"], a, b, z0, z0 + 0.08, WT, WT + 0.012, mat="paint", uv=DT.paint_uv("white"),   # no new section
                   skip=(sd.out_key, "-z") + sd.ends)


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
        holes = P.holes(l)
        for (x0, x1, y0, y1) in rects_minus(-hw, hw, -hd, hd, holes):
            for k in ("res0", "res1", "res2", "geo", "view", "fire"):
                kw = kw_for(k, "concrete", UV_REVEAL, "concrete")
                L[k].box(x0, x1, y0, y1, z - SLAB, z, **kw)
            if l < n:
                L["road"].hquad(max(x0, P.ix0), min(x1, P.ix1), max(y0, P.iy0), min(y1, P.iy1), z, mat="road_int", uv=UV_TILE)
    for (x0, x1, y0, y1) in rects_minus(-hw, hw, -hd, hd, [P.yard] if P.yard else []):
        L["shadow"].box(x0, x1, y0, y1, P.top - SLAB, P.top)
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
            L[k].ramp_slab(xa[0], xa[1], yA0, yA1, z0, zm, **kw)
            L[k].ramp_slab(xb[0], xb[1], yA1, yA0, zm, zt, **kw)
        L["road"].ramp(xa[0], xa[1], yA0, yA1, z0, zm, mat="road_int", uv=UV_TILE)
        L["road"].ramp(xb[0], xb[1], yA1, yA0, zm, zt, mat="road_int", uv=UV_TILE)
        for (xr, ya_, yb_, za_, zb_) in ((xa[1] - 0.06, yA0, yA1, z0, zm), (xb[0] + 0.06, yA1, yA0, zm, zt)):  # handrails
            tube(L["res0"], (xr, ya_, za_ + 0.95), (xr, yb_, zb_ + 0.95), 0.022, "metal", DT.UV_STEEL)    # D96: round
            for t in (0.15, 0.5, 0.85):                                                           # posts
                yp, zp = ya_ + t * (yb_ - ya_), za_ + t * (zb_ - za_)
                tube(L["res0"], (xr, yp, zp), (xr, yp, zp + 0.95), 0.014, "metal", DT.UV_STEEL, n=8)
        L["res0"].box(cx - 0.2, cx + 0.2, y1 - 0.07, y1, zt - 0.45, zt - 0.35, mat="lamp", skip=("+y",))   # bulkhead light
    # top level: guard over the open flight-A well
    _u, _fh, ztop = P.levels[-1]
    for k in ("res0", "res1", "geo", "fire"):
        kw = kw_for(k, "metal", DT.UV_PAINT, "metal")
        L[k].box(xa[0], xa[1], yA0, yA0 + 0.05, ztop, ztop + 1.0, **kw)


def front_door(L, P):
    """Hinged front door leaf (bone door_front), frame; none in the ruined state."""
    if P.door is None:
        return
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
    # D96: panelled / glazed / steel leaf from the facade kit (the texture carries panels, mouldings, ironmongery)
    g = P.A["group"]
    cell = (("door_green", "door_oak", "door_boards")[int(h01(P.name, "door") * 3)] if g == "residential" else
            "door_oak" if g in ("mixed", "civic") else "door_shop" if g == "commercial" else "door_steel")
    vis = {"mat": "facadekit", "uv": UVRect(0, 2, (d0, 0.0), (d1, dh), S.facadekit_uv(cell))}
    for k in ("res0", "res1", "geo", "view", "fire", "shadow"):
        kw = dict(vis) if k.startswith("res") else ({"mat": "pen_wood" if wood else "pen_metal"} if k == "fire" else {})
        L[k].lod.box(*leaf, sel=[name], **kw)
    L["res0"].lod.box(d1 - 0.18, d1 - 0.1, y - 0.06, y - 0.025, 1.0, 1.1, mat="metal", uv=DT.UV_STEEL, sel=[name])   # handle
    # D96 stone threshold step outside (render only, 6 cm: feet do not visibly sink) - not on a ruin
    L["res0"].lod.box(d0 - 0.12, d1 + 0.12, -P.hd - 0.32, -P.hd + 0.02, 0.0, 0.03, mat="stone", uv=DT.stone_uv("granite"))
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
    wall_fittings(Lz, P, walls, z0)
    wall_wear(L, P, walls, z0, top)


def _wall_decal(lod, axis, c, face, a0, a1, z0, z1, band, fit=False, tile=4.0):
    """One decal_grime quad on a partition face (Res0, 4 mm proud: 4 mm under the switch plates). fit: the band's U spans the quad (bands that
    fade at the sides), else it tiles every `tile` m along the wall."""
    f = c + face * (PT / 2 + 0.004)                                          # sec review L: 4 mm under the 8 mm plates
    if axis == "x":
        pts, nrm, ax = [(a0, f, z0), (a1, f, z0), (a1, f, z1), (a0, f, z1)], (0, face, 0), 0
    else:
        pts, nrm, ax = [(f, a0, z0), (f, a1, z0), (f, a1, z1), (f, a0, z1)], (face, 0, 0), 1
    rect = DT.grime_rect(band) if fit else DT.grime_rect(band, a0 / tile, a1 / tile)
    lod.quad(pts, nrm, mat="decal_grime", uv=UVRect(ax, 2, (a0, z0), (a1, z1), rect))


def wall_wear(L, P, walls, z0, top):
    """D92 lived-in walls (decal_grime wear bands, Res0, no new section): scuffs low beside doorways and a hand
    smudge on the latch side (60 % of doorways intact, all in damaged / ruined); damaged / ruined walls also get
    water stains under the ceiling and mould at a wall end. Kept inside the free spans of each wall."""
    r0 = L["res0"]
    tw = DT.D["trim_w"]
    worn = P.state > 0
    for wi, (axis, c, a0, a1, ops) in enumerate(walls):
        cuts = sorted(ops)
        spans, cur = [], a0
        for o0, o1 in cuts:
            spans.append((cur, o0 - tw))
            cur = o1 + tw
        spans.append((cur, a1))

        def clip(x0, x1):
            for s0, s1 in spans:
                lo, hi = max(x0, s0 + 0.05), min(x1, s1 - 0.05)
                if hi - lo > 0.15:
                    return lo, hi
            return None
        done = {1: [], -1: []}                                          # scuff spans per face: no stacked layers (perf L)

        def free(face, x0, x1):
            pieces = [(x0, x1)]
            for d0, d1 in done[face]:                                       # subtract every scuff already there
                pieces = [q for (p0, p1) in pieces for q in ((p0, min(p1, d0)), (max(p0, d1), p1)) if q[1] - q[0] > 1e-6]
            best = max(pieces, key=lambda q: q[1] - q[0], default=None)
            return best if best and best[1] - best[0] > 0.15 else None
        for oi, (o0, o1) in enumerate(ops):
            if not worn and h01(P.name, "wear", z0, wi, oi) > 0.6:
                continue
            s = 1 if h01(P.name, "sw", z0, wi, oi) < 0.5 else -1                  # the switch face (wall_fittings)
            right = h01(P.name, "swr", z0, wi, oi) < 0.5
            for (x0, x1) in ((o0 - tw - 0.9, o0 - tw), (o1 + tw, o1 + tw + 0.9)):    # scuffs both sides of the door
                r = clip(x0, x1)
                r = r and free(s, *r)
                if r:
                    done[s].append(r)
                    _wall_decal(r0, axis, c, s, r[0], r[1], z0 + 0.08, z0 + 0.42, "scuff")
            hx = (o1 + tw, o1 + tw + 0.3) if right else (o0 - tw - 0.3, o0 - tw)      # hand smudge, latch side
            r = clip(*hx)
            if r:
                _wall_decal(r0, axis, c, s, r[0], r[1], z0 + 0.85, z0 + 1.55, "smudge", fit=True)
        if not worn:
            continue
        for si, (s0, s1) in enumerate(spans):
            if s1 - s0 < 1.0:
                continue
            face = 1 if h01(P.name, "stf", z0, wi, si) < 0.5 else -1
            if h01(P.name, "stain", z0, wi, si) < 0.45 + 0.25 * (P.state == 2):     # water stain under the ceiling
                w = min(s1 - s0 - 0.1, 1.0 + 1.5 * h01(P.name, "stw", z0, wi, si))
                x = s0 + 0.05 + (s1 - s0 - 0.1 - w) * h01(P.name, "stx", z0, wi, si)
                _wall_decal(r0, axis, c, face, x, x + w, top - 1.0, top - 0.02, "stain")
            if h01(P.name, "mould", z0, wi, si) < 0.25 + 0.25 * (P.state == 2):     # mould at the span's end
                end = s1 - 0.65 if h01(P.name, "mde", z0, wi, si) < 0.5 else s0 + 0.05
                _wall_decal(r0, axis, c, -face, end, end + 0.6, top - 0.9, top - 0.02, "mould", fit=True)


def wall_fittings(L, P, walls, key):
    """D89 wall dressing: a light switch beside each partition doorway (latch side, 1.05 m) and a socket low on the
    other face (0.25 m). Render-only Res0 quads 8 mm proud (2 tris each - perf review: box sides unseen past 2 m;
    paint: no new section); skipped where the wall runs out beside the door."""
    tw = DT.D["trim_w"]
    for wi, (axis, c, a0, a1, ops) in enumerate(walls):
        for oi, (o0, o1) in enumerate(ops):
            s = 1 if h01(P.name, "sw", key, wi, oi) < 0.5 else -1
            right = h01(P.name, "swr", key, wi, oi) < 0.5
            for (face, z0, z1, w, dist) in ((s, 1.02, 1.14, 0.08, 0.1), (-s, 0.22, 0.3, 0.12, 0.45)):
                if right and o1 + tw + dist + w < a1 - 0.1:
                    p0 = o1 + tw + dist
                elif o0 - tw - dist - w > a0 + 0.1:
                    p0 = o0 - tw - dist - w
                else:
                    continue
                f = c + face * (PT / 2 + 0.008)
                if axis == "x":
                    pts, nrm = [(p0, f, z0), (p0 + w, f, z0), (p0 + w, f, z1), (p0, f, z1)], (0, face, 0)
                else:
                    pts, nrm = [(f, p0, z0), (f, p0 + w, z0), (f, p0 + w, z1), (f, p0, z1)], (face, 0, 0)
                L["res0"].quad(pts, nrm, mat="paint", uv=DT.paint_uv("white"))


FLOOR = {"living": "parquet", "bedroom": "parquet", "kitchen": "tile", "hall": "tile", "shop": "tile", "storage": None,
         "lobby": "marble", "open_office": "carpet", "office": "carpet", "site_office": "carpet", "warehouse": None,
         "police_lobby": "tile", "cell": None, "waiting": "tile", "exam": "tile", "room": "carpet", "dorm": "parquet",
         "market": "tile", "bay": None, "workshop": None, "garage": None, "kiosk": "tile", "shed": None,
         "reception": "marble", "ward": "tile", "class": "parquet", "banking": "marble", "vault": None, "nave": "marble",
         "gas": "tile", "cafe": "tile", "parking": None, "dept": "tile", "factory": None,
         # D61 venues
         "hyper": "tile", "foyer": "carpet", "auditorium": "carpet", "bar": "parquet", "club_hall": "tile",
         "changing": "tile", "play": "parquet", "nap": "parquet", "wash": None, "mall_shop": "tile", "food": "tile",
         "mall_hall": "marble"}
VENUE_KINDS = ("hyper", "foyer", "auditorium", "bar", "club_hall", "changing", "play", "nap", "wash", "mall_shop",
               "food", "mall_hall")
CEIL = {"lobby": "ceiling", "open_office": "ceiling", "office": "ceiling", "shop": "ceiling", "police_lobby": "ceiling"}
WALL_BAND = {"house": "beige", "flats": "sage", "flat": "white", "shop": "white", "office_lobby": "white",
             "office": "slate", "warehouse": "white", "police_ground": "slate", "police_upper": "white",
             "corridor": "white", "clinic_ground": "white", "market": "white", "firebays": "beige", "workshop": "white",
             "garage": "white", "kiosk": "white", "shed": "white", "ring": "beige", "double_exam": "white",
             "double_ward": "sage", "double_class": "beige", "double_office": "slate", "bank_ground": "beige",
             "dept": "white", "nave": "beige", "gas": "white", "cafe": "terracotta", "parking": "white", "factory": "white",
             "hyper": "white", "cinema": "terracotta", "bar": "beige", "mall": "white", "creche": "sage", "changing": "white"}
NO_CEILING = ("warehouse", "firebays", "workshop", "garage", "shed", "factory", "parking", "hyper")
CEILING_USES = ("office_lobby", "office", "shop", "police_ground", "police_upper", "corridor", "clinic_ground", "market",
                "bank_ground", "dept", "nave", "gas", "cafe", "mall", "bar")


def finish_uv(mat):
    return {"parquet": DT.UV_PARQUET, "tile": UV_TILE, "marble": DT.UV_MARBLE, "carpet": UV_CARPET}[mat]


def interior(L, P, l):
    use, fh, z0 = P.levels[l]
    top = z0 + fh - SLAB
    walls, rooms = layout(P, use, l)
    partitions(L, P, walls, z0, top, WALL_BAND.get(use, "white"))
    hole_up = P.holes(l + 1)
    stair = ([P.stair] if P.stair else []) + P.holes(l, stair=False)
    for (x0, x1, y0, y1) in rects_minus(P.ix0, P.ix1, P.iy0, P.iy1, hole_up):        # ceiling under the next slab
        cm = "ceiling" if (use in CEILING_USES or use.startswith("double_")) else "paint"
        if use in NO_CEILING:
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
        zones.append((P.entry[0] - 0.3, P.entry[1] + 0.3, P.iy0 - 0.1, P.iy0 + 1.6))
        bays = P.bays(-P.hw, P.hw, 4.0 if P.A["skin"][0] == "metal" else None)
        for i in P.A.get("open_bays", ()):
            zones.append((bays[i][0], bays[i][1], P.iy0 - 0.1, P.iy0 + 3.0))
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


def shop_window(L, P, r, z, zones):
    """D87: a window display along the street wall (y0) left and right of the door, by shop type. One collision
    stand per span (<= 0.9 m, the window stays see-through above it); goods on it are small render-only pieces."""
    x0, x1, y0, y1 = r
    arch = P.arch
    if P.A.get("catalog", arch) == "PostOffice":
        return
    ya, yb = y0 + 0.08, y0 + 0.58
    # the shop counter (kitchen_run x1-2.4..x1-0.4 at y0+1.2) keeps its walkway: no stand in front of it (sec M)
    zones = zones + [(x1 - 2.6, x1, y0, y0 + 1.9)]
    for (a, b) in ((x0 + 0.4, min(x0 + 2.8, (x0 + x1) / 2 - 0.2)), (max(x1 - 2.8, (x0 + x1) / 2 + 0.2), x1 - 0.4)):
        if b - a < 1.0 or not clear(zones, (a, b, ya, yb + 0.1)):
            continue
        k = (P.name, round(a, 1))
        if "Market" in arch:                                                    # stepped produce stand + crates
            piece(L, (a, b, ya, yb, z, z + 0.5), "wood", UV_OAK)
            L["res0"].box(a, b, ya + 0.25, yb, z + 0.5, z + 0.8, mat="wood", uv=UV_OAK)
            n = int((b - a) / 0.45)
            for i in range(n):
                cx_ = a + 0.05 + i * (b - a - 0.1) / n
                for (zz, y_a, y_b) in ((z + 0.5, ya + 0.02, ya + 0.24), (z + 0.8, ya + 0.27, yb - 0.02)):
                    col = ("terracotta", "sage", "beige")[int(h01(k, i, zz) * 3)]
                    L["res0"].box(cx_, cx_ + 0.38, y_a, y_b, zz, zz + 0.12, mat="paint", uv=DT.paint_uv(col))
            L["geo"].box(a, b, ya + 0.25, yb, z + 0.5, z + 0.8)                  # the upper step collides too
            L["fire"].box(a, b, ya + 0.25, yb, z + 0.5, z + 0.8, mat="pen_wood")
        elif "Pharmacy" in arch:                                                # white display shelf with boxes
            piece(L, (a, b, ya, yb, z, z + 0.9), "paint", DT.paint_uv("white"), pen="wood")
            for i in range(int((b - a) / 0.22)):
                if h01(k, "box", i) < 0.7:
                    bx = a + 0.05 + i * 0.22
                    L["res0"].box(bx, bx + 0.16, ya + 0.1, ya + 0.3, z + 0.9, z + 1.06, mat="paint",
                                  uv=DT.paint_uv(("white", "sage", "beige")[int(h01(k, "bc", i) * 3)]))
        elif "Hardware" in arch:                                                # pallet stand with paint cans
            piece(L, (a, b, ya, yb, z, z + 0.3), "wood", UV_OAK)
            for i in range(int((b - a) / 0.2)):
                for j in range(2):
                    if h01(k, "can", i, j) < 0.8:
                        L["res0"].prism(a + 0.12 + i * 0.2, ya + 0.15 + j * 0.22, 0.08, z + 0.3, z + 0.48, n=6,
                                        mat="paint", uv=DT.paint_uv(("terracotta", "slate", "sage", "white")[int(h01(k, "cc", i, j) * 4)]))
        elif "News" in arch:                                                    # newspaper rack, papers face the street
            piece(L, (a, b, y0 + 0.02, yb, z, z + 0.8), "wood", UV_WALNUT)           # flush to the wall: no slot
            for i in range(int((b - a) / 0.32)):
                px = a + 0.04 + i * 0.32
                for zz in (z + 0.35, z + 0.6):
                    L["res0"].box(px, px + 0.28, ya + 0.1, ya + 0.15, zz, zz + 0.2, mat="paint",
                                  uv=DT.paint_uv("white" if h01(k, "np", i, zz) < 0.6 else "beige"))
        else:                                                                   # general shop: goods table
            piece(L, (a, b, ya, yb, z, z + 0.75), "wood", UV_LAMINATE)
            for i in range(int((b - a) / 0.3)):
                if h01(k, "g", i) < 0.75:
                    gx = a + 0.06 + i * 0.3
                    L["res0"].box(gx, gx + 0.22, ya + 0.1, yb - 0.1, z + 0.75, z + 0.92, mat="textile",
                                  uv=DT.band_fit("textile", "rug_a", gx, gx + 0.22, ya, yb))


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
            L["res0"].prism(cx, cy, 0.22, top - 0.6, top - 0.46, n=12, mat="metal", uv=DT.UV_PAINT)   # dead shade, shallow (D82)
        if kind in ("hall", "bedroom") and P.state < 2:                    # D90: smoke detector off the lamp (Res0, 20 tris)
            sx = cx + (0.9 if w > 2.4 else 0.0)
            sy = cy if w > 2.4 else cy + 0.9 * (1 if d > 2.4 else 0)
            L["res0"].prism(sx, sy, 0.065, top - 0.04, top - 0.005, n=6, mat="paint", uv=DT.paint_uv("white"))
    # D84: seeded layout variant per room (0 = the original kit, unchanged); swaps pieces, at most one collision
    # part more than the original layout (geo budgets)
    var = int(h01(P.name, l, kind, "var", round(cx, 1), round(cy, 1)) * 3)
    if kind == "living" and w > 2.6 and d > 2.6 and var == 1 and w > 3.2:
        # sofa against the far wall facing a TV unit, a bookcase in a side corner
        if clear(zones, (cx - 1.0, cx + 1.0, y1 - 0.95, y1)):
            sofa(L, cx - 1.0, cx + 1.0, y1 - 0.9, y1 - 0.05, z, "+y", fabric="beige" if h01(P.name, l, "sf") < 0.5 else "grey")
        if clear(zones, (cx - 0.7, cx + 0.7, y0, y0 + 0.5)):
            tv_unit(L, cx - 0.7, cx + 0.7, y0 + 0.05, y0 + 0.47, z, "-y")
        for (bx0, bx1) in ((x0 + 0.05, x0 + 0.95), (x1 - 0.95, x1 - 0.05)):
            if clear(zones, (bx0, bx1, y1 - 0.4, y1)) and (bx1 < cx - 1.0 or bx0 > cx + 1.0):
                bookshelf(L, bx0, bx1, y1 - 0.37, y1 - 0.02, z, "+y", key=(P.name, l, round(cx, 1)))
                break
        DT.rug(Lz, cx - 0.9, cx + 0.9, cy - 0.6, cy + 0.6, "rug_a")
        if clear(zones, (x0, x0 + 0.1, cy - 0.45, cy + 0.45)):                  # not in a side door (sec review M)
            DT.wall_art(L, x0, cy, z + 1.6, 0.7, 0.5, "+x", "art_%s" % "abcd"[int(h01(P.name, l, "art2", cx) * 4)])
    elif kind == "living" and w > 2.6 and d > 2.6 and var == 2 and d > 3.0:
        # dining room: table with chairs, a sideboard on the far wall
        if clear(zones, (cx - 0.9, cx + 0.9, cy - 0.95, cy + 0.95)):
            table(L, cx - 0.6, cx + 0.6, cy - 0.45, cy + 0.45, z)
            for (chx, chy, f) in ((cx - 0.3, cy - 0.7, "+y"), (cx + 0.3, cy - 0.7, "+y"), (cx - 0.3, cy + 0.7, "-y"),
                                  (cx + 0.3, cy + 0.7, "-y")):
                if h01(P.name, l, "chair", chx, chy) < 0.85:
                    chair(L, chx, chy, z, f, mat="wood", uv=UV_OAK)
        if clear(zones, (cx - 0.8, cx + 0.8, y1 - 0.5, y1)):
            sideboard(L, cx - 0.8, cx + 0.8, y1 - 0.47, y1 - 0.02, z)
        DT.wall_art(L, cx, y1 - 0.0 if y1 < P.iy1 - 0.01 else y1, z + 1.7, 0.6, 0.6, "-y", "art_%s" % "abcd"[int(h01(P.name, l, "art", cx) * 4)])
    elif kind == "living" and w > 2.6 and d > 2.6:
        DT.rug(Lz, cx - 1.0, cx + 1.0, cy - 0.7, cy + 0.7, "rug_b" if h01(P.name, l, cx) < 0.5 else "rug_a")
        # lounge set along the axis that leaves a 0.9 m passage on both sides (walkability)
        if w >= 2.84 + 1.8 and clear(zones, (cx - 1.5, cx + 1.5, cy - 0.5, cy + 0.5)):
            DT.coffee_table(Lz, cx - 0.4, cx + 0.4, cy - 0.3, cy + 0.3)
            DT.lounge_chair(Lz, cx - 1.0, cy, "+x")
            DT.lounge_chair(Lz, cx + 1.0, cy, "-x")
        elif d >= 2.84 + 1.8 and w >= 0.85 + 1.8 and clear(zones, (cx - 0.5, cx + 0.5, cy - 1.5, cy + 1.5)):
            DT.coffee_table(Lz, cx - 0.3, cx + 0.3, cy - 0.4, cy + 0.4)
            DT.lounge_chair(Lz, cx, cy - 1.0, "+y")
            DT.lounge_chair(Lz, cx, cy + 1.0, "-y")
        corners = sorted([(x0 + 0.45, y0 + 0.45), (x1 - 0.45, y0 + 0.45), (x0 + 0.45, y1 - 0.45), (x1 - 0.45, y1 - 0.45)],
                         key=lambda c: -(abs(c[0]) + abs(c[1])))               # outer corners first
        for (px, py) in corners:
            if clear(zones, (px - 0.35, px + 0.35, py - 0.35, py + 0.35)):
                DT.potted_plant(Lz, px, py, collide=True)
                break
        DT.wall_art(L, cx, y1 - 0.0 if y1 < P.iy1 - 0.01 else y1, z + 1.6, 0.8, 0.8, "-y", "art_%s" % "abcd"[int(h01(P.name, l, "art", cx) * 4)])
    elif kind == "bedroom" and w > 3.0 and d >= 3.45 and var == 1:              # desk leaves a way in (sec review L)
        # children's room: two single beds along the side walls, a desk under the window wall
        for (a, b) in ((x0 + 0.05, x0 + 0.95), (x1 - 0.95, x1 - 0.05)):
            if clear(zones, (a, b, y1 - 2.1, y1)):
                bed(L, a, b, y1 - 2.05, y1 - 0.05, z, fabric="blue" if a < cx else "beige")
        if clear(zones, (cx - 0.6, cx + 0.6, y0, y0 + 0.65)):
            table(L, cx - 0.6, cx + 0.6, y0 + 0.05, y0 + 0.65, z)
            chair(L, cx, y0 + 0.9, z, "-y", mat="wood", uv=UV_OAK)
    elif kind == "bedroom" and w > 2.2 and d > 2.6 and var == 2 and w >= 3.15:  # bed-bookcase gap >= 0.75 m (sec L)
        # bed against a side wall, chest of drawers + bookcase
        if clear(zones, (x0, x0 + 1.5, y1 - 2.1, y1)):
            bed(L, x0 + 0.05, x0 + 1.45, y1 - 2.05, y1 - 0.05, z, fabric="beige")
        if clear(zones, (x1 - 0.95, x1, y1 - 0.4, y1)):
            bookshelf(L, x1 - 0.95, x1 - 0.05, y1 - 0.37, y1 - 0.02, z, "+y", key=(P.name, l, "bed", round(cx, 1)))
        if clear(zones, (x1 - 0.5, x1, cy - 0.5, cy + 0.5)) and x1 - 0.5 > x0 + 1.45 + 0.75:
            sideboard(L, x1 - 0.47, x1 - 0.02, cy - 0.5, cy + 0.5, z)
        DT.rug(Lz, x0 + 1.5, min(x1 - 0.6, x0 + 2.7), cy - 0.6, cy + 0.6, "rug_b")
    elif kind == "bedroom" and w > 2.2 and d > 2.6:
        bw = 1.6 if w > 3.0 else 0.95
        if clear(zones, (cx - bw / 2, cx + bw / 2, y1 - 2.1, y1)):
            bed(L, cx - bw / 2, cx + bw / 2, y1 - 2.1, y1 - 0.05, z, fabric="blue" if h01(P.name, l, cy) < 0.5 else "beige")
        if w > 3.4 and clear(zones, (x0, x0 + 0.65, y1 - 1.7, y1)) and cx - bw / 2 - (x0 + 0.65) > 0.75:
            wardrobe(L, x0 + 0.05, x0 + 0.65, y1 - 1.7, y1 - 0.05, z)
        DT.rug(Lz, cx - 0.9, cx + 0.9, y1 - 3.0, y1 - 2.2, "rug_a")
    elif kind == "kitchen" and w > 2.0 and var == 1 and d > 2.4:
        # galley: the run along the side wall, a fridge at its end, a small table by the window
        run = (x1 - 0.62, x1 - 0.02, y0 + 0.1, y0 + 0.1 + min(d - 1.2, 2.6))
        if clear(zones, run):
            kitchen_run(L, *run, z)
            f0, f1 = run[3] + 0.02, run[3] + 0.69
            gap = y1 - f1                                         # slot behind the fridge: closed or walkable (sec M)
            if clear(zones, (x1 - 0.67, x1, f0, f1)) and gap >= -1e-6 and (gap <= 0.05 or gap >= 0.75):
                fridge(L, x1 - 0.67, x1 - 0.02, f0, f1, z)
        if w > 2.6 and clear(zones, (x0, x0 + 0.9, cy - 0.45, cy + 0.45)):
            table(L, x0 + 0.05, x0 + 0.75, cy - 0.4, cy + 0.4, z)
            chair(L, x0 + 1.0, cy, z, "-x", mat="wood", uv=UV_OAK)
    elif kind == "kitchen" and w > 2.0:
        for (ka, kb) in ((y1 - 0.62, y1 - 0.02), (y0 + 0.02, y0 + 0.62)):
            box = (x1 - min(w - 0.2, 3.1) - 0.1, x1 - 0.1, ka, kb)
            if clear(zones, box):
                kitchen_run(L, box[0], box[1], ka, kb, z)
                break
        if d > 3.0 and clear(zones, (cx - 0.5, cx + 0.5, cy - 0.4, cy + 0.4)):
            table(L, cx - 0.5, cx + 0.5, cy - 0.4, cy + 0.4, z)
    elif kind == "shop":
        shop_window(L, P, r, z, zones)                                           # D87 window display per shop type
        for row_y in (cy - 1.3, cy + 0.3):
            shelf_unit(L, x0 + 1.0, cx - 0.4, row_y - 0.25, row_y + 0.25, z, h=1.6)
        kitchen_run(L, x1 - 2.4, x1 - 0.4, y0 + 1.2, y0 + 1.8, z)                     # counter
        L["res0"].box(x1 - 1.6, x1 - 1.2, y0 + 1.35, y0 + 1.65, z + 0.92, z + 1.15, mat="metal", uv=DT.UV_PAINT)  # till
        rack = None
        if P.A.get("catalog", P.arch) == "PostOffice":
            racks = [(a, b, y1 - 0.45, y1 - 0.05) for (a, b) in ((cx + 0.2, min(cx + 2.0, x1 - 0.4)), (cx - 2.0, cx - 0.2),
                                                                  (x0 + 0.4, x0 + 2.2))]
            rack = next((rk for rk in racks if rk[1] - rk[0] > 1.2 and clear(zones, rk)), None)   # first wall spot off the doors
        if rack:
            # D71 mail sorting rack: a pigeonhole frame with letters and parcels, searched (table post)
            piece(L, rack + (z, z + 1.9), "wood", UV_WALNUT)
            cols = int((rack[1] - rack[0]) / 0.3)
            for r_ in range(5):
                zz = z + 0.35 + r_ * 0.3
                L["res0"].box(rack[0], rack[1], rack[2] - 0.01, rack[2], zz, zz + 0.02, mat="wood", uv=UV_WALNUT)
                for c_ in range(cols):
                    if h01(P.name, "mail", r_, c_) < 0.55:
                        mx = rack[0] + 0.05 + c_ * (rack[1] - rack[0] - 0.1) / cols
                        L["res0"].quad([(mx, rack[2] - 0.02, zz + 0.02), (mx + 0.2, rack[2] - 0.02, zz + 0.02), (mx + 0.2, rack[2] - 0.02, zz + 0.2),
                                        (mx, rack[2] - 0.02, zz + 0.2)], (0, -1, 0), "paint",
                                       DT.paint_uv("beige" if (r_ + c_) % 3 else "white"))   # letters: front quads (perf L)
            if not P.near_collapse((rack[0] + rack[1]) / 2, rack[2] - 0.7, l):
                search_point(L, (rack[0] + rack[1]) / 2, rack[2] - 0.7, z)
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
        office_b = var == 1 and kind == "office" and w > 3.2 and d > 3.2 and not (
            l == 0 and P.A.get("catalog", P.arch) == "Police")                      # police offices keep the lockers
        if office_b:
            # D84: two desks facing each other, a filing cabinet in a corner, chairs
            if clear(zones, (cx - 0.9, cx + 0.9, cy - 1.5, cy + 1.5)):
                table(L, cx - 0.8, cx + 0.8, cy - 0.8, cy + 0.8, z)          # two facing workstations, one block (perf M)
                for (my, f) in ((cy - 0.35, "+y"), (cy + 0.35, "-y")):
                    L["res0"].box(cx - 0.25, cx + 0.25, my - 0.05, my + 0.05, z + 0.76, z + 1.1, mat="metal", uv=DT.UV_PAINT)
                chair(L, cx, cy - 1.15, z, "+y")
                chair(L, cx, cy + 1.15, z, "-y")
            for (a, b) in ((x0 + 0.05, x0 + 0.55), (x1 - 0.55, x1 - 0.05)):
                if clear(zones, (a, b, y1 - 0.65, y1)):
                    filing_cabinet(L, a, b, y1 - 0.62, y1 - 0.02, z)
                    break
        elif clear(zones, (cx - 0.9, cx + 0.9, cy - 1.2, cy + 0.6)):
            desk(L, cx, cy - 0.3, z, rot=(w < d))
        if (l == 0 and P.A.get("catalog", P.arch) == "Police" and w > 2.4
                and not getattr(P, "sky_lockers", False)):                      # D71 gear lockers (table police), one bank
            for (a0, a1) in ((x0 + 0.1, x0 + 1.45), (x1 - 1.45, x1 - 0.1)):
                if clear(zones, (a0, a1, y1 - 0.5, y1 - 0.05)):
                    piece(L, (a0, a1, y1 - 0.5, y1 - 0.05, z, z + 1.85), "paint", DT.paint_uv("slate"), pen="metal")
                    for i in range(3):                                            # three doors with vents and handles
                        dx = a0 + 0.02 + i * (a1 - a0 - 0.04) / 3
                        dw = (a1 - a0 - 0.04) / 3
                        L["res0"].box(dx + 0.01, dx + dw - 0.01, y1 - 0.51, y1 - 0.5, z + 0.05, z + 1.8, mat="paint",
                                      uv=DT.paint_uv("slate"))
                        for v in range(3):                                       # vents: front quads only (perf L)
                            vz = z + 1.5 + v * 0.06
                            L["res0"].quad([(dx + 0.08, y1 - 0.512, vz), (dx + dw - 0.08, y1 - 0.512, vz), (dx + dw - 0.08, y1 - 0.512, vz + 0.02),
                                            (dx + 0.08, y1 - 0.512, vz + 0.02)], (0, -1, 0), "metal", DT.UV_STEEL)
                        L["res0"].box(dx + dw - 0.08, dx + dw - 0.05, y1 - 0.53, y1 - 0.51, z + 0.95, z + 1.1, mat="metal", uv=DT.UV_STEEL)
                    if not P.near_collapse((a0 + a1) / 2, y1 - 1.1, l):
                        search_point(L, (a0 + a1) / 2, y1 - 1.1, z)
                    P.sky_lockers = True                                         # one bank per station (perf L)
                    break
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
    elif kind == "waiting":
        for i in range(3):
            bx = x0 + 0.4 + i * 2.4
            if bx + 2.0 < x1 and clear(zones, (bx, bx + 2.0, y0 + 0.2, y0 + 0.65)):
                DT.bench(Lz, bx, bx + 2.0, y0 + 0.2, y0 + 0.65)
        if clear(zones, (x1 - 3.4, x1 - 0.6, y1 - 1.2, y1 - 0.6)):
            kitchen_run(L, x1 - 3.4, x1 - 0.6, y1 - 1.2, y1 - 0.6, z)                  # reception counter
        DT.potted_plant(Lz, x0 + 0.5, y1 - 0.5) if clear(zones, (x0, x0 + 1.0, y1 - 1.0, y1)) else None
        if lit:
            for gx in (x0 + 2.0, cx, x1 - 2.0):
                L["res0"].hquad(gx - 0.3, gx + 0.3, cy - 0.6, cy + 0.6, top - 0.025, mat="lamp_cool", up=False)
    elif kind == "exam":
        # D85: the medicine shelving and its search spot stay reachable whatever variant is drawn (sec review M)
        zones = zones + [(x1 - 1.1, x1, y0, y0 + 1.5)]
        if var == 1 and w > 2.6 and d > 2.6:
            # D85 treatment room: couch on the far wall, doctor's desk + chair, a thin folding screen
            if clear(zones, (cx - 1.0, cx + 1.0, y1 - 0.8, y1)):
                bed(L, cx - 1.0, cx + 1.0, y1 - 0.75, y1 - 0.05, z, fabric="grey")
            if clear(zones, (x0 + 0.05, x0 + 0.75, cy - 0.6, cy + 0.6)):
                table(L, x0 + 0.05, x0 + 0.75, cy - 0.6, cy + 0.6, z)
                chair(L, x0 + 1.0, cy, z, "-x")
            sx = min(x1 - 0.3, cx + 1.2)
            for j in range(3):
                yy = y1 - 0.9 - j * 0.55
                if clear(zones, (sx - 0.015, sx + 0.015, yy - 0.5, yy)):            # not across a door or the shelving
                    L["res0"].box(sx - 0.015, sx + 0.015, yy - 0.5, yy, z, z + 1.7, mat="fabric", uv=UV_FAB["blue"])
        elif var == 2 and w > 3.2 and d > 2.9:                       # clear of the medicine shelving (sec review M)
            # D85 procedure room: reclining treatment chair (collides) and an instrument trolley (collides)
            if clear(zones, (cx - 0.4, cx + 0.4, cy - 0.9, cy + 0.9)):
                piece(L, (cx - 0.35, cx + 0.35, cy - 0.9, cy + 0.9, z, z + 0.55), "fabric", UV_FAB["blue"], pen="wood")
                L["res0"].box(cx - 0.35, cx + 0.35, cy + 0.72, cy + 0.9, z + 0.55, z + 1.05, mat="fabric", uv=UV_FAB["blue"])
                L["res0"].box(cx - 0.03, cx + 0.03, cy - 0.03, cy + 0.03, z + 0.55, z + 1.9, mat="metal", uv=DT.UV_STEEL)  # lamp arm
                L["res0"].prism(cx, cy - 0.2, 0.16, z + 1.9, z + 1.98, n=10, mat="metal", uv=DT.UV_PAINT)
            if clear(zones, (cx - 1.2, cx - 0.7, cy - 0.3, cy + 0.3)):              # trolley on the side away from the shelving
                piece(L, (cx - 1.2, cx - 0.7, cy - 0.3, cy + 0.3, z, z + 0.9), "metal", DT.UV_STEEL, pen="metal")
        elif clear(zones, (x0 + 0.1, x0 + 0.85, cy - 1.0, cy + 1.0)):
            bed(L, x0 + 0.1, x0 + 0.85, cy - 1.0, cy + 1.0, z, fabric="grey")
        cabs = P.__dict__.setdefault("sky_cabinets", set())                       # D71: one cabinet per floor (security L)
        if clear(zones, (x1 - 1.0, x1 - 0.1, y0 + 0.1, y0 + 0.55)):
            shelf_unit(L, x1 - 1.0, x1 - 0.1, y0 + 0.1, y0 + 0.55, z, h=1.8)
        if l not in cabs and clear(zones, (x1 - 1.0, x1 - 0.1, y0 + 0.1, y0 + 0.55)):
            cabs.add(l)
            # D71 medicine cabinet: white doors with a red cross on the shelving, searched (table medical)
            L["res0"].box(x1 - 0.98, x1 - 0.12, y0 + 0.55, y0 + 0.57, z + 1.0, z + 1.75, mat="paint", uv=DT.paint_uv("white"))
            L["res0"].box(x1 - 0.6, x1 - 0.5, y0 + 0.57, y0 + 0.58, z + 1.2, z + 1.55, mat="paint", uv=DT.paint_uv("terracotta"))
            L["res0"].box(x1 - 0.72, x1 - 0.38, y0 + 0.57, y0 + 0.58, z + 1.33, z + 1.42, mat="paint", uv=DT.paint_uv("terracotta"))
            if not P.near_collapse(x1 - 0.55, y0 + 1.0, l):
                search_point(L, x1 - 0.55, y0 + 1.0, z)
        if lit:
            L["res0"].hquad(cx - 0.3, cx + 0.3, cy - 0.6, cy + 0.6, top - 0.025, mat="lamp_cool", up=False)
    elif kind == "dorm":
        for bx in (x0 + 0.1, x1 - 0.95):
            if clear(zones, (bx, bx + 0.85, y1 - 2.05, y1)):
                bed(L, bx, bx + 0.85, y1 - 2.05, y1 - 0.05, z, fabric="grey")
        if lamp:
            DT.pendant(L, cx, cy, top - 0.02, 0.5, r=0.2)
    elif kind == "room":
        if clear(zones, (cx - 0.9, cx + 0.9, cy - 0.7, cy + 0.7)):
            desk(L, cx, cy, z, rot=(w < d))
        if lit:
            L["res0"].hquad(cx - 0.3, cx + 0.3, cy - 0.6, cy + 0.6, top - 0.025, mat="lamp_cool", up=False)
    elif kind == "market":
        n_aisle = max(1, int((d - 4.0) / 2.6))
        for i in range(n_aisle):
            ry = y0 + 3.2 + i * 2.6
            for (ax0, ax1) in ((x0 + 1.5, cx - 1.2), (cx + 1.2, x1 - 1.5)):
                if ax1 - ax0 > 1.0 and clear(zones, (ax0, ax1, ry - 0.3, ry + 0.3)):
                    shelf_unit(L, ax0, ax1, ry - 0.3, ry + 0.3, z, h=1.7)
        for cxk in (x1 - 4.5, x1 - 2.5):                                           # checkouts
            if clear(zones, (cxk - 0.35, cxk + 0.35, y0 + 1.0, y0 + 2.4)):
                kitchen_run(L, cxk - 0.35, cxk + 0.35, y0 + 1.0, y0 + 2.4, z)
        if lit:
            for gx in [x0 + 2.0 + i * 3.0 for i in range(int((w - 2.0) / 3.0))]:
                for gy in (y0 + 2.0, cy, y1 - 2.0):
                    L["res0"].hquad(gx - 0.3, gx + 0.3, gy - 0.6, gy + 0.6, top - 0.025, mat="lamp_cool", up=False)
    elif kind in ("bay", "workshop", "garage"):
        n = max(1, int((w - 1.0) / 2.6))
        for i in range(n):
            sx = x0 + 0.4 + i * 2.6
            if clear(zones, (sx, sx + 2.0, y1 - 0.6, y1 - 0.1)):
                shelf_unit(L, sx, sx + 2.0, y1 - 0.6, y1 - 0.1, z, h=2.0)
        if kind == "workshop" and clear(zones, (x0 + 0.1, x0 + 0.8, cy - 1.5, cy + 1.5)):
            kitchen_run(L, x0 + 0.1, x0 + 0.8, cy - 1.5, cy + 1.5, z)                 # workbench
        if lit:
            for gx in [x0 + 2.0 + i * 4.0 for i in range(max(1, int((w - 2.0) / 4.0)))]:
                L["res0"].prism(gx, cy, 0.25, top - 0.5, top - 0.42, n=12, mat="lamp_cool")
    elif kind == "kiosk":
        if clear(zones, (x0 + 0.1, x1 - 0.1, y0 + 0.05, y0 + 0.5)):
            kitchen_run(L, x0 + 0.1, x1 - 0.1, y0 + 0.05, y0 + 0.5, z)
    elif kind == "shed":
        if clear(zones, (x0 + 0.1, x1 - 0.1, y1 - 0.45, y1 - 0.05)):
            shelf_unit(L, x0 + 0.1, x1 - 0.1, y1 - 0.45, y1 - 0.05, z, h=1.8)
    elif kind == "reception":
        if clear(zones, (cx - 1.6, cx + 1.6, y0 + 2.4, y0 + 3.0)):
            kitchen_run(L, cx - 1.6, cx + 1.6, y0 + 2.4, y0 + 3.0, z)                  # front desk
        for (bx0, bx1) in ((x0 + 0.2, x0 + 2.2), (x1 - 2.2, x1 - 0.2)):
            if bx1 - bx0 > 1.0 and clear(zones, (bx0, bx1, y0 + 0.2, y0 + 0.65)):
                DT.bench(Lz, bx0, bx1, y0 + 0.2, y0 + 0.65)
        for (px, py) in ((x0 + 0.5, y1 - 0.5), (x1 - 0.5, y1 - 0.5)):
            if clear(zones, (px - 0.35, px + 0.35, py - 0.35, py + 0.35)):
                DT.potted_plant(Lz, px, py, collide=True)
        if lit:
            for gx in (cx - w / 4, cx + w / 4):
                L["res0"].hquad(gx - 0.3, gx + 0.3, cy - 0.6, cy + 0.6, top - 0.025, mat="lamp_cool", up=False)
    elif kind in ("ward", "class"):
        far = y0 if abs(y1) < abs(y0) else y1                                      # wall away from the corridor
        sgn = 1 if far == y0 else -1
        if kind == "ward":
            n = max(1, min(3, int((w - 0.4) / 1.4)))
            for i in range(n):
                bx = x0 + 0.3 + i * (w - 0.6) / n + ((w - 0.6) / n - 0.9) / 2
                by0, by1 = (far + 0.05, far + 2.05) if sgn > 0 else (far - 2.05, far - 0.05)
                if clear(zones, (bx, bx + 0.9, by0, by1)):
                    bed(L, bx, bx + 0.9, by0, by1, z, fabric="grey" if var != 2 else "blue")
                    L["res0"].box(bx - 0.1, bx + 1.0, by0, by1, top - 0.35, top - 0.33, mat="metal", uv=DT.UV_STEEL)  # curtain rail
                    if var >= 1:                                                     # D85 ward detail, render-only, thin
                        ix = bx + 1.0
                        iy = by1 - 0.2 if sgn > 0 else by0 + 0.2
                        L["res0"].box(ix - 0.015, ix + 0.015, iy - 0.015, iy + 0.015, z, z + 1.8, mat="metal", uv=DT.UV_STEEL)  # IV stand
                        L["res0"].box(ix - 0.06, ix + 0.06, iy - 0.02, iy + 0.02, z + 1.55, z + 1.75, mat="paint", uv=DT.paint_uv("white"))
                        if h01(P.name, l, "curtain", i) < 0.5:                       # curtain half drawn on the rail
                            cy0 = by0 if sgn > 0 else by1 - 1.0
                            L["res0"].box(bx - 0.11, bx - 0.09, cy0, cy0 + 1.0, z + 0.3, top - 0.36, mat="fabric", uv=UV_FAB["beige"])
        elif var == 1 and d > 4.0 and w > 4.0:                                      # no corner pockets (sec review M)
            # D85 science room: two long benches along the side walls and a teacher's bench at the front (3 parts)
            for (a, b) in ((x0 + 0.05, x0 + 0.75), (x1 - 0.75, x1 - 0.05)):
                box = (a, b, min(far + sgn * 0.8, far + sgn * (d - 1.6)), max(far + sgn * 0.8, far + sgn * (d - 1.6)))
                if clear(zones, box):
                    kitchen_run(L, *box, z)
            tb = (cx - 1.0, cx + 1.0, min(far + sgn * 0.02, far + sgn * 0.62), max(far + sgn * 0.02, far + sgn * 0.62))   # flush: no slot (D87)
            if clear(zones, tb):
                table(L, *tb, z, h=0.9)
        elif var == 2 and w > 4.0:
            # D85 reading room: bookcases on the far wall, one large table (<= 3 parts like the bench rows)
            nb = min(2, int((w - 1.0) / 1.0))
            for i in range(nb):
                a = x0 + 0.5 + i * 1.0
                by = (far + 0.02, far + 0.37) if sgn > 0 else (far - 0.37, far - 0.02)
                if clear(zones, (a, a + 0.9, by[0], by[1])):
                    bookshelf(L, a, a + 0.9, by[0], by[1], z, "+y" if sgn < 0 else "-y", key=(P.name, l, "lib", i))
            tb = (cx - 1.2, cx + 1.2, cy - 0.5, cy + 0.5)
            if clear(zones, tb):
                table(L, *tb, z)
                for (chx, chy, f) in ((cx - 0.6, cy - 0.75, "+y"), (cx + 0.6, cy + 0.75, "-y")):   # 2 chairs (perf L)
                    chair(L, chx, chy, z, f, mat="wood", uv=UV_OAK)
        else:
            for row in range(3):                                                    # bench desk rows
                ry = far + sgn * (1.0 + row * 1.4)
                box = (x0 + 0.8, x1 - 1.4, min(ry, ry + sgn * 0.5), max(ry, ry + sgn * 0.5))
                if box[1] - box[0] > 1.0 and clear(zones, box):
                    table(L, *box, z)
            bx = x0 + 0.02                                                          # blackboard on the side wall
            L["res0"].quad([(bx, cy - 1.2, z + 0.9), (bx, cy + 1.2, z + 0.9), (bx, cy + 1.2, z + 2.1), (bx, cy - 1.2, z + 2.1)],
                           (1, 0, 0), "paint", DT.paint_uv("slate"))
        if lit:
            L["res0"].hquad(cx - 0.3, cx + 0.3, cy - 0.6, cy + 0.6, top - 0.025, mat="lamp_cool", up=False)
    elif kind == "banking":
        if clear(zones, (x0 + 0.5, -1.0, y1 - 1.6, y1 - 1.0)):
            kitchen_run(L, x0 + 0.5, -1.0, y1 - 1.6, y1 - 1.0, z)                   # teller counter + glass screen
            L["res0"].quad([(x0 + 0.5, y1 - 1.3, z + 0.95), (-1.0, y1 - 1.3, z + 0.95), (-1.0, y1 - 1.3, z + 1.9),
                            (x0 + 0.5, y1 - 1.3, z + 1.9)], (0, -1, 0), "glass", UV_GLASS, double=True)
        for (bx0, bx1) in ((x1 - 2.6, x1 - 0.4),):
            if clear(zones, (bx0, bx1, y0 + 0.2, y0 + 0.65)):
                DT.bench(Lz, bx0, bx1, y0 + 0.2, y0 + 0.65)
        if lit:
            for gx in (x0 + 2.0, cx, x1 - 2.0):
                L["res0"].hquad(gx - 0.3, gx + 0.3, cy - 0.6, cy + 0.6, top - 0.025, mat="lamp_cool", up=False)
    elif kind == "vault":
        for (sx0_, sx1_, sy0_, sy1_) in ((x0 + 0.1, x0 + 0.55, y0 + 1.6, y1 - 0.2), (x0 + 0.6, x1 - 0.2, y1 - 0.5, y1 - 0.05)):
            if sx1_ - sx0_ > 0.3 and sy1_ - sy0_ > 0.3 and clear(zones, (sx0_, sx1_, sy0_, sy1_)):
                piece(L, (sx0_, sx1_, sy0_, sy1_, z, z + 2.0), "metal", DT.UV_STEEL, pen="metal", view=True)   # deposit boxes
        if lit:
            L["res0"].hquad(cx - 0.3, cx + 0.3, cy - 0.6, cy + 0.6, top - 0.025, mat="lamp_cool", up=False)
    elif kind == "nave":
        yb0, yb1 = y0 + 3.0, y1 - 4.0
        ry = yb0
        while ry + 0.5 < yb1:                                                       # pews, central aisle 1.8 m
            for (px0, px1) in ((x0 + 0.9, -0.9), (0.9, x1 - 0.9)):
                if P.A.get("decor") == "hanged" and h01(P.name, "pew", round(ry, 1), px0) < 0.3:
                    if clear(zones, (px0, px1, ry, ry + 0.5)):                     # toppled pew on its back
                        piece(L, (px0 + 0.1, px1 - 0.1, ry - 0.1, ry + 0.8, z, z + 0.25), "wood", UV_WALNUT)
                    continue
                if clear(zones, (px0, px1, ry, ry + 0.5)):
                    piece(L, (px0, px1, ry, ry + 0.45, z, z + 0.45), "wood", UV_WALNUT)
                    L["res0"].box(px0, px1, ry + 0.45, ry + 0.5, z, z + 0.9, mat="wood", uv=UV_WALNUT)
            ry += 1.1
        for k in ("res0", "res1", "geo", "fire"):                                    # chancel step + altar
            kw = kw_for(k, "stone", DT.stone_uv("limestone"), "concrete")
            L[k].box(x0, x1, y1 - 3.0, y1, z, z + 0.3, **kw)
            L[k].box(-1.0, 1.0, y1 - 1.6, y1 - 0.8, z + 0.3, z + 1.3, **kw)
        L["road"].hquad(x0, x1, y1 - 3.0, y1, z + 0.3, mat="road_int", uv=UV_TILE)
        if P.A.get("decor") == "hanged":
            hanged(L, P, r, z, top)
        if lamp:
            for gy in (yb0 + 2.0, cy, yb1 - 1.0):
                DT.pendant(L, 0.0, gy, top - 0.02, 2.5, r=0.5)
    elif kind in ("gas", "cafe"):
        if clear(zones, (x0 + 0.3, x0 + 3.3, y1 - 0.75, y1 - 0.15)):
            kitchen_run(L, x0 + 0.3, x0 + 3.3, y1 - 0.75, y1 - 0.15, z)                # counter
        if kind == "gas":
            for (ax0, ax1) in ((cx - 0.5, cx + 2.5),):
                for ry in (cy - 0.6, cy + 1.0):
                    if clear(zones, (ax0, ax1, ry - 0.25, ry + 0.25)):
                        shelf_unit(L, ax0, ax1, ry - 0.25, ry + 0.25, z, h=1.5)
            if clear(zones, (x1 - 0.8, x1 - 0.1, y1 - 2.2, y1 - 0.1)):
                piece(L, (x1 - 0.8, x1 - 0.1, y1 - 2.2, y1 - 0.1, z, z + 2.0), "metal", DT.UV_ALU, pen="metal", view=True)  # fridges
        else:
            for tx in (cx - 1.5, cx + 1.5):
                if clear(zones, (tx - 0.4, tx + 0.4, cy - 0.4, cy + 0.4)):
                    table(L, tx - 0.4, tx + 0.4, cy - 0.4, cy + 0.4, z)
        if lit:
            for gx in (x0 + 2.0, cx, x1 - 2.0):
                L["res0"].hquad(gx - 0.3, gx + 0.3, cy - 0.6, cy + 0.6, top - 0.025, mat="lamp_cool", up=False)
    elif kind == "dept":
        ry = y0 + 3.0
        while ry < y1 - 1.0:
            rx = x0 + 1.5
            while rx + 3.5 < x1 - 1.0:
                box = (rx, rx + 3.5, ry - 0.3, ry + 0.3)
                if clear(zones, box) and not any(P.in_hole(px, py, l, 1.0) for px in box[:2] for py in box[2:]) and \
                        not (P.atrium and l >= 1 and box[0] < P.atrium[1] + 1.0 and P.atrium[0] - 1.0 < box[1]
                             and box[2] < P.atrium[3] + 1.0 and P.atrium[2] - 1.0 < box[3]):
                    shelf_unit(L, *box, z, h=1.6)
                rx += 5.5
            ry += 3.2
        if l == 0:
            for cxk in (-6.0, 6.0):                                                  # checkouts by the entrance
                if clear(zones, (cxk - 0.35, cxk + 0.35, y0 + 1.0, y0 + 2.4)):
                    kitchen_run(L, cxk - 0.35, cxk + 0.35, y0 + 1.0, y0 + 2.4, z)
        if lit:
            for gx in [x0 + 3.0 + i * 5.0 for i in range(int((w - 3.0) / 5.0))]:
                for gy in [y0 + 2.5 + j * 5.0 for j in range(int((d - 2.5) / 5.0))]:
                    if not P.in_hole(gx, gy, l + 1, 0.5):
                        L["res0"].hquad(gx - 0.3, gx + 0.3, gy - 0.6, gy + 0.6, top - 0.025, mat="lamp_cool", up=False)
    elif kind == "factory":
        for row, my in enumerate((y0 + 4.0, y0 + 9.0)):                               # machine rows
            mx = x0 + 3.0
            while mx + 2.2 < x1 - 2.0:
                box = (mx, mx + 2.2, my - 0.7, my + 0.7)
                if clear(zones, box) and h01(P.name, "mach", row, round(mx, 1)) < 0.8:
                    piece(L, box + (z, z + 1.6), "metal", DT.UV_PAINT, pen="metal", view=True)
                    piece(L, (mx + 0.3, mx + 1.0, my - 0.3, my + 0.3, z + 1.6, z + 2.3), "metal", DT.UV_STEEL, pen="metal",
                          res1=False, view=True)                                 # head unit collides (D82: climbable machine)
                mx += 4.5
        n_racks = max(1, int((x1 - x0 - 8.0) / 6.0))
        for i in range(n_racks):
            rx = x0 + 4.0 + i * 6.0
            if clear(zones, (rx, rx + 3.0, y1 - 1.02, y1)):                       # flush: a 0.4 m slot behind was a wedge (D87)
                shelf_unit(L, rx, rx + 3.0, y1 - 1.02, y1 - 0.02, z, h=3.0)
        for yy in (y0 + 1.0, y1 - 0.5):                                              # crane runway + bridge (Res0)
            L["res0"].box(x0, x1, yy - 0.2, yy + 0.2, top - 1.4, top - 1.0, mat="metal", uv=DT.UV_PAINT)
        L["res0"].box(cx - 0.3, cx + 0.3, y0 + 1.0, y1 - 0.5, top - 1.6, top - 1.2, mat="metal", uv=DT.UV_PAINT)
        if lit:
            for gx in [x0 + 3.0 + i * 6.0 for i in range(int((x1 - x0 - 2.0) / 6.0))]:
                for gy in (y0 + 3.0, cy, y1 - 3.0):
                    L["res0"].prism(gx, gy, 0.3, top - 0.9, top - 0.8, n=12, mat="lamp_cool")
    elif kind == "parking":
        stalls = [(y0 + 0.1, y0 + 4.3), (y1 - 4.3, y1 - 0.1)]          # D90 wedge check: nose 0.1 m off the barrier (was 0.4)
        for si, (sy0_, sy1_) in enumerate(stalls):
            sx = x0 + 3.0
            while sx + 1.9 < x1 - 0.8:
                box = (sx, sx + 1.9, sy0_, sy1_)
                if clear(zones, box) and not P.in_hole(sx + 0.9, (sy0_ + sy1_) / 2, l, 1.0) and \
                        h01(P.name, "car", l, si, round(sx, 1)) < 0.45:
                    wreck(L, sx + 0.95, (sy0_ + sy1_) / 2, z, P.name, l, si, sx)
                sx += 2.6
        if lit:
            for gx in [x0 + 2.5 + i * 5.0 for i in range(int((w - 2.5) / 5.0))]:
                for gy in (y0 + 2.5, y1 - 2.5):
                    L["res0"].hquad(gx - 0.6, gx + 0.6, gy - 0.1, gy + 0.1, top - 0.03, mat="lamp_cool", up=False)
    elif kind == "cell":
        bed(L, x0 + 0.05, x0 + 0.85, y1 - 2.05, y1 - 0.05, z, fabric="grey")
        piece(L, (x1 - 0.5, x1 - 0.05, y1 - 0.55, y1 - 0.05, z, z + 0.45), "metal", DT.UV_STEEL, pen="metal")
    elif kind in VENUE_KINDS:
        furnish_venue(L, P, l, r, kind, z, top, zones)


CAR_PAINT = ("white", "slate", "terracotta", "sage", "beige")


def wreck(L, x, y, z, *key):
    """Burnt-out / abandoned car hulk (static scenery, 1.9 x 4.2 m along Y, front -Y). Collision: body + cabin
    boxes (unchanged). D78: render shape follows the Wreck_Sedan kit (D73): stepped bonnet / cabin / boot,
    sloped screens, empty side windows, bumpers, rust through the panels, flat tyres; Res1 body + cabin."""
    col = CAR_PAINT[int(h01("carc", *key) * len(CAR_PAINT))]
    burnt = h01("carb", *key) < 0.35
    mat, uv = ("rust", UVBand(S.MATERIALS["rust"]["bands"]["burnt"], 1.0)) if burnt else ("paint", DT.paint_uv(col))
    rust = UVBand(S.MATERIALS["rust"]["bands"]["rust"], 1.0)
    prof = [(y - 1.0, z + 0.86), (y + 1.0, z + 0.86), (y + 0.65, z + 1.38), (y - 0.6, z + 1.38)]        # (y, z) cabin
    prof_c = [(y - 1.0, z + 0.84), (y + 1.0, z + 0.84), (y + 0.65, z + 1.38), (y - 0.6, z + 1.38)]
    for k in ("geo", "fire", "view"):                       # collision follows the render (security D78 M1)
        kw = kw_for(k, mat, uv, "metal")
        L[k].box(x - 0.9, x + 0.9, y - 2.1, y + 2.1, z + 0.3, z + 0.84, **kw)
        L[k].extrude_x(prof_c, x - 0.8, x + 0.8, **kw)
    L["res2"].box(x - 0.9, x + 0.9, y - 2.1, y + 2.1, z + 0.3, z + 1.2, mat=mat, uv=uv, skip=("-z",))   # far LOD (perf D78 M5)
    r1 = L["res1"]
    r1.box(x - 0.9, x + 0.9, y - 2.1, y + 2.1, z + 0.3, z + 0.84, mat=mat, uv=uv)
    r1.extrude_x(prof, x - 0.8, x + 0.8, mat=mat, uv=uv)
    r0 = L["res0"]
    r0.box(x - 0.9, x + 0.9, y - 2.1, y + 2.1, z + 0.3, z + 0.62, mat=mat, uv=uv)                      # sills to waist
    r0.box(x - 0.88, x + 0.88, y - 2.08, y - 1.0, z + 0.62, z + 0.82, mat=mat, uv=uv, skip=("-z",))    # bonnet
    r0.box(x - 0.88, x + 0.88, y + 1.15, y + 2.08, z + 0.62, z + 0.8, mat=mat, uv=uv, skip=("-z",))    # boot
    r0.box(x - 0.9, x + 0.9, y - 1.0, y + 1.15, z + 0.62, z + 0.86, mat=mat, uv=uv, skip=("-z",))  # waist
    r0.extrude_x(prof, x - 0.8, x + 0.8, mat=mat, uv=uv)
    for (ya, yb, f) in ((y - 1.0, y - 0.6, (0, -0.8, 0.6)), (y + 1.0, y + 0.65, (0, 0.8, 0.6))):     # grimy screens, 6 mm proud
        q = [(x - 0.72, ya, z + 0.87), (x + 0.72, ya, z + 0.87), (x + 0.72, yb, z + 1.37), (x - 0.72, yb, z + 1.37)]
        q = [(p[0], p[1] + 0.006 * f[1], p[2] + 0.006 * f[2]) for p in q]
        r0.quad(q, f, "glassfar", UV_GLASS)
    for sx in (-1, 1):                                                                  # empty side windows (dark)
        wx = x + sx * 0.806
        for (y0, y1) in ((-0.85, 0.02), (0.08, 0.9)):
            q = [(wx, y + y0 + 0.05, z + 0.9), (wx, y + y1 - 0.05, z + 0.9), (wx, y + min(y1, 0.6) - 0.05, z + 1.32),
                 (wx, y + max(y0, -0.55) + 0.05, z + 1.32)]
            r0.quad(q if sx > 0 else q[::-1], (sx, 0, 0), "glassfar", UV_GLASS)
        for (y0, y1, z0, z1) in ((-1.9, -1.2, 0.34, 0.55), (0.4, 1.1, 0.33, 0.5)):                  # rust through the flanks
            fx = x + sx * 0.906
            q = [(fx, y + y0, z + z0), (fx, y + y1, z + z0), (fx, y + y1, z + z1), (fx, y + y0, z + z1)]
            r0.quad(q if sx > 0 else q[::-1], (sx, 0, 0), "rust", rust)
    for yb, s_ in ((y - 2.1, -1), (y + 2.1, 1)):                                        # bumpers
        r0.box(x - 0.92, x + 0.92, min(yb, yb + s_ * 0.06), max(yb, yb + s_ * 0.06), z + 0.3, z + 0.42, mat="metal", uv=DT.UV_STEEL)
    for wx in (x - 0.92, x + 0.84):                                                     # flat tyres, 2 cm proud (perf D78 M2)
        for wy in (y - 1.35, y + 1.35):
            r0.extrude_x([(wy - 0.3, z), (wy + 0.3, z), (wy + 0.24, z + 0.5), (wy - 0.24, z + 0.5)],
                         wx, wx + 0.08, mat="rubble", uv=UV_RUBBLE)


def cells_bars(L, P, l):
    use, fh, z0 = P.levels[l]
    if use == "police_ground":
        bars(L, "x", 2.5, 2.0, P.ix1, z0, z0 + fh - SLAB, openings=[(2.9, 3.7), (5.4, 6.2), (8.0, 8.8)])


def rail(L, x0, x1, y0, y1, z, h=1.05, glass=False):
    """Guard rail / balustrade: one collision box, steel top rail, glass infill or bars (Res0)."""
    for k in ("geo", "fire"):
        L[k].box(x0, x1, y0, y1, z, z + h, **({"mat": "pen_metal"} if k == "fire" else {}))
    for k in ("res0", "res1"):
        L[k].box(x0, x1, y0, y1, z + h - 0.06, z + h, mat="metal", uv=DT.UV_STEEL)
    along_x = (x1 - x0) >= (y1 - y0)
    if glass:
        c = (y0 + y1) / 2 if along_x else (x0 + x1) / 2
        pts = ([(x0, c, z + 0.05), (x1, c, z + 0.05), (x1, c, z + h - 0.06), (x0, c, z + h - 0.06)] if along_x else
               [(c, y0, z + 0.05), (c, y1, z + 0.05), (c, y1, z + h - 0.06), (c, y0, z + h - 0.06)])
        L["res0"].quad(pts, (0, 1, 0) if along_x else (1, 0, 0), "glass", UV_GLASS, double=True)
    else:
        L["res0"].box(x0, x1, y0, y1, z + 0.1, z + 0.16, mat="metal", uv=DT.UV_STEEL)
        L["res0"].box(x0, x1, y0, y1, z + 0.52, z + 0.57, mat="metal", uv=DT.UV_STEEL, skip=("-x", "+x") if along_x else ("-y", "+y"))
        n = int(((x1 - x0) if along_x else (y1 - y0)) / 1.2)
        for i in range(n + 1):
            a = (x0 if along_x else y0) + i * (((x1 - x0) if along_x else (y1 - y0)) / max(1, n))
            b = (a - 0.02, a + 0.02, y0, y1) if along_x else (x0, x1, a - 0.02, a + 0.02)
            L["res0"].box(*b, z, z + h - 0.06, mat="metal", uv=DT.UV_STEEL, skip=("-z", "+z"))


def level_features(L, P, l):
    """Atrium balustrades, car ramps with their spine wall and edge rails."""
    use, fh, z0 = P.levels[l]
    if P.atrium and l >= 1:
        x0, x1, y0, y1 = P.atrium
        t = 0.06
        g = P.state < 2                                                          # ruins: no glass left
        rail(L, x0 - t, x1 + t, y0 - t, y0, z0, glass=g)
        rail(L, x0 - t, x1 + t, y1, y1 + t, z0, glass=g)
        rail(L, x0 - t, x0, y0, y1, z0, glass=g)
        rail(L, x1, x1 + t, y0, y1, z0, glass=g)
    if P.escalators:
        escalators(L, P, l)
    if P.ramps and l < len(P.levels) - 1:                                       # spine between the ramp strips
        for k in ("res0", "res1", "geo", "view", "fire"):
            L[k].box(-9.0, 9.0, -0.15, 0.15, z0, z0 + fh - SLAB, **kw_for(k, "concrete", UV_CONC, "concrete"))
    for (k, x0, x1, y0, y1, d) in P.ramps:
        if k == l:                                                              # the ramp rising from this level
            za, zb = z0, P.levels[k + 1][2]
            xl, xh = (x0, x1) if d > 0 else (x1, x0)
            verts = [(xl, y0, za - 0.3), (xh, y0, zb - 0.3), (xh, y0, zb), (xl, y0, za),
                     (xl, y1, za - 0.3), (xh, y1, zb - 0.3), (xh, y1, zb), (xl, y1, za)]
            faces = [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
            for kk in ("res0", "res1", "geo", "view", "fire"):
                L[kk].solid(verts, faces, **kw_for(kk, "concrete", UV_CONC, "concrete"))
            L["road"].quad([(xl, y0, za), (xh, y0, zb), (xh, y1, zb), (xl, y1, za)], (0, 0, 1), "road_ext", UV_TILE)
            for i in range(1, 8):                                               # painted arrows / lane marks (Res0)
                a = xl + (xh - xl) * i / 8.0
                zz = za + (zb - za) * i / 8.0 + 0.01
                L["res0"].hquad(min(a, a + 0.5 * d), max(a, a + 0.5 * d), (y0 + y1) / 2 - 0.08, (y0 + y1) / 2 + 0.08, zz,
                                mat="paint", uv=DT.paint_uv("white"))
        if k + 1 == l:                                                          # rails round the hole on the upper deck
            xl = x0 if d > 0 else x1
            outer = (y0 - 0.08, y0) if y0 < 0 else (y1, y1 + 0.08)
            rail(L, x0, x1, outer[0], outer[1], z0)
            rail(L, xl - (0.08 if d > 0 else 0.0), xl + (0.0 if d > 0 else 0.08), y0, y1, z0)
            if l == len(P.levels) - 1:                                          # top deck: no spine, rail inside too
                inner = (y1, y1 + 0.08) if y0 < 0 else (y0 - 0.08, y0)
                rail(L, x0, x1, inner[0], inner[1], z0)


def forecourt(L, P):
    """Paved forecourt in front of the body: filling-station canopy and pumps, or cafe terrace."""
    fc = P.A.get("forecourt")
    if not fc:
        return
    hw, hd = P.hw, P.hd
    fx0, fx1, fy0 = P.fx0, P.fx1, P.fy0
    for k in ("res0", "res1", "res2", "geo", "view", "fire"):
        kw = kw_for(k, "concrete", UV_REVEAL, "concrete")
        L[k].box(fx0, fx1, fy0, -hd, -SLAB, 0.0, **kw)
    L["road"].hquad(fx0, fx1, fy0, -hd, 0.0, mat="road_ext", uv=UV_TILE)
    sk = ST["skirt"]
    for (x0, x1, y0, y1) in ((fx0, fx1, fy0, fy0 + WT), (fx0, fx0 + WT, fy0 + WT, -hd), (fx1 - WT, fx1, fy0 + WT, -hd)):
        for k in ("res0", "res1", "res2", "geo", "fire"):
            kw = kw_for(k, "stone", DT.stone_uv("granite"), "concrete")
            if k.startswith("res"):
                kw["skip"] = ("+z", "-z")
            L[k].box(x0, x1, y0, y1, -sk, -SLAB, **kw)
    use = P.levels[0][0]
    lit = P.state == 0
    if use == "gas":
        zc0, zc1 = 4.6, 5.2
        cy0, cy1 = fy0 + 0.4, -hd - 0.5
        for cxp in (-5.5, 5.5):                                                 # columns
            for cyp in (cy0 + 1.4, cy1 - 1.4):
                for k in ("res0", "res1", "res2", "geo", "view", "fire"):
                    L[k].box(cxp - 0.18, cxp + 0.18, cyp - 0.18, cyp + 0.18, 0.0, zc0, **kw_for(k, "metal", DT.UV_PAINT, "metal"))
        for k in ("res0", "res1", "res2", "geo", "view", "fire", "shadow"):     # canopy deck
            L[k].box(fx0 + 0.4, fx1 - 0.4, cy0, cy1, zc0, zc1, **kw_for(k, "metal", DT.UV_PAINT, "metal"))
        v0, v1 = S.SIGN_BAND["fuel"]
        for k in ("res0", "res1"):                                              # fascia sign, front
            L[k].quad([(-4.0, cy0 - 0.01, zc0 + 0.05), (4.0, cy0 - 0.01, zc0 + 0.05), (4.0, cy0 - 0.01, zc1 - 0.05),
                       (-4.0, cy0 - 0.01, zc1 - 0.05)], (0, -1, 0), "signs",
                      UVRect(0, 2, (-4.0, zc0 + 0.05), (4.0, zc1 - 0.05), (0, 1 - v1, 1, 1 - v0)))
        if lit:
            for gx in (-3.0, 0.0, 3.0):
                for gy in (cy0 + 1.5, cy1 - 1.5):
                    L["res0"].hquad(gx - 0.5, gx + 0.5, gy - 0.3, gy + 0.3, zc0 - 0.01, mat="lamp_cool", up=False)
        for ix in (-2.75, 2.75):                                                # pump islands
            iy0, iy1 = cy0 + 1.0, cy1 - 1.0
            for k in ("res0", "res1", "geo", "fire"):
                L[k].box(ix - 0.6, ix + 0.6, iy0, iy1, 0.0, 0.15, **kw_for(k, "stone", DT.stone_uv("granite"), "concrete"))
            L["road"].hquad(ix - 0.6, ix + 0.6, iy0, iy1, 0.15, mat="road_ext", uv=UV_TILE)
            for py in ((iy0 + iy1) / 2 - 0.9, (iy0 + iy1) / 2 + 0.9):
                for k in ("res0", "res1", "geo", "view", "fire"):
                    L[k].box(ix - 0.3, ix + 0.3, py - 0.25, py + 0.25, 0.15, 1.9, **kw_for(k, "paint", DT.paint_uv("white"), "metal"))
                L["res0"].box(ix - 0.31, ix + 0.31, py - 0.26, py + 0.26, 1.5, 1.75, mat="paint", uv=DT.paint_uv("terracotta"))
    elif use == "creche":
        playground(L, P)
    elif use == "cafe":
        yr = fy0 + 0.1
        gap = (P.entry[0] - 0.4, P.entry[1] + 0.4)
        for (a, b) in ((fx0 + 0.1, gap[0]), (gap[1], fx1 - 0.1)):               # low terrace fence, gap at the door
            rail(L, a, b, yr - 0.04, yr + 0.04, 0.0, h=0.9)
        for sx in (fx0 + 0.06, fx1 - 0.1):
            rail(L, sx, sx + 0.04, yr + 0.04, -hd - 0.1, 0.0, h=0.9)
        for tx in (fx0 + 1.6, fx0 + 3.8, fx1 - 3.8, fx1 - 1.6):
            ty = (fy0 - hd) / 2
            if abs(tx) < 1.3:
                continue
            table(L, tx - 0.4, tx + 0.4, ty - 0.4, ty + 0.4, 0.0)
            for cxo in (-0.7, 0.7):                                             # chairs
                piece(L, (tx + cxo - 0.2, tx + cxo + 0.2, ty - 0.2, ty + 0.2, 0.0, 0.45), "metal", DT.UV_ALU, pen="metal",
                      res1=False)
            if P.state < 2:                                                     # parasol (no collision)
                L["res0"].prism(tx, ty, 0.03, 0.75, 2.3, n=6, mat="metal", uv=DT.UV_STEEL)
                fab = "blue" if int(tx) % 2 else "beige"
                L["res0"].prism(tx, ty, 1.2, 2.3, 2.38, n=8, mat="fabric", uv=UV_FAB[fab])
                L["res1"].prism(tx, ty, 1.2, 2.3, 2.38, n=6, mat="fabric", uv=UV_FAB[fab])


def disc_x(lod, cx, y, cz, r, t, mat, uv, n=16):
    """Flat disc in the X-Z plane (clock face) from y to y - t."""
    ring = [(cx + r * math.cos(2 * math.pi * k / n), cz + r * math.sin(2 * math.pi * k / n)) for k in range(n)]
    verts = [(a, y, b) for a, b in ring] + [(a, y - t, b) for a, b in ring]
    faces = [tuple(range(n)), tuple(range(n, 2 * n))] + [(k, (k + 1) % n, n + (k + 1) % n, n + k) for k in range(n)]
    lod.solid(verts, faces, mat, uv)


def clock(L, cx, y, cz, r):
    disc_x(L["res0"], cx, y, cz, r + 0.08, 0.05, "stone", DT.stone_uv("limestone"))
    disc_x(L["res0"], cx, y - 0.05, cz, r, 0.02, "paint", DT.paint_uv("white"))
    disc_x(L["res1"], cx, y, cz, r + 0.08, 0.07, "paint", DT.paint_uv("white"))
    yy = y - 0.08
    L["res0"].box(cx - 0.03, cx + 0.03, yy - 0.02, yy, cz, cz + r * 0.8, mat="metal", uv=DT.UV_STEEL)
    L["res0"].box(cx, cx + r * 0.55, yy - 0.02, yy, cz - 0.03, cz + 0.03, mat="metal", uv=DT.UV_STEEL)


def landmark(L, P):
    """Civic dressing: pilasters + cornice (bank, town hall); pediment, clock, cupola (town hall)."""
    kind = P.A.get("landmark")
    if not kind:
        return
    if kind == "cinema":
        return marquee(L, P)
    if kind == "creche":
        return creche_mural(L, P)
    hw, hd, top = P.hw, P.hd, P.top
    lim = DT.stone_uv("limestone")
    for (b0, b1) in [(a, a) for a, _b in P.bays(-hw, hw)[1:]] + [(-hw + 0.25, 0), (hw - 0.25, 0)]:
        c = b0
        for k in ("res0", "res1"):
            L[k].box(c - 0.25, c + 0.25, -hd - 0.22, -hd, ST["plinth"], top - 0.6, mat="stone", uv=lim, skip=("+y",))
            L[k].box(c - 0.35, c + 0.35, -hd - 0.3, -hd, top - 0.95, top - 0.6, mat="stone", uv=lim, skip=("+y",))
    for k in ("res0", "res1", "res2"):                                          # cornice
        L[k].box(-hw - 0.15, hw + 0.15, -hd - 0.45, -hd, top - 0.6, top - 0.3, mat="stone", uv=lim, skip=("+y",))
    if kind != "townhall":
        return
    par = P.A.get("parapet", ST["parapet"])
    zb = top + par
    for k in ("res0", "res1", "res2", "geo", "view", "fire"):                   # pediment over the 3 middle bays
        y0 = -hd - 0.3 if k.startswith("res") else -hd
        L[k].extrude_y([(-5.0, zb), (5.0, zb), (0.0, zb + 2.2)], y0, -hd + 0.6, **kw_for(k, "stone", lim, "concrete"))
    clock(L, 0.0, -hd - 0.31, zb + 0.85, 0.55)
    cx, cy = 0.0, -hd * 0.3                                                      # cupola with copper dome
    copper = UVBand(S.MATERIALS["rust"]["bands"]["green"], 1.0)
    for k in ("res0", "res1", "res2", "geo", "view", "fire"):
        L[k].prism(cx, cy, 1.8, top, top + 3.0, n=8 if k == "res0" else 6, **kw_for(k, "stone", lim, "concrete"))
    for i, (r, h) in enumerate(((1.75, 0.6), (1.45, 0.5), (1.0, 0.45), (0.45, 0.4))):
        z = top + 3.0 + sum(hh for _r, hh in ((1.75, 0.6), (1.45, 0.5), (1.0, 0.45), (0.45, 0.4))[:i])
        L["res0"].prism(cx, cy, r, z, z + h, n=12, mat="rust", uv=copper)
        if i < 2:
            L["res1"].prism(cx, cy, r, z, z + h, n=8, mat="rust", uv=copper)
    L["res0"].prism(cx, cy, 0.05, top + 4.95, top + 5.8, n=6, mat="metal", uv=DT.UV_STEEL)
    for a in range(8):                                                          # cupola windows (dark)
        ang = 2 * math.pi * (a + 0.5) / 8
        px, py = cx + 1.82 * math.cos(ang), cy + 1.82 * math.sin(ang)
        L["res0"].box(px - 0.2, px + 0.2, py - 0.2, py + 0.2, top + 1.0, top + 2.3, mat="glassfar", uv=UV_GLASS,
                      skip=("-z", "+z"))                                  # caps sit inside the drum (D91: unseen)


def bell_tower(L, P):
    """Front bell tower (church): shaft above the nave front, belfry openings, clocks, spire."""
    if not P.A.get("tower"):
        return
    hd, top = P.hd, P.top
    tx, ty0, ty1 = 2.2, -hd, -hd + 4.4
    zt = top + 13.0
    lim = DT.stone_uv("limestone")
    mat, uv = wall(P, P.A["skin"][0])
    for k in ("res0", "res1", "res2", "geo", "view", "fire", "shadow"):
        pr = 0.04 if k.startswith("res") else 0.0              # proud of the gable (no coplanar faces); collision inside
        L[k].box(-tx, tx, ty0 - pr, ty1, top, zt, **kw_for(k, mat, uv, "masonry"))
    L["res3"].box(-tx, tx, ty0 - 0.04, ty1, top, zt, mat=mat, uv=uv, skip=("-z",))
    for k in ("res0", "res1", "res2"):
        L[k].box(-tx - 0.15, tx + 0.15, ty0 - 0.15, ty1 + 0.15, zt, zt + 0.35, mat="stone", uv=lim)
    zb0, zb1 = zt - 4.2, zt - 1.2
    for (axis, c, nrm) in (("x", ty0 - 0.01, (0, -1, 0)), ("x", ty1 + 0.01, (0, 1, 0)), ("y", -tx - 0.01, (-1, 0, 0)),
                           ("y", tx + 0.01, (1, 0, 0))):
        for a0, a1 in ((-1.4, -0.2), (0.2, 1.4)):                               # twin belfry openings
            pts = ([(a0, c, zb0), (a1, c, zb0), (a1, c, zb1), (a0, c, zb1)] if axis == "x" else
                   [(c, ty0 + 2.2 + a0, zb0), (c, ty0 + 2.2 + a1, zb0), (c, ty0 + 2.2 + a1, zb1), (c, ty0 + 2.2 + a0, zb1)])
            L["res0"].quad(pts, nrm, "glassfar", UV_GLASS, double=True)          # D91: opaque both ways
            L["res1"].quad(pts, nrm, "glassfar", UV_GLASS, double=True)
    clock(L, 0.0, ty0 - 0.06, zt - 6.0, 0.8)
    green = UVBand(S.MATERIALS["rust"]["bands"]["green"], 1.0)
    s = tx - 0.1
    spire = [(-s, ty0 + 0.1, zt + 0.35), (s, ty0 + 0.1, zt + 0.35), (s, ty1 - 0.1, zt + 0.35), (-s, ty1 - 0.1, zt + 0.35),
             (0.0, (ty0 + ty1) / 2, zt + 7.5)]
    sf = [(0, 1, 2, 3), (0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4)]
    for k in ("res0", "res1", "res2", "res3", "geo", "view", "fire", "shadow"):
        L[k].solid(spire, sf, **kw_for(k, "rust", green, "metal"))
    yc = (ty0 + ty1) / 2
    L["res0"].box(-0.04, 0.04, yc - 0.04, yc + 0.04, zt + 7.4, zt + 8.6, mat="metal", uv=DT.UV_STEEL)     # cross
    L["res0"].box(-0.35, 0.35, yc - 0.04, yc + 0.04, zt + 8.1, zt + 8.18, mat="metal", uv=DT.UV_STEEL)


def sawtooth(L, P, par):
    """North-light sawtooth roof: glazed vertical faces to +Y (north), zinc slopes, on the roof slab."""
    top = P.top
    zuv = UVBand(S.MATERIALS["rust"]["bands"]["grey"], 1.0)
    n = max(2, int(round((P.iy1 - P.iy0) / 6.0)))
    p = (P.iy1 - P.iy0) / n
    for i in range(n):
        ya, yb = P.iy0 + i * p, P.iy0 + (i + 1) * p
        prof = [(ya, top), (yb, top), (yb, top + 2.4)]
        nseg = max(1, int(round((P.ix1 - P.ix0) / 4.0)))                      # segments: a ruin drops only
        xs = [P.ix0 + j * (P.ix1 - P.ix0) / nseg for j in range(nseg + 1)]    # the bays over its collapse
        for xa, xb in zip(xs, xs[1:]):
            for k in ("res0", "res1", "res2", "geo", "view", "fire", "shadow"):
                L[k].extrude_x(prof, xa, xb, **kw_for(k, "rust", zuv, "metal"))
            for k in ("res0", "res1"):                                          # north glazing
                L[k].quad([(xa + 0.15, yb + 0.01, top + 0.25), (xb - 0.15, yb + 0.01, top + 0.25),
                           (xb - 0.15, yb + 0.01, top + 2.2), (xa + 0.15, yb + 0.01, top + 2.2)], (0, 1, 0),
                          "glass" if P.state == 0 else "glassfar", UV_GLASS,
                          double=P.state > 0)                           # D91: the opaque glassfar both ways (alpha glass: one side)
        L["res3"].extrude_x(prof, P.ix0, P.ix1, mat="rust", uv=zuv)


class UVSlope:
    """D96: roof covering at world scale along the slope (rooftile / roofslate sheets tile in U and V): U along the
    ridge, V down the slope (distance from the ridge line), `sheet` metres per UV unit."""

    def __init__(self, along, pitch_deg, sheet=4.0):
        self.ia, self.ic = (0, 1) if along == "x" else (1, 0)
        self.k = 1.0 / math.cos(math.radians(pitch_deg))
        self.sheet = sheet

    def __call__(self, pts, normal):
        return [(p[self.ia] / self.sheet, abs(p[self.ic]) * self.k / self.sheet) for p in pts]


def roof_cover(P):
    """Clay pantiles or slate (church / steep roofs, and a quarter of the rest, seeded per building type)."""
    if P.A.get("pitch", 32) >= 40 or h01(P.arch, "roofmat") < 0.25:
        return "roofslate"
    return "rooftile"


def pitched_roof(L, P, mat_uv):
    """Gable roof (D96 rebuild of the D59 zinc roof). Ridge along X (houses) or Y (church nave: P.A ridge "y").
    Collision (Geometry / View / Fire / Shadow) is unchanged: a slab per ~2.5 m segment inside the footprint so a
    ruin's collapse removes only the roof over the collapsed corner. The graphical LODs get the real roof: clay
    pantiles or slate mapped along the slope, 0.35 m eaves, and in Res0 a round ridge cap, fascia boards, half-round
    gutters with downpipes, barge boards on the gables and a capped chimney with two pots."""
    along = "y" if P.A.get("ridge") == "y" else "x"
    T = (lambda u, v, z: (u, v, z)) if along == "x" else (lambda u, v, z: (v, u, z))
    hl, hs = (P.hw, P.hd) if along == "x" else (P.hd, P.hw)          # half length along the ridge, half span
    top = P.top
    ov, th = 0.35, 0.16
    pitch = P.A.get("pitch", 32 if along == "x" else 45)
    rise = (hs + ov) * math.tan(math.radians(pitch))
    cover = roof_cover(P)
    ruv = UVSlope(along, pitch)
    n = max(1, int(round(2 * (hl + ov) / 2.5)))
    us = [-hl - ov + i * 2 * (hl + ov) / n for i in range(n + 1)]

    def ext(lod, prof, a, b, **kw):
        if along == "x":
            lod.extrude_x(prof, a, b, **kw)
        else:
            lod.extrude_y(prof, a, b, **kw)

    def box(lod, u0, u1, v0, v1, z0, z1, **kw):
        x0, y0, _ = T(u0, v0, 0)
        x1, y1, _ = T(u1, v1, 0)
        lod.box(min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1), z0, z1, **kw)

    def slope_z(v):                                              # underside of the covering above plan offset v
        return top - 0.05 + (hs + ov - abs(v)) * math.tan(math.radians(pitch))
    for s in (-1, 1):                                                       # the two slopes
        for a, b in zip(us, us[1:]):
            for k in ("res0", "res1", "res2", "geo", "view", "fire", "shadow"):
                vis = k.startswith("res")
                # eaves overhang is visual: collision stays inside the footprint (test_city)
                y_e = s * (hs + ov) if vis else s * hs
                z_e = top - 0.05 if vis else top - 0.05 + rise * ov / (hs + ov)
                prof = [(y_e, z_e), (0.0, top + rise - 0.05), (0.0, top + rise + th), (y_e, z_e + th + 0.05)]
                a2, b2 = (a, b) if vis else (max(a, -hl), min(b, hl))
                if b2 - a2 < 0.05:
                    continue
                kw = {"mat": cover, "uv": ruv} if vis else kw_for(k, cover, ruv, "metal")
                ext(L[k], prof, a2, b2, **kw)
    for su in (-1, 1):                                                      # gable walls
        u0, u1 = sorted((su * hl, su * (hl - WT)))
        for k in ("res0", "res1", "res2", "geo", "view", "fire"):
            kw = kw_for(k, mat_uv[0], mat_uv[1], "masonry")
            ext(L[k], [(-hs, top), (hs, top), (0.0, top + rise * hs / (hs + ov))], u0, u1, **kw)
    ext(L["res3"], [(-hs - ov, top), (hs + ov, top), (0.0, top + rise)], -hl - ov, hl + ov, mat=cover, uv=ruv)
    zr = top + rise + th - 0.05                                             # ridge line (top of the covering)
    # ridge cap: half-round tiles (smooth: 10-sided), in Res0 and Res1
    cap = [(0.13 * math.cos(math.pi * i / 10), zr - 0.03 + 0.12 * math.sin(math.pi * i / 10)) for i in range(11)]
    for k in ("res0", "res1"):
        ext(L[k], cap, -hl - ov, hl + ov, mat=cover, uv=ruv)
    r0 = L["res0"]
    fas = DT.paint_uv("white") if h01(P.arch, "fascia") < 0.5 else DT.paint_uv("terracotta")
    for s in (-1, 1):
        ve = s * (hs + ov)
        ze = top - 0.05                                                     # eaves line (lower edge of the covering)
        # fascia board under the covering edge
        box(r0, -hl - ov, hl + ov, ve - (0.035 if s > 0 else 0.0), ve + (0.0 if s > 0 else 0.035), ze - 0.2, ze + 0.12,
            mat="paint", uv=fas)
        # half-round gutter (smooth) on brackets, falling to the downpipes at both ends
        gc = ve + s * 0.09
        prof = [(gc + 0.075 * math.cos(math.pi + math.pi * i / 8), ze - 0.06 + 0.075 * math.sin(math.pi + math.pi * i / 8))
                for i in range(9)]
        ext(r0, prof, -hl - ov + 0.05, hl + ov - 0.05, mat="metal", uv=DT.UV_STEEL)
        for j in range(int((2 * (hl + ov)) / 0.9) + 1):                    # brackets
            u = -hl - ov + 0.2 + j * 0.9
            if u > hl + ov - 0.15:
                break
            box(r0, u - 0.015, u + 0.015, min(ve, gc + s * 0.08), max(ve, gc + s * 0.08), ze - 0.14, ze - 0.12,
                mat="metal", uv=DT.UV_STEEL)
        if P.state < 2 or s < 0:
            for su in (-1, 1):                                              # downpipes at the corners
                u = su * (hl - 0.18)
                x, y, _ = T(u, s * (hs + 0.07), 0)
                r0.prism(x, y, 0.045, 0.12, ze - 0.1, n=12, mat="metal", uv=DT.UV_STEEL)
                x2, y2, _ = T(u, gc, 0)
                xm, ym = (x + x2) / 2, (y + y2) / 2                          # swan neck under the gutter outlet
                r0.prism(xm, ym, 0.045, ze - 0.25, ze - 0.05, n=12, mat="metal", uv=DT.UV_STEEL)
                r0.prism(x, y, 0.06, 0.0, 0.14, n=12, mat="metal", uv=DT.UV_STEEL)          # shoe
    # barge boards along the gable edges of the covering
    for su in (-1, 1):
        ua, ub = sorted((su * (hl + ov), su * (hl + ov) + su * 0.035))
        for s in (-1, 1):
            ve = s * (hs + ov)
            pts = [(ve, top - 0.25), (0.0, top + rise - 0.25), (0.0, top + rise + th + 0.02), (ve, top - 0.05 + th + 0.05)]
            ext(r0, pts, ua, ub, mat="paint", uv=fas)
    if along == "y":                                                        # church nave: no chimney
        return rise
    # chimney through the back slope: brick stack, oversailing cap, two clay pots (smooth)
    cu, cv = hl * 0.45, hs * 0.3
    zc = top + rise + 0.9
    for k in ("res0", "res1"):
        box(L[k], cu - 0.3, cu + 0.3, cv, cv + 0.5, top, zc, mat="brick", uv=DT._brick_uv("bond"), skip=("-z",))
    box(r0, cu - 0.36, cu + 0.36, cv - 0.06, cv + 0.56, zc, zc + 0.08, mat="stone", uv=DT.stone_uv("limestone"))
    for du in (-0.13, 0.13):
        x, y, _ = T(cu + du, cv + 0.25, 0)
        r0.prism(x, y, 0.085, zc + 0.08, zc + 0.42, n=12, mat="brick", uv=DT._brick_uv("bond"))   # perf L: no extra section
        r0.prism(x, y, 0.1, zc + 0.36, zc + 0.44, n=12, mat="brick", uv=DT._brick_uv("bond"))
    return rise


def roof(L, P):
    hw, hd, top = P.hw, P.hd, P.top
    par = P.A.get("parapet", ST["parapet"])
    skin = P.A["skin"][0]
    if P.A.get("roof") == "pitched":
        rise = pitched_roof(L, P, wall(P, skin))
        L["res3"].box(-hw, hw, -hd, hd, -SLAB, top, mat=wall(P, skin)[0], uv=wall(P, skin)[1], skip=("-z", "+z"))
        roof_signs(L, P, skin)
        return rise
    ring = [(-hw, hw, -hd, -hd + WT), (-hw, hw, hd - WT, hd), (-hw, -hw + WT, -hd + WT, hd - WT), (hw - WT, hw, -hd + WT, hd - WT)]
    skin = P.A["skin"][0]
    mat, uv = wall(P, skin) if skin not in ("curtain",) else ("concrete", UV_CONC)
    for (x0, x1, y0, y1) in ring:
        for k in ("res0", "res1", "res2", "geo", "view", "fire", "shadow"):
            kw = kw_for(k, mat, uv, "concrete")
            if k.startswith("res"):
                kw["skip"] = ("-z",)
            L[k].box(x0, x1, y0, y1, top, top + par, **kw)
        for k in ("res0", "res1"):
            L[k].box(x0 - 0.03, x1 + 0.03, y0 - 0.03, y1 + 0.03, top + par, top + par + 0.05, mat="metal", uv=DT.UV_ALU,
                     skip=("-z",))
    if P.yard:                                                                     # parapet round the yard
        y = P.yard[1]
        for (x0, x1, y0, y1) in ((-y - WT, y + WT, -y - WT, -y), (-y - WT, y + WT, y, y + WT), (-y - WT, -y, -y, y), (y, y + WT, -y, y)):
            for k in ("res0", "res1", "res2", "geo", "view", "fire"):
                kw = kw_for(k, mat, uv, "concrete")
                if k.startswith("res"):
                    kw["skip"] = ("-z",)
                L[k].box(x0, x1, y0, y1, top, top + par, **kw)
    L["res3"].box(-hw, hw, -hd, hd, -SLAB, top + par, mat=mat if mat != "metal" else "metal", uv=uv, skip=("-z", "+z"))
    L["res3"].hquad(-hw, hw, -hd, hd, top, mat="concrete", uv=UV_CONC)
    cornice(L, P)
    if P.A.get("roof") == "sawtooth":
        sawtooth(L, P, par)
    Lt = lifted(L, top)
    g = P.A["group"]
    if not P.A.get("roof_gear", True):
        pass
    elif g in ("residential", "mixed"):
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
    skylight(L, P)
    roof_signs(L, P, skin)
    roof_clutter(L, P)


def cornice(L, P):
    """D96: moulded cornice at the roof line of masonry buildings (render / stone / brick skins): bed moulding, cove,
    corona and a weathered top, 24 cm proud - the strongest single cue that separates a real facade from a box.
    Res0 full profile, Res1 the corona only. Party walls get none; S / N runs reach over the corners."""
    skin = P.A["skin"][0]
    if S.CITY_SKINS[skin]["mat"] not in ("render", "stone", "brick") or P.A.get("roof") == "sawtooth":
        return
    z = P.top
    lim = DT.stone_uv("limestone")
    pieces = [[(0.0, z - 0.44), (-0.05, z - 0.44), (-0.05, z - 0.32), (0.0, z - 0.32)],           # bed moulding
              [(0.0, z - 0.32), (-0.05, z - 0.32), (-0.19, z - 0.13), (0.0, z - 0.13)],           # cove
              [(0.0, z - 0.13), (-0.24, z - 0.13), (-0.24, z + 0.0), (0.0, z + 0.0)],             # corona
              [(0.0, z + 0.0), (-0.24, z + 0.0), (-0.17, z + 0.07), (0.0, z + 0.07)]]             # weathered top
    for key in ("S", "N", "W", "E"):
        if key in P.A.get("blank", ()):
            continue
        sd = FSide(P, key)
        e = 0.24 if sd.axis == "x" else 0.0
        if sd.axis == "y":                                                   # reach the S / N corner pieces
            a0, a1 = sd.a0 - WT, sd.a1 + WT
        else:
            a0, a1 = sd.a0 - e, sd.a1 + e
        for pr in pieces:
            side_profile(L["res0"], sd, a0, a1, pr, mat="stone", uv=lim)
        side_profile(L["res1"], sd, a0, a1, pieces[2], mat="stone", uv=lim)
        side_profile(L["fire"], sd, a0, a1, pieces[2], mat="pen_concrete")    # D96 sec L1: the corona stops rounds


def roof_occupied(P):
    """Plan rects already used on a flat roof (gear placed by roof(), the stair bulkhead, atrium, yard)."""
    hw, hd = P.hw, P.hd
    occ = []
    if P.A["group"] in ("residential", "mixed"):
        occ += [(x - 0.4, x + 0.4, y - 0.3, y + 0.3) for (x, y) in ((-hw * 0.6, hd * 0.55), (hw * 0.5, hd * 0.55))]
        occ.append((-hw * 0.2 - 0.5, -hw * 0.2 + 0.5, -hd * 0.3 - 0.5, -hd * 0.3 + 0.5))
    else:
        occ.append((-hw * 0.6, -hw * 0.6 + 2.2, -1.0, 1.0))
        if P.W > 15:
            occ.append((hw * 0.3, hw * 0.3 + 2.2, -hd * 0.6, -hd * 0.6 + 1.8))
        occ.append((hw - 1.5, hw - 0.5, hd - 1.5, hd - 0.5))
    if P.stair:
        x0, x1, y0, y1 = P.stair
        occ.append((x0, x1, y0 + 1.2, y1))
    if P.A.get("skylight") and P.atrium:
        x0, x1, y0, y1 = P.atrium
        occ.append((x0 - 0.3, x1 + 0.3, y0 - 0.3, y1 + 0.3))
    if P.yard:
        x0, x1, y0, y1 = P.yard
        occ.append((x0 - WT, x1 + WT, y0 - WT, y1 + WT))
    return occ


def roof_clutter(L, P):
    """D89 flat-roof clutter (the roofs are seen from the towers): vent pipes with caps, mushroom vents, a conduit
    run from the gear to the parapet, and on some residential roofs a panel water tank on a steel frame. Render-only and
    low (<= 0.9 m, pipes <= 0.07 m radius) except the tank, which collides as one solid box from the roof up (nothing to
    crawl under) and stays >= 1 m from parapets and other gear (no wedge slots, test_city)."""
    if P.A.get("roof") in ("pitched", "sawtooth") or not P.A.get("roof_gear", True) or P.state == 2:
        return
    hw, hd, top = P.hw, P.hd, P.top
    occ = roof_occupied(P)
    m = WT + 0.9                                                               # clear of the parapet

    def free(x0, x1, y0, y1, margin):
        if x0 < -hw + m or x1 > hw - m or y0 < -hd + m or y1 > hd - m:
            return False
        return not any(x0 - margin < b[1] and b[0] < x1 + margin and y0 - margin < b[3] and b[2] < y1 + margin for b in occ)

    def spot(tag, w, d, margin, tries=24):
        for t in range(tries):
            x = -hw + m + w / 2 + (2 * hw - 2 * m - w) * h01(P.arch, tag, "x", t)
            y = -hd + m + d / 2 + (2 * hd - 2 * m - d) * h01(P.arch, tag, "y", t)
            r = (x - w / 2, x + w / 2, y - d / 2, y + d / 2)
            if free(*r, margin):
                occ.append(r)
                return x, y
        return None

    r0, r1 = L["res0"], L["res1"]                                            # seeded per archetype: all states match
    if P.A["group"] in ("residential", "mixed") and P.W > 10 and h01(P.arch, "tank") < 0.5:
        s = spot("tank", 1.8, 1.4, 1.0)
        if s:
            x, y = s
            x0, x1, y0, y1 = x - 0.8, x + 0.8, y - 0.6, y + 0.6
            for k in ("res0", "res1"):
                L[k].box(x0, x1, y0, y1, top + 0.3, top + 1.5, mat="metal", uv=DT.UV_PAINT, skip=("-z",))
            for k in ("geo", "view", "fire", "shadow"):                          # one solid incl. the frame: no crawl space
                L[k].box(x0, x1, y0, y1, top, top + 1.5, **(kw_for(k, "metal", DT.UV_PAINT, "metal") if k != "shadow" else {}))
            # steel skirt round the frame (sec review L: open legs would show a gap the solid collision blocks)
            r0.box(x0 + 0.02, x1 - 0.02, y0 + 0.02, y1 - 0.02, top, top + 0.3, mat="metal", uv=DT.UV_STEEL, skip=("-z", "+z"))
            r0.box(x - 0.3, x + 0.3, y - 0.3, y + 0.3, top + 1.5, top + 1.56, mat="metal", uv=DT.UV_STEEL)   # manhole lid
            occ.append((x0, x1, y0, y1))
    n = 2 + min(4, int(P.W * P.D / 120))
    for i in range(n):                                                         # vent pipes with rain caps
        s = spot(("vent", i), 0.3, 0.3, 0.4)
        if not s:
            continue
        x, y = s
        h = 0.5 + 0.35 * h01(P.arch, "vh", i)
        r0.prism(x, y, 0.06, top, top + h, n=8, mat="metal", uv=DT.UV_STEEL)
        r0.prism(x, y, 0.11, top + h, top + h + 0.05, n=8, mat="metal", uv=DT.UV_PAINT)
        r1.prism(x, y, 0.06, top, top + h, n=4, mat="metal", uv=DT.UV_STEEL)
    for i in range(1 + int(h01(P.arch, "mush") * 2)):                          # mushroom vents
        s = spot(("mush", i), 0.5, 0.5, 0.4)
        if s:
            x, y = s
            r0.prism(x, y, 0.1, top, top + 0.35, n=8, mat="metal", uv=DT.UV_ALU)
            r0.prism(x, y, 0.22, top + 0.35, top + 0.45, n=8, mat="metal", uv=DT.UV_ALU)
    g = occ[0] if P.A["group"] not in ("residential", "mixed") else occ[2]   # conduit: gear / mast -> S parapet
    gx, gy = (g[0] + g[1]) / 2, g[2]
    ye = -hd + WT
    if gy - ye > 0.5 and not any(b is not g and b[0] - 0.1 < gx < b[1] + 0.1 and ye < b[3] and b[2] < gy for b in occ):
        r0.box(gx - 0.04, gx + 0.04, ye, gy, top + 0.1, top + 0.16, mat="metal", uv=DT.UV_PAINT, skip=("-z",))
        for j in range(int((gy - ye) / 1.2)):                                  # sleepers
            yy = ye + 0.4 + j * 1.2
            r0.box(gx - 0.12, gx + 0.12, yy, yy + 0.1, top, top + 0.1, mat="concrete", uv=UV_REVEAL, skip=("-z",))


def roof_signs(L, P, skin):
    hw, hd = P.hw, P.hd
    if P.stair and P.A.get("roof") != "pitched":                                     # stair bulkhead
        x0, x1, y0, y1 = P.stair
        top = P.top
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
        wsg = P.A.get("sign_w", min(P.W * 0.5, 6.0))
        hs = 0.5 * max(1.0, wsg / 6.0) if P.A.get("sign_w") else 0.5             # big venue signs scale up
        if P.A.get("sign_w") and P.A.get("ground") == "shopfront":
            zs0 = P.levels[0][1] - SLAB + 0.15                                     # above the shopfront, on the parapet band
        for k in ("res0", "res1"):
            L[k].box(-wsg / 2, wsg / 2, y, y + 0.08, zs0, zs0 + hs, mat="metal", uv=DT.UV_PAINT, skip=("+y",))
            L[k].quad([(-wsg / 2, y - 0.003, zs0), (wsg / 2, y - 0.003, zs0), (wsg / 2, y - 0.003, zs0 + hs),
                       (-wsg / 2, y - 0.003, zs0 + hs)], (0, -1, 0), S.SIGN_MAT[sign],
                      UVRect(0, 2, (-wsg / 2, zs0), (wsg / 2, zs0 + hs), (0, 1 - v1, 1, 1 - v0)))
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
            L["res1"].solid(verts, [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)],
                            mat="fabric", uv=UV_FAB[fab])
            # D96 Res0: a real folding-arm awning - roller cassette on the wall, canvas sagging slightly between
            # the cassette and the front bar, hanging valance, two steel arms with elbow joints
            r0 = L["res0"]
            xa, xb = a0 + 0.05, a1 - 0.05
            prof = [(-hd - 0.02, zt + 0.02), (-hd - 0.47, zt - 0.22), (-hd - 0.94, zt - 0.43), (-hd - 1.4, zt - 0.6)]
            sag = [0.0, -0.035, -0.035, 0.0]
            pts = [(y, z + s_) for (y, z), s_ in zip(prof, sag)]
            for (y0_, z0_), (y1_, z1_) in zip(pts, pts[1:]):
                r0.quad([(xa, y0_, z0_), (xb, y0_, z0_), (xb, y1_, z1_), (xa, y1_, z1_)], (0, -0.4, 1), mat="fabric",
                        uv=UV_FAB[fab], double=True)
            yv, zv = pts[-1]
            r0.quad([(xa, yv, zv), (xb, yv, zv), (xb, yv, zv - 0.22), (xa, yv, zv - 0.22)], (0, -1, 0), mat="fabric",
                    uv=UV_FAB[fab], double=True)                                # valance
            r0.extrude_x([(-hd - 0.02 + 0.075 * math.cos(2 * math.pi * i / 12), zt + 0.06 + 0.075 * math.sin(2 * math.pi * i / 12))
                          for i in range(12)], xa - 0.03, xb + 0.03, mat="metal", uv=DT.UV_PAINT)    # cassette (smooth)
            r0.extrude_x([(yv + 0.025 * math.cos(2 * math.pi * i / 10), zv - 0.01 + 0.025 * math.sin(2 * math.pi * i / 10))
                          for i in range(10)], xa, xb, mat="metal", uv=DT.UV_PAINT)                 # front bar
            for xx in (xa + 0.12, xb - 0.12):                                                     # arms
                ym, zm = -hd - 0.75, zt - 0.62
                for (p_, q_) in (((xx, -hd - 0.05, zt - 0.55), (xx, ym, zm)), ((xx, ym, zm), (xx, yv + 0.05, zv - 0.03))):
                    tube(r0, p_, q_, 0.018, "metal", DT.UV_PAINT)


# ================================================================== DayZ ambiance (D59)
def grime_uv(sd, a0, a1, z0, z1, band, tile=4.0):
    """UVRect onto one band of decal_grime: tiles every `tile` m along the side, the band's
    height stretched over z0..z1 (bottom of the quad = bottom of the band)."""
    v0, v1 = DT.grime_v(band)                                                # D92: shared 8-band layout
    return UVRect(sd.uvax(), 2, (a0, z0), (a1, z1), (a0 / tile, v0, a1 / tile, v1))


def veg_card(L, pts, facing, cell, lods=("res0",)):
    """Alpha-tested vegetation card (double-sided) mapped onto one atlas cell."""
    u0, v0, u1, v1 = S.veg_uv(cell)
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    ax = 0 if (max(xs) - min(xs)) >= (max(ys) - min(ys)) else 1
    a = [p[ax] for p in pts]
    z = [p[2] for p in pts]
    uv = UVRect(ax, 2, (min(a), min(z)), (max(a), max(z)), (u0 + 0.004, v0 + 0.004, u1 - 0.004, v1 - 0.004))
    if pts[1][ax] < pts[0][ax]:                                          # keep the plant upright on mirrored cards
        uv = UVRect(ax, 2, (max(a), min(z)), (min(a), max(z)), (u0 + 0.004, v0 + 0.004, u1 - 0.004, v1 - 0.004))
    for k in lods:
        L[k].quad(pts, facing, "vegetation", uv, double=True)


def plant_tuft(L, x, y, z, w, h, cell, key, lods=("res0",)):
    """Two crossed vegetation cards (a tuft / bush seen from any side)."""
    a = h01("tuft", key) * math.pi
    dx, dy = math.cos(a) * w / 2, math.sin(a) * w / 2
    veg_card(L, [(x - dx, y - dy, z), (x + dx, y + dy, z), (x + dx, y + dy, z + h), (x - dx, y - dy, z + h)],
             (-dy, dx, 0), cell, lods)
    veg_card(L, [(x + dy, y - dx, z), (x - dy, y + dx, z), (x - dy, y + dx, z + h), (x + dy, y - dx, z + h)],
             (-dx, -dy, 0), cell, lods)


def sapling(L, x, y, z, h, key):
    """Young birch growing out of rubble / a cracked roof (ruins): thin trunk + crown cards."""
    for k, n in (("res0", 6), ("res1", 4)):
        L[k].prism(x, y, 0.05, z, z + h * 0.7, n=n, mat="vegetation", uv=UVRect(0, 2, (x - 0.05, z), (x + 0.05, z + h * 0.7),
                   S.veg_uv("bark")))
    plant_tuft(L, x, y, z + h * 0.35, h * 0.7, h * 0.65, "birch_crown", key + ("crown",), lods=("res0", "res1"))


def dress(L, P):
    """Weathering and overgrowth of one building (seeded per class): rising damp along the base,
    run-off under the roofline, weeds at the walls, ivy, downpipes, ground-floor window bars,
    weeds and saplings on damaged / ruined roofs. All visual (Res0 / Res1): no collision."""
    A, st = P.A, P.state
    W = S.WEATHER
    skin = A["skin"][0]
    par = A.get("parapet", ST["parapet"]) if A.get("roof") != "pitched" else 0.0
    sides = ["S", "N", "W", "E"] + (["iS", "iN", "iW", "iE"] if P.yard else [])
    for key in sides:
        sd = FSide(P, key)
        blank = key in A.get("blank", ())
        shop = A.get("ground") == "shopfront" and key in A.get("shop_sides", ())
        a0, a1 = sd.a0, sd.a1
        # rising damp (behind shop glass there is no wall: skip those sides)
        if not shop and skin != "curtain":
            # D96: broken at the front door (the damp band no longer runs over the door leaf)
            segs = [(a0, a1)]
            if key == "S" and P.door is not None:
                segs = [(a0, P.door[0] - 0.2), (P.door[1] + 0.2, a1)]
            zt = 1.1 + 0.4 * h01(P.name, "damp", key)
            for (sa, sb) in segs:
                if sb - sa < 0.3:
                    continue
                for k in ("res0", "res1"):
                    sd.quad(L[k], sa, sb, -0.3, zt, -0.045, mat="decal_grime", uv=grime_uv(sd, sa, sb, -0.3, 1.5, "damp"))
        # run-off under the roofline / parapet coping
        if skin != "curtain":
            ztop = P.top + par
            rh = min(2.6, 0.45 * ztop)
            for k in ("res0", "res1"):
                sd.quad(L[k], a0, a1, ztop - rh, ztop - 0.02, -0.006, mat="decal_grime",
                        uv=grime_uv(sd, a0, a1, ztop - rh, ztop - 0.02, "runoff"))
        # weeds at the base of the wall (not on party walls)
        if not blank:
            a = a0 + 0.3
            i = 0
            while a < a1 - 0.6:
                w = 0.9 + 0.9 * h01(P.name, "wd", key, i)
                if h01(P.name, "weed", key, i) < W["weeds"][st] and not (key == "S" and P.entry[0] - 0.4 < a + w and a < P.entry[1] + 0.4):
                    cell = ("grass", "weeds", "dry_grass", "burdock")[int(h01(P.name, "wc", key, i) * 4)]
                    h = (0.55 + 0.65 * h01(P.name, "wh", key, i)) * (1.0 if st < 2 else 1.35)
                    pts = sd.rect(a, min(a1, a + w), -0.3, h, -0.16)
                    veg_card(L, pts, sd.out, cell)
                    if h01(P.name, "wd2", key, i) < 0.6:                      # a lower second row in front
                        b = a + 0.3 * w
                        veg_card(L, sd.rect(b, min(a1, b + 0.8 * w), -0.3, 0.45 * h, -0.42), sd.out, "grass")
                a += w + 0.2 + 0.9 * h01(P.name, "wg", key, i)
                i += 1
        # ivy on the wall (party walls too: they show above the neighbours)
        if h01(P.name, "ivy", key) < W["ivy"][st] and skin not in ("curtain", "open"):
            iw = min(a1 - a0 - 0.4, 2.0 + 4.0 * h01(P.name, "ivw", key))
            ia = a0 + 0.2 + (a1 - a0 - 0.4 - iw) * h01(P.name, "iva", key)
            ih = min(P.top, 3.0 + (P.top - 3.0) * h01(P.name, "ivh", key))
            cell = "ivy_dark" if h01(P.name, "ivc", key) < 0.5 else "ivy"
            for k in ("res0", "res1"):
                sd.quad(L[k], ia, ia + iw, -0.2, ih, -0.07, mat="vegetation",           # D96: in front of sills / lintels
                        uv=UVRect(sd.uvax(), 2, (ia, -0.2), (ia + iw, ih),
                                  (S.veg_uv(cell)[0] + 0.004, S.veg_uv(cell)[1] + 0.004,
                                   S.veg_uv(cell)[2] - 0.004, S.veg_uv(cell)[3] - 0.004)))
            if par:                                                          # strands over the parapet
                hw_ = min(iw, 3.0)
                sd.quad(L["res0"], ia, ia + hw_, P.top + par - 1.6, P.top + par, -0.075, mat="vegetation",
                        uv=UVRect(sd.uvax(), 2, (ia, P.top + par - 1.6), (ia + hw_, P.top + par), S.veg_uv("ivy_hang")))
        # downpipes at the side ends (masonry, flat roofs; not on party walls)
        if key in ("S", "N") and skin not in ("curtain", "metal", "open") and not A.get("roof") and P.W > 5:
            for j, ax in enumerate((a0 + 0.3, a1 - 0.3)):
                if (key == "S" and P.entry[0] - 0.6 < ax < P.entry[1] + 0.6) or h01(P.name, "pipe", key, j) < 0.25:
                    continue
                pm, pu = "metal", DT.UV_PAINT                                    # painted steel (no extra section)
                for k in ("res0", "res1"):
                    sd.box(L[k], ax - 0.05, ax + 0.05, 0.15, P.top + par - 0.25, -0.13, -0.03, mat=pm, uv=pu, skip=("-z",))
                sd.box(L["res0"], ax - 0.12, ax + 0.12, P.top + par - 0.45, P.top + par - 0.2, -0.2, -0.02, mat=pm, uv=pu)   # hopper
                sd.box(L["res0"], ax - 0.07, ax + 0.07, 0.0, 0.15, -0.3, -0.03, mat=pm, uv=pu)                                  # shoe
    # ground-floor window bars on residential buildings (intact / damaged)
    if st < 2 and A["group"] in ("residential", "mixed") and skin not in ("curtain", "metal", "open"):
        SK = dict(S.CITY_SKINS[skin])
        if A.get("win"):
            SK["ww"], SK["sill"], SK["head"] = A["win"]
        fh0 = P.levels[0][1]
        for key in ("S", "N", "W", "E"):
            if key in A.get("blank", ()) or (A.get("ground") == "shopfront" and key in A.get("shop_sides", ())):
                continue
            sd = FSide(P, key)
            for i, (b0, b1) in enumerate(P.bays(sd.a0, sd.a1)):
                if (key == "S" and P.door is not None and b0 <= P.door[0] <= b1) or h01(P.name, "bars", key, i) >= W["bars"]:
                    continue
                ww = min(SK["ww"], b1 - b0 - 0.5)
                c = (b0 + b1) / 2
                s0, s1 = SK["sill"], min(SK["head"], fh0 - SLAB - 0.35)
                for j in range(5):
                    xb = c - ww / 2 + 0.1 + j * (ww - 0.2) / 4
                    sd.box(L["res0"], xb - 0.012, xb + 0.012, s0, s1, -0.05, -0.026, mat="metal",
                           uv=DT.UV_STEEL, skip=("-z", "+z"))
                for zz in (s0 + 0.1, s1 - 0.1):
                    sd.box(L["res0"], c - ww / 2, c + ww / 2, zz - 0.015, zz + 0.015, -0.05, -0.026, mat="metal",
                           uv=DT.UV_STEEL)
    # roofs: moss on the coping, weeds (damaged), weeds + saplings (ruined)
    if A.get("roof") != "pitched" and par:
        for i in range(2 if st == 0 else 6):
            x = -P.hw + 1.0 + (P.W - 2.0) * h01(P.name, "rw", i)
            y = (P.hd - 0.9) * (1 if h01(P.name, "ry", i) < 0.5 else -1)
            if st == 0 and h01(P.name, "rw0", i) < 0.5:
                continue
            plant_tuft(L, x, y, P.top, 0.9, 0.5 + 0.3 * st, ("grass", "dry_grass", "weeds")[i % 3], (P.name, "roof", i))
    if st == 2:
        r = P.ruin.region
        zf = P.levels[P.kc - 1][2] if P.kc - 1 < len(P.levels) else 0.0
        cx = (max(r[0], P.ix0 + 0.4) + min(r[1], P.ix1 - 0.4)) / 2
        cy = (max(r[2], P.iy0 + 0.4) + min(r[3], P.iy1 - 0.4)) / 2
        sapling(L, cx + 0.3, cy - 0.2, zf + (0.6 if (P.ix1 - P.ix0) * (P.iy1 - P.iy0) < 30.0 else 1.0),
                2.0 + 1.5 * h01(P.name, "sap"), (P.name, "sap"))
        for i in range(4):                                                    # weeds over the rubble
            plant_tuft(L, cx - 1.2 + 2.4 * h01(P.name, "rbx", i), cy - 1.0 + 2.0 * h01(P.name, "rby", i), zf + 0.2,
                       0.8, 0.6, ("weeds", "bramble", "grass", "dry_grass")[i], (P.name, "rb", i))


def window_streak(L, P, sd, w0, w1, s0, key):
    """Dirt streak under a window sill (more on damaged / ruined buildings)."""
    if h01(P.name, "wst", sd.key, *key) < S.WEATHER["window_streaks"][P.state] and s0 > 1.2:
        ln = min(s0 - 0.3, 0.9 + 0.9 * h01(P.name, "wsl", sd.key, *key))
        v0, v1 = DT.grime_v("streak")                                            # band "streak", fitted to the quad (D92 layout)
        sd.quad(L["res0"], w0 - 0.05, w1 + 0.05, s0 - ln, s0 - 0.07, DECAL_D["streak"], mat="decal_grime",
                uv=UVRect(sd.uvax(), 2, (w0 - 0.05, s0 - ln), (w1 + 0.05, s0 - 0.07), (0.0, v0, 1.0, v1)))


def ruin_extras(L, P):
    """Damaged / ruined dressing: cracks and graffiti on the front, rubble below the collapse."""
    if P.state >= 1:
        sd = FSide(P, "S")
        placed = []
        for i in range(3 if P.state == 1 else 6):
            for t in range(6):                             # D96: cracks never overlap each other (same depth: z-fight)
                a = -P.hw + 0.8 + (P.W - 1.6) * h01(P.name, "crack", i, t)
                lvl = int(h01(P.name, "crackl", i, t) * len(P.levels))
                z = P.levels[lvl][2] + 0.4 + 1.6 * h01(P.name, "crackz", i, t)
                if not any(abs(a - pa) < 1.8 and abs(z - pz) < 1.8 for pa, pz in placed):
                    break
            else:
                continue
            placed.append((a, z))
            sd.quad(L["res0"], a - 0.9, a + 0.9, z, z + 1.8, DECAL_D["cracks"], mat="decal_cracks",
                    uv=UVRect(0, 2, (a - 0.9, z), (a + 0.9, z + 1.8), (0, 0, 1, 1)))
        a = P.entry[1] + 0.35 if P.entry[1] + 1.4 < P.hw else P.entry[0] - 1.35
        sd.quad(L["res0"], a, a + 1.0, 0.0, 0.85, DECAL_D["graffiti"], mat="decal_graffiti",   # street level, under the sills
                uv=UVRect(0, 2, (a, 0.0), (a + 1.0, 0.85), (0, 0, 1, 1)))
    if P.state == 2:
        r = P.ruin.region
        zf = P.levels[P.kc - 1][2] if P.kc - 1 < len(P.levels) else 0.0
        x0, x1 = max(r[0], P.ix0 + 0.4), min(r[1], P.ix1 - 0.4)
        y0, y1 = max(r[2], P.iy0 + 0.4), min(r[3], P.iy1 - 0.4)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        small = (P.ix1 - P.ix0) * (P.iy1 - P.iy0) < 30.0
        rx = min(2.0, (x1 - x0) / 2.6, cx - P.ix0 - 0.15, P.ix1 - cx - 0.15)          # stays inside the walls
        ry = min(1.8, (y1 - y0) / 2.6, cy - P.iy0 - 0.15, P.iy1 - cy - 0.15)
        rubble_pile(L, cx, cy, zf, rx, ry, 0.6 if small else 1.1, (P.name, "main"))
        if not small:
            rubble_pile(L, x0 + 0.6, y0 + 0.6, zf, 0.45, 0.45, 0.5, (P.name, "side"))
        # charred interior walls above the rubble (soot), broken slab edge (rebar) at the cut
        for k in range(4):
            xr = x0 + (x1 - x0) * h01(P.name, "rebar", k)
            zr = P.levels[P.kc][2] if P.kc < len(P.levels) else P.top
            L["res0"].box(xr - 0.01, xr + 0.01, r[3] - 0.01, r[3] + 0.6, zr - 0.2, zr - 0.18, mat="rust",
                          uv=UVBand(S.MATERIALS["rust"]["bands"]["rust"], 1.0))


# ================================================================== rubble lots (kit, D57)
LOT = 12.0
LOT_SKINS = {"A": ("brick", None), "B": ("render", "ochre"), "C": ("panel", None), "D": ("stone", None)}


def build_rubble_lot(v):
    """12 x 12 m collapsed lot: broken ground slab, jagged wall fragments of the lost building
    (same ruin layer with the whole lot as collapse zone), rubble mounds you can climb
    (Geometry + Roadway), loose chunks, charred beams, rebar. No loot, no door."""
    name = "City_RubbleLot_%s" % v
    hw = LOT / 2
    ruin = Ruin(name, 2, (-hw - 1, hw + 1, -hw - 1, hw + 1, 0.0))
    L = city_lods(ruin)
    A = {"skin": LOT_SKINS[v]}

    class _P:                                          # minimal plan for skin_uv / wall
        pass
    P = _P()
    P.A = A
    mat, uv = wall(P, LOT_SKINS[v][0])
    for k in ("res0", "res1", "res2", "geo", "view", "fire"):                  # cracked slab remnant
        kw = kw_for(k, "concrete", UV_REVEAL, "concrete")
        for (x0, x1, y0, y1) in ((-hw + 0.5, -0.4, -hw + 0.5, hw - 0.5), (0.4, hw - 0.5, -hw + 0.5, 1.0)):
            L[k].lod.box(x0, x1, y0, y1, -0.3, 0.0 + 0.002 * (x0 > 0), **kw)
    for (x0, x1, y0, y1) in ((-hw + 0.5, -0.4, -hw + 0.5, hw - 0.5), (0.4, hw - 0.5, -hw + 0.5, 1.0)):
        L["road"].lod.hquad(x0, x1, y0, y1, 0.002 * (x0 > 0), mat="road_ext", uv=UV_TILE)
    # wall fragments: L-shaped remains along two sides, cut jagged by the ruin layer
    frags = [("x", hw - 0.8, -hw + 0.5, hw - 0.5), ("y", -hw + 0.8, -hw + 0.5, hw - 2.0)]
    if v in ("B", "D"):
        frags.append(("x", -hw + 0.8, -2.0, hw - 0.5))
    for axis, c, a0, a1 in frags:
        for k in ("res0", "res1", "res2", "geo", "view", "fire", "shadow"):
            kw = kw_for(k, mat, uv, "masonry")
            seg = 1.2
            a = a0
            while a < a1 - 1e-6:
                b = min(a1, a + seg)
                if axis == "x":
                    L[k].box(a, b, c - 0.15, c + 0.15, 0.0, 4.0, **kw)
                else:
                    L[k].box(c - 0.15, c + 0.15, a, b, 0.0, 4.0, **kw)
                a = b
    # mounds + chunks + charred beams + rebar
    mounds = {"A": [(1.5, -1.5, 2.6, 2.0, 1.4), (-3.0, 3.0, 1.6, 1.4, 0.8)],
              "B": [(-1.0, -1.0, 2.8, 2.4, 1.6)], "C": [(2.0, 1.0, 2.2, 2.6, 1.2), (-2.5, -3.0, 1.5, 1.2, 0.7)],
              "D": [(0.0, 0.5, 3.0, 2.2, 1.8), (3.5, -3.5, 1.2, 1.2, 0.6)]}[v]
    U = {k: x.lod for k, x in L.items()}              # mounds are not subject to the wall cut
    for i, (x, y, rx, ry, h) in enumerate(mounds):
        rubble_pile(U, x, y, 0.0, rx, ry, h, (name, i))
    for i in range(5):
        x = -hw + 1.5 + (LOT - 3.0) * h01(name, "beam", i)
        y = -hw + 1.5 + (LOT - 3.0) * h01(name, "beamy", i)
        ln = 1.5 + 2.0 * h01(name, "beaml", i)
        L["res0"].lod.box(x, x + ln, y, y + 0.2, 0.0, 0.2, mat="wood", uv=UVBand(S.MATERIALS["rust"]["bands"]["burnt"], 1.0))
    for i in range(8):
        x = -hw + 1.0 + (LOT - 2.0) * h01(name, "rebar", i)
        L["res0"].lod.box(x, x + 0.02, hw - 0.95, hw - 0.65, 0.3, 1.6 + h01(name, "rh", i), mat="rust",
                          uv=UVBand(S.MATERIALS["rust"]["bands"]["rust"], 1.0))
    for axis, c, a0, a1 in frags:                                             # far LOD: jagged remains
        if axis == "x":
            L["res3"].box(a0, a1, c - 0.15, c + 0.15, 0.0, 4.0, mat=mat, uv=uv, skip=("-z",))
        else:
            L["res3"].box(c - 0.15, c + 0.15, a0, a1, 0.0, 4.0, mat=mat, uv=uv, skip=("-z",))
    U["res3"].hquad(-hw + 0.5, hw - 0.5, -hw + 0.5, hw - 0.5, 0.01, mat="rubble", uv=UV_RUBBLE)
    for i in range(10):                                                       # overgrowth (D59)
        x = -hw + 1.0 + (LOT - 2.0) * h01(name, "vx", i)
        y = -hw + 1.0 + (LOT - 2.0) * h01(name, "vy", i)
        plant_tuft(U, x, y, 0.0, 1.0 + 0.6 * h01(name, "vw", i), 0.6 + 0.6 * h01(name, "vh", i),
                   ("weeds", "bramble", "grass", "dry_grass", "burdock")[i % 5], (name, "veg", i),
                   lods=("res0", "res1") if i < 3 else ("res0",))
    for i, (x, y, rx, ry, h) in enumerate(mounds[:1]):
        sapling(U, x + 0.4, y - 0.3, h * 0.8, 3.0 + 2.0 * h01(name, "sap"), (name, "sap"))
    L["mem"].lod.point("lot_center", (0.0, 0.0, 0.0))
    geo = L["geo"].lod
    geo.props.update({"class": "house", "map": "building", "autocenter": "0"})
    geo.mass = 20000.0
    return [x.lod for x in L.values()]


# ================================================================== special pieces (wave 3, D58)
def _pad(L, hw, hd, mat="concrete", uv=None, top=0.0):
    """Ground pad (-SLAB..top) + foundation skirt ring, walkable (Roadway)."""
    uv = uv or UV_REVEAL
    for k in ("res0", "res1", "res2", "geo", "view", "fire"):
        L[k].box(-hw, hw, -hd, hd, top - SLAB, top, **kw_for(k, mat, uv, "concrete"))
    L["road"].hquad(-hw, hw, -hd, hd, top, mat="road_ext", uv=UV_TILE)
    sk = ST["skirt"]
    for (x0, x1, y0, y1) in ((-hw, hw, -hd, -hd + WT), (-hw, hw, hd - WT, hd), (-hw, -hw + WT, -hd + WT, hd - WT),
                             (hw - WT, hw, -hd + WT, hd - WT)):
        for k in ("res0", "res1", "geo", "fire"):
            kw = kw_for(k, "stone", DT.stone_uv("granite"), "concrete")
            if k.startswith("res"):
                kw["skip"] = ("+z", "-z")
            L[k].box(x0, x1, y0, y1, -sk, top - SLAB, **kw)


def _finish(L, mass):
    geo = L["geo"].lod
    geo.props.update({"class": "house", "map": "building", "autocenter": "0"})
    geo.mass = mass
    return [x.lod for x in L.values()]


def bar(lod, p0, p1, r, mat=None, uv=None):
    """Square-section strut between two points (braces, ladder rails)."""
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


def tube(lod, p0, p1, r, mat=None, uv=None, n=10):
    """D96: round tube between two points (n-gon section; the P3D writer smooths it - pipes, rails, arms)."""
    d = [p1[i] - p0[i] for i in range(3)]
    ln = math.sqrt(sum(v * v for v in d)) or 1.0
    d = [v / ln for v in d]
    a = (0, 0, 1) if abs(d[2]) < 0.9 else (1, 0, 0)
    u = [d[1] * a[2] - d[2] * a[1], d[2] * a[0] - d[0] * a[2], d[0] * a[1] - d[1] * a[0]]
    un = math.sqrt(sum(v * v for v in u))
    u = [v / un for v in u]
    w = [d[1] * u[2] - d[2] * u[1], d[2] * u[0] - d[0] * u[2], d[0] * u[1] - d[1] * u[0]]
    ring = [tuple(r * (math.cos(2 * math.pi * k / n) * u[i] + math.sin(2 * math.pi * k / n) * w[i]) for i in range(3))
            for k in range(n)]
    verts = [tuple(p0[i] + c[i] for i in range(3)) for c in ring] + [tuple(p1[i] + c[i] for i in range(3)) for c in ring]
    faces = [tuple(range(n)), tuple(range(n, 2 * n))] + [(k, (k + 1) % n, n + (k + 1) % n, n + k) for k in range(n)]
    lod.solid(verts, faces, mat, uv)


def build_substation(state):
    """10 x 8 m fenced substation (not enterable, no loot): pad, palisade with a closed gate,
    two transformers with bushings, a busbar gantry, a brick control hut. Damaged: soot, a fence
    panel down; ruined: one transformer burnt out, gantry and fence corner collapsed."""
    name = "City_Substation_%s" % S.RUIN_STATES[state]
    hw, hd = 5.0, 4.0
    ruin = Ruin(name, state, (0.4, hw + 1.0, -hd - 1.0, hd * 0.35, 0.6) if state == 2 else None)
    L = city_lods(ruin)
    _pad(L, hw, hd)
    fh = 2.2
    gaps_s = [(-1.6, -0.2)] if state >= 1 else []
    for axis, c, a0, a1, gaps in (("x", -hd + 0.12, -hw + 0.12, hw - 0.12, gaps_s), ("x", hd - 0.12, -hw + 0.12, hw - 0.12, []),
                                  ("y", -hw + 0.12, -hd + 0.15, hd - 0.15, []), ("y", hw - 0.12, -hd + 0.15, hd - 0.15, [])):
        bars(L, axis, c, a0, a1, 0.0, fh, openings=gaps)
        n = int((a1 - a0) / 2.5)
        for i in range(n + 1):                                                  # posts
            a = a0 + i * (a1 - a0) / max(1, n)
            b = (a - 0.05, a + 0.05, c - 0.05, c + 0.05) if axis == "x" else (c - 0.05, c + 0.05, a - 0.05, a + 0.05)
            for k in ("res0", "res1", "res2", "geo", "fire"):
                L[k].box(*b, 0.0, fh + 0.15, **kw_for(k, "metal", DT.UV_PAINT, "metal"))
    for gx in (-0.9, 0.9):                                                      # warning plates on the gate
        L["res0"].box(gx - 0.2, gx + 0.2, -hd + 0.06, -hd + 0.08, 1.2, 1.5, mat="paint", uv=DT.paint_uv("terracotta"))
    brick = DT._brick_uv("bond")
    hx0, hx1, hy0, hy1 = -hw + 0.5, -hw + 3.5, hd - 3.0, hd - 0.5                 # control hut
    for k in ("res0", "res1", "res2", "geo", "view", "fire", "shadow"):
        L[k].box(hx0, hx1, hy0, hy1, 0.0, 2.8, **kw_for(k, "brick", brick, "masonry"))
        L[k].box(hx0 - 0.15, hx1 + 0.15, hy0 - 0.15, hy1 + 0.15, 2.8, 3.0, **kw_for(k, "concrete", UV_CONC, "concrete"))
    L["res0"].box(hx0 + 0.9, hx0 + 1.9, hy0 - 0.04, hy0, 0.0, 2.1, mat="metal", uv=DT.UV_PAINT, skip=("+y",))
    L["res0"].box(hx1 - 0.9, hx1 - 0.3, hy0 - 0.03, hy0, 1.6, 2.2, mat="metal", uv=DT.UV_STEEL, skip=("+y",))
    porcelain = DT.paint_uv("terracotta")
    for i, tx in enumerate((0.3, 3.1)):                                         # transformers
        burnt = state == 2 and i == 1
        tmat, tuv = ("rust", UVBand(S.MATERIALS["rust"]["bands"]["burnt"], 1.0)) if burnt else ("paint", DT.paint_uv("slate"))
        x0, x1, y0, y1 = tx - 0.8, tx + 0.8, -1.4, 0.2
        for k in ("res0", "res1", "res2", "geo", "view", "fire", "shadow"):
            L[k].box(x0 - 0.2, x1 + 0.2, y0 - 0.2, y1 + 0.2, 0.0, 0.3, **kw_for(k, "concrete", UV_CONC, "concrete"))
            L[k].box(x0, x1, y0, y1, 0.3, 2.1, **kw_for(k, tmat, tuv, "metal"))
        for j in range(6):                                                      # cooling fins (Res0)
            fy = y0 + 0.15 + j * (y1 - y0 - 0.3) / 5
            for fx in (x0 - 0.18, x1):
                L["res0"].box(fx, fx + 0.18, fy - 0.02, fy + 0.02, 0.5, 1.9, mat=tmat, uv=tuv)
        for k in ("res0", "geo", "fire", "view"):                                  # conservator (collides, D82)
            L[k].box(x0 + 0.2, x1 - 0.2, y1 - 0.45, y1 - 0.05, 2.35, 2.75, **kw_for(k, tmat, tuv, "metal"))
        for bx in (x0 + 0.35, tx, x1 - 0.35):                                   # bushings
            for k in ("res0", "res1"):
                L[k].prism(bx, (y0 + y1) / 2 - 0.2, 0.09, 2.1, 2.9, n=8, mat="paint", uv=porcelain)
        if state >= 1:
            L["res0"].quad([(x0 - 0.01, y0 - 0.2, 0.6), (x0 - 0.01, y1 + 0.2, 0.6), (x0 - 0.01, y1 + 0.2, 2.1),
                            (x0 - 0.01, y0 - 0.2, 2.1)], (-1, 0, 0), "decal_dirt",
                           UVRect(1, 2, (y0 - 0.2, 0.6), (y1 + 0.2, 2.1), (0, 0, 1, 1)))
    gy = 2.4                                                                     # busbar gantry
    for gx in (-0.9, 4.4):
        for k in ("res0", "res1", "res2", "geo", "view", "fire", "shadow"):
            L[k].box(gx - 0.12, gx + 0.12, gy - 0.12, gy + 0.12, 0.0, 5.5, **kw_for(k, "metal", DT.UV_STEEL, "metal"))
    for k in ("res0", "res1", "res2", "geo", "fire", "shadow"):
        L[k].box(-0.9, 4.4, gy - 0.1, gy + 0.1, 5.2, 5.45, **kw_for(k, "metal", DT.UV_STEEL, "metal"))
    for bx in (0.3, 1.7, 3.1):
        L["res0"].prism(bx, gy, 0.08, 4.5, 5.2, n=8, mat="paint", uv=porcelain)
        bar(L["res0"], (bx, gy, 4.5), (bx, -0.6, 2.9), 0.02, "metal", DT.UV_ALU)
    L["res3"].box(-hw, hw, -hd, hd, -SLAB, 0.0, mat="concrete", uv=UV_REVEAL, skip=("-z",))
    L["res3"].box(-0.5, 3.9, -1.4, 0.2, 0.0, 2.1, mat="paint", uv=DT.paint_uv("slate"), skip=("-z",))
    L["res3"].box(hx0, hx1, hy0, hy1, 0.0, 3.0, mat="brick", uv=brick, skip=("-z",))
    if state == 2:
        rubble_pile(L, 3.4, -2.0, 0.0, 0.9, 0.7, 0.5, (name, "main"))
    U = {k: x.lod for k, x in L.items()}
    for i in range(6 + 4 * state):                                           # weeds along the fence, in pad cracks
        x = -hw + 0.6 + (2 * hw - 1.2) * h01(name, "wx", i)
        y = (hd - 0.45) * (1 if i % 2 else -1) if i < 6 else -hd + 0.6 + (2 * hd - 1.2) * h01(name, "wy", i)
        plant_tuft(U, x, y, 0.0, 0.8, 0.5 + 0.4 * h01(name, "wh", i) + 0.2 * state, ("grass", "dry_grass", "weeds")[i % 3],
                   (name, "w", i))
    L["mem"].lod.point("center", (0.0, 0.0, 0.0))
    return _finish(L, 30000.0)


def build_watertower():
    """6 x 6 m steel water tower: concrete footings, 4 legs with ring beams and X bracing, an
    18 m tank with a cone roof, gallery and ladder (Res only: no climb route)."""
    name = "City_WaterTower"
    L = city_lods(Ruin(name, 0))
    lg, zt = 2.4, 14.0
    steel, paint = DT.UV_STEEL, DT.UV_PAINT
    tank_uv = UVBand(S.MATERIALS["rust"]["bands"]["grey"], 1.0)
    for sx in (-1, 1):
        for sy in (-1, 1):
            x, y = sx * lg, sy * lg
            for k in ("res0", "res1", "res2", "geo", "view", "fire"):
                L[k].box(x - 0.5, x + 0.5, y - 0.5, y + 0.5, -ST["skirt"], 0.3, **kw_for(k, "concrete", UV_CONC, "concrete"))
                L[k].box(x - 0.15, x + 0.15, y - 0.15, y + 0.15, 0.3, zt, **kw_for(k, "metal", paint, "metal"))
            L["road"].hquad(x - 0.5, x + 0.5, y - 0.5, y + 0.5, 0.3, mat="road_ext", uv=UV_TILE)
            L["shadow"].box(x - 0.15, x + 0.15, y - 0.15, y + 0.15, 0.3, zt)
            L["res3"].box(x - 0.15, x + 0.15, y - 0.15, y + 0.15, 0.0, zt, mat="metal", uv=paint, skip=("-z", "+z"))
    for z in (5.0, 9.5):                                                         # ring beams + X bracing
        for (a0, a1, b0, b1) in ((-lg, lg, -lg - 0.1, -lg + 0.1), (-lg, lg, lg - 0.1, lg + 0.1),
                                 (-lg - 0.1, -lg + 0.1, -lg, lg), (lg - 0.1, lg + 0.1, -lg, lg)):
            for k in ("res0", "res1", "res2", "geo", "fire"):
                L[k].box(a0, a1, b0, b1, z, z + 0.2, **kw_for(k, "metal", paint, "metal"))
    for (za, zb) in ((0.3, 5.0), (5.2, 9.5), (9.7, zt)):
        for (p, q) in (((-lg, -lg), (lg, -lg)), ((lg, -lg), (lg, lg)), ((lg, lg), (-lg, lg)), ((-lg, lg), (-lg, -lg))):
            for (s0, s1) in ((p, q), (q, p)):
                bar(L["res0"], (s0[0], s0[1], za), (s1[0], s1[1], zb), 0.04, "metal", steel)
    for k in ("res0", "res1", "res2", "geo", "view", "fire", "shadow"):          # gallery deck + tank + roof
        L[k].prism(0.0, 0.0, 2.98, zt, zt + 0.15, n=16 if k == "res0" else 8, **kw_for(k, "metal", steel, "metal"))
        L[k].prism(0.0, 0.0, 2.6, zt + 0.15, zt + 4.5, n=16 if k == "res0" else 8, **kw_for(k, "rust", tank_uv, "metal"))
    for k in ("res0", "res1", "res2", "res3", "geo", "fire", "shadow"):
        nn = 16 if k == "res0" else (8 if k != "res3" else 6)
        ring = [(2.75 * math.cos(2 * math.pi * i / nn), 2.75 * math.sin(2 * math.pi * i / nn), zt + 4.5) for i in range(nn)]
        L[k].solid(ring + [(0.0, 0.0, zt + 6.0)], [tuple(range(nn))] + [(i, (i + 1) % nn, nn) for i in range(nn)],
                   **kw_for(k, "rust", tank_uv, "metal"))
    L["res3"].prism(0.0, 0.0, 2.6, zt, zt + 4.5, n=6, mat="rust", uv=tank_uv)
    for i in range(16):                                                         # gallery railing
        a = 2 * math.pi * i / 16
        L["res0"].prism(2.9 * math.cos(a), 2.9 * math.sin(a), 0.025, zt + 0.15, zt + 1.15, n=4, mat="metal", uv=steel)
    for zz in (zt + 0.6, zt + 1.1):
        for i in range(16):
            a0, a1 = 2 * math.pi * i / 16, 2 * math.pi * (i + 1) / 16
            bar(L["res0"], (2.9 * math.cos(a0), 2.9 * math.sin(a0), zz), (2.9 * math.cos(a1), 2.9 * math.sin(a1), zz), 0.02,
                "metal", steel)
    for lx in (-0.25, 0.25):                                                    # ladder up the south side (visual)
        bar(L["res0"], (lx, -lg - 0.3, 0.3), (lx, -lg - 0.3, zt), 0.025, "metal", steel)
    for i in range(int((zt - 0.6) / 0.35)):
        z = 0.6 + i * 0.35
        L["res0"].box(-0.25, 0.25, -lg - 0.32, -lg - 0.28, z, z + 0.03, mat="metal", uv=steel)
    U = {k: x.lod for k, x in L.items()}
    for sx in (-1, 1):                                                       # weeds round the footings
        for sy in (-1, 1):
            plant_tuft(U, sx * (lg - 0.7), sy * (lg - 0.7), 0.3, 0.9, 0.7, ("weeds", "grass")[(sx + sy) % 2 == 0],
                       (name, sx, sy))
    L["mem"].lod.point("center", (0.0, 0.0, 0.0))
    return _finish(L, 60000.0)


def build_metro(v):
    """4 x 6 m metro entrance, sealed at street level (no terrain hole needed, D58).
    A: granite stair-head walls with railings, chequer-plate cover, closed gate, METRO pylon.
    B: glazed steel pavilion over the same cover, doors chained shut, METRO fascia."""
    name = "City_MetroEntrance_%s" % v
    L = city_lods(Ruin(name, 0))
    hw, hd = 2.0, 3.0
    _pad(L, hw, hd, "stone", DT.stone_uv("granite"))
    for k in ("res0", "res1"):                                                  # chequer-plate cover over the well
        L[k].hquad(-1.6, 1.6, -2.6, 2.6, 0.012, mat="metal", uv=DT.UV_STEEL)
    for k in ("res0", "res1", "geo", "fire"):
        L[k].box(-1.6, 1.6, -2.6, 2.6, 0.0, 0.01, **kw_for(k, "metal", DT.UV_STEEL, "metal"))
    v0, v1 = S.SIGN_BAND["metro"]
    if v == "A":
        gran = DT.stone_uv("granite")
        for (x0, x1, y0, y1) in ((-hw, -hw + 0.3, -hd, hd), (hw - 0.3, hw, -hd, hd), (-hw + 0.3, hw - 0.3, hd - 0.3, hd)):
            for k in ("res0", "res1", "res2", "geo", "view", "fire", "shadow"):
                L[k].box(x0, x1, y0, y1, 0.0, 1.0, **kw_for(k, "stone", gran, "concrete"))
            rail(L, x0 + 0.1, x1 - 0.1, y0 + 0.1 if y1 - y0 < 1 else y0, y1 - 0.1 if y1 - y0 < 1 else y1, 1.0, h=0.9)
        bars(L, "x", -hd + 0.15, -hw + 0.3, hw - 0.3, 0.0, 1.9)                 # closed gate
        px, py = hw - 0.15, -hd + 0.15
        for k in ("res0", "res1", "res2", "geo", "fire"):
            L[k].prism(px, py, 0.08, 1.0, 3.4, n=8, **kw_for(k, "metal", DT.UV_PAINT, "metal"))
        for k in ("res0", "res1", "res2"):
            L[k].box(px - 0.45, px + 0.15, py - 0.06, py + 0.06, 2.7, 3.3, mat="metal", uv=DT.UV_PAINT)
        for sgn in (-1, 1):
            L["res0"].quad([(px - 0.42, py + sgn * 0.065, 2.75), (px + 0.12, py + sgn * 0.065, 2.75),
                            (px + 0.12, py + sgn * 0.065, 3.25), (px - 0.42, py + sgn * 0.065, 3.25)], (0, sgn, 0), "signs",
                           UVRect(0, 2, (px - 0.42, 2.75), (px + 0.12, 3.25), (0, 1 - v1, 1, 1 - v0)))
        L["res3"].box(-hw, hw, -hd, hd, -SLAB, 1.0, mat="stone", uv=gran, skip=("-z",))
    else:
        zt = 3.0
        for (x, y) in ((-hw + 0.1, -hd + 0.1), (hw - 0.1, -hd + 0.1), (-hw + 0.1, hd - 0.1), (hw - 0.1, hd - 0.1),
                       (-hw + 0.1, 0.0), (hw - 0.1, 0.0)):
            for k in ("res0", "res1", "res2", "geo", "view", "fire"):
                L[k].box(x - 0.1, x + 0.1, y - 0.1, y + 0.1, 0.0, zt, **kw_for(k, "metal", DT.UV_PAINT, "metal"))
        for k in ("res0", "res1", "res2", "res3", "geo", "view", "fire", "shadow"):
            o = 0.1 if k.startswith("res") else 0.0                             # overhang is visual only
            L[k].box(-hw - o, hw + o, -hd - o, hd + o, zt, zt + 0.3, **kw_for(k, "metal", DT.UV_PAINT, "metal"))
        walls = (("x", -hd + 0.1), ("x", hd - 0.1), ("y", -hw + 0.1), ("y", hw - 0.1))
        for axis, c in walls:                                                   # glass walls (closed: collide)
            a = hw - 0.2 if axis == "x" else hd - 0.2
            b = (-a, a, c - 0.02, c + 0.02) if axis == "x" else (c - 0.02, c + 0.02, -a, a)
            for k in ("geo", "fire"):
                L[k].box(*b, 0.0, zt, **({"mat": "pen_glass"} if k == "fire" else {}))
            pts = ([(-a, c, 0.05), (a, c, 0.05), (a, c, zt), (-a, c, zt)] if axis == "x" else
                   [(c, -a, 0.05), (c, a, 0.05), (c, a, zt), (c, -a, zt)])
            nrm = (0, 1, 0) if axis == "x" else (1, 0, 0)
            L["res0"].quad(pts, nrm, "glass", UV_GLASS, double=True)
            L["res1"].quad(pts, nrm, "glass", UV_GLASS, double=True)
            L["res2"].quad(pts, nrm, "glassfar", UV_GLASS, double=True)
        for dx in (-0.6, 0.6):                                                  # door frames + chain
            L["res0"].box(dx - 0.04, dx + 0.04, -hd + 0.04, -hd + 0.16, 0.0, 2.2, mat="metal", uv=DT.UV_STEEL)
        L["res0"].box(-0.6, 0.6, -hd + 0.04, -hd + 0.16, 2.16, 2.24, mat="metal", uv=DT.UV_STEEL)
        L["res0"].box(-0.25, 0.25, -hd + 0.02, -hd + 0.05, 1.0, 1.06, mat="rust", uv=UVBand(S.MATERIALS["rust"]["bands"]["rust"], 1.0))
        for k in ("res0", "res1"):                                              # fascia
            L[k].quad([(-1.4, -hd - 0.11, zt + 0.03), (1.4, -hd - 0.11, zt + 0.03), (1.4, -hd - 0.11, zt + 0.27),
                       (-1.4, -hd - 0.11, zt + 0.27)], (0, -1, 0), "signs",
                      UVRect(0, 2, (-1.4, zt + 0.03), (1.4, zt + 0.27), (0, 1 - v1, 1, 1 - v0)))
    U = {k: x.lod for k, x in L.items()}
    for i, (x, y) in enumerate(((-hw + 0.35, -hd + 0.4), (hw - 0.35, hd - 0.4), (-hw + 0.35, hd - 0.5))):
        plant_tuft(U, x, y, 0.0, 0.5, 0.45, ("grass", "dry_grass", "weeds")[i], (name, "w", i))
    L["mem"].lod.point("center", (0.0, 0.0, 0.0))
    return _finish(L, 20000.0)


def build_veg(name):
    """Vegetation kit pieces (D59). Cards on the vegetation atlas; Res1 / Res2 / Res3 thin out to a
    single crossed card. Weeds and bushes have no collision; trees collide with the trunk only."""
    L = city_lods(Ruin(name, 0))
    U = {k: x.lod for k, x in L.items()}
    if name == "Veg_Weeds":
        cells = ("grass", "weeds", "dry_grass", "burdock", "bramble", "grass", "weeds")
        for i, cell in enumerate(cells):
            x, y = -1.0 + 2.0 * h01(name, "x", i), -1.0 + 2.0 * h01(name, "y", i)
            h = 0.5 + 0.7 * h01(name, "h", i)
            plant_tuft(U, x, y, -0.15, 0.9, h, cell, (name, i), lods=("res0", "res1") if i < 3 else ("res0",))
        plant_tuft(U, 0.0, 0.0, -0.15, 2.4, 0.9, "weeds", (name, "far"), lods=("res2",))
        veg_card(U, [(-1.2, 0.0, -0.15), (1.2, 0.0, -0.15), (1.2, 0.0, 0.7), (-1.2, 0.0, 0.7)], (0, -1, 0), "grass", ("res3",))
    elif name == "Veg_Bush":
        for i in range(3):
            plant_tuft(U, 0.25 * math.cos(i * 2.1), 0.25 * math.sin(i * 2.1), -0.1, 2.2, 2.0 + 0.4 * h01(name, i),
                       "shrub", (name, i), lods=("res0", "res1") if i == 0 else ("res0",))
        plant_tuft(U, 0.0, 0.0, -0.1, 2.5, 0.9, "bramble", (name, "skirt"))
        plant_tuft(U, 0.0, 0.0, -0.1, 2.3, 2.2, "shrub", (name, "far"), lods=("res2",))
        veg_card(U, [(-1.1, 0.0, -0.1), (1.1, 0.0, -0.1), (1.1, 0.0, 2.1), (-1.1, 0.0, 2.1)], (0, -1, 0), "shrub", ("res3",))
    elif name in ("Veg_Birch", "Veg_TreeDead"):
        birch = name == "Veg_Birch"
        th, r = (9.0, 0.13) if birch else (6.0, 0.16)
        bark = UVRect(0, 2, (-r, 0.0), (r, th), S.veg_uv("bark"))
        for k, n in (("res0", 8), ("res1", 5), ("res2", 4), ("res3", 3)):
            U[k].prism(0.0, 0.0, r, -0.3, th * ((0.8 if birch else 0.85) if k != "res3" else 0.5), n=n,
                       mat="vegetation", uv=bark)                              # dead birch: same bark, one section
        for k in ("geo", "fire", "shadow"):
            kw = {"mat": "pen_wood"} if k == "fire" else {}
            U[k].prism(0.0, 0.0, r, -0.3, th * 0.8, n=6 if k != "shadow" else 4, **kw)
        cell = "birch_crown" if birch else "dead_branches"
        levels = ((3.2, 3.0), (4.8, 3.6), (6.6, 3.0)) if birch else ((2.2, 3.8),)
        for i, (z, h) in enumerate(levels):
            plant_tuft(U, 0.15 * math.cos(i * 2.4), 0.15 * math.sin(i * 2.4), z, 2.4 + 0.5 * h01(name, i), h, cell, (name, i),
                       lods=("res0", "res1") if i == 1 else ("res0",))
        plant_tuft(U, 0.0, 0.0, 2.8 if birch else 2.0, 2.8, 6.0 if birch else 4.0, cell, (name, "far"), lods=("res2",))
        veg_card(U, [(-1.4, 0.0, 2.8), (1.4, 0.0, 2.8), (1.4, 0.0, th), (-1.4, 0.0, th)], (0, -1, 0), cell, ("res3",))
        geo = U["geo"]
        geo.props.update({"class": "house", "map": "tree" if birch else "building", "autocenter": "0"})
        geo.mass = 1500.0
    U["mem"].point("center", (0.0, 0.0, 0.0))
    keep = ("res0", "res1", "res2", "res3", "mem") + (("geo", "fire", "shadow") if name in ("Veg_Birch", "Veg_TreeDead") else ())
    return [U[k] for k in keep]


# ================================================================== memory, loot, build

# ================================================================== D61 venues (ROADMAP.md)
# Hypermarket, mall, cinema, bar, kindergarten, clubhouse, hanged church. Same grammar and rules:
# collision only where walkable / big; keep-clear zones; Res0 detail, Res1 big forms.
VENUE_SHOPS = ["fashion", "shoes", "jewelry", "electro"]


def sign2_quad(lod, pts, facing, sign, axes, lo, hi):
    """Quad textured with one band of a sign sheet (signs / signs2, skyspec.SIGN_MAT)."""
    v0, v1 = S.SIGN_BAND[sign]
    lod.quad(pts, facing, S.SIGN_MAT[sign], UVRect(axes[0], axes[1], lo, hi, (0, 1 - v1, 1, 1 - v0)))


def layout_venue(P, use, l):
    ix0, ix1, iy0, iy1 = P.ix0, P.ix1, P.iy0, P.iy1
    h = PT / 2
    walls, rooms = [], []
    if use == "hyper":
        ys = iy1 - 7.0
        walls.append(("x", ys, ix0, ix1, [(ix0 + 2.6, ix0 + 4.0), (ix1 - 4.0, ix1 - 2.6)]))
        rooms += [(ix0, ix1, iy0, ys - h, "hyper"), (ix0, ix1, ys + h, iy1, "storage")]
    elif use == "cinema":
        yw = iy0 + 9.0
        walls.append(("x", yw, ix0, ix1, [(ix0 + 0.15, ix0 + 1.45), (ix1 - 1.45, ix1 - 0.15)]))
        rooms += [(ix0, ix1, iy0, yw - h, "foyer"), (ix0, ix1, yw + h, iy1, "auditorium")]
    elif use == "bar":
        ys = iy1 - 2.4
        walls.append(("x", ys, ix0, ix1, [(ix1 - 1.8, ix1 - 0.9)]))
        rooms += [(ix0, ix1, iy0, ys - h, "bar"), (ix0, ix1, ys + h, iy1, "storage")]
    elif use == "changing":
        yh = iy0 + 2.2
        walls += [("x", yh, ix0, ix1, [(-4.5, -3.6), (3.6, 4.5)]), ("y", 0.0, yh + h, iy1, [])]
        rooms += [(ix0, ix1, iy0, yh - h, "club_hall"), (ix0, -h, yh + h, iy1, "changing"), (h, ix1, yh + h, iy1, "changing")]
    elif use == "creche":
        walls, rooms = layout(P, "corridor", l)
        kinds = ["play", "nap", "play", "wash"]
        rooms = [(r[0], r[1], r[2], r[3], kinds[i % 4] if r[4] in ("room", "exam", "dorm") else r[4])
                 for i, r in enumerate(rooms)]
    elif use == "mall":
        sx0, sx1, sy0, sy1 = P.stair
        dp = 7.5
        xw, xe, yn = ix0 + dp, ix1 - dp, iy1 - dp
        shop_kind = "food" if l == len(P.levels) - 1 else "mall_shop"
        for side, xc, a_lo in (("W", xw, ix0), ("E", xe, ix1)):
            units = split_bays(iy0, yn - h, 8.0, 5.0)
            walls.append(("y", xc, iy0, yn - h, [((a + b) / 2 - 1.6, (a + b) / 2 + 1.6) for a, b in units]))
            for a, b in units[1:]:
                walls.append(("x", a, ix0, xw - h, []) if side == "W" else ("x", a, xe + h, ix1, []))
            for i, (a, b) in enumerate(units):
                x0, x1 = (ix0, xw - h) if side == "W" else (xe + h, ix1)
                rooms.append((x0, x1, a + (h if i else 0), b - (h if i < len(units) - 1 else 0), shop_kind))
        north = [(ix0, sx0 - 1.2 - h), (sx1 + 1.2 + h, ix1)]
        ops = [(sx0 - 1.2, sx1 + 1.2)]
        for (a0, a1) in north:
            units = split_bays(a0, a1, 8.5, 5.0)
            ops += [((a + b) / 2 - 1.6, (a + b) / 2 + 1.6) for a, b in units]
            for a, b in units[1:]:
                walls.append(("y", a, yn + h, iy1, []))
            for i, (a, b) in enumerate(units):
                rooms.append((a + (h if i else 0), b - (h if i < len(units) - 1 else 0), yn + h, iy1, shop_kind))
        for c in (sx0 - 1.2, sx1 + 1.2):                                        # corridor to the stair
            walls.append(("y", c, yn + h, iy1, []))
        walls.append(("x", yn, ix0, ix1, sorted(ops)))
        rooms.append((sx0 - 1.2 + h, sx1 + 1.2 - h, yn + h, sy0, "hall"))
        rooms.append((xw + h, xe - h, iy0, yn - h, "mall_hall"))
    return walls, rooms


def tube_row(L, x0, x1, y, z, lit, lods=("res0",)):
    """Fluorescent batten row: steel housings with diffuser tubes (lamp_cool when lit), 1.5 m each."""
    a = x0
    while a + 1.5 <= x1 + 1e-6:
        L["res0"].box(a + 0.05, a + 1.45, y - 0.09, y + 0.09, z, z + 0.06, mat="metal", uv=DT.UV_PAINT, skip=("-z",))
        L["res0"].hquad(a + 0.08, a + 1.42, y - 0.07, y + 0.07, z - 0.001, mat="lamp_cool" if lit else "metal",
                        uv=None if lit else DT.UV_STEEL, up=False)
        a += 1.6
    if "res1" in lods:
        L["res1"].hquad(x0, x1, y - 0.09, y + 0.09, z - 0.001, mat="lamp_cool" if lit else "metal",
                        uv=None if lit else DT.UV_STEEL, up=False)


def chair(L, x, y, z, face, s=1.0, mat="metal", uv=None):
    """Visual chair (seat + back), face = direction the sitter looks ('+y', '-y', '+x', '-x')."""
    uv = uv or DT.UV_ALU
    w, sh = 0.42 * s, 0.45 * s
    L["res0"].box(x - w / 2, x + w / 2, y - w / 2, y + w / 2, z + sh - 0.05 * s, z + sh, mat=mat, uv=uv)
    for (lx, ly) in ((x - w / 2 + 0.03, y - w / 2 + 0.03), (x + w / 2 - 0.03, y - w / 2 + 0.03),
                     (x - w / 2 + 0.03, y + w / 2 - 0.03), (x + w / 2 - 0.03, y + w / 2 - 0.03)):
        L["res0"].box(lx - 0.015, lx + 0.015, ly - 0.015, ly + 0.015, z, z + sh - 0.05 * s, mat="metal", uv=DT.UV_STEEL,
                      skip=("-z", "+z"))
    back = {"+y": (x - w / 2, x + w / 2, y - w / 2, y - w / 2 + 0.03), "-y": (x - w / 2, x + w / 2, y + w / 2 - 0.03, y + w / 2),
            "+x": (x - w / 2, x - w / 2 + 0.03, y - w / 2, y + w / 2), "-x": (x + w / 2 - 0.03, x + w / 2, y - w / 2, y + w / 2)}[face]
    L["res0"].box(*back, z + sh, z + sh + 0.42 * s, mat=mat, uv=uv)


def bottles(L, x0, x1, y, z, depth=0.2, key=(), ruin=False):
    """A row of bottles on a shelf (Res0): glass / brown / green / clear by seed."""
    n = int((x1 - x0) / 0.11)
    for i in range(n):
        r = h01("btl", key, i)
        if r < 0.12:
            continue
        cx = x0 + 0.055 + i * (x1 - x0 - 0.11) / max(1, n - 1)
        hb = 0.24 + 0.1 * h01("btlh", key, i)
        mat = ("glassfar", "paint", "paint", "glassfar" if ruin else "glass")[int(r * 4)]
        uv = UV_GLASS if mat.startswith("glass") else DT.paint_uv(("sage", "terracotta", "beige")[i % 3])
        L["res0"].prism(cx, y, 0.035, z, z + hb, n=6, mat=mat, uv=uv)
        L["res0"].prism(cx, y, 0.012, z + hb, z + hb + 0.08, n=4, mat=mat, uv=uv)


SEARCH_MAX = 8                                                                   # SKY_Search reads search_1..search_8


def search_point(L, x, y, z):
    """Searchable spot (D61, ActionSKY_Search): memory point search_N where the player stands
    (floor level); the server picks the loot table from the building class (SKY_SearchTable)."""
    lod = L["mem"].lod
    n = sum(1 for g in lod.groups if g.startswith("search_"))
    if n < SEARCH_MAX:
        lod.point("search_%d" % (n + 1), (x, y, z))


def mannequin(L, x, y, z, key):
    """Shop mannequin (Res0): stand, legs, torso with a garment, head - pale paint."""
    pale = DT.paint_uv("white")
    L["res0"].prism(x, y, 0.18, z, z + 0.03, n=8, mat="metal", uv=DT.UV_STEEL)
    L["res0"].prism(x, y, 0.02, z + 0.03, z + 0.85, n=4, mat="metal", uv=DT.UV_STEEL)
    L["res0"].box(x - 0.13, x + 0.13, y - 0.08, y + 0.08, z + 0.85, z + 1.45, mat="textile",
                  uv=DT.band_fit("textile", ("rug_a", "rug_b", "curtain")[int(h01("mq", key) * 3)], x - 0.13, x + 0.13, y - 0.08, y + 0.08))
    L["res0"].box(x - 0.2, x + 0.2, y - 0.09, y + 0.09, z + 1.3, z + 1.5, mat="paint", uv=pale)
    L["res0"].prism(x, y, 0.035, z + 1.5, z + 1.58, n=6, mat="paint", uv=pale)
    L["res0"].prism(x, y, 0.1, z + 1.58, z + 1.8, n=8, mat="paint", uv=pale)


def garment_rail(L, x0, x1, y, z, key):
    """Clothes rail with hanging garments (double-sided textile cards)."""
    for xx in (x0, x1):
        L["res0"].prism(xx, y, 0.02, z, z + 1.5, n=4, mat="metal", uv=DT.UV_STEEL)
    bar(L["res0"], (x0, y, z + 1.5), (x1, y, z + 1.5), 0.012, "metal", DT.UV_STEEL)
    n = int((x1 - x0) / 0.12)
    for i in range(n):
        gx = x0 + 0.08 + i * (x1 - x0 - 0.16) / max(1, n - 1)
        if h01("gr", key, i) < 0.25:
            continue
        band = ("rug_a", "rug_b", "curtain", "runner")[int(h01("grc", key, i) * 4)]
        ln = 0.7 + 0.5 * h01("grl", key, i)
        L["res0"].quad([(gx, y - 0.22, z + 1.48 - ln), (gx, y + 0.22, z + 1.48 - ln), (gx, y + 0.22, z + 1.46), (gx, y - 0.22, z + 1.46)],
                       (1, 0, 0), "textile", DT.band_fit("textile", band, y - 0.22, y + 0.22, 0.0, 1.0, axes=(1, 2)), double=True)


def furnish_venue(L, P, l, r, kind, z, top, zones):
    x0, x1, y0, y1 = r
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    w, d = x1 - x0, y1 - y0
    lit = P.state == 0
    Lz = lifted(L, z)
    var = int(h01(P.name, l, kind, "var", round(cx, 1), round(cy, 1)) * 3)   # D86 venue layout variant (0 = original)
    if kind == "hyper":
        # checkout lines along the front, trolley corral by the door
        for xk in [x0 + 6.0 + i * 3.6 for i in range(int((w - 12.0) / 3.6) + 1)]:
            box = (xk - 0.35, xk + 0.35, y0 + 2.2, y0 + 4.8)
            if clear(zones, box):
                kitchen_run(L, *box, z)
                piece(L, (xk + 0.4, xk + 0.85, y0 + 2.6, y0 + 3.0, z, z + 0.5), "metal", DT.UV_PAINT, pen="metal",
                      res1=False, view=True)                                     # cashier seat (collides, D82)
                L["res0"].prism(xk - 0.3, y0 + 4.7, 0.025, z + 0.9, z + 2.1, n=4, mat="metal", uv=DT.UV_STEEL)
                L["res0"].box(xk - 0.42, xk - 0.18, y0 + 4.68, y0 + 4.72, z + 2.0, z + 2.25,
                              mat="lamp_cool" if lit else "metal", uv=None if lit else DT.UV_STEEL)
        for i in range(5):                                                      # trolleys (Res0)
            tx = x0 + 1.2 + i * 0.55
            L["res0"].box(tx, tx + 0.5, y0 + 1.0, y0 + 1.95, z + 0.25, z + 0.95, mat="metal", uv=DT.UV_STEEL)
        tb_ = (x0 + 1.2, x0 + 1.2 + 4 * 0.55 + 0.5, y0 + 1.0, y0 + 1.95)
        if clear(zones, tb_):                                                   # the nested trolley row collides down to
            for k in ("geo", "fire", "view"):                                   # the floor (D82; no loot gap under it)
                L[k].box(*tb_, z, z + 0.95, **({"mat": "pen_metal"} if k == "fire" else {}))
        # tall racking: rows across the hall, main aisle in the middle, cross aisle halfway
        ry = y0 + 7.0
        while ry + 0.9 < y1 - 1.6:
            for (a0, a1) in ((x0 + 2.0, -2.5), (2.5, x1 - 2.0)):
                mid = (a0 + a1) / 2
                for (b0, b1) in ((a0, mid - 1.2), (mid + 1.2, a1)):
                    box = (b0, b1, ry, ry + 0.9)
                    if b1 - b0 > 2.0 and clear(zones, box):
                        shelf_unit(L, *box, z, h=3.4)
                        if h01(P.name, "srch", round(b0, 1), round(ry, 1)) < 0.35:        # stockroom-ish search (D65)
                            search_point(L, (b0 + b1) / 2, ry - 0.7, z)
            ry += 3.4
        for (px, py) in ((-6.0, y0 + 5.6), (0.0, y0 + 5.6), (6.0, y0 + 5.6)):    # promotion pallets
            box = (px - 0.6, px + 0.6, py - 0.4, py + 0.4)
            if clear(zones, box):
                piece(L, box + (z, z + 0.15), "wood", UV_LAMINATE)
                for j in range(3):
                    L["res0"].box(px - 0.55 + 0.02 * j, px + 0.55 - 0.02 * j, py - 0.35, py + 0.35, z + 0.15 + 0.3 * j,
                                  z + 0.44 + 0.3 * j, mat="wood", uv=UV_LAMINATE)
                for k in ("geo", "fire", "view"):                               # the stacked goods collide (D82)
                    L[k].box(px - 0.51, px + 0.51, py - 0.35, py + 0.35, z + 0.15, z + 1.04, **({"mat": "pen_wood"} if k == "fire" else {}))
        # aisle signs hung over the main aisle
        for i, sg in enumerate(("food", "electro", "fashion", "tickets")[:3]):
            sy = y0 + 9.0 + i * 7.0
            if sy > y1 - 2.0:
                break
            for k in ("res0", "res1"):
                L[k].box(-1.6, 1.6, sy - 0.03, sy + 0.03, top - 2.2, top - 1.7, mat="metal", uv=DT.UV_PAINT)
            for s_ in (-1, 1):
                sign2_quad(L["res0"], [(-1.55, sy + s_ * 0.032, top - 2.15), (1.55, sy + s_ * 0.032, top - 2.15),
                                        (1.55, sy + s_ * 0.032, top - 1.75), (-1.55, sy + s_ * 0.032, top - 1.75)],
                           (0, s_, 0), sg, (0, 2), (-1.55, top - 2.15), (1.55, top - 1.75))
            for xx in (-1.4, 1.4):
                L["res0"].prism(xx, sy, 0.008, top - 1.7, top, n=3, mat="metal", uv=DT.UV_STEEL)
        # harsh light: continuous fluorescent rows every 2.4 m, hung 1 m below the roof
        yy = y0 + 1.5
        while yy < y1 - 0.5:
            tube_row(L, x0 + 1.0, x1 - 1.0, yy, top - 1.0, lit, lods=("res0", "res1"))
            for xx in (x0 + 2.0, cx, x1 - 2.0):
                L["res0"].prism(xx, yy, 0.006, top - 0.94, top, n=3, mat="metal", uv=DT.UV_STEEL)
            yy += 2.4
    elif kind == "foyer":
        DT.rug(Lz, cx - 3.0, cx + 3.0, y0 + 1.5, y1 - 1.5, "runner")
        tb = (x0 + 0.4, x0 + 3.6, y1 - 2.2, y1 - 1.5)                          # ticket booth (glass screen)
        if clear(zones, tb):
            kitchen_run(L, *tb, z)
            L["res0"].quad([(tb[0], tb[2] - 0.01, z + 0.95), (tb[1], tb[2] - 0.01, z + 0.95), (tb[1], tb[2] - 0.01, z + 2.0),
                            (tb[0], tb[2] - 0.01, z + 2.0)], (0, -1, 0), "glass" if lit else "glassfar", UV_GLASS, double=True)
            for k in ("res0", "res1"):
                L[k].box(tb[0], tb[1], tb[2], tb[3], z + 2.0, z + 2.5, mat="wood", uv=UV_WALNUT)
            for k in ("geo", "fire", "view"):                                   # header collides (D82); with the glass
                L[k].box(tb[0], tb[1], tb[2], tb[3], z + 2.0, z + 2.5, **({"mat": "pen_wood"} if k == "fire" else {}))
            sign2_quad(L["res0"], [(tb[0] + 0.2, tb[2] - 0.012, z + 2.05), (tb[1] - 0.2, tb[2] - 0.012, z + 2.05),
                                    (tb[1] - 0.2, tb[2] - 0.012, z + 2.45), (tb[0] + 0.2, tb[2] - 0.012, z + 2.45)],
                       (0, -1, 0), "tickets", (0, 2), (tb[0] + 0.2, z + 2.05), (tb[1] - 0.2, z + 2.45))
        sc = (x1 - 5.0, x1 - 0.4, y1 - 2.2, y1 - 1.5)                           # snack counter + popcorn machine
        if clear(zones, sc):
            kitchen_run(L, *sc, z)
            piece(L, (sc[0] + 0.3, sc[0] + 0.9, sc[2] + 0.1, sc[3] - 0.1, z + 0.93, z + 1.6), "paint",
                  DT.paint_uv("terracotta"), pen="metal", res1=False, view=True)                   # popcorn machine collides (D82)
            L["res0"].box(sc[0] + 0.35, sc[0] + 0.85, sc[2] + 0.09, sc[2] + 0.1, z + 1.0, z + 1.5, mat="glassfar", uv=UV_GLASS)
        for i, cell in enumerate(("art_a", "art_b", "art_c", "art_d")):          # film posters on the side walls
            yy = y0 + 2.0 + i * 1.6
            if yy < y1 - 2.6:
                DT.wall_art(Lz, x0, yy, 1.7, 1.0, 1.5, "+x", cell)
                DT.wall_art(Lz, x1, yy, 1.7, 1.0, 1.5, "-x", ("art_d", "art_c", "art_b", "art_a")[i])
        if var == 1 and clear(zones, (cx - 1.6, cx + 1.6, cy - 0.65, cy + 0.45)):    # incl. the control decks (sec L)
            # D86: two arcade cabinets back to back (collide + View like a wardrobe), screens as thin render
            for (ax0, ax1) in ((cx - 1.5, cx - 0.8), (cx + 0.8, cx + 1.5)):
                piece(L, (ax0, ax1, cy - 0.4, cy + 0.4, z, z + 1.8), "paint", DT.paint_uv("slate"), pen="wood", view=True)
                L["res0"].box(ax0 + 0.08, ax1 - 0.08, cy - 0.42, cy - 0.4, z + 1.1, z + 1.55, mat="paint", uv=DT.paint_uv("sage"))
                L["res0"].box(ax0, ax1, cy - 0.6, cy - 0.4, z + 0.9, z + 0.95, mat="paint", uv=DT.paint_uv("terracotta"))   # control deck
        elif var == 2 and clear(zones, (cx - 1.2, cx + 1.2, cy - 0.3, cy + 0.3)):
            # D86: a waiting bench and a cardboard film standee (render-only, 1 cm)
            DT.bench(Lz, cx - 1.2, cx + 0.4, cy - 0.25, cy + 0.2)
            sw = (cx + 0.7, cx + 1.3)
            # two-sided 1 cm board (no one-way sight), the poster on its front face just proud of it
            L["res0"].box(sw[0], sw[1], cy - 0.005, cy + 0.005, z + 0.02, z + 1.85, mat="paint", uv=DT.paint_uv("white"))
            DT.wall_art(Lz, (sw[0] + sw[1]) / 2, cy - 0.006, 0.95, 0.56, 1.75, "-y", "art_b")
        else:
            for (px, py) in ((cx - 1.5, cy), (cx + 1.5, cy)):                   # velvet rope posts
                L["res0"].prism(px, py, 0.05, z, z + 0.95, n=8, mat="metal", uv=DT.UV_ALU)
            bar(L["res0"], (cx - 1.5, cy, z + 0.85), (cx + 1.5, cy, z + 0.8), 0.02, "textile", DT.band_fit("textile", "curtain", 0, 1, 0, 1))
        if lit:
            for gx in (cx - 4.0, cx, cx + 4.0):
                DT.pendant(L, gx, cy, top - 0.02, 1.4, r=0.45)
    elif kind == "auditorium":
        cinema_hall(L, P, r, z, top, lit)
    elif kind == "bar":
        ys = y1                                                                 # back wall line (storage partition)
        cnt = (x0 + 0.8, x1 - 2.6, ys - 1.75, ys - 1.05)
        if clear(zones, cnt):
            kitchen_run(L, *cnt, z)
            for i in range(int((cnt[1] - cnt[0]) / 0.9)):                        # beer taps
                tx = cnt[0] + 0.5 + i * 0.9
                L["res0"].prism(tx, cnt[2] + 0.35, 0.03, z + 0.92, z + 1.3, n=6, mat="metal", uv=DT.UV_ALU)
                L["res0"].box(tx - 0.03, tx + 0.03, cnt[2] + 0.2, cnt[2] + 0.36, z + 1.24, z + 1.3, mat="metal", uv=DT.UV_ALU)
            for i in range(int((cnt[1] - cnt[0]) / 0.75)):                       # stools (visual)
                sx = cnt[0] + 0.4 + i * 0.75
                L["res0"].prism(sx, cnt[2] - 0.45, 0.03, z, z + 0.72, n=6, mat="metal", uv=DT.UV_STEEL)
                L["res0"].prism(sx, cnt[2] - 0.45, 0.2, z + 0.72, z + 0.78, n=10, mat="fabric", uv=UV_FAB["grey"])
            search_point(L, (cnt[0] + cnt[1]) / 2, cnt[2] - 0.7, z)                # behind-the-bar stock (idea 10)
        bb = (x0 + 0.8, x1 - 2.6, ys - 0.4, ys)                                  # back bar: shelves of bottles
        piece(L, bb + (z, z + 0.9), "wood", UV_WALNUT)
        for j, zz in enumerate((z + 1.2, z + 1.6, z + 2.0)):
            L["res0"].box(bb[0], bb[1], bb[2] + 0.1, bb[3], zz - 0.03, zz, mat="wood", uv=UV_WALNUT)
            bottles(L, bb[0] + 0.1, bb[1] - 0.1, bb[2] + 0.25, zz, key=(P.name, j), ruin=P.state == 2)
        bottles(L, bb[0] + 0.1, bb[1] - 0.1, bb[2] + 0.2, z + 0.9, key=(P.name, "top"), ruin=P.state == 2)
        if lit:                                                                 # neon BAR sign + pendants
            sign2_quad(L["res0"], [(cx - 1.4, ys - 0.02, z + 2.4), (cx + 1.0, ys - 0.02, z + 2.4), (cx + 1.0, ys - 0.02, z + 2.9),
                                    (cx - 1.4, ys - 0.02, z + 2.9)], (0, -1, 0), "bar", (0, 2), (cx - 1.4, z + 2.4), (cx + 1.0, z + 2.9))
            for gx in [cnt[0] + 0.8 + i * 1.8 for i in range(int((cnt[1] - cnt[0]) / 1.8))]:
                DT.pendant(L, gx, cnt[2] + 0.35, top - 0.02, 0.9, r=0.18)
        for i in range(2):                                                      # booths on the west wall
            by = y0 + 1.6 + i * 2.4
            if by + 1.2 > cnt[2] - 1.2:
                break
            tbx = (x0 + 0.05, x0 + 0.85, by - 0.4, by + 0.4)
            if clear(zones, tbx):
                table(L, *tbx, z)
                for s_ in (-1, 1):
                    bb2 = (x0 + 0.05, x0 + 1.05, by + s_ * 0.85 - 0.25, by + s_ * 0.85 + 0.25)
                    piece(L, bb2 + (z, z + 0.45), "fabric", UV_FAB["blue"], pen="wood")
                    L["res0"].box(bb2[0], bb2[1], *(sorted((by + s_ * 1.05, by + s_ * 1.1))), z + 0.45, z + 1.15,
                                  mat="fabric", uv=UV_FAB["blue"])
        pt = (cx + 0.3, cx + 2.8, cy - 1.0, cy + 0.4)                            # pool table
        # the original bar keeps its pool table; BarB draws darts or a stage (both bars drew darts by hash alone)
        var = 0 if P.arch == "Bar" else 1 + int(h01(P.name, "bar_var") * 2)
        if var == 1 and clear(zones, pt):
            # D86: darts corner - two pub tables and a dartboard on the east wall
            for (tx0, ty0) in ((pt[0] + 0.1, pt[2] + 0.1), (pt[0] + 1.4, pt[2] + 0.6)):
                table(L, tx0, tx0 + 0.7, ty0, ty0 + 0.7, z)
            if clear(zones, (x1 - 0.1, x1, cy - 0.35, cy + 0.35)):                 # not in a doorway (D84 rule)
                DT.wall_art(Lz, x1, cy, 1.5, 0.45, 0.45, "-x", "art_a")
        elif var == 2 and clear(zones, pt):
            # D86: a low stage (walkable, 0.3 m step) with a mic stand
            piece(L, (pt[0], pt[1], pt[2], pt[3], z, z + 0.3), "wood", UV_OAK)
            mx, my = (pt[0] + pt[1]) / 2, (pt[2] + pt[3]) / 2
            L["res0"].prism(mx, my, 0.015, z + 0.3, z + 1.75, n=6, mat="metal", uv=DT.UV_STEEL)
            L["res0"].prism(mx, my, 0.18, z + 0.3, z + 0.32, n=10, mat="metal", uv=DT.UV_STEEL)
        elif clear(zones, pt):
            piece(L, pt + (z, z + 0.8), "wood", UV_WALNUT)
            L["res0"].hquad(pt[0] + 0.1, pt[1] - 0.1, pt[2] + 0.1, pt[3] - 0.1, z + 0.801, mat="paint", uv=DT.paint_uv("sage"))
            for (qx, qy) in ((pt[0] + 0.1, pt[2] + 0.1), (pt[1] - 0.1, pt[2] + 0.1), (pt[0] + 0.1, pt[3] - 0.1),
                             (pt[1] - 0.1, pt[3] - 0.1), ((pt[0] + pt[1]) / 2, pt[2] + 0.1), ((pt[0] + pt[1]) / 2, pt[3] - 0.1)):
                L["res0"].prism(qx, qy, 0.06, z + 0.79, z + 0.802, n=6, mat="rubble", uv=UV_RUBBLE)
            if lit:
                L["res0"].box(pt[0] + 0.3, pt[1] - 0.3, cy - 0.35, cy - 0.25, top - 0.8, top - 0.7, mat="lamp")
    elif kind == "club_hall":
        DT.wall_art(Lz, cx, y1, 1.6, 1.4, 0.9, "-y", "art_c")                   # team photo
        if lit:
            DT.downlight(L, cx - 3.0, cy, top - 0.02)
            DT.downlight(L, cx + 3.0, cy, top - 0.02)
    elif kind == "changing":
        for (a0, a1, b0, b1) in ((x0 + 0.05, x0 + 0.5, y0 + 0.4, y1 - 2.4), (x0 + 0.5, x1 - 2.4, y1 - 0.5, y1 - 0.05)):
            if clear(zones, (a0, a1, b0, b1)):
                DT.bench(lifted(L, z), a0, a1, b0, b1)
                along_x = (a1 - a0) > (b1 - b0)
                sx_, sy_ = ((a0 + a1) / 2, b0 - 0.8) if along_x else (a1 + 0.8, (b0 + b1) / 2)
                if not P.near_collapse(sx_, sy_, l):                             # D71: no spot in a sealed ruin pocket
                    search_point(L, sx_, sy_, z)                                 # lockers (D65)
                for i in range(int(((a1 - a0) if along_x else (b1 - b0)) / 0.5)):   # coat hooks + kit
                    t = (a0 if along_x else b0) + 0.25 + i * 0.5
                    hx, hy = (t, b1 - 0.02) if along_x else (a0 + 0.02, t)
                    L["res0"].box(hx - 0.02, hx + 0.02, hy - 0.02, hy + 0.02, z + 1.65, z + 1.72, mat="metal", uv=DT.UV_STEEL)
                    if h01(P.name, "kit", round(t, 1), l) < 0.4:
                        band = ("rug_a", "rug_b")[i % 2]
                        if along_x:
                            L["res0"].quad([(hx - 0.2, hy - 0.04, z + 1.0), (hx + 0.2, hy - 0.04, z + 1.0), (hx + 0.2, hy - 0.04, z + 1.68),
                                            (hx - 0.2, hy - 0.04, z + 1.68)], (0, -1, 0), "textile",
                                           DT.band_fit("textile", band, hx - 0.2, hx + 0.2, z + 1.0, z + 1.68, axes=(0, 2)))
        sh = (x1 - 2.2, x1, y1 - 2.2, y1)                                        # shower corner: tiles + heads
        for k in ("res0", "res1"):
            L[k].hquad(sh[0], sh[1], sh[2], sh[3], z + 0.006, mat="tile", uv=UV_TILE)
        L["res0"].box(sh[0], sh[0] + 0.08, sh[2], sh[3] - 0.9, z, z + 2.0, mat="tile", uv=UV_TILE)
        for i in range(3):
            hx = sh[0] + 0.4 + i * 0.6
            L["res0"].box(hx - 0.04, hx + 0.04, sh[3] - 0.25, sh[3] - 0.02, z + 2.0, z + 2.08, mat="metal", uv=DT.UV_ALU)
        L["res0"].box(cx - 0.6, cx + 0.6, y0 + 0.02, y0 + 0.05, z + 1.2, z + 2.0, mat="paint", uv=DT.paint_uv("slate"))   # tactics board
        if lit:
            DT.downlight(L, cx, cy, top - 0.02)
    elif kind in ("play", "nap", "wash"):
        creche_room(L, P, l, r, kind, z, top, zones, lit)
    elif kind == "mall_shop" or kind == "food":
        mall_unit(L, P, l, r, kind, z, top, zones, lit)
    elif kind == "mall_hall":
        mall_gallery(L, P, l, r, z, top, zones, lit)


def cinema_hall(L, P, r, z, top, lit):
    """Raked auditorium: stage + screen + curtains on the foyer wall (audience looks at -y), tiers
    rising to the back with seat rows, side aisle ramps, a cross aisle on top, projection window."""
    x0, x1, y0, y1 = r
    ax = 1.6                                                                     # side aisle width
    t0, t1 = x0 + ax, x1 - ax
    stage = (t0, t1, y0, y0 + 2.4)
    for k in ("res0", "res1", "geo", "view", "fire"):
        L[k].box(*stage, z, z + 0.6, **kw_for(k, "wood", UV_WALNUT, "wood"))
    L["road"].hquad(*stage, z + 0.6, mat="road_int", uv=UV_TILE)
    for tx in (t0 + 0.7, t1 - 0.7):                                              # costume trunks (idea 19)
        for k in ("res0", "res1", "geo", "fire"):
            L[k].box(tx - 0.45, tx + 0.45, y0 + 0.6, y0 + 1.15, z + 0.6, z + 1.12, **kw_for(k, "wood", UV_WALNUT, "wood"))
        L["res0"].box(tx - 0.47, tx + 0.47, y0 + 0.58, y0 + 1.17, z + 1.12, z + 1.16, mat="metal", uv=DT.UV_STEEL)
        L["res0"].quad([(tx - 0.3, y0 + 1.155, z + 0.62), (tx + 0.3, y0 + 1.155, z + 0.62), (tx + 0.3, y0 + 1.155, z + 1.0),
                        (tx - 0.3, y0 + 1.155, z + 1.0)], (0, 1, 0), "textile", DT.band_fit("textile", "curtain", 0, 1, 0, 1))
        search_point(L, tx, y0 + 1.75, z + 0.6)
    ws = y0 - 0.02                                                               # screen on the partition
    sx0, sx1, sz0, sz1 = t0 + 0.8, t1 - 0.8, z + 2.0, z + 7.4
    for k in ("res0", "res1"):
        L[k].quad([(sx0, ws + 0.05, sz0), (sx1, ws + 0.05, sz0), (sx1, ws + 0.05, sz1), (sx0, ws + 0.05, sz1)], (0, 1, 0),
                  "paint", DT.paint_uv("white"))
        for (a, b) in ((sx0 - 0.25, sx0), (sx1, sx1 + 0.25)):
            L[k].box(a, b, ws, ws + 0.06, sz0 - 0.25, sz1 + 0.25, mat="paint", uv=DT.paint_uv("slate"))
        L[k].box(sx0, sx1, ws, ws + 0.06, sz1, sz1 + 0.25, mat="paint", uv=DT.paint_uv("slate"))
    cur = DT.band_fit("textile", "curtain", 0, 1, 0, 1)
    for (a, b) in ((t0 - 0.2, sx0 - 0.25), (sx1 + 0.25, t1 + 0.2)):              # drapes + valance
        for k in ("res0", "res1"):
            L[k].box(a, b, ws + 0.1, ws + 0.4, z + 0.6, sz1 + 0.9, mat="textile", uv=cur)
    for k in ("res0", "res1"):
        L[k].box(t0 - 0.2, t1 + 0.2, ws + 0.1, ws + 0.4, sz1 + 0.3, sz1 + 1.1, mat="textile", uv=cur)
    # tiers: rise 0.25 m per 1.0 m row, from 4.5 m behind the screen wall to the cross aisle
    rise, depth = 0.25, 1.0
    ty0, ty1 = y0 + 4.5, y1 - 1.8
    n = int((ty1 - ty0) / depth)
    ztop = z + n * rise
    seat_uv = DT.paint_uv("terracotta")
    for i in range(n):
        ya, yb = ty0 + i * depth, ty0 + (i + 1) * depth
        zt = z + (i + 1) * rise
        for k in ("res0", "res1", "geo", "view", "fire"):
            kw = kw_for(k, "concrete", UV_REVEAL, "concrete")
            if k.startswith("res"):
                kw["skip"] = ("-z",)
            L[k].box(t0, t1, ya, yb, z, zt, **kw)
        for k in ("res0", "res1"):
            L[k].hquad(t0, t1, ya, yb, zt + 0.004, mat="carpet", uv=UV_CARPET)
        L["road"].hquad(t0, t1, ya, yb, zt, mat="road_int", uv=UV_TILE)
        # seat row at the front of the tier, facing -y (the screen)
        sy0_, sy1_ = ya + 0.05, ya + 0.55
        for k in ("geo", "fire"):
            L[k].box(t0 + 0.2, t1 - 0.2, sy0_, sy1_, zt, zt + 0.45, **({"mat": "pen_wood"} if k == "fire" else {}))
        L["res1"].box(t0 + 0.2, t1 - 0.2, sy0_, sy1_, zt, zt + 0.95, mat="paint", uv=seat_uv, skip=("-z",))
        sxx = t0 + 0.25
        while sxx + 0.5 < t1 - 0.2:
            L["res0"].box(sxx + 0.03, sxx + 0.5, sy0_ + 0.05, sy1_ - 0.08, zt + 0.35, zt + 0.47, mat="paint", uv=seat_uv)
            L["res0"].box(sxx + 0.03, sxx + 0.5, sy1_ - 0.12, sy1_ - 0.02, zt + 0.35, zt + 0.98, mat="paint", uv=seat_uv)
            L["res0"].box(sxx, sxx + 0.03, sy0_ + 0.05, sy1_ - 0.02, zt, zt + 0.65, mat="metal", uv=DT.UV_STEEL)
            sxx += 0.53
        if lit and i % 3 == 0:                                                   # aisle step lights
            for ax_ in (t0 - 0.05, t1 + 0.05):
                L["res0"].box(ax_ - 0.03, ax_ + 0.03, yb - 0.2, yb - 0.1, zt + 0.05, zt + 0.1, mat="lamp")
    # side aisles: flat to the first tier, then a ramp up to the cross aisle
    for (a0, a1) in ((x0, t0), (t1, x1)):
        for k in ("geo", "fire"):
            L[k].wedge(a0, a1, ty0, ty0 + n * depth, z - 0.25, z, ztop, **({"mat": "pen_concrete"} if k == "fire" else {}))
        for k in ("res0", "res1"):
            L[k].ramp(a0, a1, ty0, ty0 + n * depth, z + 0.004, ztop + 0.004, mat="carpet", uv=UV_CARPET)
        L["road"].ramp(a0, a1, ty0, ty0 + n * depth, z, ztop, mat="road_int", uv=UV_TILE)
    cross = (x0, x1, ty0 + n * depth, y1)
    for k in ("res0", "res1", "geo", "view", "fire"):
        kw = kw_for(k, "concrete", UV_REVEAL, "concrete")
        if k.startswith("res"):
            kw["skip"] = ("-z",)
        L[k].box(*cross, z, ztop, **kw)
    L["road"].hquad(*cross, ztop, mat="road_int", uv=UV_TILE)
    for k in ("res0", "res1"):
        L[k].hquad(*cross, ztop + 0.004, mat="carpet", uv=UV_CARPET)
    rail(L, t0, t1, cross[2], cross[2] + 0.06, ztop, h=0.9)                     # rail at the top row
    # projection window high in the back wall
    L["res0"].quad([(-0.9, y1 - 0.01, ztop + 2.4), (0.9, y1 - 0.01, ztop + 2.4), (0.9, y1 - 0.01, ztop + 3.0),
                    (-0.9, y1 - 0.01, ztop + 3.0)], (0, -1, 0), "glassfar", UV_GLASS)
    if lit:
        for yy in (ty0 + 2.0, ty0 + n * depth / 2, ty0 + n * depth - 1.0):
            zz = z + (yy - ty0) / depth * rise + 2.2
            DT.sconce(L, x0, yy, zz, "+x")
            DT.sconce(L, x1, yy, zz, "-x")
        for s_ in (-1, 1):                                                       # green EXIT boxes over the doors
            ex = x0 + 0.8 if s_ < 0 else x1 - 0.8
            L["res0"].box(ex - 0.25, ex + 0.25, y0 + 0.02, y0 + 0.08, z + 2.25, z + 2.45, mat="lamp")


def creche_room(L, P, l, r, kind, z, top, zones, lit):
    x0, x1, y0, y1 = r
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    w, d = x1 - x0, y1 - y0
    Lz = lifted(L, z)
    bands = ("terracotta", "sage", "beige", "white")
    front = cy < (P.stair[2] - 0.9 if P.stair else 0.0)                          # door on y1 (front rooms) or y0
    far0, far1 = (y0 + 0.05, y0 + 0.45) if front else (y1 - 0.45, y1 - 0.05)
    if kind == "play":
        if w > 2.6 and d > 2.6:
            DT.rug(Lz, cx - 1.2, cx + 1.2, cy - 1.0, cy + 1.0, "rug_b")
        tb = (cx - 0.6, cx + 0.6, cy - 0.4, cy + 0.4)
        if w > 3.0 and d > 3.0 and clear(zones, tb):
            table(L, *tb, z, h=0.52)
            for (qx, qy, f) in ((cx - 0.85, cy, "+x"), (cx + 0.85, cy, "-x"), (cx - 0.3, cy - 0.65, "+y"), (cx + 0.3, cy + 0.65, "-y")):
                chair(L, qx, qy, z, f, s=0.65, mat="paint", uv=DT.paint_uv(bands[int(h01(P.name, qx, qy, l) * 4)]))
        sh = (x0 + 0.1, min(x1 - 0.1, x0 + 1.9), far0, far1)                         # low toy shelf (far wall)
        if sh[1] - sh[0] > 1.0 and clear(zones, sh):
            shelf_unit(L, *sh, z, h=1.0)
        for i in range(7):                                                        # scattered toy blocks (visual)
            bx = x0 + 0.6 + (w - 1.2) * h01(P.name, "toy", l, i, round(x0, 1))
            byy = y0 + 0.6 + (d - 1.2) * h01(P.name, "toyy", l, i, round(y0, 1))
            s = 0.08 + 0.06 * h01(P.name, "toys", i)
            L["res0"].box(bx - s, bx + s, byy - s, byy + s, z, z + 2 * s, mat="paint", uv=DT.paint_uv(bands[i % 4]))
        DT.wall_art(Lz, cx, y0 if front else y1, 1.4, min(1.6, w - 0.6), 0.9, "+y" if front else "-y", "art_a")
    elif kind == "nap":
        cot_x = x0 + 0.3
        while cot_x + 0.7 < x1 - 0.3:
            for (b0, b1) in ((y0 + 0.4, y0 + 1.7), (y1 - 1.7, y1 - 0.4)):
                box = (cot_x, cot_x + 0.65, b0, b1)
                if d > 3.6 and clear(zones, box):
                    piece(L, box + (z, z + 0.3), "wood", UV_OAK)
                    L["res0"].box(box[0] + 0.04, box[1] - 0.04, b0 + 0.04, b1 - 0.04, z + 0.3, z + 0.4, mat="fabric",
                                  uv=UV_FAB[("blue", "beige", "grey")[int(h01(P.name, "cot", cot_x, b0) * 3)]])
                    L["res0"].box(box[0], box[1], b1 - 0.04, b1, z + 0.3, z + 0.65, mat="wood", uv=UV_OAK)
            cot_x += 0.95
    elif kind == "wash":
        for k in ("res0", "res1"):
            L[k].hquad(x0, x1, y0, y1, z + 0.006, mat="tile", uv=UV_TILE)
        n = int((w - 0.6) / 0.6)
        tap = (far0, far0 + 0.07) if front else (far1 - 0.07, far1)
        for i in range(n):                                                         # row of low basins (far wall)
            bx = x0 + 0.5 + i * 0.6
            L["res0"].box(bx - 0.22, bx + 0.22, far0, far1, z + 0.45, z + 0.6, mat="paint", uv=DT.paint_uv("white"))
            L["res0"].box(bx - 0.02, bx + 0.02, tap[0], tap[1], z + 0.6, z + 0.75, mat="metal", uv=DT.UV_ALU)
        L["geo"].box(x0 + 0.2, x0 + 0.3 + n * 0.6, far0, far1, z, z + 0.6)
    if lit:
        DT.pendant(L, cx, cy, top - 0.02, 0.5, r=0.25)


def mall_unit(L, P, l, r, kind, z, top, zones, lit):
    """Mall shop unit: rails, display tables, mannequins, counter; top level = food court kitchens.
    Fascia sign and half-down shutter on the gallery side."""
    x0, x1, y0, y1 = r
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    key = (P.name, l, round(cx, 1), round(cy, 1))
    if kind == "food":
        # D87: counters flush to the back / side wall (a 0.2 m slot behind them was a wedge)
        kb = (x0 + 0.3, x1 - 0.3, y1 - 0.72, y1 - 0.02) if (x1 - x0) >= (y1 - y0) else (x0 + 0.02, x0 + 0.72, y0 + 0.3, y1 - 0.3)
        if clear(zones, kb):
            kitchen_run(L, *kb, z)
            if lit:
                L["res0"].box(kb[0], kb[1], kb[2], kb[3], z + 2.0, z + 2.6, mat="lamp")
    else:
        var = int(h01(P.name, l, kind, "var", round(cx, 1), round(cy, 1)) * 3)   # D86: 0 clothes, 1 shoes, 2 phones
        rails_ = 0
        ry = y0 + 1.2
        while ry < y1 - 1.0 and rails_ < (4 if var == 0 else 1):              # the first rail (search spot) always stays
            if clear(zones, (x0 + 0.8, x1 - 0.8, ry - 0.3, ry + 0.3)) and x1 - x0 > 3.0:
                garment_rail(L, x0 + 1.0, min(x1 - 1.0, x0 + 3.4), ry, z, key + (ry,))
                if rails_ == 0 and ry + 0.9 < y1 - 0.3:
                    search_point(L, x0 + 2.0, ry + 0.8, z)                       # costume rail (idea 19)
                rails_ += 1
            ry += 1.6
        tb = (cx - 0.5, cx + 0.5, cy - 0.35, cy + 0.35)
        if var == 1:
            # shoe shop: shelving along the back wall (collides like all shelf_units; boxes = shoe boxes), a fitting bench
            sb = (x0 + 0.4, x1 - 0.4, y1 - 0.4, y1 - 0.05)
            if sb[1] - sb[0] > 1.0 and clear(zones, sb):
                shelf_unit(L, *sb, z, h=1.8)
            if clear(zones, (cx - 0.7, cx + 0.7, cy - 0.25, cy + 0.25)):
                DT.bench(lifted(L, z), cx - 0.7, cx + 0.7, cy - 0.22, cy + 0.22)
        elif var == 2:
            # phone shop: a service counter on the side wall, a display table with handsets
            sc = (x1 - 0.6, x1, y0 + 0.6, min(y1 - 0.6, y0 + 2.6))              # flush to the wall: no wedge gap
            if sc[3] - sc[2] > 1.0 and clear(zones, (sc[0] - 0.6, sc[1], sc[2] - 0.6, sc[3] + 0.6)):   # margin off the shutter (sec L)
                kitchen_run(L, *sc, z)
            if clear(zones, tb):
                table(L, *tb, z, h=0.9)
                for i in range(6):
                    hx = tb[0] + 0.08 + (i % 3) * 0.3
                    hy = cy - 0.2 + (i // 3) * 0.3
                    L["res0"].box(hx, hx + 0.08, hy, hy + 0.15, z + 0.9, z + 0.91, mat="paint", uv=DT.paint_uv("slate"),
                                  skip=("-z",))                                   # underside hidden (perf L)
        elif clear(zones, tb):
            table(L, *tb, z, h=0.8)
            for i in range(4):
                L["res0"].box(tb[0] + 0.05 + i * 0.23, tb[0] + 0.25 + i * 0.23, cy - 0.15, cy + 0.15, z + 0.8, z + 0.86,
                              mat="fabric", uv=UV_FAB[("blue", "beige", "grey", "blue")[i]])
        for i in range(2 if var == 0 else 1):
            mx = x1 - 0.6 - i * 0.7
            my = y0 + 0.6 if (y1 - y0) > 3 else cy
            if var == 2 and x1 - 0.7 < mx + 0.3 and y0 + 0.6 <= my <= y0 + 2.6:
                continue                                                         # the counter stands there
            mannequin(L, mx, my, z, key + (i,))
    if lit:
        DT.downlight(L, cx, cy, top - 0.02)


def mall_gallery(L, P, l, r, z, top, zones, lit):
    """Gallery round the atrium: benches, palm planters, kiosk cart; ground floor: dry fountain
    with weeds; top floor: food-court tables; shop fascias facing the gallery."""
    x0, x1, y0, y1 = r
    at = P.atrium
    if l == 0 and at:                                                             # dry fountain in the atrium
        fx, fy = (at[0] + at[1]) / 2, (at[2] + at[3]) / 2
        for k in ("res0", "res1", "geo", "view", "fire"):
            L[k].prism(fx, fy, 3.0, z, z + 0.5, n=16 if k == "res0" else 8, **kw_for(k, "stone", DT.stone_uv("limestone"), "concrete"))
        L["road"].hquad(fx - 2.1, fx + 2.1, fy - 2.1, fy + 2.1, z + 0.5, mat="road_ext", uv=UV_TILE)
        L["res0"].prism(fx, fy, 2.6, z + 0.5, z + 0.505, n=16, mat="rubble", uv=UV_RUBBLE)
        for k in ("res0", "res1", "geo", "fire"):
            L[k].prism(fx, fy, 0.5, z + 0.5, z + 2.2, n=10 if k == "res0" else 6, **kw_for(k, "stone", DT.stone_uv("limestone"), "concrete"))
        L["res0"].prism(fx, fy, 1.1, z + 2.2, z + 2.35, n=12, mat="stone", uv=DT.stone_uv("limestone"))
        U = {k: v.lod for k, v in L.items()}
        for i in range(6):
            a = 2 * math.pi * i / 6 + 0.3
            plant_tuft(U, fx + 2.0 * math.cos(a), fy + 2.0 * math.sin(a), z + 0.5, 0.7, 0.6,
                       ("weeds", "grass", "dry_grass")[i % 3], (P.name, "ftn", i))
    # palm planters at the atrium corners (every level), benches between
    if at:
        for (px, py) in ((at[0] - 2.2, at[2] + 1.5), (at[1] + 2.2 if l % 2 else at[0] - 2.2, at[3] - 1.5)):
            box = (px - 0.7, px + 0.7, py - 0.7, py + 0.7)
            if clear(zones, box) and not P.in_hole(px, py, l, 1.0):
                for k in ("res0", "res1", "geo", "fire", "view"):
                    L[k].box(*box, z, z + 0.6, **kw_for(k, "stone", DT.stone_uv("granite"), "concrete"))
                L["res0"].prism(px, py, 0.12, z + 0.6, z + 3.4, n=8, mat="wood", uv=UV_WALNUT)
                U = {k: v.lod for k, v in L.items()}
                for i in range(5):
                    a = 2 * math.pi * i / 5
                    p0 = (px, py, z + 3.4)
                    ex, ey = px + 1.3 * math.cos(a), py + 1.3 * math.sin(a)
                    veg_card(U, [(px + 0.1 * math.cos(a), py + 0.1 * math.sin(a), z + 3.0), (ex, ey, z + 2.6),
                                 (ex, ey, z + 3.3), (px + 0.1 * math.cos(a), py + 0.1 * math.sin(a), z + 3.6)],
                             (-math.sin(a), math.cos(a), 0), "shrub")
        top_level = l == len(P.levels) - 1
        for (bx0, bx1) in ((at[0] + 2.0, at[0] + 5.0), (at[1] - 5.0, at[1] - 2.0)):
            by = at[2] - 1.4
            box = (bx0, bx1, by - 0.25, by + 0.25)
            if clear(zones, box) and not P.in_hole((bx0 + bx1) / 2, by, l, 0.8):
                if top_level:
                    table(L, bx0 + 0.6, bx0 + 1.4, by - 0.4, by + 0.4, z)
                    table(L, bx1 - 1.4, bx1 - 0.6, by - 0.4, by + 0.4, z)
                else:
                    DT.bench(lifted(L, z), *box)
    if lit:
        x = x0 + 2.0
        while x < x1 - 1.0:
            for yy in (y0 + 1.5, y1 - 1.5):
                if not P.in_hole(x, yy, l + 1, 0.6):
                    DT.downlight(L, x, yy, top - 0.02, r=0.12)
            x += 4.0


def escalators(L, P, l):
    """Static escalator banks (stopped = stairs) rising from level l through the slab hole of l+1:
    stepped Res0 treads on a steel truss, glass balustrades with black handrails, smooth Roadway
    and Geometry wedge; rails round the hole on the upper deck."""
    for (k, x0, x1, y0, y1) in P.escalators:
        if k == l:
            za, zb = P.levels[k][2], P.levels[k + 1][2]
            for kk in ("geo", "fire", "view"):
                kw = {"mat": "pen_metal"} if kk == "fire" else {}
                L[kk].wedge(x0, x1, y0, y1, za - 0.3, za, zb, **kw)
            L["road"].ramp(x0, x1, y0, y1, za, zb, mat="road_int", uv=UV_TILE)
            n = int(math.ceil((y1 - y0) / 0.4))
            for i in range(n):
                ya, yb = y0 + i * (y1 - y0) / n, y0 + (i + 1) * (y1 - y0) / n
                zt = za + (i + 1) * (zb - za) / n
                L["res0"].box(x0 + 0.12, x1 - 0.12, ya, yb, zt - 0.3, zt, mat="metal", uv=DT.UV_STEEL, skip=("-x", "+x"))
            L["res1"].ramp(x0 + 0.12, x1 - 0.12, y0, y1, za, zb, mat="metal", uv=DT.UV_STEEL)
            for (a0, a1) in ((x0, x0 + 0.12), (x1 - 0.12, x1)):                 # truss sides + balustrades
                verts = [(a0, y0, za - 0.4), (a0, y1, zb - 0.4), (a0, y1, zb + 0.15), (a0, y0, za + 0.15),
                         (a1, y0, za - 0.4), (a1, y1, zb - 0.4), (a1, y1, zb + 0.15), (a1, y0, za + 0.15)]
                faces = [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
                for kk in ("res0", "res1", "res2"):
                    L[kk].solid(verts, faces, mat="metal", uv=DT.UV_PAINT)
                c = (a0 + a1) / 2
                gv = [(c - 0.01, y0, za + 0.15), (c - 0.01, y1, zb + 0.15), (c - 0.01, y1, zb + 1.0), (c - 0.01, y0, za + 1.0),
                      (c + 0.01, y0, za + 0.15), (c + 0.01, y1, zb + 0.15), (c + 0.01, y1, zb + 1.0), (c + 0.01, y0, za + 1.0)]
                for kk in ("geo", "fire"):
                    L[kk].solid(gv, faces, **({"mat": "pen_glass"} if kk == "fire" else {}))
                if P.state < 2:
                    L["res0"].quad([gv[0], gv[1], gv[2], gv[3]], (1, 0, 0), "glass", UV_GLASS, double=True)
                bar(L["res0"], (c, y0 - 0.3, za + 1.0), (c, y1 + 0.3, zb + 1.0), 0.04, "rubble", UV_RUBBLE)
        if k + 1 == l:                                                          # rails round the hole on the upper deck
            z0 = P.levels[l][2]
            rail(L, x0 - 0.06, x0, y0, y1, z0, glass=P.state < 2)
            rail(L, x1, x1 + 0.06, y0, y1, z0, glass=P.state < 2)
            rail(L, x0 - 0.06, x1 + 0.06, y0 - 0.06, y0, z0, glass=P.state < 2)


def skylight(L, P):
    """Glass barrel vault over the atrium hole in the roof slab: steel ribs every 2 m, glazed bays
    (Res0 / Res1), opaque far LODs; a flat glass deck in Geometry / Fire keeps the roof closed."""
    if not (P.A.get("skylight") and P.atrium):
        return
    x0, x1, y0, y1 = P.atrium
    top = P.top
    rise, nseg = 2.6, 8
    pts = [(x0 + (x1 - x0) * i / nseg, top + 0.2 + rise * math.sin(math.pi * i / nseg)) for i in range(nseg + 1)]
    ribs = [y0 + i * 2.0 for i in range(int((y1 - y0) / 2.0) + 1)]
    for yy in ribs:
        for (a, b) in zip(pts, pts[1:]):
            bar(L["res0"], (a[0], yy, a[1]), (b[0], yy, b[1]), 0.06, "metal", DT.UV_PAINT)
    for (a, b) in zip(pts, pts[1:]):
        q = [(a[0], y0, a[1]), (b[0], y0, b[1]), (b[0], y1, b[1]), (a[0], y1, a[1])]
        if P.state < 2:
            L["res0"].quad(q, (0, 0, 1), "glass", UV_GLASS, double=True)
            L["res1"].quad(q, (0, 0, 1), "glass", UV_GLASS, double=True)
        L["res2"].quad(q, (0, 0, 1), "glassfar", UV_GLASS)
        if P.state == 2:                                                         # ruin: only a few panes left
            L["res0"].quad(q, (0, 0, 1), "metal", DT.UV_STEEL) if h01(P.name, "sky", a[0]) < 0.2 else None
    for (yy, nrm) in ((y0, -1), (y1, 1)):                                        # gable ends
        for (a, b) in zip(pts, pts[1:]):
            tri = [(a[0], yy, top + 0.2), (b[0], yy, top + 0.2), (b[0], yy, b[1]), (a[0], yy, a[1])]
            if P.state < 2:
                L["res0"].quad(tri, (0, nrm, 0), "glass", UV_GLASS, double=True)
    for k in ("res0", "res1", "res2", "geo", "fire", "view"):                   # kerb round the opening
        for (a0, a1, b0, b1) in ((x0 - 0.3, x1 + 0.3, y0 - 0.3, y0), (x0 - 0.3, x1 + 0.3, y1, y1 + 0.3),
                                 (x0 - 0.3, x0, y0, y1), (x1, x1 + 0.3, y0, y1)):
            L[k].box(a0, a1, b0, b1, top, top + 0.2, **kw_for(k, "concrete", UV_REVEAL, "concrete"))
    for k in ("geo", "fire"):
        L[k].box(x0, x1, y0, y1, top + 0.15, top + 0.2, **({"mat": "pen_glass"} if k == "fire" else {}))
    L["res3"].box(x0, x1, y0, y1, top, top + 0.2 + rise, mat="glassfar", uv=UV_GLASS, skip=("-z",))


def marquee(L, P):
    """Cinema front: canopy marquee with a bulb frame and the KINO fascia, vertical blade sign,
    poster cases either side of the door."""
    hd = P.hd
    zc = 4.0
    y = -hd
    for k in ("res0", "res1", "res2", "geo", "fire", "view", "shadow"):
        L[k].box(-5.5, 5.5, y - 2.6, y, zc, zc + 0.7, **kw_for(k, "metal", DT.UV_PAINT, "metal"))
    sign2_quad(L["res0"], [(-5.3, y - 2.61, zc + 0.08), (5.3, y - 2.61, zc + 0.08), (5.3, y - 2.61, zc + 0.62),
                            (-5.3, y - 2.61, zc + 0.62)], (0, -1, 0), P.A.get("marquee", "kino"), (0, 2), (-5.3, zc + 0.08), (5.3, zc + 0.62))
    sign2_quad(L["res1"], [(-5.3, y - 2.61, zc + 0.08), (5.3, y - 2.61, zc + 0.08), (5.3, y - 2.61, zc + 0.62),
                            (-5.3, y - 2.61, zc + 0.62)], (0, -1, 0), P.A.get("marquee", "kino"), (0, 2), (-5.3, zc + 0.08), (5.3, zc + 0.62))
    if P.state == 0:                                                              # bulbs round the canopy edge
        for i in range(23):
            bx = -5.4 + i * 10.8 / 22
            L["res0"].prism(bx, y - 2.62, 0.04, zc - 0.06, zc, n=6, mat="lamp")
            L["res0"].prism(bx, y - 2.62, 0.04, zc + 0.7, zc + 0.76, n=6, mat="lamp")
        for i in range(10):
            by = y - 2.5 + i * 0.25
            for bx in (-5.52, 5.52):
                L["res0"].prism(bx, by, 0.04, zc + 0.3, zc + 0.36, n=6, mat="lamp")
    for x_ in (-4.5, 4.5):                                                        # canopy hangers
        bar(L["res0"], (x_, y - 2.4, zc + 0.7), (x_, y - 0.02, zc + 2.4), 0.03, "metal", DT.UV_STEEL)
    bx, bz0, bz1 = P.hw - 1.2, 4.9, P.top - 0.6                                    # vertical blade sign on the corner
    for k in ("res0", "res1", "res2"):
        L[k].box(bx - 0.6, bx + 0.6, y - 0.9, y - 0.1, bz0, bz1, mat="metal", uv=DT.UV_PAINT)
    for s_ in (-1, 1):
        xx = bx + s_ * 0.61
        sign2_quad(L["res0"], [(xx, y - 0.85, bz0 + 0.1), (xx, y - 0.15, bz0 + 0.1), (xx, y - 0.15, bz1 - 0.1),
                                (xx, y - 0.85, bz1 - 0.1)], (s_, 0, 0), P.A.get("marquee", "kino"), (2, 1), (bz0 + 0.1, y - 0.85), (bz1 - 0.1, y - 0.15))
    for x_ in (-3.6, 3.6):                                                        # poster cases
        for k in ("res0", "res1"):
            L[k].box(x_ - 0.6, x_ + 0.6, y - 0.12, y, 0.6, 2.4, mat="metal", uv=DT.UV_ALU)
        u0, v0, u1, v1 = S.atlas_uv(("art_a" if x_ < 0 else "art_b"))
        L["res0"].quad([(x_ - 0.5, y - 0.125, 0.7), (x_ + 0.5, y - 0.125, 0.7), (x_ + 0.5, y - 0.125, 2.3), (x_ - 0.5, y - 0.125, 2.3)],
                       (0, -1, 0), "atlas", UVRect(0, 2, (x_ - 0.5, 0.7), (x_ + 0.5, 2.3), (u0, v0, u1, v1)))


def creche_mural(L, P):
    """Faded Soviet tile mural on the blank east gable of the kindergarten: a sun with 16 rays over
    rolling hills (triangle mosaic, Res0; a simple disc and band in Res1)."""
    x = P.hw + 0.012
    cy, cz = 0.0, P.top * 0.62
    cols = ("terracotta", "beige", "sage", "white")
    n = 16
    for i in range(n):
        a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 0.5) / n
        r0, r1 = 0.95, 2.1 + 0.4 * (i % 2)
        tri = [(x, cy + r0 * math.cos((a0 + a1) / 2), cz + r0 * math.sin((a0 + a1) / 2)),
               (x, cy + r1 * math.cos(a0), cz + r1 * math.sin(a0)), (x, cy + r1 * math.cos(a1), cz + r1 * math.sin(a1))]
        L["res0"].quad(tri, (1, 0, 0), "paint", DT.paint_uv(cols[i % 2]))
    for i in range(12):                                                          # sun disc (fan)
        a0, a1 = 2 * math.pi * i / 12, 2 * math.pi * (i + 1) / 12
        tri = [(x + 0.002, cy, cz), (x + 0.002, cy + 0.85 * math.cos(a0), cz + 0.85 * math.sin(a0)),
               (x + 0.002, cy + 0.85 * math.cos(a1), cz + 0.85 * math.sin(a1))]
        L["res0"].quad(tri, (1, 0, 0), "paint", DT.paint_uv("beige"))
    for j, (h0, col) in enumerate(((0.5, "sage"), (0.9, "white"))):              # hills
        pts = [(x + 0.001 * (j + 1), -P.hd + 0.6 + 2.0 * i, P.top * 0.18 + h0 + 0.5 * math.sin(i * 1.3 + j)) for i in range(int((P.D - 1.2) / 2.0) + 1)]
        for a, b2 in zip(pts, pts[1:]):
            L["res0"].quad([(a[0], a[1], P.top * 0.18), (b2[0], b2[1], P.top * 0.18), (b2[0], b2[1], b2[2]), (a[0], a[1], a[2])],
                           (1, 0, 0), "paint", DT.paint_uv(col))
    for i in range(12):
        a0, a1 = 2 * math.pi * i / 12, 2 * math.pi * (i + 1) / 12
        L["res1"].quad([(x, cy, cz), (x, cy + 1.6 * math.cos(a0), cz + 1.6 * math.sin(a0)),
                        (x, cy + 1.6 * math.cos(a1), cz + 1.6 * math.sin(a1))], (1, 0, 0), "paint", DT.paint_uv("terracotta"))


def playground(L, P):
    """Kindergarten forecourt: low fence with a gate gap, rusty swings, slide, sandbox, merry-go-round."""
    hd = P.hd
    fx0, fx1, fy0 = P.fx0, P.fx1, P.fy0
    rust = UVBand(S.MATERIALS["rust"]["bands"]["rust"], 1.0)
    green = UVBand(S.MATERIALS["rust"]["bands"]["green"], 1.0)
    gap = (P.entry[0] - 0.6, P.entry[1] + 0.6)
    for (a, b) in ((fx0 + 0.1, gap[0]), (gap[1], fx1 - 0.1)):
        rail(L, a, b, fy0 + 0.06, fy0 + 0.12, 0.0, h=0.9)
    for sx in (fx0 + 0.06, fx1 - 0.12):
        rail(L, sx, sx + 0.06, fy0 + 0.12, -hd - 0.1, 0.0, h=0.9)
    # swings (west): A-frames + beam (collide), two seats on chains (visual)
    sx0, sx1, sy = fx0 + 1.5, fx0 + 5.5, (fy0 - hd) / 2
    for xx in (sx0, sx1):
        for s_ in (-1, 1):
            bar(L["res0"], (xx, sy + s_ * 0.9, 0.0), (xx, sy, 2.4), 0.05, "rust", green)
            bar(L["res1"], (xx, sy + s_ * 0.9, 0.0), (xx, sy, 2.4), 0.05, "rust", green)
        for k in ("geo", "fire"):
            L[k].box(xx - 0.06, xx + 0.06, sy - 0.9, sy + 0.9, 0.0, 0.3, **({"mat": "pen_metal"} if k == "fire" else {}))
    bar(L["res0"], (sx0, sy, 2.4), (sx1, sy, 2.4), 0.06, "rust", green)
    for i, cxs in enumerate((sx0 + 1.2, sx1 - 1.2)):
        swing = 0.2 * (h01(P.name, "swing", i) - 0.5)
        for dx in (-0.25, 0.25):
            bar(L["res0"], (cxs + dx, sy, 2.38), (cxs + dx, sy + swing, 0.5), 0.008, "metal", DT.UV_STEEL)
        L["res0"].box(cxs - 0.3, cxs + 0.3, sy + swing - 0.12, sy + swing + 0.12, 0.45, 0.5, mat="rust", uv=rust)
    # slide (east): ladder tower + chute (collide as one block + wedge)
    tx, ty = fx1 - 3.0, (fy0 - hd) / 2
    for k in ("res0", "res1", "geo", "fire", "view"):
        L[k].box(tx - 0.5, tx + 0.5, ty - 0.5, ty + 0.5, 1.4, 1.5, **kw_for(k, "rust", green, "metal"))
    for (a, b) in ((tx - 0.5, ty - 0.5), (tx + 0.5, ty - 0.5), (tx - 0.5, ty + 0.5), (tx + 0.5, ty + 0.5)):
        for k in ("res0", "res1", "geo", "fire"):
            L[k].box(a - 0.04, a + 0.04, b - 0.04, b + 0.04, 0.0, 1.4, **kw_for(k, "rust", green, "metal"))
    chute = [(tx + 0.5, ty - 0.3, 1.45), (tx + 2.4, ty - 0.3, 0.25), (tx + 2.4, ty + 0.3, 0.25), (tx + 0.5, ty + 0.3, 1.45)]
    L["res0"].quad(chute, (0.55, 0, 0.83), "metal", DT.UV_ALU, double=True)
    L["res1"].quad(chute, (0.55, 0, 0.83), "metal", DT.UV_ALU, double=True)
    for i in range(5):
        L["res0"].box(tx - 0.95, tx - 0.5, ty - 0.25, ty + 0.25, 0.25 + i * 0.27, 0.29 + i * 0.27, mat="metal", uv=DT.UV_STEEL)
    # sandbox + merry-go-round in the middle
    sbx, sby = -1.0 if P.entry[0] > 1.0 else -6.0, fy0 + 1.6
    for (a0, a1, b0, b1) in ((sbx - 1.2, sbx + 1.2, sby - 1.2, sby - 1.05), (sbx - 1.2, sbx + 1.2, sby + 1.05, sby + 1.2),
                             (sbx - 1.2, sbx - 1.05, sby - 1.05, sby + 1.05), (sbx + 1.05, sbx + 1.2, sby - 1.05, sby + 1.05)):
        for k in ("res0", "res1", "geo", "fire"):
            L[k].box(a0, a1, b0, b1, 0.0, 0.3, **kw_for(k, "wood", UV_OAK, "wood"))
    L["res0"].hquad(sbx - 1.05, sbx + 1.05, sby - 1.05, sby + 1.05, 0.2, mat="paint", uv=DT.paint_uv("beige"))
    mx, my = fx1 - 7.5, fy0 + 1.8
    for k in ("res0", "res1", "geo", "fire"):
        L[k].prism(mx, my, 1.0, 0.0, 0.2, n=12 if k == "res0" else 8, **kw_for(k, "rust", rust, "metal"))
    for a in range(4):
        ang = math.pi / 2 * a + 0.4
        bar(L["res0"], (mx, my, 0.9), (mx + 0.9 * math.cos(ang), my + 0.9 * math.sin(ang), 0.2), 0.025, "rust", green)
    U = {k: v.lod for k, v in L.items()}
    for i in range(8):                                                           # weeds through the playground
        px = fx0 + 0.8 + (fx1 - fx0 - 1.6) * h01(P.name, "pgw", i)
        py = fy0 + 0.5 + (-hd - fy0 - 1.0) * h01(P.name, "pgwy", i)
        plant_tuft(U, px, py, 0.0, 0.6, 0.5, ("grass", "weeds", "dry_grass")[i % 3], (P.name, "pg", i))


def hanged(L, P, r, z, top):
    """Hanged church (idea 12): shrouded bodies hang from ropes off the trusses along both sides of
    the aisle (feet ~2 m up, out of reach; visual only), candles on the altar step, toppled pews."""
    x0, x1, y0, y1 = r
    rope = UVBand(S.MATERIALS["wood"]["bands"]["oak"], 1.0)
    n = 0
    yy = y0 + 4.0
    while yy < y1 - 5.0 and n < 7:
        xx = (-2.1 if n % 2 else 2.1) + 0.3 * (h01(P.name, "hx", n) - 0.5)
        zf = z + 2.0 + 0.4 * h01(P.name, "hz", n)
        bar(L["res0"], (xx, yy, top - 0.3), (xx, yy, zf + 1.85), 0.012, "wood", rope)
        # shrouded figure: lofted rings feet -> knees -> hips -> shoulders -> neck -> head (burlap shroud)
        prof = [(0.0, 0.07, 0.06), (0.45, 0.10, 0.08), (0.85, 0.15, 0.11), (1.35, 0.19, 0.12), (1.45, 0.07, 0.06),
                (1.52, 0.10, 0.09), (1.72, 0.09, 0.08), (1.78, 0.03, 0.03)]
        tilt = 0.06 * (h01(P.name, "tilt", n) - 0.5)
        for (za, ra, rb), (zb, rc, rd) in zip(prof, prof[1:]):
            ring_a = [(xx + tilt * za + ra * math.cos(2 * math.pi * k / 8), yy + rb * math.sin(2 * math.pi * k / 8), zf + za) for k in range(8)]
            ring_b = [(xx + tilt * zb + rc * math.cos(2 * math.pi * k / 8), yy + rd * math.sin(2 * math.pi * k / 8), zf + zb) for k in range(8)]
            L["res0"].solid(ring_a + ring_b, [tuple(range(8)), tuple(range(8, 16))] +
                            [(k, (k + 1) % 8, 8 + (k + 1) % 8, 8 + k) for k in range(8)], mat="fabric", uv=UV_FAB["beige"])
        for zz in (zf + 0.5, zf + 1.0, zf + 1.4):                                # rope bindings round the shroud
            L["res0"].prism(xx + tilt * (zz - zf), yy, 0.16 if zz < zf + 1.2 else 0.08, zz, zz + 0.03, n=8, mat="wood", uv=rope)
        L["res1"].box(xx - 0.15, xx + 0.15, yy - 0.12, yy + 0.12, zf, zf + 1.75, mat="fabric", uv=UV_FAB["beige"])
        yy += 2.2
        n += 1
    for i in range(14):                                                          # candles on the chancel step
        cx_ = -1.6 + 3.2 * h01(P.name, "cnd", i)
        cy_ = y1 - 2.8 + 0.3 * h01(P.name, "cndy", i)
        hh = 0.1 + 0.25 * h01(P.name, "cndh", i)
        L["res0"].prism(cx_, cy_, 0.025, z + 0.3, z + 0.3 + hh, n=6, mat="paint", uv=DT.paint_uv("white"))
        L["res0"].prism(cx_, cy_, 0.008, z + 0.3 + hh, z + 0.33 + hh, n=4, mat="lamp")


def memory(L, P):
    m = L["mem"].lod
    if P.A.get("light") == "hyper":                                              # 4 points over the sales hall (D61)
        for i, (fx, fy) in enumerate(((-0.25, -0.3), (0.25, -0.3), (-0.25, 0.15), (0.25, 0.15))):
            m.point("light_%d" % (i + 1), (fx * P.W, fy * P.D, P.levels[0][1] - SLAB - 1.3))
        m.point("entrance", ((P.entry[0] + P.entry[1]) / 2, -P.hd - 1.0, 0.0))
        return
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
    m.point("entrance", ((P.entry[0] + P.entry[1]) / 2, -P.hd - 1.0, 0.0))


def comp_boxes(lod):
    out = []
    for g, v in lod.groups.items():
        if g.startswith("Component"):
            pts = [lod.verts[i] for i in v]
            out.append(tuple(f(p[j] for p in pts) for j in range(3) for f in (min, max)))
    return out


def wedge_slots(bx, P, lo=0.15, hi=0.6, run=1.0, height=0.5):
    """D87: floor-standing collision boxes facing each other across a lo..hi m gap over more than `run` m, nothing
    else in the gap: a slot a player wedges into (and AI cannot path). Gaps under lo are flush, over hi walkable.
    Returns (gap, run, box a, box b) with boxes rounded for reports; test_city fails on any."""
    levels = [z for (_u, _f, z) in P.levels] + ([P.top] if getattr(P, "top", None) is not None else [])   # D89: roof gear too
    out = []
    for i, a in enumerate(bx):
        for b in bx[i + 1:]:
            for ax in (0, 1):
                o = 1 - ax
                g1, g2 = b[2 * ax] - a[2 * ax + 1], a[2 * ax] - b[2 * ax + 1]
                g = g1 if g1 > 0 else g2
                if not (lo < g < hi):
                    continue
                ol, oh = max(a[2 * o], b[2 * o]), min(a[2 * o + 1], b[2 * o + 1])
                zl, zh = max(a[4], b[4]), min(a[5], b[5])
                if oh - ol < run:
                    continue
                g0, g1_ = (a[2 * ax + 1], b[2 * ax]) if g1 > 0 else (b[2 * ax + 1], a[2 * ax])
                pocket = False
                if zh - zl < height:
                    # D93 prone pocket: low sides, but boxes over the gap below 1.4 m (a body slides in lying down or
                    # crouched and cannot stand up). Sec review: covers may be partial (>= 0.2 m of the gap width, or
                    # all of a narrower gap), split into several boxes (their spans along the run are merged), angled
                    # (bounding box), and dip up to 5 cm below the side tops.
                    if zh - zl < 0.1:
                        continue
                    need = min(0.2, g1_ - g0) - 0.01
                    cov = sorted((max(ol, c[2 * o]), min(oh, c[2 * o + 1])) for c in bx
                                 if c is not a and c is not b and zh - 0.05 <= c[4] < zl + 1.4
                                 and min(g1_, c[2 * ax + 1]) - max(g0, c[2 * ax]) >= need
                                 and c[2 * o] < oh and c[2 * o + 1] > ol)
                    covered, cur = 0.0, ol
                    for (c0, c1) in cov:                                         # union length along the run
                        c0 = max(c0, cur)
                        if c1 > c0:
                            covered += c1 - c0
                            cur = c1
                    if covered < run:
                        continue
                    pocket = True
                # something to stand on under the gap - a floor level or (D90) a plinth / deck / stage top - at most
                # 0.1 m above zl and less than 0.45 m below it (one box on a low plinth beside a floor box: D90 sec L)
                sup = [z for z in levels if z <= zl + 0.1] + [
                    c[5] for c in bx if c[5] <= zl + 0.1 and c[2 * ax] < g1_ and c[2 * ax + 1] > g0
                    and c[2 * o] < oh and c[2 * o + 1] > ol]
                if not sup or zl - max(sup) >= 0.45:
                    continue
                # D89 (sec review L): what fills the gap is cut out of the run; a thin post no longer hides a long slot
                fill = sorted((max(ol, c[2 * o]), min(oh, c[2 * o + 1])) for c in bx
                              if c is not a and c is not b and c[2 * ax] < g1_ - 0.01 and c[2 * ax + 1] > g0 + 0.01
                              and c[2 * o] < oh and c[2 * o + 1] > ol and c[4] < zh - (0.05 if pocket else 0.0)
                              and c[5] > zl)                                    # a pocket's own cover is not fill
                best, cur = (0.0, ol, oh), ol
                for (f0, f1) in fill + [(oh, oh)]:
                    if f0 - cur > best[0]:
                        best = (f0 - cur, cur, f0)
                    cur = max(cur, f1)
                if best[0] < run:
                    continue
                ol, oh = best[1], best[2]
                out.append((round(g, 2), round(oh - ol, 2), tuple(round(v, 2) for v in a), tuple(round(v, 2) for v in b),
                            (ax, g0, g1_, ol, oh, zl, zh)))
    return out


def close_slots(L, P):
    """D87: in ruins, rubble lands next to surviving furniture and walls and leaves wedge slots; fill each with a
    rubble block (collides, renders as rubble) up to the lower of the two neighbours - debris spills into the gap."""
    for _ in range(3):
        sl = wedge_slots(comp_boxes(L["geo"].lod), P)
        if not sl:
            return
        for (_g, _r, _a, _b, (ax, g0, g1, ol, oh, zl, zh)) in sl:
            box = (g0, g1, ol, oh) if ax == 0 else (ol, oh, g0, g1)
            for k in ("res0", "res1", "geo", "fire", "view"):
                L[k].lod.box(*box, zl, zh, **kw_for(k, "rubble", UV_RUBBLE, "concrete"))


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
                ok = ok and not P.collapsed(x, y, l) and not P.near_collapse(x, y, l) and not P.in_hole(x, y, l, 0.5, False)
                ok = ok and not (P.yard and P.yard[0] - 0.5 <= x <= P.yard[1] + 0.5 and P.yard[2] - 0.5 <= y <= P.yard[3] + 0.5)
                ok = ok and not any(r[1] - 0.6 <= x <= r[2] + 0.6 and r[3] - 0.6 <= y <= r[4] + 0.6 and r[0] == l
                                    for r in P.ramps)
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
    sides = ("S", "N", "W", "E") + (("iS", "iN", "iW", "iE") if P.yard else ())
    for l in range(len(P.levels)):
        for key in sides:
            sd, ops = facade(L, P, key, l)
            facade_level_extras(L, P, sd, l, ops)
        interior(L, P, l)
        cells_bars(L, P, l)
        level_features(L, P, l)
    stairs(L, P)
    front_door(L, P)
    roof(L, P)
    forecourt(L, P)
    landmark(L, P)
    bell_tower(L, P)
    ruin_extras(L, P)
    if P.state == 2:
        close_slots(L, P)                                                      # D87 wedge slots next to rubble
    dress(L, P)
    memory(L, P)
    geo = L["geo"].lod
    geo.props.update({"class": "house", "map": "building", "autocenter": "0"})
    geo.mass = 15000.0 + 6000.0 * len(P.levels)
    LOOT_OUT["Land_SKY_" + P.name] = loot_points(L, P)
    macro_variant(L, P)
    for k in ("res0", "res1"):                     # D96: interior faces go to proxy parts first when a LOD is over budget
        lod = L[k].lod
        zt = max(v[2] for v in lod.verts) if lod.verts else 0.0
        lod.proxy_hint = (lambda c, zt=zt: not is_outer(P, c, zt))
    ext = exterior_lod(L, P)
    strip_faces(L["res1"].lod, "glassvoid")                                   # far-LOD-only voids (see window())
    if P.A["skin"][0] == "open":                                              # open decks: no "exterior"
        return [v.lod for v in L.values()]
    mid = far_mid_lod(ext, L["res2"].lod, P)
    if (mid is None and _tris(ext) > EXT_MAX * _tris(L["res1"].lod)          # D90 perf: no near-copy of Res1 (kept when
            and _tris(L["res2"].lod) >= 0.05 * _tris(L["res1"].lod)):         # a Res 1.75 follows, or Res1 -> Res2 < 5 %)
        return [v.lod for v in L.values()]
    return [v.lod for v in L.values()] + [ext] + ([mid] if mid else [])


def strip_faces(lod, mat):
    """Drop every face of material `mat`, compacting the vertices and selections."""
    faces = [f for f in lod.faces if f[1] != mat]
    if len(faces) == len(lod.faces):
        return
    used = sorted({i for idx, _m, _u in faces for i in idx})
    remap = {o: n for n, o in enumerate(used)}
    lod.vprim = [lod.vprim[i] if i < len(lod.vprim) else -1 for i in used]
    lod.verts = [lod.verts[i] for i in used]
    lod.faces = [(tuple(remap[i] for i in idx), m, uv) for idx, m, uv in faces]
    lod.groups = {g: {remap[i] for i in vs if i in remap} for g, vs in lod.groups.items()}
    lod.groups = {g: vs for g, vs in lod.groups.items() if vs}


EXT_BAND = 0.9      # m: faces within this of the outer walls / yard walls (or in the roof zone) are exterior
EXT_ROOF = 2.5      # m below the highest point: parapets, roof plant, skylights
# far-LOD rule (check_assets: no blended alpha from Res2 on): blended decals dropped (the grime macro covers that range),
# clear glass swapped for the opaque far glass; alpha-TESTED materials (gen_configs.ALPHA_TEST) stay
EXT_DROP = {"decal_grime", "decal_dirt"}
EXT_SWAP = {"glass": "glassfar", "glassvoid": "glassfar"}


def is_outer(P, c, ztop):
    """Face centroid c in the exterior band: near the footprint walls / the yard walls, or in the roof zone."""
    x0, x1, y0, y1 = -P.hw, P.hw, -P.hd, P.hd
    cx, cy, cz = c
    outer = min(cx - x0, x1 - cx, cy - y0, y1 - cy) < EXT_BAND or cz > ztop - EXT_ROOF
    yard = getattr(P, "yard", None)
    if not outer and yard:
        yx0, yx1, yy0, yy1 = yard[:4]
        outer = (yx0 - EXT_BAND < cx < yx1 + EXT_BAND and yy0 - EXT_BAND < cy < yy1 + EXT_BAND
                 and not (yx0 + EXT_BAND < cx < yx1 - EXT_BAND and yy0 + EXT_BAND < cy < yy1 - EXT_BAND))
    return outer


def exterior_lod(L, P):
    """Full audit (ASSET_QUALITY_GUIDE section 6: each LOD ~40-60 % of the previous): Res1 still carries the whole
    interior, invisible at the range where the far shell takes over, so the chain dropped 30 % -> 3 %. This
    resolution-1.5 LOD is Res1's exterior only - outer facades, roof zone and (courtyard blocks) the yard facades -
    with the door selections kept so doors still animate. Typically 35-60 % of Res1."""
    from skygeo import Lod
    r1 = L["res1"].lod
    ext = Lod("res1x", LOD_RES, 1.5)
    if not r1.verts:
        return ext
    zs = [v[2] for v in r1.verts]
    ztop = max(zs)
    # D90 fix: the band is measured from the footprint walls, not the vertex extremes - canopies, awnings, signs and
    # AC units stand proud of the facade and pushed the real wall out of the band (front facades went missing)
    remap = {}
    for idx, mat, uv in r1.faces:
        pts = [r1.verts[i] for i in idx]
        outer = is_outer(P, [sum(p[k] for p in pts) / len(pts) for k in range(3)], ztop)
        outer = outer or mat == "rubble"                 # D90: collapse debris is the ruin's silhouette (no see-through)
        if not outer or mat in EXT_DROP:
            continue
        mat = EXT_SWAP.get(mat, mat)
        nidx = []
        for i in idx:
            if i not in remap:
                remap[i] = ext.copy_vert(r1, i)
            nidx.append(remap[i])
        ext.faces.append((tuple(nidx), mat, uv))
    for g, vs in r1.groups.items():                      # door selections (model.cfg animations), kept verts only
        kept = {remap[i] for i in vs if i in remap}
        if kept:
            ext.groups[g] = kept
    return ext


def _tris(lod):
    return sum(len(i) - 2 for i, _m, _u in lod.faces)


def _area(pts):
    import numpy as np
    p = np.asarray(pts, float)
    return 0.5 * float(np.linalg.norm(sum(np.cross(p[0] - p[k], p[0] - p[k + 1]) for k in range(1, len(p) - 1))))


EXT_MAX = 0.85      # D90 perf review: a Res 1.5 holding > 85 % of Res1 (small buildings) is dropped - memory for nothing
MID_STEP = 7.0      # a Res 1.75 LOD where Res 1.5 has more than 7x the triangles of Res 2 (D90: P58 step warnings)...
MID_MIN = 3000      # ...and at least this many (small buildings: a 6th LOD saves too little)
MID_TARGET = 0.25   # ...holding about a quarter of Res 1.5: its large faces (walls, slabs, glass, roof); trims and gear go
MID_TARGET_BIG = 0.15   # Res 1.5 over 10 k tris: a sixth, so the step on to Res 2 stays >= ~20 %


SHELL_DEPTH = 0.4   # m: faces parallel to a wall plane within this of it (recessed glass, boards, shutters) are shell


def _on_shell(pts, P):
    """Face parallel to an outer wall plane (or a yard wall plane) and within SHELL_DEPTH of it: the wall itself and
    what fills its openings (recessed glass, boards, shutters) - the silhouette, never dropped from far LODs."""
    planes = [(0, -P.hw), (0, P.hw), (1, -P.hd), (1, P.hd)]
    if getattr(P, "yard", None):
        yx0, yx1, yy0, yy1 = P.yard[:4]
        planes += [(0, yx0), (0, yx1), (1, yy0), (1, yy1)]
    for a, c in planes:
        v = [p[a] for p in pts]
        if max(v) - min(v) < 0.01 and abs(v[0] - c) < SHELL_DEPTH:
            return True
    return False


def far_mid_lod(ext, r2, P):
    """D90: the 3 largest buildings stepped from a 8-14 k-tri Res 1.5 to a 300-700-tri Res 2 (< 5 %, popping risk,
    P58). This resolution-1.75 LOD keeps the Res 1.5 faces whose area is above a cut-off searched so that about
    MID_TARGET of the triangles stay - the broad planes that carry the silhouette; frames, cornices, plant and
    clutter drop out. Faces in the outer / yard wall planes are always kept (small piers between windows would
    leave holes). Door selections are kept for the kept vertices. None where the step is already gentle."""
    from skygeo import Lod
    t1, t2 = _tris(ext), max(1, _tris(r2))
    if t1 <= MID_STEP * t2 or (t1 < MID_MIN and t1 <= 20 * t2):       # small but a < 5 % step: still needed
        return None
    target = MID_TARGET_BIG if t1 > 10000 else MID_TARGET
    areas = [_area([ext.verts[i] for i in idx]) for idx, _m, _u in ext.faces]
    tri = [len(idx) - 2 for idx, _m, _u in ext.faces]
    shell = {k for k, (idx, _m, _u) in enumerate(ext.faces) if _on_shell([ext.verts[i] for i in idx], P)}
    order = sorted(range(len(areas)), key=lambda k: -areas[k])
    keep, n = set(shell), sum(tri[k] for k in shell)
    for k in order:
        if n >= target * t1:
            break
        keep.add(k)
        n += tri[k]
    mid = Lod("res1y", LOD_RES, 1.75)
    remap = {}
    for k, (idx, mat, uv) in enumerate(ext.faces):
        if k not in keep:
            continue
        nidx = []
        for i in idx:
            if i not in remap:
                remap[i] = mid.copy_vert(ext, i)
            nidx.append(remap[i])
        mid.faces.append((tuple(nidx), mat, uv))
    for g, vs in ext.groups.items():
        kept = {remap[i] for i in vs if i in remap}
        if kept:
            mid.groups[g] = kept
    return mid


def macro_variant(L, P):
    """D85: move this building's wall faces onto one grime-macro offset variant (0 = base rvmat), picked per
    archetype + variant so the three ruin states of one building keep the same soot pattern. Still one material
    per wall type per model: no extra sections."""
    k = int(h01(P.A.get("catalog", P.arch), P.arch, "macro") * (len(S.MACRO_OFFSETS) + 1))
    if not k:
        return
    walls = set(S.MACRO_WALLS)
    for v in L.values():
        lod = v.lod
        lod.faces = [(i, ("%s_m%d" % (m, k)) if m in walls else m, uv) for (i, m, uv) in lod.faces]


def _builder(arch, state):
    return lambda: build(arch, state)


BUILDERS = {"City_%s_%s" % (a, st): _builder(a, i) for a in S.CITY_ARCHETYPES for i, st in enumerate(S.RUIN_STATES)
            if not S.CITY_ARCHETYPES[a].get("special")}
BUILDERS.update({"City_RubbleLot_%s" % v: (lambda v=v: build_rubble_lot(v)) for v in LOT_SKINS})
BUILDERS.update({"City_Substation_%s" % st: (lambda i=i: build_substation(i)) for i, st in enumerate(S.RUIN_STATES)})
BUILDERS["City_WaterTower"] = build_watertower
BUILDERS.update({n: (lambda n=n: build_veg(n)) for n in S.VEG_PIECES})
BUILDERS.update({"City_MetroEntrance_%s" % v: (lambda v=v: build_metro(v)) for v in "AB"})


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
