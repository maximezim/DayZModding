#!/usr/bin/env python3
"""Custom-terrain sources for the SKY city (D63, MOD_DEVELOPMENT_GUIDE 4.3 Level 2).

    python mods/SKY_Skyline/terrain/gen_terrain.py [--layout-out placement/out_citylife] [--check]

Reads a layout run made with `site.target: terrain` (placement/sky_layout.py --out <dir>): sky_objects.json
(every object, site frame) and underground_trenches.json (sewer / metro footprints and trench bottoms).
Writes terrain/out/ (committed; PNG/ASC through Git LFS), in the formats of Bohemia's DayZ-Samples
Test_Terrain (source/gis_input/terrain.asc, mask_lco, sat_lco, source/layers.cfg):
  heightmap.asc   ESRI ASCII grid, SIZE x SIZE m at CELL m, heights in metres
  mask_lco.png    surface mask, 1 px per CELL m, colours = layers.cfg Legend
  sat_lco.png     colour (satellite) map, same grid
  layers.cfg      surface layers -> vanilla DZ\\surfaces rvmats (verified names from the sample)
  objects_terrain.csv  the layout objects moved into terrain coordinates (class, x, y, z, yaw) for import
  terrain.json    the transform (offset, plateau height) and statistics
Shape: rolling Chernarus-like hills (seeded value noise) around a flat city plateau at PLATEAU m; the
plateau blends out over BLEND m; trenches are cut to each underground piece's bottom inside its footprint
(+0.75 m, so the slope stays outside the piece walls); a dry river valley runs under every Bridge_Long.
Deterministic (numpy seed). Terrain Builder import / .wrp build happen on Windows (TESTING §28, P28).
"""
import argparse
import hashlib
import io
import json
import math
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
MOD = os.path.dirname(HERE)
OUT = os.path.join(HERE, "out")
SIZE = 1024.0                    # terrain edge (m)
CELL = 1.0                       # heightmap cell (m): trenches need metre resolution (P28)
PLATEAU = 120.0                  # street level of the city (m above sea)
BLEND = 90.0                     # plateau -> hills blend distance (m)
MARGIN = 30.0                    # flat apron round the city's object extent (m)
TRENCH_PAD = 0.75                # trench reaches this far past a piece footprint (m)
RIVER = {"depth": 9.0, "half_width": 26.0, "bank": 22.0}
# surface layers: name -> (vanilla rvmat from the Test_Terrain sample layers.cfg, legend colour)
LAYERS = {
    "cp_concrete1": ("DZ\\surfaces\\data\\terrain\\cp_concrete1.rvmat", (110, 110, 110)),
    "cp_gravel": ("DZ\\surfaces\\data\\terrain\\cp_gravel.rvmat", (127, 127, 127)),
    "cp_grass": ("DZ\\surfaces\\data\\terrain\\cp_grass.rvmat", (172, 211, 115)),
    "cp_grass_tall": ("DZ\\surfaces\\data\\terrain\\cp_grass_tall.rvmat", (110, 160, 60)),
    "cp_conifer_common1": ("DZ\\surfaces\\data\\terrain\\cp_conifer_common1.rvmat", (0, 255, 255)),
    "cp_rock": ("DZ\\surfaces\\data\\terrain\\cp_rock.rvmat", (200, 120, 60)),
}
SAT = {"cp_concrete1": (96, 94, 90), "cp_gravel": (120, 112, 98), "cp_grass": (88, 104, 58), "cp_grass_tall": (78, 92, 48),
       "cp_conifer_common1": (46, 62, 38), "cp_rock": (110, 104, 96)}


def value_noise(n, scale, rng):
    """Smooth value noise on an n x n grid (bilinear-upsampled random lattice, cosine eased)."""
    k = int(n / scale) + 2
    lat = rng.random((k, k))
    t = np.arange(n) / scale
    i = t.astype(int)
    f = t - i
    f = (1 - np.cos(f * math.pi)) / 2
    a = lat[np.ix_(i, i)]
    b = lat[np.ix_(i + 1, i)]
    c = lat[np.ix_(i, i + 1)]
    d = lat[np.ix_(i + 1, i + 1)]
    fy, fx = f[:, None], f[None, :]
    return (a * (1 - fy) * (1 - fx) + b * fy * (1 - fx) + c * (1 - fy) * fx + d * fy * fx)


def inside_poly(px, pz, poly):
    """Vectorised point-in-convex-polygon (corners in order, either winding)."""
    area = sum(poly[k][0] * poly[(k + 1) % len(poly)][1] - poly[(k + 1) % len(poly)][0] * poly[k][1] for k in range(len(poly)))
    sign = 1.0 if area > 0 else -1.0
    ok = np.ones(px.shape, bool)
    for k in range(len(poly)):
        x0, z0 = poly[k]
        x1, z1 = poly[(k + 1) % len(poly)]
        ok &= ((x1 - x0) * (pz - z0) - (z1 - z0) * (px - x0)) * sign >= -1e-9
    return ok


def grow(poly, pad):
    cx = sum(p[0] for p in poly) / len(poly)
    cz = sum(p[1] for p in poly) / len(poly)
    out = []
    for (x, z) in poly:
        dx, dz = x - cx, z - cz
        ln = math.hypot(dx, dz) or 1.0
        out.append((x + dx / ln * pad * math.sqrt(2), z + dz / ln * pad * math.sqrt(2)))
    return out


def build(layout_out):
    objs = json.load(open(os.path.join(layout_out, "sky_objects.json")))["Objects"]
    tr_path = os.path.join(layout_out, "underground_trenches.json")
    trenches = json.load(open(tr_path))["pieces"] if os.path.exists(tr_path) else []
    n = int(SIZE / CELL)
    xs = np.arange(n) * CELL
    gx, gz = np.meshgrid(xs, xs)                    # gz rows (north), gx columns (east)
    off = (SIZE / 2, SIZE / 2)                      # site centre -> terrain centre
    street_y = min(o["pos"][1] for o in objs if "Street_" in o["name"]) if any("Street_" in o["name"] for o in objs) else 0.0
    dy = PLATEAU - street_y
    px = [o["pos"][0] + off[0] for o in objs]
    pz = [o["pos"][2] + off[1] for o in objs]
    x0, x1, z0, z1 = min(px) - MARGIN, max(px) + MARGIN, min(pz) - MARGIN, max(pz) + MARGIN
    rng = np.random.default_rng(63)
    hills = 26.0 * value_noise(n, 180.0, rng) + 9.0 * value_noise(n, 55.0, rng) + 2.0 * value_noise(n, 14.0, rng)
    hills = PLATEAU - 14.0 + hills
    # distance outside the plateau rectangle -> blend weight
    ddx = np.maximum(np.maximum(x0 - gx, gx - x1), 0.0)
    ddz = np.maximum(np.maximum(z0 - gz, gz - z1), 0.0)
    dist = np.hypot(ddx, ddz)
    w = np.clip(dist / BLEND, 0.0, 1.0)
    w = w * w * (3 - 2 * w)
    h = PLATEAU * (1 - w) + hills * w
    mask = np.full((n, n), "cp_grass", dtype=object)
    forest = (value_noise(n, 70.0, rng) > 0.58) & (w > 0.6)
    mask[forest] = "cp_conifer_common1"
    mask[(w > 0.2) & (w <= 0.6)] = "cp_grass_tall"
    mask[w == 0.0] = "cp_concrete1"
    # dry river valleys under the bridges (perpendicular to the deck, the deck spans the valley)
    for o in objs:
        if o["name"] != "Land_SKY_Bridge_Long":
            continue
        bx, bz = o["pos"][0] + off[0], o["pos"][2] + off[1]
        yaw = math.radians(o["ypr"][0])
        ax, az = math.cos(yaw), -math.sin(yaw)      # deck axis (model X) in the site frame
        across = (gx - bx) * ax + (gz - bz) * az     # distance along the deck = across the river
        rd = np.abs(across)
        prof = np.clip(1.0 - (rd - RIVER["half_width"]) / RIVER["bank"], 0.0, 1.0)
        prof = np.where(rd <= RIVER["half_width"], 1.0, prof)
        h = h - RIVER["depth"] * prof * prof * (3 - 2 * prof)
        mask[rd <= RIVER["half_width"]] = "cp_gravel"
    # trenches under the underground pieces
    for p in trenches:
        poly = grow([(c[0] + off[0], c[1] + off[1]) for c in p["corners"]], TRENCH_PAD)
        bx0, bx1 = int(max(0, min(q[0] for q in poly) / CELL - 2)), int(min(n, max(q[0] for q in poly) / CELL + 3))
        bz0, bz1 = int(max(0, min(q[1] for q in poly) / CELL - 2)), int(min(n, max(q[1] for q in poly) / CELL + 3))
        sub = inside_poly(gx[bz0:bz1, bx0:bx1], gz[bz0:bz1, bx0:bx1], poly)
        hh = h[bz0:bz1, bx0:bx1]
        hh[sub] = np.minimum(hh[sub], p["bottom"] + dy)
    h = np.round(h, 2)
    stats = {"size_m": SIZE, "cell_m": CELL, "plateau_m": PLATEAU, "offset_xz": off, "offset_y": dy,
             "city_rect": [round(v, 2) for v in (x0, x1, z0, z1)], "trenches": len(trenches),
             "bridges": sum(1 for o in objs if o["name"] == "Land_SKY_Bridge_Long"),
             "h_min": float(h.min()), "h_max": float(h.max())}
    return h, mask, objs, off, dy, stats


def outputs(layout_out):
    h, mask, objs, off, dy, stats = build(layout_out)
    n = h.shape[0]
    files = {}
    buf = io.StringIO()                                         # ESRI ASCII, first row = north (top)
    buf.write("ncols         %d\nnrows         %d\nxllcorner     200000.000000\nyllcorner     0.000000\n"
              "cellsize      %.6f\nNODATA_value  -9999\n" % (n, n, CELL))
    for row in h[::-1]:
        buf.write(" ".join("%.2f" % v for v in row) + "\n")
    files["heightmap.asc"] = buf.getvalue().encode()
    names = list(LAYERS)
    idx = np.vectorize(names.index)(mask)
    pal_mask = np.array([LAYERS[k][1] for k in names], dtype=np.uint8)
    pal_sat = np.array([SAT[k] for k in names], dtype=np.int16)
    rng = np.random.default_rng(631)
    img = pal_mask[idx][::-1]
    files["mask_lco.png"] = png(img)
    sat = pal_sat[idx] + rng.integers(-8, 9, size=(n, n, 1))
    files["sat_lco.png"] = png(np.clip(sat, 0, 255).astype(np.uint8)[::-1])
    cfg = "// GENERATED by terrain/gen_terrain.py - surface layers (format: DayZ-Samples Test_Terrain/source/layers.cfg)\n"
    cfg += "class Layers\n{\n" + "".join('\tclass %s\n\t{\n\t\tmaterial = "%s";\n\t};\n' % (k, v[0]) for k, v in LAYERS.items()) + "};\n\n"
    cfg += 'class Legend\n{\n\tpicture = "SKY_Skyline\\terrain\\source\\mapLegend.png";\n\tclass Colors\n\t{\n'
    cfg += "".join("\t\t%s[]={{%d,%d,%d}};\n" % ((k,) + v[1]) for k, v in LAYERS.items()) + "\t};\n};\n"
    files["layers.cfg"] = cfg.replace("\n", "\r\n").encode()
    csv = "class,x,y,z,yaw\n" + "".join("%s,%.3f,%.3f,%.3f,%.2f\n" % (o["name"], o["pos"][0] + off[0], o["pos"][1] + dy,
                                                                       o["pos"][2] + off[1], o["ypr"][0]) for o in objs)
    files["objects_terrain.csv"] = csv.encode()
    files["terrain.json"] = (json.dumps(stats, indent=1) + "\n").encode()
    return files


def png(arr):
    b = io.BytesIO()
    Image.fromarray(arr, "RGB").save(b, "PNG", optimize=False, compress_level=6)
    return b.getvalue()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--layout-out", default=os.path.join(MOD, "placement", "out_citylife"))
    ap.add_argument("--check", action="store_true", help="exit 1 if terrain/out is stale")
    a = ap.parse_args()
    files = outputs(a.layout_out)
    stale = []
    for name, data in files.items():
        path = os.path.join(OUT, name)
        old = open(path, "rb").read() if os.path.exists(path) else None
        if old is None or hashlib.sha256(old).digest() != hashlib.sha256(data).digest():
            stale.append(name)
            if not a.check:
                os.makedirs(OUT, exist_ok=True)
                with open(path, "wb") as fh:
                    fh.write(data)
    if a.check:
        print("stale: " + ", ".join(stale) if stale else "up to date")
        sys.exit(1 if stale else 0)
    print("wrote: " + (", ".join(stale) or "nothing (up to date)"))


if __name__ == "__main__":
    main()
