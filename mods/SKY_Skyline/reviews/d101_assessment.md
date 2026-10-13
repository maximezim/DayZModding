# D101 assessment of the remaining box-like assets, and the soft-furnishing batch

After D96-D100 (city buildings, wrecks, doors, balconies, lobby) the remaining candidates were ranked by Res0 triangles
from the build stats (99 kit models with per-model stats) and checked on eye-height PBR contact sheets.

## Ranking (lowest Res0 first, excluding decals and road tiles, which are flat by design)

| Group | Models (Res0 tris) | Verdict |
|---|---|---|
| Interior kit props (spawned on every Tower A floor by FURNISH) | Bed 154, Desk 158, Sofa 190, ReceptionDesk 230, ServerRack 238, Cubicle 242, ExtinguisherCabinet 262, Locker 344, Kitchenette 508 | Had a D76 close-up pass; textures carry the hard surfaces (rack, vending, locker, kitchenette read well). **Soft furnishings still read as wedges** (sofa cushions / arms, bed mattress / duvet / pillow), and the cubicle has no chair. -> **D101** |
| Street props | PhoneBooth 142, Barrier_Concrete 172, Planter 188, Dumpster 412, StreetLight 426, TrafficLight 442, TrashBin 584, Billboard 562, BusStop 580, AdColumn 664 | Hold up at eye height after D66-D96 (texture detail, AO); TrafficLight housing and Planter are the weakest. Candidates for a later pass. |
| Vegetation | Veg_Bush 32, Veg_TreeDead 104, Veg_Birch 160 | Card-based by design (alpha foliage); D96 gave trunks lofted bark. A tree pass (more cards, branch lofts) is a separate, larger batch. |
| Road / decal / flat pieces | Decals 2, Manhole 12, road tiles 16-166 | Flat by design; detail is in the textures. No action. |

![Interior props](img/d101_assess_interior.png)
![Street props](img/d101_assess_street.png)

**Picked: D101 soft furnishings** (highest exposure: every flat and office floor, seen at arm's length).

## D101 changes (`assets/blender/build_props.py`)

- `soft()`: lofted rounded-rectangle shape (superellipse section, puffy ends, optional sag), smoothed by the P3D writer.
- Sofa: rolled arms, back frame, sat-in seat cushions and plump back cushions; the mid LOD keeps the soft shapes.
- Bed: soft mattress, a duvet draped past the mattress sides, a rolled turn-back, a dented pillow.
- Cubicle: a swivel chair (5-star base, gas column, padded seat and back, armrests), render only, inside its footprint.
- Collision unchanged except the sofa back, which now covers the deeper back cushions (sec M1: a head pocket).

![Before](img/d101_props_before.png)
![After](img/d101_props_after.png)

## Gates and review

| Gate / review | Result |
|---|---|
| test_quality, test_conceal, test_slits, test_kit (Sofa, Bed, Cubicle) | PASS (first runs: sofa Res1 lofts on the old boxes, 11 z-fight layers -> separate shapes) |
| check_assets | Sofa 730 / Bed 646 Res0 over the 600 interior_small budget (hypothesis, D96 quality first); Cubicle PASS |
| review M1 (sofa back pocket 0.19 m in front of the back collision) | back collision moved forward (y 0.08) |
| review L1 (over budget) | loft resolution cut (sofa 10, bed 16 sides) |
| review L2 (pillow 0.14 m over the mattress collision) | unchanged from before; no head fits |
