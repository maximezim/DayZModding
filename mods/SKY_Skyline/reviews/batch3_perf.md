# Batch 3 perf gate (perf-engineer)

## SKY_Skyline batch 3 (interior props): static perf gate, commit dd30941

This is a static review only. Nothing ran in DayZ. P:\scripts and P:\DZ are not reachable from this Linux container, so anything marked "verify on P:" is unconfirmed. I edited no files.

**Summary**
- **Per prop, the cost is low.**
  - Triangle counts are tiny and everything is inside BUDGETS.
  - No scripts, net-sync variables or timers are attached to the props (`sky_scripts` has no prop classes).
  - Doors animate only when someone interacts with them.
  - New VRAM is about 2.5 MB: wood is 1024 (co + nohq) and fabric is 512 (co + nohq). The monitor and extinguisher reuse free cells of the existing 2048 `sky_atlas`, so they add no VRAM.
- **The real risk is how many of them get placed.** Every prop is its own replicated, physics, pathgraph-updating entity. Nothing in skyspec or placement caps how many go on a floor yet.

**Geometry components by construction (from the builder):**

| Prop | Geometry components | Geometry tris | Budget |
|---|---|---|---|
| ReceptionDesk | 2 | | |
| Desk | 3 | | |
| Cubicle | 5 | | |
| ServerRack | 1 | | |
| VendingMachine | 2 | | |
| Locker | 10 | 120 | medium 12 / 200 |
| Sofa | 4 | | |
| Bed | 3 | | |
| Kitchenette | 3 | | |
| ExtinguisherCabinet | 6 | 72 | small 8 / 120 |

**Res0 sections:** at most 3 per prop. Res2 drops to 1-2 sections on every prop.

### High
None.

### Medium

**M1. Every prop is a separate entity, and nothing caps them per floor or per tower.**
- Where:
  - `addons/sky_props/config.cpp:20-210`: every class is `HouseNoDestruct`, `scope = 1`.
  - `assets/skyspec.py:352-368`: the batch-3 KIT entries have no cap. The decals have one (`DECAL_CAPS` at `:327`).
  - `placement/sky_layout.py`: no cap logic.
  - `DECISIONS.md` D3 already says proxies would cut the object count.
- Cost: as a hypothesis, an office floor of 12 cubicles, 4 desks, 1 kitchenette, 1 locker bank, 1 vending machine and 2 extinguisher cabinets is about 21 entities. A 25-floor Office Tower is then about 525, and the planned skyline (25 + 20 + 18 + 35 floors) is about 2,000 props. Each one is:
  - a replicated network object. Join and bubble-scope work grows with props x players.
  - a static physics body, up to 10 components for the Locker.
  - a pathgraph update at spawn (see M2).
  - 1-3 client draw calls.
- Unlike vanilla furniture proxies inside a building P3D, these props do not disappear with the building's far LODs. Through glass facades they stay drawn at Res2 out to object view distance. At 500 m a tower costs about 500+ extra draws instead of 0.
- Fix:
  1. Add `PROP_CAPS` to skyspec next to `DECAL_CAPS` (hypothesis: at most 25 per floor module, 600 per tower). Make `sky_layout.py --strict` fail when a cap is exceeded, and print the total entity count in `placement_report.md`.
  2. For the new tower floor generators (not Tower A, which is frozen), put the non-interactive props in the floor P3D Res0/Res1 as proxies, or as merged geometry. That covers ReceptionDesk, Desk, Cubicle, ServerRack, Sofa, Bed and Kitchenette. Keep only the door props (Locker, VendingMachine, ExtinguisherCabinet) as spawned entities. Verify the proxy path on P: with a vanilla office building P3D (`P:\DZ\structures\...`).
  3. Until then, offer pre-merged cluster modules (for example `Cubicle_Cluster_2x2` as 1 entity with 3 sections instead of 4 entities with 12 sections). That is the same move as the batch-1 combined street tiles.

**M2. Each spawned prop triggers a pathgraph update at server start.**
- Where: `placement/README.md:4-6`. The vanilla `objectspawner.c` uses `ECE_UPDATEPATHGRAPH` and then `ProcessMarkedObjectsForPathgraphUpdate()` (verify the flags on P: `scripts/3_game/objectspawner.c`).
- Cost:
  - About 2,000 small obstacles mark navmesh tiles for rebuild, which lengthens server start.
  - Cubicle and desk clutter breaks floors into narrow passages, which makes infected pathing more expensive and more likely to fail (watch for path-failure spam).
  - The flag is set by the vanilla spawner, so the mod cannot clear it per object.
- Fix: the same lever as M1. Proxies or merged geometry inside the floor P3D give one pathgraph update per floor instead of about 20. Keep the cap, and leave at least 1.2 m aisles in the layout rules so the navmesh does not fragment.

**M3. Shadow volumes are full copies of the collision, multiplied by the entity count.**
- Where: `assets/blender/build_kit.py:47-54`. `finish()` copies every Geometry face into the Shadow Volume, and now keeps the door selections too.
- Results:
  - Locker shadow is about 120 tris, 10 closed parts, close to Res0 (132).
  - ExtinguisherCabinet is about 72 tris, including its glass door.
  - Cubicle is about 60.
- Cost: shadow volumes are extruded and stencil-filled per object within shadow distance. Interior props under slabs mostly cast into rooms the sun never reaches, but they still pay the cost. Thin parts such as the 2 cm locker walls and dividers add silhouette edges with no visible result.
- The shadow-volume budget is also never checked. `check_assets.py:72` only tests `b["shadow"]`, and BUDGETS small/medium (`skyspec.py:259-260`) have no `shadow` key.
- Fix:
  1. Build prop shadow LODs from one hull box per prop, plus the door leaves as their own boxes so they still swing. Locker: 1 carcass box + 3 doors = 48 tris, or the carcass only.
  2. Call `finish(L, mass, shadow=False)` for ExtinguisherCabinet (wall-mounted, 0.4 x 0.7 m) and for low furniture (Bed, Sofa, Desk). Add an `interior_small` category, or an exemption flag, so `check_assets.py:45-46` does not demand a Shadow Volume for them.
  3. Add `"shadow": 60` (small) and `"shadow": 100` (medium) to BUDGETS as hypotheses.

### Low

- **L1. The monitor screen adds a full section for 2 triangles.**
  - Where: `build_props.py:75` (ReceptionDesk), `:87` (Desk), `:100` (Cubicle).
  - Cost: the `atlas` material appears only for the screen quad, so with 12-16 desks per floor that is 12-16 extra draws.
  - Fix: add a 5 % "screen" sub-band to the new `sky_wood` laminate band (`gen_textures.py:631-635`; batch-3 texture, not frozen) and map the screen there. Desk and Cubicle then use 2 sections.
- **L2. Cubicle Res2 buys nothing.** It is 62/60/60 tris and still has 2 sections at Res2 (fabric + laminate, `build_props.py:97-99`).
  - Fix: Res2 = the 3 screens only, which is 1 section and about 36 tris. ServerRack (14/14/12) and VendingMachine (26/26/14) are fine; triangles do not matter at this scale, sections do.
- **L3. The ExtinguisherCabinet door is a 12-tri alpha-blended box.**
  - Where: `build_props.py:191-192`. It uses `sky_glass` in Res0 and Res1: Super shader, specular power 120, env map, blended (`sky_glass.rvmat`).
  - Cost: one sorted, blended draw per cabinet, with two overlapping layers (front and back faces).
  - Fix: use a single 2-tri quad in Res0 only, and drop the glass in Res1 (or use opaque `glassfar`). Keep the glass door out of the shadow LOD (see M3).
- **L4. One normal map is nearly flat and the other will alias.**
  - `gen_textures.py:630,637`: `sky_wood_nohq` is 1024 DXT5 (1.33 MB) from a height of `0.05 * grain`, so it is almost flat. Make it procedural (`PROCEDURAL_MAPS["sky_wood"]` += `"nohq"`, `gen_configs.py:51`) or generate it at 512.
  - `:644,652`: the `sky_fabric` weave is a 2 px checker at 512. Mip 1 averages it to flat, so it shimmers up close and carries nothing at range. Use a 6-8 px weave period, or a procedural nohq.
  - With both fixed, batch 3 is about 1 MB of new VRAM.
- **L5. Fabric and wood run the full Super stack.** That means fresnel and env map (`sky_fabric.rvmat:72-79`) on a material whose SMDI specular is 0.03, so those stages contribute almost nothing. Check whether vanilla furniture rvmats (`P:\DZ\structures\furniture\...\data\*.rvmat`) use a cheaper pixel shader, and match them.
- **L6. Skeletons and doors on many entities.**
  - Where: `model.cfg:10-24` and `:38-120`; `config.cpp:49-90`, `:96-186`, `:211-251`.
  - Server cost is negligible: door state changes only on interaction, there are no scripts, and the DamageZones have 0 damage.
  - Client side, skinned or animated models may not instance as well as static ones. That is unverified and should be measured.
  - If lockers are placed decoratively in bulk, add a door-less `Land_SKY_Locker_Static` variant (same P3D minus the skeleton, via a second `CfgModels` entry) and cap the door variants per floor.
- **L7. The `check_assets` section heuristic is approximate.** `check_assets.py:81` computes `len(materials | textures) // 2`, which miscounts when procedural textures or shared paths appear. Count unique (material, texture) pairs instead. That matters once M1 merged modules approach `sections_res0`.

### Already fine
- All 10 props have three Res LODs, Geometry with `autocenter=0`, mass and Fire Geometry, plus a Shadow Volume (`build_kit.py:42-55`).
- View Geometry exists only where a prop actually blocks sight: ReceptionDesk, Cubicle, ServerRack, VendingMachine, Locker, Kitchenette.
- Door leaves are absent from Res2 (Vending, Locker, Extinguisher), so far LODs carry no animated sections.
- Every texture size is a power of two. Suffixes are `_co` and `_nohq`; `as` and `smdi` are procedural (`gen_configs.py:51,54`).
- The atlas cells reuse the existing 2048 sheet, with 6 cells still free.

### Measure it
- **Server:**
  - Start time (RPT timestamps from mission load to "Mission read") and the pathgraph messages in `server\profiles\dedicated\*.RPT`, with 0, 1 and N towers of props in `objectSpawnersArr`.
  - Join time and server FPS (`#monitor` / diag server stats) with 1 and 10 clients standing in a furnished tower (protocol S6).
  - Infected path-failure lines in the RPT near furnished floors.
  - After one restart, compare the entity count: confirm `ECE_DYNAMIC_PERSISTENCY` does not duplicate props (SLICE_REPORT open risk 1). With about 2,000 props, duplication would be the one finding that turns into a High.
- **Client (DayZDiag):**
  - Draw calls and frame ms from the diag statistics, looking at a furnished tower from 30 m, 150 m and 500 m.
  - Shadow cost: toggle shadows (or the shadow-volume diag) with 20 Lockers in view.
  - VRAM delta with the batch-3 materials on screen.
  - Locker door open/close on 10 instances. Watch frame ms, and `diag-client\*.RPT` for skeleton or animation warnings and missing penetration rvmat (`pen_glass`).

Files:
- /home/user/DayZModding/mods/SKY_Skyline/assets/blender/build_props.py
- /home/user/DayZModding/mods/SKY_Skyline/assets/blender/build_kit.py
- /home/user/DayZModding/mods/SKY_Skyline/assets/skyspec.py
- /home/user/DayZModding/mods/SKY_Skyline/assets/gen_configs.py
- /home/user/DayZModding/mods/SKY_Skyline/assets/check_assets.py
- /home/user/DayZModding/mods/SKY_Skyline/assets/textures/gen_textures.py
- /home/user/DayZModding/mods/SKY_Skyline/addons/sky_props/config.cpp
- /home/user/DayZModding/mods/SKY_Skyline/addons/sky_props/model.cfg
- /home/user/DayZModding/mods/SKY_Skyline/addons/sky_textures/data/sky_glass.rvmat
- /home/user/DayZModding/mods/SKY_Skyline/addons/sky_textures/data/sky_wood.rvmat
- /home/user/DayZModding/mods/SKY_Skyline/addons/sky_textures/data/sky_fabric.rvmat
- /home/user/DayZModding/mods/SKY_Skyline/placement/README.md
- /home/user/DayZModding/mods/SKY_Skyline/DECISIONS.md

0 High, 3 Medium, 7 Low. M1 and M2 should be binding requirements on the batch-5 layout generator (prop caps, entity totals in the report).

GATE: PASS
