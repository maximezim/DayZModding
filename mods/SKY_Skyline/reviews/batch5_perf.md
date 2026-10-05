# Batch 5 perf gate (perf-engineer)

## SKY_Skyline Batch 5 (economy + placement prep): static perf gate, commit bc4d299

This is a static review only. Nothing ran in DayZ, P: was not reachable, and I edited no files. All paths are under `/home/user/DayZModding/mods/SKY_Skyline/`.

**Summary**
- **No new server script cost.**
  - No `.c` changes, no timers or RPCs, and no dynamic lights. `Land_SKY_StreetLight` is a static emissive model (`addons/sky_street/config.cpp:86-91`), and there is no `ScriptedLight`/`PointLight` anywhere in the mod.
  - Spawner entries keep `enableCEPersistency: 0` (`placement/sky_layout.py:109`), so the batch-3 duplication risk is not reintroduced.
- **Template totals (my own recount matches `out_district/placement_report.md:24-29`):**
  - 323 spawned entities: 32 modules, 45 tiles, 16 lights, 227 props, 3 decals.
  - About 200 CE loot groups: 28 module groups plus 172 prop groups.
  - About 540 loot points.
  - Up to about 360 loot items: module lootmax sums to about 178 and prop lootmax to about 182.
- **The district itself is modest.** The open problems are:
  - The caps are loose or don't bind.
  - The entity budget doesn't count CE loot.
  - Props are 70% of all entities (batch-3 M1/M2 proxy lever still unused).

### High
None.

### Medium

**M1. `PROP_CAPS["per_tower"] = 600` can never be reached, and `ENTITY_CAP` 3000 is per district with no server-wide total.**
- Where: `assets/skyspec.py:358`, `:464`; checked at `placement/sky_layout.py:220` and `:420-422`.
- Why it costs:
  - D38 fixes every tower at 5 typical floors, so the per-floor cap (25) already limits a tower to 125 props. The 600 cap is a hypothesis left over from the 25-floor tower and never fires.
  - 3000 per district is about 9x the template. Under the caps that allows about 20 fully furnished towers (133 entities each) in one district.
  - Every entity is a replicated network object, a static physics body and an `ECE_UPDATEPATHGRAPH` mark (batch3 M2). The cost shows up as join and bubble-entry cost per player in the area, and as server start time.
  - Nothing sums several districts (several `sky_objects.json` files), so a "full skyline" has no ceiling at all.
- Fix:
  - Set `per_tower` to a value that binds: the template's maximum is 60, so use about 70.
  - Lower `ENTITY_CAP["per_district"]` to about 800 (2.5x the template) until S1/S6 measurements justify more.
  - Add `ENTITY_CAP["per_server"]` (hypothesis 2500). Have `sky_layout.py` take several `--layout` files, or a manifest of districts, and fail on the sum.
  - Print a per-tower entity line in the report (modules + props + decals).

**M2. Props are 227 of 323 entities. About 198 of them are non-interactive and could be proxies or merged geometry (batch3 M1 item 2 / M2, still open).**
- Where:
  - `assets/skyspec.py:445-459` (FURNISH).
  - Each instance is added as its own spawned object at `sky_layout.py:218`.
- Detail:
  - Non-interactive props (Cubicle, Desk, Bed, Sofa, Kitchenette, ServerRack) are 40 + 60 + 60 + 38 per tower in T1-T4.
  - Only Locker, VendingMachine and ExtinguisherCabinet have doors.
  - D39 validates sets once in `test_kit`, which is the right structure, and makes the move cheap. Each FURNISH set is fixed per floor class, so it can become a furnished floor variant: the same floor P3D plus the set as proxies or merged Res0/Res1/Geometry.
  - The prop `lootshelves` points then move into that floor's mapgroupproto group, as in vanilla buildings with proxy furniture. That also removes B7 (CE export of spawned props).
- Effect:
  - The template drops from about 323 to about 125 entities, and from about 200 to about 30 CE groups.
  - Spawned props no longer stay drawn through glass at Res2.
- Fix: make it the batch-6 requirement (`Land_SKY_Floor_Hotel_Furnished`, etc.). Keep only the door props as spawned entities.

**M3. Prop loot doubles the district's loot load, and the entity budget does not count it.**
- Where: `assets/skyspec.py:492-510`; `economy/mapgroupproto_sky.xml` (72 proto points).
- Cost in the template:
  - An office floor goes from lootmax 6 to 16 (floor 6, plus 6 cubicles x1, desk 1, kitchenette 1, locker 2).
  - District-wide loot goes from about 178 to about 360 items. Each item is a replicated entity that every player entering the bubble receives, on top of the 323 statics.
  - CE totals stay bounded by `nominal`, so the extra points pull loot into the district from the rest of the map. That makes the district a player and loot hotspot, which is the worst case for server load.
  - The extra 172 groups and about 314 points are small for the CE scan next to vanilla mapgrouppos, so scan time is not the issue. Item density in one bubble is.
- Fix:
  - Count `sum(lootmax)` per district in `placement_report.md` and include it in the ENTITY_CAP check.
  - Cut the prop lootmax so that floor plus props is at most about 8 per office floor. One way: give loot to only 2 of the 6 cubicles by using a `Cubicle` variant without a group, or set floor `lootFloor` to 3 when furnished. Another way: drop Bed loot on hotel floors, which already carry 8 floor points.

**M4. The infected guidance overlaps zones and stacks the targets.**
- Where: `economy/README.md:80-91`.
- Detail:
  - The README says "one zone per tower (radius 60 m), dmax <= 10" and that mixed towers "sum their rows".
  - Template towers are 48 m apart (block centres at +-24 m), so 4 zones of r = 60 m overlap almost completely.
  - Summing the table gives about 13-20 infected targeted per hotel tower, and about 50-70 across the district.
- Cost:
  - Server cost is per infected alive, and multi-storey stair pathing is the expensive case (long paths, path failures through the narrow hotel and apartment doors, batch4 L8).
  - Overlapping territory zones also concentrate respawns where players already are.
- Fix: one `InfectedCity` zone per district centred on the central intersection, with `dmax` 10-15 total. Present the per-floor table explicitly as a ceiling, as the README's own B6 note suggests, not as something to sum. Measure in B6 before any increase.

### Low

**L1. The decal cap is per tower but is called `per_block` (40). `per_tile` (6) is never enforced.**
- Where: `skyspec.py:333`, `sky_layout.py:304-306`.
- Detail: 40 alpha-blended, replicated decals per tower would be 160 in this district. The template uses 3.
- Fix: rename the key to `per_tower` and lower it to about 12. Drop `per_tile`, or enforce it once tile decals exist.

**L2. Street lights.**
- 16 lights on 32 straight tiles is within `LIGHT_CAP` 0.5 (`sky_layout.py:370-379`), and they are static emissive with no light sources. That is fine.
- The counter runs over all straights in i/j loop order (`:372`), so the spacing along an individual street is uneven. Cost is unaffected; only looks.
- The emissive head is lit 24/7 (visual only).
- Optional: count per street line rather than globally.

**L3. The loot export radius does not cover a district.**
- Where: `placement/README.md:30-31` documents `exportRadius: 40`.
- Detail: template towers sit 34 m from the centre with props out to about 51 m, and the survey needs halfW 56. With radius 40, `ExportProxyData` misses outer floors and props, so loot silently does not spawn there.
- Fix: document `exportRadius >= hypot(halfW, halfD)` (about 80 for the template) for districts. Optionally have `sky_layout.py` print the required radius.
- Cost: this is a one-shot survey call. It costs nothing at runtime.

**L4. Survey resolution degrades on large districts.**
- Where: `SKY_SiteSurvey.c:50,91` (MAX_STEP_COUNT 64).
- Detail: the 64-step limit bounds runtime, which is good. But beyond about 128 m the step exceeds 2 m and each 12 m tile gets few samples (about 6 at 300 m), so tile validation at `sky_layout.py:355-366` gets coarse.
- Fix: survey large districts in several pieces, and warn when a tile has fewer than 9 samples.

**L5. Generator complexity: no blocker.**
- Tower-vs-tower is O(T^2) and tower-vs-tile is O(T * tiles).
- Per-tile `survey_ground` is O(tiles * samples), and samples are capped at 4096, so 400 tiles is about 1.6M `inside()` calls, a few seconds.
- The prop aisle check is O(25^2) per floor.
- Nothing breaks on large districts.
- `test_kit.reachability` uses `cell=0.1` while its docstring says 0.25 m (`assets/blender/test_kit.py:109-110`). That is 57.6k cells x about 50 blockers per FURNISH set, which is offline-slow but fine. Fix the docstring, or use 0.25 with the 0.3 m radius inflation.

**L6. Roof drops are fine.**
- 16 positions with `nominal` 1, `saferadius` 200 and `cleanupradius` 300 (`economy/gen_economy.py:62-81`) is negligible.
- Per-roof-class points close batch4 L7 (`sky_layout.py:265-267`).

**L7. Pathgraph and aisles.**
- 1.2 m prop-to-prop aisles (`sky_layout.py:212-216`), plus `test_kit` reachability with a 0.3 m player radius against walls, address batch3 M2's fragmentation concern.
- The pathgraph update is still one mark per entity. M2 is the lever for that.

### Measure it
- **Server start:** in `server\profiles\dedicated\*.RPT`, compare the time from mission load to "Mission read", plus the pathgraph lines, for 0 towers, the Tower A slice and `out_district`. Repeat with an M1-cap stress layout (for example 12 furnished towers, about 1600 entities).
- **Join and bubble cost:** S6 join time, and server FPS (`#monitor` / diag server stats) with 1 and 10 clients standing at the central intersection. Do this after CE has filled the district, and record the loot item count via a CE/admin entity count.
- **CE (B7):**
  - Check that `storage_1\export\mapgrouppos.xml` contains `Land_SKY_<prop>` groups. With radius 40 you should expect only part of the district (L3).
  - Use `script_*.log` and the CE debug output to confirm loot on props.
  - Compare loot items per office floor against the M3 target.
- **Infected (B6):** with the M4 zone, count infected alive in the district over a 30-minute visit. Check the RPT for path-failure spam near hotel and apartment doors, and server frame ms p99.
- **Client:** diag draw-call and frame stats facing the district from 150 m and 500 m, with props spawned vs. removed. This quantifies M2.

GATE: PASS
