"""Render review images of the procedural city buildings (Res0) - no game needed.

    blender -b --factory-startup -P preview_city.py -- --out <dir> [--tex <png dir>] [--only Rowhouse,Police]
        [--shot states|street|interior|roof] [--night] [--lod res1x]   (--lod: render that LOD instead of Res0, D90)
        [--state Damaged]   (interior / roof shots of another ruin state, D92)

states   one image per archetype: intact / damaged / ruined side by side, front 3/4 view
street   all archetypes (one state each, seeded mix) along a street, as a city block would read
interior one image per archetype: ground floor of the intact building, cut open at the front
roof     one image per archetype: the intact roof seen from a neighbouring tower (D89 roof clutter)
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import bpy  # noqa: E402
import build_city as C  # noqa: E402
import preview_towera as PT  # noqa: E402
import skyspec as S  # noqa: E402
from build_kit import KIT_MATS  # noqa: E402
from skygeo import build_object, optional_arma_toolbox  # noqa: E402


def place(name, x, y, cache, cut_front=None):
    lods = C.BUILDERS[name]()
    chain = {"res1y": ("res1y", "res1x", "res1"), "res1x": ("res1x", "res1")}.get(LOD_NAME, (LOD_NAME,)) + ("res0",)
    res0 = next(l for n_ in chain for l in lods if l.name == n_)          # missing far LOD: the next nearer one
    seen, keep = set(), []
    for f in res0.faces:
        k = frozenset(tuple(round(c, 4) for c in res0.verts[i]) for i in f[0])
        if k in seen:
            continue
        if cut_front is not None:
            ys = [res0.verts[i][1] for i in f[0]]
            zs = [res0.verts[i][2] for i in f[0]]
            if min(ys) < cut_front or min(zs) > cut_front_z:
                continue
        seen.add(k)
        keep.append(f)
    res0.faces = keep
    obj = build_object(res0, KIT_MATS, cache)
    obj.location = (x, y, 0.0)
    if PT.NIGHT:
        mem = [l for l in lods if l.name == "mem"][0]
        for n in ("light_1", "light_4"):
            g = mem.groups.get(n)
            if g and name.endswith("Intact"):
                p = mem.verts[next(iter(g))]
                ld = bpy.data.lights.new(n, "POINT")
                ld.energy = 350
                ld.color = (1.0, 0.86, 0.66)
                ob = bpy.data.objects.new(n, ld)
                ob.location = (p[0] + x, p[1] + y, p[2])
                bpy.context.scene.collection.objects.link(ob)
    return obj


cut_front_z = 1e9
LOD_NAME = "res0"


def ground_street(width):
    """Asphalt road and a sidewalk strip in front of the buildings (context only)."""
    bpy.ops.mesh.primitive_plane_add(size=1, location=(width / 2, -14.0, -0.28))
    road = bpy.context.active_object
    road.scale = (width + 60, 10, 1)
    m = bpy.data.materials.new("road_prev")
    m.use_nodes = True
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.08, 0.08, 0.085, 1)
    road.data.materials.append(m)
    bpy.ops.mesh.primitive_plane_add(size=1, location=(width / 2, -8.0, -0.12))
    walk = bpy.context.active_object
    walk.scale = (width + 60, 4, 1)
    m2 = bpy.data.materials.new("walk_prev")
    m2.use_nodes = True
    m2.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.42, 0.41, 0.39, 1)
    walk.data.materials.append(m2)


def main():
    global cut_front_z, LOD_NAME
    argv = sys.argv[sys.argv.index("--") + 1:]
    out = argv[argv.index("--out") + 1]
    tex = argv[argv.index("--tex") + 1] if "--tex" in argv else None
    only = argv[argv.index("--only") + 1].split(",") if "--only" in argv else list(S.CITY_ARCHETYPES)
    shot = argv[argv.index("--shot") + 1] if "--shot" in argv else "states"
    PT.NIGHT = "--night" in argv
    LOD_NAME = argv[argv.index("--lod") + 1] if "--lod" in argv else "res0"
    PT.DAYZ = "--dayz" in argv
    os.makedirs(out, exist_ok=True)
    jobs = []
    if shot == "lots":
        jobs = [("RubbleLot", [("City_RubbleLot_%s" % v, i) for i, v in enumerate("ABCD")])]
    elif shot == "pieces":
        jobs = [("Pieces", [("City_WaterTower", 0), ("City_MetroEntrance_A", 1), ("City_MetroEntrance_B", 2)])]
    elif shot == "states":
        jobs = [(a, [("City_%s_%s" % (a, st), i) for i, st in enumerate(S.RUIN_STATES)]) for a in only]
    elif shot == "street":
        names, x = [], 0.0
        for k, a in enumerate(only):
            st = S.RUIN_STATES[[0, 1, 0, 2, 1, 0][k % 6]]
            names.append(("City_%s_%s" % (a, st), k))
        jobs = [("street", names)]
    else:
        st = argv[argv.index("--state") + 1] if "--state" in argv else "Intact"            # D92: interior of any state
        jobs = [(a if st == "Intact" else "%s_%s" % (a, st), [("City_%s_%s" % (a, st), 0)]) for a in only]
    for title, items in jobs:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        optional_arma_toolbox()
        cache = {}
        x = 0.0
        spans = []
        for name, _i in items:
            arch = S.KIT[name]["city"]["archetype"]
            pc = S.KIT[name]["city"].get("piece")
            if pc:
                _k, pw, pd = S.CITY_PIECES[pc]
                A = {"w": pw, "d": pd, "levels": [("piece", 20.0 if pc == "WaterTower" else 3.5)], "blank": ()}
            else:
                A = S.CITY_ARCHETYPES[arch] if arch else {"w": 12.0, "d": 12.0, "levels": [("lot", 4.0)], "blank": ()}
            if A.get("tower"):
                A = dict(A, levels=list(A["levels"]) + [("tower", 20.0)])
            if shot == "street":
                gap = 0.0 if A["blank"] else 4.0
            else:
                gap = 8.0
            cx = x + A["w"] / 2
            if shot == "interior":
                cut_front_z = A["levels"][0][1] - 0.05
                place(name, cx, 0.0, cache, cut_front=-A["d"] / 2 + 0.6)
            else:
                cut_front_z = 1e9
                place(name, cx, A["d"] / 2 - 6.0 if shot == "street" else 0.0, cache)
            spans.append((cx, A))
            x += A["w"] + gap
        PT.shade(tex)
        for m in bpy.data.materials:                            # the city materials are kit materials
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
                    if key.startswith("decal") or key == "vegetation":
                        nt.links.new(img.outputs["Alpha"], bsdf.inputs["Alpha"])
                        m.blend_method = "BLEND"
                        if key == "vegetation":                            # alpha-tested in game (AlphaTest32)
                            m.blend_method = "CLIP"
        PT.scene_setup()
        ground_street(x)
        hmax = max(sum(fh for _u, fh in A["levels"]) for _c, A in spans)
        if shot == "interior":
            cx, A = spans[0]
            PT.camera((cx - A["w"] * 0.15, -A["d"] / 2 - 2.5, 1.7), (cx + A["w"] * 0.1, A["d"] * 0.2, 1.1), 16)
        elif shot == "roof":
            cx, A = spans[0]
            PT.camera((cx - A["w"] * 0.6, -A["d"] * 0.9 - 4.0, hmax + 9.0), (cx, 0.0, hmax), 22)
        elif shot == "street":
            PT.camera((-8.0, -30.0, 14.0), (x * 0.45, 0.0, hmax * 0.35), 24)
            bpy.context.scene.render.resolution_x, bpy.context.scene.render.resolution_y = 1600, 800
        else:
            dist = max(x * 0.62, hmax * 2.4, 30.0)
            PT.camera((x * 0.32, -dist, hmax * 0.8 + 4.0), (x * 0.5 - 4.0, 0.0, hmax * 0.38), 26)
            bpy.context.scene.render.resolution_x, bpy.context.scene.render.resolution_y = 1400, 760
        PT.render(os.path.join(out, "%s_%s%s%s.png" % (title, shot, "_night" if PT.NIGHT else "",
                                                       "" if LOD_NAME == "res0" else "_" + LOD_NAME)))
        print("RENDERED", title)


if __name__ == "__main__":
    main()
