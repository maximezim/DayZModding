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
    from test_kit import wedge_voxel, geo_halfspaces                            # D91: next to sloped parts (stairs, cars)
    global GEO_HS
    GEO_HS = geo_halfspaces(lods["geo"])
    for (g, r, b, fz) in wedge_voxel(lods["geo"], floors=[z for (_u, _f, z) in P.levels] + [P.top]):
        check(False, "%s geo: wedge slot over %.2f m next to non-box %s %s (floor %.1f)" % (name, r, g, b, fz))
    facade_cover(lods, P, name)
    opening_cover(lods, P, name)
    far_see_through(lods, P, name)
    # D90 (sec): glassfar is opaque (no alpha). In a reachable window opening of Res0 / Res1 it would be a one-sided
    # dark pane - outside sees nothing, inside sees and shoots out. Far LODs only.
    for k in ("res0", "res1"):
        lod = lods[k]
        n_bad = sum(1 for idx, m, _u in lod.faces
                    if m in ("glassfar", "glassvoid") and in_opening([lod.verts[i] for i in idx], P)
                    and min(lod.verts[i][2] for i in idx) < P.top              # belfry / cupola: above the roof, unreachable
                    and not backed(lod, [lod.verts[i] for i in idx]))          # painted on a solid wall (projection window)
        check(n_bad == 0, "%s %s: %d opaque glassfar / glassvoid faces in outer openings" % (name, k, n_bad))
        one = one_sided_panes(lod, GEO_HS)                                    # D91: at any height (roof glazing too)
        check(not one, "%s %s: one-sided opaque glassfar panes at %s" % (name, k, one[:4]))
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


def in_opening(pts, P):
    """Own definition (not build_city._on_shell, so a change there cannot blind the test): parallel to an outer or
    yard wall plane, within 0.4 m of it."""
    planes = [(0, -P.hw), (0, P.hw), (1, -P.hd), (1, P.hd)]
    if getattr(P, "yard", None):
        planes += [(0, P.yard[0]), (0, P.yard[1]), (1, P.yard[2]), (1, P.yard[3])]
    for a, c in planes:
        v = [p[a] for p in pts]
        if max(v) - min(v) < 0.01 and abs(v[0] - c) < 0.4:
            return True
    return False


def _nrm(pts):
    import numpy as np
    p = np.asarray(pts, float)
    n = sum(np.cross(p[k] - p[0], p[k + 1] - p[0]) for k in range(1, len(p) - 1))   # winding: the visible side
    ln = np.linalg.norm(n)
    return n / ln if ln > 1e-12 else n


def _covers(q, pts, n, frac=0.9):
    """Face q's projection on the plane of `pts` (normal n) covers at least `frac` of the pane's bounding box."""
    import numpy as np
    a = int(np.argmax(np.abs(n)))
    o = [j for j in range(3) if j != a]
    pa = [(min(p[j] for p in pts), max(p[j] for p in pts)) for j in o]
    qa = [(min(p[j] for p in q), max(p[j] for p in q)) for j in o]
    ov = 1.0
    full = 1.0
    for (p0, p1), (q0, q1) in zip(pa, qa):
        ov *= max(0.0, min(p1, q1) - max(p0, q0))
        full *= max(1e-9, p1 - p0)
    return ov >= frac * full


def one_sided_panes(lod, geo_halfspaces=None, min_area=0.05):
    """D91 (rev. after the sec review): opaque glassfar faces of any orientation with nothing behind them - no opaque
    wall within 5 cm, no opposite-facing glassfar twin covering it (coplanar double-sided pane, or the far side of a
    closed dark block within 0.5 m) - and with room for a head on their see-through side (the point 0.25 m behind
    the centre is not inside Geometry). Coplanar small faces are merged before `min_area` (a head). Returns centres."""
    import numpy as np
    cand = {}
    gl = [(idx, [lod.verts[i] for i in idx]) for idx, m, _u in lod.faces if m == "glassfar"]
    # perf: planes whose glassfar faces add up to less than a head (bottles, small trims) are dropped up front
    plane_area = {}
    info = []
    for idx, pts in gl:
        n = _nrm(pts)
        if not n.any():
            continue
        c = np.mean(np.asarray(pts, float), 0)
        key = (tuple(np.round(n, 2)), round(float(n @ c), 2))
        plane_area[key] = plane_area.get(key, 0.0) + C._area(pts)
        info.append((idx, pts, n, key))
    big = [(idx, pts, n) for idx, pts, n, key in info if plane_area[key] >= min_area]
    if not big:
        return []
    gl = [(idx, pts) for idx, pts, _n, key in info if plane_area[key] >= 0.5 * min_area]   # twins: sizeable faces only
    for idx, pts, n in big:
        if backed_any(lod, pts, n):
            continue
        c = np.mean(np.asarray(pts, float), 0)
        d = float(n @ c)
        twin = False
        for idx2, q in gl:
            if set(idx2) == set(idx):
                continue
            n2 = _nrm(q)
            if n2 @ n > -0.99:
                continue                                         # must face the other way
            dist = d - float(n @ np.asarray(q[0], float))        # > 0: behind the pane
            if -0.005 < dist < 0.5 and _covers(q, pts, n):
                twin = True
                break
        if twin:
            continue
        back = c - 0.25 * n
        if geo_halfspaces and any(all(back @ hn - hd <= 1e-4 for hn, hd in h) for h in geo_halfspaces if h):
            continue                                             # nobody can be on the see-through side
        key = (tuple(np.round(n, 2)), round(d, 2))
        cand.setdefault(key, []).append((C._area(pts), tuple(round(v, 2) for v in c)))
    return [faces[0][1] for faces in cand.values() if sum(a for a, _c in faces) >= min_area]


_OPAQUE_CACHE = {}


def _opaque_planes(lod):
    """Per LOD (cached): unit normals, plane offsets and bounding boxes of its opaque faces, as arrays (perf)."""
    import numpy as np
    key = id(lod)
    if key not in _OPAQUE_CACHE:
        N, D, LO, HI = [], [], [], []
        for idx, m, _u in lod.faces:
            if m in SEE_THROUGH or m in ("glassfar", "glassvoid"):
                continue
            q = np.asarray([lod.verts[i] for i in idx], float)
            n = _nrm(q)
            if not n.any():
                continue
            N.append(n)
            D.append(float(n @ q[0]))
            LO.append(q.min(0))
            HI.append(q.max(0))
        _OPAQUE_CACHE.clear()                                    # one LOD at a time
        _OPAQUE_CACHE[key] = (np.array(N).reshape(-1, 3), np.array(D), np.array(LO).reshape(-1, 3),
                              np.array(HI).reshape(-1, 3))
    return _OPAQUE_CACHE[key]


def backed_any(lod, pts, n):
    """An opaque face parallel to the pane, coplanar or within 5 cm behind it, covers >= 90 % of it (painted on a
    wall, or resting on a shelf)."""
    import numpy as np
    N, D, LO, HI = _opaque_planes(lod)
    if not len(N):
        return False
    p = np.asarray(pts, float)
    par = np.abs(np.abs(N @ n) - 1) <= 0.01
    # distance of each candidate plane behind the pane: n . c - (a point of that plane) . n
    plane_pt = N * D[:, None]                                    # the plane's point closest to the origin
    dist = float(n @ p.mean(0)) - plane_pt @ n
    sel = par & (dist > -0.005) & (dist < 0.05)
    if not sel.any():
        return False
    a = int(np.argmax(np.abs(n)))
    o = [j for j in range(3) if j != a]
    pl, ph = p.min(0), p.max(0)
    ov = np.ones(sel.sum())
    full = 1.0
    for j in o:
        ov *= np.clip(np.minimum(ph[j], HI[sel, j]) - np.maximum(pl[j], LO[sel, j]), 0, None)
        full *= max(1e-9, ph[j] - pl[j])
    return bool((ov >= 0.9 * full).any())


def _inside_proj(q, c, n):
    import numpy as np
    a = int(np.argmax(np.abs(n)))
    return all(min(p[j] for p in q) - 1e-6 <= c[j] <= max(p[j] for p in q) + 1e-6 for j in range(3) if j != a)


def backed(lod, pts):
    """An opaque face parallel to `pts` within 5 cm covers its centre: the pane is painted on a wall, not an opening."""
    a = next(j for j in range(2) if max(p[j] for p in pts) - min(p[j] for p in pts) < 0.01)
    c = [sum(p[j] for p in pts) / len(pts) for j in range(3)]
    o = [j for j in range(3) if j != a]
    for idx, m, _u in lod.faces:
        if m in SEE_THROUGH or m in ("glassfar", "glassvoid"):
            continue
        q = [lod.verts[i] for i in idx]
        v = [p[a] for p in q]
        if max(v) - min(v) < 0.01 and 0.0 < abs(v[0] - c[a]) < 0.05 and all(
                min(p[j] for p in q) <= c[j] <= max(p[j] for p in q) for j in o):
            return True
    return False


def opening_cover(lods, P, name):
    """D90: the glass / void / board faces filling the outer window openings in Res1 (parallel to a wall, within
    0.4 m) must all survive into res1x / res1y - an empty opening at range shows a hollow building."""
    for k in ("res1x", "res1y"):
        if k not in lods:
            continue
        have = {frozenset(tuple(round(c, 3) for c in lods[k].verts[i]) for i in idx)
                for idx, m, _u in lods[k].faces}
        miss = 0
        for idx, m, _u in lods["res1"].faces:
            if not m.startswith("glass"):
                continue
            pts = [lods["res1"].verts[i] for i in idx]
            if in_opening(pts, P) and frozenset(tuple(round(c, 3) for c in p) for p in pts) not in have:
                miss += 1
        check(miss == 0, "%s %s: %d window panes of Res1 missing" % (name, k, miss))


GEO_HS = None

SEE_THROUGH = {"glass", "foliage", "vegetation", "decal_dirt", "decal_cracks", "decal_graffiti", "decal_grime",
               "roadmark", "windows", "windows_lit", "lamp", "lamp_cool", "fair_ca"}   # glassfar is opaque (D90)


def through_rays(lod, P, n_h=12, n_a=24):
    """Horizontal rays straight across the footprint (both axes) on a grid; count those that meet no opaque face."""
    import numpy as np
    tri = []
    for idx, m, _u in lod.faces:
        if m in SEE_THROUGH:
            continue
        p = [lod.verts[i] for i in idx]
        for k in range(1, len(p) - 1):
            tri.append((p[0], p[k], p[k + 1]))
    if not tri:
        return 0, 0
    T = np.array(tri, float)
    v0, e1, e2 = T[:, 0], T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]
    zs = [0.6 + (P.top - 1.2) * (i + 0.5) / n_h for i in range(n_h)]
    rays = []
    for ax, half_a, half_o in ((0, P.hw, P.hd), (1, P.hd, P.hw)):
        for z in zs:
            for j in range(n_a):
                o = -half_o * 0.9 + 1.8 * half_o * (j + 0.5) / n_a
                if ax == 0:
                    rays.append(((-half_a - 2.0, o, z), (1.0, 0.0, 0.0)))
                else:
                    rays.append(((o, -half_a - 2.0, z), (0.0, 1.0, 0.0)))
    passed = 0
    for orig, d in rays:
        o_, d_ = np.array(orig), np.array(d)
        pv = np.cross(d_, e2)
        det = (e1 * pv).sum(1)
        ok = np.abs(det) > 1e-12
        inv = 1.0 / np.where(ok, det, 1.0)
        tv = o_ - v0
        u = (tv * pv).sum(1) * inv
        q = np.cross(tv, e1)
        v = (q * d_).sum(1) * inv
        t = (e2 * q).sum(1) * inv
        if not (ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 0)).any():
            passed += 1
    return passed, len(rays)


def far_see_through(lods, P, name):
    """D90 (sec review M): no far LOD lets more rays straight through the building than Res1 does (a hollow shell or
    open broken windows would show what is inside / behind it at range)."""
    if "res1x" not in lods:
        return
    ref, n = through_rays(lods["res1"], P)
    for k in ("res1x", "res1y"):
        if k in lods:
            got, _n = through_rays(lods[k], P)
            check(got <= ref, "%s %s: %d of %d rays pass straight through (Res1: %d)" % (name, k, got, n, ref))


def facade_cover(lods, P, name):
    """D90: each outer facade plane keeps >= 80 % of its Res1 face area in the far LODs built from it (res1x, res1y):
    the D88 exterior LOD dropped most of the street facade and no gate saw it."""
    def plane_area(lod, axis, c):
        a = 0.0
        for idx, m, _u in lod.faces:
            pts = [lod.verts[i] for i in idx]
            if m not in C.EXT_DROP and max(abs(p[axis] - c) for p in pts) < 0.05:     # decals: dropped on purpose
                a += C._area(pts)
        return a
    for axis, c in ((1, -P.hd), (1, P.hd), (0, -P.hw), (0, P.hw)):
        ref = plane_area(lods["res1"], axis, c)
        if ref < 5.0:
            continue
        for k in ("res1x", "res1y"):
            if k in lods:
                got = plane_area(lods[k], axis, c)
                check(got >= 0.8 * ref, "%s %s: facade %s=%.1f keeps %.0f of %.0f m2" % (name, k, "xy"[axis], c, got, ref))


def pane_selftest():
    """D91 (sec review H/M): pinned cases for one_sided_panes."""
    from skygeo import Lod, LOD_RES, LOD_GEOMETRY
    from test_kit import geo_halfspaces
    Q = [(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)]                            # 1 m2 pane in y = 0, visible from -y
    def run(build, geo=None):
        L = Lod("r", LOD_RES, 0)
        build(L)
        return len(one_sided_panes(L, geo_halfspaces(geo) if geo else None))
    check(run(lambda L: L.quad(Q, (0, -1, 0), mat="glassfar")) == 1, "pane selftest: one-sided pane missed")
    check(run(lambda L: L.quad(Q, (0, -1, 0), mat="glassfar", double=True)) == 0, "pane selftest: double pane flagged")
    check(run(lambda L: (L.quad(Q, (0, -1, 0), mat="glassfar"), L.quad(Q, (0, -1, 0), mat="glassfar"))) == 1,
          "pane selftest: a same-facing duplicate counted as twin")
    small = [(0.4, 0.001, 0.4), (0.6, 0.001, 0.4), (0.6, 0.001, 0.6), (0.4, 0.001, 0.6)]
    check(run(lambda L: (L.quad(Q, (0, -1, 0), mat="glassfar"), L.quad(small, (0, 1, 0), mat="paint"))) == 1,
          "pane selftest: a small decal behind counted as backing")
    far = [(p[0], 0.45, p[2]) for p in Q]
    check(run(lambda L: (L.quad(Q, (0, -1, 0), mat="glassfar"), L.quad(far, (0, -1, 0), mat="glassfar"))) == 2,
          "pane selftest: a same-facing pane 0.45 m behind counted as a closed block")
    check(run(lambda L: (L.quad(Q, (0, -1, 0), mat="glassfar"), L.quad(far, (0, 1, 0), mat="glassfar"))) == 0,
          "pane selftest: closed dark block flagged")
    def tiles(L):
        for i in range(5):
            for j in range(5):
                L.quad([(i * .2, 0, j * .2), (i * .2 + .2, 0, j * .2), (i * .2 + .2, 0, j * .2 + .2), (i * .2, 0, j * .2 + .2)],
                       (0, -1, 0), mat="glassfar")
    check(run(tiles) == 1, "pane selftest: 25 tiles of 0.04 m2 not merged")
    diag = [(0, 0, 0), (0.7, 0.7, 0), (0.7, 0.7, 1), (0, 0, 1)]
    check(run(lambda L: L.quad(diag, (0.7, -0.7, 0), mat="glassfar")) == 1, "pane selftest: 45-degree pane missed")
    G = Lod("geo", LOD_GEOMETRY)
    G.box(0.0, 1.0, 0.0, 0.5, 0.0, 1.0)                                         # solid behind: nobody on the back side
    check(run(lambda L: L.quad(Q, (0, -1, 0), mat="glassfar"), G) == 0, "pane selftest: pane on a solid flagged")


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
    D = (0.0, 1.0, 0.0, 4.0, 0.6, 1.6)                                          # D90: on a 0.6 m stage
    stage = (-1.0, 3.5, -1.0, 5.0, 0.0, 0.6)
    check(hits(D, at(0.6, 1.4, 2.4, 0, 4), stage) == 1, "wedge selftest: slot on a stage not found")
    check(hits(D, at(0.6, 1.4, 2.4, 0, 4)) == 0, "wedge selftest: floating pair (nothing under the gap) flagged")
    low_a, low_b = (0.0, 1.0, 0.0, 4.0, 0.0, 0.3), (1.4, 2.4, 0.0, 4.0, 0.0, 0.3)   # D93: 0.4 m gap between low boxes
    slab = (-0.2, 2.6, 0.0, 4.0, 0.6, 0.9)
    check(hits(low_a, low_b, slab) == 1, "wedge selftest: prone pocket under a slab not found")
    check(hits(low_a, low_b) == 0, "wedge selftest: open low gap flagged (step over it)")
    for nm, covs in (("narrow cover (0.3 of 0.4 m)", [(1.0, 1.3, 0.0, 4.0, 0.6, 0.9)]),               # sec review D93
                     ("split cover", [(-0.2, 2.6, 0.0, 2.0, 0.6, 0.9), (-0.2, 2.6, 2.0, 4.0, 0.6, 0.9)]),
                     ("cover dipping 3 cm", [(-0.2, 2.6, 0.0, 4.0, 0.27, 0.6)]),
                     ("cover at 1.2 m", [(-0.2, 2.6, 0.0, 4.0, 1.2, 1.5)])):
        check(hits(low_a, low_b, *covs) == 1, "wedge selftest: pocket with %s not found" % nm)
    plinth = (1.4, 2.4, 0.0, 4.0, 0.0, 0.3)                                     # floor box beside a box on a 0.3 m plinth
    check(hits((0.0, 1.0, 0.0, 4.0, 0.0, 1.6), at(0.3, 1.4, 2.4, 0, 4), plinth) == 1,
          "wedge selftest: slot beside a box on a low plinth not found")


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    names = argv[argv.index("--only") + 1].split(",") if "--only" in argv else sorted(C.BUILDERS)
    wedge_selftest()
    pane_selftest()
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
