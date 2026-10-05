# City buildings wave 1 (D56): perf, security and QA gates

Scope: procedural generator `assets/blender/build_city.py`, 14 archetypes (Rowhouse, RowhouseRender,
RowhousePanel, AptBlock, AptBlockTall, AptBlockBrick, CornerShop, CornerPharmacy, CornerHardware,
OfficeMid, OfficeTall, Warehouse, WarehouseSmall, Police) x Intact / Damaged / Ruined = 42 P3Ds in
pbo `sky_city`; catalog / estimate / progress `CITY_PLAN.md`. Static gates only - nothing ran in DayZ.

## Perf - PASS (budgets are hypotheses, D56)

Res chain Res0/Res1/Res2/Res3 triangles, budget category, Res0 sections, Geometry parts, Fire triangles:

| Model | Res chain | Category | Sections | Geo parts | Fire tris |
|---|---|---|---|---|---|
| Rowhouse_Intact | 5906/2346/236/10 | city | 14 | 69 | 1704 |
| Rowhouse_Damaged | 5326/2264/348/10 | city | 19 | 69 | 1644 |
| Rowhouse_Ruined | 4766/2478/332/38 | city | 19 | 79 | 1904 |
| AptBlock_Intact | 27972/8424/348/10 | city | 15 | 182 | 5352 |
| AptBlock_Damaged | 25794/8930/712/10 | city | 20 | 182 | 5604 |
| AptBlock_Ruined | 20042/8392/444/38 | city | 20 | 197 | 5048 |
| CornerShop_Intact | 10228/3138/236/10 | city | 18 | 81 | 2400 |
| CornerShop_Damaged | 9822/3470/348/10 | city | 22 | 81 | 2568 |
| CornerShop_Ruined | 7526/3104/332/38 | city | 22 | 91 | 2288 |
| OfficeMid_Intact | 20850/6664/384/10 | city | 16 | 208 | 5676 |
| OfficeMid_Damaged | 21672/7620/552/10 | city | 21 | 208 | 5844 |
| OfficeMid_Ruined | 15476/7428/480/38 | city | 21 | 217 | 5012 |
| Warehouse_Intact | 5400/1246/128/10 | city | 12 | 32 | 1524 |
| Warehouse_Damaged | 5170/1334/128/10 | city | 14 | 32 | 1572 |
| Warehouse_Ruined | 4410/1340/204/38 | city | 15 | 36 | 1448 |
| Police_Intact | 9590/3534/160/10 | city | 16 | 85 | 2364 |
| Police_Damaged | 10668/4074/440/10 | city | 21 | 85 | 2484 |
| Police_Ruined | 7898/4014/256/38 | city | 20 | 95 | 2528 |
| RowhouseRender_Intact | 8414/3070/292/10 | city | 15 | 89 | 2232 |
| RowhouseRender_Damaged | 7892/3154/516/10 | city | 20 | 89 | 2280 |
| RowhouseRender_Ruined | 6192/3010/388/38 | city | 20 | 99 | 2288 |
| RowhousePanel_Intact | 4170/1622/180/10 | city | 15 | 49 | 1176 |
| RowhousePanel_Damaged | 4120/1708/320/10 | city | 20 | 49 | 1212 |
| RowhousePanel_Ruined | 3400/1706/276/38 | city | 19 | 59 | 1328 |
| AptBlockTall_Intact | 45156/13374/516/10 | city_tall | 15 | 287 | 8484 |
| AptBlockTall_Damaged | 41808/14046/1188/10 | city_tall | 20 | 287 | 8724 |
| AptBlockTall_Ruined | 33078/13590/612/38 | city_tall | 20 | 303 | 8156 |
| AptBlockBrick_Intact | 19568/6774/292/10 | city | 14 | 147 | 4308 |
| AptBlockBrick_Damaged | 17940/7066/656/10 | city | 19 | 147 | 4356 |
| AptBlockBrick_Ruined | 13454/6836/388/38 | city | 19 | 162 | 4196 |
| CornerPharmacy_Intact | 10228/3138/236/10 | city | 18 | 81 | 2400 |
| CornerPharmacy_Damaged | 9654/3282/348/10 | city | 22 | 81 | 2400 |
| CornerPharmacy_Ruined | 7584/3152/332/38 | city | 22 | 91 | 2348 |
| CornerHardware_Intact | 9556/3138/236/10 | city | 17 | 81 | 2400 |
| CornerHardware_Damaged | 9402/3392/404/10 | city | 21 | 81 | 2484 |
| CornerHardware_Ruined | 7818/3440/332/38 | city | 21 | 91 | 2600 |
| OfficeTall_Intact | 31620/9988/552/10 | city_tall | 16 | 316 | 8556 |
| OfficeTall_Damaged | 33442/11896/916/10 | city_tall | 21 | 316 | 8940 |
| OfficeTall_Ruined | 24314/11472/648/38 | city_tall | 21 | 325 | 7892 |
| WarehouseSmall_Intact | 3808/962/116/10 | city | 12 | 28 | 1128 |
| WarehouseSmall_Damaged | 3674/1052/116/10 | city | 14 | 28 | 1188 |
| WarehouseSmall_Ruined | 3322/1058/204/38 | city | 15 | 32 | 1100 |
- `check_assets`: 86 checked, 0 fail, 0 over budget. Far LODs: Res2 = outer faces per side and level
  (opaque, glassfar for glazing), Res3 = one block + roof (10 tris; ruins 38, the collapse stays visible).
  No blended alpha beyond Res1 (decals, glass, foliage are Res0 / Res1 only).
- Found and fixed in the gate: View / Fire built per window bay (4 boxes per bay) -> merged window-run
  bands (sill band, head band, piers): ~35 % fewer Fire triangles (AptBlock 8.6k -> 5.4k).
  Tall variants (8-9 storeys) got their own budget category (`city_tall`) instead of raising `city`.
- Watch items for FPS_PROTOCOL: sections per building (14-22), Geometry parts on 8-9 storey blocks
  (~290-325), Res1 of tall blocks (13-14k: furniture boxes + interior faces; drop furniture from Res1
  first if the client cost shows), night lights 2 per intact building.

## Security - PASS

- No new script logic beyond generated light classes (client only, `SKY_LitBuilding`, D55): no RPC,
  no server state. Door behaviour = vanilla house doors (inward, lockpick like any house, D56).
- Collision: every building's Geometry stays inside its footprint (`test_city`), nothing below the
  foundation skirt; roofs have no access route (no stair to the roof, bulkheads are solid); awnings,
  canopies, signs, shutters, balconies rails have no Geometry (nothing to climb onto); broken windows
  keep their Geometry (no new climb-in routes); cell bars block movement, not bullets or sight.
- Ruins: collapse never removes the entrance or the stair (zone chosen away from both); the floor
  above the collapse ends at a jagged edge onto collidable rubble; rooms sealed by rubble get no loot.
- Loot: points only on floors, clear of solids, outside stair wells and collapse zones, and reachable
  from the entrance / stairs (flood fill per level). CE usages / categories from the vanilla
  cfglimitsdefinition (Town, Office, Industrial, Police, Medic).

## QA - PASS

- `test_city` PASS (42): LOD set, watertight parts, footprint, door rig + swing (orient -1, inward),
  ruins without door / glass, two flights per storey, walkability per level (0.1 m grid, 0.3 m player
  radius, doors open), loot reachable, `city_loot.json` fresh.
- Found and fixed by test_city: front doors swung outward (orient -> -1); a plant pot plugged the flat
  doors on mirrored plans and in front of the rowhouse door; a kitchen counter and an office shelf
  blocked doorways; the rowhouse back-room door straddled a wall junction (0.43 m clear). Fix:
  keep-clear zones (front door, every opening, stair exit, cell doors) that furniture may not enter.
- `test_kit` PASS (81 assets, now including the city kit), `test_towera` PASS, `gen_configs` /
  `gen_manifest` / `gen_economy` / `city_progress --check` up to date, `test_sky_layout` 0 failed,
  `Invoke-SelfTest` passed, `enscript_xref` OK (13 files), PowerShell parse of the edited scripts clean.
- Renders: `reviews/img/city_<archetype>.png` (3 states each), `city_street.png`,
  `city_street_night.png`, `city_interiors.png`. In-game rows: TESTING section 21 (CB-01..CB-10).
