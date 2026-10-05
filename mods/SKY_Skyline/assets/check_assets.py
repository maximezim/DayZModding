#!/usr/bin/env python3
"""Asset gate: P3D structure + manifest budgets (static part of the perf/qa gates).

    python mods/SKY_Skyline/assets/check_assets.py [--strict]

For every manifest entry with a `p3d` + `budget`:
  * required LODs present (enterable modules: 3+ Resolution, Shadow, Geometry,
    Fire, View, Roadway, Memory), Geometry has mass + autocenter=0
  * triangles per LOD / Geometry components / Res0 sections within budget
Budgets are hypotheses, so overruns are WARN unless --strict. Structure errors always FAIL.
"""
import argparse
import os
import re
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "..", "..", "tools", "assets"))
import p3d_inspect  # noqa: E402

ENTERABLE = ["Shadow Volume", "Geometry", "Fire Geometry", "View Geometry", "Roadway", "Memory"]
# Alpha-TESTED materials are cheap at range; any other _ca texture or the blended glass in Res2+
# is a blended draw at distance (perf_review H2, batch-6 perf M3: static gate instead of diag stats).
sys.path.insert(0, HERE)
from gen_configs import ALPHA_TEST  # noqa: E402  (single source: rvmats with renderFlags AlphaTest32)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true")
    a = ap.parse_args()
    man = yaml.safe_load(open(os.path.join(HERE, "manifest.yaml")))
    entries = [e for e in man.get("kit", []) + man.get("items", []) + man.get("generated_kit", [])
               if isinstance(e, dict) and e.get("p3d")]
    fails = warns = 0
    for e in entries:
        lods = p3d_inspect.parse(os.path.join(ROOT, e["p3d"]))
        by = {l["name"]: l for l in lods}
        res = sorted((l for l in lods if l["name"].startswith("Resolution")), key=lambda l: l["resolution"])
        b = e.get("budget", {})
        errs, over = [], []
        is_item = e["p3d"].startswith("addons/sky_items")
        # kit asset: 3+ Res, Geometry, Fire Geometry; floor/roof variants are enterable modules
        is_prop = "category" in e and e["category"] not in ("floor", "roof", "city", "city_tall", "city_large", "core_tall")
        if is_prop:
            flat = e["category"] in ("flat", "decal")   # decals: render only, must NOT collide
            need = (["Roadway"] if e["category"] == "flat" else []) if flat else ["Geometry", "Fire Geometry"]
            if e["category"] in ("small", "medium"):    # interior_small: no shadow volume (perf batch-3 M3)
                need.append("Shadow Volume")    # perf batch-1 M3
            for req in need:
                if req not in by:
                    errs.append("missing LOD " + req)
            if flat and ("Geometry" in by or "Fire Geometry" in by):
                errs.append("flat decal must not have Geometry/Fire Geometry")
            if len(res) < 3:
                errs.append("only %d resolution LODs" % len(res))
            g = by.get("Geometry")
            if g and g["properties"].get("autocenter") != "0":
                errs.append("Geometry lacks autocenter=0")
        elif not is_item:
            for req in ENTERABLE:
                if req not in by:
                    errs.append("missing LOD " + req)
            if len(res) < 3:
                errs.append("only %d resolution LODs" % len(res))
            g = by.get("Geometry")
            if g and g["properties"].get("autocenter") != "0":
                errs.append("Geometry lacks autocenter=0")
        g = by.get("Geometry")
        if (not g or not g["mass"]) and e.get("category") not in ("flat", "decal"):
            errs.append("Geometry missing or massless")
        for i, key in enumerate(("res0", "res1", "res2", "res3")):
            if key in b and i < len(res) and res[i]["triangles"] > b[key]:
                over.append("%s %d > %d" % (key, res[i]["triangles"], b[key]))
        if "shadow" in b and "Shadow Volume" in by and by["Shadow Volume"]["triangles"] > b["shadow"]:
            over.append("shadow %d > %d" % (by["Shadow Volume"]["triangles"], b["shadow"]))
        if g:
            comps = sum(1 for k in g["selections"] if k.startswith("Component"))
            if "geo_comps" in b and comps > b["geo_comps"]:
                over.append("geo comps %d > %d" % (comps, b["geo_comps"]))
            if "geo_tris" in b and g["triangles"] > b["geo_tris"]:
                over.append("geo tris %d > %d" % (g["triangles"], b["geo_tris"]))
        if res and "sections_res0" in b:
            sec = len(set(res[0]["materials"]) | set(res[0]["textures"])) // 2 or 1
            if sec > b["sections_res0"]:
                over.append("res0 sections %d > %d" % (sec, b["sections_res0"]))
        if e.get("category") != "decal":          # decal Res2 blending is a documented decision (D22)
            for i, l in enumerate(res[2:], 2):
                blended = [t for t in l["textures"] if t.lower().endswith("_ca.paa")
                           and re.sub(r"(_[a-d])?_ca$", "", os.path.basename(t.replace("\\", "/")).lower()[:-4]) not in ALPHA_TEST]
                if blended or any(m.lower().replace("\\", "/").endswith("/sky_glass.rvmat") for m in l["materials"]):
                    errs.append("blended alpha in Res%d (far LOD): %s" % (i, blended or "sky_glass.rvmat"))
        chain = " -> ".join(str(l["triangles"]) for l in res)
        state = "FAIL" if errs else ("OVER" if over else "PASS")
        print("%-32s %-4s LODs=%d res=%s %s" % (e["name"], state, len(lods), chain, "; ".join(errs + over)))
        fails += bool(errs) or (a.strict and bool(over))
        warns += bool(over)
    print("\n%d checked, %d fail, %d over budget (hypotheses)" % (len(entries), fails, warns))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
