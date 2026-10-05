# QA static run: SKY_Skyline Tower A

- Date: 2026-10-05, about 10:44 to 10:55 UTC. Repo HEAD `0526fb0`.
- Host: Linux, Python 3.11.15, PowerShell 7.4.6, Blender 4.2.23 LTS (all in the session scratchpad).
- Not available here: DayZ, DayZDiag, DayZ Server, DayZ Tools (Addon Builder, Binarize, ImageToPAA, Object Builder) and the `P:` work drive.
- So nothing in this report was loaded by the game. In-game gates are in `TESTING.md` and still have to be run on the Windows workstation.
- Other agents added files while this run was in progress: `assets/Build-SkyAssets.ps1`, `assets/MANUAL_STEPS.md`, `placement/README.md`, `economy/README.md` and `reviews/img/`. The results below describe the tree as it was at about 10:55 UTC.
- Side effects of the commands I was asked to run:
  - `placement/sky_layout.py` rewrote the 4 files in `placement/out/`. The generator is deterministic and the site is the placeholder.
  - `Build-Mod.ps1 -DryRun` wrote `build/@SKY_Skyline/mod.cpp` and `build-manifest.json`. That folder is git-ignored.
  - No other files were modified.

## Verdict

| # | Check | Result |
|---|---|---|
| 1 | `p3d_inspect.py` on 5 P3Ds | 5/5 parsed (exit 0). LOD sets are complete; see section 1 |
| 2 | `assets/check_assets.py` | 5 checked, **0 fail, 1 over budget** (core Geometry 81 comps > 80), exit 0 |
| 3 | `assets/gen_configs.py --check` | up to date, exit 0 |
| 4 | `economy/gen_economy.py --check` | up to date, exit 0 |
| 5 | `enscript_xref.py` (vanilla script dump vs `sky_scripts`) | OK: 10 files, all calls/types resolve, exit 0 |
| 6 | `placement/tests/test_sky_layout.py` | **8 PASS / 0 failed**, exit 0 |
| 7 | `placement/sky_layout.py` | PASS with 3 warnings (placeholder site, no survey, Y=0). `--strict`: **FAIL**, exit 1. This is expected: no survey exists yet |
| 8 | Blender `assets/blender/test_towera.py` | **PASS** (81 core components checked), exit 0 |
| 9 | `tools/tests/Invoke-SelfTest.ps1` | **45 OK / 0 FAIL**, exit 0 |
| 10 | `Build-Mod.ps1 -ModName SKY_Skyline -DryRun` | OK: 4 PBOs, **2 binarized** (`sky_items`, `sky_towera`), **2 pack-only** (`sky_scripts`, `sky_textures`) |
| 11 | Cross-checks (section 3) | 54/54 SKY paths resolve; 8 `dz\` paths need checking on P:. **15 findings**, listed in section 4 |

**Static gate: PASS with findings.** No static check failed. Two findings must be fixed or checked before in-game testing will mean anything:
- QA-01: `enableCfgGameplayFile` is not set, so the tower never spawns.
- QA-03: no `.paa` files exist yet.

QA-02 (keycard retexture) and QA-04 (ghost foundation skirt) are Medium.

---

## 1. `p3d_inspect.py`

Command (from `mods/SKY_Skyline`):

```
python3 /home/user/DayZModding/tools/assets/p3d_inspect.py addons/*/*.p3d
python3 /home/user/DayZModding/tools/assets/p3d_inspect.py --json addons/*/*.p3d   # exit 0
```

| P3D | LODs | Res0 / Res1 / Res2 / Res3 tris | Shadow | Geometry (comps, mass, props) | View | Fire | Roadway |
|---|---|---|---|---|---|---|---|
| `sky_towera/sky_towera_lobby.p3d` | 10 | 1064 / 668 / 92 / 16 | 60 | 17 comps + `door_sec`, 60000, class=house map=building autocenter=0 | 10 comps + `door_sec` + 4 occluders | 17 comps + `door_sec` | 8 |
| `sky_towera/sky_towera_floor_office.p3d` | 10 | 928 / 536 / 56 / 16 | 48 | 12 comps, 40000, same props | 8 comps + 4 occluders (glass excluded) | 12 comps | 8 |
| `sky_towera/sky_towera_core.p3d` | 10 | 1602 / 846 / 132 / 10 | 12 | 81 comps + 14 door leaves, 120000, same props | 52 comps + 14 leaves + 2 occluders | 81 comps + 14 leaves | 72 (stairs sloped, 14 faces) |
| `sky_towera/sky_towera_roof_helipad.p3d` | 10 | 98 / 98 / 96 / 48 | 96 | 8 comps, 30000, same props | 8 comps + 4 occluders | 8 comps | 8 |
| `sky_items/sky_keycard.p3d` | 5 (Res0, Res1, Geometry, Memory, Fire) | 12 / 12 | - | 1 comp, 0.05 | - | 1 comp | - |

Named selections, all present where `model.cfg` and `config.cpp` need them:

**Lobby**
- `door_sec` appears in Res0, Res1, Geometry, View and Fire.
  - Leaf bounds: x 5.975..6.025, y 0..2.09, z 7.01..7.99.
- Memory points:
  - `door_sec` (6.0, 1.05, 7.5)
  - `door_sec_action` (5.6, 1.1, 7.5): corridor side
  - `door_sec_axis` (6.0, 0, 7.0) to (6.0, 2.1, 7.0): vertical hinge at the z=7 edge
  - `entrance`, `light_1..4`

**Core**
- `elev_door_l0..6_a/_b` appear in Res0, Res1, Geometry, View and Fire.
  - Leaves: x -0.6..0 and 0..0.6, z 4.28..4.34, y stop..stop+2.095.
- Memory points (63 in total):
  - `elev_cab_lN` (0, stop+0.05, 2.875)
  - `elev_panel_lN` (1.15, stop+1.25, 3.55): inside the cab
  - `elev_call_lN` (0.95, stop+1.25, 4.65): on the landing
  - `elev_door_lN_a_axis` (0→-0.58 in x) and `elev_door_lN_b_axis` (0→+0.58), at stop+1.0, z 4.31
  - `light_cab_lN`, `light_stair_N`
- A cab floor exists at every stop (probed Geometry under (0, stop-0.1, 2.875): Component23/59/63/67/71/75/79).
- Wall pieces exist between the stacked door openings at every level, so perf_review H1 is fixed in the current MLOD.

**Roof**
- Memory: `heli_pad` (0, 0.05, 8.15) and `roof_drop_1..4` at (±8, 0.05, ±8).
- Helipad decal: x -3.25..3.25, z 4.9..11.4.

**Floor**
- Memory: `floor_center` (0, 0.05, -8), `light_1..4`. No named selections in the visual LODs.

**Keycard**
- `camo` in Res0 and Res1. Memory: `ce_center`, `ce_radius`.

**Fire Geometry materials**
- Lobby: concrete for the slab and security-room walls, glass for the facade, wood_desk for the desk, metalplate for the door.
- Floor: concrete for the slab, glass for the facade, bricks for the partitions.
- Core: 52 concrete, 43 metalplate.
- Roof: concrete.
- Keycard: metalplate.

## 2. Tool outputs (verbatim)

```
$ python3 assets/check_assets.py                       # exit 0
Land_SKY_TowerA_Lobby            PASS LODs=10 res=1064 -> 668 -> 92 -> 16
Land_SKY_TowerA_Floor_Office     PASS LODs=10 res=928 -> 536 -> 56 -> 16
Land_SKY_TowerA_Core             OVER LODs=10 res=1602 -> 846 -> 132 -> 10 geo comps 81 > 80
Land_SKY_TowerA_Roof_Helipad     PASS LODs=10 res=98 -> 98 -> 96 -> 48
SKY_Keycard_T1 / T2 / T3         PASS LODs=5 res=12 -> 12
5 checked, 0 fail, 1 over budget (hypotheses)

$ python3 assets/gen_configs.py --check                 # exit 0
up to date
$ python3 economy/gen_economy.py --check                # exit 0
up to date

$ python3 /home/user/DayZModding/tools/assets/enscript_xref.py \
    --vanilla /tmp/claude-0/-home-user-DayZModding/eac31f0c-ff63-501e-bd5f-bd983451ec62/scratchpad/dzs/scripts \
    --mod addons/sky_scripts/scripts                    # exit 0
OK: 10 files, all calls/types resolve

$ python3 placement/tests/test_sky_layout.py            # exit 0
PASS flat site passes strict
PASS base height = max ground inside footprint + clearance
PASS 8 objects (lobby, 5 floors, roof, core)
PASS steep site fails (drop > skirt)
PASS existing building inside footprint fails
PASS vegetation inside footprint only warns
PASS overlapping towers fail
PASS survey without samples in footprint fails
0 failed

$ python3 placement/sky_layout.py                       # exit 0
status: PASS (with warnings)
WARN : site 'placeholder-site' is a PLACEHOLDER - do not deploy
WARN : no survey: ground height / overlaps NOT validated
WARN : tower A1: no base height (survey or base_y) - Y set to 0.0
$ python3 placement/sky_layout.py --strict --out <scratchpad>/layout_strict   # exit 1 (expected)
status: FAIL
ERROR: site 'placeholder-site' is a PLACEHOLDER - do not deploy
ERROR: no survey: ground height / overlaps NOT validated
ERROR: tower A1: no base height (survey or base_y) - Y set to 0.0

$ <scratchpad>/blender/blender -b --factory-startup -P assets/blender/test_towera.py   # exit 0
TOWER A GEOMETRY TESTS: PASS (81 core components checked)

$ <scratchpad>/pwsh/pwsh -NoProfile -File /home/user/DayZModding/tools/tests/Invoke-SelfTest.ps1   # exit 0
... 45 x [OK] (parse 17 scripts, New-Mod, Build-Mod pack-only/binarize/$PBOPREFIX$/pboProject,
    Sign-Mod, launchers, server cfg templates, repo hygiene)
    [OK]   all self-tests passed

$ <scratchpad>/pwsh/pwsh -NoProfile -File /home/user/DayZModding/tools/build/Build-Mod.ps1 -ModName SKY_Skyline -DryRun   # exit 0
==> Build SKY_Skyline (addonbuilder)  .../mods/SKY_Skyline -> .../build/@SKY_Skyline
    PBO 'sky_items'  prefix=SKY_Skyline\sky_items  binarize=True
    junction P://SKY_Skyline -> .../mods/SKY_Skyline/addons
    > "<tool not installed>" P://SKY_Skyline/sky_items .../build/@SKY_Skyline/addons -prefix=SKY_Skyline\sky_items -include=.../addonbuilder-include.lst -project=P:\ -clear
    PBO 'sky_scripts'  prefix=SKY_Skyline\sky_scripts  binarize=False
    > "<tool not installed>" .../addons/sky_scripts .../build/@SKY_Skyline/addons -prefix=SKY_Skyline\sky_scripts -include=... -packonly
    PBO 'sky_textures'  prefix=SKY_Skyline\sky_textures  binarize=False
    > "<tool not installed>" .../addons/sky_textures .../build/@SKY_Skyline/addons -prefix=SKY_Skyline\sky_textures -include=... -packonly
    PBO 'sky_towera'  prefix=SKY_Skyline\sky_towera  binarize=True
    junction P://SKY_Skyline -> .../mods/SKY_Skyline/addons
    > "<tool not installed>" P://SKY_Skyline/sky_towera .../build/@SKY_Skyline/addons -prefix=SKY_Skyline\sky_towera -include=... -project=P:\ -clear
    [OK]   Built .../build/@SKY_Skyline
```

PBO plan from the dry-run build:

| PBO | Prefix | Mode | Why |
|---|---|---|---|
| `sky_items.pbo` | `SKY_Skyline\sky_items` | **binarize** via `P:\SKY_Skyline` junction | contains `sky_keycard.p3d` |
| `sky_scripts.pbo` | `SKY_Skyline\sky_scripts` | pack-only | `config.cpp` + `.c` only |
| `sky_textures.pbo` | `SKY_Skyline\sky_textures` | pack-only | `config.cpp` + `.rvmat`; the `.paa` files are not generated yet (QA-03) |
| `sky_towera.pbo` | `SKY_Skyline\sky_towera` | **binarize** | 4 P3Ds + `model.cfg` |

## 3. Consistency cross-checks

| Check | Result |
|---|---|
| `model=` paths in `addons/*/config.cpp` vs prefix `SKY_Skyline\<pbo>` | 5/5 OK: 4 tower modules in `sky_towera`, keycard in `sky_items` |
| SKY texture/rvmat paths referenced by P3Ds, rvmats and configs | 54/54 resolve |
| - rvmats | 9 committed (`sky_textures/data` x8, `sky_items/data` x1) |
| - `.paa` files | 40 match `gen_textures.py` output names, routed by `Build-SkyAssets.ps1` (`sky_keycard*` → `sky_items\data`, the rest → `sky_textures\data`). **None are present on disk yet** |
| - `.p3d` files | 5 OK |
| - unreferenced | `sky_asphalt.rvmat` (street kit) |
| `model.cfg` skeleton bones ↔ P3D selections | Lobby: `door_sec` OK. Core: 14 `elev_door_lN_a/b` OK, present in Res0, Res1, Geometry, View and Fire. Res2/Res3 have no door selections, which is acceptable at distance |
| `model.cfg` axes | `door_sec_axis` (2 pts) OK. 14 `elev_door_lN_a/b_axis` (2 pts each) OK |
| `Doors` class (lobby) | `component="door_sec"` exists in Geometry, Fire and View. `soundPos="door_sec_action"` exists in Memory. Animation source `door_sec` = Doors class name = `model.cfg` `source`, OK. `DamageZones.door_sec.componentNames={"door_sec"}` is in Fire Geometry, OK |
| Core `AnimationSources` `elev_door_l0..6` ↔ `model.cfg` sources ↔ script `SetAnimationPhase("elev_door_l"+i)` | 7/7 OK |
| Script memory points | `elev_cab_lN`, `elev_panel_lN`, `elev_call_lN` for N=0..6, `door_sec`, `door_sec_action`, `door_sec_axis` and `elev_door_lN_a/b_axis` all exist |
| `skyStops[]` ↔ memory heights ↔ layout Y | {0, 7, 10.5, 14, 17.5, 21, 24.5}. Cab points at stop+0.05. Layout Y 0/7/.../24.5 matches |
| `skySecurityRoom[]` {6.125, 11.85, 6.125, 11.85} ↔ Geometry | Matches the room interior: walls at 5.875..6.125, facade at 11.88 |
| Module stacking | Lobby top 6.7 = floor 1 slab bottom (7 - 0.3). Floor top 3.2 + 0.3 = 3.5 floor-to-floor. Roof slab bottom 24.2 = floor 5 top. Core 0..28.3 |
| `mapgroupproto` group names ↔ config classes | `Land_SKY_TowerA_Lobby`, `_Floor_Office` and `_Roof_Helipad` are equal to the config class names. The core has no group, which is intended |
| Loot point frame | `pos = (X, 0, Y)` from `skyspec.LOOT` (Blender X/Y → P3D x/z, y = slab top). This matches the `skyspec` frame note and the module origin (top of slab, `autocenter=0`). The Blender test confirms a floor under each point and nothing solid around it |
| Roof-drop event | `cfgeventspawns` positions are T + (±8, ±8) at roof Y + 0.05, which matches `roof_drop_1..4`. With the placeholder site, the absolute Y (24.55) is meaningless |

`dz\` vanilla paths. **Verify on P: on Windows**: `Build-SkyAssets.ps1` does this unless `-SkipPChecks` is passed.

| Path | Used by | Seen in Bohemia `Test_Building` sample? |
|---|---|---|
| `dz\data\data\penetration\concrete.rvmat` | Fire Geometry of all 4 tower modules | **no** |
| `dz\data\data\penetration\glass.rvmat` | Fire Geometry of lobby and floor | **no** |
| `dz\data\data\env_land_co.paa` | all 10 rvmats (env map stage) | **no** |
| `dz\data\data\penetration\bricks.rvmat` | floor partitions | yes |
| `dz\data\data\penetration\metalplate.rvmat` | core, lobby door, keycard | yes |
| `dz\data\data\penetration\wood_desk.rvmat` | lobby desk | yes |
| `dz\surfaces\data\roadway\concrete_int.tga` | Roadway of lobby, floor and core | yes (same `.tga` spelling) |
| `dz\surfaces\data\roadway\concrete_ext.paa` | Roadway of the roof | yes |

## 4. Findings (not fixed: routed to the owner)

| ID | Sev | Finding | Evidence | Owner |
|---|---|---|---|---|
| QA-01 | **High** | The tower relies on `cfggameplay.json` `objectSpawnersArr`, but neither server config template sets `enableCfgGameplayFile = 1;`. Without it the server ignores `cfggameplay.json` and **no module spawns**. `placement/README.md` does not mention the setting | `server/templates/serverDZ.{diag,dedicated}.cfg` (no match for `enableCfgGameplayFile`). Vanilla `3_game/cfggameplayhandler.c:53,62` (the `DIAG_DEVELOPER` override applies only when `!IsDedicatedServer()`) | workspace tooling / placement docs |
| QA-02 | Medium | `sky_items` has no `model.cfg`, so `camo` is not declared in `CfgModels.sky_keycard.sections[]`. In the binarized model, `hiddenSelectionsTextures` (T1/T2/T3 colours) may not apply, and every card could show the baked T1 texture | `addons/sky_items/` holds only `config.cpp`, `sky_keycard.p3d` and `data/`. `config.cpp` has `hiddenSelections[]={"camo"}` | asset-pipeline (verify in game: TESTING K-09) |
| QA-03 | Medium | None of the 40 referenced `.paa` files exist in `addons/sky_textures/data` or `addons/sky_items/data`. `sky_textures` is pack-only, and `Build-Mod.ps1` does not check this, so a build today ships untextured models | cross-check script, section 3. Fix path: `assets/Build-SkyAssets.ps1` on Windows before `Build-Mod` | asset-pipeline (precondition in TESTING) |
| QA-04 | Medium | The lobby foundation skirt exists only in the visual LODs (Res0..Res2 bbox y down to -2.5). Geometry, Fire and View stop at y -0.3. On a sloped site (allowed drop up to 2.2 m), players, AI and bullets pass through the skirt, a player can crawl into the void under the lobby slab, and the skirt does not block view | `p3d_inspect` bbox: lobby Res0 `[-12.04,-2.5,..]` vs Geometry `[-12,-0.3,..]` | asset-pipeline |
| QA-05 | Low | Core Geometry has 81 components, over the budget of 80 | `check_assets.py` OVER line | asset-pipeline / perf |
| QA-06 | Low | `assets/manifest.yaml` core `open_items` is stale: it says Res0 2322, Res2 252 and 99 comps; the actual values are 1602, 132 and 81. perf_review H1 evidence (solid walls over upper openings) no longer matches the MLOD: the openings now exist at every level. perf needs a re-review | manifest line `open_items: [...]`; core Geometry Component02..08 / 11..17 | asset-pipeline / perf-engineer |
| QA-07 | Low | Comments reference scripts that do not exist: `Check-SkyAssets.ps1` (`assets/skyspec.py:61`, `assets/gen_configs.py:56`) and `tools\assets\Convert-SkyTextures.ps1` (`assets/textures/gen_textures.py:5`). The real scripts are `assets/Build-SkyAssets.ps1` and `tools/assets/Convert-Textures.ps1` | grep | asset-pipeline |
| QA-08 | Low | 3 vanilla paths are unverified: `penetration\concrete.rvmat`, `penetration\glass.rvmat` and `env_land_co.paa`. If they are missing, Fire Geometry falls back to default penetration and glass may stop bullets like concrete | table above, `skyspec.PENETRATION` flags | asset-pipeline (on P:) |
| QA-09 | Low | Elevator leaves travel 0.58 m (axis length 0.58 x `offset1=1`) but are 0.60 m wide, so 2 cm of each leaf stays in the 1.2 m opening (clear width 1.16 m) | memory axes vs Geometry leaf bounds | asset-pipeline |
| QA-10 | Low | Process gap: in-game tests need mission edits (`cfggameplay.json`, `sky/sky_objects.json`, CE folder, `mapgroupproto`, `cfgeventspawns`, `mapgrouppos`). `CLAUDE.md` forbids editing `server\mpmissions` (vanilla copy) and the server install, and no script creates a separate test mission | `CLAUDE.md` Conventions; `tools/setup/Initialize-TestServer.ps1` copies vanilla only | workspace tooling |
| QA-11 | Low | Lobby Res3 still has no foundation skirt (bbox y -0.3..6.7 vs -2.5 at Res0), so perf H2.4 is still partly open. Roof Res1 = Res0 (98 tris, no reduction, but within budget) | p3d_inspect bbox and tris | asset-pipeline |
| QA-12 | Low | The helipad decal (z 4.9..11.4) is 0.4 m from the 3.8 m core penthouse wall, so there is no rotor clearance. This is cosmetic in vanilla (no flyable helicopters). `heli_pad` memory point sits at (0, 8.15) | decal bbox, core z max 4.5 | design note |
| QA-13 | Low | Economy design: `lootSecurity` uses tag `shelves`, but the room has no shelves. Keycards are category `tools` with usage Office/Town, so a T2 card can spawn inside the T2 room it unlocks | `mapgroupproto_sky.xml`, `sky_ce/types.xml` | economy-designer |
| QA-14 | Info | Placement is still the placeholder (7500, 7500, Y=0), so `--strict` fails as designed. A real survey is required before any deploy | step 7 | placement |
| QA-15 | Info | Memory points `light_*` and `floor_center` have no consumer in config or script (no lights are defined). `floor_center` is not at the centre (z = -8) | memory dump | asset-pipeline |

Checked and **no discrepancy found**:
- config prefixes and `requiredAddons` chain (Items → Scripts, TowerA → Textures + Scripts)
- `CfgMods` script module paths
- Doors, animation sources and damage-zone names
- every script memory point
- elevator stop heights
- security-room bounds
- stacking heights
- loot point frame and group names
- texture name routing

## 5. Not checkable here (in-game gates)

These are open until someone runs them on Windows:
- collisions
- Fire Geometry penetration
- View Geometry occlusion
- door rotation sign (`angle1 = 1.4` about +Y; intended to swing into +X, the room)
- leaf slide direction
- AI navmesh
- CE spawning
- elevator and keycard behaviour on a dedicated server
- lock state after restart (security M3)
- logs
- FPS (`perf_review.md` section 4)

See `mods/SKY_Skyline/TESTING.md`.
