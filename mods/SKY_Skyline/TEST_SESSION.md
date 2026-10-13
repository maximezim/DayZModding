# Test sessions (D60, updated D93; section 6 = the D96-D100 build, D101)

Goal for tonight: first pack and first run of SKY_Skyline in DayZ. The order below gets the most
answers per hour, and every step says what to send back. Run everything from the repo root in
PowerShell.

## 0. Before we start (10 min)

1. `git pull`, then `tools\setup\Get-ToolchainStatus.ps1`. All green? P: mounted?
2. `tools\tests\Invoke-SelfTest.ps1`. Expected: all self-tests passed.
3. Textures (PAA files are generated, not committed): `mods\SKY_Skyline\assets\Build-SkyAssets.ps1`.
   It writes PNGs, converts them with ImageToPAA (including the new 4096 `sky_hq_facade`), then checks every
   `dz\` path on P:. Expected: it ends with `SKY assets ready`. **Send me** any missing `dz\` path it names
   (P3 / P4), and whether `sky_decal_grime_ca` (1024 x 2048 since D92, the only non-square sheet) converted (P65).
4. Static checks, which need no game: `tools\tests\Invoke-ModValidation.ps1 -ModName SKY_Skyline -DryRun`.
   It prints every command. The geometry tests now run in plain Python, so Blender is not needed.

## 1. Pack, sign, first dedicated start (20 min)

```
tools\tests\Invoke-ModValidation.ps1 -ModName SKY_Skyline -Layout mods\SKY_Skyline\placement\district_template.yaml -Minutes 5
```
- **Send me** `build\validation\<timestamp>\summary.md` and the `logs\` folder (RPT + script log).
- Packing takes a while: 6 city PBOs (`sky_city_res|block|com|civic|ind|env`, ~250 MB of source max each).
  If pboProject / Addon Builder fails on one, the summary names it. Send that log.
- Expected 0 SKY FAIL lines. Anything naming `SKY_` in the RPT is a finding (B9 tunes the patterns).

## 2. Diag walk-through (45 min) - TESTING.md sections in this order

`tools\build\Build-And-Run.ps1 -ModName SKY_Skyline -FilePatching` (diag server + client).

| Order | TESTING section | Why first |
|---|---|---|
| 1 | §1 Collisions, §11 Clean logs | if Geometry or loading is wrong, everything else is moot |
| 2 | §4 Doors (P1), §5 Keycard, §6 Elevator (P2) | the three sign / behaviour parameters we can only see in game |
| 3 | §2 Fire Geometry (P3), §3 View Geometry | penetration paths and occluders |
| 4 | §15 floor / roof variants, §25 content pass (HQ, Lobby_B, skybridge) | tonight's new content |
| 5 | §21-24 city buildings, vegetation, clutter cutters (P12) | the bulk of the models |
| 6 | §8 Loot, §10 Roof drop | needs the CE files merged (the validation script does it) |

For each row, note PASS/FAIL in TESTING.md, or just tell me the ID and what you saw.
A screenshot is worth more than a description.

### 2b. Since D88: the checks that matter most (20 min, same diag run)

| Order | Rows | Why |
|---|---|---|
| 1 | §54 FL-03 (stand behind a broken window, a friend outside) and FL-01 / FL-02 (walk away from big blocks to 600 m) | the one-way broken-window panes are gone and the far LODs were rebuilt: confirm both in game (P58, P63) |
| 2 | §52 RV-04 (kennel at a doorway / base gate) and RV-05 (rare search cap) | security fixes of the full review (P59, P60) |
| 3 | §52 RV-01 (lights at night, walk the centre) and RV-07 (alarm alone / with 4+ players) | the perf fixes: light director and horde scaling (P56, P61) |
| 4 | §55 OW-01 (factory roof glazing) and OW-03 (shoot the foot of a jersey barrier) | one-way glass and the convex barrier collision (P64) |
| 5 | §56 WW-01 / WW-03 and §53 WD-01 / WD-02 | wall wear, switches, roof clutter; the facade weathering after the sheet change (P62, P65) |

## 3. Parameters to read off in game

P1 door swing, P2 elevator slide, P3 penetration, P4 env map, P5 armor class, P7 emissive
strength, P9 yaw sign, P10 script lights, P12 clutter cutter size. Since D88: P56 light director range, P58 / P63 far
LODs and dark windows at range, P59 kennel door rule, P62 / P65 wall dressing and the 1024 x 2048 decal sheet, P64
barrier hits. Each has a one-line fix in `PENDING_VERIFICATION.md` (P1-P12 also in `AFTER_TESTING.md`). Tell me the
observation and I make the change and re-export in plain Python.

## 4. If there is time

- B10-EXP: open `addons\sky_floors\sky_floor_hq.p3d` in Object Builder. Does every LOD load?
- FPS: `FPS_PROTOCOL.md` §1 on the district template (client FPS at 2 view distances).
- Skyline: `placement\skyline_template.yaml` needs a surveyed site first (placement/README §1).
  It is 778 entities + loot of the 800 cap, so pick a flat spot.

## 5. City life, creatures, underground, vehicles (D61-D65): second session

These rows need two players and a shortened alarm timer on the diag build. Spawn single pieces with
the diag console: the city life template is a terrain layout.
1. §26 city life: search (CL-08 to CL-10, including the security spam test), hydrant, alcohol, hordes, and the
   alarm (shortened timer).
2. §27 creatures: kennel guard with 2 players (CR-01 to CR-04 first, they are the security-critical rows), then
   the rat nest.
3. §30 refinement: the new search spots and the ambience loops.
4. §29 vehicles: the wrecks only.
5. §28 underground needs the custom test terrain (Terrain Builder import of `terrain/out`, P28): plan it as its
   own session.
Parameters to read off: P14 alarm reach, P15 horde caps / FPS, P16 drunk levels, P17 search points, P18 hydrant,
P19 jams, P20/P23/P32 sound ranges, P21 kennel guard, P22 rat bites.

## 6. Second session: the D96-D100 build (TESTING sections 59-61)

Everything since the Chernarus evening: the quality pass (textures, z-fighting, the vertex limit, detail), the bus and
garbage-truck wrecks, interior doors, balconies on the apartment blocks and the Tower A lobby. Same site and mission as
section 58 (`dayzOffline_sky.chernarusplus`, `placement/out_city_chernarus/`): no layout moved (footprints unchanged).
About 90 minutes.

### 6.0 Rebuild (25 min, unattended)

1. `git pull`, `tools\setup\Get-ToolchainStatus.ps1`, `tools\tests\Invoke-SelfTest.ps1` (all green).
2. Textures: `mods\SKY_Skyline\assets\Build-SkyAssets.ps1`. New since D96: `sky_rooftile`, `sky_roofslate`, `sky_facadekit`
   (2048), the 8-band painted metal (1024 x 2048), new plaster sheets. Expected: `SKY assets ready`. **Send me** any sheet that
   fails to convert (P71). The P3Ds are committed: no `-Models` needed.
3. Pack and sign: `tools\build\Build-Mod.ps1 -ModName SKY_Skyline`, then `tools\build\Sign-Mod.ps1 -ModName SKY_Skyline`. Every city
   PBO changed (doors, balconies, detail). If one fails, send its log.
4. Optional (WIN-06 is fixed by proxy parts): put the two CourtyardBlock landmarks back into `placement/city_chernarus.yaml`
   and re-run `sky_layout.py ... --no-entity-cap --strict` as in section 58. Skip it if short of time.

### 6.1 Load check (10 min) - stop here if this fails

`tools\build\Build-And-Run.ps1 -ModName SKY_Skyline -FilePatching` with the city mission, as in section 58. In the server
and client RPT search for:

| Look for | Means | Parameter |
|---|---|---|
| `Too many vertices` | a model still over the engine limit (WIN-06) | P72 |
| `proxy` + `_res0p` errors, or furniture / partitions missing up close in the Hospital, Mall, DepartmentStore | proxy parts not loading | P68 |
| `Doors`, `DamageSystem`, `animation`, `bone` warnings naming `Land_SKY_City_` | interior door config (48 doors per building) | P74 |
| `Cannot open object SKY_Skyline\...` | a missing P3D / PAA | P71 |

**Send me** the RPT lines with `SKY` in them, even if it looks fine.

### 6.2 Walk-through in this order (55 min)

| Order | Rows (TESTING) | Where | Why this order |
|---|---|---|---|
| 1 | QP-01, ID-06 | Hospital, CourtyardBlock, Mall | the largest models: proxy parts and 48 doors; if these break, the rest waits |
| 2 | QP-02, QP-07, QP-09 | any street, 2 / 10 / 50 m | the CT-13 complaint (glitched textures, ugly details): z-fighting, smooth shading, new sheets |
| 3 | ID-01, ID-02, ID-03, ID-04 | AptBlock, School (Intact + Damaged) | door swing direction (P1), clearance, slits at the edges |
| 4 | ID-05 | AptBlock with infected nearby (diag navmesh view) | can infected path through closed doors (P75); if not, doors become a safe room |
| 5 | BA-01, BA-02, BA-03, BA-04 | the three apartment block types, all states | balconies: look, bullets / sight through bar parapets, climbing out of a ruin's broken window |
| 6 | QP-12, QP-13, QP-14 | a Warehouse, a ruined Church / office, a ruin's collapse corner | the D96 collision fixes (inside cladding, open broken windows in ruins, no invisible stubs) |
| 7 | QP-03, QP-04, QP-05, QP-06, QP-08 | Villa / Rowhouse, a sedan / van wreck | roofs, windows, doors, cornices, curved car bodies |
| 8 | QP-20 | Wreck_CityBus / Wreck_GarbageTruck (citylife template or diag spawn) | the new wreck bodies, crawl under / climb on |
| 9 | LB-01, QP-10, QP-15 to QP-19 | Tower A lobby, Ferris wheel, bridge, carousel, tunnel | the rest of the D96 list |
| 10 | QP-11 | FPS_PROTOCOL.md section 1 | the detail cost: a drop over 10 % at 1600 m view distance is a finding |

For each row: PASS / FAIL in TESTING.md, or just the ID and what you saw. A screenshot per FAIL.

### 6.3 Parameters to read off

P1 door swing (now on 727 interior doors too), P68 proxy parts, P69 smooth shading, P70 the 4 mm z-fight offset, P71 the
new sheets, P72 the vertex limit, P73 thin collision (carousel fence, ship ladder), P74 the door count / draw calls, P75
infected through doors. Each has its one-line fix in `PENDING_VERIFICATION.md`.

## What I need back, in one message

`summary.md`, the RPT and script log of the diag run, TESTING IDs with FAIL plus a screenshot,
and the P1/P2/P9 observations, plus FL-03 (can you see the friend through the broken window?) and P65 (did the sheet
convert).

**For section 6**: the load-check RPT lines (6.1), the FAIL IDs with screenshots, P1 (which way do the interior doors
open compared with the room they were built for?), P75 (do infected follow you through a door?), the FPS numbers (QP-11)
and any texture that failed to convert.
