# Manual steps (cannot be automated here)

Everything from geometry to MLOD P3D is scripted (`assets/blender/build_towera.py`, Arma Toolbox
export, headless). Most steps below are **verification** in Bohemia's tools on Windows. Menu names
follow DayZ Tools' Object Builder; if a label differs in your build, the dialog names in brackets
are what to look for.

## A. Object Builder: check each tower P3D (once per model change)
For each of `sky_towera_lobby.p3d`, `sky_towera_floor_office.p3d`, `sky_towera_core.p3d`,
`sky_towera_roof_helipad.p3d` and `sky_items/sky_keycard.p3d` (open from `P:\SKY_Skyline\...`;
Build-Mod links `P:\SKY_Skyline` to `mods\SKY_Skyline\addons`):

1. **File > Open**, pick the P3D. The LOD list (right panel) must show Resolution 0.000 to 3.000,
   ShadowVolume 0.000, Geometry, Memory, Roadway, View Geometry and Fire Geometry.
2. Select the **Geometry** LOD. **Structure > Topology > Find Components**. The ComponentNN
   count must not change; the generator already wrote one per convex box.
3. Still in Geometry: **Structure > Convexity > Find Non-Convexities**. Expect "0 non-convex".
   Repeat in **Fire Geometry** and **View Geometry**.
4. Geometry: **Window > Named Properties**. Confirm `class=house`, `map=building`, `autocenter=0`.
   Then **Tools > Mass** (the Mass dialog) and confirm the total (lobby 60000, floor 40000, roof 30000, core 120000).
5. **ShadowVolume 0.000**: **Structure > Topology > Close Topology** (or the "check closed" tool). Expect no
   open edges. The boxes are generated closed with shared vertices.
6. **Memory**: confirm the points exist:
   - core: `elev_door_lN_a/b_axis` (2 points each), `elev_panel_lN`, `elev_call_lN`, `elev_cab_lN`
   - lobby: `door_sec`, `door_sec_action`, `door_sec_axis` (2 points)
7. Resolution 0: **Window > Named Selections**. Selecting `door_sec` (lobby) or `elev_door_l3_a` (core)
   must highlight only the door leaf.
8. Optional: **File > Save** in Object Builder re-saves the MLOD in Bohemia's own writer. This is harmless and
   normalises the file if Binarize ever complains about the Arma Toolbox output.

## B. Binarize / pack (scripted, but read the logs)
`tools\build\Build-Mod.ps1 -ModName SKY_Skyline` binarizes `sky_towera` and `sky_items` (they
contain P3Ds) through P:. Then open `DayZ Tools\Bin\Logs\AddonBuilder*.rpt` and the Binarize output. Look for:
- "non-convex" or "component" warnings
- missing textures (`.paa` not generated: run `assets\Build-SkyAssets.ps1` first)
- unknown penetration rvmats (`skyspec.PENETRATION`; `concrete.rvmat` and `glass.rvmat` are unverified)

## C. In-game checks that need a human
See `TESTING.md`. In particular the door swing direction. If `door_sec` opens outward or into the wall,
flip `angle1` to `-1.4` in `assets/gen_configs.py` (model.cfg `Door_Sec`) and rebuild. If the elevator leaves
slide the wrong way, swap the axis point order in `build_towera.py`.
