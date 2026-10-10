"""Standalone MLOD (.p3d, "P3DM" v28.256) writer for skygeo Lod objects - no Blender add-on needed.

The SKY generators build every LOD as plain Python data (skygeo.Lod: vertices, faces with material
keys and UVs, named selections, named properties, mass). This module writes that data in the
same layout Arma Toolbox's MDLExporter produces through our pipeline (verified byte for byte by
assets/blender/test_p3dwriter.py where Arma Toolbox is available), so the export works:
  * in Blender 4.2 LTS (with or without Arma Toolbox),
  * in Blender 5.x next to the "DayZ Object Builder" extension (the extension is not needed),
  * in plain Python (no bpy at all).
Object Builder / Addon Builder read the result like any MLOD file (B10, D60).

Layout per LOD (Arma Toolbox conventions, kept identical):
  'P3DM' 0x1C 0x100, nVerts, nNormals (= face corners), nFaces, 0
  vertices   x, z, y, flags 0                  (Blender Z-up -> P3D Y-up)
  normals    -n per face corner                 (flat faces; D96: smooth across soft edges of one solid in Res LODs)
  faces      n, n x (vertex, vertex-as-normal, u, 1-v), triangle padding, flags 0, texture, rvmat
  'TAGG'     named selections (vertex bytes, face bytes), #SharpEdges# (every edge but the soft ones, D96),
             #Mass# (Geometry), #Property# (64 + 64 chars), #UVSet# 0 (+ #UVSet# 1 when lod.uv1 is set, D85),
             #EndOfFile#
  resolution (float)
"""
import math
import struct

GEOMETRY = 1.0e13
NEEDS_RESOLUTION = {"-1.0", "1.200e+3", "1.000e+4", "1.001e+4", "1.100e+4", "1.101e+4", "8.000e+15", "1.800e+16",
                    "2.000e+4"}


def _lod_key(lod):
    if lod.lod == "-1.0":
        return lod.distance
    if lod.lod in NEEDS_RESOLUTION:
        return float(lod.lod) + lod.distance
    return float(lod.lod)


def _weight_byte(w):
    w = min(1.0, max(0.0, w))
    v = round(255 - 254 * w)
    return 0 if v == 255 else v


def _newell(pts):
    nx = ny = nz = 0.0
    for i, a in enumerate(pts):
        b = pts[(i + 1) % len(pts)]
        nx += (a[1] - b[1]) * (a[2] + b[2])
        ny += (a[2] - b[2]) * (a[0] + b[0])
        nz += (a[0] - b[0]) * (a[1] + b[1])
    ln = math.sqrt(nx * nx + ny * ny + nz * nz)
    if ln < 1e-12:                            # zero-area face: Blender's default normal (+Z)
        return (0.0, 0.0, 1.0)
    return (nx / ln, ny / ln, nz / ln)


def _f32(x):
    """Round through float32 first (Blender stores UVs as float32 before the exporter flips V)."""
    return struct.unpack("<f", struct.pack("<f", x))[0]


def _cstr(s):
    return s.encode("ascii") + b"\0"


def _tagg(name, payload):
    return b"\x01" + _cstr(name) + struct.pack("<I", len(payload)) + payload


def _faces(lod, with_index=False):
    """Faces as Blender's bmesh would keep them: drop degenerate faces (a repeated vertex).
    with_index: also return each kept face's index in lod.faces (UV set 1 is stored per original face)."""
    out, orig = [], []
    seen = set()
    for fi, (idx, mat, uv) in enumerate(lod.faces):
        if len(set(idx)) != len(idx):
            continue
        key = frozenset(idx)
        if key in seen:                       # bmesh refuses a second face on the same vertices
            continue
        seen.add(key)
        out.append((idx, mat, uv))
        orig.append(fi)
    return (out, orig) if with_index else out


SMOOTH_DEG = 35.0             # D96: Resolution LODs - an edge between two faces of one solid closer than this is smooth
_SMOOTH_COS = math.cos(math.radians(SMOOTH_DEG))


def _area(pts):
    nx = ny = nz = 0.0
    for i, a in enumerate(pts):
        b = pts[(i + 1) % len(pts)]
        nx += (a[1] - b[1]) * (a[2] + b[2])
        ny += (a[2] - b[2]) * (a[0] + b[0])
        nz += (a[0] - b[0]) * (a[1] + b[1])
    return 0.5 * math.sqrt(nx * nx + ny * ny + nz * nz)


def shading(lod, faces):
    """(corner normals per face, sharp edge list). Graphical LODs (D96): faces that share an edge (shared points = one
    solid: prisms, pipes, profiles) and meet at less than SMOOTH_DEG are smooth - their corner normals are the
    area-weighted mean of the faces round that point within the angle, the edge is left out of #SharpEdges# so the
    binarizer smooths it the same way. Boxes (90 deg) and 45 deg chamfers stay hard; separate parts never blend.
    Other LODs: flat normals, every edge sharp (unchanged)."""
    fn = [_newell([lod.verts[i] for i in f[0]]) for f in faces]
    edges = {}
    for k, f in enumerate(faces):
        idx = f[0]
        for i in range(len(idx)):
            edges.setdefault(tuple(sorted((idx[i], idx[(i + 1) % len(idx)]))), []).append(k)
    if lod.lod != "-1.0":
        return [[n] * len(f[0]) for n, f in zip(fn, faces)], sorted(edges)
    smooth = set()
    for e, ks in edges.items():
        if len(ks) == 2:
            a, b = fn[ks[0]], fn[ks[1]]
            if a[0] * b[0] + a[1] * b[1] + a[2] * b[2] > _SMOOTH_COS:
                smooth.add(e)
    if not smooth:
        return [[n] * len(f[0]) for n, f in zip(fn, faces)], sorted(edges)
    area = [_area([lod.verts[i] for i in f[0]]) for f in faces]
    at = {}
    for k, f in enumerate(faces):
        for v in f[0]:
            at.setdefault(v, []).append(k)
    linked = {}                                   # faces joined by a smooth edge (only those may blend)
    for (a, b) in smooth:
        ka, kb = edges[(a, b)]
        linked.setdefault(ka, set()).add(kb)
        linked.setdefault(kb, set()).add(ka)
    out = []
    for k, f in enumerate(faces):
        if k not in linked:
            out.append([fn[k]] * len(f[0]))
            continue
        cn = []
        for v in f[0]:
            # the smooth fan round v that contains face k
            fan, todo = {k}, [k]
            while todo:
                q = todo.pop()
                for g in linked.get(q, ()):
                    if g not in fan and v in faces[g][0]:
                        fan.add(g)
                        todo.append(g)
            sx = sum(fn[g][0] * area[g] for g in fan)
            sy = sum(fn[g][1] * area[g] for g in fan)
            sz = sum(fn[g][2] * area[g] for g in fan)
            ln = math.sqrt(sx * sx + sy * sy + sz * sz)
            cn.append((sx / ln, sy / ln, sz / ln) if ln > 1e-12 else fn[k])
        out.append(cn)
    return out, sorted(e for e in edges if e not in smooth)


def render_vertex_count(lod):
    """Vertices the binarizer keeps for a graphical LOD: one per distinct (point, normal, UV) - the number the engine
    limits to 65,535 per LOD ("Too many vertices", TESTING WIN-06)."""
    faces = _faces(lod)
    norms, _sharp = shading(lod, faces)
    s = set()
    for (idx, _m, uv), ns in zip(faces, norms):
        uvs = uv if uv else [(0.0, 0.0)] * len(idx)
        for vi, n, t in zip(idx, ns, uvs):
            s.add((vi, round(n[0], 3), round(n[1], 3), round(n[2], 3), round(t[0], 5), round(t[1], 5)))
    return len(s)


def lod_bytes(lod, materials):
    faces, orig = _faces(lod, True)
    mat_keys = []
    for _idx, mat, _uv in faces:
        if mat and mat not in mat_keys:
            mat_keys.append(mat)
    # faces grouped by material slot, stable (Arma Toolbox optimize_export_lod: fewer sections)
    order = sorted(range(len(faces)), key=lambda i: mat_keys.index(faces[i][1]) if faces[i][1] else 0)
    faces, orig = [faces[i] for i in order], [orig[i] for i in order]
    nverts = len(lod.verts)
    ncorners = sum(len(f[0]) for f in faces)
    b = bytearray()
    b += b"P3DM" + struct.pack("<III", 0x1C, 0x100, nverts) + struct.pack("<III", ncorners, len(faces), 0)
    for (x, y, z) in lod.verts:
        b += struct.pack("<fffI", x, z, y, 0)
    norms, sharp = shading(lod, faces)
    for ns in norms:
        for n in ns:
            b += struct.pack("<fff", -n[0], -n[1], -n[2])
    proxy_verts = set()
    for g, vs in lod.groups.items():
        if g.startswith("proxy:"):
            proxy_verts |= vs
    for idx, mat, uv in faces:
        # a face without a material takes material slot 0, as in the Blender mesh; a proxy triangle (D96) none
        key = mat if mat else (mat_keys[0] if mat_keys and not set(idx) <= proxy_verts else None)
        tex, rvmat = "", ""
        if key:
            info = materials[key]
            tex, rvmat = info.get("co", "") or "", info.get("rvmat", "") or ""
            tex = tex[1:] if tex.startswith("\\") else tex
            rvmat = rvmat[1:] if rvmat.startswith("\\") else rvmat
        b += struct.pack("<I", len(idx))
        uvs = uv if uv else [(0.0, 0.0)] * len(idx)
        for vi, (u, v) in zip(idx, uvs):
            b += struct.pack("<IIff", vi, vi, u, 1.0 - _f32(v))
        if len(idx) == 3:
            b += struct.pack("<IIff", 0, 0, 0.0, 0.0)
        b += struct.pack("<I", 0) + _cstr(tex) + _cstr(rvmat)
    b += b"TAGG"
    # named selections (components renumbered contiguously in Geometry-type LODs, as Arma Toolbox does)
    groups = list(lod.groups.items())
    face_sets = [frozenset(f[0]) for f in faces]
    for name, vs in groups:
        vb = bytearray(nverts)
        for v in vs:
            vb[v] = _weight_byte(1.0)
        fb = bytearray(len(faces))
        for i, fs in enumerate(face_sets):
            if fs <= vs:
                fb[i] = 1
        b += _tagg(name, bytes(vb) + bytes(fb))
    if sharp:
        b += _tagg("#SharpEdges#", b"".join(struct.pack("<II", a, c) for a, c in sharp))
    key = _lod_key(lod)
    if abs(key) == GEOMETRY:
        per = lod.mass / nverts if nverts else 0.0
        b += _tagg("#Mass#", struct.pack("<%df" % nverts, *([per] * nverts)))
    for k, v in lod.props.items():
        b += _tagg("#Property#", struct.pack("<64s64s", k.encode("ascii"), v.encode("ascii")))
    uvp = bytearray(struct.pack("<I", 0))
    for idx, mat, uv in faces:
        for (u, v) in (uv if uv else [(0.0, 0.0)] * len(idx)):
            uvp += struct.pack("<ff", u, 1.0 - _f32(v))
    b += _tagg("#UVSet#", bytes(uvp))
    uv1 = getattr(lod, "uv1", None)
    if uv1:                                   # D85: second UV set (baked AO, Stage4 uvSource "tex1")
        uvq = bytearray(struct.pack("<I", 1))
        for (idx, _m, _uv), fi in zip(faces, orig):
            for (u, v) in (uv1[fi] if uv1[fi] else [(0.0, 0.0)] * len(idx)):
                uvq += struct.pack("<ff", u, 1.0 - _f32(v))
        b += _tagg("#UVSet#", bytes(uvq))
    b += b"\x01" + _cstr("#EndOfFile#") + struct.pack("<I", 0)
    b += struct.pack("<f", abs(key))
    return bytes(b)


def write_mlod(lods, materials, path):
    """Write lods (skygeo.Lod list) to an MLOD .p3d. Returns {lod name: triangle count}."""
    import os
    order = sorted(lods, key=_lod_key)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(b"MLOD" + struct.pack("<II", 0x101, len(order)))
        for lod in order:
            fh.write(lod_bytes(lod, materials))
    return {l.name: l.tri_count() for l in lods}
