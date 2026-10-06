# D67 gates (static, no DayZ run)

| Gate | Command | Result |
|---|---|---|
| Kit geometry | `python assets/blender/test_kit.py` | PASS (261 assets; BusStop route pole moved inside the 4.4 x 1.9 footprint) |
| Asset budgets | `python assets/check_assets.py` | 271 checked, 0 fail, 0 over (BusStop and PhoneBooth trimmed to 5 Res0 sections) |
| City geometry | `python assets/blender/test_city.py` | PASS (176 buildings) |
| Layout | `python placement/tests/test_sky_layout.py` | 0 failed; citylife PASS (521): collapsed variants mixed in, furniture placed, no bus stop under a lamp, no jam through a bus stop |
| Generated files | `gen_configs / gen_manifest / city_progress / economy/gen_economy --check`, `terrain/gen_terrain.py --check` | up to date (terrain objects regenerated) |
| Script API | `tools/assets/enscript_xref.py` vs vanilla scripts | OK, 26 files, all calls/types resolve |
| PowerShell | `tools/tests/Invoke-SelfTest.ps1` | all self-tests passed |

## Reviews

- **security-auditor**: no Critical/High/Medium. Low 1 (rubble slabs, beam and hanging lamp visual-only, so they could hide a player): fixed, all solid in Geometry/Fire/View. Low 2 (misleading FloodedEnd comment): fixed. New classes only subclass `Land_SKY_Sewer_Base` (server-side registration, bounded, identity from `PlayerIdentity`); YAML keys never choose a class; no keys, `.pbo` or `.bisign` in the tree.
- **perf-engineer**: no High/Medium. AdColumn Res2/Shadow reduced to a 6-sided drum (56 -> 20 tris); glass out of View LODs (bus stop, booth: lower panels only); stale `*.FAILED.*` outputs removed. Entity budget: 521 + 110 loot of 800 per district.
- Found in the render pass: the phone booth dropped all three panes (hash test); now exactly one pane is missing.

Renders (Blender preview; props float because the preview ground sits 0.31 m low):
- `img/d67_streetprops.png`: bus stop, ad column, phone booth.
- `img/d67_sewer_collapsed.png`, `img/d67_sewer_floodedend.png`.
- `img/d67_metro_station_c.png`: Stadion station into the collapsed tunnel.
