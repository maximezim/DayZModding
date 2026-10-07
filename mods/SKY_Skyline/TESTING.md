# SKY_Skyline Tower A: in-game test checklist (DayZDiag + dedicated)

**Status: NOT RUN.** None of these checks can run on the Linux environment where this checklist was written: it has no DayZ, DayZDiag, DayZ Server, DayZ Tools or `P:`. Every PASS/FAIL cell below is empty and has to be filled in on the Windows workstation.

The static run (asset, config, economy, script cross-reference, layout, Blender geometry, tooling self-test and dry-run build) is in `reviews/qa_static_run.md`. Read its findings QA-01 to QA-04 first: they change the preconditions below.

How to use this checklist:
- Run each gate on **DayZDiag** first (fast loop, file patching).
- Then run the rows marked **[DED]** again on the **dedicated** server (signed, `verifySignatures=2`, `BattlEye=1`, `allowFilePatching=0`).
- Fill in PASS/FAIL with the log line(s) and their timestamp, or a screenshot name under `reviews/img/`.
- **Evidence rule for every row** (where the Evidence/Logs cell is empty or "none"): quote the newest relevant
  `script_*.log` / RPT / ADM lines with timestamps (or "no SKY lines" + the validation `summary.md` path), and a
  screenshot `reviews/img/<ID>.png` for any visual expectation. A row without evidence is not a PASS.
- ID namespaces: `P1`..`P9` are parameters in PENDING_VERIFICATION.md, test rows use `P3-xx`, `P5-xx` etc.;
  `S1`..`S8` in FPS_PROTOCOL.md are FPS scenarios, `S-0x` here are setup steps, `S1`..`S6` in reviews/perf_review.md
  are the Tower A perf scenarios.
- `district_template*.yaml` ship with an unfilled site: `-Layout` runs need the site filled in (survey) or
  `-AllowPlaceholder` (offline / smoke only; the summary is marked "placeholder").

---

## 0. Setup (do once, in order)

| ID | Step | Expected | PASS/FAIL |
|---|---|---|---|
| S-01 | Run `tools\setup\Get-ToolchainStatus.ps1` (includes Python + Pillow / PyYAML / numpy for the asset tools; `Install-Toolchain.ps1 -Only Pillow` installs all three). If anything is missing, run `tools\setup\Initialize-WorkDrive.ps1` (P: + game data) and `tools\setup\Initialize-TestServer.ps1` | DayZ, DayZ Tools, DayZ Server and P: all found. `server\serverDZ.diag.cfg` and `server\serverDZ.dedicated.cfg` rendered | |
| S-02 | Run `mods\SKY_Skyline\assets\Build-SkyAssets.ps1` | The `.paa` files (41 at batch 6, plus the D60 `sky_hq_facade` co / nohq / smdi) are written into `addons\sky_textures\data` (36) and `addons\sky_items\data` (5). They include all 40 referenced names (QA-03). Every `dz\` path resolves on P:: `concrete.rvmat`, `glass.rvmat` and `env_land_co.paa` are the unverified ones (QA-08). Ends with `SKY assets ready` | |
| S-03 | Run `tools\build\Build-Mod.ps1 -ModName SKY_Skyline`, then `tools\build\Sign-Mod.ps1 -ModName SKY_Skyline` | 4 PBOs in `build\@SKY_Skyline\addons`. `sky_items` and `sky_towera` are binarized; `sky_scripts` and `sky_textures` are pack-only. Newest `DayZ Tools\Bin\Logs\AddonBuilder*.rpt` has no `non-convex`, `missing`, `Cannot open` or `error` lines for SKY files | |
| S-04 | Create the test mission. Do **not** edit the vanilla copy (`CLAUDE.md`, QA-10). Copy `server\mpmissions\dayzOffline.chernarusplus` to `server\mpmissions\dayzOffline.chernarusplus_sky`. Run `tools\setup\Initialize-TestServer.ps1 -Mission dayzOffline.chernarusplus_sky -Force`; it skips the copy because the folder exists. For dedicated, put the same folder in `<ServerDir>\mpmissions\` | Both rendered configs show `template = "dayzOffline.chernarusplus_sky"` | |
| S-05 | **Check cfggameplay is enabled (QA-01).** The templates already contain `enableCfgGameplayFile = 1;`; confirm it is in the rendered `server\serverDZ.diag.cfg` / `server\serverDZ.dedicated.cfg` (re-render with `Initialize-TestServer.ps1 -Force` if not) | Without this line nothing spawns. Vanilla reads the flag in `3_game/cfggameplayhandler.c:53` | |
| S-06 | Install placement into the test mission (`placement\README.md` §2). Copy `placement\out\sky_objects.json` to `<mission>\sky\sky_objects.json` and merge `cfggameplay_snippet.json` into `<mission>\cfggameplay.json`. For tests on the placeholder site, use the output of §9 (survey) instead, once it exists | `cfggameplay.json` still parses (no `JsonFileLoader`/`ErrorEx` line in the server script log) | |
| S-07 | Install the economy files into the test mission (`economy\README.md`): `sky_ce\` + `cfgeconomycore` snippet, `mapgroupproto` groups, `cfgeventspawns` snippet. Delete `<mission>\storage_1` for a fresh CE | Server RPT: no `[CE]` errors naming `SKY_` or `Land_SKY_` | |
| S-08 | Launch diag: `tools\build\Build-And-Run.ps1 -ModName SKY_Skyline -FilePatching`, which wraps `tools\launch\Start-DiagLocal.ps1 -Mods SKY_Skyline -FilePatching`. Server flags: `-dologs -adminlog -netlog -freezecheck` | Server and client start, the client connects to 127.0.0.1 | |
| S-09 | Launch dedicated **[DED]**: `tools\build\Build-And-Run.ps1 -ModName SKY_Skyline -Mode Dedicated`, which builds, signs and calls `tools\launch\Start-DedicatedServer.ps1 -Mods SKY_Skyline`; it needs `Deploy-Mod.ps1` first. Join with a normal client and `-mod=@SKY_Skyline` | No signature kick. RPT has no `Modified data`, `Signature check` or `kicked` lines | |
| S-10 | Find the tower. In the diag script console, teleport to the tower origin T, which is the `Land_SKY_TowerA_Lobby` position in `sky_objects.json` | Eight modules are visible and stacked with no gaps: lobby, 5 office floors, roof, core | |

Stop all game processes with `Get-Process DayZDiag_x64,DayZServer_x64 -ErrorAction SilentlyContinue | Stop-Process`.

**Logs.** Always read the newest file in each folder and quote exact lines with their timestamps.
- Diag: `server\profiles\diag-server\` and `server\profiles\diag-client\`
- Dedicated: `server\profiles\dedicated\`
- File types:
  - `script_*.log`: script compile and runtime errors, `[SKY]` info lines
  - `*.RPT`: engine, config, addon and asset loading; `[SKY] WARNING:` lines go here because `SKY_Log.Warn` uses `PrintToRPT`
  - `*.ADM`: admin log
  - `crash_*.log` and `*.mdmp`

**Diag tools used below.** Menu labels differ between builds, so verify them in yours.
- DayZDiag diag menu: hold Win+Alt.
  - Geometry and LOD visualisation, if your build has it; otherwise use Object Builder on the MLOD.
  - AI navmesh visualisation.
  - Statistics.
- Diag script console: spawn items and infected, teleport, set time.

**Coordinates.** "Model" coordinates are tower-local: x = east, y = up, z = north, origin = top of the lobby slab at the footprint centre. Stop heights are 0 / 7 / 10.5 / 14 / 17.5 / 21 / 24.5.

---

## 0b. One-command validation (static checks, build, sign, deploy, server, logs)

```
tools\tests\Invoke-ModValidation.ps1 -ModName SKY_Skyline -DryRun                       # prints every command
tools\tests\Invoke-ModValidation.ps1 -ModName SKY_Skyline -Blender "<blender.exe>"       # + Blender geometry tests
tools\tests\Invoke-ModValidation.ps1 -ModName SKY_Skyline -Layout mods\SKY_Skyline\placement\district_template.yaml -Minutes 5
```
It runs the Python generators in `--check` mode, `check_assets`, the placement self-test (and
`test_kit` / `test_towera` with `-Blender`), then `Build-Mod`, `Sign-Mod`, `Deploy-Mod`. With `-Layout` it
generates the objectSpawnersArr JSON and merges it plus the SKY economy into a **copy** of the
vanilla mission (`<ServerDir>\mpmissions\<mission>.validation`, rendered `server\serverDZ.validation.cfg`).
It starts the dedicated server (`verifySignatures = 2`, `BattlEye = 1`), waits `-Minutes`, stops it,
copies the new RPT / script / ADM / crash logs to `build\validation\<timestamp>\logs` and writes
`summary.md` + `summary.json` (PASS/FAIL; exit code 1 on FAIL). Re-analyse a log folder with
`-AnalyzeOnly <folder>`. FAIL patterns: script errors, compile errors, crashes, signature problems,
and missing objects/files/config entries **that name the mod** (vanilla noise is listed as notable).
The patterns are a first guess: tune them on the first real run (B9).

## 1. Collisions (Geometry LOD)

| ID | Preconditions | Steps | Expected | Evidence | PASS/FAIL |
|---|---|---|---|---|---|
| C-01 | S-10 | Walk the whole lobby perimeter along the glass facade, then through the 3 m south entrance (model x -1.5..1.5) | You cannot pass through the glass. The entrance is free and 3 m high. The reception desk blocks you | screenshot | |
| C-02 | lobby | Walk into the security room walls from outside (model x 5.875..6.125 and z 5.875..6.125) and try to jump onto the room roof (y 3.2) | Walls are solid. You cannot get onto the roof without a ladder | | |
| C-03 | stair core at the lobby | Take the stairs from the lobby (y 0) up to the roof (y 24.5): every flight and landing (landings every 1.75 m), and every stair door on the south face (x -1.8..-0.6) | No snagging, no falling through flights or landings, no stuck spots. A stair door opening exists at every stop | `script` and RPT have no position-correction spam | |
| C-04 | each office floor 1-5 | Walk the facade perimeter, the core walls and the SW partition room (door at x -8.5..-7.5) | Solid everywhere. The door gap is 1.0 m wide and 2.1 m high | | |
| C-05 | each floor | Stand on a slab next to the core and above the module seam. Crouch, go prone, roll, and drop items in 4 places per floor | **Nothing falls through the slab seam between stacked modules** (slab y -0.3..0 meets the module below at its top, 3.2). Items stay on the floor | | |
| C-06 | roof | Walk along the parapet (1.1 m) on all 4 sides, try to vault it, and walk around the core penthouse (up to about 28 m) | Parapet is solid; vaulting over it is a fall, which is the vanilla rule. The penthouse walls are solid | | |
| C-07 | elevator cab, every stop | Stand inside the closed cab (model x -1.25..1.25, z 1.5..4.25) and push against the 4 walls and the closed doors. Jump | You cannot leave a closed cab. You cannot clip into the shaft. Doors are solid when closed | | |
| C-08 | cab doors open | At each stop, walk out of the cab through the open doors | The 2 cm leaf lip at each side (QA-09) does not snag you | | |
| C-09 | security room (§5 opens it) | Walk the room interior and push into the 3 cm gap between the room and the facade | Nothing to clip into | | |
| C-10 | site with a ground drop under the lobby > 0.3 m (only on a sloped survey site) | Walk into the visual foundation skirt below the lobby slab from outside | **QA-04 is expected to FAIL here.** The skirt has no Geometry, so you walk through it. Record whether you can get under the slab | screenshot | |
| C-11 | vehicle | Drive a car into the lobby glass and the core | The vehicle collides, the building is not damaged, and there is no physics explosion | | |

## 2. Bullet hits (Fire Geometry)

Use an M4A1 and a Mosin (`M4A1`, `Mosin9130`), aiming at an `Inventory_Base` dummy or a second player behind each surface.

| ID | Steps | Expected | Evidence | PASS/FAIL |
|---|---|---|---|---|
| F-01 | Shoot through the facade glass (lobby, floor 3) at a target 2 m behind it | **Glass does not stop bullets the way concrete does.** The round goes through and hits the target. Glass impact effect and sound | screenshot of the hit, target damage in the client | |
| F-02 | Shoot the slab from below (lobby ceiling = floor 1 slab), the core walls and the roof parapet | Concrete impact. Rifle rounds do not pass through 0.25-0.30 m concrete | | |
| F-03 | Shoot the elevator doors and the lobby security door (metalplate) | Metal impact. No pass-through for pistol rounds. Record what rifle rounds do | | |
| F-04 | Shoot the SW partition walls on floors (bricks) | Masonry impact. Behaviour is like vanilla brick walls | | |
| F-05 | Shoot the reception desk (wood_desk) | Wood impact. Rounds pass through | | |
| F-06 | Check RPT and `script_*.log` during F-01 to F-05 | No `penetration`, `material` or `Cannot open` errors. If one appears, the vanilla path from QA-08 is wrong | | |
| F-07 | Use a weapon from inside a closed cab and from the stairwell | Bullets do not leak through core walls between floors | | |

## 3. View blocking (View Geometry / occluders)

| ID | Steps | Expected | Evidence | PASS/FAIL |
|---|---|---|---|---|
| V-01 | Player A stands on floor 2 and player B on floor 3 directly above. Each looks down or up. Also toggle 3rd person | Neither sees the other through the slab. 3rd-person camera does not clip through the slab | screenshot from both clients | |
| V-02 | A is in the stairwell and B is on the landing outside a closed core wall | No visibility through core walls. Players are only visible through the open stair door | | |
| V-03 | A is outside at street level and B is inside floor 2 next to the facade | **Glass is see-through both ways.** Players, infected and loot are visible through it | | |
| V-04 | Look from 50-300 m at the tower, rotating around it | No occluder culls objects that are visible through the glass. No popping of players or vehicles behind the tower edges (occluders sit only on slabs and core sides) | | |
| V-05 | A is in the lobby security room with the door closed, B is outside the room | Not visible through the concrete room walls. **Visible through the facade glass** (the room's N and E walls are the facade; note it as a design question) | | |
| V-06 | Diag menu: show View Geometry / occluders, if available | It matches the Object Builder layout: slab occluders with the core hole, and 2 core side occluders | | |

## 4. Door animations

| ID | Steps | Expected | Evidence | PASS/FAIL |
|---|---|---|---|---|
| D-01 | Open `door_sec` (via §5) and watch it from the corridor | It rotates about the vertical hinge at model (6.0, *, 7.0), **swings into the room (+x)**, about 80° (`angle1 = 1.4`), takes 1.0 s, and does not pass through the wall. If it opens outward or into the wall, it FAILS: set `DOOR_SWING_SIGN = -1` in `assets/skyspec.py`, run `python3 assets/gen_configs.py`, rebuild, and re-run D-01 and §14 P3-10..14 (P1: one value moves the lobby and every prop door together) | video or screenshot at the open position | |
| D-02 | Use the exit button to close and open again, from inside | Same direction. Collision follows the leaf: you cannot walk through the open leaf | | |
| D-03 | Call the elevator at every stop | Leaves slide **apart, outward**: `_a` toward -x and `_b` toward +x, 0.58 m in 1.2 s. They close the same way after 8 s | | |
| D-04 | Second client watching from the landing while another rides the elevator | Animation is in sync on both clients. Only the car's stop opens; the other 6 landings stay closed | | |
| D-05 **[DED]** | While the doors are open, relog the observer (and reconnect a second client) | After reconnect the door phase matches server state (open or closed): net sync of `m_SkyDoorsOpen` / `m_SkyCarLevel` | | |
| D-06 **[DED]** | Relog while `door_sec` is open, then relog after it relocks | The client shows the true state each time. No "open but locked" mismatch: you cannot walk through a visually closed door | | |

## 5. Keycard door (lobby `door_sec`, tier 2, relock 60 s)

Spawn the cards in the script console: `SKY_Keycard_T1`, `SKY_Keycard_T2`, `SKY_Keycard_T3`, plus `Lockpick`, `M67Grenade`.

| ID | Preconditions | Steps | Expected | Log evidence | PASS/FAIL |
|---|---|---|---|---|---|
| K-01 **[DED]** | fresh server start | Try to open `door_sec` with the vanilla "Open door" action | It is locked: rattle sound (`doorMetalSmallRattle`), no opening | none | |
| K-02 **[DED]** | T1 in hands | "Swipe keycard" on the door | Notification "Access denied / insufficient clearance". The door stays locked | ADM: `Player "<name>" (id=<id> pos=<...>) SKY keycard denied (insufficient clearance) tier 1/2 at Land_SKY_TowerA_Lobby <pos>`. Script log: `[SKY] SKY keycard denied ... by <id>` | |
| K-03 | T1, swipe 5 times within 5 s | Repeated swipes | Swipes inside 1.5 s are ignored silently. At most **one ADM denial line per 5 s** per player | count the ADM lines | |
| K-04 **[DED]** | T2 in hands | Swipe | The door unlocks and opens. The card loses 10 health | Script log: `[SKY] keycard T2 opened door 0 at Land_SKY_TowerA_Lobby by <id>` | |
| K-05 | T3 in hands | Swipe while locked | Opens, same as K-04 with `T3` | same line with `T3` | |
| K-06 **[DED]** | after K-04 | Wait 60 s without touching the door. Repeat with someone standing in the doorway | At about 60 s the door closes and locks again; the vanilla open action rattles again. Record what happens to the player in the doorway | timestamps of the open and relock | |
| K-07 | after K-04 | Open and close the door with vanilla actions during the 60 s window, then swipe again | Only one pending relock: the door locks 60 s after the **last** swipe or exit | | |
| K-08 | inside the room, door locked | Aim at the door from inside and use "Press exit button". Then try the same from outside the room | Inside: the door opens without a card and relocks after 60 s. Outside: the action is **not** offered, and a forged request is ignored | none expected | |
| K-09 | inventory | Look at T1, T2 and T3 in hands and on the ground | Three different colours: green T1, amber T2, red T3. **If all look the same, QA-02 is confirmed** (missing `model.cfg` `sections[]`) | screenshot | |
| K-10 | ruined T2 (set its health to 0 in the console) | Swipe | The "Swipe" prompt is hidden (`CCINonRuined`). If you force it, the server answers "card damaged" | ADM `SKY keycard denied (card damaged)` if it was reached | |
| K-11 **[DED]** | Lockpick in hands | Target `door_sec` | No "Unlock" or "Lock" action is offered (lock type NONE). Vanilla doors elsewhere still accept lockpicks (regression) | | |
| K-12 | door locked | Shoot 2 magazines into the door, hit it with melee, and throw an M67 at it | The door survives (damage zone takes 0) and stays locked and closed | RPT/script: no damage-zone errors | |
| K-13 **[DED] (security M3, release gate)** | door locked | Restart the dedicated server (stop it, start `Start-DedicatedServer.ps1 -Mods SKY_Skyline`). Within 30 s of the first player joining, try the vanilla open | **Locked after restart.** Repeat 3 restarts. A fail here makes M3 High and blocks release | RPT: no `[SKY] WARNING: ... keycard door 'door_sec' not found` or `length mismatch` | |
| K-14 | 2 players | A swipes T2 while B holds a T1 at the door | Only A's card opens the door. B gets a denial while the door is locked, and no prompt while it is open | | |
| K-15 | swipe from 3 m (beyond reach), or from the other side of the room wall | Swipe | The prompt is not offered beyond reach. The server ignores requests made through the wall from more than 2.5 m from `door_sec_action` | | |

## 6. Elevator (`Land_SKY_TowerA_Core`, 7 stops, max 4, cooldown 4 s, doors 8 s)

Timing reference:
- Close: 1.3 s.
- Travel: 1.5 s + 0.5 s per stop (for example, lobby to roof = 1.3 + 4.5 s).
- Doors open for 8 s.
- A new departure is possible 4 s after the last one.

| ID | Preconditions | Steps | Expected | Log evidence | PASS/FAIL |
|---|---|---|---|---|---|
| E-01 | car idle at L0 | At each stop L0..L6, stand at the call button (right of the doors, 1.25 m high) and use "Call elevator" | The car comes empty and the doors open at your stop. If it is already here with the doors closed, they just open | ADM: no teleport line (empty car) | |
| E-02 | inside the cab, at each stop | Use the panel (east cab wall): "up one floor", "down one floor", "lobby", "roof" | You arrive at the expected stop at the same spot in the cab. Doors open there and auto-close after 8 s | ADM per occupant: `Player "<n>" (id=..) was teleported from: <..> to: <..>. Reason: SKY elevator <from>-><to>` | |
| E-03 | at the limits | At L6 look for "up" and "roof"; at L0 look for "down" and "lobby". Also look while the doors are already open at your stop (Open) | These actions are not offered | | |
| E-04 | 2 riders | Ride, then press a command within 4 s of the previous departure | Notification "Please wait..." and no departure | | |
| E-05 | 4 players in the cab | Press "roof" | All 4 arrive. 4 ADM teleport lines | 4 lines | |
| E-06 | 5 players in the cab (needs 5 clients) | Press a floor | "Overloaded (max 4)". The doors stay open | | |
| E-07 | 4 in the cab, a 5th runs in while the doors close | Rider 1 presses a floor; the 5th player sprints into the cab before the doors finish closing | At departure the doors reopen and everyone sees "Overloaded (max 4)" | ADM: no teleport lines; screenshot of the message | |
| E-08 | A is in the cab at L0 with the doors closed, B at L3 | B presses "Call elevator" | "Elevator in use". The car does not move with A inside | | |
| E-09 | A at L3 inside a cab where the car is not (for example after E-12) | A uses "Elevator: open doors" | The car (empty) travels to L3 and opens: the rescue path. If the car is occupied elsewhere, A sees "Elevator in use" | | |
| E-10 | cab at a stop | Stand on the landing outside the cab and try the panel actions; stand inside the cab and try "Call" | Panel actions work only inside the cab within 1.6 m of the panel. "Call" works only outside, within 1.6 m of the call button | | |
| E-11 | rider in a vehicle or attached (if reproducible) | Get a rider into an attached/vehicle state inside the cab (e.g. carried/restrained, if the build allows), then press a floor | That rider is not teleported (vanilla exclusion) | ADM: teleport lines only for the free riders | |
| E-12 **[DED]** | A rides L0 to L6 | A presses Exit (logout) during TRAVEL. Then a second test: Alt-F4 during TRAVEL. Reconnect | No script error at arrival. Record whether A ends up at L6 (teleported during the logout timer) or in the closed L0 cab. If in a closed cab, E-09 frees A | script log has no `NULL pointer`. ADM teleport line (may show cached name or `(DEAD)` rules) | |
| E-13 **[DED]** | car at L4, players inside, server restart | Restart and reconnect | The car resets to L0 with the doors closed. Players in the L4 cab use E-09 to get out. No stuck players | RPT: no `[SKY] WARNING: ... missing memory point` or `invalid elevator config` | |
| E-14 | 1 client spams every elevator action as fast as the UI allows for 60 s | Hold the action key on each panel action in turn (floor buttons, open doors, call) for 60 s; watch the script log | Requests within 1.5 s are ignored. No error spam. At most 3 SKY CallLaters pending (perf S2) | script log: no SKY errors; ADM: <= 1 trip per 1.5 s | |
| E-15 | dead or unconscious player in the cab | Kill or knock out one rider, then press a floor | Only living players are moved. An unconscious player cannot press buttons | | |
| E-16 | during E-02 | Watch for rubber-banding or falling after arrival (`SetPosition`) on the rider and on an observer | No teleport-back, no fall damage, no falling through the floor of the destination cab | RPT: no position-correction lines | |

## 7. AI pathing (infected)

| ID | Steps | Expected | Evidence | PASS/FAIL |
|---|---|---|---|---|
| A-01 | Diag menu: enable navmesh visualisation near T after server start. The spawner calls `ProcessMarkedObjectsForPathgraphUpdate()` | Navmesh covers the lobby floor, every stair flight and landing, every floor and the roof. **No navmesh crosses the glass facade.** Door openings (lobby entrance, stair doors, partition door, open `door_sec`) are connected | screenshots per level | |
| A-02 | Spawn 3 infected (`ZmbM_CitizenASkinny`) at the plaza, aggro them, run into the lobby and up the stairs to floor 3, then to the roof | They follow through the entrance and up the stairs, landing by landing, and reach you | | |
| A-03 | Stand behind the facade glass on the lobby side, infected outside | They path around to the entrance. They do not walk or attack through the glass | | |
| A-04 | Close yourself in the security room (door locked) | Infected cannot path through the locked door. They do not glitch through the room walls | | |
| A-05 | Ride the elevator with infected chasing | Infected are not teleported. They take the stairs or lose the target | | |
| A-06 | Watch server RPT/script during A-02 to A-05 (perf S4) | No path-failure spam and no frame spikes | RPT grep | |

## 8. Loot (Central Economy)

| ID | Preconditions | Steps | Expected | Evidence | PASS/FAIL |
|---|---|---|---|---|---|
| L-01 | S-07 | Server start with a fresh `storage_1` | RPT has no `[CE][TypeCheck]` or unknown category/usage/tag lines for `SKY_Keycard_T1..T3` or `Land_SKY_*`. The `sky_ce` folder is loaded | RPT lines | |
| L-02 | tower spawned | Run the survey with `"exportRadius": 40` (§9), then merge the `Land_SKY_*` `<group>` lines from `<mission>\storage_1\export\mapgrouppos.xml` into `<mission>\mapgrouppos.xml`. Wipe storage and restart | `mapgrouppos.xml` has 7 SKY groups (lobby, 5 floors, roof). There is no core entry, which is intended | file diff | |
| L-03 | after L-02 | Walk the lobby, floors 1-5 and the roof after the CE has settled (about 5 min) | Loot appears **on** the floors at the `skyspec.LOOT` points: lobby 6 + 4 (room), floor 10, roof 3. Nothing is inside walls, under slabs or floating. At most 8 / 6 / 2 items per module | screenshots. A diag CE loot-point overlay, if available | |
| L-04 | after L-02 | Spawn the cards with the console, then wait for natural spawns (or temporarily raise their nominal in a scratch types copy) | `SKY_Keycard_T1/T2` spawn in Office/Town (T2 also in Police). T3 spawns in Military. Spawned cards are worn (damage 0-0.3) | | |
| L-05 | security room | Check loot behind `door_sec` | Tools and weapons only. Note whether a T2 card can spawn inside the room (QA-13) | | |

## 9. Placement (survey to strict layout)

| ID | Steps | Expected | Evidence | PASS/FAIL |
|---|---|---|---|---|
| P-01 | Pick a candidate centre. Write `server\profiles\dedicated\SKY_survey_request.json`, or the `diag-server` one: `{ "label": "site1", "center": [X, Z], "yaw": 0, "halfW": 13, "halfD": 13, "step": 2.0, "exportRadius": 0 }`. Start the server (`Build-And-Run.ps1 -ModName SKY_Skyline -Mode Dedicated -NoClient` or diag) | About 15 s after mission start, `SKY_survey_result.json` appears next to the request | script log: `[SKY] site survey 'site1' written: $profile:SKY_survey_result.json (<n> objects, ground <min>..<max>)` | |
| P-02 | Copy the result to `placement\surveys\site1.json`. In `layout.yaml` set `site.center`, `site.survey`, and `placeholder: false`. Run `python placement\sky_layout.py --strict` | `status: PASS` with no errors. Reject sites with "drop > skirt", an existing `Land_*` in the footprint, or overlap | console output | |
| P-03 | Deploy `placement\out\*` (S-06), restart, and teleport to the site | The lobby slab sits 0.05 m above the highest ground sample. No terrain pokes through the floor. No module gaps. The yaw is correct | screenshot | |
| P-04 | A malformed request file (bad JSON) | | RPT: `[SKY] WARNING: survey request invalid: ...`. The server keeps running | | |

## 10. Roof drop event (`StaticSKYRoofDrop`)

| ID | Steps | Expected | Evidence | PASS/FAIL |
|---|---|---|---|---|
| R-01 | Merge the `cfgeventspawns` snippet with the **real** site Y (from P-02), then wipe storage and start | One supply box (`StaticObj_Misc_SupplyBox1_DE` or `2_DE`) appears on the roof at one of the 4 `roof_drop_N` points (±8 m, ±8 m), resting on the slab, not floating or buried | RPT: no event errors for `StaticSKYRoofDrop`. Screenshot | |
| R-02 | Open the box | 3-6 loot items | | |
| R-03 | Wait for the lifetime (2700 s), or use the console to clean it up, and restart | The event respawns. There is never more than 1 box | | |
| R-04 | Check the box against the parapet, the helipad decal and the core penthouse | No overlap or clipping | | |

## 11. Clean logs (gate for every run above)

At the end of every session, grep the **newest** files in each profile folder (diag-server, diag-client, dedicated):

```powershell
$p = 'server\profiles\diag-server'   # repeat for diag-client, dedicated
$log = Get-ChildItem $p -Filter 'script_*.log' | Sort-Object LastWriteTime | Select-Object -Last 1
$rpt = Get-ChildItem $p -Filter '*.RPT'        | Sort-Object LastWriteTime | Select-Object -Last 1
$adm = Get-ChildItem $p -Filter '*.ADM'        | Sort-Object LastWriteTime | Select-Object -Last 1
Select-String -Path $log.FullName -Pattern 'SCRIPT \(E\)', "Can't compile", 'NULL pointer', 'SKY'
Select-String -Path $rpt.FullName -Pattern '\[SKY\] WARNING', 'Object spawner failed', 'Cannot open object', 'Cannot load', 'missing in CfgPatches', 'Updating base class', 'No entry .*SKY', '\[CE\]\[TypeCheck\]', 'sky_', 'SKY_', 'Signature', 'Modified data', 'kicked'
Select-String -Path $adm.FullName -Pattern 'SKY keycard denied', 'Reason: SKY elevator'
Get-ChildItem $p -Filter 'crash_*.log'; Get-ChildItem $p -Filter '*.mdmp'
```

| ID | Expected | PASS/FAIL |
|---|---|---|
| G-01 | `script_*.log` (server and client) has **0** `SCRIPT (E)`, `Can't compile` or `NULL pointer` lines that mention SKY files or classes | |
| G-02 | RPT has **0** `[SKY] WARNING:` lines. The possible ones are: `missing memory point`, `invalid elevator config`, `keycard door ... not found`, `length mismatch`, `invalid target level`, `survey ... failed`. RPT also has 0 of `Object spawner failed to spawn Land_SKY_*`, `Cannot open object SKY_Skyline\...` and missing `.paa`/`.rvmat` | |
| G-03 | RPT has no `Updating base class` or `missing in CfgPatches` lines for `SKY_Skyline_*` | |
| G-04 | ADM contains only the expected SKY lines: denials (rate limited) and one teleport line per rider per trip | |
| G-05 | No `crash_*.log` or `.mdmp` | |
| G-06 **[DED]** | Same as G-01 to G-05 with `verifySignatures=2`, `BattlEye=1`, `allowFilePatching=0`, plus no signature or BattlEye kicks | |

## 12. Regression (vanilla nearby)

| ID | Steps | Expected | PASS/FAIL |
|---|---|---|---|
| X-01 | Use a vanilla house door near the site (open, close, lockpick) | Unchanged vanilla behaviour | |
| X-02 | Use vanilla actions near the tower: eat, drink, open other doors, ladders elsewhere | The 8 SKY actions do not appear on non-SKY targets | |
| X-03 | Vanilla loot in towns near the site | Unchanged (the merged `mapgroupproto` did not break other groups) | |

## 13. Performance

For the kit, props, floor variants and the district (batches 1-5) use `FPS_PROTOCOL.md` (configs A/B/D/D0/D-dec/E, positions Q1-Q6, scenarios S1-S8, results template). For Tower A alone, run the DayZDiag FPS protocol exactly as written in `reviews/perf_review.md` §4:
- configs A and B (baseline / tower); config C (3 x 3 Tower A) is replaced by FPS_PROTOCOL config E
- VD1 and VD2
- positions P1-P6
- server scenarios S1-S6
- pass/fail thresholds from that table

Record the results there, or link them from here.

| ID | Expected | PASS/FAIL |
|---|---|---|
| PERF-01 | All `perf_review.md` §4 thresholds are in "Pass" | |
| PERF-02 | All `FPS_PROTOCOL.md` §4 thresholds are in "Pass" (district: configs A/B/D/D0/D-dec/E; prerequisites §0 done) | |
| B3-MC | Search `P:\DZ\structures\**\data\*.rvmat` for a Stage3 texture ending in `_mc` (PENDING B3). Expected: found / not found, with one example path | |
| B9-VAL | First real `Invoke-ModValidation.ps1` run: clean start -> summary 0 SKY FAIL lines; then rename one SKY texture in a scratch build -> summary FAIL naming it (PENDING B9). Expected: both behave as stated | |
| B10-EXP | Re-export into a **scratch** folder (never over `addons\`): `python mods\SKY_Skyline\assets\blender\build_floors.py -- --out C:\tmp\skyexp\addons --only Floor_HQ` (create `C:\tmp\skyexp\addons` and `C:\tmp\skyexp\assets` first). Open the P3D in Object Builder (DayZ Tools), then compare `python tools\assets\p3d_inspect.py` on old vs new (PENDING B10, D60). | Object Builder opens it with every LOD, selection and named property; p3d_inspect shows identical LOD / selection / triangle counts | | |

## 14. Interior props (batch 3, `sky_props`)

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
| P3-02 | Desk | spawn; crouch under the desk; walk into the legs; shoot the top | Collision on the top (0.72-0.75 m) and legs. Monitor screen (wood sheet screen band) shows a dark blue-grey screen with no stretched texture. **No shadow volume** (category `interior_small`, D26). LOD switch. | | | |
| P3-03 | Cubicle | spawn; walk around and into the 3 screens (1.4 m); enter through the open side; shoot a screen | Screens block the player and block AI view (View LOD). The L desk collides. Fabric texture tiles without seams. Res 2 shows the screens only (desk tops drop out, D28). | | | |
| P3-04 | ServerRack | spawn; walk into it; shoot it | Solid 0.6 x 1.0 x 2.0 m. Rack atlas front faces -z. Shadow. LOD switch. | | | |
| P3-05 | Sofa | spawn; walk into it; try to stand on the seat | Collision on the base, back and arms. Blue fabric with no stretching. **No shadow volume** (D26). | | | |
| P3-06 | Bed | spawn; walk into the frame and headboard | Collision as modelled. The pillow shows in Res 0 only. **No shadow volume** (D26). | | | |
| P3-07 | Kitchenette | spawn; walk into the counter and fridge; walk under the upper cabinets | The counter and fridge (1.9 m) block. Upper cabinets (1.5-2.2 m, rear 0.3 m) collide at head height. Appliance atlas cell on the fridge front. | | | |
| P3-08 | All 10 props | for each: walk 5 / 30 / 80 / 200 m away (and zoom) | LOD switches Res 0 -> 1 -> 2 with no holes or flicker. Shadows (hull boxes on Locker/VendingMachine/ServerRack/Kitchenette, D26) switch with the LODs; door shadows swing with the doors. No z-fighting on the atlas quads (offset 1 mm). | | | |
| P3-09 | All 10 props | place one inside the lobby next to a vanilla loot spot (or a SKY lobby loot point) | Loot is not hidden inside or under the prop, and the prop does not block a loot position. No loot spawns inside the prop (props have no proxies). | | | |
| P3-10 | Locker door 1 (left) | stand in front; look at the door; `Open door`; then `Close door` | The action appears at about 0.7 m in front (`locker_door1_action`). The door rotates about its **left** vertical edge **outward toward the player** (~80 deg, 0.8 s). It does not pass through the carcass or the shelf, and does not hit door 2. `doorMetalSmallOpen` / `Close` play at the door. | screenshot open/closed; video | | |
| P3-11 | Locker doors 2 and 3 | same as P3-10 for each door; then open all 3 at once | Each opens independently and about its own left edge. With all 3 open there is no leaf intersection. Collision follows each leaf. | | | |
| P3-12 | Locker, each side | try the action from behind / beside the locker and from inside the swing arc | The action appears only within reach of the front. Opening while you stand in the arc: the door pushes or stops as vanilla doors do (no player launch). Closed door blocks; open door is passable only where the leaf is not. | | | |
| P3-13 | ExtinguisherCabinet door | spawn on a wall (back at local y = 0, front -z); open and close | Glass door hinges on its left edge and swings **outward** ~80 deg. It does not enter the cabinet or hit the extinguisher. Glass is transparent in Res 0 (opaque `glassfar` from Res 1, D28). Sound plays. **No shadow volume** (D26). Shoot the glass: penetration is glass (P3). | | | |
| P3-14 | VendingMachine flap | open and close the pickup flap | Tilts **outward/down** about its bottom edge (~48 deg). QA H1 fixed with per-door `orient` (D24, convention D30); record the actual direction. | screenshot | | |
| P3-15 | Door sounds | for each door type, open, close and fully open | `soundOpen/Close` heard at `<door>_action`, about 1 m in front. No `soundLocked` (doors are never locked). Nothing logged in RPT about missing sound classes. | RPT | | |
| P3-16 [DED] | Door sync, 2 clients | client A opens locker door 2 and the flap; client B watches | B sees the same phase and animation. Collision for B matches the visual. | | | |
| P3-17 [DED] | Relog | with doors open, relog A; connect a third client | Doors show the server state after reconnect (open stays open). | | | |
| P3-18 [DED] | Server restart | open doors, restart the server | Doors are back to `initPhase 0` (closed) after the restart. This is expected because objectSpawnersArr props do not persist door state; record it. | | | |
| P3-19 | Damage | shoot, melee and frag each door and each prop | No damage and no destruction (all `damage = 0`; P5 `FragGrenade` class name). No RPT warnings about the armor class. | RPT | | |
| P3-20 | Death | die (e.g. suicide) next to an open locker; respawn | No change to the prop. The body does not fall through the prop or into it. | | | |
| P3-21 | Dedicated vs listen | repeat P3-10, P3-13 and P3-14 on the dedicated server | Same direction and behaviour as diag. No `Signature check` / `Modified data` kick for `sky_props.pbo` (key in `keys\`). | RPT, server log | | |
| P3-22 | Swing sign (P1) | **only after D-01 (lobby door) is confirmed** | If D-01 (lobby door) opened outward, set `DOOR_SWING_SIGN = -1`, run `python3 assets/gen_configs.py`, rebuild, and re-run D-01 and P3-10..14: the lobby door must open into the room and every prop door outward. If the lobby is right but a prop door is wrong, flip that door's `orient` in `skyspec.py` instead. | | | |
| P3-23 | Regression (vanilla nearby) | open a vanilla building door and a vanilla locker/cabinet near the props; pick up loot from a vanilla container | Vanilla door actions, sounds and loot are unaffected. No new RPT lines for vanilla classes. | | | |
| P3-24 | Regression (SKY) | lobby `door_sec` (D-01), a street prop (bus stop) and its atlas cells | Unchanged from batches 1-2. Atlas row 0 is pixel-identical. | | | |
| P3-25 | Lockpick (D25 / PENDING B5) | with a lockpick in hand, look at a closed locker door, the cabinet door and the flap | No `Lock door` / `Unlock door` action is offered on any prop door. If one appears, apply the B5 fix. | screenshot | | |

## 15. Floor and roof variants (batch 4, `sky_floors`)

Static results: `reviews/batch4_qa.md`. Spawn the modules on the unchanged Tower A core (layout `floors:` / `roof:` keys, batch 5) and run each row in diag, then dedicated.


Setup for all items: diag (`Build-And-Run.ps1 -ModName SKY_Skyline -FilePatching`) and dedicated (`-Mode Dedicated`, signed). Spawn a
test stack by hand at a flat site: Tower A lobby + core at T. Put the variant under test at each core stop z = 7.0, 10.5, 14.0, 17.5, 21.0
(floors) and 24.5 (roof), using objectSpawnersArr with the same yaw as the core. Logs: newest `script_*.log`, `*.RPT` and `*.ADM` per profile.
Expected clean logs: no `Cannot open object SKY_Skyline\sky_floors\...`, no `missing in CfgPatches`, no `SCRIPT (E)`.

| ID | Module | Steps (diag, then dedicated) | Expected | Evidence | Result |
|---|---|---|---|---|---|
| F4-01 | all 5 | Spawn each class once; check the RPT | Loads with no missing model/texture/rvmat lines. Dedicated: no signature kick for `sky_floors.pbo` | RPT lines + timestamps | |
| F4-02 | Apartments, Hotel, Mechanical | Stack the variant at every core stop (5 floors) | Slabs meet the core walls with no visible gap. The stair door (south face, x -1.8..-0.6) and elevator door (north face) open onto the floor at every stop | screenshot per stop | |
| F4-03 | Roof_Garden, Roof_Mechanical | Place it at the roof stop (z 24.5) on the core | The core penthouse rises through the hole. Stair and elevator roof-stop doors open onto the roof | screenshot | |
| F4-04 | all floors | Stand on the slab beside the core and above the module seam. Crouch, prone, roll, and drop items at 4 spots per floor | **Nothing falls through the seam** between modules (slab -0.3..0 meets the walls' top 3.2) or the slab/core gap | | |
| F4-05 | all floors | Jump/vault against the partition tops and the facade at ceiling height | No climbing into the slab above. Walls stop flush at 3.2 | | |
| F4-06 | Apartments | Walk from the stair door to every apartment | Every apartment has **two** hall doors (north/south 1.2 m, west/east 1.0 m, 2.1 m high) (security H1 fix, D35) and an internal door between its two wings; `test_kit` flood fill passes statically | screenshots | |
| F4-07 | Hotel | Walk the corridor and enter all 8 rooms + 2 suites | The 4 inner rooms open off the corridor; the 4 corner rooms are entered through the suites (connecting rooms, by design) | | |
| F4-08 | Mechanical | Walk around all 4 plant units and along the louvre | The units are solid and full height (3.2 m, not climbable, D35). There are no openings in the louvre. Ducts are visual only | | |
| F4-09 | Roofs | Walk the parapet perimeter. Climb the planters (0.5 m) and HVAC units (1.5-2.4 m) | Parapet 1.1 m and solid. Planters (0.5 m, 1.25 m inside the parapet) can be stepped onto; you cannot step from a planter over the parapet. Shrubs have no collision and are Res0-only decoration | | |
| F4-10 | Apartments, Hotel | Navmesh visualisation after spawn (`ProcessMarkedObjectsForPathgraphUpdate`) | Navmesh connects the hall/corridor to every room through each door opening (1.0-1.2 m). It does not cross partitions or the facade | screenshots | |
| F4-11 | Apartments, Hotel, Mechanical | Aggro 3 infected on the floor, then run from the core into the farthest room and around the plant units | Infected follow through the door openings and around the units. They do not walk through partitions or get stuck in the 1.0 m doors | | |
| F4-12 | Roofs | Aggro infected from the stair door to each roof corner | They path around planters/HVAC units to the corners | | |
| F4-13 | all floors | View Geometry: A in a room, B in the hall behind a partition; then A on floor N, B on floor N+1 | Partitions and slabs block sight both ways (AI does not detect through them). The louvre blocks sight (mechanical) | | |
| F4-14 | all | Fire Geometry: shoot the partitions (bricks), slab (concrete, P3), louvre/units/HVAC (metalplate), and facade glass (P3) | Penetration and impact effects match the material. Rounds do not leak between floors | | |
| F4-15 | Roofs | Merge a `StaticSKYRoofDrop` with this roof's drop positions from `skyspec.ROOF_DROP_POINTS` (+-8, +-2): use `placement/sky_layout.py` from batch 5 on (it writes the drop positions per roof class); an older generated snippet has the helipad (+-8, +-8) positions and is wrong for these roofs. Wipe storage, restart | The supply box sits on the open roof east/west of the core, not inside a planter/unit and not over the core | RPT: no event errors | |
| F4-16 | all | LOD switches: walk away 10 -> 500 m, and use the diag LOD display | Res0 -> 1 -> 2 -> 3 with no holes. Watch for pop of HVAC units, planters and shrubs at Res1 -> 2 (L4). Res3 is one band per floor (glassfar / louvre) and one closed box per roof (D35) | screenshots per LOD | |
| F4-16b | Roofs | Player A prone / crouched on a garden or mechanical roof; player B on a taller tower or hill at Res3 range (zoom) | A stays visible: the Res3 lid is at the walkable level, not on the parapet top (security re-gate N1) | screenshots | |
| F4-17 | Mechanical | Corner close-up of the louvre | No z-fighting on the corner strip (E/W bands now stop inside the N/S bands) | | |
| F4-18 | all | Shadows in sun | The slab/parapet shadows are correct. Note the missing shadows from partitions/louvre/HVAC (L4) | | |
| F4-19 | all | Relog and server restart | Modules are static (objectSpawnersArr) and reappear identically. No persistence issues | | |
| F4-20 | all | 2 players on different floors of the same stack, dedicated | Both see the same geometry. No desync at the module seams | | |
| F4-21 | all | Death on the floor/roof (fall from the parapet, shot) | The body stays on the slab and does not fall through | | |
| F4-R | Tower A (regression) | Repeat S-10, C-04, C-05 and E-02 on the unchanged office stack | Same results as before batch 4 (Tower A P3Ds are byte-identical) | | |

## 16. Street kit (batch 1, `sky_street`)

Spawn the district template (`Invoke-ModValidation.ps1 -Layout mods\SKY_Skyline\placement\district_template.yaml`,
site filled in) or single pieces via a scratch objectSpawnersArr. RPT gate as in §11.

| ID | Assets | Steps | Expected | Evidence | Diag | Ded |
|---|---|---|---|---|---|---|
| K1-01 | all 24 kit classes | spawn each once | no `Cannot open object` / texture / rvmat lines, no `Updating base class` | RPT | | |
| K1-02 | Road_*, Intersection_*, Street_* | walk and drive (car, 30 and 60 km/h) across every tile joint of a 3 x 3 grid | no bump, snag or fall-through at seams (P8 `ROAD_GEO_THICKNESS`), no gap at the skirt | video | | |
| K1-03 | road tiles | look at markings at 2 / 30 / 150 m | alpha-tested paint, no z-fighting on the slab, dashes tile along the road | screenshots | | |
| K1-04 | road tiles | footsteps and tyres on asphalt | surface sound = concrete_ext placeholder (P6); note if an asphalt surface exists on P: | | | |
| K1-05 | road + infected | aggro infected across a tile seam and an intersection | they path across (ECE_UPDATEPATHGRAPH navmesh) | | | |
| K1-06 | Sidewalk, Sidewalk_Corner, Curb | step up/down the 0.15 m curb, vehicle against the curb | walkable without jitter; vehicles climb or stop as expected | | | |
| K1-07 | Manhole | walk / drive over it | flush, no flicker, no collision bump (Roadway only, B2) | | | |
| K1-08 | StreetLight, TrafficLight | night | lamp head reads lit without bloom (P7); traffic light face static, not emissive (D8); no dynamic light | screenshots | | |
| K1-09 | BusStop | shoot the glass and the frame; walk into the bench | glass transparent, bullets pass glass (P3) and stop on metal; bench solid | | | |
| K1-10 | Dumpster, Planter, Barrier_* | walk, drive, shoot through gaps | collision as modelled, steel barrier gaps shootable, foliage alpha without black fringes | | | |
| K1-11 | Wreck_Sedan, Wreck_Van | cover, line of sight, interact | solid cover, AI sight blocked by the van; no vehicle/inventory actions (static) | | | |
| K1-12 | Billboard A-D | view each at 5 / 100 / 400 m, front and back | each variant shows its poster on all Res LODs; back is metal | screenshots | | |
| K1-13 | all | shadows at noon and 17:00 | tall props cast shadows (shadow LOD), no leaks | | | |
| K1-14 [DED] | all | restart the server, relog, 2 clients | same objects and variants, no duplicates, no `Modified data` kicks for `sky_street.pbo` | RPT | | |
| K1-15 | regression | Tower A modules, vanilla roads/lights nearby | unchanged | | | |

## 17. Textures, decals, window sets (batch 2)

### 17.1 Decals
| ID | Steps | Expected | Diag | Dedicated |
|---|---|---|---|---|
| DC-01 | Spawn `Land_SKY_Decal_Dirt`, `_Cracks` and `_Graffiti` flush on a facade via the layout `decals:` key (offsets 1.5 / 2.0 / 2.5 cm, D19) | All 3 render. No RPT error about missing Geometry (PENDING B1). | | |
| DC-02 | Spawn `Land_SKY_Decal_Graffiti_A..D` | 4 different designs. Lettering is fully readable, including "NO CURFEW" (D17). No pink/white missing-texture quad. | | |
| DC-03 | View dirt at 2, 10 and 60 m, day and night | No visible rectangular outline at the quad edges (M1). Streaks read as run-off. | | |
| DC-04 | View cracks at 2, 10 and 60 m | Lines stay visible at distance and do not vanish through mips (perf L5). Hard alpha edges are acceptable. | | |
| DC-05 | Place dirt in front of Tower A glass and in front of a graffiti decal; orbit the camera | No z-fighting between overlapping decals (per-type offsets). No blended-sorting pop against glass (L1). | | |
| DC-06 | Walk through, shoot and drive into each decal; vehicle at 30 km/h | No collision, no bullet impact on the decal (render-only). Behind-wall cover is unchanged. Single-sided: invisible from behind. | | |
| DC-07 | Relog and restart the server | Decals are still present (static spawner), same variant. | | |
| DC-08 | 2 clients | Both see the same graffiti variant at the same spot. | | |
| DC-09 | Perf: FPS_PROTOCOL config D-dec at Q7 (1 vs 12 dirt decals on T4 face E = +11, 10 m and 60 m) | FPS delta recorded. Feeds the D19 caps. | | |

### 17.2 Window sets (need a test quad or a future facade module; no shipped P3D uses them yet)
| ID | Steps | Expected | Diag | Dedicated |
|---|---|---|---|---|
| W-01 | Apply `sky_windows.rvmat` + `sky_windows_co.paa` to a test plane (Object Builder) and view day and night | 16 cells with interiors, blinds and frame. No emissive glow. | | |
| W-02 | Same with `sky_windows_lit.rvmat` at night | Lit cells read warm, with no bloom blow-out (PENDING P7). Dark cells do NOT glow (PENDING B4, L2). | | |
| W-03 | Swap lit/unlit per instance via `hiddenSelectionsMaterials` (D23) | The swap works without a script. No extra section is visible in the diag stats. | | |
| W-04 | View at 1024 at 5 m | Cells are acceptably sharp (~170 px/m). | | |

### 17.3 Facade sheets (used by the apartment / hotel facades since D53, see §19)
| ID | Steps | Expected | Diag | Dedicated |
|---|---|---|---|---|
| F2-01 | Apply `sky_brick` / `sky_concpanel` to a test plane | Procedural AS/SMDI look right (no black or over-shiny surface). Brick reads 21.5 cm at a 3.44 m U tile (D20). | | |

### 17.4 Regression
| ID | Steps | Expected | Diag | Dedicated |
|---|---|---|---|---|
| R2-01 | Tower A lobby/office/core/roof and keycards at the same spot as before batch 2 | Identical look up to D53 (no Tower A file changed since 681ecdc until the realism pass; after D53 use §19 for the look, gameplay unchanged). Elevator/keycard actions as in `TESTING.md`. | | |
| R2-02 | Batch 1 billboard A-D, roadmark and street tiles | Unchanged. Billboard variants still swap. | | |
| R2-03 | Vanilla wall decals or graffiti nearby (if any) | Unaffected. No vanilla texture overridden. | | |

## 18. Economy and district placement (batch 5)

Static results: `reviews/batch5_qa.md`. Deploy the district template on a surveyed site (fill
`site.center/yaw/survey`, `placeholder: false`, `--strict` PASS) with
`tools\tests\Invoke-ModValidation.ps1 -Layout mods\SKY_Skyline\placement\district_template.yaml -Minutes 10`.

| ID | Steps | Logs | Expected | PASS/FAIL |
|---|---|---|---|---|
| P5-01 | Start the server with the filled template | RPT: no `Cannot create object`, no `missing in CfgPatches`. script log: no `SCRIPT (E)` from `objectspawner.c` | 4 towers (office / apartments / hotel / office+mech) stacked without gaps, roofs garden x2, helipad, mechanical | |
| P5-02 | Walk every street tile, then drive a car over all seams | none | No tile under terrain, no hole (H1), one street plane, no steps at seams (L3 fixed), no wheel snag (P8) | |
| P5-03 | Look at each street light at night | none | Head over the **carriageway** (QA M1 fixed: pole on the -X sidewalk); emissive reads "lit" (P7); pole does not block the 2 m sidewalk (B8) | |
| P5-04 | Count lights per street | none | Every 2nd straight tile **on each street** (L2), none on intersections/crossings | |
| P5-05 | Decals: check each placed decal from outside, inside and at grazing angle | none | Only on the mechanical louvre storey (D44), facing outward, no z-fight (D19), no see-in/see-out asymmetry | |
| P5-06 | Furniture per floor: visit each furnished level of each tower | none | Props at FURNISH positions on the slab (not floating/sunk), aisles >= 1.2 m, every room reachable, core doors clear, extinguisher cabinet mounted on the core wall at 1.0 m | |
| P5-07 | Rotated site (yaw != 0): repeat P5-01/06 on one tower | none | Props and decals rotate with the tower (yaw composition) | |
| P5-08 | Restart the server twice | no duplicate-spawn warnings | Same objects, no duplicates (spawner objects are not persistent) | |
| P5-09 | Count entities and FPS at the district centre (perf protocol) | probe lines in script_*.log | Entity count = report total (323 for the template; probe count, FPS_PROTOCOL §0.1). Server frame ms from the probe, not the RPT (RPT has no FPS) | |
| L5-01 | Rerun the survey with `exportRadius` covering the district | script log `[SKY] site survey`; `storage_1/export/mapgrouppos.xml` written | `Land_SKY_*` entries for floors, roofs **and the 4 loot props** (B7). Record their `pos`/`a` and check that y is the model origin (slab top / prop base) | |
| L5-02 | Merge the exported entries, wipe storage, restart | RPT: no `[CE]` errors for SKY groups | Loot on floors at the listed points: apartments 3 per unit, hotel 1 per room + suites, mechanical 4-5 points | |
| L5-03 | Inspect each loot prop: Locker (open doors), Desk, ReceptionDesk, Kitchenette (Cubicle/Bed carry no loot, D43) | none | Items **on** the surfaces: locker floor + upper shelf (L1: not floating/falling), desk top, counter, worktop. None inside a mesh | |
| L5-04 | Pick up loot from a locker bay and from the upper shelf | ADM: normal | Reachable via the door, no clipping through the locker sides | |
| L5-05 | Categories per group | none | Only the listed categories (e.g. Kitchenette food, mech floor tools/containers) | |
| L5-06 | Roof drops on every roof type | RPT: no event errors | Supply boxes at (+-8, +-8) on the helipad and (+-8, +-2) on garden/mech roofs, on the open roof | |
| L5-07 | Relog / server restart persistence | none | Loot respawns per CE timers. No duplication on furniture | |
| L5-08 | B7 rollback check: if L5-01 shows no prop entries, remove the prop groups | none | Floor loot unaffected | |
| Z5-01 | Merge the generated `zombie_territories_snippet.xml` zone (template: dmin 6 / dmax 12, r 54) into `env/zombie_territories.xml` | RPT: no territory errors | Infected spawn at street level around players | |
| Z5-02 | Spend 10 min on each floor type with 1 and then 3 players | none | Count infected per floor vs README targets: lobby 3-5, office 1-2, apartments 2-3, hotel 2-3, mech 0-1, roofs 0-1 (B6) | |
| Z5-03 | Pathing: DayZDiag navmesh view on each floor type with furniture spawned | none | Navmesh around props (ECE_UPDATEPATHGRAPH), through doors, stairs, not through glass. Infected follow players to the roof | |
| Z5-04 | Death + respawn near the district, then reconnect | none | No infected stuck in furniture or walls | |
| R5-01 | Regression: vanilla town loot and infected nearby | no new CE warnings | Vanilla buildings still get loot. Vanilla zones unchanged | |
| R5-02 | Regression: Tower A lobby security door + keycard + elevator on each variant | ADM: swipe/elevator lines as in TESTING.md | Works the same on every floor variant | |
| P5-YAW | T4 (yaw 270) carries the asymmetric `office_open` set: on T4 floor 1 check the cubicles stand on open floor north/south of the core, not in the SW office, and the decals sit on T4's louvre storey | none | Props and decals where the report says; if mirrored, P9 `YAW_SIGN = -1` | |

---

## 19. Realism pass (D53)

Static results: `reviews/realism_gates.md`; preview renders in `reviews/img/` (`exterior`, `entrance`,
`lobby`, `office`, `facade_close`, `roof`, `realism_*`). Use the district template or the Tower A slice
with `floors:` / `roof:` set to each variant. Gameplay rows §1-§15 must still pass unchanged.

| ID | Steps | Expected | Diag | Dedicated |
|---|---|---|---|---|
| RP-01 | Walk around Tower A at 5, 50 and 300 m | Corner piers, fins, cornices and spandrel bands read at 50 m; no flicker (z-fighting) on the cornice / spandrel / corner pier; no glass blending beyond Res1 (glassfar only). | | |
| RP-02 | Lobby: walk in through the entrance, around the columns, benches and planters | Entrance clear under the canopy; canopy and sign not standable (no Geometry); sign reads `SKYLINE TOWER`, not mirrored; columns / benches / planters collide; loot points still spawn (§8). | | |
| RP-03 | Office floor: look up, walk the SW office door | Tile ceiling with light panels, not visible from the floor above (single-sided); door frame and skirting do not narrow the 1 m opening; columns collide. | | |
| RP-04 | Apartment and hotel floors from outside and inside | Brick / precast facade, windows recessed with frames, sill stones and (brick) soldier course; plaster ceiling; oak door frames on every door. Brick courses ~7.5 cm (UVTrim true scale). | | |
| RP-05 | Shoot at an apartment / hotel facade pier, sill band and a window from inside | Piers and bands stop rifle rounds (masonry / concrete); windows pass as glass (P3 `PENETRATION`). | | |
| RP-06 | Prone behind an apartment sill band (0.9 m), viewed from outside | Not visible through the band (View Geometry); visible through the window above it. | | |
| RP-07 | Plant floor | Louvre blades with dark backing, pipes overhead (no collision at head height), control panels on the units. | | |
| RP-08 | Roofs: helipad, garden, mechanical | Copings; helipad HVAC units and mast; garden benches and pergola (posts collide, beams do not); mechanical units with fans and panels, water tank collides; all roof-drop crates land clear (§10). | | |
| RP-09 | Core: stairs and every stop | Handrail along the well wall; elevator and stair door frames on every stop; doors open fully past the frames. | | |
| RP-10 | Diag stats at the tower (FPS_PROTOCOL S2) | Sections / tris within D54; client FPS within the protocol thresholds against the pre-D53 build. | | |

## 20. Splendour pass (D55)

Static results: `reviews/splendour_gates.md`; renders `reviews/img/d55_*.png` (day and night).
Gameplay rows §1-§15 and §19 must still pass unchanged.

| ID | Steps | Expected | Diag | Dedicated |
|---|---|---|---|---|
| SP-01 | Lobby by day | Marble floor reads polished (gloss, joints), limestone core cladding with `SKYLINE TOWER` strip, granite piers / plinth, pendants hang clear of heads (lowest 3.66 m over the desk), lounge chairs / table / tree pots collide, loot points spawn (§8). | | |
| SP-02 | Office floor | Light panels sit in the ceiling grid (no z-fight with the tiles), plants collide, art not mirrored. | | |
| SP-03 | Apartment floor | Parquet in the flats, tiles in the hall, beige / sage walls, curtains and radiators at every window, flower boxes outside, rugs flat (no flicker), art not mirrored. | | |
| SP-04 | Hotel floor | Wainscot + dado rail on both wall faces, runner round the core (no overlap flicker at the corners), sconces glow, art in the rooms. | | |
| SP-05 | Night (`-ServerTime` 23:00) on every lit module | Point lights at the pendants / panels: lobby 4, floors 2 each, warm (cool in offices / plant floor); none by day; no shadows; script log clean (P10). | | |
| SP-06 | Night from the street at 50 / 300 m | Emissive fixtures read through the windows; no glow beyond Res1 (fixtures are Res0/Res1 only). | | |
| SP-07 | Core at every stop | Wayfinding plate matches the level (L, 1-5, R) next to the elevator and the stair door, EXIT at the stair, nosings on every step, bulkhead light per landing. | | |
| SP-08 | Roofs | Pad edge lights, obstruction lights on masts, garden trees / loungers (collide) / string and bollard lights, ladder on the tall unit; roof drops land clear (§10). | | |
| SP-09 | FPS_PROTOCOL 4.1 | Within the thresholds. | | |

## 21. City buildings (D56; packages `sky_city_res|block|com|civic|ind|env` since D60)

Static results: `reviews/city_wave1_gates.md`; renders `reviews/img/city_*.png`; estimate and progress
`CITY_PLAN.md`. Spawn single buildings with the admin tools / objectSpawnersArr (front = -Y faces
the street), intact + damaged + ruined of each archetype. When a type passes, add its catalog id to
`skyspec.CITY_TESTED` and re-run `assets/city_progress.py`.

| ID | Steps | Expected | Diag | Dedicated |
|---|---|---|---|---|
| CB-01 | Walk in through the front door of every intact / damaged building | Door opens inward (orient -1 under P1), closes; lockpick can lock it like a vanilla house; ruined buildings have an open doorway | | |
| CB-02 | Climb every stair to the top floor and back | Steps / ramps walkable (Roadway), headroom at every landing, guard rail on the top landing, no fall-through | | |
| CB-03 | Walk every room of every floor | No invisible walls, no clipping into furniture, every room reachable (test_city flood fill); furniture never blocks a doorway | | |
| CB-04 | Ruined buildings: walk the floor below the collapse and the floor above it | Rubble collides and can be walked around; the cut edge of the floor above drops you onto the rubble, never into the void below the ground; jagged walls collide | | |
| CB-05 | Damaged / ruined windows from outside and inside | Broken windows show the soot and the dark void, still block movement (Geometry); boarded windows stop bullets (wood) | | |
| CB-06 | Shoot through glass, brick, render, stone, cladding, roller doors, cell bars | Penetration per material (P3); bars stop movement but not bullets / sight | | |
| CB-07 | Loot (CE running) | Items spawn on the floors (city_loot.json points), none in the stair wells or behind the collapse | | |
| CB-08 | Night (`-ServerTime` 23:00) | Intact buildings light up (2 lights, cool in offices / police / warehouses); damaged and ruined stay dark; script log clean (P10) | | |
| CB-09 | LOD walk-away 5 -> 300 m | Res1 / Res2 / Res3 switches without holes; ruined silhouettes keep the collapse at Res3 | | |
| CB-10 | Signs, awnings, sign text | Names read correctly (not mirrored): BAKERY, PHARMACY, HARDWARE, OFFICES, DEPOT 3, POLICE | | |

## 22. City wave 2 and generated districts (D57)

Static results: `reviews/city_wave2_gates.md`; renders `reviews/img/city2_*.png`, `reviews/img/district_*.png`.

| ID | Steps | Expected | Diag | Dedicated |
|---|---|---|---|---|
| CD-01 | Spawn each wave-2 archetype (3 states) and run CB-01..CB-10 on it | As section 21; villas: pitched roof collides only inside the walls, eaves are visual; garage block entered through the two open bays | | |
| CD-02 | Rubble lots A-D | Rubble climbable (Roadway), wall stumps collide, no loot, no floating pieces | | |
| CD-03 | Generate a small spawner district (2 x 2 blocks, `fill`) on a surveyed flat site, deploy with `Invoke-ModValidation.ps1 -Layout` | Report PASS; buildings sit on the sidewalk level (no step > 0.5 m), fronts face the streets, no overlap with tiles / towers; RPT clean | | |
| CD-04 | Walk the generated district | Corner shops on corners, terraces flush, detached houses with gaps, small pieces sparse; ruin mix reads per zone (frontline mostly ruined) | | |
| CD-05 | Night on the generated district | Only intact buildings lit (P10) | | |
| CD-06 | `city_template.yaml` (target terrain) | `city_objects.csv` written; importing it into a custom terrain is P11 | | |

## 23. City wave 3, tall towers, landmark blocks (D58)

Static results: `reviews/city_wave3_gates.md`; renders `reviews/img/city3_*.png`, `reviews/img/district3_*.png`.

| ID | Steps | Expected | Diag | Dedicated |
|---|---|---|---|---|
| CW-01 | Spawn each wave-3 archetype (3 states) and run CB-01..CB-10 on it | As section 21; double-corridor buildings: every room reachable from the corridor, ruins keep the corridor | | |
| CW-02 | Courtyard block: street door -> passage -> gallery -> yard gate; stairs to every floor | Walk the ring gallery on every floor; yard is open to the sky, no slab over it | | |
| CW-03 | Parking garage: walk up the ramps deck by deck, then the stair | Ramps walkable (Roadway), rails stop falls at every opening; U-turns at the strip ends | | |
| CW-04 | Church, town hall, bank: front door on the axis, tower / cupola / pediment | No climb route onto roofs, tower or cupola; spire and fins have no player collision issues | | |
| CW-05 | Gas station and cafe forecourts on a surveyed slope | Forecourt sits on the sidewalk, skirt hides the ground drop; canopy / parasols out of reach | | |
| CW-06 | Substation, water tower, metro entrances A/B | Not enterable (substation fence breached only when ruined), no loot, ladder is visual | | |
| CW-07 | Tall towers: layout with `core: T15`, `T23`, `T33` + `roof: crown` | Elevator serves every stop (LOBBY / ROOF / UP / DOWN), doors at every stop; crown lights at night | | |
| CW-08 | `city_template.yaml` (closed street cells, landmark blocks) | `city_objects.csv` written; merged blocks hold the landmarks; no street tile under a building | | |

## 24. DayZ ambiance, vegetation, terrain-safe fill (D59)

Static results: `reviews/d59_gates.md`; renders `reviews/img/d59_*.png`.

| ID | Steps | Expected | Diag | Dedicated |
|---|---|---|---|---|
| CV-01 | Walk a weathered building close up (brick, panel, stucco, limestone) | Walls tile without stretching or seams; grime overlays sit on the wall (no z-fighting, no visible quad edge); RPT clean of rvmat / texture errors | | |
| CV-02 | Vegetation: weeds, bushes, birch, dead tree, ivy | Cards alpha-tested (no black halos), weeds / bushes walk-through, tree trunks collide, crowns never inside a room | | |
| CV-03 | Ruins: saplings and weeds on rubble | Nothing floats; sapling trunk visual only (rubble mound is the collision) | | |
| CV-04 | Spawner district with `clutter_cutters` (P12) | No grass through lobby / ground floors; measure the cleared area around one cutter | | |
| CV-05 | Terrain-aware fill on a surveyed slope | Report lists the skipped lots; every placed building within the 1.5 m skirt, entrances within 0.5 m of the sidewalk | | |
| CV-06 | FPS walk through a dense overgrown block (FPS_PROTOCOL) | Client cost of grime quads and vegetation cards within the budget notes of `reviews/d59_gates.md` | | |

## 25. Content pass: facade variants, HQ, Lobby_B, skybridge, weathering (D60)

Layout: `placement/skyline_template.yaml` (offline it runs with warnings; fill the site to deploy).
Packages: `sky_floors` (floors, skybridge), `sky_towera` (Lobby_B), `sky_textures` (`sky_hq_facade`, 4K).

| ID | Steps | Expected | Diag | Dedicated |
|---|---|---|---|---|
| CP-01 | Walk each office floor variant (`office_concrete`, `office_brick`, `hq`) | Same plan as the Tower A office (partitions, columns, loot points, furniture fit); no gaps at the corners; night lights on like the office floor | | |
| CP-02 | HQ facade close up from the plaza and from 300 m | Bronze fins / spandrels / granite read crisply (4K); no shimmering; RPT has no error for `sky_hq_facade` | | |
| CP-03 | Lobby_B: keycard door, security exit button, loot | Behaves exactly like the lobby (§5): tier-2 swipe, relock 60 s, exit only from inside | | |
| CP-04 | Lobby_B frontage | Signs readable on S / E / W, awnings over the S shopfronts, nothing blocks the entrance | | |
| CP-05 | Skybridge: climb the steps from each roof, cross, look down | Steps walkable (Roadway ramp), no fall-through at the parapet, glass walls collide and stop bullets, roof blocks rain/view | | |
| CP-06 | Skybridge: infected and players at both landings | Nobody stuck on the steps; roof drops / crates on both roofs still clear | | |
| CP-07 | Weathering: lobby piers, roof parapets, roof weeds | Grime sits on the surface (no z-fighting); weeds alpha-tested, walk-through | | |
| CP-08 | (optional, P13) set 1-2 `VANILLA_TREES`, regenerate a city layout | Trees visible and solid on a client; if not, empty the list again | | |

## 26. City life: venues, roads, search, alcohol, hordes, alarm (D61)

Layout: `placement/citylife_template.yaml` (target terrain; fill the site, or spawn single pieces with the diag
console). Packages: `sky_city_venue`, `sky_landmarks`, `sky_roads`, `sky_street`, `sky_sounds`, `sky_items`, `sky_scripts`.
For the alarm rows, temporarily set `ALARM_MIN_MS` / `ALARM_MAX_MS` to 60000 on the diag build only.

| ID | Steps | Expected | Diag | Dedicated |
|---|---|---|---|---|
| CL-01 | Walk the hypermarket, mall (3 levels, escalators), cinema, bar, kindergarten, clubhouse, hanged church | No fall-through, escalators walkable, atrium skylight blocks rain, doors open, loot on floors | | |
| CL-02 | Hypermarket at night | Cold over-bright light, visible in daylight too (SetVisibleDuringDaylight); no FPS drop beyond FPS_PROTOCOL | | |
| CL-03 | Funfair: climb round the Ferris wheel, carousel, bumper cars | Collision on frames and gondolas; birch through the platform; no floating parts | | |
| CL-04 | Stadium, landfill, car parks (A, B, Metro hatch sealed) | Pitch flat (no clutter grass through), stand walkable, floodlight masts solid | | |
| CL-05 | Drive into a jam line, then walk through it (P19) | Vehicle stopped; player passes through the 1 m gap | | |
| CL-06 | Drive the viaduct end to end, and through the tunnel | Ramps drivable, barriers hold a car, no gap at segment joints | | |
| CL-07 | Cross the bridge | Deck drivable, checkpoint blocks cars, loot on the deck and in the two sniper nests (Military) | | |
| CL-08 | Search a bin, a dumpster, the garbage truck, each landfill mound (P17) | 6 s action, item at your feet or "Nothing useful"; same spot again -> "Someone has already been through this" for 30 min; bare hands sometimes cut | | |
| CL-09 | Search mall rails and cinema trunks; bar stock | Suits / dresses / masks; vodka or beer | | |
| CL-10 | Security: spam the search action, search from 4 m (cheat / lag), search with a desync | Server gives nothing out of reach or within 4 s of the last search; no script errors | | |
| CL-11 | Drink and fill a bottle at a wet hydrant; try a dry one (P18) | Wet behaves like a well; dry has no action | | |
| CL-12 | Drink vodka: 1 sip, 5 sips, half the bottle (P16) | Tipsy (slow heal), drunk (blur), wasted (strong blur, vomiting); sober again after ~15-20 min; relog resets | | |
| CL-13 | Walk to a siren tower downtown (P15) | Groups of infected appear out of sight within 20 s; never more than 18 per tower; they vanish when everyone leaves 550 m | | |
| CL-14 | Wait for the alarm (shortened timer) at 100 m, 1 km, 2 km (P14, P20) | Siren heard and fades with distance; infected within a few hundred metres converge; 3 extra groups arrive | | |
| CL-15 | FPS: run S-rows of FPS_PROTOCOL with 2 towers awake and one alarm | Server frame time within budget; no per-frame script cost in the profiler | | |

## 27. Creatures: guard kennel, rat nests (D62)

Two players (owner O, stranger X). Spawn `SKY_Kennel`, `Land_SKY_RatNest` with the diag console, or use the
landfill park of `placement/citylife_template.yaml`.

| ID | Steps | Expected | Diag | Dedicated |
|---|---|---|---|---|
| CR-01 | O places the kennel (hologram like a sea chest), stores items, stays online | X can open and take (guard off while O is online) | | |
| CR-02 | O logs off; wait 30 s; X tries drag, swap, hotkey, split stack, combine stack, take the kennel, shoot it, grenade it | Nothing moves, no damage, cargo hidden; dog barks at X (sound, infected come) at most every 20 s (P21) | | |
| CR-03 | Restart the server with O offline | Kennel guards straight after the restart | | |
| CR-04 | O logs back in | Guard off within 30 s; O empties and picks the kennel up; a full kennel cannot be picked up | | |
| CR-05 | Stand in a rat nest 60 s (P22) | Bites ~1 per 15 s, light foot bleeding sometimes, salmonella sometimes; nothing in a vehicle | | |
| CR-06 | Same with a placed kennel within 15 m | No bites | | |
| CR-07 | Fence + tent within 25 m of a nest, 1 h; then with a burning fireplace by the nest, and with a kennel by the fence | ~3 % health lost per hour without protection; none with the fire or the kennel | | |
| CR-08 | Horse carcass and nests in the landfill | Collision as cover, no floating parts | | |

## 28. Underground and terrain (D63)

This needs the custom test terrain built from `terrain/out` (P28) with `placement/out_citylife/objects`. Before that,
you can spawn single pieces in the air on the diag server (`Land_SKY_Sewer_Straight` at y + 20) to check
collision and looks.

| ID | Steps | Expected | Diag | Dedicated |
|---|---|---|---|---|
| UG-01 | Import heightmap / masks / layers in Terrain Builder, build the .wrp (P28) | Flat plateau at 120 m, trenches where the layout puts sewer and metro, river valley under the bridge | | |
| UG-02 | Walk down a Sewer_Stair from the street, along the walkways, through the junction, to an end (P25) | No snags, door aligned with the access piece, rails at the street opening, no gaps between pieces | | |
| UG-03 | Walk down the metro station stair, platform, tunnels to both ends | Stair headroom, platform edges, buffer stops; tracks continuous across station/tunnel joints | | |
| UG-04 | Merge `cfgundergroundtriggers_snippet.json`, walk down (P27) | Eye adaptation darkens underground, fades along the stairs; lamps read as dead fittings (P26) | | |
| UG-05 | `#weather` heavy rain (> 0.6) for 10 min, then stop (P29) | Water rises to ~1.6 m over 10 min, visible from two clients; drains in 30 min; boots/trousers soaked; damage when submerged | | |
| UG-06 | Drive over the roof slabs (streets above sewer/metro) | No bumps, no fall-through; station stair opening has rails | | |
| UG-07 | Vanilla map: try a layout with `underground` and target spawner | Refused (hatches stay sealed) | | |

## 29. Vehicles (D64)

| ID | Steps | Expected | Diag | Dedicated |
|---|---|---|---|---|
| VH-01 | Spawn `Land_SKY_Wreck_CityBus` and `Land_SKY_Wreck_GarbageTruck` | Collision on body and wheels, cover from fire, no floating parts, garbage truck hopper searchable | | |
| VH-02 | (when a modeller delivers, VEHICLE_SPEC.md) spawn `SKY_CityBus` / `SKY_GarbageTruck` with all parts | Drives, steers, brakes, 4 + passengers seats, lights, doors; no fall-through (P30, P31) | | |

## 30. Refinement: search tables, ambience (D65)

| ID | Steps | Expected | Diag | Dedicated |
|---|---|---|---|---|
| RF-01 | Search hypermarket shelf ends and clubhouse lockers | Food / drinks; sportswear; cooldown as §26 | | |
| RF-02 | Walk into the hypermarket, down a sewer, past the Ferris wheel (P32) | Hum / drips / creak fade in within ~2 s, never more than 3 loops, stop when you leave | | |

## 31. Asset quality: street props, underground signage (D66)

| ID | Steps | Expected | Diag | Dedicated |
|---|---|---|---|---|
| AQ-01 | Look at the bin, dumpster and hydrants from 1 m and 30 m | Clean silhouettes, no floating parts, LOD switch without popping; bin and dumpster searchable as before | | |
| AQ-02 | Metro station and sewers with a flashlight (P33) | Station names and exit boards readable (not mirrored); graffiti and signs without flicker | | |

## 32. Variety: street props, underground variants (D67)

| ID | Steps | Expected | Diag | Dedicated |
|---|---|---|---|---|
| VA-01 | Walk a citylife street on the -X sidewalk | Bus stops, ad columns, phone booths stand upright, open side to the road, never under a street lamp or inside a car jam; glass blocks bullets, not sight | | |
| VA-02 | Climb the rubble in Sewer_Collapsed and Metro_Collapsed (P34) | Heap is walkable; the free walkway / track always passes; slabs and beam stop players and bullets | | |
| VA-03 | Stand in Sewer_FloodedEnd during heavy rain (P35) | One water surface; drowning grace and damage as §28 | | |
| VA-04 | Visit both citylife metro stations | Different name boards (Pobedy, Vokzal), not mirrored | | |

## 33. Ambience and search: metro, stadium, mall (D68)

| ID | Steps | Expected | Diag | Dedicated |
|---|---|---|---|---|
| AM-01 | Walk a metro tunnel and station, then climb to the street above it (P37) | Tunnel wind in the metro; on the street and in the sewer above it: no wind, no drips | | |
| AM-02 | Stand in front of the stadium stand, then on its terraces | Flags flap on the roof (model) and are heard within ~50 m | | |
| AM-03 | Walk all three mall floors | Quiet muzak on every floor, gone ~35 m outside | | |
| AM-04 | Search a metro ticket kiosk and a bus-stop bin (P36) | Kiosk: papers / snacks / torch etc. on the platform floor; bin: trash table; cooldown and rate limit as §26 | | |

## 34. Venue variants (D69)

| ID | Steps | Expected | Diag | Dedicated |
|---|---|---|---|---|
| VV-01 | Walk through each B venue (universam, TC Galaktika both floors, kino Oktyabr, pivnaya, FC Torpedo) in all three states (P38) | Signs readable, doors open, every floor reachable, no sealed rooms, ruins climbable | | |
| VV-02 | Search universam shelves, mall rails, pivnaya counter, Torpedo lockers | Same tables as the base venues (grocery, costume, alcohol, sport), cooldown as §26 | | |
| VV-03 | Stand in the universam and in TC Galaktika | Tube hum / muzak as the base venues, gone outside the hall | | |

## 35. Asset quality: stand, fair booth, kennel (D70)

| ID | Steps | Expected | Diag | Dedicated |
|---|---|---|---|---|
| AQ-03 | Walk away from the stadium stand and a fair booth from 5 m to 80 m (P40) | No popping seat rows or booth dressing; stand seats keep their colours | | |
| AQ-04 | Lie prone in a missing-seat gap on the stand; a second player watches from 60 m | The viewer sees the gap (no solid row drawn over the player) | | |
| AQ-05 | Drop an item on the booth counter; place a kennel and look at it from 1 m | The item lies on the counter top; kennel storage opens as before | | |

## 36. Civic search spots (D71)

| ID | Steps | Expected | Diag | Dedicated |
|---|---|---|---|---|
| CS-01 | Search a clinic medicine cabinet (upper floor exam rooms), a police gear locker (ground-floor office), a post office sorting rack (P41) | Medical / police / post items appear at the spot; never a weapon or ammunition; "Nothing useful." on a miss | | |
| CS-02 | Repeat a search at once, then at another spot within 4 s | Spot cooldown and per-player rate limit as §26 | | |
| CS-03 | Search the cinema costume trunks from the stage | Action available on the stage | | |
| CS-04 | Stand outside a police office / clinic exam room wall, within 2 m of the locker or cabinet, and search (P42) | Nothing happens (no loot, no cooldown used); from inside the room it works | | |

## 37. Ruin exits and search UX (D72)

| ID | Steps | Expected | Diag | Dedicated |
|---|---|---|---|---|
| RX-01 | In 3 ruins (rowhouse, villa, shop row): drop into the collapse and climb out over the rubble (P43) | The pile can be climbed and left on every side; no room you cannot leave | | |
| RX-02 | Aim at a police locker through the office wall, then from inside the room | No Search prompt through the wall; prompt inside | | |
| RX-03 | Start a search, step behind the door frame before it ends | "Something is in the way.", no loot, the spot is not on cooldown | | |

## 38. Street kit close-up pass (D73)

| ID | Steps | Expected | Diag | Dedicated |
|---|---|---|---|---|
| SK-01 | Walk a car jam: shoot through a sedan hulk's windows and between cabin and body (P44) | Bullets stop on the hulk; no slit in its collision | | |
| SK-02 | Look along a lit street at night from 5 m to 120 m | Lamps light the road as before; no pole / head popping; barrier stripes stay visible at mid range | | |
| SK-03 | Hide behind a planter and a barrier, a second player watches from 80 m | Same cover in every LOD (no shrub card hiding a crouched player from one side only) | | |

## 39. Street kit pass 2 and jam variants (D74)

| ID | Steps | Expected | Diag | Dedicated |
|---|---|---|---|---|
| WV-01 | Walk a car jam: find intact, burnt and overturned sedans; try to crawl under the overturned one, shoot through the van's open rear door (P45) | No crawl space; bullets stop at the door; jam lines still leave one 1 m gap | | |
| WV-02 | Look at a billboard (each poster variant) and a traffic light from 5 m to 200 m | Poster shows with its peeled corner; walkway and signal head do not vanish at mid range | | |
| WV-03 | Shoot between the garbage truck cab and body, and under its body between the wheels | Bullets stop (no slit) | | |

## 40. Street surface pass (D75)

| ID | Steps | Expected | Diag | Dedicated |
|---|---|---|---|---|
| SS-01 | Walk a citylife street at night and day; look at kerbs, gutters and asphalt cracks from 2 m to 150 m; cross the kerb on foot (P46) | Kerb chamfer and gutter visible, no flicker; feet do not float on the kerb lip | | |
| SS-02 | Drive a street: count worn tiles (patches, trench) over 10 tiles | About 4 in 10 worn, no obvious repeat; no wheel bump at the patches | | |
| SS-03 | Stand under a viaduct and on its deck | Ribs, spalls, drain streaks visible; expansion joints do not flicker; bullets stop at the deck | | |

## 41. Interior props close-up (D76)

| ID | Steps | Expected | Diag | Dedicated |
|---|---|---|---|---|
| IP-01 | Walk an office floor: reception desk, desks, cubicles, server rack, vending machine, lockers, kitchenette at 0.5-25 m (P47) | Detail visible up close, no flicker at 10-30 m when Res1 swaps in, no black faces | | |
| IP-02 | Open each locker door, the vending flap and the extinguisher cabinet door | Louvres, handles and frame swing with the leaf; nothing left floating | | |
| IP-03 | Search loot on the desk, reception and kitchenette | Items spawn clear of the mouse, phone, kettle and sink; nothing hidden in the detail | | |
| IP-04 | Crouch under a desk / beside a bed and shoot through the gaps under furniture | Bullets stop where the collision is (same both ways); nobody can hide inside render-only parts | | |

## 42. Texture depth (D77)

| ID | Steps | Expected | Diag | Dedicated |
|---|---|---|---|---|
| TX-01 | Look at wood furniture, sofas and beds under a lamp at 1 m (P48) | Grain, pores and twill visible; bumps lit from the right side; walnut lacquered, not wet | | |
| TX-02 | Walk a sidewalk and a concrete facade at 1-50 m | Paver bevels, chips and moss joints; no tiling seam on concrete, metal or stone; no shimmer from 1 px scratches at distance | | |
| TX-03 | Grep the client RPT after loading citylife | No `Cannot load texture` / missing `sky_*.paa` (sky_stone_as fixed in D77) | | |

## 43. Street kit pass 3 (D78)

| ID | Steps | Expected | Diag | Dedicated |
|---|---|---|---|---|
| SK-01 | Shoot over the bonnet and through the side windows of a hulk in a car park and on the bridge (P49) | Bullets stop where the car is drawn, pass over the bonnet where it looks clear | | |
| SK-02 | Walk round the entrance booth and pay machine of each car park | No pocket you can get stuck in; machine blocks like a pillar | | |
| SK-03 | Walk away from a car park to 300 m | Lamp posts and cars fade with the lot, no sudden pop | | |
| SK-04 | Line up crowd barriers, shoot through the bars and at the rails | Bars pass bullets, rails stop them; hooks line up end to end | | |
| SK-05 | Walk the sewer junction | Quoins at the corners, no snag, pipes above head height, well grating visible | | |

## 44. Concealment fixes (D79)

| ID | Steps | Expected | Diag | Dedicated |
|---|---|---|---|---|
| CF-01 | Two players: one tries to put their head into a sewer pipe, the bus-stop bin, a bumper car seat, a landfill fridge / barrel, a stadium seat, a Ferris-wheel gondola roof (P50) | Collision stops them, or the volume is too small to hide a head; the other player always sees them | | |
| CF-02 | Walk the sewer walkways, landfill mounds, stadium terraces and board the bottom gondola | No new snag spots, headroom under the sewer pipes, the bottom cabin still boardable | | |

## 45. Facade textures (D80)

| ID | Steps | Expected | Diag | Dedicated |
|---|---|---|---|---|
| FT-01 | Look at brick, stucco and panel facades at 1-80 m, strafing at grazing angles (P51) | Mortar, bevels, cracks and sockets read; no flicker or sparkle; no seam at sheet repeats | | |
| FT-02 | Grep the client RPT after loading citylife | No missing `sky_wall_*` textures | | |

## 46. City concealment and ruin fixes (D82)

| ID | Steps | Expected | Diag | Dedicated |
|---|---|---|---|---|
| CC-01 | In a ruined building, shoot at the tops of cut walls and lintels over windows (P52) | Bullets stop at the visible wall top; nothing stops them above it | | |
| CC-02 | Try to hide your head in a lampshade (from a table), a rubble chunk, a pallet stack, a factory machine top, a roof HVAC fan drum, a roof-garden lounger | Collision stops you, or the object is too small to hide a head | | |
| CC-03 | Shoot between a bus-stop side panel and its front post | Bullets stop (closed) | | |
| CC-04 | Look at limestone, concrete-panel and brick-trim facades at 1-80 m | Block bevels, tooling, blowholes, sill groove read; no seam, no black line on limestone | | |

## 47. Slits and ruin cuts (D83)

| ID | Steps | Expected | Diag | Dedicated |
|---|---|---|---|---|
| SC-01 | In ruined churches, town halls and stone villas, shoot at the gables, cornices and roof pieces still standing over a collapse (P53) | Bullets stop on everything visible; nothing invisible stops them | | |
| SC-02 | In a damaged OfficeTall, shoot through the shopfront corner mullion with a broken pane | Bullets pass the 8 cm mullion (accepted, thin aluminium); the wall beside it stops them | | |
| SC-03 | Look at brick soldier courses and stone sills over windows at 1-30 m in raking light | Soldier bricks and sill joints show relief; no seam or step where the sheet repeats | | |

## 48. Grime macro and furnished rooms (D84)

| ID | Steps | Expected | Diag | Dedicated |
|---|---|---|---|---|
| GM-01 | Look along a street of brick, panel, limestone and stucco buildings from 30, 80 and 150 m (P54) | Soft soot, rain runs and wash patches; no 3-4 m tiling, no seams every 24-32 m, no black / pink walls, no RPT texture errors | | |
| GM-02 | Walk through 5 apartment blocks and 2 office buildings | Living rooms, bedrooms, kitchens and offices vary between flats; sofas, beds, tables and cabinets collide; no piece blocks a door or traps you behind a fridge or bookcase | | |
| GM-03 | Try to hide your head in a sofa back, TV, bookcase, fridge or filing cabinet | Collision stops you or the part is too thin to hide in | | |

### Sign-off

| Gate | Diag | Dedicated | Tester / date |
|---|---|---|---|
| Collisions §1 | | | |
| Fire Geometry §2 | | | |
| View Geometry §3 | | | |
| Doors §4 | | | |
| Keycard §5 (incl. K-13 / M3) | | | |
| Elevator §6 | | | |
| AI §7 | | | |
| Loot §8 | | | |
| City life §26 | | | |
| Creatures §27 | | | |
| Underground §28 | | | |
| Vehicles §29 | | | |
| Refinement §30 | | | |
| Asset quality §31 | | | |
| Variety §32 | | | |
| Ambience §33 | | | |
| Venue variants §34 | | | |
| Stand / booth / kennel §35 | | | |
| Civic search §36 | | | |
| Ruin exits / search UX §37 | | | |
| Street kit §38 | | | |
| Street kit 2 / jams §39 | | | |
| Street surface §40 | | | |
| Interior props §41 | | | |
| Texture depth §42 | | | |
| Street kit 3 §43 | | | |
| Concealment fixes §44 | | | |
| Facade textures §45 | | | |
| City concealment / ruins §46 | | | |
| Slits and ruin cuts §47 | | | |
| Grime macro / rooms §48 | | | |
| Placement §9 | | | |
| Roof drop §10 | | | |
| Clean logs §11 | | | |
| Perf §13 | | | |
| Interior props §14 | | | |
| Floor / roof variants §15 | | | |
| Street kit §16 | | | |
| Decals / windows §17 | | | |
| Economy / district §18 | | | |
| Validation script §0b (summary PASS, 0 SKY FAIL lines) | | | |
| Regression §12 | | | |
| Realism pass §19 | | | |
| Splendour pass §20 | | | |
| City buildings §21 | | | |
| City wave 2 / districts §22 | | | |
| Wave 3 / tall towers §23 | | | |
| Ambiance / vegetation §24 | | | |
| Content pass §25 | | | |
| FPS protocol (`FPS_PROTOCOL.md` §4 thresholds) | | | |
