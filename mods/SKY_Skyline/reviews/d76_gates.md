# D76 gates (static, no DayZ run)

| Gate | Command | Result |
|---|---|---|
| Kit geometry + hull + wiring | `python assets/blender/test_kit.py` | PASS (279 assets; PROP_BOX bounds unchanged, cubicle back screen now between the side screens) |
| Asset budgets | `python assets/check_assets.py` | 289 checked, 0 fail, 0 over. Res0 -> Res1 -> Res2: ReceptionDesk 230 -> 60 -> 24, Desk 158 -> 50 -> 12, Cubicle 242 -> 72 -> 36, ServerRack 238 -> 40 -> 12, VendingMachine 232 -> 60 -> 14, Locker 344 -> 120 -> 12, Sofa 190 -> 48 -> 24, Bed 154 -> 48 -> 24, Kitchenette 460 -> 112 -> 24, ExtinguisherCabinet 246 -> 72 -> 12 (was 14-132 Res0) |
| City geometry / layout | `test_city.py`, `test_sky_layout.py` | PASS 191 / 0 failed (props are spawned by FURNISH; counts unchanged) |
| Generated files | `gen_configs / gen_manifest / city_progress / gen_economy / gen_terrain --check` | all exit 0 |
| Script API / PowerShell | `enscript_xref.py`, `Invoke-SelfTest.ps1` | OK 26 files / all passed |

## Reviews

- **security-auditor**: no Critical / High / Medium. Collision (Geometry / Fire / View), door bones, memory points and loot points unchanged, verified tuple by tuple. No render-only volume thicker than 0.2 m; render gaps under bed / sofa / rack are symmetric (no one-way advantage). Door hardware carries the door selection. Low: desk mouse inside the 0.2 m loot radius -> moved. Info: dead code removed. Hygiene clean.
- **perf-engineer**: no High. Medium: locker and cabinet carcass boxes overlapped coplanar (the "black faces") -> render carcass rebuilt without overlaps, collision untouched; atlas / screen quads 1 mm in front of opaque faces in mid/far LODs -> 4 mm or the face replaced; cubicle back screen overlapped the side screens -> trimmed. Lows: wood dark-plastic trick only where wood already exists (rack brush and eyes dropped, locker plinth uses the rust sheet), redundant reception back quad removed, Res1 monitor body added to the cubicle, glass pane trimmed to the frame opening, grommet as a quad, tap Res0 only. One furnished office floor at Res0 is ~2.9k triangles / ~40 section draws vs the floor module's 16k.

Renders: `img/d76_before.png` (batch-3 boxes), `img/d76_props_metal.png`, `img/d76_props_office.png`, `img/d76_props_home.png`, `img/d76_extinguisher.png` (D77 textures).
