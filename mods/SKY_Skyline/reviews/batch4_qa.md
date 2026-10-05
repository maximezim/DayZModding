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

---

## Re-gate (20746e8)

Date: 2026-10-05. Static checks only. Nothing ran in DayZ, and every asset stays **built-unverified**. All results come from a clean
`git archive 20746e8` snapshot (`scratchpad/qa4b`). Mutations ran on throw-away copies of `assets/` (`scratchpad/qa4b_mut`, rebuilt from the
snapshot before each run). Afterwards `git archive 20746e8 | tar -d` against the snapshot reported no differences. This run changed no mod code
and appended only this section.

**Verdict for 20746e8: GATE: PASS.** H1 is fixed and independently confirmed. There are no High or Medium findings. 3 Low test-coverage gaps
and the known-latent M3 (Batch 5) remain.

> **Note:** HEAD moved to `226f4c0` ("security re-gate fixes") during this run. That commit changes the apartments, hotel and both roof P3Ds.
> It **reverts** perf item (4) "Geometry without lintels" (D37: Apartments Geometry 40 comps, Hotel 38) and changes roof Res3 to a band plus a lid at z = 0.
> This verdict covers `20746e8` only, so `226f4c0` needs its own QA pass. A quick, non-gating look at the committed HEAD P3Ds with the flood fill
> from R2: all 4 changed modules are fully reachable at r = 0.30 and r = 0.49. Geometry lintels are 12 (apartments) and 10 (hotel). Roof Res3 is still 5 faces / 10 tris / 1 section.

### R1. Standard suite (cwd `mods/SKY_Skyline`, `PYTHONDONTWRITEBYTECODE=1`)

| # | Command | Result |
|---|---|---|
| 1 | `python3 assets/check_assets.py` | exit 0, `44 checked, 0 fail, 5 over budget (hypotheses)`: `Floor_Apartments geo comps 28 > 24; geo tris 336 > 300`, `Floor_Hotel geo comps 28 > 24; geo tris 336 > 300`, `Floor_Mechanical PASS res=152 -> 128 -> 80 -> 8`, `Roof_Garden res1 128 > 120; res0 sections 3 > 2`, `Roof_Mechanical res1 128 > 120`, plus the pre-existing `TowerA_Core geo comps 81 > 80`. Res3: floors 8 tris, roofs 10 tris |
| 2 | `gen_configs.py --check` / `gen_manifest.py --check` / `economy/gen_economy.py --check` | all exit 0 (`up to date`) |
| 3 | `blender -b --factory-startup --python-exit-code 1 -P assets/blender/test_kit.py` | exit 0, `KIT GEOMETRY TESTS: PASS (39 assets)` |
| 4 | `... -P assets/blender/test_towera.py` | exit 0, `TOWER A GEOMETRY TESTS: PASS (81 core components checked)` |
| 5 | `build_floors / build_props / build_kit / build_towera -- --out scratch/qa4b_rb/addons`, then `cmp` | all exit 0. 5 + 10 + 24 + 5 `EXPORTED`, 0 `EXPORT FAILED`. **44/44 P3Ds byte-identical** to the committed files. The regenerated `build_stats.json` and `build_stats_kit.json` are identical |
| 6 | `gen_textures.py --out scratch/qa4b_tex` | exit 0, 1 min 18 s, 69 PNGs, 0 non-power-of-two. **69/69 pixel files byte-identical to the fcc7f4c gate run** |
| 7 | Reference resolution (all P3D textures/materials, config and rvmat strings) | 86 `SKY_Skyline\...` refs (64 `.paa`), **0 unresolved**. Orphans are unchanged (`sky_brick_co`, `sky_concpanel_co`, `sky_windows_co`). sky_floors uses carpet, concrete, foliage, glass, glassfar, metal, paver, tile and wallpaper, plus vanilla `bricks`/`metalplate` (verified), `concrete`/`glass` penetration (P3) and roadway `concrete_int.tga`/`concrete_ext.paa` |
| 8 | `enscript_xref.py --vanilla dzs/scripts --mod addons/sky_scripts/scripts` | exit 0, `OK: 11 files, all calls/types resolve` |
| 9 | Tower A vs `681ecdc` | `git diff 681ecdc 20746e8 -- addons/sky_towera addons/sky_items` is empty. All 10 files pass `sha256sum -c` against the baseline list. The rebuild (#5) is byte-identical. `build_towera.py` has no change since `fcc7f4c` |

### R2. H1 - independent flood fill (`scratchpad/qa4b_flood.py`, reads the exported MLOD P3Ds directly and shares no code with builders or test_kit)

Method: parse the Geometry LOD components. Block every component that spans body height (z 0.1..1.9) and the core footprint (x +-3, y +-4.5).
Inflate the blockers by the player radius r. Seed the stair (x -1.8..-0.6, y -5.7..-4.5) and elevator (x -0.6..0.6, y 4.5..5.7) clear zones,
then flood with 4-connectivity. **r = 0.30 on a 0.05 m grid** gives walkability. **r = 0.49 on a 0.01 m grid** checks that every room is reachable through openings >= 0.98 m.
In addition, each partition gap is measured and any other body-height box within 0.3 m of the wall line is subtracted to get the clear width.
Sanity check: on the old `fcc7f4c` apartments P3D the tool reproduces H1 (`82.5 m2 x -11.6..-0.5 y 0.4..11.6`, `82.4 m2 x 0.4..11.6 y -11.6..-0.5`) and L1 (`x=-5.500 -1.000..0.000 gap 1.000 clear 0.875 <1.0!`).

| Module | r = 0.30: free / reached | r = 0.49: free / reached | Unreached > 1 m2 | Door clear widths |
|---|---|---|---|---|
| Floor_Apartments | 404.3 / 404.3 m2 | 341.3 / 341.3 m2 | none | Hall S/N y = +-7: x -1.5..-0.3 and 0.3..1.5 = **1.200**. Hall W/E x = +-5.5: y -1.2..-0.2 and 0.2..1.2 = **1.000** (the party-wall butt is gone, so L1 is fixed). Internal x +-(7..8) = 1.000 |
| Floor_Hotel | 400.0 / 400.0 | 335.9 / 335.9 | none | Rooms y = +-6.5 at x +-(3.5..4.5) and +-(8.5..9.5) = 1.000. Suites x = +-5, y -1..1 = 2.000 |
| Floor_Mechanical | 401.4 / 401.4 | 362.0 / 362.0 | none | open plan |
| Roof_Garden | 367.2 / 367.2 | 328.3 / 328.3 | none | open |
| Roof_Mechanical | 385.6 / 385.6 | 348.2 / 348.2 | none | open |

Each apartment has 2 hall doors, as D35 says: SW = S(-1.5..-0.3) + W(-1.2..-0.2), NW = N(-1.5..-0.3) + W(0.2..1.2),
SE = S(0.3..1.5) + E(-1.2..-0.2), NE = N(0.3..1.5) + E(0.2..1.2). **H1: FIXED (PASS).**

### R3. test_kit new checks vs mutations (`test_kit.py -- --only <module>`)

| Mutation | Expected | Result |
|---|---|---|
| a1 Apartments hall walls reverted to the fcc7f4c openings (H1) | fail | FAIL x2 `91.2 m2 unreachable ... (near x -11.8, y 0.2)` and `(near x 0.2, y -11.8)`: **caught** |
| a2 NW apartment's two hall doors removed | fail | FAIL `91.2 m2 unreachable (near x -11.8, y 0.2)`: **caught** |
| a3 only the N-wall NW door removed (NW still has its W door) | pass | PASS (correct negative) |
| a5 Mechanical: 2 extra Geometry walls fence off the NW corner | fail | FAIL `28.8 m2 unreachable`: **caught** |
| a6 Hotel: west suite door removed | fail | FAIL `137.2 m2 unreachable`: **caught** |
| **a4 NW doors narrowed to 0.3 m (N -0.6..-0.3, W 0.2..0.5)** | fail | **PASS: not caught** (L-R1) |
| b1 Roadway quad spanning the hole (-4..4, -5..5) | fail | FAIL `a Roadway face covers the core hole`: **caught** (was M2(b)) |
| b2 Roadway quad on the hole edges (-3..3, -4.5..4.5) | fail | **caught** |
| b3 Roadway quad that overlaps the hole edge with no vertex inside (-5..5, 4..6) | fail | **caught** |
| b4 Roadway quad that only touches the hole edge (-5..5, 4.5..6) | pass | PASS (correct negative) |
| c1 / c2 `occluder_004` removed (Hotel) / `occluder_001` removed (Roof_Mechanical) | fail | FAIL `3 slab occluders (< 4)`: **caught** |
| **c3 extra `occluder_005` over the core hole** | fail | **PASS: not caught** (count only, L-R3) |
| d1 `ROOF_DROPS_CLEAR[0]` = (-8, -8) (inside planter / HVAC) | fail | FAIL `roof_drop_1 crate overlaps Geometry Component09` on both roofs: **caught** |
| d3 drop at (-10.2, -2) (crate 1.05 m from the parapet) | fail | FAIL `crate closer than 1 m to the parapet` on both: **caught** |
| d4 drop at (-10.0, -2) (exactly 1.25 m) | pass | PASS (correct boundary) |
| d5 builder writes x + 0.5 (diverges from skyspec) | fail | FAIL x4 `memory point != skyspec.ROOF_DROP_POINTS`: **caught** |
| d6 builder emits only 3 drop points | fail | FAIL `roof_drop_4 memory point != ...`: **caught** |
| **d2 drop at (-1, -2) (over the core hole / penthouse)** | fail | **PASS: not caught** (L-R2) |

All 4 new checks fail on the defects they target and pass on the real modules (R1 #3). PASS.

### R4. DECISIONS, skyspec and memory points

- **D36** matches check_assets exactly: Apartments and Hotel 28 / 336, Roof_Garden res1 128 > 120 and 3 sections, Roof_Mechanical res1 128 > 120.
- **D35** matches the code and the P3Ds: 2 hall doors per apartment (R2); test_kit flood fill > 1 m2 (R3); crate 1.5 m with parapet margin >= 1 m
  (`test_kit.py:186-191`); plant units z 0..3.20 (P3D Geometry Component09-12); garden planters in View (garden View 12 comps, the same as Geometry) and
  1.25 m inside the parapet (`build_floors.py:155`, x/y +-10.5); Res3 1 section; Geometry lintels dropped while View/Fire keep them (R5).
  Wording nit: "floors' Res3 is one glassfar band" holds for apartments and hotel. The mechanical floor's Res3 is one **metal** louvre band (`build_floors.py:133`),
  which TESTING F4-16 states correctly (Info).
- **ROOF_DROP_POINTS** (`skyspec.py:407-409`) vs the P3D memory LOD: garden and mechanical `roof_drop_1..4` = (-8,-2), (8,-2), (-8,2), (8,2) at h 0.05.
  Helipad = (+-8, +-8). **12/12 match.** Each 1.5 m crate hits 0 Geometry components, sits 3.0 m from the parapet inner face and is not over the core.
- **Known latent (Batch 5, not a Batch 4 failure):** `placement/sky_layout.py:148` still iterates `S.ROOF_DROPS` (helipad positions), so M3 stays open
  until Batch 5. The comments `build_floors.py:167,183` ("shared with sky_layout") and `skyspec.py:404-406` ("Read by ... placement/sky_layout.py")
  describe the Batch 5 target state, not current code. TESTING F4-15 at 20746e8 says sky_layout "writes per roof class", which is not true yet.
  (226f4c0 rewords F4-15 to "from batch 5 on".)

### R5. Perf fixes (measured from the 20746e8 P3Ds, `scratchpad/qa4b_perf.py`)

| Item | Result |
|---|---|
| Floors Res3 = 1 band | Apartments and Hotel: 4 faces / 8 tris / 1 section `sky_glassfar.rvmat`, z -0.30..3.20. Mechanical: 4 / 8 / 1 `sky_metal.rvmat`. PASS |
| Roofs Res3 = 1 closed box | Garden and Mechanical: 5 faces / 10 tris / 1 section `sky_concrete.rvmat`, z -0.30..1.10, open bottom (Mechanical was 24 faces at fcc7f4c). PASS. (Security re-gate N1 later moved the lid to z = 0 in 226f4c0) |
| Geometry without lintels, Fire/View keep them | Lintel components (z0 1.9..2.5, top > 2.5): Apartments geo **0** / view 12 / fire 12; Hotel geo **0** / view 10 / fire 10. PASS. (Reverted by 226f4c0 / D37) |
| Plant units full height | Mechanical Geometry Component09-12 = z 0.00..3.20 (were 2.20). PASS |
| Louvre corners non-overlapping | Same-facing coplanar overlapping face pairs in Res0/1/2: **0** (fcc7f4c had 8 in Res0, at x = +-12 and y = +-12). Pairs that remain are only back-to-back contacts (E/W band end caps against the N/S band inner faces, slab hole edges, unit bases on the slab). These are hidden faces, so there is no z-fighting. L5 fixed: PASS |

### R6. Docs

- **TESTING.md §15**: F4-01..F4-21 and F4-R are present and updated for the fixes. F4-06 covers two hall doors, F4-07 the connecting corner rooms (M1, now by design),
  F4-08 full-height units, F4-09 planter inset, F4-10/11 1.0 m doors, F4-16 Res3 band/box, and F4-17 the louvre fix. The sign-off row
  `Floor / roof variants §15` is present. Nits at 20746e8: F4-06 says "two 1.0 m" (N/S doors are 1.2 m) and F4-15 is as noted in R4. Both are reworded in 226f4c0. PASS.
- **manifest.yaml section A**: Floor_Apartments, Floor_Hotel, Floor_Mechanical, Roof_Mechanical and Roof_Garden are now `built-unverified` with `note: batch 4 - see generated_kit`.
  No batch-4 entry still says `planned` (the remaining `planned` entries are Lobby_B, Skybridge, facades and towers). The hotel description matches skyspec and config.cpp. L2 fixed: PASS.
- **PENDING_VERIFICATION P3** now names every `sky_floors` module (slabs, partitions = masonry, facade glass, louvre/HVAC = metal). L3 fixed: PASS.

### R7. Status of earlier findings

| Finding | Status |
|---|---|
| H1 sealed NW/SE apartments | **Fixed** (R2, independent) |
| M1 hotel corner rooms | Resolved as design: description changed in skyspec, config.cpp, manifest and F4-07 |
| M2 test_kit gaps (a-d) | Fixed. Residual gaps: L-R1, L-R2, L-R3 |
| M3 CE drop positions | **Open, known latent**: skyspec side done, `sky_layout.py` is Batch 5 work |
| L1 0.875 m doors | Fixed (all doors >= 1.0 m) |
| L2 manifest | Fixed |
| L3 TESTING / PENDING | Fixed |
| L4 LOD/shadow simplifications | Unchanged by design (D36). Still watch in F4-16 / F4-18 |
| L5 louvre corner z-fight | Fixed (R5) |

### R8. New findings (20746e8)

- **High**: none.
- **Medium**: none.
- **L-R1** - `test_kit.reachability` (`test_kit.py:109-158`) does not inflate the blockers by the player radius. A 0.3 m opening passes (mutation a4),
  so the test proves connectivity, not passability. Suggested fix: inflate blockers by ~0.3 m (or require door gaps >= 0.9 m) before flooding.
  Today's doors are >= 1.0 m (R2).
- **L-R2** - The roof-drop crate check (`test_kit.py:178-191`) ignores the core footprint. A drop at (-1, -2) passes (mutation d2) even though the crate
  would spawn inside the core penthouse. Suggested fix: add `CORE_CLEAR["core footprint"]` to the crate overlap test. Today's points are 5 m clear of the core.
- **L-R3** - The occluder check only counts `occluder_*` groups (>= 4). An occluder over the core hole passes (mutation c3). Suggested fix: require every
  occluder's bounding box to lie outside the core hole.
- **Info** - D35 wording "glassfar" vs the mechanical floor's metal Res3 (R4). The skyspec/builder comments describe the Batch 5 `sky_layout` state (R4).
  HEAD `226f4c0` landed during this gate and needs its own QA pass (see the note at the top of this section).

**GATE: PASS (20746e8)**
