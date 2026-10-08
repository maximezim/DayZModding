# D87 gates (static, no DayZ run)

| Gate | Command | Result |
|---|---|---|
| One-way concealment, kit + city | `python assets/blender/test_conceal.py --city --jobs 4` | 3 FAILED (courtyard blocks: under-sill AC units on yard facades within head reach of the ring galleries) -> no clutter on yard sides; the 4 changed courtyard models re-scanned: PASS |
| Slits, kit + city | `python assets/blender/test_slits.py --city` | PASS (273; same two scoped acceptances; 34 views > 9 Mpx skipped); courtyards re-run PASS |
| City geometry (+ new wedge-slot check) | `python assets/blender/test_city.py` | PASS (191). First run of the new check: 51 raw hits -> 29 real after "nothing in the gap" -> all fixed (see below); ruins: 10 rubble slots filled by `close_slots`. Synthetic: 0.4 m slot found, flush / 0.8 m / filled gaps not |
| Ruin cuts | `python assets/blender/test_ruin_cuts.py` | PASS (120 models) |
| Kit geometry | `python assets/blender/test_kit.py` | PASS (279) |
| Asset budgets | `python assets/check_assets.py` | 289 checked, 0 over |
| Texture references | `python assets/textures/test_texture_refs.py` | PASS (85 / 0 missing; 3 new street-prop AO maps) |
| Layout / generated files | `test_sky_layout.py`, `--check` on gen_configs / gen_manifest / city_progress / gen_economy / gen_terrain | 0 failed / all exit 0 |
| Script API / PowerShell | `enscript_xref.py`, `Invoke-SelfTest.ps1` | OK (no script change) |

![Street-prop AO](img/d87_ao_street.png)

Bus stop, ad column, phone booth and the three re-unwrapped hero props (kitchenette, server rack, vending machine):
baked map, map on the prop through UV set 1, per-chart colour check (black = faces of other materials, no chart).

Wedge slots fixed: dining sideboard vs table (D84), school teacher's bench 0.2 m off the wall (D85), the D87 news rack,
mall food-court counters 0.2 m off the back wall, escalators 0.6 m beside the atrium balustrade (now 1.0 m), factory
racks 0.4 m off the back wall; ruins: rubble fillers. Facade clutter over the city: 172 AC units, 62 dishes, 36 laundry
lines; window displays: 28 stands in 7 shop types.

## Review

- **security-auditor**: no Critical / High. M right window stand + counter left a 0.52 m slot -> no stand in front of
  the counter; suggested a general >= 0.7 m clearance test -> `wedge_slots` gate (it found the list above); L market step
  climbable (no access gained; glass collision intact); dish clipped shutters -> skipped on shuttered windows; clutter is
  render-only, two-sided, out of reach; window stands outside door zones.
- **perf-engineer**: no High. M facade clutter Res0-only would pop -> AC body and dish plate in Res1; hidden faces
  skipped, laundry as two-sided quads (4 tris); L paint cans 8 -> 6 sides; L AdColumn: only the drum caps are hidden (the
  sides show under torn posters) - left charted; 256 AO maps ~43 KB each.
