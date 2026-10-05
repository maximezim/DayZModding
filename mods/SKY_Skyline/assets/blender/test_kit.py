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


def rotate(p, a, b, ang):
    """Rotate point p about axis a->b by ang (right-hand rule, Rodrigues)."""
    import math
    k = [b[i] - a[i] for i in range(3)]
    n = math.sqrt(sum(x * x for x in k))
    k = [x / n for x in k]
    v = [p[i] - a[i] for i in range(3)]
    c, s_ = math.cos(ang), math.sin(ang)
    kv = sum(k[i] * v[i] for i in range(3))
    kxv = [k[1] * v[2] - k[2] * v[1], k[2] * v[0] - k[0] * v[2], k[0] * v[1] - k[1] * v[0]]
    return [a[i] + v[i] * c + kxv[i] * s_ + k[i] * kv * (1 - c) for i in range(3)]


def dist(p, q):
    return sum((p[i] - q[i]) ** 2 for i in range(3)) ** 0.5


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
        for d in S.KIT[n].get("doors", []):
            dn = d["name"]
            for k in ("res0", "res1", "geo", "fire"):
                check(dn in lods[k].groups, "%s %s: door selection %s missing" % (n, k, dn))
            if "shadow" in lods:
                check(dn in lods["shadow"].groups, "%s shadow: door selection %s missing (shadow would not swing)" % (n, dn))
            mem = lods.get("mem")
            check(mem is not None, "%s: doors need a Memory LOD" % n)
            if mem is not None:
                check(len(mem.groups.get(dn + "_axis", ())) == 2, "%s: %s_axis must have 2 points" % (n, dn))
                for pt in (dn + "_action", dn):
                    check(len(mem.groups.get(pt, ())) == 1, "%s: memory point %s missing" % (n, pt))
            # swing test (security batch-3 L1): rotate the Geometry leaf by its configured angle
            # (right-hand rule about axis p0 -> p1, the P1 convention); its centre must move
            # toward the action point (outward), never back into the carcass / wall.
            if mem is not None and dn in lods["geo"].groups and len(mem.groups.get(dn + "_axis", ())) == 2:
                p0, p1 = (mem.verts[i] for i in sorted(mem.groups[dn + "_axis"]))
                act = mem.verts[next(iter(mem.groups[dn + "_action"]))]
                ang = S.DOOR_SWING_SIGN * d["orient"] * S.DOOR_OPEN_ANGLE * d["scale"]
                leaf = [lods["geo"].verts[i] for i in lods["geo"].groups[dn]]
                c0 = [sum(v[j] for v in leaf) / len(leaf) for j in range(3)]
                c1 = rotate(c0, p0, p1, ang)
                check(dist(c1, act) < dist(c0, act) - 0.02, "%s: door %s swings away from its action point (inward)" % (n, dn))
            # the door leaf must be its own Geometry component (Doors component = selection)
            if dn in lods["geo"].groups:
                gv = lods["geo"].groups[dn]
                comps = [g for g, v in lods["geo"].groups.items() if g.startswith("Component") and v & gv]
                check(len(comps) == 1 and lods["geo"].groups[comps[0]] == gv,
                      "%s: door %s is not exactly one Geometry component" % (n, dn))
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
