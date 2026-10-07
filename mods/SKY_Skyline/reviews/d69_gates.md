# D69 gates (static, no DayZ run)

| Gate | Command | Result |
|---|---|---|
| City geometry | `python assets/blender/test_city.py` | PASS (191 buildings, 15 new). MallB at 48 x 32 left 75 m2 of its ruined upper floor unreachable; resized to 48 x 34. New WARN line: 20 ruin pockets open from above (pre-existing, P39) |
| Kit geometry + wiring | `python assets/blender/test_kit.py` | PASS (276 assets); WIRING: 8 sound sets, 7 search tables |
| Asset budgets | `python assets/check_assets.py` | 286 checked, 0 fail, 0 over |
| Layout | `python placement/tests/test_sky_layout.py` | 0 failed; out_city 300 entities + 335 loot, out_citylife 513 + 103 (caps 800 / 2500) |
| Generated files | `gen_configs / gen_manifest / city_progress / economy/gen_economy --check`, `terrain/gen_terrain.py --check` | up to date (new `sky_signs4.rvmat`, configs and loot points for the 15 classes) |
| Script API | `tools/assets/enscript_xref.py` | OK, 26 files |
| PowerShell | `tools/tests/Invoke-SelfTest.ps1` | all self-tests passed |
| Package size | `du -sh addons/sky_city_venue` | 146 MB of source models (was 94 MB; budget ~300 MB) |

## Reviews

- **perf-engineer**: no High. Medium: the `rare` chance was rolled on every slot draw (bars near certain in every block) -> rolled once per block, layouts regenerated. Low: signs4 had 5 bands (204.8 px edges) -> 8 bands of 128 px (3 spare), models rebuilt. Low: package size -> measured, 146 MB. Checked: tris within budget, lights/ambience client-only and bounded.
- **security-auditor**: no Critical/High/Medium. Each variant gets exactly its base's `skySearch` table, nothing else became searchable, fill classes come only from skyspec. Low: ruin pockets open from above (guide section 7) - pre-existing in 20 ruins; test_city now reports them, fix tracked (P39, ROADMAP D72).

Renders (Res0, intact / damaged / ruined): `img/d69_hypermarketb_states.png`, `img/d69_mallb_states.png`, `img/d69_cinemab_states.png`, `img/d69_barb_states.png`, `img/d69_clubhouseb_states.png`.
