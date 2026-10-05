# Decisions taken while working unattended

| # | Decision | Why | Revisit if |
|---|---|---|---|
| D1 | All untested assumptions moved into a single `ASSUMPTIONS` block in `skyspec.py`. Tower A outputs were checked to be **byte-identical** after the refactor (29 files, sha256). | Rule 2; Tower A is the reference for your testing. | — |
| D2 | Every asset is `status: built-unverified` (Tower A included); nothing is `done`. | Nothing has run in DayZ. | after your tests |
| D3 | Kit assets (street + interior props) are **separate objects** (`HouseNoDestruct`, scope 1) placed by the layout generator. Tower A P3Ds are not touched (no proxies added). | Rule 1: Tower A stays the reference. | proxies would cut object count once props are validated |
| D4 | Textures a batch needs are generated in that batch: batch 1 added paver, road markings, weathered paint/rust, foliage, props atlas, 4 billboards. Batch 2 completes decals, windows and facades. | Lowest-risk order; no placeholder textures in shipped configs. | — |
| D5 | Kit Geometry LODs carry `class=house`, `autocenter=0` but **no `map=building`**. | Props must not draw as buildings on the in-game map. | if props vanish from collision/rendering in tests |
| D6 | Street lights get an emissive lamp material only (`EMISSIVE_LAMP`), with no scripted dynamic light. A memory point `light` is ready for later. | No scripts or server cost in batch 1; a power/generator system is planned. | when the power system is built |
| D7 | Road modules are flat 0.3 m slabs on a 12 m grid (road top z=0, sidewalk top +0.15). Terrain fitting is the layout generator's job (batch 5). | Modules must snap; slopes need per-tile height from the survey. | — |
| D8 | Traffic lights use a static painted atlas face (no lit lenses). | Lighting all three lenses at once would look wrong; animating them needs script. | — |
| D9 | `Intersection_T` uses 4 sections against the road budget of 3 (it includes a sidewalk). **Flagged, not hidden.** The budget stays a hypothesis. | It needs asphalt + paint + paver + curb concrete. | if the FPS test shows road draw calls matter |
| D10 | Preview renders found a tooling bug: `os.path.basename` did not split `\` game paths on Linux, so previews were untextured (including Tower A's earlier renders). Fixed in the preview scripts only; no asset changed. | — | — |
| D11 | Combined `Street_*` tiles are the default for districts; the separate road, sidewalk and corner pieces stay for odd layouts. | perf batch-1 M1 (entities and draw calls). | — |
| D12 | Kit materials use procedural stages for information-free maps; **Tower A's rvmats are not changed.** | Rule 1 vs perf M5. Tower A is the test reference. | after Tower A is validated |
| D13 | Manhole is Roadway-only (no Geometry/Fire), category `flat`. | A 2 cm collision bump snags wheels; a decal needs no collision. | — |
| D14 | Road-tile collision skirt = one convex box under the whole tile (not per part). | Security M1 fix without blowing the component budget. | — |
| D15 | Road paint uses `AlphaTest32`, the verified flag from Bohemia's Test_Clutter rvmat; `AlphaTest64` (suggested by perf) is not used because it is unverified. | Never guess names. | if in-game edges look too hard |
| D16 | `Decal_*` objects may only be placed flush (<= 5 cm) in front of a surface that has Geometry, facing away from it. The Batch 5 layout generator enforces this; until then no decal goes into `placement/`. | security batch-2 L1: single-sided, render-only quads used free-standing give one-sided concealment. | — |
| D17 | Graffiti lettering is auto-fitted (shrink until it fits 84 % of the tile, centred) and is excluded from the noise alpha erosion. | security batch-2 I2: "NO CURFEW" was clipped. | — |
| D18 | Brick and concrete-panel `_as`/`_smdi` are procedural constants (AO folded into `_co`); concpanel normal map is half size; window atlas is 1024; dirt decal is 512 x 1024; crack lines are >= 2 px; graffiti noise mask is lower frequency. | perf batch-2 M1, M2.3, L1, L4, L5. | — |
| D19 | Decals get per-type wall offsets (`DECAL_OFFSET`: dirt 1.5 cm, cracks 2.0 cm, graffiti 2.5 cm) and density caps (`DECAL_CAPS`: 6 per 12 m tile, 40 per block, hypothesis), enforced by the Batch 5 layout generator. | perf batch-2 M2.2 / M3 (coplanar z-fight, entity and draw-call count). | tune caps after the FPS protocol |
| D20 | Brick trim sheet is mapped at 3.44 m per U tile (`MATERIALS["brick"]["sheet_m"]`): 16 bricks of 21.5 cm across. | perf batch-2 L3: comment and texture did not agree. | — |
| D21 | Graffiti stays 4 textures swapped via `hiddenSelectionsTextures` on one P3D (not a 2 x 2 atlas with 4 UV-offset models). Same VRAM; the batching gain is unmeasured and would add 4 P3Ds. | perf batch-2 M3 option, not taken. | if the FPS test shows decal draw calls matter |
| D22 | Large-area facade grime via a Super-shader macro (`_mc`, Stage3) map is **not** done: no vanilla rvmat with a Stage3 `_mc` was verified from this container. Dirt decals stay hand-placed accents under the D19 caps. Dirt Res2 stays alpha-blended (no second rvmat). | perf batch-2 M2.1 / L6; never guess. | see PENDING_VERIFICATION B3 |
| D23 | `sky_windows_lit` and `sky_windows` are never combined in one LOD: lit/unlit is chosen per module variant (or per instance via `hiddenSelectionsMaterials`), never switched from script. | perf batch-2 L2. | — |
