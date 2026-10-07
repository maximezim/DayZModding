# D72 gates (static, no DayZ run)

| Gate | Command | Result |
|---|---|---|
| City geometry | `python assets/blender/test_city.py` | PASS (191 buildings). The P39 pocket warning is now a failure: a pocket open from above needs an edge free of wall stubs onto the floor one storey down; rubble (<= 1.1 m, <= 45 deg, Geometry selection `rubble`) is walked over. Mutation (rubble treated as walls) -> 18 failures, so the check fires |
| Kit geometry + wiring | `python assets/blender/test_kit.py` | PASS (276 assets) |
| Asset budgets | `python assets/check_assets.py` | 286 checked, 0 fail, 0 over; 64 ruins / lots rebuilt, tris equal or lower except City_Hospital_Ruined +26 |
| Layout | `python placement/tests/test_sky_layout.py` | 0 failed |
| Generated files | `gen_configs / gen_manifest / city_progress / economy/gen_economy / terrain/gen_terrain --check` | all exit 0 |
| Script API | `tools/assets/enscript_xref.py` | OK, 26 files |
| PowerShell | `tools/tests/Invoke-SelfTest.ps1` | all self-tests passed |

## Reviews

- **security-auditor**: Medium: the first drop-out rule ignored wall stubs on the hole edge and the drop height -> the exit edge must be clear of collision and land on an existing floor one storey down (<= 4.6 m). Low: the slope cap ignored the top offset -> cap 0.575 r. Low: rubble height never checked -> test fails above 1.1 m. Search UX: per-player action instances, server re-checks uncached before any cooldown or spawn, fixed message to the sender only.
- **perf-engineer**: no High/Medium. The action cache bounds the raycasts to a few per second while aiming; the server raycast stays before the rate limit on purpose (a blocked search uses no cooldown). Ruin tris only went down (one +26).

Renders: `img/d72_rowhouse_states.png`, `img/d72_villa_states.png` (ruined state: regraded rubble).
