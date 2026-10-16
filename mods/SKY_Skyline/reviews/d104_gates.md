# D104 terrain mapper: gates and reviews

User request: "prepare the terrain mapper which would allow to modify the existing maps of dayz to create custom
surfaces to place our cities and assets". Vanilla maps are binarized and never edited, so D104 builds a **mapped copy**
pipeline (`terrain/README.md`, section "Terrain mapper"):

- `addons/sky_scripts/scripts/5_Mission/SKY/SKY_TerrainCapture.c`: survey request `"mode": "capture"`. Server only,
  empty server, the request file is consumed. It captures heights (cm), surface types and map objects of a rectangle
  into `$profile:SKY_capture`.
- `terrain/terrain_mapper.py` + `terrain/projects/chernarus_skyline.yaml`: pads under city layouts (street level,
  slope-limited blend, trenches), graded roads, painted surfaces, objects removed / re-seated. Outputs are the
  Terrain Builder inputs and a report with gates, in git-ignored `terrain/work/`.
- `terrain/tests/test_terrain_mapper.py`: a synthetic capture in the exact Enforce format, 36 checks (also run by
  `Invoke-ModValidation.ps1`).

## Demo (synthetic capture, NOT Chernarus data)

The example project was run on a synthetic 1024 x 1024 capture at 2.5 m covering its crop (flat apron round the city,
hills around, 4000 trees). Capture write 0.7 s, mapper 1.9 s.

![region](img/d104_mapper_region.png)

Region preview: hillshade, cut red / fill blue, pad hull yellow, road green.

![zoom](img/d104_mapper_demo.png)

Left: cut / fill under the city pad and the south access road. Right: colour map with concrete under the pad, a
tall-grass edge, a gravel road, grass and forest.

| item | value |
|---|---|
| pad | 49 912 m2 at the layout street level 140.057 m, flat; blend 25 m |
| earthworks | cut 18 966 m3, fill 4 963 m3 (synthetic ground: max cut 0.89 m) |
| road | 279.6 m, max grade 0.070 (limit 0.08) |
| objects | 3 955 map objects kept, 45 removed (pad / road), 299 SKY objects with model paths, 532 ClutterCutter dropped |
| gates | pads_flat, road_grades, tile_surfaces, grid_square_pow2: all True |

## Reviews

**Security** (no Critical / High):
- M1: the capture re-ran on every restart and ships in the release PBO. Fixed: the request file is deleted when a
  capture starts, the capture refuses to start with players connected, and it is capped at 4.3 M cells.
- L1, malformed input: file size cap, row-count check, integer-only rows, finite origin, 0 < cell <= 100, header
  bounds before loading, NaN / NODATA refused.
- L2, memory: coordinate grids are built for the edited window only.
- L3, object strings: allow-list `[A-Za-z0-9_\/.- ]`, the rest is rejected and counted.
- L4, output path: `realpath`; tracked repo folders are refused (only `terrain/work/` or outside the repo).
- L5: the pre-commit hook refuses `terrain/work/`, `SKY_capture/` and `*_heights/_surfaces/_objects.txt`.

**Perf** (no High):
- M1: object lines are budgeted per tick (1500, a dense tile spans several ticks), 50 m tiles, and the `found`
  array is reused.
- M2: CELLS_PER_TICK lowered from 8192 to 4096.
- M3: on mission end `Abort()` removes the timer and closes the files; the meta file is written last with
  `complete: true`, and the mapper refuses an incomplete capture.
- M4: MAX_CELLS is 4096, with window-only coordinates.
- M5: the heightmap is written with `np.savetxt`.
- M6: objects are annotated in place, with no dict copies.
- Lows: the clamped grid and failed file opens are logged, and surface-legend overflow is counted. The trench mask
  is reused.

A demo bug was also fixed: road cut / fill read 0 because the original window was a view of the array being edited.
There is now a test for it.

## Gates

| gate | result |
|---|---|
| test_terrain_mapper.py | 36 PASS, 0 failures |
| test_sky_layout.py | 0 failed |
| gen_configs / gen_manifest / gen_terrain / city_progress --check | up to date |
| gen_economy --check | was **stale at HEAD before D104** (loot points moved by D98 door sweeps / D99 10 m deep blocks); regenerated, now up to date |
| check_assets | 289 checked, 0 fail, 54 over budget (hypotheses, unchanged) |
| D96 model gates | not applicable: no model changed in D104 |
| pyflakes (mapper, test) | clean |

Not verifiable in the cloud: the Enforce APIs (P76, no P:), surface rvmats (P77), Terrain Builder limits and formats
(P78, P79), licensing of map-derived terrain (P80), capture cost and fidelity (P81). TESTING section 62 (TM-01 to
TM-08) covers them.
