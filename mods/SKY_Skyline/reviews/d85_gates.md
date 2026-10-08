# D85 gates (static, no DayZ run)

| Gate | Command | Result |
|---|---|---|
| One-way concealment, kit + city | `python assets/blender/test_conceal.py --city --jobs 4` | PASS (273 models, 57 min) with the exam / classroom / ward variants and the AO VendingMachine |
| Slits, kit + city | `python assets/blender/test_slits.py --city` | PASS (273; same two scoped acceptances; 34 views > 9 Mpx skipped) |
| Ruin cuts | `python assets/blender/test_ruin_cuts.py` | PASS (120 models, 173 whole pieces) |
| City geometry (walkability, reachability, search spots) | `python assets/blender/test_city.py` | PASS (191) |
| Kit geometry | `python assets/blender/test_kit.py` | PASS (279) |
| Asset budgets | `python assets/check_assets.py` | 289 checked, 0 over |
| Texture references | `python assets/textures/test_texture_refs.py` | PASS (78 / 0 missing; `sky_vend_as` new, macro-offset rvmats reuse existing maps) |
| Layout / generated files | `test_sky_layout.py`, `--check` on gen_configs / gen_manifest / city_progress / gen_economy / gen_terrain | 0 failed / all exit 0 |
| Script API / PowerShell | `enscript_xref.py`, `Invoke-SelfTest.ps1` | OK 26 files / all passed (no script change) |
| P3D writer stability | rebuild city + props, md5 before / after the `#UVSet#` 1 change | every model without `uv1` byte-identical; VendingMachine Res0 carries set 0 and set 1 (3780 bytes each) |

![AO pilot](img/d85_ao_pilot.png)

Left: `sky_vend_as` (256, baked by `aobake.py` in 7 s). Middle: the map on the VendingMachine through UV set 1 (Blender
Cycles, emission only). Right: a per-chart colour sheet on the same UV set - every face shows one flat colour, so the
second set maps each face to its own chart (no flipped or shared charts).

Variant counts over the city: exam rooms 22 / 30 / 26 (original / treatment / procedure), classrooms 22 / 21 / 29
(original / science / reading), wards 52 / 71 / 69 (before the D85 size rules trimmed the smallest rooms).

## Review

- **security-auditor**: M procedure-room chair + trolley could box in the medicine search spot -> keep-clear zone over
  the shelving and spot for all exam variants, trolley on the far side, w > 3.2; M science room corner pockets -> w and
  d > 4 m; L folding screens skipped `clear()` -> per panel; L unwrap failure was a KeyError -> explicit error; curtains,
  IV stands and screens are thin two-sided render (no one-way sight); bookcases flush to the wall; all names constant.
- **perf-engineer**: L AO 512 was oversized -> 256 baked at size; bake waste -> back-face triangle culling, floor test
  first, float32 bounded chunks (2 min -> 7 s); L reading room 4 chairs ~220 tris -> 2; macro-offset rvmats cost only
  state sorting between buildings (each model is its own P3D anyway); second UV set 4-8 bytes per Res0 vertex; exam
  variants +1 collision part (within the D84 rule).
