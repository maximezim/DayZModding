# D71 gates (static, no DayZ run)

| Gate | Command | Result |
|---|---|---|
| City geometry | `python assets/blender/test_city.py` | PASS (191 buildings). New check: every search point reachable. It found ruined clubhouse locker spots (D65) inside sealed collapse pockets and the cinema stage spots (raised, now checked against a floor within 1.5 m); spots next to a collapse are no longer created |
| Kit geometry + wiring | `python assets/blender/test_kit.py` | PASS (276 assets); WIRING: 8 sound sets, 10 search tables (all defined in SKY_Search.c) |
| Asset budgets | `python assets/check_assets.py` | 286 checked, 0 fail, 0 over (police 9888 -> 10080, clinic 9864 -> 10008, post office 9258 -> 9486 Res0 tris) |
| Layout | `python placement/tests/test_sky_layout.py` | 0 failed (outputs unchanged) |
| Generated files | `gen_configs / gen_manifest / city_progress / economy/gen_economy --check`, `terrain/gen_terrain.py --check` | up to date (`skySearch` on City_Police_*, City_Clinic_*, City_PostOffice_*) |
| Script API | `tools/assets/enscript_xref.py` | OK, 26 files |
| PowerShell | `tools/tests/Invoke-SelfTest.ps1` | all self-tests passed |

## Reviews

- perf-engineer / security-auditor: running at commit time; findings and fixes follow in the next commit.

Renders: `img/d71_postoffice_interior.png` (sorting rack behind the shelves), `img/d71_police_interior.png` (lobby; the lockers are in the office behind it).
