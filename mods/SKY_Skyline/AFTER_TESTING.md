# After testing: what to flip, in which order

Use this after the in-game runs in `TESTING.md` and `FPS_PROTOCOL.md`. Every untested assumption
is one named value in `assets/skyspec.py` (details and asset lists: `PENDING_VERIFICATION.md`).
Change only what a test actually disproved, regenerate, rebuild, and re-run the listed test IDs.

Regenerate / rebuild commands (repo root, Windows):
```
python mods\SKY_Skyline\assets\gen_configs.py              # configs, model.cfg, rvmats
python mods\SKY_Skyline\economy\gen_economy.py              # CE files
mods\SKY_Skyline\assets\Build-SkyAssets.ps1 -Models -Blender "<blender.exe>"   # P3Ds (only when a row says re-export)
tools\tests\Invoke-ModValidation.ps1 -ModName SKY_Skyline -Layout <layout.yaml> -Blender "<blender.exe>"
```

## 1. Parameters (flip only on a FAIL of the named test)

| # | Test that decides it | If it FAILS, change | Then run | Re-test |
|---|---|---|---|---|
| P1 | D-01 lobby door opens outward / into the wall | `DOOR_SWING_SIGN = -1` (lobby right but one prop door wrong: flip that door's `orient` in its `door(...)` entry instead) | `gen_configs.py` (no re-export) | D-01, P3-10..14, P3-22 |
| P1b | doors open too far / not far enough | `DOOR_OPEN_ANGLE` (radians) | `gen_configs.py` | D-01, P3-10..14 |
| P2 | D-03 elevator leaves slide into each other | `ELEVATOR_SLIDE_SIGN = -1` | re-export core: `build_towera.py -- --out addons --only core` | D-03, D-04 |
| P3 | F-xx / F4-14 / P3-13 penetration wrong, or RPT "Cannot open ... penetration" | `PENETRATION["concrete"]` / `["glass"]` paths (and the flag to `True` once verified) | re-export every P3D (all four builders) | Fire-geometry rows §2, F4-14, P3-13 |
| P4 | RPT "Cannot open ... env_land_co" or black reflections | `ENV_MAP` | `gen_configs.py` | any visual row + validation summary |
| P5 | P3-19 / lobby: explosives damage doors, or RPT armor-class warning | `ARMOR_EXPLOSION_CLASS` | `gen_configs.py` | P3-19, K-xx door damage |
| P6 | driving sounds like concrete and an asphalt surface is found on P: | `ROADWAY_ASPHALT` | re-export street kit (`build_kit.py`) | street-kit driving rows |
| P7 | lamps / lit windows too dim or blooming at night | `EMISSIVE_LAMP`, `EMISSIVE_WINDOW` | `gen_configs.py` | night visual rows, W-xx |
| P8 | vehicles snag on tile seams | `ROAD_GEO_THICKNESS = 0.05` | re-export street kit | street-kit driving rows |
| P9 | P5-YAW: off-centre props / decals of a yaw-90/270 tower mirrored or rotated the wrong way | `YAW_SIGN = -1` (only the written engine yaw flips) | `python placement/sky_layout.py --layout <yaml> --strict` (no rebuild) | P5-YAW, P5-06, P5-05 |

## 2. Behaviour checks (no parameter; one targeted change each)

| # | If the test shows | Do |
|---|---|---|
| B1 / B2 | decals or the manhole do not spawn/render without Geometry | add a tiny Geometry far below in `build_kit.build_decal` / `build_manhole`, re-export street kit |
| B3 | a vanilla building rvmat uses a Stage3 `_mc` macro map | add a grime `_mc` to `sky_brick` / `sky_concpanel` in `gen_configs.rvmat_super`, lower `DECAL_CAPS` |
| B4 | dark window cells glow under `sky_windows_lit` | split the lit set into its own atlas (`gen_textures.windows`) |
| B5 | a lockpick offers "lock" on a prop door | generate one empty `class Land_SKY_<Prop> extends Land_SKY_Props_Base {}` per door prop |
| B6 | infected never reach upper floors / overload | tune the district's `InfectedCity` zone `dmin/dmax` (economy/README.md); no code change |
| B7 | no `mapgrouppos` entries / loot on spawned props | delete the prop groups from `skyspec.LOOT` (Locker, Desk, ReceptionDesk, Kitchenette), `gen_economy.py` |
| B8 | street lights block the sidewalk, or decals z-fight | move the light offset in `sky_layout.py` (0.5 m inside the curb) / raise `DECAL_OFFSET` per type |
| B9 | a clean run shows FAIL lines, or a broken build shows none | adjust `$FailPatterns` / `$ModScoped` in `tools\tests\Invoke-ModValidation.ps1` (regexes only) |
| B10 | you need to re-export P3Ds (P2/P3/P6/P8, B1/B2) | install Blender 4.2 LTS + Arma Toolbox next to Blender 5.2 and pass `-Blender`, or port `skygeo.export_p3d` to the DayZ Object Builder exporter and prove the output identical |
| B11 | you want the server-side FPS numbers | ask for the `SKY_PerfProbe` diag server mod (FPS_PROTOCOL §0.1), then run the protocol with `-ServerMods SKY_PerfProbe` |
| B12 | first run shows the real ready/connect/spawn log texts and `-limitFPS` | write them into FPS_PROTOCOL.md §0.2/§0.4 (and the validation script's patterns if useful) |

## 3. Budgets and caps (from FPS_PROTOCOL.md results)

| Result | Change |
|---|---|
Only valid with FPS_PROTOCOL.md §0 done (probe, frame cap, mapgrouppos export, noise floor).

| Result (FPS_PROTOCOL.md §4 row) | Change |
|---|---|
| **server** D vs D0 (S1/S1b avg, S6, S7) over threshold | build furnished floor variants with merged furniture (D43 / D27); keep only door props spawned |
| **client** D vs D0 (Q2/Q3/Q6) over threshold, server D vs D0 fine | cut prop LODs (Res1/Res2 triangles, sections) - not D43 |
| D-dec vs D at Q7 > +1 ms | `DECAL_CAPS["per_tower"]` = budget / ((D-dec - D) / 12) |
| S1/S1b/S6/S7 pass with headroom (0.2) at E | raise `ENTITY_CAP` / `PROP_CAPS` by 25 %, then re-run E **sized to the new cap** before keeping it |
| S8 loot < 10 % of max **with** `-MapGroupPos` | B7 rollback (prop loot groups) |
| OVER assets (Apartments/Hotel Geometry, roof Res1, Tower A core comps) | accepted unless a district threshold fails **and** the diag profiler attributes it to that asset; then apply the cut named in its review (reviews/batch4_perf.md L1, perf_review.md M2). Tower A core 81 > 80 comps: accepted statically (rule 1 freezes Tower A) |
| any threshold in the in-between band | 5 re-runs, then diag profiler (Start-DiagLocal with the `.validation` mission) |

## 4. Status rules (manifest.yaml)

* `built-unverified` -> `packed` only after `Invoke-ModValidation.ps1` built, signed and loaded it with 0 SKY FAIL lines.
* `packed` -> `tested` only when every TESTING.md row for that asset passed in diag **and** dedicated.
* `tested` -> `done` only after the FPS protocol row(s) covering it passed. Nothing is `done` today.
* Record the commit, date and tester in the TESTING.md sign-off table; change statuses in
  `manifest.yaml` (hand-written sections) and `gen_manifest.py` (generated kit section).
