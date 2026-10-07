# D84 gates (static, no DayZ run)

| Gate | Command | Result |
|---|---|---|
| One-way concealment, kit + city | `python assets/blender/test_conceal.py --city --jobs 4` | PASS (273 models, 67 min) with the new furniture (sofas, TV units, bookcases, sideboards, fridges, filing cabinets) |
| Slits, kit + city | `python assets/blender/test_slits.py --city` | PASS (273; same two scoped acceptances as D83; 34 views > 9 Mpx skipped) |
| Ruin cuts | `python assets/blender/test_ruin_cuts.py` | PASS (120 models, 173 whole pieces) |
| City geometry (walkability, reachability, search spots) | `python assets/blender/test_city.py` | PASS (191) |
| Kit geometry | `python assets/blender/test_kit.py` | PASS (279) |
| Asset budgets | `python assets/check_assets.py` | 289 checked, 0 over |
| Texture references | `python assets/textures/test_texture_refs.py` | PASS (77 / 0 missing; `sky_grime_mc` new) |
| Layout / generated files | `test_sky_layout.py`, `--check` on gen_configs / gen_manifest / city_progress / gen_economy / gen_terrain | 0 failed / all exit 0 (city_loot + mapgroupproto regenerated, loot point count unchanged) |
| Script API / PowerShell | `enscript_xref.py`, `Invoke-SelfTest.ps1` | OK 26 files / all passed (no script change) |

![Grime macro](img/d84_macro.png)

27 m brick and 32 m stucco walls (base sheet tiled 8 x 8), left without, right with the macro blended as the
Super shader does (lerp by alpha). The stucco now has small plaster losses only.

![Furnished flats](img/d84_interior.png)

AptBlock ground floor (Blender preview, cut open at the front): the left flat keeps the original lounge kit, the
right one drew variant 1 (TV unit, bookcase, rug, art; the sofa was skipped because its spot touched a door zone).
Furniture placement traced per room: 56 sofas, 95 TV units, 201 bookcases, 173 sideboards, 48 fridges, 67 filing
cabinets across the 191 city models.

## Review

- **security-auditor**: M art panel could hang in a side doorway (opaque one way at head height) -> `clear()` check;
  M 0.38 m slot behind the fridge -> fridge flush to the run, gap to the end wall <= 5 cm or >= 0.75 m; L bed-bookcase
  slot -> bedroom variant 2 needs w >= 3.15; L twin-bed desk blocked the aisle -> d >= 3.45; L sofa collision 0.1 m
  over the cushions -> collision at the cushion top. Sofa backs, TV, chairs, books < 0.2 m; View boxes like the wardrobe.
- **perf-engineer**: M office variant added 2 collision parts -> one shared desk block + cabinet (+1); L macro alpha
  floor tinted every wall -> removed; Stage3 macro costs only bandwidth for one shared 1024 DXT5 (Super already
  samples Stage3); book quads ~26 tris per bookcase, no new sections.
