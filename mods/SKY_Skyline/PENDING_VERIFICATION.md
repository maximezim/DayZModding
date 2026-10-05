# Pending verification (needs DayZ / DayZ Tools on Windows)

Every untested assumption is a **named parameter in `assets/skyspec.py`**. Nothing is hard-coded.
After testing, change the value there, regenerate, and rebuild:
```
python assets/gen_configs.py ; python economy/gen_economy.py
blender -b -P assets/blender/build_towera.py -- --out addons     (and build_kit.py / build_floors.py)
```
Asset lists below are kept current per batch.

| # | Parameter (skyspec.py) | Assumption | Assets depending on it | One-line fix once known |
|---|---|---|---|---|
| P1 | `DOOR_SWING_SIGN` (+ `DOOR_OPEN_ANGLE`) | `+1` opens hinged doors *into* the room/cabinet | Lobby `door_sec` (model.cfg `Door_Sec`); every hinged prop door (lockers, cabinets, vending flap; see manifest `uses: [DOOR_SWING_SIGN]`) | `DOOR_SWING_SIGN = -1` → `gen_configs.py` |
| P2 | `ELEVATOR_SLIDE_SIGN` | `+1` slides elevator leaves apart (a → −X, b → +X) | `sky_towera_core.p3d` (memory axes `elev_door_lN_a/b_axis`) | `ELEVATOR_SLIDE_SIGN = -1` → re-export core (`build_towera.py --only core`) |
| P3 | `PENETRATION["concrete"]`, `PENETRATION["glass"]` | `dz\data\data\penetration\concrete.rvmat` / `glass.rvmat` exist | Fire Geometry of every module and prop using concrete or glass | point to the real file names → re-export P3Ds |
| P4 | `ENV_MAP` | `dz\data\data\env_land_co.paa` exists (Super shader Stage7) | every SKY rvmat | set the real path → `gen_configs.py` |
| P5 | `ARMOR_EXPLOSION_CLASS` | explosion damage armor class is called `FragGrenade` | Lobby security door DamageSystem | rename → `gen_configs.py` |
| P6 | `ROADWAY_ASPHALT` | no verified asphalt surface; roads use the verified `concrete_ext` surface sound | street kit Roadway LODs | set a vanilla asphalt roadway texture → re-export street kit |
| P7 | `EMISSIVE_LAMP`, `EMISSIVE_WINDOW` | rvmat `emmisive[]` strength reads as "lit" at night without blooming | street lights, traffic lights, lit window sets | tune the numbers → `gen_configs.py` |

Behaviour (not parameters) still to observe in-game: see `TESTING.md` and `AFTER_TESTING.md`.
