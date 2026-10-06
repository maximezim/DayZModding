"""Interior renders of the D63 underground kit (Blender, no game needed).

    blender -b --factory-startup -P preview_underground.py -- --out <dir> [--tex <png dir>]

sewer.png: Sewer_Straight + Sewer_Access + Sewer_Junction in a row, camera on a walkway;
metro.png: Metro_Tunnel + Metro_Station + Metro_Tunnel, camera on the platform. Lit only by the kit's
lamps (emissive) plus one point light per lamp position (the in-game lights are script lights, P26).
--variants adds the D67 pieces: sewer_collapsed.png, sewer_floodedend.png, metro_station_c.png.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import bpy  # noqa: E402
import build_underground as U  # noqa: E402
import preview_towera as PT  # noqa: E402
import skyspec as S  # noqa: E402
from skygeo import build_object  # noqa: E402

UG = S.UNDERGROUND


def place(name, y, cache):
    lods = U.BUILDERS[name]()
    res0 = [l for l in lods if l.name == "res0"][0]
    obj = build_object(res0, U.KIT_MATS, cache)
    obj.location = (0.0, y, 0.0)
    return res0


def lights(points, energy):
    for i, p in enumerate(points):
        ld = bpy.data.lights.new("l%d" % i, "POINT")
        ld.energy = energy
        ld.color = (0.85, 0.92, 1.0)
        ob = bpy.data.objects.new("l%d" % i, ld)
        ob.location = p
        bpy.context.scene.collection.objects.link(ob)


def shoot(out, tex, pieces, cam, target, light_pts, energy, fname):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    cache = {}
    for name, y in pieces:
        place(name, y, cache)
    PT.shade(tex)
    for m in bpy.data.materials:
        if m.name in S.MATERIALS and m.name not in PT.FLAT and tex:
            stem = S.MATERIALS[m.name]["co"].replace("\\", "/").split("/")[-1].replace(".paa", ".png")
            png = os.path.join(tex, stem)
            if os.path.exists(png):
                m.use_nodes = True
                nt = m.node_tree
                bsdf = nt.nodes.get("Principled BSDF")
                img = nt.nodes.new("ShaderNodeTexImage")
                img.image = bpy.data.images.load(png)
                nt.links.new(img.outputs["Color"], bsdf.inputs["Base Color"])
        if m.name == "decal_graffiti" and m.use_nodes:                     # alpha-blended decal
            nt = m.node_tree
            img = [n for n in nt.nodes if n.type == "TEX_IMAGE"]
            if img:
                nt.links.new(img[0].outputs["Alpha"], nt.nodes.get("Principled BSDF").inputs["Alpha"])
                m.blend_method = "BLEND"
        if m.name in ("lamp_cool", "lamp"):
            m.use_nodes = True
            b = m.node_tree.nodes.get("Principled BSDF")
            b.inputs["Emission Color"].default_value = (0.8, 0.9, 1.0, 1)
            b.inputs["Emission Strength"].default_value = 8
    PT.NIGHT = True
    PT.scene_setup()
    lights(light_pts, energy)
    PT.camera(cam, target, 18)
    bpy.context.scene.render.resolution_x, bpy.context.scene.render.resolution_y = 1280, 720
    PT.render(os.path.join(out, fname))


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    out = argv[argv.index("--out") + 1]
    tex = argv[argv.index("--tex") + 1] if "--tex" in argv else None
    zf = UG["sewer_floor"]
    zc = zf + UG["sewer_height"]
    shoot(out, tex, [("Sewer_Straight", -12.0), ("Sewer_Access", 0.0), ("Sewer_Junction", 12.0)],
          (-1.2, -16.5, zf + 1.65), (0.3, 10.0, zf + 0.6),
          [(0.0, y, zc - 0.3) for y in (-15.0, -9.0, -3.0, 3.0, 12.0)], 60, "sewer.png")
    mf = UG["metro_floor"]
    shoot(out, tex, [("Metro_Tunnel", -18.0), ("Metro_Station", 0.0), ("Metro_Tunnel", 18.0)],
          (2.4, -8.8, mf + 1.0 + 1.7), (-1.0, 8.0, mf + 2.4),
          [(x, y, mf + 5.4) for x in (-1.8, 1.8) for y in (-8.0, -4.0, -0.5)] + [(-4.0, -18.0, mf + 3.5), (0.0, 8.0, mf + 4.0)],
          150, "metro.png")
    if "--variants" in argv:                                                     # D67 variant pieces
        shoot(out, tex, [("Sewer_Straight", -12.0), ("Sewer_Collapsed", 0.0)],
              (-1.2, -16.5, zf + 1.65), (0.3, 6.0, zf + 0.6),
              [(0.0, y, zc - 0.3) for y in (-15.0, -9.0, -3.0)], 60, "sewer_collapsed.png")
        shoot(out, tex, [("Sewer_Straight", -12.0), ("Sewer_FloodedEnd", 0.0)],
              (-1.2, -16.5, zf + 1.65), (0.3, 6.0, zf + 0.6),
              [(0.0, y, zc - 0.3) for y in (-15.0, -9.0, -3.0)], 60, "sewer_floodedend.png")
        shoot(out, tex, [("Metro_Tunnel", -18.0), ("Metro_Station_C", 0.0), ("Metro_Collapsed", 18.0)],
              (2.4, -8.8, mf + 1.0 + 1.7), (-1.0, 8.0, mf + 2.4),
              [(x, y, mf + 5.4) for x in (-1.8, 1.8) for y in (-8.0, -4.0, -0.5)] + [(0.0, 8.0, mf + 4.0)],
              150, "metro_station_c.png")


if __name__ == "__main__":
    main()
