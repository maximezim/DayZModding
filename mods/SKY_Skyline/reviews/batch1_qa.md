# SKY_Skyline - Batch 1 (street kit) static QA gate

Date: 2026-10-05. Host: Linux, no DayZ / DayZ Tools / P: drive. Static checks only; nothing here
proves in-game behaviour. No mod code, asset, config or generator was modified by this run.

Tools: Blender 4.2.23 LTS (scratchpad), ArmaToolbox (`ARMATOOLBOX_PATH` scratchpad), pwsh (scratchpad),
vanilla scripts dump (scratchpad `dzs/scripts`).

**Verdict: GATE: PASS** (no Critical/High findings; 1 Medium and several Low/Info items below).

## 1. Commands and results (cwd `mods/SKY_Skyline` unless noted)

| # | Command | Result |
|---|---|---|
| 1 | `python3 assets/check_assets.py` | exit 0. `23 checked, 0 fail, 2 over budget (hypotheses)`: `Land_SKY_TowerA_Core OVER geo comps 81 > 80` (pre-existing, same as `qa_static_run.md` #2) and `Land_SKY_Intersection_T OVER res0 sections 4 > 3` (new, documented as DECISIONS D9). All 18 street classes PASS. |
| 2 | `python3 assets/gen_configs.py --check` | exit 0, `up to date` |
| 3 | `python3 assets/gen_manifest.py --check` | exit 0 (silent on success) |
| 4 | `python3 economy/gen_economy.py --check` | exit 0, `up to date` |
| 5 | `blender -b --factory-startup -P assets/blender/test_kit.py` | exit 0, `KIT GEOMETRY TESTS: PASS (18 assets)`; no error/warn/traceback lines |
| 6 | `blender -b --factory-startup -P assets/blender/test_towera.py` | exit 0, `TOWER A GEOMETRY TESTS: PASS (81 core components checked)` |
| 7 | `python3 tools/assets/enscript_xref.py --vanilla <scratch>/dzs/scripts --mod addons/sky_scripts/scripts` | exit 0, `OK: 10 files, all calls/types resolve` (sky_scripts unchanged in this batch) |
| 8 | `pwsh -NoProfile -File tools/build/Build-Mod.ps1 -ModName SKY_Skyline -DryRun` | exit 0. `PBO 'sky_street'  prefix=SKY_Skyline\sky_street  binarize=True`, packer line `P://SKY_Skyline/sky_street ... -prefix=SKY_Skyline\sky_street ... -project=P:\ -clear`. `sky_textures` and `sky_scripts` packonly, `sky_towera`/`sky_items` binarized. `build/` deleted afterwards (verified absent). |
| 9 | `git diff --stat HEAD -- mods/SKY_Skyline/addons/sky_towera mods/SKY_Skyline/addons/sky_items` | **empty**; `git status --short` on both folders also empty. |
| 10 | Extra: regenerated all P3Ds into scratchpad (`build_towera.py -- --out <scratch>`, `build_kit.py -- --out <scratch>`) and `cmp` against committed files | all 23 P3Ds byte-identical (18 street, 4 Tower A, keycard): committed P3Ds are fresh and generation is deterministic. |
| 11 | Extra: `gen_textures.py --out <scratch> --size 256` | exit 0; produced the name list used in section 2.2. |

## 2. sky_street cross-checks

### 2.1 Config / model.cfg
- 18 `model=` paths `SKY_Skyline\sky_street\<name>.p3d` -> all 18 files exist under `addons/sky_street/`. PASS
- Every CfgVehicles class is prefixed `Land_SKY_` (`Land_SKY_Street_Base` scope 0, 18 scope 1 kit classes, `Land_SKY_Billboard_A..D`). PASS
- CfgPatches `SKY_Skyline_Street`, `requiredAddons[] = {"DZ_Data","SKY_Skyline_Textures","SKY_Skyline_Scripts"}`; both SKY patch names exist (`sky_textures`, `sky_scripts` config.cpp). PASS
- Manifest `generated_kit`: 18 entries, 18 `status: built-unverified`, every `p3d:` path exists, names match the 18 config classes exactly. PASS

### 2.2 Textures / rvmats referenced by the street P3Ds (`p3d_inspect.py --json`, all LODs)
SKY PAAs - all produced by `gen_textures.py`:
`sky_asphalt_co, sky_atlas_co, sky_billboard_a_co, sky_concrete_co, sky_foliage_ca, sky_glass_ca, sky_glassfar_co, sky_metal_co, sky_paver_co, sky_roadmark_ca, sky_rust_co` - PASS.

SKY rvmats - all committed in `addons/sky_textures/data/`:
`sky_asphalt, sky_atlas, sky_billboard, sky_concrete, sky_foliage, sky_glass, sky_glassfar, sky_lamp, sky_metal, sky_paver, sky_roadmark, sky_rust` - PASS. Every SKY texture referenced inside these rvmats is also a generator output; the rest are procedural `#(argb...)` / `#(ai...)`.

Procedural: `#(argb,8,8,3)color(1,0.95,0.85,1,CO)` (street light lamp face, with `sky_lamp.rvmat`, `emmisive[] = {1, 0.92, 0.75, 1}`).

`dz\` paths - **must be verified on P:** (none can be checked here):
| Path | Used in | Status |
|---|---|---|
| `dz\data\data\penetration\concrete.rvmat` | Fire Geometry: barrier_concrete, curb, intersection_4way/_t, planter, road_crossing/_straight, sidewalk, sidewalk_corner | unverified (PENDING P3) |
| `dz\data\data\penetration\glass.rvmat` | Fire Geometry: busstop | unverified (PENDING P3) |
| `dz\data\data\penetration\metalplate.rvmat` | Fire Geometry: barrier_steel, billboard, busstop, dumpster, manhole, streetlight, trafficlight, wreck_sedan, wreck_van | verified earlier (qa_static_run) |
| `dz\surfaces\data\roadway\concrete_ext.paa` | Roadway: road_straight/_crossing, intersection_4way/_t, sidewalk, sidewalk_corner | verified earlier; asphalt sound is a placeholder (PENDING P6) |
| `dz\data\data\env_land_co.paa` | Stage7 of every SKY rvmat | unverified (PENDING P4) |

### 2.3 Billboard
- `camo` selection present in Resolution 0, 1 and 2 of `sky_billboard.p3d` (4 points / 1 face each). PASS
- `sky_street/model.cfg`: `class sky_billboard: Default { sections[] = {"camo"}; }`. PASS
- Variant textures `sky_billboard_a/b/c/d_co.paa` -> generator outputs `sky_billboard_a_co .. sky_billboard_d_co` exist. PASS

## 3. Findings

| ID | Sev | Finding | Evidence | Owner |
|---|---|---|---|---|
| B1-01 | Medium | No `Shadow Volume` LOD on any of the 18 street P3Ds (Tower A modules have one). Tall props (street light 8 m, traffic light, bus stop, billboard, wrecks, dumpster) will most likely cast no or wrong shadows. Not listed in DECISIONS.md; `check_assets.py` only requires Shadow for enterable modules, so the gate does not catch it. | p3d_inspect LOD lists, e.g. `sky_streetlight.p3d ['Resolution 0','Resolution 1','Resolution 2','Geometry','Memory','Fire Geometry']` | asset-pipeline (add shadow LOD or record a decision) |
| B1-02 | Low | Unverified vanilla paths used by the new kit: `penetration\concrete.rvmat`, `penetration\glass.rvmat`, `env_land_co.paa` (already tracked as P3/P4). | table 2.2 | asset-pipeline on P: |
| B1-03 | Low | `Land_SKY_Wreck_Sedan` has no View Geometry while `Wreck_Van` (similar size) has one; AI/player view occlusion may differ between the two wrecks. | sedan LODs `[Res0-2, Geometry, Fire Geometry]`; van adds `View Geometry` | asset-pipeline |
| B1-04 | Low | PENDING_VERIFICATION.md references files that do not exist: `AFTER_TESTING.md` and `build_floors.py`. | `ls` -> No such file | doc owner |
| B1-05 | Low | PENDING P7 lists "traffic lights" as depending on `EMISSIVE_LAMP`, but D8 / config comment say traffic lights have no emissive, and their P3D uses only `sky_atlas`/`sky_rust`. Doc inconsistency. | PENDING_VERIFICATION.md P7; config.cpp `Land_SKY_TrafficLight` comment | doc owner |
| B1-06 | Low (tooling) | `Build-Mod.ps1` copies every root file of the mod folder except README into `build/@SKY_Skyline/`: dry run produced `DECISIONS.md, PENDING_VERIFICATION.md, SLICE_REPORT.md, TESTING.md` next to `mod.cpp`. Internal dev docs would ship. | `Build-Mod.ps1:111-113`; dry-run file list | tooling |
| B1-07 | Info | `Land_SKY_Intersection_T` 4 sections > road budget 3 (documented D9); `TowerA_Core` geo comps 81 > 80 (pre-existing). | check_assets output | perf-engineer |
| B1-08 | Info | `Land_SKY_Billboard` (base, scope 1) and `Land_SKY_Billboard_A` render identically (both use `sky_billboard_a_co.paa`). Harmless; the layout should use one of them consistently. | config.cpp | enforce-coder / layout |
| B1-09 | Info | Street light memory points `light`/`light_dir` exist but are unused (D6, intended). `requiredAddons` includes `SKY_Skyline_Scripts` though street classes have no script class (harmless, only affects load order). | config.cpp, build_kit.py:188-189 | - |

## 4. In-game test items needed (per new asset type)

Run each in diag (`Build-And-Run.ps1 -ModName SKY_Skyline -FilePatching`, spawn via objectSpawnersArr / debug) and once in Dedicated (signed). Watch RPT for `Cannot open object`, missing texture/rvmat, `Updating base class`; script log must stay clean.

**Road modules** (Road_Straight, Road_Crossing, Intersection_4Way, Intersection_T)
- Load with no RPT errors; textures, road markings (`_ca` alpha) render without z-fighting on the 0.3 m slab.
- Modules snap on the 12 m grid with no gaps/seams; walk and drive (car) across tile joints without bumps or falling through.
- Roadway: walking and driving sound/surface (concrete_ext placeholder, P6); AI zombies path across tiles (navmesh ECE_UPDATEPATHGRAPH).
- Bullets: impact effect/penetration (concrete.rvmat, P3).
- LOD switching distance and draw calls at an intersection cluster (Intersection_T has 4 sections).

**Sidewalks / curb / manhole** (Sidewalk, Sidewalk_Corner, Curb, Manhole)
- Step-up from road (+0.15 m) is walkable without stuck/jitter; vehicles climb or are blocked as expected.
- Paver texture scale; corner piece aligns with sidewalk and intersection; manhole decal sits flush (no flicker).

**Street furniture** (StreetLight, TrafficLight, BusStop, Dumpster, Planter, Barrier_Concrete, Barrier_Steel)
- Collision: player cannot walk through; vehicle hits (static, no destruction - HouseNoDestruct).
- Street light: emissive lamp reads as lit at night without bloom (P7); no dynamic light expected (D6). Traffic light: static face, no emissive.
- Bus stop: glass transparency (`_ca`), bullets pass glass / stop on metal (glass.rvmat P3); bench not walk-through.
- Planter foliage alpha renders (no black fringes); barriers block vehicles, steel barrier thin parts are shootable through gaps.
- Shadows of all tall props (B1-01) day and night.

**Wrecks** (Wreck_Sedan, Wreck_Van)
- Collision and fire geometry match visuals; player can take cover; AI line of sight through/around sedan vs van (B1-03).
- They are static objects (not CarScript): no inventory, no vehicle actions.

**Billboard** (Land_SKY_Billboard, _A.._D)
- Each variant shows its own poster via `hiddenSelectionsTextures` on a static Land_ object, on all 3 Res LODs (check at distance).
- Poster side only (camo is 1 face); back face shows rust/metal.

**Edge cases (all kit assets)**
- Server restart: objects respawn from objectSpawnersArr in the same place; no duplicates after restart.
- Relog / multiple players: both clients see same objects and billboard variants (texture is config-driven, nothing synced).
- Dedicated (verifySignatures=2, BattlEye=1, no filePatching): `sky_street.pbo` signed and loads, no `Modified data` kicks.

**Regression**
- Tower A modules and keycards behave exactly as in `TESTING.md` (P3Ds byte-identical, check 9/10).
- Vanilla roads/buildings nearby: no z-fighting with terrain roads, vanilla street lights unaffected.
