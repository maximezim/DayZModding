# Mod development guide for agents: building the best DayZ city mod

How the agents in `.claude/agents/` plan, build, review and ship a DayZ mod with a dense city
scene and many features. Read with `CLAUDE.md` (rules), `docs/ASSET_QUALITY_GUIDE.md` (asset
quality bar) and the mod's own `DECISIONS.md` / `PENDING_VERIFICATION.md`.

**Priorities, in order, when they conflict:**
1. **Security** - never shippable with an exploit (the client is hostile).
2. **Performance** - inside the budgets, measured, server FPS first.
3. **Building quality and mapping** - the reason players come: believable, coherent, well-placed
   architecture and city layout. This is the main creative priority: spend effort here first.
4. Feature count - fewer features done well beat many half-features.

Security and performance are gates (pass/fail); building quality and mapping are where the
quality effort goes.

---

## 1. Ground rules for every agent

- **Never guess an API, class, config key, file path or log text.** Verify on `P:\scripts`,
  `P:\DZ`, the vanilla mission (`mpmissions`) or the DayZ Tools install, and cite `file:line`. If
  it can't be verified, make it a **named parameter** in the spec with a PENDING entry and a
  one-line fix (the P1-P9 pattern), never a hard-coded guess.
- **Never edit vanilla** (game, server install, `P:\DZ`, `P:\scripts`, the vanilla mission copy).
  Extend (`modded class`, config inheritance), or work on **copies** (the `.validation` mission).
- **Single source of truth**: one spec module per mod (`assets/skyspec.py` pattern) holds
  dimensions, budgets, classes, loot, caps and assumptions. Generators read it; nothing is
  hand-edited in outputs; `--check` proves outputs are current.
- **Deterministic generators + committed outputs** (configs, P3Ds, CE files, layouts); binaries in
  Git LFS; regenerate instead of patching.
- **Every untested thing stays `built-unverified`** until the in-game row passes. Status path:
  `planned -> built-unverified -> packed -> tested -> done`.
- **Record decisions** (DECISIONS.md: what, why, revisit-when) for every trade-off, overrun,
  deferral or deviation from a review.
- **Do not create mods, items or gameplay code the user did not ask for**; ask (or record as
  blocked) when a task needs new code beyond the request (e.g. a diag probe).
- Commit per batch with gates passed; push; hand off (bundle + zip) when asked.

## 2. Agent roles and the batch loop

| Agent | Owns | Must not |
|---|---|---|
| `asset-pipeline` | Blender generators, LODs, collision, textures, rvmats, model.cfg | invent engine facts; skip previews/tests |
| `enforce-coder` | Enforce Script, config.cpp, actions, RPC | trust client data; per-frame work |
| `economy-designer` | types, spawnabletypes, events, mapgroupproto, infected zones | put loot inside geometry or on unreachable spots |
| `perf-engineer` (read-only) | budgets, server/client cost, FPS protocol | approve unmeasured caps |
| `security-auditor` (read-only) | RPC/actions, exploitable geometry, secrets, BattlEye | pass a High |
| `qa-tester` | static suites, builds, runs, logs, test lists | edit files other than its review |

**Batch loop** (one coherent batch at a time, lowest propagation risk first):
1. Plan: spec entries, budgets, assumptions as parameters, test IDs.
2. Build: generators + outputs + docs (manifest, TESTING rows).
3. Self-check: static suite green, preview renders reviewed.
4. Gates in parallel: perf, security, QA (QA on a clean `git archive` snapshot).
5. Fix every finding or record a decision; re-gate whatever failed. If a gate fails twice on the
   **same** issue, record it in PENDING and move on.
6. Commit, push, hand off. Then the next batch.

## 3. City scene design (mapping priority)

A great city reads as **one place with a history**, not a pile of assets.

### 3.1 Urban structure
- **Street hierarchy**: arterial (2x2 lanes, 16-20 m), collector (8-12 m, our 12 m tile),
  local lanes and alleys (4-6 m), pedestrian passages. Not every street the same width.
- **Block sizes**: 60-120 m blocks; corner buildings taller and more detailed; alleys and
  courtyards break large blocks (cover, loot, flanking routes).
- **Density gradient**: core (towers, 8-25 floors) -> mid-rise ring (4-8 floors, apartments,
  hotels) -> low-rise edge (2-4 floors, shops, industrial) -> outskirts (garages, depots, fields).
  The skyline should step down, not end in a wall.
- **Landmarks and sightlines**: 1 landmark per district (HQ tower, station, plaza, stadium),
  visible from approach roads; streets aligned so landmarks terminate views; landmarks help
  navigation (DayZ has no minimap by default).
- **Districts with identity**: business (glass, plazas), residential (panel blocks, balconies,
  playgrounds), industrial (warehouses, rails, yards), old town (brick, narrow streets),
  government/military (fenced, high-tier loot). Material palette and props differ per district.
- **Ground plane**: sidewalks, curbs, parking, plazas, green strips, trees, fences, walls,
  bins, signs, wrecks; vary per district. Bare terrain between buildings breaks immersion.
- **Integrate with the map**: connect city roads to vanilla roads; match terrain height (survey);
  transition zones (outskirts, abandoned checkpoints) where city meets countryside.

### 3.2 Gameplay layout
- **Routes**: several ways in and out of every block and building (no single-door death traps,
  no sealed rooms - flood-fill tested); vertical routes (stairs, elevators, roof bridges only when
  asked) with risk at chokepoints.
- **Risk-reward by height and access**: better loot higher up and behind keycards/doors, with
  longer exposure to reach it; street level fast but low tier.
- **Cover and sightlines**: wrecks, barriers, planters, kiosks on streets; avoid endless open
  boulevards and avoid sniper perches that see everything (one-way concealment is a security
  bug: decals on glass, render-only quads in the open).
- **AI**: infected density per floor type, zones at street level, aisles >= 1.2 m, doors >= 1.0 m;
  test pathing on the navmesh.
- **Vehicles**: drivable street grid without snags (tile seams, curbs), parking, dead-ends that
  allow turning.

### 3.2b Building stock (procedural, one grammar)

Ordinary city buildings are not modelled one by one: `mods/SKY_Skyline/assets/blender/build_city.py`
builds every archetype (data in `skyspec.CITY_ARCHETYPES`) from one style grammar (`CITY_STYLE`,
`CITY_SKINS`: bays, wall depth, plinth, string courses, parapet, windows per skin, shared materials)
and in three ruin states (intact / damaged / ruined) through one ruin layer. A new building is a data
record plus, if it has a new use, a floor plan; the look stays coherent by construction.
`CITY_PLAN.md` (generated by `assets/city_progress.py`) holds the estimate for a full city (types,
variants, unique models, placed buildings) and the live progress; keep it current in every batch.

### 3.3 Placement rules
- Everything placed through the layout generator (spec + YAML), validated: survey-based ground
  height, no floating or buried objects, no overlap with vanilla objects, caps per tile/block/
  district/server, snap grid (12 m streets, 90-degree yaws), deterministic output.
- Never ship a placeholder site; `--strict` must pass on a surveyed site before deployment.
- Loot positions from the engine's own export (`ExportProxyData`), never hand-computed.

## 4. Terrain: mapping and modifying (when available)

Three levels, from least to most invasive. Use the lowest level that achieves the goal, and
detect what is available before planning terrain work (`tools\setup\Get-ToolchainStatus.ps1`
reports DayZ Tools, Terrain Builder and the work drive).

### 4.1 Level 0 - adapt objects to the existing terrain (default, always available)
- Spawn objects with `objectSpawnersArr` (mission `cfggameplay.json`); survey the ground
  first (`SKY_SiteSurvey`), pick flat sites, absorb relief with foundation skirts / plinths /
  retaining walls / stairs, and keep everything on one street plane per district.
- Works on any vanilla map, no terrain files touched, easy to remove. This is the SKY approach.
- Limits: cannot flatten hills, move rivers, remove vanilla buildings/trees (only hide or avoid;
  vanilla removal via mission files is possible only for what the mission allows - **verify**
  `cfgIgnoreList.xml` / mission object-removal options before relying on them).

### 4.2 Level 1 - edit object placement in-game (community editors, if the user allows)
- Community in-game editors (e.g. a "DayZ Editor" mod) can place/remove objects visually and
  export placement files. They are third-party: **ask the user** before depending on one, verify
  the export format, and convert its output into the repo's layout YAML / spawner JSON so the
  generator remains the source of truth.
- Still no heightmap change.

### 4.3 Level 2 - a custom terrain (Terrain Builder, full control)
Use when the city needs real terrain shaping (flattened city plateau, embankments, river
quays, cut roads) or a whole new map. Requirements and facts to **verify** in the installed
DayZ Tools before planning:
- Terrain Builder (part of DayZ Tools) and its sample/project structure; the work drive `P:`
  with extracted game data (`Initialize-WorkDrive.ps1`); enough disk (tens of GB).
- Vanilla maps (Chernarus+, Livonia, Sakhal) are shipped binarized: their source terrain projects
  are not part of the game install, so **modifying a vanilla heightmap in place is not possible
  without sources** (verify on the install; never patch vanilla `.wrp` files). Terrain changes
  therefore mean a **new terrain** (own map / own `.wrp`) or a terrain mod built from sources the
  user owns.
- Typical pipeline (**verify each step against the DayZ Tools documentation on the machine**):
  1. Project on `P:\<Mod>\` (lowercase paths), terrain size / cell size / grid chosen up front.
  2. Heightmap (16-bit, e.g. ASC/PNG from a GIS or generated by a script in `mods/<Mod>/terrain/`),
     imported into Terrain Builder; city plateaus flattened to the street plane in the source
     heightmap, not by hand-sculpting after the fact.
  3. Surface masks and layers (satellite/colour map, surface mask -> surface types / clutter),
     generated from the same source data (roads, zones) so they stay consistent.
  4. Roads as shapes/road network; buildings and props imported from the layout generator's
     output (one source: the city layout YAML), not hand-placed twice.
  5. Export/binarize the world (`.wrp`) through the PBO pipeline (`Build-Mod.ps1` binarizes PBOs
     containing `.wrp` through `P:`), plus the map config (CfgWorlds/CfgWorldList entries) and a
     mission folder with its own CE files (mapgrouppos for the new buildings, events, territories).
- Terrain work is a separate mod/PBO (`<Mod>_terrain`), versioned, with generators for heightmap
  edits and masks in `mods/<Mod>/terrain/` (committed sources; large binaries via LFS).
- Gates for terrain: perf (terrain cell size, clutter density, object count per km2, view
  distance), security (no out-of-bounds holes, no under-terrain voids, no unreachable loot),
  QA (walk/drive every road, water, slopes, seams between terrain and objects, navmesh).
- **Never start a custom terrain without the user's explicit go-ahead** (scope, size, map name):
  it is a multi-week project and changes what players need to download.

### 4.4 Decision table
| Need | Level |
|---|---|
| Place a district on an existing map | 0 (objectSpawnersArr + survey) |
| Visual placement of many small props | 0, or 1 with the user's OK |
| Flatten a city plateau, cut roads, quays | 2 (custom terrain) |
| Remove vanilla buildings at the site | verify mission options; otherwise pick another site or level 2 |
| A whole new city map | 2 |

## 5. Features (with their security and performance contract)

Every feature ships with: spec entry, server-authoritative design, budget, test rows, and a
kill switch (config flag) where it touches the server loop.

| Feature type | Rules |
|---|---|
| Doors, elevators, keycards | vanilla actions where possible (server re-runs `ActionCondition`); server validates identity, distance, permissions, rate; no client-chosen targets; doors not lockable unless intended (`GetLockCompatibilityType`) |
| Loot (CE) | mapgroupproto groups with verified names (`cfglimitsdefinition.xml`); points on surfaces, reachable, not in geometry; tiers by height/access; lootmax counted in entity caps |
| Events (supply drops, helicrashes) | vanilla event patterns (`StaticAirplaneCrate`-style); positions from the generator per roof/site; crate clearance tested |
| Infected | territory zones (verified `zombie_territories.xml` format), one per district, densities as ceilings |
| Lighting | emissive materials first; dynamic lights only with a cap and verified classes |
| Interactive props | spawned only where interaction is needed; decorative clutter merged or proxied when verified |
| Anything with RPC | unique mod-scoped ids, small payloads (ids), sender from `PlayerIdentity`, rate limits, no per-frame sends |

## 6. Performance contract
- Budgets per asset category (triangles per LOD, sections, Geometry components, shadow) in the
  spec; `check_assets` enforces; overruns need a DECISIONS entry.
- Entity caps per floor / tower / tile / district / server, including loot items.
- No per-frame script work; throttled timers; remove CallLater/ScriptInvoker on delete.
- Far LODs opaque and 1-2 sections; no blended alpha beyond Res1.
- Measure with the FPS protocol before raising any cap.

## 7. Security contract
- Client is hostile; every server handler validates identity, permissions, target, distance,
  bounds, rate. Clients never decide outcomes; never let client strings choose classes/paths.
- Geometry exploits are security bugs: sealed rooms, wedge gaps, see-through walls, one-way
  concealment, unreachable or in-geometry loot, climbable spots that clip slabs.
- Keys outside the repo; no bisign/pbo/config/passwords committed; release-like tests use
  `verifySignatures = 2`, `BattlEye = 1`, `allowFilePatching = 0`.

## 8. Testing and evidence
- Static: generators `--check`, `check_assets`, geometry tests (watertight, reachability, door
  swing, clear zones), layout tests, script xref against `P:\scripts`, self-test.
- One command: `tools\tests\Invoke-ModValidation.ps1` (build, sign, deploy, mission copy, server,
  logs, PASS/FAIL summary).
- In-game: TESTING.md rows with evidence (log lines with timestamps, screenshots), diag then
  dedicated; FPS_PROTOCOL.md; then AFTER_TESTING.md flips only what tests disproved.

## 9. Anti-patterns (reject in review)
- Hard-coded guesses for engine facts; "it should work" without a test.
- Box-only buildings shipped as final; identical repeated facades; floating or buried props.
- Decorative props spawned as hundreds of entities; decals as large-area grime.
- Hand-edited generated files; placement duplicated in two places (layout + terrain).
- Features without a server-side validation path or a budget.
- Editing vanilla files or the vanilla mission; committing secrets or build outputs.
