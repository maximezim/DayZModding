# Batch 2 perf gate (perf-engineer)

## SKY_Skyline batch 2 (textures and decals): static perf gate

I made no in-game measurements, and P:\scripts and P:\DZ are not reachable from this Linux container, so I could not compare against vanilla. Anything marked "verify on P:" is unconfirmed. I had no Bash, so I worked from the files you listed rather than `git show`.

**No server-script changes are in this batch.** The decals are `HouseNoDestruct` objects with no Geometry, Fire Geometry or View Geometry (`addons/sky_street/config.cpp:16`, `:164-199`). Server cost is entity count only (M3).

### Whole SKY texture set: VRAM estimate (full mips, x1.33)
Format assumptions: `_co` and `_as` are DXT1. `_ca`, `_nohq` and `_smdi` are DXT5. So a 2048 map is 2.67 MB as DXT1 or 5.33 MB as DXT5, and a 1024 map is 0.67 or 1.33 MB.

| Group | MB |
|---|---|
| Tower A materials (concrete, metal, tile, carpet, wallpaper, glass, glassfar, roofmark, asphalt, keycards) | ~75 |
| Batch 1 kit (paver, atlas, billboards, roadmark, rust, foliage) | ~16.4 |
| **Batch 2:** brick 10.75 + concpanel 10.75 + decals 4.0 + windows 2.67 | **~28.2** |
| **Total** | **~120 MB** |

- The 11 normal maps (`_nohq`) at 2048 DXT5 take about 59 MB, roughly half the set.
- Batch 2 adds about 31 % on top of the ~92 MB from earlier batches.
- The ~120 MB is a skyline-wide resident-set figure. The 80 MB budget in `reviews/perf_review.md:145` was per tower.
- With the fixes below, batch 2 drops to about 18 MB (whole set about 110 MB).

### High
None.

### Medium

**M1. New information-free 2048 AO maps repeat the batch-1 M5 problem.**
- Where: `assets/textures/gen_textures.py:534` (`sky_brick_as`) and `:558` (`sky_concpanel_as`), referenced in `addons/sky_textures/data/sky_brick.rvmat:48` and `sky_concpanel.rvmat:48`.
- Brick AO only darkens the mortar rows to 0.96, a 4 % change. Concpanel AO only darkens the joints to 0.90. Both PNGs are 16 KB, which confirms there is almost no content.
- Cost: 2 x 2.67 MB of VRAM, one extra 2048 texture fetch per pixel on what will be the largest surfaces in the city, and PBO size.
- Fix:
  - Add `"as"` to `PROCEDURAL_MAPS` for `sky_brick` and `sky_concpanel` (`assets/gen_configs.py:45-50`).
  - The joint and mortar darkening is already in `_co` (`col[p:p+j] *= 0.6` for concpanel, mortar colour for brick). Fold any remaining AO into `_co`, then stop generating both `_as` files.
- While you are there, also add `"smdi"` for both. `sky_brick_smdi` and `sky_concpanel_smdi` are constant 256 files (`:533`, `:557`). The cost is trivial, but it is one less file and fetch, and matches the decals and windows.

**M2. The dirt decal is alpha-blended and is the intended way to cover large wall areas.**
- Where: `addons/sky_textures/data/sky_decal_dirt.rvmat` has no `renderFlags`, so it is blended. `sky_decal_dirt` is not in `ALPHA_TEST` (`assets/gen_configs.py:92`). Model: `assets/blender/build_kit.py:474`.
- Each 2 x 3 m dirt instance is its own entity and its own draw call in the transparent pass. That pass is sorted, has no depth write, and runs the full Super shader (fresnel + env map, Stage6/7).
- Grime across a facade means many instances: one 30 x 9 m facade needs about 15. With view distance, that becomes hundreds of sorted, blended draws, and overlapping instances each re-shade the same pixels.
- Two other risks:
  - Every decal sits on the same 1 cm offset plane (`skyspec.py:323`). Overlapping decals are coplanar and will z-fight.
  - 1 cm is below the 1.5 cm lift adopted for roadmarks in batch 1 (M2), so flicker at range is likely.
- Fix, in order of preference:
  1. Do large-area grime through the Super shader's macro stage on the facade materials instead of decal objects. Stage3 is currently a neutral `color(0,0,0,0,MC)` in `sky_brick`, `sky_concpanel` and `sky_concrete`. A 512-1024 `_mc` grime map with low-frequency streaks costs no extra draw calls, no blending and no entities. Verify on P: which vanilla building rvmats use `_mc` in Stage3, and copy that.
  2. Keep `Decal_Dirt` for hand-placed accents only, and enforce caps in the batch-5 layout generator: at most N per facade, no overlap, and different offsets per decal type (dirt 1.5 cm, cracks 2.0 cm, graffiti 2.5 cm).
  3. Size `sky_decal_dirt_ca` at 512 x 1024 (W x H) to match the 2 x 3 m aspect. That is 256 px/m on soft fbm content (currently 512 x 341 px/m, stretched) and saves about 0.67 MB.

**M3. Every decal instance is a separate entity: replicated, and a draw call that cannot be merged.**
- Where: `addons/sky_street/config.cpp:164-199`. Placement goes through `objectSpawnersArr`, as noted in batch 1 L9.
- Each decal costs the server one entity: no physics, but it counts towards entity count and join and bubble sync, if objectSpawnersArr entities replicate (verify on P:, `3_Game` object spawner).
- On the client, each costs one object, one draw call and one LOD selection.
- The four graffiti variants use `hiddenSelectionsTextures` (`:181-198`), so instances of different variants cannot share a material or batch.
- Fix:
  - For decals that repeat on a module (for example the dirt band under every window row), bake them into the facade or module P3D as an extra alpha-tested section. That makes them part of the building draw, with no separate entity.
  - For stand-alone decals, add a per-tile and per-block cap to the layout generator (`placement/layout.yaml` rules, batch 5), alongside the light-density cap from batch 1. My proposal, as a hypothesis: no more than 6 decal entities per 12 m street tile, and no more than 40 per 100 m block.
  - Optionally replace the 4 graffiti textures with one 1024 2 x 2 atlas (same 1.33 MB). Make the variants UV-offset models, or keep one model with per-variant UVs. All graffiti then share one material. This would also match the docstring, which says "graffiti atlas (2 x 2)" at `gen_textures.py:421`, while the code writes 4 files.

### Low

- **L1. Window atlas is 2048 for flat content** (`gen_textures.py:477-498`, 23 KB PNG; `sky_windows_co` 2.67 MB). The cells are 512 px of flat rectangles and blinds on a 10 px pitch.
  - Fix: at 1024, a cell is 256 px. That still holds the blinds (5 px pitch) and keeps about 170 px/m on a 1.5 m window. It saves 2 MB.
  - Better: use this atlas as the opaque far-facade material (the H2 "glassfar" idea) so Res1+ facades need neither alpha glass nor a second section. It could absorb `sky_glassfar` (256) as one band.
- **L2. Lit windows: the cost is in the sections, not the emissive term.** `emmisive[]` in `sky_windows_lit.rvmat:5` is a constant on the same Super shader, so it costs nothing extra per pixel and adds no dynamic lights. That is good.
  - Cost appears only if a facade mixes lit and unlit cells as two materials: +1 section per module. That doubles the window draws per tower.
  - Fix: choose lit or unlit per module variant, or per instance through `hiddenSelectionsMaterials`. Never switch by time of day from script; that would be per-frame or timer work on every tower. Note in the manifest that `sky_windows_lit` is never combined with `sky_windows` in one LOD.
  - Visual, to verify in-game: if RV adds the emissive colour without modulating it by the texture, the dark "unlit" cells in the atlas (`:487`, every third cell) will glow too.
- **L3. Brick texel density is undocumented and the code comment does not match it.** At `gen_textures.py:510`, `bh, bw = size//32, size//8` gives 64 x 256 px. At the stated "3 m mapping" (683 px/m) that is a 9.4 x 37.5 cm brick, not 6.5 x 21.5 cm.
  - Real-size bricks need roughly 1.7 m per U tile, which is about 1190 px/m and over the 700 px/m trim budget. Do not get there by shrinking the mapping.
  - Fix: decide the mapping first, then size the bricks in the texture. For 8 bricks across U at 21.5 cm, the sheet is 1.72 m. Either generate 16 bricks across with the sheet at 3.44 m (595 px/m), or accept bigger bricks.
  - Record the mapping in `assets/manifest.yaml`, as wallpaper has at `:109`.
  - No model uses brick, concpanel or windows yet. Re-check density when the facade models land (`manifest.yaml:67`).
- **L4. The concpanel normal map at 2048 is mostly low-frequency.** It has fbm at strength 0.15 plus 8 px joints. A 1024 normal map would keep 4 px joints and save 4 MB (DXT5). The brick normal map should stay at 2048, because its 2 px mortar lines would drop to 1 px at 1024.
- **L5. Alpha-tested decals with thin or noisy alpha lose coverage in the mips.** Cracks (`:437-444`) are 1-3 px lines at 1024. The graffiti mask (`:461` region, `fbm > 0.3`) is speckled.
  - Effect: beyond about 20-30 m they dissolve but are still drawn, so the draw calls buy nothing.
  - Fix: widen the crack lines to 2-4 px, use a lower-frequency graffiti mask, and if the generator allows it, scale mip alpha to preserve coverage. Placement should keep them off long sightlines; they are cheap per pixel because they are alpha-tested.
- **L6. Decal LOD chain is 3 identical 2-tri LODs** (`build_kit.py:457-460`). This is harmless, but Res1 and Res2 buy nothing.
  - If the 3-LOD rule stays, make Res2 of `Decal_Dirt` alpha-tested (a second rvmat with `AlphaTest32`) so dirt leaves the blended pass at range. This is the same principle as H2: no blended draws at far LODs.
- **L7. Decal rvmats run the full Super stack.** `sky_decal_*.rvmat` have env map, fresnel and `specular 0.7` on grime and cracks. The per-pixel cost matches the walls they cover. Lower the specular for looks if you like; check whether vanilla wall decals use a cheaper shader (verify `P:\DZ\structures\...\data\*decal*.rvmat`).
- **Tower A maps still open from the earlier review (rule 1, untouched):**
  - `sky_wallpaper` is still 2048 (an extra 6 MB, if 1024 at 4 m is acceptable).
  - `sky_roofmark_as` and `sky_roofmark_nohq` are flat 1024 maps (2 MB).
  - `sky_metal_smdi` is a 16 KB banded map at 2048: 5.3 MB, which a 256 map with the same band layout would replace.
  - Together that is about 13 MB. Revisit them when Tower A is unfrozen.

### Already fine
- Every size is a power of two (enforced at `gen_textures.py` main).
- Suffixes are correct: `_ca` on all alpha decals, `_co` on the window atlas.
- Decals, windows and billboards use procedural nohq/as/smdi.
- Cracks and graffiti are alpha-tested (`AlphaTest32` in `sky_decal_cracks.rvmat:8`).
- Decals have no collision LODs, so there is no physics or wheel-snag cost.
- The window atlas `_co` is shared between the lit and unlit rvmats.

### Measure it
- After binarizing, check the actual PAA formats in the pboProject or ImageToPAA log, or TexView: `_co` should be DXT1 and `_ca`/`_nohq` DXT5. That confirms or corrects the ~120 MB estimate.
- In DayZDiag (protocol in `reviews/perf_review.md` section 4), add a scenario P7: one facade with 0, 15 and 40 `Decal_Dirt` instances at 10 m and 60 m.
  - Read client frame ms and draw call count from the diag statistics.
  - Watch for z-fighting and flicker at 50-150 m, and for overlap where decals stack.
- Compare the VRAM delta (diag stats or GPU counter) with and without the batch-2 materials on screen.
- Server side: compare the entity count and join time (S6) with N decals in `objectSpawnersArr`.
- Check `server\profiles\diag-server\*.RPT` and `diag-client\*.RPT` for missing-texture or `hiddenSelections` warnings on the graffiti variants.

Relevant files:
- /home/user/DayZModding/mods/SKY_Skyline/assets/textures/gen_textures.py
- /home/user/DayZModding/mods/SKY_Skyline/assets/gen_configs.py
- /home/user/DayZModding/mods/SKY_Skyline/assets/skyspec.py
- /home/user/DayZModding/mods/SKY_Skyline/assets/blender/build_kit.py
- /home/user/DayZModding/mods/SKY_Skyline/addons/sky_street/config.cpp
- /home/user/DayZModding/mods/SKY_Skyline/addons/sky_textures/data/sky_decal_dirt.rvmat
- /home/user/DayZModding/mods/SKY_Skyline/addons/sky_textures/data/sky_windows_lit.rvmat
- /home/user/DayZModding/mods/SKY_Skyline/addons/sky_textures/data/sky_brick.rvmat
- /home/user/DayZModding/mods/SKY_Skyline/addons/sky_textures/data/sky_concpanel.rvmat
- /home/user/DayZModding/mods/SKY_Skyline/reviews/batch2_textures.txt

0 High, 3 Medium, 7 Low.

GATE: PASS (static)
