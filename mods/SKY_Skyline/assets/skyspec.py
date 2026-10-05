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
            {"name": "lootSecurity", "lootmax": 3, "categories": ["tools", "weapons"],
             "tags": ["floor", "shelves"],
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
