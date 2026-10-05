"""Geometry tests for the procedural city buildings (D56) - run headless in Blender, no export.

    blender -b --factory-startup --python-exit-code 1 -P test_city.py [-- --only City_Rowhouse_Intact]

Per class (all archetypes x Intact / Damaged / Ruined):
  * LOD set of an enterable building, Geometry mass + autocenter=0, watertight components
  * Geometry inside the footprint (front = -Y), nothing below the foundation skirt
  * front door (Intact / Damaged): Doors rig like the props (selection in Res/Geo/Fire/Shadow,
    2-point axis, action point, one Geometry component) and it swings toward its action point
    (inside) under P1; Ruined: no door, no glass anywhere
  * stairs: two flight solids per storey inside the stair well
  * walkability per level (0.1 m grid, 0.3 m player radius, doors open): every free floor area
    > 1 m2 is reachable from the entrance (ground) or the stair landing (upper levels)
  * loot points (assets/city_loot.json): on a floor, clear of solids, reachable; JSON up to date
Exit code 1 on failure.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import build_city as C  # noqa: E402
import skyspec as S  # noqa: E402
from test_kit import comp_boxes, dist, rotate, watertight  # noqa: E402

FAIL = []
NEED = ("res0", "res1", "res2", "res3", "shadow", "geo", "view", "fire", "road", "mem")


def check(c, m):
    if not c:
        FAIL.append(m)


def door_comps(geo):
    names = [g for g in geo.groups if not g.startswith("Component")]
    out = set()
    for g, v in geo.groups.items():
        if g.startswith("Component") and any(v <= geo.groups[n] for n in names):
            out.add(g)
    return out


def flood(P, lods, l, cell=0.1, radius=0.3):
    """Reachable cells of level l (set of (i, j)) and the free-but-unreached regions."""
    geo = lods["geo"]
    skip = door_comps(geo)
    boxes = [(g, b) for g, b in comp_boxes(geo)]
    use, fh, z = P.levels[l]
    floor = [b for g, b in boxes if abs(b[5] - z) < 0.05]
    block = [b for g, b in boxes if g not in skip and b[4] < z + 1.9 and b[5] > z + 0.1 + 0.25]
    block = [(b[0] - radius, b[1] + radius, b[2] - radius, b[3] + radius) for b in block]
    x0, y0 = P.ix0, P.iy0
    nx, ny = int((P.ix1 - P.ix0) / cell), int((P.iy1 - P.iy0) / cell)
    free = [[False] * ny for _ in range(nx)]
    for i in range(nx):
        cx = x0 + (i + 0.5) * cell
        for j in range(ny):
            cy = y0 + (j + 0.5) * cell
            if not any(b[0] <= cx <= b[1] and b[2] <= cy <= b[3] for b in floor):
                continue
            free[i][j] = not any(b[0] < cx < b[1] and b[2] < cy < b[3] for b in block)
    if l == 0:
        seed = ((P.door[0] + P.door[1]) / 2, P.iy0 + 0.35)
    else:
        seed = ((P.stair[0] + P.stair[1]) / 2, P.stair[2] + 0.6)
    si, sj = int((seed[0] - x0) / cell), int((seed[1] - y0) / cell)
    check(0 <= si < nx and 0 <= sj < ny and free[si][sj], "%s level %d: seed %s is not walkable" % (P.name, l, seed))
    seen = set()
    stack = [(si, sj)] if (0 <= si < nx and 0 <= sj < ny and free[si][sj]) else []
    while stack:
        i, j = stack.pop()
        if (i, j) in seen:
            continue
        seen.add((i, j))
        for a, b in ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)):
            if 0 <= a < nx and 0 <= b < ny and free[a][b] and (a, b) not in seen:
                stack.append((a, b))
    lost = {(i, j) for i in range(nx) for j in range(ny) if free[i][j] and (i, j) not in seen}
    while lost:
        st = [lost.pop()]
        region = []
        while st:
            c = st.pop()
            region.append(c)
            for d in ((c[0] + 1, c[1]), (c[0] - 1, c[1]), (c[0], c[1] + 1), (c[0], c[1] - 1)):
                if d in lost:
                    lost.discard(d)
                    st.append(d)
        if len(region) * cell * cell > 1.0:
            i, j = region[0]
            cx = x0 + sum(c[0] for c in region) / len(region) * cell
            cy = y0 + sum(c[1] for c in region) / len(region) * cell
            if P.near_collapse(cx, cy, l):
                continue                                  # sealed by the collapse (allowed, no loot there)
            check(False, "%s level %d: %.1f m2 unreachable (near x %.1f, y %.1f)"
                  % (P.name, l, len(region) * cell * cell, x0 + i * cell, y0 + j * cell))
    return seen, (x0, y0, cell)


def test_class(name, fresh_loot):
    e = S.KIT[name]
    arch, state = e["city"]["archetype"], e["city"]["ruin"]
    P = C.Plan(arch, state)
    lods = {l.name: l for l in C.BUILDERS[name]()}
    fresh_loot.update(C.LOOT_OUT)
    for k in NEED:
        check(k in lods and lods[k].verts, "%s: missing LOD %s" % (name, k))
    geo = lods["geo"]
    check(geo.mass > 0 and geo.props.get("autocenter") == "0", "%s: Geometry mass / autocenter" % name)
    for k in ("geo", "view", "fire"):
        for g in lods[k].groups:
            if g.startswith("Component"):
                check(watertight(lods[k], g), "%s %s %s is not watertight" % (name, k, g))
    xs = [v[0] for v in geo.verts]
    ys = [v[1] for v in geo.verts]
    zs = [v[2] for v in geo.verts]
    check(min(xs) >= -P.hw - 1e-6 and max(xs) <= P.hw + 1e-6 and min(ys) >= -P.hd - 1e-6 and max(ys) <= P.hd + 1e-6,
          "%s: Geometry leaves the %gx%g footprint" % (name, P.W, P.D))
    check(min(zs) >= -S.CITY_STYLE["skirt"] - 1e-6, "%s: Geometry below the foundation skirt" % name)
    # doors
    for d in e.get("doors", []):
        dn = d["name"]
        for k in ("res0", "res1", "geo", "fire", "shadow"):
            check(dn in lods[k].groups, "%s %s: door selection %s missing" % (name, k, dn))
        mem = lods["mem"]
        check(len(mem.groups.get(dn + "_axis", ())) == 2, "%s: %s_axis must have 2 points" % (name, dn))
        for pt in (dn + "_action", dn):
            check(len(mem.groups.get(pt, ())) == 1, "%s: memory point %s missing" % (name, pt))
        p0, p1 = (mem.verts[i] for i in sorted(mem.groups[dn + "_axis"]))
        act = mem.verts[next(iter(mem.groups[dn + "_action"]))]
        leaf = [geo.verts[i] for i in geo.groups[dn]]
        c0 = [sum(v[j] for v in leaf) / len(leaf) for j in range(3)]
        c1 = rotate(c0, p0, p1, -d["orient"] * S.DOOR_OPEN_ANGLE * d["scale"])
        check(dist(c1, act) < dist(c0, act) - 0.02, "%s: door %s swings away from its action point" % (name, dn))
        gv = geo.groups[dn]
        comps = [g for g, v in geo.groups.items() if g.startswith("Component") and v & gv]
        check(len(comps) == 1 and geo.groups[comps[0]] == gv, "%s: door %s is not exactly one component" % (name, dn))
    if state == 2:
        check(not e.get("doors"), "%s: a ruin keeps no door" % name)
        for k in ("res0", "res1", "res2"):
            mats = {f[1] for f in lods[k].faces}
            check("glass" not in mats, "%s %s: glass left in a ruin" % (name, k))
    # stairs: two flight solids per storey
    if P.stair:
        x0, x1, y0, y1 = P.stair
        for l in range(len(P.levels) - 1):
            z0, z1 = P.levels[l][2], P.levels[l + 1][2]
            flights = [b for g, b in comp_boxes(geo) if x0 - 1e-6 <= b[0] and b[1] <= x1 + 1e-6 and y0 + 1.1 <= b[2]
                       and b[4] < z0 + 0.1 and b[5] > z0 + 1.0 and b[5] <= z1 + 0.01]
            flights += [b for g, b in comp_boxes(geo) if x0 - 1e-6 <= b[0] and b[1] <= x1 + 1e-6 and y0 + 1.1 <= b[2]
                        and abs(b[5] - z1) < 0.01 and b[4] < z1 - 1.0 and b[1] - b[0] < 1.5]
            check(len(flights) >= 2, "%s: stair flights missing between level %d and %d" % (name, l, l + 1))
    # walkability + loot
    reach = {l: flood(P, lods, l) for l in range(len(P.levels))}
    for p in C.LOOT_OUT.get(e["cls"], []):
        x, y, z = p
        l = min(range(len(P.levels)), key=lambda k: abs(P.levels[k][2] - z))
        seen, (gx0, gy0, cell) = reach[l]
        i, j = int((x - gx0) / cell), int((y - gy0) / cell)
        check((i, j) in seen, "%s: loot point (%g, %g, %g) is not reachable" % (name, x, y, z))
    check(len(C.LOOT_OUT.get(e["cls"], [])) >= 1, "%s: no loot points" % name)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    names = argv[argv.index("--only") + 1].split(",") if "--only" in argv else sorted(C.BUILDERS)
    fresh = {}
    for n in names:
        test_class(n, fresh)
    if "--only" not in argv:
        cur = json.load(open(C.LOOT_JSON)) if os.path.exists(C.LOOT_JSON) else {}
        norm = {k: [list(p) for p in v] for k, v in fresh.items()}
        check(cur == norm, "assets/city_loot.json is stale - re-run build_city.py")
    if FAIL:
        print("CITY GEOMETRY TESTS: %d FAILED" % len(FAIL))
        for f in FAIL:
            print("  FAIL", f)
        sys.exit(1)
    print("CITY GEOMETRY TESTS: PASS (%d buildings)" % len(names))


if __name__ == "__main__":
    main()
