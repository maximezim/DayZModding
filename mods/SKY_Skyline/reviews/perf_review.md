# SKY_Skyline - Tower A performance review (perf-engineer, static)

Date: 2026-10-05. Scope: Tower A vertical slice (1 lobby + 5 office floors + 1 roof + 1 core, stacked via
`cfggameplay objectSpawnersArr`), keycard item, `sky_scripts` scripts, `sky_towera` config/model.cfg, texture generator, rvmats.

**No in-game measurement was possible in this environment** (Linux container, no DayZ / DayZDiag / P: drive,
no binarized ODOL, no PAA textures generated yet). Everything below is static analysis of the sources and of the
MLOD P3Ds (`tools/assets/p3d_inspect.py` plus a scratch parser that reads per-component bounding boxes). Vanilla
comparisons against `P:\scripts` / `P:\DZ` could not be run; where this matters it is marked "verify on P:".
All budgets are **hypotheses** to be confirmed with the protocol in section 4.

Severity used here: **High** = blocks release, or a likely measurable FPS/desync cost. **Medium** = scales badly
(players, towers, view distance) or a correctness problem in a perf-relevant LOD. **Low** = hygiene.

---

## 0. Measured static numbers (from the MLODs)

| Model | Res0 | Res1 | Res2 | Res3 | Shadow | Geometry (tris / comps) | Fire (comps) | View (tris / comps + occluders) | Roadway | Sections Res0 (alpha) |
|---|---|---|---|---|---|---|---|---|---|---|
| sky_towera_lobby | 1064 | 680 | 92 | 8 (glass only) | 60 | 204 / 17 | 17 | 128 / 10 + 4 | 8 | 4 (1) |
| sky_towera_floor_office | 928 | 544 | 56 | 16 | 48 | 144 / 12 | 12 | 104 / 8 + 4 | 8 | 5 (1) |
| sky_towera_roof_helipad | 98 | 98 | 96 | 48 | 48 | 96 / 8 | 8 | 104 / 8 + 4 | 8 | 2 (1 decal) |
| sky_towera_core | 2738 | 918 | 10 | 10 | 12 | 1044 / 87 | 87 | 632 / 52 + 4 | 72 | 3 (0) |
| sky_keycard | 12 | 12 | - | - | - | 12 / 1 | 1 | - | - | 1 |

Whole tower (1 + 5 + 1 + 1 objects):
- Triangles at Res0: 1064 + 5 x 928 + 98 + 2738 = **8,540** (low for a 31 m building; triangles are not the problem).
- Sections / draw calls, main pass: Res0 4 + 25 + 2 + 3 = **34**, of which **7 alpha-blended** (6 glass + 1 decal). Res3: 1 + 10 + 1 + 1 = **13**, of which **6 still alpha** (glass).
- Faces are already grouped by material in face order (material runs == distinct materials in every LOD), so sections == materials.
- Alpha-blended glass area, Res0/Res1: lobby 1,268 m2 (double-sided), each floor 614 m2 (4 x 24 m x 3.2 m, x2 faces) -> **about 4,400 m2 of alpha per tower** at near LODs, about 2,170 m2 at Res2/Res3 (single-sided, still alpha).
- Shadow Volume LODs: every box is stored with 24 points for 8 unique positions (core 24/8, floor 96/24, lobby 120/32, roof 96/24) = topologically open.

---

## 1. Findings

### High

**H1 - Core: door openings are cut only at stop 0; every upper stair door and elevator landing is solid wall (all LODs).**
- Where: `assets/blender/skygeo.py:221-234` (`wall_x`) and `:237-249` (`wall_y`) take `hole[0]` only when several openings share the same horizontal span; `assets/blender/build_towera.py:261-266` passes 7 stacked openings with identical X ranges.
- Evidence (sky_towera_core.p3d, Geometry): `Component02` = x -1.8..-0.6, **y 2.2..28.0** (south wall over the stair door, solid from level 0 lintel to the cap); `Component05` = x -0.6..0.6, **y 2.1..28.0** (north wall over the elevator doors). Same in Res0/Res1/View/Fire.
- Cost: not an FPS cost, but a blocker: players teleported to stops 1-6 arrive in a cab sealed by the shaft wall; stairs cannot be left above the lobby. It also invalidates the core's component/triangle budget (the correct model has about 12 more Geometry components, see M2).
- Fix: in `wall_x`/`wall_y`, for a segment covered by several openings, sort them by `oz0` and emit the solid pieces between them (`z0..o1.z0`, `o1.z1..o2.z0`, ..., `oN.z1..z1`). Regenerate the core and re-run `p3d_inspect`. Out of perf scope; route to asset-pipeline.

**H2 - Facade transparency: alpha glass at every LOD, double-sided at Res0 and Res1, and the lobby's last LOD is 100 % alpha.**
- Where: `build_towera.py:108-109` (`double=True` for res0 and res1), `:110` (res2 alpha), `:128` (res3 alpha); `gen_textures.py:145` (alpha 0.38); `addons/sky_textures/data/sky_glass.rvmat` (Super shader, specularPower 120, env map, 4 texture stages).
- Cost: alpha-blended sections are drawn after opaques, sorted per object, without depth writes, with full Super-shader cost per layer. A view through one floor crosses 4 glass layers (near facade front and back faces, far facade front and back faces); a view up the facade crosses one glass section per floor object. That overdraw scales with screen coverage, so it is worst at close range and when several towers are on screen. At Res2/Res3 (hundreds of metres) the interior is invisible anyway, yet the facade is still in the transparent pass. The lobby Res3 (8 tris) has only glass: no slab, no skirt (bbox y 0..6.7 vs -2.5..6.7 at Res0), so at range the base is see-through and the terrain gap may show.
- Fix:
  1. Res0: keep double-sided glass (interior view matters close up).
  2. Res1: single-sided, outward-facing glass only (inside the building you are always at Res0).
  3. Res2/Res3: replace glass with an **opaque** `sky_glass_far` material (`_co`, no alpha; tinted, with the dark interior and mullion lines baked in). Ideally put it as a band of the concrete trim sheet so Res2/Res3 are a single section per module.
  4. Lobby Res3: add the slab-edge band and the skirt (opaque), like the floor Res3.
  5. Glass rvmat: drop the constant texture maps (see M6) and compare its shader with a vanilla building glass rvmat (verify on `P:\DZ\structures\...\data\*glass*.rvmat`). If vanilla uses a cheaper glass shader, use the same.
  6. If the renderer uses resolution LODs for shadow maps, glass faces cast full shadows into the interior; give them the "no shadow" face flag (verify in-game, see the protocol, check S5).
- Expected effect (hypothesis): far LODs leave the alpha pass entirely (6 -> 0 alpha sections per tower at Res2/Res3), and Res1 alpha overdraw is halved.

### Medium

**M1 - Core LOD chain: cliff Res1 -> Res2, a duplicate Res3, and wasted Res0 triangles.**
- Where: `build_towera.py:275-276` (res2 and res3 are both the same 5-face shell), `:301-307` (140 stair steps as closed 6-face boxes).
- Numbers: Res0 2738 -> Res1 918 (34 %) -> Res2 10 (1 %) -> Res3 10 (identical). The jump from 918 to 10 is a visible pop (the door openings, cab and stair silhouette vanish at once, through the glass). Res3 adds nothing. Of the 2738 Res0 tris, about 1,680 are step boxes, whose bottom faces and overlapping sides are never seen.
- Fix: Res0: build each flight as one stepped strip (tread and riser quads plus two side polygons), about 4 tris per step -> about 600 tris instead of 1,680 (Res0 about 1,650). Res2: outer shell plus the door openings as recessed dark quads (about 60-150 tris). Res3: the current 10-tri shell. Interior cab boxes can leave Res1 (only seen through doors at close range).

**M2 - Core Geometry / Fire Geometry: 87 convex components, assessment and concrete reduction.**
- Current breakdown (from per-component bboxes): outer walls, divider, cap and ground slab 11; stairs 7 sections x (2 landings + 1 well wall + 2 wedges) = 35; elevator 7 stops x (2 side walls + ceiling + floor above stop 0) = 27; door leaves 14. All are 8-vertex boxes or wedges (convex, closed; good).
- Assessment: 87 small boxes is not expensive in itself. Large vanilla buildings commonly carry many more components (verify the count on a comparable `P:\DZ\structures` building). Collision is only resolved when something overlaps the object's bbox, which for a 28 m core is anyone in the tower, though. The H1 fix adds about 12 lintel components (6 per wall), so the correct model would reach about 99. Fire Geometry is queried by every bullet ray through the bbox; per-component bbox culling keeps this cheap, but fewer components still help.
- Concrete reduction (same collision behaviour), applied to Geometry and Fire:
  - Cab side walls: 2 x 7 per-stop boxes -> **2 full-height boxes** (they are coplanar and continuous in X; the shaft is never accessible): -12.
  - Cab ceiling of stop i plus cab floor of stop i+1 -> **one solid box** spanning `s_i + 2.7 .. s_(i+1)` (the space between is a closed shaft): 13 -> 7, so -6.
  - Stair well wall: 7 per-section boxes -> **1 full-height box**: -6.
  - Result: about 99 (after H1) - 24 = **about 75 components** (doors 14, stairs 28, cab 9, walls about 23, well 1). Going below that would require dropping animated door leaves from Geometry, which is not recommended.
- View Geometry (52 components): it only needs what blocks sight: the outer walls with openings (about 23 after H1), the cap and the 14 door leaves. Drop the stairs and cab interior -> **about 38**.

**M3 - Shadow Volume LODs are open meshes and incomplete.**
- Where: `skygeo.py:121-158`. `box()` only shares the 8 corner vertices for component LODs (`COMPONENT_LODS`, line 27), so Shadow Volume boxes get 4 unshared vertices per face (24 points per box).
- Cost and risk: RV shadow volumes must be closed (every edge shared by two faces). Expect binarize / Object Builder "shadow volume not closed" warnings and shadow artifacts or leaks. Coverage is also partial: floors and roof cast shadow from the slab only (no parapet, no partition walls); the lobby shadow bbox stops at y 3.2 (slab plus security room) although the lobby is 6.7 m tall.
- Fix: weld shadow boxes (shared 8 vertices without ComponentNN selections, e.g. a `closed=True` path in `box()` used for `LOD_SHADOW`). Add the roof parapet (4 boxes) and keep the shadow LOD at 100 tris or less per module. Whether the glass facade should shadow is an art call. With the slab-only shadow plus single-sided glass, sun floods the interior; decide it in-game (protocol check S5). Optionally add a second, coarser shadow LOD for distance (verify the LOD set on a vanilla building on P:).

**M4 - Core View Geometry occluders cover the door openings.**
- Where: `build_towera.py:353-359`: four full-height occluder planes on the outer wall faces, including the 14 door and 7 stair openings.
- Risk: if the engine uses the `occluder_NNN` selections for visibility culling (pattern taken from the Test_Building sample, `skygeo.py:205-208`), objects in the stairwell or cab seen through an open doorway can be culled: an "invisible player" exploit, not just a cost. This becomes live once H1 opens the doors.
- Fix: split the occluders around the opening column (e.g. per wall: the two solid strips left and right of the door column), or use occluders only on the opening-free east and west walls. The floor-slab occluders (`build_towera.py:142-145`) are fine; the facade correctly has no occluders (glass).

**M5 - Client: elevator ActionCondition allocates strings every frame, 5 times.**
- Where: `ActionSKY_Elevator.c:22-30` -> `Land_SKY_TowerA_Core.c:169-199` -> `SkyIsInCab` (`:130` `"elev_cab_l" + level`, `MemoryPointExists`, `GetMemoryPointPos`) and `SkyIsNear` (`:145-147`, `:190` / `:198` string concat).
- Cost: the client action manager evaluates every registered action's condition for the cursor target each frame. 5 elevator actions -> 5 x `SkyLevelOfPlayer` plus up to 10 string allocations and named memory-point lookups per frame while a player looks at any part of the 28 m core (which is most of the time inside the tower). Client-only, small, but it breaks the "no allocations per frame" rule. The server runs it once per action start (fine).
- Fix: in `SkyLoadConfig`/`EEInit`, cache `array<vector>` of model-space positions for `elev_cab_l*`, `elev_call_l*` and `elev_panel_l*` (and an `array<string>` of door source names for M7). Compute `WorldToModel(player pos)` once and use index lookups. Optionally cache the last `(player, frame time) -> level` result so the 5 actions share it.

**M6 - Textures: constant-value maps at full resolution; wallpaper over-dense.**
- Where: `gen_textures.py`: `sky_metal_as` (`:138`), `sky_carpet_as` (`:190`), `sky_wallpaper_as` (`:201`), `sky_asphalt_as` (`:211`) are constant 2048 maps; `sky_carpet_smdi` (`:189`) and `sky_wallpaper_smdi` (`:200`) are constant 2048; `sky_glass_nohq/_smdi/_as` (`:148-150`, 512) and `sky_roofmark_nohq/_smdi/_as` (`:227-229`, 1024) are flat or constant; `sky_keycard_nohq` (`:253`) is flat.
- Cost: about 2.8 MB (DXT1) to 5.6 MB (DXT5) of VRAM per 2048 map with mips, plus PBO size, for zero information. In the tower set that is about 20 MB of about 90 MB total (estimate; streaming means actual residency depends on distance).
- Fix: replace them in the rvmats with procedural textures (`#(argb,8,8,3)color(r,g,b,a,AS|SMDI|NOHQ)`, as Stage2/Stage3 already do) and stop generating the files.
- Density (`build_towera.py:35-43`): trims at 2048 / 3 m = about 680 px/m; tile 680 px/m; carpet 512 px/m; **wallpaper 2048 / 2 m = 1024 px/m** (smooth wall, seen close but plain) -> generate wallpaper at 1024 (512 px/m). Concrete, metal and tile at 2048 are acceptable for trim sheets shared by the whole skyline. Do not go above 2048. All sizes are powers of two (enforced at `gen_textures.py:271`). The suffixes `_co _ca _nohq _smdi _as` are correct.

### Low

- **L1 - `SkyOccupants` allocations** (`Land_SKY_TowerA_Core.c:202-214`): 2 new arrays plus `GetPlayers` plus, per player, a string concat and memory-point lookup inside `SkyIsInCab`. It is called once per request, twice in the overload branch of `SkyDepart` (`:273` and `:275`), and once in `SkyArrive` (`:299`). Event-driven, behind the per-player limiter and the 4 s cooldown, so O(players) a few times per trip: negligible server cost. Fix: reuse member arrays, hoist the cab centre out of the loop (M5 cache), add a cheap `DistanceSq` pre-filter, and store the result of line 273 instead of recomputing it at 275.
- **L2 - `SkyApplyDoors` string concat** (`:103`): 7 allocations per state change (about 4 per trip), on both sides. Precompute the names (M5).
- **L3 - Rate limiters per instance**: the lobby has 2 and the core 1 `SKY_RateLimiter`, each bounded at 512 entries with prune (`SKY_RateLimiter.c:19-40`): bounded, good. With many towers, a single static limiter per class would hold one map instead of N. `Prune` allocates only when full. OK as is.
- **L4 - Lobby `SkyLockAll` CallLater not removed** (`Land_SKY_TowerA_Lobby.c:76`): the destructor (`:36-40`) removes only `SkyRelock`. Add `Remove(SkyLockAll)` (only matters if the object is deleted within 1 s of init).
- **L5 - `SkyRelock` may stack** (`Land_SKY_TowerA_Lobby.c:160`): one CallLater per successful swipe. It is normally 1 per door, because a swipe requires a locked door, but it can stack if the door gets locked by another path and is swiped again within 60 s. Call `Remove`/`RemoveByName` before `CallLater`.
- **L6 - Roof LOD chain is flat**: 98 / 98 / 96 / 48. Res1 equals Res0 and Res2 only drops the decal. Use 3 LODs (Res0 98, Res1 48, Res2 12 = slab-edge band) or keep 4 with real steps. The roofmark decal is alpha-blended: make it alpha-tested or bake it into a concrete variant (it is seen mostly from the air).
- **L7 - Mullions as closed 6-face boxes** (`build_towera.py:114-122`): 64 mullions = 768 of the floor's 928 Res0 tris; top and bottom faces sit against the slabs and are never visible. Skip `+z/-z` (-33 %), and in Res1 also the inward face. Triangles are cheap here; do it when touching the generator for H2.
- **L8 - Keycard**: a 512 texture for an 86 x 54 mm card (3 tiers = 3 maps), and Res1 duplicates Res0 (12 tris). Use 256 and drop Res1 (or keep it; the cost is trivial). No shadow LOD is fine for an item.
- **L9 - Network/entity count**: each tower adds 8 replicated `House` entities via `objectSpawnersArr` (not static map objects), and the core registers 3 tiny net-sync vars (5 bits + 2 bits + bool) with `SetSynchDirty()` only on real changes (`:84`, `:227`): good. For one tower this is negligible; for a skyline of N towers measure the join time and the bubble entity count (protocol S6).
- **L10 - Per-object LOD switching**: the 5 floors are separate objects at different heights, so they can sit on different LODs at once (mullion density changes mid-facade). This is visual only. Keep the Res0 -> Res1 facade difference small (already only mullion spacing).
- **L11 - Hygiene**: config comments name non-existent classes `SKY_KeycardDoorHelper` and `SKY_ElevatorCore` (`config.cpp:50`, `:127`, generated from `gen_configs.py:130`, `:148`).
- **L12 - Spawned buildings are not in the baked navmesh** (objectSpawnersArr). Watch for zombie path-failure spam or CPU in the server RPT near the tower (protocol S4). Not verifiable statically.

### Script verdict (server FPS)

No per-frame server work: no `OnUpdate`/`EOnFrame`/`CommandHandler` overrides and no repeating `CallLater`. All work is triggered by actions and is rate-limited per identity plus a per-core cooldown. There is no custom RPC; notifications are targeted to one player. All CallLaters are one-shot and removed in destructors (except L4). Collections are bounded. Logging is per event and rate-limited for denials. **Scripts pass** for server FPS; M5 is a client-side hygiene fix.

---

## 2. Budget hypotheses (for the manifest)

Triangles per LOD, sections = materials per LOD (alpha sections in brackets), components = ComponentNN count.
"Now" = current MLOD. All targets are hypotheses until the protocol below confirms them.

| Module | Res0 | Res1 | Res2 | Res3 | Shadow (closed, welded) | Geometry comps / tris | Fire comps | View comps (+occluders) | Roadway |
|---|---|---|---|---|---|---|---|---|---|
| Floor (office) | <= 1,500 tris, <= 5 sec (1 alpha, 2-sided) | <= 60 % Res0, <= 4 sec (1 alpha, 1-sided) | <= 120 tris, <= 2 sec (0 alpha) | <= 24 tris, 1 sec (0 alpha) | <= 100 | <= 24 / <= 300 | <= 24 | <= 16 (+4 horizontal) | <= 16 |
| now | 928, 5 (1) | 544, 5 (1) | 56, 2 (1) - fail alpha | 16, 2 (1) - fail alpha | 48, open - fail | 12 / 144 | 12 | 8 (+4) | 8 |
| Lobby | <= 2,000, <= 5 sec (1 alpha) | <= 60 %, <= 4 sec (1 alpha, 1-sided) | <= 150, <= 2 sec (0 alpha) | <= 30, 1 sec (0 alpha), includes skirt | <= 120 | <= 32 / <= 400 | <= 32 | <= 20 (+4) | <= 16 |
| now | 1064, 4 (1) | 680, 4 (1) | 92, 2 (1) - fail | 8, 1 (1), no skirt - fail | 60, open - fail | 17 / 204 | 17 | 10 (+4) | 8 |
| Roof (helipad) | <= 300, <= 2 sec (0 blended; decal alpha-tested) | <= 120, 1 sec | <= 24, 1 sec | (optional) | <= 100, includes parapet | <= 12 | <= 12 | <= 12 (+4) | <= 16 |
| now | 98, 2 (1) | 98 - no reduction | 96 - no reduction | 48 | 48, open, no parapet - fail | 8 | 8 | 8 (+4) | 8 |
| Core (stairs + elevator, 7 stops) | <= 2,000, <= 3 sec | <= 1,000, <= 3 sec | <= 150, 1 sec | <= 20, 1 sec | <= 24 | <= 80 / <= 1,000 | <= 80 | <= 40 (occluders must not cover openings) | <= 100 |
| now | 2738 - fail | 918 | 10 (cliff) - fail | 10 (dup) | 12, open - fail | 87 / 1044 (H1 bug; about 99 when fixed, about 75 after M2) | 87 | 52 (+4 over openings) - fail | 72 |
| Keycard (item) | <= 100, 1 sec | <= 50 % or none | - | - | none | 1 / <= 12 | 1 | - | - |

Ratio rule (hypothesis): each Res step should be at most about 50-60 % of the previous one, and none should drop below about 5 % in one step (no pop) unless the silhouette is unchanged.

Per-tower totals (hypothesis): Res0 <= 12,000 tris, <= 36 sections, <= 7 alpha sections; Res2/Res3 <= 12 sections and **0 alpha**.

Textures (hypothesis):
- Shared trims <= 2048 at <= about 700 px/m.
- Interior surfaces with low detail (wallpaper, carpet) <= 1024.
- Glass far `_co` <= 512.
- Decals <= 1024.
- Hand items <= 256-512.
- No constant-value maps (use procedural `#(argb,...)`).
- Total tower texture set <= 80 MB VRAM at full mip.
- No unique per-module textures; every module draws from the same <= 8 rvmats.

---

## 3. "Measure it" summary

Static checks to run on Windows before the FPS test:
- Binarize the models (`tools\build\Build-Mod.ps1 -ModName SKY_Skyline`) and read the binarize/pboProject log for shadow-volume, component (non-convex) and missing-material warnings (M3, H1).
- Confirm the penetration rvmats marked unverified in `skyspec.py:60-66` exist on `P:\DZ\data\data\penetration`.
- Compare the core's component count with a vanilla multi-storey building in Object Builder (M2).
- Logs: `server\profiles\diag-server\*.RPT`, `script_*.log`, `*.ADM` (teleport and keycard lines), and `server\profiles\diag-client\` for the client.

---

## 4. DayZDiag FPS test protocol (to run on the Windows workstation)

**Status: not executed. No in-game measurement was possible in this environment.**

### Setup
1. Build and launch: `tools\build\Build-And-Run.ps1 -ModName SKY_Skyline -FilePatching` (diag server + client, same machine). Repeat the final pass with `-Mode Dedicated` (release-like: `verifySignatures=2`, `BattlEye=1`, `allowFilePatching=0`) for the server-side numbers.
2. Two `cfggameplay.json` variants on the same map spot, open terrain or the town edge chosen once and recorded:
   - **A (baseline)**: `objectSpawnersArr` without the tower.
   - **B (tower)**: Tower A at origin T.
   - **C (stress)**: a 3 x 3 grid of Tower A, 60 m spacing, centred on T. It amplifies the deltas above run-to-run noise.
3. Freeze conditions: fixed `serverTime` with `serverTimeAcceleration = 0` (noon, and a second set at 17:00 for long shadows); fixed weather (clear, no fog, rain 0) via the mission's `cfgweather.xml` (diag mission copy only, never the vanilla `mpmissions`); same client video preset ("High", fixed resolution, VSync off, frame cap off); no other clients for the client runs.
4. View distance settings, two required plus one optional. Set them in the client profile (`<name>.DayZProfile`: `viewDistance` / `preferredObjectViewDistance`; verify the key names in the generated profile) and restart the client between settings:
   - **VD1 = 1000 m / object 1000 m**
   - **VD2 = 3000 m / object 1600 m (or the client maximum)**
   - optional VD0 = 500 m
5. Server frame time probe (the vanilla DayZ server has no `#monitor`): a **diag-only, never shipped** server mod, e.g. `SKY_PerfProbe`, in its own PBO and not part of SKY_Skyline. A `modded class MissionServer` accumulates the `OnUpdate(float timeslice)` deltas and every 10 s prints avg / max / p99 frame ms plus the `CallQueue`-relevant counts to `script_*.log`. Verify `MissionServer.OnUpdate` on `P:\scripts\5_Mission` before writing it (enforce-coder task). Alternative: the diag server's own statistics if its diag menu exposes them.
6. Client measurement: the DayZDiag diag menu (default binding: hold Win+Alt; verify) -> Statistics / FPS overlay (frame ms, and triangles/draw calls if exposed). Capture with a frame-time logger if available (e.g. PresentMon or CapFrameX) for avg FPS, 1 % low, and avg frame ms. Each capture is **60 s standing still** after 20 s settle (texture streaming), 3 repeats per cell; report the median.

### Camera positions (relative to the tower origin T; same position and heading in A, B and C)

| ID | Position | Heading | Exercises |
|---|---|---|---|
| P1 | street, 30 m south of the facade, eye height | N, tower fills the view | Res0 facade, 2-sided alpha overdraw, mullions |
| P2 | inside floor 3, SW office doorway | NE across the floor through 2 facades | interior overdraw (4 glass layers), core Res0, wallpaper/carpet textures |
| P3 | 300 m south, on the ground or a rooftop | N | Res1/Res2 switch, alpha at mid range |
| P4 | 1000 m south, elevated (hill or building) | N | Res3 / far LOD, alpha at range, LOD pops |
| P5 | roof, next to the helipad | S, looking down over the edge | roof LODs, decal, shadow LOD of the floors below |
| P6 | lobby security room | out through the lobby glass | lobby Res0, door/keycard area |

Run P1-P6 at VD1 and VD2 for A and B, and P1/P3/P4 for C.

### Server-side scenarios (diag first, then dedicated)
- **S1 idle**: 0 players for 10 min, then 1 player idle at P2 for 10 min. Compare server avg/p99 frame ms between A and B.
- **S2 elevator loop**: 2 clients ride lobby <-> roof continuously for 10 min (about 1 trip per 8-10 s), with a third client spamming every elevator action and the keycard swipe as fast as the UI allows. Watch frame p99, `script_*.log` (no errors, no "invalid target level"), the ADM teleport lines (one per occupant per trip), and that the number of pending CallLaters stays at 3 or fewer per core. Add a probe counter if possible.
- **S3 desync**: during S2, check the riders for rubber-banding or falling after `SetPosition` (`Land_SKY_TowerA_Core.c:306`). Watch the RPT for position-correction messages and the client for "teleport back".
- **S4 AI**: spawn about 10 infected around the lobby entrance. Watch the RPT for path-failure spam and server frame p99 (L12).
- **S5 visual sanity** (no numbers): shadow artifacts or leaks at 17:00 (M3); whether glass casts shadows into the interior (H2.6); LOD pops while walking P1 -> P4; invisible players in the stairwell seen through doors (M4, after H1).
- **S6 join**: client join time and the replicated-entity count near the tower in configs A, B and C (L9).

### Pass / fail thresholds (hypotheses, relative to baseline A at the same spot and settings)

| Metric | Pass | Fail |
|---|---|---|
| Client avg frame ms, B vs A, P1/P3/P4/P5/P6 | delta <= +1.0 ms (or FPS >= 95 % of A) | > +2.0 ms |
| Client avg frame ms, B vs A, P2 (interior, worst overdraw) | delta <= +2.0 ms | > +3.0 ms |
| Client 1 % low, B vs A, any position | >= 90 % of A | < 80 % |
| Client, C (9 towers) vs A at P3/P4, VD2 | delta <= +4.0 ms | > +6.0 ms |
| Res2/Res3 at P4: alpha sections visible (diag stats or frame capture) | 0 | > 0 |
| Server avg frame ms, S1/S2, B vs A | delta <= 2 % | > 5 % |
| Server p99 frame ms during S2 | no spikes > 5 ms above A attributable to SKY (probe log) | any repeatable spike |
| Script/RPT errors from SKY, S1-S6 | 0 | any |
| Pending SKY CallLaters per core | <= 3 at all times | growth over time |
| VRAM delta B vs A (diag stats or GPU memory counter) | <= 80 MB | > 150 MB |

Between 'pass' and 'fail' = investigate (re-run 5 times; profile with the diag menu engine/script profiler if available).

---

## 5. Required before re-review

1. H1: fix the opening generation in `skygeo.wall_x/wall_y`; regenerate the core.
2. H2: Res1 single-sided glass; opaque far-glass material at Res2/Res3; lobby Res3 with slab and skirt.
3. M1-M4: core Res0 steps, a real Res2 for the core, the M2 component merges, welded and complete shadow volumes, occluders clear of the openings.
4. Re-run `p3d_inspect.py --json` against the budget table above (it can be turned into a `--spec` gate file), then execute section 4.

GATE: FAIL (static)
