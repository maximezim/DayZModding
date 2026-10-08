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
# Sealed pockets excused next to a collapse, open to the floor above and with no edge on the hole to drop out of
# (a player could drop in and be stuck). D69 reported them; D72 fixed the generator and fails the test (P39).
POCKETS = []
NEED = ("res0", "res1", "res2", "res3", "shadow", "geo", "view", "fire", "road", "mem")


def check(c, m):
    if not c:
        FAIL.append(m)


def door_comps(geo):
    names = [g for g in geo.groups if not g.startswith("Component") and g != "rubble"]
    out = set()
    for g, v in geo.groups.items():
        if g.startswith("Component") and any(v <= geo.groups[n] for n in names):
            out.add(g)
    return out


def rubble_comps(geo):
    r = geo.groups.get("rubble", set())
    comps = {g for g, v in geo.groups.items() if g.startswith("Component") and r and v <= r}
    for g in comps:                                             # walked over only while it stays climbable (sec L)
        zs = [geo.verts[i][2] for i in geo.groups[g]]
        check(max(zs) - min(zs) <= 1.1 + 1e-6, "rubble pile %s is %.2f m high (max 1.1)" % (g, max(zs) - min(zs)))
    return comps


def flood(P, lods, l, cell=0.1, radius=0.3):
    """Reachable cells of level l (set of (i, j)) and the free-but-unreached regions."""
    geo = lods["geo"]
    skip = door_comps(geo) | rubble_comps(geo)                  # D72: rubble (<= 45 deg, Roadway) is walked over
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
            if not any(b[0] <= cx <= b[1] and b[2] <= cy <= b[3] for b in floor) or P.in_hole(cx, cy, l):
                continue                                  # no slab (stair / atrium / ramp / yard opening)
            free[i][j] = not any(b[0] < cx < b[1] and b[2] < cy < b[3] for b in block)
    if l == 0:
        seed = ((P.entry[0] + P.entry[1]) / 2, P.iy0 + 0.35)
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
                # D72 (P39): a trap = open to the floor above (a player can drop in) and no edge on the hole of this
                # level to drop out of; rubble is walkable (rubble_comps), so most pockets connect over it
                pts = [(x0 + (c[0] + 0.5) * cell, y0 + (c[1] + 0.5) * cell) for c in region]
                open_above = any(P.collapsed(x, y, l + 1) for x, y in pts)
                # exit = a step off the edge (no wall stub there) onto the floor one storey down (security D72 M)
                drop_ok = l > 0 and P.levels[l][2] - P.levels[l - 1][2] <= 4.6
                exit_down = drop_ok and any(
                    P.collapsed(x + dx, y + dy, l) and not P.collapsed(x + dx, y + dy, l - 1)
                    and not any(b[0] < x + dx < b[1] and b[2] < y + dy < b[3] for b in block)
                    for x, y in pts for dx, dy in ((0.4, 0), (-0.4, 0), (0, 0.4), (0, -0.4)))
                if open_above and not exit_down:
                    POCKETS.append("%s level %d (%.1f m2)" % (P.name, l, len(region) * cell * cell))
                continue                                  # sealed by the collapse (allowed, no loot there)
            check(False, "%s level %d: %.1f m2 unreachable (near x %.1f, y %.1f)"
                  % (P.name, l, len(region) * cell * cell, x0 + i * cell, y0 + j * cell))
    return seen, (x0, y0, cell)


def test_lot(name):
    """Rubble lots: LOD set, watertight parts, inside the 12 x 12 lot, walkable rubble, no loot / door."""
    lods = {l.name: l for l in C.BUILDERS[name]()}
    for k in NEED:
        check(k in lods and lods[k].verts, "%s: missing LOD %s" % (name, k))
    for k in ("geo", "view", "fire"):
        for g in lods[k].groups:
            if g.startswith("Component"):
                check(watertight(lods[k], g), "%s %s %s is not watertight" % (name, k, g))
    hw = C.LOT / 2
    for v in lods["geo"].verts:
        check(abs(v[0]) <= hw + 1e-6 and abs(v[1]) <= hw + 1e-6, "%s: Geometry leaves the lot" % name)
        break
    xs = [v[0] for v in lods["geo"].verts]
    ys = [v[1] for v in lods["geo"].verts]
    check(min(xs) >= -hw - 1e-6 and max(xs) <= hw + 1e-6 and min(ys) >= -hw - 1e-6 and max(ys) <= hw + 1e-6,
          "%s: Geometry leaves the 12 m lot" % name)
    check(len(lods["road"].faces) > 8, "%s: rubble has no Roadway (not walkable)" % name)
    check(not S.KIT[name]["doors"] and S.KIT[name]["cls"] not in C.LOOT_OUT, "%s: lots carry no door / loot" % name)


def test_piece(name, hw, hd):
    """Not-enterable pieces (substation, water tower, metro entrances): LOD set, watertight parts,
    Geometry inside the footprint and above the skirt, no door / loot."""
    lods = {l.name: l for l in C.BUILDERS[name]()}
    for k in NEED:
        check(k in lods and lods[k].verts, "%s: missing LOD %s" % (name, k))
    for k in ("geo", "view", "fire"):
        for g in lods[k].groups:
            if g.startswith("Component"):
                check(watertight(lods[k], g), "%s %s %s is not watertight" % (name, k, g))
    xs = [v[0] for v in lods["geo"].verts]
    ys = [v[1] for v in lods["geo"].verts]
    zs = [v[2] for v in lods["geo"].verts]
    check(min(xs) >= -hw - 1e-6 and max(xs) <= hw + 1e-6 and min(ys) >= -hd - 1e-6 and max(ys) <= hd + 1e-6,
          "%s: Geometry leaves the %gx%g footprint" % (name, 2 * hw, 2 * hd))
    check(min(zs) >= -S.CITY_STYLE["skirt"] - 1e-6, "%s: Geometry below the foundation skirt" % name)
    check(not S.KIT[name]["doors"] and S.KIT[name]["cls"] not in C.LOOT_OUT, "%s: pieces carry no door / loot" % name)


def test_veg(name):
    """Vegetation pieces: 4 Res LODs, cards inside the footprint; weeds / bushes never collide,
    trees collide with a watertight trunk only (inside 0.5 m of the centre)."""
    lods = {l.name: l for l in C.BUILDERS[name]()}
    for k in ("res0", "res1", "res2", "res3"):
        check(k in lods and lods[k].faces, "%s: missing LOD %s" % (name, k))
    _k, w, _d = S.CITY_PIECES[name]
    for v in lods["res0"].verts:
        if abs(v[0]) > w / 2 + 1e-6 or abs(v[1]) > w / 2 + 1e-6:
            check(False, "%s: Res0 leaves the %g m footprint" % (name, w))
            break
    tree = S.KIT[name]["category"] == "tree"
    check(("geo" in lods) == tree, "%s: %s" % (name, "a tree needs a trunk Geometry" if tree else "weeds / bushes must not collide"))
    if tree:
        for g in lods["geo"].groups:
            if g.startswith("Component"):
                check(watertight(lods["geo"], g), "%s geo %s is not watertight" % (name, g))
        check(all(abs(v[0]) <= 0.5 and abs(v[1]) <= 0.5 for v in lods["geo"].verts), "%s: trunk Geometry too wide" % name)


def test_class(name, fresh_loot):
    e = S.KIT[name]
    if e["city"].get("lot"):
        return test_lot(name)
    if e["city"].get("veg"):
        return test_veg(name)
    if e["city"].get("piece"):
        _k, w, d = S.CITY_PIECES[e["city"]["piece"]]
        return test_piece(name, w / 2, d / 2)
    if S.CITY_ARCHETYPES[e["city"]["archetype"]].get("special"):
        A = S.CITY_ARCHETYPES[e["city"]["archetype"]]
        return test_piece(name, A["w"] / 2, A["d"] / 2)
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
    check(min(xs) >= P.fx0 - 1e-6 and max(xs) <= P.fx1 + 1e-6 and min(ys) >= P.fy0 - 1e-6 and max(ys) <= P.fy1 + 1e-6,
          "%s: Geometry leaves the %gx%g footprint" % (name, P.fx1 - P.fx0, P.fy1 - P.fy0))
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
    mem = lods.get("mem")                                                      # D71: search spots = where a player stands
    for g in (sorted(k for k in mem.groups if k.startswith("search")) if mem else []):
        x, y, z = mem.verts[min(mem.groups[g])]
        l = min(range(len(P.levels)), key=lambda k: abs(P.levels[k][2] - z))
        seen, (gx0, gy0, cell) = reach[l]
        i, j = int((x - gx0) / cell), int((y - gy0) / cell)
        raised = z - P.levels[l][2] >= 0.3
        if raised:                                                           # only the cinema stage (security L): a floor
            check(P.A.get("catalog", P.arch) == "Cinema", "%s: raised search point %s" % (name, g))   # cell within 1.5 m
            rr = int(1.5 / cell) + 1
            near = any((i + di, j + dj) in seen and (di * di + dj * dj) * cell * cell <= 1.5 ** 2
                       for di in range(-rr, rr + 1) for dj in range(-rr, rr + 1))
        else:
            near = any((i + di, j + dj) in seen for di in (-2, -1, 0, 1, 2) for dj in (-2, -1, 0, 1, 2))
        check(near, "%s: search point %s (%g, %g, %g) is not reachable" % (name, g, x, y, z))
        # D86 (sec review): the spot itself must not stand inside furniture - the reach test above accepts a free
        # cell up to 2 cells away, so a spot buried in a counter or cabinet passed
        inside = [b for _g, b in comp_boxes(lods["geo"]) if b[0] + 0.05 < x < b[1] - 0.05 and b[2] + 0.05 < y < b[3] - 0.05
                  and b[4] < z + 1.0 and b[5] > z + 0.1]
        check(not inside, "%s: search point %s (%g, %g, %g) is inside a collision box %s" % (
            name, g, x, y, z, tuple(round(v, 2) for v in inside[0]) if inside else ()))
    for sl in C.wedge_slots([b for _g, b in comp_boxes(lods["geo"])], P):                                            # D87 (sec review): no wedge slots
        check(False, "%s: %.2f m slot over %.2f m between collision boxes %s and %s" % ((name,) + sl[:4]))
    tiny = (P.ix1 - P.ix0) * (P.iy1 - P.iy0) < 30.0
    check(len(C.LOOT_OUT.get(e["cls"], [])) >= 1 or (state == 2 and tiny), "%s: no loot points" % name)


def wedge_selftest():
    """D89: pinned cases for build_city.wedge_slots (floor z = 0, roof z = 10)."""
    class P:
        levels = [("x", 3.0, 0.0)]
        top = 10.0
    A = (0.0, 1.0, 0.0, 4.0, 0.0, 1.0)
    def hits(*bx):
        return len(C.wedge_slots(list(bx), P))
    def at(z, *b):
        return (b[0], b[1], b[2], b[3], z, z + 1.0)
    check(hits(A, at(0, 1.4, 2.4, 0, 4)) == 1, "wedge selftest: 0.4 m slot not found")
    check(hits(A, at(0, 1.1, 2.1, 0, 4)) == 0, "wedge selftest: 0.1 m (flush) flagged")
    check(hits(A, at(0, 1.8, 2.8, 0, 4)) == 0, "wedge selftest: 0.8 m (walkable) flagged")
    check(hits(A, at(0, 1.4, 2.4, 0, 4), at(0, 1.0, 1.4, 0, 4)) == 0, "wedge selftest: filled slot flagged")
    check(hits(A, at(0, 1.4, 2.4, 0, 4), at(0, 1.0, 1.4, 1.9, 2.1)) == 1, "wedge selftest: a thin post hides the slot")
    check(hits(A, at(0, 1.4, 2.4, 0, 4), at(0, 1.0, 1.4, 0.8, 3.2)) == 0, "wedge selftest: short leftover runs flagged")
    R = (0.0, 1.0, 0.0, 4.0, 10.0, 11.0)
    check(hits(R, at(10, 1.4, 2.4, 0, 4)) == 1, "wedge selftest: roof-level slot not found")


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    names = argv[argv.index("--only") + 1].split(",") if "--only" in argv else sorted(C.BUILDERS)
    wedge_selftest()
    fresh = {}
    for n in names:
        test_class(n, fresh)
    if "--only" not in argv:
        cur = json.load(open(C.LOOT_JSON)) if os.path.exists(C.LOOT_JSON) else {}
        norm = {k: [list(p) for p in v] for k, v in fresh.items()}
        check(cur == norm, "assets/city_loot.json is stale - re-run build_city.py")
    for p in POCKETS:
        check(False, "ruin pocket a player can drop into but not leave: %s (P39)" % p)
    if FAIL:
        print("CITY GEOMETRY TESTS: %d FAILED" % len(FAIL))
        for f in FAIL:
            print("  FAIL", f)
        sys.exit(1)
    print("CITY GEOMETRY TESTS: PASS (%d buildings)" % len(names))


if __name__ == "__main__":
    main()
