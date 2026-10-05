# Batch 1 (street kit) — perf-engineer gate

**GATE: PASS (static).** 0 High, 6 Medium, 12 Low. This is a condensed copy of the agent's report plus the actions taken.
There was no in-game measurement.

| ID | Finding | Action |
|---|---|---|
| M1 | A 12 m tile was 7 entities and 14 draw calls; the sidewalk corner was its own object. | **Fixed.** Added combined `Street_Straight`, `Street_Crossing` and `Street_Intersection` tiles (1 entity, 4 sections, new `road_combined` budget). Separate pieces remain for edge cases. Light density and an entity-count cap go into the layout generator in batch 5. |
| M2 | Roadmarks were alpha-blended decals, 6 mm offset, with overlapping layers. | **Fixed.** Alpha-test (`AlphaTest32`, verified flag), binary alpha with wear in RGB, 1.5 cm lift, lines split around crosswalks, and a 512 sheet tiling along U. |
| M3 | No Shadow Volume on any kit asset. | **Fixed.** Every raised prop gets a shadow LOD built from its closed collision solids. Flat tiles stay shadowless. `check_assets` and `test_kit` now require it for small and medium props. |
| M4 | 0.3 m road Geometry slabs may snag wheels at seams. | **Parameterised:** `ROAD_GEO_THICKNESS` (P8), pending test V1. |
| M5 | Textures carried information-free maps or had uneven texel density. | **Fixed for kit materials:** atlas, billboard, roadmark and foliage use procedural nohq/as/smdi stages. Rust is 1024, foliage 512, paver AO 1024. Tower A rvmats are deliberately untouched (rule 1). Open: rust is stretched along tall poles (Low, visual). |
| M6 | LOD pops on the planter, bus stop and wrecks. | **Fixed.** The planter keeps a card at Res2. The bus stop Res2 is roof + posts + an opaque back pane. Wreck Res2 bodies reach the ground. |
| L1 | Intersection_T was over its section budget. | **Fixed:** the asset moved to `road_combined`. |
| L2 | Several Res1 LODs barely reduce. | Partly: Intersection Res1 drops the side crosswalks. The others stay (cheap; 3 Res LODs are required). |
| L3 | Hidden bottom caps on prisms. | Deferred (all far below budget). |
| L4 | Planter was 3 sections. | **Fixed:** soil now uses the concrete board band, so 2 sections. |
| L5 | Manhole had collision and a poor LOD chain. | **Fixed:** now a Roadway-only flat decal with no collision; Res2 is 2 tris (`flat` category). |
| L6 | The lamp rvmat uses the full Super shader. | Deferred; check a vanilla lamp rvmat on P: (TESTING). |
| L7 | Light memory points are unused. | Noted: a future dynamic-light system must cap the number of lights (it would be High otherwise). |
| L11 | Manifest hygiene. | **Fixed:** sections C and F updated. |
| L12 | Smooth shading on hard edges. | To verify in Object Builder (MANUAL_STEPS A). |

Per-tile cost for a typical street tile:

| | Entities | Res0 sections | Alpha-blended draws |
|---|---|---|---|
| Before | 7 | 14 | 1 |
| After (combined tile + 1 light + bin + planter) | 4 | about 9 | 0 |
