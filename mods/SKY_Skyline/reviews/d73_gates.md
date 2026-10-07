# D73 gates (static, no DayZ run)

| Gate | Command | Result |
|---|---|---|
| Kit geometry + wiring | `python assets/blender/test_kit.py` | PASS (276 assets) |
| Asset budgets | `python assets/check_assets.py` | 286 checked, 0 fail, 0 over: StreetLight 330 -> 136 -> 24, Barrier_Concrete 172 -> 36 -> 12, Planter 188 -> 90 -> 14, Wreck_Sedan 326 -> 124 -> 24, Kennel 986 -> 356 -> 44 |
| City / layout / generated / scripts / PowerShell | `test_city`, `test_sky_layout`, all `--check`, `enscript_xref`, `Invoke-SelfTest` | PASS / 0 failed / all exit 0 / OK 26 files / all passed |

Ranking (Res0 tris, kit pieces of the sky_street / landmarks / vehicles / underground packages): Planter 18, Barrier_Concrete 20, Billboard 38, TrafficLight 66, StreetLight 80, Wreck_Sedan 136, PhoneBooth 142, Wreck_Van 152 ... The four most placed of the weakest (lamps on every street, barriers and sedans in every jam) were upgraded; Billboard, TrafficLight and Wreck_Van stay for a later pass.

## Reviews

- **security-auditor**: High: the first sedan draft extruded the new cabin profile into Geometry/Fire/View, leaving a 1 cm slit over the body -> collision keeps the batch-1 hull. Medium: see-through cabin in Res0 -> grimy windscreen / rear window quads. Medium: the planter Res2 card was single-sided and larger -> same card as Res1, double-sided. Low: engine bay 13 cm below the collision top -> accepted, nothing hides there. Light memory points unchanged; key hygiene clean.
- **perf-engineer**: Medium: barrier Res1 rebuilt the chamfers -> one extrusion plus the stripes (36). Medium: barrier 3 sections -> accepted (close range only, DECISIONS D73). Lows fixed: anchor bolts n=4, planter chips removed and crack moved to the concrete sheet, lamp crack offset 6 mm, sedan Res1 wheels n=5. District cost at range: about 12.8k (Res1) / 2.3k (Res2) tris for 30 lamps, 75 barriers, 30 sedans.

Renders: `img/d73_street_kit.png` (barrier, planter, sedan), `img/d73_streetlight.png`, `img/d73_sedan.png`, `img/d73_kennel_far.png`.
