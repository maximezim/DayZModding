# Batch 6 perf gate (perf-engineer)

## SKY_Skyline Batch 6: static perf gate on the FPS protocol (commit 8a6616d, nothing edited)

The protocol is laid out well: configs, positions, scenarios, a threshold table, a results table and a CSV. But as written it cannot produce valid numbers for the server-side decisions that `AFTER_TESTING.md` §3 relies on: ENTITY_CAP and PROP_CAPS raises, D43, and D27. There are three causes:
- The server frame metric has no source the tooling can load.
- The layout runs spawn no loot, although the loot counts against ENTITY_CAP.
- Baseline A runs on a different mission and storage state than D, D0 and E.

All paths below are under `/home/user/DayZModding/`. The CSV is at `mods/SKY_Skyline/reviews/fps_results_template.csv`, not at `reviews/` in the repo root.

### High

**H1. S1 server frame time has no metric source in the specified tooling.**
- **Where:** `FPS_PROTOCOL.md:42`, `:58`. It points to the probe in `reviews/perf_review.md:175`.
  - The probe (`SKY_PerfProbe`) does not exist anywhere in the repo.
  - `tools/tests/Invoke-ModValidation.ps1:305` calls `Start-DedicatedServer.ps1 -Mods $ModName` and has no `-ServerMods` parameter, so a diag-only server mod cannot be loaded in the run that applies the layouts.
  - `tools/launch/Start-DiagLocal.ps1:41` always uses `server\mpmissions\<mission>` and ignores the `.validation` copy. So "diag first" (`FPS_PROTOCOL.md:7-9`) is impossible for B, D, D0 and E.
- **Why it matters:** S1 is the only server-FPS threshold. D43 says "decide after S1/S6", and `AFTER_TESTING.md:50` ("S1/S6/S7 fine with headroom -> raise ENTITY_CAP/PROP_CAPS") depends on it. With no source, that row will be filled by eye from RPT, which has no frame data.
- **Second problem:** the dedicated server's frame rate is capped (verify the `-limitFPS` default on the first run). An idle A and an idle D both sit at the cap, so "+3 % avg" passes even when D has no headroom. That is a false PASS that then justifies raising caps.
- **Fix:**
  1. Make "write `SKY_PerfProbe`" an explicit prerequisite step. It is an enforce-coder task; verify `MissionServer.OnUpdate` in `P:\scripts\5_Mission`.
  2. Add `-ServerMods` to `Invoke-ModValidation.ps1` and pass it through to `Start-DedicatedServer.ps1`.
  3. Add `-Mission` / `-Config` to `Start-DiagLocal.ps1`.
  4. Run S1 with `-limitFPS` raised well above idle (or record the cap and use p99/max as the primary metric). Define "headroom" as a number, e.g. probe avg < 50 % of the frame budget at the cap.
  5. Run A twice to get a noise floor before trusting a 3 % delta.

**H2. Every layout run has 0 loot, so D, D0, E and S8 under-measure the very thing ENTITY_CAP counts.**
- **Where:** `Invoke-ModValidation.ps1:248-299`. Each run re-copies the vanilla mission and wipes `storage_1` (`:252-255`). It merges mapgroupproto, CE, event and zone files, but never `mapgrouppos.xml`. Line `:299` only notes that ExportProxyData is needed.
- **Why it matters:** CE only spawns loot in buildings listed in `mapgrouppos` (`placement/README.md` §3). Any manual merge is wiped on the next run.
  - D is described as "323 + up to 226 loot" (`FPS_PROTOCOL.md:17`), and E as 1647 (`:20`). In practice they spawn 323 and 969 entities with no loot, but `ENTITY_CAP` (`assets/skyspec.py:474`) counts entities plus loot.
  - S8 will read about 0 items. That looks exactly like the B7 failure, and `AFTER_TESTING.md:39` would then delete the prop loot groups on a false result.
- **Fix:** add a `-MapGroupPos <file>` parameter (or a per-layout `mapgrouppos_sky.xml` next to the layout output). Merge it into the copy like mapgroupproto. Add a protocol step 0: survey with `exportRadius >= 73` (batch5_qa) and save the exported groups once per site. Record the loot count actually spawned in every S1, S6 and E row.

**H3. Baseline A is not the same mission or storage state as D, D0 and E.**
- **Where:** `FPS_PROTOCOL.md:15`. Without `-Layout`, `Invoke-ModValidation.ps1:233` uses the vanilla mission: persisted `storage_1`, no `sky_ce`, no zone. Every `-Layout` run is a fresh wipe (`:254-255`) with the SKY economy merged.
- **Why it matters:**
  - S7 (`:59`, +20 s / +60 s) and the first 10 min of S1 compare a cold, map-wide CE initial fill against a warm persisted start. The difference swamps the district effect, and `AFTER_TESTING.md:48` then triggers D43 on a confound.
  - batch5_perf (line 116) asked for measurements after CE has filled the district. S1 starts immediately.
- **Fix:**
  - Produce A through the same path, using a zero-object layout or a `-Baseline` switch that copies, wipes and merges CE without objects.
  - Split S7 into a cold-start and a warm-start measurement (second boot without wipe; needs a `-NoWipe` switch).
  - Start the S1 clock only after CE has settled (e.g. 15 min).

**H4. The per-server cap and the "raise by 25 %" rule are never measured at or above the cap.**
- **Where:** `FPS_PROTOCOL.md:20`, `AFTER_TESTING.md:50`, `skyspec.py:474`.
- **Why it matters:**
  - E (1647) is 66 % of the 2500 cap, and with H2 it is really 969 entities.
  - E also cannot be produced: `Invoke-ModValidation.ps1:262` writes a single `objectSpawnersArr` file and takes one `-Layout`, with one zone and event snippet. `--others` only counts towards the cap; it does not merge spawns.
  - S1 uses 1 player, but batch5_perf M1 says the cost is per player in the bubble (`batch5_perf.md:31`, `:116`: 1 and 10 clients).
- **Fix:**
  - Allow several `-Layout` values: merge their spawn JSONs into the `objectSpawnersArr` list and append all their snippets.
  - Make E the largest legal set: 4 districts, 2196 including loot.
  - Add S1b with N clients (at least 4, ideally 10) at Q1.
  - Any cap raise must be re-measured at the new cap value, with E sized to it.

### Medium

**M1. D43 attribution is ambiguous.**
- **Where:** `FPS_PROTOCOL.md:56`, `AFTER_TESTING.md:48`.
- The client D-D0 delta mixes the furniture's render cost, which stays after merging, with per-entity overhead, which merging removes. The AFTER_TESTING trigger also uses S6/S7 "over threshold", but those thresholds are D vs A (`:59-60`), so street-kit or tower cost could trigger furniture work.
- **Fix:**
  - Add server-side D-D0 thresholds (S1 avg/p99, S6 join, S7 start, replicated count) and use only those for D43/D27.
  - Route a client-only D-D0 overrun to prop LOD cuts instead.
  - Record per-entity cost as (D-D0)/227 so the merged variant (227 -> about 30) can be predicted.

**M2. Interior and roof positions have no baseline in A.**
- **Where:** `FPS_PROTOCOL.md:31-34`, `:54`. In A there is no building, so a player at Q2, Q3 or Q6 falls.
- **Fix:** use the diag free camera at fixed coordinates in every config. This needs the M-H1 diag launcher fix. Alternatively, define the interior thresholds against D0 (same shell) and use A only for exterior positions.

**M3. Thresholds without a measurable source.**
- "Res2/Res3 alpha sections visible at Q5" (`:62`) needs diag render stats. These are unavailable on the retail client, which is the only client that can join the BattlEye validation server, and the active LOD at 500 m is unknown. **Fix:** make it a static gate (p3d_inspect/check_assets: 0 alpha sections in Res2/Res3 of every SKY model) plus a visual note.
- S6 "entity count (admin/diag)" (`:44`): vanilla has no admin tool. **Fix:** have the probe print, once at a fixed time, the server-side count of `Land_SKY_*` objects and of items within R of T. It is a one-off query, so the cost is acceptable.
- TESTING.md:405 (P5-09) says "server FPS in RPT/admin tool"; RPT has no FPS. Point it at the probe.

**M4. S6 "join near T" conflicts with the storage wipe.**
- A wiped `storage_1` means a fresh character with a random coast spawn, so the join never happens near T. Repeats and the timing source are also undefined.
- **Fix:** use `-KeepRunning`. Join, move to T, log out, rejoin within the same session three times. Time from the client RPT connect line to the spawn line (verify the texts) or the ADM connect line.

**M5. D-dec does not test what it claims.**
- **Where:** `FPS_PROTOCOL.md:19`, `:57`.
- T4 is in the SE block (`placement/district_template.yaml:54-58`). Q1 faces north, so T4's decals are outside the view and D-dec - D will be about 0, a false PASS.
- "40 on one facade" contradicts "faces N/E/S/W".
- DC-09 (`TESTING.md:367`) wants 0/15/40 at 10 m and 60 m.
- **Fix:** add Q7, facing T4's decal face at 10 m and 60 m, with all 40 decals on that one face. Derive the cap as budget / ((D-dec - D)/40).

**M6. Run length is undefined.**
- `-Minutes` defaults to 3 (`Invoke-ModValidation.ps1:33`), and the deadline counts from launch including boot (`:314`), so a slower-booting D gets a shorter sample. The server is killed after that (`:324`).
- S1 needs 20 min or more after ready; S8 needs 30 min.
- **Fix:** add a per-scenario `-Minutes` table to the protocol (S7 5, S1 30, S8 40), or count from a ready marker.

**M7. S4 cannot be compared and has no threshold.**
- There is no pass/fail row for S4 in §4.
- A and B have no T3, and A has no zone, but the CSV has S4 rows for A and B.
- "dmax 15" (`:43`) disagrees with the generated dmax 12 (`placement/out_district/zombie_territories_snippet.xml:3`, TESTING Z5-01).
- "Infected alive per floor" has no source.
- **Fix:** run S4 as D vs D0. Threshold: 0 SKY-attributable path-failure lines and p99 within the S1 band. The probe counts infected per height band.

**M8. S7 relies on unverified markers.**
- The "Mission read" and "pathgraph lines" log texts are unverified, and the script extracts nothing.
- **Fix:** verify the texts on the first A run, then add `start_s` to `summary.json` (RPT first timestamp to marker), cross-checked with the process `StartTime`.

**M9. Items dropped from the Tower A protocol that it claims to extend.**
- Missing: the VRAM threshold (`perf_review.md:212`), a server p99 pass/fail (p99 is recorded at `FPS_PROTOCOL.md:86` but has no threshold), and the S5 shadow/LOD visual pass at 17:00.
- TESTING §13 (`TESTING.md:244`) requires config C (3x3 Tower A), but no layout for it exists.
- **Fix:** add these rows back, or explicitly retire C in favour of E.

**M10. The AFTER_TESTING over-budget rows have no measurement that can trigger them.**
- **Where:** `AFTER_TESTING.md:51-52`.
- No config isolates:
  - Apartments/Hotel Geometry, 40/38 comps (D37)
  - Roof Res1, 128 > 120 (D36)
  - the Tower A core, 81 > 80 comps
- Geometry and Fire component cost only appears under collision or bullet load, and no scenario creates that. "Measured cost over threshold for an OVER asset" has no per-asset threshold.
- **Fix:** state that these are accepted unless a district threshold fails *and* the diag profiler attributes the cost to the asset. Close the core 81 > 80 case statically (record 81 in `BUDGETS`, M2 merges pending) rather than implying an FPS test decides it. Optionally add S9: player plus infected on T2/T3 floors with gunfire, D vs D0.

**M11. The CSV cannot hold the protocol's data.**
- **Where:** `fps_results_template.csv`.
  - There is no VD column, although VD1 and VD2 are required (`FPS_PROTOCOL.md:36`), so rows collide.
  - The unit "ms_or_fps" is ambiguous, and `low1pct_fps` does not match the "% of A" threshold.
  - Only the median is stored, with no per-repeat values, so the noise band and the "re-run 5x" rule cannot be checked.
  - Missing rows: delta/verdict, run info (commit, CPU/GPU, limitFPS), the Q5 alpha check, S1b multi-client, D-dec server rows, loot actually spawned, and S2/S3.
- **Fix:** add the columns `vd, repeat_n, value_raw, unit (ms|fps|s|count), delta_vs, verdict`, plus run-info rows.

### Low
- **L1.** Positions are described in words (`FPS_PROTOCOL.md:29-34`). Record world X/Y/Z, heading in degrees, and the date and weather freeze per site in the run info.
- **L2.** Thresholds are looser than in Tower A (+2 ms vs +1, 1 % low 85 % vs 90 %, server 3 % vs 2 %) with no stated rationale. Add one line on why.
- **L3.** TESTING §13 has PERF-01 for Tower A only. Add a PERF-02 row: "FPS_PROTOCOL §4 all Pass" (the sign-off at `TESTING.md:447` exists, but there is no row in §13).
- **L4.** LIGHT_CAP (`skyspec.py:471`) is never isolated. Street lights are emissive only (`skyspec.py:306`), so they count only as entities. That is acceptable; just say so.
- **L5.** "Profile with the diag menu" in the in-between band (`:64`) is not available on the dedicated run. Name the diag run for it.

### Measure it
- Server:
  - `server\profiles\dedicated\script_*.log`: probe avg/p99/max lines and the one-off object and item count.
  - `*.RPT`: timestamps from start to the verified "mission ready" marker, and path-failure lines.
  - `*.ADM`: connect and spawn lines for join time.
  - `build\validation\<stamp>\summary.json`: FAIL lines and the planned `start_s`.
- Check `storage_1\export\mapgrouppos.xml` contains the `Land_SKY_*` groups before any D, E or S8 run.
- Client: PresentMon or CapFrameX on the retail client (dedicated runs). Diag Statistics overlay plus free camera only after `Start-DiagLocal` can load the `.validation` mission.
- Do a first sanity run of A twice to get the noise floor, and confirm the server frame cap from the probe's idle value.

GATE: FAIL


## Re-gate (8908bb7)

## Perf re-gate: SKY_Skyline Batch 6 at commit 8908bb7 (read-only, nothing edited)

The gate passes. All four previous High findings (H1–H4) are fixed or reasonably deferred, and nothing in the protocol can still produce a false PASS that would lead to raising a cap. Eight new or remaining Medium issues and ten Low ones should be fixed before the first real run. None of them is High.

All paths below are under `/home/user/DayZModding/`. "Protocol" means `mods/SKY_Skyline/FPS_PROTOCOL.md` and "validation script" means `tools/tests/Invoke-ModValidation.ps1`.

### Previous findings
- **H1 (no server frame metric): reasonably deferred, the deferral is acceptable.** `CLAUDE.md` says "Do not create mods ... unless the user asks", so a new probe mod needs your go-ahead. Leaving it as a blocked prerequisite is the right call. It is recorded in four places:
  - Protocol `:13` marks it as prerequisite 0.1, and `:9` says nothing below is valid without §0.
  - `PENDING_VERIFICATION.md:36` (B11) and `AFTER_TESTING.md:43` give the decision to you.
  - `AFTER_TESTING.md:50` says §3 is only valid with §0 done.
  - `TESTING.md:255` (PERF-02) and `:406` (P5-09) point at the probe, not the RPT.
  
  The tooling fails closed: the §1 commands pass `-ServerMods SKY_PerfProbe`, and `Build-Mod` of a mod that doesn't exist stops the run (validation script `:227`, `:240-244`). The rest of H1 is done: `-ServerMods` is passed through (`:383`), and `Start-DiagLocal.ps1:29,44` accepts `-Mission`. The frame-cap half is only partly done (see M-2).
- **H2 (layout runs spawn no loot): fixed.** `-MapGroupPos` merges the `Land_SKY_*` groups from the survey export (validation script `:322-331`). A layout run without it shows a visible SKIP step (`:332-333`). Protocol step 0.3 adds the survey. Two smaller gaps remain (M-4).
- **H3 (baseline A on a different mission and storage state): fixed.**
  - `-Baseline` uses the same copy, wipe and SKY economy as the layout runs (`:250-320`).
  - `-NoWipe` gives a warm start (`:275`).
  - S1 measures only after a 15-minute CE settle.
  - S7 is split into cold and warm runs.
- **H4 (cap never measured): fixed.**
  - Several `-Layout` values are supported, each with `--others` (`:254-268`), and there is one spawner file per layout (`:296-300`).
  - E has 4 districts, 2196 entities plus loot. That is the largest legal set (batch5_qa: 5 districts give 2745, over the 2500 cap).
  - S1b adds N clients.
  - AFTER_TESTING `:57` requires E to be re-run at any new cap.
- **M1, M2, M3, M4, M7, M9, M10, L1, L2, L3, L5: fixed.**
- **Partly fixed:**
  - M5: D-dec divides by the wrong number (M-1).
  - M6: run length still counts from launch (L-1).
  - M8: the `summary.json` cross-check doesn't exist (L-2).
  - M11: some CSV rows are missing (L-3).
- **L4: not addressed.** Trivial, see L-4.

### High
None.

### Medium
**M-1. D-dec divides by 12, but only 9 to 11 decals differ from D, so the decal cap comes out too high.**
- Where: protocol `:30` and `:79`, `AFTER_TESTING.md:56`, `TESTING.md:368` ("0 vs 12").
- Why: D already has 3 decals (`placement/district_template.yaml:67-69`), one of them on T4 face E.
  - D-dec replaces those 3 with 12 (`district_template_decals.yaml:67-78`), so 332 − 323 = 9 net new entities.
  - On screen at Q7, the difference is 12 − 1 = 11 decals.
  - Dividing by 12 understates the cost per decal by 8–25 %, so `DECAL_CAPS` comes out higher than it should.
- Fix: divide client Q7 results by 11 and server results by 9. Alternatively, drop D's face-E decal from the D-dec comparison, or compare against D0, which also has the 3 decals. Correct the wording of DC-09.

**M-2. The frame cap cannot be lifted through the specified tooling, and the probe as specified measures time between frames, not work time.**
- Where: protocol `:13-14`. `Start-DedicatedServer.ps1:53` has a fixed argument list, and the validation script has no pass-through for extra arguments.
- Why: step 0.2 says "restart with `-limitFPS` raised", but none of the scripts can do that, so the operator has to leave the common launch path.
  - The probe adds up `OnUpdate(timeslice)`, which is wall time between frames and includes the limiter's sleep. While the server sits at the cap, avg is about 1/cap for every config.
  - The headroom check then reads 100 %. That fails closed, so caps are not raised by mistake.
  - But "S1 avg D vs D0 ≤ +2 %" passes trivially, which is a false PASS for D43. D43 then stays deferred.
- Fix:
  - Add `-ServerArgs <string[]>` to both scripts, or `-LimitFPS <int>`.
  - State in §4 that S1 avg rows are invalid unless A's idle avg is below the cap. At the cap, use only p99 and max.
  - Note in the B11 spec that headroom should use the probe's own `TickCount` work time or an uncapped run.
  - Define "frame budget" as the production server's FPS target, not the raised limit.

**M-3. The noise floor is defined as cold A vs warm A.**
- Where: protocol `:17`.
- Why: the cold/warm difference is a systematic effect (the first map-wide CE fill), not noise.
  - For S7 it can easily reach tens of seconds. With the rule "ignore deltas < 2 × noise", that swallows the +20 s / +60 s S7 thresholds completely.
  - S1 headroom is an absolute check, so it still guards cap raises. But S7 and S6 become uninformative.
- Fix: take the noise band from two runs in the same state (two cold runs, and separately two warm runs), and record it per metric.

**M-4. Loot positions (`-MapGroupPos`) for D0 and E are under-specified.**
- Where: protocol `:15`, `:29`, `:31`; validation script `:40` (a single `[string]`).
- D0: step 0.3 says "every D/D0/E run passes it". D's export contains the furniture loot groups.
  - CE most likely places loot at `mapgrouppos` positions whether or not the object exists (verify this on the first D0 run).
  - In that case D0 gets up to 226 items, some of them floating, not the 178 in its table row. The D − D0 difference then becomes entity cost only, with no loot cost.
  - Fix: decide which is intended and say so. Either use a separate D0 survey export, or keep D's export on purpose and change the 178.
- E: needs 4 surveys (one request per server start), but `-MapGroupPos` takes one file.
  - Fix: make it `[string[]]` like `-Layout`, and drop duplicate groups by `name` + `pos`. Otherwise E silently gets about a quarter of its loot. The step line does print `$n groups merged`; the protocol should state the expected count.

**M-5. `-NoWipe` warm starts are not checked and may start from stale storage.**
- Where: validation script `:275-276` and `:402`.
- Why:
  - The script reuses whatever `.validation` copy exists. A warm D after a cold D0 would silently measure D0.
  - The cold run ends with `Stop-Process -Force`, which skips the shutdown save. The warm state is then whatever the last autosave left (verify).
  - Diag runs with `Start-DiagLocal -Mission <copy>` also write `storage_1` into the same copy.
- Fix:
  - On a fresh copy, write a marker file into the copy (layout file hashes, `-Baseline`, MapGroupPos hash). With `-NoWipe`, refuse to run if the marker doesn't match.
  - Shut the server down cleanly before a warm run (RCon `#shutdown`), or require the cold run to last past one autosave.

**M-6. E has no thresholds for S6 or S7.**
- Where: `AFTER_TESTING.md:57` raises the caps when "S1/S1b/S6/S7 pass with headroom at E".
- Why: §4 defines S6 and S7 only as D vs A and D vs D0 (protocol `:84-86`). "Pass at E" is left to the tester's judgement.
- Fix: add "S7 cold/warm, E vs A" and "S6 join, E vs A" rows, or limit the `:57` row to S1/S1b.

**M-7. D, D0 and D-dec are three hand-filled copies of the site.**
- Where: `placement/district_template_noprops.yaml:13-21`, `district_template_decals.yaml:13-21`.
- Why: if `center`, `yaw` or `survey` differ by mistake, every D − D0 and D-dec − D difference is meaningless, and nothing checks for it.
- Fix: before the D0/D-dec runs, check that `site:` matches across the three files. A simple text compare of the blocks is enough; a script check is better.

**M-8. The survey request is not removed after step 0.3.**
- Where: `SKY_SiteSurvey.c:4-13`, `:127-129`.
- Why: if `$profile:SKY_survey_request.json` stays in `server\profiles\dedicated`, every later start runs the 64 × 64 ground sampling, an object query and `ExportProxyData` about 15 s after start. That inflates S7, and every run overwrites the export.
- Fix: add "delete the request file" to step 0.3.

### Low
- **L-1.** Protocol `:56` says run lengths count from the "mission ready" line, but the deadline is `$t0` at launch (validation script `:392`). The `-Minutes` values have about 5 minutes of slack. State that "last 15 min" is cut from the probe log, not taken from the run end.
- **L-2.** Protocol `:65` relies on a `summary.json` cross-check against process start, but `summary.json` stores neither `StartTime` nor `start_s` (`:159`, `:401`). Add `$proc.StartTime` to the "server run" step detail.
- **L-3.** Rows missing from `reviews/fps_results_template.csv`:
  - server A has no repeat-2 rows (needed for the noise floor);
  - S8 has no minute-15 rows (only `loot_items_min40`, `:454-457`);
  - S1b has no p99 rows (`:421-424`).
- **L-4.** Old L4 is still open: there is still no line saying LIGHT_CAP is not isolated because street lights are emissive only, so they count only as entities.
- **L-5.** `-Baseline` together with `-MapGroupPos` is not rejected (validation script `:251` only rejects `-Layout`). That would spawn SKY loot in A with no buildings. Make the two exclusive.
- **L-6.** Q7 heading "W" (protocol `:48`) assumes T4's own face E is world east, but T4 has yaw 270 plus the site yaw. Take the heading from the decal positions in the placement report.
- **L-7.** `check_assets.py:26-27` keeps its own list of alpha-tested textures, a hand-written copy of `gen_configs.py:102` `ALPHA_TEST`. The two can drift and give a false PASS. Import the set, or read `renderFlags` from the rvmat.
- **L-8.** `AFTER_TESTING.md:46-50` has a stray empty table header before the "Only valid with" sentence. It renders as an empty table.
- **L-9.** The header comments in `district_template_noprops.yaml:1,8` and `district_template_decals.yaml:1,8` still name `district_template.yaml`.
- **L-10.** For B11, when the probe is approved:
  - store frame times in a preallocated ring buffer or a fixed histogram;
  - allocate, format strings and print only every 10 s;
  - run the minute-15 object, item and infected counts once, with a radius of 80 m or less.
  
  This keeps the probe's own cost out of the numbers. Verify `MissionServer.OnUpdate` in `P:\scripts\5_Mission` first.

### Measure it
- **Probe:** `server\profiles\dedicated\script_*.log` (avg/p99/max every 10 s, counts at minute 15). Before trusting any S1 avg, confirm A's idle avg is below the cap.
- **Logs:** `*.RPT` for the ready-line timing and S4 path failures; `*.ADM` for the S6 connect-to-spawn times (line texts per B12).
- **Each run's summary:** `build\validation\<stamp>\summary.md`, under:
  - **mapgrouppos**: expected group count per site, times 4 for E;
  - **mission copy**: fresh copy vs reused.
- **Before D/D0/E:** check that `storage_1\export\mapgrouppos.xml` is saved under `placement\surveys\`, and that `SKY_survey_request.json` is gone from the profile.
- **Noise band:** two cold A runs and two warm A runs, recorded per metric.

GATE: PASS
