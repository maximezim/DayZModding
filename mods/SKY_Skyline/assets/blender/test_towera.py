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


def main():
    C = S.CORE
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
    lb = solids(get(lobby, "geo"))
    d = S.KEYCARD_DOOR
    p = (d["hinge"][0], d["hinge"][1] + d["width"] / 2, 1.0)
    check(blocked(lb, p), "keycard door opening is not blocked by the door leaf")
    check(not blocked(lb, p, ignore_tag=d["name"]), "keycard door opening blocked by something other than the leaf")
    check(not blocked(lb, (0.0, -S.TOWER_A["footprint"][1] / 2 + 0.05, 1.0)), "lobby entrance blocked")

    builders = {S.CLASS_LOBBY: lobby, S.CLASS_FLOOR: T.build_floor_office(), S.CLASS_ROOF: T.build_roof_helipad()}
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
