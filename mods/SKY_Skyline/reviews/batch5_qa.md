# SKY_Skyline - Batch 5 (economy + placement prep) static QA gate

Date: 2026-10-05. Host: Linux. There is no DayZ, no DayZ Tools and no P: drive, so **everything here is static**.
Every asset, loot group and layout output stays **built-unverified**. This run changed no mod code, asset, config or generator.
It wrote only this file. All mutations and scratch layouts were made in scratch copies.

Gated revision: **`bc4d299`** ("WIP batch 5"). It was taken from a clean `git archive bc4d299` snapshot (scratchpad `qa5/`, cwd `mods/SKY_Skyline`).
Tools: Blender 4.2.23 LTS + ArmaToolbox (scratchpad), python3 + PyYAML, `tools/assets/p3d_inspect.py` (plus a scratch MLOD
reader built on its `Reader` that adds per-component boxes and face materials), the vanilla scripts dump (`dzs/scripts`), and the vanilla
CE reference `ce/dayzOffline.chernarusplus/` (`cfglimitsdefinition.xml`, `mapgroupproto.xml`, `db/events.xml`,
`cfgeventspawns.xml`, `cfgenvironment.xml`, `env/*.xml`).

**Verdict: GATE: FAIL.** Every mechanical check passes (section 1). The gate fails on 1 High (H1): with a survey, `--strict`
passes a district whose street tiles have no survey samples and silently puts them at Y = 0. The documented template workflow
reaches this case. There are also 3 Medium findings (section 6).

## 1. Standard suite

| # | Command | Result |
|---|---|---|
| 1 | `python3 assets/check_assets.py` | exit 0, `44 checked, 0 fail, 5 over budget (hypotheses)`: Floor_Apartments geo comps 40 > 24 / tris 480 > 300 (batch-4 door fix; was 30/360), Floor_Hotel 38/456, Roof_Garden res1 128 > 120 + 3 sections, Roof_Mechanical res1 128 > 120, plus the pre-existing TowerA_Core |
| 2 | `python3 assets/gen_configs.py --check` | exit 0, `up to date` |
| 3 | `python3 assets/gen_manifest.py --check` | exit 0 |
| 4 | `python3 economy/gen_economy.py --check` | exit 0, `up to date` (`mapgroupproto_sky.xml` matches `skyspec.LOOT`) |
| 5 | `blender -b --factory-startup -P assets/blender/test_kit.py` | exit 0, `KIT GEOMETRY TESTS: PASS (39 assets)`. This includes `batch5_checks` (runs only without `--only`) |
| 6 | `blender ... -P assets/blender/test_towera.py` | exit 0, `TOWER A GEOMETRY TESTS: PASS (81 core components checked)` |
| 7 | `build_floors/props/kit/towera.py -- --out <scratch>/addons`, then `cmp` | All 4 exit 0: 5 + 10 + 24 + 5 `EXPORTED`, 0 `EXPORT FAILED`. **44/44 P3Ds byte-identical** to the committed files. `build_stats.json` and `build_stats_kit.json` are identical when the 3 kit builders run **sequentially** (the order in `Build-SkyAssets.ps1:52`). If run in parallel, they race on the shared `build_stats_kit.json` (Info I1). |
| 8 | `enscript_xref.py --vanilla dzs/scripts --mod addons/sky_scripts/scripts` | exit 0, `OK: 11 files, all calls/types resolve` (batch 5 adds no script) |
| 9 | Tower A vs `681ecdc` | `git ls-tree` of `addons/sky_towera` is identical (tree `79904d3`). The snapshot P3D sha256 equals the LFS oids at `681ecdc` for all 4. The rebuild (#7) is byte-identical. `build_towera.py` diff vs `681ecdc` is only D34 + `ELEVATOR_SLIDE_SIGN` (both gated before). `build_kit.py` change: the decal sizes now come from `S.DECAL_SIZE` (output-neutral, see #7) |
| 10 | `python3 placement/tests/test_sky_layout.py` | exit 0, `0 failed` (old cases + 15 new district cases) |
| 11 | `sky_layout.py` / `--layout district_template.yaml` into scratch, then `diff -r` vs committed `out/` / `out_district/` | Both exit 0, `PASS (with warnings)`, 8 / 323 entities. The outputs are **identical** apart from CRLF on `cfgeventspawns_snippet.xml`, which is expected from `.gitattributes` `*.xml eol=crlf` (`diff --strip-trailing-cr` is empty) |
| 12 | `--strict` on the template | exit 1: `PLACEHOLDER`, `no survey`, `site.center is not set`, `no base height` x4. PASS |

## 2. `economy/mapgroupproto_sky.xml`

- `xmllint --noout`: well-formed, CRLF. There are 14 groups: the 3 Tower A groups (unchanged), `Land_SKY_Floor_{Apartments,Hotel,Mechanical}`,
  `Land_SKY_Roof_{Garden,Mechanical}`, and `Land_SKY_{Locker,Desk,Cubicle,ReceptionDesk,Kitchenette,Bed}`. All 14 names are config classes
  (`sky_floors/config.cpp:20-44`, `sky_props/config.cpp:20,26,32,91,194,200`).
- Names vs vanilla `cfglimitsdefinition.xml`. Usages used: Industrial, Office, Town. Categories used: books, clothes, containers, food, tools, weapons.
  Tags used: floor, ground, shelves. **All exist**. No value flags are used.
- Container names: `lootFloor`, `lootSecurity` (Tower A), `lootshelves`. Vanilla uses `lootshelves` 192 times (and `lootFloor` 359 times). PASS.
- Point format: `<point pos="x h y" range height />` with h = height (y), which matches vanilla (`<point pos="0.504883 -1.174019 0.807373" range=... height=... [flags]>`;
  vanilla has 10648 points without `flags`, so omitting it is fine). Prop points use small range/height (0.1-0.3 / 0.3). Vanilla `lootshelves` uses
  range 0.13-0.26 and height 0.21-0.6, so these are consistent. Vanilla y values are negative because vanilla models are bbox-centred.
  All SKY Geometry LODs have `autocenter=0` (checked on all 6 loot props), so y relative to the model origin (slab top / prop base) is the right frame,
  provided CE uses the model origin. That is checked in-game (L5-01).
- **Prop points vs P3D Geometry** (independent: per-component boxes from the MLOD):

| Prop | Point z | Surface under it (Geometry / Res0) | XY inside the surface incl. range | Result |
|---|---|---|---|---|
| Locker | 0.06 x3 | floor plate top 0.05 / Res0 0.06 | bays -0.43..-0.16 / -0.14..0.14 / 0.16..0.43 vs x +-0.12 around -0.3/0/0.3 | PASS |
| Locker | 1.48 x3 | **no Geometry shelf**. Res0-only shelf 1.45..1.47 | as above | L1 (visual shelf, no collision) |
| Desk | 0.75 x2 | top 0.72..0.75 | x +-0.5 +-0.2, y -0.15 +-0.2 within +-0.8 / +-0.4 | PASS |
| Cubicle | 0.75 x2 | desk L comps 04/05 top 0.75 | both disks inside their desk part | PASS |
| ReceptionDesk | 1.10 x2 | counter Geometry 1.05, Res0 1.10 | within x +-1.5, y +-0.4 | PASS (5 cm above collision, on the visual) |
| ReceptionDesk | 0.75 | return desk 0.75 | (1.9, 0.8) +-0.25 inside 1.5..2.3 x -0.4..1.2 | PASS |
| Kitchenette | 0.92 x2 | worktop Geometry 0.88, Res0 0.92 | inside -1.2..0.6 x +-0.3; wall cabinet starts at 1.5 (above 0.92 + 0.3) | PASS |
| Bed | 0.50 | mattress top 0.50 | (0, -0.3) +-0.3 inside +-0.68 x +-0.98 | PASS |

- **Floor points vs Geometry + core + FURNISH props** (independent: floor P3D Geometry, Tower A core Geometry, every FURNISH prop's own
  Geometry rotated and placed). Minimum 2D clearance to anything occupying 0.05..1.5 m:
  apartments 0.88 m (walls) / 1.00 m (props), hotel 1.07 / 1.30, mechanical 2.50 / 2.59, garden/mech roof 1.50 / -, office 1.38 / 1.20.
  **No point is inside Geometry or under a prop, and every spawn disk (range 0.6) is clear.** Apartments have 3 points per apartment
  (NE band (5, 9), NE strip (8.5, 6) / (9.5, 1), mirrored). Hotel has 1 per guest room plus 1 per suite. PASS.
- Independent FURNISH vs floor Geometry (real prop components, not `PROP_BOX`): 0 overlaps with walls/units/core, all inside +-12.
  The tightest gaps are the hotel beds (0.62 m to the facade) and the ExtinguisherCabinet, which is flush on the core's west face (x = -3.00, core wall -3.00..-2.75).

## 3. `placement/sky_layout.py` (independent re-derivation + probes)

A scratch verifier (`scratchpad/qa5_verify_layout.py`) recomputes every object from first principles. It uses model +X = east,
+Y = north, and DayZ yaw clockwise: forward (sin a, cos a), right (cos a, -sin a). It then matches the generator output 1:1.

| Case | Result |
|---|---|
| Template (site yaw 0) | 323 objects: 307 matched exactly (modules, cores, tiles, props, decals) + 16 lights checked separately; 16 roof drops equal. **0 mismatches** |
| Template with `center [6000, 8000]`, **site yaw 37** | 323 / 307 + 16 / 16, **0 mismatches**. Tower yaw = site + tower yaw, props = tower yaw + prop yaw, tiles = site + 0/90, decals = tower yaw + face yaw: the composition is correct |
| Props inside floors | For all 4 towers (yaw 0/90/180/270, and +37), every rotated `PROP_BOX` corner, mapped back to the tower frame, lies inside +-12. y = base + level z (7.0, 10.5, ... 21.0). The T4 level-3 mechanical set lands on the mechanical floor. PASS |
| Decals | Position = facade (12 m) + `DECAL_OFFSET[type]` along the tower-frame face normal, at base + z. The quad's front (model -Y; the Res0 winding is consistent with the batch-2 convention) points along the world outward normal for N/E/S/W at any tower yaw. PASS geometrically. **See M2 for what lies behind them** |
| Roof drops | Per roof class: helipad (+-8, +-8), garden/mechanical (+-8, +-2), rotated by the tower yaw, y = base + 24.5 + 0.05. PASS |
| Street tiles | `Street_Straight`: carriageway is model x -4..4 along Y, so yaw 0 = N-S and 90 = E-W. PASS. 9 intersections exactly at the 3 x 3 ns/ew crossings. The 4 `crossings` are zebra tiles with the right yaw |
| Lights | Placed on straight tiles only, 4.5 m from the axis (0.5 m inside the curb), at y = base + 0.15 (sidewalk top). The 16/32 total respects `LIGHT_CAP`. **But see M1 (arm direction) and L2 (spacing)** |
| Caps | per_floor 25 (test), per_tower 600, aisle 1.2 m (test), `ENTITY_CAP` 3000 (323), `LIGHT_CAP` (test), decals per tower. PASS. `DECAL_CAPS.per_tile` is not enforced (L4) |
| Strict mode | Refuses the template (placeholder, no survey, no centre). PASS |
| Block maths | rect = cell centres +- 6 m. 3 x 3 blocks give 36 m, so a 24 m tower has 5.5 m left after the setback. Cells vs street cells are checked. A tower 6 m off-centre fails (test). PASS. `(i, j) placed twice` can never fire (each cell is visited once), so the "tile/tile overlap" check in the docstring is structurally a no-op (Info) |
| **Survey probes** | (a) Site-frame survey with a 14 x 14 m sampling gap over tile (4, 1), placeholder false, `--strict`: **PASS, exit 0, `Street_Straight` at Y = 0.0** (ground is at 200). (b) Survey axis-aligned (yaw 0, halfW = halfD = 56 as the template says) with site yaw 37: **`--strict` PASS, 4 corner `Street_Intersection` at Y = 0.0**. Towers in the same situation error with `survey has no samples inside its footprint`. -> **H1** |
| Sloped survey (1 %) | 21 distinct tile heights. Each tile sits at its own max + 0.05, so neighbours step about 0.12 m. Lobby vs sidewalk height is not related at all (L3) |

## 4. test_kit `batch5_checks` mutations (scratch copies of `assets/`, full run, `PYTHONDONTWRITEBYTECODE=1`)

| Mutation (`skyspec.py`) | Expected | Result |
|---|---|---|
| m1 apartments Sofa (9, 3) -> (5.6, 3): **prop in the hall wall** | fail | FAIL x4 `FURNISH apartments ...: Sofa at (+-5.6, +-3) hits a wall/unit` - caught |
| m2 apartments loot (9.5, 1) -> (5.5, 3): **loot point in a wall** | fail | FAIL x4 `LOOT Land_SKY_Floor_Apartments: point (+-5.5, +-3) inside Geometry` - caught |
| m3 hotel Sofa (9.5, 0, 90) -> (5.6, 0, 90): **furniture sealing the suite door** (no wall contact) | fail | FAIL `Floor_Hotel + FURNISH hotel: 98.1 m2 unreachable from the core (near x 5.5, y -6.0)` - caught |
| m4 `PROP_BOX["Desk"]` y1 0.4 -> 0.5 | fail | FAIL `PROP_BOX[Desk] ... != Geometry ...` - caught |
| m6 Locker point x 0 -> 0.15 (in the divider) | fail | FAIL x2 `inside its Geometry` - caught |
| m7 apartments floor point -> (3, 10) (under the bed) | fail | FAIL x4 `inside a furnish prop` - caught |
| m8 Bed point -> (0, -1.5) (off the bed) | fail | FAIL `outside the prop` - caught |
| **m5 Desk point z 0.75 -> 1.30 (floating 55 cm above the top)** | fail | **PASS - not caught** (L1) |

All copies were discarded. The unmodified run is `PASS (39 assets)`.

## 5. Docs vs code

- `economy/README.md` loot table: group/usage/category/point counts match the XML for all batch-5 rows (apartments 8 of 12, hotel 8 of 10,
  mechanical 4 of 5, roofs 2 of 3, Locker 2 of 6, Desk/Cubicle 1 of 2, Reception 2 of 3, Kitchenette 1 of 2, Bed 1 of 1).
  - "test_kit.py checks ... every prop point sits on its prop" overclaims. It checks "inside the prop's XY and not inside Geometry" (m5, L1).
  - Pre-existing (from `0526fb0`, not batch 5): the lobby `lootSecurity` row says "tools/weapons", but the XML/skyspec has `weapons` only.
  - Install step 3 points at `placement/out/` only; the district output is in `placement/out_district/` (L4).
- Infected per floor type: the table is plausible and correctly marked as hypotheses (B6). **But the README and D41 say `zombie_territories.xml`
  is "not shipped in the reference copy used here". That is false**: `ce/dayzOffline.chernarusplus/env/zombie_territories.xml` (82 KB) is there,
  it is referenced from `cfgenvironment.xml:16` and `:97` (`<file usable="zombie_territories" />`), and its format is
  `<zone name="InfectedCity" smin dmin dmax x z r/>` (36 InfectedCity, 65 InfectedIndustrial, 190 InfectedVillage ...). The README's recommended
  `InfectedCity` r 60 / dmin 6 / dmax 10 matches that format, and it has x/z only (no height), which supports "zones are at street level" (M3).
- `placement/README.md` section 4 matches the code for streets, blocks, variants, caps, decals and roof drops. It says "every N-th straight tile", which
  the code does not do per street (L2). It does not say that a tile without survey samples falls back silently (H1).
- DECISIONS: D38 (exactly 5 floors) is enforced (`wrong floor count fails`). D39 is enforced (test_kit + generator; mutations m1/m3/m7).
  D40 matches the XML. D41: wrong premise (M3). D42: "right-hand sidewalk, 0.5 m inside the curb" matches the pole position, but the
  lamp arm points away from the road (M1).
- PENDING B6/B7/B8 cover the right open questions. B8 should also cover the arm direction (M1) and decals on glass (M2).

## 6. Findings

### High
- **H1 - Street tiles without survey samples are placed at Y = 0 (or `site.base_y`) silently, and `--strict` passes.**
  `placement/sky_layout.py:354-368`: when `survey_ground()` returns no samples for a tile, `base_y` stays `None` and falls back to
  `site.base_y or 0.0` with no error and no `soft()`. Towers in the same case error (`:231-232`). The template's own workflow reaches this.
  `district_template.yaml:5-6` says to survey with `halfW = halfD = 56` but not to use the site yaw for the survey. With site yaw 37 and an axis-aligned survey,
  the 4 corner intersections land at Y = 0.0, 200 m under the terrain, and `--strict` prints `PASS` (probe 3b). The generator also
  never checks that the survey's `center`/`yaw`/`halfW`/`halfD` cover the district.
  Likely fix (placement owner): `ctx.errors.append("street tile (%d, %d): survey has no samples ...")` when `survey is not None and not ys`.
  Optionally also check that the survey rectangle contains every tile and footprint, and document "survey yaw = site yaw" in the template.

### Medium
- **M1 - Street-light arm points away from the carriageway.** The model arm and head extend to local **+X** (`build_kit.py:265-267`,
  head x 1.2..1.8, `light` memory point x 1.5). `sky_layout.py:374-376` puts the pole on the **+X** sidewalk (4.5 m) with the tile yaw. So the
  lamp hangs over the outer sidewalk edge / block (tile x 5.7..6.3) and lights nothing on the road. In the template every one of the 16
  lights points into the blocks. Fix: put the pole on the -X sidewalk (`lu = -(carriageway/2 + 0.5)`) or add 180 to its yaw. Rebuild nothing.
- **M2 - Decals are placed on glass.** Tower A lobby (z 0..6.7) and every glazed floor (z 0..3.2) facade is `sky_glass` at 11.94 with the Geometry plane
  at 12.00 and no View Geometry. Only the 0.3 m slab edges and the mechanical floor (metal louvre) are opaque. All 3 template decals
  (T1 S graffiti at z 0.2..2.2, T1 S dirt 4..7, T3 E cracks 0.5..2.5) cover glass. A single-sided decal on glass gives one-sided concealment:
  players inside see out, players outside cannot see in. This is the security batch-2 L1 concern that D16 exists to prevent, and here it is at player height.
  The decals also sit 8.5 cm in front of the visible glass, while the mullion fronts (12.04) cut through them.
  The generator has no facade-material / opaque-band data. Fix: allow decals only on opaque bands (a per-module `DECAL_ZONES` in skyspec:
  slab edges, the mechanical floor louvres, the roof parapet) or on street objects. Make the template comply.
- **M3 - D41 / economy README premise is false.** `zombie_territories.xml` is in the reference copy (`env/`). The per-floor-type table can
  stay a hypothesis (B6). Correct the statement, cite the zone format (`zone name/smin/smax/dmin/dmax/x/z/r`, no height), and decide whether
  to generate a `sky_zombie_territories` snippet from the layout (zone at the district centre, r 60). This is a docs fix only. No zone is needed for the gate.

### Low
- **L1 - Prop loot points are not checked to rest on a surface.** test_kit only checks "inside the prop's XY, not inside Geometry". A point 55 cm
  above the desk passes (m5). The Locker's upper points (z 1.48) sit on a Res0-only shelf (1.45..1.47) with no Geometry shelf, so an item
  rests on a visual-only surface. Reception (1.10) and Kitchenette (0.92) points are on the Res0 tops, 4-5 cm above Geometry. Add a
  "Geometry top within 0..0.06 m below the point" check, and a Geometry shelf in the locker (or drop the 1.48 points).
- **L2 - Lights are every 2nd straight tile globally, not per street.** `n_straight` counts across the i-outer/j-inner loop (`sky_layout.py:345-372`),
  and E-W rows interleave. In the template, E-W row j = 4 gets lights on adjacent tiles (-3,4) (-2,4) and (1,4) (2,4), while N-S column i = -4 gets
  j -3, -1, 2. The total equals the cap. Fix: count per street run (per i for N-S, per j for E-W).
- **L3 - No height continuity between tiles / lobby.** Each tile takes its own max ground + 0.05. A 1 % slope gives about 0.12 m steps at every seam
  (21 distinct heights in probe 3). The lobby floor height is not related to the sidewalk. Consider one street plane per district, or a max step check,
  plus a check that the lobby sill is within the curb height of the adjacent sidewalk.
- **L4 - Small doc/code gaps.** `DECAL_CAPS.per_tile` is never enforced, and `per_block` is applied per tower (`sky_layout.py:304-306`).
  The `ReceptionDesk` loot group is spawned by no FURNISH set. `ExtinguisherCabinet` is described as a "wall cabinet" but its Geometry is z 0..0.7 and
  FURNISH has no z offset, so it stands on the floor. economy/README install step 3 only mentions `placement/out/`. The pre-existing lobby `lootSecurity` row says "tools/weapons".
  Crossings listed on intersection or non-street cells are ignored silently.

### Info
- I1 - `build_kit.py`, `build_props.py` and `build_floors.py` all merge into `assets/build_stats_kit.json`. Running them in parallel loses entries
  (seen in this QA's first rebuild). `Build-SkyAssets.ps1` runs them sequentially, so the shipped flow is fine.
- I2 - `_mirror4` rotates (it does not mirror) asymmetric props. For example, the Kitchenette's tall unit flips sides in the S apartments. This is harmless here.

### Severity summary
High 1 (H1) · Medium 3 (M1 light arm, M2 decals on glass, M3 D41 premise) · Low 4 · Info 2.

## 7. In-game test list (batch 5). Run in diag (`Build-And-Run.ps1 -FilePatching`), then dedicated (`-Mode Dedicated`, signed)

Preconditions: H1 and M1 fixed (or knowingly waived). Survey a real site with **survey yaw = site yaw**, halfW = halfD = 56, step 2.
Fill `district_template.yaml` (`center`, `yaw`, `survey`, `placeholder: false`). `sky_layout.py --layout ... --strict` -> PASS.
Copy `out_district/sky_objects.json` to `<mission>\sky\`, and merge the cfggameplay, cfgeventspawns and mapgroupproto snippets plus the `sky_ce` folder.
Logs: newest `script_*.log`, `*.RPT` and `*.ADM` in `server\profiles\{diag-server,dedicated}\`.

| ID | Steps | Expected logs | Expected in game | PASS/FAIL |
|---|---|---|---|---|
| P5-01 | Start the server with the filled template | RPT: no `Cannot create object`, no `missing in CfgPatches`. script log: no `SCRIPT (E)` from `objectspawner.c` | 4 towers (office / apartments / hotel / office+mech) stacked without gaps, roofs garden x2, helipad, mechanical | |
| P5-02 | Walk every street tile, then drive a car over all seams | none | No tile under terrain, no hole (H1), no step > curb at seams (L3), no wheel snag (P8) | |
| P5-03 | Look at each street light at night | none | Head over the **carriageway** (M1); emissive reads "lit" (P7); pole does not block the 2 m sidewalk (B8) | |
| P5-04 | Count lights per street | none | Every 2nd straight tile **on each street** (L2), none on intersections/crossings | |
| P5-05 | Decals: check each placed decal from outside, inside and at grazing angle | none | Facing outward, no z-fight (D19), not on glass (M2), no see-in/see-out asymmetry | |
| P5-06 | Furniture per floor: visit each furnished level of each tower | none | Props at FURNISH positions on the slab (not floating/sunk), aisles >= 1.2 m, every room reachable, core doors clear, cabinet flush on the core wall | |
| P5-07 | Rotated site (yaw != 0): repeat P5-01/06 on one tower | none | Props and decals rotate with the tower (yaw composition) | |
| P5-08 | Restart the server twice | no duplicate-spawn warnings | Same objects, no duplicates (spawner objects are not persistent) | |
| P5-09 | Count entities and FPS at the district centre (perf protocol) | server FPS in RPT/admin tool | Entity count = report total (323 for the template). FPS within the perf budget | |
| L5-01 | Rerun the survey with `exportRadius` covering the district | script log `[SKY] site survey`; `storage_1/export/mapgrouppos.xml` written | `Land_SKY_*` entries for floors, roofs **and the 6 loot props** (B7). Record their `pos`/`a` and check that y is the model origin (slab top / prop base) | |
| L5-02 | Merge the exported entries, wipe storage, restart | RPT: no `[CE]` errors for SKY groups | Loot on floors at the listed points: apartments 3 per unit, hotel 1 per room + suites, mechanical 4-5 points | |
| L5-03 | Inspect each loot prop: Locker (open doors), Desk, Cubicle, ReceptionDesk, Kitchenette, Bed | none | Items **on** the surfaces: locker floor + upper shelf (L1: not floating/falling), desk/cubicle top, counter, worktop, mattress. None inside a mesh | |
| L5-04 | Pick up loot from a locker bay and from the upper shelf | ADM: normal | Reachable via the door, no clipping through the locker sides | |
| L5-05 | Categories per group | none | Only the listed categories (e.g. Kitchenette food, Bed clothes, mech floor tools/containers) | |
| L5-06 | Roof drops on every roof type | RPT: no event errors | Supply boxes at (+-8, +-8) on the helipad and (+-8, +-2) on garden/mech roofs, on the open roof | |
| L5-07 | Relog / server restart persistence | none | Loot respawns per CE timers. No duplication on furniture | |
| L5-08 | B7 rollback check: if L5-01 shows no prop entries, remove the prop groups | none | Floor loot unaffected | |
| Z5-01 | Add an `InfectedCity` zone at the district centre (r 60, dmin 6 / dmax 10) in `zombie_territories.xml` | RPT: no territory errors | Infected spawn at street level around players | |
| Z5-02 | Spend 10 min on each floor type with 1 and then 3 players | none | Count infected per floor vs README targets: lobby 3-5, office 1-2, apartments 2-3, hotel 2-3, mech 0-1, roofs 0-1 (B6) | |
| Z5-03 | Pathing: DayZDiag navmesh view on each floor type with furniture spawned | none | Navmesh around props (ECE_UPDATEPATHGRAPH), through doors, stairs, not through glass. Infected follow players to the roof | |
| Z5-04 | Death + respawn near the district, then reconnect | none | No infected stuck in furniture or walls | |
| R5-01 | Regression: vanilla town loot and infected nearby | no new CE warnings | Vanilla buildings still get loot. Vanilla zones unchanged | |
| R5-02 | Regression: Tower A lobby security door + keycard + elevator on each variant | ADM: swipe/elevator lines as in TESTING.md | Works the same on every floor variant | |
