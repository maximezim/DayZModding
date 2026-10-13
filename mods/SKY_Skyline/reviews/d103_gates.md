# D103 street props close-up: gates, review, before / after

Next wave after D102 (D101 assessment candidates): the most-placed street props.

## Changes (`assets/blender/build_kit.py`, collision unchanged)

- **StreetLight**: round tube arm (was square bars) and a lofted cobra head tapering to the nose (was an extruded
  polygon + a box cap).
- **Barrier_Concrete**: one loft with chamfered ends (three extrusions met in slivers at the ends).
- **Dumpster**: rolled top lip as tubes, pressed side ribs on the tapered sides, lid hinge pins.
- Barrier_Steel already reads well (D78): unchanged.
- Not done: a second tree species (a new piece in the vegetation mix would re-scatter every committed layout,
  including the Chernarus test city).

![Before](img/d103_before.png)
![After](img/d103_after.png)
![After, overview](img/d103_after_overview.png)

| Model | Res0 | Res1 |
|---|---|---|
| StreetLight | 586 | 248 |
| Barrier_Concrete | 156 | 36 |
| Dumpster | 650 | 36 |

## Gates

| Gate | Result |
|---|---|
| test_quality, test_conceal, test_slits, test_kit (3 models) | PASS |
| check_assets, check_p3d_sync, gen_configs --check, texture refs | CHECKS |

## Review

| Finding | Fix |
|---|---|
| M: barrier end caps fanned from one corner over the concave knees (the dark slivers at both ends, also before D103) | uncapped loft + two convex cap pieces per end |
| M: dumpster Res0 +71 % (412 -> 706) on a prop on every street | 6-sided lip tubes and hinge pins, rib faces against the body dropped: 650 |
| L: dumpster ribs 9.5 mm off the tapered sides (see-through sliver) | ribs follow the side plane |
| L: street-light diffuser / crack wider than the new head's rear | narrowed inside the head |
| L: street-light arm caps at the joints | accepted (Res1 248) |
| Info: head and lip 1-7 cm past Fire / Geometry, as before | unchanged |
