# SKY placement (Chernarus, `dayzOffline.chernarusplus`)

Tower modules are **not** map objects: they are spawned at server start by the vanilla
`objectSpawnersArr` mechanism (`3_game/objectspawner.c`). It creates class-named
objects with `ECE_UPDATEPATHGRAPH` and then calls
`ProcessMarkedObjectsForPathgraphUpdate()`, so infected get a navmesh for the tower.

## 1. Survey a candidate site (in DayZDiag or on a local dedicated server)

1. Pick a candidate centre on the map (X, Z) that looks flat in the in-game map or a map tool.
2. Create `server\profiles\dedicated\SKY_survey_request.json` (or the `diag-server` profile):
   ```json
   { "label": "site1", "center": [X, Z], "yaw": 0, "halfW": 13, "halfD": 13, "step": 2.0, "exportRadius": 0 }
   ```
3. Start the server with the mod (`tools\build\Build-And-Run.ps1 -ModName SKY_Skyline -Mode Dedicated -NoClient`).
   After ~15 s, `SKY_survey_result.json` is written next to the request. The `[SKY] site survey` line is in `script_*.log`.
4. Copy it to `placement/surveys/site1.json`, then set in `layout.yaml`: `site.center`, `site.survey: surveys/site1.json` and `placeholder: false`.
5. `python placement/sky_layout.py --strict` must say **PASS**. Failures name the problem: slope beyond the 2.2 m skirt, an existing `Land_*` building inside the footprint, or overlapping towers. Vegetation in the footprint is only a warning; clear it with a `cfgIgnoreList`/area flag or move the site.

## 2. Deploy to the mission

1. Copy `placement/out/sky_objects.json` to `<mission>\sky\sky_objects.json`.
2. Merge `placement/out/cfggameplay_snippet.json` into `<mission>\cfggameplay.json` (`WorldsData.objectSpawnersArr`).
3. Economy: see `economy/README.md` (CE folder, mapgroupproto merge, roof-drop event positions from `placement/out/cfgeventspawns_snippet.xml`).

## 3. Loot positions (mapgrouppos)

CE only spawns loot in buildings listed in `mapgrouppos.xml`. Spawned towers are not in it, so let the engine export their entries:

1. Rerun the survey with `"exportRadius": 40` once the tower is spawned (step 2 done).
2. The survey calls `GetCEApi().ExportProxyData(centre, 40)`, which writes `<mission>\storage_1\export\mapgrouppos.xml`.
3. Copy its `Land_SKY_*` `<group>` lines into the mission's `mapgrouppos.xml`.

The engine's own export is used instead of computing the `rpy`/`a` orientation fields by hand.

## Files
| File | What |
|---|---|
| `layout.yaml` | Sites, towers (blocks/roads come with the street kit) |
| `sky_layout.py` | Generator + validation (`--strict` for live servers) |
| `tests/test_sky_layout.py` | Synthetic-survey tests (flat, slope, building, vegetation, overlap) |
| `out/` | Generated: `sky_objects.json`, `cfggameplay_snippet.json`, `cfgeventspawns_snippet.xml`, `placement_report.md` |

The committed `out/` uses the **placeholder** site (7500, 7500, Y = 0). Do not deploy it.
