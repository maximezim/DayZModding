# D107 street bin and advertising column: gates, review, before / after

These are the last street-prop candidates from the D101 assessment (`reviews/d101_assessment.md`).

![Before](img/d107_before.png)
![After](img/d107_after.png)

| Model | Res0 before -> after | Res1 | check_assets |
|---|---|---|---|
| TrashBin | 584 -> 648 | 64 | over the 600 budget: recorded as a D96 hypothesis (bag detail) |
| AdColumn | 664 -> 640 | 180 | PASS |

## Review

| Finding | Fix |
|---|---|
| sec L: the taller bags gave a crouching player partial render-only cover over the bin | bags moved inside the collision radius and no taller than the old prisms |
| sec info: the search point, the poster flap and the door strips are clear | none needed |
| perf M: hidden loft caps (heap and bag bases, dome base on the cornice, dome top under the finial) | `caps=False` on those lofts |
| perf L: over-tessellated bags and dome | 8 x 4 bags; the near-vertical and finial dome rings dropped |
| perf L: door strips half inside the drum | accepted (6 faces) |

## Gates

| Gate | Result |
|---|---|
| test_quality (2), test_kit (2), test_conceal (2), test_slits (2) | PASS |
| check_assets | 289 checked, 0 fail, 55 over budget (TrashBin added as a hypothesis) |
| check_p3d_sync (build_landmarks, build_streetprops) | PASS, 24 models byte-identical |
| gen_configs / gen_manifest --check, texture refs | up to date, PASS (91) |
