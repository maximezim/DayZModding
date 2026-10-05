# City buildings wave 2 + city layout generator (D57): perf, security and QA gates

Scope: wave 2 archetypes in `assets/blender/build_city.py` (Villa, ShopRow, Supermarket, Clinic,
FireStation, Workshop, GarageBlock, Kiosk, Shed + variants VillaBrick, VillaStone, ShopRowMarket,
ShopRowNews, ShopRowHardware, SupermarketSmall, WorkshopBrick, KioskCafe, ShedBrick) x Intact /
Damaged / Ruined = 54 P3Ds, plus 4 rubble lots (`City_RubbleLot_A..D`) = **58 new P3Ds** in pbo
`sky_city` (100 city models in total). City layout generator `placement/city_fill.py` +
`sky_layout.py place_city()`, template `placement/city_template.yaml`. Static gates only - nothing ran
in DayZ.

## Perf - PASS (budgets are hypotheses, D56/D57)

Res0/Res1/Res2/Res3 triangles, Geometry triangles, Fire triangles:

| Model | Res chain | Geo tris | Fire tris |
|---|---|---|---|
| clinic_damaged | 10886/3946/524/10 | 1140 | 2496 |
| clinic_intact | 9628/3412/160/10 | 1140 | 2436 |
| clinic_ruined | 6714/3442/256/38 | 1304 | 2168 |
| firestation_damaged | 10198/3360/308/10 | 1068 | 2376 |
| firestation_intact | 10596/3262/196/10 | 1068 | 2340 |
| firestation_ruined | 8640/3512/292/38 | 1184 | 2468 |
| garageblock_damaged | 3900/1036/180/10 | 288 | 804 |
| garageblock_intact | 3924/1008/152/10 | 288 | 804 |
| garageblock_ruined | 3834/1248/240/38 | 392 | 980 |
| kiosk_damaged | 760/490/104/10 | 204 | 384 |
| kiosk_intact | 716/444/104/10 | 204 | 348 |
| kiosk_ruined | 702/504/152/38 | 268 | 352 |
| kioskcafe_damaged | 792/464/132/10 | 204 | 300 |
| kioskcafe_intact | 764/444/104/10 | 204 | 348 |
| kioskcafe_ruined | 704/504/152/38 | 268 | 352 |
| rubblelot_a | 596/296/296/22 | 296 | 296 |
| rubblelot_b | 580/352/352/32 | 352 | 352 |
| rubblelot_c | 596/296/296/22 | 296 | 296 |
| rubblelot_d | 680/380/380/32 | 380 | 380 |
| shed_damaged | 1176/466/132/10 | 216 | 360 |
| shed_intact | 1068/438/104/10 | 216 | 360 |
| shed_ruined | 1062/522/152/38 | 280 | 412 |
| shedbrick_damaged | 1024/480/104/10 | 216 | 372 |
| shedbrick_intact | 996/438/104/10 | 216 | 360 |
| shedbrick_ruined | 956/474/152/38 | 280 | 364 |
| shoprow_damaged | 8922/3198/460/10 | 1296 | 2448 |
| shoprow_intact | 9346/3162/292/10 | 1296 | 2448 |
| shoprow_ruined | 7340/3070/388/38 | 1436 | 2408 |
| shoprowhardware_damaged | 9642/3348/516/10 | 1296 | 2532 |
| shoprowhardware_intact | 9850/3162/292/10 | 1296 | 2448 |
| shoprowhardware_ruined | 7822/3166/388/38 | 1436 | 2516 |
| shoprowmarket_damaged | 9442/3292/460/10 | 1296 | 2532 |
| shoprowmarket_intact | 9850/3162/292/10 | 1296 | 2448 |
| shoprowmarket_ruined | 7798/3166/388/38 | 1436 | 2516 |
| shoprownews_damaged | 9190/3226/488/10 | 1296 | 2448 |
| shoprownews_intact | 9514/3162/292/10 | 1296 | 2448 |
| shoprownews_ruined | 7658/3160/388/38 | 1436 | 2480 |
| supermarket_damaged | 12012/1888/160/10 | 396 | 1260 |
| supermarket_intact | 11918/1626/104/10 | 396 | 1224 |
| supermarket_ruined | 11320/1904/180/38 | 476 | 1388 |
| supermarketsmall_damaged | 5492/1468/104/10 | 324 | 984 |
| supermarketsmall_intact | 5650/1354/104/10 | 324 | 1020 |
| supermarketsmall_ruined | 5308/1656/180/38 | 416 | 1244 |
| villa_damaged | 6008/2334/232/16 | 652 | 1660 |
| villa_intact | 6958/2392/232/16 | 652 | 1648 |
| villa_ruined | 4778/2530/296/40 | 760 | 1696 |
| villabrick_damaged | 5692/2690/288/16 | 652 | 1780 |
| villabrick_intact | 6214/2392/232/16 | 652 | 1648 |
| villabrick_ruined | 4452/2592/296/40 | 760 | 1732 |
| villastone_damaged | 6008/2602/344/16 | 652 | 1636 |
| villastone_intact | 6462/2392/232/16 | 652 | 1648 |
| villastone_ruined | 4612/2544/296/40 | 760 | 1696 |
| workshop_damaged | 3290/818/144/10 | 276 | 792 |
| workshop_intact | 3314/794/116/10 | 276 | 816 |
| workshop_ruined | 3162/930/204/38 | 368 | 884 |
| workshopbrick_damaged | 2742/838/116/10 | 276 | 624 |
| workshopbrick_intact | 2866/842/116/10 | 276 | 648 |
| workshopbrick_ruined | 2798/1026/204/38 | 368 | 776 |

- `check_assets`: 144 checked, 0 fail, 0 over budget. Wave 2 models are all lighter than the wave 1
  blocks (largest: Supermarket 12k Res0, Clinic / FireStation ~11k); kiosks, sheds and lots < 1.2k.
  Res3 = one block + roof (10 tris; pitched villas 16; ruins 38-40).
- Pitched roofs (villas): eaves overhang in the Res LODs only; collision stays inside the footprint.
- Layout: the 192 m template places 117 buildings + 145 tiles + 40 lights. **Spawner target**
  (objectSpawnersArr) keeps `ENTITY_CAP` (800 per district incl. loot) and refuses a city over it;
  the **terrain target** writes `city_objects.csv` for a Terrain Builder import and is not capped
  (static terrain objects cost no script / network sync; format = P11, unverified).
- Watch items for FPS_PROTOCOL: object count per streamed cell in a dense downtown (many small
  buildings), night lights (2 per intact building, client only), rubble-lot Roadway faces.

## Security - PASS

- No new script logic: wave 2 adds models, configs, CE entries and generated light classes
  (client-only `SKY_LitBuilding`, D55). No RPC, no server state, no client input.
- Collision: Geometry inside every footprint (`test_city`, lots inside 12 x 12); roofs unreachable
  (no stair to roof, pitched roofs have no ladder); roller shutters are closed solids (GarageBlock open
  bays are deliberate openings with a solid back wall); signs, awnings, eaves have no Geometry.
- Ruins: the collapse avoids the entrance (first open bay when there is no door) and the stair;
  rubble is collidable and walkable (Roadway), clamped inside the walls; sealed rooms get no loot.
- Loot: points on floors, reachable (flood fill per level), CE usages from vanilla
  cfglimitsdefinition (Town, Village, Industrial, Medic, Firefighter); rubble lots carry none.
- Layout generator: offline Python, deterministic seed, no runtime code; it never edits vanilla
  `mpmissions` (writes snippets under `placement/out_city/`).

## QA - PASS

- `test_city` PASS (100): LOD set, watertight parts, footprint, door rig + inward swing, ruins without
  door / glass, stairs, walkability per level, loot reachable, rubble lots (LODs, inside lot, Roadway).
- Found and fixed by the tests: ruined kiosks / sheds threw rubble outside the walls (radii clamped,
  one smaller pile under 30 m2); ShopRow flats unreachable (lounge set turned to leave 0.9 m passages);
  rubble lots lost their mounds to the ruin cut and had no Res3; pitched-roof eaves left the footprint
  in Geometry; kiosks flooded the fill (65 in one city -> per-zone `small_cap`).
- `test_sky_layout` 52 checks, 0 failed: template runs, deterministic, > 100 buildings, all inside their
  blocks, no overlaps, fronts face the street, frontline more ruined than residential, small_cap kept,
  spawner cap enforced, terrain run reports the cap as not applied, a building across a street and a
  too-steep slope both fail.
- `test_kit`, `test_towera`, `gen_configs` / `gen_manifest` / `gen_economy` / `city_progress --check`
  up to date, `Invoke-SelfTest` passed, `enscript_xref` OK.
- Renders: `reviews/img/city2_<archetype>_states.png`, `city2_*_interior.png`, `city2_rubblelot_lots.png`,
  `city2_sheet_a.png` / `_b.png`, generated quarter `district_aerial.png`, `district_street_a.png`,
  `district_street_b.png`, `district_night.png`. In-game rows: TESTING section 22 (CD-01..CD-06).
