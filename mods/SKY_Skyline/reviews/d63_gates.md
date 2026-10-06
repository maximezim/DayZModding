# D63 gates (static, no DayZ run)

Underground and the custom terrain sources, decided autonomously (DECISIONS D63). Nothing here has run in DayZ.
The terrain still has to be built on Windows (Terrain Builder, P28). The in-game checks are TESTING §28 and P25-P29.

| Gate | Command | Result |
|---|---|---|
| Kit geometry | `python assets/blender/test_kit.py` | PASS (252 assets incl. 8 underground pieces, watertight components) |
| Asset budgets | `python assets/check_assets.py` | 262 checked, 0 fail, 0 over (new budget `underground`; station 2356 / 830 tris) |
| Layout | `python placement/tests/test_sky_layout.py` | 0 failed. New checks: piece counts, one darkness trigger per piece with stair breadcrumbs, trenches written, `underground` refused on a vanilla map, sewer through the metro refused |
| City life + underground | `sky_layout.py --layout citylife_template.yaml --out out_citylife` | PASS (warnings: placeholder site), 495 entities |
| Terrain | `python terrain/gen_terrain.py --check` | up to date; 1024 x 1024 m at 1 m, plateau 120 m, 23 trenches, 1 river valley |
| Generated files | `gen_configs / gen_manifest / gen_economy / city_progress --check` | up to date (model.cfg: translation `flood_move` on 4 sewer pieces) |
| Script API | `tools/assets/enscript_xref.py` | OK, 24 files |
| PowerShell | `tools/tests/Invoke-SelfTest.ps1` | all self-tests passed |

Self-review of `SKY_Underground.c` against the security and performance rules:
- No client input.
- One 10 s timer, removed in `Stop`. Work only happens while the sewers are flooded (players x pieces within 10 m).
- `SetAnimationPhase` is called only when the level moves by 0.02.
- The piece registry is capped at 512.

Renders (Blender, kit lamps only):
- `img/d63_sewer.png`: sewer straight, access and junction.
- `img/d63_metro.png`: the station between two tunnels.
- `img/d63_terrain.png`: hillshade of the generated terrain. The city plateau is in the middle, the sewer and metro trenches are under the west and east streets, and the river valley runs east-west under the bridge.

Fixed during the run:
- The tunnel tracks did not meet the station tracks. The tunnel was widened to 12 m and both use tracks at +-4.6.
- The station had no end walls.
- The stair pieces reached into the blocks. The Sewer_Stair is now parallel to its access piece, under the sidewalk.
- The template's river ran through the city. The bridge was turned 90 degrees.
