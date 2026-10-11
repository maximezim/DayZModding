# D97 wreck bodies: gates, reviews, before / after

Next ROADMAP cloud item after D96 ("still box-like, next in line"): the two kit wrecks `Wreck_CityBus` and
`Wreck_GarbageTruck` (`assets/blender/build_vehicles.py`). Decision D97, test row TESTING QP-20.

## Before / after (eye height, PBR maps)

![Before](img/d97_wrecks_before.png)
Before: boxes with flat quads on them, wheels half inside the body, window panes floating on the sides, paint reading
as wood grain.

![After](img/d97_wrecks_after.png)
After: bus with a lofted crowned shell, the glazing band part of the shell with pillars and seals, wheels in half-round
wells, two-pane windscreen in rubber, destination box, quad headlamps, grille, rounded bumpers, wipers, mirrors, glazed
two-leaf doors on the kerb side (one leaf gone), cream over terracotta. Truck with a ZiL-like short-nose cab (bonnet,
wings, round headlamps, vertical-bar grille, raked windscreen, beacon), ribbed compactor body, chassis, twin rears.

![After, rear quarter](img/d97_wrecks_after_rear.png)
Rear quarter: slanted rear-loader hopper with the packer mouth (trash), lift rams, tail lamps, mudflaps; bus engine
louvres, rear window, rust runs on the skirt. (The detached shadows are the preview camera beyond the ground plane.)

## Numbers

| | Res0 | Res1 | Res2 | Res3 | Geometry (comps) | Fire / View |
|---|---|---|---|---|---|---|
| Wreck_CityBus before | 836 | 110 | 12 | 12 | 60 tris (5) | 60 / 12 |
| Wreck_CityBus after | 3,580 | 710 | 124 | 12 | 76 tris (5) | 76 / 28 |
| Wreck_GarbageTruck before | 1,090 | 254 | 36 | 12 | 108 tris | 108 / 36 |
| Wreck_GarbageTruck after | 4,134 | 576 | 200 | 56 | 188 tris (15) | 188 / 68 |

Budget `vehicle`: Res0 5,000, Res1 1,200, Res2 200, 16 components, 10 Res0 sections (5 / 6 used): within budget.

## Gates

| Gate | Result |
|---|---|
| `test_quality.py --only` both | PASS (first run: door-side pillars inside the door leaves, 4 z-fight layers -> skipped) |
| `test_conceal.py --only` both | PASS (first runs caught the fuel tank, battery box and inner twin tyres drawn without collision -> collision added) |
| `test_slits.py --only` both | PASS |
| `test_kit.py` (hull test) both | PASS (first run: 5 cm slit between the truck cab and the front-wheel collision -> cab collision down to 0.9 m) |
| `check_assets.py` | 289 checked, 0 fail, 50 over the old budgets (unchanged; the bus Res1 -> Res2 step warning fixed) |
| `check_p3d_sync.py` | PASS (10 builders, 396 models byte-identical; references re-exported) |
| `gen_configs.py --check`, texture refs | up to date, PASS |

## Reviews

| Review | Finding | Fix |
|---|---|---|
| perf M | Res1 -> Res2 pop (bus 710 -> 24, truck without wheels) | Res2 wheels (6-gon), bus glazing band and bumpers |
| perf L | bus Res3 floating, shadow without wheels, 8 nuts per wheel | Res3 from the floor (see sec M2), wheel boxes in the shadow LOD, 5 nuts |
| perf L | hidden back faces of flush details, rim of the inner twin tyre | accepted (a few hundred triangles on 3 placed instances) |
| sec M1 | bus collision to 2.85 m under a 3.0 m drawn roof: a prone player sinks into the roof, sees and shoots over it | hull = crowned prism following the roof |
| sec M2 | far LODs (truck Res3 ground box, Res2 chassis box) hide players under the truck / above the cab at range | Res3 stepped like the collision (bonnet, cab prism, body, hopper), bus Res3 from the floor, Res2 rails as drawn |
| sec L3 | truck wheel collision 10 cm off the drawn front tyre | collision per axle on the drawn tyre |
| sec L4 | bus wheel wells and 12 cm tapered corners sealed by the hull's side plane | accepted (wells 0.4-0.7 m deep, corners within the ghost tolerance) |
| sec L5 | chassis rails drawn without collision | rail + subframe boxes up to the body |
| sec info | search point on open ground behind the hopper, bags render-only and 22 cm high | unchanged (reachable) |
