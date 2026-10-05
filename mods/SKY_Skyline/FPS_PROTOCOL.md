# SKY_Skyline FPS protocol (batches 1-5) + results template

**Status: NOT RUN.** Nothing has run in DayZ yet; every number below is a hypothesis until this
protocol is executed on the Windows workstation. It extends the Tower A protocol in
`reviews/perf_review.md` section 4 (freeze conditions: fixed time/weather, client preset, VD1 =
1000/1000 m and VD2 = 3000/1600 m; capture method: 60 s still after 20 s settle, 3 repeats,
median). It **replaces** that protocol's config C (3 x 3 Tower A) with config E below.

## 0. Prerequisites (do once, in order; nothing below is valid without them)

| # | Step | Why |
|---|---|---|
| 0.1 | **Server frame probe** `SKY_PerfProbe`: a separate, diag-only, never-shipped server mod (`modded class MissionServer`, accumulate `OnUpdate(float timeslice)`, every 10 s print avg / p99 / max frame ms to `script_*.log`; once at minute 15 print the count of `Land_SKY_*` objects and of items within 80 m of T, and infected per 3.5 m height band in T3's footprint). Verify `MissionServer.OnUpdate` in `P:\scripts\5_Mission` first (enforce-coder). **Not written yet: new mod code needs your go-ahead (CLAUDE.md "no mods unless asked"), PENDING B11.** Load it with `-ServerMods SKY_PerfProbe`. | S1/S4/S6 have no other server-side metric source: RPT has no frame data |
| 0.2 | Frame cap: start config A once, read the probe's idle avg. If it sits at a cap, restart with `-limitFPS` raised well above it (verify the parameter and its default on this build, PENDING B12) and record it in the run info. **Headroom** = probe avg frame ms < 50 % of the frame budget at that cap. | an idle A and D both at the cap would "pass" with no headroom |
| 0.3 | Survey the district site with `exportRadius` >= the value in the layout report (73 m for the template), after one run with the layout spawned; save `storage_1\export\mapgrouppos.xml` as `placement\surveys\<site>_mapgrouppos.xml`. Every D/D0/E run passes it with `-MapGroupPos`. | without it no loot spawns on spawned buildings (ENTITY_CAP counts loot) |
| 0.4 | Verify the RPT "mission ready" line text and the ADM connect/spawn line texts on the first A run; note them here: ready = `________`, connect = `________`, spawn = `________` (PENDING B12). | S6/S7 timing source |
| 0.5 | Noise floor: run A **twice** (cold, then warm). The delta between the two is the noise band; no delta smaller than 2 x noise counts as a result. | |

## 1. Configurations (same site T, same mission copy path for all)

All configs go through `tools\tests\Invoke-ModValidation.ps1` so they share the same fresh
`.validation` mission copy, the same SKY economy and the same wipe state:

| ID | Command (plus `-ServerMods SKY_PerfProbe -Minutes <see §3>`) | Spawned entities | Loot items (max) |
|---|---|---|---|
| A | `-Baseline` | 0 | 0 |
| B | `-Layout mods\SKY_Skyline\placement\layout.yaml -MapGroupPos <site>_mapgrouppos.xml` | 8 | see its report |
| D | `-Layout <district.yaml> -MapGroupPos ...` (the template with site filled in) | 323 | 226 |
| D0 | `-Layout placement\district_template_noprops.yaml -MapGroupPos ...` (D without furniture; same site filled in) | 96 | 178 |
| D-dec | `-Layout placement\district_template_decals.yaml ...`: D with its 3 decals replaced by 12 `Decal_Dirt` on **T4 face E**, mechanical storey (z 14.1), u = -11..+11 m (12 = `DECAL_CAPS` per tower; one facade) | 332 | 226 |
| E | `-Layout d1.yaml,d2.yaml,d3.yaml,d4.yaml -MapGroupPos ...` (4 districts at different centres; the 4th is checked with `--others` automatically) | 4 x 323 | 4 x 226 (= 2196 with entities, the largest legal set under `ENTITY_CAP` per_server 2500) |

Warm-start variants: add `-NoWipe` to reuse the previous copy and its storage (S7 warm).
If a cap is ever raised (AFTER_TESTING §3), re-run E **at the new cap** before keeping it.

## 2. Camera positions (district: T = central intersection)

Record for each: world X / Y / Z, heading (deg), date/time freeze, weather (run info).

| ID | Position | Heading | Exercises | Configs |
|---|---|---|---|---|
| Q1 | street, central intersection, eye height | N along the street | street tiles, lights, curbs, 4 lobbies | all |
| Q2 | inside T3 (hotel) floor 3 corridor | along the corridor | partitions, props, 1.0 m doors, glass behind | D, D0 (no shell in A) |
| Q3 | inside T1 (office) floor 2 | across the open floor | cubicles, Res0 props, glass overdraw | D, D0 |
| Q4 | 150 m south, ground | N | prop/LOD switches through glass, lights at range | all |
| Q5 | 500 m south, elevated | N | Res2/Res3 floors and roofs, tile far LOD | all |
| Q6 | T2 garden roof | S over the edge | foliage alpha-test, planters | D, D0 |
| Q7 | facing T4 face E at 10 m and at 60 m (two captures) | W | the 12 decals of D-dec | D, D-dec |

Interior/roof positions have no shell in A: their thresholds are **D vs D0** (same shell).
Use the DayZDiag free camera at the recorded coordinates for client-side numbers where possible:
`tools\launch\Start-DiagLocal.ps1 -Mods SKY_Skyline -Mission "<ServerDir>\mpmissions\<mission>.validation"`
(the copy made by the validation script; diag runs are the only ones with the diag Statistics
overlay and profiler). Dedicated runs (retail client, BattlEye) use PresentMon / CapFrameX.

## 3. Server scenarios (dedicated; run lengths count from the "mission ready" line)

| ID | Scenario | `-Minutes` | Metric (source) |
|---|---|---|---|
| S1 | idle: 0 players 15 min (CE settles), then measure 15 min | 35 | probe avg / p99 / max frame ms, last 15 min |
| S1b | N = 4 (ideally 10) clients standing at Q1 for 15 min after settle | 40 | probe avg / p99 frame ms |
| S4 | infected: the generated zone (template: `InfectedCity` dmin 6 / dmax 12, r 54); 1 player walks T3 floors 1-5 | 40 | RPT path-failure lines naming SKY classes or T's area; probe p99; probe infected per height band |
| S5 | visual at 17:00: shadows, LOD pops walking Q1 -> Q5 | - | screenshots / notes |
| S6 | join: `-KeepRunning`; first join, walk to T, log out; then 3 x rejoin within the same session | 30 | seconds from ADM connect line to spawn line (0.4 texts) |
| S7 | server start: cold (fresh copy) and warm (`-NoWipe`, second boot) | 8 each | seconds from first RPT line to the "mission ready" line; validation `summary.json` cross-check with process start |
| S8 | CE fill: fresh copy, 40 min | 45 | probe item count within 80 m of T at minute 15 and 40 vs the report's "loot items (max)" |
| S2/S3 | elevator loop / desync (Tower A, unchanged) | 15 | as in perf_review.md |

## 4. Pass / fail thresholds (hypotheses)

Client thresholds are looser than Tower A's (+2 ms vs +1 ms) because a district puts ~40 x the
entities on screen; the server thresholds keep Tower A's strictness.

| Metric | Pass | Fail | Decides |
|---|---|---|---|
| Client avg frame ms, D vs A, Q1/Q4/Q5 | <= +2.0 ms | > +4.0 ms | district as a whole |
| Client avg frame ms, D vs D0, Q2/Q3/Q6 | <= +1.5 ms | > +3.0 ms | prop **render** cost -> prop LOD cuts (not D43) |
| Client 1 % low, D vs A | >= 85 % of A | < 75 % | |
| D-dec vs D at Q7 (10 m / 60 m) | <= +0.5 ms | > +1.0 ms | `DECAL_CAPS` = budget / ((D-dec - D) / 12) |
| VRAM delta D vs A (diag stats or GPU counter) | <= 150 MB | > 250 MB | texture sizes |
| Server S1 avg, D vs A | <= +3 % **and** headroom (0.2) kept | > +6 % or headroom lost | |
| Server S1 p99, D vs A | <= +2 ms | > +5 ms | |
| Server S1/S1b avg, **D vs D0** (props only) | <= +2 % | > +4 % | **D43 / D27** (merge furniture into floor variants) |
| S6 join, D vs D0 | <= +1 s | > +3 s | D43 |
| S7 start (cold and warm), D vs A | <= +20 s | > +60 s | ENTITY_CAP |
| S7 start, D vs D0 | <= +5 s | > +15 s | D43 (pathgraph updates per entity) |
| S1b avg with N clients, E vs A | headroom kept | headroom lost | ENTITY_CAP per_server |
| S4 SKY path-failure lines / 10 min, D | 0 | any | furniture aisles / doors |
| S4 p99, D vs D0 | within the S1 band | > S1 fail | infected density (B6) |
| S8 loot items | 50-100 % of the report's max | < 10 % | B7 (only with `-MapGroupPos`!) |
| Far-LOD blended alpha | static gate: `check_assets.py` (0 blended alpha in Res2+) | any | - |
| SKY FAIL lines (validation `summary.md`) | 0 | any | B9 |

Record per-entity cost as (D - D0) / 227 for S1, S6, S7: it predicts the merged-furniture variant
(227 -> ~30 spawned props). Between pass and fail: re-run 5 times, then profile in the **diag**
run (Start-DiagLocal with the `.validation` mission) before changing anything.

Over-budget assets (Apartments/Hotel Geometry 40/38 comps, roof Res1 128, Tower A core 81 comps)
are **accepted** unless a district threshold fails **and** the diag profiler attributes the cost
to that asset. Optional S9: player + 3 infected + gunfire on T2/T3 floors, D vs D0 (collision /
Fire Geometry load).

## 5. Results template (copy per run)

Run info: date ____ · commit ____ · client GPU/CPU ____ · server CPU ____ · DayZ build ____ ·
limitFPS ____ · noise band (A vs A) ____ · VD ____ · site T (X, Z) ____ · time/weather ____ ·
loot spawned (S8) ____ · probe build ____

### 5.1 Client frame time (ms; median of 3 [min-max]; 1 % low in brackets)

| Pos | A | B | D | D0 | D-dec | E | D - A | D - D0 | verdict |
|---|---|---|---|---|---|---|---|---|---|
| Q1 | | | | | | | | | |
| Q2 | - | - | | | | | - | | |
| Q3 | - | - | | | | | - | | |
| Q4 | | | | | | | | | |
| Q5 | | | | | | | | | |
| Q6 | - | - | | | | | - | | |
| Q7 10 m | - | - | | | | - | - | - | |
| Q7 60 m | - | - | | | | - | - | - | |

### 5.2 Server

| Scenario | A | B | D | D0 | E | D - A | D - D0 | (D - D0)/227 | verdict |
|---|---|---|---|---|---|---|---|---|---|
| S1 avg ms | | | | | | | | | |
| S1 p99 ms | | | | | | | | | |
| S1b avg ms (N = __) | | | | | | | | | |
| S4 path failures / 10 min | - | - | | | | | | | |
| S4 infected per floor (T3 1-5) | - | - | | | | | | | |
| S6 join s (median of 3) | | | | | | | | | |
| S7 start s cold | | | | | | | | | |
| S7 start s warm | | | | | | | | | |
| S8 loot items (min 15 / 40) | | | | | | | | | |
| entities near T (probe) | | | | | | | | | |
| validation FAIL lines | | | | | | | | | |

### 5.3 Visual notes (LOD pops, z-fighting, shadow leaks, flicker, S5)

| Pos / asset | Observation | Screenshot | Follow-up |
|---|---|---|---|
| | | | |

A machine-readable copy is `reviews/fps_results_template.csv` (in `mods/SKY_Skyline/`).
After the run, apply `AFTER_TESTING.md` §3.
