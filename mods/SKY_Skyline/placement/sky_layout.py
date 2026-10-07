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
  blocks    rectangles of grid cells between streets; towers placed block-locally (`at`);
            `fill: {zone, seed}` packs procedural city buildings along the block's street edges
            (placement/city_fill.py, skyspec.CITY_ZONES), `buildings:` places explicit ones
  site.target  spawner (default: objectSpawnersArr, ENTITY_CAP applies) | terrain (a whole city
            for a custom map: no cap, also writes city_objects.csv for the terrain import)
  towers    site-frame towers (legacy) - same keys as block towers
  tower     {id, type: TowerA, floors: [5 variants], roof: variant, lobby: A|B, yaw, furnish: {level: set}}
  decals    {tower, face: N|E|S|W, u, z, type}: flush on the facade at DECAL_OFFSET (D16, D19)
  jams      {density, seed}: abandoned-car blocking lines on straight tiles, one pedestrian gap (D61)
  viaducts  [{axis: ns|ew, index, from, to}]: elevated road over a street line, ramps at both ends (D61)
  tunnels   [{axis, index, from, to}]: cut-and-cover tunnel cells replace the street tiles (D61)
  bridges   [{at: [u, v], y, yaw}]: Bridge_Long (river crossing, deck height explicit) (D61)
  props     [{type, at: [u, v], yaw}]: free kit pieces (siren towers, dumpsters) (D61)
  streets.furniture {bins_every, hydrants_every, wet, seed}: bins / hydrants on the sidewalks (D61)
  blocks[].park  funfair | stadium | landfill: fixed arrangement instead of the fill (skyspec.PARKS, D61)
  skybridges {from: <tower id>, to: <tower id>}: Land_SKY_Skybridge between the two roofs (D60) -
            same yaw, same roof height, facing sides aligned, facade gap SKYBRIDGE["gap"]

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
import city_fill  # noqa: E402

TOWER_TYPES = {"TowerA": S.TOWER_A}
TILE = S.STREET["tile"]
FACE_NORMAL = {"N": (0.0, 1.0), "S": (0.0, -1.0), "E": (1.0, 0.0), "W": (-1.0, 0.0)}
FACE_YAW = {"S": 0.0, "W": 90.0, "N": 180.0, "E": 270.0}   # decal quad faces -Y (south) at yaw 0


def rot(u, v, yaw_deg):
    """Local (u east, v north) -> world offset for a yaw turning clockwise from north. All
    generator maths uses this one convention; P9 (`YAW_SIGN`) is applied only to the yaw value
    written to the JSON (spawner), so flipping it re-orients nothing but the engine angle."""
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
    # ypr[0] = YAW_SIGN * yaw (P9 engine yaw sense; positions never depend on it)
    return {"name": name, "pos": [round(pos[0], 4), round(pos[1], 4), round(pos[2], 4)],
            "ypr": [round((S.YAW_SIGN * yaw) % 360.0, 4), 0.0, 0.0], "scale": 1.0, "enableCEPersistency": 0, "customString": ""}


class Ctx:
    def __init__(self, strict):
        self.strict = strict
        self.errors, self.warnings, self.notes = [], [], []
        self.objects, self.drops = [], []
        self.counts = {}
        self.city_stats = {}
        self.veg_stats = {}
        self.fill_stats = {}
        self.max_drop = 0.0
        self.cutters = False

    def soft(self, msg):
        (self.errors if self.strict else self.warnings).append(msg)

    def add(self, kind, name, pos, yaw):
        self.objects.append(spawner(name, pos, yaw))
        self.counts[kind] = self.counts.get(kind, 0) + 1


VEGETATION = ("tree", "bush", "plant", "grass", "t_", "b_")   # survey object types/models allowed to overlap (hypothesis)


def foreign_objects(ctx, survey, what, test):
    """Survey objects inside an area: Land_* = error; vegetation = warning; anything else
    (rocks, walls, fences) = error in --strict (security batch-5 L1/M2)."""
    for o in survey.get("objects", []) if survey else []:
        if o["type"].startswith("Land_SKY_"):
            continue
        if test(o["pos"][0], o["pos"][2]):
            msg = "%s contains existing object %s at %s" % (what, o["type"], [round(v, 1) for v in o["pos"]])
            if o["type"].startswith("Land_"):
                ctx.errors.append(msg)
            elif o["type"].lower().startswith(VEGETATION):
                ctx.warnings.append(msg)
            else:
                ctx.soft(msg)


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
    closed = {tuple(c) for c in st.get("closed", [])}         # street cells built over (merged blocks, D58)
    tiles = []
    for i in range(i0, i1 + 1):
        for j in range(j0, j1 + 1):
            if (i, j) in closed:
                continue
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
def tower_spec(ctx, t):
    """Tower spec of the chosen core (D58): A = Tower A (5 floors), T15 / T23 / T33 = tall cores."""
    core = t.get("core", "A")
    if core not in S.CORE_VARIANTS:
        ctx.errors.append("tower %s: unknown core '%s' (%s)" % (t["id"], core, ", ".join(S.CORE_VARIANTS)))
        core = "A"
    spec = dict(TOWER_TYPES[t["type"]])
    spec["typical_floors"] = S.CORE_VARIANTS[core][1]["typical_floors"]
    return spec


def tower_modules(ctx, t):
    """[(class, z)] for a tower: lobby, typical floors (variants), roof, plus the roof class."""
    spec = tower_spec(ctx, t)
    n = spec["typical_floors"]
    floors = t.get("floors") or [spec["floor_variant"]] * n
    if len(floors) != n:
        ctx.errors.append("tower %s: %d floors given, core %s has exactly %d typical-floor stops"
                          % (t["id"], len(floors), t.get("core", "A"), n))
        floors = (list(floors) + [spec["floor_variant"]] * n)[:n]
    roof = t.get("roof", "helipad")
    mods = []
    for kind, _suffix, z in S.tower_levels(spec):
        if kind == "lobby":
            lobby = t.get("lobby", "A")                       # A = Tower A lobby, B = retail frontage (D60)
            if lobby not in S.LOBBY_VARIANTS:
                ctx.errors.append("tower %s: unknown lobby '%s' (%s)" % (t["id"], lobby, ", ".join(S.LOBBY_VARIANTS)))
                lobby = "A"
            mods.append((S.LOBBY_VARIANTS[lobby], z))
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
        for entry in props:
            name, px, py, pyaw = entry[:4]
            pz = entry[4] if len(entry) > 4 else 0.0          # mounting height (wall cabinets)
            dx, dz = rot(px, py, yaw)
            wx, wz = cx + dx, cz + dz
            poly = box_corners(wx, wz, S.PROP_BOX[name], yaw + pyaw)
            for other_name, other in polys:
                g = poly_gap(poly, other)
                if g < S.PROP_CAPS["aisle_min"] - 1e-6:
                    ctx.errors.append("tower %s level %d: %s and %s only %.2f m apart (< %.1f m aisle)"
                                      % (t["id"], level, name, other_name, g, S.PROP_CAPS["aisle_min"]))
            polys.append((name, poly))
            ctx.add("props", S.KIT[name]["cls"], (wx, base_y + z + pz, wz), yaw + pyaw)
        total += len(props)
    if total > S.PROP_CAPS["per_tower"]:
        ctx.errors.append("tower %s: %d props > PROP_CAPS per_tower %d" % (t["id"], total, S.PROP_CAPS["per_tower"]))
    return total


def place_tower(ctx, lay, t, cx, cz, yaw, survey, site):
    spec = tower_spec(ctx, t)
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
        foreign_objects(ctx, survey, "tower %s footprint" % t["id"], lambda x, z: inside(x, z, cx, cz, hw, hd, yaw))
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
    ctx.add("modules", S.CORE_VARIANTS.get(t.get("core", "A"), S.CORE_VARIANTS["A"])[0], (cx, base_y, cz), yaw)
    roof_cls, roof_z = mods[-1]
    for (u, v) in S.ROOF_DROP_POINTS[roof_cls]:
        dx, dz = rot(u, v, yaw)
        ctx.drops.append((cx + dx, base_y + roof_z + 0.05, cz + dz))
    nprops = furnish(ctx, t, mods, cx, cz, base_y, yaw)
    ctx.notes.append("tower %s: %d entities (%d modules + core, %d props): %s" % (
        t["id"], len(mods) + 1 + nprops, len(mods), nprops, " / ".join(c.replace("Land_SKY_", "") for c, _ in mods)))
    floors = t.get("floors") or [spec["floor_variant"]] * spec["typical_floors"]
    opaque = [(z, z + S.FLOOR_H - S.SLAB_T) for (_c, z), v in zip(mods[1:-1], floors) if v in S.DECAL_OPAQUE_FLOORS]
    return {"id": t["id"], "c": (cx, cz), "yaw": yaw, "hw": hw, "hd": hd, "base_y": base_y, "opaque": opaque,
            "top": base_y + mods[-1][1], "quad": footprint_corners(cx, cz, hw, hd, yaw)}


def add_cutters(ctx, site, cx, cz, hw, hd, yaw, y):
    """Clutter cutters tiled under a ground floor (spawner sites; D59, P12): no grass through slabs."""
    if not ctx.cutters:
        return
    size = S.CLUTTER_CUTTER["size"]
    nx, nz = max(1, int(math.ceil(2 * hw / size))), max(1, int(math.ceil(2 * hd / size)))
    for i in range(nx):
        for j in range(nz):
            u = -hw + (i + 0.5) * 2 * hw / nx
            v = -hd + (j + 0.5) * 2 * hd / nz
            dx, dz = rot(u, v, yaw)
            ctx.add("cutters", S.CLUTTER_CUTTER["class"], (cx + dx, y, cz + dz), yaw)


def place_city(ctx, lay, block_rects, world, site_yaw, survey, site, tile_quads, tower_quads):
    """Procedural city buildings of every block (`fill`, `buildings`) -> objects. Returns centres."""
    ctx.city_stats = {}
    ctx.fill_stats = {}
    centres, bquads = [], []
    clearance = float(site.get("clearance", 0.05))

    def ground(arch, u, v, hw, hd, yaw_rel):
        """Why the terrain cannot take this lot (None = fine) - the fill skips or downsizes it."""
        cx, cz = world(u, v)
        yaw = (site_yaw + yaw_rel) % 360.0
        quad = footprint_corners(cx, cz, hw, hd, yaw)
        for tid, tq in tower_quads:
            if sat_overlap(quad, tq):
                return "tower %s" % tid
        if survey is None:
            return None
        inside_fp = lambda x, z: inside(x, z, cx, cz, hw, hd, yaw)
        ys = survey_ground(survey, inside_fp)
        if not ys:
            return "no survey samples"
        for o in survey.get("objects", []):
            if not o["type"].startswith("Land_SKY_") and inside_fp(o["pos"][0], o["pos"][2]) and \
                    not o["type"].lower().startswith(VEGETATION):
                return "existing object %s" % o["type"]
        if arch in S.VEG_PIECES:
            return None
        base = max(ys) + clearance
        if base - min(ys) > S.CITY_SKIRT_DROP:
            return "ground falls %.2f m (skirt %.1f m)" % (base - min(ys), S.CITY_SKIRT_DROP)
        if ctx.street_y is not None and abs(base - (ctx.street_y + S.STREET["curb_h"])) > 0.5:
            return "floor %.2f m off the sidewalk" % (base - ctx.street_y - S.STREET["curb_h"])
        return None

    for b, rect in block_rects:
        if not (b.get("fill") or b.get("buildings")):
            continue
        for cls, arch, state, u, v, yaw_rel, hw, hd, ou, ov in city_fill.fill_block(S, b, rect, S.BLOCK_SETBACK,
                                                                                       ground, ctx.fill_stats):
            cx, cz = world(u, v)                                        # footprint centre (checks)
            mx, mz = world(ou, ov)                                      # model origin (spawn position)
            yaw = (site_yaw + yaw_rel) % 360.0
            quad = footprint_corners(cx, cz, hw, hd, yaw)
            if arch in S.VEG_PIECES:                                    # plants: on the ground, no slab checks
                ys = survey_ground(survey, lambda x, z: inside(x, z, cx, cz, hw, hd, yaw)) if survey is not None else []
                gy = min(ys) if ys else ((ctx.street_y + S.STREET["curb_h"]) if ctx.street_y is not None else
                                         float(site.get("base_y") or 0.0))
                ctx.add("vegetation", cls, (mx, gy, mz), yaw)
                ctx.veg_stats[arch] = ctx.veg_stats.get(arch, 0) + 1
                continue
            what = "%s in block %s" % (cls.replace("Land_SKY_City_", ""), b["id"])
            for cell, tq in tile_quads:
                if sat_overlap(quad, tq):
                    ctx.errors.append("%s overlaps street tile %s" % (what, cell))
            for tid, tq in tower_quads:
                if sat_overlap(quad, tq):
                    ctx.errors.append("%s overlaps tower %s" % (what, tid))
            for oid, oq in bquads:
                if sat_overlap(quad, oq):
                    ctx.errors.append("%s overlaps %s" % (what, oid))
            bquads.append((what, quad))
            base_y = None
            if survey is not None:
                ys = survey_ground(survey, lambda x, z: inside(x, z, cx, cz, hw, hd, yaw))
                if not ys:
                    ctx.errors.append("%s: survey has no samples inside its footprint" % what)
                else:
                    base_y = max(ys) + float(site.get("clearance", 0.05))
                    if base_y - min(ys) > S.CITY_SKIRT_DROP:
                        ctx.errors.append("%s: ground falls %.2f m below the slab (> skirt %.1f m)" % (
                            what, base_y - min(ys), S.CITY_SKIRT_DROP))
                foreign_objects(ctx, survey, what, lambda x, z: inside(x, z, cx, cz, hw, hd, yaw))
            if base_y is None:
                base_y = (ctx.street_y + S.STREET["curb_h"]) if ctx.street_y is not None else float(site.get("base_y") or 0.0)
            if ctx.street_y is not None and abs(base_y - (ctx.street_y + S.STREET["curb_h"])) > 0.5:
                ctx.soft("%s: ground floor %.2f m off the sidewalk - entrance step too high" % (
                    what, base_y - ctx.street_y - S.STREET["curb_h"]))
            ctx.add("buildings", cls, (mx, base_y, mz), yaw)
            if survey is not None:
                ys = survey_ground(survey, lambda x, z: inside(x, z, cx, cz, hw, hd, yaw))
                if ys:
                    ctx.max_drop = max(ctx.max_drop, base_y - min(ys))
            add_cutters(ctx, site, cx, cz, hw, hd, yaw, base_y - clearance)
            st = ctx.city_stats.setdefault(arch, [0, 0, 0])
            st[state if arch != "RubbleLot" else 2] += 1
            centres.append((cx, cz))
    return centres


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
        if not any(z0 - 1e-6 <= d["z"] and d["z"] + h <= z1 + 1e-6 for z0, z1 in t["opaque"]):
            ctx.errors.append("decal %s: z %.2f..%.2f is not on an opaque facade storey %s (glass / entrance behind "
                              "a decal = one-way concealment, D44)" % (d, d["z"], d["z"] + h, t["opaque"]))
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


def place_skybridges(ctx, lay, towers):
    """Skybridges (D60): the bridge model runs along its Y axis, origin = gap centre at roof slab
    top. Both towers need the same yaw and roof height and must face each other squarely with the
    designed facade gap; the lateral offset puts both landings in the lane test_kit.py proves free
    on every roof variant."""
    B = S.SKYBRIDGE
    by_id = {t["id"]: t for t in towers}
    for sb in lay.get("skybridges", []) or []:
        a, b = by_id.get(sb.get("from")), by_id.get(sb.get("to"))
        if a is None or b is None or a is b:
            ctx.errors.append("skybridge %s: needs two different existing towers (from / to)" % sb)
            continue
        name = "skybridge %s-%s" % (a["id"], b["id"])
        if abs((a["yaw"] - b["yaw"] + 180.0) % 360.0 - 180.0) > 1e-3:
            ctx.errors.append("%s: towers have different yaw (%.1f / %.1f)" % (name, a["yaw"], b["yaw"]))
            continue
        if abs(a["top"] - b["top"]) > 0.01:
            ctx.errors.append("%s: roofs at different heights (%.2f / %.2f) - same core and base height needed"
                              % (name, a["top"], b["top"]))
            continue
        du, dv = rot(b["c"][0] - a["c"][0], b["c"][1] - a["c"][1], -a["yaw"])      # B in A's frame
        if abs(du) > abs(dv):
            off, along, half, lat, yaw = abs(dv), abs(du), a["hw"] + b["hw"], (0.0, B["lateral"]["EW"]), a["yaw"] + 90.0
        else:
            off, along, half, lat, yaw = abs(du), abs(dv), a["hd"] + b["hd"], (B["lateral"]["NS"], 0.0), a["yaw"]
        if off > 0.05:
            ctx.errors.append("%s: towers are offset %.2f m sideways - their facing sides must line up" % (name, off))
            continue
        gap = along - half
        if abs(gap - B["gap"]) > B["gap_tol"]:
            ctx.errors.append("%s: facade gap %.2f m, the bridge spans %.1f +- %.1f m" % (name, gap, B["gap"], B["gap_tol"]))
            continue
        lx, lz = rot(lat[0], lat[1], a["yaw"])
        mx, mz = (a["c"][0] + b["c"][0]) / 2 + lx, (a["c"][1] + b["c"][1]) / 2 + lz
        ctx.add("skybridges", S.KIT["Skybridge"]["cls"], (mx, a["top"], mz), yaw % 360.0)
        ctx.notes.append("%s: span %.2f m at y %.2f" % (name, gap, a["top"]))


# ------------------------------------------------------------------ D61: roads, jams, parks, bridges
def line_cells(ctx, spec, what):
    """Cells of one street-line segment {axis: ns|ew, index, from, to} -> [(i, j)] in travel order."""
    axis, k, a, b = spec.get("axis"), spec.get("index"), spec.get("from"), spec.get("to")
    if axis not in ("ns", "ew") or k is None or a is None or b is None or a == b:
        ctx.errors.append("%s %s: needs axis ns|ew, index, from, to (from != to)" % (what, spec))
        return []
    step = 1 if b > a else -1
    return [((k, c) if axis == "ns" else (c, k)) for c in range(a, b + step, step)]


def _line_yaw(spec):
    """Model +Y along the travel direction of a line segment (site frame, before site yaw)."""
    base = 0.0 if spec["axis"] == "ns" else 90.0
    return base if spec["to"] > spec["from"] else base + 180.0


def place_viaducts(ctx, lay, kinds, world, site_yaw, street_y):
    """Elevated roads over a street line (idea 2): a 48 m ramp at each end (on straight tiles),
    12 m deck segments between. Returns the ramp cells (no jams there)."""
    R = S.VIADUCT["ramp_cells"]
    ramp_cells = set()
    for vd in lay.get("viaducts", []) or []:
        cells = line_cells(ctx, vd, "viaduct")
        if not cells:
            continue
        name = "viaduct %s %s %s..%s" % (vd["axis"], vd["index"], vd["from"], vd["to"])
        if len(cells) < 2 * R + 1:
            ctx.errors.append("%s: %d cells, needs at least %d (two %d-cell ramps + a deck)" % (name, len(cells), 2 * R + 1, R))
            continue
        missing = [c for c in cells if c not in kinds]
        if missing:
            ctx.errors.append("%s: cells %s are not street tiles" % (name, missing[:4]))
            continue
        ramps = cells[:R] + cells[-R:]
        bad = [c for c in ramps if kinds[c] != "Street_Straight"]
        if bad:
            ctx.errors.append("%s: ramp over a junction / crossing %s - ramps need straight tiles" % (name, bad[:4]))
            continue
        fwd = _line_yaw(vd)
        for grp, yaw in ((cells[:R], fwd), (cells[-R:], fwd + 180.0)):
            us = [cell_center(lay, *c) for c in grp]
            wx, wz = world(sum(u for u, _v in us) / R, sum(v for _u, v in us) / R)
            ctx.add("roads", S.KIT["Viaduct_Ramp"]["cls"], (wx, street_y, wz), (site_yaw + yaw) % 360.0)
            ramp_cells |= set(grp)
        for c in cells[R:-R]:
            wx, wz = world(*cell_center(lay, *c))
            ctx.add("roads", S.KIT["Viaduct_Straight"]["cls"], (wx, street_y, wz), (site_yaw + fwd) % 360.0)
        ctx.notes.append("%s: %d m deck at +%.0f m, ramps at both ends" % (name, 12 * (len(cells) - 2 * R), S.VIADUCT["height"]))
    return ramp_cells


def tunnel_cells(ctx, lay):
    out = []
    for t in lay.get("tunnels", []) or []:
        out += line_cells(ctx, t, "tunnel")
    return out


def place_tunnels(ctx, lay, world, site_yaw, street_y):
    """Cut-and-cover tunnels on a street line (idea 2): portal cells at both ends, straights between;
    the cells are taken off the street grid (the tunnel carries the road). Returns footprints (24 m
    wide with the berms) so blocks keep clear of them."""
    quads = []
    for t in lay.get("tunnels", []) or []:
        cells = line_cells(ctx, t, "tunnel")
        if len(cells) < 2:
            continue
        fwd = _line_yaw(t)
        for n, c in enumerate(cells):
            wx, wz = world(*cell_center(lay, *c))
            if n == 0:
                cls, yaw = "Tunnel_Portal", fwd                        # headwall (-Y) faces back out of the tunnel
            elif n == len(cells) - 1:
                cls, yaw = "Tunnel_Portal", fwd + 180.0
            else:
                cls, yaw = "Tunnel_Straight", fwd
            yaw = (site_yaw + yaw) % 360.0
            ctx.add("roads", S.KIT[cls]["cls"], (wx, street_y, wz), yaw)
            w, d = S.LANDMARK_SIZE[cls]
            quads.append(("tunnel cell %s" % (c,), footprint_corners(wx, wz, w / 2, d / 2, yaw)))
    return quads


def place_underground(ctx, lay, world, site_yaw, street_y, terrain):
    """Sewers and metro under street lines (D63, ROADMAP ideas 18, 22): cut-and-cover pieces whose roof is
    just under street level, so they need a trench in the terrain: custom terrain only (MOD_DEVELOPMENT_GUIDE
    4.3; terrain/gen_terrain.py trenches them). On a vanilla map the ParkingLot_Metro hatches stay sealed.
    underground: [{kind: sewer|metro, axis, index, from, to, access: [c...], stations: [c...],
                   collapse: 0..1, flooded_ends: bool, seed}]   (D67 variants; stations cycle S.METRO_STATIONS)
    - sewer: Sewer_Straight per cell, Sewer_Junction where two sewer runs cross, Sewer_End at open ends,
      at an `access` cell a Sewer_Access + a parallel Sewer_Stair on its +X side (under the sidewalk);
    - metro: Metro_Tunnel per cell, Metro_End at both ends, a 24 m Metro_Station over cells c and c+1.
    Returns obstacle quads (stations) and records ctx.underground (pieces with their
    world footprint and floor depth) for the darkness triggers and the terrain trenches."""
    runs = lay.get("underground") or []
    ctx.underground = []
    ctx.station_count = 0
    if not runs:
        return []
    if not terrain:
        ctx.errors.append("underground needs site.target: terrain (cut-and-cover under the street; a vanilla map "
                          "cannot be trenched - D63); the metro hatches stay sealed on vanilla maps")
        return []
    quads = []
    sewer_cells = {}
    for r in runs:
        if r.get("kind") == "sewer":
            for c in line_cells(ctx, r, "underground"):
                sewer_cells[c] = sewer_cells.get(c, 0) + 1
    done_junctions = set()
    UG = S.UNDERGROUND

    def put(cls, x, z, yaw, floor):
        yaw = yaw % 360.0
        ctx.add("underground", S.KIT[cls]["cls"], (x, street_y, z), yaw)
        w, d = S.LANDMARK_SIZE[cls]
        ctx.underground.append({"cls": cls, "pos": (x, street_y, z), "yaw": yaw, "size": (w, d),
                                "floor": street_y + floor, "roof": street_y + UG["roof_top"]})
        return footprint_corners(x, z, w / 2, d / 2, yaw)

    for r in runs:
        kind = r.get("kind")
        if kind not in ("sewer", "metro"):
            ctx.errors.append("underground %s: kind must be sewer or metro" % r)
            continue
        cells = line_cells(ctx, r, "underground")
        if len(cells) < 2:
            continue
        fwd = _line_yaw(r)
        along = [c[1] if r["axis"] == "ns" else c[0] for c in cells]
        stations = set(r.get("stations") or [])
        import random
        rr = random.Random(int(r.get("seed", 63)))
        collapse = float(r.get("collapse", 0.0))                          # D67: share of plain cells that collapsed
        flooded_ends = bool(r.get("flooded_ends", False))                 # D67: sewer dead ends hold water
        access = set(r.get("access") or [])
        skip = set()
        for n, c in enumerate(cells):
            if n in skip:
                continue
            wx, wz = world(*cell_center(lay, *c))
            yaw = site_yaw + fwd
            if kind == "metro":
                if along[n] in stations:
                    if n + 1 >= len(cells) - 1 or n == 0:
                        ctx.errors.append("underground metro %s: station at %s needs a tunnel cell before and after it" % (r.get("index"), along[n]))
                        continue
                    nx, nz = world(*cell_center(lay, *cells[n + 1]))
                    variant = S.METRO_STATIONS[ctx.station_count % len(S.METRO_STATIONS)]     # D67: each station its own name
                    ctx.station_count += 1
                    quads.append(("metro station %s" % (c,), put(variant, (wx + nx) / 2, (wz + nz) / 2, yaw, UG["metro_floor"])))
                    skip.add(n + 1)
                    continue
                if n == 0:
                    put("Metro_End", wx, wz, yaw + 180.0, UG["metro_floor"])
                elif n == len(cells) - 1:
                    put("Metro_End", wx, wz, yaw, UG["metro_floor"])
                else:
                    put("Metro_Collapsed" if rr.random() < collapse else "Metro_Tunnel", wx, wz, yaw, UG["metro_floor"])
                continue
            if sewer_cells.get(c, 0) > 1:                                       # crossing of two sewer runs
                if c not in done_junctions:
                    done_junctions.add(c)
                    put("Sewer_Junction", wx, wz, site_yaw, UG["sewer_floor"])
                continue
            if along[n] in access:
                put("Sewer_Access", wx, wz, yaw, UG["sewer_floor"])
                ox, oz = rot(1.0, 0.0, yaw)                                      # piece +X (the door side)
                off = S.LANDMARK_SIZE["Sewer_Access"][0] / 2 + S.LANDMARK_SIZE["Sewer_Stair"][0] / 2
                put("Sewer_Stair", wx + ox * off, wz + oz * off, yaw, UG["sewer_floor"])   # parallel, under the sidewalk
            elif n == 0:
                put("Sewer_FloodedEnd" if flooded_ends else "Sewer_End", wx, wz, yaw + 180.0, UG["sewer_floor"])
            elif n == len(cells) - 1:
                put("Sewer_FloodedEnd" if flooded_ends else "Sewer_End", wx, wz, yaw, UG["sewer_floor"])
            else:
                put("Sewer_Collapsed" if rr.random() < collapse else "Sewer_Straight", wx, wz, yaw, UG["sewer_floor"])
        bad = [a for a in access if a not in along] + [s_ for s_ in stations if s_ not in along]
        if bad:
            ctx.errors.append("underground %s %s: access/station positions %s are not on the run" % (kind, r.get("index"), bad))
    ug = ctx.underground
    for p in ug:
        if not all(v > 0 for v in p["size"]) or any(v != v for v in p["pos"]):
            ctx.errors.append("underground %s: bad size / position %s %s" % (p["cls"], p["size"], p["pos"]))
    sewers = sum(1 for p in ug if p["cls"].startswith("Sewer_") and p["cls"] != "Sewer_Stair")   # flooding pieces
    if sewers > 512:
        ctx.errors.append("underground: %d flooding sewer pieces > SKY_Under.MAX_PIECES 512" % sewers)
    polys = [footprint_corners(p["pos"][0], p["pos"][2], p["size"][0] / 2 - 0.05, p["size"][1] / 2 - 0.05, p["yaw"]) for p in ug]
    for i in range(len(ug)):
        for j in range(i + 1, len(ug)):
            if sat_overlap(polys[i], polys[j]):
                ctx.errors.append("underground %s at %s overlaps %s at %s" % (ug[i]["cls"], tuple(round(v, 1) for v in ug[i]["pos"]),
                                                                          ug[j]["cls"], tuple(round(v, 1) for v in ug[j]["pos"])))
    return quads


def underground_triggers(ctx):
    """cfgundergroundtriggers.json entries (vanilla schema: 3_game/undergroundarealoader.c JsonUndergroundTriggers):
    one dark box per piece interior, plus a breadcrumb fade down each stair (P27: EyeAccommodation values)."""
    out = []
    UG = S.UNDERGROUND
    for p in ctx.underground:
        x, y, z = p["pos"]
        w, d = p["size"]
        h = p["roof"] - p["floor"]
        trig = {"CustomSpawn": False, "Tag": "", "ParentNetworkId": [],
                "Position": [round(x, 3), round((p["floor"] + p["roof"]) / 2, 3), round(z, 3)],
                "Orientation": [round(p["yaw"], 2), 0.0, 0.0], "Size": [round(w, 2), round(h, 2), round(d, 2)],
                "EyeAccommodation": S.UNDERGROUND_LIGHT["eye_inside"], "InterpolationSpeed": S.UNDERGROUND_LIGHT["speed"],
                "UseLinePointFade": False, "AmbientSoundType": "", "AmbientSoundSet": "", "Breadcrumbs": []}
        if p["cls"] == "Sewer_Stair" or p["cls"].startswith("Metro_Station"):
            # fade along the stair: street end bright -> bottom dark (local +-Y ends)
            ends = [(0.0, -d / 2 + 1.0, y + UG["roof_top"]), (0.0, d / 2 - 2.0, p["floor"])] if p["cls"] == "Sewer_Stair" else \
                   [(0.0, d / 2 - 0.5, y + UG["roof_top"]), (0.0, 0.0, p["floor"] + 1.0)]   # station stair (all variants)
            crumbs = []
            for i, (u, v, yy) in enumerate(ends):
                dx, dz = rot(u, v, p["yaw"])
                crumbs.append({"Position": [round(x + dx, 3), round(yy + 1.5, 3), round(z + dz, 3)],
                               "EyeAccommodation": 1.0 if i == 0 else S.UNDERGROUND_LIGHT["eye_inside"],
                               "UseRaycast": False, "Radius": -1.0, "LightLerp": False})
            trig["Breadcrumbs"] = crumbs
            trig["UseLinePointFade"] = True
        out.append(trig)
    return out


def place_street_furniture(ctx, lay, tiles, world, site_yaw, street_y):
    """Bins and hydrants on the +X sidewalk of straight tiles (ideas 16, 17): a bin every
    `bins_every`, a hydrant every `hydrants_every` tile per street line; `wet` = share of hydrants
    that still give water (Hydrant_Wet), the rest are dry. Clear of the jam lines (|v| <= 4.9).
    D67, -X sidewalk: a bus shelter every `bus_stops_every` tile (centred, never on a street-lamp tile;
    the tile is reserved so no jam line crosses it), an advertising column every `ads_every` (v -5.2),
    a phone booth every `phones_every` (v +5.3). Returns the reserved (bus stop) cells."""
    fu = (lay.get("streets") or {}).get("furniture")
    if not fu:
        return set()
    import random
    rng = random.Random(int(fu.get("seed", 1)))
    be, he, wet = int(fu.get("bins_every", 0) or 0), int(fu.get("hydrants_every", 0) or 0), float(fu.get("wet", 0.35))
    bse, ade, phe = (int(fu.get(k, 0) or 0) for k in ("bus_stops_every", "ads_every", "phones_every"))   # D67, -X sidewalk
    le = int((lay.get("streets") or {}).get("lights_every", 0) or 0)            # street lamps stand at v 0 there too
    reserved = set()
    per_line = {}
    lu = S.STREET["carriageway"] / 2 + 0.6
    for kind, i, j, tyaw in tiles:
        if kind != "Street_Straight":
            continue
        line = ("ns", i) if tyaw == 0.0 else ("ew", j)
        k = per_line.get(line, 0)
        per_line[line] = k + 1
        u, v = cell_center(lay, i, j)
        wx, wz = world(u, v)
        yaw = site_yaw + tyaw
        y = street_y + S.STREET["curb_h"]
        if be and k % be == 0:
            dx, dz = rot(lu, 5.4, yaw)
            ctx.add("furniture", S.KIT["TrashBin"]["cls"], (wx + dx, y, wz + dz), yaw)
        if he and k % he == 1 % he:
            dx, dz = rot(lu, -5.4, yaw)
            cls = "Hydrant_Wet" if rng.random() < wet else "Hydrant_Dry"
            ctx.add("furniture", S.KIT[cls]["cls"], (wx + dx, y, wz + dz), yaw)
        su = -(lu + 0.4)                                                            # -X sidewalk centre line
        lamp_here = bool(le) and k % le == 0
        if bse and k % bse == 2 % bse and not lamp_here:                            # shelter faces the carriageway
            dx, dz = rot(su, 0.0, yaw)
            ctx.add("furniture", S.KIT["BusStop"]["cls"], (wx + dx, y, wz + dz), (yaw + 270.0) % 360.0)
            reserved.add((i, j))                                                    # no jam line across a bus stop
        elif ade and k % ade == 1 % ade:
            dx, dz = rot(su, -5.2, yaw)
            ctx.add("furniture", S.KIT["AdColumn"]["cls"], (wx + dx, y, wz + dz), yaw)
        if phe and k % phe == 3 % phe and not (bse and k % bse == 2 % bse and not lamp_here):
            dx, dz = rot(su, 5.3, yaw)
            ctx.add("furniture", S.KIT["PhoneBooth"]["cls"], (wx + dx, y, wz + dz), (yaw + 270.0) % 360.0)
    return reserved


def place_props(ctx, lay, world, site_yaw, survey):
    """Free props in the site frame: {type: <KIT name>, at: [u, v], yaw} (siren towers, dumpsters...)."""
    for pr in lay.get("props", []) or []:
        name = pr.get("type")
        if name not in S.KIT or S.KIT[name]["category"] in ("floor", "roof") or name.startswith("City_"):
            ctx.errors.append("prop %s: unknown or not a free prop" % pr)
            continue
        wx, wz = world(float(pr["at"][0]), float(pr["at"][1]))
        y = (ctx.street_y + S.STREET["curb_h"]) if ctx.street_y is not None else 0.0
        if survey is not None:
            ys = survey_ground(survey, lambda x, z: (x - wx) ** 2 + (z - wz) ** 2 < 4.0)
            if ys:
                y = min(ys)
        ctx.add("props", S.KIT[name]["cls"], (wx, y, wz), (site_yaw + float(pr.get("yaw", 0.0))) % 360.0)


def place_jams(ctx, lay, tiles, world, site_yaw, street_y, skip):
    """Abandoned-car jams (idea 2): on a share of the straight tiles a blocking line of wrecks and
    jersey barriers across the whole 12 m section with one JAM_GAP-wide gap (people pass, vehicles
    do not); vanilla wrecks (decor, P19 sizes) a few metres away. Each line is verified here."""
    jm = lay.get("jams")
    if not jm:
        return
    import random
    rng = random.Random(int(jm.get("seed", 1)))
    vrng = random.Random("%s:variant" % jm.get("seed", 1))                  # D74 (perf review M)
    density = float(jm.get("density", 0.4))
    half = TILE / 2
    gap_w = S.JAM_GAP
    lines = 0
    for kind, i, j, tyaw in tiles:
        if kind != "Street_Straight" or (i, j) in skip or rng.random() >= density:
            continue
        u, v = cell_center(lay, i, j)
        wx, wz = world(u, v)
        yaw = site_yaw + tyaw
        vb = rng.choice((-1.0, 1.0)) * (2.4 + 1.0 * rng.random())       # extent <= 4.9 m: clear of bins / hydrants
        g0 = rng.choice([-half, half - gap_w, rng.uniform(-3.0, 2.0)])
        segs = [(a, b) for (a, b) in ((-half, g0), (g0 + gap_w, half)) if b - a > 1e-6]
        cover = []
        row = 0
        for a, b in segs:
            x = a
            while x < b - 1e-6:
                left = b - x
                names = [n for n in S.JAM_BLOCKERS if S.JAM_BLOCKERS[n][0] <= max(left, 3.0) + 1e-6] or ["Barrier_Concrete"]
                piece = rng.choice(names)
                ln, dp = S.JAM_BLOCKERS[piece]
                start = min(x, b - ln)
                if start < a - 1e-6:                                   # segment shorter than the piece: centre it
                    start = a
                uc = start + ln / 2
                off = 0.45 if row % 2 else -0.45
                dx, dz = rot(uc, vb + off, yaw)
                py = (yaw + 90.0 + (180.0 if rng.random() < 0.5 else 0.0)) % 360.0
                opts = S.JAM_VARIANTS.get(piece, [piece])                    # D74: sedan intact / burnt / overturned,
                model = vrng.choice(opts) if len(opts) > 1 else piece          # own stream: the jam layout is unchanged
                ctx.add("jams", S.KIT[model]["cls"], (wx + dx, street_y, wz + dz), py)
                cover.append((start, start + ln))
                row += 1
                if start + ln >= b - 1e-6:                              # segment closed
                    break
                x = start + ln - 0.3
        # verify: union of covered intervals leaves exactly one opening of about gap_w
        cover.sort()
        free, cur = [], -half
        for c0, c1 in cover:
            if c0 > cur + 1e-6:
                free.append((cur, c0))
            cur = max(cur, c1)
        if cur < half - 1e-6:
            free.append((cur, half))
        widest = max((b - a for a, b in free), default=0.0)
        if widest > gap_w + 0.05 or widest < gap_w - 0.3:
            ctx.errors.append("jam on tile (%d, %d): widest opening %.2f m (expected %.1f m)" % (i, j, widest, gap_w))
        for _k in range(1 + int(rng.random() < 0.5)):                   # decor: vanilla wrecks away from the line
            lu = rng.choice((-2.0, 2.0)) + rng.uniform(-0.4, 0.4)
            lv = -math.copysign(1.0, vb) * (4.0 + 1.5 * rng.random())
            dx, dz = rot(lu, lv, yaw)
            ctx.add("jams", rng.choice(S.JAM_DECOR), (wx + dx, street_y, wz + dz),
                    (yaw + rng.uniform(-25.0, 25.0) + (180.0 if rng.random() < 0.5 else 0.0)) % 360.0)
        lines += 1
    ctx.notes.append("jams: %d blocking lines (%.0f%% of straight tiles asked), %.1f m pedestrian gap each" % (
        lines, 100 * density, gap_w))


def _piece_size(name):
    if name in S.LANDMARK_SIZE:
        return S.LANDMARK_SIZE[name] + (0.0,)
    if name.startswith("City_"):
        arch = name[len("City_"):].rsplit("_", 1)[0]
        return city_fill.footprint(S, arch)
    if name in S.CITY_PIECES:
        return S.CITY_PIECES[name][1], S.CITY_PIECES[name][2], 0.0
    return {"Dumpster": (1.9, 1.1, 0.0)}.get(name, (2.0, 2.0, 0.0))


def place_parks(ctx, lay, block_rects, world, site_yaw, survey, site, tile_quads, obstacles):
    """Whole-block arrangements (skyspec.PARKS: funfair, stadium, landfill) instead of the fill."""
    quads = []
    clearance = float(site.get("clearance", 0.05))
    for b, rect in block_rects:
        kind = b.get("park")
        if not kind:
            continue
        if kind not in S.PARKS:
            ctx.errors.append("block %s: unknown park '%s' (%s)" % (b["id"], kind, ", ".join(sorted(S.PARKS))))
            continue
        P = S.PARKS[kind]
        bw, bd = rect[1] - rect[0], rect[3] - rect[2]
        if bw < P["min"][0] - 1e-6 or bd < P["min"][1] - 1e-6:
            ctx.errors.append("block %s: %s needs %.0f x %.0f m, block is %.0f x %.0f" % (b["id"], kind, P["min"][0], P["min"][1], bw, bd))
            continue
        bu, bv = (rect[0] + rect[1]) / 2, (rect[2] + rect[3]) / 2
        mine = []
        for name, du, dv, yr in P["pieces"]:
            w, d, oy = _piece_size(name)
            cu, cv = bu + du, bv + dv
            loc = footprint_corners(cu, cv, w / 2, d / 2, yr)
            m = S.BLOCK_SETBACK
            what = "%s %s in block %s" % (kind, name, b["id"])
            if any(not (rect[0] + m - 1e-6 <= x <= rect[1] - m + 1e-6 and rect[2] + m - 1e-6 <= z <= rect[3] - m + 1e-6)
                   for x, z in loc):
                ctx.errors.append("%s leaves the block (setback %.1f m)" % (what, m))
            cx, cz = world(cu, cv)
            yaw = (site_yaw + yr) % 360.0
            quad = footprint_corners(cx, cz, w / 2, d / 2, yaw)
            small = name.startswith("Veg_") or name in ("TrashBin", "Dumpster")
            if not small:
                for oid, oq in tile_quads + obstacles + mine:
                    if sat_overlap(quad, oq):
                        ctx.errors.append("%s overlaps %s" % (what, oid))
                mine.append((what, quad))
            base_y = (ctx.street_y + S.STREET["curb_h"]) if ctx.street_y is not None else float(site.get("base_y") or 0.0)
            if survey is not None:
                ys = survey_ground(survey, lambda x, z: inside(x, z, cx, cz, w / 2, d / 2, yaw))
                if not ys:
                    ctx.errors.append("%s: survey has no samples inside its footprint" % what)
                else:
                    base_y = (min(ys) if small else max(ys) + clearance)
                    if not small and base_y - min(ys) > S.CITY_SKIRT_DROP:
                        ctx.errors.append("%s: ground falls %.2f m (skirt %.1f m)" % (what, base_y - min(ys), S.CITY_SKIRT_DROP))
                    if not small:
                        foreign_objects(ctx, survey, what, lambda x, z: inside(x, z, cx, cz, w / 2, d / 2, yaw))
            mdu, mdv = rot(0.0, oy, yaw)
            ctx.add("parks", S.KIT[name]["cls"], (cx + mdu, base_y, cz + mdv), yaw)
        quads += mine
        ctx.notes.append("block %s: park %s (%d pieces)" % (b["id"], kind, len(P["pieces"])))
    return quads


def place_bridges(ctx, lay, world, site_yaw, survey):
    """The bridge (idea 23): Bridge_Long at a site position, deck height y given explicitly (a river
    crossing is not on the street plane); with a survey both abutments must sit on the banks."""
    for br in lay.get("bridges", []) or []:
        at, y = br.get("at"), br.get("y")
        if at is None or y is None:
            ctx.errors.append("bridge %s: needs at: [u, v] and y (deck height)" % br)
            continue
        yaw = (site_yaw + float(br.get("yaw", 0.0))) % 360.0
        wx, wz = world(float(at[0]), float(at[1]))
        if survey is not None:
            for s_ in (-1, 1):
                ex, ez = rot(s_ * 46.0, 0.0, yaw)
                ys = survey_ground(survey, lambda x, z: inside(x, z, wx + ex, wz + ez, 2.0, 6.0, yaw))
                if not ys:
                    ctx.errors.append("bridge %s: no survey samples at the %s abutment" % (at, "west" if s_ < 0 else "east"))
                elif not (float(y) - 3.5 <= max(ys) <= float(y) + 0.3):
                    ctx.errors.append("bridge %s: bank %.2f m at the %s abutment, deck %.2f (bank must be 0.3 above to 3.5 below)"
                                      % (at, max(ys), "west" if s_ < 0 else "east", float(y)))
        ctx.add("bridges", S.KIT["Bridge_Long"]["cls"], (wx, float(y), wz), yaw)
        ctx.notes.append("bridge at %s, deck y %.2f: checkpoint + convoy loot mid-span" % (at, float(y)))


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
    # grass through ground floors: cutters on spawner sites by default; a custom terrain paints no-clutter ground
    ctx.cutters = bool(site.get("clutter_cutters", site.get("target", "spawner") != "terrain"))

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
    tcells = tunnel_cells(ctx, lay)                                         # D61: tunnels carry their own road
    if tcells and lay.get("streets"):
        lay["streets"] = dict(lay["streets"])
        lay["streets"]["closed"] = [list(c) for c in lay["streets"].get("closed", [])] + [list(c) for c in tcells]
    tiles = street_tiles(lay)
    street_cells = set()
    tile_quads = []
    st = lay.get("streets") or {}
    lights_every = int(st.get("lights_every", 0) or 0)
    # pass 1: geometry + survey samples per tile
    rows = []
    for kind, i, j, tyaw in tiles:
        if (i, j) in street_cells:
            ctx.errors.append("street tile (%d, %d) placed twice" % (i, j))
        street_cells.add((i, j))
        u, v = cell_center(lay, i, j)
        wx, wz = world(u, v)
        yaw = site_yaw + tyaw
        tile_quads.append(((i, j), footprint_corners(wx, wz, TILE / 2, TILE / 2, yaw)))
        ys = []
        if survey is not None:
            ys = survey_ground(survey, lambda x, z, wx=wx, wz=wz, yaw=yaw: inside(x, z, wx, wz, TILE / 2, TILE / 2, yaw))
            if not ys:
                ctx.errors.append("street tile (%d, %d) has no survey samples - extend the survey (halfW/halfD)" % (i, j))
            elif len(ys) < 9:
                ctx.warnings.append("street tile (%d, %d): only %d survey samples - survey the district in smaller pieces" % (i, j, len(ys)))
            foreign_objects(ctx, survey, "street tile (%d, %d)" % (i, j),
                            lambda x, z, wx=wx, wz=wz, yaw=yaw: inside(x, z, wx, wz, TILE / 2, TILE / 2, yaw))
        rows.append((kind, i, j, tyaw, wx, wz, yaw, ys))
    # one street plane for the whole district: no height steps at tile seams (QA batch-5 L3)
    street_y = st.get("base_y")
    all_ys = [y for r in rows for y in r[7]]
    if street_y is None and all_ys:
        street_y = max(all_ys) + float(site.get("clearance", 0.05))
    if street_y is None:
        street_y = float(site.get("base_y") or 0.0)
    if rows:
        ctx.notes.append("street plane y %.2f (one height for every tile)" % street_y)
    lim = S.STREET["slab_t"] + S.STREET["skirt"]
    # pass 2: checks, tiles, lights (every N-th straight tile counted per street line, QA L2)
    per_line = {}
    n_straight = 0
    for kind, i, j, tyaw, wx, wz, yaw, ys in rows:
        if ys:
            if street_y - min(ys) > lim:
                ctx.errors.append("street tile (%d, %d): ground falls %.2f m below the tile (> slab + skirt %.2f m)"
                                  % (i, j, street_y - min(ys), lim))
            if street_y < max(ys) - 1e-6:
                ctx.errors.append("street tile (%d, %d): ground %.2f pokes through the tile at %.2f" % (i, j, max(ys), street_y))
        ctx.add("tiles", S.KIT[kind]["cls"], (wx, street_y, wz), yaw)
        if kind == "Street_Straight":
            n_straight += 1
            line = ("ns", i) if tyaw == 0.0 else ("ew", j)
            k = per_line.get(line, 0)
            per_line[line] = k + 1
            if lights_every and k % lights_every == 0:
                # pole on the local -X sidewalk, 0.5 m inside the curb: the lamp arm (+X) hangs over
                # the carriageway (QA batch-5 M1)
                lu = -(S.STREET["carriageway"] / 2 + 0.5)
                dx, dz = rot(lu, 0.0, yaw)
                ctx.add("lights", S.KIT["StreetLight"]["cls"], (wx + dx, street_y + S.STREET["curb_h"], wz + dz), yaw)
    allowed = sum(math.ceil(S.LIGHT_CAP["per_tile"] * n - 1e-9) for n in per_line.values())   # per street, rounded up
    if n_straight and ctx.counts.get("lights", 0) > allowed:
        ctx.errors.append("%d street lights on %d straight tiles > LIGHT_CAP %.2f per tile (%d allowed per street line)"
                          % (ctx.counts["lights"], n_straight, S.LIGHT_CAP["per_tile"], allowed))
    ctx.street_y = street_y if rows else None

    # ---- towers (blocks + legacy site-frame towers)
    placed, quads = [], []
    jobs = []
    block_rects = []
    for b in lay.get("blocks", []) or []:
        bi0, bj0, bi1, bj1 = b["cells"]
        cells = {(i, j) for i in range(bi0, bi1 + 1) for j in range(bj0, bj1 + 1)}
        if cells & street_cells:
            ctx.errors.append("block %s overlaps street cells %s" % (b["id"], sorted(cells & street_cells)[:4]))
        u0, v0 = cell_center(lay, bi0, bj0)
        u1, v1 = cell_center(lay, bi1, bj1)
        rect = (u0 - TILE / 2, u1 + TILE / 2, v0 - TILE / 2, v1 + TILE / 2)
        bu, bv = (rect[0] + rect[1]) / 2, (rect[2] + rect[3]) / 2
        block_rects.append((b, rect))
        for t in b.get("towers", []) or []:
            jobs.append((t, bu + t.get("at", [0, 0])[0], bv + t.get("at", [0, 0])[1], rect, b["id"]))
    for t in lay.get("towers", []) or []:
        jobs.append((t, t["offset"][0], t["offset"][1], None, None))
    jobs_res = [any(v in ("apartments", "hotel") for v in (t.get("floors") or [])) for t, _u, _v, _r, _b in jobs]
    seen_ids = set()
    for t, u, v, rect, bid in jobs:
        if t["id"] in seen_ids:
            ctx.errors.append("duplicate tower id %s" % t["id"])
        seen_ids.add(t["id"])
        if float(t.get("yaw", 0.0)) % 90.0:
            ctx.errors.append("tower %s: yaw %s is not a multiple of 90 (block grid, crate clearance; security L4)" % (t["id"], t.get("yaw")))
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
        add_cutters(ctx, site, cx, cz, placed[-1]["hw"], placed[-1]["hd"], yaw,
                    placed[-1]["base_y"] - float(site.get("clearance", 0.05)))

    place_decals(ctx, lay, placed, site_yaw)
    place_skybridges(ctx, lay, placed)
    sy_ = ctx.street_y if ctx.street_y is not None else float(site.get("base_y") or 0.0)
    kinds = {(i, j): k for k, i, j, _y in tiles}
    ramp_cells = place_viaducts(ctx, lay, kinds, world, site_yaw, sy_)
    tq = place_tunnels(ctx, lay, world, site_yaw, sy_)
    tq += place_underground(ctx, lay, world, site_yaw, sy_, site.get("target", "spawner") == "terrain")   # D63
    for oid, oq in tq:
        for tid, tq2 in quads:
            if sat_overlap(oq, tq2):
                ctx.errors.append("%s: berm overlaps tower %s" % (oid, tid))
    bus_cells = place_street_furniture(ctx, lay, tiles, world, site_yaw, sy_)
    place_jams(ctx, lay, tiles, world, site_yaw, sy_, set(ramp_cells) | bus_cells)
    place_props(ctx, lay, world, site_yaw, survey)
    pq = place_parks(ctx, lay, block_rects, world, site_yaw, survey, site, tile_quads, quads + tq)
    place_bridges(ctx, lay, world, site_yaw, survey)
    city = place_city(ctx, lay, block_rects, world, site_yaw, survey, site, tile_quads, quads + tq + pq)
    if ctx.street_y is not None:
        for t in placed:
            step = t["base_y"] - (ctx.street_y + S.STREET["curb_h"])
            if abs(step) > 0.5:
                ctx.soft("tower %s: lobby floor %.2f m %s the sidewalk - entrance step too high (> 0.5 m)" % (
                    t["id"], abs(step), "above" if step > 0 else "below"))
            elif abs(step) > 0.3:
                ctx.warnings.append("tower %s: lobby floor %.2f m %s the sidewalk - entrance step" % (
                    t["id"], abs(step), "above" if step > 0 else "below"))
    # one InfectedCity zone per district (economy/README.md, perf batch-5 M4), vanilla
    # env/zombie_territories.xml zone format (verified in dayzOffline.chernarusplus)
    zone = None
    if city and not placed:
        r = min(150.0, max(50.0, max(math.hypot(c[0] - cx0, c[1] - cz0) for c in city) + 20.0))
        zone = '<zone name="InfectedCity" smin="0" smax="0" dmin="%d" dmax="%d" x="%.1f" z="%.1f" r="%.0f"/>' % (
            8, 16, cx0, cz0, r)
    if placed:
        res = sum(1 for t in jobs_res if t)
        dmax = min(15, 10 + res)
        r = min(100.0, max(50.0, max(math.hypot(t["c"][0] - cx0, t["c"][1] - cz0) for t in placed) + 20.0))   # vanilla zones r >= 50
        zone = '<zone name="InfectedCity" smin="0" smax="0" dmin="%d" dmax="%d" x="%.1f" z="%.1f" r="%.0f"/>' % (
            dmax // 2, dmax, cx0, cz0, r)

    def loot_of(objs):
        return sum(S.LOOT[o["name"]]["lootmax"] for o in objs if o["name"] in S.LOOT)
    loot = loot_of(ctx.objects)
    total = len(ctx.objects)
    terrain = site.get("target", "spawner") == "terrain"
    if terrain:
        ctx.notes.append("target terrain: ENTITY_CAP not applied (%d objects + %d loot would be %s the spawner cap %d); "
                         "deploy through a custom terrain, city_objects.csv" % (
                             total, loot, "over" if total + loot > S.ENTITY_CAP["per_district"] else "within",
                             S.ENTITY_CAP["per_district"]))
    elif total + loot > S.ENTITY_CAP["per_district"]:
        ctx.errors.append("%d entities + %d loot items > ENTITY_CAP per_district %d" % (total, loot, S.ENTITY_CAP["per_district"]))
    server = total + loot
    for other in [x for x in a.others.split(",") if x]:
        objs = json.load(open(other))["Objects"]
        server += len(objs) + loot_of(objs)
        ctx.notes.append("other district %s: %d entities + %d loot" % (other, len(objs), loot_of(objs)))
    if server > S.ENTITY_CAP["per_server"] and not terrain:
        ctx.errors.append("server total %d (entities + loot) > ENTITY_CAP per_server %d" % (server, S.ENTITY_CAP["per_server"]))
    # loot export (placement/README.md section 3): ExportProxyData must reach every module/prop
    radius = max([math.hypot(o["pos"][0] - cx0, o["pos"][2] - cz0) for o in ctx.objects] or [0.0]) + 5.0
    ctx.notes.append("loot export: survey request \"exportRadius\" >= %.0f m around site.center" % math.ceil(radius))

    os.makedirs(a.out, exist_ok=True)
    # a failed layout must not be deployable (security batch-5 L3): only the report + *.FAILED.json
    for name in ("sky_objects.json", "cfggameplay_snippet.json", "cfgeventspawns_snippet.xml"):
        if os.path.exists(os.path.join(a.out, name)):
            os.remove(os.path.join(a.out, name))
    objects_name = "sky_objects.FAILED.json" if ctx.errors else "sky_objects.json"
    with open(os.path.join(a.out, objects_name), "w") as fh:
        json.dump({"Objects": ctx.objects}, fh, indent=1)
    if not ctx.errors:
        with open(os.path.join(a.out, "cfggameplay_snippet.json"), "w") as fh:
            json.dump({"WorldsData": {"objectSpawnersArr": ["sky/sky_objects.json"]}}, fh, indent=1)
    with open(os.path.join(a.out, "cfgeventspawns_snippet.xml" if not ctx.errors else "cfgeventspawns_snippet.FAILED.xml"), "w") as fh:
        fh.write("<!-- MERGE into the mission cfgeventspawns.xml (inside <eventposdef>). y = roof height. -->\n")
        fh.write('<event name="StaticSKYRoofDrop">\n    <zone smin="0" smax="0" dmin="0" dmax="0" r="0" />\n')
        for (x, y, z) in ctx.drops:
            fh.write('    <pos x="%.3f" z="%.3f" a="0" y="%.3f" />\n' % (x, z, y))
        fh.write("</event>\n")
    if zone and not ctx.errors:
        with open(os.path.join(a.out, "zombie_territories_snippet.xml"), "w") as fh:
            fh.write("<!-- MERGE this <zone> into an existing <territory> of the mission's env/zombie_territories.xml.\n"
                     "     One zone per district; dmin/dmax from the floor mix (economy/README.md, tune after B6). -->\n")
            fh.write(zone + "\n")
    elif os.path.exists(os.path.join(a.out, "zombie_territories_snippet.xml")):
        os.remove(os.path.join(a.out, "zombie_territories_snippet.xml"))
    csv_path = os.path.join(a.out, "city_objects.csv")
    if terrain and not ctx.errors:
        with open(csv_path, "w") as fh:                       # neutral list for the terrain import (TB format: P11)
            fh.write("class,x,y,z,yaw\n")
            for o in ctx.objects:
                fh.write("%s,%.3f,%.3f,%.3f,%.2f\n" % (o["name"], o["pos"][0], o["pos"][1], o["pos"][2], o["ypr"][0]))
    elif os.path.exists(csv_path):
        os.remove(csv_path)
    ug_path = os.path.join(a.out, "cfgundergroundtriggers_snippet.json")
    tr_path = os.path.join(a.out, "underground_trenches.json")
    if getattr(ctx, "underground", None) and not ctx.errors:
        with open(ug_path, "w") as fh:                          # MERGE into <mission>/cfgundergroundtriggers.json "Triggers"
            json.dump({"Triggers": underground_triggers(ctx)}, fh, indent=1, allow_nan=False)   # invalid JSON drops every trigger
        with open(tr_path, "w") as fh:                          # terrain/gen_terrain.py trenches the heightmap under these
            json.dump({"pieces": [{"cls": p["cls"], "corners": [[round(c[0], 3), round(c[1], 3)] for c in footprint_corners(
                p["pos"][0], p["pos"][2], p["size"][0] / 2 + 0.5, p["size"][1] / 2 + 0.5, p["yaw"])],
                "bottom": round(p["floor"] - 1.5, 3)} for p in ctx.underground]}, fh, indent=1)
    else:
        for pth in (ug_path, tr_path):
            if os.path.exists(pth):
                os.remove(pth)
    status = "FAIL" if ctx.errors else ("PASS (with warnings)" if ctx.warnings else "PASS")
    with open(os.path.join(a.out, "placement_report.md"), "w") as fh:
        fh.write("# Placement report\n\nmap: %s  site: %s  status: **%s**\n\n" % (lay["map"], site["name"], status))
        for title, items in (("Errors", ctx.errors), ("Warnings", ctx.warnings), ("Notes", ctx.notes)):
            fh.write("## %s\n" % title + ("".join("- %s\n" % i for i in items) or "- none\n") + "\n")
        fh.write("## Entity counts (caps: entities + loot %d per district / %d per server, %d props per floor / %d per tower)\n"
                 % (S.ENTITY_CAP["per_district"], S.ENTITY_CAP["per_server"], S.PROP_CAPS["per_floor"], S.PROP_CAPS["per_tower"]))
        base = ("modules", "buildings", "vegetation", "cutters", "tiles", "lights", "props", "decals")
        for k in base + tuple(sorted(k for k in ctx.counts if k not in base)):      # D61: jams, roads, parks...
            fh.write("- %s: %d\n" % (k, ctx.counts.get(k, 0)))
        fh.write("- **total: %d** entities, %d loot items (max), server total %d\n\n" % (total, loot, server))
        if ctx.city_stats:
            fh.write("## City buildings by type (intact / damaged / ruined)\n")
            for arch in sorted(ctx.city_stats):
                st = ctx.city_stats[arch]
                fh.write("- %s: %d / %d / %d\n" % (arch, st[0], st[1], st[2]))
            tot = [sum(v[i] for v in ctx.city_stats.values()) for i in range(3)]
            fh.write("- **all: %d / %d / %d** (%d buildings)\n\n" % (tot[0], tot[1], tot[2], sum(tot)))
            fh.write("## Terrain fit and overgrowth (D59)\n")
            fs = ctx.fill_stats
            fh.write("- lots the terrain could not take (given to a smaller type or left as yard): %d\n"
                     % len(fs.get("terrain_skips", [])))
            for r in fs.get("terrain_skips", [])[:20]:
                fh.write("  - %s\n" % r)
            fh.write("- slivers avoided (gap < %.1f m between buildings): %d\n" % (city_fill.MIN_GAP, fs.get("slivers_avoided", 0)))
            fh.write("- deepest ground drop under a city building: %.2f m (skirt %.1f m)\n" % (ctx.max_drop, S.CITY_SKIRT_DROP))
            fh.write("- clutter cutters: %s\n" % ("%d (%s)" % (ctx.counts.get("cutters", 0), S.CLUTTER_CUTTER["class"]) if ctx.cutters
                                                else "off (custom terrain: paint a no-clutter surface under the city)"))
            fh.write("- vegetation: %s\n\n" % (", ".join("%s %d" % kv for kv in sorted(ctx.veg_stats.items())) or "none"))
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
