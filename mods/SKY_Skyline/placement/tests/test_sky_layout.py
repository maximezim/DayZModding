#!/usr/bin/env python3
"""Self-test for sky_layout.py with synthetic surveys (no game needed).

    python mods/SKY_Skyline/placement/tests/test_sky_layout.py
"""
import json
import os
import subprocess
import sys
import tempfile

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), "sky_layout.py")


def survey(cx, cz, ground, objects=()):
    samples = []
    for i in range(-13, 14, 2):
        for j in range(-13, 14, 2):
            samples += [cx + i, ground(i, j), cz + j]
    return {"label": "t", "center": [cx, cz], "yaw": 0, "halfW": 13, "halfD": 13,
            "minY": 0, "maxY": 0, "samples": samples, "objects": list(objects), "proxyExport": ""}


def run(case, sv, towers=None, strict=True):
    d = tempfile.mkdtemp()
    json.dump(sv, open(os.path.join(d, "s.json"), "w"))
    lay = {"map": "chernarusplus", "mission": "m", "blocks": [], "roads": [],
           "site": {"name": case, "placeholder": False, "center": [1000.0, 2000.0], "yaw": 0.0,
                    "survey": "s.json", "base_y": None, "clearance": 0.05, "max_ground_drop": 2.2},
           "towers": towers or [{"id": "A1", "type": "TowerA", "offset": [0, 0], "yaw": 0}]}
    yaml.safe_dump(lay, open(os.path.join(d, "layout.yaml"), "w"))
    args = [sys.executable, TOOL, "--layout", os.path.join(d, "layout.yaml"), "--out", os.path.join(d, "out")]
    if strict:
        args.append("--strict")
    r = subprocess.run(args, capture_output=True, text=True)
    objs = json.load(open(os.path.join(d, "out", "sky_objects.json")))["Objects"] if r.returncode == 0 else []
    return r.returncode, r.stdout, objs


def main():
    fails = 0

    def expect(name, cond, info=""):
        nonlocal fails
        print(("PASS " if cond else "FAIL ") + name + ("" if cond else "\n" + info))
        fails += not cond

    rc, out, objs = run("flat", survey(1000, 2000, lambda i, j: 150.0 + 0.01 * i))
    lobby = [o for o in objs if o["name"] == "Land_SKY_TowerA_Lobby"]
    expect("flat site passes strict", rc == 0, out)
    expect("base height = max ground inside footprint + clearance", lobby and abs(lobby[0]["pos"][1] - (150.11 + 0.05)) < 1e-3, str(lobby))
    expect("8 objects (lobby, 5 floors, roof, core)", len(objs) == 8, str(len(objs)))

    rc, out, _ = run("slope", survey(1000, 2000, lambda i, j: 150.0 + 0.2 * i))
    expect("steep site fails (drop > skirt)", rc == 1 and "flatter site" in out, out)

    rc, out, _ = run("building", survey(1000, 2000, lambda i, j: 150.0, [{"type": "Land_House_1W01", "pos": [1003.0, 150.0, 2004.0]}]))
    expect("existing building inside footprint fails", rc == 1 and "Land_House_1W01" in out, out)

    rc, out, _ = run("tree", survey(1000, 2000, lambda i, j: 150.0, [{"type": "TreeHard_PiceaAbies_2s", "pos": [1003.0, 150.0, 2004.0]}]))
    expect("vegetation inside footprint only warns", rc == 0 and "WARN" in out, out)

    rc, out, _ = run("overlap", survey(1000, 2000, lambda i, j: 150.0),
                     towers=[{"id": "A1", "type": "TowerA", "offset": [0, 0], "yaw": 0},
                             {"id": "A2", "type": "TowerA", "offset": [10, 0], "yaw": 0}])
    expect("overlapping towers fail", rc == 1 and "overlaps" in out, out)

    rc, out, _ = run("nosurvey-strict", {"samples": [], "objects": []})
    expect("survey without samples in footprint fails", rc == 1, out)
    print("%d failed" % fails)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
