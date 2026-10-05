"""Render review images of the stacked Tower A (Res0 LODs) - no game needed.

    blender -b --factory-startup -P preview_towera.py -- --out <dir> [--tex <png dir>]

Produces: exterior.png (3/4 view), section.png (cut through the core),
lobby.png (inside the podium looking at the security room). Materials use the
generated PNG textures when --tex is given, flat colours otherwise.
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import bpy  # noqa: E402
import build_towera as T  # noqa: E402
import skyspec as S  # noqa: E402
from skygeo import build_object  # noqa: E402

FLAT = {"concrete": (0.55, 0.55, 0.53, 1), "glass": (0.3, 0.4, 0.45, 0.35), "metal": (0.6, 0.6, 0.62, 1),
        "tile": (0.72, 0.71, 0.68, 1), "carpet": (0.3, 0.33, 0.37, 1), "wall": (0.8, 0.78, 0.73, 1),
        "roofmark": (0.85, 0.7, 0.2, 1)}


def shade(tex_dir):
    for m in bpy.data.materials:
        key = m.name
        if key not in FLAT:
            continue
        m.use_nodes = True
        nt = m.node_tree
        bsdf = nt.nodes.get("Principled BSDF")
        bsdf.inputs["Base Color"].default_value = FLAT[key]
        png = None
        if tex_dir:
            stem = os.path.basename(S.MATERIALS[key]["co"]).replace(".paa", ".png")
            cand = os.path.join(tex_dir, stem)
            png = cand if os.path.exists(cand) else None
        if png:
            img = nt.nodes.new("ShaderNodeTexImage")
            img.image = bpy.data.images.load(png)
            nt.links.new(img.outputs["Color"], bsdf.inputs["Base Color"])
            if key in ("glass", "roofmark"):
                nt.links.new(img.outputs["Alpha"], bsdf.inputs["Alpha"])
        if key == "glass":
            bsdf.inputs["Alpha"].default_value = 0.35
            bsdf.inputs["Roughness"].default_value = 0.05
        m.blend_method = "BLEND" if key in ("glass", "roofmark") else "OPAQUE"


def stack(section_cut=None):
    cache = {}
    mats = T.MATS
    parts = []
    builders = {"lobby": T.build_lobby, "floor": T.build_floor_office, "roof": T.build_roof_helipad}
    for kind, _suffix, z in S.tower_levels():
        res0 = [l for l in builders[kind]() if l.name == "res0"][0]
        parts.append((res0, z))
    parts.append(([l for l in T.build_core() if l.name == "res0"][0], 0.0))
    for lod, z in parts:
        if section_cut is not None:
            keep = []
            for f in lod.faces:
                xs = [lod.verts[i][0] for i in f[0]]
                if min(xs) < section_cut:
                    keep.append(f)
            lod.faces = keep
        obj = build_object(lod, mats, cache)
        obj.location.z = z
    return cache


def camera(loc, target, lens=28):
    cam = bpy.data.cameras.new("cam")
    cam.lens = lens
    ob = bpy.data.objects.new("cam", cam)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = loc
    d = [target[i] - loc[i] for i in range(3)]
    ob.rotation_euler = (math.atan2(math.hypot(d[0], d[1]), -d[2]), 0, math.atan2(d[1], d[0]) - math.pi / 2)
    bpy.context.scene.camera = ob


def scene_setup():
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 24
    sc.render.resolution_x, sc.render.resolution_y = 960, 640
    world = bpy.data.worlds.new("w")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.62, 0.72, 0.85, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.8
    sc.world = world
    sun = bpy.data.lights.new("sun", "SUN")
    sun.energy = 3.5
    so = bpy.data.objects.new("sun", sun)
    so.rotation_euler = (math.radians(50), math.radians(10), math.radians(35))
    sc.collection.objects.link(so)
    bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, -0.31))


def render(path):
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    only = argv[argv.index("--only") + 1].split(",") if "--only" in argv else None
    out = argv[argv.index("--out") + 1]
    tex = argv[argv.index("--tex") + 1] if "--tex" in argv else None
    os.makedirs(out, exist_ok=True)
    shots = [
        ("exterior", None, (-38, -46, 22), (0, 0, 13), 30),
        ("section", 0.05, (26, -3, 14), (0, 0, 12), 24),
        ("elevator", None, (-1.5, 9.5, 1.8), (0.2, 4.5, 1.2), 22),
        ("floor3_core", None, (-2.5, 10.5, 15.7), (0.0, 0.0, 15.0), 18),
        ("lobby", None, (-9, -9.5, 1.7), (8, 8, 1.5), 20),
    ]
    for name, cut, loc, tgt, lens in shots:
        if only and name not in only:
            continue
        bpy.ops.wm.read_factory_settings(use_empty=True)
        from skygeo import load_arma_toolbox
        load_arma_toolbox()
        stack(cut)
        shade(tex)
        scene_setup()
        camera(loc, tgt, lens)
        render(os.path.join(out, name + ".png"))
        print("RENDERED", name)


if __name__ == "__main__":
    main()
