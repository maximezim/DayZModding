# D75 gates (static, no DayZ run)

| Gate | Command | Result |
|---|---|---|
| Kit geometry + hull + wiring | `python assets/blender/test_kit.py` | PASS (279 assets, new Street_Straight_B) |
| Asset budgets | `python assets/check_assets.py` | 289 checked, 0 fail, 0 over: Street_Straight 68 -> 60 -> 6, Street_Crossing 76 -> 64 -> 6, Street_Straight_B 74 -> 60 -> 6 (road_combined 400), Viaduct_Straight 360 -> 146 -> 76 -> 20 (road_struct 12000) |
| City geometry | `python assets/blender/test_city.py` | PASS (191 buildings) |
| Layout | `python placement/tests/test_sky_layout.py` | 0 failed; new check: worn straight tiles mixed in (citylife 28 of 79, ~40 %); entity totals unchanged (513 + 103 loot) |
| Generated files | `gen_configs / gen_manifest / city_progress / economy/gen_economy / terrain/gen_terrain --check` | all exit 0 |
| Script API / PowerShell | `enscript_xref.py`, `Invoke-SelfTest.ps1` | OK 26 files / all passed |

## Reviews

- **perf-engineer**: Medium: the 2 m kerb units (box + chamfer wedge) were 288 of 360 Res0 triangles and left B at 392/400 -> one open profile per side (road face, chamfer, top, back lip; no bottom, end or shared faces), 16 triangles; Res0 360 -> 68. Lows: gutter (4 mm), repairs and trench (6-7 mm) under the 15 mm Res1 lift -> gutter at 15 mm in Res1, repairs and trench Res0 only; the solid edge line overlapped the gutter -> moved 15 cm inward; viaduct expansion joints 1 mm above the deck asphalt -> lifted to 15 mm. Second street model costs ~4 batches in view, accepted.
- **security-auditor**: no Critical / High / Medium. Low: soffit ribs are render-only 0.45 m below the deck collision; nothing under a viaduct puts a head 5.65 m up -> accepted, noted. Info: the sunken paver patch was hidden under the opaque sidewalk -> removed; kerb chamfer face coincided with the slab side wall -> road face 1 mm proud; viaduct diaphragm and bearings sat inside the pier cap -> removed. Worn-variant class comes only from skyspec (crc32 of the grid cell); key hygiene clean.

Renders: `img/d75_kerb.png` (kerb / gutter close-up), `img/d75_street_worn.png` (worn tile), `img/d75_asphalt_tile.png`, `img/d75_intersection.png`, `img/d75_viaduct.png` (render before the hidden diaphragm/bearings were removed; nothing visible changed).
