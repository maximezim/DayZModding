# Batch 4 security gate (security-auditor)

Security gate: SKY_Skyline Batch 4 (floor and roof variants), range f73d587..fcc7f4c

This was a static review only. Nothing was run in DayZ or Blender. I did not run any Python either, because building the modules would write `__pycache__` into the repo. I checked the geometry by working through the wall coordinates in `build_floors.py` against `build_towera.py` and `skygeo.wall_x/wall_y` (`skygeo.py:299-313`).

Result: 0 Critical, 1 High, 2 Medium, 3 Low, plus Info.

## High

**H1. Floor_Apartments has two apartments with no door. The SE and NW apartments are fully sealed rooms.**
- Location: `/home/user/DayZModding/mods/SKY_Skyline/assets/blender/build_floors.py:51-60`
- How the walls work: `partitions()` treats an "x" wall as running along X at y=c, and a "y" wall as running along Y at x=c. Its openings are 2.1 m high.
- The hall ring is x ±5.5 by y ±7. The party walls are x=0 (outside the hall in Y) and y=0 (outside the hall in X). Openings that lead out of the hall:
  - south wall (y=-7): x(-1.5,-0.3) leads to SW
  - west wall (x=-5.5): y(-1,0) leads to SW
  - east wall (x=5.5): y(0,1) leads to NE
- Every other opening is internal to one apartment: (-8,-7) and (7,8) on both y=±7 walls, outside the hall's X span.
- SE (x>0, y<-7, plus x>5.5, -7<y<0) and NW (the mirror image) have no opening to the hall or to a neighbour. The partitions are solid in Geometry, View and Fire (`pen_masonry`), and the glass facade has Geometry. So each one is a closed volume of about 100 m², on every Apartments storey (10 per tower with 5 typical floors).
- Exploit scenarios:
  - A player who logged out at that spot logs back in trapped. This happens when a site's floor variant changes (office to apartments in the batch-5 layouts) or after a desync, vault or teleport glitch through a 0.25 m partition. The only way out is suicide.
  - If anyone gets in, it is a "glitch stash" or hideout nobody else can reach. Walls and slabs stop bullets. If loot is later added to this class, those points would also be unreachable.
- This also contradicts the design text: "4 apartments around a hall ring" (`skyspec.py:397`, `config.cpp:22`).
- `test_kit.module_checks` (`/home/user/DayZModding/mods/SKY_Skyline/assets/blender/test_kit.py:109-127`) has no reachability check, so this passed.
- Fix:
  - Give SE an opening from the hall at the same 2.1 m opening height: for example add `(-1.0, 0.0)` to the east hall wall (x=5.5, line 56), or `(0.3, 1.5)` to the south hall wall.
  - Give NW one the same way: for example add `(0.0, 1.0)` to the west hall wall (line 55), or `(-1.5, -0.3)` to the north hall wall. Both stay clear of `CORE_CLEAR`.
  - Add a reachability test to `module_checks`: rasterise the Geometry components at about 0.25 m and z 0.1..1.9, flood-fill from the core stair and elevator clear zones, and fail if any floor cell larger than about 1 m² inside the footprint is unreachable.

## Medium

**M1. The roof-drop positions now differ by roof type, but they only live in the Blender script.**
- Locations:
  - `build_floors.py:30` (`ROOF_DROPS_CLEAR`) and `:150-151`, `:166-167`
  - `/home/user/DayZModding/mods/SKY_Skyline/placement/sky_layout.py:147-150`, which writes the `cfgeventspawns` positions from `S.ROOF_DROPS`, the helipad values at (±8, ±8)
  - `skyspec.py:223`
- The garden and mechanical roofs moved their `roof_drop_N` memory points to (±8, ±2) (D33). That is correct: the points are clear of the core (|x|≥3), the planters and HVAC units (|y|≥6.5) and the parapet (3.75 m away).
- The problem: the layout and event generator still uses the helipad (±8, ±8), and those positions are inside the planters and HVAC units.
- Exploit scenario: once batch 5 places a garden or mechanical roof, `StaticSKYRoofDrop` supply boxes spawn inside the planter or HVAC Geometry. That gives loot that can only be reached by clipping, or that can't be reached at all, and a crate overlapping collision can launch or snag players.
- `test_kit` does not check drop points against Geometry.
- Fix:
  - Move the drop positions into `skyspec` per roof class, for example `KIT[...]["roof_drops"]`, with the helipad keeping `ROOF_DROPS`. Have both `build_*` and `sky_layout.py` read them from there.
  - In `module_checks`, assert that each `roof_drop_N` memory point and a crate-sized box around it (about 1.5 x 1.5 x 1.5 m) does not overlap any Geometry component, and stays at least 1 m from the parapet.

**M2. Plant units on the mechanical floor leave 1.0 m of headroom under the next slab.**
- Location: `build_floors.py:110-114`
- The units are 2.2 m tall, solid in Geometry, View and Fire. The next module's slab underside is at WT = 3.2.
- Exploit scenario: if the engine's climb test accepts a 2.2 m climb, a player on top is pushed against the slab above. The head or the third-person camera can then clip into or through the 0.3 m slab and look into the floor above (slab peeking). This is unverified, because it depends on DayZ's climb-height and head-clearance rules.
- Fix: either make the units full height (top at WT, so nothing is climbable), or keep them at 1.2 m or less. Then add a TESTING.md row: try to climb each unit, and check the camera against the slab above.

## Low

**L1. Roof_Garden shrubs exist only in Res0.**
- Location: `build_floors.py:144-149`
- The foliage cards have no Res1 and no View Geometry. A player hiding prone behind a shrub is concealed for viewers who draw Res0, but fully visible to anyone drawing Res1 (low object detail or medium range).
- Fix: add one simplified card pair in Res1, or treat the shrubs as purely decorative.

**L2. Planters have no View Geometry.**
- Location: `build_floors.py:140`
- The loop covers `res0, res1, geo, fire` but not `view`. Infected and animals can see through 0.5 m planters while bullets are stopped. This is minor, but it is inconsistent with the HVAC units, which include `view`.
- Fix: add `"view"` to the loop.

**L3. Parapet edges are easy to step over from roof furniture.**
- Locations: `build_floors.py:130-132` and `:138`, `:159`
- The parapet is 1.1 m high and vaultable from the slab, as on the helipad. The planters sit 0.75 m from the parapet with their tops at 0.5 m, so from a planter the parapet is effectively 0.6 m.
- The risk is self-inflicted falls only. There is no teleport or push vector.
- Fix (optional): raise the parapet to about 1.3–1.5 m on these roofs, or move the planters and units at least 1.2 m away from the parapet. Add a row to TESTING.md.

## Info (no action)

- **Louvre facade:** it is opaque and blocks both view and bullets. `louvre_facade` (`build_floors.py:91-103`) emits matching boxes 0.12 m thick in Res0–2, Geometry, View and Fire (`pen_metal`). The corners overlap, so there are no gaps, and Res3 is one band. Penetration through 0.12 m of `pen_metal` is still subject to the open PENETRATION verification. The ducts and fan housings exist only in Res0 and have no collision; they are cosmetic and overhead.
- **No see-through at distance:** partitions are left out of Res2 and Res3. That is harmless, because the Res2 and Res3 facade uses `glassfar`, which is an opaque `_co` texture (`gen_textures.py:146-154`). So there is no low-LOD wallhack into the rooms.
- **Seams:** none between stacked modules. Slab (-0.3..0) plus walls or facade (0..3.2) plus the next slab at 3.2 is continuous. The partitions end at the glass inner face (e = HW − CT). The core-hole edges and Roadway are the same as the frozen Tower A floor, and Roadway over the hole is asserted absent (`test_kit.py:126-127`). Core-door clear zones are checked for floors and roofs.
- **Hotel:** every room, suite and the corridor ring is reachable. Openings have no door leaves, so they can't be locked. Players can still block doorways with vanilla base building, which is a server-rules matter.
- **Loot:** none of the new classes appear in `mapgroupproto_sky.xml`, `types.xml` or `events.xml`, so no loot is exposed yet. Fix H1 before adding loot to Floor_Apartments.
- **Client-to-server surface:** none. The batch adds no scripts, RPCs or actions (config-only `HouseNoDestruct` classes). `Land_SKY_Props_Base.c` (batch 3) only returns `EBuildingLockType.NONE`. No DIAG or filePatching paths were added.
- **Tower A:** the `build_towera.py` change is the exit-code wrapper only (lines 434-442).
- **Key and secret hygiene: clean.**
  - The range's diff and the `git ls-files` listing contain no `*.biprivatekey`, `*.bisign`, `*.bikey`, `*.pbo`, `workspace.config.json` or rendered `server/serverDZ.*.cfg`. Across all history (`git log --all --diff-filter=A`), the only `serverDZ` files ever added are the two placeholder templates under `server/templates/`.
  - No password, token, webhook or private-key strings were added in the range.
  - `git config core.hooksPath` is `.githooks`. `/home/user/DayZModding/.githooks/pre-commit` still refuses keys, bisign, bikey, pbo, ebo, `_handoff`, bundles, `workspace.config.json`, `server/serverDZ.*.cfg` and admin/RCon passwords, and `.gitignore` covers the same files. The other hooks are the standard Git LFS stubs.
- **BattlEye:** no impact.

Files referenced:
- /home/user/DayZModding/mods/SKY_Skyline/assets/blender/build_floors.py
- /home/user/DayZModding/mods/SKY_Skyline/assets/blender/test_kit.py
- /home/user/DayZModding/mods/SKY_Skyline/assets/blender/build_towera.py
- /home/user/DayZModding/mods/SKY_Skyline/assets/skyspec.py
- /home/user/DayZModding/mods/SKY_Skyline/placement/sky_layout.py
- /home/user/DayZModding/mods/SKY_Skyline/addons/sky_floors/config.cpp
- /home/user/DayZModding/.githooks/pre-commit

GATE: FAIL (H1: sealed SE and NW apartments on Floor_Apartments)
