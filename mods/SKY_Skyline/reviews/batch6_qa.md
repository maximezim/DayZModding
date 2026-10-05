# Batch 6 QA gate (qa-tester): testing docs and Windows readiness

Commit `8a6616d`, tested on a clean snapshot (`git archive 8a6616d`) in the session scratchpad. No mod code was changed.
Tools: PowerShell 7.4.6 on Linux (PS 5.1 compatibility was checked by reading the code), Blender 4.2.23 LTS with `ARMATOOLBOX_PATH`, and vanilla `dayzOffline.chernarusplus` CE data.
The mission merge ran for real against a fake `<ServerDir>`. A scratch `workspace.config.json` in the snapshot pointed at it; the real repo's config was not touched.

**GATE: FAIL.** The standard suite is green and the mission merge works. The failure is in the one-command validation: it reports **PASS** for several failure modes it exists to catch (H1, M1-M4). TESTING.md does not meet the "every row names evidence" criterion (M6). FPS_PROTOCOL and AFTER_TESTING have reproducibility and traceability gaps (M7, M8).

---

## Standard suite (snapshot)

| Check | Result | Evidence |
|---|---|---|
| `gen_configs.py --check` | PASS, exit 0 | `up to date` |
| `gen_manifest.py --check` | PASS, exit 0 | (no output) |
| `gen_economy.py --check` | PASS, exit 0 | `up to date` |
| `check_assets.py` | PASS, exit 0 | `44 checked, 0 fail, 5 over budget (hypotheses)` |
| `placement/tests/test_sky_layout.py` | PASS, exit 0 | `0 failed` |
| `test_kit.py` (Blender 4.2 headless) | PASS, exit 0 | `KIT GEOMETRY TESTS: PASS (39 assets)` |
| `test_towera.py` | PASS, exit 0 | `TOWER A GEOMETRY TESTS: PASS (81 core components checked)` |
| `tools\tests\Invoke-SelfTest.ps1` | PASS, exit 0 | `[OK] all self-tests passed` (46 OK lines) |
| Python checks with Windows-like piped stdout (`PYTHONIOENCODING=cp1252`) | PASS, all exit 0 | no `UnicodeEncodeError`; inputs are ASCII |

## Invoke-ModValidation.ps1 runs

| Run | Exit | Result |
|---|---|---|
| `-DryRun` (no layout) | 0 | `Validation DRYRUN`; prints the AddonBuilder, robocopy and DayZServer command lines. Sign step `DRYRUN No signing key configured` |
| `-DryRun -Layout district_template.yaml` | 0 | Shows `sky_layout.py ... --strict`, the copy/merge step and `-config=...serverDZ.validation.cfg` |
| `-DryRun -Layout ... -AllowPlaceholder` | 0 | Same, without `--strict` |
| Real, `-SkipBuild -Layout district_template.yaml` (placeholder, strict) | **1** | `[FAIL] sky_layout: FAIL exit 1 - ERROR: tower T4: no base height`. Only `*.FAILED.*` outputs are written. The mission is not copied. Correct |
| Real, `-SkipBuild -SkipStatic -Minutes 0 -Layout <surveyed copy of the template>` | 1 | `sky_layout: PASS status: PASS entities: 323`, `mission copy: PASS`, then `server run: FAIL DayZServer_x64 did not start`. This is expected on Linux: the fake exe is a shell script, so `Get-Process -Name DayZServer_x64` cannot find it. Logs written by the fake server were collected and analysed |
| Real, `-AllowPlaceholder` re-run over an existing `.validation` with a `storage_1` | 1 (same reason) | Idempotent: `mapgroupproto.xml` still has 448 groups (436 + 12, no duplicates), `storage_1` was wiped, and the cfg shows `template = "dayzOffline.chernarusplus.validation";` |
| Real, `-Python nosuchpython` (fresh process) | 1 | Each check reports `FAIL exit  - ` |
| Same, called from a session whose last native exit code was 0 | static checks **PASS** | See M3 |

**Mission merge (real run on the fake server), all verified:**
- The vanilla mission is unchanged: md5 of all 43 files matches.
- `.validation` copy: `sky/sky_objects.json` was written.
- `cfggameplay.json` is semantically identical to vanilla except `WorldsData.objectSpawnersArr = ['sky/sky_objects.json']`. Checked with a recursive compare, including value types, under PS 7.4.
- `cfgeconomycore.xml` gained `<ce folder="sky_ce">` with types, spawnabletypes and events.
- `mapgroupproto.xml` has 436 + 12 groups.
- `cfgeventspawns.xml` has 34 + 1 events, including `StaticSKYRoofDrop` with 16 positions at y 174.600.
- `env/zombie_territories.xml`: the `InfectedCity` zone (dmin 6 / dmax 12, x/z 7000, r 54) went into the territory whose first zone is `InfectedCity`.
- All 4 XML files parse.
- `server\serverDZ.validation.cfg` was rendered, and the template already has `enableCfgGameplayFile = 1`.

**`-AnalyzeOnly` on synthetic log folders:**

| Folder | Content | Exit / status | Correct? |
|---|---|---|---|
| clean | `Mission read.`, `StaticHeliCrash registered`, `[SKY]` info lines, ADM denial | 0 / PASS | yes |
| skyerr | `SCRIPT (E)` in a SKY file, `Can't compile`, `Cannot open object SKY_Skyline\...`, `Cannot load texture SKY_Skyline\...`, `Updating base class ... Land_SKY_Base`, `No entry ... Land_SKY_Foo` | 1 / FAIL, 6 lines | yes |
| vanilla | `StaticHeliCrash`, `Cannot open file dz\...`, `Cannot open object dz\...`, vanilla `Updating base class`, `No entry`, `SCRIPT (W)` | 0 / PASS (5 under "other-mod / vanilla load errors") | yes |
| crashlog | `crash_*.log` | 1 / FAIL | yes |
| dmp | `*.mdmp` | 1 / FAIL | yes |
| **skylower** | the same SKY missing-object/texture/rvmat lines with **lower-case** `sky_skyline\...` paths | **0 / PASS** | **no (M1)** |
| **spawner** | `Object spawner failed to spawn Land_SKY_Floor_Hotel`, `Object spawner: invalid path sky/sky_objects.json`, `[SKY] WARNING: ... invalid elevator config` | **0 / PASS** | **no (H1)** |
| **empty** / **missing** folder | no logs | **0 / PASS** | **no (M4)** |

---

## Findings

### High

**H1. The validation summary passes runs where the district did not spawn, or where SKY's own warnings fire.**
- `Invoke-ModValidation.ps1:49-58` (`$FailPatterns`) has no pattern for any of these:
  - the vanilla spawner errors `PrintToRPT("Object spawner failed to spawn "+item.name)` and `PrintToRPT("Object spawner: invalid path "+ path)` (`P:\scripts\3_game\objectspawner.c:68`, `:89`, checked in `dzs/scripts/3_game/objectspawner.c`);
  - SKY's own `[SKY] WARNING:` (`sky_scripts/scripts/3_Game/SKY/SKY_Constants.c:47`, `PrintToRPT(LOG_TAG + "WARNING: " + msg)`).
- The synthetic `spawner` folder produced `Status: **PASS**`, exit 0. Those lines only raised "SKY script lines : 1" and "mod mentions : 1".
- This contradicts three documents:
  - TESTING.md G-02 says 0 `[SKY] WARNING:` and 0 `Object spawner failed to spawn Land_SKY_*`.
  - The sign-off row "Validation script §0b (summary PASS, 0 SKY FAIL lines)".
  - The AFTER_TESTING §4 `built-unverified -> packed` rule.
- A wrong class name, a failed config PBO, or a broken `objectSpawnersArr` path therefore certifies as PASS.
- Fix (regexes only, B9 scope):
  - `'spawner' = 'Object spawner failed to spawn|Object spawner: invalid path'`, scoped to the mod for the first part. An invalid path should always FAIL.
  - `'SKY warning' = '\[SKY\] WARNING:'`.

### Medium

**M1. Mod-scoped failures are matched case-sensitively, so lower-case engine paths are filed as vanilla noise.**
- `$ModFilter = 'SKY_|Land_SKY|\[SKY\]'` with `-cnotmatch` (`:82`, `:97`).
- The RV engine usually prints file paths lower-cased (`cannot open object a3\...` / `dz\...`). Model paths inside binarized P3Ds and rvmats are lower-case as well.
- Synthetic `skylower` (`Cannot open object sky_skyline\sky_props\sky_locker.p3d`, `Cannot load texture sky_skyline\...`, `Cannot open file sky_skyline\...rvmat`) gave PASS, exit 0.
- The R-L4 intent was to stop vanilla `StaticHeliCrash` and lower-case `sky_` from matching. Fix:
  - keep `\bCrash\b` case-sensitive;
  - make the mod filter case-insensitive and anchored to the prefix: `(?i)sky_skyline[\\/]|land_sky_|\[SKY\]`. Then vanilla `dz\...\sky_*` still cannot match.
- Confirm on the first real run (B9).

**M2. The Blender geometry tests cannot fail on a crash.**
- Blender returns exit 0 when the `-P` script raises: `raise RuntimeError("boom")` gave `exit 0`.
- With a `RuntimeError` injected at the top of both test scripts (scratch copy), the run printed `[OK] test_kit: PASS Blender quit` and `[OK] test_towera: PASS Blender quit`.
- This matters most for B10: the test machine has Blender 5.2, where API breaks are likely.
- Fix:
  - add `--python-exit-code 1` to both `Invoke-DzCheck` Blender calls (`:201-202`);
  - and/or require the `GEOMETRY TESTS: PASS` line in `$out`.

**M3. A missing interpreter can PASS through a stale `$LASTEXITCODE`.**
- When `-Python` or `-Blender` does not resolve, `& $Exe` raises CommandNotFound. `$LASTEXITCODE` is not updated (`:180-181`).
- Run from a session whose last native command exited 0, which is the documented `.\tools\tests\...` usage, all five static checks showed `[OK] ... PASS` with an empty detail.
- Fix: set `$global:LASTEXITCODE = $null` before the call, or check `Get-Command $Exe` first and FAIL with "not found".

**M4. No logs gives PASS.**
- `-AnalyzeOnly` on an empty folder, or on a path that does not exist, gives PASS with exit 0. In the second case `Write-DzSummary` even creates the folder.
- The full run has the same hole: if no RPT or script log is newer than `$t0` (wrong `-profiles`, the server never wrote, or the copy failed), the summary is PASS.
- Fix: FAIL with "no RPT / script log collected" unless at least one `*.RPT` and one `script_*.log` exist.

**M5. PyYAML is not part of the Windows toolchain.**
- `check_assets.py:16`, `placement/sky_layout.py` and `placement/tests/test_sky_layout.py` all `import yaml`.
- `Install-Toolchain.ps1:116` installs only Pillow, and `Get-ToolchainStatus.ps1:112` checks only `PIL`. SETUP_REPORT lists Python 3.11 + Pillow only.
- On a fresh workstation the first `Invoke-ModValidation.ps1` FAILs `check_assets`, the placement self-test and every `-Layout` run with `ModuleNotFoundError`.
- Fix: add PyYAML to Install-Toolchain and Get-ToolchainStatus, and mention it in TESTING S-01.

**M6. TESTING.md: most rows do not name their evidence.**
- 204 test IDs, all unique (no duplicates; checked across every table).
- 120 rows name no evidence: an empty Evidence cell, or a table without an Evidence column.

  | Section | Rows without evidence |
  |---|---|
  | §0 S-01..10 | 10 (no column) |
  | §1 | 8 |
  | §2 | 6 |
  | §3 | 5 |
  | §4 | 5 |
  | §5 | 4 |
  | §6 | 10 |
  | §7 | 4 |
  | §8 | 2 |
  | §10 | 3 |
  | §12 X-01..03 | 3 (no column) |
  | §13 PERF-01 | 1 (no column) |
  | §14 | 18 |
  | §15 | 15 |
  | §16 | 9 |
  | §17 DC/W/F2/R2 | 17 (no column) |

- §18 has 14 more rows with Logs = "none".
- E-07, E-11 and E-14 have an empty Steps cell (the step sits in Preconditions).
- The generic rule on line 10 ("log line(s) ... or a screenshot name") does not say what to capture per row.
- Asset coverage is complete:
  - all 39 `generated_kit` classes (24 street kit including the 3 decals, 10 props, 5 floors/roofs) are covered, by name or by a named group (`Road_*`, `Intersection_*`, `Street_*`, `Barrier_*`, "Apartments, Hotel, Mechanical", "`_Cracks`");
  - Billboard and Graffiti A-D, the window sets and the facade sheets are covered;
  - all 12 `mapgroupproto_sky.xml` groups (L-02/L5-01/L5-03), the keycard types (L-01/L-04), `StaticSKYRoofDrop` (R-xx/F4-15/L5-06), district placement (§18 P5-xx) and infected (Z5-xx) are covered.
- The sign-off table covers §0b-§18 + FPS. Only §0 Setup has no row.

**M7. FPS_PROTOCOL: several configurations and metrics cannot be reproduced with the shipped tools.**
- (a) The **server frame probe does not exist.** S1 "server avg/p99 frame ms (probe)" relies on `SKY_PerfProbe` from `perf_review.md` §4 step 5, described there as an "enforce-coder task". `grep PerfProbe` finds only the review. The "Server avg frame ms S1" threshold cannot be measured.
- (b) **Config E cannot be deployed.** I generated it: `--others o_e1/..,o_e2/..` gives `server total 1647`, which matches the doc. But `Invoke-ModValidation.ps1 -Layout` takes one layout and replaces `objectSpawnersArr` with a single file (`:262`). Merging three `cfgeventspawns` snippets by hand would create three `<event name="StaticSKYRoofDrop">` elements. No procedure is given.
- (c) **Freeze conditions are wiped on every run.** The protocol (via perf_review §4) requires `serverTimeAcceleration = 0` and fixed weather in the `.validation` copy. The script deletes and re-copies the mission and re-renders the cfg each run (`:252-296`), so manual edits are lost.
- (d) **The validation server runs BattlEye with verifySignatures 2**, so only the retail client can join, and the diag-menu statistics the protocol needs are unavailable. `Start-DiagLocal.ps1` has no `-Mission` option; it always uses `server\mpmissions\<server.mission>`. "Diag first" for B/D/D0/D-dec/E therefore needs a manual mission setup, which the protocol does not describe.
- (e) **Config B** (`-Layout ...\layout.yaml`) is a placeholder: `placeholder: true`, centre 7500/7500. With the default `--strict` it FAILs. Nothing says to survey it and centre it on T.
- (f) **D-dec** requires editing the tracked `skyspec.py` (`DECAL_CAPS`) and hand-writing 40 rows. Reproduced:
  - cap 12 gives `ERROR: tower T4: 43 decals > DECAL_CAPS per_tower 12`;
  - cap 64 gives `PASS entities: 363`.

  Ship `placement/fps/{d0,ddec}.yaml` plus a CLI cap override, or document the exact edit and its revert.
- (g) **S4** says `dmax 15`, but the generated and merged zone is dmax 12 (economy/README rule: 10 + 1 per apartment/hotel tower). S4 runs on a different zone than the one written.
- D0 reproduces as documented: removing every `furnish:` gives `PASS entities: 96` (323 - 227).

**M8. AFTER_TESTING: test IDs and commands are missing or inexact.**
- Behaviour table §2 (B1-B10) has no "test that decides it" column and no regenerate command for most rows.
  - B3 and B10 have no TESTING row at all.
  - B9 (a deliberately broken build must FAIL) has no row.
- Parameter rows P4, P6, P7 and P8 name a symptom, not a test ID. Suggested IDs:
  - P4: G-02 / F-06 / S-02
  - P6: K1-04
  - P7: K1-08 / P5-03 / W-02
  - P8: K1-02 / P5-02
- The re-test cells say "street-kit driving rows", "night visual rows" and "any visual row".
- Commands:
  - P2 `build_towera.py -- --out addons --only core` lacks `blender -b --factory-startup -P` and `ARMATOOLBOX_PATH` (`--only` itself exists, `build_towera.py:422`).
  - P3, P6 and P8 say "re-export ... (build_kit.py)" instead of a command line. `Build-SkyAssets.ps1 -Models` re-exports all four builders.
- P1-P9 are all present, and their parameters exist in `skyspec.py:71-107`. The P3 verified flag exists (`PENETRATION` tuples).

### Low

- **L1. A launcher failure leaves no summary.** If `Start-DedicatedServer.ps1` throws, step 4 (`:305`) is not in try/catch. Reproduced with `@SKY_Skyline is not deployed` under `-SkipBuild`: exit 1, but `build\validation\<stamp>\` is never written. Wrap it and `Add-Step 'server start' 'FAIL'`.
- **L2. `-AllowPlaceholder` runs look like real runs.** Nothing in `summary.md` marks the placeholder site: the district is spawned around (0, 0) at y 0, and the step row reads `sky_layout | PASS | WARN : tower T4: no base height`. Add a step or status `PLACEHOLDER`.
- **L3. Dry runs report PASS and write files.** In `-DryRun`, `build (pack)`, `deploy` and `mission copy` report **PASS**; they should report DRYRUN. Dry runs also create `build\validation\<stamp>\summary.*`. Messages at `:242` and `:307` build `$layoutOut\...` and `$outDir\logs` with a literal backslash (cosmetic).
- **L4. TESTING command and setup text is out of date.**
  - §0b line 56 (`-Layout district_template.yaml -Minutes 5`) and §16 line 333 FAIL out of the box: the template is a placeholder and the script defaults to strict. Say "after filling site.center/yaw/survey, placeholder: false".
  - S-05 asks to add `enableCfgGameplayFile = 1`, but both templates already contain it (`serverDZ.{diag,dedicated}.cfg:28`). Make S-05 a check.
- **L5. Test IDs collide with parameter and position names.** These are not duplicates, but they read ambiguously:
  - P3 (penetration parameter) vs P3-xx (prop tests), e.g. P3-13 "penetration is glass (P3)";
  - P5 vs P5-xx;
  - perf_review positions P1-P6 vs parameters P1-P9 (TESTING §13);
  - perf_review S1-S6 vs FPS_PROTOCOL S1-S8, where S4 means different things;
  - K-xx vs K1-xx.
- **L6. The CSV does not match the protocol** (`reviews/fps_results_template.csv`).
  - There is no VD column, though Q1-Q6 run at VD1 **and** VD2, so the two VDs collide.
  - The unit is `ms_or_fps`.
  - D-dec and E rows exist for Q2/Q3/Q6, but the protocol runs them only at Q1/Q4/Q5.
  - There are no run-info rows (commit, GPU, VD), no delta or verdict columns, and no visual-notes rows.
  - `S4 infected_per_floor` for configs A and B is meaningless (no T3 there).
  - The `VAL` id is not defined in the protocol. The markdown table §5.1 has the same D-dec/E column issue.
- **L7. AFTER_TESTING §4 status rules have two gaps.**
  - "loaded it with 0 SKY FAIL lines" can be met by a run without `-Layout`, where no `Land_SKY_*` model or texture is ever instantiated. Require the `-Layout` (surveyed district) run for `packed`.
  - `gen_manifest.py:35` hard-codes `status: built-unverified` for every generated entry, so per-asset promotion needs a generator change, not a value edit.
  - The vocabulary (`planned -> built-unverified -> packed -> tested -> done`, `manifest.yaml:3`) is consistent.
- **L8. Invoke-SelfTest.ps1 does not exercise Invoke-ModValidation.** There is no `-AnalyzeOnly` fixture test. The synthetic folders above (clean / skyerr / skylower / vanilla / spawner / crash / mdmp / empty) would make a cheap offline regression.

### Info: verified OK

- **PS 5.1 syntax in Invoke-ModValidation.ps1:**
  - no `?:`, `??`, `&&`, `||`, `$IsWindows`, `-AsHashtable`, `utf8NoBOM` or `-Parallel`;
  - no non-ASCII bytes, so a BOM-less file is safe in 5.1;
  - native stderr is handled by switching to `ErrorActionPreference = 'Continue'` around `& $Exe ... 2>&1` (`:177-182`);
  - every path goes through `Join-DzPath`, except the module import `Join-Path $PSScriptRoot '..\lib\DzCommon.psm1'` (`:44`), which is not on P:.
- **Not testable here (PS 5.1):** whether the `ConvertFrom-Json`/`ConvertTo-Json` round trip of `cfggameplay.json` keeps number formatting. Diff the file on the first Windows run.
- **CRLF:** `.gitattributes` has `*.ps1 text eol=crlf` / `*.psm1 text eol=crlf`. `git ls-files --eol` shows `attr/text eol=crlf` for `tools/tests/Invoke-ModValidation.ps1` and `tools/lib/DzCommon.psm1` (index LF, so a Windows checkout gets CRLF).
- **Exit codes:**
  - DryRun: 0
  - `-AnalyzeOnly` PASS: 0, FAIL: 1
  - layout FAIL: 1
  - step FAIL: 1
  - launcher throw: 1 (no summary, L1)
- **Vanilla noise:** `StaticHeliCrash` does not match `\bCrash\b` (case-sensitive). `Cannot open file dz\...` and other vanilla load errors land under "other-mod / vanilla load errors".
- **FPS_PROTOCOL numbers are consistent with the generator:**
  - 323 entities and 226 loot items (max) give 549;
  - 227 props;
  - 3 x 549 = 1647 < 2500, and 5 districts (2745) exceed it;
  - T1 office, T2 apartments + garden, T3 hotel + garden, T4 with the mechanical storey at z 14.0-17.2 (opaque, decals allowed);
  - AFTER_TESTING §3 thresholds match FPS_PROTOCOL §4.

## Files

- Reviewed:
  - `mods/SKY_Skyline/TESTING.md`
  - `mods/SKY_Skyline/FPS_PROTOCOL.md`
  - `mods/SKY_Skyline/AFTER_TESTING.md`
  - `mods/SKY_Skyline/PENDING_VERIFICATION.md`
  - `mods/SKY_Skyline/reviews/fps_results_template.csv`
  - `mods/SKY_Skyline/reviews/perf_review.md` §4
  - `tools/tests/Invoke-ModValidation.ps1`
  - `tools/lib/DzCommon.psm1`
  - `tools/launch/Start-DedicatedServer.ps1`
  - `tools/launch/Start-DiagLocal.ps1`
  - `server/templates/*.cfg`
  - `.gitattributes`
  - `assets/manifest.yaml`
  - `assets/skyspec.py`
  - `economy/*`
  - `placement/sky_layout.py`
- Scratch artefacts (not in the repo), under the session scratchpad:
  - `qa6/`: snapshot
  - `qa6_srv/`: fake server
  - `qa6_fix/`: surveyed layout, D0/D-dec/E fixtures
  - `qa6_logs/`: synthetic log folders
  - `qa6m/`: injected-failure copy
  - `qa6_*.log`: run logs

GATE: FAIL
