"""Geometry regression tests for Tower A (run headless in Blender, no export).

    blender -b --factory-startup -P test_towera.py

Checks walkability-critical facts on the collision (Geometry) LODs:
  * every elevator stop: stair door opening and elevator opening are clear,
    except the elevator door leaves themselves (which animate away)
  * cab interior is clear at every stop, stair landings exist at every storey
  * keycard door opening is blocked only by the door leaf
  * loot points of every module are on a floor and not inside a solid
  * Geometry components are closed (8 shared verts per box) and carry mass
Exit code 1 on failure.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import build_towera as T  # noqa: E402
import skyspec as S  # noqa: E402

FAIL = []


def check(cond, msg):
    if not cond:
        FAIL.append(msg)


def solids(lod):
    """Axis-aligned bounds of each ComponentNN in a component LOD + its other selections."""
    out = []
    for name, verts in lod.groups.items():
        if not name.startswith("Component"):
            continue
        pts = [lod.verts[i] for i in verts]
        lo = tuple(min(p[k] for p in pts) for k in range(3))
        hi = tuple(max(p[k] for p in pts) for k in range(3))
        tags = [n for n, vs in lod.groups.items() if not n.startswith("Component") and verts <= vs]
        out.append((lo, hi, tags, len(verts)))
    return out


def blocked(boxes, p, ignore_tag=None, eps=1e-3):
    for lo, hi, tags, _n in boxes:
        if ignore_tag and any(t.startswith(ignore_tag) for t in tags):
            continue
        if all(lo[k] + eps < p[k] < hi[k] - eps for k in range(3)):
            return True
    return False


def get(lods, name):
    return [l for l in lods if l.name == name][0]


def _convex_solids(lod):
    """Per closed convex Component: (bbox lo, bbox hi, [(normal, point)] outward face planes). Computed once."""
    by_vert = {}
    for idx, _mat, _uv in lod.faces:
        for i in idx:
            by_vert.setdefault(i, []).append(idx)
    out = []
    for name, verts in lod.groups.items():
        if not name.startswith("Component"):
            continue
        pts = [lod.verts[i] for i in verts]
        lo = tuple(min(q[k] for q in pts) for k in range(3))
        hi = tuple(max(q[k] for q in pts) for k in range(3))
        c = tuple(sum(q[k] for q in pts) / len(pts) for k in range(3))
        seen = set()
        planes = []
        for i in verts:
            for idx in by_vert.get(i, ()):
                if idx in seen or not set(idx) <= verts:
                    continue
                seen.add(idx)
                a, b, d = (lod.verts[j] for j in idx[:3])
                u = tuple(b[k] - a[k] for k in range(3))
                v = tuple(d[k] - a[k] for k in range(3))
                n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
                if sum(n[k] * (c[k] - a[k]) for k in range(3)) > 0:
                    n = tuple(-x for x in n)
                planes.append((n, a))
        out.append((lo, hi, planes))
    return out


def _inside(solids_, p, eps=1e-4):
    for lo, hi, planes in solids_:
        if not all(lo[k] < p[k] < hi[k] for k in range(3)):
            continue
        if all(sum(n[k] * (p[k] - a[k]) for k in range(3)) <= eps for n, a in planes):
            return True
    return False


STAND_HEADROOM = 2.0       # m: standing character is about 1.8 m; crouching (about 1.4 m) must not be the only way up


def check_stairs(spec, label):
    """Walk both flights of every storey section along their centre line and require standing headroom.
    Found in game 2026-10-09 (TESTING C-03): flat-bottomed stair wedges left 1.5 m under the flight above."""
    C = S.CORE
    w = S.WALL_T
    geo = _convex_solids(get(T.build_core(spec), "geo"))
    iy0 = C["y"][0] + w
    half = S.FLOOR_H / 2
    yA0, yA1 = iy0 + 1.2, -0.25
    n_sections = int(round(S.elevator_stops(spec)[-1] / S.FLOOR_H))
    worst = (99.0, None)
    for sec in range(n_sections):
        z0 = sec * S.FLOOR_H
        for xc, up in ((-1.5, True), (1.5, False)):
            for i in range(21):
                f = i / 20.0
                y = yA0 + f * (yA1 - yA0) if up else yA1 - f * (yA1 - yA0)
                zf = z0 + f * half if up else z0 + half + f * half
                head = 0.0
                while head < 2.5 and not _inside(geo, (xc, y, zf + 0.03 + head)):
                    head += 0.05
                if head + 0.03 < worst[0]:
                    worst = (head + 0.03, (sec, xc, round(y, 2), round(zf, 2)))
    check(worst[0] >= STAND_HEADROOM,
          "%s stairs: standing headroom only %.2f m (< %.1f) at section %s, x=%s, y=%s, floor z=%s"
          % (label, worst[0], STAND_HEADROOM, worst[1][0], worst[1][1], worst[1][2], worst[1][3]) if worst[1] else "")


def check_core(spec, label):
    """Doors, cab and landings at every stop + memory points the elevator script needs per stop."""
    C = S.CORE
    check_stairs(spec, label)
    core = T.build_core(spec)
    geo = get(core, "geo")
    boxes = solids(geo)
    y0, y1 = C["y"]
    mem = get(core, "mem")
    for i, s in enumerate(S.elevator_stops(spec)):
        for pt in ("elev_cab_l%d" % i, "elev_panel_l%d" % i, "elev_call_l%d" % i):
            check(len(mem.groups.get(pt, ())) == 1, "%s stop %d: memory point %s missing" % (label, i, pt))
        for leaf in ("a", "b"):
            check(len(mem.groups.get("elev_door_l%d_%s_axis" % (i, leaf), ())) == 2,
                  "%s stop %d: door %s axis missing" % (label, i, leaf))
        # Stair door (south face) - sample through the wall thickness.
        for dy in (0.05, 0.12, 0.2):
            p = (sum(C["stair_door_x"]) / 2, y0 + dy, s + 1.0)
            check(not blocked(boxes, p), "%s stop %d (z=%.1f): stair door blocked at %s" % (label, i, s, p))
            p = (0.0, y1 - dy, s + 1.0)
            check(not blocked(boxes, p, ignore_tag="elev_door_l%d_" % i), "%s stop %d: elevator opening blocked at %s" % (label, i, p))
        p = (0.0, (C["elev_y"][0] + y1 - S.WALL_T) / 2, s + 1.2)
        check(not blocked(boxes, p), "%s stop %d: cab interior blocked at %s" % (label, i, p))
        if s > 0:
            p = (-1.2, y0 + S.WALL_T + 0.6, s - 0.1)
            check(blocked(boxes, p), "%s stop %d: no stair landing under the door at %s" % (label, i, p))
    for lo, hi, tags, n in boxes:
        check(n == 8, "%s component %s..%s is not a closed 8-vertex box" % (label, lo, hi))
    check(geo.mass > 0, "%s Geometry has no mass" % label)


def main():
    for k, (_c, spec) in sorted(S.CORE_VARIANTS.items()):
        if k != "A":
            check_core(spec, "core " + k)                       # tall cores (D58)
    C = S.CORE
    check_stairs(S.TOWER_A, "core A")
    core = T.build_core()
    geo = get(core, "geo")
    boxes = solids(geo)
    y0, y1 = C["y"]
    for i, s in enumerate(S.elevator_stops()):
        # Stair door (south face) - sample through the wall thickness.
        for dy in (0.05, 0.12, 0.2):
            p = (sum(C["stair_door_x"]) / 2, y0 + dy, s + 1.0)
            check(not blocked(boxes, p), "stop %d (z=%.1f): stair door blocked at %s" % (i, s, p))
            p = (0.0, y1 - dy, s + 1.0)
            check(not blocked(boxes, p, ignore_tag="elev_door_l%d_" % i), "stop %d: elevator opening blocked at %s" % (i, p))
        # Cab interior clear, landing exists below the stair door.
        p = (0.0, (C["elev_y"][0] + y1 - S.WALL_T) / 2, s + 1.2)
        check(not blocked(boxes, p), "stop %d: cab interior blocked at %s" % (i, p))
        if s > 0:
            p = (-1.2, y0 + S.WALL_T + 0.6, s - 0.1)
            check(blocked(boxes, p), "stop %d: no stair landing under the door at %s" % (i, p))
    for lo, hi, tags, n in boxes:
        check(n == 8, "core component %s..%s is not a closed 8-vertex box" % (lo, hi))
    check(geo.mass > 0, "core Geometry has no mass")

    lobby = T.build_lobby()
    builders = {S.CLASS_LOBBY: lobby, S.CLASS_FLOOR: T.build_floor_office(), S.CLASS_ROOF: T.build_roof_helipad(),
                S.CLASS_LOBBY_B: T.build_lobby("B")}
    d = S.KEYCARD_DOOR
    for lcls in (S.CLASS_LOBBY, S.CLASS_LOBBY_B):                     # Lobby_B keeps Lobby A's door (D60)
        lb = solids(get(builders[lcls], "geo"))
        p = (d["hinge"][0], d["hinge"][1] + d["width"] / 2, 1.0)
        check(blocked(lb, p), "%s: keycard door opening is not blocked by the door leaf" % lcls)
        check(not blocked(lb, p, ignore_tag=d["name"]), "%s: keycard door opening blocked by something other than the leaf" % lcls)
        check(not blocked(lb, (0.0, -S.TOWER_A["footprint"][1] / 2 + 0.05, 1.0)), "%s: entrance blocked" % lcls)
        mem = get(builders[lcls], "mem")
        names = set(mem.groups) if hasattr(mem, "groups") else set()
        check(not names or d["name"] + "_axis" in names, "%s: door axis memory point missing" % lcls)
    for cls, lods in builders.items():
        g = solids(get(lods, "geo"))
        for c in S.LOOT[cls]["containers"]:
            for (x, y) in c["points"]:
                check(not blocked(g, (x, y, 0.5)), "%s loot point (%s, %s) is inside a solid" % (cls, x, y))
                check(blocked(g, (x, y, -0.1)), "%s loot point (%s, %s) has no floor under it" % (cls, x, y))

    if FAIL:
        print("TOWER A GEOMETRY TESTS: %d FAILED" % len(FAIL))
        for f in FAIL:
            print("  FAIL", f)
        sys.exit(1)
    print("TOWER A GEOMETRY TESTS: PASS (%d core components checked)" % len(boxes))


if __name__ == "__main__":
    main()
