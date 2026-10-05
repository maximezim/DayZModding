# Batch 6 security gate (security-auditor)

## Security gate: SKY_Skyline Batch 6 (testing and Windows readiness), commit 8a6616d

I did a static review only. No files were edited and I did not run anything with pwsh or Python, so nothing was created that needs cleaning up.

### Critical
None.

### High
None.

### Medium
None.

### Low

**L1. `-Mission` is not checked, so the delete and copy targets can point outside `mpmissions`.**
- Where: /home/user/DayZModding/tools/tests/Invoke-ModValidation.ps1:163, :245-246, :252-253
- Problem: `Join-DzPath` uses `[IO.Path]::Combine` (/home/user/DayZModding/tools/lib/DzCommon.psm1:37), and that drops the base path when a part is rooted.
  - `-Mission 'C:\Users\x\Desktop\proj'` gives `$valMission = C:\Users\x\Desktop\proj.validation`, which line 252 deletes with `Remove-Item -Recurse -Force`.
  - `-Mission '..\..\foo'` deletes `<ServerDir>\..\foo.validation` the same way.
  - An empty mission (both `-Mission` and `server.mission` blank) makes `$srcMission` the whole `<ServerDir>\mpmissions`, which then gets copied into its own child `mpmissions\.validation`.
  - The deleted folder name always ends in `.validation`, and only the local operator can set the value. Nothing in vanilla is ever written to.
- Fix: before step 3, check the name and the resolved path:
  ```
  if ($Mission -notmatch '^[A-Za-z0-9_][A-Za-z0-9_.-]*$' -or $Mission -match '\.\.') { throw "Invalid -Mission '$Mission'" }
  $mpm = [IO.Path]::GetFullPath((Join-DzPath $paths.ServerDir 'mpmissions'))
  if ([IO.Path]::GetDirectoryName([IO.Path]::GetFullPath($valMission)) -ne $mpm.TrimEnd('\','/')) { throw 'mission copy outside mpmissions' }
  ```
  Also refuse to delete `$valMission` if it is a reparse point: `(Get-Item $valMission).Attributes -band [IO.FileAttributes]::ReparsePoint`. Windows PowerShell 5.1 `Remove-Item -Recurse` follows junctions into their targets.

**L2. The validation server does not check its release settings.**
- Where: /home/user/DayZModding/tools/tests/Invoke-ModValidation.ps1:294-296 (and :233 without `-Layout`)
- Problem: the validation cfg is a verbatim copy of `server\serverDZ.dedicated.cfg`, with only `template` changed.
  - The script header (line 17) and TESTING.md:62 both say the run uses `verifySignatures = 2` / `BattlEye = 1`.
  - But if a tester relaxed the rendered dedicated cfg, the validation run silently inherits that. Start-DedicatedServer.ps1 suggests doing so to connect DayZDiag.
  - A run like that could still PASS and move manifest statuses up (AFTER_TESTING.md section 4, `built-unverified -> packed`).
- Fix: in both modes, read the cfg the run will use and fail the step unless it matches `verifySignatures\s*=\s*2`, `BattlEye\s*=\s*1` and `allowFilePatching\s*=\s*0`. Write the three values into summary.json.

**L3. `-Mission` is not escaped when it is put into the cfg.**
- Where: /home/user/DayZModding/tools/tests/Invoke-ModValidation.ps1:295
- Problem: `$Mission` goes into the cfg text and the regex replacement string with no escaping. A `"` would inject cfg content, and `$1`/`$&` would be treated as regex substitution tokens. Only the operator controls the value.
- Fix: the L1 whitelist covers this. Alternatively, build the replacement through a MatchEvaluator.

### Info

- **I1. Vanilla is never edited.** Step 3 only writes inside `<ServerDir>\mpmissions\<Mission>.validation`, which it copies fresh (lines 252-293).
  - `storage_1` is removed only inside that copy.
  - The XML/JSON merges target only files inside the copy.
  - TESTING.md S-04 copies into a new `_sky` folder and does not edit the vanilla copy.
  - S-05 edits only the rendered, git-ignored cfgs.
  - FPS_PROTOCOL.md:8 explicitly says to use the `.validation` copy.
- **I2. The admin password stays out of git and out of the run output.**
  - `server/serverDZ.validation.cfg` is git-ignored (`git check-ignore`: .gitignore:16 `/server/serverDZ.*.cfg`), and the pre-commit `server/serverDZ.*.cfg` case also blocks it.
  - The script prints only the cfg path. The cfg is not copied into `build\validation`, and its contents never reach summary.md or summary.json.
  - The rendered file stays on disk between runs, holding the password from the dedicated cfg. This is expected, the same as `serverDZ.dedicated.cfg`.
- **I3. Copied logs are git-ignored, but the ignore relies on `.gitignore` alone.**
  - Logs are copied to `build\validation\<ts>\logs` and the summaries are written there. That folder is ignored via .gitignore:8 `/build/`.
  - Only top-level `.RPT`, `.log`, `.ADM`, `.mdmp` and `crash*` files are copied (lines 334-336), so the BattlEye folder and its `RConPassword` cfg are not copied.
  - summary.md quotes up to 5 failing log lines per category. These may contain player names.
  - `-AnalyzeOnly <folder>` writes summary.md/json into whatever folder it is given, which may not be ignored.
  - `*.ADM` is not in .gitignore and the hook does not block `build/` (a `git add -f` would get through). Optional hardening: add `*.ADM` to .gitignore, and add `build/*|*.ADM` to the pre-commit `case` in /home/user/DayZModding/.githooks/pre-commit:8.
- **I4. Signing keys are handled correctly.**
  - The script only calls Sign-Mod.ps1. It never reads, copies or logs the private key.
  - Sign-Mod still refuses keys inside the repo (Sign-Mod.ps1:30).
  - In `-DryRun` only, an exception message from Sign-Mod (which may include the private key path, not its contents) goes into the summary's step detail (line 219). That is path disclosure only, in an ignored folder.
- **I5. Process stop.** The `DayZServer_x64` process picked at line 311 is "first started since t0-2s". A second server instance started at the same moment could be the one stopped. Prefer to have Start-DedicatedServer.ps1 return the PID (`Invoke-DzTool -NoWait` already returns `$proc`).
- **I6. `-Layout` and `-ModName`.**
  - `-Layout` is passed only as a Python argument. `sky_layout.py` uses `yaml.safe_load` and writes only under `--out` (`build\validation\<ts>\layout`).
  - `-ModName` is used only to read paths and to call the build/sign/deploy scripts. It does not drive any delete in this script.
- **I7. BattlEye.** No script/RPC changes in this batch, so there are no new filter exceptions. `-filePatching` appears only on the diag rows (TESTING S-08, section 14 setup). Dedicated/[DED] rows keep `verifySignatures=2`, `BattlEye=1`, `allowFilePatching=0` (TESTING.md:9, :231, :259). No document tells testers to turn security settings off for release-like runs.
- **I8. Docs and CSV.** TESTING.md, FPS_PROTOCOL.md, AFTER_TESTING.md, PENDING_VERIFICATION.md, reviews/fps_results_template.csv and the CLAUDE.md command row contain no passwords, tokens, webhooks, IPs or personal paths.
- **I9. Key and secret hygiene since the last gate.** I checked 103cc57..8a6616d, including the user commits aaa7c36, c9d15fa and b363416.
  - `git log --all --diff-filter=A` shows no `*.biprivatekey`, `*.bisign`, `*.bikey`, `*.pbo`, `*.ebo`, `workspace.config.json`, rendered `server/serverDZ.*.cfg`, `build/`, logs or `_handoff` bundles ever added. The one name match is the script tools/assets/make_handoff.py.
  - No added lines match a real `passwordAdmin`/`RConPassword`, Discord webhook, GitHub/Slack/AWS token or PEM private key.
  - SETUP_REPORT.md records only `%USERPROFILE%\.dayz-keys` and the key tag `MZ`, which is not secret.
  - `git config core.hooksPath` is `.githooks`, and the .gitignore and hook rules still cover keys, build output and rendered cfgs.

### Files reviewed
- /home/user/DayZModding/tools/tests/Invoke-ModValidation.ps1
- /home/user/DayZModding/tools/lib/DzCommon.psm1
- /home/user/DayZModding/tools/launch/Start-DedicatedServer.ps1
- /home/user/DayZModding/tools/build/Sign-Mod.ps1
- /home/user/DayZModding/server/templates/serverDZ.dedicated.cfg
- /home/user/DayZModding/.gitignore
- /home/user/DayZModding/.githooks/pre-commit
- /home/user/DayZModding/mods/SKY_Skyline/TESTING.md
- /home/user/DayZModding/mods/SKY_Skyline/FPS_PROTOCOL.md
- /home/user/DayZModding/mods/SKY_Skyline/AFTER_TESTING.md
- /home/user/DayZModding/mods/SKY_Skyline/PENDING_VERIFICATION.md
- /home/user/DayZModding/mods/SKY_Skyline/reviews/fps_results_template.csv
- /home/user/DayZModding/mods/SKY_Skyline/placement/sky_layout.py (path handling only)
- /home/user/DayZModding/CLAUDE.md

GATE: PASS
