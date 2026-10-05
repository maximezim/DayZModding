# SKY_Skyline FPS protocol (batches 1-5) + results template

**Status: NOT RUN.** Nothing has run in DayZ yet; every number below is a hypothesis until this
protocol is executed on the Windows workstation. It extends the Tower A protocol in
`reviews/perf_review.md` section 4 (setup, freeze conditions, view distances, probe, capture
method) to the street kit, interior props, floor/roof variants and a full district. Read that
section first: the same rules apply (60 s captures after 20 s settle, 3 repeats, median; diag
first, then dedicated; never edit the vanilla mission - use the `.validation` mission copy made by
`tools\tests\Invoke-ModValidation.ps1 -Layout ...`).

## 1. Configurations (same map spot T, same heading per camera position)

| ID | objectSpawnersArr | How to produce it |
|---|---|---|
| A | none (baseline) | `Invoke-ModValidation.ps1 -ModName SKY_Skyline` (no `-Layout`) |
| B | Tower A slice (8 entities) | `-Layout mods\SKY_Skyline\placement\layout.yaml` |
| D | district template (323 entities + up to 226 loot) | `-Layout mods\SKY_Skyline\placement\district_template.yaml` (fill `site.center` with T first) |
| D0 | district without props | copy of the template with every `furnish:` removed (227 fewer entities) |
| D-dec | district + 40 `Decal_Dirt` on one facade | template + 40 decal rows on T1 face S (temporarily raise `DECAL_CAPS` for the test only) |
| E | stress: 3 x template side by side | three districts, run `sky_layout.py --others` to see the server total (expect FAIL on ENTITY_CAP: that is the point) |

D vs D0 isolates the spawned-prop cost (perf batch-5 M2: decides whether furnished floor variants
with merged furniture are needed, D43). D vs B isolates the street kit + variants.

## 2. Camera positions (district: T = central intersection)

| ID | Position | Heading | Exercises |
|---|---|---|---|
| Q1 | street, central intersection, eye height | N along the street | street tiles, lights, curbs, decals, 4 lobbies |
| Q2 | inside T3 (hotel) floor 3 corridor | along the corridor | partitions, 12 props, 1.0 m doors, alpha facade behind |
| Q3 | inside T1 (office) floor 2 | across the open floor | cubicles (6), Res0 props, glass overdraw |
| Q4 | 150 m south, ground | N | prop/LOD switches through glass, street lights at range |
| Q5 | 500 m south, elevated | N | Res2/Res3 floors (1 band each), roofs (closed lid), tiles far LOD |
| Q6 | T2 garden roof | S over the edge | foliage alpha-test, planters, roof drops |

Run Q1-Q6 at VD1 and VD2 for A, B, D, D0; Q1/Q4/Q5 for E and D-dec.

## 3. Server scenarios

| ID | Scenario | Watch |
|---|---|---|
| S1 | idle 10 min (0 players), then 1 player at Q2 for 10 min | server avg/p99 frame ms (probe), A vs D vs D0 |
| S4 | infected: one `InfectedCity` zone at T, `dmax` 15 (economy/README.md), 1 player walks T3 floors 1-5 | path-failure lines in RPT, p99, infected alive per floor (B6) |
| S6 | join time and replicated entity count near T, configs A / B / D / D0 / E | join seconds, entity count (admin/diag) |
| S7 | server start: RPT time from mission load to "Mission read" and pathgraph lines | seconds, A / B / D / D0 / E (ECE_UPDATEPATHGRAPH per entity) |
| S8 | CE fill: wipe storage, start, wait 30 min, count loot items in the district | items vs report "loot items (max)", loot on props (B7) |
| S2/S3 | elevator loop / desync (Tower A, unchanged) | as in perf_review.md |

## 4. Pass / fail thresholds (hypotheses; relative to A at the same spot and settings)

| Metric | Pass | Fail |
|---|---|---|
| Client avg frame ms, D vs A, Q1/Q4/Q5/Q6 | <= +2.0 ms | > +4.0 ms |
| Client avg frame ms, D vs A, Q2/Q3 (interiors) | <= +3.0 ms | > +5.0 ms |
| Client 1 % low, D vs A | >= 85 % of A | < 75 % |
| D vs D0 (props only), any position | <= +1.0 ms | > +2.0 ms -> build furnished floor variants (D43) |
| D-dec vs D at Q1 (40 blended decals) | <= +0.5 ms | > +1.0 ms -> lower `DECAL_CAPS` |
| Server avg frame ms S1, D vs A | <= +3 % | > +6 % |
| Server start S7, D vs A | <= +20 s | > +60 s |
| Join S6, D vs A | <= +3 s | > +8 s |
| SKY lines in RPT / script logs (validation summary) | 0 FAIL lines | any |
| Res2/Res3 alpha sections visible at Q5 | 0 | > 0 |

Between pass and fail: re-run 5 times, then profile (diag menu) before changing anything.

## 5. Results template (copy per run; fill medians of 3 captures)

Run info: date ____ · build commit ____ · client GPU/CPU ____ · server CPU ____ · DayZ ____ · VD ____

### 5.1 Client frame time (ms, median of 3; 1 % low in brackets)

| Pos | A | B | D | D0 | D-dec | E | D - A | D - D0 | verdict |
|---|---|---|---|---|---|---|---|---|---|
| Q1 | | | | | | | | | |
| Q2 | | | | | | | | | |
| Q3 | | | | | | | | | |
| Q4 | | | | | | | | | |
| Q5 | | | | | | | | | |
| Q6 | | | | | | | | | |

### 5.2 Server

| Scenario | A | B | D | D0 | E | verdict |
|---|---|---|---|---|---|---|
| S1 avg frame ms | | | | | | |
| S1 p99 frame ms | | | | | | |
| S4 path-failure lines / 10 min | | | | | | |
| S4 infected alive per floor (T3 1-5) | | | | | | |
| S6 join s | | | | | | |
| S6 entities near T | | | | | | |
| S7 start s | | | | | | |
| S8 loot items in district | | | | | | |
| validation summary FAIL lines | | | | | | |

### 5.3 Visual notes (LOD pops, z-fighting, shadow leaks, flicker)

| Pos / asset | Observation | Screenshot | Follow-up |
|---|---|---|---|
| | | | |

A machine-readable copy of these tables is `reviews/fps_results_template.csv`.
After the run, apply `AFTER_TESTING.md` (budgets section) to the numbers.
