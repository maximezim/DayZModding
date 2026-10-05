# SKY_Skyline - Batch 4 (floor / roof variants, `sky_floors`) static QA gate

Date: 2026-10-05. Host: Linux, no DayZ / DayZ Tools / P: drive. These are static checks only and prove nothing about
in-game behaviour. Every asset stays **built-unverified**. This run changed no mod code, asset, config or generator.
It wrote only this file. Mutations were made in a scratch copy only.

Tools: Blender 4.2.23 LTS and ArmaToolbox (both in scratchpad), python3 with Pillow, `tools/assets/p3d_inspect.py`,
and the vanilla scripts dump (scratchpad `dzs/scripts`).

**Gated revision: `fcc7f4c`.** Its commit title is "Batch 3 ... re-gate fixes", but the tree also contains the WIP
batch 4 from `9a33796`. All results come from a clean `git archive fcc7f4c` snapshot (`scratchpad/qa4`).

**Verdict: GATE: FAIL.** There is 1 High finding (H1): 2 of the 4 apartments on `Land_SKY_Floor_Apartments` are sealed
and have no door from the hall. Every mechanical check passes (section 1). There are also 3 Medium findings and several
Low/Info findings (section 5).

## 1. Standard suite (snapshot `fcc7f4c`, cwd `mods/SKY_Skyline`)

| # | Command | Result |
|---|---|---|
| 1 | `python3 assets/check_assets.py` | exit 0, `44 checked, 0 fail, 5 over budget (hypotheses)`. New: `Floor_Apartments OVER geo comps 30 > 24; geo tris 360 > 300`, `Floor_Hotel OVER geo comps 38 > 24; geo tris 456 > 300`, `Floor_Mechanical PASS res=152 -> 128 -> 80 -> 8`, `Roof_Garden OVER res1 136 > 120; res0 sections 3 > 2`, `Roof_Mechanical OVER res1 136 > 120`. The 5th OVER is the pre-existing `TowerA_Core geo comps 81 > 80`. **The overruns match D32 exactly.** |
| 2 | `python3 assets/gen_configs.py --check` | exit 0, `up to date` |
| 3 | `python3 assets/gen_manifest.py --check` | exit 0 |
| 4 | `python3 economy/gen_economy.py --check` | exit 0, `up to date` |
| 5 | `blender -b --factory-startup -P assets/blender/test_kit.py` | exit 0, `KIT GEOMETRY TESTS: PASS (39 assets)`, which includes `module_checks` for the 5 new modules |
| 6 | `blender ... -P assets/blender/test_towera.py` | exit 0, `TOWER A GEOMETRY TESTS: PASS (81 core components checked)` |
| 7 | `build_floors.py`, `build_props.py`, `build_kit.py`, `build_towera.py -- --out <scratch>/addons`, then `cmp` | all 4 exit 0 (5 + 10 + 24 + 5 EXPORTED, 0 `EXPORT FAILED`). **44/44 P3Ds byte-identical** to the committed files. The regenerated `build_stats.json` and `build_stats_kit.json` are identical to the committed ones. |
| 8 | `python3 assets/textures/gen_textures.py --out <scratch>/tex` | exit 0 (1 min 17 s), 69 PNGs, 0 non-power-of-two |
| 9 | Texture/rvmat reference resolution (P3D + rvmat + config strings) | 88 `SKY_Skyline\...` refs (66 `.paa`), **0 unresolved**. Orphans unchanged: `sky_brick_co`, `sky_concpanel_co`, `sky_windows_co`. sky_floors uses carpet, concrete, foliage, glass, glassfar, metal, paver, tile and wallpaper. Non-SKY refs: penetration `bricks`, `metalplate` (verified), `concrete`, `glass` (P3, unverified); roadway `concrete_int.tga` (floors), `concrete_ext.paa` (roofs), both verified |
| 10 | `enscript_xref.py --vanilla dzs/scripts --mod addons/sky_scripts/scripts` | exit 0, `OK: 11 files, all calls/types resolve` (batch 4 adds no scripts) |
| 11 | `git diff 681ecdc fcc7f4c -- addons/sky_towera addons/sky_items` | **empty**. Tower A / keycard P3Ds, configs and model.cfg are unchanged, and the rebuild (#7) is byte-identical. |
| 12 | `git diff 681ecdc fcc7f4c -- assets/blender/build_towera.py` | 2 hunks. (a) The D34 `__main__` try/except -> `sys.exit(1)`, as documented. (b) `ELEVATOR_SLIDE_SIGN` in the elevator leaf axis (`build_towera.py:373-374`), which comes from batch 1 `929eaf1` (P2) and was gated then. With sign = 1 it is output-neutral (see #11). No other Tower A change. `skygeo.py` +89 lines are shared helpers (run_cli etc.), output-neutral per #7. PASS |
| 13 | `p3d_inspect.py [--json] addons/sky_floors/*.p3d` | exit 0, 10 LODs each (Res0-3, Shadow, Geometry, Memory, Roadway, View, Fire). Geometry props are `class=house, map=building, autocenter=0`. Masses are 40000 / 40000 / 45000 / 32000 / 34000. bbox floors y -0.30..3.20 and roofs y -0.30..1.10 (garden) / 2.40 (mechanical). There are 4 `occluder_00N` in each View Geometry. Roadway is 8 tris (4 slab quads) at y = 0 |

## 2. Stacking on the unchanged Tower A core (builder reasoning plus a scratch flood-fill in Blender)

| Check | Apartments | Hotel | Mechanical | Roof_Garden | Roof_Mechanical |
|---|---|---|---|---|---|
| Footprint +-12 x +-12 (Geometry) | PASS | PASS | PASS | PASS | PASS |
| Slab -0.30..0 (`T.floor_slab`, the same function as Tower A) | PASS | PASS | PASS | PASS | PASS |
| Walls/facade stop at 3.20 (next slab underside) | PASS (geo z max 3.20) | PASS | PASS (louvre 0..3.2) | n/a (max 1.10) | n/a (max 2.40, penthouse level) |
| Core hole = `CORE` x -3..3, y -4.5..4.5 (`CORE_HOLE` from build_towera) | PASS: 0 Geometry/View/Fire boxes over the footprint | PASS | PASS | PASS | PASS |
| Roadway not over the hole | PASS (0 verts inside; 4 slab quads only) | PASS | PASS | PASS | PASS |
| Occluders (4 slab planes, View Geometry) | PASS | PASS | PASS | PASS | PASS |
| Stair door clear zone (x -1.8..-0.6, y -5.7..-4.5) / elevator (x -0.6..0.6, y 4.5..5.7) | PASS | PASS | PASS | PASS | PASS |
| Elevator door reachable from stair door (player radius 0.3 m, z 0.1..1.9) | yes | yes | yes | yes | yes |
| Free floor reached from the core doors | **237.2 of 402.1 m2** | 400.0 / 400.0 | 401.4 / 401.4 | 346.8 / 346.8 | 385.6 / 385.6 |
| Unreached regions | **NW apt 82.5 m2 (x -11.6..-0.5, y 0.4..11.6); SE apt 82.4 m2 (x 0.4..11.6, y -11.6..-0.5)** | none | none | none | none |

### 2.1 Room-by-room door analysis

- **Apartments** (`build_floors.py:51-60`). The x-walls at y = +-7 run facade to facade. The y-walls at x = +-5.5 enclose the hall
  (|x| < 5.5, |y| < 7). Party walls are at x = 0 (|y| > 7) and y = 0 (|x| > 5.5). So each apartment is an L shape: one band
  plus one side strip, joined by its internal door at x +-(7..8) on the y = +-7 wall.
  - Hall door S (y = -7, x -1.5..-0.3) -> **SW**. Hall door W (x = -5.5, y -1..0) -> **SW** again. Hall door E (x = 5.5, y 0..1) -> **NE**.
    The N hall wall has only the two internal openings at x +-(7..8), which lie outside the hall.
  - **NW and SE have no opening to the hall. They are sealed (H1).** SW has two hall doors.
  - The W and E hall doors **open onto the end of a party wall**: the y = 0 party wall (y -0.125..0.125) butts against the
    opening, so the clear width is 0.875 m instead of 1.0 m (L1).
- **Hotel** (`build_floors.py:74-83`). The corridor is |x| < 5, |y| < 6.5 around the core. Its walls are at y = +-6.5 (full width) and
  x = +-5. Suites are x < -5 and x > 5. Guest rooms are y < -6.5 and y > 6.5, split at x = -6 / 0 / 6.
  - The inner rooms (x -6..0 and 0..6, doors x +-(3.5..4.5)) open onto the corridor. PASS.
  - **The corner rooms (x < -6 and x > 6, doors x +-(8.5..9.5)) open into the suites, not the corridor**, because the corridor stops at x = +-5.
    They are reachable, so not sealed, but 4 of the 8 "guest rooms" can only be entered through a suite (M1).
  - The suite doors (x = +-5, y -1..1, 2 m wide) are clear.
- **Mechanical floor**: open plan. The 4 plant units sit at the corners (2.2 m tall). Ducts are Res0 only at z 2.6..3.0 (L4).
- **Roofs**: parapet 1.1 m. The garden has 4 planters (0.5 m, Geometry/Fire, no View) and shrub cards (Res0 only, no collision).
  The mechanical roof has 4 HVAC units (1.5-2.4 m, Geometry/View/Fire). All roof areas are reachable.

### 2.2 Roof drops (D33)

`roof_drop_1..4` are at (-8,-2), (8,-2), (-8,2), (8,2), z 0.05 (`build_floors.py:30`). On both roofs: **0 Geometry boxes contain them, 0 lie within 1 m,
none is over the core (x +-3), and all are reachable**. PASS for the memory points.
**But the CE positions do not come from the memory points.** `placement/sky_layout.py:148` writes `cfgeventspawns` from `S.ROOF_DROPS`
(the helipad (+-8,+-8), `skyspec.py:223`). On these roofs, (+-8,+-8) lies inside a planter (e.g. bed x 6..11, y 6.5..11) or an HVAC unit
(e.g. x 5..9, y 6.5..10). See M3.

## 3. test_kit `module_checks` can fail (mutations in a scratch copy, `PYTHONDONTWRITEBYTECODE=1`, `__pycache__` cleared each run)

| Mutation (build_floors.py copy) | Result |
|---|---|
| Apartments S hall wall moved to y = -5 (across the stair door) | FAIL x3 `geo/view/fire ComponentNN blocks the core stair door` (caught) |
| `WT` + 0.2 (walls 3.4 m) on Hotel | FAIL `Geometry reaches z 3.40, next slab starts at 3.20` (caught) |
| HVAC unit at x -0.6..0.6, y 4.6..5.2 on Roof_Mechanical | FAIL x3 `blocks the core elevator door` (caught) |
| Footprint HW + 0.5 on Mechanical | FAIL `footprint (-12.5, 12.5, ...) != +-12 x +-12` (caught) |
| Extra Geometry slab over the core hole | FAIL `geo Component05 blocks the core core footprint` (caught) |
| Extra Geometry slab down to -0.5 | FAIL `slab underside -0.500 != -0.300` (caught) |
| Roadway quad with vertices inside the hole (-2..2, -4..4) | FAIL `Roadway covers the core hole` (caught) |
| **Roadway quad on the hole edges (-3..3, -4.5..4.5) or spanning it (-4..4, -5..5)** | **PASS: not caught** (M2) |
| **Roof drop moved to (-8,-8) (inside a planter) or (-1,-2) (over the core)** | **PASS: not caught** (M2) |
| **Apartments W hall door removed** | **PASS: not caught**. There is no reachability test, and the shipped H1 already passes (M2) |

After the mutations, the copy was restored: `diff` against the snapshot is empty and the full run gives `PASS (39 assets)`.

## 4. Config / model.cfg / manifest / decisions

- `addons/sky_floors/config.cpp`: `SKY_Skyline_Floors` `requiredAddons {"DZ_Data","SKY_Skyline_Textures","SKY_Skyline_Scripts"}` (same as TowerA).
  `Land_SKY_Floors_Base: HouseNoDestruct` scope 0, 5 classes scope 1. Model paths `SKY_Skyline\sky_floors\<lower>.p3d` match the files
  (there is no `$PBOPREFIX$`, so the default prefix applies). PASS.
- `model.cfg`: `CfgModels` has one class per P3D basename (`sky_floor_apartments` ... `sky_roof_mechanical`) on `Default`. No skeleton is needed (no doors). PASS.
- `gen_configs.py:121` maps `sky_floors -> SKY_Skyline_Floors`. `Build-SkyAssets.ps1:52` runs `build_floors.py`. PASS.
- Manifest `generated_kit` (`manifest.yaml:350-384`): all 5 are `category floor/roof`, `status: built-unverified`, and the budgets equal Tower A's. PASS.
  **Section A is stale.** `manifest.yaml:46,47,55,62,63` still list the same 5 classes as `status: planned`. These duplicate entries contradict
  `generated_kit` (L2).
- DECISIONS: **D31** matches the code for stacking, core hole, origin and "Tower A files not touched" (except D34). Its claim "test_kit enforces ...
  no Roadway over the core hole" holds only for vertices inside the hole (M2). **D32** overrun numbers match check_assets exactly
  (30/360, 38/456, 136 > 120 and 3 > 2 sections, 136 > 120). **D33** matches `ROOF_DROPS_CLEAR`, but see M3. **D34** matches #12.
- PENDING_VERIFICATION.md: P3 (concrete/glass penetration) applies to all 5 new P3Ds, but its asset list was not updated for batch 4 (L3).
- TESTING.md has no batch-4 section. The F4 list below must be merged before the in-game run (L3).

## 5. Findings

### High
- **H1 - Floor_Apartments: the NW and SE apartments are sealed (2 x 82.5 m2, no door from the hall or core).**
  Location: `assets/blender/build_floors.py:53-56`. The hall door openings are S (-1.5..-0.3) -> SW, W (y -1..0) -> SW, E (y 0..1) -> NE,
  and the N wall has none. Players, loot and AI can never enter the NW and SE apartments. This contradicts the module description
  "4 apartments around a hall ring" and the builder docstring "checked by test_kit.py".
  Likely fix (asset-pipeline): give each apartment one hall door that is not next to a party wall. For example: W wall `[(1.0, 2.0)]` -> NW,
  E wall `[(-2.0, -1.0)]` -> SE, N wall add `(0.3, 1.5)` -> NE. Keep S (-1.5..-0.3) -> SW. Then re-export the apartments P3D only.
  Changing the openings does not change the Geometry component count much.

### Medium
- **M1 - Floor_Hotel: the 4 corner guest rooms open into the suites, not the corridor** (`build_floors.py:74-83`). Doors x +-(8.5..9.5) on
  the y = +-6.5 walls lie outside the corridor (|x| < 5). Everything is reachable, but the layout does not match "corridor ring, 8 guest rooms + 2 suites".
  Fix: extend the corridor (move the suite walls / add a corridor spur), or treat the corner rooms as suite bedrooms and update the description.
- **M2 - test_kit gaps for the batch-4 rules** (`assets/blender/test_kit.py:99-127`):
  (a) No reachability check from the core doors, so H1 passes.
  (b) The Roadway-over-hole test is vertex-based, so a quad on or across the hole edges passes.
  (c) Roof-drop points are not checked (inside Geometry / over the core).
  (d) Occluders are not checked.
  Fix: add a coarse grid flood-fill from the stair/elevator door zones against Geometry boxes in z 0.1..1.9, and fail on unreached
  regions > 1 m2. Add a polygon/rect overlap for Roadway faces versus the hole. Require `roof_drop_N` outside every Geometry box and the core
  footprint (with 1 m clearance). Require 4 `occluder_*` in View.
- **M3 - Roof-drop CE positions ignore D33** (latent). `ROOF_DROPS_CLEAR` exists only in the builder (`build_floors.py:30`). The CE snippet
  comes from `S.ROOF_DROPS` (`placement/sky_layout.py:148`, `economy/README.md:40`), which is the helipad's (+-8,+-8). On a garden or mechanical
  roof, all 4 supply boxes would spawn inside planters / HVAC units. Today no tower places these roofs (`MODULE_CLASS` is fixed to Tower A), so it is not live yet.
  Fix: move the per-roof drop lists into `skyspec` (e.g. `KIT[...]["roof_drops"]`) and have both the builder and `sky_layout.py` read from there.

### Low
- **L1** - Apartments W/E hall doors butt against the y = 0 party wall end (clear width 0.875 m, not 1.0 m). This disappears with the H1 fix.
- **L2** - `manifest.yaml:46,47,55,62,63` still say `planned` for the 5 classes and duplicate the `generated_kit` entries. Set them to
  built-unverified with a pointer, or remove them. `generated_kit` also has no `open_items` noting the D32 overruns.
- **L3** - TESTING.md has no batch-4 section. The PENDING P3 asset list does not name the sky_floors P3Ds.
- **L4** - LOD/shadow simplifications (D32 cuts). Roof_Mechanical HVAC units (up to 2.4 m) and Roof_Garden planters/shrubs are missing from Res2/Res3, so watch for pop (F4-L*).
  Floor/roof Shadow Volumes cover only the slab and parapet: no shadow from the opaque mechanical louvre, partitions, planters or HVAC.
  Mechanical-floor ducts are Res0 only (no Geometry/Fire; above head height).
- **L5** - Mechanical louvre: the 4 side boxes overlap at the corners (coplanar end faces over a 0.12 m strip). Possible z-fighting at the building corners in Res0-2.

### Info
- The new classes have no `skyspec.LOOT` points, no mapgroupproto entries and no placement path (`tower_levels` / `MODULE_CLASS`). They can be spawned only by hand for now.
- `light_1..4` / `floor_center` memory points are present on floors. Nothing consumes them yet.

## 6. In-game test list (batch 4, F4-xx). Status: all **NOT RUN**

Setup for all items: diag (`Build-And-Run.ps1 -ModName SKY_Skyline -FilePatching`) and dedicated (`-Mode Dedicated`, signed). Spawn a
test stack by hand at a flat site: Tower A lobby + core at T. Put the variant under test at each core stop z = 7.0, 10.5, 14.0, 17.5, 21.0
(floors) and 24.5 (roof), using objectSpawnersArr with the same yaw as the core. Logs: newest `script_*.log`, `*.RPT` and `*.ADM` per profile.
Expected clean logs: no `Cannot open object SKY_Skyline\sky_floors\...`, no `missing in CfgPatches`, no `SCRIPT (E)`.

| ID | Module | Steps (diag, then dedicated) | Expected | Evidence | Result |
|---|---|---|---|---|---|
| F4-01 | all 5 | Spawn each class once; check the RPT | Loads with no missing model/texture/rvmat lines. Dedicated: no signature kick for `sky_floors.pbo` | RPT lines + timestamps | |
| F4-02 | Apartments, Hotel, Mechanical | Stack the variant at every core stop (5 floors) | Slabs meet the core walls with no visible gap. The stair door (south face, x -1.8..-0.6) and elevator door (north face) open onto the floor at every stop | screenshot per stop | |
| F4-03 | Roof_Garden, Roof_Mechanical | Place it at the roof stop (z 24.5) on the core | The core penthouse rises through the hole. Stair and elevator roof-stop doors open onto the roof | screenshot | |
| F4-04 | all floors | Stand on the slab beside the core and above the module seam. Crouch, prone, roll, and drop items at 4 spots per floor | **Nothing falls through the seam** between modules (slab -0.3..0 meets the walls' top 3.2) or the slab/core gap | | |
| F4-05 | all floors | Jump/vault against the partition tops and the facade at ceiling height | No climbing into the slab above. Walls stop flush at 3.2 | | |
| F4-06 | Apartments | Walk from the stair door to every apartment | **Expected to FAIL until H1 is fixed:** NW and SE cannot be entered. After the fix, each apartment has one 1.0 m x 2.1 m hall door and an internal door between band and strip | screenshots | |
| F4-07 | Hotel | Walk the corridor and enter all 8 rooms + 2 suites | The inner rooms open off the corridor. The corner rooms are entered via the suites (M1) unless the layout is changed | | |
| F4-08 | Mechanical | Walk around all 4 plant units and along the louvre | The units are solid (2.2 m). There are no openings in the louvre. Ducts are visual only | | |
| F4-09 | Roofs | Walk the parapet perimeter. Climb the planters (0.5 m) and HVAC units (1.5-2.4 m) | Parapet 1.1 m and solid. Planters can be stepped onto. Shrubs have no collision | | |
| F4-10 | Apartments, Hotel | Navmesh visualisation after spawn (`ProcessMarkedObjectsForPathgraphUpdate`) | Navmesh connects the hall/corridor to every room through each door opening (1.0 m; the W/E apartment doors 0.875 m). It does not cross partitions or the facade | screenshots | |
| F4-11 | Apartments, Hotel, Mechanical | Aggro 3 infected on the floor, then run from the core into the farthest room and around the plant units | Infected follow through the door openings and around the units. They do not walk through partitions or get stuck on the 0.875 m doors | | |
| F4-12 | Roofs | Aggro infected from the stair door to each roof corner | They path around planters/HVAC units to the corners | | |
| F4-13 | all floors | View Geometry: A in a room, B in the hall behind a partition; then A on floor N, B on floor N+1 | Partitions and slabs block sight both ways (AI does not detect through them). The louvre blocks sight (mechanical) | | |
| F4-14 | all | Fire Geometry: shoot the partitions (bricks), slab (concrete, P3), louvre/units/HVAC (metalplate), and facade glass (P3) | Penetration and impact effects match the material. Rounds do not leak between floors | | |
| F4-15 | Roofs | Merge a `StaticSKYRoofDrop` with this roof's drop positions **from `roof_drop_N` (+-8, +-2)**, not `S.ROOF_DROPS` (M3). Wipe storage, restart | The supply box sits on the open roof east/west of the core, not inside a planter/unit and not over the core | RPT: no event errors | |
| F4-16 | all | LOD switches: walk away 10 -> 500 m, and use the diag LOD display | Res0 -> 1 -> 2 -> 3 with no holes. Watch for pop of HVAC units, planters and shrubs at Res1 -> 2 (L4). The mechanical floor reads as a louvre band at Res3 | screenshots per LOD | |
| F4-17 | Mechanical | Corner close-up of the louvre | No z-fighting on the corner strip (L5) | | |
| F4-18 | all | Shadows in sun | The slab/parapet shadows are correct. Note the missing shadows from partitions/louvre/HVAC (L4) | | |
| F4-19 | all | Relog and server restart | Modules are static (objectSpawnersArr) and reappear identically. No persistence issues | | |
| F4-20 | all | 2 players on different floors of the same stack, dedicated | Both see the same geometry. No desync at the module seams | | |
| F4-21 | all | Death on the floor/roof (fall from the parapet, shot) | The body stays on the slab and does not fall through | | |
| F4-R | Tower A (regression) | Repeat S-10, C-04, C-05 and E-02 on the unchanged office stack | Same results as before batch 4 (Tower A P3Ds are byte-identical) | | |
