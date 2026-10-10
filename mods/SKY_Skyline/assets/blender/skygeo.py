"""Geometry helpers for SKY_Skyline Blender generators (Blender 4.2 + Arma Toolbox 4.2.x).

Model in the Blender frame (X east, Y north, Z up, metres). Each `Lod` collects
convex boxes / wedges / quads with materials, UVs and named selections, then
`export_p3d()` turns them into Arma Toolbox objects and writes an MLOD P3D.

Convex-component LODs (Geometry, View Geometry, Fire Geometry) get one
ComponentNN selection per solid automatically, which is what Object Builder's
"Find Components" would produce for disjoint convex boxes.
"""
import math
import os
import sys

try:                       # Blender is optional (D60): only the preview renderers and the Arma Toolbox
    import bmesh           # backend need bpy; generation, tests and the native P3D writer are plain Python
    import bpy
except ImportError:
    bmesh = bpy = None

# LOD codes - exact strings from ArmaToolbox/properties.py lodPresets.
LOD_RES = "-1.0"            # graphical LOD, resolution = Lod.distance
LOD_SHADOW = "1.000e+4"     # Shadow Volume 0 (resolution 10000)
LOD_GEOMETRY = "1.000e+13"
LOD_MEMORY = "1.000e+15"
LOD_ROADWAY = "3.000e+15"
LOD_VIEWGEO = "6.000e+15"
LOD_FIREGEO = "7.000e+15"

COMPONENT_LODS = {LOD_GEOMETRY, LOD_VIEWGEO, LOD_FIREGEO}


# ------------------------------------------------------------------ UV mappers
class UVWorld:
    """Planar projection on the face's dominant axis; `scale` metres per UV unit."""

    def __init__(self, scale=3.0, offset=(0.0, 0.0)):
        self.scale, self.offset = scale, offset

    def __call__(self, pts, normal):
        ax = max(range(3), key=lambda i: abs(normal[i]))
        a, b = [(1, 2), (0, 2), (0, 1)][ax]
        return [(p[a] / self.scale + self.offset[0], p[b] / self.scale + self.offset[1]) for p in pts]


BAND_MIN = 0.1     # UV per metre: a band stretched thinner than this streaks (test_quality SMEAR_MIN)


class UVBand:
    """Trim-sheet band: vertical faces stretch their height over V band (v0, v1);
    U runs along the face every `scale` metres. Horizontal faces (D96): U along their longer side, V across the
    shorter side at true scale (square texels, clamped to the band, centred in it) - before, a top face that ran
    along Y stretched the whole band down its length (test_quality smear: 35-55 m streaks on skirtings, slab edges)."""

    def __init__(self, band, scale=3.0):
        self.v0, self.v1 = band
        self.scale = scale

    def __call__(self, pts, normal):
        ax = max(range(3), key=lambda i: abs(normal[i]))
        if ax == 2:
            ex = max(p[0] for p in pts) - min(p[0] for p in pts)
            ey = max(p[1] for p in pts) - min(p[1] for p in pts)
            along, across = (0, 1) if ex >= ey else (1, 0)
            c0 = min(p[across] for p in pts)
            span = min(max(ex, ey) and min(ex, ey) / self.scale, 0.98 * (self.v1 - self.v0))
            vc = (self.v0 + self.v1) / 2
            ext = min(ex, ey) or 1.0
            return [(p[along] / self.scale, 1.0 - (vc - span / 2 + (p[across] - c0) / ext * span)) for p in pts]
        # (U axis, axis stretched across the band)
        along, across = {0: (1, 2), 1: (0, 2)}[ax]
        cs = [p[across] for p in pts]
        c0, c1 = min(cs), max(cs)
        h = (c1 - c0) or 1.0
        if (self.v1 - self.v0) / h < BAND_MIN:
            # D96: a long thin upright or diagonal (downpipe, rod, sloped member): U runs along its length (longest
            # edge), the band goes across its width (stretching the band over 6-25 m streaked it)
            q = [(p[along], p[across]) for p in pts]
            e = max(((q[(i + 1) % len(q)][0] - q[i][0], q[(i + 1) % len(q)][1] - q[i][1]) for i in range(len(q))),
                    key=lambda v: v[0] * v[0] + v[1] * v[1])
            el = math.hypot(*e) or 1.0
            d = (e[0] / el, e[1] / el)
            t = [a * d[0] + b * d[1] for a, b in q]
            s = [-a * d[1] + b * d[0] for a, b in q]
            L, W = max(t) - min(t), max(s) - min(s)
            if L > 4.0 * W:
                s0 = min(s)
                return [(ti / self.scale, 1.0 - (self.v1 - (si - s0) / (W or 1.0) * (self.v1 - self.v0)))
                        for ti, si in zip(t, s)]
        # Image rows grow downwards while Blender V grows upwards -> 1 - v.
        return [(p[along] / self.scale, 1.0 - (self.v1 - (p[across] - c0) / h * (self.v1 - self.v0))) for p in pts]


class UVFit:
    """Fit a rectangle (x0, x1, y0, y1) exactly onto UV 0..1 (decals, card faces)."""

    def __init__(self, x0, x1, y0, y1):
        self.r = (x0, x1, y0, y1)

    def __call__(self, pts, normal):
        x0, x1, y0, y1 = self.r
        return [((p[0] - x0) / (x1 - x0), (p[1] - y0) / (y1 - y0)) for p in pts]


class UVRect:
    """Map a rectangle on any face plane to a UV box. u from coordinate axis
    `u_axis` over [lo[0], hi[0]], v from `v_axis` over [lo[1], hi[1]]; `uv`
    = (u0, v0, u1, v1) may exceed 0..1 to tile (e.g. road lines)."""

    def __init__(self, u_axis, v_axis, lo, hi, uv=(0.0, 0.0, 1.0, 1.0)):
        self.ua, self.va, self.lo, self.hi, self.uv = u_axis, v_axis, lo, hi, uv

    def __call__(self, pts, normal):
        u0, v0, u1, v1 = self.uv
        ua, va = self.ua, self.va
        w = 3 - ua - va                                   # D96: a box side square to the mapped plane takes the third
        if abs(normal[ua]) > 0.7:                         # axis for its collapsed coordinate (was a constant: streaks)
            ua = w
        elif abs(normal[va]) > 0.7:
            va = w
        lo_u = self.lo[0] if ua == self.ua else min(p[ua] for p in pts)
        lo_v = self.lo[1] if va == self.va else min(p[va] for p in pts)
        return [(u0 + (p[ua] - lo_u) / (self.hi[0] - self.lo[0]) * (u1 - u0),
                 v0 + (p[va] - lo_v) / (self.hi[1] - self.lo[1]) * (v1 - v0)) for p in pts]


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _normal(pts):
    n = _cross(_sub(pts[1], pts[0]), _sub(pts[2], pts[0]))
    l = math.sqrt(_dot(n, n)) or 1.0
    return (n[0] / l, n[1] / l, n[2] / l)


# ------------------------------------------------------------------ LOD container
class Lod:
    def __init__(self, name, lod, distance=0.0):
        self.name, self.lod, self.distance = name, lod, distance
        self.verts = []
        self.faces = []        # (vertex index tuple, material key or None, uv list or None)
        self.groups = {}       # selection name -> set(vertex index)
        self.props = {}
        self.mass = 0.0
        self._component = 0
        self.vprim = []        # D96: primitive id per vertex (box / solid / quad call) - zfix moves whole primitives
        self._prim = 0

    def _begin(self):
        self._prim += 1
        return self._prim

    def copy_vert(self, src, i, offset=0):
        """Append src.verts[i] keeping its primitive id (+ offset when merging several sources). Returns the index."""
        self.verts.append(src.verts[i])
        p = src.vprim[i] if i < len(src.vprim) else -1
        self.vprim.append(p + offset if p > 0 else p)
        return len(self.verts) - 1

    # -- primitives ---------------------------------------------------
    def _add_face(self, pts, outward, mat, uv, vidx_base_sel):
        n = _normal(pts)
        if outward is not None and _dot(n, outward) < 0:
            pts = list(reversed(pts))
            n = _normal(pts)
        base = len(self.verts)
        self.verts.extend(pts)
        self.vprim.extend([self._prim] * len(pts))
        idx = tuple(range(base, base + len(pts)))
        self.faces.append((idx, mat, uv(pts, n) if (uv and mat) else None))
        for s in vidx_base_sel:
            self.groups.setdefault(s, set()).update(idx)
        return idx

    def _next_component(self):
        self._component += 1
        return "Component%02d" % self._component

    def box(self, x0, x1, y0, y1, z0, z1, mat=None, uv=None, sel=(), skip=(), component=None):
        """Axis-aligned box. skip: subset of {'-x','+x','-y','+y','-z','+z'} faces to omit
        (only for graphical LODs - collision boxes must stay closed)."""
        if x1 - x0 < 1e-4 or y1 - y0 < 1e-4 or z1 - z0 < 1e-4:
            return
        self._begin()
        sel = list(sel)
        if component is None:
            component = self.lod in COMPONENT_LODS
        closed = component or self.lod == LOD_SHADOW
        if component:
            sel.append(self._next_component())
        if closed:
            skip = ()
        c = [(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
        P = lambda i, j, k: c[i * 4 + j * 2 + k]
        quads = {
            "-x": ([P(0, 0, 0), P(0, 1, 0), P(0, 1, 1), P(0, 0, 1)], (-1, 0, 0)),
            "+x": ([P(1, 0, 0), P(1, 1, 0), P(1, 1, 1), P(1, 0, 1)], (1, 0, 0)),
            "-y": ([P(0, 0, 0), P(1, 0, 0), P(1, 0, 1), P(0, 0, 1)], (0, -1, 0)),
            "+y": ([P(0, 1, 0), P(1, 1, 0), P(1, 1, 1), P(0, 1, 1)], (0, 1, 0)),
            "-z": ([P(0, 0, 0), P(1, 0, 0), P(1, 1, 0), P(0, 1, 0)], (0, 0, -1)),
            "+z": ([P(0, 0, 1), P(1, 0, 1), P(1, 1, 1), P(0, 1, 1)], (0, 0, 1)),
        }
        if closed:
            # Closed convex solid: share 8 vertices so the component / shadow volume is watertight.
            base = len(self.verts)
            self.verts.extend(c)
            self.vprim.extend([self._prim] * 8)
            remap = {v: base + i for i, v in enumerate(c)}
            for key, (pts, out) in quads.items():
                n = _normal(pts)
                if _dot(n, out) < 0:
                    pts = list(reversed(pts))
                idx = tuple(remap[p] for p in pts)
                self.faces.append((idx, mat, uv(pts, _normal(pts)) if (uv and mat) else None))
            for s in sel:
                self.groups.setdefault(s, set()).update(range(base, base + 8))
            return
        for key, (pts, out) in quads.items():
            if key in skip:
                continue
            if key in ("-z", "+z") and isinstance(uv, UVBand):
                # D96: a wide top / bottom with a band texture is cut into band-wide strips across its short side
                # (one face stretched the band over up to 40 m)
                bm = 0.98 * (uv.v1 - uv.v0) * uv.scale
                ex, ey = x1 - x0, y1 - y0
                short = min(ex, ey)
                n = int(math.ceil(short / bm - 1e-6)) if bm > 0 else 1
                if (uv.v1 - uv.v0) / short < BAND_MIN and 1 < n <= 400:          # only where it would streak
                    zz = pts[0][2]
                    for i in range(n):
                        if ex >= ey:
                            a, b = y0 + i * ey / n, y0 + (i + 1) * ey / n
                            q = [(x0, a, zz), (x1, a, zz), (x1, b, zz), (x0, b, zz)]
                        else:
                            a, b = x0 + i * ex / n, x0 + (i + 1) * ex / n
                            q = [(a, y0, zz), (b, y0, zz), (b, y1, zz), (a, y1, zz)]
                        self._add_face(q, out, mat, uv, sel)
                    continue
            self._add_face(pts, out, mat, uv, sel)

    def wedge(self, x0, x1, y_low, y_high, z_base, z_low, z_high, mat=None, uv=None, sel=(), component=None):
        """Stair ramp solid running along Y from (y_low, z_low) to (y_high, z_high),
        bottom flat at z_base (must be below both ends). Convex (a prism)."""
        if z_base >= min(z_low, z_high) - 1e-4:
            raise ValueError("wedge base must be below the ramp")
        sel = list(sel)
        if component is None:
            component = self.lod in COMPONENT_LODS
        if component:
            sel.append(self._next_component())
        a = [(x0, y_low, z_base), (x0, y_high, z_base), (x0, y_high, z_high), (x0, y_low, z_low)]
        b = [(x1, p[1], p[2]) for p in a]
        cx = (x0 + x1) / 2
        cy = (y_low + y_high) / 2
        cz = (z_base + max(z_low, z_high)) / 2
        centre = (cx, cy, cz)
        self._begin()
        base = len(self.verts)
        verts = a + b
        self.verts.extend(verts)
        self.vprim.extend([self._prim] * len(verts))
        quads = [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
        for q in quads:
            pts = [verts[i] for i in q]
            n = _normal(pts)
            fc = tuple(sum(p[i] for p in pts) / 4 for i in range(3))
            if _dot(n, _sub(fc, centre)) < 0:
                q = tuple(reversed(q))
                pts = [verts[i] for i in q]
            self.faces.append((tuple(base + i for i in q), mat, uv(pts, _normal(pts)) if (uv and mat) else None))
        for s in sel:
            self.groups.setdefault(s, set()).update(range(base, base + 8))

    def ramp_slab(self, x0, x1, y_low, y_high, z_low, z_high, t=0.30, mat=None, uv=None, sel=(), component=None):
        """Collision for one stair flight: a sloped slab of vertical thickness t running along Y from
        (y_low, z_low) to (y_high, z_high); top and bottom are parallel (convex, 8 vertices). Use this instead
        of wedge() for flights that stack: a wedge's flat bottom fills the space under the flight above and
        leaves floor_height/2 - 0.25 m of headroom at the top of each flight (1.5 m in Tower A), so a standing
        player is blocked and only a crouching one fits (TESTING C-03, 2026-10-09)."""
        verts = [(x0, y_low, z_low - t), (x0, y_high, z_high - t), (x0, y_high, z_high), (x0, y_low, z_low),
                 (x1, y_low, z_low - t), (x1, y_high, z_high - t), (x1, y_high, z_high), (x1, y_low, z_low)]
        faces = [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
        self.solid(verts, faces, mat=mat, uv=uv, sel=sel, component=component)

    def solid(self, verts, faces, mat=None, uv=None, sel=(), component=None):
        """Closed convex solid from vertices + polygon index lists. Faces are
        oriented outward from the centroid; polygons > 4 verts are fanned
        (Arma Toolbox rejects n-gons). Shared vertices -> watertight."""
        sel = list(sel)
        if component is None:
            component = self.lod in COMPONENT_LODS
        if component:
            sel.append(self._next_component())
        centre = tuple(sum(v[i] for v in verts) / len(verts) for i in range(3))
        self._begin()
        base = len(self.verts)
        self.verts.extend(verts)
        self.vprim.extend([self._prim] * len(verts))
        for poly in faces:
            pieces = [poly] if len(poly) <= 4 else [(poly[0], poly[i], poly[i + 1]) for i in range(1, len(poly) - 1)]
            for q in pieces:
                pts = [verts[i] for i in q]
                n = _normal(pts)
                fc = tuple(sum(p[i] for p in pts) / len(pts) for i in range(3))
                if _dot(n, _sub(fc, centre)) < 0:
                    q = tuple(reversed(q))
                    pts = [verts[i] for i in q]
                self.faces.append((tuple(base + i for i in q), mat, uv(pts, _normal(pts)) if (uv and mat) else None))
        for s in sel:
            self.groups.setdefault(s, set()).update(range(base, base + len(verts)))

    def prism(self, cx, cy, r, z0, z1, n=8, mat=None, uv=None, sel=(), component=None, rot=0.0):
        """Regular n-gon prism along Z (poles, bollards, manholes). D96: graphical LODs get at least 12 sides (16 from
        r = 0.3 m) so the writer's smooth normals make them round; collision LODs keep the requested n."""
        if self.lod == LOD_RES and self.distance <= 1.0 and r >= (0.03 if self.distance < 1.0 else 0.05):   # Res0; Res1 from 5 cm
            n = max(n, 16 if r >= 0.3 else 12)
        ring = [(cx + r * math.cos(rot + 2 * math.pi * k / n), cy + r * math.sin(rot + 2 * math.pi * k / n)) for k in range(n)]
        verts = [(x, y, z0) for x, y in ring] + [(x, y, z1) for x, y in ring]
        faces = [tuple(range(n)), tuple(range(n, 2 * n))]
        faces += [(k, (k + 1) % n, n + (k + 1) % n, n + k) for k in range(n)]
        self.solid(verts, faces, mat, uv, sel, component)

    def extrude_y(self, profile, y0, y1, mat=None, uv=None, sel=(), component=None):
        """Extrude a convex (x, z) profile along Y (curbs, jersey barriers)."""
        n = len(profile)
        verts = [(x, y0, z) for x, z in profile] + [(x, y1, z) for x, z in profile]
        faces = [tuple(range(n)), tuple(range(n, 2 * n))]
        faces += [(k, (k + 1) % n, n + (k + 1) % n, n + k) for k in range(n)]
        self.solid(verts, faces, mat, uv, sel, component)

    def extrude_x(self, profile, x0, x1, mat=None, uv=None, sel=(), component=None):
        """Extrude a convex (y, z) profile along X (wheels, vehicle cabins)."""
        n = len(profile)
        verts = [(x0, y, z) for y, z in profile] + [(x1, y, z) for y, z in profile]
        faces = [tuple(range(n)), tuple(range(n, 2 * n))]
        faces += [(k, (k + 1) % n, n + (k + 1) % n, n + k) for k in range(n)]
        self.solid(verts, faces, mat, uv, sel, component)

    def loft(self, rings, mat=None, uv=None, sel=(), caps=True, mats=None):
        """D96: closed shell through rings of points (same count, same winding; each ring is one cross-section),
        consecutive rings joined by quads, the end rings capped by a fan. Points are shared, so the P3D writer
        smooths the shell (car bodies, hulls, rounded furniture). mats: optional {(ring i, segment k): material}
        overrides (glazing bands). Each quad is oriented away from its station's centroid (star-shaped sections)."""
        self._begin()
        sel = list(sel)
        n = len(rings[0])
        base = len(self.verts)
        for r in rings:
            self.verts.extend(r)
        self.vprim.extend([self._prim] * (n * len(rings)))
        cents = [tuple(sum(p[a] for p in r) / n for a in range(3)) for r in rings]

        def add(idx, out_ref, m):
            pts = [self.verts[i] for i in idx]
            nrm = _normal(pts)
            fc = tuple(sum(p[a] for p in pts) / len(pts) for a in range(3))
            if _dot(nrm, _sub(fc, out_ref)) < 0:
                idx = tuple(reversed(idx))
                pts = [self.verts[i] for i in idx]
                nrm = _normal(pts)
            self.faces.append((tuple(idx), m, uv(pts, nrm) if (uv and m) else None))
        for i in range(len(rings) - 1):
            ref = tuple((cents[i][a] + cents[i + 1][a]) / 2 for a in range(3))
            for k in range(n):
                q = (base + i * n + k, base + i * n + (k + 1) % n, base + (i + 1) * n + (k + 1) % n, base + (i + 1) * n + k)
                add(q, ref, (mats or {}).get((i, k), mat))
        if caps:
            for i, other in ((0, 1), (len(rings) - 1, len(rings) - 2)):
                c = cents[i]
                d = _sub(c, cents[other])
                ref = (c[0] - d[0], c[1] - d[1], c[2] - d[2])           # a point behind the cap, inside the shell
                for k in range(1, n - 1):
                    add((base + i * n, base + i * n + k, base + i * n + k + 1), ref, mat)
        for s in sel:
            self.groups.setdefault(s, set()).update(range(base, base + n * len(rings)))

    def quad(self, pts, facing, mat=None, uv=None, sel=(), double=False):
        """Single quad; `facing` = desired normal. double=True adds the back face."""
        self._begin()
        self._add_face(list(pts), facing, mat, uv, sel)
        if double:
            self._add_face(list(pts), tuple(-f for f in facing), mat, uv, sel)

    def hquad(self, x0, x1, y0, y1, z, mat=None, uv=None, sel=(), up=True):
        pts = [(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)]
        self.quad(pts, (0, 0, 1 if up else -1), mat, uv, sel)

    def ramp(self, x0, x1, y_low, y_high, z_low, z_high, mat=None, uv=None, sel=()):
        pts = [(x0, y_low, z_low), (x1, y_low, z_low), (x1, y_high, z_high), (x0, y_high, z_high)]
        self.quad(pts, (0, 0, 1), mat, uv, sel)

    def occluder(self, pts, name):
        """Single-face occluder plane in View Geometry (pattern from Bohemia's
        Test_Building sample: selections occluder_NNN, 4 points, 1 face)."""
        self._begin()
        self._add_face(list(pts), None, None, None, [name])

    def point(self, name, co):
        """Memory point (or 2-point axis when called twice with the same name)."""
        idx = len(self.verts)
        self.verts.append(tuple(co))
        self.vprim.append(-1)
        self.groups.setdefault(name, set()).add(idx)

    def tri_count(self):
        return sum(1 if len(f[0]) == 3 else 2 for f in self.faces)


# ------------------------------------------------------------------ composite helpers
def _column_spans(openings, a, b, z0, z1):
    """Solid Z spans of the wall column [a, b] around ALL openings covering it
    (several openings may be stacked, e.g. one door per storey)."""
    holes = sorted((o[2], o[3]) for o in openings if o[0] <= a + 1e-6 and o[1] >= b - 1e-6)
    spans, cur = [], z0
    for h0, h1 in holes:
        if h0 > cur + 1e-6:
            spans.append((cur, min(h0, z1)))
        cur = max(cur, h1)
    if cur < z1 - 1e-6:
        spans.append((cur, z1))
    return spans

def wall_x(lod, x0, x1, y0, y1, z0, z1, openings=(), **kw):
    """Wall running along X (thickness y0..y1) with rectangular openings
    [(ox0, ox1, oz0, oz1), ...]; emitted as convex boxes."""
    xs = sorted({x0, x1} | {o[0] for o in openings} | {o[1] for o in openings})
    for a, b in zip(xs, xs[1:]):
        for c0, c1 in _column_spans(openings, a, b, z0, z1):
            lod.box(a, b, y0, y1, c0, c1, **kw)


def wall_y(lod, x0, x1, y0, y1, z0, z1, openings=(), **kw):
    """Wall running along Y (thickness x0..x1); openings [(oy0, oy1, oz0, oz1)]."""
    ys = sorted({y0, y1} | {o[0] for o in openings} | {o[1] for o in openings})
    for a, b in zip(ys, ys[1:]):
        for c0, c1 in _column_spans(openings, a, b, z0, z1):
            lod.box(x0, x1, a, b, c0, c1, **kw)


def slab_with_hole(lod, half_w, half_d, hole, z0, z1, **kw):
    """Rectangular slab (+-half_w, +-half_d) with one rectangular hole (hx0,hx1,hy0,hy1)."""
    hx0, hx1, hy0, hy1 = hole
    lod.box(-half_w, half_w, -half_d, hy0, z0, z1, **kw)
    lod.box(-half_w, half_w, hy1, half_d, z0, z1, **kw)
    lod.box(-half_w, hx0, hy0, hy1, z0, z1, **kw)
    lod.box(hx1, half_w, hy0, hy1, z0, z1, **kw)


def floor_quads_with_hole(lod, half_w, half_d, hole, z, **kw):
    hx0, hx1, hy0, hy1 = hole
    lod.hquad(-half_w, half_w, -half_d, hy0, z, **kw)
    lod.hquad(-half_w, half_w, hy1, half_d, z, **kw)
    lod.hquad(-half_w, hx0, hy0, hy1, z, **kw)
    lod.hquad(hx1, half_w, hy0, hy1, z, **kw)


# ------------------------------------------------------------------ Blender / Arma Toolbox export
_ATB = None


def load_arma_toolbox():
    """Import + register Arma Toolbox from ARMATOOLBOX_PATH (folder containing
    the 'ArmaToolbox' package) - works headless without installing the extension."""
    global _ATB
    if _ATB:
        return _ATB
    root = os.environ.get("ARMATOOLBOX_PATH")
    if not root or not os.path.isdir(os.path.join(root, "ArmaToolbox")):
        raise RuntimeError("Set ARMATOOLBOX_PATH to the folder that contains the ArmaToolbox package")
    if root not in sys.path:
        sys.path.insert(0, root)
    import ArmaToolbox
    try:
        ArmaToolbox.register()
    except ValueError:
        pass   # already registered (installed as an extension)
    from ArmaToolbox import MDLExporter
    _ATB = MDLExporter
    return _ATB


def optional_arma_toolbox():
    """Previews: register Arma Toolbox when ARMATOOLBOX_PATH is set (Arma properties on the
    objects), otherwise build plain Blender objects - rendering needs no add-on (D60)."""
    if os.environ.get("ARMATOOLBOX_PATH"):
        return load_arma_toolbox()
    return None


def _material(key, materials, cache):
    if key in cache:
        return cache[key]
    m = bpy.data.materials.new(key)
    info = materials[key]
    cache[key] = m
    if not hasattr(m, "armaMatProps"):        # preview without Arma Toolbox (D60): plain material
        return m
    m.armaMatProps.texType = "Texture"
    m.armaMatProps.texture = info.get("co", "")
    m.armaMatProps.rvMat = info.get("rvmat", "")
    cache[key] = m
    return m


def build_object(lod, materials, cache):
    me = bpy.data.meshes.new(lod.name)
    obj = bpy.data.objects.new(lod.name, me)
    bpy.context.scene.collection.objects.link(obj)
    bm = bmesh.new()
    # Create custom layers BEFORE elements: adding a layer later invalidates BMVert refs.
    uvl = bm.loops.layers.uv.new("UVMap")
    w = bm.verts.layers.float.new("FHQWeights")
    bverts = [bm.verts.new(v) for v in lod.verts]
    bm.verts.ensure_lookup_table()
    mat_keys = []
    for idx, mat, uv in lod.faces:
        try:
            f = bm.faces.new([bverts[i] for i in idx])
        except ValueError:
            continue   # duplicate face (coplanar overlap); skip
        if mat:
            if mat not in mat_keys:
                mat_keys.append(mat)
            f.material_index = mat_keys.index(mat)
        if uv:
            for loop, (u, v) in zip(f.loops, uv):
                loop[uvl].uv = (u, v)
    if lod.lod == LOD_GEOMETRY and bverts:
        per = lod.mass / len(bverts)
        for v in bverts:
            v[w] = per
    bm.to_mesh(me)
    bm.free()
    for k in mat_keys:
        me.materials.append(_material(k, materials, cache))
    for name, vs in lod.groups.items():
        vg = obj.vertex_groups.new(name=name)
        vg.add(sorted(vs), 1.0, "REPLACE")
    if not hasattr(obj, "armaObjProps"):      # preview without Arma Toolbox (D60)
        return obj
    p = obj.armaObjProps
    p.isArmaObject = True
    p.lod = lod.lod
    p.lodDistance = lod.distance
    for k, v in lod.props.items():
        np_ = p.namedProps.add()
        np_.name, np_.value = k, v
    return obj


def run_cli(modules, materials, stats_name):
    """Shared CLI for generator scripts: `-- --out <addons> [--only a,b]`.
    modules: {key: (builder, pbo_folder, p3d_name)}. Stats merge into assets/<stats_name>."""
    import json
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = argv[argv.index("--out") + 1]
    only = argv[argv.index("--only") + 1].split(",") if "--only" in argv else list(modules)
    stats_path = os.path.join(out, "..", "assets", stats_name)
    try:
        mine = {}
        for key in only:
            fn, pbo, fname = modules[key]
            path = os.path.join(out, pbo, fname)
            mine[fname] = export_p3d(fn(), materials, path)
            print("EXPORTED", path, mine[fname])
        os.makedirs(os.path.dirname(stats_path), exist_ok=True)
        # D96: re-read just before writing so shards running in parallel (--only) do not drop each other's entries
        stats = json.load(open(stats_path)) if os.path.exists(stats_path) else {}
        stats.update(mine)
        with open(stats_path, "w") as fh:
            json.dump(stats, fh, indent=1, sort_keys=True)
    except Exception:
        # Blender -P exits 0 on an uncaught exception: fail loudly instead (QA batch-3 L1).
        import traceback
        traceback.print_exc()
        print("EXPORT FAILED")
        sys.exit(1)


MAX_LOD_POINTS = 60000      # engine limit: about 65535 vertices per LOD (16-bit indices); the binarizer splits vertices per
                            # normal / UV, so the MLOD point count must stay clear of it. Found in game 2026-10-09: all 17 models
                            # with a LOD over 65535 points were rejected ("Too many vertices") and the buildings were missing.


def enforce_vertex_budget(lods, path):
    """A graphical (Resolution) LOD over MAX_LOD_POINTS is replaced by the next lower-detail Resolution LOD that fits, keeping
    its name, distance and selections. The over-detailed geometry is dropped for that model (it could not be loaded anyway).
    Returns the list of (lod name, points, replaced by, points)."""
    import copy
    res = sorted([l for l in lods if l.lod == LOD_RES], key=lambda l: l.distance)
    done = []
    for i, lod in enumerate(res):
        if len(lod.verts) <= MAX_LOD_POINTS:
            continue
        repl = None
        for cand in res[i + 1:]:
            if len(cand.verts) <= MAX_LOD_POINTS and set(lod.groups) <= set(cand.groups):
                repl = cand
                break
        if repl is None:
            raise ValueError("%s: LOD %s has %d points (> %d) and no lower Resolution LOD fits with the same selections"
                             % (path, lod.name, len(lod.verts), MAX_LOD_POINTS))
        new = copy.deepcopy(repl)
        new.name, new.lod, new.distance = lod.name, lod.lod, lod.distance
        new.props = dict(lod.props)
        lods[lods.index(lod)] = new
        done.append((lod.name, len(lod.verts), repl.name, len(repl.verts)))
        print("LOD BUDGET %s: %s had %d points (> %d), now uses %s (%d points)" % (
            os.path.basename(path), lod.name, len(lod.verts), MAX_LOD_POINTS, repl.name, len(repl.verts)))
    return done


VERTEX_BUDGET = 58000       # D96: render vertices (binarizer split per normal / UV) per LOD, engine hard limit 65,535
PROXY_PART = 50000          # render vertices per proxy part


def _sub_lod(lod, ks, shift=(0.0, 0.0, 0.0), name=None, keep_groups=False):
    """New Lod with faces ks of lod (vertices compacted, moved by -shift); selections only when keep_groups."""
    out = Lod(name or lod.name, lod.lod, lod.distance)
    remap = {}
    for k in ks:
        idx, mat, uv = lod.faces[k]
        nidx = []
        for i in idx:
            if i not in remap:
                v = lod.verts[i]
                remap[i] = len(out.verts)
                out.verts.append((v[0] - shift[0], v[1] - shift[1], v[2] - shift[2]))
                out.vprim.append(lod.vprim[i] if i < len(lod.vprim) else -1)
            nidx.append(remap[i])
        out.faces.append((tuple(nidx), mat, uv))
    if keep_groups:
        for g, vs in lod.groups.items():
            kept = {remap[i] for i in vs if i in remap}
            if kept:
                out.groups[g] = kept
        out.props = dict(lod.props)
    uv1 = getattr(lod, "uv1", None)
    if uv1:
        out.uv1 = [uv1[k] for k in ks]
    return out


def _bisect(lod, groups, limit):
    """Split a list of primitive face-groups into spatially compact units of <= limit render vertices (storeys
    first, then the longest axis); a primitive is never split across units (sec review D96 H1)."""
    import p3dwriter
    flat = [k for g in groups for k in g]
    if len(groups) < 2 or p3dwriter.render_vertex_count(_sub_lod(lod, flat)) <= limit:
        return [flat]
    cs = []
    for g in groups:
        pts = [lod.verts[i] for k in g for i in lod.faces[k][0]]
        cs.append(tuple(sum(p[a] for p in pts) / len(pts) for a in range(3)))
    span = [max(c[a] for c in cs) - min(c[a] for c in cs) for a in range(3)]
    ax = 2 if span[2] > 2.5 else span.index(max(span))     # perf M: cut by storey first - parts stay small, cull per floor
    order = sorted(range(len(groups)), key=lambda j: (cs[j][ax], j))
    h = len(order) // 2
    return (_bisect(lod, [groups[j] for j in sorted(order[:h])], limit) +
            _bisect(lod, [groups[j] for j in sorted(order[h:])], limit))


def _boxes(lod):
    """Axis-aligned boxes (lo, hi) of the components of a collision LOD."""
    out = []
    for name, vs in lod.groups.items():
        if name.startswith("Component") and vs:
            pts = [lod.verts[i] for i in vs]
            out.append((tuple(min(p[a] for p in pts) for a in range(3)), tuple(max(p[a] for p in pts) for a in range(3))))
    return out


def split_for_export(lods, path):
    """D96 (TESTING WIN-06): a Resolution LOD over VERTEX_BUDGET render vertices keeps its detail by moving part of its
    faces into proxy models (own P3D, own vertex budget) placed by a proxy triangle. Only render-only detail moves
    (sec review D96 H1): a primitive that matches View (or Geometry) collision - walls, slabs, partitions, glass, tall
    furniture that blocks sight - always stays in the model, so a part that fails to load can never leave an invisible
    wall that still stops bullets or a one-way pane. Primitives move whole, interior ones first (lod.proxy_hint).
    Faces in a named selection (doors, hidden selections) never move. If the render-only detail is not enough, the
    LOD keeps the old fallback (enforce_vertex_budget: the next lower LOD) and the exporter says so.
    Returns [(file stem suffix, lods)]: ("", the model) first, then ("_<lod>p<k>", [one Res LOD]) per part.
    SKY_PROXY_SPLIT=0 switches the split off (D95 behaviour)."""
    import p3dwriter
    if os.environ.get("SKY_PROXY_SPLIT", "1") == "0":
        return [("", list(lods))]
    lods = list(lods)
    stem = os.path.splitext(os.path.basename(path))[0]
    pbo = os.path.basename(os.path.dirname(path))
    coll = next((l for l in lods if l.lod == LOD_VIEWGEO), None) or next((l for l in lods if l.lod == LOD_GEOMETRY), None)
    cboxes = _boxes(coll) if coll is not None else []
    parts = []
    for li, lod in enumerate(lods):
        if lod.lod != LOD_RES or p3dwriter.render_vertex_count(lod) <= VERTEX_BUDGET:
            continue
        fixed = set()
        for vs in lod.groups.values():
            fixed |= vs
        prims = {}
        for k, (idx, _m, _uv) in enumerate(lod.faces):
            pid = lod.vprim[idx[0]] if idx[0] < len(lod.vprim) and lod.vprim[idx[0]] > 0 else ("f", k)
            prims.setdefault(pid, []).append(k)
        hint = getattr(lod, "proxy_hint", None)
        inner, outer = [], []
        for pid, ks in prims.items():
            vs = {i for k in ks for i in lod.faces[k][0]}
            if vs & fixed or any(lod.faces[k][1] in ("glass", "glassfar", "glassvoid") for k in ks):
                continue
            pts = [lod.verts[i] for i in vs]
            lo = [min(p[a] for p in pts) - 0.01 for a in range(3)]
            hi = [max(p[a] for p in pts) + 0.01 for a in range(3)]
            vol = (hi[0] - lo[0]) * (hi[1] - lo[1]) * (hi[2] - lo[2])
            ov = 0.0
            for cl, ch in cboxes:
                d = [min(hi[a], ch[a]) - max(lo[a], cl[a]) for a in range(3)]
                if d[0] > 0 and d[1] > 0 and d[2] > 0:
                    ov += d[0] * d[1] * d[2]
            if ov > 0.3 * vol:                                   # matches collision: structural, stays
                continue
            c = tuple(sum(p[a] for p in pts) / len(pts) for a in range(3))
            (inner if hint and hint(c) else outer).append(ks)
        move = []
        for group in (inner, outer):                             # interior detail first, facade detail only if needed
            move += group
            ms = {k for g in move for k in g}
            if p3dwriter.render_vertex_count(_sub_lod(lod, [k for k in range(len(lod.faces)) if k not in ms])) <= VERTEX_BUDGET:
                break
        units = _bisect(lod, move, PROXY_PART) if move else []
        ms = {k for g in move for k in g}
        keep = [k for k in range(len(lod.faces)) if k not in ms]
        out_groups = []
        for g in sorted(units, key=len):                         # give whole parts back while the model still fits
            trial = sorted(keep + g)
            if p3dwriter.render_vertex_count(_sub_lod(lod, trial)) <= VERTEX_BUDGET - 3 * len(units):
                keep = trial
            else:
                out_groups.append(g)
        main = _sub_lod(lod, keep, keep_groups=True)
        if p3dwriter.render_vertex_count(main) > VERTEX_BUDGET:
            print("PROXY SHORT %s %s: render-only detail is not enough (%d render vertices kept) - the LOD falls back to "
                  "the next lower one" % (stem, lod.name, p3dwriter.render_vertex_count(main)))
            continue
        for j, g in enumerate(out_groups):
            pts = [lod.verts[i] for k in g for i in lod.faces[k][0]]
            c = tuple(round((min(p[a] for p in pts) + max(p[a] for p in pts)) / 2, 3) for a in range(3))
            part = _sub_lod(lod, g, shift=c, name="res0")
            part.distance = 0.0
            sfx = "_%sp%d" % (lod.name, j + 1)
            parts.append((sfx, [part]))
            proxy = "proxy:\\SKY_Skyline\\%s\\%s%s.001" % (pbo, stem, sfx)
            base = len(main.verts)
            main.verts += [c, (c[0], c[1], c[2] + 1.0), (c[0], c[1] + 0.5, c[2])]   # Arma Toolbox proxy triangle
            main.vprim += [-1, -1, -1]
            main.faces.append(((base, base + 1, base + 2), None, None))
            main.groups[proxy] = {base, base + 1, base + 2}
        lods[li] = main
    return [("", lods)] + parts


def export_p3d(lods, materials, path):
    """Write an MLOD .p3d. Default: the standalone writer (p3dwriter, no add-on, any Blender or plain
    Python - D60). SKY_P3D_BACKEND=atb uses Arma Toolbox (Blender 4.2 + ARMATOOLBOX_PATH) instead."""
    lods = list(lods)
    import zfix
    zfix.resolve_lods(lods)                   # D96: no coplanar fights left in any Resolution LOD
    units = split_for_export(lods, path)      # D96: proxy parts for LODs over the engine vertex limit
    stem, ext = os.path.splitext(path)
    import glob
    for old in glob.glob(glob.escape(stem) + "_res*p*" + ext):     # perf L: parts of an earlier, bigger split
        if os.path.basename(old)[len(os.path.basename(stem)):-len(ext)] not in [sfx for sfx, _ls in units]:
            os.remove(old)
    stats = None
    extra = {}
    for sfx, ls in units:
        enforce_vertex_budget(ls, path + sfx)
        p = stem + sfx + ext
        if os.environ.get("SKY_P3D_BACKEND", "native").lower() == "atb":
            st = export_p3d_atb(ls, materials, p)
        else:
            import p3dwriter
            st = p3dwriter.write_mlod(ls, materials, p)
        if stats is None:
            stats = st
        else:                                 # the parts render with the model: count them in its LOD
            lod_name = sfx[1:].rsplit("p", 1)[0]
            extra[lod_name] = extra.get(lod_name, 0) + sum(st.values())
    for k, v in extra.items():
        stats[k] = stats.get(k, 0) + v
    return stats


def export_p3d_atb(lods, materials, path):
    exporter = load_arma_toolbox()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    cache = {}
    objs = [build_object(l, materials, cache) for l in lods]
    bpy.context.view_layer.objects.active = objs[0]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        # (myself, file, selectedOnly, applyModifiers, mergeSameLOD, renumberComponents, applyTransforms)
        exporter.exportMDL(None, fh, False, True, True, True, True)
    return {l.name: l.tri_count() for l in lods}
