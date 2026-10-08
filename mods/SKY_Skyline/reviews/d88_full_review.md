# D88 full quality review (static, no DayZ run)

This review covers everything from D1 to D87. It was done in four steps:

1. A full-mod security audit and a full-mod performance audit over every script, config and tool.
2. The fixes for those audits.
3. A re-review of the fixes by both reviewers.
4. A re-run of the gates, plus a docs consistency pass.

There were no Critical findings in either audit. The perf audit found 2 High findings in script code (H1 lights, H2 hordes) and one asset-side High (H3, view / fire density); the re-review found one more High in a fix. Every script and tooling finding is fixed except those listed under "Accepted / deferred".

## Findings and fixes

| Source | Sev | Finding | Fix |
|---|---|---|---|
| security | M1 | Items nested in a guarded kennel (a bag in it, a stored gun's attachments) could still be taken | modded `ItemBase` `CanReleaseCargo / CanReleaseAttachment / CanReceiveItemIntoCargo / CanReceiveAttachment` refuse when the hierarchy root is a guarding kennel |
| security | M2 | A guarded kennel cannot be damaged or moved. In a doorway it seals the room | `CanBePlaced` refuses a placement within 2.5 m of a building door (`GetDoorSoundPos`). The server re-checks (`actiondeployobject.c:67`) |
| security re-review | M | ...and it could also seal a player base gate (`Fence` is a `BaseBuildingBase`, not a `Building`) | also refused within 4 m of a `BaseBuildingBase` ("Too close to a door or gate") |
| security | M3 | Elevator car level net-synced on a 0..15 range; Core33 has 35 stops | range 0..`ELEVATOR_MAX_STOPS - 1` (64). Stop lists above it are cut |
| security | L1-L5 | Lazy limiter before the first use; search drop could land behind a wall; rare items without a cap; site survey without clamps; key-in-repo check missed junctions | limiter created on demand; `ClearDrop` raycast; rare items capped at 3 per class per hour; survey half sizes 1..1000 m and step >= 0.25 m; `Test-DzPathInRepo` (real path) |
| security re-review | L | The key path check did not follow a junction to a junction, nor 8.3 names (`DAYZMO~1`) | `Resolve-DzRealPath` follows up to 32 hops per segment and expands short names |
| security re-review | L | `Unregister` from a destructor after statics are torn down | null guard |
| perf | H1 | Every lit building created its lights on init: a terrain city means thousands of `ScriptedLightBase` | `SKY_LightDirector` (client, 1 s): lights the nearest 24 within 150 m, unlights them past 180 m |
| perf re-review | M | Candidate list unbounded with O(n^2) inserts; the first tick could create 24 x 2-4 lights in one frame | candidates bounded to 24; at most 6 buildings lit per tick; arrays reused |
| perf | H2 | Horde cap fixed at 72 whatever the player count; 6 AI spawned in one frame | live cap 12 + 4 per online player (<= 72); one infected per 250 ms |
| perf | H3 | View / Fire Geometry density not gated | `check_assets` warns above 2x (view) and 3x (fire) the geo budget. No model is over |
| perf | M4 | Budgets keyed by LOD order (a Res 1.5 LOD would be measured as Res 2); no LOD-step check | budgets keyed by resolution; LOD-step warning below 5 %; exact section counts |
| perf | M4 follow-up | Large buildings dropped from Res1 straight to a box shell | `exterior_lod`: a Res 1.5 LOD built from the exterior faces only (no decals, opaque far glass) on every city building |
| perf | M5 | Sewer water only animated by the server; map objects of a terrain are not networked (P29) | client fallback `SKY_Underground.StartClient`, derived from the synced rain |
| perf re-review | H | ...but pieces only registered on the server, so the client fallback never ran | pieces register on both sides; soaking / drowning stay in the server `Tick` |
| perf re-review | M / L | Kennel door scan every frame while the hologram moves; `GetHierarchyRoot` on every inventory query; `SpawnOne` left in the queue after `Stop`; `s_All` kept at mission end | client scan at most every 250 ms (the server stays exact), member array reused; kennel count gate (one compare when no kennel is loaded); `SpawnOne` returns if the director stopped; `StopClient` clears the registry |
| perf | L7, L9, L12 | `m_Under` unbounded; door names rebuilt per call; carpet 2048 | bounded to players + 16; cached door anims; carpet 1024 (wallpaper stays 2048: 512 px/m on close walls) |
| docs | - | DECISIONS had no D81 row; TESTING sign-off stopped at §25 (26 sections had no row); PROGRESS_REPORT listed done work (D75 hull test, street kit 3, night lights) as open and stale counts | D81 row; 27 sign-off rows added (§26-§52); report corrected |

## Accepted / deferred (with the reason)

- **Placement survey (security M4)**: the layouts were never surveyed on a real site. This is a release gate (ROADMAP),
  not a cloud task: `SKY_SiteSurvey` runs on the chosen terrain.
- **Far-shell step (3 warnings)**: CourtyardBlock Intact / Ruined and Hospital Intact go from Res 1.5 (8-14 k tris) to a 300-700-tri Res 2.
  This is a step of 4-5 %, against a 5 % warning threshold. In game the Res 2 distance is above 250 m for these footprints. Check: TESTING RV-03 (P58).
- **Grid bucketing (perf M6)**: the director loops are linear over at most 4096 entries once a second. That is fine at the current scale;
  bucket them if the profiler shows `SKY_LightDirector.Tick` above 0.2 ms.
- **Shared rate limiters (L8), rvmat count growth (L11)**: noted. They have no measurable cost before T1.
- **Kennel scan on the client**: the hint may lag 250 ms while the hologram moves. The server decision is exact.

## Gates after the fixes

| Gate | Result |
|---|---|
| `test_city.py` (wedge slots, search points) | PASS (191) |
| `test_kit.py` | PASS (279) |
| `test_ruin_cuts.py` | PASS (120 models) |
| `test_slits.py --selftest` | PASS |
| `test_towera.py` | PASS (81) |
| `check_assets.py` | 289 checked, 0 fail, 3 LOD-step warnings (above) |
| `test_texture_refs.py` | PASS (85 / 0 missing) |
| `--check` on gen_configs, gen_manifest, city_progress, gen_economy, gen_terrain | all up to date |
| `enscript_xref.py` | OK, 26 files resolve |
| `Invoke-SelfTest.ps1` | all self-tests passed |

`test_conceal --city` and `test_slits --city` were not re-run. Res0, Geometry, Fire and View are unchanged since the D87
scans (PASS); the new Res 1.5 LOD is render-only and inside the Res1 hull. `test_p3dwriter.py` needs Arma Toolbox
(optional backend, not installed in the cloud).

## Visual check

![Apartment block, three states](img/d88_aptblock_states.png)

![Market shop interior](img/d88_shoprow_interior.png)

Facades, ruin cuts, clutter and shop rooms read as intended. The gap is that the interior walls are plain (paint only).
Wall dressing (skirting, switches, radiators, frames) is the next content batch.
