# Realism pass (D53/D54): perf, security and QA gates

Scope: every existing building module re-generated with the shared detail kit
`assets/blender/detail.py` (Tower A lobby, office floor, helipad roof, core; Floor_Apartments,
Floor_Hotel, Floor_Mechanical, Roof_Garden, Roof_Mechanical). Static gates only - nothing ran in DayZ.

## Perf - PASS (budgets raised as hypotheses, D54)

| Module | Res0 | Res1 | Res2 | Res3 | Res0 sections | Geo comps | Fire comps |
|---|---|---|---|---|---|---|---|
| TowerA_Lobby | 1064 -> 1722 | 668 -> 924 | 92 -> 136 | 24 | 8 | 21 -> 32 | 33 |
| TowerA_Floor_Office | 928 -> 1560 | 536 -> 776 | 56 -> 128 | 16 | 6 | 12 -> 20 | 20 |
| TowerA_Core | 1602 -> 2106 | 846 | 132 | 10 | 3 | 81 (pre-existing) | 81 |
| TowerA_Roof_Helipad | 98 -> 410 | 98 -> 210 | 96 | 48 | 4 | 8 -> 10 | 11 |
| Floor_Apartments | 1264 -> 3240 | 872 | 56 -> 200 | 8 -> 24 | 7 | 40 (pre-existing) | 40 -> 112 |
| Floor_Hotel | 1240 -> 3056 | 848 | 56 -> 200 | 8 -> 24 | 7 | 38 (pre-existing) | 38 -> 110 |
| Floor_Mechanical | 152 -> 896 | 128 | 80 | 8 | 3 | 12 | 12 |
| Roof_Garden | 160 -> 526 | 128 -> 262 | 88 | 10 | 5 | 12 -> 18 | 18 |
| Roof_Mechanical | 272 -> 696 | 128 -> 288 | 88 | 10 | 3 | 12 -> 13 | 14 |

- Detail lives in Res0; Res1 of the floor variants is unchanged in triangles, Res2/Res3 carry outer
  faces only with opaque materials (`check_assets` far-LOD alpha gate: 0 fails). No shadow-volume change.
- Found and fixed during the gate: lobby 9 sections (entrance mat removed), office 8 sections
  (spandrel back-panel and skirting moved to the metal sheet: 6), office Geometry 304 > 300 tris
  (column collision = inscribed box instead of an octagon).
- Tower A stack: res0 ~12.0k, 45 sections (manifest `budget_total` raised to 14000 / 48, D54).
  Watch item for the FPS protocol: sections per tower (one draw call per material per module).
- Fire Geometry components on apartment/hotel floors grew 40 -> ~110 (piers, bands, panes). Raycast
  cost only on hits against that tower; no per-frame cost. Flagged for S2/S6 measurement.
- `check_assets`: 44 checked, 0 fail, 3 over budget, all pre-existing (core 81 comps; apartments /
  hotel Geometry 40 / 38 comps, D37).

## Security - PASS

- No collision outside the footprint: Tower A modules' Geometry bounds are exactly +-12 m (slab
  -0.3 m, lobby skirt -2.5 m); `test_kit` checks the variants. Visual projections (cornice 6 cm,
  fins 18 cm, sill stones 6 cm, canopy 2.2 m) have no Geometry.
- Core clear zones (stair / elevator doors) untouched in Geometry, View and Fire on all 9 modules
  (`test_kit` for variants; same check run on Tower A modules for this gate). Door frames are Res0 only.
- Reachability flood fill: office and helipad fully reachable; lobby unreachable area = the
  keycard security room only (closed leaf, by design); variants pass incl. FURNISH sets.
- No new standable surface above reach: canopy, sign, pergola beams, pipes and masts have no
  Geometry. New climbable heights: helipad units 1.6 m (0.55 m from the parapet, no access
  gained), garden benches 0.45 m, mechanical-roof tank 2.6 m (not climbable).
- Ballistics/visibility change (documented in D54): apartment/hotel piers and bands are masonry /
  concrete in Fire Geometry and solid in View Geometry, glass only in the window openings. More
  cover than the previous all-glass facade; matches what players see.
- Keycard door, leaf, card reader and its memory points unchanged (`test_towera` PASS). Sign text is
  original (`SKYLINE TOWER`), no real brand.

## QA - PASS

- `test_towera` PASS (81 core components), `test_kit` PASS (39 assets: footprint, core zones,
  reachability, roof-drop crates, FURNISH, loot points), `check_assets` 0 fail, `gen_configs --check`,
  `gen_manifest --check`, `gen_economy --check` up to date, `test_sky_layout` 0 failed,
  `Invoke-SelfTest.ps1` all passed, pyflakes clean on the changed generators.
- Visual review renders (Cycles, generated textures): `reviews/img/exterior.png`, `entrance.png`,
  `lobby.png`, `office.png`, `facade_close.png`, `roof.png`, `section.png`, `elevator.png`,
  `floor3_core.png`, `realism_apartments.png`, `realism_hotel.png`, `realism_mechanical.png`.
  Found and fixed: dark seam at the curtain-wall corners (corner mullions poked 4 cm past the pier;
  the visual pier now wraps them, collision stays inside the footprint); sign text centred.
- Preview note: Cycles renders back faces, so the single-sided ceilings look white from above in
  top-down shots; in game they are culled (RP-03 checks it).
- In-game rows: `TESTING.md` §19 RP-01..RP-10.
