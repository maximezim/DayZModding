# D96 asset quality pass: gates, reviews, before / after

The user asked (2026-10-09), after the first Windows session, for a pass on every asset: no clipping textures, correct
dimensions, no gaps or big collisions, and much more quality and detail ("they feel sometimes like Minecraft"), with
the performance constraints relaxed. Decision D96, test rows TESTING §59, parameters P68-P72.

## What the first test showed and what caused it

| Report | Cause found offline | Fix |
|---|---|---|
| CT-13 "some textures are glitched" | 670 graphical LODs had same-facing coplanar overlapping faces (z-fighting): door / window frames flush with the wall reveals, stair nosings flush with the risers, shelf goods taller than the shelf gap, stacked boards, decals of different families at the same depth | source fixes + `zfix.resolve` at export (smaller part lifted 4 mm per layer, whole primitives) + gate |
| CT-13 "textures glitched" (2) | 438 LODs with smeared UVs: the trim mappers stretched a band down every top face that ran along Y (up to 55 m streaks) | `UVBand` / `UVTrim` horizontal mapping |
| CT-13 "details not pretty / ugly" | box-only openings and roofs, every edge exported sharp (round parts faceted), 512 px previews hid it; textures with 1-texel streak columns and cartoon blobs | detail uplift (below), smooth normals, new textures |
| WIN-06 "Too many vertices" | the limit counts render vertices (point + normal + UV) | proxy parts (P68) + vertex gate |

## Gates

| Gate | Command | Result |
|---|---|---|
| Quality (new) | `python assets/blender/test_quality.py --jobs 3` | baseline before the pass: 1,128 failures (670 z-fight, 438 smear, 20 vertex limit); self-test 9 cases PASS; final run: see the follow-up below |
| Asset budgets | `python assets/check_assets.py` | see follow-up |
| Texture references | `python assets/textures/test_texture_refs.py` | PASS (91 referenced, 0 missing) |
| Generated files | `--check` on gen_configs / gen_manifest | up to date (3 new rvmats) |
| Concealment / slits / city / kit / sync | `test_conceal.py --city`, `test_slits.py --city`, `test_city.py`, `test_kit.py`, `check_p3d_sync.py` | running after this commit; results in the follow-up section |

## Review

- **perf-engineer** (no High): M proxy parts multiply draw calls -> parts cut by storey (cull per floor); M check_assets
  did not see the parts -> counted; M stale stats -> rebuilt; L chimney pots forced a rooftile section on slate roofs ->
  brick; L Res1 prism bump -> from r 5 cm only; L slow split (O(F x M)) -> sets; L stale part files -> deleted at export.
  Accepted under the relaxed budget: Res0 +20-70 %, three 2048 sheets, 7 collision parts per gondola.
- **security-auditor**: H1 the first split also moved facade walls / glass into parts: a part failing to load would have
  left walls that still stop bullets (see-through, one-way when a solid was split) -> only render-only detail moves,
  never anything matching View / Geometry, never glass, whole primitives; H2 mattress + new pillow 0.32 m above the bed
  collision (prone head pocket) -> bed collision to the mattress top; M1 Ferris-wheel slit acceptance is whole-model ->
  follow-up; M2 the geometry gates check builder output, not the export (zfix / split) -> zfix only grows render faces
  and the split now moves no collision-matching faces, so the gates' view stays valid; L1 cornice corona added to Fire;
  L2 step flush at ground level, 3 cm; L3 van cab loft follows the collision. Hygiene: clean.

## Before / after (PBR preview: normal, macro and specular maps, physical sky, writer smoothing)

![Villa, eye height](img/d96_villa_close.png)
Louvred shutters (door-shutter atlas) with strap hinges, sashes with glazing bars, stone sills, panelled door, stone
step, half-round gutter and downpipe, subdued rising damp (no green blobs, no damp over the door).

![Villa roof](img/d96_villa_roof.png)
The rust-striped zinc sheet becomes clay pantiles at true size, ridge cap, fascia, barge boards, chimney cap and pots.

![Rowhouse](img/d96_rowhouse_corner.png)
![Shop row](img/d96_shoprow_close.png)
![Apartment block](img/d96_aptblock_close.png)
![Church](img/d96_church_corner.png)
![Corner shop](img/d96_cornershop_close.png)
![Office](img/d96_officemid_close.png)
![School](img/d96_school_close.png)
![Rendered rowhouse](img/d96_rowhouserender_corner.png)
![Warehouse](img/d96_warehouse_close.png)
![Apartment interior](img/d96_aptblock_interior.png)
![Street props](img/d96_kit_street.png)
Street props: chipped painted metal instead of rust stripes, round poles, lofted saloon and van bodies with round tyres.

## Follow-up: the full gate on every model (288 models, all states)

The first commit gated the source of CT-13 (z-fight, smear, vertex limit). The collision check ("big collisions",
"gaps") was then run on every model, one process per model (the Hospital / Mall builds need ~6 GB each, the pool
version was OOM-killed). Runs: **1,282 findings** (835 ghost collision, 274 smear, 173 z-fight) -> 466 -> 50 -> see the
final line below. What it found and what changed (all at the source unless marked *gate*):

| Finding | Fix |
|---|---|
| Warehouses: outer walls had no interior face since wave 1 (seen through from inside, collision still there) | cladding drawn inside |
| Racks / shelving: one collision box over open shelves; racks along Y built with 14 m solid side boards | `shelf_unit` along either axis, steel back panel, top deck, goods 3 cm apart; cut at a ruin's collapse floor |
| Ruins: broken windows kept a collision pane (church lancets 10-20 m2 per wall, curtain bays 3 x 2.6 m) | a broken window of a ruin opens its collision (curtain bays: broken in any state); a boarded window whose boards fell with the collapse opens too |
| Ruins: rails / desks / beds cut to stubs, render parts fell, collision stayed | low loose parts fall whole; facade pieces (`wall=True`) keep the jagged cut like the wall collision |
| Damaged buildings: broken panes | kept (vanilla), recorded by `window()` in `geo.kept_panes`, accepted by the gate |
| Bridge ladder: collision wedge down to the ground under the nest (6 m invisible wall), no rungs | steel ship ladder, treads every 25 cm, thin slab collision (P73) |
| Carousel: 5.6 m collision cylinder round a cone canopy; fence = 1 m thick bar | 8 sector slabs on the cone; 8 cm sheet under the rail (P73) |
| Floodlight: solid frustum round an open lattice | four leg solids (bullets pass the lattice) |
| Mall skylight: flat plate under the glass vault, the vault itself not solid (walk through the glass onto air) | collision follows the vault and its gables |
| Escalators: open triangle under a solid wedge | side cladding down to the floor, end panel |
| Viaduct ramp: open 10 x 7 m collision face at the high end | concrete abutment face |
| Landfill fence: 4 wires over a 2.2 m collision sheet | 9 strands |
| Water tower / town hall drum: square / hexagon collision round a round render | matching polygons |
| Z-fight: door frames inside the wall, door surrounds / steps / plinths ending in one plane, shutters at the damp decal depth, shop doors with a second frame, parasol discs overlapping, tunnel walls through the roof slab, stadium tiers nested, truss / wheel-rim joints, metro track ends, Tower A rails / plinth / mullions, column tops, two barrels in one spot | moved off the shared planes (5 mm - 3 cm), parts abut instead of overlapping, conical parasols, alternating 7 mm bar sizes |
| Smear: downpipes / rods / bridge braces / Ferris legs, 40 m slab tops, roller shutters, box sides, roof-tile edges and ridges, birch trunks (one bark cell over 7 m), church spire, drain streaks | `UVBand` along thin parts, `Lod.box` strips for wide band faces, `UVRect` third axis, `UVSlope` edges, lofted tapered trunks with `BarkUV`, slate spire, wider decals |
| *gate*: what counts as an invisible collision | seen = a render face within 20 cm, 12 cm outside, inside the solid or on its far face; allowed: low rails / desks with a drawn top, joints between collision pieces, kept panes, slivers < 1 m2 (2 m2 on a wall, < 2 % of a large wall) |
| *gate*: z-fight / smear limits | 3 layers on Res0, 6 on farther LODs, 10 on debris < 1 m; ground-contact bottoms ignored; smear = under 0.1 UV/m, measured across the true width; the farthest LOD (silhouette) is not smear-checked |

![Warehouse interior](img/d96b_warehouselarge_interior.png)
Warehouse inside: racks built along their length with back panels and goods; the outer walls now have their inside face.
(Interior previews cut the front of the building away; the ceiling now stays in the shot because the slab underside is
drawn in strips - before, one face spanning the whole depth fell to the cut.)

![Hypermarket](img/d96b_hypermarket_interior.png)
Hypermarket sales floor: gondolas with back panels (no see-through shelves over solid collision).

![Cafe](img/d96b_cafe_close.png)
Cafe terrace: conical parasols (the flat discs overlapped and flickered), door frame off the wall planes.

![Ruined church](img/d96b_church_ruined_interior.png)
Ruined church: boarded lancets boarded tight; broken lancets are open (walk / shoot through).
