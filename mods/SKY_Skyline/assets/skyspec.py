"""SKY_Skyline - single source of truth for Tower A (vertical slice).

Imported by: Blender generators (assets/blender/*.py), the config/model.cfg
generator (assets/gen_configs.py), the loot generator, and the layout tool
(placement/sky_layout.py). No third-party dependencies: it must import inside
Blender's bundled Python as well as system Python.

Frames
------
Blender authoring frame: X = east, Y = north, Z = up, metres.
P3D / game model space : x = X, y = Z (up), z = Y  (Arma Toolbox swaps Y/Z on export).
Every module's origin is the TOP of its floor slab at the footprint centre, and
every Geometry LOD carries autocenter=0, so stacking is pure +Y offsets.
"""
import json as _json
import os

TAG = "SKY"
MOD = "SKY_Skyline"

# --------------------------------------------------------------------- grid
GRID = 3.0            # structural bay / snap grid (m)
FLOOR_H = 3.5         # floor-to-floor height (m)
SLAB_T = 0.30         # slab thickness (m)
WALL_T = 0.25         # core / partition wall thickness
CURTAIN_T = 0.12      # facade glass + mullion depth
MULLION_W = 0.08

# --------------------------------------------------------------------- PBO prefixes
PREFIX_TEX = MOD + "\\sky_textures"
PREFIX_TOWER = MOD + "\\sky_towera"
PREFIX_ITEMS = MOD + "\\sky_items"


def tex(name):
    """Game path of a generated texture (PAA produced on Windows by ImageToPAA)."""
    return PREFIX_TEX + "\\data\\" + name + ".paa"


def rvmat(name):
    return PREFIX_TEX + "\\data\\" + name + ".rvmat"


# --------------------------------------------------------------------- materials
# Shared trim-sheet materials -> one rvmat each. UV "bands" are V ranges of the
# trim sheet (0 = top of image) used by the Blender UV helpers.
MATERIALS = {
    "concrete": {"rvmat": rvmat("sky_concrete"), "co": tex("sky_concrete_co"),
                 "bands": {"panel": (0.0, 0.5), "board": (0.5, 0.75), "reveal": (0.75, 1.0)}},
    "glass":    {"rvmat": rvmat("sky_glass"), "co": tex("sky_glass_ca")},
    # Opaque stand-in for distant LODs (Res2/Res3): no alpha blending far away.
    "glassfar": {"rvmat": rvmat("sky_glassfar"), "co": tex("sky_glassfar_co")},
    "metal":    {"rvmat": rvmat("sky_metal"), "co": tex("sky_metal_co"),
                 "bands": {"alu": (0.0, 0.5), "steel": (0.5, 0.75), "painted": (0.75, 1.0)}},
    "tile":     {"rvmat": rvmat("sky_tile"), "co": tex("sky_tile_co")},
    "carpet":   {"rvmat": rvmat("sky_carpet"), "co": tex("sky_carpet_co")},
    "wall":     {"rvmat": rvmat("sky_wallpaper"), "co": tex("sky_wallpaper_co")},
    "roofmark": {"rvmat": rvmat("sky_roofmark"), "co": tex("sky_roofmark_ca")},
}

# --------------------------------------------------------------------- UNVERIFIED ASSUMPTIONS
# Everything below is a guess until confirmed in DayZ (see PENDING_VERIFICATION.md).
# Flip the value here, regenerate (gen_configs.py / build_*.py), rebuild - never hard-code.
#
# Hinged doors (keycard door, locker doors, vending flap): model.cfg rotation
# angle1 = DOOR_SWING_SIGN * DOOR_OPEN_ANGLE (* per-door orient * scale for props).
# Convention (anchored on the Tower A lobby door, which +1 must open INTO the room):
# +1 assumes RV rotates a positive angle by the LEFT-hand rule about the memory axis
# (first point -> second point, Blender frame). Under it the lobby door opens into the
# room and every prop door opens OUTWARD (per-door orient below); test_kit.py checks
# both. If the engine turns out to use the right-hand rule, the lobby door opens outward
# and prop doors inward: set -1 and all of them become correct together.
DOOR_SWING_SIGN = 1
DOOR_OPEN_ANGLE = 1.4            # radians (~80 deg), same as Bohemia's Test_Building doors
# Elevator leaves: leaf "a" moves along -X * ELEVATOR_SLIDE_SIGN, leaf "b" along +X * sign
# (memory axis = second point minus first). +1 is intended to slide the leaves apart.
ELEVATOR_SLIDE_SIGN = 1
# Super-shader Stage7 environment map (vanilla path, not present in the samples).
ENV_MAP = "dz\\data\\data\\env_land_co.paa"
# Armor class name used for explosion damage in DamageSystem ArmorType.
ARMOR_EXPLOSION_CLASS = "FragGrenade"

# Rvmat emmisive[] RGB for lamps / lit windows (night look unverified).
EMISSIVE_LAMP = (1.0, 0.92, 0.75)
EMISSIVE_WINDOW = (0.55, 0.48, 0.35)

# Fire Geometry penetration materials. Only the three marked verified=True were
# seen in Bohemia's own Test_Building sample; the others follow the same naming
# and MUST be confirmed on P:\DZ\data\data\penetration (Check-SkyAssets.ps1 does it).
PENETRATION = {
    "concrete": ("dz\\data\\data\\penetration\\concrete.rvmat", False),
    "masonry":  ("dz\\data\\data\\penetration\\bricks.rvmat", True),
    "metal":    ("dz\\data\\data\\penetration\\metalplate.rvmat", True),
    "glass":    ("dz\\data\\data\\penetration\\glass.rvmat", False),
    "wood":     ("dz\\data\\data\\penetration\\wood_desk.rvmat", True),
}
# Roadway surface textures (footstep sounds / surface type) - all three verified
# in the Test_Building sample.
ROADWAY_INT = "dz\\surfaces\\data\\roadway\\concrete_int.tga"
ROADWAY_EXT = "dz\\surfaces\\data\\roadway\\concrete_ext.paa"
# UNVERIFIED (P6): no asphalt roadway surface confirmed yet - roads use the verified exterior concrete.
ROADWAY_ASPHALT = ROADWAY_EXT
# UNVERIFIED (P8): road-tile Geometry slab thickness. 0.3 m solid slabs may snag
# vehicle wheels at tile seams (perf batch-1 M4); if so set ~0.05 (top stays at z = 0).
ROAD_GEO_THICKNESS = 0.3
# UNVERIFIED (P9): DayZ object yaw (objectSpawnersArr "ypr"[0]) turns CLOCKWISE seen from above
# (north -> east). placement/sky_layout.py computes every position and orientation clockwise and
# writes ypr[0] = YAW_SIGN * yaw, so -1 flips only the engine angle (offsets stay consistent).
YAW_SIGN = 1

# --------------------------------------------------------------------- Tower A
TOWER_A = {
    "footprint": (24.0, 24.0),          # X x Y, 8 x 8 bays
    "lobby_h": 2 * FLOOR_H,             # double-height podium lobby
    "typical_floors": 5,
    "floor_variant": "office",
}

# Core (stairs + one elevator), centred on the tower, spans lobby -> roof penthouse.
CORE = {
    "x": (-3.0, 3.0),
    "y": (-4.5, 4.5),
    "stair_y": (-4.5, 1.5),            # stair zone
    "elev_y": (1.5, 4.5),              # elevator zone (shaft)
    "cab_x": (-1.25, 1.25),            # cab interior
    "cab_h": 2.7,
    "door_w": 1.2,                     # elevator door clear width (2 panels x 0.6)
    "door_h": 2.1,
    "stair_door_x": (-1.8, -0.6),      # stair-to-floor opening on the south face
    "max_occupants": 4,
    "cooldown_ms": 4000,
    "door_open_ms": 8000,
    "travel_ms_base": 1500,
    "travel_ms_per_stop": 500,
}


def tower_levels(spec=TOWER_A):
    """Return the stacked modules of a tower as (module, class_suffix, z_offset)."""
    out = [("lobby", "Lobby", 0.0)]
    z = spec["lobby_h"]
    for i in range(spec["typical_floors"]):
        out.append(("floor", "Floor_" + spec["floor_variant"].capitalize(), z))
        z += FLOOR_H
    out.append(("roof", "Roof_Helipad", z))
    return out


def elevator_stops(spec=TOWER_A):
    """Heights (model space, relative to tower base) where the cab stops."""
    return [z for (_, _, z) in tower_levels(spec)]


def core_height(spec=TOWER_A):
    """Core runs from 0 to roof level + one penthouse storey."""
    return elevator_stops(spec)[-1] + FLOOR_H


# --------------------------------------------------------------------- classes
def cls(suffix):
    """Config/script class name. 'Land_' prefix keeps the vanilla building convention."""
    return "Land_SKY_TowerA_" + suffix


CLASS_LOBBY = cls("Lobby")
CLASS_FLOOR = cls("Floor_Office")
CLASS_ROOF = cls("Roof_Helipad")
CLASS_CORE = cls("Core")

P3D = {
    CLASS_LOBBY: "sky_towera_lobby.p3d",
    CLASS_FLOOR: "sky_towera_floor_office.p3d",
    CLASS_ROOF: "sky_towera_roof_helipad.p3d",
    CLASS_CORE: "sky_towera_core.p3d",
}

# --------------------------------------------------------------------- keycard door (lobby security room)
SECURITY_ROOM = {"x": (6.0, 11.85), "y": (6.0, 11.85)}   # NE corner of the lobby
KEYCARD_DOOR = {
    "name": "door_sec",                 # bone / component / Doors class base name
    "hinge": (6.0, 7.0),                # (X, Y) on the room's west wall, swings inward (+X)
    "width": 1.0,
    "height": 2.1,
    "required_tier": 2,
    "relock_ms": 60000,
}

KEYCARD_TIERS = {1: "SKY_Keycard_T1", 2: "SKY_Keycard_T2", 3: "SKY_Keycard_T3"}
# D61 alcohol items (sky_items config; CE in economy/gen_economy.py; doses in SKY_PlayerLife.c).
# class: (display name, description, vanilla liquid id, initial ml)
ALCOHOL_ITEMS = {
    "SKY_Bottle_Vodka": ("Bottle of vodka", "Cheap Chernarussian vodka. A shot dulls pain; half a bottle and the street starts to spin.",
                         2048, 500),
    "SKY_Bottle_Beer": ("Bottle of beer", "Warm, flat lager from a looted bar. Mild.", 4096, 500),
}

# --------------------------------------------------------------------- loot (model-space Blender frame, Z = height above slab)
# Hand-placed points per module; the generator converts to mapgroupproto (x, y_up, z).
LOOT = {
    CLASS_LOBBY: {
        "usages": ["Town", "Office"],
        "lootmax": 8,
        "containers": [
            {"name": "lootFloor", "lootmax": 5, "categories": ["tools", "containers", "clothes"],
             "tags": ["floor"],
             "points": [(-8.0, -8.0), (-9.5, 6.0), (8.0, -8.0), (-4.5, -9.0), (4.5, -9.5), (-10.0, 0.0)]},
            # weapons only: keeps T2 keycards (category tools) from spawning behind the T2 door
            {"name": "lootSecurity", "lootmax": 3, "categories": ["weapons"],
             "tags": ["floor"],
             "points": [(8.0, 8.0), (10.5, 10.5), (8.0, 10.8), (10.8, 7.5)]},
        ],
    },
    CLASS_FLOOR: {
        "usages": ["Town", "Office"],
        "lootmax": 6,
        "containers": [
            {"name": "lootFloor", "lootmax": 6, "categories": ["tools", "containers", "clothes", "food", "books"],
             "tags": ["floor"],
             "points": [(-9.0, -9.0), (-9.0, 9.0), (9.0, -9.0), (9.0, 9.0), (-6.0, 0.0), (6.0, 0.0),
                        (0.0, -8.0), (0.0, 8.5), (-10.5, -3.0), (10.5, 3.0)]},
        ],
    },
    CLASS_ROOF: {
        "usages": ["Town"],
        "lootmax": 2,
        "containers": [
            {"name": "lootFloor", "lootmax": 2, "categories": ["tools", "containers"],
             "tags": ["ground"],
             "points": [(-9.0, -9.0), (9.0, -9.0), (-9.0, 9.0)]},
        ],
    },
}
LOOT_POINT = {"range": 0.6, "height": 1.5}

# Roof-drop event positions on the helipad roof (Blender frame X, Y; memory points roof_drop_N).
ROOF_DROPS = [(-8.0, -8.0), (8.0, -8.0), (-8.0, 8.0), (8.0, 8.0)]


# ===================================================================== KIT (batches 1-4)
# Shared materials added for the kit. Same trim-sheet idea: few rvmats, many assets.
MATERIALS.update({
    "paver":     {"rvmat": rvmat("sky_paver"), "co": tex("sky_paver_co")},
    "roadmark":  {"rvmat": rvmat("sky_roadmark"), "co": tex("sky_roadmark_ca"),
                  "bands": {"solid": (0.0, 0.25), "dashed": (0.25, 0.5), "crosswalk": (0.5, 1.0)}},
    "asphalt":   {"rvmat": rvmat("sky_asphalt"), "co": tex("sky_asphalt_co")},
    "rust":      {"rvmat": rvmat("sky_rust"), "co": tex("sky_rust_co"),
                  "bands": {"green": (0.0, 0.25), "grey": (0.25, 0.5), "rust": (0.5, 0.75), "burnt": (0.75, 1.0)}},
    "foliage":   {"rvmat": rvmat("sky_foliage"), "co": tex("sky_foliage_ca")},
    "atlas":     {"rvmat": rvmat("sky_atlas"), "co": tex("sky_atlas_co")},
    "billboard": {"rvmat": rvmat("sky_billboard"), "co": tex("sky_billboard_a_co")},
    # Emissive lamp: procedural colour + emissive rvmat (P7 EMISSIVE_LAMP).
    "lamp":      {"rvmat": rvmat("sky_lamp"), "co": "#(argb,8,8,3)color(1,0.95,0.85,1,CO)"},
})

# Props atlas cells (col, row) on a 4 x 4 grid - must match gen_textures.atlas().
ATLAS = {
    "manhole": (0, 0), "timetable": (1, 0), "traffic": (2, 0), "sign": (3, 0),
    "vending": (0, 1), "rack": (1, 1), "panel": (2, 1), "appliance": (3, 1),
}


def atlas_uv(cell):
    """UV rectangle (u0, v0, u1, v1) of an atlas cell in Blender UV space (v up)."""
    c, r = ATLAS[cell]
    return (c / 4.0, 1.0 - (r + 1) / 4.0, (c + 1) / 4.0, 1.0 - r / 4.0)


# Street grid: 12 m tiles = 8 m carriageway + 2 x 2 m sidewalk.
STREET = {"tile": 12.0, "carriageway": 8.0, "sidewalk": 2.0, "curb_h": 0.15, "slab_t": 0.3, "skirt": 0.5}

PREFIX_STREET = MOD + "\\sky_street"
PREFIX_PROPS = MOD + "\\sky_props"
PREFIX_FLOORS = MOD + "\\sky_floors"

# Budget hypotheses per category (same method as reviews/perf_review.md; confirm by FPS test).
BUDGETS = {
    "road":   {"res0": 300, "res1": 150, "res2": 40, "geo_comps": 4, "geo_tris": 60, "sections_res0": 3},
    "small":  {"res0": 600, "res1": 300, "res2": 100, "geo_comps": 8, "geo_tris": 120, "sections_res0": 4},  # D61: +1 (rust/paint/glass trims)
    "medium": {"res0": 1200, "res1": 600, "res2": 150, "geo_comps": 12, "geo_tris": 200, "sections_res0": 5},  # D61: +1
    # one object = road + sidewalks (+ corners): asphalt, paint, paver, curb concrete (perf batch-1 M1/L1)
    "road_combined": {"res0": 400, "res1": 200, "res2": 40, "geo_comps": 10, "geo_tris": 140, "sections_res0": 4},
    # walk-on decals: no Geometry/Fire (no wheel snag), Roadway only
    "flat":   {"res0": 60, "res1": 30, "res2": 4, "sections_res0": 1},
}

# name -> dict(cls, p3d, pbo, category, kind, uses=[assumption params], variants={cls: texture})
KIT = {}


def kit(name, pbo, category, uses=(), variants=None, desc=""):
    KIT[name] = {"cls": "Land_SKY_" + name, "p3d": "sky_" + name.lower() + ".p3d", "pbo": pbo,
                 "category": category, "uses": list(uses), "variants": variants or {}, "desc": desc,
                 "collide": category != "flat"}


# ---- batch 1: street kit + non-enterable props (no door/elevator assumptions)
for _n, _c, _d in [
    ("Road_Straight", "road", "8 x 12 m carriageway, centre dashed line"),
    ("Road_Crossing", "road", "8 x 12 m carriageway with crosswalk"),
    ("Intersection_4Way", "road", "12 x 12 m junction with stop lines"),
    ("Intersection_T", "road", "12 x 12 m T junction (closed side = sidewalk)"),
    ("Sidewalk", "road", "2 x 12 m paver sidewalk with curb"),
    ("Sidewalk_Corner", "road", "2 x 2 m sidewalk corner piece"),
    ("Curb", "road", "3 m curb stone (free placement)"),
    ("Manhole", "flat", "0.8 m cast-iron cover (Roadway only, no collision)"),
    # combined tiles: preferred for districts - 1 entity per 12 m tile (perf batch-1 M1)
    ("Street_Straight", "road_combined", "12 x 12 m street: road + both sidewalks"),
    ("Street_Crossing", "road_combined", "12 x 12 m street with crosswalk"),
    ("Street_Intersection", "road_combined", "12 x 12 m 4-way junction with corner sidewalks built in"),
]:
    _u = ["ROADWAY_ASPHALT", "ROAD_GEO_THICKNESS"] if _n.startswith(("Road", "Inter", "Street")) else []
    kit(_n, "sky_street", _c, uses=_u, desc=_d)
KIT["Intersection_T"]["category"] = "road_combined"     # it already contains a sidewalk (perf L1)
for _n, _c, _d, _u in [
    ("StreetLight", "small", "8 m pole street light (emissive head)", ["EMISSIVE_LAMP"]),
    ("TrafficLight", "small", "traffic light with 5 m arm (static atlas face, no emissive)", []),
    ("Barrier_Concrete", "small", "3 m jersey barrier", []),
    ("Barrier_Steel", "small", "2.4 m crowd barrier", []),
    ("BusStop", "medium", "4 m shelter with bench and timetable", []),
    ("Dumpster", "small", "1.8 m waste container", []),
    ("Planter", "small", "1.5 m concrete planter with shrub", []),
    ("Wreck_Sedan", "medium", "generic rusted sedan hulk (original shape)", []),
    ("Wreck_Van", "medium", "generic burnt box van hulk (original shape)", []),
]:
    kit(_n, "sky_street", _c, uses=_u, desc=_d)
kit("Billboard", "sky_street", "medium", desc="6 x 3 m billboard, poster via hiddenSelections",
    variants={"Land_SKY_Billboard_%s" % k.upper(): PREFIX_TEX + "\\data\\sky_billboard_%s_co.paa" % k for k in "abcd"})


# ---- batch 2: textures, decals, windows, facades
MATERIALS.update({
    "decal_dirt":     {"rvmat": rvmat("sky_decal_dirt"), "co": tex("sky_decal_dirt_ca")},       # alpha-blended (soft)
    "decal_cracks":   {"rvmat": rvmat("sky_decal_cracks"), "co": tex("sky_decal_cracks_ca")},   # alpha-tested
    "decal_graffiti": {"rvmat": rvmat("sky_decal_graffiti"), "co": tex("sky_decal_graffiti_a_ca")},
    "windows":        {"rvmat": rvmat("sky_windows"), "co": tex("sky_windows_co")},             # unlit set
    "windows_lit":    {"rvmat": rvmat("sky_windows_lit"), "co": tex("sky_windows_co")},         # emissive (P7)
    "brick":          {"rvmat": rvmat("sky_brick"), "co": tex("sky_brick_co"), "sheet_m": 3.44,   # metres per U tile
                       "bands": {"bond": (0.0, 0.6), "soldier": (0.6, 0.8), "sill": (0.8, 1.0)}},
    "concpanel":      {"rvmat": rvmat("sky_concpanel"), "co": tex("sky_concpanel_co"), "sheet_m": 3.0,   # 2 x 2 panels of 1.5 m
                       "bands": {"reveal": (0.0, 0.2), "panel": (0.2, 1.0)}},
})
# Wall decals: render-only quads (no collision). The layout tool places them flush in
# front of a surface with Geometry (D16), at a per-type offset so overlapping decals
# never share a plane (perf batch-2 M2), and caps their count (DECAL_CAPS, hypothesis).
DECAL_OFFSET = {"Decal_Dirt": 0.015, "Decal_Cracks": 0.020, "Decal_Graffiti": 0.025}
DECAL_CAPS = {"per_tower": 12}                 # perf batch-5 L1
# Decals go only on OPAQUE facade storeys (security batch-5 M1: glass or an open entrance behind a
# single-sided decal gives one-way concealment). Floor variants whose facade is opaque:
DECAL_OPAQUE_FLOORS = ("mechanical",)
DECAL_SIZE = {"Decal_Dirt": (2.0, 3.0), "Decal_Cracks": (2.0, 2.0), "Decal_Graffiti": (2.0, 2.0)}   # w, h (m)
BUDGETS["decal"] = {"res0": 4, "res1": 4, "res2": 2, "sections_res0": 1}
kit("Decal_Dirt", "sky_street", "decal", desc="2 x 3 m run-off grime (alpha-blended)")
kit("Decal_Cracks", "sky_street", "decal", desc="2 x 2 m plaster/concrete cracks (alpha-tested)")
kit("Decal_Graffiti", "sky_street", "decal", desc="2 x 2 m original graffiti, 4 designs via hiddenSelections",
    variants={"Land_SKY_Decal_Graffiti_%s" % k.upper(): PREFIX_TEX + "\\data\\sky_decal_graffiti_%s_ca.paa" % k for k in "abcd"})
KIT["Decal_Dirt"]["collide"] = KIT["Decal_Cracks"]["collide"] = KIT["Decal_Graffiti"]["collide"] = False


# ---- batch 3: interior props (pbo sky_props)
MATERIALS.update({
    "wood":   {"rvmat": rvmat("sky_wood"), "co": tex("sky_wood_co"),
               "bands": {"oak": (0.0, 0.4), "walnut": (0.4, 0.7), "laminate": (0.7, 0.95), "screen": (0.95, 1.0)}},
    "fabric": {"rvmat": rvmat("sky_fabric"), "co": tex("sky_fabric_co"),
               "bands": {"grey": (0.0, 0.33), "blue": (0.33, 0.66), "beige": (0.66, 1.0)}},
})
ATLAS.update({"monitor": (0, 2), "extinguisher": (1, 2)})
# Shadow-volume budgets (hypotheses, perf batch-3 M3); low / wall-mounted interior props
# cast no shadow volume at all (category interior_small).
BUDGETS["small"]["shadow"] = 60
BUDGETS["medium"]["shadow"] = 100
BUDGETS["interior_small"] = {k: v for k, v in BUDGETS["small"].items() if k != "shadow"}
# Spawned-prop caps for the batch-5 layout generator (perf batch-3 M1, hypotheses):
# every prop is a replicated entity + a pathgraph update at server start.
PROP_CAPS = {"per_floor": 25, "per_tower": 70, "aisle_min": 1.2}   # per_tower binds (perf batch-5 M1)


def door(name, display, orient, scale=1.0):
    """Openable prop part: vanilla building Doors entry (bone/component/memory = name).
    Open angle = DOOR_SWING_SIGN * orient * DOOR_OPEN_ANGLE * scale (P1, unverified).
    orient = +-1 makes the leaf open outward under the P1 (lobby-anchored) convention
    (security batch-3 L1: leaves are built in different orientations)."""
    return {"name": name, "display": display, "orient": orient, "scale": scale}


for _n, _c, _d, _doors in [
    ("ReceptionDesk", "medium", "3 m lobby counter with return and monitor", []),
    ("Desk", "interior_small", "1.6 m office desk with monitor", []),
    ("Cubicle", "medium", "2 x 2 m workstation: 3 fabric screens + L desk", []),
    ("ServerRack", "small", "42U server rack (closed, atlas front)", []),
    ("VendingMachine", "small", "drinks vending machine with openable pickup flap",
     [door("flap", "Pickup flap", -1, 0.6)]),
    ("Locker", "medium", "bank of 3 steel lockers, each door openable",
     [door("locker_door%d" % i, "Locker door", +1) for i in (1, 2, 3)]),
    ("Sofa", "interior_small", "2-seat fabric sofa", []),
    ("Bed", "interior_small", "single bed with headboard", []),
    ("Kitchenette", "medium", "1.8 m counter, sink, upper cabinets, fridge", []),
    ("ExtinguisherCabinet", "interior_small", "wall cabinet with extinguisher, openable glass door",
     [door("cab_door", "Cabinet door", +1)]),
]:
    kit(_n, "sky_props", _c, uses=["DOOR_SWING_SIGN", "DOOR_OPEN_ANGLE"] if _doors else [], desc=_d)
    KIT[_n]["doors"] = _doors
KIT["ExtinguisherCabinet"]["uses"].append("PENETRATION")      # glass door Fire Geometry (glass unverified)


# ---- batch 4: floor / roof variants (pbo sky_floors) on the UNCHANGED Tower A core.
# Same stacking as Tower A: origin = slab top, FLOOR_H storeys, 24 x 24 m footprint,
# core hole CORE; the core's stair door (south face) and elevator door (north face)
# must stay clear on every level (test_kit.py CORE_CLEAR).
BUDGETS["floor"] = {"res0": 1500, "res1": 900, "res2": 120, "res3": 24, "shadow": 100, "geo_comps": 24,
                    "geo_tris": 300, "sections_res0": 5}      # = Tower A Floor_Office budget
BUDGETS["roof"] = {"res0": 300, "res1": 120, "res2": 100, "res3": 50, "shadow": 100, "geo_comps": 12,
                   "geo_tris": 150, "sections_res0": 2}       # = Tower A Roof_Helipad budget
for _n, _c, _d in [
    ("Floor_Apartments", "floor", "typical floor: 4 apartments around a hall ring that wraps the core"),
    ("Floor_Hotel", "floor", "typical floor: corridor around the core, 4 guest rooms + 2 suites with 4 connecting corner rooms"),
    ("Floor_Mechanical", "floor", "plant floor: opaque louvre facade, 4 plant units"),
    ("Roof_Garden", "roof", "roof terrace: parapet, 4 planters with shrubs, 4 roof-drop points"),
    ("Roof_Mechanical", "roof", "plant roof: parapet, 4 HVAC units, 4 roof-drop points"),
]:
    kit(_n, "sky_floors", _c, uses=["PENETRATION"], desc=_d)
# Roof-drop memory points per roof class (Blender X, Y). Helipad = ROOF_DROPS; garden and
# mechanical roofs use the open strips east / west of the core (D33). Read by build_floors.py,
# test_kit.py (crate clearance) and placement/sky_layout.py (cfgeventspawns positions).
ROOF_DROPS_CLEAR = [(-8.0, -2.0), (8.0, -2.0), (-8.0, 2.0), (8.0, 2.0)]
ROOF_DROP_POINTS = {CLASS_ROOF: ROOF_DROPS, KIT["Roof_Garden"]["cls"]: ROOF_DROPS_CLEAR,
                    KIT["Roof_Mechanical"]["cls"]: ROOF_DROPS_CLEAR}


# ===================================================================== realism pass (D53)
# Detail layer of assets/blender/detail.py for every existing building module (Tower A lobby /
# office floor / helipad roof / core and the batch-4 floor and roof variants). Gameplay shell
# unchanged: footprint, slabs, core openings, doors, memory points, loot points, roof drops.
MATERIALS.update({
    # 0.6 m acoustic tile grid with a recessed light panel every 2.4 m (sheet = 2.4 m square)
    "ceiling": {"rvmat": rvmat("sky_ceiling"), "co": tex("sky_ceiling_co"), "sheet_m": 2.4},
})
ATLAS.update({"signage": (2, 2)})        # building name strip (top eighth of the cell), original text
# Facade skin per floor variant: curtain = Tower A glass curtain wall (+ detail), ribbon_* =
# masonry with recessed ribbon windows, louvre = plant floor.
FACADE = {CLASS_FLOOR: "curtain", KIT["Floor_Apartments"]["cls"]: "ribbon_brick",
          KIT["Floor_Hotel"]["cls"]: "ribbon_panel", KIT["Floor_Mechanical"]["cls"]: "louvre"}
DETAIL = {
    "spandrel": 0.3,          # opaque band at the top of each curtain-wall storey (ceiling void)
    "ceiling_drop": 0.04,     # ceiling plane below the next slab (light memory points stay below it)
    "fin_step": 3.0, "fin_d": 0.18,          # curtain-wall fins: spacing / projection (Res0)
    "cornice_d": 0.06,        # slab-nose band projection (visual only, outside the footprint)
    "corner_pier": 0.4,       # concrete corner piers (collide)
    "column_r": 0.3,          # interior columns (office floor, lobby)
    "ribbon": {"sill": 0.9, "head": 2.5, "bay": 3.0, "pier": 0.5},   # ribbon-window facade
    "reveal_back": 0.03,      # glass sits this far in front of the inner wall face (reveal = CT - this)
    "frame_w": 0.06, "frame_d": 0.05,        # window frame section
    "sill_stone": (0.06, 0.02, 0.06),        # (below sill, above sill, projection)
    "soldier_h": 0.22,        # brick soldier course over each window
    "trim_w": 0.08, "trim_d": 0.02,          # door architraves
    "louvre_step": 0.25,      # plant-floor louvre blade spacing (Res0)
}
# Budget hypotheses for the realism pass (D53; perf gate re-checks; confirm with FPS_PROTOCOL).
# Res0 grows (frames, fins, trims) but Res1 stays at about half and Res2 / Res3 at outer faces
# only, so the cost at distance (many towers) barely moves; sections stay <= 8 per module.
BUDGETS["floor"].update({"res0": 5000, "res1": 2500, "res2": 250, "res3": 24, "sections_res0": 8})
BUDGETS["roof"].update({"res0": 1500, "res1": 600, "res2": 150, "geo_comps": 20, "geo_tris": 240, "sections_res0": 5})
TOWER_A_BUDGETS = {
    CLASS_LOBBY: {"res0": 6000, "res1": 3000, "res2": 300, "res3": 40, "shadow": 120, "geo_comps": 36, "geo_tris": 500,
                  "sections_res0": 8},
    CLASS_FLOOR: dict(BUDGETS["floor"]),
    CLASS_CORE: {"res0": 2500, "res1": 1000, "res2": 150, "res3": 20, "shadow": 24, "geo_comps": 80, "geo_tris": 1000,
                 "sections_res0": 3},
    CLASS_ROOF: dict(BUDGETS["roof"]),
}


# ===================================================================== splendour pass (D55)
# User request: "vastly more room" for materials, decoration, texture maps, interior decoration
# and lighting. New shared materials (each with its own maps where they carry information),
# much larger per-module budgets, baked interior decoration and night-only script lights.
MATERIALS.update({
    "marble":  {"rvmat": rvmat("sky_marble"), "co": tex("sky_marble_co"), "sheet_m": 2.4},    # 2 x 2 slabs
    "parquet": {"rvmat": rvmat("sky_parquet"), "co": tex("sky_parquet_co"), "sheet_m": 2.0},
    "paint":   {"rvmat": rvmat("sky_paint"), "co": tex("sky_paint_co"),
                "bands": {"white": (0.0, 0.2), "beige": (0.2, 0.4), "sage": (0.4, 0.6), "slate": (0.6, 0.8),
                          "terracotta": (0.8, 1.0)}},
    "stone":   {"rvmat": rvmat("sky_stone"), "co": tex("sky_stone_co"), "sheet_m": 3.0,
                "bands": {"granite": (0.0, 0.5), "limestone": (0.5, 1.0)}},
    "textile": {"rvmat": rvmat("sky_textile"), "co": tex("sky_textile_co"),
                "bands": {"rug_a": (0.0, 0.3), "rug_b": (0.3, 0.6), "runner": (0.6, 0.8), "curtain": (0.8, 1.0)}},
    # cool-white emissive for office panels / plant rooms (P7 EMISSIVE_LAMP_COOL)
    "lamp_cool": {"rvmat": rvmat("sky_lamp_cool"), "co": "#(argb,8,8,3)color(0.92,0.96,1,1,CO)"},
})
EMISSIVE_LAMP_COOL = (0.85, 0.92, 1.0)
ATLAS.update({"art_a": (3, 2), "art_b": (0, 3), "art_c": (1, 3), "art_d": (2, 3), "wayfinding": (3, 3)})
WAYFINDING = ["L", "1", "2", "3", "4", "5", "R", "EXIT"]          # 4 x 2 sub-cells of atlas cell "wayfinding"


def wayfinding_uv(label):
    """UV rectangle of one wayfinding plate (sub-cell of ATLAS["wayfinding"])."""
    u0, v0, u1, v1 = atlas_uv("wayfinding")
    i = WAYFINDING.index(label)
    cw, ch = (u1 - u0) / 4, (v1 - v0) / 2
    c, r = i % 4, i // 4
    return (u0 + c * cw, v1 - (r + 1) * ch, u0 + (c + 1) * cw, v1 - r * ch)


DETAIL.update({
    "panel_grid": (2.4, 3.6),     # office ceiling light panels (x, y spacing, m); 0.6 x 1.2 m each
    "curtain_w": 0.45,            # curtain panel width each side of a window
    "rail_h": 0.95,               # Juliet balcony rail height above the sill line
})
# Script lights (sky_scripts SKY_LitBuilding): night-only point lights at the light_N memory
# points, no shadows. Count per module is SKY_Const.LIGHTS_PER_MODULE (client cost, D55).
# Budgets: generous room for detail (D55, hypotheses; confirm with FPS_PROTOCOL). Res0 is the
# close-up LOD; Res1 / Res2 / Res3 keep the earlier ratios so many towers at distance stay cheap.
BUDGETS["floor"].update({"res0": 16000, "res1": 6000, "res2": 500, "res3": 48, "shadow": 100, "geo_comps": 56,
                         "geo_tris": 700, "sections_res0": 14})
BUDGETS["roof"].update({"res0": 8000, "res1": 3000, "res2": 300, "res3": 60, "geo_comps": 40, "geo_tris": 500,
                        "sections_res0": 10})
TOWER_A_BUDGETS.update({
    CLASS_LOBBY: {"res0": 20000, "res1": 8000, "res2": 700, "res3": 60, "shadow": 120, "geo_comps": 72,
                  "geo_tris": 900, "sections_res0": 16},
    CLASS_FLOOR: dict(BUDGETS["floor"]),
    CLASS_CORE: {"res0": 6000, "res1": 1500, "res2": 200, "res3": 20, "shadow": 24, "geo_comps": 96, "geo_tris": 1200,
                 "sections_res0": 6},
    CLASS_ROOF: dict(BUDGETS["roof"]),
})


# ===================================================================== city buildings (D56)
# Procedural low/mid-rise buildings for a full city (assets/blender/build_city.py). One style
# grammar (CITY_STYLE) + per-archetype data (CITY_ARCHETYPES) -> every building in three ruin
# states (intact / damaged / ruined). Model frame: front = -Y (street side), origin = centre of
# the footprint at ground-floor slab top. Catalog + estimate: CITY_CATALOG / CITY_PLAN.md.
MATERIALS.update({
    "render": {"rvmat": rvmat("sky_render"), "co": tex("sky_render_co"),
               "bands": {"cream": (0.0, 0.25), "ochre": (0.25, 0.5), "grey": (0.5, 0.75), "white": (0.75, 1.0)}},
    "rubble": {"rvmat": rvmat("sky_rubble"), "co": tex("sky_rubble_co"), "sheet_m": 3.0},
    "signs":  {"rvmat": rvmat("sky_signs"), "co": tex("sky_signs_co")},
})
SIGN_NAMES = ["police", "pharmacy", "market", "cafe", "offices", "depot", "bakery", "hardware", "clinic", "fire",
              "garage", "news", "fuel", "bank", "store", "hospital", "school", "townhall", "post", "metro"]
SIGN_BAND = {k: (i / float(len(SIGN_NAMES)), (i + 1) / float(len(SIGN_NAMES))) for i, k in enumerate(SIGN_NAMES)}
RUIN_STATES = ("Intact", "Damaged", "Ruined")
CITY_STYLE = {
    "wall_t": 0.3,            # exterior wall thickness
    "part_t": 0.15,           # interior partition thickness
    "parapet": 0.9,           # roof parapet height (+ coping)
    "plinth": 0.5,            # stone / granite base band on the ground floor
    "skirt": 1.5,             # foundation skirt below the ground slab (sloped sites)
    "door": (1.2, 2.2),       # front door clear width / height
    "stair_w": 2.6,           # switchback stair well width (2 x 1.15 flights + divider)
    "tread": 0.27, "riser_max": 0.18,
    "string_course": 0.06,    # floor-line band projection on masonry skins
}
# Skins: window size per bay (width, sill, head above the level floor), recess, extras.
CITY_SKINS = {
    "brick":   {"mat": "brick", "ww": 1.2, "sill": 0.9, "head": 2.3, "recess": 0.12, "soldier": True},
    "panel":   {"mat": "concpanel", "ww": 1.5, "sill": 0.9, "head": 2.3, "recess": 0.1},
    "render":  {"mat": "render", "ww": 1.1, "sill": 0.9, "head": 2.4, "recess": 0.1, "shutters": True},
    "stone":   {"mat": "stone", "ww": 1.3, "sill": 0.8, "head": 2.7, "recess": 0.14},
    "curtain": {"mat": "metal", "ww": None, "sill": 0.0, "head": None, "recess": 0.06},
    "metal":   {"mat": "metal", "ww": 2.0, "sill": None, "head": None, "recess": 0.05},
}
# Archetypes: footprint w x d, levels [(use, floor-to-floor)], skin (+ band), ground-floor skin,
# blank sides (party walls), stair position, front door bay, sign, loot (CE verified names).
CITY_ARCHETYPES = {
    "Rowhouse": {"group": "residential", "w": 7.2, "d": 12.0, "levels": [("house", 3.0)] * 3,
                 "skin": ("brick", None), "blank": ("W", "E"), "stair": "back_left", "bay": 2.4, "door_bay": 0,
                 "usage": ["Town"], "cats": ["tools", "containers", "clothes", "food", "books"],
                 "desc": "3-storey brick townhouse, party walls both sides"},
    "AptBlock": {"group": "residential", "w": 18.0, "d": 12.0, "levels": [("flats", 3.0)] * 5,
                 "skin": ("panel", None), "blank": (), "stair": "back_center", "bay": 2.6, "door_bay": "center",
                 "usage": ["Town"], "cats": ["tools", "containers", "clothes", "food", "books"],
                 "desc": "5-storey precast apartment block, 2 flats per floor round a central stair"},
    "CornerShop": {"group": "mixed", "w": 12.0, "d": 12.0, "levels": [("shop", 4.0), ("flat", 3.0), ("flat", 3.0)],
                   "skin": ("render", "ochre"), "ground": "shopfront", "shop_sides": ("S", "W"), "blank": ("E",),
                   "stair": "back_right", "bay": 3.0, "door_bay": 1, "sign": "bakery",
                   "usage": ["Town"], "cats": ["food", "containers", "tools", "clothes"],
                   "desc": "corner bakery with two flats above, shopfront on two streets"},
    "OfficeMid": {"group": "commercial", "w": 18.0, "d": 18.0, "levels": [("office_lobby", 3.5)] + [("office", 3.5)] * 5,
                  "skin": ("curtain", None), "blank": (), "stair": "back_center", "bay": 3.0, "door_bay": "center",
                  "sign": "offices", "usage": ["Office", "Town"], "cats": ["tools", "containers", "books", "clothes"],
                  "desc": "6-storey glass office building, open plan with corner offices"},
    "Warehouse": {"group": "industrial", "w": 24.0, "d": 18.0, "levels": [("warehouse", 7.0)],
                  "skin": ("metal", None), "blank": (), "stair": None, "bay": 4.0, "door_bay": 0, "sign": "depot",
                  "roller_bays": (2, 4), "usage": ["Industrial"], "cats": ["tools", "containers"],
                  "desc": "single-bay steel warehouse, 2 roller doors, racks and a site office"},
    "Police": {"group": "civic", "w": 20.0, "d": 14.0, "levels": [("police_ground", 3.5), ("police_upper", 3.5)],
               "skin": ("stone", None), "blank": (), "stair": "back_left", "bay": 2.86, "door_bay": "center",
               "sign": "police", "usage": ["Police"], "cats": ["weapons", "clothes", "tools", "containers"],
               "desc": "2-storey police station: lobby counter, offices, 3 barred cells"},
}
# Variants of the wave-1 types (same grammar, different skin / height / size): "catalog" = type id.
def _variant(base, **kw):
    v = dict(CITY_ARCHETYPES[base])
    v.update(kw)
    v["catalog"] = base
    return v


CITY_ARCHETYPES.update({
    "RowhouseRender": _variant("Rowhouse", levels=[("house", 3.0)] * 4, skin=("render", "cream"),
                               desc="4-storey rendered townhouse with shutters, party walls"),
    "RowhousePanel": _variant("Rowhouse", levels=[("house", 3.0)] * 2, skin=("panel", None),
                              desc="2-storey precast townhouse, party walls"),
    "AptBlockTall": _variant("AptBlock", levels=[("flats", 3.0)] * 8, desc="8-storey precast apartment block"),
    "AptBlockBrick": _variant("AptBlock", levels=[("flats", 3.0)] * 4, skin=("brick", None),
                              desc="4-storey brick apartment block"),
    "CornerPharmacy": _variant("CornerShop", skin=("render", "white"), sign="pharmacy",
                               usage=["Medic", "Town"], cats=["tools", "containers", "clothes"],
                               desc="corner pharmacy with two flats above"),
    "CornerHardware": _variant("CornerShop", skin=("brick", None), sign="hardware",
                               cats=["tools", "containers"], desc="corner hardware store with two flats above"),
    "OfficeTall": _variant("OfficeMid", levels=[("office_lobby", 3.5)] + [("office", 3.5)] * 8,
                           desc="9-storey glass office building"),
    "WarehouseSmall": _variant("Warehouse", w=18.0, d=12.0, roller_bays=(2,), bay=4.5,
                               desc="small steel warehouse, 1 roller door"),
})
CITY_TESTED = ()          # catalog ids whose TESTING.md city rows passed in DayZ (city_progress.py)

# ---- wave 2 (D57): new uses (corridor plans, market, engine bays, workshop, garage hall, kiosk, shed),
# pitched roofs, doorless garage blocks entered through open bays.
_RES = ["tools", "containers", "clothes", "food", "books"]
CITY_ARCHETYPES.update({
    "Villa": {"group": "residential", "w": 10.0, "d": 10.0, "levels": [("house", 3.0)] * 2, "skin": ("render", "white"),
              "roof": "pitched", "blank": (), "stair": "back_left", "bay": 2.5, "door_bay": 1, "usage": ["Town", "Village"],
              "cats": _RES, "desc": "detached 2-storey villa, pitched zinc roof"},
    "ShopRow": {"group": "mixed", "w": 9.0, "d": 14.0, "levels": [("shop", 4.0)] + [("flat", 3.0)] * 3,
                "skin": ("brick", None), "ground": "shopfront", "shop_sides": ("S",), "blank": ("W", "E"),
                "stair": "back_right", "bay": 3.0, "door_bay": 1, "sign": "cafe", "usage": ["Town"],
                "cats": ["food", "containers", "tools", "clothes"], "desc": "4-storey terrace: cafe below, three flats"},
    "Supermarket": {"group": "commercial", "w": 24.0, "d": 20.0, "levels": [("market", 5.0)], "skin": ("render", "white"),
                    "ground": "shopfront", "shop_sides": ("S",), "blank": (), "stair": None, "bay": 4.0,
                    "door_bay": "center", "sign": "market", "usage": ["Town"], "cats": ["food", "containers", "tools"],
                    "desc": "single-storey supermarket: aisles, checkouts, stock room"},
    "Clinic": {"group": "civic", "w": 16.0, "d": 14.0, "levels": [("clinic_ground", 3.5), ("corridor", 3.5)],
               "skin": ("render", "white"), "blank": (), "stair": "back_center", "bay": 2.67, "door_bay": "center",
               "sign": "clinic", "usage": ["Medic"], "cats": ["tools", "containers", "clothes"],
               "desc": "2-storey clinic: waiting room, exam rooms off a corridor"},
    "FireStation": {"group": "civic", "w": 22.0, "d": 16.0, "levels": [("firebays", 4.5), ("corridor", 3.5)],
                    "skin": ("brick", None), "blank": (), "stair": "back_left", "bay": 3.67, "door_bay": 0,
                    "roller_bays": (2, 3, 4), "sign": "fire", "usage": ["Firefighter"],
                    "cats": ["tools", "clothes", "containers"], "desc": "fire station: 3 engine bays, dormitory floor"},
    "Workshop": {"group": "industrial", "w": 12.0, "d": 10.0, "levels": [("workshop", 4.5)], "skin": ("metal", None),
                 "blank": (), "stair": None, "bay": 4.0, "door_bay": 0, "roller_bays": (1,), "sign": "garage",
                 "parapet": 0.5, "usage": ["Industrial"], "cats": ["tools", "containers"],
                 "desc": "car repair workshop: roller door, workbench, shelving"},
    "GarageBlock": {"group": "industrial", "w": 18.0, "d": 6.0, "levels": [("garage", 3.0)], "skin": ("brick", None),
                    "blank": (), "stair": None, "bay": 3.0, "door_bay": None, "roller_bays": (0, 1, 3, 5),
                    "open_bays": (2, 4), "parapet": 0.4, "roof_gear": False, "usage": ["Industrial", "Town"],
                    "cats": ["tools", "containers"], "desc": "row of lock-up garages, two shutters open"},
    "Kiosk": {"group": "small", "w": 3.0, "d": 2.4, "levels": [("kiosk", 2.8)], "skin": ("panel", None), "blank": (),
              "stair": None, "bay": 3.0, "door_bay": 0, "sign": "news", "parapet": 0.15, "roof_gear": False,
              "usage": ["Town"], "cats": ["food", "books"], "desc": "news kiosk"},
    "Shed": {"group": "small", "w": 4.0, "d": 3.0, "levels": [("shed", 2.6)], "skin": ("render", "grey"), "blank": (),
             "stair": None, "bay": 4.0, "door_bay": 0, "parapet": 0.15, "roof_gear": False,
             "usage": ["Town", "Village"], "cats": ["tools", "containers"], "desc": "yard shed"},
})
CITY_ARCHETYPES.update({
    "VillaBrick": _variant("Villa", skin=("brick", None), desc="detached 2-storey brick villa"),
    "VillaStone": _variant("Villa", skin=("stone", None), desc="detached 2-storey stone villa"),
    "ShopRowMarket": _variant("ShopRow", skin=("render", "cream"), sign="market", desc="4-storey terrace: grocer below"),
    "ShopRowNews": _variant("ShopRow", skin=("panel", None), sign="news", cats=["books", "food", "containers"],
                            desc="4-storey terrace: newsagent below"),
    "ShopRowHardware": _variant("ShopRow", skin=("render", "grey"), sign="hardware", cats=["tools", "containers"],
                                desc="4-storey terrace: hardware store below"),
    "SupermarketSmall": _variant("Supermarket", w=18.0, d=14.0, bay=3.6, desc="small supermarket"),
    "WorkshopBrick": _variant("Workshop", skin=("brick", None), desc="brick car repair workshop"),
    "KioskCafe": _variant("Kiosk", skin=("render", "ochre"), sign="cafe", cats=["food"], desc="coffee kiosk"),
    "ShedBrick": _variant("Shed", skin=("brick", None), desc="brick yard shed"),
})

# ---- wave 3 (D58): civic landmarks and large types. New plan grammar: "double_<kind>" (rooms both
# sides of a central corridor, hall to the stair, wide entry room on the ground), "ring" (perimeter
# block round an open yard, ring gallery), "dept" (sales floors round an atrium), "parking" (open
# decks + car ramps), forecourts (canopy / terrace inside the footprint, in front of the body),
# per-archetype window sizes ("win"), Y-ridge pitched roof + bell tower, sawtooth roof.
# Odd bay counts on the front put the door on the axis (landmarks).
_OFF = ["tools", "containers", "books", "clothes"]
CITY_SKINS["open"] = {"mat": "concrete", "ww": None, "sill": None, "head": None, "recess": 0.0}
CITY_ARCHETYPES.update({
    "WarehouseLarge": _variant("Warehouse", w=36.0, d=24.0, roller_bays=(2, 4, 6),
                               desc="large steel warehouse, 3 roller doors"),
    "CourtyardBlock": {"group": "residential", "w": 30.0, "d": 30.0, "levels": [("ring", 3.0)] * 5,
                       "skin": ("render", "ochre"), "yard": 14.0, "blank": (), "stair": "back_center", "bay": 3.33,
                       "door_bay": "center", "room_w": 4.4, "usage": ["Town"], "cats": _RES,
                       "desc": "5-storey perimeter block round an inner yard, gateway from the street"},
    "GasStation": {"group": "commercial", "w": 12.0, "d": 8.0, "forecourt": (20.0, 6.5), "levels": [("gas", 3.8)],
                   "skin": ("render", "white"), "ground": "shopfront", "shop_sides": ("S",), "blank": (), "stair": None,
                   "bay": 2.4, "door_bay": "center", "sign": "fuel", "parapet": 0.6, "roof_gear": False,
                   "usage": ["Town", "Industrial"], "cats": ["food", "tools", "containers"],
                   "desc": "filling station: shop and pump canopy on the forecourt"},
    "Cafe": {"group": "commercial", "w": 12.0, "d": 6.0, "forecourt": (12.0, 4.0), "levels": [("cafe", 3.6)],
             "skin": ("render", "cream"), "ground": "shopfront", "shop_sides": ("S", "W", "E"), "blank": (),
             "stair": None, "bay": 2.4, "door_bay": "center", "sign": "cafe", "parapet": 0.5, "roof_gear": False,
             "usage": ["Town"], "cats": ["food", "containers"], "desc": "cafe pavilion with a street terrace"},
    "Bank": {"group": "commercial", "w": 16.0, "d": 14.0,
             "levels": [("bank_ground", 4.0), ("double_office", 3.5), ("double_office", 3.5)],
             "skin": ("stone", None), "blank": (), "stair": "back_right", "bay": 3.2, "door_bay": "center",
             "room_w": 3.6, "sign": "bank", "landmark": "portico", "usage": ["Office", "Town"], "cats": _OFF,
             "desc": "3-storey stone bank: banking hall, vault, offices above"},
    "DepartmentStore": {"group": "commercial", "w": 40.0, "d": 30.0,
                        "levels": [("dept", 4.5), ("dept", 4.0), ("dept", 4.0)], "skin": ("render", "white"),
                        "ground": "shopfront", "shop_sides": ("S", "W", "E"), "blank": (), "stair": "back_center",
                        "bay": 4.44, "door_bay": "center", "atrium": (12.0, 8.0), "sign": "store",
                        "usage": ["Town"], "cats": ["clothes", "containers", "tools", "food", "books"],
                        "desc": "3-storey department store round a central atrium"},
    "Hospital": {"group": "civic", "w": 40.0, "d": 24.0, "levels": [("double_exam", 4.0)] + [("double_ward", 3.5)] * 4,
                 "skin": ("render", "white"), "blank": (), "stair": "back_center", "bay": 3.08, "door_bay": "center",
                 "entry_w": 8.0, "entry_kind": "reception", "room_w": 4.8, "sign": "hospital",
                 "usage": ["Medic"], "cats": ["tools", "containers", "clothes"],
                 "desc": "5-storey hospital: reception and exam rooms, four ward floors"},
    "School": {"group": "civic", "w": 30.0, "d": 16.0, "levels": [("double_class", 3.6)] * 3, "skin": ("brick", None),
               "blank": (), "stair": "back_center", "bay": 3.33, "door_bay": "center", "entry_w": 6.0,
               "entry_kind": "reception", "room_w": 7.2, "sign": "school", "usage": ["School"],
               "cats": ["books", "clothes", "containers", "tools"], "desc": "3-storey brick school, classrooms off a corridor"},
    "TownHall": {"group": "civic", "w": 24.0, "d": 18.0,
                 "levels": [("double_office", 4.0), ("double_office", 3.6), ("double_office", 3.6)],
                 "skin": ("stone", None), "blank": (), "stair": "back_center", "bay": 3.43, "door_bay": "center",
                 "entry_w": 6.0, "entry_kind": "reception", "room_w": 4.8, "sign": "townhall", "landmark": "townhall",
                 "usage": ["Office", "Town"], "cats": _OFF,
                 "desc": "3-storey stone town hall: pilasters, pediment, clock and cupola"},
    "Church": {"group": "civic", "w": 14.0, "d": 24.0, "levels": [("nave", 9.0)], "skin": ("stone", None),
               "roof": "pitched", "ridge": "y", "tower": True, "win": (1.2, 3.0, 7.0), "blank": (), "stair": None,
               "bay": 2.8, "door_bay": "center", "usage": ["Town", "Village"], "cats": ["clothes", "containers", "books"],
               "desc": "stone church: tall nave, pews, front bell tower with spire"},
    "PostOffice": {"group": "civic", "w": 14.0, "d": 12.0, "levels": [("shop", 3.6), ("corridor", 3.4)],
                   "skin": ("render", "cream"), "ground": "shopfront", "shop_sides": ("S",), "blank": (),
                   "stair": "back_right", "bay": 2.8, "door_bay": "center", "sign": "post", "usage": ["Town", "Office"],
                   "cats": ["books", "containers", "clothes"], "desc": "2-storey post office: counter hall, offices above"},
    "FactoryHall": {"group": "industrial", "w": 36.0, "d": 24.0, "levels": [("factory", 8.0)], "skin": ("brick", None),
                    "win": (2.4, 3.6, 6.6), "roof": "sawtooth", "blank": (), "stair": None, "bay": 4.0, "door_bay": 0,
                    "roller_bays": (3, 6), "parapet": 0.6, "roof_gear": False, "usage": ["Industrial"],
                    "cats": ["tools", "containers"], "desc": "brick factory hall: sawtooth roof, machines, crane beam"},
    "ParkingGarage": {"group": "industrial", "w": 30.0, "d": 24.0, "levels": [("parking", 3.0)] * 4,
                      "skin": ("open", None), "blank": (), "stair": "back_left", "bay": 5.0, "door_bay": None,
                      "open_bays": (3,), "roller_h": 2.6, "ramps": True, "parapet": 1.1, "roof_gear": False,
                      "usage": ["Town", "Industrial"], "cats": ["tools", "containers"],
                      "desc": "4-deck open parking garage: car ramps, stair, wrecks"},
    "Substation": {"group": "industrial", "w": 10.0, "d": 8.0, "levels": [("yard", 3.0)], "skin": ("brick", None),
                   "special": "substation", "blank": (), "stair": None, "bay": 2.5, "door_bay": None,
                   "usage": [], "cats": [], "desc": "fenced electrical substation (not enterable)"},
})
CITY_ARCHETYPES.update({
    "CourtyardBlockBrick": _variant("CourtyardBlock", skin=("brick", None), levels=[("ring", 3.0)] * 4,
                                    desc="4-storey brick perimeter block round an inner yard"),
    "CafeBrick": _variant("Cafe", skin=("brick", None), desc="brick cafe pavilion with a street terrace"),
})


# ---- D61 venues (ROADMAP.md ideas 4, 6, 7, 10, 12, 14, 21). Second sign sheet so the existing
# sign bands (and every committed city P3D) stay unchanged.
MATERIALS.update({"signs2": {"rvmat": rvmat("sky_signs2"), "co": tex("sky_signs2_co")}})
SIGN2_NAMES = ["hyper", "kino", "mall", "bar", "creche", "club", "fair", "parking", "landfill", "food", "tickets",
               "fashion", "shoes", "jewelry", "electro", "danger"]
SIGN_MAT = {k: "signs" for k in SIGN_NAMES}
SIGN_MAT.update({k: "signs2" for k in SIGN2_NAMES})
SIGN_BAND.update({k: (i / float(len(SIGN2_NAMES)), (i + 1) / float(len(SIGN2_NAMES))) for i, k in enumerate(SIGN2_NAMES)})
# Night light per archetype ("light"): hyper = cold, over-bright, also on by day (idea 4: "une lumiere
# blanche qui fait mal aux yeux"); warm = interior light; default by group (gen_configs.city_lit_script).
CITY_LIGHT = {"hyper": "SKY_HyperLight", "warm": "SKY_InteriorLight", "cool": "SKY_OfficeLight"}
CITY_ARCHETYPES.update({
    "Hypermarket": {"group": "venue", "w": 44.0, "d": 32.0, "levels": [("hyper", 7.0)], "skin": ("panel", None),
                    "ground": "shopfront", "shop_sides": ("S",), "blank": (), "stair": None, "bay": 4.0,
                    "door_bay": "center", "sign": "hyper", "sign_w": 16.0, "parapet": 1.2, "light": "hyper",
                    "usage": ["Town"], "cats": ["food", "containers", "tools", "clothes"],
                    "desc": "hypermarket: 44 x 32 m hall, tall racks, checkout lines, harsh fluorescent light"},
    "Mall": {"group": "venue", "w": 56.0, "d": 40.0, "levels": [("mall", 5.0)] * 3, "skin": ("render", "white"),
             "ground": "shopfront", "shop_sides": ("S",), "blank": (), "stair": "back_center", "bay": 4.0,
             "door_bay": "center", "atrium": (20.0, 12.0), "skylight": True, "escalators": True, "sign": "mall",
             "sign_w": 12.0, "costume": True, "light": "warm", "usage": ["Town"],
             "cats": ["clothes", "containers", "food", "tools", "books"],
             "desc": "3-level mall round a glass-roofed atrium: shop units, galleries, escalators, fountain, food court"},
    "Cinema": {"group": "venue", "w": 22.0, "d": 34.0, "levels": [("cinema", 9.0)], "skin": ("render", "cream"),
               "forecourt": (14.0, 3.0),
               "blank": (), "stair": None, "bay": 3.67, "door_bay": "center", "landmark": "cinema",
               "costume": True, "light": "warm", "usage": ["Town"], "cats": ["clothes", "food", "containers"],
               "desc": "cinema KINO: marquee, foyer with ticket and snack counters, raked auditorium, screen"},
    "Bar": {"group": "commercial", "w": 12.0, "d": 10.0, "levels": [("bar", 3.8)], "skin": ("brick", None),
            "ground": "shopfront", "shop_sides": ("S",), "blank": (), "stair": None, "bay": 2.4, "door_bay": "center",
            "sign": "bar", "parapet": 0.5, "roof_gear": False, "alcohol": True, "light": "warm", "usage": ["Town"],
            "cats": ["food", "containers"], "desc": "corner bar: long counter, bottle wall, booths, pool table"},
    "Kindergarten": {"group": "civic", "w": 20.0, "d": 14.0, "levels": [("creche", 3.3)] * 2,
                     "skin": ("render", "ochre"), "forecourt": (20.0, 9.0), "blank": ("E",), "stair": "back_left",
                     "bay": 2.86, "door_bay": "center", "sign": "creche", "landmark": "creche", "light": "warm",
                     "usage": ["School"], "cats": ["clothes", "books", "containers"],
                     "desc": "2-storey kindergarten: playrooms, nap room with cots, mosaic sun, rusty playground"},
    "Clubhouse": {"group": "civic", "w": 16.0, "d": 8.0, "levels": [("changing", 3.2)], "skin": ("brick", None),
                  "blank": (), "stair": None, "bay": 2.67, "door_bay": "center", "sign": "club", "parapet": 0.5,
                  "roof_gear": False, "light": "warm", "usage": ["Town"], "cats": ["clothes", "containers"],
                  "desc": "football clubhouse: home and away changing rooms with benches, lockers and showers"},
})
CITY_ARCHETYPES["ChurchHanged"] = _variant("Church", decor="hanged",
                                           desc="stone church: hanged shrouded bodies from the trusses, toppled pews, candles")


def city_footprint(A):
    """Model-space footprint (x0, x1, y0, y1) of an archetype: body + forecourt in front (-Y)."""
    hw, hd = A["w"] / 2, A["d"] / 2
    fc = A.get("forecourt")
    if not fc:
        return (-hw, hw, -hd, hd)
    fw = max(hw, fc[0] / 2)
    return (-fw, fw, -hd - fc[1], hd)


# City packages (D60): one PBO per group keeps every package well under ~300 MB of source models
# (the single sky_city was 939 MB). Class names and .p3d names do not change, only the folder.
CITY_PBOS = {
    "sky_city_res": "rowhouses, apartment blocks, villas",
    "sky_city_block": "perimeter (courtyard) blocks",
    "sky_city_com": "shops, shop rows, offices, supermarkets, cafes, gas station, bank, department store",
    "sky_city_civic": "police, fire station, clinic, hospital, school, town hall, church, post office",
    "sky_city_ind": "warehouses, workshops, garages, factory, parking garage, substation, kiosks, sheds",
    "sky_city_env": "rubble lots, vegetation, water tower, metro entrances",
    "sky_city_venue": "hypermarket, mall, cinema (D61 venues)",
}


def city_pbo(arch=None):
    """Package of a city archetype (None: lots, vegetation and kit pieces)."""
    if arch is None:
        return "sky_city_env"
    if arch.startswith("CourtyardBlock"):
        return "sky_city_block"
    return {"residential": "sky_city_res", "mixed": "sky_city_com", "commercial": "sky_city_com", "venue": "sky_city_venue",
            "civic": "sky_city_civic", "industrial": "sky_city_ind", "small": "sky_city_ind"}[CITY_ARCHETYPES[arch]["group"]]


def _city_category(e):
    if len(e["levels"]) >= 7:
        return "city_tall"
    return "city_large" if e["w"] * e["d"] >= 600 else "city"


for _a, _e in CITY_ARCHETYPES.items():
    for _i, _st in enumerate(RUIN_STATES):
        kit("City_%s_%s" % (_a, _st), city_pbo(_a), _city_category(_e), uses=["PENETRATION"] + (["DOOR_SWING_SIGN"] if _i < 2 else []),
            desc="%s (%s)" % (_e["desc"], _st.lower()))
        # orient -1: city front doors open inward (action point inside), see test_city swing test
        KIT["City_%s_%s" % (_a, _st)]["doors"] = [door("door_front", "Door", -1)] if (_i < 2 and _e["door_bay"] is not None) else []
        KIT["City_%s_%s" % (_a, _st)]["city"] = {"archetype": _a, "ruin": _i}
for _v in "ABCD":                                     # standalone collapsed lots (kit, no ruin states)
    kit("City_RubbleLot_%s" % _v, city_pbo(), "city", uses=["PENETRATION"], desc="12 x 12 m collapsed building lot")
    KIT["City_RubbleLot_%s" % _v]["doors"] = []
    KIT["City_RubbleLot_%s" % _v]["city"] = {"archetype": None, "ruin": 2, "lot": _v}
    KIT["City_RubbleLot_%s" % _v]["catalog"] = "RubbleLot"
# Wave 3 kit pieces (one model each, not enterable, no loot). Metro entrances are sealed at street
# level: a stair down needs a terrain hole (custom terrain only), so both variants stay on the
# surface (D58).
for _n, _cid, _d in [("City_WaterTower", "WaterTower", "18 m steel water tower on a lattice frame"),
                     ("City_MetroEntrance_A", "MetroEntrance", "metro stair head sealed with steel plates, railings, sign"),
                     ("City_MetroEntrance_B", "MetroEntrance", "glazed metro entrance pavilion, doors chained shut")]:
    kit(_n, city_pbo(), "city", uses=["PENETRATION"], desc=_d)
    KIT[_n]["doors"] = []
    KIT[_n]["city"] = {"archetype": None, "ruin": 0, "piece": _cid}
    KIT[_n]["catalog"] = _cid
# Placeable non-archetype pieces for placement/city_fill.py: class keys, footprint (w, d).
CITY_PIECES = {"RubbleLot": (["City_RubbleLot_%s" % v for v in "ABCD"], 12.0, 12.0),
               "WaterTower": (["City_WaterTower"], 6.0, 6.0),
               "MetroEntrance": (["City_MetroEntrance_A", "City_MetroEntrance_B"], 4.0, 6.0)}
# Loot points of the city buildings are computed by build_city.py (on a slab, clear of every solid,
# outside stair and collapse) and committed in assets/city_loot.json -> CE groups here.
_CITY_LOOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "city_loot.json")
if os.path.exists(_CITY_LOOT):
    for _cls, _pts in _json.load(open(_CITY_LOOT)).items():
        _a = CITY_ARCHETYPES[KIT[_cls[len("Land_SKY_"):]]["city"]["archetype"]]
        LOOT[_cls] = {"usages": _a["usage"], "lootmax": max(1, min(12, len(_pts) // 2)), "containers": [
            {"name": "lootFloor", "lootmax": max(1, min(12, len(_pts) // 2)), "categories": _a["cats"], "tags": ["floor"],
             "points": [(p[0], p[1], p[2], LOOT_POINT["range"], LOOT_POINT["height"]) for p in _pts]}]}
# ---- full-city catalog + estimate (CITY_PLAN.md is generated from this by city_progress.py)
# Reference (vanilla dayzOffline.chernarusplus mapgroupproto / mapgrouppos, counted D56):
# 414 lootable building types on the map; Chernogorsk ~980 lootable buildings of 169 types,
# Elektrozavodsk ~545 of 136. Target "SKY city" = dense downtown + midtown + 2 residential
# districts + an industrial edge, about the size of Chernogorsk: ~650 placed buildings, ~150
# unique models. kind: proc = build_city archetype (x 3 ruin states), modular = Tower A system,
# kit = sky_street / sky_props pieces. variants = size / layout / skin variants of the type.
CITY_CATALOG = [
    # id, group, footprint (m), floors, kind, variants, instances in the full city, wave, note
    ("Rowhouse", "residential", "7.2x12", 3, "proc", 3, 120, 1, "brick / render / panel skins, 2-4 floors"),
    ("AptBlock", "residential", "18x12", 5, "proc", 3, 45, 1, "4 / 5 / 8 floors"),
    ("Villa", "residential", "10x10", 2, "proc", 3, 50, 2, "detached house with garden wall"),
    ("CourtyardBlock", "residential", "30x30", 5, "proc", 2, 8, 3, "perimeter block, inner yard"),
    ("TowerResidential", "residential", "24x24", 7, "modular", 1, 6, 0, "Tower A core + apartment / hotel floors"),
    ("CornerShop", "mixed", "12x12", 3, "proc", 3, 30, 1, "bakery / pharmacy / hardware signs"),
    ("ShopRow", "mixed", "9x14", 4, "proc", 4, 80, 2, "shops on the ground floor, flats above"),
    ("OfficeMid", "commercial", "18x18", 6, "proc", 2, 20, 1, "6 / 9 floors"),
    ("OfficeTower", "commercial", "24x24", 25, "modular", 2, 3, 4, "Tower A modules on tall cores T15 / T23 (17 / 25 storeys)"),
    ("HQLandmark", "commercial", "24x24", 35, "modular", 1, 1, 4, "core T33 + crown roof (pylons, fins, spire)"),
    ("TowerOffice", "commercial", "24x24", 7, "modular", 1, 4, 0, "Tower A as built"),
    ("Supermarket", "commercial", "24x20", 1, "proc", 2, 6, 2, "shelf aisles, loading bay"),
    ("GasStation", "commercial", "20x14", 1, "proc", 1, 4, 2, "shop + pump canopy"),
    ("Cafe", "commercial", "12x10", 1, "proc", 2, 10, 2, "pavilion with terrace"),
    ("Bank", "commercial", "16x14", 3, "proc", 1, 3, 3, "vault (keycard tier 3)"),
    ("DepartmentStore", "commercial", "40x30", 3, "proc", 1, 1, 3, "atrium, escalators as stairs"),
    ("Police", "civic", "20x14", 2, "proc", 1, 3, 1, "cells, armoury loot"),
    ("FireStation", "civic", "22x16", 2, "proc", 1, 2, 2, "engine bays"),
    ("Clinic", "civic", "16x14", 2, "proc", 1, 4, 2, "Medic loot"),
    ("Hospital", "civic", "40x24", 5, "proc", 1, 1, 3, "wards, Medic loot"),
    ("School", "civic", "30x16", 3, "proc", 1, 2, 3, "School usage"),
    ("TownHall", "civic", "24x18", 3, "proc", 1, 1, 3, "landmark square"),
    ("Church", "civic", "14x24", 1, "proc", 1, 1, 3, "landmark, tower"),
    ("PostOffice", "civic", "14x12", 2, "proc", 1, 2, 3, ""),
    ("Warehouse", "industrial", "24x18", 1, "proc", 3, 30, 1, "18x12 / 24x18 / 36x24"),
    ("Workshop", "industrial", "12x10", 1, "proc", 2, 30, 2, "garage / car repair"),
    ("FactoryHall", "industrial", "36x24", 1, "proc", 1, 4, 3, "sawtooth roof"),
    ("ParkingGarage", "industrial", "30x24", 4, "proc", 1, 4, 3, "ramps, cars"),
    ("Substation", "industrial", "10x8", 1, "proc", 1, 6, 2, "fenced, not enterable"),
    ("WaterTower", "industrial", "6x6", 1, "kit", 1, 2, 3, ""),
    ("Kiosk", "small", "3x2.4", 1, "proc", 2, 30, 2, "news / coffee"),
    ("MetroEntrance", "small", "4x6", 1, "kit", 2, 8, 3, "sealed at street level (no terrain hole)"),
    ("RubbleLot", "ruin", "12x12", 0, "kit", 4, 50, 2, "collapsed lot fillers"),
    ("GarageBlock", "industrial", "18x6", 1, "proc", 1, 40, 2, "row of lock-up garages"),
    ("Shed", "small", "4x3", 1, "proc", 2, 40, 2, "yard sheds / annexes"),
]
# One object per building (Tower A splits into 7 modules, 77 sections): ~20 sections and ~200
# convex parts for a 5-6 storey block are in line with large vanilla buildings (hypothesis, D56).
BUDGETS["city"] = {"res0": 30000, "res1": 9000, "res2": 1500, "res3": 200, "shadow": 600, "geo_comps": 240,
                   "geo_tris": 3000, "sections_res0": 24}
BUDGETS["city_tall"] = {"res0": 50000, "res1": 15000, "res2": 2000, "res3": 200, "shadow": 800, "geo_comps": 340,
                        "geo_tris": 4200, "sections_res0": 24}            # 7+ storeys (scales per storey)
# Footprints >= 600 m2 (hospital, department store, courtyard block, factory, large warehouse): one
# object like the large vanilla buildings (hospital / school), more rooms and parts (D58 hypothesis).
BUDGETS["city_large"] = {"res0": 80000, "res1": 24000, "res2": 2500, "res3": 300, "shadow": 1000, "geo_comps": 640,
                         "geo_tris": 8000, "sections_res0": 24}    # largest: courtyard block, 4500 m2 floor area


# ---- city layout zones (D57): placement/city_fill.py fills blocks lot by lot along their street
# edges. weights = archetype mix, ruin = (intact, damaged, ruined) probabilities, lots = chance of
# a rubble lot per slot, gap = metres between detached buildings (party-wall types sit flush),
# corner = archetypes preferred on a block corner (shopfront on two streets), small_cap = kiosks / sheds
# per block (small pieces would otherwise fill every leftover gap; real blocks keep yards and alleys),
# once = landmarks / big types placed at most once per block (D58).
CITY_ZONES = {
    "downtown": {"weights": {"OfficeMid": 3, "OfficeTall": 2, "AptBlockTall": 2, "ShopRow": 3, "ShopRowMarket": 2,
                             "ShopRowNews": 1, "ShopRowHardware": 1, "Supermarket": 1, "Clinic": 1, "Police": 1,
                             "Kiosk": 1, "KioskCafe": 1, "Bank": 1, "Cafe": 1, "CafeBrick": 1, "PostOffice": 1,
                             "MetroEntrance": 1},
                 "corner": ["CornerShop", "CornerPharmacy", "CornerHardware"], "ruin": (0.40, 0.40, 0.20),
                 "lots": 0.04, "gap": 1.5, "small_cap": 1,
                 "once": ["Bank", "Police", "Clinic", "PostOffice", "MetroEntrance", "Supermarket"]},
    "midtown": {"weights": {"AptBlock": 3, "AptBlockBrick": 2, "ShopRow": 2, "ShopRowMarket": 1, "Rowhouse": 2,
                            "RowhouseRender": 2, "SupermarketSmall": 1, "Clinic": 1, "FireStation": 1, "Kiosk": 1,
                            "CourtyardBlock": 2, "CourtyardBlockBrick": 1, "Cafe": 1, "GasStation": 1, "PostOffice": 1},
                "corner": ["CornerShop", "CornerPharmacy", "CornerHardware"], "ruin": (0.45, 0.35, 0.20),
                "lots": 0.05, "gap": 1.5, "small_cap": 1,
                "once": ["CourtyardBlock", "CourtyardBlockBrick", "GasStation", "PostOffice", "Clinic", "FireStation"]},
    "residential": {"weights": {"Rowhouse": 4, "RowhouseRender": 3, "RowhousePanel": 2, "Villa": 3, "VillaBrick": 2,
                                "VillaStone": 1, "Shed": 2, "ShedBrick": 1, "KioskCafe": 1, "CourtyardBlockBrick": 1,
                                "CafeBrick": 1},
                    "corner": ["CornerShop", "CornerPharmacy"], "ruin": (0.55, 0.30, 0.15), "lots": 0.03, "gap": 2.0,
                    "small_cap": 3, "once": ["CourtyardBlockBrick", "CafeBrick"]},
    "industrial": {"weights": {"Warehouse": 3, "WarehouseSmall": 3, "Workshop": 3, "WorkshopBrick": 2, "GarageBlock": 3,
                               "Shed": 1, "WarehouseLarge": 2, "FactoryHall": 1, "ParkingGarage": 1, "Substation": 2,
                               "WaterTower": 1, "GasStation": 1},
                   "corner": [], "ruin": (0.35, 0.40, 0.25), "lots": 0.08, "gap": 2.5, "small_cap": 2,
                   "once": ["FactoryHall", "ParkingGarage", "WaterTower", "GasStation", "Substation"]},
    "frontline": {"weights": {"AptBlock": 2, "AptBlockBrick": 2, "ShopRow": 2, "Rowhouse": 2, "RowhouseRender": 1,
                              "Police": 1, "WarehouseSmall": 1, "GarageBlock": 1, "CourtyardBlock": 1, "Substation": 1},
                  "corner": ["CornerShop", "CornerHardware"], "ruin": (0.10, 0.40, 0.50), "lots": 0.20, "gap": 1.5,
                  "small_cap": 1, "once": ["CourtyardBlock", "Police", "Substation"]},
}
# Spawned city buildings are replicated entities (objectSpawnersArr): a layout with target
# "spawner" obeys ENTITY_CAP; target "terrain" (a whole city baked into a custom map, Level 2 in
# MOD_DEVELOPMENT_GUIDE 4.3) writes an object list instead and is not capped.
CITY_SKIRT_DROP = 1.5           # ground may fall this far below a city building's ground slab (skirt)


# ===================================================================== batch 5: economy + placement prep
# Tower variants: Tower A's core has len(elevator_stops()) stops (lobby + typical_floors + roof),
# so every tower built on it has exactly TOWER_A["typical_floors"] typical floors; each may be
# any floor variant, and the roof any roof variant (same stacking, D31).
FLOOR_VARIANTS = {"office": CLASS_FLOOR, "apartments": KIT["Floor_Apartments"]["cls"],
                  "hotel": KIT["Floor_Hotel"]["cls"], "mechanical": KIT["Floor_Mechanical"]["cls"]}
ROOF_VARIANTS = {"helipad": CLASS_ROOF, "garden": KIT["Roof_Garden"]["cls"],
                 "mechanical": KIT["Roof_Mechanical"]["cls"]}

# Model-space XY bounds (Blender x0, x1, y0, y1) of every spawnable prop's Geometry. Used by the
# layout generator for aisle / overlap checks; test_kit.py verifies them against the P3D Geometry.
PROP_BOX = {
    "ReceptionDesk": (-1.55, 2.3, -0.5, 1.2), "Desk": (-0.8, 0.8, -0.4, 0.4), "Cubicle": (-1.0, 1.0, -1.0, 1.0),
    "ServerRack": (-0.3, 0.3, -0.5, 0.5), "VendingMachine": (-0.5, 0.5, -0.43, 0.4),
    "Locker": (-0.45, 0.45, -0.27, 0.25), "Sofa": (-1.0, 1.0, -0.45, 0.45), "Bed": (-0.75, 0.75, -1.0, 1.06),
    "Kitchenette": (-1.22, 1.2, -0.32, 0.3), "ExtinguisherCabinet": (-0.2, 0.2, -0.27, 0.0),
}


def _mirror4(props):
    """Props given for the +X +Y quadrant -> all four quadrants (yaw mirrored)."""
    out = []
    for name, x, y, yaw in props:
        out += [(name, x, y, yaw), (name, -x, y, (360 - yaw) % 360),
                (name, x, -y, (180 - yaw) % 360), (name, -x, -y, (180 + yaw) % 360)]
    return out


# Furnish sets: props spawned per floor (objectSpawnersArr), model-space Blender (x, y) + DayZ
# yaw (deg, clockwise) relative to the floor module [+ optional mounting height z, e.g. wall
# cabinets on the core wall at 1.0 m]. "for" = floor classes the set fits.
# test_kit.py checks every prop box against the floor's Geometry, core clear zones and loot
# points; sky_layout.py checks PROP_CAPS and aisles.
FURNISH = {
    "office_open": {"for": [CLASS_FLOOR], "props": [
        # cubicles keep clear of Tower A's loot points at (+-9, +-9) (Tower A frozen)
        ("Cubicle", 3.5, -9.5, 0), ("Cubicle", 6.8, -9.5, 0), ("Cubicle", 3.5, 9.0, 0), ("Cubicle", 6.8, 9.0, 0),
        ("Cubicle", -3.5, 9.0, 0), ("Cubicle", -6.8, 9.0, 0), ("Desk", 9.5, 0.0, 90), ("Kitchenette", 8.5, -4.0, 0),
        ("Locker", -9.5, 2.5, 90), ("VendingMachine", -5.0, -2.0, 0), ("ExtinguisherCabinet", -3.0, 0.0, 90, 1.0)]},
    "apartments": {"for": [KIT["Floor_Apartments"]["cls"]], "props": _mirror4([
        ("Bed", 3.0, 10.0, 0), ("Sofa", 9.0, 3.0, 90), ("Kitchenette", 8.5, 9.5, 0)])},
    "hotel": {"for": [KIT["Floor_Hotel"]["cls"]], "props": [
        ("Bed", x, 10.2, 0) for x in (-9.0, -3.0, 3.0, 9.0)] + [("Bed", x, -10.2, 180) for x in (-9.0, -3.0, 3.0, 9.0)] + [
        ("Bed", 9.0, 4.0, 0), ("Sofa", 9.5, 0.0, 90), ("Bed", -9.0, 4.0, 0), ("Sofa", -9.5, 0.0, 270)]},
    "mechanical": {"for": [KIT["Floor_Mechanical"]["cls"]], "props": [
        ("ServerRack", x, y, 0) for x in (-6.5, 6.5) for y in (-2.2, 0.0, 2.2)] + [
        ("Locker", 0.0, -8.5, 0), ("ExtinguisherCabinet", -3.0, 0.0, 90, 1.0)]},
}

# Street furniture density caps (perf batch-1 M1/L7, hypotheses): lights per straight street tile,
# total entities per district (towers + core + tiles + props + decals + lights).
LIGHT_CAP = {"per_tile": 0.5}
# per_district / per_server count spawned entities + loot items (sum of group lootmax); hypotheses
# until the S1/S6 measurements (perf batch-5 M1/M3).
ENTITY_CAP = {"per_district": 800, "per_server": 2500}
BLOCK_SETBACK = 0.5          # m between a tower footprint and the block edge (street sidewalk)


# ---- batch 5 loot groups (mapgroupproto). Points: (x, y) on the slab (Blender frame, floor
# loot, LOOT_POINT range/height) or (x, y, z, range, height) for furniture surfaces (vanilla
# "lootshelves" pattern: small range/height, tag "shelves"). Names verified against
# dayzOffline.chernarusplus cfglimitsdefinition.xml (categories, usages, tags).
def _m4(pts):
    return [(sx * x, sy * y) for x, y in pts for sx in (1, -1) for sy in (1, -1)]


LOOT.update({
    KIT["Floor_Apartments"]["cls"]: {"usages": ["Town"], "lootmax": 8, "containers": [
        {"name": "lootFloor", "lootmax": 8, "categories": ["tools", "containers", "clothes", "food", "books"],
         "tags": ["floor"], "points": _m4([(5.0, 9.0), (8.5, 6.0), (9.5, 1.0)])}]},
    KIT["Floor_Hotel"]["cls"]: {"usages": ["Town"], "lootmax": 8, "containers": [
        {"name": "lootFloor", "lootmax": 8, "categories": ["clothes", "containers", "tools", "food"],
         "tags": ["floor"], "points": [(x, y) for x in (-7.2, -1.2, 4.8, 10.8) for y in (-8.5, 8.5)] + [(7.0, -3.0), (-7.0, -3.0)]}]},
    KIT["Floor_Mechanical"]["cls"]: {"usages": ["Industrial"], "lootmax": 4, "containers": [
        {"name": "lootFloor", "lootmax": 4, "categories": ["tools", "containers"],
         "tags": ["floor"], "points": [(-8.0, -5.0), (8.0, -5.0), (-8.0, 5.0), (8.0, 5.0), (0.0, 8.0)]}]},
    KIT["Roof_Garden"]["cls"]: {"usages": ["Town"], "lootmax": 2, "containers": [
        {"name": "lootFloor", "lootmax": 2, "categories": ["tools", "containers"],
         "tags": ["ground"], "points": [(0.0, -8.0), (0.0, 8.0), (-8.0, -5.0)]}]},
    KIT["Roof_Mechanical"]["cls"]: {"usages": ["Industrial"], "lootmax": 2, "containers": [
        {"name": "lootFloor", "lootmax": 2, "categories": ["tools"],
         "tags": ["ground"], "points": [(0.0, -8.0), (0.0, 8.0), (-8.0, -5.0)]}]},
    # props (spawned per floor by FURNISH): small shelf-style points on their surfaces
    KIT["Locker"]["cls"]: {"usages": ["Town", "Office", "Industrial"], "lootmax": 1, "containers": [
        {"name": "lootshelves", "lootmax": 1, "categories": ["clothes", "tools", "containers"], "tags": ["shelves"],
         "points": [(x, 0.0, z, 0.12, 0.3) for x in (-0.3, 0.0, 0.3) for z in (0.06, 1.48)]}]},
    KIT["Desk"]["cls"]: {"usages": ["Office", "Town"], "lootmax": 1, "containers": [
        {"name": "lootshelves", "lootmax": 1, "categories": ["tools", "books"], "tags": ["shelves"],
         "points": [(-0.5, -0.15, 0.75, 0.2, 0.3), (0.5, -0.15, 0.75, 0.2, 0.3)]}]},
    KIT["ReceptionDesk"]["cls"]: {"usages": ["Office", "Town"], "lootmax": 2, "containers": [
        {"name": "lootshelves", "lootmax": 2, "categories": ["tools", "books", "containers"], "tags": ["shelves"],
         "points": [(-1.0, 0.0, 1.1, 0.25, 0.3), (1.0, 0.0, 1.1, 0.25, 0.3), (1.9, 0.8, 0.75, 0.25, 0.3)]}]},
    KIT["Kitchenette"]["cls"]: {"usages": ["Town", "Office"], "lootmax": 1, "containers": [
        {"name": "lootshelves", "lootmax": 1, "categories": ["food"], "tags": ["shelves"],
         "points": [(0.2, 0.0, 0.92, 0.2, 0.3), (-1.1, 0.0, 0.92, 0.1, 0.3)]}]},
})


# ===================================================================== tall towers (D58)
# The Tower A system scaled up: same lobby, floor and roof modules, a taller core per height.
# The elevator script reads its stops from config (skyStops[]), so a core with more stops is only a
# new model + config class (script class generated as a subclass of Land_SKY_TowerA_Core).
# OfficeTower = cores with 15 / 23 typical floors (17 / 25 storeys incl. the double-height lobby);
# HQLandmark = 33 typical floors (35 storeys) + the crown roof (Roof_Crown).
def tower_spec(n):
    spec = dict(TOWER_A)
    spec["typical_floors"] = n
    return spec


CORE_VARIANTS = {"A": (CLASS_CORE, TOWER_A)}
for _n in (15, 23, 33):
    _c = cls("Core%d" % _n)
    CORE_VARIANTS["T%d" % _n] = (_c, tower_spec(_n))
    P3D[_c] = "sky_towera_core%d.p3d" % _n
    # budgets scale with the stops (one cab, two door leaves, landings per stop); hypotheses
    _k = (_n + 2) / 7.0
    TOWER_A_BUDGETS[_c] = {"res0": int(6000 * _k), "res1": int(1500 * _k), "res2": 400, "res3": 20, "shadow": 24,
                           "geo_comps": int(96 * _k), "geo_tris": int(1200 * _k), "sections_res0": 6}
BUDGETS["core_tall"] = {"res0": 52000, "res1": 13000, "res2": 520, "res3": 20, "shadow": 24, "geo_comps": 840,
                        "geo_tris": 10500, "sections_res0": 6}
TOWER_CORE_MANIFEST = [(c, "sky_towera", P3D[c], "core_tall",
                        "stair + elevator core, %d stops (lobby, %d floors, roof), script Land_SKY_TowerA_Core subclass"
                        % (len(elevator_stops(spec)), spec["typical_floors"], ))
                       for k, (c, spec) in CORE_VARIANTS.items() if k != "A"]
kit("Roof_Crown", "sky_floors", "roof", uses=["PENETRATION"],
    desc="HQ crown roof: parapet, setback glass lantern, steel crown fins, 24 m spire with obstruction lights")
ROOF_DROP_POINTS[KIT["Roof_Crown"]["cls"]] = ROOF_DROPS_CLEAR
ROOF_VARIANTS["crown"] = KIT["Roof_Crown"]["cls"]


# ===================================================================== DayZ ambiance pass (D59)
# Weathering overlay (alpha-blended, like decal_dirt) and vegetation (alpha-tested) for the city.
MATERIALS.update({
    "decal_grime": {"rvmat": rvmat("sky_decal_grime"), "co": tex("sky_decal_grime_ca"),
                    "bands": {"damp": (0.0, 0.25), "runoff": (0.25, 0.5), "streak": (0.5, 0.75), "moss": (0.75, 1.0)}},
    "vegetation": {"rvmat": rvmat("sky_vegetation"), "co": tex("sky_vegetation_ca")},
})
# 4 x 4 cells of sky_vegetation_ca (gen_textures.VEG_CELLS, row-major from the top-left)
VEG_ATLAS = {n: (i % 4, i // 4) for i, n in enumerate(
    ["grass", "weeds", "burdock", "shrub", "ivy", "ivy_hang", "birch_crown", "dead_branches",
     "bark", "litter", "moss", "sapling", "dry_grass", "reeds", "bramble", "ivy_dark"])}


def veg_uv(cell):
    """(u0, v0, u1, v1) of a vegetation cell, Blender UV (v up)."""
    c, r = VEG_ATLAS[cell]
    return (c / 4.0, 1.0 - (r + 1) / 4.0, (c + 1) / 4.0, 1.0 - r / 4.0)


# How much the city is overgrown / weathered per ruin state (seeded per building, build_city.dress).
WEATHER = {
    "ivy": (0.15, 0.35, 0.6),          # chance per facade side (intact, damaged, ruined)
    "weeds": (0.6, 0.85, 1.0),          # chance per facade base bay
    "roof_weeds": (0.0, 0.5, 1.0),      # roof / upper-floor weeds and saplings
    "window_streaks": (0.25, 0.5, 0.7), # chance per window
    "bars": 0.35,                       # ground-floor window bars on residential blocks (intact / damaged)
}

# Vegetation kit (D59): our own plants on the vegetation atlas, scattered by placement/city_fill.py in
# yards, rubble lots and block interiors. veg = no collision (walk through, like vanilla grass /
# small bushes); tree = trunk collides (Geometry + Fire), crown is cards.
BUDGETS["veg"] = {"res0": 300, "res1": 120, "res2": 40, "res3": 8, "sections_res0": 1}
BUDGETS["tree"] = {"res0": 500, "res1": 200, "res2": 60, "res3": 12, "shadow": 40, "geo_comps": 2, "geo_tris": 40,
                   "sections_res0": 1}
for _n, _c, _w, _d in [("Veg_Weeds", "veg", 3.0, "3 x 3 m patch of grass, weeds, burdock and bramble (no collision)"),
                       ("Veg_Bush", "veg", 2.6, "2.5 m wild shrub with bramble skirt (no collision)"),
                       ("Veg_Birch", "tree", 3.2, "9 m self-seeded birch: trunk collides, crown cards"),
                       ("Veg_TreeDead", "tree", 3.2, "6 m dead tree: trunk collides, bare branch cards")]:
    kit(_n, city_pbo(), _c, desc=_d)
    KIT[_n]["doors"] = []
    KIT[_n]["city"] = {"archetype": None, "ruin": 0, "piece": _n, "veg": True}
    KIT[_n]["catalog"] = "Vegetation"
    KIT[_n]["collide"] = _c == "tree"                                     # weeds / bushes: render only
    CITY_PIECES[_n] = ([_n], _w, _w)
VEG_PIECES = ["Veg_Weeds", "Veg_Bush", "Veg_Birch", "Veg_TreeDead"]

# Overgrowth per zone (city_fill.scatter_vegetation): grid step (m), chance per grid point, piece mix,
# cap per block, extra points in perimeter-block yards. Downtown is kept, the frontline is wild.
_VEG = {"downtown": {"step": 9.0, "fine": 6.0, "chance": 0.4, "mix": {"Veg_Weeds": 5, "Veg_Bush": 2, "Veg_Birch": 1},
                     "cap": 14, "yard": 4},
        "midtown": {"step": 8.0, "fine": 5.0, "chance": 0.55, "mix": {"Veg_Weeds": 4, "Veg_Bush": 3, "Veg_Birch": 2,
                                                                        "Veg_TreeDead": 1}, "cap": 22, "yard": 5},
        "residential": {"step": 7.0, "fine": 4.5, "chance": 0.65, "mix": {"Veg_Weeds": 4, "Veg_Bush": 3, "Veg_Birch": 3,
                                                                            "Veg_TreeDead": 1}, "cap": 28, "yard": 5, "fine_trees": True},
        "industrial": {"step": 8.0, "fine": 5.0, "chance": 0.6, "mix": {"Veg_Weeds": 6, "Veg_Bush": 2, "Veg_Birch": 1,
                                                                          "Veg_TreeDead": 2}, "cap": 22, "yard": 3},
        "frontline": {"step": 7.0, "fine": 4.5, "chance": 0.75, "mix": {"Veg_Weeds": 5, "Veg_Bush": 3, "Veg_Birch": 2,
                                                                          "Veg_TreeDead": 3}, "cap": 28, "yard": 5, "fine_trees": True}}
for _z, _v in _VEG.items():
    CITY_ZONES[_z]["veg"] = _v
# Grass through ground floors: on a spawner site the clutter (grass) of the terrain grows through
# slabs that sit a few cm above it. Vanilla cutter objects remove it (verified class:
# 4_world/entities/gardenbase/gardenplot.c:19 creates "ClutterCutter6x6"). Footprint assumed 6 x 6 m
# from the name (P12). Custom terrains paint a no-clutter surface under the city instead.
CLUTTER_CUTTER = {"class": "ClutterCutter6x6", "size": 6.0}

# Tileable wall sheets (D59): the facade skins map their walls onto these at world scale (u along the
# wall, v = height), so storey-high piers and tall naves no longer stretch a trim band. The trim
# sheets stay for sills, string courses, soldier courses and plinths.
MATERIALS.update({
    "wall_brick": {"rvmat": rvmat("sky_wall_brick"), "co": tex("sky_wall_brick_co"), "sheet_m": 3.44},
    "wall_panel": {"rvmat": rvmat("sky_wall_panel"), "co": tex("sky_wall_panel_co"), "sheet_m": 3.0},
    "wall_limestone": {"rvmat": rvmat("sky_wall_limestone"), "co": tex("sky_wall_limestone_co"), "sheet_m": 3.0},
})
for _c in ("cream", "ochre", "grey", "white"):
    MATERIALS["wall_render_" + _c] = {"rvmat": rvmat("sky_wall_render_" + _c), "co": tex("sky_wall_render_%s_co" % _c),
                                      "sheet_m": 4.0}
CITY_SKINS["brick"]["wall"] = "wall_brick"
CITY_SKINS["panel"]["wall"] = "wall_panel"
CITY_SKINS["stone"]["wall"] = "wall_limestone"
CITY_SKINS["render"]["wall"] = "wall_render_%s"          # + skin band (cream / ochre / grey / white)


# ===================================================================== content pass (D60)
# Office floor facade variants on the unchanged office plan (same slab, partitions, loot points,
# furniture and light points as Tower A's Floor_Office): precast-panel and brick ribbon windows,
# and the HQ landmark floor (dark curtain wall, deep bronze fins, ribbed bronze spandrels, granite
# piers) on its own 4K atlas - the skyline landmark is seen up close from the plaza.
MATERIALS.update({
    "hqfacade": {"rvmat": rvmat("sky_hq_facade"), "co": tex("sky_hq_facade_co"), "sheet_m": 6.0,
                 "bands": {"bronze": (0.0, 0.25), "spandrel": (0.25, 0.5), "granite": (0.5, 0.75),
                           "louvre": (0.75, 1.0)}},
})
for _n, _d in [
    ("Floor_Office_Concrete", "typical office floor: precast concrete panels with ribbon windows"),
    ("Floor_Office_Brick", "typical office floor: brick facade with ribbon windows"),
    ("Floor_HQ", "HQ office floor: dark curtain wall, bronze fins and ribbed spandrels, granite piers (4K atlas)"),
]:
    kit(_n, "sky_floors", "floor", uses=["PENETRATION"], desc=_d)
FACADE.update({KIT["Floor_Office_Concrete"]["cls"]: "ribbon_panel", KIT["Floor_Office_Brick"]["cls"]: "ribbon_brick",
               KIT["Floor_HQ"]["cls"]: "hq"})
FLOOR_VARIANTS.update({"office_concrete": KIT["Floor_Office_Concrete"]["cls"],
                       "office_brick": KIT["Floor_Office_Brick"]["cls"], "hq": KIT["Floor_HQ"]["cls"]})
OFFICE_FLOORS = [CLASS_FLOOR] + [KIT[_n]["cls"] for _n in ("Floor_Office_Concrete", "Floor_Office_Brick", "Floor_HQ")]
FURNISH["office_open"]["for"] = list(OFFICE_FLOORS)
for _c in OFFICE_FLOORS[1:]:
    LOOT[_c] = LOOT[CLASS_FLOOR]
# Lobby_B: Tower A's lobby plan with a street-retail frontage (shop fascias, signs, awnings,
# limestone piers). Same keycard door, security room, loot and light points; config class
# inherits Land_SKY_TowerA_Lobby (script class generated as its subclass).
CLASS_LOBBY_B = cls("Lobby_B")
P3D[CLASS_LOBBY_B] = "sky_towera_lobby_b.p3d"
TOWER_A_BUDGETS[CLASS_LOBBY_B] = dict(TOWER_A_BUDGETS[CLASS_LOBBY])
LOOT[CLASS_LOBBY_B] = LOOT[CLASS_LOBBY]
LOBBY_VARIANTS = {"A": CLASS_LOBBY, "B": CLASS_LOBBY_B}

# Skybridge: enclosed glazed walkway between the roofs of two towers in facing blocks (12 m street,
# towers centred in 36 m blocks -> facade gap 24 m). Model frame: bridge along Y, origin = gap
# centre at roof slab top (z 0 = roof slab top of both towers). It lands LANDING m onto each roof
# over the 1.1 m parapet: deck DECK_Z above the roof, steps down onto the roof at both ends.
# Lateral position on the roofs (tower frame): bridges leaving an N / S side run at x = 0, E / W at
# y = +4.7 - free on every roof variant (no parapet-interior Geometry, roof drops, planters, plant,
# crown fins in the 3 m landing lane; checked by test_kit.py on all roofs and sides).
SKYBRIDGE = {"gap": 24.0, "gap_tol": 0.5, "half_w": 1.2, "landing": 3.0, "deck_z": 1.25, "deck_t": 0.15,
             "clear_h": 2.5, "steps": 5, "lateral": {"NS": 0.0, "EW": 4.7}}
BUDGETS["skybridge"] = {"res0": 1500, "res1": 600, "res2": 120, "res3": 40, "shadow": 60, "geo_comps": 40,
                        "geo_tris": 400, "sections_res0": 6}
kit("Skybridge", "sky_floors", "skybridge", uses=["PENETRATION"],
    desc="enclosed glazed walkway, 24 m span between two tower roofs, landings with steps over the parapets")

# Vanilla trees (P13): objectSpawnersArr spawns a .p3d path under DZ\plants* as a static object
# (3_game/objectspawner.c:44 CreateStaticObjectUsingP3D, path check :3-8 / :81). Empty = off: the
# paths are not verified from this container and client visibility of these server-side static
# objects is untested. Fill with paths checked on P:\DZ\plants\tree\ to replace VANILLA_TREE_SHARE
# of the Veg_Birch picks (same 4 m footprint, same clearances) with real DayZ trees.
VANILLA_TREES = []
VANILLA_TREE_SHARE = 0.5


# ===================================================================== D61 landmarks, roads, street props
# ROADMAP.md: funfair (1), car jams / viaducts / tunnel (2), landfill (13), searchable bins (16),
# hydrants (17), alarm sirens (20), football ground (21), car parks + hidden metro hatch (22), the bridge (23).
MATERIALS.update({
    "fair": {"rvmat": rvmat("sky_fair"), "co": tex("sky_fair_co"),
             "bands": {"yellow": (0.0, 0.25), "red": (0.25, 0.5), "blue": (0.5, 0.75), "white": (0.75, 1.0)}},
    "trash": {"rvmat": rvmat("sky_trash"), "co": tex("sky_trash_co"), "sheet_m": 4.0},
    "turf": {"rvmat": rvmat("sky_turf"), "co": tex("sky_turf_co"), "sheet_m": 8.0},
})
BUDGETS["landmark"] = {"res0": 60000, "res1": 15000, "res2": 2500, "res3": 300, "shadow": 600, "geo_comps": 400,
                       "geo_tris": 6000, "sections_res0": 16}           # Ferris wheel, bridge, stadium stand (hypothesis)
BUDGETS["lot"] = {"res0": 30000, "res1": 9000, "res2": 1500, "res3": 200, "shadow": 400, "geo_comps": 300,
                  "geo_tris": 4000, "sections_res0": 16}                # open lots: landfill, pitch, car parks
BUDGETS["road_struct"] = {"res0": 12000, "res1": 4000, "res2": 800, "res3": 100, "shadow": 200, "geo_comps": 80,
                          "geo_tris": 1200, "sections_res0": 10}        # viaduct / tunnel segments
LANDMARKS = [
    # name, pbo, category, footprint (w, d), description
    ("Fair_FerrisWheel", "sky_landmarks", "landmark", (28.0, 10.0), "26 m Ferris wheel, 16 yellow gondolas, rust and saplings (Pripyat)"),
    ("Fair_Carousel", "sky_landmarks", "landmark", (14.0, 14.0), "chain-swing carousel: striped canopy, 16 swings, ring fence"),
    ("Fair_BumperCars", "sky_landmarks", "landmark", (18.0, 12.0), "bumper-car pavilion: steel roof, fascia, 6 abandoned cars"),
    ("Fair_Booth", "sky_landmarks", "medium", (4.0, 3.0), "ticket / shooting-gallery booth with striped awning"),
    ("Fair_Gate", "sky_landmarks", "landmark", (14.0, 3.0), "LUNAPARK entrance arch with turnstiles"),
    ("Landfill", "sky_landmarks", "lot", (40.0, 40.0), "municipal landfill: rubbish mounds, crushed cars, compactor shed, fence"),
    ("Stadium_Pitch", "sky_landmarks", "lot", (64.0, 44.0), "football pitch: worn turf, lines, goals, dugouts, rail fence"),
    ("Stadium_Stand", "sky_landmarks", "landmark", (24.0, 8.0), "covered stand: 6 terraces with seats, roof on columns"),
    ("Stadium_Floodlight", "sky_landmarks", "medium", (4.0, 2.0), "18 m lattice floodlight mast"),
    ("ParkingLot_A", "sky_landmarks", "lot", (24.0, 24.0), "surface car park: bays, lamp posts, barrier booth, wrecks"),
    ("ParkingLot_B", "sky_landmarks", "lot", (24.0, 12.0), "small surface car park: one row of bays, wrecks"),
    ("ParkingLot_Metro", "sky_landmarks", "lot", (24.0, 24.0), "car park hiding a sealed metro service hatch behind a van wreck"),
    ("TrashBin", "sky_street", "small", (0.7, 0.7), "street litter bin with lid (searchable)"),
    ("Hydrant_Wet", "sky_street", "small", (0.6, 0.6), "fire hydrant that still gives water (vanilla well behaviour)"),
    ("Hydrant_Dry", "sky_street", "small", (0.6, 0.6), "dry fire hydrant (decoration)"),
    ("SirenTower", "sky_street", "medium", (2.0, 2.0), "civil-defence siren on a 10 m pole (city alarm event)"),
    ("Wreck_GarbageTruck", "sky_street", "medium", (2.6, 9.0), "abandoned garbage truck (rear hopper searchable)"),
    ("Viaduct_Straight", "sky_roads", "road_struct", (12.0, 12.0), "elevated road, 12 m segment at 7 m, barriers, central pier"),
    ("Viaduct_Ramp", "sky_roads", "road_struct", (12.0, 48.0), "viaduct ramp: 0 -> 7 m over 48 m, retaining walls"),
    ("Tunnel_Straight", "sky_roads", "road_struct", (24.0, 12.0), "cut-and-cover road tunnel, 12 m segment, earth berms, deck on top"),
    ("Tunnel_Portal", "sky_roads", "road_struct", (24.0, 12.0), "tunnel end cell: headwall over the mouth at -Y, hazard band, sign"),
    ("Bridge_Long", "sky_roads", "landmark", (98.0, 16.0), "96 m truss bridge: checkpoint, convoy pile-up, sniper nests (the bridge)"),
]
LANDMARK_SIZE = {}
for _n, _pbo, _cat, _fp, _d in LANDMARKS:
    kit(_n, _pbo, _cat, uses=["PENETRATION"], desc=_d)
    LANDMARK_SIZE[_n] = _fp
KIT["Fair_Booth"]["doors"] = []
# Placeable non-archetype pieces for city_fill.py (class keys, footprint w, d).
CITY_PIECES.update({"ParkingLot": (["ParkingLot_A", "ParkingLot_Metro"], 24.0, 24.0),
                    "ParkingLotSmall": (["ParkingLot_B"], 24.0, 12.0)})
for _p in ("ParkingLot", "ParkingLotSmall"):
    CITY_ZONES["downtown"]["weights"][_p] = 1
    CITY_ZONES["midtown"]["weights"][_p] = 2
    CITY_ZONES["industrial"]["weights"][_p] = 1
# D62 creatures (build_creatures.py): static pieces driven by server scripts (no AI rig possible, D62).
kit("RatNest", "sky_street", "medium", uses=["P22"], desc="rat nest: rubbish heap with 9 rats; bites and gnaws nearby bases (SKY_Rats.c)")
kit("HorseCarcass", "sky_street", "medium", desc="dead horse on its side, half hide half bone (horses are blocked, D62)")
LANDMARK_SIZE["RatNest"] = (2.6, 2.6)
LANDMARK_SIZE["HorseCarcass"] = (2.4, 2.8)
# The guard kennel is an item (sky_items/sky_kennel.p3d), config in gen_configs.items_config.
KENNEL = {"cls": "SKY_Kennel", "p3d": "sky_kennel.p3d", "base": "SeaChest",
          "display": "Dog kennel", "desc": "A doghouse and its old guard dog. Place it by your stash: while you are away the "
          "dog keeps everyone out of it and barks at anyone who comes close."}
# D63 underground kit (build_underground.py): cut-and-cover boxes under street level (custom terrain only).
UNDERGROUND = {"roof_top": -0.1, "sewer_floor": -6.0, "sewer_height": 2.6, "metro_floor": -8.0, "metro_height": 5.0,
               "flood_rise": 1.6}
# Underground darkness (cfgundergroundtriggers EyeAccommodation 0..1, InterpolationSpeed) - P27 hypotheses.
UNDERGROUND_LIGHT = {"eye_inside": 0.15, "speed": 1.0}
BUDGETS["underground"] = {"res0": 9000, "res1": 3000, "res2": 200, "geo_comps": 40, "geo_tris": 600, "sections_res0": 10}
for _n, _fp, _d in [
        ("Sewer_Straight", (4.8, 12.0), "brick sewer, 12 m: channel, two walkways, pipes, lamps; flooding water"),
        ("Sewer_Access", (4.8, 12.0), "sewer straight with a side door (+X wall, y 4.0..5.2) to a Sewer_Stair"),
        ("Sewer_End", (4.8, 12.0), "sewer straight closed at +Y: brick end wall, outfall grating"),
        ("Sewer_Junction", (12.0, 12.0), "sewer crossing, plank bridges over the channels; flooding water"),
        ("Sewer_Stair", (2.8, 12.0), "stair beside a Sewer_Access (+X, same yaw): street opening at -Y, door in its -X wall"),
        ("Metro_Tunnel", (13.0, 12.0), "double-track metro box tunnel, 12 m: ballast, sleepers, rails, ledges, cables"),
        ("Metro_End", (13.0, 12.0), "metro tunnel closed at +Y: end wall, buffer stops"),
        ("Metro_Station", (17.0, 24.0), "metro station: island platform, columns, tiles, benches, kiosk, stair to the street (+Y)")]:
    kit(_n, "sky_underground", "underground", uses=["P25", "P26"], desc=_d)
    KIT[_n]["doors"] = []
    LANDMARK_SIZE[_n] = _fp
for _n in ("Sewer_Straight", "Sewer_Access", "Sewer_End", "Sewer_Junction"):
    KIT[_n]["flood"] = True
# CE loot of the two loot destinations (ROADMAP ideas 13, 23): the landfill has a bit of everything at the foot of
# each rubbish mound; the bridge is the high-risk military drop (deck points + the two sniper nests).
_LF_MOUNDS = [(-11.0, 8.0, 5.5), (2.0, 11.0, 5.0), (12.0, 6.0, 6.5), (-12.0, -6.0, 4.0), (9.5, -8.0, 4.5), (-2.0, 1.5, 3.5),
              (-4.0, -12.5, 3.0)]
LOOT.update({
    "Land_SKY_Landfill": {"usages": ["Industrial", "Farm", "Village"], "lootmax": 8, "containers": [
        {"name": "lootFloor", "lootmax": 8, "categories": ["tools", "containers", "clothes", "food", "books"],
         "tags": ["ground"],
         "points": [(x, y - ry - 1.2) for (x, y, ry) in _LF_MOUNDS] + [(6.0, -14.0), (-8.0, 15.0), (16.0, -2.0),
                                                                        (-16.5, 4.0), (0.0, -6.5)]}]},
    "Land_SKY_Bridge_Long": {"usages": ["Military"], "lootmax": 4, "containers": [
        {"name": "lootFloor", "lootmax": 4, "categories": ["weapons", "tools", "containers"],
         "tags": ["ground"],
         "points": [(-2.0, 0.0), (2.0, 0.0), (-6.5, -3.0), (6.5, 3.0), (-12.0, 0.0), (12.0, 0.0),
                    (-45.0, 0.0, 6.45, 0.6, 1.5), (45.0, 0.0, 6.45, 0.6, 1.5)]}]},
})
# Searchable objects (ActionSKY_SearchTrash): memory point "search" (or search_N) marks where the player
# stands; the server loot table lives in SKY_SearchTable (scripts), not in config.
SEARCHABLE = ["Dumpster", "TrashBin", "Wreck_GarbageTruck", "Landfill"]
# config value skySearch = <table> (read by SKY_SearchService; the tables themselves are server script)
SEARCH_TABLES = ["trash", "landfill", "costume", "alcohol"]
SEARCH_TABLE = {"Dumpster": "trash", "TrashBin": "trash", "Wreck_GarbageTruck": "trash", "Landfill": "landfill"}
for _n, _e in KIT.items():
    _c = _e.get("city") or {}
    _arch = CITY_ARCHETYPES.get(_c.get("archetype")) if _c.get("archetype") else None
    if _arch and _arch.get("costume"):
        SEARCH_TABLE[_n] = "costume"                     # mall rails, cinema costume trunks (idea 19)
    elif _arch and _arch.get("alcohol"):
        SEARCH_TABLE[_n] = "alcohol"                     # behind-the-bar stock (idea 10)
for _n, _t in SEARCH_TABLE.items():
    assert _t in SEARCH_TABLES, (_n, _t)
    KIT[_n]["config_extra"] = KIT[_n].get("config_extra", "") + '\t\tskySearch = "%s";\n' % _t
# Parks: fixed arrangements placed in a whole block (layout `blocks: [{park: <kind>}]`) instead of the fill.
# (piece | archetype@state, u, v, yaw) relative to the block centre; min = block size needed (m).
PARKS = {
    "funfair": {"min": (48.0, 48.0), "pieces": [
        ("Fair_Gate", 0.0, -22.0, 0.0), ("Fair_FerrisWheel", 0.0, 12.0, 0.0), ("Fair_Carousel", -13.0, -6.0, 0.0),
        ("Fair_BumperCars", 12.0, -6.0, 0.0), ("Fair_Booth", -6.0, -16.0, 0.0), ("Fair_Booth", 6.0, -16.0, 0.0),
        ("Fair_Booth", 21.0, 6.0, 270.0), ("Veg_Birch", -20.0, 19.0, 0.0), ("Veg_Birch", 19.0, -19.0, 0.0),
        ("Veg_TreeDead", -21.0, -18.0, 0.0), ("Veg_Bush", 20.0, 20.0, 0.0), ("Veg_Weeds", -3.0, -12.0, 0.0),
        ("Veg_Weeds", 4.0, 2.0, 0.0), ("TrashBin", -3.0, -19.0, 0.0), ("TrashBin", 3.0, -19.0, 0.0)]},
    "stadium": {"min": (72.0, 60.0), "pieces": [
        ("Stadium_Pitch", 0.0, -6.0, 0.0), ("Stadium_Stand", 0.0, 22.0, 0.0), ("City_Clubhouse_Intact", -24.0, 24.0, 0.0),
        ("Stadium_Floodlight", 34.0, -26.0, 90.0), ("Stadium_Floodlight", 34.0, 14.0, 90.0),
        ("Stadium_Floodlight", -34.0, -26.0, 270.0), ("Stadium_Floodlight", -34.0, 14.0, 270.0),
        ("Veg_Birch", 26.0, 25.0, 0.0), ("Veg_Weeds", 17.0, 25.0, 0.0)]},
    "landfill": {"min": (48.0, 48.0), "pieces": [
        ("Landfill", 0.0, 0.0, 0.0), ("Wreck_GarbageTruck", 16.0, -22.0, 90.0), ("Dumpster", -8.0, -22.5, 0.0),
        ("Dumpster", -5.5, -22.5, 0.0), ("Veg_Birch", 20.0, 22.0, 0.0), ("Veg_TreeDead", -20.0, 22.0, 0.0),
        ("RatNest", -14.0, 22.5, 0.0), ("RatNest", 6.0, 22.5, 0.0), ("HorseCarcass", 2.0, -22.4, 90.0)]},
}
# Car jams (idea 2): blocking lines across straight street tiles from pieces with known Geometry
# (our wrecks and jersey barriers), one pedestrian gap; vanilla wrecks (CE types, verified names)
# as decoration away from the line - their sizes are not verified (P19).
JAM_BLOCKERS = {"Wreck_Van": (5.2, 2.1), "Wreck_Sedan": (4.2, 1.8), "Barrier_Concrete": (3.0, 0.6)}   # length, depth
JAM_GAP = 1.0                       # m: people pass, vehicles (>= 1.8 m wide) do not
JAM_DECOR = ["Land_Wreck_Ikarus_DE", "Land_Wreck_V3S_DE", "Land_Wreck_sed01_aban1_black_DE", "Land_Wreck_hb01_aban1_blue_DE",
             "Land_wreck_truck01_aban1_blue_DE", "Land_Wreck_offroad02_aban1_DE", "Land_Wreck_sed02_aban1_red_DE",
             "Land_Wreck_Volha_Police"]
VIADUCT = {"ramp_cells": 4, "height": 7.0}
