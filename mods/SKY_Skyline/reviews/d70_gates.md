# D70 gates (static, no DayZ run)

| Gate | Command | Result |
|---|---|---|
| Kit geometry + wiring | `python assets/blender/test_kit.py` | PASS (276 assets); the booth counter collision keeps to the 4 x 3 footprint |
| Asset budgets | `python assets/check_assets.py` | 286 checked, 0 fail, 0 over: booth 1028 -> 432 -> 84 -> 10 (5 sections; metal parts moved to the fair trim), stand 5560 -> 682 -> 168 -> 22, kennel 986 -> 248 -> 44 (item budget 1200) |
| Generated files | `gen_manifest / gen_configs --check` | up to date |
| City / layout / terrain / economy / scripts / PowerShell | not affected (landmark + item models only) | re-run with D71 |

## Reviews

- **security-auditor**: Medium: the first stand Res1 drew solid 3 m seat blocks over missing-seat gaps (one-way concealment for prone players) -> runs break at every missing seat, no backrests in Res1. Low: the booth counter top was visual only (items sink into it) -> it collides now. Kennel Geometry/View/Fire unchanged, nothing narrows the door or blocks the storage.
- **perf-engineer**: Medium: booth Res1 was 18 % of Res0 -> shelves, toys, valance, stripes, battens and a bulb strip in Res1 (42 %). Medium: stand Res1 colours differed from Res0 -> each run takes its first seat's colour. Low: kennel Res1 25 % -> bowl and name board added, rest accepted (DECISIONS D70). No new sections; server cost zero.
- Found in the render pass: the awning valance rendered black (winding) -> wound counter-clockwise from the front.

Renders: `img/d70_booth_before.png` / `img/d70_booth_after.png`, `img/d70_kennel_before.png` / `img/d70_kennel_after.png`, `img/d70_stand.png`.
