# Batch 4 perf gate (perf-engineer)

## SKY_Skyline Batch 4 (floor and roof variants): static perf gate, commit fcc7f4c

This is a static review only. Nothing ran in DayZ, P: was not reachable, and I edited no files. All paths are under `/home/user/DayZModding/mods/SKY_Skyline/`.

**Summary**
- **No server script cost.** `sky_floors` contains only `HouseNoDestruct` subclasses (`addons/sky_floors/config.cpp:16-49`). There are no scripts, no net-sync variables, no timers and no loot. Nothing in `sky_scripts` references the new classes or their `light_N`, `floor_center` or `roof_drop_N` memory points.
- **Each tower has a fixed size.** The core height is fixed by `TOWER_A["typical_floors"] = 5` (`assets/skyspec.py:109`, `:132-150`). Because the core is unchanged, a tower built from these modules is still 8 entities: lobby, 5 floors, roof and core. You cannot stack more floors without a taller core variant.
- **Worst-case tower (5 Hotel floors + Roof_Mechanical), estimated:**
  - About 10.3k Res0 triangles and about 35 Res0 sections, of which 6 are alpha.
  - About 0 alpha sections at Res2/Res3.
  - All of this is inside the per-tower hypotheses in `reviews/perf_review.md` section 2.
- **Cost growth comes from the number of towers, not the number of floors.**

**Component counts.** I re-derived the check_assets numbers from the builder and they match:
- Apartments has 30 components: slab 4, glass 4, and 22 wall pieces, of which 7 are lintels.
- Hotel has 38 components: slab 4, glass 4, and 30 wall pieces, of which 10 are lintels.
- Every door in `wall_x`/`wall_y` adds a separate lintel box above it (`assets/blender/skygeo.py:299-313`).
- View Geometry has the same partitions minus the glass: 26 for Apartments and 34 for Hotel. The office floor has 8.

### High
None.

### Medium

**M1. Floor_Apartments: two of the four apartments have no door (closed navmesh islands).**
- Where: `assets/blender/build_floors.py:51-60`.
- How I traced it:
  - Hall-side openings: the south hall wall at x -1.5..-0.3 leads to SW. The west hall wall at y -1..0 also leads to SW (the y<0 half). The east hall wall at y 0..1 leads to NE.
  - Openings at (-8,-7) and (7,8) on the y=+-7 walls only connect the two halves of each L-shaped apartment.
  - Party walls at x=0 (where |y|>7) and y=0 (where |x|>5.5) have no openings.
  - Result: the NW apartment (N-W strip + W-N strip) and the SE apartment (S-E strip + E-S strip) cannot be reached.
- Cost: there is no FPS cost. However:
  - Each sealed unit is a navmesh island that the pathgraph update still builds for every spawned floor.
  - Any loot or AI target placed inside later causes path failures.
  - Half the floor cannot be played.
- `test_kit.py` only checks the core-door clear zones (`test_kit.py:102-123`). It has no connectivity check.
- Fix:
  - Add a hall door for NW: an opening on the west hall wall at y 0..1 (`("y", -5.5, ..., [(-1.0, 0.0), (0.0, 1.0)])`, or move it to (0.5, 1.5)).
  - Add a hall door for SE: an opening on the east hall wall at y -1..0.
  - Add a flood-fill reachability test to `test_kit.py` (a 0.25 m grid on Geometry at z 1.0, starting from the core stair-door zone) for every floor variant.
- This is a functional blocker for QA, not a perf blocker. Route it to asset-pipeline.

**M2. Roofs at Res3 have no slab, so the tower looks hollow from above at range.**
- Where:
  - `build_floors.py:126-132`: `roof_base` puts only the 4 parapet boxes into `res3`.
  - `assets/blender/build_towera.py:131-140`: `floor_slab` never writes `res3`.
  - Floor Res3 is single-sided outward glassfar plus a slab-edge band with no top (`build_towera.py:128`, `build_floors.py:64/87`).
- Cost: from elevated viewpoints (other rooftops, hills; perf_review P4) the Res3 tower is a ring of back-face-culled quads and you see the ground inside. The parapet boxes are also the most expensive part of Res3: 48 tris, of which the inner and bottom faces are never visible at that distance. Tower A's helipad has the same defect (frozen, so note it only).
- Fix: for both roofs, replace the parapet in `res3` with one box `(-HW, HW, -HD, HD, -SLAB_T, 1.1)`, concrete, `skip=("-z",)`. That is 10 tris instead of 48 and 1 section, and it closes the top. Keep the 4 parapet boxes in shadow, Geometry, View and Fire.

**M3. Draw calls at range: apartments and hotel use 2 sections at Res2/Res3 (concrete + glassfar).**
- Where: `build_towera.py:110` and `:128` (glassfar), and the concrete band at `build_floors.py:64/87`. This comes from the shared `facade()`.
- Cost:
  - 5 floors per tower x 2 means 10 far-LOD draws per tower from floors alone. This scales with the number of towers on screen, which is the case that matters for a skyline.
  - Floor_Mechanical already does this right: 1 section and 8 tris at Res3 (`build_floors.py:122`).
- Fix (new modules only; `facade()` must stay byte-identical for Tower A): in `build_floors.py`, emit the Res3 band as a single box `-SLAB_T..WT` using a glassfar texture whose top or bottom strip carries the slab edge, like the mechanical floor. Alternatively, add a "glassfar" band to the concrete trim sheet. Optionally apply the same to Res2. That gives 1 section per floor at range.

**M4. Alpha glass: no regression, but it is the main per-floor client cost.**
- Where: `facade()` is shared (`build_towera.py:108-110`):
  - Res0 is double-sided `glass` (about 614 m2 of blended area per floor).
  - Res1 is single-sided.
  - Res2/Res3 use `glassfar`, which is opaque (`addons/sky_textures/data/sky_glassfar.rvmat`, Super shader, no alpha renderFlags).
- So the far LODs are alpha-free, as perf_review H2 required.
- Hotel and apartments put many partition walls right behind the glass. At close range this adds opaque overdraw on top of the 2-layer alpha per facade; the triangle count is not the issue.
- Fix or advice: no change to `facade()`. When designing towers, mix in Floor_Mechanical (0 alpha sections, opaque louvre) as plant storeys to break up alpha. Measure at position P2 using a hotel floor.

### Low

**L1. Geometry overruns: acceptable after one cheap cut.**
- Components are not a stacking cost. Collision and Fire are only tested when something overlaps a floor's bbox, which in practice means the floor the player stands on and its neighbours. 30-38 small convex boxes is well below typical vanilla buildings (verify a comparable one on `P:\DZ\structures`).
- Cut: in `partitions()` (`build_floors.py:33-42`), leave out the lintel boxes for the `geo` key only. These are the spans z 2.1..WT over openings. Nobody can reach a 1.1 m slot at 2.1 m, and the doorway below it is open anyway. Keep the lintels in Fire (bullets) and View (AI line of sight).
- Effect:
  - Apartments goes to 23 components and about 276 tris, which is inside the 24/300 budget.
  - Hotel goes to 28 components and about 336 tris.
  - Fire stays at 30/38. View could use a single header box per wall instead (n+2 boxes instead of 2n+1): Apartments 23 View components, Hotel 28.
- For Hotel, record an explicit `geo_comps: 28` / `geo_tris: 340` budget in D32 rather than distorting the layout. Its room-separation T-junctions cannot be merged into convex pieces.

**L2. View Geometry has 26 / 34 components (budget hypothesis ≤16).**
- Infected and player line-of-sight raycasts test these components, but only on that floor.
- Apply the header-box change from L1 to View. Do not add vertical occluders on partitions: they have doorways (the perf_review M4 "invisible player" risk).
- The `floor_slab` occluders still apply to every new module: 4 horizontal planes at slab top (`build_towera.py:142-145`), called from all five builders (`roof_base` -> `floor_slab`). They correctly cull the storeys above and below.
- Optional: Floor_Mechanical's louvre is fully opaque with no openings, so 4 vertical occluders on its outer faces are safe. The benefit is small (a 3.2 m band).

**L3. Roof Res1 overruns (136 > 120) and a flat LOD chain (Garden 168/136/96/48, Mechanical 280/136/96/48).**
- The triangles are trivial. The real issue is that Res1 is 81% of Res0 for Garden.
- Accept the overrun, or trim:
  - Parapet `skip=("-z",)` in res0/1/2 (`build_floors.py:132`): -8 tris per LOD.
  - Planters and HVAC units are already `-z`-skipped.
- After M2, Res3 is 10 tris, so the chain gets a real last step.

**L4. Roof_Garden has 3 Res0 sections (budget 2).**
- `sky_foliage.rvmat` is `AlphaTest32`, not blended. That means no sorting and no transparent pass, and the cards are Res0-only (16 tris, `build_floors.py:144-149`).
- That is +1 near-range draw per tower: accept it.
- If you want 2 sections, use the concrete panel trim for the roof top instead of `paver` (`:137`).

**L5. Wasted Res0/Res1 faces on partitions.**
- `partitions()` emits closed 6-face boxes in res0/res1. The top faces of full-height pieces sit against the next slab, and the bottom faces sit on the slab. That is about 4 of 12 tris per wall piece (about 90 tris on Apartments, about 120 on Hotel).
- Fix: pass `skip=("+z","-z")` for pieces that span 0..WT, and `("-z",)` for jamb columns that start at 0. Keep the lintel `-z` faces.
- Related: the Roof_Mechanical fan prisms (`:165`, n=10, 36 tris each) have a hidden bottom cap. Use n=8 and drop the cap.

**L6. Shadow LODs.**
- Floors: slab only, 4 closed boxes, 48 tris. This is now welded (`skygeo.py:143-170`, perf_review M3 fixed).
- Roofs: slab + parapet, 96 tris, within 100.
- Partitions are interior, so having no shadow is correct.
- Roof_Mechanical HVAC units (up to 2.4 m) cast no shadow. That is a visual-only gap. Adding them would push the LOD to 144 tris, over budget, so leave them out or add only the tallest unit.
- Stacking 5 slab volumes per tower is a stencil-fill cost: measure it at the 17:00 sun (S5).

**L7. Roof drops: the generated event file still uses the helipad positions.**
- Where: `placement/sky_layout.py:148` uses `S.ROOF_DROPS` (+-8, +-8). On the garden and mechanical roofs those points fall inside planters and units (D33).
- The layout tool does not place batch-4 modules yet, so this is a latent issue.
- When it does: take the drop positions per roof class from the module's own `roof_drop_N` (`ROOF_DROPS_CLEAR`, `build_floors.py:30`). Crates spawned inside Geometry jitter in physics and can get stuck.

**L8. Hotel layout note (navmesh).**
- 4 of the 8 guest rooms (x<-6 and x>6) open only into the suites (`build_floors.py:74-83`).
- All rooms are reachable, but paths are longer.
- Doors are 1.0 m wide. Vanilla door widths are similar, but check infected pass-through in-game (S4).

**L9. Batch-3 M1 still open.**
- Batch-3 M1 asked new floor generators to carry non-interactive props as proxies or merged geometry. These floors carry none, so furnishing them with spawned props will hit the PROP_CAPS entity cost (`skyspec.py:357`).

### Overrun verdict (D32)
- Apartments geo 30/360: cut via L1, which brings it inside budget.
- Hotel geo 38/456: cut via L1 to 28, then accept with an explicit budget.
- Roof res1 136 and Garden 3 sections: accept, since they are near-range only and alpha-tested.
- None of these overruns is a server-FPS or desync risk.

### Measure it
- **Binarize and inspect (Windows):**
  - Run `tools\build\Build-Mod.ps1 -ModName SKY_Skyline` and check the binarize log for non-convex component or shadow-volume warnings on `sky_floors`.
  - Run `tools/assets/p3d_inspect.py --json` on the 5 P3Ds after the L1/M2/M3 changes.
- **Connectivity (M1):** after adding the flood-fill test, walk into all 4 apartments in DayZDiag. Spawn infected in the hall and confirm in `server\profiles\diag-server\*.RPT` that there is no path-failure spam into the NW/SE units.
- **Client cost:** run perf_review section 4 using a test tower of 5 Floor_Hotel + Roof_Garden.
  - P2: interior overdraw through hotel partitions plus glass.
  - P4, elevated, at VD2:
    - M2 hollow roof: should be closed after the fix.
    - M3: Res3 section count from the diag statistics should be 1 per floor after the fix.
    - Alpha sections at range: expected 0.
  - S5 at 17:00: shadow fill from the stacked slabs.
- **Server:** S1/S4 avg/p99 frame ms (B vs A) and S6 join time. `script_*.log` should show no SKY lines from these classes (they have no scripts).

GATE: PASS
