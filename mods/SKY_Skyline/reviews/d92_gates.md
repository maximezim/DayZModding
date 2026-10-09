# D92 gates (static, no DayZ run)

| Gate | Command | Result |
|---|---|---|
| City geometry | `python assets/blender/test_city.py` | PASS (191) |
| Kit / Tower A geometry | `test_kit.py`, `test_towera.py` | PASS (279), PASS (81) |
| Ruin cuts | `test_ruin_cuts.py` | PASS (120) |
| Asset budgets / sections | `python assets/check_assets.py` | 289 checked, 0 fail, 0 warnings (no Res0 section over budget) |
| Texture references | `textures/test_texture_refs.py` | PASS (85 / 0 missing) |
| Generated files | `--check` on gen_configs / gen_manifest / city_progress / gen_economy / gen_terrain | all exit 0 |
| Concealment / slits | not re-run | only alpha decals (see-through for both scans) and UVs changed; Geometry / Fire / View of every city model unchanged (stats: geo / fire / view delta 0) |
| Script API / PowerShell | not re-run | no script or tool change |

![Wear bands](img/d92_wear_bands.png)

The four new bands of `sky_decal_grime_ca` over white paint: scuff (horizontal rub marks, densest at the bottom), hand
smudge (fades to every edge), water stain with a tide mark, mould. The facade bands are unchanged in the top half.

![Damaged flat](img/d92_aptblock_damaged_interior.png)

Damaged apartment block, ground floor: water stains under the ceiling; scuffs and smudges read up close.

## Review

- **perf-engineer**: no High. M the window-sill streaks still used the old quarter layout (they would have shown
  scuff / smudge art on every facade) -> `grime_v("streak")`; M curtain-wall offices gain the decal section -> within
  budget, accepted; L two close doorways stacked scuffs -> earlier spans subtracted; L mip bleed between bands -> clear
  edge rows on the wear bands; texture +1.3 MB once.
- **security-auditor**: no Critical / High / Medium. 7352 wear quads checked by a harness: none in a doorway, past a
  wall end, zero-size or above the ceiling, none overlapping; decals are see-through for the concealment gates and
  dropped from the far LODs. L smudge 2 mm under the switch plates -> 4 mm.
