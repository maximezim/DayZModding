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

1. Rerun the survey with `"exportRadius": 40` once the tower is spawned (step 2 done). For a district use the
   radius `sky_layout.py` prints in the report notes ("loot export: exportRadius >= N m", e.g. 73 m for the
   template) - a smaller radius silently leaves outer floors and props without loot.
2. The survey calls `GetCEApi().ExportProxyData(centre, 40)`, which writes `<mission>\storage_1\export\mapgrouppos.xml`.
3. Copy its `Land_SKY_*` `<group>` lines into the mission's `mapgrouppos.xml`.

The engine's own export is used instead of computing the `rpy`/`a` orientation fields by hand.

## 4. Districts (batch 5): streets, blocks, tower variants, furniture, decals

Start from `district_template.yaml` (site coordinates left blank on purpose; `--strict` refuses it
until a surveyed site is filled in). It shows every key:

* `streets`: 12 m grid of combined `Street_*` tiles - N-S columns `ns`, E-W rows `ew` over `extent`;
  intersections are automatic, `crossings` become zebra tiles, `lights_every: N` puts a
  `StreetLight` on every N-th straight tile (cap `LIGHT_CAP`). With a survey, every tile is checked:
  ground may not poke through it nor fall more than slab + skirt (0.8 m) below it.
* `blocks`: cell rectangles between streets (a tower needs 3 x 3 cells); towers inside use `at`
  (block-local) and must keep `BLOCK_SETBACK` from the block edge; footprints may not overlap each
  other or any street tile.
* towers: `floors` = exactly 5 variants (`office | apartments | hotel | mechanical`; the unchanged core
  has 5 typical-floor stops), `roof` = `helipad | garden | mechanical`, `furnish` = `{level: set}` from
  `skyspec.FURNISH`. Caps `PROP_CAPS` (25 per floor, 70 per tower, 1.2 m aisles) and `ENTITY_CAP`
  (entities + loot items: 800 per district, 2500 per server - pass the other districts' outputs with
  `--others a.json,b.json`) fail the run; the report lists entity counts per kind and per tower.
* `decals`: placed flush on a tower facade (face N/E/S/W, `u` along it, `z` bottom height) at the
  per-type `DECAL_OFFSET` (D16, D19); cap `DECAL_CAPS` (12 per tower).
* Roof drops: each roof class writes its own `ROOF_DROP_POINTS` into `cfgeventspawns_snippet.xml`.

Self-test: `python placement/tests/test_sky_layout.py` (synthetic surveys, no game).

## Files
| File | What |
|---|---|
| `layout.yaml` | The Tower A slice site (one tower) |
| `district_template.yaml` | District template: streets, blocks, 4 tower variants, furniture, decals (unfilled site) |
| `sky_layout.py` | Generator + validation (`--strict` for live servers) |
| `tests/test_sky_layout.py` | Synthetic-survey tests (flat, slope, building, vegetation, overlap) |
| `out/` | Generated: `sky_objects.json`, `cfggameplay_snippet.json`, `cfgeventspawns_snippet.xml`, `placement_report.md` |

The committed `out/` uses the **placeholder** site (7500, 7500, Y = 0). Do not deploy it.
