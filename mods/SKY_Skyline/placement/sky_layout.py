#!/usr/bin/env python3
"""layout.yaml -> objectSpawnersArr JSON (+ cfggameplay snippet + report).

    python mods/SKY_Skyline/placement/sky_layout.py [--layout layout.yaml] [--out out/] [--strict]

Output (in --out):
  sky_objects.json         {"Objects": [...]} in the exact schema of the vanilla
                           ObjectSpawnerJson / ITEM_SpawnerObject (3_game/objectspawner.c)
  cfggameplay_snippet.json the WorldsData.objectSpawnersArr entry to merge
  placement_report.md      validation results (survey, ground, overlaps, stacking)

Validation
  * every tower module stacks at base_y + skyspec offsets (floor-to-floor 3.5 m)
  * survey present: base_y >= max ground + clearance and (base_y - min ground)
    <= slab + max_ground_drop (foundation skirt hides the gap), no foreign
    objects inside any footprint, footprints of different towers don't overlap
  * --strict (use for live servers) fails on placeholder sites or missing survey
"""
import argparse
import json
import math
import os
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "assets"))
import skyspec as S  # noqa: E402

TOWER_TYPES = {"TowerA": S.TOWER_A}
MODULE_CLASS = {"lobby": S.CLASS_LOBBY, "floor": S.CLASS_FLOOR, "roof": S.CLASS_ROOF}


def rot(u, v, yaw_deg):
    """Local (u east, v north) -> world offset for a DayZ yaw (clockwise from north)."""
    a = math.radians(yaw_deg)
    return (u * math.cos(a) + v * math.sin(a), -u * math.sin(a) + v * math.cos(a))


def footprint_corners(cx, cz, hw, hd, yaw):
    return [(cx + dx, cz + dz) for dx, dz in (rot(u, v, yaw) for u, v in ((-hw, -hd), (hw, -hd), (hw, hd), (-hw, hd)))]


def inside(px, pz, cx, cz, hw, hd, yaw):
    # inverse rotation of the point into the footprint frame
    dx, dz = px - cx, pz - cz
    a = math.radians(yaw)
    u = dx * math.cos(a) - dz * math.sin(a)
    v = dx * math.sin(a) + dz * math.cos(a)
    return abs(u) <= hw and abs(v) <= hd


def sat_overlap(a, b):
    """Separating-axis test for two convex quads [(x, z)] x4."""
    for poly in (a, b):
        for i in range(4):
            x1, z1 = poly[i]
            x2, z2 = poly[(i + 1) % 4]
            nx, nz = z2 - z1, x1 - x2
            pa = [nx * x + nz * z for x, z in a]
            pb = [nx * x + nz * z for x, z in b]
            if max(pa) < min(pb) or max(pb) < min(pa):
                return False
    return True


def spawner(name, pos, yaw):
    return {"name": name, "pos": [round(pos[0], 4), round(pos[1], 4), round(pos[2], 4)],
            "ypr": [round(yaw, 4), 0.0, 0.0], "scale": 1.0, "enableCEPersistency": 0, "customString": ""}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--layout", default=os.path.join(HERE, "layout.yaml"))
    ap.add_argument("--out", default=os.path.join(HERE, "out"))
    ap.add_argument("--strict", action="store_true", help="fail on placeholder site / missing survey")
    a = ap.parse_args()
    lay = yaml.safe_load(open(a.layout))
    site = lay["site"]
    errors, warnings, notes = [], [], []

    survey = None
    if site.get("survey"):
        sp = os.path.join(os.path.dirname(a.layout), site["survey"])
        survey = json.load(open(sp))
        notes.append("survey: %s (label %s, %d samples, %d objects)" % (
            site["survey"], survey.get("label"), len(survey.get("samples", [])) // 3, len(survey.get("objects", []))))
    if site.get("placeholder"):
        (errors if a.strict else warnings).append("site '%s' is a PLACEHOLDER - do not deploy" % site["name"])
    if survey is None:
        (errors if a.strict else warnings).append("no survey: ground height / overlaps NOT validated")

    cx0, cz0 = site["center"]
    site_yaw = float(site.get("yaw", 0.0))
    objects, quads, drops = [], [], []
    for t in lay["towers"]:
        spec = TOWER_TYPES[t["type"]]
        hw, hd = spec["footprint"][0] / 2, spec["footprint"][1] / 2
        ox, oz = rot(t["offset"][0], t["offset"][1], site_yaw)
        cx, cz = cx0 + ox, cz0 + oz
        yaw = (site_yaw + float(t.get("yaw", 0.0))) % 360.0
        quad = footprint_corners(cx, cz, hw, hd, yaw)
        for other_id, other in quads:
            if sat_overlap(quad, other):
                errors.append("tower %s footprint overlaps tower %s" % (t["id"], other_id))
        quads.append((t["id"], quad))

        # ---- base height
        base_y = site.get("base_y")
        if survey is not None:
            pts = survey["samples"]
            ys = [pts[i + 1] for i in range(0, len(pts), 3) if inside(pts[i], pts[i + 2], cx, cz, hw, hd, yaw)]
            if not ys:
                errors.append("tower %s: survey has no samples inside its footprint (wrong site?)" % t["id"])
            else:
                gmin, gmax = min(ys), max(ys)
                auto = gmax + float(site.get("clearance", 0.05))
                if base_y is None:
                    base_y = auto
                elif base_y < auto:
                    errors.append("tower %s: base_y %.2f is below ground %.2f (+clearance)" % (t["id"], base_y, gmax))
                drop = base_y - S.SLAB_T - gmin
                notes.append("tower %s ground %.2f..%.2f (relief %.2f m), base_y %.2f, drop under slab %.2f m"
                             % (t["id"], gmin, gmax, gmax - gmin, base_y, drop))
                if drop > float(site.get("max_ground_drop", 2.2)):
                    errors.append("tower %s: ground falls %.2f m below the slab (> skirt %.2f m) - pick a flatter site"
                                  % (t["id"], drop, site["max_ground_drop"]))
            for o in survey.get("objects", []):
                if o["type"].startswith("Land_SKY_"):
                    continue
                if inside(o["pos"][0], o["pos"][2], cx, cz, hw, hd, yaw):
                    msg = "tower %s footprint contains existing object %s at %s" % (t["id"], o["type"], [round(v, 1) for v in o["pos"]])
                    (errors if o["type"].startswith("Land_") else warnings).append(msg)
        if base_y is None:
            base_y = 0.0
            (errors if a.strict else warnings).append("tower %s: no base height (survey or base_y) - Y set to 0.0" % t["id"])

        # ---- stacked modules (+ core spanning all levels)
        prev = None
        for kind, _suffix, z in S.tower_levels(spec):
            if prev is not None and not (abs(z - prev - S.FLOOR_H) < 1e-6 or (prev == 0.0 and abs(z - spec["lobby_h"]) < 1e-6)):
                errors.append("tower %s: stacking gap at z=%.2f" % (t["id"], z))
            prev = z
            objects.append(spawner(MODULE_CLASS[kind], (cx, base_y + z, cz), yaw))
        objects.append(spawner(S.CLASS_CORE, (cx, base_y, cz), yaw))
        roof_z = [z for kind, _s, z in S.tower_levels(spec) if kind == "roof"][0]
        for (u, v) in S.ROOF_DROPS:
            dx, dz = rot(u, v, yaw)
            drops.append((cx + dx, base_y + roof_z + 0.05, cz + dz))

    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "sky_objects.json"), "w") as fh:
        json.dump({"Objects": objects}, fh, indent=1)
    with open(os.path.join(a.out, "cfggameplay_snippet.json"), "w") as fh:
        json.dump({"WorldsData": {"objectSpawnersArr": ["sky/sky_objects.json"]}}, fh, indent=1)
    with open(os.path.join(a.out, "cfgeventspawns_snippet.xml"), "w") as fh:
        fh.write("<!-- MERGE into the mission cfgeventspawns.xml (inside <eventposdef>). y = roof height. -->\n")
        fh.write('<event name="StaticSKYRoofDrop">\n    <zone smin="0" smax="0" dmin="0" dmax="0" r="0" />\n')
        for (x, y, z) in drops:
            fh.write('    <pos x="%.3f" z="%.3f" a="0" y="%.3f" />\n' % (x, z, y))
        fh.write("</event>\n")
    status = "FAIL" if errors else ("PASS (with warnings)" if warnings else "PASS")
    with open(os.path.join(a.out, "placement_report.md"), "w") as fh:
        fh.write("# Placement report\n\nmap: %s  site: %s  status: **%s**\n\n" % (lay["map"], site["name"], status))
        for title, items in (("Errors", errors), ("Warnings", warnings), ("Notes", notes)):
            fh.write("## %s\n" % title + ("".join("- %s\n" % i for i in items) or "- none\n") + "\n")
        fh.write("## Objects (%d)\n" % len(objects))
        for o in objects:
            fh.write("- %s at %s yaw %s\n" % (o["name"], o["pos"], o["ypr"][0]))
    print("status:", status)
    for e in errors:
        print("ERROR:", e)
    for w in warnings:
        print("WARN :", w)
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
