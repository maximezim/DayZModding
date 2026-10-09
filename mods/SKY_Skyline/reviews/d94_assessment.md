# D94 second full assessment (static, no DayZ run)

Scope: everything up to D93 - scripts, configs, economy, tools, the asset pipeline and the docs. Two fresh full-mod audits
(security, performance), a re-review of every fix by both, plus own checks: Windows build / validation wiring, model
sync, repo health, docs consistency, a visual spot check.

## Findings and what was done

| Source | Sev | Finding | Fix |
|---|---|---|---|
| own check | M | `Build-SkyAssets.ps1 -Models` re-exported 5 of the 10 generators (landmarks, street props, underground, creatures, vehicles never) | all ten; and a new gate `assets/check_p3d_sync.py` (in `Invoke-ModValidation`): every committed P3D byte-identical to a fresh export - PASS, 289 / 289, ~1.5 min |
| security | M1 | vanilla actions that target an item (load a magazine from an ammo pile, craft, drain) could still take things out of a guarded kennel (actionbase.c:873 only refuses another player's hierarchy) | modded `ActionBase.Can` refuses targets / parents / held items inside a guarding kennel (the server runs it: actionmanagerserver.c:142) |
| security | M2 | a guarded kennel on a stair landing or in an elevator cab seals what lies beyond (SKY elevator doors are animations, not Doors) | kennels are outdoor only: no placement inside any Building's collision box (object.c:376); courtyards / canopies count as indoors (accepted) |
| security | M3 | search loot outside the CE, persisted at once, no server-wide cap | `ECE_DYNAMIC_PERSISTENCY` (persists once taken, centraleconomy.c:32); 120 + 4 per player finds per hour server-wide and 30 per player (re-review M: one macro could drain the pool) |
| security | L1 | keycards not counted in cargo / hoarders (a stashed T3 respawns) | count_in_cargo / count_in_hoarder 1 (gen_economy) |
| security | L3 | pre-commit hook case-sensitive, password regex narrow | lower-cased names, any quoted password assignment; re-review M: `serverDZ` pattern then needed lower case -> fixed; tested with a staged KEY.BIPRIVATEKEY and a password line |
| security | L4 | tipsy heal endless (sipping beer) | heal budget 0.5 HP per ml of ethanol, max 20, reset when sober |
| security | L5 | one player could keep fetching the elevator car | one fetch per identity per 20 s; re-review L: a refused call no longer cancels the doors' auto-close |
| security | info | survey export radius unclamped | clamped to 2 km |
| perf | M1 | lights created by day too (invisible, but per-frame updates) | director lights at night only (World.IsNight), hypermarkets by day too (generated `SkyLitByDay`); dawn switch-off spread over ticks |
| perf | M2 | kennel inventory gate counted all kennels (the CE always has some) | counts guarding kennels only (server + synced client), early-out for loose items |
| perf | M3 | sewer water animated by the server and by every client | server animates offline only |
| perf | M4 | blended grime decals in Res1 | kept - dropping them pops the run-off band at the Res1 switch; measure in game (P66, one-line fix ready) |
| perf | M5 | Res1 / Res 1.5 sections not budgeted | noted; measure draw calls in diag first |
| perf | L | search action built a type string for every cursor target; bark loop order; LOD-step ratios (Res0 -> Res1 13 % on the department store / hypermarket); Fire density 3x geo | House pre-check; distance first; LOD steps and Fire density left to the FPS protocol (they need in-game numbers) |
| perf re-review | M | the sync gate could inherit `SKY_P3D_BACKEND=atb` from a Build-SkyAssets run in the same shell | forced native writer; Build-SkyAssets clears the variable |
| docs | - | PROGRESS_REPORT counted 83 sign-off rows (84 in TESTING) | corrected |

## Own checks

- **Model sync**: all ten generators re-run into a temp folder: 289 / 289 P3Ds byte-identical to `addons/` (deterministic
  writer, no stale model). Now a gate.
- **Windows wiring**: `Invoke-ModValidation` runs test_kit / test_towera / test_city (with every self-test), ruin cuts,
  slit self-test and the sync gate; `Build-SkyAssets -Models` runs every generator and the long scans.
- **Docs**: D1-D94, P1-P67, TESTING §1-§57 all contiguous, every section has a sign-off row.
- **Repo health**: the LFS working set is 1.6 GB (1.4 GB P3Ds), but every city rebuild re-uploads ~190 changed P3Ds
  (~1.3 GB); the local LFS store is 15 GB and GitHub bills LFS storage for every version. Not changed here (CLAUDE.md:
  generated outputs are committed) - a decision for you: e.g. commit P3Ds only at releases and let
  `Build-SkyAssets -Models` regenerate them (byte-identical, now proven by the sync gate).
- **Visual**: a street-prop contact sheet (wrecks, bus stop, barrier, dumpster, hydrant, bins, ad column, phone booth,
  street / traffic lights) - nothing broken.

## Gates

| Gate | Result |
|---|---|
| `enscript_xref.py` | OK, 26 files |
| `Invoke-SelfTest.ps1` | all self-tests passed |
| `check_p3d_sync.py` | PASS (289) |
| `check_assets.py` | 289 checked, 0 fail, 0 warnings |
| `--check` generators (configs incl. the generated SKY_CityLit.c, manifest, progress, economy, terrain) | all up to date |
| geometry tests / scans | not re-run: no model changed (sync gate) |
