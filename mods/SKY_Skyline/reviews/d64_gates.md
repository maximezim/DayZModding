# D64 gates (static, no DayZ run)

| Gate | Command | Result |
|---|---|---|
| Kit geometry | `python assets/blender/test_kit.py` | PASS (253 assets, incl. Wreck_CityBus and the rebuilt Wreck_GarbageTruck) |
| Asset budgets | `python assets/check_assets.py` | 263 checked, 0 fail, 0 over (new `vehicle` budget; bus 836 / 110 tris, truck 902 / 162) |
| Layout | `python placement/tests/test_sky_layout.py` | 0 failed; citylife template with 2 bus wrecks: PASS, 497 entities |
| Generated files | `gen_configs / gen_manifest --check`, `terrain/gen_terrain.py --check` | up to date |

The drivable versions are **blocked**, with the reason in DECISIONS D64 and the pipeline in `vehicles/VEHICLE_SPEC.md`.

Render: `img/d64_wrecks.png` (bus and garbage truck wrecks, Blender preview).
