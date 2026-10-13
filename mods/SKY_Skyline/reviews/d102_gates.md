# D102 tree pass + traffic light + planter: gates, review, before / after

Picked by the D101 assessment (`reviews/d101_assessment.md`): vegetation and the two weakest street props.

## Changes

- **Trees** (`build_city.build_veg`, new `tree_crown`, `tree_branch`, `BranchUV`): Veg_Birch and Veg_TreeDead grow real
  branches - tapered lofted limbs at golden-angle azimuths, rising and shortening up the trunk, two twigs each, bark
  mapped along the branch - carrying foliage clusters (crossed cards) at the branch tips and midpoints; the birch keeps
  one inner volume card. The crown is clamped to the 3.2 m footprint (layouts and the vegetation scatter unchanged).
  Res1 keeps every other branch and only the clusters on them. Collision unchanged (trunk).
- **Bush** (Veg_Bush): a dome of seven crossed-card tufts over five lofted stems with the bramble skirt (no collision,
  as before), inside its 2.6 m footprint.
- **TrafficLight**: lofted tapered round pole with a cap, round arm and brace, domed lenses (atlas) under half-round
  hoods, clamp bands, a controller box at the foot (now in Fire). Collision otherwise unchanged.
- **Planter**: rounded-corner body with a flared foot (lofted), soil inside the rim.

![Before](img/d102_before.png)
![After](img/d102_after.png)
![Dead tree and bush](img/d102_deadtree_bush.png)
![Traffic light and planter](img/d102_trafficlight_planter.png)
Birch, before / after (distant overview):
![Birch before](img/d102_birch_before.png)
![Birch after](img/d102_birch_after.png)

| Model | Res0 before -> after | Res1 after |
|---|---|---|
| Veg_Birch | 160 -> 1,264 | 308 |
| Veg_TreeDead | 104 -> 880 | 208 |
| Veg_Bush | 32 -> 164 | 24 |
| TrafficLight | 442 -> 1,046 | 130 |
| Planter | 188 -> 384 | 90 |

## Gates

| Gate | Result |
|---|---|
| test_quality (5 models) | PASS (first runs: branch faces past the bark cell's top edge -> per-face offset in the cell) |
| test_city (vegetation) | PASS (first runs: birch crown and bush ring outside the footprint -> clamped) |
| test_conceal, test_slits, test_kit | PASS (first run: 1 cm Fire slit between the new controller box and the pole -> overlapped) |
| check_assets | 289 checked, 0 fail; TrafficLight (1,046 / 600), Veg_Birch (1,264 / 500), Veg_TreeDead (880 / 500) over the pre-D96 budgets (hypotheses, quality first) |
| check_p3d_sync | first run: Fair_FerrisWheel stale - it grows a Veg_Birch through its platform, so it inherits the new tree (re-exported; its quality, conceal, slits and kit gates PASS) |
| gen_configs / gen_manifest --check, texture refs | up to date, PASS |

## Review (security + performance)

No Critical / High / Medium. Low: crown alpha overdraw (clusters now on tips and mids only, about half the cards); Res1
clusters hanging on undrawn branches (now only on Res1 branches); crown casts no shadow (trunk-only shadow LOD kept:
cost); controller box shoot-through (now in Fire). Bush concealment unchanged in kind (no collision, like vanilla bushes).
