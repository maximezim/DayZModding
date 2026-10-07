# SKY_Skyline progress report

## Status at a glance (after D77, 2026-10-07)

**Overall: about 59 % of a releasable v1.0.** About 92 % of the content is authored and every offline gate
passes. But nothing has been packed, signed or run in DayZ yet. In-game verification is 0 % and carries the
most weight of what remains.

| Area | Weight | Done | Why |
|---|---|---|---|
| Design and spec (23 ideas, city catalog, decisions D1-D77) | 10 % | 100 % | every idea has a design or a documented block |
| Content authored (models, scripts, configs, economy, layouts) | 30 % | 92 % | 21 of 23 ideas built; horses and drivable vehicles blocked on Workbench skills; the underground needs a custom terrain |
| Offline quality gates (tests, budgets, generators, script xref, reviews) | 10 % | 100 % | test_city 191, test_kit 279 (with hull and wiring checks), check_assets 289 / 0 over, layout 0 failed, texture references 72 / 0 missing, perf + security reviews on every batch |
| Asset quality to ASSET_QUALITY_GUIDE section 8 | 15 % | 63 % | street kit, street surfaces, the interior room kit, venues and underground passed close-up passes; wood, fabric, paver and concrete maps have real depth (D77); facades still use flat procedural maps (no baked AO); building interiors repeat their room kits |
| Pack, sign, PAA on Windows (full mod) | 10 % | 10 % | toolchain verified with the empty template only (SETUP_REPORT); the 18 SKY packages were never packed |
| In-game verification (TESTING sign-off, P-parameters) | 20 % | 0 % | 0 of 44 sign-off rows, 0 of 48 `P` assumptions, `CITY_TESTED` empty |
| Release prep (real site / terrain, FPS numbers, server-owner docs) | 5 % | 20 % | layouts and terrain generator ready; no surveyed site, no Terrain Builder import, no FPS run, no perf probe |

Weighted: 10 + 27.6 + 10 + 9.5 + 1 + 0 + 1 = **59.1 %**.

### Built (offline-verified, `built-unverified`)
- **City**: 35 building types and 60 variants, 156 procedural models in 3 ruin states, plus 15 venue
  variants (D69). Tower A (modular core, lobby, floors, roofs) and the floor/roof variants. A layout
  generator with city fill by zone, ruins, vegetation and caps.
- **Street kit**: roads and combined street tiles. Lamps, lights, barriers, bins, hydrants, bus stops,
  ad columns, phone booths, billboards. Sedan hulks in 3 states, van, bus and garbage-truck wrecks.
- **City life (D61-D74)**: funfair, landfill, stadium, venues, the bridge, viaducts, road tunnel, car jams.
  Hordes, sirens, searchable bins and furniture (10 server tables), hydrants, alcohol, kennel / guard dog,
  rats. Sewers and metro with flooding, ambience loops, night lights.

### Not done / blocked
1. **First in-game session**: packing, signing, PAA conversion, a dedicated + diag run, logs.
   `TEST_SESSION.md` is the script. It needs the Windows machine; the cloud sessions cannot run DayZ.
2. **45 engine assumptions** (PENDING_VERIFICATION P1-P45) and **41 sign-off rows** (TESTING): each has a
   one-line fix ready.
3. **Blocked on skills outside the procedural pipeline**:
   - horses (idea 11);
   - drivable bus / garbage truck (idea 15, `vehicles/VEHICLE_SPEC.md`);
   - animated dogs / rats: today they are static models plus server rules.
4. **Custom terrain (Level 2)**: the sewers / metro and hidden hatches need terrain holes. Terrain Builder
   import of `terrain/out` is not done (P11). A real map site is not surveyed.
5. **Perf numbers**: FPS protocol never run; the server perf probe (B11) is not written.

### Refinement still worth doing
- **D75 hull test 2**:
  - a ray-grid slit test;
  - a check that render LODs stay inside the collision (one-way concealment).
- **Street kit pass 3**: steel barriers, benches, Sewer_Junction, ParkingLot_B.
- **Texture depth**: baked AO / normal maps for building facades and the hero props (`_nohq` today are flat
  procedural). Grime macro maps (B3).
- **Interior variety**: furniture sets per room kind repeat across buildings. Merged furniture (D43) is
  deferred until FPS is measured.
- **Billboard / traffic-light night lights** (memory points exist; no script light yet).
- Elevator hum / ding sounds (manifest: planned).

---

## Batch log


Branch `claude/dayz-modding-setup-3q6dxg`. **Nothing has run in DayZ.** Every asset is
`built-unverified`; nothing is `done`. Tower A was not changed except for a build-tool exit code
(D34, byte-identical P3Ds). The HQ landmark, the 25-floor Office Tower and the skybridge were not
started. Every batch was committed and pushed (push works now); a handoff zip was sent after
batches 1-5, and one goes out with this report.

## 1. What was built

| Batch | Built | Key files |
|---|---|---|
| 1 Street kit + props | 24 classes in `sky_street`: road / sidewalk / curb / manhole, 3 combined 12 m street tiles, street light, traffic light, barriers, bus stop, dumpster, planter, 2 wrecks, billboard A-D | `assets/blender/build_kit.py`, `addons/sky_street/` |
| 2 Textures + decals | dirt / cracks / 4 original graffiti decals, window-set atlas (lit + unlit rvmats), brick and concrete-panel facade trims; PAA conversion via `Build-SkyAssets.ps1` | `assets/textures/gen_textures.py`, `addons/sky_textures/data/` |
| 3 Interior props | 10 props in `sky_props`: reception desk, desk, cubicle, server rack, vending machine (flap), locker bank (3 doors), sofa, bed, kitchenette, extinguisher cabinet (glass door); doors on `DOOR_SWING_SIGN`, not lockable (`Land_SKY_Props_Base.c`) | `assets/blender/build_props.py`, `addons/sky_props/` |
| 4 Floors + roofs | `Floor_Apartments`, `Floor_Hotel`, `Floor_Mechanical`, `Roof_Garden`, `Roof_Mechanical` on the unchanged Tower A core, same stacking; reachability (flood fill) tested | `assets/blender/build_floors.py`, `addons/sky_floors/` |
| 5 Economy + placement | 9 new loot groups (5 floor/roof types, 4 props); layout generator with 12 m street grid, blocks, tower variants, furniture sets, decals, street lights, caps, roof drops per roof type, one infected zone per district; zombie notes per floor type; district template with unfilled site | `placement/sky_layout.py`, `placement/district_template*.yaml`, `economy/` |
| 6 Testing + Windows readiness | TESTING.md sections for every asset type (§0b, §14-§18), one-command validation `tools\tests\Invoke-ModValidation.ps1`, FPS protocol + results template, AFTER_TESTING checklist | `TESTING.md`, `FPS_PROTOCOL.md`, `AFTER_TESTING.md`, `reviews/fps_results_template.csv` |

Totals: 44 P3Ds (39 kit + 5 Tower A/keycard), 12 loot groups, 52 decisions (`DECISIONS.md`),
9 parameters P1-P9 + 12 behaviour checks B1-B12 (`PENDING_VERIFICATION.md`).

## 2. Gate results (static; reviews in `reviews/batchN_*.md`)

| Batch | Security | Perf | QA |
|---|---|---|---|
| 1 | PASS | PASS | PASS |
| 2 | PASS | PASS | PASS |
| 3 | PASS | PASS | FAIL (vending flap swung inward) -> fixed -> PASS |
| 4 | FAIL (2 sealed apartments) -> fixed -> PASS | PASS | FAIL (same) -> fixed -> PASS |
| 5 | PASS | PASS | FAIL (street tiles without survey at Y = 0) -> fixed -> PASS |
| 6 | PASS | FAIL (protocol could not produce server numbers) -> fixed -> PASS | FAIL (validation passed on spawn errors) -> fixed -> FAIL (new: live RPT read would hit a Windows sharing violation) -> fixed -> PASS |

No gate failed twice on the same issue (Batch 6 QA failed twice, on two different issues). Every finding was fixed or recorded as a decision. Your two setup commits (smoke test, SETUP_REPORT) were merged, not rebased; the verified ready line `Player connect enabled` is now used by the validation run.
Static suite on the final commit: `check_assets` 44 checked / 0 fail / 5 over budget, generators
`--check` clean, `test_kit` PASS (39), `test_towera` PASS, `test_sky_layout` PASS,
`Invoke-SelfTest.ps1` PASS, script xref OK.

### Budget overruns (flagged, accepted until measured)
- `Land_SKY_TowerA_Core` Geometry 81 > 80 components (Tower A frozen).
- `Land_SKY_Floor_Apartments` / `Floor_Hotel` Geometry 40 / 38 components, 480 / 456 tris (> 24 / 300): one component per wall piece and lintel; lintels kept for security (D37).
- `Land_SKY_Roof_Garden` Res1 128 > 120 and 3 Res0 sections > 2; `Land_SKY_Roof_Mechanical` Res1 128 > 120.

## 3. Blocked / needs you

1. **Server frame probe (B11)**: the FPS protocol's server rows need a small diag-only server mod
   (`SKY_PerfProbe`). It is new mod code, so it is not written. Say "write the perf probe".
2. **Blender on your machine (B10)**: you have Blender 5.2 + DayZ Object Builder; the P3D export was
   built on Blender 4.2 + Arma Toolbox. The committed P3Ds pack as they are; re-exports (after a P2,
   P3, P6 or P8 flip) need 4.2 + Arma Toolbox side by side, or a port of `skygeo.export_p3d`.
3. **Untested parameters P1-P9** (door swing, elevator slide, penetration paths, env map, explosion
   armor class, asphalt surface, emissive strengths, road slab thickness, yaw sense): each has a
   one-line fix in `AFTER_TESTING.md`.
4. **A surveyed site**: `placement/layout.yaml` and `district_template*.yaml` have placeholder /
   unfilled sites; `--strict` refuses them until a survey is filled in.
5. Deferred by decision (measure first): furnished floor variants with merged furniture (D43), grime
   macro maps (B3), proxies for props (D27).

## 4. Test order when you are back

Each step: diag first where noted, then dedicated; fill the TESTING.md rows and sign-off.

1. `tools\tests\Invoke-SelfTest.ps1`, then `tools\setup\Get-ToolchainStatus.ps1` (PyYAML, numpy now listed;
   run `Install-Toolchain.ps1 -Only Pillow` if missing).
2. `tools\tests\Invoke-ModValidation.ps1 -ModName SKY_Skyline -DryRun`, then without `-DryRun`
   (static checks, build, sign, deploy, server start, logs; no layout). Expect summary PASS; tune log
   patterns if not (B9-VAL).
3. **Doors and elevator first, they decide P1/P2 for everything else:** TESTING §4 D-01 (lobby door swing)
   and D-03 (elevator slide), using the Tower A slice (`placement/layout.yaml` with a surveyed site,
   README §1). If D-01 fails: `DOOR_SWING_SIGN = -1`, `gen_configs.py`, rebuild, repeat.
4. Tower A §1-§13 as before (keycard, elevator, loot, roof drop, clean logs).
5. Street kit §16 (spawn single pieces or the district template), then decals/windows §17.
6. Interior props §14 (P3-10..P3-14 door swing confirms P1 on props; P3-25 lockpick = B5).
7. Floor/roof variants §15 on the Tower A core (layout `floors:` / `roof:`).
8. District §18: survey a flat site (relief <= ~0.75 m), fill `district_template.yaml`, `--strict` PASS,
   `Invoke-ModValidation.ps1 -Layout ...`, then the survey export (`exportRadius` from the report) and
   loot (L5-xx), yaw check P5-YAW (P9), infected Z5-xx.
9. FPS protocol (`FPS_PROTOCOL.md`), after B11 if you want server numbers; client-side rows work without it.
10. Apply `AFTER_TESTING.md`: flip only what a test disproved, regenerate, re-run the listed tests, then
    move statuses `built-unverified -> packed -> tested`.

## 5. Where things are
- Decisions: `DECISIONS.md` (D1-D52). Untested assumptions: `PENDING_VERIFICATION.md`.
- Tests: `TESTING.md`, `FPS_PROTOCOL.md`, `AFTER_TESTING.md`. Gate reviews: `reviews/`.
- Asset spec (single source of truth): `assets/skyspec.py`; manifest: `assets/manifest.yaml`.
- Handoffs: `_handoff/batchN/` (git-ignored; bundle + zip + HANDOFF.txt).

## 6. Realism pass (after the batches, D53/D54)

On request ("make all already created buildings much more realistic and complete") every existing
building was re-generated with one shared detail kit (`assets/blender/detail.py`, numbers in
`skyspec.DETAIL`). Gameplay shell unchanged and re-tested.

- **Tower A**: curtain wall with spandrels, deep fins, slab-nose cornices and concrete corner piers;
  lobby with columns, tile-grid ceiling, entrance canopy with an invented `SKYLINE TOWER` sign,
  door portal, oak/walnut reception desk, benches and planters; office floor with columns, ceiling,
  door frame and skirting; helipad roof with coping, two HVAC units and a mast; core with
  handrails and door frames on every stop.
- **Apartments / Hotel**: brick / precast-panel facades with recessed ribbon windows (frames,
  mullion, sill stones, soldier course), plaster ceilings, oak door frames and skirting.
- **Plant floor**: louvre blades on a dark backing, pipes, control panels. **Roofs**: copings,
  HVAC units with fans and panels, water tank, mast, benches, pergola with deck.
- New material `ceiling`; atlas cell `signage`. Budgets raised as hypotheses (D54); gates PASS
  (`reviews/realism_gates.md`); renders in `reviews/img/`; in-game rows `TESTING.md` §19.

## 7. Splendour pass (D55)

On request ("vastly more room for materials, decorations, texture maps, interior decoration,
lighting"): budgets raised (floor res0 16k / 14 sections, lobby 20k / 16, roofs 8k / 10), five new
material sets with real maps, original artworks and wayfinding plates, baked decoration in every
module (lobby marble / limestone / pendants / lounge / trees; office light panels / plants / art;
apartments parquet / paint / curtains / radiators / flower boxes / rugs / art; hotel wainscot /
runner / sconces / art; plant floor, roofs, core wayfinding), and night-only client lights
(`SKY_LitBuilding`, 2 per module, lobby 4; untested parameter P10). Gates PASS
(`reviews/splendour_gates.md`), renders `reviews/img/d55_*.png`, in-game rows TESTING §20, FPS
checks FPS_PROTOCOL 4.1.

## 8. City buildings, wave 1 (D56)

Estimate for a full city: 35 building types, 60 variants, **148 unique models**, **651 placed
buildings** (grounded in vanilla Chernarus counts). Procedural generator `assets/blender/build_city.py`
(one style grammar, three ruin states through one ruin layer). Wave 1: 14 archetypes (6 types + 8
variants) x intact / damaged / ruined = 42 P3Ds, all passing `test_city.py` (walkability per floor,
stairs, doors, loot reachable), `test_kit.py`, `check_assets.py` (0 over budget). Progress is tracked in
the generated `CITY_PLAN.md` (30 % of the unique models; one variant per started type could already
fill 40 % of the city's lots). Next waves and the city layout generator: CITY_PLAN.md "Waves".


## 9. City buildings wave 2 + city layout generator (D57)

Wave 2 adds villa (3 skins, pitched roof), shop row (4 shop signs), supermarket (2 sizes), clinic,
fire station, workshop (2 skins), garage block, kiosk (2), shed (2) and 4 rubble lots: **58 new
P3Ds**, 100 city models in total, all passing `test_city.py` and `check_assets.py`. `CITY_PLAN.md`:
102 / 156 unique models (65 %); one variant per started type could fill 91 % of the city's lots.
`placement/city_fill.py` fills street blocks lot by lot (fronts on the street, corner shops on the
corners, party walls flush, zone weights and ruin mix: downtown / midtown / residential / industrial /
frontline, rubble lots, deterministic seed). The template quarter (`placement/city_template.yaml`)
places 117 buildings. Spawner target stays capped (ENTITY_CAP); the terrain target writes
`city_objects.csv` for Terrain Builder (P11, unverified). Gates PASS (`reviews/city_wave2_gates.md`),
renders `reviews/img/city2_*.png`, `district_*.png`, in-game rows TESTING §22.

## 10. City catalog complete: wave 3, tall towers, landmark blocks (D58)

Every type in `CITY_PLAN.md` is built: **156 / 156 unique models** (35 types, 60 variants). Wave 3 adds
the civic and large types on new shared plans - hospital, school and town hall (double-loaded corridor),
courtyard blocks (perimeter block round a yard with a gallery ring), department store (atrium), bank
(banking hall + vault), church (bell tower, spire), post office, factory hall (sawtooth roof), large
warehouse, parking garage (decks + car ramps), gas station and cafes (forecourts), substation, water
tower and two sealed metro entrances - 51 city P3Ds, all passing `test_city.py`. Office towers and the
HQ landmark reuse the Tower A modules on taller cores (17 / 25 / 35 storeys, same elevator script) with a
new crown roof. The city template now merges blocks by closing street cells and holds the landmarks:
93 buildings, 43 / 27 / 23 intact / damaged / ruined. Gates PASS (`reviews/city_wave3_gates.md`), renders
`reviews/img/city3_*.png`, `district3_*.png`, `towers_tall*.png`, in-game rows TESTING §23.

## 11. DayZ ambiance pass (D59)

The city now reads as Chernarus after the collapse: faded post-Soviet stucco colours, sooty brick,
weeping precast joints, plaster falling off the brick, rising damp with moss at every wall base,
run-off under every roofline, streaks under sills, rusty downpipes, barred ground-floor windows, ivy
on a share of the facades, weeds at the walls and on the roofs of damaged buildings, young birches
growing out of the rubble of ruins. Walls moved to tileable wall sheets (no more stretched textures on
tall faces). A vegetation kit (weeds, bushes, birch, dead tree) is scattered by the fill per zone,
including perimeter-block yards. The fill is terrain-aware (it skips or downsizes lots the ground
cannot take instead of failing), avoids slivers between buildings, and spawner sites get vanilla
clutter cutters under ground floors (P12). Gates PASS (`reviews/d59_gates.md`), renders
`reviews/img/d59_*.png`, in-game rows TESTING §24.

## 12. Exporter port, package split, content pass (D60)

The P3D export no longer depends on an add-on. A standalone MLOD writer turns the generators'
data into the same files Arma Toolbox wrote, so the toolchain works in plain Python, in Blender
4.2 and in Blender 5.x next to the DayZ Object Builder extension (B10 resolved). The 939 MB
`sky_city` is split into six packages, the largest about 250 MB. New content:
- two masonry office floors and the HQ floor (dark curtain wall, bronze fins and spandrels,
  granite piers, the only 4K atlas);
- a retail-frontage lobby (Lobby_B), which keeps the keycard door and security room;
- an enclosed skybridge between two tower roofs, with layout support and lane proofs on every
  roof variant;
- Tower A weathering;
- an optional vanilla-tree hook (P13).

The manifest has no planned buildings left. Tall towers are layouts (`placement/skyline_template.yaml`).
Gates PASS (`reviews/d60_gates.md`), renders `reviews/img/d60_*.png`, in-game rows TESTING §25,
session plan `TEST_SESSION.md`.

## 13. City life: the 23 brainstorm ideas (D61)

The friend's 23 ideas are on `ROADMAP.md`, each with its feature, phase and status. D61 builds everything
that does not need new animation, terrain or vehicle simulation:
- **Venues**: hypermarket under harsh cold light, a 3-level Dead Island mall round a glass atrium, the KINO
  cinema, a bar, a kindergarten with a rusty playground, a football clubhouse, and a church with shrouded
  hanged figures.
- **Specials**: the Pripyat funfair, the landfill, the football ground, car parks (one with a sealed metro
  hatch), bins, hydrants, siren towers and a garbage-truck wreck.
- **Roads**: streets jammed with vanilla wrecks (walkable gaps only), an elevated viaduct as the drivable
  bypass, a road tunnel, and the deadly bridge (military loot, sniper nests).
- **Gameplay**:
  - search bins, dumpsters, the garbage truck and landfill mounds; the mall rails and cinema trunks give
    costumes and evening dresses;
  - bar stock and vodka/beer with a dose model: heals, blur, vomiting;
  - wet hydrants work as wells;
  - hordes downtown;
  - a city alarm every 45-90 minutes with a procedural siren that pulls infected in.
All decisions are server-side and every collection is bounded.

Creatures (dogs, rats, horses) wait on a decision: the public mods need the author's authorisation, or we
build our own. Sewers and the metro need a custom terrain. Drivable buses and trucks need a vehicle
simulation. Gates PASS (`reviews/d61_gates.md`), renders `reviews/img/d61_*.png`, in-game rows TESTING §26,
new pending checks P14-P20.

## 14. Creatures (D62)

Real animals need a rig, animations and an AI graph, which the procedural toolchain cannot make. Vanilla
scripts cannot make an animal follow a player. D62 therefore delivers the friend's creature ideas as
static models driven by server rules:
- **Guard kennel**: a deployable doghouse with its dog. While the owner is offline (up to 48 h), nobody can
  loot it, carry it or damage it, and strangers make the dog bark. The bark is a procedural sound that also
  draws infected.
- **Rat nests**: they bite players who stand in them (damage, bleeding, salmonella) and gnaw nearby bases. A
  burning fire or a guard dog nearby stops them.
- **Horse**: riding is blocked; a horse carcass sets the mood.

Security and performance reviews ran on all D61-D62 scripts and every finding was fixed (`reviews/d62_gates.md`).
In-game rows: TESTING §27; pending checks: P21-P24.

## 15. Underground and terrain (D63)

The underground is cut-and-cover, so it works only on a custom terrain: a DayZ terrain cannot have holes, and
a vanilla map cannot be dug.
- **Kit**: brick sewers with walkways, pipes and a channel whose water rises with heavy rain, a junction, end
  caps and stairs to street openings. The metro has tunnels, buffer-stop ends and a tiled station with an
  island platform and a stair to the street.
- **Layout**: the layout generator lays both networks under the streets. It also writes the vanilla
  underground darkness triggers and a list of trenches.
- **Terrain**: the new `terrain/gen_terrain.py` builds Terrain Builder inputs in Bohemia's sample format: a
  1 m heightmap with the city plateau, trenches and a river valley, the surface mask, the colour map and the layers.
- **Flooding**: rain floods the sewers over 10 minutes and drains them over 30. Clothes get soaked, and
  players take damage when the water is over their head.
Building the .wrp itself needs Terrain Builder on Windows and a map name (TESTING §28, P25-P29,
`reviews/d63_gates.md`).

## 16. Vehicles (D64)

A drivable bus or garbage truck needs a model rigged on a vanilla vehicle's skeleton and physics. Those files
are binarized game data, so a generated rig would be guessed, and the project does not ship guesses. D64
delivers:
- a parametric vehicle body generator: two new wrecks, a faded LiAZ-style city bus and the rebuilt garbage truck;
- intact reference bodies, with documented selection and memory names, for a modeller;
- a full pipeline spec (V3S donor) and config/script templates.
Driving waits on a modeller (`vehicles/VEHICLE_SPEC.md`, TESTING §29, P30-P31).

## 17. Refinement (D65)

- **Search**: hypermarket shelf ends give food and drinks, and the clubhouse lockers give sportswear. Both use
  server tables of verified vanilla items.
- **Ambience**: the city got a sound layer, made procedurally like the siren: the hypermarket tubes hum with a
  dying ballast, the sewers drip with a tunnel echo, and the Ferris wheel creaks in the wind. A client-only
  director plays at most three of the nearest loops (TESTING §30, P32).

## 18. Asset quality (D66)

The weakest street props were rebuilt from boxes into real objects:
- a Soviet tipping street urn;
- a wheeled 1100 L dumpster;
- detailed fire hydrants with flanges, flutes, a bonnet, and caps on chains.

The underground got its identity: station name boards with the M roundel, exit and line boards, a sewer
warning, graffiti and sagging cables. Before/after renders: `reviews/d66_gates.md`.

## 19. Variety (D67)

Streets got their furniture: Soviet bus shelters with a smashed pane, poster-wrapped advertising columns and
phone booths, placed along the sidewalk away from lamps and car jams (citylife: 14 bus stops, 23 columns,
14 booths; 521 entities). Underground, every station now carries its own name (four variants), and seeded
dead ends break the routine: a collapsed sewer vault and metro tunnel you climb over, and a flooded sewer
dead end. Renders and gates: `reviews/d67_gates.md`.

## 20. Ambience and search (D68)

The city got three more procedural loops: wind breathing through the metro tunnels, flags flapping on the
stadium stand (which now flies three ragged club flags) and tinny muzak still playing in the mall. Wiring them
up showed that the sewer drips were playing at street level; every underground sound now comes from the
tunnel floor and stays underground. Players can also search the metro ticket kiosks (papers, snacks, a torch)
and the bin at every bus stop. Gates and reviews: `reviews/d68_gates.md`.

## 21. Venue variants (D69)

Every venue now has a second look: a brick universam, a two-floor panel shopping centre, an ochre cinema, a
grey beer hall and a panel football clubhouse, each with its own weathered sign. Venues are no longer only
hand-placed: the city generator now drops them into blocks where they fit, rarely (each block rolls once
per venue type; a mall in about one large downtown block in eight). The test city now gets a bar from the fill. Renders and gates:
`reviews/d69_gates.md`.

## 22. Asset quality: stand, booth, kennel (D70)

The fair booths became real shooting galleries (prize shelves with plush toys, tin ducks, chained air rifles,
a valance and a dead bulb string), the guard kennel got a shingled roof, trims, straw and a bone, and the
stadium stand gained a middle level of detail so its seats no longer vanish at once. Before/after renders:
`reviews/d70_gates.md`.

## 23. Civic search spots (D71)

Clinics now have medicine cabinets, police stations steel gear lockers and post offices a sorting rack full of
old letters, each searchable for its own kind of loot (medical supplies, police kit without weapons, paper and
tools). A new check proves every search spot in every building can be reached; it caught locker spots that had
been sealed inside ruined clubhouses. Gates and reviews: `reviews/d71_gates.md`.

## 24. Ruin exits and search UX (D72)

No ruin can trap a player any more: rubble heaps are now gentle enough to climb out over, a floating sliver of
shelving was cleared from a collapsed department store, and the city test fails if any ruin room can be dropped
into but not left. The Search prompt no longer shows through walls, and a blocked search says why. Gates and
reviews: `reviews/d72_gates.md`.

## 25. Street kit close-up (D73)

The pieces players walk past most were still simple boxes. Street lamps now have a tapered pole, a bolted
plinth and a cobra-head lamp; jersey barriers have faded hazard stripes and chipped ends; planters hold a dead
shrub; sedan hulks have windows, chrome bumpers, flat tyres and a gutted engine under a sprung bonnet. The guard
dog in the kennel keeps its shape at mid range. Renders and reviews: `reviews/d73_gates.md`.

## 26. Street kit pass 2 and car-jam variety (D74)

Billboards now stand on I-beams with a ladder, a walkway and lamps, their posters peeling at a corner; traffic
lights got visors, a braced arm and a push-button box; the burnt box van has ribs, windows and a rear door
hanging open. Car jams mix intact, burnt-out and overturned saloons. A new test checks every prop's collision
for slits between its parts; it found and closed six, including a gap behind the garbage truck's cab.
Reviews and renders: `reviews/d74_gates.md`.

## 27. Street surfaces (D75)

Every district street now has a chamfered concrete kerb, a gutter strip and a paver edge, and the asphalt texture shows sparse cracks, sealed crack lines, oil stains and bleached patches. About 4 in 10 straight tiles are a worn variant with patched asphalt and a filled trench. Viaducts got ribs underneath, spalled concrete with rebar, expansion joints and drain spouts with rust streaks. The perf review cut the new kerbs from 288 to 16 triangles per tile.
Reviews and renders: `reviews/d75_gates.md`.

## 28. Interior props close-up (D76)

The office and flat furniture that fills every tower floor was made of plain boxes. The reception desk now has a fluted walnut front and a marble top, desks and cubicles carry monitors, keyboards and papers, the server rack and vending machine got framed fronts and vents, lockers have louvres and handles that swing with their doors, the kitchenette has a real sink, tap and tiled splashback, and the sofa, bed and extinguisher are properly shaped. Collision, doors and loot points are unchanged; the reviews removed hidden faces and z-fighting that showed as black patches.
Reviews and renders: `reviews/d76_gates.md`.

## 29. Texture depth (D77)

Wood shows boards, grain and pores; fabrics have a twill weave; sidewalk slabs have bevelled edges, chips, mossy joints and the odd cracked or sunken slab; concrete gets blowholes and hairline cracks and, like metal and stone, no longer shows a seam every texture repeat. A new check found that the stone cladding referenced an ambient-occlusion map that was never generated (a missing texture in game); it is generated now and the check runs on every asset build.
Reviews and renders: `reviews/d77_gates.md`.
