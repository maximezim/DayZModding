# D60 gates (static, no DayZ run)

Exporter port, sky_city split, content pass. Nothing here ran in DayZ yet: the content is
`built-unverified` until TESTING section 25 and B10-EXP pass on the Windows machine.

| Gate | Command | Result |
|---|---|---|
| Writer parity with Arma Toolbox | `blender -b -P assets/blender/test_p3dwriter.py` (ATB set) | PASS: 18 models earlier, plus Floor_HQ, Skybridge, Floor_Office_Brick and the lobby after the content pass. They are structurally identical; normals differ by < 1e-3 |
| Kit geometry | `python assets/blender/test_kit.py` | PASS (199 assets), including the skybridge landing-lane check on 4 roofs x 4 sides. A mutation run (lane moved onto the plant / planters) gives 8 failures, as expected |
| Tower A geometry | `python assets/blender/test_towera.py` | PASS: Lobby_B has the same door, entrance and loot checks as the lobby |
| City geometry | `python assets/blender/test_city.py` | PASS (155 buildings, unchanged by the split) |
| Asset budgets | `python assets/check_assets.py` | 208 checked, 0 fail, 0 over |
| Layout | `python placement/tests/test_sky_layout.py` | 0 failed. New checks: skybridge placed and refused (gap, yaw), Lobby_B, facade variants, skyline template |
| Generated files | `gen_configs / gen_manifest / gen_economy / city_progress --check` | all up to date |
| Script API | `tools/assets/enscript_xref.py` | OK, 14 files. New script classes only subclass existing ones (Lobby_B, lit floors) |
| PowerShell | `tools/tests/Invoke-SelfTest.ps1` | all self-tests passed; Invoke-ModValidation parses (0 errors) |

New budget hypotheses: `skybridge` res0 1500 / res1 600 / shadow 60 / geo 40 comps. The floor variants
use the `floor` budget. Lobby_B uses the lobby budget. Results: Floor_HQ res0 2412 / res1 1280 / res2 344;
Lobby_B res0 3620; Skybridge res0 716 / shadow 48.

Texture cost: `sky_hq_facade` is the only 4096 texture (co). Its nohq is 2048 and its smdi 1024. It is used
by the HQ floors only, so 32 instances share one texture.

Renders: `img/d60_skyline_aerial.png` (skyline template), `img/d60_floor_hq.png`, `img/d60_floor_office_brick.png`.
