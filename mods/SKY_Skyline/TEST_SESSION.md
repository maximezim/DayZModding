# First joint test session (D60, updated D93)

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

## What I need back, in one message

`summary.md`, the RPT and script log of the diag run, TESTING IDs with FAIL plus a screenshot,
and the P1/P2/P9 observations, plus FL-03 (can you see the friend through the broken window?) and P65 (did the sheet
convert).
