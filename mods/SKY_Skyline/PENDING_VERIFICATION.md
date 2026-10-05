# Pending verification (needs DayZ / DayZ Tools on Windows)

Every untested assumption is a **named parameter in `assets/skyspec.py`**. Nothing is hard-coded.
After testing, change the value there, regenerate, and rebuild:
```
python assets/gen_configs.py ; python economy/gen_economy.py
blender -b -P assets/blender/build_towera.py -- --out addons     (and build_kit.py; build_props.py / build_floors.py from batches 3-4)
```
Asset lists below are kept current per batch.

| # | Parameter (skyspec.py) | Assumption | Assets depending on it | One-line fix once known |
|---|---|---|---|---|
| P1 | `DOOR_SWING_SIGN` (+ `DOOR_OPEN_ANGLE`) | `+1` = engine turns a positive angle by the **left-hand rule** about `<door>_axis` (point 1 → 2). Then the lobby door opens **into the room** and every prop door **outward** (per-door `orient`, D24; `test_kit.py` checks both). Judge it on the lobby door (D-01) first | Lobby `door_sec` (model.cfg `Door_Sec`); props `Land_SKY_Locker` (`locker_door1..3`), `Land_SKY_ExtinguisherCabinet` (`cab_door`), `Land_SKY_VendingMachine` (`flap`, scaled 0.6) - model.cfg `<door>_rot` | lobby door opens outward → `DOOR_SWING_SIGN = -1` → `python3 assets/gen_configs.py` (fixes lobby + all props together, no re-export). Lobby right but one prop door wrong → flip that door's `orient` in `skyspec.py` |
| P2 | `ELEVATOR_SLIDE_SIGN` | `+1` slides elevator leaves apart (a → −X, b → +X) | `sky_towera_core.p3d` (memory axes `elev_door_lN_a/b_axis`) | `ELEVATOR_SLIDE_SIGN = -1` → re-export core (`build_towera.py --only core`) |
| P3 | `PENETRATION["concrete"]`, `PENETRATION["glass"]` | `dz\data\data\penetration\concrete.rvmat` / `glass.rvmat` exist | Fire Geometry of every module and prop using concrete or glass (incl. `ExtinguisherCabinet` glass door, BusStop glass) | point to the real file names → re-export P3Ds |
| P4 | `ENV_MAP` | `dz\data\data\env_land_co.paa` exists (Super shader Stage7) | every SKY rvmat | set the real path → `gen_configs.py` |
| P5 | `ARMOR_EXPLOSION_CLASS` | explosion damage armor class is called `FragGrenade` | Lobby security door DamageSystem; prop door DamageSystems (Locker, ExtinguisherCabinet, VendingMachine) | rename → `gen_configs.py` |
| P6 | `ROADWAY_ASPHALT` | no verified asphalt surface; roads use the verified `concrete_ext` surface sound | street kit Roadway LODs | set a vanilla asphalt roadway texture → re-export street kit |
| P8 | `ROAD_GEO_THICKNESS` | 0.3 m Geometry slabs under road tiles do not snag vehicle wheels at tile seams | all road/street/intersection tiles | `ROAD_GEO_THICKNESS = 0.05` → re-export street kit |
| P7 | `EMISSIVE_LAMP`, `EMISSIVE_WINDOW` | rvmat `emmisive[]` strength reads as "lit" at night without blooming | street lights (`sky_lamp`), lit window sets (batch 2). Traffic lights are NOT emissive (D8). | tune the numbers → `gen_configs.py` |

Behaviour checks without a parameter (see TESTING.md):
- B1 Render-only decal objects (`Decal_*`, category `decal`) have **no Geometry LOD**. Confirm a `HouseNoDestruct` P3D without Geometry spawns and renders via objectSpawnersArr. If not, give them a tiny Geometry far below the decal (fix in `build_kit.build_decal`).
- B2 The manhole (`flat`) has only Roadway (no Geometry). Same check.
- B3 Find a vanilla building rvmat whose Stage3 uses an `_mc` macro map (`P:\DZ\structures\...\data\*.rvmat`). If one exists, add a low-frequency grime `_mc` to `sky_brick` / `sky_concpanel` / kit concrete in `gen_configs.rvmat_super` (one line per material) and reduce `DECAL_CAPS`.
- B5 Prop doors: confirm a child config class (e.g. `Land_SKY_Locker`) resolves to script class `Land_SKY_Props_Base` (check with a lockpick: no lock action on a locker door). If not, generate one empty `class Land_SKY_<Prop> extends Land_SKY_Props_Base {}` per door prop.
- B4 Lit window cells: check that dark (unlit) cells of `sky_windows_co` do not glow under `sky_windows_lit` (emissive not modulated by texture). If they glow, split the lit set into its own atlas.

Behaviour (not parameters) still to observe in-game: see `TESTING.md` and `AFTER_TESTING.md` (written in batch 6).
