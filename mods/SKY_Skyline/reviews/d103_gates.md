# D103 street props close-up: gates, review, before / after

Next wave after D102 (D101 assessment candidates): the most-placed street props.

## Changes (`assets/blender/build_kit.py`, collision unchanged)

- **StreetLight**: round tube arm (was square bars) and a lofted cobra head tapering to the nose (was an extruded
  polygon + a box cap).
- **Barrier_Concrete**: one loft with chamfered ends (three extrusions met in slivers at the ends).
- **Dumpster**: rolled top lip as tubes, pressed side ribs on the tapered sides, lid hinge pins.
- Barrier_Steel already reads well (D78): unchanged.
- Not done: a second tree species (a new piece in the vegetation mix would re-scatter every committed layout,
  including the Chernarus test city); the barrier end faces still show the concrete sheet's dark band (a UV fix on the
  loft caps, follow-up).

![Before](img/d103_before.png)
![After](img/d103_after.png)
![After, overview](img/d103_after_overview.png)

| Model | Res0 | Res1 |
|---|---|---|
| StreetLight | 586 | 248 |
| Barrier_Concrete | 156 | 36 |
| Dumpster | 706 | 36 |

## Gates

| Gate | Result |
|---|---|
| test_quality, test_conceal, test_slits, test_kit (3 models) | PASS |
| check_assets, check_p3d_sync, gen_configs --check, texture refs | CHECKS |

## Review

REVIEW
