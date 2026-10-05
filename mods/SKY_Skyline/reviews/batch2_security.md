# Batch 2 security gate (security-auditor)

Security gate for SKY_Skyline batch 2 (HEAD 69b1866, "WIP batch 2: decals, windows, brick and concrete panel facades")

The batch has no blocking issues. It adds no scripts and no RPCs, nothing in it gives clients an action or inventory access, and no keys or secrets are committed. The four checks are below, then findings by severity.

**Check 1: client-to-server paths and config entries**
- `/home/user/DayZModding/mods/SKY_Skyline/addons/sky_street/config.cpp:164-199` adds 7 classes: Land_SKY_Decal_Dirt, Land_SKY_Decal_Cracks, Land_SKY_Decal_Graffiti and its A/B/C/D variants.
  - They all inherit `Land_SKY_Street_Base : HouseNoDestruct` (scope 0, lines 15-19) and are `scope = 1`.
  - None of them has `UserActions`, inventory or cargo, attachments, or damage/destruction entries. The only things set are `hiddenSelections[] = {"camo"}` and a fixed, mod-prefixed `hiddenSelectionsTextures` path.
  - The texture is chosen by the config class name. No client value can choose a texture or a class.
- `model.cfg:43-48` only adds `sections[] = {"camo"}`.
- The decals are not in `economy/` or `placement/` yet, so they cannot spawn as loot.
- No `.c` files changed.

**Check 2: artwork content** (`assets/textures/gen_textures.py` `decals()` 420-462, `windows()` 465-485, `brick()` 488-522, `concpanel()` 525-547; I also looked at `reviews/img/textures_batch2.png`)
- Graffiti: the only words are "SKY", "NO CURFEW", "ZONE 7" and "RUN". They are drawn in Pillow's built-in default font (`_font()`, line 336) over 5 randomly placed solid ellipses with a noise-masked alpha.
  - There are no logos, brand marks, gang tags, hate symbols, flags or extremist references.
  - "NO CURFEW" is a generic, invented protest line that fits the setting. It is not tied to any real movement or party.
- Cracks are random-walk polylines and dirt is noise streaks.
- Windows are flat rectangles with furniture/blind silhouettes and no readable content. Brick and concrete panel are procedural.
- No external images or fonts are imported, so there is no third-party artwork or licensing issue.

**Check 3: render-only decals with no Geometry (exploit analysis)**
`build_kit.build_decal` (`assets/blender/build_kit.py:454-461`) makes a single-sided quad in res0, res1 and res2 only. There are no Geometry, View Geometry, Fire Geometry or Roadway LODs.
- **Hiding players or loot:** this is not possible when a decal sits 1 cm in front of a solid wall as designed. There is no room behind it. Loot uses building proxies, not these objects.
- **Seeing through walls / z-fighting:** this cannot show anything through a wall. At worst the decal flickers against the wall face at long range; the wall still renders and still blocks view and bullets.
- **Residual risk (Low, not blocking):** a decal placed free-standing or out in the open would act as a one-way screen.
  - Because the quad is single-sided, the side facing the wall is not drawn. Someone standing on that side can see straight through it.
  - Someone on the front side sees an opaque 2 x 2 m picture, but it has no View or Fire Geometry. Bullets and the AI's line of sight pass through it.
  - The result is concealment that favours one side, or a soft spot to hide in a corridor.
  - Fix: make the placement survey (layout.yaml -> objectSpawnersArr validation) reject any `Decal_*` entry that is not within about 2-5 cm of a surface backed by Geometry, with the normal facing away from it. Add this before decals go into `placement/`.
  - Note that admin tools can also spawn these scope-1 objects. That only matters for servers that give out free spawn rights, and it is the same as any vanilla static.
- PENDING_VERIFICATION item B1 (does a HouseNoDestruct P3D with no Geometry spawn?) is a functional question, not a security one. If a fallback Geometry is added, keep it tiny and below ground as described there. It must not become a thin wall-sized slab: a slab overlapping the parent wall could let players clip into the wall.

**Check 4: key and secret hygiene**
- The commit touches 24 files: text, rvmats, Python, and LFS pointers for 3 P3Ds and 1 PNG. I checked that they are real pointers.
- There are no `*.biprivatekey`, `*.bisign`, `*.bikey`, `*.pbo`, `workspace.config.json`, rendered `server/serverDZ.*.cfg` files, passwords, tokens or webhooks. I checked `git ls-files`, a grep of the diff, and the full history with `git log --all --diff-filter=A`.
- `git config core.hooksPath` is `.githooks`.
  - `/home/user/DayZModding/.githooks/pre-commit` blocks keys, `.bisign`, `.bikey`, `.pbo`, `.ebo`, `_handoff/*`, `*.bundle`, `workspace.config.json`, `server/serverDZ.*.cfg`, and admin/RCon password lines.
  - `.gitignore` covers the same set; `/_handoff/` is at line 45.
- `/home/user/DayZModding/_handoff/` is git-ignored (`git status --ignored` shows `!! _handoff/`). The contents of `batch1/`:
  - `HANDOFF.txt` has only the branch, commit and restore instructions.
  - The zip has 113 entries and none match key, sign, pbo, config or secret patterns.
  - The `.bundle` head is f73d587, which is already in the history of HEAD and already checked clean.
  - These files are meant to be shared, so the existing ignore rule plus the hook is the right coverage.

## Findings

**Critical / High / Medium:** none.

**Low**
- **L1:** decals are single-sided, render-only quads with no View or Fire Geometry. If placed away from a wall they give one-sided concealment (`build_kit.py:454-461`, `skyspec.py:322-329`).
  - Fix: a placement-survey rule that every `Decal_*` must sit flush (2-5 cm or less) against a surface with Geometry, with its normal pointing away from that surface.
  - Optionally, keep the decal classes out of admin/trader spawn lists.

**Info**
- **I1:** the word "SKY" is the mod tag in a generic font, so there is no brand-mark problem.
- **I2:** cosmetic, not security. In the preview, "NO CURFEW" (variant b) is cut off at the right edge of the 512 tile, and the noise alpha eats into letters in "SKY" and "RUN". The cause is the font-size formula at `gen_textures.py:457`. Pass this to asset-pipeline.
- **I3:** BattlEye impact is none. There is no script and no network traffic, and nothing requires `-filePatching`.

GATE: PASS
