# DayZ ambiance pass (D59): perf, security and QA gates

Scope: weathered texture set + tileable wall sheets, `decal_grime` / `vegetation` materials, per-building
dressing in `build_city.py` (all 155 city models rebuilt), vegetation kit (`Veg_Weeds`, `Veg_Bush`,
`Veg_Birch`, `Veg_TreeDead`), terrain-aware fill, overgrowth scatter, sliver guard, clutter cutters
(`placement/`). Static gates only - nothing ran in DayZ.

## Perf - PASS (hypotheses, FPS_PROTOCOL to confirm)

- `check_assets`: 203 checked, 0 fail, 0 over budget. Dressing cost is small: AptBlock intact Res0
  27972 -> 28392 (+1.5 %), Res1 8424 -> 8460; Rowhouse ruined 4766 -> 5024; courtyard block 73554 -> 74752.
  Res2 / Res3 unchanged (dressing is Res0 / Res1 only; vegetation cards are alpha-TESTED, no blended
  alpha beyond Res1 - the far-LOD blend check passes).
- Sections: + `decal_grime` and `vegetation` per building; damaged shops and the hospital hit 25 > 24 in the
  first build -> downpipes / window bars moved to the metal sheet they already use; all within 24 now.
  Walls moved to one tileable sheet per skin (base trim sheets stay for sills / string courses), so a
  masonry building uses one more texture than before at most.
- Blended overlays: rising damp + run-off are 2 quads per facade side (+ one per streaked window); the
  overdraw is the main client cost to watch in CV-06 (drop them from Res1 first if it shows).
- Vegetation kit: Res0 32-56 tris, 1 section, Res3 a single card; weeds / bushes have no Geometry.
  The city template places 50 plants (27 weeds, 17 bushes, 6 trees); cap per block per zone.
- Spawner sites: clutter cutters are entities: the district template is now 323 + 64 cutters = 387
  entities + 226 loot = 613 (cap 800); the Tower A slice 8 + 16 = 24.

## Security - PASS

- No script changes. No new collision anyone can climb: grime / ivy / weeds / pipes / bars / saplings
  are visual only; tree trunks collide (0.13-0.16 m), crowns are cards; weeds and bushes walk-through.
- Vegetation never inside a building (>= 1 m clear, weeds 0.3 m) except perimeter-block yards (open sky).
- Clutter cutters are vanilla objects (`ClutterCutter6x6`, verified class) placed at ground level under
  the footprint only; the layout still refuses a run over ENTITY_CAP.

## QA - PASS

- `test_city` PASS (155: + vegetation pieces - LODs, cards inside the footprint, weeds / bushes without
  collision, watertight trunks inside 0.5 m). `test_kit` PASS (195), `test_towera` PASS.
- `test_sky_layout` 0 failed; new: a 3 m hollow in a filled block is routed around (run passes, lots
  reported, no building over it), plants follow the surveyed ground, spawner city gets cutters under
  the floors, spawner tower gets 16 cutters at ground level; rubble lots counted as ruined.
- Found and fixed: trim-sheet stretching on tall faces (black church gable, plank streaks on stone and
  stucco) -> tileable wall sheets; ivy cards with straight edges -> ragged ivy outline; tree crowns
  wider than their footprint -> 3.2 m footprint, narrower crowns; too little greenery (12 plants) ->
  finer grid for weeds / bushes and wall-hugging weeds; frontline ruin share test skewed by lots
  recorded as damaged -> lots are ruined.
- `gen_configs` / `gen_manifest` / `gen_economy` / `city_progress --check` up to date.
- Renders (`--dayz`: overcast sky, grass stand-in for the terrain): `reviews/img/d59_city_*.png`,
  `d59_street_*.png`, `d59_civic_walls.png`, `d59_rubble_lots.png`, `d59_vegetation_atlas.png`.
  In-game rows: TESTING section 24 (CV-01..CV-06), P12.
