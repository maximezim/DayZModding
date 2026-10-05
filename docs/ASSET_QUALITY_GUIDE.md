# Asset quality guide: realistic DayZ buildings and models

Applies to every model and building in this repo (SKY_Skyline and all future mods). It is the
quality bar the `asset-pipeline` agent builds to, and the `qa-tester` / `perf-engineer` agents
review against. Engine facts marked **(verify)** must be checked against a comparable vanilla
asset on `P:\DZ\...` before relying on them; cite the file you checked.

Priority order when goals conflict: **correct (collision, LODs, no exploits) > believable at
gameplay distance > performance budget > detail.** Realism that breaks a budget is not done:
recover it with textures, normals and LODs, not triangles.

---

## 1. What "realistic" means in DayZ

DayZ is played at three distances. A building must hold up at each:

| Distance | What the player judges | Where realism comes from |
|---|---|---|
| 0-10 m (inside, at the door) | edges, materials, scale, wear, clutter | bevelled edges, baked normals, texel density, decals, props |
| 10-150 m (street) | silhouette, depth, rhythm, colour variation | facade depth (recessed windows, cornices, balconies), material breakup, grime gradients |
| 150 m+ (skyline) | silhouette and value contrast only | roofline variety, roof clutter, lit windows at night, opaque far-LOD glass |

The current SKY_Skyline assets are **box-built placeholders with correct gameplay structure**
(collision, LODs, doors, budgets). They read as "blockout" up close because they lack: edge
bevels, facade depth, material breakup, wear, and unique detail. Section 9 is the upgrade
roadmap for them.

## 2. Reference and scale (do this before any geometry)

1. **Collect references** for every building type: 10-20 photos (front, corner, roof, ground
   floor, interior, details, damage). Note the region (DayZ = post-Soviet Eastern Europe:
   Chernarus / Livonia architecture, panel blocks, brick, plaster, corrugated metal). Original
   designs only: no real brands, logos or recognisable copyrighted buildings.
2. **Write the measurements into the spec** (`assets/skyspec.py` or the mod's equivalent), never
   into the builder: storey heights, wall and slab thickness, opening sizes, module grid.
3. **Real-world dimensions** (metres; player is ~1.8 m; verify against a vanilla house on P:):

| Element | Typical value |
|---|---|
| Residential storey (floor to floor) | 2.8-3.0 |
| Office / commercial storey | 3.3-3.6 (SKY uses 3.5) |
| Ground floor retail / lobby | 4.0-7.0 |
| Interior door (clear) | 0.8-0.9 x 2.0-2.1 |
| Exterior / entrance door | 0.9-1.2 x 2.1-2.4 (double 1.8-2.0) |
| Window sill height | 0.85-0.95 (residential), 0-0.3 (curtain wall) |
| Stair riser / tread / width | 0.16-0.18 / 0.27-0.30 / >= 1.1 |
| Handrail / parapet height | 0.9-1.1 (parapet 1.1-1.5 on roofs) |
| Exterior wall | 0.25-0.45 (panel/brick), interior partition 0.10-0.15 |
| Floor slab | 0.20-0.30 |
| Corridor width | >= 1.2 (hotel 1.6-2.0) |

4. **Gameplay clearances override realism** where they conflict: door openings >= 1.0 m clear,
   corridors >= 1.2 m, stairs >= 1.1 m wide, headroom >= 2.2 m, no gap a player can wedge into
   (0.3-0.6 m slots), no climbable ledge that reaches a slab above (see `test_kit` reachability).

## 3. Form: silhouette, depth, hierarchy

Realism is mostly **depth and hierarchy**, not polygon count.

- **Three levels of form**: primary (mass, roofline, setbacks), secondary (floor bands,
  balconies, cornices, window reveals, pilasters, canopies), tertiary (sills, frames, mullions,
  gutters, pipes, AC units, signage plates, vents). A building with only primary forms looks like
  a placeholder; every facade needs all three.
- **Facade depth**: glazing set back 0.10-0.25 m from the wall face (window reveal), sills that
  project 0.03-0.06 m, floor bands/cornices projecting 0.05-0.20 m, balconies 1.0-1.5 m. Depth
  creates shadow lines that sell scale from the street.
- **Break repetition**: vary every 2-4 bays (open/closed blinds, AC units, balcony clutter,
  different window atlas cells, missing panels, boarded windows). Vary per floor variant and via
  `hiddenSelectionsTextures` per instance.
- **Rooflines**: parapet caps, stair/elevator penthouses, water tanks, HVAC units, antennas,
  satellite dishes, railings, roof drains. The skyline LODs keep the largest of these.
- **Ground floor matters most**: shopfronts, canopies, entrance steps, ramps, bollards, plinth
  material (stone/concrete band 0.5-1.0 m high), signage plates, shutters, graffiti, grime.
- **Damage and age** (DayZ tone): cracked plaster, missing tiles, rust streaks under metal,
  water stains under sills, broken windows (boarded or holed), overgrowth at the base. Use
  decals and texture variation; keep collision intact unless the damage is a gameplay feature.

## 4. Mesh quality (Blender)

- **Bevel every exterior edge the player can see up close**: 1-3 cm chamfer (one segment) on
  walls, slabs, frames, furniture. Hard 90-degree box edges are the #1 "fake" tell. Use a Bevel
  modifier with angle limit in the generator, or bake the bevel into the normal map (section 5).
- **Normals**: weighted normals (Weighted Normal modifier) or custom split normals on bevelled
  low-poly; flat shading only where intended (panels). No smoothing seams across hard edges.
- **Topology**: quads/tris without long slivers; no n-gons in exported LODs; no T-junctions at
  module seams (they crack under LOD changes); merge by distance; no interior faces that are
  never seen (Res LODs), but **closed convex** components in Geometry/Fire/View LODs.
- **Modular grid**: design facades on a module (e.g. 1.5 m or 3.0 m bay, 3.5 m storey) so kit
  pieces snap; keep the origin rule consistent (SKY: origin = slab top at footprint centre).
- **Instancing**: repeated detail (window frames, AC units, railings) as shared geometry in the
  generator, or as proxies where the proxy path is verified (D27) - not hand-duplicated.
- **Scale check**: import a vanilla character/door proxy reference into the scene (or place a
  1.8 m capsule) in every generator's preview render.

## 5. Textures and materials (DayZ Super shader)

- **Texel density**: pick a target per asset class and hold it: buildings ~512 px/m on trims
  (SKY uses 3-4 m per 2048 sheet = 512-680 px/m), props ~1024 px/m, far LODs much lower. Record
  the mapping in the manifest (as done for brick: 3.44 m per U tile).
- **Trim sheets + tiling + unique**: walls/floors from tiling materials, edges and details from
  trim sheets (bands), one small unique atlas for signage/panels. Few materials, many assets.
- **Map set** (suffixes are enforced by ImageToPAA): `_co`/`_ca` colour (no baked lighting
  except subtle AO), `_nohq` normal, `_smdi` (G = specular intensity, B = gloss), `_as` ambient
  shadow, `_mc` macro (large-scale variation, **verify** which vanilla building rvmats use it,
  PENDING B3), `_dt` detail. Information-free maps become procedural rvmat stages (`#(argb,...)`).
- **Material values** (believable ranges; tune on screen at noon and 17:00):

| Material | Colour (albedo) | Spec (smdi G) | Gloss (smdi B) |
|---|---|---|---|
| Concrete / plaster | mid grey/beige, never pure white | 0.05-0.15 | 0.1-0.25 |
| Brick | desaturated red-brown, per-brick variation | 0.05-0.10 | 0.1-0.2 |
| Painted metal | colour + rust streaks | 0.2-0.4 | 0.3-0.5 |
| Bare/brushed metal | darkish | 0.5-0.8 | 0.5-0.7 |
| Glass | dark, reflection does the work | 0.8-1.0 | 0.9-1.0 |
| Wood (furniture) | warm, grain along the long axis | 0.1-0.3 | 0.2-0.4 |
| Fabric | low contrast weave | 0.02-0.05 | 0.05-0.15 |
| Asphalt | dark grey, lighter wear lanes | 0.05-0.1 | 0.1-0.2 |

- **Breakup layers** on every surface: macro value variation (large, soft), mid detail (stains,
  patches), micro (grain/normal). Grime gathers **under** sills and ledges and **at the base**
  (gravity), edges get lighter wear. Do it in the generator (masks from geometry: height, edge,
  cavity), not by hand-painting outputs.
- **Normal maps from geometry**: bake high-poly detail (bevels, bricks, panel joints, bolts)
  onto the low-poly in Blender (Cycles bake, selected-to-active) instead of drawing heights in
  Pillow. Bake AO the same way into `_as` (or fold it into `_co` for trims, as SKY does).
- **Glass**: Res0 alpha glass only where you can see in; Res1+ single-sided; Res2+ **opaque**
  `glassfar` (no blended alpha at range: `check_assets` gate). Fake interiors with the window
  atlas (rooms, blinds, lit/unlit sets) on opaque storeys and far LODs.
- **Decals**: dirt, cracks, leaks, graffiti as separate alpha-tested quads with a per-type
  offset (D19), only on opaque surfaces (D44); prefer baking repeated grime into the facade
  texture (macro/trim) over spawning decal entities.
- **No real-world IP**: original lettering, invented brands, generic signage (the security gate
  checks artwork).

## 6. LODs, collision and the gameplay LODs

Quality includes the invisible LODs: a beautiful building with bad collision is a bug.

- **Resolution LOD chain**: each step ~40-60 % of the previous triangles, keep silhouette and
  the largest depth cues, drop tertiary detail first, merge materials toward fewer sections at
  range (far LOD = 1-2 sections, opaque). No LOD may open holes (back faces, missing caps).
- **Geometry**: closed convex components, simple boxes; mass set; `autocenter = 0` for modules;
  doors as their own component with the door selection; budgets per category in the spec.
- **View Geometry**: everything that blocks sight (walls, slabs, louvres); not glass; no
  occluders over openings (perf_review M4).
- **Fire Geometry**: matches the visual wall thickness; penetration materials per surface
  (PENETRATION, verify paths - P3).
- **Roadway**: every walkable surface (floors, stairs, roofs) with the right surface type for
  footsteps; never over holes (core shafts).
- **Memory**: door axes/actions, light points, loot/event points, named and checked by tests.
- **Shadow volume**: closed, simple (hull + door boxes), no thin slivers; none for low or
  wall-mounted props.
- **Navigation**: DayZ AI uses the runtime navmesh (no Paths LOD): keep doors >= 1.0 m, aisles
  >= 1.2 m, stairs regular; the reachability flood fill must pass with furniture placed.

## 7. Lighting and night

- Emissive lamps and lit window sets are cheap (no dynamic lights): use them to make the city
  read at night. Never switch them from script per frame (D23).
- Dynamic lights only behind a hard cap and a verified light class (perf L7).
- Check every asset at noon, 17:00 (long shadows) and night.

## 8. Process: how every asset is made and accepted

1. **Spec first**: dimensions, module grid, materials, budgets, loot/memory points in the spec.
2. **Generator, not hand edits**: Blender Python builds the asset deterministically from the
   spec; outputs are committed; `--check`/rebuild proves they are current.
3. **Preview renders** at the three distances (contact sheet in `reviews/img/`), with a human
   scale reference, before any gate.
4. **Static gates**: `check_assets` (budgets, LODs, far-LOD alpha), geometry tests (watertight,
   reachability, door swing, clear zones), `p3d_inspect`, texture size/suffix checks.
5. **Agent gates**: perf, security (exploitable geometry, wallhacks, sealed rooms), QA.
6. **In-game**: TESTING.md rows for the asset type (collision, bullets, view, doors, LOD pops,
   shadows, night), then FPS protocol. Only then `packed -> tested -> done`.

### Definition of done for a building (all must hold)
- [ ] Real-world dimensions from the spec; human-scale check in the preview.
- [ ] Primary + secondary + tertiary forms on every visible facade; ground floor detailed.
- [ ] Bevelled or normal-baked edges on everything within 10 m.
- [ ] Materials with macro/mid/micro breakup; grime follows gravity; no visible tiling at 30 m.
- [ ] Texel density within the asset class target; power-of-two textures, correct suffixes.
- [ ] Full LOD chain without holes; far LODs opaque, 1-2 sections; shadow volume closed.
- [ ] Geometry/View/Fire/Roadway/Memory complete; every room reachable; no wedge gaps.
- [ ] Within budget, or the overrun is flagged with a reason in DECISIONS.md.
- [ ] Original artwork only; manifest entry updated.

## 9. SKY_Skyline upgrade roadmap (from placeholder to realistic)

In priority order; each step is a generator change + re-export + gates (Tower A changes need
the user's go-ahead: it is the frozen test reference until its in-game test passes).

1. **Bevels and weighted normals** in `skygeo` box helpers (Res0/Res1 only; collision stays
   boxes). Biggest visual gain for the cost.
2. **Facade depth**: recessed glazing (0.15 m reveals), projecting floor bands and cornices,
   mullions with depth, spandrel panels between floors on curtain walls; balconies on apartment
   floors; louvre fins with real depth on mechanical floors.
3. **Baked maps**: high-poly detail baked to `_nohq` and AO (Cycles) instead of Pillow
   heightfields; per-building macro grime (`_mc` once B3 is verified, otherwise unique facade
   bands).
4. **Ground floor kit**: shopfront module, canopies, entrance steps/ramps, plinth band, signage
   plates with invented names, roller shutters.
5. **Roof kit**: penthouse detail, water tanks, HVAC with fans and ducts, antennas, railings,
   drains, gravel and membrane materials.
6. **Interior quality**: skirting boards, door frames, ceiling grid and light panels, floor
   material per room type, wall wear; furniture with bevelled edges and baked AO.
7. **Variation**: per-floor and per-instance texture variants (window cells, blinds, AC units,
   damage), 2-3 colourways per material.
8. **Damage set**: boarded windows, broken glass decal, collapsed ceiling tiles - visual only
   unless a gameplay feature needs collision.

**Status (realism pass, SKY D53):** step 2 done (spandrels, fins, cornices, corner piers, recessed
ribbon windows with frames and sills, louvre blades; balconies still open); step 4 partly (canopy,
plinth, name sign, door portal; shopfront and steps open); step 5 partly (copings, HVAC with fans and
panels, water tank, masts, pergola; railings, drains, gravel open); step 6 partly (ceiling grid with
light panels, door frames, skirting, columns; per-room floor materials and wear open). Steps 1, 3, 7
and 8 are open. Shared code: `mods/SKY_Skyline/assets/blender/detail.py`, numbers in
`skyspec.DETAIL`; new buildings reuse it instead of one-off detail.

**Status (splendour pass, SKY D55):** step 4 adds stone cladding and granite plinths; step 5 adds pad
edge / obstruction / string / bollard lights, trees, loungers, ladder; step 6 largely done (marble,
parquet, per-room paint, wainscot, curtains, radiators, rugs, art, light fixtures, wayfinding);
lighting: night-only client point lights at `light_N` memory points (`SKY_LitBuilding`), fixtures
as emissive geometry at the same spots. Still open: bevels/weighted normals (1), baked maps (3),
variation (7), damage (8), balconies and shopfronts.

## 10. Tooling notes

- Export path today: Blender 4.2 LTS + Arma Toolbox (`skygeo.export_p3d`); the test machine has
  Blender 5.2 + DayZ Object Builder (B10). Pick one exporter per project, prove it with
  `p3d_inspect` byte/structure equality on the existing assets before switching.
- Run Blender headless with `--python-exit-code 1` so a crashing generator fails the build.
- Keep generators deterministic (fixed seeds), outputs committed, and LFS for binaries.
