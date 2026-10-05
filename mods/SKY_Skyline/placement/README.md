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

1. Copy `placement/out/sky_objects.json` (or `out_district/` for a district) to `<mission>\sky\sky_objects.json`. For a district also merge `zombie_territories_snippet.xml` into `<mission>\env\zombie_territories.xml`. `tools\tests\Invoke-ModValidation.ps1 -Layout ...` does all of this on a mission copy for testing.
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
* Streets sit on **one** plane (max surveyed ground under any tile + clearance): no steps at seams; a
  tile whose ground falls more than slab + skirt (0.8 m) below it, or that has no survey samples, fails.
  So a district needs a site with <= ~0.75 m of relief under its streets (about 0.7 % over 108 m):
  pick flat sites (D46). Lobbies 0.3-0.5 m off the sidewalk warn, > 0.5 m fail in `--strict`.
* Infected: one `InfectedCity` zone per district in `zombie_territories_snippet.xml` (economy/README.md).
* A failed run writes only `placement_report.md` and `*.FAILED.*` files - nothing deployable.

Self-test: `python placement/tests/test_sky_layout.py` (synthetic surveys, no game).

## Files
| File | What |
|---|---|
| `layout.yaml` | The Tower A slice site (one tower) |
| `district_template.yaml` | District template: streets, blocks, 4 tower variants, furniture, decals (unfilled site) |
| `district_template_noprops.yaml`, `district_template_decals.yaml` | FPS protocol configs D0 (no furniture) and D-dec (12 decals on one facade) |
| `sky_layout.py` | Generator + validation (`--strict` for live servers) |
| `tests/test_sky_layout.py` | Synthetic-survey tests (flat, slope, building, vegetation, overlap) |
| `out/` | Generated: `sky_objects.json`, `cfggameplay_snippet.json`, `cfgeventspawns_snippet.xml`, `placement_report.md` |

The committed `out/` uses the **placeholder** site (7500, 7500, Y = 0). Do not deploy it.

## 5. Cities: block fill (D57)

`city_template.yaml` generates a city quarter: `python placement/sky_layout.py --layout placement/city_template.yaml --out placement/out_city`.

* A block with `fill: {zone: downtown | midtown | residential | industrial | frontline, seed: N}` is packed lot
  by lot along its four street edges by `placement/city_fill.py`: fronts face the street, corner shops on the
  corners, party-wall buildings flush, detached ones with the zone's gap, kiosks / sheds capped per block,
  rubble lots by chance; ruin state per building from the zone's (intact, damaged, ruined) mix. The zones live
  in `skyspec.CITY_ZONES`. The same seed always gives the same city; change the seed to re-roll one block.
* `buildings: [{type, ruin, at, yaw}]` places landmarks (police, clinic, fire station, supermarket) first.
* Every building gets its ground height from the survey (1.5 m skirt) or the street plane, and the same
  overlap / foreign-object checks as towers. The report lists every archetype by intact / damaged / ruined.
* `site.target: spawner` (default) obeys ENTITY_CAP (every spawned building is a replicated entity);
  `target: terrain` is for a whole city baked into a custom map: no cap, plus `city_objects.csv`
  (class, x, y, z, yaw) for the terrain import (P11). Render any layout with
  `assets/blender/preview_district.py -- --objects <out>/sky_objects.json --out <dir>`.

