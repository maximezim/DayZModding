"""Render a generated layout (placement/out*/sky_objects.json) - the city as sky_layout placed it.

    blender -b --factory-startup -P preview_district.py -- --objects <sky_objects.json> --out <dir> [--tex <png dir>]
        [--shots aerial,street_a,street_b,night]

Every object's Res0 is built once per class (shared mesh) and instanced at its exact JSON
position / yaw (DayZ x, y-up, z -> Blender X, Z, Y; yaw clockwise -> -Z rotation, YAW_SIGN
undone), so the render shows what the spawner / terrain import will place.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import bpy  # noqa: E402
import preview_towera as PT  # noqa: E402
import skyspec as S  # noqa: E402
from build_kit import KIT_MATS  # noqa: E402
from skygeo import build_object, load_arma_toolbox  # noqa: E402


def builders():
    out = {}
    for modname in ("build_kit", "build_props", "build_floors", "build_city"):
        m = __import__(modname)
        for n, (fn, _p, _f) in m.modules().items():
            out[S.KIT[n]["cls"]] = fn
    import build_towera as T
    for key, (fn, _p, fname) in T.MODULES.items():
        for cls, p3d in S.P3D.items():
            if p3d == fname:
                out[cls] = fn
    return out


def dedupe(lod):
    seen, keep = set(), []
    for f in lod.faces:
        k = frozenset(tuple(round(c, 4) for c in lod.verts[i]) for i in f[0])
        if k not in seen:
            seen.add(k)
            keep.append(f)
    lod.faces = keep


def texture_all(tex):
    PT.shade(tex)
    for m in bpy.data.materials:
        key = m.name
        if key in S.MATERIALS and key not in PT.FLAT and tex:
            stem = S.MATERIALS[key]["co"].replace("\\", "/").split("/")[-1].replace(".paa", ".png")
            png = os.path.join(tex, stem)
            if os.path.exists(png):
                m.use_nodes = True
                nt = m.node_tree
                bsdf = nt.nodes.get("Principled BSDF")
                img = nt.nodes.new("ShaderNodeTexImage")
                img.image = bpy.data.images.load(png)
                nt.links.new(img.outputs["Color"], bsdf.inputs["Base Color"])
                if key.startswith("decal") or key in ("roadmark",):
                    nt.links.new(img.outputs["Alpha"], bsdf.inputs["Alpha"])
                    m.blend_method = "BLEND"
        if key in PT.EMISSIVE:
            bsdf = m.node_tree.nodes.get("Principled BSDF") if m.use_nodes else None
            if bsdf:
                bsdf.inputs["Emission Color"].default_value = PT.EMISSIVE[key][0]
                bsdf.inputs["Emission Strength"].default_value = PT.EMISSIVE[key][1] * (3.0 if PT.NIGHT else 1.0)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    objs = json.load(open(argv[argv.index("--objects") + 1]))["Objects"]
    out = argv[argv.index("--out") + 1]
    tex = argv[argv.index("--tex") + 1] if "--tex" in argv else None
    shots = (argv[argv.index("--shots") + 1] if "--shots" in argv else "aerial,street_a,street_b,night").split(",")
    # --cams "name=x,y,z,tx,ty,tz,lens;..." overrides / adds camera positions (Blender frame, see above);
    # a shot whose name ends in "_night" renders at night
    cams = {}
    for c in (argv[argv.index("--cams") + 1].split(";") if "--cams" in argv else []):
        n, v = c.split("=")
        f = [float(x) for x in v.split(",")]
        cams[n] = ((f[0], f[1], f[2]), (f[3], f[4], f[5]), f[6])
    os.makedirs(out, exist_ok=True)
    B = builders()
    cx = sum(o["pos"][0] for o in objs) / len(objs)
    cz = sum(o["pos"][2] for o in objs) / len(objs)
    y0 = min(o["pos"][1] for o in objs)
    for shot in shots:
        PT.NIGHT = shot == "night" or shot.endswith("_night")
        bpy.ops.wm.read_factory_settings(use_empty=True)
        load_arma_toolbox()
        cache, protos, mems = {}, {}, {}
        for o in objs:
            cls = o["name"]
            if cls not in B:
                continue
            if cls not in protos:
                lods = B[cls]()
                res0 = [l for l in lods if l.name == "res0"][0]
                dedupe(res0)
                protos[cls] = build_object(res0, KIT_MATS, cache)
                protos[cls].location = (0, 0, -1000)
                mems[cls] = [l for l in lods if l.name == "mem"]
            ob = protos[cls].copy()
            bpy.context.scene.collection.objects.link(ob)
            yaw = o["ypr"][0] * S.YAW_SIGN
            ob.location = (o["pos"][0] - cx, o["pos"][2] - cz, o["pos"][1] - y0)
            ob.rotation_euler = (0.0, 0.0, -math.radians(yaw))
            if PT.NIGHT and cls.endswith("_Intact") and mems[cls]:
                mem = mems[cls][0]
                for n in ("light_1", "light_4"):
                    g = mem.groups.get(n)
                    if not g:
                        continue
                    p = mem.verts[next(iter(g))]
                    a = -math.radians(yaw)
                    lx = p[0] * math.cos(a) - p[1] * math.sin(a)
                    ly = p[0] * math.sin(a) + p[1] * math.cos(a)
                    ld = bpy.data.lights.new(n, "POINT")
                    ld.energy = 300
                    ld.color = (1.0, 0.85, 0.65)
                    lo = bpy.data.objects.new(n, ld)
                    lo.location = (ob.location[0] + lx, ob.location[1] + ly, ob.location[2] + p[2])
                    bpy.context.scene.collection.objects.link(lo)
        texture_all(tex)
        PT.scene_setup()
        sc = bpy.context.scene
        sc.render.resolution_x, sc.render.resolution_y = 1600, 900
        if shot in cams:
            PT.camera(*cams[shot])
        elif shot in ("aerial", "night"):
            PT.camera((-150.0, -170.0, 125.0), (0.0, 5.0, 0.0), 30)
        elif shot == "street_a":
            PT.camera((-30.0, -50.5, 2.2), (30.0, -43.0, 6.0), 22)
        else:
            PT.camera((-49.5, 34.0, 2.0), (-47.5, -30.0, 6.0), 24)
        PT.render(os.path.join(out, "district_%s.png" % shot))
        print("RENDERED", shot)


if __name__ == "__main__":
    main()
