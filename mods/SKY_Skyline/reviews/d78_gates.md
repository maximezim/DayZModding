# D78 gates (static, no DayZ run)

| Gate | Command | Result |
|---|---|---|
| Kit geometry + hull + wiring | `python assets/blender/test_kit.py` | PASS (279 assets) |
| City geometry | `python assets/blender/test_city.py` | PASS (191; the three parking garages rebuilt with the new hulks) |
| Asset budgets | `python assets/check_assets.py` | 289 checked, 0 over. Barrier_Steel 204 -> 404 Res0; ParkingLot_A 1250 -> 2270 (Res2 12 -> 146), ParkingLot_B 288 -> 488, ParkingLot_Metro 1002 -> 1640; Bridge_Long 5578 -> 5398; City_ParkingGarage_* ~13k; Sewer_Junction 272 -> 840 |
| Layout / generated files | `test_sky_layout.py`, `gen_configs / gen_manifest / city_progress / gen_economy / gen_terrain --check` | 0 failed / all exit 0 |

## Reviews

- **security-auditor**: no Critical / High. Medium: the reworked hulk render sat up to 20 cm below its old collision boxes (invisible slab over bonnet / boot, wedges at the screens) -> collision is now the body to 0.84 m plus the sloped cabin profile, matching the render. Medium: the new pay machine and an older wreck that overlapped the booth formed a 0.5 x 0.35 m snag pocket on ParkingLot_A / Metro -> machine flush with the booth and the bay beside the booth stays empty (also removes the old overlap). Low: render-only sewer pipes at head height (a head could hide inside) -> raised to 2.2 m; pilasters touched the corner masses on one edge only -> quoins wrapping the corner. Hygiene clean.
- **perf-engineer**: no High. Medium: wreck screens sat inside the cabin (never drawn), tyres coplanar with the sills, waist open on top, sewer well throat under the silt quad, lots popped from Res1 to a 12-tri Res2 -> all fixed (Res2 keeps posts and a box per wreck). Low: hexagonal ladder bars -> square (-88 tris), 1 mm offsets -> 5-6 mm, 1-2 mm boxes -> quads.

Renders: `img/d78_barrier.png`, `img/d78_lot_overview.png` (before the hulk rework), `img/d78_lot_wrecks.png`, `img/d78_sewer_junction.png`.
