# Splendour pass (D55): perf, security and QA gates

Scope: new materials (marble, parquet, paint, stone, textile, lamp_cool, atlas artworks and
wayfinding), baked decoration in every building module, night-only script lights
(`sky_scripts/scripts/4_World/SKY/SKY_Lighting.c`). Static gates only - nothing ran in DayZ.

## Perf - PASS (room raised on request, D55; measure with FPS_PROTOCOL 4.1)

| Module | Res0 (D54 -> D55) | Res1 | Res2 / Res3 | Res0 sections | Geo comps |
|---|---|---|---|---|---|
| TowerA_Lobby | 1722 -> 3452 | 924 -> 1292 | 136 / 24 | 8 -> 12 | 32 -> 37 |
| TowerA_Floor_Office | 1560 -> 1876 | 776 -> 944 | 128 / 16 | 6 -> 11 | 20 -> 24 |
| TowerA_Core | 2106 -> 3058 | 846 | 132 / 10 | 3 -> 5 | 81 |
| TowerA_Roof_Helipad | 410 -> 662 | 210 | 96 / 48 | 4 -> 5 | 10 |
| Floor_Apartments | 3240 -> 5144 | 872 -> 1008 | 200 / 24 | 7 -> 12 | 40 |
| Floor_Hotel | 3056 -> 5496 | 848 -> 972 | 200 / 24 | 7 -> 10 | 38 |
| Floor_Mechanical | 896 -> 1100 | 128 -> 188 | 80 / 8 | 3 -> 4 | 12 -> 14 |
| Roof_Garden | 526 -> 1210 | 262 -> 314 | 88 / 10 | 5 -> 7 | 18 -> 20 |
| Roof_Mechanical | 696 -> 840 | 288 | 88 / 10 | 3 -> 4 | 13 |

- `check_assets`: 44 checked, 0 fail, **0 over budget** (the D55 budgets also absorb the old core /
  apartments / hotel overruns). Far-LOD alpha gate clean: fixtures, rugs, curtains, art and
  foliage are Res0 (some Res1), never Res2/Res3, so a skyline of towers costs what it did.
- Tower A stack: res0 ~16.6k, 77 sections (budget_total 60000 / 120). Sections are the cost to
  watch (one draw call per material per module) - FPS_PROTOCOL 4.1 row 3.
- Lights: client only, night only, no shadows, 2 per module (lobby 4) => 14 per Tower A, ~56 for a
  4-tower district. Each vanilla ScriptedLightBase runs its own EOnFrame; `LIGHTS_PER_MODULE` /
  `LIGHTS_ENABLED` are the knobs; FPS_PROTOCOL 4.1 rows 1-2 decide. No server cost (nothing is
  created or synchronised on the server, `CreateLight` refuses on a dedicated server).
- Texture memory: +5 material sets (marble/parquet/stone 2048 with nohq+smdi, paint/textile 1024).

## Security - PASS

- No RPC, no net sync, no server code: lights are created on clients from local memory points
  (`g_Game.IsDedicatedServer()` guard + vanilla CreateLight server refusal); a client cannot
  influence another client or the server through them.
- Collision: new solids only where walkable clutter would otherwise be clipped (plant/tree pots,
  lounge chairs, coffee table, loungers, pumps). All inside the footprint; Tower A modules'
  Geometry bounds still exactly +-12 m; no new solid in the core door clear zones (Geometry / View
  / Fire) on all 9 modules. Pendants, sconces, fixtures, curtains, flower boxes, ladder, string
  lights: no Geometry (no new standable surface; the mechanical-roof ladder is visual, so it adds
  no climbable route).
- Reachability flood fill unchanged (office, helipad, all variants incl. FURNISH sets; lobby =
  hall reachable, keycard room closed by design). Loot points: not inside any new solid, floor
  under each (`test_towera`, `test_kit`).
- Keycard door, leaf, reader, memory points and `Land_SKY_TowerA_Lobby` security logic unchanged
  (the class now extends `SKY_LitBuilding`, which only adds client-side light code; EEInit /
  DeferredInit still reach the lobby's server setup through `super`).
- Artwork and signage are original (procedural shapes, invented name).

## QA - PASS

- `test_towera` PASS, `test_kit` PASS (39 assets), `check_assets` 0 fail / 0 over,
  `gen_configs --check`, `gen_manifest --check`, `gen_economy --check` up to date,
  `test_sky_layout` 0 failed, `Invoke-SelfTest.ps1` all passed, `enscript_xref` OK (12 files resolve
  against the vanilla scripts reference), pyflakes clean on the generators.
- Renders (Cycles, generated textures, `reviews/img/d55_*`): day and night for Tower A and each
  variant; `--furnish` places the spawned FURNISH props exactly as the layout does; `--night`
  places point lights at the same memory points the script uses.
- Found and fixed in review: foliage cards rendered black in Cycles (coincident double-sided
  faces; preview now drops the duplicate, the P3D is unchanged); ceiling texture no longer prints
  light panels (they are emissive fixtures aligned with the script lights).
- New untested parameter: P10 (script-only light classes). In-game rows: TESTING §20 SP-01..SP-09.
