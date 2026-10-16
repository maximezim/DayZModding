# SKY terrain sources (D63, MOD_DEVELOPMENT_GUIDE 4.3 Level 2)

`gen_terrain.py` turns a layout run with `site.target: terrain` into the GIS inputs Terrain Builder imports.
The formats follow Bohemia's DayZ-Samples `Test_Terrain` (`source/gis_input/terrain.asc`, `mask_lco`,
`sat_lco`, `source/layers.cfg`):

```
python mods/SKY_Skyline/placement/sky_layout.py --layout mods/SKY_Skyline/placement/citylife_template.yaml --out mods/SKY_Skyline/placement/out_citylife
python mods/SKY_Skyline/terrain/gen_terrain.py            # writes terrain/out/ (--check in validation)
```

| File | Content |
|---|---|
| `out/heightmap.asc` | 1024 x 1024 m at 1 m. City plateau at 120 m that blends into rolling hills over 90 m. Trenches under every sewer and metro piece (bottom 1.5 m under the piece floor, 0.75 m past its footprint). A dry river valley under every bridge |
| `out/mask_lco.png` | Surface mask, 1 px = 1 m. Concrete under the city, tall grass on the blend, grass and conifer patches outside, gravel in the riverbed |
| `out/sat_lco.png` | Colour map on the same grid |
| `out/layers.cfg` | Layers mapped to the vanilla `DZ\surfaces\data\terrain\*.rvmat` names used by the sample, plus the legend colours |
| `out/objects_terrain.csv` | The layout's objects in terrain coordinates (x + 512, y + 120, z + 512), ready to import |
| `out/terrain.json` | The transform and some stats |

Not done here, because it needs the Windows tools and your go-ahead on the map name and size (P28, TESTING §28):
- the Terrain Builder project;
- the `.wrp` build;
- CfgWorlds;
- the navmesh;
- the mission folder.

Why the underground needs this: objectSpawnersArr places objects on the terrain surface, and a vanilla heightmap
cannot be cut. The cut-and-cover pieces therefore sit in these trenches with their roofs just under street level.
On vanilla maps the hatches stay sealed (D58).

## Terrain mapper: modify an existing map (D104)

Vanilla maps ship binarized, so they are never edited. The mapper captures a region of a vanilla map in-game, edits a
copy (flat pads under the cities, graded roads, painted surfaces) and writes the Terrain Builder inputs for a new
terrain mod (MOD_DEVELOPMENT_GUIDE 4.3 Level 2).

1. **Capture** (diag server, vanilla mission, no players). Copy `projects/capture_request_cher_ne.json` to
   `server\profiles\diag-server\SKY_survey_request.json` and start the server. `SKY_TerrainCapture.c` consumes the
   request and writes `SKY_capture\<label>_heights.txt` (cm, north row first), `_surfaces.txt` (surface index per cell),
   `_objects.txt` (`type;model;x;y;z;yaw;pitch;roll;scale`) and `_meta.json` (written last, `"complete": true`).
   Bounds: cell 0.5-50 m, 4096 cells per axis, 4.3 M cells, 1.5 M objects. A whole Chernarus at 7.5 m fits.
2. **Map** (any OS): `python mods/SKY_Skyline/terrain/terrain_mapper.py --project mods/SKY_Skyline/terrain/projects/chernarus_skyline.yaml`.
   The project YAML lists:
   - `source`: `capture` + `label`, or `heightmap` (an ESRI ASCII of a terrain you own);
   - `grid`: output `cell`, `crop` rectangle, `origin: zero` for a new smaller map or `keep`;
   - `sites`: `layout_out` (a placement output, world coordinates) or `polygon`; `level` (`layout` = street level,
     `auto` = median ground, or metres), `margin`, `max_slope`, `min_blend`, `surface`, `edge_surface`;
   - `roads`: `points`, `width`, `shoulder`, `max_grade`, `surface`;
   - `paint`: `polygon` + `surface`.
3. **Outputs** in `terrain/work/<project>/` (git-ignored, P80): `heightmap.asc`, `mask_lco.png`, `sat_lco.png`,
   `layers.cfg`, `objects_import.txt` (Terrain Builder text import), `objects_world.csv`, `removed_objects.csv`,
   `preview.png` (cut red / fill blue, pad yellow, roads green), `report.md` / `mapper.json` (earthworks and gates).
   Map objects inside a pad or on a road deck are removed; the others follow the new ground. The layout's
   `ClutterCutter*` objects are dropped (the pad's concrete surface has no clutter).
4. **Terrain Builder** on Windows: TESTING section 62 (TM-04 to TM-07).

Gates in the report: `pads_flat`, `road_grades`, `tile_surfaces` (<= 6 surfaces per 512-cell mask tile, P78),
`grid_square_pow2`. Self-test: `python mods/SKY_Skyline/terrain/tests/test_terrain_mapper.py` (synthetic capture,
also run by `Invoke-ModValidation.ps1`). Open points: P76-P81.
