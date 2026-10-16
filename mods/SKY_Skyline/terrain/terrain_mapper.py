#!/usr/bin/env python3
"""Terrain mapper: a modified copy of an existing DayZ map region for a custom terrain (D104, MOD_DEVELOPMENT_GUIDE 4.3).

    python mods/SKY_Skyline/terrain/terrain_mapper.py --project mods/SKY_Skyline/terrain/projects/chernarus_skyline.yaml
        [--out <dir>] [--source-capture <dir>] [--source-heightmap <asc>]

Vanilla maps ship binarized: their .wrp cannot be edited, and this tool never touches one. It works on a COPY:
  1. Source. Either an in-game capture (SKY_TerrainCapture.c, request mode "capture": heights in cm, surface types and
     map objects of a rectangle, written to $profile:SKY_capture) or any ESRI ASCII heightmap (e.g. a Terrain Builder
     export of a terrain you own).
  2. Edits from the project YAML, all from the repo's own sources:
     - sites: a flat pad under a city layout (placement/out_*/sky_objects.json, world coordinates) or a polygon,
       at the layout's street level, blended into the original ground with a slope limit; trenches under the
       layout's underground pieces (underground_trenches.json, when the layout has one); map objects inside the pad
       are dropped from the import (listed in removed_objects.csv);
     - roads: polylines graded to a maximum grade, flat across their width, with blended shoulders;
     - paint: polygons painted with a surface.
  3. Outputs (default terrain/work/<project>/, git-ignored: map-derived data stays local):
       heightmap.asc        ESRI ASCII, first row = north, xllcorner 200000 (Terrain Builder convention, P79)
       mask_lco.png         surface mask, 1 px per cell, colours = layers.cfg Legend
       sat_lco.png          colour map (surface palette x hillshade)
       layers.cfg           every surface -> DZ\\surfaces\\data\\terrain\\<name>.rvmat (P77)
       objects_import.txt   Terrain Builder text import: "template";x;y;yaw;pitch;roll;scale;z_rel; (P79)
       objects_world.csv    the same objects in world coordinates with their source (map / sky)
       removed_objects.csv  map objects removed by a pad, a trench or a road
       preview.png          hillshade with cut (red) / fill (blue) and pad / road outlines
       report.md, mapper.json   transform, cut / fill volumes, slopes, grades, gate results
Deterministic. The Terrain Builder project, the .wrp build, CfgWorlds, the mission and the navmesh happen on Windows
(TESTING section 62). Never point --out at the game install, P:\\DZ, P:\\scripts or a mission folder: the tool refuses.
"""
import argparse
import hashlib
import io
import json
import math
import os
import re
import sys

import numpy as np
import yaml
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
MOD = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import gen_terrain as GT  # noqa: E402  (LAYERS colours / rvmats verified from the DayZ-Samples Test_Terrain)

EASTING = 200000.0                 # Terrain Builder projects add this to x (gen_terrain.py, DayZ-Samples; P79)
MAX_CELLS = 4096                   # per axis (capture and output grids; a whole map at 3.75 m, D104 perf M4)
MAX_FILE = 400 * 1024 * 1024       # bytes per capture / heightmap file (security L1)
NAME_OK = re.compile(r"^[A-Za-z0-9_\\/.\- ]*$")   # object type / model strings (security L3: no quotes, ; or newlines)
MAX_TILE_SURFACES = 6              # surfaces per mask tile Terrain Builder handles (P78)
MASK_TILE = 512                    # mask tile edge in cells for that gate (P78)
VANILLA_PARTS = ("\\dz\\", "/dz/", "\\scripts\\", "/scripts/", "mpmissions", "steamapps", "\\dayz\\", "/dayz/",
                 "dayzserver", "dayz tools")


# ----------------------------------------------------------------------------------------------- sources
class Grid:
    """Heights h[j, i] at world (x0 + i * cell, z0 + j * cell); row 0 = SOUTH. surf: index into names (or None)."""

    def __init__(self, x0, z0, cell, h, surf=None, names=None):
        self.x0, self.z0, self.cell = float(x0), float(z0), float(cell)
        self.h = h
        self.surf = surf
        self.names = list(names or [])
        self.zone = np.zeros(h.shape, np.int16)       # edited zones (pads, road decks): map objects there are removed
        self.zone_names = []
        self.pads = []                                 # (window, flat mask, level): re-asserted after the roads

    @property
    def nz(self):
        return self.h.shape[0]

    @property
    def nx(self):
        return self.h.shape[1]

    def coords(self, j0=0, j1=None, i0=0, i1=None):
        """World x, z of a window of the grid (the whole grid by default)."""
        j1 = self.nz if j1 is None else j1
        i1 = self.nx if i1 is None else i1
        xs = self.x0 + np.arange(i0, i1) * self.cell
        zs = self.z0 + np.arange(j0, j1) * self.cell
        return np.meshgrid(xs, zs)

    def sample(self, x, z):
        """Bilinear height at world points (arrays), clamped to the grid."""
        fi = np.clip((np.asarray(x, float) - self.x0) / self.cell, 0, self.nx - 1.000001)
        fj = np.clip((np.asarray(z, float) - self.z0) / self.cell, 0, self.nz - 1.000001)
        i, j = fi.astype(int), fj.astype(int)
        u, v = fi - i, fj - j
        h = self.h
        return (h[j, i] * (1 - u) * (1 - v) + h[j, i + 1] * u * (1 - v) + h[j + 1, i] * (1 - u) * v
                + h[j + 1, i + 1] * u * v)


def load_capture(cap_dir, label):
    label = re.sub(r"[^A-Za-z0-9_-]", "", label)[:32] or "capture"
    meta = json.load(open(os.path.join(cap_dir, label + "_meta.json")))
    if not meta.get("complete", False):
        raise SystemExit("capture %s: incomplete (no 'complete' flag: the mission ended mid-capture?)" % label)
    nx, nz = int(meta["nx"]), int(meta["nz"])
    _finite_cell(meta["x0"], meta["z0"], meta["cell"], label)
    if meta.get("heightUnit", "cm") != "cm" or meta.get("rowOrder", "north_first") != "north_first":
        raise SystemExit("capture %s: unsupported unit / row order" % label)
    if not (2 <= nx <= MAX_CELLS and 2 <= nz <= MAX_CELLS):
        raise SystemExit("capture %s: grid %d x %d out of bounds" % (label, nx, nz))
    h = _read_rows(os.path.join(cap_dir, label + "_heights.txt"), nx, nz, np.float64) / 100.0
    sp = os.path.join(cap_dir, label + "_surfaces.txt")
    names = [str(s) for s in meta.get("surfaces") or []]
    surf = None
    if os.path.exists(sp) and names:
        surf = _read_rows(sp, nx, nz, np.int32)
        if surf.min() < 0 or surf.max() >= len(names):
            raise SystemExit("capture %s: surface index outside the legend" % label)
    g = Grid(meta["x0"], meta["z0"], meta["cell"], h[::-1].copy(), None if surf is None else surf[::-1].copy(), names)
    objs = []
    rejected = 0
    op = os.path.join(cap_dir, label + "_objects.txt")
    if os.path.exists(op):
        _size_ok(op)
        for line in open(op, encoding="utf-8", errors="replace"):
            parts = line.rstrip("\r\n").split(";")
            if len(parts) != 9:
                continue
            if not (NAME_OK.match(parts[0]) and NAME_OK.match(parts[1])):
                rejected += 1
                continue
            try:
                vals = [float(v) for v in parts[2:]]
            except ValueError:
                rejected += 1
                continue
            if not all(math.isfinite(v) for v in vals):
                rejected += 1
                continue
            objs.append({"type": parts[0], "model": parts[1], "pos": vals[0:3], "ypr": vals[3:6], "scale": vals[6],
                         "src": "map"})
    meta["objects_rejected"] = rejected
    return g, objs, meta


def _size_ok(path):
    if os.path.getsize(path) > MAX_FILE:
        raise SystemExit("%s: over %d MB" % (path, MAX_FILE // (1024 * 1024)))


def _finite_cell(x0, z0, cell, what):
    vals = [float(x0), float(z0), float(cell)]
    if not all(math.isfinite(v) for v in vals) or not (0.0 < vals[2] <= 100.0):
        raise SystemExit("%s: origin / cell must be finite and 0 < cell <= 100 m" % what)


def _read_rows(path, nx, nz, dtype):
    _size_ok(path)
    out = np.empty((nz, nx), dtype)
    r = 0
    for line in open(path):
        vals = line.split()
        if not vals:
            continue
        if r >= nz:
            raise SystemExit("%s: more than %d rows" % (path, nz))
        if len(vals) != nx:
            raise SystemExit("%s: row %d has %d values, expected %d" % (path, r, len(vals), nx))
        try:
            out[r] = np.array(vals, dtype=np.int64)          # the capture writes integers only (cm / indices)
        except ValueError:
            raise SystemExit("%s: row %d has a non-integer value" % (path, r))
        r += 1
    if r != nz:
        raise SystemExit("%s: %d rows, expected %d" % (path, r, nz))
    return out


def load_asc(path):
    _size_ok(path)
    head = {}
    with open(path) as fh:
        for _ in range(6):
            k, v = fh.readline().split()
            head[k.lower()] = float(v)
        nx, nz = int(head["ncols"]), int(head["nrows"])
        if not (2 <= nx <= MAX_CELLS and 2 <= nz <= MAX_CELLS):
            raise SystemExit("%s: grid %d x %d out of bounds" % (path, nx, nz))
        _finite_cell(head.get("xllcorner", 0.0), head.get("yllcorner", 0.0), head["cellsize"], path)
        data = np.loadtxt(fh, dtype=np.float64, ndmin=2)
    if not np.isfinite(data).all() or (data == head.get("nodata_value", -9999)).any():
        raise SystemExit("%s: non-finite or NODATA heights" % path)
    if data.shape != (nz, nx):
        raise SystemExit("%s: grid %s does not match the header %d x %d" % (path, data.shape, nz, nx))
    x0 = head.get("xllcorner", 0.0)
    if x0 >= EASTING:
        x0 -= EASTING
    return Grid(x0, head.get("yllcorner", 0.0), head["cellsize"], data[::-1].copy()), [], {"source": path}


# ----------------------------------------------------------------------------------------------- geometry
def hull(pts):
    pts = sorted(set((round(p[0], 3), round(p[1], 3)) for p in pts))
    if len(pts) < 3:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(up) >= 2 and cross(up[-2], up[-1], p) <= 0:
            up.pop()
        up.append(p)
    return lo[:-1] + up[:-1]


def poly_distance(px, pz, poly):
    """0 inside the polygon (any simple polygon), else the distance to its boundary."""
    n = len(poly)
    inside = np.zeros(px.shape, bool)
    d = np.full(px.shape, np.inf)
    for k in range(n):
        ax, az = poly[k]
        bx, bz = poly[(k + 1) % n]
        # even-odd crossing test
        cond = (az > pz) != (bz > pz)
        with np.errstate(divide="ignore", invalid="ignore"):
            xc = ax + (pz - az) * (bx - ax) / (bz - az)
        inside ^= cond & (px < xc)
        d = np.minimum(d, seg_distance(px, pz, ax, az, bx, bz)[0])
    return np.where(inside, 0.0, d)


def seg_distance(px, pz, ax, az, bx, bz):
    dx, dz = bx - ax, bz - az
    ll = dx * dx + dz * dz
    t = np.zeros(px.shape) if ll == 0 else np.clip(((px - ax) * dx + (pz - az) * dz) / ll, 0.0, 1.0)
    return np.hypot(px - (ax + t * dx), pz - (az + t * dz)), t


def smooth(w):
    w = np.clip(w, 0.0, 1.0)
    return w * w * (3 - 2 * w)


def window(g, xmin, xmax, zmin, zmax):
    i0 = max(0, int(math.floor((xmin - g.x0) / g.cell)))
    i1 = min(g.nx, int(math.ceil((xmax - g.x0) / g.cell)) + 1)
    j0 = max(0, int(math.floor((zmin - g.z0) / g.cell)))
    j1 = min(g.nz, int(math.ceil((zmax - g.z0) / g.cell)) + 1)
    return j0, j1, i0, i1


# ----------------------------------------------------------------------------------------------- project
def resolve(base, p):
    return p if os.path.isabs(p) else os.path.normpath(os.path.join(base, p))


def refuse_vanilla(path):
    real = os.path.realpath(path)                      # security L4: junctions / symlinks resolved
    low = real.lower().replace("/", "\\") + "\\"
    raw = os.path.abspath(path).lower().replace("/", "\\") + "\\"
    for p in (low, raw):
        if re.match(r"^p:\\(dz|scripts)\\", p) or any(s.replace("/", "\\") in p for s in VANILLA_PARTS):
            raise SystemExit("refused: %s looks like a vanilla / game / mission folder (never edit vanilla)" % path)
    repo = os.path.realpath(os.path.join(MOD, "..", ".."))
    work = os.path.realpath(os.path.join(HERE, "work"))
    if os.path.commonpath([real, repo]) == repo and os.path.commonpath([real, work]) != work:
        raise SystemExit("refused: %s is a tracked repo folder; map-derived outputs go to terrain/work/ (P80)" % path)


def config_models():
    """class -> model path from the mod's own config.cpp files (SKY objects in the import)."""
    out = {}
    adir = os.path.join(MOD, "addons")
    for d in sorted(os.listdir(adir)) if os.path.isdir(adir) else []:
        cp = os.path.join(adir, d, "config.cpp")
        if not os.path.exists(cp):
            continue
        cur = None
        for line in open(cp, encoding="utf-8", errors="replace"):
            m = re.match(r"\s*class\s+(\w+)\s*(?::\s*\w+)?\s*$", line)
            if m:
                cur = m.group(1)
                continue
            m = re.match(r'\s*model\s*=\s*"([^"]+)"', line)
            if m and cur and cur not in out:
                out[cur] = m.group(1)
    return out


def resample(g, crop, cell):
    if crop:
        x0, z0, x1, z1 = [float(v) for v in crop]
    else:
        x0, z0 = g.x0, g.z0
        x1, z1 = g.x0 + (g.nx - 1) * g.cell, g.z0 + (g.nz - 1) * g.cell
    cell = float(cell or g.cell)
    nx = int(math.floor((x1 - x0) / cell + 1e-6)) + 1
    nz = int(math.floor((z1 - z0) / cell + 1e-6)) + 1
    if not (2 <= nx <= MAX_CELLS and 2 <= nz <= MAX_CELLS):
        raise SystemExit("output grid %d x %d out of bounds (max %d)" % (nx, nz, MAX_CELLS))
    xs = x0 + np.arange(nx) * cell
    zs = z0 + np.arange(nz) * cell
    gx, gz = np.meshgrid(xs, zs)
    h = g.sample(gx, gz)
    surf = None
    if g.surf is not None:
        ii = np.clip(np.rint((gx - g.x0) / g.cell).astype(int), 0, g.nx - 1)
        jj = np.clip(np.rint((gz - g.z0) / g.cell).astype(int), 0, g.nz - 1)
        surf = g.surf[jj, ii]
    return Grid(x0, z0, cell, h, surf, g.names)


def surface_id(g, name):
    if name not in g.names:
        g.names.append(name)
    return g.names.index(name)


def layout_objects(layout_out):
    objs = json.load(open(os.path.join(layout_out, "sky_objects.json")))["Objects"]
    tr = os.path.join(layout_out, "underground_trenches.json")
    trenches = json.load(open(tr))["pieces"] if os.path.exists(tr) else []
    return objs, trenches


def mark_zone(g, win, mask, label):
    j0, j1, i0, i1 = win
    if label not in g.zone_names:
        g.zone_names.append(label)
    k = g.zone_names.index(label) + 1
    sub = g.zone[j0:j1, i0:i1]
    sub[mask & (sub == 0)] = k


def apply_site(g, site, base, rep):
    name = str(site.get("name", "site"))
    margin = float(site.get("margin", 14.0))
    max_slope = float(site.get("max_slope", 0.5))
    min_blend = float(site.get("min_blend", 20.0))
    sky, trenches, shift = [], [], 0.0
    if site.get("layout_out"):
        lo = resolve(base, site["layout_out"])
        sky, trenches = layout_objects(lo)
        if not sky:
            raise SystemExit("site %s: %s has no objects" % (name, lo))
        poly = hull([(o["pos"][0], o["pos"][2]) for o in sky])
        streets = [o["pos"][1] for o in sky if "Street_" in o["name"]]
        layout_y = min(streets) if streets else min(o["pos"][1] for o in sky)
    else:
        poly = [tuple(map(float, p)) for p in site["polygon"]]
        layout_y = None
    if len(poly) < 3:
        raise SystemExit("site %s: footprint needs at least 3 points" % name)
    reach = margin + 400.0
    xs, zs = [p[0] for p in poly], [p[1] for p in poly]
    j0, j1, i0, i1 = window(g, min(xs) - reach, max(xs) + reach, min(zs) - reach, max(zs) + reach)
    sx, sz = g.coords(j0, j1, i0, i1)
    d = poly_distance(sx, sz, poly)
    orig = g.h[j0:j1, i0:i1].copy()
    pad = d <= margin
    lev = site.get("level", "layout")
    if isinstance(lev, (int, float)):
        level = float(lev)
    elif lev == "layout" and layout_y is not None:
        level = layout_y - float(site.get("embed", 0.0))
    else:
        level = float(np.median(orig[pad]))
    if layout_y is not None:
        shift = level + float(site.get("embed", 0.0)) - layout_y
    ring = (d > margin) & (d <= margin + 4 * min_blend)
    diff = float(np.abs(orig[ring] - level).max()) if ring.any() else 0.0
    blend = min(max(min_blend, 1.5 * diff / max(max_slope, 0.05)), 400.0)
    w = smooth((d - margin) / blend)
    new = level * (1 - w) + orig * w
    # trenches under the layout's underground pieces (same frame as sky_objects.json)
    tmask = np.zeros(sx.shape, bool)
    for p in trenches:
        tp = GT.grow([(c[0], c[1]) for c in p["corners"]], GT.TRENCH_PAD)
        inside = poly_distance(sx, sz, tp) <= 0.0
        new[inside] = np.minimum(new[inside], p["bottom"] + shift)
        tmask |= inside
    g.h[j0:j1, i0:i1] = new
    g.pads.append(((j0, j1, i0, i1), pad & ~tmask, level))
    mark_zone(g, (j0, j1, i0, i1), pad, "pad:" + name)
    if g.surf is not None or site.get("surface"):
        if g.surf is None:
            g.surf = np.full(g.h.shape, surface_id(g, "cp_grass"), np.int32)
        sid = surface_id(g, site.get("surface", "cp_concrete1"))
        sub = g.surf[j0:j1, i0:i1]
        sub[pad] = sid
        edge = site.get("edge_surface")
        if edge:
            sub[(~pad) & (w < 0.35)] = surface_id(g, edge)
    delta = new - orig
    area = g.cell * g.cell
    rep["sites"].append({
        "name": name, "level": round(level, 3), "object_shift": round(shift, 3), "margin": margin,
        "blend": round(blend, 1), "pad_cells": int(pad.sum()), "pad_area_m2": round(float(pad.sum()) * area, 1),
        "orig_relief_in_pad": round(float(orig[pad].max() - orig[pad].min()), 2) if pad.any() else 0.0,
        "cut_m3": round(float(-delta[delta < 0].sum()) * area, 1) + 0.0,
        "fill_m3": round(float(delta[delta > 0].sum()) * area, 1) + 0.0,
        "trenches": len(trenches), "objects": len(sky), "max_slope": max_slope,
        "hull": [[round(p[0], 2), round(p[1], 2)] for p in poly]})
    return [dict(o, shift=shift) for o in sky]


def road_profile(g, pts, step, max_grade, smooth_m):
    """Centreline stations (x, z, s) and a graded height profile."""
    st = []
    s0 = 0.0
    for k in range(len(pts) - 1):
        (ax, az), (bx, bz) = pts[k], pts[k + 1]
        ln = math.hypot(bx - ax, bz - az)
        n = max(1, int(math.ceil(ln / step)))
        for q in range(n):
            t = q / n
            st.append((ax + (bx - ax) * t, az + (bz - az) * t, s0 + ln * t))
        s0 += ln
    st.append((pts[-1][0], pts[-1][1], s0))
    st = np.array(st)
    y = g.sample(st[:, 0], st[:, 1])
    k = max(1, int(round(smooth_m / step / 2)))
    if len(y) > 2 * k + 1:
        pad = np.concatenate([np.full(k, y[0]), y, np.full(k, y[-1])])
        ker = np.ones(2 * k + 1) / (2 * k + 1)
        ys = np.convolve(pad, ker, mode="valid")
        ys[0], ys[-1] = y[0], y[-1]                 # the ends meet the ground (or a pad) exactly
        y = ys
    # grade limit: two passes so neither direction exceeds max_grade (the ends keep their height when they can)
    ds = np.diff(st[:, 2])
    for _ in range(2):
        for q in range(1, len(y)):
            y[q] = min(max(y[q], y[q - 1] - max_grade * ds[q - 1]), y[q - 1] + max_grade * ds[q - 1])
        for q in range(len(y) - 2, -1, -1):
            y[q] = min(max(y[q], y[q + 1] - max_grade * ds[q]), y[q + 1] + max_grade * ds[q])
    return st, y


def apply_road(g, road, rep):
    name = str(road.get("name", "road"))
    pts = [tuple(map(float, p)) for p in road["points"]]
    if len(pts) < 2:
        raise SystemExit("road %s: needs at least 2 points" % name)
    half = float(road.get("width", 8.0)) / 2
    shoulder = float(road.get("shoulder", 10.0))
    max_grade = float(road.get("max_grade", 0.08))
    st, y = road_profile(g, pts, max(g.cell / 2, 0.5), max_grade, float(road.get("smooth", 40.0)))
    reach = half + shoulder + g.cell
    j0, j1, i0, i1 = window(g, st[:, 0].min() - reach, st[:, 0].max() + reach, st[:, 1].min() - reach,
                            st[:, 1].max() + reach)
    sx, sz = g.coords(j0, j1, i0, i1)
    dmin = np.full(sx.shape, np.inf)
    hr = np.zeros(sx.shape)
    for q in range(len(st) - 1):
        ax, az, bx, bz = st[q, 0], st[q, 1], st[q + 1, 0], st[q + 1, 1]
        bj0, bj1, bi0, bi1 = window(g, min(ax, bx) - reach, max(ax, bx) + reach, min(az, bz) - reach, max(az, bz) + reach)
        bj0, bj1, bi0, bi1 = bj0 - j0, bj1 - j0, bi0 - i0, bi1 - i0
        d, t = seg_distance(sx[bj0:bj1, bi0:bi1], sz[bj0:bj1, bi0:bi1], ax, az, bx, bz)
        better = d < dmin[bj0:bj1, bi0:bi1]
        dmin[bj0:bj1, bi0:bi1][better] = d[better]
        hr[bj0:bj1, bi0:bi1][better] = (y[q] * (1 - t) + y[q + 1] * t)[better]
    orig = g.h[j0:j1, i0:i1].copy()
    w = smooth((dmin - half) / max(shoulder, 0.01))
    new = np.where(np.isfinite(dmin), hr * (1 - w) + orig * w, orig)
    deck = dmin <= half
    g.h[j0:j1, i0:i1] = new
    if road.get("surface"):
        if g.surf is None:
            g.surf = np.full(g.h.shape, surface_id(g, "cp_grass"), np.int32)
        g.surf[j0:j1, i0:i1][deck] = surface_id(g, road["surface"])
    mark_zone(g, (j0, j1, i0, i1), dmin <= half + 1.0, "road:" + name)
    grades = np.abs(np.diff(y)) / np.maximum(np.diff(st[:, 2]), 1e-9)
    area = g.cell * g.cell
    delta = new - orig
    rep["roads"].append({"name": name, "points": [[round(p[0], 2), round(p[1], 2)] for p in pts], "length_m": round(float(st[-1, 2]), 1), "width": 2 * half,
                         "max_grade": round(float(grades.max()), 4), "grade_limit": max_grade,
                         "cut_m3": round(float(-delta[delta < 0].sum()) * area, 1) + 0.0,
                         "fill_m3": round(float(delta[delta > 0].sum()) * area, 1) + 0.0})


def apply_paint(g, paint):
    if g.surf is None:
        g.surf = np.full(g.h.shape, surface_id(g, "cp_grass"), np.int32)
    poly = [tuple(map(float, p)) for p in paint["polygon"]]
    xs, zs = [p[0] for p in poly], [p[1] for p in poly]
    j0, j1, i0, i1 = window(g, min(xs), max(xs), min(zs), max(zs))
    sx, sz = g.coords(j0, j1, i0, i1)
    inside = poly_distance(sx, sz, poly) <= 0.0
    g.surf[j0:j1, i0:i1][inside] = surface_id(g, paint["surface"])


# ----------------------------------------------------------------------------------------------- outputs
def colour(name):
    if name in GT.LAYERS:
        return GT.LAYERS[name][1]
    d = hashlib.sha256(name.encode()).digest()
    return (40 + d[0] % 200, 40 + d[1] % 200, 40 + d[2] % 200)


def sat_colour(name):
    if name in GT.SAT:
        return GT.SAT[name]
    r, g, b = colour(name)
    return (int(r * 0.6), int(g * 0.6), int(b * 0.6))


def hillshade(h, cell):
    gy, gx = np.gradient(h, cell)
    nx, ny, nz = -gx, -gy, np.ones_like(h)
    ln = np.sqrt(nx * nx + ny * ny + nz * nz)
    light = np.array([-0.5, 0.5, 0.7])
    light = light / np.linalg.norm(light)
    return np.clip((nx * light[0] + ny * light[1] + nz * light[2]) / ln, 0, 1)


def png(arr):
    b = io.BytesIO()
    Image.fromarray(arr, "RGB").save(b, "PNG", optimize=False, compress_level=6)
    return b.getvalue()


def build(project_path, out=None, source_capture=None, source_heightmap=None):
    base = os.path.dirname(os.path.abspath(project_path))
    proj = yaml.safe_load(open(project_path))
    pname = re.sub(r"[^A-Za-z0-9_-]", "", str(proj.get("project", "terrain")))[:48] or "terrain"
    src = proj.get("source") or {}
    if source_capture:
        src = {"capture": source_capture, "label": src.get("label", "capture")}
    if source_heightmap:
        src = {"heightmap": source_heightmap}
    if src.get("capture"):
        g0, map_objs, meta = load_capture(resolve(base, src["capture"]), str(src.get("label", "capture")))
    elif src.get("heightmap"):
        g0, map_objs, meta = load_asc(resolve(base, src["heightmap"]))
    else:
        raise SystemExit("project %s: source.capture or source.heightmap is required" % project_path)
    grid = proj.get("grid") or {}
    g = resample(g0, grid.get("crop"), grid.get("cell"))
    orig = g.h.copy()
    rep = {"project": pname, "source": {k: str(v) for k, v in src.items()}, "sites": [], "roads": [], "gates": {}}
    sky = []
    for site in proj.get("sites") or []:
        sky += apply_site(g, site, base, rep)
    for road in proj.get("roads") or []:
        apply_road(g, road, rep)
    for (j0, j1, i0, i1), flat, level in g.pads:      # a road shoulder never tilts a pad
        g.h[j0:j1, i0:i1][flat] = level
    for paint in proj.get("paint") or []:
        apply_paint(g, paint)
    g.h = np.round(g.h, 2)
    for s, ((j0, j1, i0, i1), flat, level) in zip(rep["sites"], g.pads):
        s["pad_flat"] = bool(np.all(np.abs(g.h[j0:j1, i0:i1][flat] - round(level, 2)) < 1e-6))
    if g.surf is None:
        g.surf = np.full(g.h.shape, surface_id(g, "cp_grass"), np.int32)
    origin = grid.get("origin", "keep")
    ox, oz = (g.x0, g.z0) if origin == "zero" else (0.0, 0.0)

    # objects: map objects outside the edited zones re-seated on the new ground; SKY objects shifted to the pad
    models = config_models()
    keep, removed = [], []
    xe, ze = g.x0 + (g.nx - 1) * g.cell, g.z0 + (g.nz - 1) * g.cell
    map_objs = [o for o in map_objs if g.x0 <= o["pos"][0] <= xe and g.z0 <= o["pos"][2] <= ze]
    if map_objs:
        ox_, oz_ = np.array([o["pos"][0] for o in map_objs]), np.array([o["pos"][2] for o in map_objs])
        ii = np.clip(np.rint((ox_ - g.x0) / g.cell).astype(int), 0, g.nx - 1)
        jj = np.clip(np.rint((oz_ - g.z0) / g.cell).astype(int), 0, g.nz - 1)
        zk = g.zone[jj, ii]
        dys = g.sample(ox_, oz_) - Grid(g.x0, g.z0, g.cell, orig).sample(ox_, oz_)
        for o, k, dy in zip(map_objs, zk, dys):
            if k:
                o["reason"] = g.zone_names[k - 1]           # perf M6: annotate in place, no dict copies
                removed.append(o)
            else:
                o["pos"][1] += float(dy)
                o["reseat"] = float(dy)
                keep.append(o)
    cutters = 0
    for o in sky:
        if o["name"].startswith("ClutterCutter"):     # the pad's surface (no clutter) replaces the spawner's grass cutters
            cutters += 1
            continue
        model = models.get(o["name"], "")
        keep.append({"type": o["name"], "model": model, "pos": [o["pos"][0], o["pos"][1] + o["shift"], o["pos"][2]],
                     "ypr": list(o["ypr"]), "scale": o.get("scale", 1.0), "src": "sky", "reseat": 0.0})
    rep["clutter_cutters_dropped"] = cutters
    files = outputs(g, orig, keep, removed, rep, proj, ox, oz, pname)
    out = out or os.path.join(HERE, "work", pname)
    refuse_vanilla(out)
    os.makedirs(out, exist_ok=True)
    for name, data in files.items():
        with open(os.path.join(out, name), "wb") as fh:
            fh.write(data)
    return out, rep


def outputs(g, orig, objs, removed, rep, proj, ox, oz, pname):
    files = {}
    n_x, n_z = g.nx, g.nz
    buf = io.BytesIO()
    buf.write(b"ncols         %d\nnrows         %d\nxllcorner     %.6f\nyllcorner     %.6f\ncellsize      %.6f\n"
              b"NODATA_value  -9999\n" % (n_x, n_z, EASTING + g.x0 - ox, g.z0 - oz, g.cell))
    np.savetxt(buf, g.h[::-1], fmt="%.2f", delimiter=" ")        # perf M5: no per-value Python formatting
    files["heightmap.asc"] = buf.getvalue()
    names = g.names
    pal = np.array([colour(k) for k in names], np.uint8)
    files["mask_lco.png"] = png(pal[g.surf][::-1])
    shade = hillshade(g.h, g.cell)
    satp = np.array([sat_colour(k) for k in names], np.float64)
    sat = satp[g.surf] * (0.75 + 0.35 * shade[..., None])
    files["sat_lco.png"] = png(np.clip(sat, 0, 255).astype(np.uint8)[::-1])
    used = sorted(set(int(v) for v in np.unique(g.surf)))
    cfg = "// GENERATED by terrain/terrain_mapper.py (%s) - surface layers (format: DayZ-Samples Test_Terrain/source/layers.cfg)\n" % pname
    cfg += "// rvmat paths follow the sample's DZ\\surfaces\\data\\terrain\\<surface>.rvmat pattern: verify each on P: (P77)\n"
    cfg += "class Layers\n{\n" + "".join('\tclass %s\n\t{\n\t\tmaterial = "%s";\n\t};\n' % (
        _cls(names[k]), GT.LAYERS[names[k]][0] if names[k] in GT.LAYERS else "DZ\\surfaces\\data\\terrain\\%s.rvmat" % _cls(names[k]))
        for k in used) + "};\n\n"
    cfg += 'class Legend\n{\n\tpicture = "%s\\source\\mapLegend.png";\n\tclass Colors\n\t{\n' % pname
    cfg += "".join("\t\t%s[]={{%d,%d,%d}};\n" % ((_cls(names[k]),) + tuple(int(c) for c in colour(names[k]))) for k in used)
    cfg += "\t};\n};\n"
    files["layers.cfg"] = cfg.replace("\n", "\r\n").encode()
    # Terrain Builder text import (P79): template name = model file name, x/y in TB coordinates, z relative to the ground
    tb, csv = [], ["source,type,model,x,y,z,yaw,pitch,roll,scale"]
    no_model = 0
    ground = g.sample(np.array([o["pos"][0] for o in objs]), np.array([o["pos"][2] for o in objs])) if objs else []
    for o, gy0 in zip(objs, ground):
        x, y, z = o["pos"]
        tpl = os.path.splitext(os.path.basename(o["model"].replace("\\", "/")))[0] if o["model"] else ""
        if not tpl:
            no_model += 1
            tpl = o["type"]
        rel = y - float(gy0)
        tb.append('"%s";%.3f;%.3f;%.3f;%.3f;%.3f;%.4f;%.3f;' % (tpl, EASTING + x - ox, z - oz, o["ypr"][0], o["ypr"][1],
                                                               o["ypr"][2], o["scale"], rel))
        csv.append("%s,%s,%s,%.3f,%.3f,%.3f,%.2f,%.2f,%.2f,%.4f" % (o["src"], o["type"], o["model"], x - ox, y, z - oz,
                                                                    o["ypr"][0], o["ypr"][1], o["ypr"][2], o["scale"]))
    files["objects_import.txt"] = ("\r\n".join(tb) + "\r\n").encode()
    files["objects_world.csv"] = ("\n".join(csv) + "\n").encode()
    rm = ["reason,type,model,x,y,z"] + ["%s,%s,%s,%.3f,%.3f,%.3f" % (o["reason"], o["type"], o["model"], o["pos"][0] - ox,
                                                                       o["pos"][1], o["pos"][2] - oz) for o in removed]
    files["removed_objects.csv"] = ("\n".join(rm) + "\n").encode()
    # gates
    delta = g.h - orig
    gy, gxg = np.gradient(g.h, g.cell)
    slope = np.hypot(gxg, gy)
    changed = np.abs(delta) > 0.01
    tiles_over = []
    for tj in range(0, n_z, MASK_TILE):
        for ti in range(0, n_x, MASK_TILE):
            k = len(np.unique(g.surf[tj:tj + MASK_TILE, ti:ti + MASK_TILE]))
            if k > MAX_TILE_SURFACES:
                tiles_over.append([ti // MASK_TILE, tj // MASK_TILE, k])
    reseat = [abs(o.get("reseat", 0.0)) for o in objs if o["src"] == "map"]
    rep["grid"] = {"x0": g.x0, "z0": g.z0, "cell": g.cell, "nx": n_x, "nz": n_z, "origin": [ox, oz],
                   "size_m": [round((n_x - 1) * g.cell, 2), round((n_z - 1) * g.cell, 2)],
                   "pow2": bool(n_x == n_z and (n_x & (n_x - 1)) == 0)}
    rep["stats"] = {"changed_cells": int(changed.sum()), "changed_area_m2": round(float(changed.sum()) * g.cell ** 2, 1),
                    "max_cut_m": round(float(-delta.min()), 2), "max_fill_m": round(float(delta.max()), 2),
                    "max_slope_changed": round(float(slope[changed].max()), 3) if changed.any() else 0.0,
                    "h_min": float(g.h.min()), "h_max": float(g.h.max()), "surfaces": [names[k] for k in used],
                    "objects_map_kept": sum(1 for o in objs if o["src"] == "map"),
                    "objects_sky": sum(1 for o in objs if o["src"] == "sky"), "objects_removed": len(removed),
                    "objects_reseated_over_0_2m": sum(1 for v in reseat if v > 0.2), "objects_without_model": no_model,
                    "clutter_cutters_dropped": rep.pop("clutter_cutters_dropped", 0)}
    max_slope = max([s["max_slope"] for s in rep["sites"]] + [0.0])
    rep["gates"] = {
        "pads_flat": all(s["pad_flat"] for s in rep["sites"]),
        "road_grades": all(r["max_grade"] <= r["grade_limit"] + 1e-6 for r in rep["roads"]),
        "tile_surfaces": not tiles_over, "tiles_over": tiles_over[:20],
        "grid_square_pow2": rep["grid"]["pow2"],
        "embankment_slope_hint": max_slope,
    }
    files["preview.png"] = preview(g, delta, rep)
    files["mapper.json"] = (json.dumps(rep, indent=1) + "\n").encode()
    files["report.md"] = report(rep).encode()
    return files


def _cls(name):
    return re.sub(r"[^A-Za-z0-9_]", "_", name) or "surface"


def preview(g, delta, rep):
    shade = hillshade(g.h, g.cell)
    img = np.stack([shade * 200 + 40] * 3, -1)
    full = max(0.5, float(np.abs(delta).max()))          # colour scale: the largest change is full red / blue
    cut = np.clip(-delta / full, 0, 1)
    fill = np.clip(delta / full, 0, 1)
    img[..., 0] = img[..., 0] * (1 - fill * 0.7) + 255 * cut * 0.7
    img[..., 2] = img[..., 2] * (1 - cut * 0.7) + 255 * fill * 0.7
    img[..., 1] = img[..., 1] * (1 - 0.5 * np.maximum(cut, fill))
    im = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)[::-1], "RGB")
    dr = ImageDraw.Draw(im)

    def px(x, z):
        return ((x - g.x0) / g.cell, g.nz - 1 - (z - g.z0) / g.cell)
    for s in rep["sites"]:
        dr.polygon([px(*p) for p in s["hull"]], outline=(255, 230, 0))
    for r in rep["roads"]:
        dr.line([px(*p) for p in r["points"]], fill=(0, 200, 90))
    scale = max(1, int(math.ceil(1024 / max(g.nx, g.nz))))
    if scale > 1:
        im = im.resize((g.nx * scale, g.nz * scale), Image.NEAREST)
    b = io.BytesIO()
    im.save(b, "PNG", compress_level=6)
    return b.getvalue()


def report(rep):
    L = ["# Terrain mapper report: %s" % rep["project"], "",
         "Generated by `terrain/terrain_mapper.py` (D104). Map-derived data: keep it local (P80).", "",
         "## Grid", "", "| key | value |", "|---|---|"]
    L += ["| %s | %s |" % (k, v) for k, v in rep["grid"].items()]
    L += ["", "## Sites", "", "| site | level (m) | object shift (m) | pad m2 | relief in pad (m) | blend (m) | cut m3 | fill m3 | trenches | objects |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    L += ["| %(name)s | %(level)s | %(object_shift)s | %(pad_area_m2)s | %(orig_relief_in_pad)s | %(blend)s | %(cut_m3)s | %(fill_m3)s | %(trenches)s | %(objects)s |" % s
          for s in rep["sites"]]
    L += ["", "## Roads", "", "| road | length (m) | width (m) | max grade | limit | cut m3 | fill m3 |", "|---|---|---|---|---|---|---|"]
    L += ["| %(name)s | %(length_m)s | %(width)s | %(max_grade)s | %(grade_limit)s | %(cut_m3)s | %(fill_m3)s |" % r for r in rep["roads"]]
    L += ["", "## Stats", "", "| key | value |", "|---|---|"]
    L += ["| %s | %s |" % (k, v) for k, v in rep["stats"].items()]
    L += ["", "## Gates", "", "| gate | result |", "|---|---|"]
    L += ["| %s | %s |" % (k, v) for k, v in rep["gates"].items()]
    L += ["", "Next: Terrain Builder import on Windows (TESTING section 62, `terrain/README.md` section 'Terrain mapper').", ""]
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--project", required=True)
    ap.add_argument("--out", help="output folder (default terrain/work/<project>)")
    ap.add_argument("--source-capture", help="override source.capture (folder with <label>_meta.json)")
    ap.add_argument("--source-heightmap", help="override the source with an ESRI ASCII heightmap")
    a = ap.parse_args()
    out, rep = build(a.project, a.out, a.source_capture, a.source_heightmap)
    gates = rep["gates"]
    print("wrote %s: %d x %d cells of %.2f m, %d sites, %d roads, %d map objects removed; gates: pads_flat=%s road_grades=%s tile_surfaces=%s"
          % (out, rep["grid"]["nx"], rep["grid"]["nz"], rep["grid"]["cell"], len(rep["sites"]), len(rep["roads"]),
             rep["stats"]["objects_removed"], gates["pads_flat"], gates["road_grades"], gates["tile_surfaces"]))
    sys.exit(0 if gates["pads_flat"] and gates["road_grades"] else 1)


if __name__ == "__main__":
    main()
