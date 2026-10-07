# D68 gates (static, no DayZ run)

| Gate | Command | Result |
|---|---|---|
| Kit geometry + wiring | `python assets/blender/test_kit.py` | PASS (261 assets); new WIRING check: 8 sound sets played, all in sky_sounds with their .ogg; 7 search tables, all defined in SKY_Search.c |
| Asset budgets | `python assets/check_assets.py` | 271 checked, 0 fail, 0 over (stadium stand + flags 5560 / 252 tris) |
| City geometry | `python assets/blender/test_city.py` | PASS (176 buildings) |
| Layout | `python placement/tests/test_sky_layout.py` | 0 failed |
| Generated files | `gen_configs / gen_manifest / city_progress / economy/gen_economy --check`, `terrain/gen_terrain.py --check` | up to date (SKY_CityLit.c regenerated: mall muzak) |
| Sounds | `python assets/sounds/gen_ambience.py` | deterministic: the D65 loops are byte-identical; new wind 14 s, flags 11 s, muzak 13.3 s (mono 22.05 kHz Vorbis q3, 70 KB each) |
| Script API | `tools/assets/enscript_xref.py` vs vanilla scripts | OK, 26 files, all calls/types resolve |
| PowerShell | `tools/tests/Invoke-SelfTest.ps1` | all self-tests passed |

## Reviews

- **security-auditor**: no Critical/High/Medium. Low (kiosk loot traced to a surface could pop up on the street): fixed, loot below the terrain keeps the spot height (`ECE_KEEPHEIGHT`, P36). Confirmed: the kiosk table is a fixed server list chosen from config, `FindSpot` uses 3D distance (2 m reach), so nobody searches the kiosk from the street; rate limit, cooldown and the 4096-spot cap cover the new spots; the ambience code is client-only.
- **perf-engineer**: no High. Medium (same loot placement): fixed. Lows: metro wind could leak into the sewer 2 m above -> per-source vertical cut-off (underground 1.8 m); flag cloth missing in Res1 -> one sheet per flag added. Noted, not changed: the stand's existing Res0 -> Res1 drop (5560 -> 252) predates D68.
- Found while wiring: D65 sewer drips played at the street-level origin of the pieces; fixed with emitter offsets.
- Found in the spectrograms: the first wind render had most energy at 8 Hz; it is now high-passed.

Images: `img/d68_stand_flags.png` (roof flags), `img/d68_loops.png` (spectrograms of wind, flags, muzak).
