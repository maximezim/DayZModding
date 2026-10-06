"""Render a review contact sheet of kit assets (Res0) - no game needed.

    blender -b --factory-startup -P preview_kit.py -- --out <png> [--only A,B] [--tex <png dir>] [--cols 6]

Builds every requested skyspec.KIT asset with build_kit (and later batch
generators registered in KIT_BUILDERS), lays them out on a grid with labels
and renders one image (Cycles, CPU).
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import bpy  # noqa: E402
import preview_towera as PT  # noqa: E402
import skyspec as S  # noqa: E402
from skygeo import build_object, optional_arma_toolbox  # noqa: E402

KIT_BUILDERS = {}


def register(mod):
    for n, (fn, _pbo, _p3d) in mod.modules().items():
        KIT_BUILDERS[n] = (fn, mod.KIT_MATS)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    out = argv[argv.index("--out") + 1]
    tex = argv[argv.index("--tex") + 1] if "--tex" in argv else None
    cols = int(argv[argv.index("--cols") + 1]) if "--cols" in argv else 6
    optional_arma_toolbox()
    import build_kit
    register(build_kit)
    for extra in ("build_props", "build_floors"):
        try:
            register(__import__(extra))
        except ImportError:
            pass
    names = argv[argv.index("--only") + 1].split(",") if "--only" in argv else list(KIT_BUILDERS)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    cache = {}
    cell = float(argv[argv.index("--cell") + 1]) if "--cell" in argv else 14.0
    for i, n in enumerate(names):
        fn, mats = KIT_BUILDERS[n]
        res0 = [l for l in fn() if l.name == "res0"][0]
        obj = build_object(res0, mats, cache)
        obj.location = ((i % cols) * cell, -(i // cols) * cell, 0.0)
        txt = bpy.data.curves.new(n, "FONT")
        txt.body = n
        txt.size = cell * 0.06
        to = bpy.data.objects.new(n + "_lbl", txt)
        to.location = ((i % cols) * cell - cell * 0.45, -(i // cols) * cell - cell * 0.45, 0.01)
        bpy.context.scene.collection.objects.link(to)
    PT.shade(tex)
    for m in bpy.data.materials:
        if m.name in ("rust", "asphalt", "paver", "atlas", "billboard", "foliage", "roadmark", "lamp", "wood", "fabric",
                      "brick", "concpanel", "windows") and tex:
            m.use_nodes = True
            nt = m.node_tree
            bsdf = nt.nodes.get("Principled BSDF")
            stem = S.MATERIALS[m.name]["co"].replace("\\", "/").split("/")[-1].replace(".paa", ".png")
            png = os.path.join(tex, stem)
            if os.path.exists(png):
                img = nt.nodes.new("ShaderNodeTexImage")
                img.image = bpy.data.images.load(png)
                nt.links.new(img.outputs["Color"], bsdf.inputs["Base Color"])
                if m.name in ("foliage", "roadmark"):
                    nt.links.new(img.outputs["Alpha"], bsdf.inputs["Alpha"])
                    m.blend_method = "BLEND"
            if m.name == "lamp":
                bsdf.inputs["Emission Color"].default_value = (1, 0.9, 0.7, 1)
                bsdf.inputs["Emission Strength"].default_value = 5
    PT.scene_setup()
    rows = math.ceil(len(names) / cols)
    w, h = (cols - 1) * cell, (rows - 1) * cell
    PT.camera((w / 2 - cell * 0.4, -h - cell * 1.6, cell * 1.7 + rows * cell * 0.45), (w / 2, -h / 2, 1.5), 24)
    bpy.context.scene.render.resolution_x, bpy.context.scene.render.resolution_y = 1400, 900
    PT.render(out)
    print("RENDERED", out)


if __name__ == "__main__":
    main()
