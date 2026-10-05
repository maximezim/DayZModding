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
    "small":  {"res0": 600, "res1": 300, "res2": 100, "geo_comps": 8, "geo_tris": 120, "sections_res0": 3},
    "medium": {"res0": 1200, "res1": 600, "res2": 150, "geo_comps": 12, "geo_tris": 200, "sections_res0": 4},
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
    "concpanel":      {"rvmat": rvmat("sky_concpanel"), "co": tex("sky_concpanel_co"),
                       "bands": {"reveal": (0.0, 0.2), "panel": (0.2, 1.0)}},
})
# Wall decals: render-only quads (no collision). The layout tool places them flush in
# front of a surface with Geometry (D16), at a per-type offset so overlapping decals
# never share a plane (perf batch-2 M2), and caps their count (DECAL_CAPS, hypothesis).
DECAL_OFFSET = {"Decal_Dirt": 0.015, "Decal_Cracks": 0.020, "Decal_Graffiti": 0.025}
DECAL_CAPS = {"per_tile": 6, "per_block": 40}
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
PROP_CAPS = {"per_floor": 25, "per_tower": 600, "aisle_min": 1.2}


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
