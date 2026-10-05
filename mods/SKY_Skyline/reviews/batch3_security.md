# Batch 3 security gate (security-auditor)

## Batch 3 security gate (interior props, sky_props), commit dd30941

**Result: 0 Critical, 0 High, 0 Medium, 3 Low, 5 Info.**

This was a static review only. Nothing was built or run in DayZ, and `P:\scripts` is not mounted on this machine. Where I describe vanilla behaviour without a source, it is marked "verify". The batch adds no scripts, RPCs or actions. The prop doors use only the vanilla door actions, which already re-check their conditions on the server, so the client-to-server checklist has nothing new to apply to.

### Critical
None.

### High
None.

### Medium
None.

### Low

**L1. One `DOOR_SWING_SIGN` value cannot open every prop door the right way.**
- Where:
  - `/home/user/DayZModding/mods/SKY_Skyline/assets/skyspec.py:64-66`
  - `/home/user/DayZModding/mods/SKY_Skyline/assets/gen_configs.py:190`
  - `/home/user/DayZModding/mods/SKY_Skyline/assets/blender/build_props.py:118-119` (flap), `:137-138` (lockers), `:193-194` (cabinet)
- What is wrong:
  - The spec comment says `+1` is meant to open doors "INTO the room/cabinet". For a locker or cabinet door, that intent is itself wrong: the leaf would swing into the carcass.
  - The doors are also built in different orientations. The flap hinges on a +X axis with the leaf along +Z. The locker and cabinet doors hinge on a +Z axis with the leaf along +X.
  - With the same sign, the flap therefore rotates toward −Y (out) while the locker and cabinet doors rotate toward +Y (in), or the reverse. No single value gets all three right.
- What happens if it swings inward:
  - The cabinet's glass leaf (0.38 m wide, 1.4 rad) reaches about y = +0.11 m, which is behind the cabinet's back plane at y = 0. Its Geometry and Fire Geometry stick into the wall it is mounted on.
  - On a SKY partition (`WALL_T` 0.25) that stays inside the wall. On a thinner vanilla wall, or if the cabinet is recessed, a collidable glass pane sticks out into the next room.
  - The locker leaves clip their own dividers (cosmetic only).
- Why it is not worse: it adds geometry rather than removing it, so it cannot be used to see through walls.
- Fix:
  - Give each door its own swing sign in `door()`, for example a `swing=±1` field, or a negative `scale` for the flap.
  - Change the P1 wording to "outward" for prop doors.
  - Add a check to `test_kit.py` (the door block at line 103) that rotates each leaf's Geometry to `angle1` and fails if it leaves the prop's footprint behind the back plane.
  - Verify in Diag together with P1.

**L2. A player with a lockpick can probably lock the prop doors (verify).**
- Where: `/home/user/DayZModding/mods/SKY_Skyline/addons/sky_props/config.cpp:49-64, 96-137, 211-226`
- What is wrong:
  - Unlike `Land_SKY_TowerA_Lobby.c:126-130`, which returns `EBuildingLockType.NONE`, the props use plain `HouseNoDestruct`. They therefore inherit vanilla `Building.GetLockCompatibilityType`, which is probably lockpick-compatible.
  - The locker cavities (about 0.28 x 0.46 x 1.7 m) are too small for a player but can hold items, which can be thrown or placed in while the door is open.
- Exploit: someone stashes loot, closes the door and locks it. The stash can then only be opened with a lockpick. The same trick can grief the vending flap or the cabinet.
- Impact: low. These are ordinary vanilla mechanics, nothing is duplicated, and lock state on spawned objects probably resets on restart.
- Fix (any one of these):
  - Add a 4_World script class `Land_SKY_Props_Base extends HouseNoDestruct` that overrides `GetLockCompatibilityType` to return `EBuildingLockType.NONE`.
  - Make the doors visual-only (no Doors class).
  - Accept and document the behaviour.
- Verify first against `3_game/entities/building.c` and `actionlockdoors.c:39`.

**L3. The `FragGrenade` armor name is still unverified (P5) and now also covers 5 prop door zones.**
- Where: `/home/user/DayZModding/mods/SKY_Skyline/addons/sky_props/config.cpp:72, 85, 145, 158, 171, 184, 234, 247`
- Risk: if the real explosion armor class has a different name, explosives may damage or ruin the door zones. There is nothing behind these doors worth protecting, so impact is minimal. This carries over from the lobby door.
- Fix: resolve P5 and regenerate with `gen_configs.py`.

### Info

- **I1. Nothing for players to hide inside.**
  - Every enclosed space is smaller than a player: locker compartment 0.28 m wide, cabinet 0.36 x 0.23 m, vending machine and server rack are solid boxes.
  - The cubicle is open on one side.
  - Players lying prone under the desks (top at 0.72 m) is the same as vanilla tables.
- **I2. Collision and View Geometry are consistent.**
  - Nothing has View Geometry without matching visuals, so nothing is an invisible vision blocker.
  - Door leaves are in Geometry, View and Fire Geometry on the same bone, so they animate together.
  - Visual-only parts (monitors, cushions, pillow, modesty panel, reception transaction top, extinguisher body) cannot be used to see through walls.
  - Door damage zones take 0 damage from everything, so the doors cannot be destroyed (apart from L3).
- **I3. Doors cannot push players through walls or block corridors.**
  - Open leaves reach at most 0.29 m (locker), about 0.38 m (cabinet) and 0.19 m (flap). They never sweep sideways past the prop's footprint.
  - Doors can only be locked while closed.
  - Recommendation: when these props are placed in `placement/layout.yaml`, keep at least 1 m of clearance in front of door-bearing props.
- **I4. Artwork contains no brands or logos.**
  - The only text is "COLD DRINKS", "DANGER 400V" and "FIRE" (`/home/user/DayZModding/mods/SKY_Skyline/assets/textures/gen_textures.py:394, 414, 433`), drawn with Pillow's built-in default font.
  - The monitor cell has no UI branding, and there are no real-world references.
  - Optional: the red vending front with white text is generic, so it needs no change. Changing the colour would remove any resemblance to a drinks brand's red-and-white livery.
- **I5. Key and secret hygiene: clean.**
  - `git ls-files` and the full history (`git log --all --diff-filter=A`) contain no `*.biprivatekey`, `*.bisign`, `*.bikey`, `*.pbo`, `workspace.config.json` or rendered `server/serverDZ.*.cfg`.
  - The commit diff contains no password, token, webhook or private-key strings.
  - The P3D files and the review PNG are Git LFS pointers.
  - `git config core.hooksPath` is `.githooks`. `/home/user/DayZModding/.githooks/pre-commit` blocks keys, signatures, PBO/EBO files, local configs and admin/RCon passwords.
  - `.gitignore` covers all of these (confirmed with `git check-ignore`).
  - BattlEye: no new script or RPC traffic, so no filter exceptions are needed. No `-filePatching` or diagnostic-only code is added.

GATE: PASS
