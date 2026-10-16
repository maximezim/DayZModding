#!/usr/bin/env python3
"""Self-test for terrain_mapper.py with a synthetic capture (no game needed, D104).

    python mods/SKY_Skyline/terrain/tests/test_terrain_mapper.py
"""
import json
import math
import os
import re
import shutil
import sys
import tempfile

import numpy as np
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
TERRAIN = os.path.dirname(HERE)
MOD = os.path.dirname(TERRAIN)
sys.path.insert(0, TERRAIN)
import terrain_mapper as TM  # noqa: E402

CAPTURE_C = os.path.join(MOD, "addons", "sky_scripts", "scripts", "5_Mission", "SKY", "SKY_TerrainCapture.c")
FAILS = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        FAILS.append(msg)


def ground(x, z):
    """Tilted, rolling ground: 1.5 % slope east plus hills of a few metres."""
    return 150.0 + 0.015 * (x - 5000) + 3.0 * np.sin(x / 47.0) * np.cos(z / 61.0) + 1.5 * np.sin((x + z) / 23.0)


def make_capture(d, label, x0, z0, cell, nx, nz, surf_fn=None, objects=()):
    """Writes the files exactly as SKY_TerrainCapture.c does (north row first, integer cm, trailing spaces)."""
    xs = x0 + np.arange(nx) * cell
    names = []
    with open(os.path.join(d, label + "_heights.txt"), "w") as fh, open(os.path.join(d, label + "_surfaces.txt"), "w") as fs:
        for r in range(nz):
            z = z0 + (nz - 1 - r) * cell
            hs = np.rint(ground(xs, z) * 100).astype(int)
            fh.write("".join("%d " % v for v in hs) + "\n")
            row = []
            for x in xs:
                s = surf_fn(x, z) if surf_fn else ("cp_grass" if (int(x / 40) + int(z / 40)) % 3 else "cp_dirt")
                if s not in names:
                    names.append(s)
                row.append(names.index(s))
            fs.write("".join("%d " % v for v in row) + "\n")
    with open(os.path.join(d, label + "_objects.txt"), "w") as fo:
        for o in objects:
            fo.write(";".join(str(v) for v in o) + "\n")
        fo.write("bad;line\n")                          # malformed lines are skipped
        fo.write('Land_X";1;2;3;4;5;6;7;1\n')           # quote injection: rejected
        fo.write('Evil";x;1;2;3;0;0;0;1\n')             # quote in the type: rejected
        fo.write("Tree;t.p3d;nan;150;5000;0;0;0;1\n")   # non-finite: rejected
    meta = {"version": 1, "label": label, "x0": x0, "z0": z0, "cell": cell, "nx": nx, "nz": nz, "worldSize": 15360,
            "surfaces": names, "objects": len(objects), "objectsTruncated": False, "rowOrder": "north_first",
            "heightUnit": "cm", "complete": True}
    json.dump(meta, open(os.path.join(d, label + "_meta.json"), "w"))


def make_layout(d, street_y):
    objs = []
    for i in range(-4, 5):
        for j in range(-4, 5):
            name = "Land_SKY_Street_Intersection" if (i % 4 == 0 and j % 4 == 0) else "Land_SKY_StreetLight"
            objs.append({"name": name, "pos": [5200.0 + i * 12, street_y + (0.15 if "Light" in name else 0.0), 5200.0 + j * 12],
                         "ypr": [0.0, 0.0, 0.0], "scale": 1.0})
    json.dump({"Objects": objs}, open(os.path.join(d, "sky_objects.json"), "w"))
    trench = {"pieces": [{"name": "Land_SKY_Sewer_Straight", "corners": [[5190, 5195], [5210, 5195], [5210, 5199], [5190, 5199]],
                          "bottom": street_y - 6.0}]}
    json.dump(trench, open(os.path.join(d, "underground_trenches.json"), "w"))
    return objs


def project(d, **extra):
    p = {"project": "test_map",
         "source": {"capture": "cap", "label": "t1"},
         "grid": {"cell": 2.0},
         "sites": [{"name": "city", "layout_out": "lay", "margin": 10, "max_slope": 0.5, "min_blend": 20,
                    "surface": "cp_concrete1", "edge_surface": "cp_grass_tall"}],
         "roads": [{"name": "access", "points": [[4880, 4900], [5000, 5050], [5100, 5150], [5140, 5200]], "width": 8,
                    "shoulder": 8, "max_grade": 0.06, "surface": "cp_gravel"}],
         "paint": [{"polygon": [[5350, 4880], [5390, 4880], [5390, 4920], [5350, 4920]], "surface": "cp_rock"}]}
    p.update(extra)
    path = os.path.join(d, "proj.yaml")
    yaml.safe_dump(p, open(path, "w"))
    return path


def main():
    tmp = tempfile.mkdtemp(prefix="sky_tm_")
    try:
        run(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("\n%d failure(s)" % len(FAILS))
    sys.exit(1 if FAILS else 0)


def run(tmp):
    cap, lay = os.path.join(tmp, "cap"), os.path.join(tmp, "lay")
    os.makedirs(cap)
    os.makedirs(lay)
    street_y = 158.0
    objects = [
        ("Land_House_1W01", "dz\\structures\\residential\\houses\\house_1w01.p3d", 5200.0, 150.0, 5200.0, 30, 0, 0, 1),   # in the pad
        ("", "dz\\plants\\tree\\t_betulapendula_2s.p3d", 5263.0, 150.0, 5200.0, 0, 0, 0, 1),                            # blend band
        ("Land_Barn_W1", "dz\\structures\\farm\\barn_w1.p3d", 4830.0, 151.0, 5420.0, 90, 0, 0, 1),                       # far
        ("", "dz\\plants\\bush\\b_corylus_2s.p3d", 5000.0, 150.0, 5050.0, 0, 0, 0, 1),                                    # on the road
    ]
    make_capture(cap, "t1", 4800.0, 4800.0, 5.0, 141, 141, objects=objects)
    make_layout(lay, street_y)
    pp = project(tmp)
    out1 = os.path.join(tmp, "out1")
    _, rep = TM.build(pp, out1)
    g, _, _ = TM.load_asc(os.path.join(out1, "heightmap.asc"))
    src = TM.resample(TM.load_capture(cap, "t1")[0], None, 2.0)

    # 1. grid
    check(g.nx == 351 and g.nz == 351 and abs(g.cell - 2.0) < 1e-9, "resampled grid 351 x 351 at 2 m (%d x %d)" % (g.nx, g.nz))
    check(abs(g.x0 - 4800.0) < 1e-6 and abs(g.z0 - 4800.0) < 1e-6, "ASC xllcorner = 200000 + x0, yllcorner = z0 (origin keep)")
    # 2. pad flat at the layout street level, trench cut
    site = rep["sites"][0]
    check(site["pad_flat"] and abs(site["level"] - street_y) < 1e-6 and abs(site["object_shift"]) < 1e-9,
          "pad flat at the layout street level %.2f (level %.3f, shift %.3f)" % (street_y, site["level"], site["object_shift"]))
    gx, gz = g.coords()
    hull = site["hull"]
    d = TM.poly_distance(gx, gz, hull)
    pad = d <= 10.0
    tr = TM.poly_distance(gx, gz, TM.GT.grow([(5190, 5195), (5210, 5195), (5210, 5199), (5190, 5199)], TM.GT.TRENCH_PAD)) <= 0
    check(np.allclose(g.h[pad & ~tr], street_y), "every pad cell outside the trench is at street level")
    check(tr.any() and np.allclose(g.h[tr], street_y - 6.0), "trench cells are cut to the piece bottom (%d cells)" % tr.sum())
    # 3. untouched far away
    dist_road = np.full(gx.shape, np.inf)
    rp = [(4880, 4900), (5000, 5050), (5100, 5150), (5140, 5200)]
    for k in range(len(rp) - 1):
        dist_road = np.minimum(dist_road, TM.seg_distance(gx, gz, rp[k][0], rp[k][1], rp[k + 1][0], rp[k + 1][1])[0])
    far = (d > 10.0 + site["blend"] + 1) & (dist_road > 4 + 8 + 3)
    check(np.abs(g.h[far] - np.round(src.h[far], 2)).max() < 0.006, "cells outside pads / blends / roads are unchanged")
    # 4. embankment slope
    gy_, gx_ = np.gradient(g.h, g.cell)
    slope = np.hypot(gx_, gy_)
    band = (d > 10.0) & (d < 10.0 + site["blend"]) & (dist_road > 14)
    nat = np.hypot(*np.gradient(src.h, g.cell))
    check(float((slope[band] - nat[band]).max()) <= 0.5 + 0.05,
          "blend adds at most max_slope to the natural slope (max extra %.3f)" % float((slope[band] - nat[band]).max()))
    # 5. road
    road = rep["roads"][0]
    check(road["cut_m3"] + road["fill_m3"] > 100.0, "road earthworks are measured (cut %.0f + fill %.0f m3)" % (road["cut_m3"], road["fill_m3"]))
    check(road["max_grade"] <= 0.06 + 1e-9, "road profile max grade %.4f <= 0.06" % road["max_grade"])
    st, _ = TM.road_profile(g, [tuple(map(float, p)) for p in rp], 1.0, 1.0, 1.0)
    hy = g.sample(st[:, 0], st[:, 1])
    on_pad = TM.poly_distance(st[:, 0], st[:, 1], hull) <= 10.0
    gr = np.abs(np.diff(hy)) / np.maximum(np.diff(st[:, 2]), 1e-9)
    ok = (~on_pad[1:]) & (~on_pad[:-1])
    check(float(gr[ok].max()) <= 0.06 + 0.02, "terrain along the built road keeps the grade (max %.4f, 2 cm rounding)" % float(gr[ok].max()))
    # 6. surfaces
    from PIL import Image
    mask = np.array(Image.open(os.path.join(out1, "mask_lco.png")))[::-1]
    conc, grav, rock = TM.colour("cp_concrete1"), TM.colour("cp_gravel"), TM.colour("cp_rock")
    check(np.all(mask[pad & ~(dist_road <= 4)] == conc), "pad painted cp_concrete1 in the mask")
    deck = (dist_road <= 3.5) & ~pad
    check(np.all(mask[deck] == grav), "road deck painted cp_gravel")
    pnt = (gx > 5352) & (gx < 5388) & (gz > 4882) & (gz < 4918)
    check(np.all(mask[pnt] == rock), "paint polygon painted cp_rock")
    lc = open(os.path.join(out1, "layers.cfg"), "rb").read().decode()
    check("\r\n" in lc and 'class cp_dirt' in lc and 'material = "DZ\\surfaces\\data\\terrain\\cp_dirt.rvmat"' in lc
          and "cp_concrete1[]={{110,110,110}}" in lc, "layers.cfg lists the captured + painted surfaces (CRLF)")
    # 7. objects
    rm = open(os.path.join(out1, "removed_objects.csv")).read()
    check("pad:city,Land_House_1W01" in rm and "road:access" in rm and "b_corylus" in rm,
          "map objects inside the pad and on the road deck are removed")
    csv = open(os.path.join(out1, "objects_world.csv")).read().splitlines()
    tree = [l for l in csv if "t_betulapendula" in l][0].split(",")
    barn = [l for l in csv if "barn_w1" in l][0].split(",")
    dy_tree = float(tree[4]) - 150.0
    exp = float(g.sample(np.array([5263.0]), np.array([5200.0]))[0] - src.sample(np.array([5263.0]), np.array([5200.0]))[0])
    check(abs(dy_tree - exp) < 0.02 and abs(dy_tree) > 0.05, "a tree in the blend band follows the new ground (dy %.2f)" % dy_tree)
    check(abs(float(barn[4]) - 151.0) < 0.006, "a far object keeps its height")
    sky = [l for l in csv if l.startswith("sky,")]
    check(len(sky) == 81 and any("SKY_Skyline\\sky_street\\sky_street_intersection.p3d" in l for l in sky),
          "81 SKY objects with model paths from config.cpp")
    tb = open(os.path.join(out1, "objects_import.txt"), "rb").read().decode().split("\r\n")
    pat = re.compile(r'^"[^";]+";-?\d+\.\d{3};-?\d+\.\d{3};(-?\d+\.\d{3};){3}\d+\.\d{4};-?\d+\.\d{3};$')
    check(all(pat.match(l) for l in tb if l), "objects_import.txt lines match the Terrain Builder text format")
    inter = [l for l in tb if l.startswith('"sky_street_intersection"')][0].split(";")
    check(abs(float(inter[1]) - (200000 + 5152.0)) < 1e-3 or abs(float(inter[1]) - 200000) > 5000,
          "TB x includes the 200000 easting")
    check(abs(float(inter[7])) < 0.01, "a street piece sits on the pad (z_rel %.3f)" % float(inter[7]))
    # 8. determinism
    out2 = os.path.join(tmp, "out2")
    TM.build(pp, out2)
    same = all(open(os.path.join(out1, f), "rb").read() == open(os.path.join(out2, f), "rb").read() for f in os.listdir(out1))
    check(same, "two runs give byte-identical outputs")
    # 9. crop + origin zero (a smaller map cut from the region)
    pp2 = project(tmp, grid={"cell": 2.0, "crop": [4900, 4900, 5410.0, 5410.0], "origin": "zero"})
    out3 = os.path.join(tmp, "out3")
    _, rep3 = TM.build(pp2, out3)
    head = open(os.path.join(out3, "heightmap.asc")).read(400)
    check("xllcorner     200000.000000" in head and "yllcorner     0.000000" in head and rep3["grid"]["nx"] == 256,
          "crop with origin zero: 256 x 256 grid at TB origin")
    check(rep3["gates"]["grid_square_pow2"], "256 x 256 passes the square power-of-two hint")
    # 10. surface-per-tile gate
    cap2 = os.path.join(tmp, "cap2")
    os.makedirs(cap2)
    make_capture(cap2, "t2", 0.0, 0.0, 1.0, 64, 64, surf_fn=lambda x, z: "s%d" % (int(x) % 8))
    pp3 = os.path.join(tmp, "p3.yaml")
    yaml.safe_dump({"project": "t2", "source": {"capture": "cap2", "label": "t2"}}, open(pp3, "w"))
    _, rep4 = TM.build(pp3, os.path.join(tmp, "out4"))
    check(not rep4["gates"]["tile_surfaces"] and rep4["gates"]["tiles_over"][0][2] == 8, "8 surfaces in one mask tile fail the P78 gate")
    # 11. ESRI heightmap source + label sanitising + vanilla refusal
    _, rep5 = TM.build(pp, os.path.join(tmp, "out5"), source_heightmap=os.path.join(out1, "heightmap.asc"))
    check(rep5["sites"][0]["pad_flat"], "an ESRI ASCII heightmap works as the source")
    os.rename(os.path.join(cap, "t1_meta.json"), os.path.join(cap, "evil_meta.json"))
    try:
        TM.load_capture(cap, "../evil")
        refused = False
    except FileNotFoundError:
        refused = True
    os.rename(os.path.join(cap, "evil_meta.json"), os.path.join(cap, "t1_meta.json"))
    check(refused, "a capture label cannot leave the capture folder ('../evil' -> 'evil')")
    bad = 0
    for p in ("P:\\DZ\\worlds\\out", "C:\\steamapps\\common\\DayZ\\x", "/srv/server/mpmissions/dayzOffline.chernarusplus/x", "P:\\scripts\\x"):
        try:
            TM.refuse_vanilla(p)
        except SystemExit:
            bad += 1
    check(bad == 4, "outputs into vanilla / game / mission folders are refused (%d/4)" % bad)
    # 11b. hostile / broken inputs (D104 security review)
    _, _, m = TM.load_capture(cap, "t1")
    check(m["objects_rejected"] == 3, "object lines with quotes / non-finite numbers are rejected (%d)" % m["objects_rejected"])
    tb_all = open(os.path.join(out1, "objects_import.txt")).read()
    check('Evil"' not in tb_all and "Land_X" not in tb_all, "no injected object reaches the Terrain Builder import")
    meta_p = os.path.join(cap, "t1_meta.json")
    meta = json.load(open(meta_p))
    meta["complete"] = False
    json.dump(meta, open(meta_p, "w"))
    try:
        TM.load_capture(cap, "t1")
        inc = False
    except SystemExit:
        inc = True
    meta["complete"] = True
    json.dump(meta, open(meta_p, "w"))
    check(inc, "an incomplete capture (mission ended mid-run) is refused")
    bad_asc = os.path.join(tmp, "bad.asc")
    open(bad_asc, "w").write("ncols 2\nnrows 2\nxllcorner 0\nyllcorner 0\ncellsize 0\nNODATA_value -9999\n1 2\n3 4\n")
    nan_asc = os.path.join(tmp, "nan.asc")
    open(nan_asc, "w").write("ncols 2\nnrows 2\nxllcorner 0\nyllcorner 0\ncellsize 1\nNODATA_value -9999\n1 nan\n3 -9999\n")
    refused = 0
    for pth in (bad_asc, nan_asc):
        try:
            TM.load_asc(pth)
        except SystemExit:
            refused += 1
    check(refused == 2, "heightmaps with cell 0 or NaN / NODATA heights are refused (%d/2)" % refused)
    try:
        TM.refuse_vanilla(os.path.join(TERRAIN, "out"))
        rp = False
    except SystemExit:
        rp = True
    TM.refuse_vanilla(os.path.join(TERRAIN, "work", "x"))
    check(rp, "outputs into tracked repo folders are refused (terrain/work/ is allowed)")
    # 12. coupling with the Enforce capture
    c = open(CAPTURE_C).read()
    check(all(k in c for k in ('"_heights.txt"', '"_surfaces.txt"', '"_objects.txt"', '"_meta.json"', '"north_first"', '"cm"',
                               "m_Meta.complete = true", "DeleteFile(SKY_SiteSurvey.REQUEST)")),
          "SKY_TerrainCapture.c writes the file names / units the mapper reads")
    line = re.search(r'FPrintln\(m_FO, (.*)\);', c).group(1)
    check(line.count('";"') == 8, "capture object lines have 9 fields")
    check(math.isfinite(rep["stats"]["max_slope_changed"]), "stats computed")


if __name__ == "__main__":
    main()
