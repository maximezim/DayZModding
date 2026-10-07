# D80 gates (static, no DayZ run)

| Gate | Command | Result |
|---|---|---|
| Texture references | `python assets/textures/test_texture_refs.py` | PASS: 75 referenced, 0 missing (adds sky_wall_brick_as, sky_wall_panel_as, shared sky_wall_render_nohq) |
| Generator | `gen_textures.py --size 2048 --only wall_brick,wall_panel,wall_render` | completes (brick ~30 s, panel + render ~70 s) |
| Generated configs | `gen_configs.py --check` | exit 0 (brick / panel / render rvmats regenerated; render colours share one nohq via `SHARED_MAPS`) |
| Everything else | test_kit, test_city, layout, check_assets, concealment, xref, self-test | see `d79_gates.md` (same run) |

## Review

- **perf-engineer**: no High; ~+3.5-4.5 MB video memory in total, shared stucco nohq approved. Medium: brick _smdi carried no information (spec 0.04-0.12, damp field repeating every sheet) -> back to the procedural stage (perf batch-2 M1 stands); hard 1-2 px steps (mortar, cracks) fed the normals and would flicker at grazing angles -> soft edges (smoothstep joint, continuous crack field) in the height, hard masks kept for colour. Low: panel AO -> 512; manifest.yaml texture rows updated; pits kept (halve them if sparkle shows, P51).

Renders: `img/d80_brick_before_after.png` (left batch-2 brick, right D80), `img/d80_render_panel.png` (ochre stucco, precast panels).
