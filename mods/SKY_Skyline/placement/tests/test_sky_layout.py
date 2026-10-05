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


def run(case, sv, towers=None, strict=True, extra=None):
    d = tempfile.mkdtemp()
    json.dump(sv, open(os.path.join(d, "s.json"), "w"))
    lay = {"map": "chernarusplus", "mission": "m", "blocks": [], "roads": [],
           "site": {"name": case, "placeholder": False, "center": [1000.0, 2000.0], "yaw": 0.0,
                    "survey": "s.json", "base_y": None, "clearance": 0.05, "max_ground_drop": 2.2},
           "towers": towers or [{"id": "A1", "type": "TowerA", "offset": [0, 0], "yaw": 0}]}
    lay.update(extra or {})
    yaml.safe_dump(lay, open(os.path.join(d, "layout.yaml"), "w"))
    args = [sys.executable, TOOL, "--layout", os.path.join(d, "layout.yaml"), "--out", os.path.join(d, "out")]
    if strict:
        args.append("--strict")
    r = subprocess.run(args, capture_output=True, text=True)
    objs = json.load(open(os.path.join(d, "out", "sky_objects.json")))["Objects"] if r.returncode == 0 else []
    return r.returncode, r.stdout, objs


def run_layout(path, strict=False):
    out = tempfile.mkdtemp()
    args = [sys.executable, TOOL, "--layout", path, "--out", out] + (["--strict"] if strict else [])
    r = subprocess.run(args, capture_output=True, text=True)
    return r.returncode, r.stdout, out


def variant(i, j, **kw):
    t = {"id": "B1", "type": "TowerA", "at": [0, 0], "yaw": 0}
    t.update(kw)
    return {"streets": {"origin": [0, 0], "extent": [-2, 2, -2, 2], "ns": [-2, 2], "ew": [-2, 2]},
            "blocks": [{"id": "C", "cells": [i, j, i + 2, j + 2], "towers": [t]}], "towers": []}


def district_tests(expect):
    tpl = os.path.join(os.path.dirname(HERE), "district_template.yaml")
    rc, out, od = run_layout(tpl)
    objs = json.load(open(os.path.join(od, "sky_objects.json")))["Objects"] if rc == 0 else []
    rep = open(os.path.join(od, "placement_report.md")).read() if rc == 0 else ""
    expect("district template runs offline (warnings only)", rc == 0 and "site.center is not set" in out, out)
    expect("template: 4 towers x 8 modules", sum(o["name"].startswith(("Land_SKY_TowerA_", "Land_SKY_Floor_", "Land_SKY_Roof_")) for o in objs) == 32, rep[:400])
    expect("template: variants placed", any(o["name"] == "Land_SKY_Floor_Hotel" for o in objs) and any(o["name"] == "Land_SKY_Roof_Garden" for o in objs))
    expect("template: furnished props + entity counts in report", any(o["name"] == "Land_SKY_Cubicle" for o in objs) and "**total:" in rep)
    ev = open(os.path.join(od, "cfgeventspawns_snippet.xml")).read() if rc == 0 else ""
    expect("template: garden roof drops use ROOF_DROP_POINTS (+-8, +-2), not the helipad (+-8, +-8)",
           'x="22.000" z="32.000"' in ev and 'x="26.000" z="16.000"' in ev, ev[:600])
    rc, out, _ = run_layout(tpl, strict=True)
    expect("district template refused by --strict", rc == 1 and "PLACEHOLDER" in out, out)

    flat = survey(1000, 2000, lambda i, j: 150.0)
    # districts: the survey must cover the street tiles too (tiles without samples fail)
    flat["samples"] += [v for x in range(-31, 32, 3) for z in range(-31, 32, 3) for v in (1000 + x, 150.0, 2000 + z)]
    rc, out, objs = run("variants-ok", flat, towers=[{"id": "A1", "type": "TowerA", "offset": [0, 0], "yaw": 0,
                                                     "floors": ["hotel"] * 5, "roof": "mechanical"}])
    expect("legacy tower with variants passes", rc == 0 and any(o["name"] == "Land_SKY_Roof_Mechanical" for o in objs), out)
    rc, out, _ = run("floors-4", flat, towers=[{"id": "A1", "type": "TowerA", "offset": [0, 0], "floors": ["office"] * 4}])
    expect("wrong floor count fails (core stops)", rc == 1 and "typical-floor stops" in out, out)
    rc, out, _ = run("variant-bad", flat, towers=[{"id": "A1", "type": "TowerA", "offset": [0, 0], "roof": "pool"}])
    expect("unknown roof variant fails", rc == 1 and "unknown roof variant" in out, out)
    rc, out, _ = run("furnish-bad", flat, towers=[{"id": "A1", "type": "TowerA", "offset": [0, 0], "furnish": {"2": "hotel"}}])
    expect("furnish set on the wrong floor type fails", rc == 1 and "does not fit" in out, out)
    rc, out, _ = run("street-overlap", flat, towers=[], extra=variant(-2, -1))
    expect("tower over a street fails", rc == 1 and "overlaps street tile" in out, out)
    big = variant(-1, -1)
    big["blocks"][0]["towers"][0]["at"] = [6.0, 0.0]   # 6 + 12 > 18 - 0.5 setback
    rc, out, _ = run("leaves-block", flat, towers=[], extra=big)
    expect("tower leaving its block fails", rc == 1 and "leaves block" in out, out)
    ok = variant(-1, -1)
    rc, out, objs = run("block-ok", flat, towers=[], extra=ok)
    expect("tower in a 3x3 block between streets passes", rc == 0 and sum(o["name"] == "Land_SKY_Street_Intersection" for o in objs) == 4, out)
    lit = variant(-1, -1)
    lit["streets"]["lights_every"] = 1
    rc, out, _ = run("lights", flat, towers=[], extra=lit)
    expect("street lights over LIGHT_CAP fail", rc == 1 and "LIGHT_CAP" in out, out)
    dec = variant(-1, -1, floors=["mechanical", "office", "office", "office", "office"])
    dec["decals"] = [{"tower": "B1", "face": "S", "u": 11.5, "z": 7.5, "type": "Decal_Graffiti_A"}]
    rc, out, _ = run("decal-off", flat, towers=[], extra=dec)
    expect("decal running off the facade fails", rc == 1 and "runs off" in out, out)
    dec["decals"] = [{"tower": "B1", "face": "S", "u": 0.0, "z": 1.0, "type": "Decal_Graffiti_A"}]
    rc, out, _ = run("decal-glass", flat, towers=[], extra=dec)
    expect("decal over lobby glass / entrance fails (D44)", rc == 1 and "opaque" in out, out)
    dec["decals"] = [{"tower": "B1", "face": "S", "u": 0.0, "z": 7.5, "type": "Decal_Graffiti_A"}]
    rc, out, objs = run("decal-ok", flat, towers=[], extra=dec)
    d = [o for o in objs if o["name"] == "Land_SKY_Decal_Graffiti_A"]
    expect("decal placed flush at facade + DECAL_OFFSET", rc == 0 and d and abs(d[0]["pos"][2] - (2000.0 - 12.0 - 0.025)) < 1e-3, str(d))
    slope = survey(1000, 2000, lambda i, j: 150.0)
    # street tiles beyond |x| > 20 m sit over ground 2 m lower than the tower site (> slab + skirt 0.8 m)
    slope["samples"] += [v for x in range(-30, 31, 3) for z in range(-30, 31, 3) for v in (1000 + x, 150.0 - (2.0 if abs(x) > 20 else 0.0), 2000 + z)]
    rc, out, _ = run("tile-slope", slope, towers=[], extra=variant(-1, -1))
    expect("street tile over a drop deeper than its skirt fails", rc == 1 and "skirt" in out, out)
    rc, out, _ = run("tile-unsurveyed", survey(1000, 2000, lambda i, j: 150.0), towers=[], extra=variant(-1, -1))
    expect("street tile without survey samples fails (security M2)", rc == 1 and "no survey samples" in out, out)
    rock = dict(flat, objects=[{"type": "rock_bright_spike1", "pos": [1024.0, 150.0, 2000.0]}])
    rc, out, _ = run("tile-rock", rock, towers=[], extra=variant(-1, -1))
    expect("rock under a street tile fails in --strict (security M2/L1)", rc == 1 and "rock_bright_spike1" in out, out)
    yw = variant(-1, -1, yaw=45)
    rc, out, _ = run("yaw45", flat, towers=[], extra=yw)
    expect("tower yaw not a multiple of 90 fails", rc == 1 and "multiple of 90" in out, out)
    dup = variant(-1, -1)
    dup["towers"] = [{"id": "B1", "type": "TowerA", "offset": [200, 0]}]
    rc, out, _ = run("dup-id", flat, towers=None, extra=dup)
    expect("duplicate tower ids fail", rc == 1 and "duplicate tower id" in out, out)
    d = tempfile.mkdtemp()
    rc, _o, od = run_layout(tpl, strict=True)
    expect("failed run writes no deployable sky_objects.json", not os.path.exists(os.path.join(od, "sky_objects.json"))
           and os.path.exists(os.path.join(od, "sky_objects.FAILED.json")))

    # lights: pole on the -X sidewalk of its tile, arm (+X) over the road; every 2nd straight tile per street
    lit = variant(-1, -1)
    lit["streets"]["lights_every"] = 2
    rc, out, objs = run("lights-side", flat, towers=[], extra=lit)
    tiles = [o for o in objs if o["name"] == "Land_SKY_Street_Straight" and abs(o["pos"][0] - (1000 - 24.0)) < 1e-3]
    lights = [o for o in objs if o["name"] == "Land_SKY_StreetLight" and abs(o["pos"][0] - (1000 - 24.0 - 4.5)) < 1e-3]
    expect("lights sit on the -X sidewalk (arm over the road)", rc == 0 and lights and len(lights) == (len(tiles) + 1) // 2, "%d lights / %d tiles\n%s" % (len(lights), len(tiles), out))
    ys = {round(o["pos"][1], 3) for o in objs if o["name"].startswith("Land_SKY_Street_")}
    expect("one street plane for every tile", rc == 0 and len(ys) == 1, str(ys))
    _rc, _out, tod = run_layout(tpl)
    zt = os.path.join(tod, "zombie_territories_snippet.xml")
    expect("district writes one InfectedCity zone (r >= 50)", os.path.exists(zt) and open(zt).read().count('<zone name="InfectedCity"') == 1
           and float(open(zt).read().split('r="')[1].split('"')[0]) >= 50)
    other = os.path.join(tod, "sky_objects.json")
    d2 = tempfile.mkdtemp()
    r = subprocess.run([sys.executable, TOOL, "--layout", tpl, "--out", d2, "--others", ",".join([other] * 4)], capture_output=True, text=True)
    expect("--others: 5 template districts exceed ENTITY_CAP per_server", r.returncode == 1 and "per_server" in r.stdout, r.stdout[-400:])
    r = subprocess.run([sys.executable, TOOL, "--layout", tpl, "--out", d2, "--others", ",".join([other] * 2)], capture_output=True, text=True)
    expect("--others: 3 template districts stay under ENTITY_CAP per_server", r.returncode == 0, r.stdout[-400:])

    # FPS D / D0 / D-dec must share the same site (perf batch-6 re-gate M-7)
    sites = [yaml.safe_load(open(os.path.join(os.path.dirname(HERE), f)))["site"]
             for f in ("district_template.yaml", "district_template_noprops.yaml", "district_template_decals.yaml")]
    expect("D / D0 / D-dec layouts share an identical site block", sites[0] == sites[1] == sites[2], str(sites))

    sys.path.insert(0, os.path.dirname(HERE))
    import sky_layout as SL
    S = SL.S
    S.FURNISH["_t_many"] = {"for": [S.CLASS_FLOOR], "props": [("ServerRack", -11.0 + 1.5 * k, 11.0, 0) for k in range(26)]}
    S.FURNISH["_t_tight"] = {"for": [S.CLASS_FLOOR], "props": [("Desk", 8.0, -8.0, 0), ("Desk", 8.0, -7.0, 0)]}
    ctx = SL.Ctx(True)
    t = {"id": "X", "type": "TowerA", "furnish": {"1": "_t_many", "2": "_t_tight"}}
    mods = SL.tower_modules(ctx, t)
    SL.furnish(ctx, t, mods, 0.0, 0.0, 0.0, 0.0)
    expect("PROP_CAPS per_floor enforced", any("per_floor" in e for e in ctx.errors), str(ctx.errors))
    expect("aisle minimum enforced", any("aisle" in e for e in ctx.errors), str(ctx.errors))
    # P9: flipping YAW_SIGN changes only the written yaw, never a position (QA re-gate R-M1)
    base = SL.spawner("X", (1.0, 2.0, 3.0), 90.0)
    S.YAW_SIGN = -1
    flip = SL.spawner("X", (1.0, 2.0, 3.0), 90.0)
    S.YAW_SIGN = 1
    expect("YAW_SIGN flips only ypr (270 vs 90), positions unchanged", base["pos"] == flip["pos"] and base["ypr"][0] == 90.0 and flip["ypr"][0] == 270.0, "%s %s" % (base, flip))


def city_tests(expect):
    """City block fill (D57): template runs, deterministic, inside blocks, no overlaps, fronts on
    the street, ruin mix follows the zones, caps / streets / skirt enforced."""
    sys.path.insert(0, os.path.dirname(HERE))
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "assets"))
    import math
    import city_fill as CF
    import skyspec as S
    tpl = os.path.join(os.path.dirname(HERE), "city_template.yaml")
    rc, out, od = run_layout(tpl)
    expect("city template runs (target terrain)", rc == 0 and os.path.exists(os.path.join(od, "city_objects.csv")), out)
    a = json.load(open(os.path.join(od, "sky_objects.json")))["Objects"]
    rc2, _out2, od2 = run_layout(tpl)
    b = json.load(open(os.path.join(od2, "sky_objects.json")))["Objects"]
    expect("city fill is deterministic", a == b)
    nb = sum(1 for o in a if o["name"].startswith("Land_SKY_City_"))
    expect("city template places > 80 buildings (landmark blocks hold fewer, bigger ones)", nb > 80, str(nb))
    lay = yaml.safe_load(open(tpl))
    tile = S.STREET["tile"]
    inside_ok, overlap_ok, front_ok = True, True, True
    ruin_by_zone = {}
    for blk in lay["blocks"]:
        i0, j0, i1, j1 = blk["cells"]
        rect = (i0 * tile - tile / 2, i1 * tile + tile / 2, j0 * tile - tile / 2, j1 * tile + tile / 2)
        res = CF.fill_block(S, blk, rect, S.BLOCK_SETBACK)
        quads = []
        bc = ((rect[0] + rect[1]) / 2, (rect[2] + rect[3]) / 2)
        for cls, arch, state, u, v, yaw, hw, hd, _ou, _ov in res:
            q = CF._corners(u, v, hw, hd, yaw)
            m = S.BLOCK_SETBACK - 1e-6
            if any(not (rect[0] + m <= x <= rect[1] - m and rect[2] + m <= z <= rect[3] - m) for x, z in q):
                inside_ok = False
            if any(CF._sat(q, o) for o in quads):
                overlap_ok = False
            quads.append(q)
            f = CF._rot(0.0, -1.0, yaw)                       # model front (-Y) in the site frame
            if arch not in S.CITY_PIECES and (u - bc[0]) * f[0] + (v - bc[1]) * f[1] <= 0:
                front_ok = False
            z = blk["fill"]["zone"]
            ruin_by_zone.setdefault(z, []).append(state)
    expect("every city building inside its block (setback)", inside_ok)
    expect("no two city buildings overlap", overlap_ok)
    expect("every front faces the street (out of the block)", front_ok)
    share = {z: sum(1 for x in v if x == 2) / float(len(v)) for z, v in ruin_by_zone.items()}
    expect("frontline is more ruined than residential", share["frontline"] > share["residential"], str(share))
    small = {}
    for blk in lay["blocks"]:
        i0, j0, i1, j1 = blk["cells"]
        rect = (i0 * tile - tile / 2, i1 * tile + tile / 2, j0 * tile - tile / 2, j1 * tile + tile / 2)
        n = sum(1 for r in CF.fill_block(S, blk, rect, S.BLOCK_SETBACK)
                if CF.is_small(S, r[1]))
        small[blk["id"]] = n <= S.CITY_ZONES[blk["fill"]["zone"]].get("small_cap", 1)
    expect("small buildings within small_cap per block", all(small.values()), str(small))
    # spawner target: the same city exceeds ENTITY_CAP -> fails
    d = tempfile.mkdtemp()
    lay2 = dict(lay)
    lay2["site"] = dict(lay["site"], target="spawner")
    yaml.safe_dump(lay2, open(os.path.join(d, "c.yaml"), "w"))
    rc, out, od3 = run_layout(os.path.join(d, "c.yaml"))
    rep = open(os.path.join(od3, "placement_report.md")).read()
    import re
    m = re.search(r"\*\*total: (\d+)\*\* entities, (\d+) loot", rep)
    over = m and int(m.group(1)) + int(m.group(2)) > S.ENTITY_CAP["per_district"]
    expect("spawner target enforces ENTITY_CAP (fails exactly when over)", m and ((rc == 1 and "ENTITY_CAP" in out) == bool(over)),
           out)
    rep_t = open(os.path.join(od, "placement_report.md")).read()
    expect("terrain target reports the cap as not applied", "ENTITY_CAP not applied" in rep_t)
    # explicit building across a street fails; steep survey fails the skirt
    lay3 = {"map": "chernarusplus", "mission": "m", "towers": [],
            "site": {"name": "c3", "placeholder": False, "center": [1000.0, 2000.0], "yaw": 0.0, "target": "terrain",
                     "survey": "s.json", "base_y": None, "clearance": 0.05},
            "streets": {"origin": [0, 0], "extent": [-2, 2, -2, 2], "ns": [-2, 2], "ew": [-2, 2]},
            "blocks": [{"id": "X", "cells": [-1, -1, 1, 1],
                        "buildings": [{"type": "Police", "ruin": "intact", "at": [0.0, -14.0], "yaw": 0}]}]}
    sv = survey(1000, 2000, lambda i, j: 150.0)
    sv["samples"] = []
    for i in range(-30, 31, 2):
        for j in range(-30, 31, 2):
            sv["samples"] += [1000 + i, 150.0, 2000 + j]
    d = tempfile.mkdtemp()
    json.dump(sv, open(os.path.join(d, "s.json"), "w"))
    yaml.safe_dump(lay3, open(os.path.join(d, "c.yaml"), "w"))
    rc, out, _ = run_layout(os.path.join(d, "c.yaml"))
    expect("city building across a street fails", rc == 1 and "overlaps street tile" in out, out)
    lay3["blocks"][0]["buildings"][0]["at"] = [0.0, -7.0]
    for k in range(0, len(sv["samples"]), 3):
        sv["samples"][k + 1] = 150.0 + 0.25 * (sv["samples"][k] - 1000)
    json.dump(sv, open(os.path.join(d, "s.json"), "w"))
    yaml.safe_dump(lay3, open(os.path.join(d, "c.yaml"), "w"))
    rc, out, _ = run_layout(os.path.join(d, "c.yaml"))
    expect("city building on a steep slope fails the skirt", rc == 1 and "skirt" in out, out)
    del math


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
    # tall cores (D58): a T23 tower stacks lobby + 23 floors + roof on Land_SKY_TowerA_Core23
    rc, out, objs = run("tall", survey(1000, 2000, lambda i, j: 150.0),
                        towers=[{"id": "T1", "type": "TowerA", "offset": [0, 0], "yaw": 0, "core": "T23", "roof": "crown"}])
    names = [o["name"] for o in objs]
    expect("tall core T23: 26 objects (lobby, 23 floors, crown roof, core)", rc == 0 and len(objs) == 26, out)
    expect("tall core T23 spawns Land_SKY_TowerA_Core23 and the crown roof",
           "Land_SKY_TowerA_Core23" in names and "Land_SKY_Roof_Crown" in names, str(names))
    rc, out, _ = run("tall-mismatch", survey(1000, 2000, lambda i, j: 150.0),
                     towers=[{"id": "T1", "type": "TowerA", "offset": [0, 0], "yaw": 0, "core": "T15",
                              "floors": ["office"] * 5}])
    expect("floors list must match the core's stops", rc == 1 and "core T15 has exactly 15" in out, out)
    district_tests(expect)
    city_tests(expect)
    print("%d failed" % fails)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
