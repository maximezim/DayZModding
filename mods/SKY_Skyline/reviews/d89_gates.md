# D89 gates (static, no DayZ run)

| Gate | Command | Result |
|---|---|---|
| One-way concealment, kit + city | `python assets/blender/test_conceal.py --city --jobs 3` | CONCEAL_RESULT |
| Slits, kit + city | `python assets/blender/test_slits.py --city` | PASS (273; same two scoped acceptances; 34 views > 9 Mpx skipped) |
| City geometry (wedge slots now on roofs too, run cutting, pinned self-test) | `python assets/blender/test_city.py` | PASS (191); self-test 7 cases (0.4 m found; flush / 0.8 m / filled not; thin post no longer hides a slot; short leftovers not; roof-level slot found); the new run cutting gave one ruin (RowhouseRender_Ruined) an extra rubble filler |
| Kit geometry (+ wedge slots on every collidable kit asset) | `python assets/blender/test_kit.py` | first run: 1 FAILED (Landfill: 0.34 m x 7.4 m slot between mounds 1 and 2) -> mound moved 1 m, loot points follow; PASS (279) |
| Ruin cuts | `python assets/blender/test_ruin_cuts.py` | PASS (120 models) |
| Asset budgets | `python assets/check_assets.py` | 289 checked, 0 fail; the 3 known far-shell LOD-step warnings (D88, P58) |
| Texture references | `python assets/textures/test_texture_refs.py` | PASS (85 / 0 missing) |
| Generated files | `--check` on gen_configs / gen_manifest / city_progress / gen_economy / gen_terrain | all exit 0 (mapgroupproto regenerated for the moved landfill loot) |
| Script API / PowerShell | `enscript_xref.py`, `Invoke-SelfTest.ps1` | not re-run: no script or tool change |

Cost: +46.4 k Res0 tris over 191 city models (switch / socket quads, skirting, radiators, roof clutter), +4 k Res1,
no new Res0 sections, 6 models +1 Geometry component (the water tank). Largest: Hospital_Intact +2.5 k;
CourtyardBlock_Intact 76.8 k of its 80 k budget.

![Apartment block roof](img/d89_aptblock_roof.png)

Roof of the apartment block from a neighbouring tower: water tank on its skirted frame, vent pipes with caps, mushroom
vents, the conduit from the mast to the parapet on sleepers; chimneys, mast and stair bulkhead as before.

![Clinic ground floor](img/d89_clinic_interior.png)

![Apartment ground floor](img/d89_aptblock_interior.png)

Radiators under the clinic windows (new for public buildings); in the flats, socket plates low beside the doorways and
switches at 1.05 m on the latch side; skirting along the outer walls.

## Review

- **perf-engineer**: no High. M courtyard headroom (98 % with box plates) -> plates as 2-tri quads (-80 %),
  tank detail out of Res1, seams dropped: courtyard 78.4 k -> 76.8 k; M tank as 2 collision components -> one solid box
  per LOD; L skirting in wood could add a section where no partition has one -> white paint; L tank had no shadow ->
  Shadow box (12 tris). Kept: radiators Res0 only; vent shafts n = 4 in Res1.
- **security-auditor**: no Critical / High. M roofs were never wedge-checked (P.top not a level) -> roof level added
  (the tank sits >= 1.2 m from parapets, >= 1.1 m from the bulkhead: no slot today); L a thin post skipped the whole
  slot -> the filled spans are cut out of the run; L open tank legs vs solid collision -> steel skirt panel (render
  matches collision; no one-way view). Deferred (noted in DECISIONS D89): props on plinths / raised decks, sloped shapes
  by bounding box (landfill mounds checked by hand: no pair under 1.0 m except two that intersect). Checked OK: tank is
  no climbing aid or sealed volume, radiators / plates / skirting render-only, loot points keep 0.4 m off walls.
