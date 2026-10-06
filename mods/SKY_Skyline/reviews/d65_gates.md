# D65 gates (static, no DayZ run)

| Gate | Command | Result |
|---|---|---|
| City geometry | `python assets/blender/test_city.py` | PASS (Hypermarket and Clubhouse rebuilt with search points: 6 and 4) |
| Layout, assets, economy, terrain | test_sky_layout, check_assets, gen_economy / city_progress / gen_terrain --check | 0 failed; 263 checked 0 fail; up to date |
| PowerShell | `tools/tests/Invoke-SelfTest.ps1` | all self-tests passed |
| Generated files | `gen_configs --check` (SKY_CityLit.c registers the hum; skySearch grocery / sport) | up to date |
| Script API | `tools/assets/enscript_xref.py` | OK, 26 files |
| Self-review | `SKY_Ambience.c` | client only (returns on the dedicated server); one 2 s timer removed in StopClient; sources capped at 2048; at most 3 sounds; destroyed on unregister |

## Reviews of D63-D65 (subagents) and fixes

Security (no High):
- Drowning no longer hits players in their first minute online, nor unconscious or restrained players
  (griefing). The message and an admin log line now fire once per event.
- The flood check uses a 9 m horizontal radius, which covers the junction corners.
- A warning is logged once when the sewer cap is reached, and `sky_layout` refuses layouts with more than 512
  flooding pieces.
- The trigger JSON is written with `allow_nan=False` and a size/position check, because an invalid file would
  make the loader drop every trigger.

Performance (no High):
- `PHASE_STEP` went from 0.02 to 0.05, and pieces start at phase 0 instead of a forced first push.
- Players on the surface are skipped before the piece scan.
- The piece registry no longer uses `Find`.
- Ambience reuses its buffers, caches each source's position (lazily, after placement) and squared range, and
  plays through `PlaySoundCachedParams`.

**Fur**: new procedural `sky_fur` sheet (tan, black saddle, rat grey, chestnut) for the kennel dog, the rats and
the horse carcass (`img/d65_creatures_fur.png`).

