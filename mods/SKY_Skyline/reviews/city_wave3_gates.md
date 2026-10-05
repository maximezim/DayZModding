# City wave 3, tall towers, landmark blocks (D58): perf, security and QA gates

Scope: the rest of `CITY_PLAN.md`. Wave 3 procedural archetypes in `assets/blender/build_city.py`
(WarehouseLarge, CourtyardBlock + Brick, GasStation, Cafe + Brick, Bank, DepartmentStore, Hospital, School,
TownHall, Church, PostOffice, FactoryHall, ParkingGarage, Substation) x Intact / Damaged / Ruined = 48 P3Ds,
kit pieces WaterTower and MetroEntrance A / B (3), tall tower cores T15 / T23 / T33 (`sky_towera`, 3) and
the `Roof_Crown` module (`sky_floors`, 1): **55 new P3Ds**. CITY_PLAN: 156 / 156 unique models.
Layout: `streets.closed`, zone `once` lists, forecourt origins, `core:` per tower. Static gates only -
nothing ran in DayZ.

## Perf - PASS (budgets are hypotheses, D58)

Res0/Res1/Res2/Res3 triangles, budget category, Geometry triangles, Fire triangles:

| Model | Res chain | Category | Geo tris | Fire tris |
|---|---|---|---|---|
| WarehouseLarge_Intact | 7772/1696/140/10 | city_large | 420 | 2148 |
| WarehouseLarge_Damaged | 7506/1788/196/10 | city_large | 420 | 2124 |
| WarehouseLarge_Ruined | 6110/1694/216/38 | city_large | 524 | 1880 |
| CourtyardBlock_Intact | 73554/22532/608/10 | city_large | 6852 | 14256 |
| CourtyardBlock_Damaged | 65880/22902/1840/10 | city_large | 6852 | 14484 |
| CourtyardBlock_Ruined | 49450/21752/648/38 | city_large | 6920 | 13592 |
| CourtyardBlockBrick_Intact | 53776/18060/508/10 | city_large | 5508 | 11448 |
| CourtyardBlockBrick_Damaged | 48992/18524/1600/10 | city_large | 5508 | 11664 |
| CourtyardBlockBrick_Ruined | 36488/17286/548/38 | city_large | 5576 | 10808 |
| GasStation_Intact | 3240/1306/200/10 | city | 432 | 1068 |
| GasStation_Damaged | 3234/1342/200/10 | city | 432 | 1044 |
| GasStation_Ruined | 2982/1556/288/38 | city | 536 | 1232 |
| Cafe_Intact | 2826/1226/140/10 | city | 480 | 1140 |
| Cafe_Damaged | 3028/1388/168/10 | city | 480 | 1224 |
| Cafe_Ruined | 2332/1302/216/38 | city | 572 | 1220 |
| CafeBrick_Intact | 2706/1226/140/10 | city | 480 | 1140 |
| CafeBrick_Damaged | 2812/1288/168/10 | city | 480 | 1104 |
| CafeBrick_Ruined | 2254/1302/216/38 | city | 572 | 1220 |
| Bank_Intact | 13396/4542/226/10 | city | 1668 | 3300 |
| Bank_Damaged | 14802/5244/590/10 | city | 1668 | 3408 |
| Bank_Ruined | 11728/5010/322/38 | city | 1856 | 3344 |
| DepartmentStore_Intact | 54842/7014/288/10 | city_large | 2316 | 5652 |
| DepartmentStore_Damaged | 54750/7562/344/10 | city_large | 2316 | 5724 |
| DepartmentStore_Ruined | 46252/7300/372/38 | city_large | 2456 | 5324 |
| Hospital_Intact | 50702/16398/328/10 | city_large | 6096 | 11664 |
| Hospital_Damaged | 55394/19074/1812/10 | city_large | 6096 | 11856 |
| Hospital_Ruined | 40366/17532/424/38 | city_large | 6176 | 10832 |
| School_Intact | 17302/6728/216/10 | city | 2412 | 4764 |
| School_Damaged | 19162/7706/692/10 | city | 2412 | 4896 |
| School_Ruined | 14538/7282/312/38 | city | 2600 | 4652 |
| TownHall_Intact | 19084/6226/254/10 | city | 2272 | 4336 |
| TownHall_Damaged | 20956/7174/758/10 | city | 2272 | 4360 |
| TownHall_Ruined | 16898/6912/350/38 | city | 2472 | 4452 |
| Church_Intact | 4880/2234/350/32 | city | 814 | 1570 |
| Church_Damaged | 4694/2424/378/32 | city | 814 | 1606 |
| Church_Ruined | 3578/2150/342/56 | city | 822 | 1422 |
| PostOffice_Intact | 8974/2730/160/10 | city | 828 | 2052 |
| PostOffice_Damaged | 9030/2882/188/10 | city | 828 | 2076 |
| PostOffice_Ruined | 6678/2690/256/38 | city | 956 | 1808 |
| FactoryHall_Intact | 7184/2328/416/42 | city_large | 756 | 1692 |
| FactoryHall_Damaged | 6730/2678/416/42 | city_large | 768 | 1824 |
| FactoryHall_Ruined | 5612/2426/396/70 | city_large | 764 | 1640 |
| ParkingGarage_Intact | 10506/5030/380/10 | city_large | 4908 | 5772 |
| ParkingGarage_Damaged | 10338/4990/436/10 | city_large | 4812 | 5676 |
| ParkingGarage_Ruined | 10510/5088/464/38 | city_large | 4988 | 5852 |
| Substation_Intact | 3084/608/312/30 | city | 408 | 360 |
| Substation_Damaged | 3040/632/312/30 | city | 420 | 360 |
| Substation_Ruined | 3018/588/352/40 | city | 484 | 400 |
| WaterTower | 1686/262/262/62 | city | 262 | 262 |
| MetroEntrance_A | 554/194/88/10 | city | 184 | 172 |
| MetroEntrance_B | 208/160/112/12 | city | 204 | 204 |
| TowerA_Core15 / 23 / 33 | 7198 / 10510 / 14650 Res0, Res1 1866 / 2682 / 3702, Res2 252 / 348 / 468, Res3 10 | core_tall | 2172 / 3132 / 4332 | same |
| Roof_Crown | 884/536/184/22, shadow 96 | roof | 144 | 192 |

- `check_assets`: 199 checked, 0 fail, 0 over budget. New category `city_large` (footprint >= 600 m2:
  hospital, department store, courtyard blocks, factory hall, large warehouse) - res0 80k / res1 24k /
  640 Geometry parts; the courtyard block (4500 m2 floor area) is the largest building and sets it.
  Per m2 of floor it is cheaper than the wave-1 blocks (courtyard 16 Res0 tris / m2, AptBlock 26).
- Found and fixed in the gate: school classrooms had one collision box per desk (333 Geometry parts) ->
  one bench desk per row; town hall offices widened (244 -> under 240 parts); crown roof fins and
  pylons out of Res2 / Shadow (res2 496 -> 184, shadow 224 -> 96).
- Tall cores scale with their stops (one cab and two door leaves per stop); Res2 / Res3 stay a shell.
  A 35-storey tower is 37 objects (lobby, 33 floors, roof, core): heavy for the spawner - towers this
  tall belong in a terrain build or one per server.
- Watch items for FPS_PROTOCOL: courtyard and hospital interiors (Res1 17-23k), parking decks (wrecks +
  ramps), sawtooth roof segments, church tower spire (visible from far: Res3 kept).

## Security - PASS

- New script code: only generated script classes `Land_SKY_TowerA_Core15/23/33 extends
  Land_SKY_TowerA_Core` (no logic). The elevator keeps its server-side validation (the client sends a
  direction, never a floor; stops come from config); more stops only lengthen the travel time
  (`travel_ms_per_stop`). `enscript_xref` OK (14 files).
- Collision: Geometry inside every footprint (forecourts included; eaves, tower face, roof overhangs are
  visual only); no route onto roofs, towers, cupola, canopy, water-tower tank (ladder is visual), crown
  fins / spire; substation and metro entrances are closed (no loot, no interior); parking openings and
  atrium edges have rails.
- Ruins: double-corridor plans collapse only in front of the corridor (every room behind stays reachable);
  rooms sealed by rubble get no loot.
- Loot: CE usages from the vanilla cfglimitsdefinition (Town, Office, Medic, School, Industrial,
  Village); none on substation / water tower / metro / lots; loot points never over a slab opening
  (atrium, ramp, yard).

## QA - PASS

- `test_city` PASS (151): every wave-3 archetype and state (LODs, watertight parts, footprint incl.
  forecourt, doors, stairs, walkability per level with slab openings excluded, loot reachable), the
  three kit pieces and the substations (not-enterable piece test).
- Found and fixed by the tests: parking garage too shallow for two stall rows + ramps (18 -> 24 m deep);
  hospital / bank ruins cut the corridor (collapse moved in front of it); town hall ground stair landing
  left a sealed 1.2 m2 pocket (ground storey 4.2 -> 4.0 m); department store ruin kept glass balustrades;
  water tower gallery and metro roof overhang left the footprint (visual-only now).
- Render review fixed: church tower face coplanar with the gable (black shading) -> tower face proud in
  the visual LODs; ruined factory roof teeth floating over the collapse -> teeth cut in 4 m segments.
- `test_towera` PASS: Tower A core plus every tall core (doors, cab, landings and the elevator memory
  points at every stop). `test_kit` PASS (191, incl. Roof_Crown). `test_sky_layout` 0 failed (new:
  T23 tower = 26 objects with Core23 + crown roof; floors must match the core; city template with closed
  street cells). `gen_configs` / `gen_manifest` / `gen_economy` / `city_progress --check` up to date,
  `Invoke-SelfTest` passed.
- Existing models: only the 51 sign-carrying wave 1 / 2 P3Ds changed (sign sheet 12 -> 20 bands remaps
  their sign UVs); their loot points are unchanged.
- Renders: `reviews/img/city3_<archetype>_states.png`, `city3_*_interior.png`, `city3_pieces.png`,
  `district3_*.png` (city template with landmark blocks), `towers_tall*.png`. In-game rows: TESTING
  section 23 (CW-01..CW-08).
