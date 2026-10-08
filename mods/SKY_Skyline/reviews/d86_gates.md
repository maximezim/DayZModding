# D86 gates (static, no DayZ run)

| Gate | Command | Result |
|---|---|---|
| One-way concealment, kit + city | `python assets/blender/test_conceal.py --city --jobs 4` | PASS (273 models, 61 min); after the review fixes the 6 changed mall models re-scanned: PASS |
| Slits, kit + city | `python assets/blender/test_slits.py --city` | PASS (273; same two scoped acceptances; 34 views > 9 Mpx skipped, 9 of them the malls); malls re-run: PASS |
| Ruin cuts | `python assets/blender/test_ruin_cuts.py` | PASS (120 models; malls re-run PASS) |
| City geometry (+ new: no search spot inside a collision box) | `python assets/blender/test_city.py` | PASS (191). Mutation: bar spot moved into its counter -> 2 FAIL (unreachable + inside box) |
| Kit geometry | `python assets/blender/test_kit.py` | PASS (279) |
| Asset budgets | `python assets/check_assets.py` | 289 checked, 0 over |
| Texture references | `python assets/textures/test_texture_refs.py` | PASS (82 / 0 missing; 4 new `sky_<tag>_as`) |
| Layout / generated files | `test_sky_layout.py`, `--check` on gen_configs / gen_manifest / city_progress / gen_economy / gen_terrain | 0 failed / all exit 0 |
| Script API / PowerShell | `enscript_xref.py`, `Invoke-SelfTest.ps1` | OK 26 files / all passed (no script change) |

![AO props](img/d86_ao_props.png)

Per prop (reception desk, kitchenette, server rack, lockers): top the baked 256 map, middle the map on the prop through
UV set 1 (Blender Cycles, emission), bottom a per-chart colour sheet on the same set - one flat colour per face, so the
mapping is right. All five maps bake in ~1 min.

Variant draw over the city: bars - Bar pool table (pinned), BarB darts / stage; foyers - Cinema arcade, CinemaB standee;
mall shops 12 clothes / 12 shoe / 14 phone.

## Review

- **security-auditor**: no Critical / High / Medium. L phone counter touched the shutter keep-clear zone and left a 0.1 m
  wedge -> flush to the wall, checked with a 0.6 m margin; L arcade control decks outside the checked box -> checked to
  cy - 0.65; info: cabinets side by side with a 1.6 m aisle, stage and darts clear of the behind-bar spot, shoe shelving
  collides like every shelf_unit, the standee is two-sided render (hides, stops nothing); test gap -> `test_city` now fails
  a search spot inside a collision box.
- **perf-engineer**: no High / Medium. Per-prop AO rvmats cost only a Stage4 texture switch (different props never shared
  draw calls), 5 maps ~220 KB; L shoe shelving comment wrong (it collides) -> fixed; L handset undersides -> skipped; the
  shoe boxes on the shelving (~300 tris) kept on purpose.
