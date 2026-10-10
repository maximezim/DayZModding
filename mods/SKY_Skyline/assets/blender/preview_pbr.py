"""Physically based preview materials and light (D96, preview only - nothing here is exported).

The older previews put the colour map on a flat material and lit it with a grey sky: walls looked like paper and the
renders hid both the generators' strengths and their faults. This module wires every material the way the game's
"Super" shader reads its rvmat, so a review render is close to what the engine shows:
    colour  _co / _ca (alpha for decals and vegetation)
    normal  Stage1 _nohq (tangent space)
    macro   Stage3 _mc (grime macro, own UV scale, blended by its alpha)
    specular Stage5 _smdi (G = specular, B = gloss) or the procedural colour(...,SMDI) value
and lights the scene with a physical sky and sun (AgX view transform), with the meshes smoothed exactly like the P3D
writer does (p3dwriter.SMOOTH_DEG).

    import preview_pbr as PB
    PB.materials(tex_dir)      # after the objects exist
    PB.scene(sun_elev=32, sun_rot=215, samples=64)
"""
import math
import os
import re

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
ADDONS = os.path.join(os.path.dirname(os.path.dirname(HERE)), "addons")
SMOOTH_DEG = 35.0


def _png(tex_dir, paa):
    stem = paa.replace("\\", "/").split("/")[-1].replace(".paa", ".png")
    p = os.path.join(tex_dir, stem)
    return p if os.path.exists(p) else None


def rvmat_stages(rvmat):
    """{stage number: (texture, (u scale, v scale))} from an rvmat in addons/ (None when not found)."""
    if not rvmat:
        return {}
    path = os.path.join(os.path.dirname(ADDONS), "addons", *rvmat.replace("\\", "/").split("/")[1:])
    if not os.path.exists(path):
        return {}
    txt = open(path).read()
    out = {}
    for m in re.finditer(r"class Stage(\d+)\s*\{(.*?)\n\};", txt, re.S):
        body = m.group(2)
        t = re.search(r'texture\s*=\s*"([^"]*)"', body)
        a = re.search(r"aside\[\]\s*=\s*\{([^,]+),", body)
        u = re.search(r"up\[\]\s*=\s*\{[^,]+,([^,]+),", body)
        out[int(m.group(1))] = (t.group(1) if t else "", (float(a.group(1)) if a else 1.0, float(u.group(1)) if u else 1.0))
    return out


def _img(nt, path, non_color=False):
    n = nt.nodes.new("ShaderNodeTexImage")
    n.image = bpy.data.images.load(path, check_existing=True)
    if non_color:
        n.image.colorspace_settings.name = "Non-Color"
    return n


def materials(tex_dir, materials_spec):
    """Rewire every scene material named after a skyspec material (others are left as they are)."""
    for m in bpy.data.materials:
        key = m.name.split(".")[0]
        info = materials_spec.get(key)
        if not info or not tex_dir:
            continue
        co = info.get("co", "")
        if co.startswith("#"):                                            # procedural colour (lamps): keep
            continue
        png = _png(tex_dir, co)
        if not png:
            continue
        m.use_nodes = True
        nt = m.node_tree
        for n in list(nt.nodes):
            if n.type not in ("OUTPUT_MATERIAL",):
                nt.nodes.remove(n)
        out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
        bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
        nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
        uv = nt.nodes.new("ShaderNodeUVMap")
        col = _img(nt, png)
        nt.links.new(uv.outputs["UV"], col.inputs["Vector"])
        base = col.outputs["Color"]
        alpha_mat = co.endswith("_ca.paa") or key.startswith(("decal", "vegetation", "foliage", "glass"))
        st = rvmat_stages(info.get("rvmat", ""))
        mc = st.get(3, ("", (1, 1)))
        if mc[0].endswith("_mc.paa") and _png(tex_dir, mc[0]):          # grime macro over the colour
            mp = nt.nodes.new("ShaderNodeMapping")
            mp.inputs["Scale"].default_value = (mc[1][0], mc[1][1], 1.0)
            nt.links.new(uv.outputs["UV"], mp.inputs["Vector"])
            mi = _img(nt, _png(tex_dir, mc[0]))
            nt.links.new(mp.outputs["Vector"], mi.inputs["Vector"])
            mix = nt.nodes.new("ShaderNodeMix")
            mix.data_type = "RGBA"
            mix.blend_type = "MULTIPLY"
            nt.links.new(mi.outputs["Alpha"], mix.inputs["Factor"])
            nt.links.new(base, mix.inputs[6])
            nt.links.new(mi.outputs["Color"], mix.inputs[7])
            base = mix.outputs[2]
        nt.links.new(base, bsdf.inputs["Base Color"])
        nohq = st.get(1, ("", 0))[0]
        if nohq.endswith("_nohq.paa") and _png(tex_dir, nohq):
            ni = _img(nt, _png(tex_dir, nohq), non_color=True)
            nt.links.new(uv.outputs["UV"], ni.inputs["Vector"])
            nm = nt.nodes.new("ShaderNodeNormalMap")
            nm.inputs["Strength"].default_value = 1.0
            nt.links.new(ni.outputs["Color"], nm.inputs["Color"])
            nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
        smdi = st.get(5, ("", 0))[0]
        if smdi.endswith("_smdi.paa") and _png(tex_dir, smdi):
            si = _img(nt, _png(tex_dir, smdi), non_color=True)
            nt.links.new(uv.outputs["UV"], si.inputs["Vector"])
            sep = nt.nodes.new("ShaderNodeSeparateColor")
            nt.links.new(si.outputs["Color"], sep.inputs["Color"])
            inv = nt.nodes.new("ShaderNodeMath")
            inv.operation = "SUBTRACT"
            inv.inputs[0].default_value = 1.0
            nt.links.new(sep.outputs["Blue"], inv.inputs[1])
            nt.links.new(inv.outputs["Value"], bsdf.inputs["Roughness"])
            nt.links.new(sep.outputs["Green"], bsdf.inputs["Specular IOR Level"])
        else:
            g = re.search(r"color\(([\d.]+),([\d.]+),([\d.]+)", smdi or "")
            spec, gloss = (float(g.group(2)), float(g.group(3))) if g else (0.1, 0.15)
            bsdf.inputs["Roughness"].default_value = max(0.05, 1.0 - gloss)
            bsdf.inputs["Specular IOR Level"].default_value = min(1.0, spec)
        if key == "glass":
            bsdf.inputs["Roughness"].default_value = 0.03
            bsdf.inputs["Transmission Weight"].default_value = 0.0
        if alpha_mat:
            nt.links.new(col.outputs["Alpha"], bsdf.inputs["Alpha"])
            m.blend_method = "CLIP" if key in ("vegetation", "foliage") else "BLEND"
        if key.startswith("metal") or key.startswith("rust"):
            bsdf.inputs["Metallic"].default_value = 0.35


def smooth(obj):
    """Shade like the P3D writer: smooth across edges under SMOOTH_DEG (only where faces share points)."""
    me = obj.data
    me.shade_smooth()
    if hasattr(me, "set_sharp_from_angle"):
        me.set_sharp_from_angle(angle=math.radians(SMOOTH_DEG))


def scene(sun_elev=32.0, sun_rot=215.0, samples=64, strength=1.0, exposure=-0.6):
    """Physical sky (Nishita) + matching sun, AgX, denoised Cycles."""
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    try:
        sc.view_settings.view_transform = "AgX"
        sc.view_settings.look = "AgX - Medium High Contrast"
    except TypeError:
        pass
    sc.view_settings.exposure = exposure
    world = sc.world or bpy.data.worlds.new("w")
    sc.world = world
    world.use_nodes = True
    nt = world.node_tree
    for n in list(nt.nodes):
        if n.type != "OUTPUT_WORLD":
            nt.nodes.remove(n)
    sky = nt.nodes.new("ShaderNodeTexSky")
    sky.sky_type = "NISHITA"
    sky.sun_elevation = math.radians(sun_elev)
    sky.sun_rotation = math.radians(sun_rot)
    sky.air_density = 1.4
    sky.dust_density = 2.5
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = 0.22 * strength
    nt.links.new(sky.outputs["Color"], bg.inputs["Color"])
    nt.links.new(bg.outputs["Background"], next(n for n in nt.nodes if n.type == "OUTPUT_WORLD").inputs["Surface"])
    for ob in list(bpy.data.objects):
        if ob.type == "LIGHT" and ob.data.type == "SUN":
            bpy.data.objects.remove(ob)
    sun = bpy.data.lights.new("sun_pbr", "SUN")
    sun.energy = 3.2 * strength
    sun.angle = math.radians(1.5)
    sun.color = (1.0, 0.95, 0.88)
    so = bpy.data.objects.new("sun_pbr", sun)
    so.rotation_euler = (math.radians(90 - sun_elev), 0.0, math.radians(sun_rot + 180.0))
    sc.collection.objects.link(so)
