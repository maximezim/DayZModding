# SKY terrain sources (D63, MOD_DEVELOPMENT_GUIDE 4.3 Level 2)

`gen_terrain.py` turns a layout run with `site.target: terrain` into the GIS inputs Terrain Builder imports.
The formats follow Bohemia's DayZ-Samples `Test_Terrain` (`source/gis_input/terrain.asc`, `mask_lco`,
`sat_lco`, `source/layers.cfg`):

```
python mods/SKY_Skyline/placement/sky_layout.py --layout mods/SKY_Skyline/placement/citylife_template.yaml --out mods/SKY_Skyline/placement/out_citylife
python mods/SKY_Skyline/terrain/gen_terrain.py            # writes terrain/out/ (--check in validation)
```

| File | Content |
|---|---|
| `out/heightmap.asc` | 1024 x 1024 m at 1 m. City plateau at 120 m that blends into rolling hills over 90 m. Trenches under every sewer and metro piece (bottom 1.5 m under the piece floor, 0.75 m past its footprint). A dry river valley under every bridge |
| `out/mask_lco.png` | Surface mask, 1 px = 1 m. Concrete under the city, tall grass on the blend, grass and conifer patches outside, gravel in the riverbed |
| `out/sat_lco.png` | Colour map on the same grid |
| `out/layers.cfg` | Layers mapped to the vanilla `DZ\surfaces\data\terrain\*.rvmat` names used by the sample, plus the legend colours |
| `out/objects_terrain.csv` | The layout's objects in terrain coordinates (x + 512, y + 120, z + 512), ready to import |
| `out/terrain.json` | The transform and some stats |

Not done here, because it needs the Windows tools and your go-ahead on the map name and size (P28, TESTING §28):
- the Terrain Builder project;
- the `.wrp` build;
- CfgWorlds;
- the navmesh;
- the mission folder.

Why the underground needs this: objectSpawnersArr places objects on the terrain surface, and a vanilla heightmap
cannot be cut. The cut-and-cover pieces therefore sit in these trenches with their roofs just under street level.
On vanilla maps the hatches stay sealed (D58).
