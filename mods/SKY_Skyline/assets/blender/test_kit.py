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


def overlaps(a, b):
    """Strict overlap of two (x0, x1, y0, y1, z0, z1) boxes (touching is not overlap)."""
    return all(a[2 * i] < b[2 * i + 1] - 1e-6 and b[2 * i] < a[2 * i + 1] - 1e-6 for i in range(3))


def comp_boxes(lod):
    out = []
    for g, v in lod.groups.items():
        if g.startswith("Component"):
            pts = [lod.verts[i] for i in v]
            out.append((g, tuple(f(p[j] for p in pts) for j in range(3) for f in (min, max))))
    return out


# Clear zones in front of the unchanged core's doors on every level (1.2 m deep, door
# height + 0.1), plus the core footprint itself (the core P3D occupies it).
_C = S.CORE
CORE_CLEAR = {
    "stair door": (_C["stair_door_x"][0], _C["stair_door_x"][1], _C["y"][0] - 1.2, _C["y"][0], 0.0, 2.2),
    "elevator door": (-_C["door_w"] / 2, _C["door_w"] / 2, _C["y"][1], _C["y"][1] + 1.2, 0.0, _C["door_h"] + 0.1),
    "core footprint": (_C["x"][0], _C["x"][1], _C["y"][0], _C["y"][1], -S.SLAB_T, S.FLOOR_H),
}


def reachability(n, lods, cell=0.25):
    """Flood fill over the walkable slab (security batch-4 H1): 0.25 m grid, blocked by every
    Geometry component spanning body height (z 0.1..1.9) and by the core footprint; seeds are
    the core's stair / elevator door clear zones. Any unreached free region > 1 m2 fails."""
    hw, hd = S.TOWER_A["footprint"][0] / 2, S.TOWER_A["footprint"][1] / 2
    nx, ny = int(round(2 * hw / cell)), int(round(2 * hd / cell))
    blockers = [b for _c, b in comp_boxes(lods["geo"]) if b[4] < 1.9 and b[5] > 0.1]
    blockers.append(CORE_CLEAR["core footprint"][:4] + (0.0, 2.0))
    free = [[True] * ny for _ in range(nx)]
    for i in range(nx):
        for j in range(ny):
            x0, y0 = -hw + i * cell, -hd + j * cell
            c = (x0, x0 + cell, y0, y0 + cell, 0.1, 1.9)
            free[i][j] = not any(overlaps(c, b) for b in blockers)
    seen = [[False] * ny for _ in range(nx)]
    stack = []
    for zone in ("stair door", "elevator door"):
        z = CORE_CLEAR[zone]
        for i in range(nx):
            for j in range(ny):
                xc, yc = -hw + (i + 0.5) * cell, -hd + (j + 0.5) * cell
                if z[0] < xc < z[1] and z[2] < yc < z[3] and free[i][j]:
                    stack.append((i, j))
    check(stack, "%s: core door zones are blocked" % n)
    while stack:
        i, j = stack.pop()
        if seen[i][j] or not free[i][j]:
            continue
        seen[i][j] = True
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            a, b = i + di, j + dj
            if 0 <= a < nx and 0 <= b < ny and not seen[a][b] and free[a][b]:
                stack.append((a, b))
    lost = [[free[i][j] and not seen[i][j] for j in range(ny)] for i in range(nx)]
    for i in range(nx):
        for j in range(ny):
            if not lost[i][j]:
                continue
            region, st = [], [(i, j)]
            while st:
                a, b = st.pop()
                if not (0 <= a < nx and 0 <= b < ny) or not lost[a][b]:
                    continue
                lost[a][b] = False
                region.append((a, b))
                st += [(a + 1, b), (a - 1, b), (a, b + 1), (a, b - 1)]
            area = len(region) * cell * cell
            if area > 1.0:
                a, b = region[0]
                check(False, "%s: %.1f m2 unreachable from the core (near x %.1f, y %.1f)"
                      % (n, area, -hw + a * cell, -hd + b * cell))


def module_checks(n, lods):
    """Batch 4 floor / roof variants: same stacking and core as Tower A."""
    hw, hd = S.TOWER_A["footprint"][0] / 2, S.TOWER_A["footprint"][1] / 2
    for k in ("shadow", "view", "road", "mem"):
        check(k in lods and lods[k].verts, "%s: enterable module needs %s" % (n, k))
    b = bounds(lods["geo"])
    check(abs(b[0] + hw) < 1e-6 and abs(b[1] - hw) < 1e-6 and abs(b[2] + hd) < 1e-6 and abs(b[3] - hd) < 1e-6,
          "%s footprint %s != +-%g x +-%g" % (n, b[:4], hw, hd))
    check(abs(b[4] + S.SLAB_T) < 1e-6, "%s: slab underside %.3f != %.3f" % (n, b[4], -S.SLAB_T))
    if S.KIT[n]["category"] == "floor":
        top = S.FLOOR_H - S.SLAB_T
        check(b[5] <= top + 1e-6, "%s: Geometry reaches z %.2f, next slab starts at %.2f" % (n, b[5], top))
    for k in ("geo", "view", "fire"):
        for comp, box in comp_boxes(lods[k]):
            for zone, cz in CORE_CLEAR.items():
                check(not overlaps(box, cz), "%s %s %s blocks the core %s" % (n, k, comp, zone))
    reachability(n, lods)
    if S.KIT[n]["category"] == "roof":
        mem = lods["mem"]
        pts = S.ROOF_DROP_POINTS[S.KIT[n]["cls"]]
        for i, (x, y) in enumerate(pts):
            g = mem.groups.get("roof_drop_%d" % (i + 1))
            check(g and abs(mem.verts[next(iter(g))][0] - x) < 1e-6 and abs(mem.verts[next(iter(g))][1] - y) < 1e-6,
                  "%s: roof_drop_%d memory point != skyspec.ROOF_DROP_POINTS" % (n, i + 1))
            # supply crate ~1.5 m cube must fit, >= 1 m from the parapet (security batch-4 M1)
            crate = (x - 0.75, x + 0.75, y - 0.75, y + 0.75, 0.05, 1.55)
            for comp, box in comp_boxes(lods["geo"]):
                check(not overlaps(crate, box), "%s: roof_drop_%d crate overlaps Geometry %s" % (n, i + 1, comp))
            check(hw - abs(x) - 0.75 >= 1.25 - 1e-6 and hd - abs(y) - 0.75 >= 1.25 - 1e-6,
                  "%s: roof_drop_%d crate closer than 1 m to the parapet" % (n, i + 1))
    road = lods["road"]
    check(all(not (_C["x"][0] + 1e-6 < v[0] < _C["x"][1] - 1e-6 and _C["y"][0] + 1e-6 < v[1] < _C["y"][1] - 1e-6)
              for v in road.verts), "%s: Roadway covers the core hole" % n)


def convention_check():
    """P1 anchor: under the same convention the Tower A lobby door (read-only use of
    build_towera) must open INTO the security room, i.e. away from its action point."""
    import build_towera as T
    lods = {l.name: l for l in T.build_lobby()}
    dn, mem, geo = S.KEYCARD_DOOR["name"], lods["mem"], lods["geo"]
    p0, p1 = (mem.verts[i] for i in sorted(mem.groups[dn + "_axis"]))
    act = mem.verts[next(iter(mem.groups[dn + "_action"]))]
    leaf = [geo.verts[i] for i in geo.groups[dn]]
    c0 = [sum(v[j] for v in leaf) / len(leaf) for j in range(3)]
    c1 = rotate(c0, p0, p1, -S.DOOR_OPEN_ANGLE)   # sign-independent, see swing test below
    # signed check (QA batch-3 R-M1): the room lies on the +X side of the hinge (KEYCARD_DOOR
    # "swings inward (+X)"); a reversed swing would end on the -X (corridor) side.
    check(c1[0] - c0[0] > 0.3, "P1 convention: lobby door would not open into the room (+X)")


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
    convention_check()
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
            # swing test (security batch-3 L1, QA batch-3 H1): rotate the Geometry leaf by its
            # configured angle under the P1 convention (left-hand rule about axis p0 -> p1);
            # its centre must move toward the action point (outward), never into the carcass.
            if mem is not None and dn in lods["geo"].groups and len(mem.groups.get(dn + "_axis", ())) == 2:
                p0, p1 = (mem.verts[i] for i in sorted(mem.groups[dn + "_axis"]))
                act = mem.verts[next(iter(mem.groups[dn + "_action"]))]
                # DOOR_SWING_SIGN encodes the engine's rotation sense (P1), so the real swing is
                # sign-independent: right-hand angle = -orient * angle (see skyspec P1 comment).
                ang = d["orient"] * S.DOOR_OPEN_ANGLE * d["scale"]
                leaf = [lods["geo"].verts[i] for i in lods["geo"].groups[dn]]
                c0 = [sum(v[j] for v in leaf) / len(leaf) for j in range(3)]
                c1 = rotate(c0, p0, p1, -ang)             # left-hand rule = right-hand with -ang
                check(dist(c1, act) < dist(c0, act) - 0.02, "%s: door %s swings away from its action point (inward)" % (n, dn))
            # the door leaf must be its own Geometry component (Doors component = selection)
            if dn in lods["geo"].groups:
                gv = lods["geo"].groups[dn]
                comps = [g for g, v in lods["geo"].groups.items() if g.startswith("Component") and v & gv]
                check(len(comps) == 1 and lods["geo"].groups[comps[0]] == gv,
                      "%s: door %s is not exactly one Geometry component" % (n, dn))
        if S.KIT[n]["category"] in ("floor", "roof"):
            module_checks(n, lods)
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
