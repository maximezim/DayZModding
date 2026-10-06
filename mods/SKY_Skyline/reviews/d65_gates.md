# D65 gates (static, no DayZ run)

| Gate | Command | Result |
|---|---|---|
| City geometry | `python assets/blender/test_city.py` | PASS (Hypermarket and Clubhouse rebuilt with search points: 6 and 4) |
| Layout, assets, economy, terrain | test_sky_layout, check_assets, gen_economy / city_progress / gen_terrain --check | 0 failed; 263 checked 0 fail; up to date |
| PowerShell | `tools/tests/Invoke-SelfTest.ps1` | all self-tests passed |
| Generated files | `gen_configs --check` (SKY_CityLit.c registers the hum; skySearch grocery / sport) | up to date |
| Script API | `tools/assets/enscript_xref.py` | OK, 26 files |
| Self-review | `SKY_Ambience.c` | client only (returns on the dedicated server); one 2 s timer removed in StopClient; sources capped at 2048; at most 3 sounds; destroyed on unregister |
