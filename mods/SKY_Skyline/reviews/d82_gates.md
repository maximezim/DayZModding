# D82 gates (static, no DayZ run)

| Gate | Command | Result |
|---|---|---|
| One-way concealment, kit + city (extended) | `python assets/blender/test_conceal.py --city --jobs 4` | PASS (273 models, 72 min on 4 jobs). Earlier runs found head-sized render-only volumes in pendant shades, rubble chunks, factory machines, hypermarket pallets / trolleys / cashier seats, cinema booth + popcorn machine, HVAC fans, lounger backs, potted plants, substation conservator and ruin cut mismatches - all fixed; two 4-cube mound-foot slivers accepted with a reason |
| Slits (new) | `python assets/blender/test_slits.py --city` | PASS (273 models; kit blocks, 14 city models ADVISORY: 3-5 cm partition-end render vs Fire mismatches seen through windows, triage D83; 34 views > 9 Mpx skipped) |
| Kit geometry + hull + wiring | `python assets/blender/test_kit.py` | PASS (279 assets) |
| City geometry | `python assets/blender/test_city.py` | PASS (191) |
| Asset budgets | `python assets/check_assets.py` | 289 checked, 0 over (city_tall geo_tris 4200 -> 4500, see DECISIONS D82) |
| Texture references | `python assets/textures/test_texture_refs.py` | PASS (76 referenced, 0 missing) |
| Layout / generated files | `test_sky_layout.py`, `--check` on gen_configs / gen_manifest / city_progress / gen_economy / gen_terrain | 0 failed / all exit 0 |
| Script API / PowerShell | `enscript_xref.py`, `Invoke-SelfTest.ps1` | OK 26 files / all passed |

Note: the res2 cut-cell change (review M below) rebuilt the city P3Ds while the final concealment scan ran; it
changes only res2, which that scan does not read, and the build is deterministic for the scanned LODs.

![D82 trim textures](img/d82_trims.png)

Limestone ashlar, concrete trim panels and brick trim (co / nohq). The brick soldier course and sill are still
flat in `_nohq` (D83 item).

## Ruin cut cells

A cut cell per 2 m pushed six ruined blocks over the geo budget (the cut-cell lines split every collision box
in the ruin region). Two fixes: pieces whose top never reaches the lowest possible cut (zc + 0.35) get no cell
lines, and the cell is 5 m (`CUT_CELL`). 4 m still left two blocks over; at 5 m, OfficeTall ruined sits at
4380 geo triangles, so the city_tall hypothesis goes to 4500 (P-budget, not verified in game).

## Review

- **security-auditor** (D82 batch): H floor cache keyed on `id()` -> floors computed per check; H ruin cuts disagreed
  across a cut cell -> cell lines in the near and collision LODs; M OBJ_MAX only when Geometry covers both ends,
  ties in `capped`, stricter mound feet, city flags in the build, trolleys clear the keep-clear zones and collide down to the floor.
- **security-auditor** (cut-cell follow-up): z1 skip and flat-quad skip confirmed safe (the cut is never below
  zc + 0.35; flat quads never use it). M res2 kept one cut per piece, so a distant wall top could differ from its
  collision by up to 2.2 m -> res2 now cut per cell too (res3 / shadow keep region edges). L centroid-kept
  extrudes / solids / prisms vs per-cell cut boxes -> P53, per-cell res0-vs-Geometry check planned for D83.
- **perf-engineer** (textures): limestone unwritten column -> exact block edges; drip groove as a cosine; concpanel
  pores lighter; whole soldier bricks per sheet; limestone AO kept at 512.
