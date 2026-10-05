# Batch 5 security gate (security-auditor)

## Security gate: SKY_Skyline Batch 5, range 103cc57..bc4d299 (static review)

I didn't edit anything. I ran some probes under the scratchpad with PYTHONDONTWRITEBYTECODE=1:
- A probe layout and survey run through `sky_layout.py --strict`, writing to `scratchpad/probe_out`.
- `test_kit.batch5_checks` run headless, with `bpy`/`bmesh` stubbed out. It reported **0 failures**.

### Critical
None.

### High
None.

### Medium

**M1. Decals can be placed on the glass curtain wall and across the lobby entrance, which gives one-way concealment. This is the same problem D16 was written to stop.**
- Location: `/home/user/DayZModding/mods/SKY_Skyline/placement/sky_layout.py:274-303`.
- What the generator checks: the decal fits within ±half the face width and within 0..facade height. It then places it at the footprint edge + `DECAL_OFFSET`.
- Why that is a problem:
  - Every floor except the mechanical floor has a full-height facade. So does the lobby. These are `facade()` panes (`build_towera.py:103-112`): transparent `glass` panes that are double-sided in Res0.
  - Decals are render-only, single-sided, outward-facing quads (`build_kit.py:471-478`).
  - Result: from outside, the graffiti covers the window. From inside, its back face is culled, so the view out is clear.
  - D16 only requires "a surface that has Geometry". Glass has Geometry, so a decal on glass passes D16's wording while defeating its purpose.
- Second case, the lobby entrance:
  - The lobby's south entrance (u -1.5..1.5, z < 3, `build_towera.py:193`) has no glass and no Geometry.
  - A decal there is free-standing in the doorway. My probe `{face: S, u: 0, z: 0.5}` was accepted with `--strict` PASS.
- The template already ships two of these at player height on lobby glass:
  - `district_template.yaml:65` (T1 S face, Graffiti_B at z 0.2)
  - `district_template.yaml:67` (T3 E face, Cracks at z 0.5)
  - Both are also in `/home/user/DayZModding/mods/SKY_Skyline/placement/out_district/sky_objects.json`.
- Exploit: a player crouches in the lobby behind the graffiti. They can see and shoot out, but people on the street can't see them.
- Fix:
  - Add a per-module solid-zone map to skyspec, e.g. `DECAL_ZONES`: mechanical-floor louvre storeys, the slab-edge bands, and any opaque podium parts.
  - Have the generator reject any decal that overlaps glazing or an entrance opening.
  - Reword D16 to "opaque Geometry surface".
  - Move or remove the template's decals and regenerate `out_district`.
  - Minor, for QA: Res0 mullions stick out 0.04 m past the plane, while decals sit at 0.015-0.025 m, so the mullions show through decals.

**M2. Street tiles outside the survey get an arbitrary Y with no check, and survey objects are never tested against tiles.**
- Location: `sky_layout.py:354-368`.
- First part, tile height:
  - If the survey has no samples under a tile, there is no error. Y falls back to `streets.base_y`, then `site.base_y`, then `0.0`.
  - My probe (survey covering only the tower area, 5x5 street grid) gave `--strict` → `PASS (with warnings)`, rc 0, with all street tiles at Y = 0.0 (e.g. `Land_SKY_Street_Straight at [976.0, 0.0, 1988.0]`). Terrain there was 150 m.
  - With `site.base_y` set, tiles end up floating above unsurveyed lower ground. That recreates the batch-1 M1 under-road void: a hiding spot shielded from fire.
  - The template's own instructions (halfW 56) make it easy to under-cover the district.
- Second part, objects under tiles:
  - Survey `objects` are only tested against tower footprints (`:246-251`). Tiles and street lights are never tested.
  - So a tile can be laid over an existing building, wall or rock, or over a cellar or entrance, and `--strict` still passes.
- Fix:
  - When a survey is present and `ys` is empty, raise an error ("street tile (i, j) has no survey samples"), mirroring the tower check at `:231-232`.
  - Run the foreign-object test for every tile quad and light position: error on `Land_*`, warn on vegetation.

### Low

**L1. In `--strict`, non-`Land_` survey objects inside a tower footprint are only a warning, and only the object's centre point is tested.**
- Location: `sky_layout.py:246-251`. This is unchanged from earlier batches, but districts multiply the exposure.
- Objects with an empty type are reported as their `GetDebugNameNative()` model name (`SKY_SiteSurvey.c:119-121`). That covers rocks, walls and fences. My probe's `rock_bright_spike1` inside the footprint gave only a WARN, with rc 0.
- Exploit: a rock or wall poking through the lobby or the T2 security room becomes a collision seam that players can glitch through.
- A `Land_` object whose centre is just outside the footprint but whose body overlaps it isn't caught either.
- Fix:
  - Under `--strict`, raise an error for any object that isn't on an explicit vegetation allow-list.
  - Have the survey script export bounding radius or extents, and test overlap instead of only the centre.

**L2. The yaw convention for objects placed off the tower centre (props, decals, roof drops, lights) has never been checked in the engine.**
- Location: `sky_layout.py:50-53`, `:209-218`, `:265-267`, `:301`.
- `test_kit` only validates FURNISH in the model frame. P-03 checks only the tower's own yaw, and centred modules look the same under either convention.
- Which towers are exposed:
  - `office_open` is asymmetric, and the template puts it on T4 at yaw 270.
  - If DayZ's yaw turns out to be mirrored relative to `rot()`, cubicles land in the SW office partitions or on top of loot points.
  - Apartments, garden/mechanical roof drops and the hotel at 180 are symmetric, so they're safe either way.
- Fix:
  - Add a PENDING/TESTING row: spawn one asymmetric floor with props at yaw 90 and check the props against the walls.
  - Until that passes, have `--strict` reject towers whose yaw isn't 0 or 180 when they carry an asymmetric furnish set.

**L3. Output files are written even when the run fails.**
- Location: `sky_layout.py:424-453`.
- `sky_objects.json` and the snippets are written with a FAIL status. The workflow says to deploy `placement\out\*` (TESTING P-03), so a failed layout could be deployed.
- Fix: on errors, write only the report, or write `*.FAILED.json`.

**L4. Roof-drop crate orientation and yaw.**
- Location: `sky_layout.py:431-433`.
- Every drop is written with `a="0"`. The crate clearance in `test_kit.py:189-195` assumes a 1.5 m square aligned to the model axes.
- Tower yaw is free, so at 45° the crate's corners reach about 0.31 m further relative to the roof (plant units, parapet).
- Fix: restrict tower yaw to multiples of 90, or test against the circumscribed radius (about 1.06 m). Alternatively, emit `a` = tower yaw once the meaning of `a` is verified.

### Info

- **Trust boundary, class names:** no injection is possible.
  - Floor and roof variants, furnish sets, prop classes and street kinds all come from skyspec dictionaries.
  - Decal classes are checked against `KIT[base]["cls"] | variants` (`:285-288`).
  - An unknown tower `type` raises a KeyError and crashes the run; it does not inject anything.
- **Trust boundary, files:**
  - Output filenames under `--out` are fixed.
  - `site.survey` is joined to the layout directory. Absolute paths or `..` are accepted, but the file is only read, and it is an admin input.
  - YAML strings are echoed into the markdown report. That is harmless.
  - Duplicate tower ids are not rejected: `by_id` overwrites earlier ones and decal caps miscount. Worth adding a check.
- **Loot:**
  - Categories are tools, containers, clothes, food and books only; there are no weapons in the range.
  - Locker loot sits behind 3 hinged, unlockable doors (`build_props.py:145`, D25), so it is fair.
  - `batch5_checks` passes: no point inside Geometry, the core or a prop.
  - Every floor loot point is more than 0.9 m from any furnish prop (LOOT_POINT range 0.6).
  - No duplication path: props are static `House` spawns and can't be picked up.
  - Prop loot raises per-floor lootmax considerably (hotel up to 18 per floor). That is a question for economy-designer, not a security issue.
- **Furniture:**
  - Only named FURNISH sets on typical floors are accepted (lobby and roof are excluded).
  - No prop is in a doorway or a core clear zone, and reachability with a 0.3 m radius passes with furniture in place. This satisfies batch-4 N2.
  - Street lights sit 1.5 m in from the block edge and don't block entrances.
- **Roof drops:** now taken per roof class from `ROOF_DROP_POINTS` (`:264-267`). The output matches helipad (±8, ±8) and garden/mechanical (±8, ±2) after rotation.
- **Infected notes (`economy/README.md`):** no zone placement on upper floors and nothing that traps players.
  - Perf note: one 60 m zone per tower overlaps on the template's 48 m tower spacing, so densities add up.
- **Client-to-server surface:** no `.c` or `config.cpp` changes, no RPC/DIAG/filePatching paths, and no BattlEye impact.
- **Key/secret hygiene, range clean:**
  - No `*.biprivatekey`, `*.bisign`, `*.bikey`, `*.pbo`, `workspace.config.json` or rendered `server/serverDZ.*.cfg` in `git ls-files` or anywhere in history; the only serverDZ files ever added are the two placeholder templates.
  - The diff contains no passwords, tokens or webhooks.
  - `core.hooksPath` is `.githooks`, and the pre-commit hook covers keys, bisign, pbo, the local config and admin/RCon passwords.
  - `.gitignore`, `.githooks` and `.gitattributes` are unchanged in the range.
  - The other hooks in `.githooks` are the standard Git LFS ones.
  - `tools/tests/Invoke-ModValidation.ps1` is untracked and outside the range.

**Files:**
- /home/user/DayZModding/mods/SKY_Skyline/placement/sky_layout.py
- /home/user/DayZModding/mods/SKY_Skyline/placement/district_template.yaml
- /home/user/DayZModding/mods/SKY_Skyline/placement/out_district/sky_objects.json
- /home/user/DayZModding/mods/SKY_Skyline/assets/skyspec.py
- /home/user/DayZModding/mods/SKY_Skyline/assets/blender/test_kit.py
- /home/user/DayZModding/mods/SKY_Skyline/assets/blender/build_towera.py
- /home/user/DayZModding/mods/SKY_Skyline/assets/blender/build_kit.py
- /home/user/DayZModding/mods/SKY_Skyline/addons/sky_scripts/scripts/5_Mission/SKY/SKY_SiteSurvey.c
- /home/user/DayZModding/mods/SKY_Skyline/economy/README.md
- /home/user/DayZModding/mods/SKY_Skyline/DECISIONS.md

Fix M1 and M2 before any district is generated with `--strict` for a live server.

GATE: PASS
