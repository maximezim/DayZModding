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
import math
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


def _halfspaces(lod, g):
    """Outward planes (n, d) of a convex Geometry component (the engine requires convex components)."""
    import numpy as np
    vs = lod.groups[g]
    P = np.array([lod.verts[i] for i in vs], float)
    cen = P.mean(0)
    out = []
    for idx, _m, _u in lod.faces:
        if not set(idx) <= vs:
            continue
        p = np.array([lod.verts[i] for i in idx[:3]], float)
        n = np.cross(p[1] - p[0], p[2] - p[0])
        ln = np.linalg.norm(n)
        if ln < 1e-12:
            continue
        n /= ln
        d = n @ p[0]
        if n @ cen - d > 0:
            n, d = -n, -d
        out.append((n, d))
    return out


def _gap_mask(occ, cell, lo, hi):
    """Free cells lying in a lo..hi wide gap between solid cells along axis 0 (vectorised)."""
    import numpy as np
    n = occ.shape[0]
    idx = np.arange(n)[:, None] * np.ones((1, occ.shape[1]), int)
    prv = np.maximum.accumulate(np.where(occ, idx, -1), axis=0)
    nxt = np.minimum.accumulate(np.where(occ, idx, n)[::-1], axis=0)[::-1]
    w = (nxt - prv - 1) * cell
    return ~occ & (prv >= 0) & (nxt < n) & (w > lo) & (w < hi)


def _longest_run(mask):
    """Longest run of True along axis 0 or 1 (cells)."""
    import numpy as np
    best = 0
    for m in (mask, mask.T):
        cur = np.zeros(m.shape[1], int)
        for row in m:
            cur = np.where(row, cur + 1, 0)
            best = max(best, int(cur.max(initial=0)))
    return best


def wedge_voxel(lod, cell=0.05, lo=0.15, hi=0.6, run=1.0, heights=(0.2, 0.4, 0.65, 0.9, 1.3, 1.6), margin=0.7, floors=(0.0,),
                angles=(0.0, 22.5, 45.0, 67.5)):
    """D91: wedge slots next to the non-box (sloped / round) components the box test skips. Convex components are
    rasterised exactly on a `cell` grid round each one; a cell is a slot cell when, along x or y, it lies in a free gap
    lo..hi wide between solid cells at two body heights at least 0.5 m apart (of prone 0.2, crouch 0.4, chest 0.9,
    head 1.6: sides tall enough to hold a body - cinema legroom, 0.25-0.45 m deep, is stepped over); a slot is a run
    of such cells >= `run` along the gap. The grid is laid at 0 / 22.5 / 45 / 67.5 degrees so diagonal gaps are
    measured across, not along x / y (sec review H). Vectorised; regions without a neighbour skip (perf review)."""
    import numpy as np
    boxes = dict(comp_boxes(lod))
    raw = set(comp_boxes_raw(lod))
    nonbox = [g for g in boxes if boxes[g] not in raw]
    if not nonbox:
        return []
    faces_of = {}
    for idx, m, u in lod.faces:                                          # faces grouped by component, one pass
        for g in boxes:
            if idx[0] in lod.groups[g]:
                faces_of.setdefault(g, []).append((idx, m, u))
                break
    hs = {}

    def halfspaces(g):
        if g not in hs:
            tmp = type("L", (), {})()
            tmp.verts, tmp.faces, tmp.groups = lod.verts, faces_of.get(g, []), lod.groups
            hs[g] = _halfspaces(tmp, g)
        return hs[g]

    found = []
    for g, fz in [(g, fz) for g in nonbox for fz in floors]:
        b = boxes[g]
        hz = [fz + h for h in heights]
        if b[4] > max(hz) or b[5] < min(hz):
            continue
        x0, x1, y0, y1 = b[0] - margin, b[1] + margin, b[2] - margin, b[3] + margin
        near = [h for h, bb in boxes.items() if bb[0] < x1 and bb[1] > x0 and bb[2] < y1 and bb[3] > y0
                and bb[4] <= max(hz) and bb[5] >= min(hz)]
        if not [h for h in near if h != g]:
            continue
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        R = 0.5 * math.hypot(x1 - x0, y1 - y0)                              # rotated grids cover the region's circle
        us = np.arange(-R, R, cell) + cell / 2
        U, V = np.meshgrid(us, us, indexing="ij")
        best = 0
        for ang in angles:
            ca, sa = math.cos(math.radians(ang)), math.sin(math.radians(ang))
            pts = np.stack([cx + ca * U.ravel() - sa * V.ravel(), cy + sa * U.ravel() + ca * V.ravel(), np.zeros(U.size)], 1)
            per, occs = {}, {}
            for z in hz:
                pts[:, 2] = z
                occ = np.zeros(len(pts), bool)
                for h in near:
                    if not (boxes[h][4] <= z <= boxes[h][5]) or not halfspaces(h):
                        continue
                    ins = np.ones(len(pts), bool)
                    for n, d in halfspaces(h):
                        ins &= pts @ n - d <= 1e-4
                    occ |= ins
                if not occ.any():
                    continue
                occ = occ.reshape(U.shape)
                occs[z] = occ
                per[z] = _gap_mask(occ, cell, lo, hi) | _gap_mask(occ.T, cell, lo, hi).T
            for za in per:
                for zb in per:
                    if zb - za >= 0.5 - 1e-6:
                        best = max(best, _longest_run(per[za] & per[zb]))
            # D93 prone pocket: a gap at the lowest height with solid right above it at chest height (a body slides
            # in lying down and cannot stand up) - cinema legroom is open above, so it stays out
            z0_ = min(hz)
            covers = [occs[z] for z in occs if z0_ < z <= z0_ + 1.2]              # sec review: 0.4 / 0.9 (and to 1.4 m)
            if z0_ in per and covers:
                best = max(best, _longest_run(per[z0_] & np.logical_or.reduce(covers)))
            if best * cell >= run:
                break
        if best * cell >= run:
            found.append((g, round(best * cell, 2), tuple(round(v, 2) for v in b), fz))
    return found


def voxel_selftest():
    """D91: a hexagonal column (not a box) with a 1.2 m flat side 0.35 m off a wall is a slot; 0.8 m off and flush
    are not; a round r 0.6 column 0.35 m off is not (the gap stays under 0.6 m for only ~0.96 m)."""
    import math
    from skygeo import Lod, LOD_GEOMETRY
    for gap, n, r, want in ((0.35, 6, 1.2, 1), (0.8, 6, 1.2, 0), (0.05, 6, 1.2, 0), (0.35, 16, 0.6, 0)):
        L = Lod("geo", LOD_GEOMETRY)
        L.box(-3.0, 3.0, 0.0, 0.3, 0.0, 2.0)                                    # wall
        a = r * math.cos(math.pi / n)                                          # apothem: flat side towards the wall
        L.prism(0.0, 0.3 + gap + (a if n == 6 else r), r, 0.0, 2.0, n=n)
        got = len(wedge_voxel(L))
        check(got == want, "voxel selftest: n=%d gap %.2f -> %d slots (want %d)" % (n, gap, got, want))
    for gap, cover, want in ((0.35, True, 1), (0.35, False, 0), (0.8, True, 0), (0.35, "low", 1)):   # D93: prone pockets
        L = Lod("geo", LOD_GEOMETRY)
        L.box(-3.0, 3.0, 0.0, 0.3, 0.0, 2.0)                                    # wall
        a = 1.2 * math.cos(math.pi / 6)
        L.prism(0.0, 0.3 + gap + a, 1.2, 0.0, 0.3, n=6)                         # a low hexagonal plinth (0.3 m)
        if cover == "low":
            L.box(-1.5, 1.5, 0.0, 0.3 + gap + 2 * a, 0.5, 0.8)                  # sec review: a slab at 0.5-0.8 m
        elif cover:
            L.box(-1.5, 1.5, 0.0, 0.3 + gap + 2 * a, 0.7, 1.0)                  # a slab over plinth and gap (0.7-1.0)
        got = len(wedge_voxel(L))
        check(got == want, "voxel selftest: pocket gap %.2f cover %s -> %d slots (want %d)" % (gap, cover, got, want))
    for gap, want in ((0.3, 1), (0.45, 1), (0.9, 0)):                       # two 45-degree square columns (sec review H)
        L = Lod("geo", LOD_GEOMETRY)
        r = 1.5
        L.prism(0.0, 0.0, r, 0.0, 2.0, n=4)                                     # a diamond: edges at 45 degrees
        k = (r * math.sqrt(2) + gap) / math.sqrt(2)
        L.prism(k, k, r, 0.0, 2.0, n=4)
        got = len(wedge_voxel(L))
        check(got >= want and (want or got == 0), "voxel selftest: diagonal gap %.2f -> %d slots (want %d)" % (gap, got, want))


def comp_boxes_raw_set(lod):
    return set(comp_boxes_raw(lod))


ACCEPTED_VOXEL = {}

ACCEPTED_PANES = {}     # {(asset, centre): reason} - none left once Geometry is consulted (D91 sec review L)


def geo_halfspaces(lod):
    """Halfspaces of every Geometry component; None for a non-convex one (reported by convexity())."""
    return [_halfspaces(lod, g) for g in lod.groups if g.startswith("Component")]


def convexity(lod):
    """D91 (sec review L): components must be convex (the engine requires it; the voxel test assumes it)."""
    bad = []
    for g in lod.groups:
        if not g.startswith("Component"):
            continue
        h = _halfspaces(lod, g)
        if any(any(lod.verts[i][0] * n[0] + lod.verts[i][1] * n[1] + lod.verts[i][2] * n[2] - d > 1e-3 for n, d in h)
               for i in lod.groups[g]):
            bad.append(g)
    return bad


def one_sided_panes(lod, geo=None):
    from test_city import one_sided_panes as osp
    return osp(lod, geo_halfspaces(geo) if geo is not None else None)


def comp_boxes_raw(lod):
    """Axis-aligned box components only (every vertex on its bounding box's corners): a sloped part (Ferris wheel
    A-frame legs, ramps) would be compared by a bounding box far larger than the part (D90 false positives)."""
    out = []
    for g, b in comp_boxes(lod):
        pts = [lod.verts[i] for i in lod.groups[g]]
        if all(any(abs(p[j] - b[2 * j + s]) < 1e-4 for s in (0, 1)) for p in pts for j in range(3)):
            out.append(b)
    return out


WEDGE_SKIPPED = [0]


class _Ground:
    """build_city.wedge_slots asks P.levels for the floor heights: kit props stand on z = 0 (floor / roof modules too)."""
    levels = [("ground", 0.0, 0.0)]


GROUND = _Ground()


def WEDGE(bx, P):
    from build_city import wedge_slots
    return wedge_slots(bx, P)


def hull_slits(lod, tol=0.001, max_gap=0.3, min_overlap=0.05):
    """D74 hull test: two components stacked over each other (footprints overlap by more than min_overlap m on
    both axes) must touch or overlap vertically within tol; a gap of tol..max_gap is a slit bullets, sight or
    a camera pass through (the first D73 sedan draft had a 1 cm one between body and cabin). Vehicle-like props
    (wrecks, sky_vehicles) use max_gap 0.3 m; other props 0.05 m (designed openings - the space under a bin's
    bucket, a truck's wheel arches - are wider than that)."""
    doors = [v for g, v in lod.groups.items() if not g.startswith("Component")]
    boxes = [(g, b) for g, b in comp_boxes(lod)                                  # door leaves need clearance: skipped
             if not any(lod.groups[g] <= d for d in doors)]
    out = []
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            (ga, a), (gb, b) = boxes[i], boxes[j]
            ox = min(a[1], b[1]) - max(a[0], b[0])
            oy = min(a[3], b[3]) - max(a[2], b[2])
            if ox <= min_overlap or oy <= min_overlap:
                continue
            gap = max(b[4] - a[5], a[4] - b[5])
            if tol < gap <= max_gap:
                out.append("%.3f m slit between %s and %s" % (gap, ga, gb))
    for i in range(len(boxes)):                                                  # side by side (security D74 L)
        for j in range(i + 1, len(boxes)):
            (ga, a), (gb, b) = boxes[i], boxes[j]
            oz = min(a[5], b[5]) - max(a[4], b[4])
            if oz <= min_overlap:
                continue
            for ax in (0, 1):
                o = 1 - ax
                ov = min(a[2 * o + 1], b[2 * o + 1]) - max(a[2 * o], b[2 * o])
                gap = max(b[2 * ax] - a[2 * ax + 1], a[2 * ax] - b[2 * ax + 1])
                if ov > min_overlap and tol < gap <= max_gap:
                    out.append("%.3f m side slit between %s and %s" % (gap, ga, gb))
    return out


# Clear zones in front of the unchanged core's doors on every level (1.2 m deep, door
# height + 0.1), plus the core footprint itself (the core P3D occupies it).
_C = S.CORE
CORE_CLEAR = {
    "stair door": (_C["stair_door_x"][0], _C["stair_door_x"][1], _C["y"][0] - 1.2, _C["y"][0], 0.0, 2.2),
    "elevator door": (-_C["door_w"] / 2, _C["door_w"] / 2, _C["y"][1], _C["y"][1] + 1.2, 0.0, _C["door_h"] + 0.1),
    "core footprint": (_C["x"][0], _C["x"][1], _C["y"][0], _C["y"][1], -S.SLAB_T, S.FLOOR_H),
}


def reachability(n, lods, cell=0.1, radius=0.3):
    """Flood fill over the walkable slab (security batch-4 H1): 0.1 m grid, blockers grown by a
    0.3 m player radius (QA L-R1), blocked by every
    Geometry component spanning body height (z 0.1..1.9) and by the core footprint; seeds are
    the core's stair / elevator door clear zones. Any unreached free region > 1 m2 fails."""
    hw, hd = S.TOWER_A["footprint"][0] / 2, S.TOWER_A["footprint"][1] / 2
    nx, ny = int(round(2 * hw / cell)), int(round(2 * hd / cell))
    blockers = [b for _c, b in comp_boxes(lods["geo"]) if b[4] < 1.9 and b[5] > 0.1]
    blockers.append(CORE_CLEAR["core footprint"][:4] + (0.0, 2.0))
    # grow by the player radius so a gap narrower than a player blocks (QA re-gate L-R1)
    blockers = [(b[0] - radius, b[1] + radius, b[2] - radius, b[3] + radius, b[4], b[5]) for b in blockers]
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
            check(not overlaps(crate, CORE_CLEAR["core footprint"]), "%s: roof_drop_%d crate overlaps the core (QA L-R2)" % (n, i + 1))
            for comp, box in comp_boxes(lods["geo"]):
                check(not overlaps(crate, box), "%s: roof_drop_%d crate overlaps Geometry %s" % (n, i + 1, comp))
            check(hw - abs(x) - 0.75 >= 1.25 - 1e-6 and hd - abs(y) - 0.75 >= 1.25 - 1e-6,
                  "%s: roof_drop_%d crate closer than 1 m to the parapet" % (n, i + 1))
    # Roadway: no face may overlap the core hole (face bbox test - catches quads spanning it, QA batch-4 M2)
    road = lods["road"]
    hole = (_C["x"][0], _C["x"][1], _C["y"][0], _C["y"][1], -1.0, 1.0)
    for idx, _m, _uv in road.faces:
        pts = [road.verts[i] for i in idx]
        fb = tuple(f(p[j] for p in pts) for j in range(3) for f in (min, max))
        fb = fb[:4] + (fb[4] - 0.01, fb[5] + 0.01)
        check(not overlaps(fb, hole), "%s: a Roadway face covers the core hole" % n)
    occ = [g for g in lods["view"].groups if g.startswith("occluder_")]
    check(len(occ) >= 4, "%s: %d slab occluders (< 4)" % (n, len(occ)))
    for g in occ:                                   # no occluder may cover the core hole (QA L-R3)
        pts = [lods["view"].verts[i] for i in lods["view"].groups[g]]
        ob = tuple(f(p[j] for p in pts) for j in range(3) for f in (min, max))
        check(not overlaps(ob[:4] + (ob[4] - 0.01, ob[5] + 0.01), hole), "%s: %s covers the core hole" % (n, g))


def placed_box(box, x, y, yaw_deg):
    """XY bounds of a model-space box (x0, x1, y0, y1) rotated by a DayZ yaw (clockwise) and moved."""
    import math
    a = math.radians(yaw_deg)
    pts = [(u * math.cos(a) + v * math.sin(a), -u * math.sin(a) + v * math.cos(a))
           for u in box[:2] for v in box[2:]]
    return (x + min(p[0] for p in pts), x + max(p[0] for p in pts), y + min(p[1] for p in pts), y + max(p[1] for p in pts))


def module_builders():
    """{floor/roof class: builder} incl. Tower A's (read-only use of build_towera)."""
    import build_towera as T
    out = {S.CLASS_FLOOR: T.build_floor_office, S.CLASS_ROOF: T.build_roof_helipad, S.CLASS_LOBBY: T.build_lobby,
           S.CLASS_LOBBY_B: lambda: T.build_lobby("B")}
    try:
        import build_floors as F
        for n, (fn, _p, _f) in F.modules().items():
            out[S.KIT[n]["cls"]] = fn
    except ImportError:
        pass
    return out


def batch5_checks(builders):
    """Batch 5: PROP_BOX matches each prop's Geometry; every FURNISH set fits its floors
    (no prop inside walls / core zones, rooms stay reachable around the furniture); every
    LOOT point lies on open floor (not inside Geometry, the core or a furnish prop)."""
    for name, box in S.PROP_BOX.items():
        b = bounds({l.name: l for l in builders[name]()}["geo"])
        check(all(abs(b[i] - box[i]) < 1e-6 for i in range(4)), "PROP_BOX[%s] %s != Geometry %s" % (name, box, b[:4]))
    mods = module_builders()
    cache = {}

    def lods_of(cls):
        if cls not in cache:
            cache[cls] = {l.name: l for l in mods[cls]()}
        return cache[cls]
    by_cls = {e["cls"]: n for n, e in S.KIT.items()}
    furnished = {}
    for set_name, fs in S.FURNISH.items():
        for cls in fs["for"]:
            lods = lods_of(cls)
            walls = [b for _c, b in comp_boxes(lods["geo"]) if b[4] < 1.9 and b[5] > 0.1]
            boxes = []
            for entry in fs["props"]:
                name, x, y, yaw = entry[:4]
                pz = entry[4] if len(entry) > 4 else 0.0
                pb = placed_box(S.PROP_BOX[name], x, y, yaw) + (pz + 0.05, pz + 1.0)
                for w in walls:
                    check(not overlaps(pb, w), "FURNISH %s on %s: %s at (%g, %g) hits a wall/unit" % (set_name, cls, name, x, y))
                for zone, cz in CORE_CLEAR.items():
                    check(not overlaps(pb, cz), "FURNISH %s on %s: %s at (%g, %g) blocks the core %s" % (set_name, cls, name, x, y, zone))
                boxes.append(pb)
            furnished.setdefault(cls, []).extend(boxes)
            # rooms must stay reachable with the furniture in place
            geo = lods["geo"]
            saved = (list(geo.verts), {k: set(v) for k, v in geo.groups.items()}, list(geo.faces), geo._component)
            for pb in boxes:
                geo.box(pb[0], pb[1], pb[2], pb[3], 0.05, 1.0)
            reachability("%s + FURNISH %s" % (by_cls.get(cls, cls), set_name), lods)
            geo.verts, geo.groups, geo.faces, geo._component = saved
    for cls, g in S.LOOT.items():
        if cls not in mods:
            continue                      # prop groups: checked against the prop below
        lods = lods_of(cls)
        comps = [b for _c, b in comp_boxes(lods["geo"])]
        for c in g["containers"]:
            for p in c["points"]:
                x, y = p[0], p[1]
                z = p[2] if len(p) == 5 else 0.0
                pt = (x - 0.05, x + 0.05, y - 0.05, y + 0.05, z + 0.05, z + 0.15)
                check(not any(overlaps(pt, b) for b in comps), "LOOT %s: point (%g, %g) inside Geometry" % (cls, x, y))
                check(not overlaps(pt, CORE_CLEAR["core footprint"]), "LOOT %s: point (%g, %g) inside the core" % (cls, x, y))
                for pb in furnished.get(cls, []):
                    check(not overlaps(pt, pb), "LOOT %s: point (%g, %g) inside a furnish prop" % (cls, x, y))
    for cls, g in S.LOOT.items():
        n = by_cls.get(cls)
        if n is None or n not in S.PROP_BOX:
            continue
        geo = {l.name: l for l in builders[n]()}["geo"]
        comps = [b for _c, b in comp_boxes(geo)]
        for c in g["containers"]:
            for p in c["points"]:
                x, y, z, rng = p[0], p[1], p[2], p[3]
                pb = S.PROP_BOX[n]
                check(pb[0] <= x <= pb[1] and pb[2] <= y <= pb[3], "LOOT %s: point (%g, %g) outside the prop" % (cls, x, y))
                pt = (x - rng, x + rng, y - rng, y + rng, z + 0.01, z + 0.1)
                check(not any(overlaps(pt, b) for b in comps), "LOOT %s: point (%g, %g, %g) inside its Geometry" % (cls, x, y, z))
                # must rest on a collision surface (QA batch-5 L1): a component under (x, y) with its top at z
                check(any(b[0] <= x <= b[1] and b[2] <= y <= b[3] and abs(b[5] - z) <= 0.03 for b in comps),
                      "LOOT %s: point (%g, %g, %g) does not rest on a Geometry surface" % (cls, x, y, z))


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


def skybridge_lanes():
    """Skybridge (D60): on every roof variant and every side, the landing lane (bridge width x
    SKYBRIDGE["landing"] m from the facade, at the lateral offset skyspec gives) holds no roof
    Geometry above the slab except the parapet, no roof-drop crate, and the deck clears the parapet."""
    B = S.SKYBRIDGE
    hw, hd = S.TOWER_A["footprint"][0] / 2, S.TOWER_A["footprint"][1] / 2
    w, d = B["half_w"], B["landing"]
    mods = module_builders()
    for rcls in S.ROOF_VARIANTS.values():
        lods = {l.name: l for l in mods[rcls]()}
        boxes = [b for _c, b in comp_boxes(lods["geo"]) if b[5] > 0.05]
        parapet = [b for b in boxes if b[1] - b[0] > 2 * hw - 1 or b[3] - b[2] > 2 * hd - 1]
        check(parapet and max(b[5] for b in parapet) <= B["deck_z"] - B["deck_t"] + 1e-6,
              "%s: parapet higher than the skybridge deck underside" % rcls)
        lanes = {"S": (B["lateral"]["NS"] - w, B["lateral"]["NS"] + w, -hd, -hd + d),
                 "N": (B["lateral"]["NS"] - w, B["lateral"]["NS"] + w, hd - d, hd),
                 "W": (-hw, -hw + d, B["lateral"]["EW"] - w, B["lateral"]["EW"] + w),
                 "E": (hw - d, hw, B["lateral"]["EW"] - w, B["lateral"]["EW"] + w)}
        for side, (x0, x1, y0, y1) in lanes.items():
            lane = (x0, x1, y0, y1, 0.05, B["deck_z"] + B["clear_h"])
            for b in boxes:
                if b in parapet:
                    continue
                check(not overlaps(lane, b), "%s: skybridge landing lane %s blocked by roof Geometry %s" % (rcls, side, b))
            for (px, py) in S.ROOF_DROP_POINTS[rcls]:
                crate = (px - 0.75, px + 0.75, py - 0.75, py + 0.75, 0.05, 1.55)
                check(not overlaps(lane, crate), "%s: skybridge landing lane %s over roof drop (%s, %s)" % (rcls, side, px, py))


def main():
    self_check()
    builders = {}
    for modname in ("build_kit", "build_props", "build_floors", "build_city", "build_landmarks", "build_creatures", "build_underground", "build_vehicles", "build_streetprops"):
        try:
            m = __import__(modname)
        except ImportError:
            continue
        for n, (fn, _pbo, _p3d) in m.modules().items():
            builders[n] = fn
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    names = argv[argv.index("--only") + 1].split(",") if "--only" in argv else [n for n in builders if n in S.KIT]
    convention_check()
    voxel_selftest()
    if "--only" not in argv:
        batch5_checks(builders)
        skybridge_lanes()
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
            if not S.KIT[n].get("city") and S.KIT[n]["category"] not in ("floor", "roof"):
                vehicle = n.startswith("Wreck_") or S.KIT[n]["pbo"] == "sky_vehicles"
                for why in hull_slits(lods[k], max_gap=0.3 if vehicle else 0.05):   # D74: stacked parts must touch
                    check(False, "%s %s: %s" % (n, k, why))
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
        if "geo" in lods and not S.KIT[n].get("city"):                   # D89: wedge slots on kit props (city: test_city)
            for sl in WEDGE(comp_boxes_raw(lods["geo"]), GROUND):
                check(False, "%s geo: wedge slot %.2f m wide over %.2f m between %s and %s" % (n, sl[0], sl[1], sl[2], sl[3]))
            WEDGE_SKIPPED[0] += sum(1 for g in lods["geo"].groups if g.startswith("Component")) - len(comp_boxes_raw(lods["geo"]))
            for g in convexity(lods["geo"]):
                check(False, "%s geo: %s is not convex" % (n, g))
            decks = sorted({0.0} | {round(v[2], 1) for v in lods["road"].verts} if "road" in lods else {0.0})
            for (g, r, b, _fz) in wedge_voxel(lods["geo"], floors=decks):     # D91: next to sloped / round parts
                if (n, g) not in ACCEPTED_VOXEL:
                    check(False, "%s geo: wedge slot over %.2f m next to non-box %s %s" % (n, r, g, b))
        for k in ("res0", "res1"):                                      # D91: no one-way glass (test_city.one_sided_panes)
            if k in lods and not S.KIT[n].get("city"):
                one = [c for c in one_sided_panes(lods[k], lods.get("geo")) if (n, c) not in ACCEPTED_PANES]
                check(not one, "%s %s: one-sided opaque glassfar panes at %s" % (n, k, one[:4]))
        if S.KIT[n]["category"] in ("floor", "roof"):
            module_checks(n, lods)
        if n in getattr(S, "LANDMARK_SIZE", {}):                    # D61: Geometry inside the placement footprint
            w, d = S.LANDMARK_SIZE[n]
            b = bounds(lods["geo"])
            check(b[0] >= -w / 2 - 1e-6 and b[1] <= w / 2 + 1e-6 and b[2] >= -d / 2 - 1e-6 and b[3] <= d / 2 + 1e-6,
                  "%s: Geometry %s leaves the %g x %g footprint" % (n, [round(v, 2) for v in b[:4]], w, d))
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
    print("WEDGE: %d non-box Geometry components checked by the voxel test (D91)" % WEDGE_SKIPPED[0])
    print("KIT GEOMETRY TESTS: PASS (%d assets)" % len(names))


def check_wiring():
    """D68: every sound set a script plays exists in sky_sounds config (with its .ogg), and every search
    table skyspec assigns is defined in SKY_Search.c (a missing one would make a spot silently empty)."""
    import glob
    import re
    addons = os.path.join(HERE, "..", "..", "addons")
    cfg = open(os.path.join(addons, "sky_sounds", "config.cpp")).read()
    sets = set(re.findall(r"class (SKY_\w+_SoundSet)", cfg))
    for m in re.findall(r'"SKY_Skyline\\sky_sounds\\data\\(\w+)"', cfg):
        check(os.path.isfile(os.path.join(addons, "sky_sounds", "data", m + ".ogg")), "sound %s.ogg missing" % m)
    used = set()
    for f in glob.glob(os.path.join(addons, "sky_scripts", "scripts", "*", "SKY", "*.c")):
        used |= set(re.findall(r'"(SKY_\w+_SoundSet)"', open(f).read()))
    for u in sorted(used):
        check(u in sets, "script plays %s, not in sky_sounds config" % u)
    search = open(os.path.join(addons, "sky_scripts", "scripts", "4_World", "SKY", "SKY_Search.c")).read()
    defined = set(re.findall(r'm_Tables\.Insert\("(\w+)"', search))
    for t in sorted(set(S.SEARCH_TABLE.values())):
        check(t in defined, "search table %s used in skyspec, not defined in SKY_Search.c" % t)
    oggs = re.findall(r'"SKY_Skyline\\sky_sounds\\data\\(\w+)"', cfg)
    check(len(oggs) == len(sets), "sky_sounds: %d samples for %d sound sets" % (len(oggs), len(sets)))
    return len(used), len(defined)


if __name__ == "__main__":
    print("WIRING: %d sound sets used, %d search tables" % check_wiring())
    main()
