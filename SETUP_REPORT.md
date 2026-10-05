# Setup Report

Date: 2026-10-05. Machine: Windows 11, Steam library on `D:`, VS Code Insiders.

## Installed on this machine

| Component | Version / location |
|---|---|
| Steam / DayZ (221100) | buildid 25456423, `D:\SteamLibrary\steamapps\common\DayZ` (DayZDiag 1.29.0.163709, includes Sakhal) |
| DayZ Tools (830640) | buildid 24570400, `D:\SteamLibrary\steamapps\common\DayZ Tools` (AddonBuilder 1.0.240.639, Workbench, Object Builder 2.3, ImageToPAA, DSUtils, WorkDrive) |
| DayZ Server (223350) | `D:\SteamLibrary\steamapps\common\DayZServer` (auto-detected from Steam, `serverDir` in the config is only a fallback) |
| SteamCMD | `C:\SteamCMD` |
| Work drive P: | `subst`/WorkDrive mount of `D:\DayZWork`, ~25 GB extracted (`P:\scripts` 2810 `.c` files, `P:\DZ`) |
| Git 2.45.1 / Git LFS 3.5.1 | hooks path `.githooks` set |
| VS Code Insiders | extensions: Enfusion Script, C/C++, XML, GitLens, PowerShell. `enscript.includePaths = P:\scripts` (workspace `.vscode/settings.json`) |
| Blender 5.2.2 LTS | DayZ Object Builder v5.1.0 (extension, enabled) |
| Python 3.11.0 / Pillow 10.0.1 | |
| Signing key `MZ` | `%USERPROFILE%\.dayz-keys` (back up `MZ.biprivatekey` offline) |
| Mikero pboProject / DePbo | not installed (optional, AddonBuilder is the default packer) |

## Verified on this machine

| Check | Result |
|---|---|
| `Test-Toolchain.ps1`: P: mounted | PASS |
| `Test-Toolchain.ps1`: vanilla scripts readable (2810 files) | PASS |
| `Test-Toolchain.ps1`: build empty template (AddonBuilder) | PASS |
| `Test-Toolchain.ps1`: sign template (`MZ`) | PASS |
| `Test-Toolchain.ps1`: dedicated server starts (ready ~90 s after launch) | PASS |
| `Invoke-SelfTest.ps1` | PASS (the key-less sign assertion is skipped once a key is configured) |

## Findings that shaped the scripts

1. **Anonymous SteamCMD no longer works for 223350** ("No subscription"). Use `Install-Toolchain.ps1 -Only DayZServer -SteamUser <login>` or install "DayZ Server" from the Steam library.
2. **`WorkDrive.exe /ExtractGameData` ignores the mounted drive.** It unpacks to `<Documents>\DayZ Projects` (inside OneDrive here). `Initialize-WorkDrive.ps1` now junctions that folder to `workDrive.sourceDir` first and refuses to touch an existing non-junction folder.
3. **WorkDrive.exe always exits with -532462766** (it calls `Console.ReadKey` without a console). The mount/extract succeeds; the script now accepts that exit code.
4. Extraction is ~25 GB and takes 30+ minutes with the Sakhal DLC map present.
5. **The dedicated server prints `Player connect enabled` / `[CE][Hive] :: Init sequence finished` when ready**, not the "Mission read" text the smoke test first looked for. Once ready and idle it stops logging and burns one core, which looks like a hang but isn't. The smoke test now matches `Player connect enabled` (timeout 600 s). Playing the same Steam account on another PC froze the local server during one run.
6. AddonBuilder must not be left open (GUI) while `Build-Mod.ps1` runs; a stale window made one smoke-test build report a missing PBO.
7. JSON paths in `workspace.config.json` need single escaped backslashes (`D:\\DayZWork`).
8. Install scripts prefer `code-insiders` when it is on PATH.
9. The Blender add-on is installed through `blender --command extension install-file` (`Install-Toolchain.ps1 -Only BlenderAddon`).

## Open items

- Optional: install Mikero tools from https://mikero.bytex.digital/Downloads.
- Optional: try `tools\launch\Start-DiagLocal.ps1` for a vanilla diag server + client.

## Sources used for verification
- [StarDZ DayZ Modding Wiki: PBO packing](https://github.com/StarDZ-Team/DayZ-Modding-WIKI/blob/main/en/04-file-formats/06-pbo-packing.md)
- [StarDZ DayZ Modding Wiki: server setup](https://github.com/StarDZ-Team/DayZ-Modding-WIKI/blob/main/en/09-server-admin/01-server-setup.md)
- [StarDZ DayZ Modding Wiki: first mod](https://github.com/StarDZ-Team/DayZ-Modding-WIKI/blob/main/en/08-tutorials/01-first-mod.md)
- [Enfusion Script VS Code extension](https://marketplace.visualstudio.com/items?itemName=yuval.enfusion-script)
- [DayZ Object Builder (Blender 4.4+)](https://github.com/SXDIST/DayZObjectBuilder)
