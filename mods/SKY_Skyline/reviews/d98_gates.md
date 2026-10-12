# D98 interior doors: gates, reviews, before / after

ROADMAP item "interior doors (openings have no leaves)". Decision D98, test rows TESTING section 60, parameters P74 / P75.

## What was built

Every partition doorway 0.85-1.05 m wide in an Intact or Damaged city building gets a hinged door leaf with the front
door's rig (selection `door_iNN` in Res0 / Res1 / Geometry / Fire / View as one component, axis and action memory
points, vanilla `Doors` class, indestructible DamageSystem zone, model.cfg rotation). `build_city.interior_doors` picks
the hinge and swing side whose sweep is clear of walls, furniture, stairs, other doors' sweeps and the floor in front
of other doorways, with 0.7 m left to walk past the open leaf; otherwise the doorway stays open. None in ruins, about
a third missing in damaged buildings, at most 48 per model. Fire / View leaves fill the whole opening; door stops on
the closing side close the render gaps; loot points stay out of the sweeps. The list is written to
`assets/build_doors_city.json` (lock for parallel shards) and read by skyspec / gen_configs.

**727 doors in 177 models** (largest below; ruins and buildings without room doorways have none).

| Model | Doors |
|---|---|
| City_Hospital_Intact | 48 |
| City_Hospital_Damaged | 48 |
| City_CourtyardBlock_Intact | 48 |
| City_CourtyardBlock_Damaged | 48 |
| City_CourtyardBlockBrick_Intact | 48 |
| City_CourtyardBlockBrick_Damaged | 46 |

## Before / after

![Before](img/d98_aptblock_before.png)
Before: AptBlock flat, empty doorways.

![After](img/d98_aptblock_after.png)
After: oak panel doors with glazed tops and handles; the stair hall opening stays open (no clear swing side).

![School](img/d98_school_after.png)
School: class doors; the 2 m opening stays open (not a room door).

## Gates (all Intact / Damaged city models rebuilt)

| Gate | Result |
|---|---|
| `test_quality.py` (per model, Intact + Damaged city) | 0 findings on 120 models |
| `test_city.py` (door rig: selections, one component, swing toward the action point, model == JSON list) | PASS (191 buildings) |
| `test_conceal.py --city`, `test_slits.py --city` | PASS (273 models each) |
| `test_ruin_cuts.py` | PASS (120 models) |
| `check_assets.py` | 289 checked, 0 fail, 50 over the old budgets (unchanged count) |
| `check_p3d_sync.py` | PASS (396 models byte-identical) |
| `gen_configs.py --check`, `gen_manifest.py --check`, texture refs | up to date, PASS |

## Reviews

| Review | Finding | Fix |
|---|---|---|
| perf M1 | 48 door bones could split shared Res0 sections into more draw calls after binarizing | P74 (measure in DayZDiag; lower `IDOOR_CAP` if so) |
| perf M2 | Geometry / Fire / View components grow by one per door | measured by check_assets: no model over its component budget |
| perf M3 / sec info | cap 48 not sourced from vanilla | P74 |
| perf L6 / sec M1 | doors never checked against each other's sweep, other doorways or corridor width | placed sweeps and the floor in front of every doorway are obstacles; 0.7 m passage past the open leaf |
| perf L7 / sec M2 | JSON never pruned; parallel shards could lose entries (a leaf without a Doors class would seal a room) | pruned to existing models, written under a lock; test_city + gen_configs --check gate it |
| sec M3 | infected cannot open doors; rooms may become navmesh islands | P75, TESTING ID-05 (fix: doors off loot rooms or spawn open) |
| sec M4 | swing direction depends on the unverified P1 sign | TESTING ID-01 |
| sec L1 | 1 cm jamb / 3 cm head gaps (peek, lucky shots) | Fire / View leaves fill the opening; render door stops |
| sec L2 | 0.75 m doorways lose clear width to the leaf | minimum 0.85 m |
| sec L3 | loot points inside door sweeps | excluded |
| perf L4 / L5 / L8 | kennel door scan, DamageSystem size, no leaves in Res2+ | accepted (throttled; config size only; interiors not visible at that range) |
