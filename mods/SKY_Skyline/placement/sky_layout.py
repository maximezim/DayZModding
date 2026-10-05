#!/usr/bin/env python3
"""layout.yaml -> objectSpawnersArr JSON (+ cfggameplay snippet + report).

    python mods/SKY_Skyline/placement/sky_layout.py [--layout layout.yaml] [--out out/] [--strict]

Output (in --out):
  sky_objects.json          {"Objects": [...]} in the exact schema of the vanilla
                            ObjectSpawnerJson / ITEM_SpawnerObject (3_game/objectspawner.c)
  cfggameplay_snippet.json  the WorldsData.objectSpawnersArr entry to merge
  cfgeventspawns_snippet.xml roof-drop event positions (every roof's drop points)
  placement_report.md       validation results + entity counts

Layout content (all optional except site):
  streets   12 m street grid: N-S columns `ns`, E-W rows `ew` over `extent`; Street_Intersection
            where they cross, Street_Crossing at `crossings`, Street_Straight elsewhere;
            optional street lights (LIGHT_CAP)
  blocks    rectangles of grid cells between streets; towers placed block-locally (`at`)
  towers    site-frame towers (legacy) - same keys as block towers
  tower     {id, type: TowerA, floors: [5 variants], roof: variant, yaw, furnish: {level: set}}
  decals    {tower, face: N|E|S|W, u, z, type}: flush on the facade at DECAL_OFFSET (D16, D19)

Validation
  * every tower module stacks at base_y + skyspec offsets (floor-to-floor 3.5 m); exactly
    TOWER_A typical_floors floors (the unchanged core's stops)
  * survey present: base_y >= max ground + clearance and (base_y - min ground)
    <= slab + max_ground_drop (foundation skirt hides the gap), no foreign
    objects inside any footprint; street tiles: ground within the tile skirt
  * overlaps: tower/tower, tower/street tile, tower/block edge (BLOCK_SETBACK), tile/tile
  * caps: PROP_CAPS (per floor, per tower, aisles), DECAL_CAPS (per tower), LIGHT_CAP, ENTITY_CAP
    (spawned entities + loot items = sum of the spawned classes' mapgroupproto lootmax, per
    district and - with --others - per server across several districts)
  * --strict (use for live servers) fails on placeholder sites, unset coordinates or missing survey
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
TILE = S.STREET["tile"]
FACE_NORMAL = {"N": (0.0, 1.0), "S": (0.0, -1.0), "E": (1.0, 0.0), "W": (-1.0, 0.0)}
FACE_YAW = {"S": 0.0, "W": 90.0, "N": 180.0, "E": 270.0}   # decal quad faces -Y (south) at yaw 0


def rot(u, v, yaw_deg):
    """Local (u east, v north) -> world offset for a DayZ yaw (clockwise from north)."""
    a = math.radians(yaw_deg)
    return (u * math.cos(a) + v * math.sin(a), -u * math.sin(a) + v * math.cos(a))


def footprint_corners(cx, cz, hw, hd, yaw):
    return [(cx + dx, cz + dz) for dx, dz in (rot(u, v, yaw) for u, v in ((-hw, -hd), (hw, -hd), (hw, hd), (-hw, hd)))]


def box_corners(cx, cz, box, yaw):
    """Corners of a model-space box (x0, x1, y0, y1) placed at (cx, cz) with yaw."""
    x0, x1, y0, y1 = box
    return [(cx + dx, cz + dz) for dx, dz in (rot(u, v, yaw) for u, v in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)))]


def inside(px, pz, cx, cz, hw, hd, yaw):
    # inverse rotation of the point into the footprint frame
    dx, dz = px - cx, pz - cz
    a = math.radians(yaw)
    u = dx * math.cos(a) - dz * math.sin(a)
    v = dx * math.sin(a) + dz * math.cos(a)
    return abs(u) <= hw and abs(v) <= hd


def sat_overlap(a, b, eps=1e-6):
    """Separating-axis test for two convex polygons [(x, z)]; touching edges do not overlap."""
    for poly in (a, b):
        for i in range(len(poly)):
            x1, z1 = poly[i]
            x2, z2 = poly[(i + 1) % len(poly)]
            nx, nz = z2 - z1, x1 - x2
            pa = [nx * x + nz * z for x, z in a]
            pb = [nx * x + nz * z for x, z in b]
            if max(pa) <= min(pb) + eps or max(pb) <= min(pa) + eps:
                return False
    return True


def poly_gap(a, b):
    """Minimum distance between two convex polygons (0 if they overlap)."""
    if sat_overlap(a, b):
        return 0.0

    def seg_pt(p, s0, s1):
        dx, dz = s1[0] - s0[0], s1[1] - s0[1]
        L = dx * dx + dz * dz
        t = 0.0 if L == 0 else max(0.0, min(1.0, ((p[0] - s0[0]) * dx + (p[1] - s0[1]) * dz) / L))
        return math.hypot(p[0] - s0[0] - t * dx, p[1] - s0[1] - t * dz)
    best = float("inf")
    for P, Q in ((a, b), (b, a)):
        for p in P:
            for i in range(len(Q)):
                best = min(best, seg_pt(p, Q[i], Q[(i + 1) % len(Q)]))
    return best


def spawner(name, pos, yaw):
    return {"name": name, "pos": [round(pos[0], 4), round(pos[1], 4), round(pos[2], 4)],
            "ypr": [round(yaw % 360.0, 4), 0.0, 0.0], "scale": 1.0, "enableCEPersistency": 0, "customString": ""}


class Ctx:
    def __init__(self, strict):
        self.strict = strict
        self.errors, self.warnings, self.notes = [], [], []
        self.objects, self.drops = [], []
        self.counts = {}

    def soft(self, msg):
        (self.errors if self.strict else self.warnings).append(msg)

    def add(self, kind, name, pos, yaw):
        self.objects.append(spawner(name, pos, yaw))
        self.counts[kind] = self.counts.get(kind, 0) + 1


def survey_ground(survey, poly_test):
    pts = survey["samples"]
    return [pts[i + 1] for i in range(0, len(pts), 3) if poly_test(pts[i], pts[i + 2])]


# ------------------------------------------------------------------ streets
def street_tiles(lay):
    """[(kind, i, j, yaw_local)] for the street grid (site-frame cells)."""
    st = lay.get("streets")
    if not st:
        return []
    i0, i1, j0, j1 = st["extent"]
    ns, ew = set(st.get("ns", [])), set(st.get("ew", []))
    cross = {tuple(c) for c in st.get("crossings", [])}
    tiles = []
    for i in range(i0, i1 + 1):
        for j in range(j0, j1 + 1):
            if i in ns and j in ew:
                tiles.append(("Street_Intersection", i, j, 0.0))
            elif i in ns:
                tiles.append(("Street_Crossing" if (i, j) in cross else "Street_Straight", i, j, 0.0))
            elif j in ew:
                tiles.append(("Street_Crossing" if (i, j) in cross else "Street_Straight", i, j, 90.0))
    return tiles


def cell_center(lay, i, j):
    o = lay["streets"].get("origin", [0.0, 0.0]) if lay.get("streets") else [0.0, 0.0]
    return o[0] + i * TILE, o[1] + j * TILE


# ------------------------------------------------------------------ towers
def tower_modules(ctx, t):
    """[(class, z)] for a tower: lobby, typical floors (variants), roof, plus the roof class."""
    spec = TOWER_TYPES[t["type"]]
    n = spec["typical_floors"]
    floors = t.get("floors") or [spec["floor_variant"]] * n
    if len(floors) != n:
        ctx.errors.append("tower %s: %d floors given, the unchanged core has exactly %d typical-floor stops"
                          % (t["id"], len(floors), n))
        floors = (list(floors) + [spec["floor_variant"]] * n)[:n]
    roof = t.get("roof", "helipad")
    mods = []
    for kind, _suffix, z in S.tower_levels(spec):
        if kind == "lobby":
            mods.append((S.CLASS_LOBBY, z))
        elif kind == "floor":
            v = floors[len(mods) - 1]
            if v not in S.FLOOR_VARIANTS:
                ctx.errors.append("tower %s: unknown floor variant '%s' (%s)" % (t["id"], v, ", ".join(S.FLOOR_VARIANTS)))
                v = spec["floor_variant"]
            mods.append((S.FLOOR_VARIANTS[v], z))
        else:
            if roof not in S.ROOF_VARIANTS:
                ctx.errors.append("tower %s: unknown roof variant '%s' (%s)" % (t["id"], roof, ", ".join(S.ROOF_VARIANTS)))
                roof = "helipad"
            mods.append((S.ROOF_VARIANTS[roof], z))
    return mods


def furnish(ctx, t, mods, cx, cz, base_y, yaw):
    """Spawn furnish sets per level; enforce PROP_CAPS and aisles."""
    total = 0
    for level, set_name in sorted((t.get("furnish") or {}).items(), key=lambda kv: int(kv[0])):
        level = int(level)
        if not 0 < level < len(mods) - 1:
            ctx.errors.append("tower %s: furnish level %d is not a typical floor (1..%d)" % (t["id"], level, len(mods) - 2))
            continue
        cls, z = mods[level]
        fs = S.FURNISH.get(set_name)
        if fs is None:
            ctx.errors.append("tower %s: unknown furnish set '%s'" % (t["id"], set_name))
            continue
        if cls not in fs["for"]:
            ctx.errors.append("tower %s level %d: set '%s' does not fit %s" % (t["id"], level, set_name, cls))
            continue
        props = fs["props"]
        if len(props) > S.PROP_CAPS["per_floor"]:
            ctx.errors.append("tower %s level %d: %d props > PROP_CAPS per_floor %d"
                              % (t["id"], level, len(props), S.PROP_CAPS["per_floor"]))
        polys = []
        for name, px, py, pyaw in props:
            dx, dz = rot(px, py, yaw)
            wx, wz = cx + dx, cz + dz
            poly = box_corners(wx, wz, S.PROP_BOX[name], yaw + pyaw)
            for other_name, other in polys:
                g = poly_gap(poly, other)
                if g < S.PROP_CAPS["aisle_min"] - 1e-6:
                    ctx.errors.append("tower %s level %d: %s and %s only %.2f m apart (< %.1f m aisle)"
                                      % (t["id"], level, name, other_name, g, S.PROP_CAPS["aisle_min"]))
            polys.append((name, poly))
            ctx.add("props", S.KIT[name]["cls"], (wx, base_y + z, wz), yaw + pyaw)
        total += len(props)
    if total > S.PROP_CAPS["per_tower"]:
        ctx.errors.append("tower %s: %d props > PROP_CAPS per_tower %d" % (t["id"], total, S.PROP_CAPS["per_tower"]))
    return total


def place_tower(ctx, lay, t, cx, cz, yaw, survey, site):
    spec = TOWER_TYPES[t["type"]]
    hw, hd = spec["footprint"][0] / 2, spec["footprint"][1] / 2
    base_y = site.get("base_y")
    if survey is not None:
        ys = survey_ground(survey, lambda x, z: inside(x, z, cx, cz, hw, hd, yaw))
        if not ys:
            ctx.errors.append("tower %s: survey has no samples inside its footprint (wrong site?)" % t["id"])
        else:
            gmin, gmax = min(ys), max(ys)
            auto = gmax + float(site.get("clearance", 0.05))
            if base_y is None:
                base_y = auto
            elif base_y < auto:
                ctx.errors.append("tower %s: base_y %.2f is below ground %.2f (+clearance)" % (t["id"], base_y, gmax))
            drop = base_y - S.SLAB_T - gmin
            ctx.notes.append("tower %s ground %.2f..%.2f (relief %.2f m), base_y %.2f, drop under slab %.2f m"
                             % (t["id"], gmin, gmax, gmax - gmin, base_y, drop))
            if drop > float(site.get("max_ground_drop", 2.2)):
                ctx.errors.append("tower %s: ground falls %.2f m below the slab (> skirt %.2f m) - pick a flatter site"
                                  % (t["id"], drop, site["max_ground_drop"]))
        for o in survey.get("objects", []):
            if o["type"].startswith("Land_SKY_"):
                continue
            if inside(o["pos"][0], o["pos"][2], cx, cz, hw, hd, yaw):
                msg = "tower %s footprint contains existing object %s at %s" % (t["id"], o["type"], [round(v, 1) for v in o["pos"]])
                (ctx.errors if o["type"].startswith("Land_") else ctx.warnings).append(msg)
    if base_y is None:
        base_y = 0.0
        ctx.soft("tower %s: no base height (survey or base_y) - Y set to 0.0" % t["id"])

    mods = tower_modules(ctx, t)
    prev = None
    for cls, z in mods:
        if prev is not None and not (abs(z - prev - S.FLOOR_H) < 1e-6 or (prev == 0.0 and abs(z - spec["lobby_h"]) < 1e-6)):
            ctx.errors.append("tower %s: stacking gap at z=%.2f" % (t["id"], z))
        prev = z
        ctx.add("modules", cls, (cx, base_y + z, cz), yaw)
    ctx.add("modules", S.CLASS_CORE, (cx, base_y, cz), yaw)
    roof_cls, roof_z = mods[-1]
    for (u, v) in S.ROOF_DROP_POINTS[roof_cls]:
        dx, dz = rot(u, v, yaw)
        ctx.drops.append((cx + dx, base_y + roof_z + 0.05, cz + dz))
    nprops = furnish(ctx, t, mods, cx, cz, base_y, yaw)
    ctx.notes.append("tower %s: %d entities (%d modules + core, %d props): %s" % (
        t["id"], len(mods) + 1 + nprops, len(mods), nprops, " / ".join(c.replace("Land_SKY_", "") for c, _ in mods)))
    return {"id": t["id"], "c": (cx, cz), "yaw": yaw, "hw": hw, "hd": hd, "base_y": base_y,
            "top": base_y + mods[-1][1], "quad": footprint_corners(cx, cz, hw, hd, yaw)}


def place_decals(ctx, lay, towers, site_yaw):
    by_id = {t["id"]: t for t in towers}
    per_tower = {}
    for d in lay.get("decals", []) or []:
        t = by_id.get(d.get("tower"))
        kind = d.get("type", "")
        base = next((k for k in S.DECAL_OFFSET if kind == k or kind.startswith(k + "_")), None)
        if t is None or base is None or d.get("face") not in FACE_NORMAL:
            ctx.errors.append("decal %s: needs an existing tower, a Decal_* type and face N/E/S/W" % d)
            continue
        cls = "Land_SKY_" + kind
        valid = {S.KIT[base]["cls"]} | set(S.KIT[base]["variants"])
        if cls not in valid:
            ctx.errors.append("decal %s: unknown class %s" % (d, cls))
            continue
        nu, nv = FACE_NORMAL[d["face"]]
        half_face = t["hw"] if nv else t["hd"]
        w, h = S.DECAL_SIZE[base]                     # quad origin = bottom centre
        if abs(d["u"]) > half_face - w / 2:
            ctx.errors.append("decal %s: u %.2f runs off the %s face (+-%.2f)" % (d, d["u"], d["face"], half_face - w / 2))
            continue
        if not 0.0 <= d["z"] <= t["top"] - t["base_y"] - h:
            ctx.errors.append("decal %s: z %.2f..%.2f outside the facade height" % (d, d["z"], d["z"] + h))
            continue
        # flush by construction (D16): facade plane + per-type offset, quad facing out
        dist = (t["hd"] if nv else t["hw"]) + S.DECAL_OFFSET[base]
        lu, lv = (d["u"] * (1 if nv else 0) + nu * dist, d["u"] * (1 if nu else 0) + nv * dist)
        dx, dz = rot(lu, lv, t["yaw"])
        ctx.add("decals", cls, (t["c"][0] + dx, t["base_y"] + d["z"], t["c"][1] + dz), t["yaw"] + FACE_YAW[d["face"]])
        per_tower[t["id"]] = per_tower.get(t["id"], 0) + 1
    for tid, n in per_tower.items():
        if n > S.DECAL_CAPS["per_tower"]:
            ctx.errors.append("tower %s: %d decals > DECAL_CAPS per_tower %d" % (tid, n, S.DECAL_CAPS["per_tower"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--layout", default=os.path.join(HERE, "layout.yaml"))
    ap.add_argument("--out", default=os.path.join(HERE, "out"))
    ap.add_argument("--strict", action="store_true", help="fail on placeholder site / missing survey")
    ap.add_argument("--others", default="", help="comma-separated sky_objects.json of the server's other districts (ENTITY_CAP per_server)")
    a = ap.parse_args()
    lay = yaml.safe_load(open(a.layout))
    site = lay["site"]
    ctx = Ctx(a.strict)

    survey = None
    if site.get("survey"):
        sp = os.path.join(os.path.dirname(a.layout), site["survey"])
        survey = json.load(open(sp))
        ctx.notes.append("survey: %s (label %s, %d samples, %d objects)" % (
            site["survey"], survey.get("label"), len(survey.get("samples", [])) // 3, len(survey.get("objects", []))))
    if site.get("placeholder"):
        ctx.soft("site '%s' is a PLACEHOLDER - do not deploy" % site["name"])
    if survey is None:
        ctx.soft("no survey: ground height / overlaps NOT validated")
    if not site.get("center"):
        ctx.soft("site.center is not set (template) - positions are relative to (0, 0)")
    cx0, cz0 = site.get("center") or (0.0, 0.0)
    site_yaw = float(site.get("yaw") or 0.0)

    def world(u, v):
        dx, dz = rot(u, v, site_yaw)
        return cx0 + dx, cz0 + dz

    # ---- streets
    tiles = street_tiles(lay)
    street_cells = set()
    tile_quads = []
    st = lay.get("streets") or {}
    lights_every = int(st.get("lights_every", 0) or 0)
    n_straight = 0
    for kind, i, j, tyaw in tiles:
        if (i, j) in street_cells:
            ctx.errors.append("street tile (%d, %d) placed twice" % (i, j))
        street_cells.add((i, j))
        u, v = cell_center(lay, i, j)
        wx, wz = world(u, v)
        yaw = site_yaw + tyaw
        quad = footprint_corners(wx, wz, TILE / 2, TILE / 2, yaw)
        tile_quads.append(((i, j), quad))
        base_y = st.get("base_y")
        if survey is not None:
            ys = survey_ground(survey, lambda x, z: inside(x, z, wx, wz, TILE / 2, TILE / 2, yaw))
            if 0 < len(ys) < 9:
                ctx.warnings.append("street tile (%d, %d): only %d survey samples - survey the district in smaller pieces" % (i, j, len(ys)))
            if ys:
                auto = max(ys) + float(site.get("clearance", 0.05))
                if base_y is None:
                    base_y = auto
                drop = base_y - min(ys)
                lim = S.STREET["slab_t"] + S.STREET["skirt"]
                if drop > lim:
                    ctx.errors.append("street tile (%d, %d): ground falls %.2f m below the tile (> slab + skirt %.2f m)" % (i, j, drop, lim))
                if base_y < max(ys) - 1e-6:
                    ctx.errors.append("street tile (%d, %d): ground %.2f pokes through the tile at %.2f" % (i, j, max(ys), base_y))
        if base_y is None:
            base_y = float(site.get("base_y") or 0.0)
        ctx.add("tiles", S.KIT[kind]["cls"], (wx, base_y, wz), yaw)
        if kind == "Street_Straight":
            n_straight += 1
            if lights_every and n_straight % lights_every == 1 % lights_every:   # 1st, (1+N)th, ... straight tile
                # on the east (local +X) sidewalk, 0.5 m inside the curb
                lu = S.STREET["carriageway"] / 2 + 0.5
                dx, dz = rot(lu, 0.0, yaw)
                ctx.add("lights", S.KIT["StreetLight"]["cls"], (wx + dx, base_y + S.STREET["curb_h"], wz + dz), yaw)
    if n_straight and ctx.counts.get("lights", 0) > S.LIGHT_CAP["per_tile"] * n_straight:
        ctx.errors.append("%d street lights on %d straight tiles > LIGHT_CAP %.2f per tile"
                          % (ctx.counts["lights"], n_straight, S.LIGHT_CAP["per_tile"]))

    # ---- towers (blocks + legacy site-frame towers)
    placed, quads = [], []
    jobs = []
    for b in lay.get("blocks", []) or []:
        bi0, bj0, bi1, bj1 = b["cells"]
        cells = {(i, j) for i in range(bi0, bi1 + 1) for j in range(bj0, bj1 + 1)}
        if cells & street_cells:
            ctx.errors.append("block %s overlaps street cells %s" % (b["id"], sorted(cells & street_cells)[:4]))
        u0, v0 = cell_center(lay, bi0, bj0)
        u1, v1 = cell_center(lay, bi1, bj1)
        rect = (u0 - TILE / 2, u1 + TILE / 2, v0 - TILE / 2, v1 + TILE / 2)
        bu, bv = (rect[0] + rect[1]) / 2, (rect[2] + rect[3]) / 2
        for t in b.get("towers", []) or []:
            jobs.append((t, bu + t.get("at", [0, 0])[0], bv + t.get("at", [0, 0])[1], rect, b["id"]))
    for t in lay.get("towers", []) or []:
        jobs.append((t, t["offset"][0], t["offset"][1], None, None))
    for t, u, v, rect, bid in jobs:
        spec = TOWER_TYPES[t["type"]]
        hw, hd = spec["footprint"][0] / 2, spec["footprint"][1] / 2
        yaw_rel = float(t.get("yaw", 0.0))
        if rect is not None:
            loc = footprint_corners(u, v, hw, hd, yaw_rel)
            m = S.BLOCK_SETBACK
            if any(not (rect[0] + m - 1e-6 <= x <= rect[1] - m + 1e-6 and rect[2] + m - 1e-6 <= z <= rect[3] - m + 1e-6)
                   for x, z in loc):
                ctx.errors.append("tower %s: footprint leaves block %s (setback %.1f m)" % (t["id"], bid, m))
        cx, cz = world(u, v)
        yaw = (site_yaw + yaw_rel) % 360.0
        quad = footprint_corners(cx, cz, hw, hd, yaw)
        for other_id, other in quads:
            if sat_overlap(quad, other):
                ctx.errors.append("tower %s footprint overlaps tower %s" % (t["id"], other_id))
        for cell, tq in tile_quads:
            if sat_overlap(quad, tq):
                ctx.errors.append("tower %s footprint overlaps street tile %s" % (t["id"], cell))
        quads.append((t["id"], quad))
        placed.append(place_tower(ctx, lay, t, cx, cz, yaw, survey, site))

    place_decals(ctx, lay, placed, site_yaw)

    def loot_of(objs):
        return sum(S.LOOT[o["name"]]["lootmax"] for o in objs if o["name"] in S.LOOT)
    loot = loot_of(ctx.objects)
    total = len(ctx.objects)
    if total + loot > S.ENTITY_CAP["per_district"]:
        ctx.errors.append("%d entities + %d loot items > ENTITY_CAP per_district %d" % (total, loot, S.ENTITY_CAP["per_district"]))
    server = total + loot
    for other in [x for x in a.others.split(",") if x]:
        objs = json.load(open(other))["Objects"]
        server += len(objs) + loot_of(objs)
        ctx.notes.append("other district %s: %d entities + %d loot" % (other, len(objs), loot_of(objs)))
    if server > S.ENTITY_CAP["per_server"]:
        ctx.errors.append("server total %d (entities + loot) > ENTITY_CAP per_server %d" % (server, S.ENTITY_CAP["per_server"]))
    # loot export (placement/README.md section 3): ExportProxyData must reach every module/prop
    radius = max([math.hypot(o["pos"][0] - cx0, o["pos"][2] - cz0) for o in ctx.objects] or [0.0]) + 5.0
    ctx.notes.append("loot export: survey request \"exportRadius\" >= %.0f m around site.center" % math.ceil(radius))

    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "sky_objects.json"), "w") as fh:
        json.dump({"Objects": ctx.objects}, fh, indent=1)
    with open(os.path.join(a.out, "cfggameplay_snippet.json"), "w") as fh:
        json.dump({"WorldsData": {"objectSpawnersArr": ["sky/sky_objects.json"]}}, fh, indent=1)
    with open(os.path.join(a.out, "cfgeventspawns_snippet.xml"), "w") as fh:
        fh.write("<!-- MERGE into the mission cfgeventspawns.xml (inside <eventposdef>). y = roof height. -->\n")
        fh.write('<event name="StaticSKYRoofDrop">\n    <zone smin="0" smax="0" dmin="0" dmax="0" r="0" />\n')
        for (x, y, z) in ctx.drops:
            fh.write('    <pos x="%.3f" z="%.3f" a="0" y="%.3f" />\n' % (x, z, y))
        fh.write("</event>\n")
    status = "FAIL" if ctx.errors else ("PASS (with warnings)" if ctx.warnings else "PASS")
    with open(os.path.join(a.out, "placement_report.md"), "w") as fh:
        fh.write("# Placement report\n\nmap: %s  site: %s  status: **%s**\n\n" % (lay["map"], site["name"], status))
        for title, items in (("Errors", ctx.errors), ("Warnings", ctx.warnings), ("Notes", ctx.notes)):
            fh.write("## %s\n" % title + ("".join("- %s\n" % i for i in items) or "- none\n") + "\n")
        fh.write("## Entity counts (caps: entities + loot %d per district / %d per server, %d props per floor / %d per tower)\n"
                 % (S.ENTITY_CAP["per_district"], S.ENTITY_CAP["per_server"], S.PROP_CAPS["per_floor"], S.PROP_CAPS["per_tower"]))
        for k in ("modules", "tiles", "lights", "props", "decals"):
            fh.write("- %s: %d\n" % (k, ctx.counts.get(k, 0)))
        fh.write("- **total: %d** entities, %d loot items (max), server total %d\n\n" % (total, loot, server))
        fh.write("## Objects (%d)\n" % total)
        for o in ctx.objects:
            fh.write("- %s at %s yaw %s\n" % (o["name"], o["pos"], o["ypr"][0]))
    print("status:", status, "entities:", total)
    for e in ctx.errors:
        print("ERROR:", e)
    for w in ctx.warnings:
        print("WARN :", w)
    sys.exit(1 if ctx.errors else 0)


if __name__ == "__main__":
    main()
