# D79 gates (static, no DayZ run)

| Gate | Command | Result |
|---|---|---|
| One-way concealment (new) | `python assets/blender/test_conceal.py` | PASS (74 models, ~6 min). First run: 13 models with head-sized render-only volumes in reach, all fixed (no `ACCEPTED` exceptions) |
| Kit geometry + hull + wiring | `python assets/blender/test_kit.py` | PASS (279 assets; new collision checked for slits - the landfill junk slit guard and wall-to-wall gondola benches came from this) |
| City geometry | `python assets/blender/test_city.py` | PASS (191) |
| Asset budgets | `python assets/check_assets.py` | 289 checked, 0 over |
| Layout / generated files | `test_sky_layout.py`, `--check` on gen_configs / gen_manifest / city_progress / gen_economy / gen_terrain | 0 failed / all exit 0 |
| Script API / PowerShell | `enscript_xref.py`, `Invoke-SelfTest.ps1` | OK 26 files / all passed |

Fixed models: Sewer_Straight / Access / End / Collapsed / FloodedEnd (wall pipes collide), BusStop (bin), Fair_BumperCars (seat backs), Landfill (fridges, barrels), Stadium_Stand (seat shells), Fair_FerrisWheel (roofs; boardable cabins hollow with a bench), Wreck_GarbageTruck (bags flattened).

## Review

- **security-auditor**: High: the new solid sewer pipe crossed the Sewer_Access door (1.6 m headroom) -> the pipe stops either side of the door; High: the gate counted Fire / View cover only, so a Fire box without Geometry still let a head in -> covered now means Geometry AND (Fire or View). Medium: the boardable gondola's solid Geometry block left a 0.9 m crawl pocket under the new roof -> floor + four walls + bench; floor model gaps -> walkable normals to ~50 deg, floors sampled 0.3 m round the cube, z = 0 ground only for surface models; the test's blind spots (both-axes rule, face pairing, unscanned city / floor modules) are documented in its docstring. Low: pipe boxes flush to the wall; the mound-box slit guard is inert (junk sits inside the mound) - kept for the junk-to-junk case it does catch. Hygiene clean.
