# Setup Report

Date: 2026-10-05. Branch: `claude/dayz-modding-setup-3q6dxg`.

## Read this first: where this setup ran

This setup ran in a **Linux cloud container** (Ubuntu 24.04) with a fresh clone
of the repo, not on your Windows PC. DayZ, DayZ Tools, DayZDiag, Workbench,
Object Builder, TexView2, AddonBuilder, the P: drive and BattlEye are
Windows-only, so **I installed nothing on your machine and did not run
anything against the real game**. Here is what I did:

1. Wrote the whole workspace (scripts, templates, server configs, agents, docs).
   The install, detection and smoke-test steps are PowerShell scripts for you
   to run on Windows. They ask before every install.
2. Checked everything this container can check: syntax, static analysis,
   dry runs of every build and launch path, the pre-commit hook, config
   rendering, and detection behaviour when nothing is installed.

The Phase 1 installs and the Phase 3 smoke test on real game files are still
**your steps** (see "Manual steps" below). They should take about one hour
plus download time.

## Installed versions

### On your Windows machine
Not checked yet. Run `tools\setup\Get-ToolchainStatus.ps1`. It writes
`build\toolchain-status.json` with versions/build ids of every component; paste it
back to me and I will fill this table in.

| Component | Version |
|---|---|
| Steam / DayZ / DayZ Tools / DayZ Server | _pending: run Get-ToolchainStatus.ps1_ |
| Git / Git LFS / VS Code / Blender / Python / Pillow | _pending_ |
| Mikero pboProject / DePbo | _pending_ |

### In the container (used only for verification, discarded with the session)
| Tool | Version | Why |
|---|---|---|
| PowerShell (portable, scratch dir) | 7.4.6 | parse/lint/dry-run the scripts |
| PSScriptAnalyzer | 1.25.0 | static analysis incl. PS 5.1 syntax compatibility |
| Python / Pillow | 3.11.15 / 12.3.0 | Pillow availability check |
| git / git-lfs | 2.43.0 / 3.4.1 | hook tests |

## What worked (verified here)

| Check | Result |
|---|---|
| All 16 PowerShell scripts/modules parse | PASS |
| PSScriptAnalyzer incl. `PSUseCompatibleSyntax` for 5.1 and 7.4 | PASS, 0 findings |
| `tools\tests\Invoke-SelfTest.ps1` (43 assertions: parse of every script, scaffolding, pack-only vs binarize detection, `$PBOPREFIX$`, pboProject flags, signing guardrails, diag/dedicated launch args, config templates, gitignore) | PASS |
| `Build-Mod.ps1 -ModName ModTemplate -DryRun` on the empty template | PASS: produces `build\@ModTemplate` with manifest + mod.cpp; AddonBuilder command line printed |
| `.githooks/pre-commit` (temporary repo) | blocks `.biprivatekey`, `.pbo`, real `passwordAdmin`; allows placeholders/empty |
| `Initialize-TestServer.ps1` | renders both configs with random admin passwords; rendered files are git-ignored |
| `Get-ToolchainStatus.ps1` on a machine with nothing installed | runs to completion and reports each component as MISS (exit 1) |
| `Test-Toolchain.ps1` with no game | fails cleanly with 4 clear FAIL lines and an actionable message for each |

Bugs found and fixed while testing:
- `Join-Path` throws when P: isn't mounted. All path joins now use `Join-DzPath`.
- Detection crashed or hung when Steam or Program Files paths were missing.

## What failed / could not be done here

| Item | Why | Covered by |
|---|---|---|
| Install Steam, DayZ, DayZ Tools, DayZ Server, Git, VS Code, Blender, Python on Windows | No Windows host in this session | `tools\setup\Install-Toolchain.ps1` |
| Mount P:, extract game data | Needs DayZ Tools on Windows | `tools\setup\Initialize-WorkDrive.ps1` |
| Signing keypair | Needs `DSCreateKey.exe` (DayZ Tools) | `tools\setup\New-SigningKey.ps1` |
| Smoke test against real P:, server and AddonBuilder | Needs the above | `tools\setup\Test-Toolchain.ps1` |
| Verify against Bohemia wiki directly | `community.bistudio.com` returned HTTP 403 to this environment | Cross-checked against community docs (sources below); items to confirm are listed next |

### Assumptions to confirm on first real run
Taken from community docs, not from Bohemia pages I could open:
1. `WorkDrive.exe /Mount P <dir>` and `/ExtractGameData` (argument order). If they fail, the script falls back to `subst`. You can also use the DayZ Tools launcher buttons.
2. AddonBuilder `-include=<file>` format: `tools\build\addonbuilder-include.lst` is a single `;`-separated pattern line, the same as the GUI field. If a packed PBO is missing `.c` or `.layout` files, check this file first.
3. SteamCMD can download `223350` anonymously (current community docs say yes). If it fails, run `Install-Toolchain.ps1 -Only DayZServer -SteamUser <account>`.
4. pboProject CLI is `-P -W=P:\ +Mod=<out> <src>`. Set the engine to DayZ once in the pboProject GUI. AddonBuilder is the default packer, so this only matters if you switch.
5. Workbench is detected as `workbenchApp.exe` and Object Builder as `ObjectBuilder.exe` under the DayZ Tools folder. These are only used for detection.
6. winget ids: `Valve.Steam`, `Git.Git`, `GitHub.GitLFS`, `Microsoft.VisualStudioCode`, `BlenderFoundation.Blender`, `Python.Python.3.13`.

## Manual steps left for you (in order)

1. Clone the repo on Windows. Ideally use a short path without spaces, e.g. `C:\dev\DayZModding`.
2. Open PowerShell in the repo and run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` (once).
3. Copy `workspace.config.example.json` to `workspace.config.json`. Edit `serverDir` and `workDrive.sourceDir` if the defaults (`C:\DayZServer`, `C:\DayZWork`) don't suit you.
4. Run `tools\setup\Get-ToolchainStatus.ps1` to see what's missing.
5. Run `tools\setup\Install-Toolchain.ps1`. It asks for each item: winget packages, then Steam installs of DayZ (221100) and DayZ Tools (830640), then SteamCMD and DayZ Server (223350). Open a **new** terminal afterwards so PATH updates.
6. **Mikero's tools (manual):** install DePbo + pboProject from https://mikero.bytex.digital/Downloads. Optional, since AddonBuilder is the default packer.
7. **Blender add-on (manual):** for Blender 4.4+, install DayZ Object Builder from https://github.com/SXDIST/DayZObjectBuilder/releases. "Arma Toolbox" (the original you asked for) is unmaintained and needs patching for Blender 4.x. Its maintained successor is Arma 3 Object Builder (MrClock8163), and DZOB is the DayZ-focused fork of that. I recommend DZOB.
8. Start DayZ Tools from Steam once so it registers. Then run `tools\setup\Initialize-WorkDrive.ps1`. Extraction is slow and uses roughly 15+ GB.
9. In VS Code, set the Enfusion Script extension's script path to `P:\scripts` (Settings > search "enfusion"). The extension README doesn't name the exact setting key, so I didn't hard-code it.
10. Run `tools\setup\New-SigningKey.ps1 -KeyName <YOURTAG>`. Back up `%USERPROFILE%\.dayz-keys\<YOURTAG>.biprivatekey` offline.
11. Run `tools\setup\Initialize-TestServer.ps1`.
12. Run `tools\setup\Test-Toolchain.ps1`. Expect 4 PASS and the sign step PASS. Then run `tools\tests\Invoke-SelfTest.ps1`.
13. Optional manual check: `tools\launch\Start-DiagLocal.ps1`. This starts a vanilla diag server and client; you should spawn on Chernarus.
14. Send me `build\toolchain-status.json` and `build\smoke-test.json` (they contain local paths only, no secrets), and I will update this report.

## Sources used for verification
- [StarDZ DayZ Modding Wiki: PBO packing (AddonBuilder flags, DSCreateKey/DSSignFile)](https://github.com/StarDZ-Team/DayZ-Modding-WIKI/blob/main/en/04-file-formats/06-pbo-packing.md)
- [StarDZ DayZ Modding Wiki: server setup (SteamCMD 223350, launch params, serverDZ.cfg)](https://github.com/StarDZ-Team/DayZ-Modding-WIKI/blob/main/en/09-server-admin/01-server-setup.md)
- [StarDZ DayZ Modding Wiki: first mod (DayZDiag `-server`, `-filePatching`, junction, `allowFilePatching`)](https://github.com/StarDZ-Team/DayZ-Modding-WIKI/blob/main/en/08-tutorials/01-first-mod.md)
- [StarDZ DayZ Modding Wiki: textures (ImageToPAA / TexView2)](https://github.com/StarDZ-Team/DayZ-Modding-WIKI/blob/main/en/04-file-formats/01-textures.md)
- [Bohemia wiki: Work Drive (search-result summary; page itself returned 403)](https://community.bistudio.com/wiki/Work_Drive)
- [PMC Editing Wiki: Mikero tools user guide (pboProject switches)](https://pmc.editing.wiki/doku.php?id=arma3%3Atools%3Amikero-tools-user-guide)
- [Enfusion Script VS Code extension (yuval.enfusion-script)](https://marketplace.visualstudio.com/items?itemName=yuval.enfusion-script)
- [DayZ Object Builder (Blender 4.4+)](https://github.com/SXDIST/DayZObjectBuilder), [Arma 3 Object Builder](https://github.com/MrClock8163/Arma3ObjectBuilder)
