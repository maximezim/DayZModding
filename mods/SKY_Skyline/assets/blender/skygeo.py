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


class UVBand:
    """Trim-sheet band: vertical faces stretch their height over V band (v0, v1);
    U runs along the face every `scale` metres. Horizontal faces use the band's
    centre line so slab tops/undersides still sample the same strip."""

    def __init__(self, band, scale=3.0):
        self.v0, self.v1 = band
        self.scale = scale

    def __call__(self, pts, normal):
        ax = max(range(3), key=lambda i: abs(normal[i]))
        # (U axis, axis stretched across the band)
        along, across = {0: (1, 2), 1: (0, 2), 2: (0, 1)}[ax]
        cs = [p[across] for p in pts]
        c0, c1 = min(cs), max(cs)
        h = (c1 - c0) or 1.0
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
        return [(u0 + (p[self.ua] - self.lo[0]) / (self.hi[0] - self.lo[0]) * (u1 - u0),
                 v0 + (p[self.va] - self.lo[1]) / (self.hi[1] - self.lo[1]) * (v1 - v0)) for p in pts]


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

    # -- primitives ---------------------------------------------------
    def _add_face(self, pts, outward, mat, uv, vidx_base_sel):
        n = _normal(pts)
        if outward is not None and _dot(n, outward) < 0:
            pts = list(reversed(pts))
            n = _normal(pts)
        base = len(self.verts)
        self.verts.extend(pts)
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
            if key not in skip:
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
        base = len(self.verts)
        verts = a + b
        self.verts.extend(verts)
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
        base = len(self.verts)
        self.verts.extend(verts)
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
        """Regular n-gon prism along Z (poles, bollards, manholes)."""
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

    def quad(self, pts, facing, mat=None, uv=None, sel=(), double=False):
        """Single quad; `facing` = desired normal. double=True adds the back face."""
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
        self._add_face(list(pts), None, None, None, [name])

    def point(self, name, co):
        """Memory point (or 2-point axis when called twice with the same name)."""
        idx = len(self.verts)
        self.verts.append(tuple(co))
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
        stats = json.load(open(stats_path)) if os.path.exists(stats_path) else {}
        for key in only:
            fn, pbo, fname = modules[key]
            path = os.path.join(out, pbo, fname)
            stats[fname] = export_p3d(fn(), materials, path)
            print("EXPORTED", path, stats[fname])
        os.makedirs(os.path.dirname(stats_path), exist_ok=True)
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


def export_p3d(lods, materials, path):
    """Write an MLOD .p3d. Default: the standalone writer (p3dwriter, no add-on, any Blender or plain
    Python - D60). SKY_P3D_BACKEND=atb uses Arma Toolbox (Blender 4.2 + ARMATOOLBOX_PATH) instead."""
    lods = list(lods)
    enforce_vertex_budget(lods, path)
    if os.environ.get("SKY_P3D_BACKEND", "native").lower() == "atb":
        return export_p3d_atb(lods, materials, path)
    import p3dwriter
    return p3dwriter.write_mlod(lods, materials, path)


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
