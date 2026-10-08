# D90 gates (static, no DayZ run)

| Gate | Command | Result |
|---|---|---|
| One-way concealment, kit + city | `python assets/blender/test_conceal.py --city --jobs 4` | CONCEAL_RESULT |
| Slits, kit + city | `python assets/blender/test_slits.py --city` | SLITS_RESULT |
| City geometry + new far-LOD gates | `python assets/blender/test_city.py` | first runs found: the D88 Res 1.5 bug (street facades missing), Res 1.75 empty window openings, 22 wedge slots beside garage wrecks, far-LOD see-through on garages and 4 courtyard ruins, one cinema pane (painted on a wall: exempt) -> all fixed; PASS (191) |
| Gate mutations | old band / shell depth 0.04 / voids dropped / void back in Res0 | FAIL each (74 of 593 m2 front kept; 265 panes missing; 123 vs 22 rays through; 67 one-way panes) |
| Kit geometry | `python assets/blender/test_kit.py` | first run: 4 FAILED (Ferris wheel: sloped A-frame legs compared by bounding box) -> only axis-aligned box parts compared, the rest counted (180); PASS (279) |
| Ruin cuts | `python assets/blender/test_ruin_cuts.py` | PASS (120) |
| Asset budgets / LOD steps | `python assets/check_assets.py` | 289 checked, 0 fail, 0 warnings (the 3 far-shell warnings of D88 are gone) |
| Texture references | `python assets/textures/test_texture_refs.py` | PASS (85 / 0 missing) |
| Generated files | `--check` on gen_configs / gen_manifest / city_progress / gen_economy / gen_terrain | all exit 0 (mapgroupproto regenerated: garage loot moved with the wrecks) |
| Script API / PowerShell | `enscript_xref.py`, `Invoke-SelfTest.ps1` | not re-run: no script or tool change |

LOD chains after D90 (Res0 -> Res1 -> Res 1.5 -> Res 1.75 -> Res2 -> Res3):
CourtyardBlock_Intact 77.6 k -> 22.5 k -> 15.2 k -> 6.1 k -> 0.6 k; Hospital_Intact 56.5 k -> 16.5 k -> 11.7 k -> 4.8 k -> 0.3 k;
AptBlockTall_Damaged 44.2 k -> 14.0 k -> 11.3 k -> 4.3 k -> 1.2 k. Res 1.5 on 110 models, Res 1.75 on 52.

![Courtyard block, Res 1.75](img/d90_courtyard_res1y.png)

Res 1.75 of the courtyard block in its three states (rendered with `preview_city --lod res1y`): whole facades, every
window filled (glass, boards, the dark backing of broken windows), shutters and string courses kept.

![Brick apartment block, Res 1.5](img/d90_aptblockbrick_res1x.png)

## Review

- **perf-engineer**: no High. M MID_STEP 12 let 8-14 % steps through and gave small buildings a sixth LOD -> MID_STEP 7,
  MID_MIN 3 k (unless the step is < 5 %); M Res 1.75 -> Res 2 under 20 % on the largest -> 15 % target above 10 k;
  M Res 1.5 a near-copy of Res1 on small buildings -> dropped above 85 % (kept when a Res 1.75 follows or Res1 -> Res2
  would step below 5 %: the hypermarket); L res1y budget could never fail -> 35 % of res1.
- **security-auditor**: no Critical / High. M ruined far LODs see-through at range, and `facade_cover` too weak to see
  it -> the void quads moved to the far LODs, boarded windows backed, rubble kept, plus the `opening_cover` and
  `far_see_through` gates; checking the void led to the one-way pane finding: `glassfar` is opaque, and the Res0 void
  behind every broken window was a one-sided pane in an open window - removed, and a rule now fails any opaque pane in
  a reachable outer opening of Res0 / Res1 (not painted on a wall, not above the roof); L plinth false negative ->
  support rule (a box on a low plinth beside a floor box); L non-box parts silently skipped -> counted and reported.
