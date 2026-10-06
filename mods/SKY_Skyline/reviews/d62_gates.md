# D62 gates (static, no DayZ run)

Creatures, decided autonomously: an own, static, server-driven route (DECISIONS D62). Nothing here has run in
DayZ yet; TESTING §27 and P21-P24 have the in-game checks.

| Gate | Command | Result |
|---|---|---|
| Kit geometry | `python assets/blender/test_kit.py` | PASS (244 assets, incl. RatNest and HorseCarcass) |
| Asset budgets | `python assets/check_assets.py` | 254 checked, 0 fail, 0 over (Kennel 734 / 216 / 44 tris) |
| Layout | `python placement/tests/test_sky_layout.py` | 0 failed; landfill park now holds 2 rat nests and the horse carcass |
| Generated files | `gen_configs / gen_manifest / gen_economy --check` | up to date |
| Script API | `tools/assets/enscript_xref.py` | OK, 23 files |
| PowerShell | `tools/tests/Invoke-SelfTest.ps1` | all self-tests passed |

## Reviews (subagents)

**Security** (security-auditor):

| ID | Finding | Fix |
|---|---|---|
| H1 | Shooting or blowing up a kennel ruins it, and vanilla spills its cargo | `SetAllowDamage(false)` while guarding |
| H2 | Stack split / combine (playerbase.c:6309-6370) moves quantity without asking the container | modded `ItemBase.ShouldSplitQuantity` / `CanBeCombined` refuse inside a guarding kennel |
| M1 | Kennels past the registry cap could stay locked | cap raised to 1024; the guard is set on load only for registered, placed kennels; CE counts kennels in cargo and hoarders |
| M2 | A full kennel could be carried off and re-placed (the carrier becomes the owner) | only an empty kennel can be picked up |
| M3 | A bad save block deleted the kennel and its cargo | the kennel loses its owner instead; future last-seen values are clamped |

Kept as accepted: L1 (clients can see the guard state; it is visible by design), L2 (no world-wide cap on search
loot; per-spot cooldown and fail-closed map stay), L3 (strangers can trigger barks, by design), L4 (force-drinking
works like vanilla force-feeding). The review confirmed that clients cannot trigger the siren or bark RPCs.

**Performance** (perf-engineer):
- Gnawing is spread over the 10 min cycle, and dog positions are collected once per nest with one query.
- The city director spawns at most one group per tick, and alarm groups are queued.
- Kennel barks check distance before the identity string.
- One RPC param object per event.
- Search points are cached in model space per type.
- One horde tick constant.

## Render

`img/d62_creatures.png`: the kennel with its dog, the rat nest and the horse carcass (Blender preview).
