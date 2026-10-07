#!/usr/bin/env python3
"""Self-test for sky_layout.py with synthetic surveys (no game needed).

    python mods/SKY_Skyline/placement/tests/test_sky_layout.py
"""
import json
import re
import os
import subprocess
import sys
import tempfile

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), "sky_layout.py")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "assets"))
import skyspec as S  # noqa: E402


JAM_SEDANS = ("Land_SKY_Wreck_Sedan", "Land_SKY_Wreck_Sedan_B", "Land_SKY_Wreck_Sedan_C")   # D74 jam variants

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
    # D61: city life template - parks, venues, jams, viaduct, tunnel, bridge, street furniture, sirens
    life = os.path.join(os.path.dirname(HERE), "citylife_template.yaml")
    rc, out, od = run_layout(life)
    objs = json.load(open(os.path.join(od, "sky_objects.json")))["Objects"] if rc == 0 else []
    names = [o["name"] for o in objs]
    rep = open(os.path.join(od, "placement_report.md")).read() if rc == 0 else ""
    expect("city life template (D61) runs offline", rc == 0, out)
    for cls, n in (("Land_SKY_Fair_FerrisWheel", 1), ("Land_SKY_Landfill", 1), ("Land_SKY_Stadium_Pitch", 1),
                   ("Land_SKY_Viaduct_Ramp", 2), ("Land_SKY_Tunnel_Portal", 2), ("Land_SKY_Bridge_Long", 1),
                   ("Land_SKY_SirenTower", 2), ("Land_SKY_City_Cinema_Intact", 1), ("Land_SKY_City_Mall_Damaged", 1)):
        expect("city life: %d x %s" % (n, cls), names.count(cls) == n, str(names.count(cls)))
    expect("city life: car jams with vanilla wreck decor + our blockers",
           any(nm.startswith("Land_Wreck_") for nm in names) and names.count("Land_SKY_Barrier_Concrete") +
           sum(names.count(c) for c in JAM_SEDANS) + names.count("Land_SKY_Wreck_Van") >= 30 and "blocking lines" in rep, rep[-800:])
    expect("city life D74: jams mix the sedan variants (intact, burnt, overturned)",
           all(names.count(c) > 0 for c in JAM_SEDANS), str([names.count(c) for c in JAM_SEDANS]))
    expect("city life: wet and dry hydrants, bins", "Land_SKY_Hydrant_Wet" in names and "Land_SKY_Hydrant_Dry" in names
           and "Land_SKY_TrashBin" in names)
    lay = yaml.safe_load(open(life))
    tun_cells = {(c, 0) for c in range(-8, -4)}
    tiles = [o for o in objs if o["name"].startswith("Land_SKY_Street_")]
    expect("city life: no street tile under the tunnel cells",
           not any(abs(o["pos"][0] - 12 * i) < 0.1 and abs(o["pos"][2] - 12 * j) < 0.1 for (i, j) in tun_cells for o in tiles))
    bad = dict(lay)
    bad["viaducts"] = [{"axis": "ew", "index": 6, "from": -7, "to": 8}]          # ramp over the (8, 6) junction
    d = tempfile.mkdtemp()
    yaml.safe_dump(bad, open(os.path.join(d, "l.yaml"), "w"))
    rc, out, _ = run_layout(os.path.join(d, "l.yaml"))
    expect("viaduct ramp over a junction fails", rc == 1 and "ramps need straight tiles" in out, out[-400:])
    bad = dict(lay)
    bad["blocks"] = [dict(b, cells=[-8, -5, -6, -1]) if b["id"] == "FUN" else b for b in lay["blocks"]]
    yaml.safe_dump(bad, open(os.path.join(d, "l2.yaml"), "w"))
    rc, out, _ = run_layout(os.path.join(d, "l2.yaml"))
    expect("funfair in a too small block fails", rc == 1 and "funfair needs" in out, out[-400:])
    # D63: underground under the city life template (terrain target)
    rc, out, od = run_layout(life)
    names = [o["name"] for o in json.load(open(os.path.join(od, "sky_objects.json")))["Objects"]] if rc == 0 else []
    for cls, n in (("Land_SKY_Sewer_Access", 2), ("Land_SKY_Sewer_Stair", 2), ("Land_SKY_Sewer_FloodedEnd", 2),
                   ("Land_SKY_Metro_Station", 1), ("Land_SKY_Metro_Station_B", 1), ("Land_SKY_Metro_End", 2)):
        expect("underground: %d x %s" % (n, cls), names.count(cls) == n, str(names.count(cls)))
    expect("underground D67: collapsed variants mixed in (collapse share)", "Land_SKY_Sewer_Collapsed" in names
           and "Land_SKY_Metro_Collapsed" in names, str([nm for nm in names if "Collapsed" in nm]))
    objs_l = json.load(open(os.path.join(od, "sky_objects.json")))["Objects"] if rc == 0 else []
    stops = [o for o in objs_l if o["name"] == "Land_SKY_BusStop"]
    lamps = [o for o in objs_l if o["name"] == "Land_SKY_StreetLight"]
    jams = [o for o in objs_l if o["name"] in ("Land_SKY_Barrier_Concrete", "Land_SKY_Wreck_Van") + JAM_SEDANS]
    near = lambda a, b, r: (a["pos"][0] - b["pos"][0]) ** 2 + (a["pos"][2] - b["pos"][2]) ** 2 < r * r
    expect("street furniture D67: bus stops, ad columns, phone booths placed", stops and "Land_SKY_AdColumn" in names
           and "Land_SKY_PhoneBooth" in names)
    expect("street furniture D67: no bus stop on a street-lamp spot", not any(near(st, lp, 2.5) for st in stops for lp in lamps))
    expect("street furniture D67: no jam line through a bus stop", not any(near(st, j, 3.5) for st in stops for j in jams))
    trig = json.load(open(os.path.join(od, "cfgundergroundtriggers_snippet.json")))["Triggers"] if rc == 0 else []
    expect("underground: one darkness trigger per piece, stairs fade with breadcrumbs",
           len(trig) == sum(nm.startswith(("Land_SKY_Sewer_", "Land_SKY_Metro_")) for nm in names)
           and any(len(t["Breadcrumbs"]) == 2 for t in trig) and os.path.exists(os.path.join(od, "underground_trenches.json")))
    bad = dict(lay)
    bad["site"] = dict(lay["site"], target="spawner")
    bad["underground"] = lay["underground"]
    for k in ("blocks", "jams", "viaducts", "tunnels", "bridges", "props"):
        bad.pop(k, None)
    yaml.safe_dump(bad, open(os.path.join(d, "l3.yaml"), "w"))
    rc, out, _ = run_layout(os.path.join(d, "l3.yaml"))
    expect("underground on a vanilla map (spawner) fails", rc == 1 and "underground needs site.target: terrain" in out, out[-400:])
    bad = dict(lay)
    bad["underground"] = lay["underground"] + [{"kind": "sewer", "axis": "ns", "index": 8, "from": -5, "to": 5}]
    yaml.safe_dump(bad, open(os.path.join(d, "l4.yaml"), "w"))
    rc, out, _ = run_layout(os.path.join(d, "l4.yaml"))
    expect("a sewer through the metro fails (overlap)", rc == 1 and "overlaps" in out, out[-400:])
    sky = os.path.join(os.path.dirname(HERE), "skyline_template.yaml")
    rc, out, od = run_layout(sky)
    objs = json.load(open(os.path.join(od, "sky_objects.json")))["Objects"] if rc == 0 else []
    names = [o["name"] for o in objs]
    expect("skyline template (D60) runs offline: HQ, tall cores, lobby B, one skybridge, under ENTITY_CAP",
           rc == 0 and names.count("Land_SKY_Skybridge") == 1 and "Land_SKY_TowerA_Core33" in names
           and names.count("Land_SKY_Floor_HQ") == 32 and "Land_SKY_TowerA_Lobby_B" in names, out)

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
    tiles = [o for o in objs if o["name"] in ("Land_SKY_Street_Straight", "Land_SKY_Street_Straight_B")   # D75 worn variant
             and abs(o["pos"][0] - (1000 - 24.0)) < 1e-3]
    lights = [o for o in objs if o["name"] == "Land_SKY_StreetLight" and abs(o["pos"][0] - (1000 - 24.0 - 4.5)) < 1e-3]
    expect("lights sit on the -X sidewalk (arm over the road)", rc == 0 and lights and len(lights) == (len(tiles) + 1) // 2, "%d lights / %d tiles\n%s" % (len(lights), len(tiles), out))
    ys = {round(o["pos"][1], 3) for o in objs if o["name"].startswith("Land_SKY_Street_")}
    expect("one street plane for every tile", rc == 0 and len(ys) == 1, str(ys))
    allt = [o for o in objs if o["name"] in ("Land_SKY_Street_Straight", "Land_SKY_Street_Straight_B")]
    worn = sum(o["name"] == "Land_SKY_Street_Straight_B" for o in allt)
    expect("D75: worn straight tiles mixed in (about 40 %)", allt and 0 < worn < len(allt),
           "%d of %d" % (worn, len(allt)))
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
            if arch in S.VEG_PIECES:                          # plants: checked below (yards may sit in a footprint)
                continue
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
    # terrain-aware fill (D59): a 3 m hollow in one corner of a filled block - the fill gives those lots
    # up (yard / weeds) instead of failing; spawner site gets clutter cutters at ground level
    lay4 = {"map": "chernarusplus", "mission": "m", "towers": [],
            "site": {"name": "c4", "placeholder": False, "center": [1000.0, 2000.0], "yaw": 0.0, "target": "spawner",
                     "survey": "s.json", "base_y": None, "clearance": 0.05},
            "streets": {"origin": [0, 0], "extent": [-2, 2, -2, 2], "ns": [-2, 2], "ew": [-2, 2]},
            "blocks": [{"id": "Y", "cells": [-1, -1, 1, 1], "fill": {"zone": "residential", "seed": 3}}]}
    hollow = lambda x, z: 150.0 - (3.0 if (1003 < x < 1017 and 2003 < z < 2017) else 0.0)
    sv4 = survey(1000, 2000, lambda i, j: 150.0)
    sv4["samples"] = []
    for i in range(-30, 31, 1):
        for j in range(-30, 31, 1):
            sv4["samples"] += [1000 + i, hollow(1000 + i, 2000 + j), 2000 + j]
    d4 = tempfile.mkdtemp()
    json.dump(sv4, open(os.path.join(d4, "s.json"), "w"))
    yaml.safe_dump(lay4, open(os.path.join(d4, "c.yaml"), "w"))
    rc, out, od4 = run_layout(os.path.join(d4, "c.yaml"))
    rep4 = open(os.path.join(od4, "placement_report.md")).read()
    m4 = re.search(r"could not take \(given to a smaller type or left as yard\): (\d+)", rep4)
    expect("terrain-aware fill: a hollow in the block is routed around, run passes", rc == 0 and m4 and int(m4.group(1)) > 0,
           out + rep4[:1500])
    objs4 = json.load(open(os.path.join(od4, "sky_objects.json")))["Objects"] if rc == 0 else []
    bld = [o for o in objs4 if o["name"].startswith("Land_SKY_City_")]
    expect("no city building stands over the hollow", bld and all(not (1004 < o["pos"][0] < 1016 and 2004 < o["pos"][2] < 2016) or
                                                                  o["name"].startswith("Land_SKY_Veg") for o in bld), str(bld[:3]))
    cut4 = [o for o in objs4 if o["name"] == S.CLUTTER_CUTTER["class"]]
    expect("spawner city: clutter cutters under the ground floors", len(cut4) >= len(bld), "%d cutters, %d buildings" % (len(cut4), len(bld)))
    veg4 = [o for o in objs4 if o["name"].startswith("Land_SKY_Veg_")]
    expect("overgrowth placed on the ground (plants follow the hollow)", veg4 and all(o["pos"][1] <= 150.0 + 1e-6 for o in veg4),
           str(veg4[:3]))
    del math


def main():
    fails = 0

    def expect(name, cond, info=""):
        nonlocal fails
        print(("PASS " if cond else "FAIL ") + name + ("" if cond else "\n" + info))
        fails += not cond

    rc, out, objs = run("flat", survey(1000, 2000, lambda i, j: 150.0 + 0.01 * i))
    lobby = [o for o in objs if o["name"] == "Land_SKY_TowerA_Lobby"]
    cut = [o for o in objs if o["name"] == S.CLUTTER_CUTTER["class"]]
    expect("flat site passes strict", rc == 0, out)
    expect("base height = max ground inside footprint + clearance", lobby and abs(lobby[0]["pos"][1] - (150.11 + 0.05)) < 1e-3, str(lobby))
    expect("8 objects (lobby, 5 floors, roof, core)", len(objs) - len(cut) == 8, str(len(objs)))
    expect("spawner site: 16 clutter cutters (6 m grid) under the 24 x 24 m lobby, at ground level",
           len(cut) == 16 and all(abs(o["pos"][1] - 150.11) < 1e-3 for o in cut), str(cut[:2]))

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
    names = [o["name"] for o in objs if o["name"] != S.CLUTTER_CUTTER["class"]]
    expect("tall core T23: 26 objects (lobby, 23 floors, crown roof, core)", rc == 0 and len(names) == 26, out)
    expect("tall core T23 spawns Land_SKY_TowerA_Core23 and the crown roof",
           "Land_SKY_TowerA_Core23" in names and "Land_SKY_Roof_Crown" in names, str(names))
    rc, out, _ = run("tall-mismatch", survey(1000, 2000, lambda i, j: 150.0),
                     towers=[{"id": "T1", "type": "TowerA", "offset": [0, 0], "yaw": 0, "core": "T15",
                              "floors": ["office"] * 5}])
    expect("floors list must match the core's stops", rc == 1 and "core T15 has exactly 15" in out, out)
    # D60: skybridge between two roofs, Lobby_B, office facade variants
    wide = survey(1000, 2000, lambda i, j: 150.0)
    wide["samples"] += [v for x in range(-40, 41, 2) for z in range(-14, 15, 2) for v in (1000 + x, 150.0, 2000 + z)]
    pair = [{"id": "A1", "type": "TowerA", "offset": [-24, 0], "yaw": 0, "lobby": "B",
             "floors": ["office_concrete", "office_brick", "hq", "office", "office"]},
            {"id": "A2", "type": "TowerA", "offset": [24, 0], "yaw": 0, "roof": "garden"}]
    rc, out, objs = run("skybridge", wide, towers=pair, extra={"skybridges": [{"from": "A1", "to": "A2"}]})
    br = [o for o in objs if o["name"] == "Land_SKY_Skybridge"]
    roof_y = [o["pos"][1] for o in objs if o["name"] == "Land_SKY_Roof_Garden"]
    expect("skybridge placed once between the roofs (gap centre, lateral EW offset, roof height)",
           rc == 0 and len(br) == 1 and abs(br[0]["pos"][0] - 1000.0) < 1e-3
           and abs(br[0]["pos"][2] - (2000.0 + S.SKYBRIDGE["lateral"]["EW"])) < 1e-3
           and roof_y and abs(br[0]["pos"][1] - roof_y[0]) < 1e-3, out + str(br))
    names = {o["name"] for o in objs}
    expect("lobby B and office facade variants spawn their classes",
           {"Land_SKY_TowerA_Lobby_B", "Land_SKY_Floor_Office_Concrete", "Land_SKY_Floor_Office_Brick",
            "Land_SKY_Floor_HQ"} <= names, str(sorted(names)))
    near = [dict(pair[0], offset=[-20, 0]), dict(pair[1], offset=[20, 0])]
    rc, out, _ = run("skybridge-gap", wide, towers=near, extra={"skybridges": [{"from": "A1", "to": "A2"}]})
    expect("skybridge with the wrong facade gap fails", rc == 1 and "facade gap" in out, out)
    turned = [pair[0], dict(pair[1], yaw=90)]
    rc, out, _ = run("skybridge-yaw", wide, towers=turned, extra={"skybridges": [{"from": "A1", "to": "A2"}]})
    expect("skybridge between towers of different yaw fails", rc == 1 and "different yaw" in out, out)
    district_tests(expect)
    city_tests(expect)
    print("%d failed" % fails)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
