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

---

## Re-gate (6520175)

Commit `6520175` (range `8a6616d..6520175`, D47-D50), clean snapshot (`git archive 6520175`) in the session scratchpad. No mod or repo code was changed; only this section was appended.
Tools: PowerShell 7.4 on Linux (PS 5.1 by reading), Blender 4.2 LTS + `ARMATOOLBOX_PATH`, vanilla `dayzOffline.chernarusplus`.
The two user commits (setup scripts, SETUP_REPORT.md) are out of scope except for the self-test, which passes.

**GATE: FAIL.** H1, M1-M5, M8 and most Lows are fixed and were verified by running them. M6 is fixed by a general evidence rule, which I accept. M7 is fixed except time freezing.
The gate fails on a new High: the new ready-line wait reads the live RPT with `[System.IO.File]::ReadAllText`. On Windows this throws a sharing violation while the server is writing the file, so every real validation run would abort mid-run (RG-H1). It was introduced in `6520175` and could not be exercised on Linux.

### Standard suite (snapshot 6520175)

| Check | Result | Evidence |
|---|---|---|
| `gen_configs.py --check` / `gen_manifest.py --check` / `gen_economy.py --check` | PASS, exit 0 | `up to date` / (no output) / `up to date` |
| `check_assets.py` (with the new far-LOD alpha gate) | PASS, exit 0 | `44 checked, 0 fail, 5 over budget (hypotheses)` |
| `placement/tests/test_sky_layout.py` (now with the D/D0/D-dec site-identity test) | PASS, exit 0 | `0 failed` |
| `test_kit.py` (`--python-exit-code 1`) | PASS, exit 0 | `KIT GEOMETRY TESTS: PASS (39 assets)` |
| `test_towera.py` (`--python-exit-code 1`) | PASS, exit 0 | `TOWER A GEOMETRY TESTS: PASS (81 core components checked)` |
| `tools\tests\Invoke-SelfTest.ps1` | PASS, exit 0 | 51 `[OK]` lines, `[OK] all self-tests passed`; new rows `validation analysis 'clean' -> PASS`, `'spawnfail' / 'lowerpath' / 'scripterr' -> FAIL`, `no logs -> FAIL` |
| Python checks with `PYTHONIOENCODING=cp1252` | PASS | no encoding errors |

The far-LOD alpha gate was tested by mutation: a harness patched `p3d_inspect.parse` without touching the repo.

| Mutation | Result | Correct? |
|---|---|---|
| `sky_glass.rvmat` added to Res2 of Locker / Floor_Hotel / Decal_Cracks | exit 1: `Land_SKY_Locker FAIL ... blended alpha in Res2 (far LOD): sky_glass.rvmat`, same for Floor_Hotel; the decal is exempt (D22) | yes |
| `sky_window_ca.paa` added to Res2 | exit 1, `blended alpha in Res2 (far LOD): ['sky_skyline\\...\\sky_window_ca.paa']` | yes |
| Control: `sky_foliage_ca.paa` and `sky_decal_graffiti_c_ca.paa` (alpha-tested) in Res2 | exit 0 | yes |
| `sky_glass.rvmat` in Res1 | exit 0 | yes (by design: Res2 and beyond only) |

### Previous findings

| ID | Status | Evidence |
|---|---|---|
| H1 spawner / `[SKY] WARNING` | **FIXED** | `-AnalyzeOnly` fixtures, one line each (results below). `Object spawner failed to spawn Land_SKY_Floor_Hotel` -> exit 1 `object spawner: 1`. `Object spawner: invalid path sky/sky_objects_1.json` -> exit 1. `[SKY] WARNING:` in the RPT -> exit 1, and in `script_*.log` -> exit 1 (`SKY warning: 1`). `[SKY] ERROR:` -> exit 1. Patterns: `Invoke-ModValidation.ps1:77-78`. They match `objectspawner.c:68/:89` and `SKY_Constants.c:47` |
| M1 case-insensitive mod scope | **FIXED** | Lower-case `sky_skyline\...` missing object -> exit 1 `missing object: 1`. Texture -> exit 1 `missing file: 1`. `.rvmat` -> exit 1. `land_sky_foo` `No entry` -> exit 1 `config entry: 1`. Mixed-case `Sky_Skyline/...` -> exit 1. Vanilla fixture (`StaticHeliCrash`, `Cannot open file dz\...`, `dz\data\data\sky_clouds_co.paa`, `dz\data\sky\sky_skybox.rvmat`, vanilla `Updating base class` / `No entry`, `SCRIPT (W)`) -> exit 0 PASS, `other-mod / vanilla load errors : 6`. Filter `sky_skyline\|land_sky_\|\[sky\]` with `-notmatch` (`:104`, `:119`); failure patterns stay case-sensitive (`:118`) |
| M2 Blender crash | **FIXED** | Scratch copy with `raise RuntimeError` at the top of `test_kit.py` / `test_towera.py`: `[FAIL] test_kit: FAIL exit 1 - Blender quit`, same for `test_towera`, run exit 1. `--python-exit-code 1` raises a crashing `build_towera.py` to exit 1 (exit 0 without the flag). `Build-SkyAssets.ps1` passes the flag on all 6 Blender calls, each followed by a `$LASTEXITCODE` check (read) |
| M3 missing tool, stale exit code | **FIXED** | Same pwsh session: `python3 -c pass` (`last=0`), then `-Python nosuchpython -Blender nosuchblender`. Every static step shows `FAIL tool not found: nosuchpython` / `nosuchblender`, `exit=1`. Code: `Get-Command` check plus `$global:LASTEXITCODE = 0` (`:207-208`) |
| M4 no logs | **FIXED** (residual RG-L6) | `-AnalyzeOnly` on an empty folder, an ADM-only folder or a missing folder -> exit 1 with `**No RPT / script log found**`. Full run (fake server exits without writing logs) -> `Status: **FAIL**` with the same line. Dry run -> `DRYRUN`, exit 0 |
| M5 PyYAML / numpy | **FIXED** (residual RG-M1, RG-L7) | The validation step `python modules (yaml, PIL, numpy)` gives `FAIL exit 1 - ModuleNotFoundError: No module named 'yaml'` with a stub interpreter that lacks yaml. `Get-ToolchainStatus.ps1:114-120` adds PyYAML and numpy rows. `Install-Toolchain.ps1:114-116` installs `Pillow numpy PyYAML` |
| M6 TESTING evidence | **FIXED (accepted as a rule)** | TESTING.md:11-13: a general evidence rule for every empty/"none" cell ("A row without evidence is not a PASS"). E-07, E-11 and E-14 now have Steps and Evidence. Rows B3-MC, B9-VAL and B10-EXP exist in §13, but see RG-L4/RG-L5. ID namespace note at :14-16. Test IDs are still unique |
| M7 FPS reproducibility | **FIXED except (c) time** | Verified in real runs (below): multi `-Layout`, `-Baseline`, `-MapGroupPos` list with de-dup, `-MissionOverlay`, `-ServerArgs`, `-NoWipe` marker, and `Start-DiagLocal -Mission` (rooted path accepted, `:43-45`, read). (a) The probe is explicitly blocked as B11 (D48), so this is accepted. (e) Config B needs the site filled in (FPS_PROTOCOL :21). (f) `district_template_noprops/decals.yaml` both generate: D 323 entities / 226 loot, D0 96 / 178, D-dec 332 / 226, matching the FPS_PROTOCOL §1 table. The site block is identical (test). (g) S4 now says dmax 12. **(c) weather is frozen, time is not** (RG-M2) |
| M8 AFTER_TESTING | **FIXED** | §2 has a "Deciding test" column for B1-B12. P4, P6, P7 and P8 name test IDs. P2/P3/P6/P8 give full Blender / `Build-SkyAssets.ps1 -Models` commands with `--python-exit-code 1`; `build_kit.py` / `build_towera.py` accept `-- --out` / `--only`. The `packed` rule requires a non-placeholder `-Layout` run that spawned the asset, and notes that `gen_manifest.py` sets the status |
| L1 launcher failure | FIXED | `@SKY_Skyline` hidden on the fake server: `[FAIL] server start: FAIL @SKY_Skyline is not deployed ...`, summary written, exit 1 |
| L2 placeholder marked | FIXED | `-AllowPlaceholder` run: summary has `**Placeholder layout (-AllowPlaceholder): not a release-like placement.**` (status still PASS; AFTER_TESTING §4 excludes such runs) |
| L3 dry-run status | FIXED | Every step reports `DRYRUN`, overall `Validation DRYRUN`, exit 0. Dry runs still write `build\validation\<stamp>\summary.*`, and `Build-Mod -DryRun` writes `build\@SKY_Skyline\build-manifest.json` (`"dryRun": true`). Both are pre-existing; accepted |
| L4 TESTING text | FIXED | S-05 is now a check. A header note says templates need the site filled in or `-AllowPlaceholder`. §16 says "site filled in" (the §0b line 64 example is still bare but is covered by the note) |
| L5 ID collisions | FIXED (documented) | TESTING.md:14-16 namespace note |
| L6 CSV | FIXED | `run_id,section,id,config,vd,metric,unit,repeat_n,value_raw,median,delta_vs,delta,verdict,notes`, plus a `RUN,info` row |
| L7 status rules | FIXED | see M8 |
| L8 self-test | FIXED | 5 analysis checks in `Invoke-SelfTest.ps1` (see the suite) |

`-AnalyzeOnly` fixture results (`qa6b_logs/`), all exit codes as expected:

| Fixture | Exit / status |
|---|---|
| clean | 0 / PASS |
| sp_fail | 1 / FAIL |
| sp_fail_other | 1 / FAIL |
| sp_path | 1 / FAIL |
| sky_warn_rpt | 1 / FAIL |
| sky_warn_script | 1 / FAIL |
| sky_error | 1 / FAIL |
| low_obj | 1 / FAIL |
| low_tex | 1 / FAIL |
| low_rvmat | 1 / FAIL |
| low_cls | 1 / FAIL |
| mixed_obj | 1 / FAIL |
| vanilla | 0 / PASS |
| empty | 1 / FAIL |
| only_adm | 1 / FAIL |
| missing | 1 / FAIL |
| rpt_only | 0 / PASS |
| skyerr (6 categories) | 1 / FAIL |
| crashlog | 1 / FAIL |
| dmp | 1 / FAIL |

### Mission merge, real runs against a fake `<ServerDir>`

**Setup:**
- The fake `DayZServer_x64.exe` writes an RPT and a script log, then `exec`s a binary named `DayZServer_x64`, so `Get-Process -Name DayZServer_x64` finds it on Linux. That makes the ready-wait loop run for real.
- `FAKE_MODE=ready` appends `Player connect enabled` after 8 s, `noready` never appends it, and `die` exits after 8 s with no logs.
- Vanilla mission md5s were taken before the runs (43 files) and match after all runs.

**Run 1:**
```
-SkipStatic -SkipBuild -Minutes 1 -AllowPlaceholder
-Layout district_template.yaml,district_template_noprops.yaml
-MapGroupPos mgp_a.xml,mgp_b.xml
-MissionOverlay overlay
-ServerArgs '-limitFPS=1000'
```
Result: exit 0.
- **Steps:**
  - `sky_layout 1/2: PASS`
  - `mapgrouppos: PASS 4 Land_SKY_* groups merged`
  - `mission overlay: PASS`
  - `release settings: PASS`
  - `server ready: PASS 10 s from launch to "Player connect enabled"`
  - `server run: PASS 1 min`
  - `server stop: PASS`
  - The run took 1 min 12 s, so `-Minutes` counts from the ready line.
- **`cfggameplay.json`:** `objectSpawnersArr = ['sky/sky_objects_1.json', 'sky/sky_objects_2.json']` (323 and 96 objects). Every other key and value type is identical to vanilla (recursive compare).
- **`cfgeventspawns.xml`:** 34 -> 35 events. **One** `StaticSKYRoofDrop` with 32 positions (16 + 16), not two events.
- **`mapgrouppos.xml`:** 11679 -> 11683. Each export had a duplicate `Land_SKY_Locker`, and the same position appeared in both files: both duplicates were dropped. Vanilla `Land_Mil_Barracks1` in the export was not merged.
- **Other files:**
  - `mapgroupproto` 436 -> 448
  - `cfgeconomycore.xml` gained `<ce folder="sky_ce">` with 3 files
  - `InfectedCity` territory gained 2 zones (one per layout; dmin 6 / dmax 12, r 54)
  - all 6 XMLs parse
- **Overlay and marker:** the overlay `cfgweather.xml` and `env/` file were copied last. `storage_1` was wiped. The marker file holds a SHA256 for each layout and MapGroupPos file.
- **Server command line:**
  - `fake_args.txt` ends with `-mod=@SKY_Skyline -limitFPS=1000`
  - `-config=...serverDZ.validation.cfg`, which contains `template = "dayzOffline.chernarusplus.validation";`

**Other runs:**

| Run | Options | Exit | Result |
|---|---|---|---|
| E-style | two surveyed layouts (`e1.yaml`, `e2.yaml`), strict | 0 | `status: PASS entities: 323` each, the second with `--others` |
| `-NoWipe`, same config | as above | 0 | `reused (-NoWipe, warm start)`; a planted `storage_1/data/qa6b_keep.bin` survived |
| `-NoWipe`, other config | one layout instead of two | 1 | `-NoWipe: ... was built for a different config (marker mismatch)`; storage untouched; no summary (RG-L2) |
| `-Baseline` | | 0 | `objectSpawnersArr = []`, 34 events (no roof drop), mapgroupproto 448 (same CE as D) |
| `-Baseline -MapGroupPos` | | 1 | refused (`:271`) |
| `die` | | 1 | `server run: FAIL server exited early (code )` + `No RPT / script log found` |
| `noready`, `-Minutes 0` | | 1 | after 10 min 2 s: `server ready: FAIL no 'Player connect enabled' within 0 + 10 min`, then `server stop: PASS stopped`; no server left running. (The first attempt used a fake that lived 600 s; it exited just before the deadline and correctly gave `server exited early`.) |

Ready-wait logic (`:446-470`), by reading:
- The deadline is launch + `Minutes` + 10 min until ready, then ready + `Minutes`.
- An early exit is `server run FAIL`. No ready line is `server ready FAIL`, then the server is stopped.
- S7 = detection time - `proc.StartTime`.

### PowerShell 5.1 (by reading)

- None of the changed `.ps1` files (`Invoke-ModValidation`, `Invoke-SelfTest`, `Start-DiagLocal`, `Start-DedicatedServer`, `Get-ToolchainStatus`, `Install-Toolchain`, `Build-SkyAssets`) contain `??`, ternaries, `&&`/`||`, `$IsWindows`, `-AsHashtable`, `-Parallel`, `utf8NoBOM`, `::new(` or multi-child `Join-Path`.
- They contain no non-ASCII bytes, and are `attr/text eol=crlf`.
- `Invoke-DzCheck` still switches to `Continue` around native stderr.
- Exceptions: RG-H1 (a runtime issue, not syntax) and RG-M1.

### New findings

#### High

**RG-H1. The ready-line poll reads the live RPT with `File.ReadAllText`. On Windows that fails while the server writes, so every real validation run aborts.**
- `Invoke-ModValidation.ps1:458`: `$txt = [System.IO.File]::ReadAllText($r.FullName)`.
- .NET opens the file with `FileShare.Read`. Windows refuses that open (sharing violation, `IOException: ... being used by another process`) while another process holds a write handle, and the running server keeps its RPT open for writing.
- Under `$ErrorActionPreference = 'Stop'` the exception ends the script at the first poll after the RPT appears (about 5-10 s after launch):
  - no `server ready` / `server run` step and no `summary.md`;
  - exit 1;
  - **the server is left running** (the stop at `:468` is never reached), holding port 2302 for the next run.
- This blocks B9-VAL, the FPS protocol (S7 comes from this step) and the `packed` promotion rule.
- `Test-Toolchain.ps1:70` (the user-verified smoke test) reads with `Get-Content -Raw -ErrorAction SilentlyContinue`, which opens with `FileShare.ReadWrite`. That is why the smoke test works on the user's machine; this path has never run there.
- Not reproducible on Linux (no mandatory locks), so the fake-server run passed.
- Fix (script only):
  - read through `Get-Content -Raw -LiteralPath $r.FullName -ErrorAction SilentlyContinue`, or `New-Object IO.FileStream($p, 'Open', 'Read', 'ReadWrite')` + StreamReader inside try/catch;
  - optionally wrap the wait loop so any exception still stops the server and writes a summary.

#### Medium

**RG-M1. `Install-Toolchain.ps1 -Only Pillow` throws on Windows PowerShell 5.1 exactly when PyYAML or numpy is missing.**
- `:114`: `& python -c 'import PIL, numpy, yaml' 2>$null` under `$ErrorActionPreference = 'Stop'` (`:27`).
- In 5.1, redirected native stderr is subject to the error preference. PS 7.2 removed this (`PSNotApplyErrorActionToStderr`). So the `ModuleNotFoundError` traceback becomes a terminating `NativeCommandError` before `$LASTEXITCODE` is checked, and the pip install is never offered.
- SETUP_REPORT lists Python 3.11 + Pillow only, so this is the user's case.
- The pattern existed before for `PIL`, but the M5 fix now depends on it.
- `Get-ToolchainStatus.ps1` is safe (try/catch in `Get-CmdOutput`). The validation module check is safe (`Continue`).
- Fix: set `$ErrorActionPreference = 'Continue'` around the probe (as in `Invoke-DzCheck`). Workaround: `python -m pip install --user PyYAML numpy`.

**RG-M2. FPS time freeze cannot be applied as documented (residual of M7(c)).**
- FPS_PROTOCOL §0.45 says to put "the time settings the mission uses" in the `-MissionOverlay` folder.
- But time is a server-cfg setting: `serverTime`, `serverTimeAcceleration`, `serverTimePersistent` (`server/templates/serverDZ.dedicated.cfg:19-22`, acceleration 12).
- `serverDZ.validation.cfg` is re-rendered from `server\serverDZ.dedicated.cfg` on every run, and only `template` is replaced (`:398-402`).
- perf_review §4 step 3 requires fixed `serverTime` + `serverTimeAcceleration = 0`, at noon and at 17:00 for S5. With the documented procedure every run starts at system time with 12x acceleration, so the client rows (Q1-Q7) are not comparable.
- Fix, either:
  - document editing the rendered `server\serverDZ.dedicated.cfg` (persists across validation runs; revert afterwards); or
  - add a `-ServerTime` option that patches the three keys in the rendered validation cfg.

#### Low

- **RG-L1. S7 resolution is 5 s, but the D vs D0 S7 pass threshold is +5 s** (FPS_PROTOCOL :94).
  - The ready line is detected on a 5 s poll (`:452`), so start-to-ready carries 0-5 s of detection lag.
  - Use the RPT line's own `hh:mm:ss` against the process start, or poll every 1 s.
  - The §0.5 noise band (2x) limits the damage.
- **RG-L2. Some refusals still exit without a summary.**
  - `-NoWipe` marker mismatch (`:304`), `-Baseline` with `-Layout`/`-MapGroupPos` (`:270-271`), invalid `-Mission` (`:193`) and a missing vanilla mission (`:310`) all `throw` with exit 1 and no `summary.md` (same class as L1).
- **RG-L3. The `-NoWipe` marker omits `-MissionOverlay` and `-AllowPlaceholder`.**
  - A warm run with a different overlay or placeholder flag reuses the copy silently.
  - Paths are hashed as typed: relative vs absolute paths to the same file mismatch, which fails safe.
- **RG-L4. TESTING §13 table shape.** The table header has 3 columns (`| ID | Expected | PASS/FAIL |`), but B3-MC, B9-VAL and B10-EXP have 4 cells. GFM drops the extra cell: the steps render under "Expected" and the expected text under "PASS/FAIL". Add a Steps column.
- **RG-L5. B10-EXP cannot be run as written.**
  - It says `Build-SkyAssets.ps1 -Models -Blender <exe>` "into a scratch `--out`". The script has no output parameter: it re-exports into `mods\SKY_Skyline\addons`, overwriting the committed P3Ds, and also regenerates the textures/PAAs.
  - Use the direct `blender -b --factory-startup --python-exit-code 1 -P build_*.py -- --out <scratch>` lines (with `ARMATOOLBOX_PATH`).
- **RG-L6. M4 accepts an RPT without a script log** (`:134`, "RPT **or** log"). The `rpt_only` fixture gives PASS. The original ask was at least one of each.
- **RG-L7. TESTING S-01 still does not mention PyYAML/numpy** (M5 asked for it). Covered in practice by the new status rows and the validation module check.
- **RG-L8 (cosmetic).**
  - `server exited early (code )`: a process obtained with `Get-Process` may not expose `ExitCode`.
  - `-AnalyzeOnly <missing path>` still creates the folder to write the summary.

#### Info

- The `object spawner` pattern is not mod-scoped: any spawner failure FAILs the run. This is stricter than suggested and acceptable, since vanilla ships no `objectSpawnersArr`.
- The roof-drop merge appends positions without de-duplication. Two layouts on the same site give 32 positions / 16 distinct. E uses distinct centres, so this is not an issue there.
- `sky_layout.py --others` checks entity caps only, not cross-district overlap. FPS_PROTOCOL requires E districts at different centres.
- The ready line is searched only in `*.RPT`; Test-Toolchain also searched `*.log`. This fails closed (`server ready FAIL`). Confirm the file on the first run (B12).
- Carried from the previous gate: on 5.1, check the `ConvertFrom-Json`/`ConvertTo-Json` round trip of `cfggameplay.json`, including that `objectSpawnersArr` stays a plain array and does not turn into `{"value": ..., "Count": ...}`. Diff the file on the first Windows run.

### Files and artefacts

- Reviewed:
  - `tools/tests/Invoke-ModValidation.ps1`
  - `tools/tests/Invoke-SelfTest.ps1`
  - `tools/launch/Start-DiagLocal.ps1`
  - `tools/launch/Start-DedicatedServer.ps1`
  - `tools/setup/Get-ToolchainStatus.ps1`
  - `tools/setup/Install-Toolchain.ps1`
  - `tools/setup/Test-Toolchain.ps1` (comparison only)
  - `mods/SKY_Skyline/assets/Build-SkyAssets.ps1`
  - `mods/SKY_Skyline/assets/check_assets.py`
  - `mods/SKY_Skyline/placement/district_template{,_noprops,_decals}.yaml`
  - `mods/SKY_Skyline/placement/tests/test_sky_layout.py`
  - `mods/SKY_Skyline/TESTING.md`
  - `mods/SKY_Skyline/FPS_PROTOCOL.md`
  - `mods/SKY_Skyline/AFTER_TESTING.md`
  - `mods/SKY_Skyline/PENDING_VERIFICATION.md`
  - `mods/SKY_Skyline/DECISIONS.md` D47-D50
  - `mods/SKY_Skyline/reviews/fps_results_template.csv`
- Scratch (not in the repo), under the session scratchpad:
  - `qa6b/`: snapshot
  - `qa6b_m2/`: crash-injected copy
  - `qa6b_srv/`: fake server
  - `qa6b_logs/`: fixtures
  - `qa6b_fix/`: mapgrouppos and overlay fixtures
  - `qa6b_*.log`: run logs
  - `qa6b_alpha_mut.py`: alpha-gate mutation harness
- The `build/` folders created in the scratch snapshots were deleted afterwards.

GATE: FAIL

## Re-gate 2 (c049831)

Commit `c049831` (range `6520175..c049831`, D51), clean snapshot (`git archive c049831`) in the session scratchpad (`qa6c/`). No mod or repo code was changed; only this section was appended.
Tools: PowerShell 7.4 on Linux (PS 5.1 by reading), Blender 4.2 LTS + `ARMATOOLBOX_PATH`. The fake `<ServerDir>` is a fresh copy of `qa6b_srv` (`qa6c_srv`).

**GATE: PASS.** The RG-H1 fix covers the paths that run on every validation: the ready-line wait and the log analysis both read through `Read-DzShared`. RG-M1 and RG-M2 are fixed, and so are L1-L7. L8 is partly fixed (cosmetic).
One Medium is left (RG2-M1): with `-KeepRunning`, the log collection still copies the live RPT / script log / ADM with `Copy-Item`, not `Read-DzShared`. FPS S6 uses `-KeepRunning`, so fix this before the first S6 run on Windows. It fails closed (FAIL summary, exit 1), so it does not block the gate.

### Standard suite (snapshot c049831)

| Check | Result | Evidence |
|---|---|---|
| `gen_configs.py --check` / `gen_manifest.py --check` / `gen_economy.py --check` | PASS, exit 0 | `up to date` / (no output) / `up to date` |
| `check_assets.py` | PASS, exit 0 | `44 checked, 0 fail, 5 over budget (hypotheses)` |
| `placement/tests/test_sky_layout.py` | PASS, exit 0 | `0 failed` |
| `tools\tests\Invoke-SelfTest.ps1` | PASS, exit 0 | 51 `[OK]` lines, `[OK]   all self-tests passed` |
| Python checks with `PYTHONIOENCODING=cp1252` | PASS | no encoding errors |
| `Invoke-ModValidation.ps1` parse (PS 7.4 `Parser.ParseFile`) | PASS | 0 parse errors |

`-AnalyzeOnly` fixtures (fresh copies of `qa6b_logs/`):
- Unchanged results: clean 0/PASS, vanilla 0/PASS. All the FAIL fixtures still give 1/FAIL: sp_fail, sp_fail_other, sp_path, sky_warn_rpt, sky_warn_script, sky_error, low_obj, low_tex, low_rvmat, low_cls, mixed_obj, skyerr (6 categories), crashlog, dmp, empty, only_adm, missing.
- The pattern fixtures still FAIL on their pattern, not only on missing logs. Each has an RPT and a script log, with `failCount` 1 (skyerr: 6).
- **rpt_only now gives 1/FAIL** (`**RPT or script log missing**`), and a new `script_only` fixture gives 1/FAIL (see L6).

### Previous findings

| ID | Status | Evidence |
|---|---|---|
| RG-H1 live RPT read | **FIXED on the every-run paths; residual RG2-M1 for `-KeepRunning`** | See "RG-H1 read paths" below |
| RG-M1 installer probe under 5.1 | **FIXED** | `Install-Toolchain.ps1:115-119` switches to `Continue` around `& python -c ... 2>$null`, reads `$LASTEXITCODE` into `$probe`, and restores the preference. See "RG-M1 simulation" below |
| RG-M2 time freeze | **FIXED** (residuals RG2-L1/L2/L3) | See "RG-M2 run" below |
| RG-L1 S7 resolution | FIXED | `:474` polls every 1 s until ready, then every 5 s. The fake appends the ready line 8 s after launch: summary `server ready: PASS 8 s from launch to "Player connect enabled"` (previously 10 s) |
| RG-L2 refusals without summary | FIXED | Outer `try { } catch { }` (`:234-515`) writes `summary.md` with an `error` FAIL step and exits 1. The inner `exit` calls are not caught (checked: `exit 3` inside `try` returns 3). Runs are in the table below |
| RG-L3 marker | FIXED | The fresh run's `sky_validation_marker.txt` holds `baseline=False`, `placeholder=True`, the layout and MapGroupPos hashes, and **one SHA256 per overlay file** (`overlay/cfgweather.xml`, `overlay/env/qa6b_marker.xml`). `-NoWipe` with a different placeholder flag or an added overlay -> marker mismatch, exit 1 |
| RG-L4 TESTING §13 shape | FIXED | Header and the B3-MC, B9-VAL and B10-EXP rows all have 3 cells; the steps and the expected result now share the "Expected" cell |
| RG-L5 B10-EXP | FIXED | See "RG-L5 run" below |
| RG-L6 RPT-only folder | FIXED | `:145`: no `*.RPT` **or** no `script*.log` -> NoLogs. rpt_only -> exit 1, script_only -> exit 1, `die` run -> `**RPT or script log missing**` |
| RG-L7 S-01 | FIXED | TESTING S-01 now names Pillow / PyYAML / numpy and `Install-Toolchain.ps1 -Only Pillow` |
| RG-L8 cosmetic | PARTLY FIXED (accepted) | Text is now `server exited early (exit code )`, but the code is still empty on Linux: `Get-Process` objects do not expose `ExitCode` there; Windows likely shows it. `-AnalyzeOnly <missing>` still creates the folder to write its summary. Both cosmetic |

**RG-H1 read paths** (by reading every file access in `Invoke-ModValidation.ps1`):
- `Read-DzShared` (`:91-99`): `FileStream(Open, Read, ReadWrite -bor Delete)` + `StreamReader.ReadToEnd`, disposed in `finally`. Any exception returns `''`.
- Used by the ready wait (`:480`), by `Get-DzLogSummary` (`:125`, replacing `File.ReadLines`) and by the marker read (`:319`).
- The other `Get-Content` / `Copy-Item` calls (`:335-423`, `:435`) touch the mission copy, the repo economy files and the server cfg, none of which the server holds open.
- **Exception: `:500-502`** copies the profile's logs with `Copy-Item`; see RG2-M1.
- The analysis then runs on those copies (`$logOut`), so `Get-DzLogSummary` never reads the live files in a normal run.
- Sharing semantics cannot be exercised on Linux, which has no mandatory locks.

**RG-M1 simulation** (pwsh): an extracted copy of the block with `$PSNativeCommandUseErrorActionPreference = $true` stands in for 5.1's terminating stderr. A fake `python` writes `ModuleNotFoundError` to stderr and exits 1.
- Old code: `THREW: NativeCommandExitException`.
- New code: reaches `Confirm-Install` (`PROMPT: Pillow + numpy + PyYAML`), then `skipped by user (probe=1, EAP now Stop)`.
- The real script refuses non-Windows hosts, so it was not run directly.

**RG-M2 run**: real merge against the fake server (`-Layout district_template.yaml -AllowPlaceholder -MapGroupPos mgp_a.xml -MissionOverlay overlay -ServerTime 2026/6/15/12/0 -Minutes 0`), exit 0.
- `diff serverDZ.dedicated.cfg serverDZ.validation.cfg` shows only the intended changes:
  - `serverTime = "2026/6/15/12/0";`
  - `serverTimeAcceleration = 0;`
  - `serverNightTimeAcceleration = 0;`
  - `template = "dayzOffline.chernarusplus.validation";`
- `serverTimePersistent = 0` is kept. The config the fake server received is identical to the rendered file.
- A following `-NoWipe -ServerTime 2026/6/15/17/0` run re-renders to `serverTime = "2026/6/15/17/0";` (the cfg is not part of the marker, which is correct).
- Format check (`:418`):
  - `12:00` is refused, exit 1, with a summary.
  - The injection attempt `2026/6/15/12/0"; BattlEye = 0; x="` is refused, exit 1.
- FPS_PROTOCOL §0.45 now covers weather by overlay and time by `-ServerTime` (12:0 and 17:0), with the value format marked B12. D51 is recorded.
- Vanilla mission md5s (43 files) are unchanged after all runs. No fake server was left running.

**RG-L5 run**: B10-EXP was run as written on Linux, with Blender 4.2 + `ARMATOOLBOX_PATH`. It used scratch `qa6c_exp/addons` + `qa6c_exp/assets`, and all 4 builders ran with `--python-exit-code 1`.
- All exit 0.
- **44/44 P3Ds byte-identical** to the committed ones. `build_stats.json` / `build_stats_kit.json` are identical too; the builders write them to `<out>\..\assets`, which is why the row creates that folder.
- The mod tree is unchanged apart from git-ignored `__pycache__`.

Refusal and error runs:

| Run | Exit | Summary / message |
|---|---|---|
| `-NoWipe`, same config | 0 | `reused (-NoWipe, warm start)` |
| `-NoWipe` + `-AllowPlaceholder` (copy built without) | 1 | summary `\| error \| FAIL \| -NoWipe: ... was built for a different config (marker mismatch) ...` |
| `-NoWipe` + an overlay the copy was built without | 1 | same marker mismatch, summary written |
| `-Baseline -Layout` | 1 | summary `-Baseline and -Layout are exclusive ...` |
| `-Baseline -MapGroupPos` | 1 | summary `-Baseline and -MapGroupPos are exclusive ...` |
| `-Mission nosuchmission` | 1 | summary `Vanilla mission not found: ...` |
| `-ServerTime 12:00` / injection string | 1 | summary `-ServerTime must look like 2026/6/15/12/0` |
| `-Mission ../evil` | 1 | `Invalid -Mission '../evil' (letters, digits, _ . - only)`, no folder (accepted as specified) |
| `die` | 1 | `server run: FAIL server exited early (exit code )` + `RPT or script log missing` |
| `-KeepRunning` | 0 | `server stop: SKIP -KeepRunning (PID ...)`, logs copied while the fake server ran (works on Linux; see RG2-M1) |

### PowerShell 5.1 (by reading)

- `Invoke-ModValidation.ps1` and `Install-Toolchain.ps1` contain no `??`, ternaries, `&&`/`||`, `::new(`, `$IsWindows`, `-AsHashtable`, `-Parallel` or `utf8NoBOM`.
- Both are CRLF throughout (515/515 and 157/157 lines) and contain no non-ASCII bytes.
- 5.1-compatible constructs:
  - `New-Object System.IO.FileStream(...)` with a `-bor` of `FileShare` values;
  - `return` inside `try`/`finally`;
  - the outer `try`/`catch` around a script body containing `exit`.

### New findings

#### Medium

**RG2-M1. Live logs are still copied with `Copy-Item` when the server is running (`-KeepRunning`), and right after `Stop-Process -Force`.**
- Where: `Invoke-ModValidation.ps1:500-502`, `Get-ChildItem ... | ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $logOut }`.
- Why it matters:
  - With `-KeepRunning` (FPS_PROTOCOL S6, `FPS_PROTOCOL.md:72`) the RPT, script log and ADM are still open for writing. On Windows, `Copy-Item` goes through `File.Copy` / `CopyFile`, which does not use `Read-DzShared`. Whether that open succeeds against the server's write handle is not guaranteed and cannot be tested here.
  - If it fails, the outer catch writes a FAIL summary with an `error` step and exits 1. The log analysis is lost, but the server keeps running, as requested.
  - Without `-KeepRunning`, `Stop-Process -Force` does not wait for the process to exit (`TerminateProcess` is asynchronous), so the same copy can race the closing handles. This is unlikely.
- It fails closed, so it does not block the gate. It does mean the RG-H1 criterion "also with -KeepRunning" is not fully met.
- Fix (script only):
  - copy through a shared read, e.g. `Save-DzText (Join-DzPath $logOut $_.Name) (Read-DzShared $_.FullName)` for text logs, and keep `Copy-Item` for `.mdmp`;
  - add `Wait-Process -Id $proc.Id -Timeout 30 -ErrorAction SilentlyContinue` after `Stop-Process`.

#### Low

- **RG2-L1. `-ServerTime` without `-Layout` / `-Baseline` is silently ignored.**
  - Run with only `-ServerTime 2026/6/15/12/0`: exit 0 PASS. The server got `-config=...serverDZ.dedicated.cfg` with `serverTime = "SystemTime"` / acceleration 12, and no warning was given.
  - Also, `-DryRun -ServerTime bogus` is not validated (exit 0, DRYRUN).
  - The FPS protocol always passes `-Layout` or `-Baseline` (§1), so FPS runs are not affected.
  - Fix: refuse `-ServerTime` without them, and check the format before the build.
- **RG2-L2. A bad `-ServerTime` is detected only after the mission copy has been rebuilt.**
  - `:418` runs after the wipe and merge, so a typo wipes the existing `.validation` copy and its storage before refusing. A following `-NoWipe` then reuses a cold copy as "warm".
  - Fix: move the format check up next to the `-Mission` check (`:204`).
- **RG2-L3. `serverNightTimeAcceleration = 0` is outside the range the server docs give (0.1-64).**
  - It is a multiplier on `serverTimeAcceleration`, which is 0 here, so it is redundant. The engine may clamp it or log a warning.
  - Setting it to 1, or leaving it as is, is enough. Confirm together with the `serverTime` format and the effect of `serverTimeAcceleration = 0` on the first run (B12).
  - The summary does not record the `-ServerTime` value. For the FPS CSV, note it in `notes` or add it to the `mission copy` step detail.
- **RG2-L4. `Read-DzShared` returns `''` on any read error, so an unreadable log is analysed as empty (fail-open).**
  - NoLogs only checks that the file exists.
  - In a normal run it reads the copies in `logs\`, so the risk is small.
  - Fix: count read errors as a failure line (e.g. `crash`/`missing file`), or return `$null` and FAIL.

#### Info

- Parameter comment misplaced: `:43-44` now carries the `-MissionOverlay` description at the end of the `-ServerTime` line. The `.DESCRIPTION` block does not list `-MissionOverlay` / `-ServerTime`. Cosmetic.
- The outer catch does not stop a server that was already started. After launch, only `Stop-Process` (when racing a self-exit) or the log copy can throw, and both happen after the stop or under `-KeepRunning`, so no leftover server is expected.
- `Mod not found` (`:232`) is still thrown before the `try`, so it writes no summary. It is not on the RG-L2 list.
- Two runs started in the same second share `build\validation\<stamp>`, and the second overwrites the first's summary. Seen here with back-to-back refusals; not a problem for manual runs.
- B10-EXP does not mention `ARMATOOLBOX_PATH`. The builders fail with a clear `Set ARMATOOLBOX_PATH ...` message, and AFTER_TESTING P2 shows it.
- Carried: the 5.1 `ConvertTo-Json` round trip of `cfggameplay.json` still needs a diff on the first Windows run.

### Files and artefacts

- Reviewed:
  - `tools/tests/Invoke-ModValidation.ps1`
  - `tools/setup/Install-Toolchain.ps1`
  - `server/templates/serverDZ.dedicated.cfg`
  - `mods/SKY_Skyline/TESTING.md` (S-01, §13)
  - `mods/SKY_Skyline/FPS_PROTOCOL.md` (§0.45, S6)
  - `mods/SKY_Skyline/DECISIONS.md` (D51)
  - `mods/SKY_Skyline/AFTER_TESTING.md` (B10)
  - `mods/SKY_Skyline/assets/blender/build_*.py` / `skygeo.py` (output paths)
- Scratch (not in the repo), under the session scratchpad:
  - `qa6c/`: snapshot
  - `qa6c_srv/`: fake server
  - `qa6c_logs/`: fixtures + `script_only`
  - `qa6c_exp/`: B10-EXP export
  - `qa6c_m1.ps1` + `qa6c_fakepy/`: RG-M1 simulation
  - `qa6c_*.log`: run logs
- `qa6c/build/` was deleted afterwards.

GATE: PASS
