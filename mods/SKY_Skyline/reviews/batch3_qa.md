# SKY_Skyline - Batch 3 (interior props, `sky_props`) static QA gate

Date: 2026-10-05. Host: Linux, no DayZ / DayZ Tools / P: drive. Static checks only; nothing here
proves in-game behaviour. Every asset stays **built-unverified**. This run modified no mod code,
asset, config or generator (only this file was written).

Tools: Blender 4.2.23 LTS (scratchpad), ArmaToolbox (`ARMATOOLBOX_PATH` scratchpad), python3 + Pillow/numpy/PyYAML,
`tools/assets/p3d_inspect.py`, vanilla scripts dump and BI samples (scratchpad `dzs/scripts`, `samples/Test_Building`).

**Gated revision: `dd30941`** ("WIP batch 3: interior props ..."). Other work continues in the working tree, so all
results come from a clean `git archive dd30941` snapshot (`scratchpad/qa3`).

**Verdict: GATE: FAIL.** There is 1 High finding (H1: the vending-machine flap rotates the opposite way to the
locker and cabinet doors, so no value of `DOOR_SWING_SIGN` makes all prop doors open correctly). All the
mechanical checks pass (section 1). There are also 2 Medium findings and several Low/Info findings (section 4).

## 1. Commands and results (snapshot `dd30941`, cwd `mods/SKY_Skyline`)

| # | Command | Result |
|---|---|---|
| 1 | `python3 assets/check_assets.py` | exit 0. `39 checked, 0 fail, 1 over budget (hypotheses)`. The only OVER is `Land_SKY_TowerA_Core geo comps 81 > 80` (pre-existing). All 10 new props PASS, e.g. `Land_SKY_Locker PASS LODs=8 res=132 -> 120 -> 12`, `Land_SKY_VendingMachine PASS LODs=8 res=26 -> 26 -> 14`, `Land_SKY_ExtinguisherCabinet PASS LODs=7 res=100 -> 92 -> 12`. |
| 2 | `python3 assets/gen_configs.py --check` | exit 0, `up to date` |
| 3 | `python3 assets/gen_manifest.py --check` | exit 0 (silent on success) |
| 4 | `python3 economy/gen_economy.py --check` | exit 0, `up to date` |
| 5 | `blender -b --factory-startup -P assets/blender/test_kit.py` | exit 0, `KIT GEOMETRY TESTS: PASS (34 assets)`. This includes the new door checks in `test_kit.py`: selections, shadow, memory points, and one Geometry component per door. |
| 6 | `blender -b --factory-startup -P assets/blender/test_towera.py` | exit 0, `TOWER A GEOMETRY TESTS: PASS (81 core components checked)` |
| 7 | `build_props.py` and `build_kit.py -- --out <scratch>/rb2/addons`, then `cmp` against `addons/sky_props/*.p3d` and `addons/sky_street/*.p3d` | **34/34 P3Ds byte-identical** (10 props + 24 street). The regenerated `build_stats_kit.json` equals the committed one (34 keys). See L1 for the first attempt. |
| 8 | `python3 assets/textures/gen_textures.py --out <scratch>/tex` (default `--size 2048`) | exit 0, 1 min 19 s, **70 PNGs, 0 non-power-of-two**. New: `sky_wood_co/_nohq` 1024, `sky_fabric_co/_nohq` 512 (`_as`/`_smdi` are procedural in the rvmats). `sky_atlas_co` 2048 has the new cells (0,1) vending, (1,1) rack, (2,1) panel, (3,1) appliance, (0,2) monitor and (1,2) extinguisher. **Row-0 cells (manhole, timetable, traffic, sign) are pixel-identical to the `053a7d3` generator**, so there is no street-kit visual regression. |
| 9 | `p3d_inspect.py --json addons/*/*.p3d` plus a scratch parser for point order and coordinates | exit 0, 39 P3Ds. Used for sections 2 and 3. |
| 10 | `git diff --stat 681ecdc -- mods/SKY_Skyline/addons/sky_towera mods/SKY_Skyline/addons/sky_items` | **empty**, both `681ecdc..dd30941` and against the working tree (PASS). |

## 2. Door checks (from the committed P3D bytes, `model.cfg`, `config.cpp`)

P3D coordinates: x, y = up, z = depth (prop front = -z).

| Check | Locker `locker_door1/2/3` | ExtinguisherCabinet `cab_door` | VendingMachine `flap` |
|---|---|---|---|
| Selection in Res 0 / Res 1 | yes / yes | yes / yes | yes / yes |
| Selection in Res 2 | **no** (Res 2 is one box) | **no** | **no** (L3) |
| Geometry (faces) | yes (6), exactly one component each (Component08/09/10) | yes (6), Component06 | yes (6), Component02 |
| Fire Geometry | yes | yes (`pen_glass`, P3) | yes |
| View Geometry | yes | no View LOD in this model | yes |
| Shadow Volume | yes (6 faces each) | yes | yes |
| Memory `<door>_axis` | 2 pts, idx 0->1, x = -0.445 / -0.145 / 0.155, y 0.06 -> 1.77, z -0.26 | 2 pts, (-0.19, 0.02 -> 0.68, -0.26) | 2 pts, (-0.35 -> 0.35, 0.15, -0.42) |
| Memory `<door>_action` / `<door>` | 1 pt each (z -0.70 / -0.26) | 1 pt each | 1 pt each (z -0.80 / -0.42) |
| model.cfg skeleton bone | `SKY_Skeleton_Locker` `{"locker_door1","", ...}` | `SKY_Skeleton_ExtinguisherCabinet` | `SKY_Skeleton_VendingMachine` |
| model.cfg anim | `locker_doorN_rot` rotation, `memory = 1`, `angle1 = 1.4` | `cab_door_rot`, `angle1 = 1.4` | `flap_rot`, `angle1 = 0.84` |
| angle1 = SIGN * 1.4 * scale | 1 * 1.4 * 1.0 = 1.4 PASS | 1.4 PASS | 1 * 1.4 * 0.6 = 0.84 PASS |
| config `Doors` `component` / `soundPos` | `locker_doorN` / `locker_doorN_action` PASS | `cab_door` / `cab_door_action` PASS | `flap` / `flap_action` PASS |
| DamageSystem zone `componentNames[]` | `{"locker_doorN"}`, all damage 0 (P5 `FragGrenade`) | same | same |
| **+angle swing direction** (same rule as the lobby, see below) | **outward (-z)** | **outward (-z)** | **inward (+z, into the solid machine body)** |

Engine reference: `ActionOpenDoors.ActionCondition` only needs a `Building` plus `GetDoorIndex(componentIndex) != -1`
(`scratchpad/dzs/scripts/4_world/classes/useractionscomponent/actions/interact/actionopendoors.c:28-50`).
`HouseNoDestruct` props therefore qualify. The sounds `doorMetalSmall*` are the ones in `samples/Test_Building/config.cpp:39-42`.

### 2.1 Swing-direction analysis (basis for H1)
The rotation sense comes from (axis point 0 -> point 1) x (hinge -> leaf centroid). I apply the same rule to every
door. The engine handedness is unknown (that is P1), but all doors share it, so the comparison between doors does not depend on it.
- Lobby `door_sec` (`sky_towera_lobby.p3d`): the axis runs (6.0, 0, 7.0) -> (6.0, 2.1, 7.0) and the leaf centroid is (6.0, 1.04, 7.5). The +angle
  motion is **+x, into the security room** (room x 6.0..11.85; `skyspec.py:169` "swings inward (+X)"). This is the P1 assumption.
- Locker doors 1-3 and `cab_door`: the vertical axis runs bottom -> top and the leaf extends +x from the hinge. Under the same rule the motion is **-z = out of
  the cabinet**. This is correct for a locker, but it contradicts `skyspec.py:64` and PENDING P1, which say "+1 ... opens INTO the room/cabinet".
- `flap`: the horizontal axis runs -x -> +x at y 0.15 and the leaf extends +y (up). The motion is **+z = into the machine body**. The body is a solid box
  (z -0.4..0.4), so the flap disappears into it. `build_props.py:117` states the intent: "swings outward/down (P1 sign)".

Outcomes:

| P1 outcome | Lobby | Lockers/cabinet | Flap |
|---|---|---|---|
| P1 true, sign +1 | in (OK) | out (OK) | **into the body** |
| P1 false, documented fix sign -1 | in (OK) | out (OK) | **into the body** |

## 3. Other cross-checks

- **Texture references:** 67 unique `SKY_Skyline\...` texture paths in rvmats, P3D faces (all LODs) and configs.
  **67 resolve** to a generator output, **0 unresolved**. All `sky_textures\data\*.rvmat` that the props reference exist
  (`sky_atlas, sky_fabric, sky_glass, sky_metal, sky_rust, sky_wood`). Orphans are unchanged from batch 2 (`sky_brick_co`,
  `sky_concpanel_co`, `sky_windows_co`). Non-SKY paths: `dz\data\data\env_land_co.paa` (P4), the roadway textures
  (verified earlier), and the props' penetration rvmats `metalplate` / `wood_desk` (verified earlier, `qa_static_run.md:199-200`)
  and `glass` (P3, unverified; listed).
- **Rvmats:** `sky_wood.rvmat` / `sky_fabric.rvmat` use the `_nohq.paa` file, plus procedural DT/MC/AS/SMDI (`color(1,0.25,0.35,1,SMDI)` and
  `color(1,0.03,0.1,1,SMDI)`), fresnel, and Stage7 `env_land_co` (P4).
- **Geometry LOD properties:** all 10 props have `class=house`, `autocenter=0` and no `map=` (D5). Masses are 25-300.
- **Config:** `SKY_Skyline_Props` `requiredAddons[] = {"DZ_Data", "SKY_Skyline_Textures", "SKY_Skyline_Scripts"}`.
  `Land_SKY_Props_Base: HouseNoDestruct` is scope 0 and the 10 classes are scope 1. Model paths are lower-case and match the files.
- **Manifest `generated_kit`:** 34 entries. **All 10 props are `status: built-unverified`**. The door props have `uses: [DOOR_SWING_SIGN, DOOR_OPEN_ANGLE]`
  (cabinet also `PENETRATION`). PASS.
- **PENDING_VERIFICATION.md:** P1 lists Locker `locker_door1..3`, ExtinguisherCabinet `cab_door`, and VendingMachine `flap` (scaled 0.6).
  P3 lists the ExtinguisherCabinet glass door. P5 lists the prop door DamageSystems (Locker, ExtinguisherCabinet, VendingMachine). PASS for presence. See M1 for P1 wording.
- **Placement / CE:** no prop is placed yet (`placement/` and `economy/` do not reference them). There are no loot points or proxies in the props.
- **Tower A unchanged:** PASS (section 1 #10).

## 4. Findings

### High
- **H1 - The vending flap rotates opposite to the other prop doors. One `DOOR_SWING_SIGN` cannot be correct for all of them.**
  `assets/blender/build_props.py:59-61` writes the horizontal axis as (-x -> +x) with the leaf above the hinge. Under the P1
  convention (lobby door opens into the room), this puts the +angle swing **into the vending body**, while lockers and cabinet
  swing outward (section 2.1). After the documented P1 fix (`DOOR_SWING_SIGN = -1`) the flap is still wrong. The code
  intent (`build_props.py:117` "outward/down") is not met in either outcome.
  Likely fix (enforce-coder / asset-pipeline): add a per-door direction to `skyspec.door()` (e.g. `sense=-1` for `flap`) and use it in
  `gen_configs.kit_door_anims` (`gen_configs.py:190`, angle1 then becomes -0.84; no re-export needed). Alternatively, swap the flap axis
  point order in `hinged_door` and re-export the vending P3D. Then add a direction assertion to `test_kit.py`, which checks
  selections but not swing sense today.

### Medium
- **M1 - The P1 wording does not fit the props and invites a wrong flip.** `skyspec.py:64` and the PENDING P1 row say "+1 opens hinged
  doors *into* the room/cabinet". By the geometry, +1 opens the lobby door into the room and the locker/cabinet doors **out of** the cabinet.
  A tester who reads "into the cabinet", sees lockers open outward and flips the sign would break the lobby and the lockers together.
  Fix: reword P1 to "+1 = lobby door into the room = locker/cabinet doors outward", and list the expected direction per prop.
- **M2 - The in-game checklist exists only in this review.** `TESTING.md` has no prop section (D-xx covers only `door_sec` and the elevator).
  The P3-xx items below must be merged into `TESTING.md` before the in-game run. This run was told not to edit other files.

### Low
- **L1 - A rebuild into an arbitrary `--out` dir fails and still reports success.** `skygeo.run_cli` (`skygeo.py:421-429`) writes stats to
  `<out>/../assets/build_stats_kit.json`. With `--out <scratch>/rebuild` the stats write raised `FileNotFoundError` after all P3Ds had been
  exported, but Blender still exited 0 (no `--python-exit-code`). Pre-existing tooling; `Build-SkyAssets.ps1` should pass
  `--python-exit-code 1`, and run_cli should create or skip the stats dir.
- **L2 - The manifest is stale outside the generated section.** `manifest.yaml:86-90` `props: status: planned` still lists all 10 props as
  planned. The `textures:` section (lines 102-124) has no `sky_wood` (1024) or `sky_fabric` (512) entry.
- **L3 - Door leaves are not in Res 2.** On all 4 door props, Res 2 is a closed block, so an open door appears shut at Res 2 distance while the
  collision is open. Acceptable for small props; verify that the LOD switch distance hides it (P3-x7 items).
- **L4 - DECISIONS.md has no batch-3 entry** for "doors on HouseNoDestruct props + invulnerable DamageSystem zones" (last entry D23).

### Info
- I1: View Geometry is absent on Desk, Sofa, Bed and ExtinguisherCabinet (low or small objects, so AI sees over or through them). ReceptionDesk View
  covers only the front counter, not the return. Kitchenette View covers neither the upper cabinets nor the counter top above 0.88 m.
- I2: `Land_SKY_Cubicle` Res 1 -> Res 2 has no reduction (60 -> 60 triangles; check_assets PASS).
- I3: `sky_atlas` rows 2-3 unused cells changed pixels versus `053a7d3`. No model maps to them.
- I4: Cubicle fabric screens use `wood` penetration (`wood_desk.rvmat`). This is plausible, but bullets will sound and look like wood.
- I5: Blender `test_*.py` and `build_*.py` produced no traceback on the snapshot when the output went to `addons/`'s normal layout.

## 5. In-game test list (batch 3 props)

Run each item once in **diag** (`tools\build\Build-And-Run.ps1 -ModName SKY_Skyline -FilePatching`), spawning the prop by
debug or temporary objectSpawnersArr entry inside the Tower A lobby. Then run it once in **Dedicated** (`-Mode Dedicated`, signed, `verifySignatures = 2`)
with 2 clients. Gate for every run:
- RPT has no `Cannot open object SKY_Skyline\sky_props\...`, no missing `.paa`/`.rvmat`, no `Updating base class`, and no `missing in CfgPatches`.
- `script_*.log` has no `SCRIPT (E)`.
- No `crash_*.log`.

Quote the newest log lines with timestamps as evidence. Shared prop checks (apply to every class below; record per class):

| ID | Item | Steps | Expected | Evidence | Diag | Ded |
|---|---|---|---|---|---|---|
| P3-01 | ReceptionDesk | spawn; walk into the counter and the return; vault/climb; shoot the walnut panel | Spawns upright at ground (z = 0 is the base). Player is blocked by the counter (1.05 m) and the return (0.75 m). Bullets stop or penetrate as wood. Shadow shows on the floor. Res 0 -> 1 -> 2 switch has no pop of the monitor quad that looks broken. | RPT clean; screenshot | | |
| P3-02 | Desk | spawn; crouch under the desk; walk into the legs; shoot the top | Collision on the top (0.72-0.75 m) and legs. Monitor atlas cell (0,2) shows a dark screen and no stretched texture. Shadow. LOD switch. | | | |
| P3-03 | Cubicle | spawn; walk around and into the 3 screens (1.4 m); enter through the open side; shoot a screen | Screens block the player and block AI view (View LOD). The L desk collides. Fabric texture tiles without seams. Res 2 still shows the screens. | | | |
| P3-04 | ServerRack | spawn; walk into it; shoot it | Solid 0.6 x 1.0 x 2.0 m. Rack atlas front faces -z. Shadow. LOD switch. | | | |
| P3-05 | Sofa | spawn; walk into it; try to stand on the seat | Collision on the base, back and arms. Blue fabric with no stretching. Shadow. | | | |
| P3-06 | Bed | spawn; walk into the frame and headboard | Collision as modelled. The pillow shows in Res 0 only. Shadow. | | | |
| P3-07 | Kitchenette | spawn; walk into the counter and fridge; walk under the upper cabinets | The counter and fridge (1.9 m) block. Upper cabinets (1.5-2.2 m, rear 0.3 m) collide at head height. Appliance atlas cell on the fridge front. | | | |
| P3-08 | All 10 props | for each: walk 5 / 30 / 80 / 200 m away (and zoom) | LOD switches Res 0 -> 1 -> 2 with no holes or flicker. Shadows switch with the LODs. No z-fighting on the atlas quads (offset 1 mm). | | | |
| P3-09 | All 10 props | place one inside the lobby next to a vanilla loot spot (or a SKY lobby loot point) | Loot is not hidden inside or under the prop, and the prop does not block a loot position. No loot spawns inside the prop (props have no proxies). | | | |
| P3-10 | Locker door 1 (left) | stand in front; look at the door; `Open door`; then `Close door` | The action appears at about 0.7 m in front (`locker_door1_action`). The door rotates about its **left** vertical edge **outward toward the player** (~80 deg, 0.8 s). It does not pass through the carcass or the shelf, and does not hit door 2. `doorMetalSmallOpen` / `Close` play at the door. | screenshot open/closed; video | | |
| P3-11 | Locker doors 2 and 3 | same as P3-10 for each door; then open all 3 at once | Each opens independently and about its own left edge. With all 3 open there is no leaf intersection. Collision follows each leaf. | | | |
| P3-12 | Locker, each side | try the action from behind / beside the locker and from inside the swing arc | The action appears only within reach of the front. Opening while you stand in the arc: the door pushes or stops as vanilla doors do (no player launch). Closed door blocks; open door is passable only where the leaf is not. | | | |
| P3-13 | ExtinguisherCabinet door | spawn on a wall (back at local y = 0, front -z); open and close | Glass door hinges on its left edge and swings **outward** ~80 deg. It does not enter the cabinet or hit the extinguisher. Glass is transparent. Sound plays. Shoot the glass: penetration is glass (P3). | | | |
| P3-14 | VendingMachine flap | open and close the pickup flap | **Expected per design: tilts outward/down about the bottom edge (~48 deg).** With the `dd30941` config the static analysis predicts it tilts **into** the machine body (H1). Record the actual direction. | screenshot | | |
| P3-15 | Door sounds | for each door type, open, close and fully open | `soundOpen/Close` heard at `<door>_action`, about 1 m in front. No `soundLocked` (doors are never locked). Nothing logged in RPT about missing sound classes. | RPT | | |
| P3-16 [DED] | Door sync, 2 clients | client A opens locker door 2 and the flap; client B watches | B sees the same phase and animation. Collision for B matches the visual. | | | |
| P3-17 [DED] | Relog | with doors open, relog A; connect a third client | Doors show the server state after reconnect (open stays open). | | | |
| P3-18 [DED] | Server restart | open doors, restart the server | Doors are back to `initPhase 0` (closed) after the restart. This is expected because objectSpawnersArr props do not persist door state; record it. | | | |
| P3-19 | Damage | shoot, melee and frag each door and each prop | No damage and no destruction (all `damage = 0`; P5 `FragGrenade` class name). No RPT warnings about the armor class. | RPT | | |
| P3-20 | Death | die (e.g. suicide) next to an open locker; respawn | No change to the prop. The body does not fall through the prop or into it. | | | |
| P3-21 | Dedicated vs listen | repeat P3-10, P3-13 and P3-14 on the dedicated server | Same direction and behaviour as diag. No `Signature check` / `Modified data` kick for `sky_props.pbo` (key in `keys\`). | RPT, server log | | |
| P3-22 | Swing sign (P1) | **only after D-01 (lobby door) is confirmed** | If D-01 needed `DOOR_SWING_SIGN = -1`, regenerate and re-run P3-10..14: lockers and cabinet must still open outward. The flap needs its own fix (H1). | | | |
| P3-23 | Regression (vanilla nearby) | open a vanilla building door and a vanilla locker/cabinet near the props; pick up loot from a vanilla container | Vanilla door actions, sounds and loot are unaffected. No new RPT lines for vanilla classes. | | | |
| P3-24 | Regression (SKY) | lobby `door_sec` (D-01), a street prop (bus stop) and its atlas cells | Unchanged from batches 1-2. Atlas row 0 is pixel-identical. | | | |

Run status: all P3-xx items **NOT RUN** (no DayZ on this host).

---

## Re-gate (e259877)

Date: 2026-10-05. Same host and limits as above: static checks only, nothing run in DayZ, every asset stays **built-unverified**.
Snapshot: `git archive e259877` -> `scratchpad/qa3b`. Mutations and the `DOOR_SWING_SIGN = -1` variant were made in separate
scratch copies (`qa3b_mut_*`, `qa3b_neg`). No mod code, asset, config or generator was changed; only this section was appended.

**Verdict: GATE: PASS.** H1 is fixed and confirmed independently from the P3D bytes. There are no High findings. Two new Medium
findings (R-M1 test gap, R-M2 stale fix instruction) should be fixed before the first in-game run of D-01 / P3-10..14.

### R1. Commands and results (cwd `mods/SKY_Skyline` of the snapshot)

| # | Command | Result |
|---|---|---|
| 1 | `python3 assets/check_assets.py` | exit 0, `39 checked, 0 fail, 1 over budget (hypotheses)`. The only OVER is still `Land_SKY_TowerA_Core ... geo comps 81 > 80`. Props: `Land_SKY_Locker PASS LODs=8 res=132 -> 120 -> 12`, `Land_SKY_VendingMachine PASS LODs=8 res=26 -> 26 -> 14`, `Land_SKY_ExtinguisherCabinet PASS LODs=6 res=90 -> 82 -> 12`, `Land_SKY_Cubicle PASS LODs=7 res=62 -> 60 -> 36`. No shadow OVER. |
| 2 | `gen_configs.py --check` / `gen_manifest.py --check` / `economy/gen_economy.py --check` | exit 0 / 0 / 0 (`up to date`, silent, `up to date`) |
| 3 | `blender -b --factory-startup --python-exit-code 1 -P assets/blender/test_kit.py` | exit 0, `KIT GEOMETRY TESTS: PASS (34 assets)` |
| 4 | `... -P assets/blender/test_towera.py` | exit 0, `TOWER A GEOMETRY TESTS: PASS (81 core components checked)` |
| 5 | `build_props.py` + `build_kit.py -- --out scratch/qa3b_rb/addons`, then `cmp` | both exit 0, 10 + 24 `EXPORTED`. **34/34 P3Ds byte-identical**. The regenerated `build_stats_kit.json` equals the committed one (34 keys). The arbitrary `--out` no longer fails (L1 part 1 fixed: `os.makedirs` for the stats dir). |
| 6 | `gen_textures.py --out scratch/qa3b_tex` (2048) | exit 0, 1 min 19 s, **69 PNGs** (was 70: `sky_wood_nohq` is now procedural), 0 non-power-of-two. `sky_wood_co` 1024, `sky_fabric_co` / `_nohq` 512. |
| 7 | Texture reference resolution (rvmats, P3D faces of all LODs, configs) | **66 `SKY_Skyline\...\*.paa` refs, 0 unresolved**; 22 rvmat refs, 0 missing. `sky_wood_nohq` is referenced nowhere. Orphans unchanged (`sky_brick_co`, `sky_concpanel_co`, `sky_windows_co`). |
| 8 | `python3 tools/assets/enscript_xref.py --vanilla scratch/dzs/scripts --mod mods/SKY_Skyline/addons/sky_scripts/scripts` | exit 0, `OK: 11 files, all calls/types resolve` (includes the new `Land_SKY_Props_Base.c`). |
| 9 | `git diff 681ecdc e259877 -- addons/sky_towera addons/sky_items` | **empty** (0 lines). PASS. |
| 10 | `tools/assets/p3d_inspect.py --json addons/sky_props/*.p3d` + scratch MLOD parsers (`qa3b_swing.py`, `qa3b_faces.py`) | exit 0. Used for R2 and R4. |

### R2. H1 / M1: P1 convention, recomputed from the committed bytes

**Wording.** `skyspec.py:65-71` now anchors P1 on the lobby: "+1 assumes RV rotates a positive angle by the LEFT-hand rule about the memory axis (first point -> second point, Blender frame)". The PENDING P1 row and DECISIONS D30 say the same. If the lobby is wrong, the fix is `DOOR_SWING_SIGN = -1`; if the lobby is right but one prop door is wrong, flip that door's `orient`. PASS (but see R-M2).

**Method (independent of `test_kit.py`).** I took the axis points (selection `<door>_axis` in point-index order), the action point, and the Geometry leaf centroid directly from the MLOD bytes. I mapped P3D (x, y-up, z) to the Blender frame (x, y, z-up). Then I rotated the centroid by `angle1` from the `model.cfg` file (LH rule = right-hand Rodrigues with -angle). Doors: lobby `door_sec` (`sky_towera/model.cfg:62` angle1 = 1.4), `locker_door1..3` (1.4), `cab_door` (1.4), `flap` (-0.84). Blender frame: prop front = -y; security room = x 6.0..11.85.

| Door | Committed cfg, **LH rule** | Committed cfg, RH rule | `SIGN = -1` regenerated cfg, **RH rule** | `SIGN = -1`, LH rule |
|---|---|---|---|---|
| lobby `door_sec` | centroid x 6.000 -> **6.493 (into room)** | 6.000 -> 5.507 (out) | **6.493 (into room)** | 5.507 (out) |
| `locker_door1/2/3` | y -0.260 -> **-0.403 (out)**, d_act 0.477 -> 0.370 | -> -0.117 (into carcass) | **-0.403 (out)** | -0.117 (in) |
| `cab_door` | y -0.260 -> **-0.447 (out)**, d_act 0.443 -> 0.302 | -> -0.073 (in) | **-0.447 (out)** | -0.073 (in) |
| `flap` | y -0.420 -> **-0.513, z 0.275 -> 0.233 (out/down)**, d_act 0.381 -> 0.295 | -> -0.327 (into body) | **-0.513 (out/down)** | -0.327 (in) |

- Under ONE rule (LH, `SIGN = +1`), the lobby door opens into the security room and all 5 prop doors open outward. Under the opposite rule (RH) with `SIGN = -1`, the same holds. **H1 is fixed.**
- `gen_configs.py` with `DOOR_SWING_SIGN = -1` (copy `qa3b_neg`) changes exactly 6 lines: `sky_towera/model.cfg` Door_Sec 1.4 -> -1.4 and the 5 prop `angle1` values. The one-line fix moves the lobby and all props together. PASS.
- Fully open leaf extents (LH, committed): the locker leaves stay in front of the carcass (carcass y >= -0.250; open leaves y -0.547..-0.258) at disjoint x (-0.455..-0.386 / -0.155..-0.086 / 0.145..0.214), so the open doors do not intersect each other. Cabinet open y -0.636..-0.258 (body y >= -0.250). Flap open y -0.613..-0.413, z 0.143..0.324 (body y >= -0.400). No leaf penetrates its body.

**Mutation tests of `test_kit.py`** (one change per scratch copy, full test run):

| Mutation | Result | Expected |
|---|---|---|
| `cab_door` orient +1 -> -1 | exit 1, `FAIL ExtinguisherCabinet: door cab_door swings away from its action point (inward)` | fail: OK |
| `flap` orient -1 -> +1 | exit 1, `FAIL VendingMachine: door flap swings away from its action point (inward)` | fail: OK |
| only `locker_door2` orient -> -1 | exit 1, `FAIL Locker: door locker_door2 swings away from its action point (inward)` | fail: OK |
| lobby `door_sec` axis point order swapped (`build_towera.py:224-225`, which reverses the lobby swing) | **exit 0, `KIT GEOMETRY TESTS: PASS (34 assets)`** | **should fail: NOT detected (R-M1)** |
| `DOOR_SWING_SIGN = -1` only | exit 0, PASS | pass (the tests are sign-independent by design): OK |

### R3. `Land_SKY_Props_Base.c` (lock compatibility NONE)
- xref: resolves (R1 #8). The script class `Land_SKY_Props_Base extends House` (the same base as `Land_SKY_TowerA_Lobby.c:16`) matches config `class Land_SKY_Props_Base: HouseNoDestruct` (`addons/sky_props/config.cpp:16`, scope 0). The 10 props inherit from it. Vanilla has no `HouseNoDestruct` script class, so `House` (`4_world/entities/game/super/building.c:85`) is the right script parent.
- Cited vanilla lines are correct: `3_game/entities/building.c:167` `int GetLockCompatibilityType(int doorIdx)` returns `1 << EBuildingLockType.LOCKPICK`; `3_game/enums/ebuildinglocktypes.c:3` `NONE = 0`; `actionlockdoors.c:39` `tool.GetKeyCompatibilityType() & building.GetLockCompatibilityType(doorIndex)`. `actionunlockdoors.c:38` has the same mask, so unlocking is blocked too. PASS. Whether child config classes resolve to this script class stays PENDING B5 (in-game, P3-25).

### R4. Perf fixes (from the committed P3Ds)

| Item | Evidence | Result |
|---|---|---|
| Shadow hull + door boxes | Locker Shadow 48 tris, selections `locker_door1..3` (1 hull + 3 doors); VendingMachine 24 tris with `flap`; ServerRack 12; Kitchenette 12 | PASS |
| No shadow for `interior_small` | Desk, Sofa, Bed, ExtinguisherCabinet: no Shadow Volume LOD | PASS |
| Monitor on wood screen band | Desk / ReceptionDesk / Cubicle Res0: one `sky_wood` quad at V 0.95-1.00; no `sky_atlas` in these 3 models. In `sky_wood_co`, rows 973-1023 are uniform (25, 40, 61) | PASS |
| Cubicle Res2 = screens only | Res2: `sky_fabric` only, 18 faces / 36 tris, 1 section | PASS |
| Cabinet glass = 1 quad | Res0 `sky_glass_ca` 1 face; Res1 `sky_glassfar_co` 1 face; none in Res2 / Shadow | PASS |
| `sky_wood` nohq procedural | `sky_wood.rvmat:12` `#(argb,8,8,3)color(0.5,0.5,1,1,NOHQ)`; `gen_configs.py:51` | PASS |
| Fabric 8 px weave | `gen_textures.py:644` `((xx // 4) + (yy // 4)) % 2` (8 px period) | PASS |
| BUDGETS shadow keys | `skyspec.py:352-354`: small 60, medium 100, `interior_small` without shadow; `check_assets.py:45,72` | PASS |
| `PROP_CAPS` | `skyspec.py:357` `{"per_floor": 25, "per_tower": 600, "aisle_min": 1.2}`; D27 | PASS (enforced by the batch-5 layout generator, not yet) |

### R5. `skygeo.run_cli` exit code
- `--only NoSuchProp`: Blender **without** `--python-exit-code` exits **1**, printing `KeyError: 'NoSuchProp'` and then `EXPORT FAILED`.
- `--out` under a regular file: exits **1**, printing `NotADirectoryError ...` and then `EXPORT FAILED`.
- Arbitrary new `--out` dir: exits 0 and creates `<out>/../assets`. PASS for `build_kit.py` / `build_props.py`. See R-L1 for `build_towera.py`.

### R6. Docs
- `TESTING.md:238` `## 14. Interior props (batch 3, sky_props)` contains P3-01..P3-25 (P3-25 = lockpick / B5). The Sign-off table has the `Interior props §14` row. PASS.
- `manifest.yaml`: `props: status: built-unverified` with a note; `textures:` has `sky_wood` (co, 1024, nohq/smdi/as procedural) and `sky_fabric` (co + nohq, 512, 8 px weave). PASS.
- DECISIONS: D29 (L3/L4/Info) and D30 (P1 anchor) added. PENDING P1 row rewritten. PASS.

### Status of the previous findings
H1 fixed (R2). M1 fixed in skyspec, PENDING and D30, but one stale instruction remains (R-M2). M2 fixed (R6). L1 fixed for `run_cli` (R5; `build_towera` remains, R-L1). L2 fixed. L3 accepted (D29). L4 fixed (D29, D30).

### New findings

**High:** none.

**Medium**
- **R-M1 - The lobby convention check cannot fail.** `test_kit.py:85-96` `convention_check()` requires the lobby leaf centroid to move more than 0.02 m *away* from `door_sec_action`. The action point (5.6, 7.5, 1.1) is 0.4 m on the lobby side but lies laterally on the leaf centre line, so the wrong swing also moves the centroid away from it:
  - correct swing: d 0.4038 -> 0.9860;
  - reversed swing: d 0.4038 -> 0.4288 > threshold 0.4238.
  Mutation (lobby axis order swapped) gives `PASS (34 assets)`. The D30 anchor is therefore not guarded. The committed geometry is correct (R2), so this is a test gap, not a bug.
  Likely fix (enforce-coder / asset-pipeline): check the signed direction, e.g. `c1[0] > p0[0] + 0.3` (into the room, +x) or `dot(c1 - c0, act - hinge) < 0` with a margin. Then re-run the axis-swap mutation and confirm it fails.
- **R-M2 - The D-01 failure instruction still says to flip only the lobby angle.** `TESTING.md:96` (D-01: "flip `angle1` (`assets/MANUAL_STEPS.md` C)") and `assets/MANUAL_STEPS.md:39-41` ("flip `angle1` to `-1.4` in `assets/gen_configs.py` (model.cfg `Door_Sec`)") contradict P1, P3-22 and D30. A tester who finds the lobby opening outward and follows D-01 would fix the lobby alone and leave every prop door opening inward. That is the M1 risk, still present on the first door anyone tests.
  Fix: point D-01 and MANUAL_STEPS C to `DOOR_SWING_SIGN = -1` + `gen_configs.py`. Also update the elevator line in C to `ELEVATOR_SLIDE_SIGN` (P2) instead of "swap the axis point order".

**Low**
- **R-L1 - `build_towera.py` `main()` (`:419-431`) still exits 0 on an export exception.** It does not use `run_cli`, and `Build-SkyAssets.ps1:48-49` relies on `$LASTEXITCODE`. This is pre-existing and Tower A is frozen, but the same `try/sys.exit(1)` (or `--python-exit-code 1` in the ps1) closes it.

**Info**
- I-R1: The prop swing test reads `orient` from skyspec, not the generated `angle1` from `model.cfg`. Consistency relies on `gen_configs.py --check` (passes) and the formula in `gen_configs.py:190`. R2 checked the committed `model.cfg` directly.
- I-R2: "LEFT-hand rule (Blender frame)" equals a right-hand rotation in the P3D/engine left-handed frame (y-up). The wording is correct as written, because it names the frame. Testers should judge by the lobby door only, as PENDING P1 says.
- I-R3: D24 still says "right-hand-rule convention". D30 explicitly supersedes it. P3-14 cites D24 for the flap fix (D30 is the anchor).
- I-R4: ReceptionDesk (24 tris) and Cubicle (60 tris, all 5 boxes) keep Geometry-copy shadows. Both are within the medium budget of 100 and not in the D26 hull list; acceptable.
- I-R5: The ReceptionDesk screen quad has V flipped relative to Desk/Cubicle. The screen band is uniform, so it has no visible effect.

### In-game status
P3-01..P3-25 and D-01: **NOT RUN** (no DayZ on this host). Updated expectations from this re-gate:
- P3-14 expects out/down.
- D-01 and P3-10..14 must be judged together under P3-22. Fix R-M2 first.

GATE: PASS
