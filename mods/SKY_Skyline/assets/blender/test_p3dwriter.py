"""Compare the standalone MLOD writer with Arma Toolbox (where it is installed) - run in Blender 4.2.

    blender -b --factory-startup --python-exit-code 1 -P test_p3dwriter.py [-- --only City_Rowhouse_Intact,...]

For each model both exporters write a .p3d; the files must be identical except for face normals
(float32 rounding of the normal computation, |diff| < 1e-3; the engine recomputes normals anyway).
Exit 1 on any other difference.
"""
import os
import struct
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import p3dwriter as W  # noqa: E402
import skygeo  # noqa: E402

DEFAULT = ["City_Rowhouse_Intact", "City_Church_Ruined", "Veg_Birch", "Street_Intersection", "Locker",
           "Floor_Hotel", "core", "lobby"]


def builders():
    out = {}
    for modname in ("build_kit", "build_props", "build_floors", "build_city"):
        m = __import__(modname)
        for n, (fn, _p, _f) in m.modules().items():
            out[n] = fn
    import build_towera as T
    for k, (fn, _p, _f) in T.MODULES.items():
        out[k] = fn
    return out


def parse(data):
    """MLOD -> list of LODs (vertices, normals, faces, taggs, resolution) for a structural compare."""
    off, lods = 12, []
    n = struct.unpack_from("<I", data, 8)[0]
    for _ in range(n):
        nv, nn, nf, _fl = struct.unpack_from("<IIII", data, off + 12)
        p = off + 28
        verts = [struct.unpack_from("<fffI", data, p + 16 * i) for i in range(nv)]
        p += 16 * nv
        norms = [struct.unpack_from("<fff", data, p + 12 * i) for i in range(nn)]
        p += 12 * nn
        faces = []
        for _f in range(nf):
            k = struct.unpack_from("<I", data, p)[0]
            raw = data[p:p + 4 + 64 + 4]
            p += 4 + 64 + 4
            e = data.index(b"\0", p)
            tex = data[p:e]
            p = e + 1
            e = data.index(b"\0", p)
            mat = data[p:e]
            p = e + 1
            faces.append((raw, tex, mat))
        p += 4
        tags = []
        while True:
            p += 1
            e = data.index(b"\0", p)
            name = data[p:e].decode()
            p = e + 1
            ln = struct.unpack_from("<I", data, p)[0]
            p += 4
            tags.append((name, data[p:p + ln]))
            p += ln
            if name == "#EndOfFile#":
                break
        res = data[p:p + 4]
        p += 4
        off = p
        lods.append((verts, norms, faces, tags, res))
    return lods


def compare(da, db):
    """'' if equal up to normal rounding, else a description of the first difference."""
    if da[:12] != db[:12]:
        return "header"
    A, B = parse(da), parse(db)
    if len(A) != len(B):
        return "lod count"
    worst = 0.0
    for i, (x, y) in enumerate(zip(A, B)):
        for part, name in ((0, "vertices"), (2, "faces"), (3, "taggs"), (4, "resolution")):
            if x[part] != y[part]:
                return "LOD %d %s" % (i, name)
        if len(x[1]) != len(y[1]):
            return "LOD %d normal count" % i
        for na, nb in zip(x[1], y[1]):
            worst = max(worst, max(abs(p - q) for p, q in zip(na, nb)))
    # Blender computes face normals in float32 (slanted faces differ by ~1e-4); the engine recomputes
    # normals on load anyway, so only a real direction change (> 1e-3) counts
    return "" if worst < 1e-3 else "normals differ by %g" % worst


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    names = argv[argv.index("--only") + 1].split(",") if "--only" in argv else DEFAULT
    from build_kit import KIT_MATS
    B = builders()
    tmp = tempfile.mkdtemp()
    fails = 0
    for n in names:
        a, b = os.path.join(tmp, n + "_atb.p3d"), os.path.join(tmp, n + "_native.p3d")
        skygeo.export_p3d_atb(B[n](), KIT_MATS, a)
        W.write_mlod(B[n](), KIT_MATS, b)
        da, db = open(a, "rb").read(), open(b, "rb").read()
        if da == db:
            print("IDENTICAL", n, len(da))
            continue
        why = compare(da, db)
        if why:
            print("DIFF", n, why)
            fails += 1
        else:
            print("MATCH", n, len(da), "(identical but for normal rounding < 1e-3)")
    if fails:
        print("P3D WRITER TEST: %d FAILED" % fails)
        sys.exit(1)
    print("P3D WRITER TEST: PASS (%d models)" % len(names))


if __name__ == "__main__":
    main()
