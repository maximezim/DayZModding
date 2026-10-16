# D106 office desk, locker, extinguisher cabinet: gates, review, before / after

These are the next D101 candidates: the interior hard props spawned on every Tower A office floor. The server rack and
the kitchenette already read well and were left unchanged.

![Before](img/d106_before.png)
![After](img/d106_after.png)

| Model | Res0 before -> after | Res1 | check_assets |
|---|---|---|---|
| Desk | 158 -> 490 | 62 | PASS |
| Locker | 344 -> 374 | 120 | PASS |
| ExtinguisherCabinet | 262 -> 306 | 96 | PASS |

## Review

| Finding | Fix |
|---|---|
| sec M: the pedestal back face was skipped, leaving a 0.03-0.25 m slot to see through from behind (one-way) | back face kept |
| sec L / perf: the padlock shackle was not on the door bone; a locked-looking door that opens misleads | padlock removed |
| sec L: no pedestal in Res2 (the desk has no legs there either) | accepted, recorded in D106 |
| sec info: the mouse is 0.205 m from the right loot point | kept at x >= 0.3 |
| perf M: the mug and papers added a `paint` section | metal (UV_ALU): 2 sections |
| perf L: buried standoff / key-row / foot faces, mouse rings, extinguisher 14-gon | skips, mouse n=6, 12-gon with 5 rings |
| quality gate: the 3-quad paper stack z-fought (4 layers) | one ream box |

## Gates

| Gate | Result |
|---|---|
| test_quality (3), test_kit (3), test_conceal (3), test_slits (3) | PASS |
| check_assets | 289 checked, 0 fail, 54 over budget (unchanged) |
| check_p3d_sync (build_props) | PASS, 10 models byte-identical |
| gen_configs / gen_manifest --check, texture refs | up to date, PASS (91) |
