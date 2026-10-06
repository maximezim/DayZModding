# D61 gates (static, no DayZ run)

City life: the 23 brainstorm ideas (ROADMAP.md). D61 ships the world content and the gameplay systems.
Creatures (D62), the underground (D63) and drivable vehicles (D64) are planned, not built. Nothing here
ran in DayZ yet: everything is `built-unverified` until TESTING section 26 passes.

| Gate | Command | Result |
|---|---|---|
| City geometry | `python assets/blender/test_city.py` | PASS (176 buildings). New venues: Hypermarket, Mall, Cinema, Bar, Kindergarten, Clubhouse, ChurchHanged x 3 ruin states. Doors and corridors stay clear (a creche ruin keeps the corridor) |
| Kit geometry | `python assets/blender/test_kit.py` | PASS (242 assets). It now includes the 22 landmarks/street pieces from `build_landmarks.py` and checks their footprints against `skyspec.LANDMARK_SIZE` |
| Asset budgets | `python assets/check_assets.py` | 251 checked, 0 fail, 0 over. Small/medium `sections_res0` were raised by 1 (hypotheses): 5 street props carry a rust or paint trim section |
| Layout | `python placement/tests/test_sky_layout.py` | 0 failed. New checks: jams leave only a pedestrian gap, hydrant wet share, no tile under a tunnel, a viaduct over a junction fails, a funfair in a block that is too small fails |
| City life template | `python placement/sky_layout.py --layout placement/citylife_template.yaml` | PASS, 475 entities |
| Generated files | `gen_configs / gen_manifest / gen_economy / city_progress --check` | all up to date |
| Script API | `tools/assets/enscript_xref.py` vs vanilla scripts | OK, 21 files, every call and type resolves |
| PowerShell | `tools/tests/Invoke-SelfTest.ps1` | all self-tests passed |

## Gameplay scripts: security and performance review (self-review against CLAUDE.md)

| System | Client input | Server checks | Per-frame cost | Bounds |
|---|---|---|---|---|
| Search (`ActionSKY_Search`, `SKY_SearchService`) | none (vanilla action RPC only) | table from the target's config, distance to a search memory point, rate per identity (4 s), spot cooldown (30 min), alive | the client condition does a cached map lookup and at most 9 `ModelToWorld` calls for the targeted object | spots <= 4096 (fails closed when full), rate map <= 512, type caches = config classes |
| Alcohol (modded `PlayerBase`) | none: the server reads the consumed item's liquid | only server `Consume` adds ethanol | the server tick does work only while ethanol > 0. The client applies the PPE only when the synced level changes | 1 synced int (0..3), clamped to 200 ml |
| Hydrant | none | vanilla well actions | none | - |
| Hordes + alarm (`SKY_CityLife`) | none | server-only timer | one 10 s timer: sirens x players distance checks | sirens <= 64, members <= 72 + 36 |
| Siren RPC | server -> client only. A client-sent copy is ignored on the dedicated server | - | one sound per alarm | - |

Class names are only server constants checked against the vanilla types.xml and events.xml; no client
string chooses a class, a path or a log format. Logs: one line when the director starts and one per alarm.

## Renders (Blender preview, not the engine)

- District: `img/d61_district_aerial.png`, `_fun`, `_jam`, `_bridge`, `_viaduct`. The orange blocks in the jams are preview stand-ins for vanilla `Land_Wreck_*`.
- Venues: `img/d61_<venue>_states.png` (intact / damaged / ruined), `img/d61_<venue>_interior.png`.
- Kit: `img/d61_fair.png`, `img/d61_roads.png`, `img/d61_props.png`.

## Open (PENDING_VERIFICATION P14-P20)

| ID | What |
|---|---|
| P14 | Alarm noise reach |
| P15 | Horde caps vs server FPS |
| P16 | Vodka/beer liquids and the dose thresholds |
| P17 | Search points, loot tables, cooldowns |
| P18 | A spawned hydrant as a vanilla well |
| P19 | Jams really stop cars |
| P20 | Siren sound range |
