# D99 balconies + D100 Tower A lobby furniture: gates, reviews, before / after

ROADMAP items "balconies on the panel blocks" and "Tower A lobby furniture". Decisions D99, D100; TESTING section 61.

## D99 balconies

AptBlock, AptBlockTall and AptBlockBrick: the body is now 10 m deep with 1 m balconies on the S and N sides (odd bays,
every upper floor, the entrance bay clear), so the footprint stays 18 x 12 m and no layout moves. Per column a
concrete-panel, ribbed-sheet or steel-bar parapet with a steel handrail; per flat often glazed in (white frame grid,
glass up to the slab above, canopy on the top floor); laundry and flower boxes on open ones. Collision follows the
drawing (slab + parapet; one Geometry wall up to the slab above for a loggia; Fire on panels / sheet / glazing and only
the handrail of bar parapets; no View on bars or glass). Damaged blocks keep broken panes, ruins lose glazing and frames.

![Before](img/d99_aptblock_before.png)
Before: flat facade with French-balcony rails.

![After](img/d99_aptblock_after.png)
After: a bar-parapet column with a glazed loggia on the first floor (left), a ribbed-sheet column with flower boxes and
laundry (right), the entrance column clear.

## D100 Tower A lobby

![Before](img/d100_lobby_before.png)
Before: an empty marble hall, a boxy counter.

![After](img/d100_lobby_after.png)
After: fluted walnut reception desk with monitors, phone, lamp and a chair; mailbox bank, wall clock and extinguisher
cabinet on the core; the east lounge (sofa, armchairs, table, rug, floor lamp) behind. Also slatted benches, a notice
board, bins and an entrance mat.

## Gates (9 apartment blocks in all states + both lobbies, exported)

| Gate | Result |
|---|---|
| `test_quality.py` | 0 findings on 11 models (first lobby run: clock face 1 mm off its body and sofa cushion end planes -> separated) |
| `test_city.py` | PASS (9 buildings; first run: a glazed top-floor canopy 5 cm outside the footprint -> flush) |
| `test_towera.py` | PASS (loot points, entrance, keycard door clear) |
| `test_conceal.py` | PASS (11 models; the gate now covers the Tower A modules) |
| `test_slits.py`, `test_ruin_cuts.py` | PASS (9 / 120 models) |
| `check_assets.py` | 289 checked, 0 fail, 50 over the old budgets (count unchanged; the apartment blocks were already over: quality first, D96) |
| `check_p3d_sync.py` | PASS (397 models byte-identical) |
| `gen_configs.py --check`, texture refs | up to date (door lists of the blocks regenerated at the new depth), PASS |

## Reviews

| Review | Finding | Fix |
|---|---|---|
| perf H1 | bar / rib parapets as boxes: too many render vertices on the most-placed buildings | bars as two-sided strips, ribs every 25 cm |
| perf H2 | full loggia frame grid in Res1 | Res1 keeps corner posts and rails |
| perf M3 | parapet + glazing as separate Geometry components | one Geometry wall per loggia side up to the slab above |
| perf M4 | one Res2 / Shadow box per balcony | one box per run of touching balconies in a column |
| perf M5 / sec M2 | bar parapets solid in View (infected-safe perch, sight blocked) | no View on bar parapets |
| perf L | ruin loggia Res2 box to the slab; lobby lamp shade / cabinet on new materials | Res2 to the parapet; existing materials |
| sec M1 | balcony laundry could screen a shooter at a broken window (regression vs the old rail clutter) | no laundry in front of a broken window |
| sec L3 / L4 | drip nose and flower box outside the footprint; frame stubs floating in ruins | inside the footprint; no frames in ruins |
| sec L5 | a truck roof reaches a first-floor balcony with no way in (3-4 m drop back) | accepted |
| sec L6 / L7 | prone slot behind the sofa; narrow gaps round the bins | sofa against the glazing; bins moved clear |
| sec L8 | monitors / chair render-only | accepted (opaque both ways, no hide) |
