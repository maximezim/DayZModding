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
