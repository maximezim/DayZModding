# SKY_Skyline progress report: unattended batches 1-6

Branch `claude/dayz-modding-setup-3q6dxg`. **Nothing has run in DayZ.** Every asset is
`built-unverified`; nothing is `done`. Tower A was not changed except for a build-tool exit code
(D34, byte-identical P3Ds). The HQ landmark, the 25-floor Office Tower and the skybridge were not
started. Every batch was committed and pushed (push works now); a handoff zip was sent after
batches 1-5, and one goes out with this report.

## 1. What was built

| Batch | Built | Key files |
|---|---|---|
| 1 Street kit + props | 24 classes in `sky_street`: road / sidewalk / curb / manhole, 3 combined 12 m street tiles, street light, traffic light, barriers, bus stop, dumpster, planter, 2 wrecks, billboard A-D | `assets/blender/build_kit.py`, `addons/sky_street/` |
| 2 Textures + decals | dirt / cracks / 4 original graffiti decals, window-set atlas (lit + unlit rvmats), brick and concrete-panel facade trims; PAA conversion via `Build-SkyAssets.ps1` | `assets/textures/gen_textures.py`, `addons/sky_textures/data/` |
| 3 Interior props | 10 props in `sky_props`: reception desk, desk, cubicle, server rack, vending machine (flap), locker bank (3 doors), sofa, bed, kitchenette, extinguisher cabinet (glass door); doors on `DOOR_SWING_SIGN`, not lockable (`Land_SKY_Props_Base.c`) | `assets/blender/build_props.py`, `addons/sky_props/` |
| 4 Floors + roofs | `Floor_Apartments`, `Floor_Hotel`, `Floor_Mechanical`, `Roof_Garden`, `Roof_Mechanical` on the unchanged Tower A core, same stacking; reachability (flood fill) tested | `assets/blender/build_floors.py`, `addons/sky_floors/` |
| 5 Economy + placement | 9 new loot groups (5 floor/roof types, 4 props); layout generator with 12 m street grid, blocks, tower variants, furniture sets, decals, street lights, caps, roof drops per roof type, one infected zone per district; zombie notes per floor type; district template with unfilled site | `placement/sky_layout.py`, `placement/district_template*.yaml`, `economy/` |
| 6 Testing + Windows readiness | TESTING.md sections for every asset type (§0b, §14-§18), one-command validation `tools\tests\Invoke-ModValidation.ps1`, FPS protocol + results template, AFTER_TESTING checklist | `TESTING.md`, `FPS_PROTOCOL.md`, `AFTER_TESTING.md`, `reviews/fps_results_template.csv` |

Totals: 44 P3Ds (39 kit + 5 Tower A/keycard), 12 loot groups, 52 decisions (`DECISIONS.md`),
9 parameters P1-P9 + 12 behaviour checks B1-B12 (`PENDING_VERIFICATION.md`).

## 2. Gate results (static; reviews in `reviews/batchN_*.md`)

| Batch | Security | Perf | QA |
|---|---|---|---|
| 1 | PASS | PASS | PASS |
| 2 | PASS | PASS | PASS |
| 3 | PASS | PASS | FAIL (vending flap swung inward) -> fixed -> PASS |
| 4 | FAIL (2 sealed apartments) -> fixed -> PASS | PASS | FAIL (same) -> fixed -> PASS |
| 5 | PASS | PASS | FAIL (street tiles without survey at Y = 0) -> fixed -> PASS |
| 6 | PASS | FAIL (protocol could not produce server numbers) -> fixed -> PASS | FAIL (validation passed on spawn errors) -> fixed -> FAIL (new: live RPT read would hit a Windows sharing violation) -> fixed -> PASS |

No gate failed twice on the same issue (Batch 6 QA failed twice, on two different issues). Every finding was fixed or recorded as a decision. Your two setup commits (smoke test, SETUP_REPORT) were merged, not rebased; the verified ready line `Player connect enabled` is now used by the validation run.
Static suite on the final commit: `check_assets` 44 checked / 0 fail / 5 over budget, generators
`--check` clean, `test_kit` PASS (39), `test_towera` PASS, `test_sky_layout` PASS,
`Invoke-SelfTest.ps1` PASS, script xref OK.

### Budget overruns (flagged, accepted until measured)
- `Land_SKY_TowerA_Core` Geometry 81 > 80 components (Tower A frozen).
- `Land_SKY_Floor_Apartments` / `Floor_Hotel` Geometry 40 / 38 components, 480 / 456 tris (> 24 / 300): one component per wall piece and lintel; lintels kept for security (D37).
- `Land_SKY_Roof_Garden` Res1 128 > 120 and 3 Res0 sections > 2; `Land_SKY_Roof_Mechanical` Res1 128 > 120.

## 3. Blocked / needs you

1. **Server frame probe (B11)**: the FPS protocol's server rows need a small diag-only server mod
   (`SKY_PerfProbe`). It is new mod code, so it is not written. Say "write the perf probe".
2. **Blender on your machine (B10)**: you have Blender 5.2 + DayZ Object Builder; the P3D export was
   built on Blender 4.2 + Arma Toolbox. The committed P3Ds pack as they are; re-exports (after a P2,
   P3, P6 or P8 flip) need 4.2 + Arma Toolbox side by side, or a port of `skygeo.export_p3d`.
3. **Untested parameters P1-P9** (door swing, elevator slide, penetration paths, env map, explosion
   armor class, asphalt surface, emissive strengths, road slab thickness, yaw sense): each has a
   one-line fix in `AFTER_TESTING.md`.
4. **A surveyed site**: `placement/layout.yaml` and `district_template*.yaml` have placeholder /
   unfilled sites; `--strict` refuses them until a survey is filled in.
5. Deferred by decision (measure first): furnished floor variants with merged furniture (D43), grime
   macro maps (B3), proxies for props (D27).

## 4. Test order when you are back

Each step: diag first where noted, then dedicated; fill the TESTING.md rows and sign-off.

1. `tools\tests\Invoke-SelfTest.ps1`, then `tools\setup\Get-ToolchainStatus.ps1` (PyYAML, numpy now listed;
   run `Install-Toolchain.ps1 -Only Pillow` if missing).
2. `tools\tests\Invoke-ModValidation.ps1 -ModName SKY_Skyline -DryRun`, then without `-DryRun`
   (static checks, build, sign, deploy, server start, logs; no layout). Expect summary PASS; tune log
   patterns if not (B9-VAL).
3. **Doors and elevator first, they decide P1/P2 for everything else:** TESTING §4 D-01 (lobby door swing)
   and D-03 (elevator slide), using the Tower A slice (`placement/layout.yaml` with a surveyed site,
   README §1). If D-01 fails: `DOOR_SWING_SIGN = -1`, `gen_configs.py`, rebuild, repeat.
4. Tower A §1-§13 as before (keycard, elevator, loot, roof drop, clean logs).
5. Street kit §16 (spawn single pieces or the district template), then decals/windows §17.
6. Interior props §14 (P3-10..P3-14 door swing confirms P1 on props; P3-25 lockpick = B5).
7. Floor/roof variants §15 on the Tower A core (layout `floors:` / `roof:`).
8. District §18: survey a flat site (relief <= ~0.75 m), fill `district_template.yaml`, `--strict` PASS,
   `Invoke-ModValidation.ps1 -Layout ...`, then the survey export (`exportRadius` from the report) and
   loot (L5-xx), yaw check P5-YAW (P9), infected Z5-xx.
9. FPS protocol (`FPS_PROTOCOL.md`), after B11 if you want server numbers; client-side rows work without it.
10. Apply `AFTER_TESTING.md`: flip only what a test disproved, regenerate, re-run the listed tests, then
    move statuses `built-unverified -> packed -> tested`.

## 5. Where things are
- Decisions: `DECISIONS.md` (D1-D52). Untested assumptions: `PENDING_VERIFICATION.md`.
- Tests: `TESTING.md`, `FPS_PROTOCOL.md`, `AFTER_TESTING.md`. Gate reviews: `reviews/`.
- Asset spec (single source of truth): `assets/skyspec.py`; manifest: `assets/manifest.yaml`.
- Handoffs: `_handoff/batchN/` (git-ignored; bundle + zip + HANDOFF.txt).

## 6. Realism pass (after the batches, D53/D54)

On request ("make all already created buildings much more realistic and complete") every existing
building was re-generated with one shared detail kit (`assets/blender/detail.py`, numbers in
`skyspec.DETAIL`). Gameplay shell unchanged and re-tested.

- **Tower A**: curtain wall with spandrels, deep fins, slab-nose cornices and concrete corner piers;
  lobby with columns, tile-grid ceiling, entrance canopy with an invented `SKYLINE TOWER` sign,
  door portal, oak/walnut reception desk, benches and planters; office floor with columns, ceiling,
  door frame and skirting; helipad roof with coping, two HVAC units and a mast; core with
  handrails and door frames on every stop.
- **Apartments / Hotel**: brick / precast-panel facades with recessed ribbon windows (frames,
  mullion, sill stones, soldier course), plaster ceilings, oak door frames and skirting.
- **Plant floor**: louvre blades on a dark backing, pipes, control panels. **Roofs**: copings,
  HVAC units with fans and panels, water tank, mast, benches, pergola with deck.
- New material `ceiling`; atlas cell `signage`. Budgets raised as hypotheses (D54); gates PASS
  (`reviews/realism_gates.md`); renders in `reviews/img/`; in-game rows `TESTING.md` §19.

## 7. Splendour pass (D55)

On request ("vastly more room for materials, decorations, texture maps, interior decoration,
lighting"): budgets raised (floor res0 16k / 14 sections, lobby 20k / 16, roofs 8k / 10), five new
material sets with real maps, original artworks and wayfinding plates, baked decoration in every
module (lobby marble / limestone / pendants / lounge / trees; office light panels / plants / art;
apartments parquet / paint / curtains / radiators / flower boxes / rugs / art; hotel wainscot /
runner / sconces / art; plant floor, roofs, core wayfinding), and night-only client lights
(`SKY_LitBuilding`, 2 per module, lobby 4; untested parameter P10). Gates PASS
(`reviews/splendour_gates.md`), renders `reviews/img/d55_*.png`, in-game rows TESTING §20, FPS
checks FPS_PROTOCOL 4.1.

## 8. City buildings, wave 1 (D56)

Estimate for a full city: 35 building types, 60 variants, **148 unique models**, **651 placed
buildings** (grounded in vanilla Chernarus counts). Procedural generator `assets/blender/build_city.py`
(one style grammar, three ruin states through one ruin layer). Wave 1: 14 archetypes (6 types + 8
variants) x intact / damaged / ruined = 42 P3Ds, all passing `test_city.py` (walkability per floor,
stairs, doors, loot reachable), `test_kit.py`, `check_assets.py` (0 over budget). Progress is tracked in
the generated `CITY_PLAN.md` (30 % of the unique models; one variant per started type could already
fill 40 % of the city's lots). Next waves and the city layout generator: CITY_PLAN.md "Waves".

