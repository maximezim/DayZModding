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
