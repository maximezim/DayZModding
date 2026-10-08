# D91 gates (static, no DayZ run)

| Gate | Command | Result |
|---|---|---|
| One-way concealment, kit + city | `python assets/blender/test_conceal.py --city --jobs 3` | CONCEAL_RESULT |
| Slits, kit + city | `python assets/blender/test_slits.py --city` | SLITS_RESULT |
| City geometry (+ one-way glass at every height, voxel wedge check, self-tests) | `python assets/blender/test_city.py` | first runs found: sawtooth glazing (one-sided above the roof line, missed by a height exemption that was then removed), cupola caps, cinema legroom flagged by a one-height voxel rule (rule tightened to two heights >= 0.5 m apart); PASS (191), ~5.5 min |
| Kit geometry (+ one-way glass, voxel wedge check, convexity) | `python assets/blender/test_kit.py` | first runs: 4 non-convex bridge checkpoint barriers, Barrier_Concrete, 2 viaduct barriers, the flooded sewer water plane -> convex hulls, double-sided water; PASS (279; 180 non-box parts voxel-checked) |
| Self-tests | `wedge_selftest` (10), `pane_selftest` (10), `voxel_selftest` (7) | PASS; mutations (factory glazing back to one-sided, shell depth, voids) FAIL as they should |
| Ruin cuts | `python assets/blender/test_ruin_cuts.py` | PASS (120) |
| Asset budgets / LOD steps | `python assets/check_assets.py` | 289 checked, 0 fail, 0 warnings |
| Texture references | `python assets/textures/test_texture_refs.py` | PASS (85 / 0 missing) |
| Generated files | `--check` on gen_configs / gen_manifest / city_progress / gen_economy / gen_terrain | all exit 0 |
| Script API / PowerShell | `enscript_xref.py`, `Invoke-SelfTest.ps1` | not re-run: no script or tool change |

![Street at Res 1.75](img/d91_street_res1y.png)

Every city archetype along one street at Res 1.75 (`preview_city --shot street --lod res1y`; models without a Res 1.75
fall back to Res 1.5, then Res1). Res 1.5: `img/d91_street_res1x.png`.

## Review

- **perf-engineer**: no asset concern (+16 tris belfry, +72 sawtooth per LOD); L intact alpha glazing made two-sided
  for nothing -> only the opaque glassfar is two-sided; H/M voxel test cost -> vectorised gap and run masks, regions
  without a neighbour skipped, faces grouped per component once. The later pane-rule rewrite was its own hot spot
  (bars: thousands of bottle faces) -> planes filtered by merged area first, backing tested on cached arrays.
- **security-auditor**: no Critical. H diagonal slots never reported -> grids at 0 / 22.5 / 45 / 67.5 degrees
  (self-test: two 45-degree columns 0.3 / 0.45 m apart found, 0.9 m not); H twin test accepted any face -> an
  opposite-facing glassfar face covering >= 90 % (self-test: same-facing duplicate, small decal, same-facing pane
  0.45 m behind all flagged); M orientation / tiles -> general normals, coplanar faces merged before the area limit;
  M heights / decks -> 0.2 / 0.4 / 0.9 / 1.6 m above every level and Roadway deck; L non-convex components -> a
  convexity gate (found 7 real concave Geometry parts); L whole-asset exemption -> keyed per pane, none needed once
  the back-side Geometry test was added (the extinguisher cabinet's glass has its solid behind it). Deferred: a pocket
  open at a single height under an overhang (prone) - flagging single heights reported cinema legroom.
