# D66 gates (static, no DayZ run)

| Gate | Command | Result |
|---|---|---|
| Kit geometry | `python assets/blender/test_kit.py` | PASS (253 assets; TrashBin footprint updated to 0.9 x 0.7) |
| Asset budgets | `python assets/check_assets.py` | 263 checked, 0 fail, 0 over. Hydrants moved to `medium` (842 tris); TrashBin shadow is one hull and has 4 sections; `underground` sections raised to 12 |
| Layout | `python placement/tests/test_sky_layout.py` | 0 failed; citylife template PASS (497) |
| Generated files | `gen_configs / gen_manifest --check`, `terrain/gen_terrain.py --check` | up to date (new `sky_signs3.rvmat`) |
| Scripts | none changed | enscript_xref not affected; no security review needed (no code) |

Renders (Blender preview; the props float because the preview ground sits 0.31 m low):
- `img/d66_props_before.png`, `img/d66_props_after.png`, `img/d66_bin_dumpster.png`: bin, hydrants, dumpster.
- `img/d66_metro_signs.png`: station name boards on both walls (no mirroring), graffiti, cables.
- `img/d66_sewer.png`.
