# D71 gates (static, no DayZ run)

| Gate | Command | Result |
|---|---|---|
| City geometry | `python assets/blender/test_city.py` | PASS (191 buildings, re-run after the review fixes). New check: every search point reachable. It found ruined clubhouse locker spots (D65) inside sealed collapse pockets and the cinema stage spots (raised, now checked against a floor within 1.5 m); spots next to a collapse are no longer created |
| Kit geometry + wiring | `python assets/blender/test_kit.py` | PASS (276 assets); WIRING: 8 sound sets, 10 search tables (all defined in SKY_Search.c) |
| Asset budgets | `python assets/check_assets.py` | 286 checked, 0 fail, 0 over (police 9888 -> 10080, clinic 9864 -> 10008, post office 9258 -> 9486 Res0 tris) |
| Layout | `python placement/tests/test_sky_layout.py` | 0 failed (outputs unchanged) |
| Generated files | `gen_configs / gen_manifest / city_progress / economy/gen_economy --check`, `terrain/gen_terrain.py --check` | up to date (`skySearch` on City_Police_*, City_Clinic_*, City_PostOffice_*) |
| Script API | `tools/assets/enscript_xref.py` | OK, 26 files |
| PowerShell | `tools/tests/Invoke-SelfTest.ps1` | all self-tests passed |

## Reviews

- **security-auditor**: Medium: searches worked through walls (2 m 3D reach, no line of sight; true for all spots) -> server line-of-sight raycast for every memory-point spot (`InSight`, P42, TESTING CS-04). Low: raised-spot test too loose -> only cinema stages, true 1.5 m radius. Low: medical table easy to farm -> one cabinet per clinic floor, common items weighted. Confirmed: fixed server lists, no weapons/ammo, skySearch only on the 9 civic classes, key hygiene clean.
- **perf-engineer**: no High/Medium. Lows fixed: vents and letters as front quads, one locker bank per station, rack candidates only for post offices. Tables: 10 small arrays built once; per-search cost unchanged (plus one raycast per accepted search attempt).

Renders: `img/d71_postoffice_interior.png` (sorting rack behind the shelves), `img/d71_police_interior.png` (lobby; the lockers are in the office behind it).
