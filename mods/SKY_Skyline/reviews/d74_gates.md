# D74 gates (static, no DayZ run)

| Gate | Command | Result |
|---|---|---|
| Kit geometry + hull + wiring | `python assets/blender/test_kit.py` | PASS (278 assets). New `hull_slits`: stacked and side-by-side collision parts must touch within 1 mm (vehicles: gaps up to 0.3 m fail; other props: up to 5 cm; door leaves skipped). First run found the garbage truck wheel/body (10 cm) and cab/body (15 cm) slits, bed, siren tower, dugout bench, rat nest; all closed |
| Asset budgets | `python assets/check_assets.py` | 288 checked, 0 fail, 0 over: Billboard 562 -> 136 -> 34, TrafficLight 378 -> 82 -> 36, Wreck_Van 382 -> 104 -> 40, Wreck_Sedan_B 326 -> 124 -> 24, Wreck_Sedan_C 202 -> 88 -> 12 |
| City geometry | `python assets/blender/test_city.py` | PASS (191 buildings) |
| Layout | `python placement/tests/test_sky_layout.py` | 0 failed; new check: jams mix the three sedan states (citylife 12 / 9 / 9); 513 entities + 103 loot (unchanged jam layout) |
| Generated files | `gen_configs / gen_manifest / city_progress / economy/gen_economy / terrain/gen_terrain --check` | all exit 0 |
| Script API / PowerShell | `enscript_xref.py`, `Invoke-SelfTest.ps1` | OK 26 files / all passed |

## Reviews

- **security-auditor**: Medium: the overturned sedan left a 0.55 m crawl space under its overhangs while Res2 drew a solid block -> collision is one closed block. Medium: the van's open rear door was render-only -> collision slab. Low: upturned wheels render-only -> they collide. Low: the hull test only measured vertical gaps on bounding boxes -> side-by-side gaps added (found the cab/body, bed, siren, bench and nest gaps); a ray-grid version and a Res-inside-collision check stay open (noted, ROADMAP). Jam classes come only from skyspec; key hygiene clean.
- **perf-engineer**: Medium: the variant draw shifted the jam random stream (513 -> 533 entities) -> own stream, only when there is a choice; back to 513. Lows: billboard walkway and traffic-light head kept in Res2; the atlas face no longer hidden inside the backplate. Three sedan models instead of one: ~8 extra batches in view, shared materials.

Renders: `img/d74_billboard_traffic.png`, `img/d74_wrecks.png` (sedan intact / burnt / overturned, van).
