# Local test server

Everything here except `templates/` is generated and git-ignored.

| Path | What | Created by |
|---|---|---|
| `templates/serverDZ.diag.cfg` | DayZDiag listen server (no signatures, no BattlEye, file patching on) | committed |
| `templates/serverDZ.dedicated.cfg` | Dedicated server, production-like (verifySignatures=2, BattlEye=1) | committed |
| `serverDZ.diag.cfg`, `serverDZ.dedicated.cfg` | Rendered configs with a random admin password | `tools/setup/Initialize-TestServer.ps1` |
| `mpmissions/<mission>/` | Copy of the **vanilla** mission from the DayZ Server install (not committed: Bohemia content) | `Initialize-TestServer.ps1` |
| `profiles/diag-server`, `profiles/diag-client`, `profiles/dedicated` | Logs: `script_*.log`, `*.RPT`, `*.ADM`, crash dumps | the game at runtime |

The diag server uses `-mission=<repo>\server\mpmissions\<mission>`; the dedicated
server uses its own `<serverDir>\mpmissions\<mission>` selected by `template=`.
Reset a mission's persistence by deleting `mpmissions/<mission>/storage_1`.
