# D83 gates (static, no DayZ run)

| Gate | Command | Result |
|---|---|---|
| Slits, kit + city (depth-checked, city blocking) | `python assets/blender/test_slits.py --city` | PASS (273 models, ~7 min; 34 views > 9 Mpx skipped). The 14 D82 city advisories were projection artefacts; accepted: Ferris-wheel lattice (D82), OfficeTall damaged shopfront corner mullion (scoped to axis X, box, 400 cm2) |
| Slit selftest (new) | `python assets/blender/test_slits.py --selftest` | PASS: real 3 cm slit found, found next to a large artefact region, found with Fire set back 0.3 m inside an 0.8 m wall; the D82 artefact not found |
| Ruin cuts (new, P53) | `python assets/blender/test_ruin_cuts.py` | PASS (120 damaged / ruined models, 175 whole pieces). Mutations: Fire extrudes dropped -> 8 FAIL, Geometry solids dropped -> 2 FAIL |
| One-way concealment | `python assets/blender/test_conceal.py --city --jobs 4` | not re-run: the rebuild for the extrude-centre change produced byte-identical P3Ds, so the D82 PASS (273 models) stands |
| Kit geometry + hull + wiring | `python assets/blender/test_kit.py` | PASS (279) |
| City geometry | `python assets/blender/test_city.py` | PASS (191) |
| Asset budgets | `python assets/check_assets.py` | 289 checked, 0 over |
| Texture references | `python assets/textures/test_texture_refs.py` | PASS (76 / 0 missing) |
| Layout / generated files | `test_sky_layout.py`, `--check` on gen_configs / gen_manifest / city_progress / gen_economy / gen_terrain | 0 failed / all exit 0 |
| Script API / PowerShell | `enscript_xref.py`, `Invoke-SelfTest.ps1` | OK 26 files / all passed |

![D83 brick trim](img/d83_brick.png)

Brick trim co / nohq: soldier course and stone sill now carry relief (bevels, recessed joints, pits, sill stones,
bed joint, nose); 31 whole running-bond courses, no sliver under the soldiers.

## Triage of the D82 city slit advisories

Probing each finding (`slitprobe`: Fire and Res0 triangles around the pixel) showed the same pattern: the
whole-model projection pairs Fire parts metres apart in depth - AptBlock: a stair-core wall at x = -1.45 and a
gable pier at x = -9; RowhousePanel / MallB: a window pier and a partition end 0.2 m behind it - around a 6 cm
render-only window frame. No wall hides a slit at one depth. Remaining finding: OfficeTall damaged, the corner
mullion (2 x 8 cm render-only aluminium) between Fire panes 3 cm apart with a broken pane - accepted (thin-detail
rule; Fire on every mullion would add ~2 parts per bay and storey), scoped to that box. Stair flights show render
steps up to 20 cm over the collision ramp - the usual stair setup, not a finding.

## Review

- **security-auditor**: H - one sample's verdict spread over unrelated pixels -> each connected gap region sampled on
  its own (selftest with a real slit beside an artefact); M - Fire set back > 0.15 m from the visible face was
  dropped -> the depth window is the render's solid span along the ray +- 0.1 m (selftest with set-back Fire);
  M - the OfficeTall acceptance exempted the whole model -> keyed by axis, box and maximum area; H - the ruin test
  compared Res0 / Geometry only, by any overlap, whole pieces only -> Fire too, >= 60 % coverage on each axis, cut
  boxes logged as counterparts, collision dropped under kept render checked; extrudes decide by the profile's
  bounding-box centre, not its first point.
- **perf-engineer** (brick): M - 7 px running-bond sliver under the soldier course -> 31 whole courses; M - soldier
  proportions checked against the model (0.22 m quad: 6.6 x 22 cm bricks, fine); L - one-sided gradients at the sheet
  edge -> wrapped central differences in `normal_from_height` (all textures).
