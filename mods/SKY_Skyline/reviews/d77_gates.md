# D77 gates (static, no DayZ run)

| Gate | Command | Result |
|---|---|---|
| Texture references (new) | `python assets/textures/test_texture_refs.py` | PASS: 72 referenced PAAs, 0 missing. First run found `sky_stone_as.paa` (referenced by `sky_stone.rvmat`, never generated) -> generated |
| Generator | `gen_textures.py --size 2048` (default) and `--size 512` | both complete; asphalt output byte-identical after the crack-distance refactor |
| Generated configs | `gen_configs.py --check` | exit 0 (`sky_wood.rvmat` now references `sky_wood_nohq.paa` / `sky_wood_smdi.paa`) |
| Everything else | test_kit, test_city, layout, check_assets, xref, self-test | as in `d76_gates.md` (same run) |

Sizes at 2048: wood co / nohq 1024, smdi 512; fabric 512; paver co 2048, nohq 1024, smdi 256, as 1024; stone as 512.

## Review

- **perf-engineer**: no High. Medium: wood scratches (1 px) and pores (2.7 px rows) would shimmer in gloss / normals at 0-5 m -> 2 px scratches, ~5 px pores; paver grit at 4 px sparkled in the normal map on every sidewalk -> 8 px and paver nohq 1024 (-4 MB). Lows: wood smdi 512, paver smdi back to 256, stone AS 512 and the double-width joint at its wrap fixed, asphalt computed the same crack distances twice -> once. Wood nohq 1024 (reverses perf batch-3 L4) accepted: furniture is seen at 0-5 m, +1.3 MB shared.
- **security**: texture-only batch, no script / config class / RPC change; hygiene checked at commit (pre-commit hook, no keys / pbo / bisign).

Renders: `img/d77_textures.png` (wood, paver, concrete, fabric colour maps), `img/d77_paver_kerb.png`, props in `img/d76_*.png`.
