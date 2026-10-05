# DayZ Modding Workspace

DayZ (Enfusion engine) mod development workspace for Windows. Tooling is PowerShell
(Windows PowerShell 5.1 or PowerShell 7). Status of the machine setup: `SETUP_REPORT.md`.

## Layout

```
mods/<Mod>/                 mod sources (one folder per mod)
  mod.cpp                   launcher metadata -> build/@<Mod>/mod.cpp
  addons/<pbo>/             one folder = one PBO; prefix <Mod>\<pbo> unless $PBOPREFIX$ says otherwise
    config.cpp              CfgPatches (+ CfgMods, CfgVehicles ...)
    scripts/3_Game|4_World|5_Mission/   Enforce Script (if this PBO carries scripts)
  economy/                  CE files shipped with the mod (types.xml ...), never merged into vanilla
  assets/                   manifest.yaml, generator scripts (Blender/Pillow), MANUAL_STEPS.md (not packed)
  placement/                layout.yaml -> objectSpawnersArr JSON (+ survey validation)
templates/ModTemplate/      empty skeleton (CfgPatches only) used by New-Mod.ps1 and smoke tests
tools/lib/DzCommon.psm1     shared helpers: config, Steam/tool detection, dry-run process runner
tools/setup/                install / detect / work drive / keys / test server / smoke test
tools/build/                New-Mod, Build-Mod, Sign-Mod, Deploy-Mod, Build-And-Run
tools/launch/               Start-DiagLocal (DayZDiag server+client), Start-DedicatedServer
tools/tests/                Invoke-SelfTest.ps1 (offline, no game needed)
tools/assets/               p3d_inspect.py (MLOD LOD/selection gate), enscript_xref.py (script API lint
                            against P:\scripts), Convert-Textures.ps1 (ImageToPAA)
server/templates/           serverDZ.diag.cfg / serverDZ.dedicated.cfg templates (placeholders only)
server/{profiles,mpmissions,serverDZ.*.cfg}   generated, git-ignored
build/                      output: build/@<Mod>/{addons/*.pbo,*.bisign,keys/*.bikey,mod.cpp} (git-ignored)
.claude/agents/             specialist subagents (see below)
```

Machine-specific paths go in `workspace.config.json` (git-ignored, copy of
`workspace.config.example.json`). Empty paths are auto-detected from Steam
(DayZ 221100, DayZ Tools 830640, DayZ Server 223350).

## Commands (run from repo root in PowerShell)

| Task | Command |
|---|---|
| Toolchain status | `tools\setup\Get-ToolchainStatus.ps1` |
| Install missing tools (asks each time) | `tools\setup\Install-Toolchain.ps1 [-Only DayZServer,...]` |
| Mount P: + extract game data | `tools\setup\Initialize-WorkDrive.ps1 [-Force after game update]` |
| Create signing key (outside repo) | `tools\setup\New-SigningKey.ps1 -KeyName <TAG>` |
| Prepare local server | `tools\setup\Initialize-TestServer.ps1` |
| Smoke test (no mod) | `tools\setup\Test-Toolchain.ps1` |
| Offline self-test of scripts | `tools\tests\Invoke-SelfTest.ps1` |
| New empty mod | `tools\build\New-Mod.ps1 -ModName <Mod>` |
| Pack | `tools\build\Build-Mod.ps1 -ModName <Mod> [-Packer pboproject] [-DryRun]` |
| Sign | `tools\build\Sign-Mod.ps1 -ModName <Mod>` |
| Deploy to dedicated server | `tools\build\Deploy-Mod.ps1 -ModName <Mod>[,<Mod2>]` |
| Build + diag server + client | `tools\build\Build-And-Run.ps1 -ModName <Mod> [-ServerModName <Srv>] -FilePatching` |
| Build + dedicated (signed) | `tools\build\Build-And-Run.ps1 -ModName <Mod> -Mode Dedicated` |
| Launch only | `tools\launch\Start-DiagLocal.ps1 -Mods <Mod>` / `tools\launch\Start-DedicatedServer.ps1 -Mods <Mod> -ServerMods <Srv>` |

Every build/launch script accepts `-DryRun` (prints the exact tool command lines).
If execution policy blocks scripts: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

Build rules: PBO folders containing `.p3d/.rtm/.wrp` are binarized through `P:\`
(the script junctions `P:\<Mod>` -> `mods\<Mod>\addons`); everything else is
`-packonly`. PBO names are lower-cased. `-filePatching` (diag only) junctions
`<DayZ>\<Mod>` -> `mods\<Mod>\addons` so `.c` edits apply on reconnect; config.cpp
edits always need a rebuild.

Logs: `server\profiles\{diag-server,diag-client,dedicated}\` (`script_*.log`, `*.RPT`, `*.ADM`).

## Conventions

- Never edit vanilla: `P:\scripts`, `P:\DZ`, the game/server install, or `server\mpmissions` (a vanilla copy). Extend with `modded class` and config inheritance.
- Verify APIs and signatures against `P:\scripts` before using them; cite file:line in summaries.
- Script layering: 3_Game -> 4_World -> 5_Mission; lower layers can't reference higher ones.
- Prefix every new class, RPC id, config class and file with the mod tag.
- `CfgPatches.requiredAddons[]` lists every addon you modify or inherit from.
- Lowercase `addons\`, `keys\`, PBO and asset file names (Linux servers are case-sensitive).
- Binary assets go through Git LFS (`.gitattributes`); generator scripts live next to them in `mods/<Mod>/assets/`.
  Generated outputs (configs, CE files, P3Ds) are committed; regenerate instead of hand-editing (`--check` flags stale files).
- No Paths LOD: DayZ AI uses the runtime navmesh (objectSpawnersArr spawns with ECE_UPDATEPATHGRAPH).
- Prefer vanilla user actions over custom RPCs: the server re-runs ActionCondition; re-validate in the server entry point.
- Never put `*/` inside a `/* */` comment in Enforce Script (e.g. `storage_*/export`) - it ends the comment.
- Windows scripts use CRLF; keep PowerShell 5.1-compatible syntax (no `??`, ternary, `&&`), and use `Join-DzPath` (Join-Path throws when P: is not mounted).
- Do not create mods, items or gameplay code unless the user asks for it.

## Security rules

- The client is hostile. Every server-side RPC/action handler validates: sender identity (from `PlayerIdentity`, not payload), permissions (server-side list), target existence/type, distance, input bounds, and rate limits. Clients never decide outcomes.
- Never let client strings choose class names to spawn, file paths, or log formats.
- Private keys (`*.biprivatekey`) live in `signing.keyDir` outside the repo; scripts refuse in-repo keys. Never commit keys, `.bisign`, `.pbo`, `workspace.config.json`, rendered server configs or passwords. `.githooks/pre-commit` enforces this (`git config core.hooksPath .githooks`).
- Release-like testing uses the dedicated config: `verifySignatures = 2`, `BattlEye = 1`, `allowFilePatching = 0`. Debug/diag code paths must not ship enabled.

## Performance rules

- No heavy work in `OnUpdate`/`EOnFrame`/short repeating `CallLater`; prefer events and throttled timers. No allocations, string formatting or logging per frame.
- Bound every collection; remove `CallLater`/`ScriptInvoker` registrations on entity deletion.
- Minimise net sync: few `RegisterNetSyncVariable*`, `SetSynchDirty()` only on real change, targeted RPCs with small payloads (ids, not objects/strings).
- Assets: full LOD chain, power-of-two textures sized to on-screen size, correct suffixes (`_co _ca _nohq _smdi _as`).

## Subagents (`.claude/agents/`)

| Agent | Use for | Tools |
|---|---|---|
| `enforce-coder` | Enforce Script + config.cpp, modded classes, RPC | Read/Grep/Glob/Edit/Write |
| `perf-engineer` | server FPS / client cost review (read-only) | Read/Grep/Glob |
| `security-auditor` | RPC & client->server audit, key/secret hygiene, BattlEye (read-only) | Read/Grep/Glob/Bash |
| `asset-pipeline` | Blender Python, Pillow textures, PAA, model.cfg, rvmat | Read/Grep/Glob/Edit/Write/Bash |
| `economy-designer` | types.xml, cfgspawnabletypes, cfgeventspawns, balance | Read/Grep/Glob/Edit/Write |
| `qa-tester` | build, run, read logs, test checklists | Read/Grep/Glob/Bash/Write |

Typical flow: enforce-coder / asset-pipeline / economy-designer implement ->
perf-engineer + security-auditor review -> qa-tester builds, runs and checks logs.
