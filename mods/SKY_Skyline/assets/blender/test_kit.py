"""Static geometry tests for every kit asset (run headless in Blender, no export).

    blender -b --factory-startup -P test_kit.py [-- --only A,B]

For every skyspec.KIT asset that has a registered builder (build_kit, build_props,
build_floors):
  * every ComponentNN in Geometry / Fire / View Geometry is watertight
    (each edge shared by exactly 2 faces) and Geometry has mass
  * 3+ resolution LODs, Geometry + Fire Geometry present
  * street modules snap to the 12 m grid: road tops at z = 0, sidewalk tops at
    curb height, footprints exactly the documented tile sizes
Exit code 1 on failure.
"""
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import skyspec as S  # noqa: E402

FAIL = []


def check(c, m):
    if not c:
        FAIL.append(m)


def watertight(lod, comp):
    vs = lod.groups[comp]
    edges = Counter()
    for idx, _m, _uv in lod.faces:
        if set(idx) <= vs:
            for a, b in zip(idx, idx[1:] + idx[:1]):
                edges[(min(a, b), max(a, b))] += 1
    return edges and all(n == 2 for n in edges.values())


def bounds(lod):
    xs = [v[0] for v in lod.verts]
    ys = [v[1] for v in lod.verts]
    zs = [v[2] for v in lod.verts]
    return (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))


SNAP = {  # name: (x0, x1, y0, y1, top_z)
    "Road_Straight": (-4, 4, -6, 6, 0.0), "Road_Crossing": (-4, 4, -6, 6, 0.0),
    "Intersection_4Way": (-6, 6, -6, 6, 0.0), "Intersection_T": (-6, 6, -6, 6, S.STREET["curb_h"]),
    "Sidewalk": (-1, 1, -6, 6, S.STREET["curb_h"]), "Sidewalk_Corner": (-1, 1, -1, 1, S.STREET["curb_h"]),
    "Street_Straight": (-6, 6, -6, 6, S.STREET["curb_h"]), "Street_Crossing": (-6, 6, -6, 6, S.STREET["curb_h"]),
    "Street_Intersection": (-6, 6, -6, 6, S.STREET["curb_h"]),
}


def self_check():
    """The watertight test must reject an open box (guards against a vacuous test)."""
    from skygeo import LOD_GEOMETRY, Lod
    t = Lod("t", LOD_GEOMETRY)
    t.box(0, 1, 0, 1, 0, 1)
    check(watertight(t, "Component01"), "self-check: closed box reported open")
    t.faces.pop()
    check(not watertight(t, "Component01"), "self-check: open box reported watertight")


def main():
    self_check()
    builders = {}
    for modname in ("build_kit", "build_props", "build_floors"):
        try:
            m = __import__(modname)
        except ImportError:
            continue
        for n, (fn, _pbo, _p3d) in m.modules().items():
            builders[n] = fn
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    names = argv[argv.index("--only") + 1].split(",") if "--only" in argv else list(builders)
    missing = [n for n in S.KIT if n not in builders]
    check(not missing, "KIT entries without a builder: %s" % missing)
    for n in names:
        lods = {l.name: l for l in builders[n]()}
        res = [k for k in lods if k.startswith("res")]
        check(len(res) >= 3, "%s: only %d resolution LODs" % (n, len(res)))
        if not S.KIT[n]["collide"]:
            check("geo" not in lods and "fire" not in lods, "%s: decal must not have Geometry/Fire" % n)
            if S.KIT[n]["category"] == "flat":
                check("road" in lods, "%s: flat decal needs a Roadway LOD" % n)
            continue
        for k in ("geo", "fire"):
            check(k in lods and lods[k].verts, "%s: missing %s" % (n, k))
        check(lods["geo"].mass > 0, "%s: Geometry has no mass" % n)
        if S.KIT[n]["category"] in ("small", "medium"):
            check("shadow" in lods and lods["shadow"].verts, "%s: no Shadow Volume" % n)
        for k in ("geo", "fire", "view"):
            if k not in lods:
                continue
            comps = [g for g in lods[k].groups if g.startswith("Component")]
            check(comps, "%s %s: no components" % (n, k))
            for c in comps:
                check(watertight(lods[k], c), "%s %s %s is not watertight" % (n, k, c))
        if n in SNAP:
            x0, x1, y0, y1, top = SNAP[n]
            b = bounds(lods["geo"])
            check(abs(b[0] - x0) < 1e-6 and abs(b[1] - x1) < 1e-6 and abs(b[2] - y0) < 1e-6 and abs(b[3] - y1) < 1e-6,
                  "%s footprint %s != %s" % (n, b[:4], (x0, x1, y0, y1)))
            check(abs(b[5] - top) < 1e-6, "%s top z %.3f != %.3f" % (n, b[5], top))
            deep = -S.STREET["slab_t"] - S.STREET["skirt"]
            check(b[4] <= deep + 1e-6, "%s collision stops at z %.2f, skirt needs %.2f (security M1)" % (n, b[4], deep))
    if FAIL:
        print("KIT GEOMETRY TESTS: %d FAILED" % len(FAIL))
        for f in FAIL:
            print("  FAIL", f)
        sys.exit(1)
    print("KIT GEOMETRY TESTS: PASS (%d assets)" % len(names))


if __name__ == "__main__":
    main()
