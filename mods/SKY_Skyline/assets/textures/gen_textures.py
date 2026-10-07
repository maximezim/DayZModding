#!/usr/bin/env python3
"""Generate SKY_Skyline texture sources (PNG) procedurally.

Deterministic (fixed seeds) so the PNGs are build artifacts, not source: run
this, then tools\\assets\\Convert-SkyTextures.ps1 (ImageToPAA) on Windows.

    python gen_textures.py --out <dir> [--size 2048] [--only concrete,glass]

Each material gets the DayZ map set:
    _co / _ca  colour (alpha for _ca)
    _nohq      tangent-space normal (standard RGB; ImageToPAA applies the
               _nohq conversion based on the suffix)
    _smdi      R = 1 (unused), G = specular intensity, B = glossiness
    _as        ambient shadow (white = unoccluded)
All designs are original: no brands, logos or real-building references.
"""
import argparse
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont


# ------------------------------------------------------------------ helpers
def value_noise(size, cells, seed):
    rng = np.random.default_rng(seed)
    small = rng.random((cells, cells)).astype(np.float32)
    img = Image.fromarray((small * 255).astype(np.uint8), "L").resize((size, size), Image.BICUBIC)
    return np.asarray(img, dtype=np.float32) / 255.0


def fbm(size, seed, octaves=5, base=4):
    acc = np.zeros((size, size), np.float32)
    amp, total = 1.0, 0.0
    for o in range(octaves):
        acc += amp * value_noise(size, base * (2 ** o), seed + o)
        total += amp
        amp *= 0.5
    return acc / total


def normal_from_height(h, strength):
    # D83: wrapped central differences, so the normals match across the sheet seam (np.gradient is one-sided
    # at the edges - perf review L)
    gx = 0.5 * (np.roll(h, -1, 1) - np.roll(h, 1, 1))
    gy = 0.5 * (np.roll(h, -1, 0) - np.roll(h, 1, 0))
    nx, ny, nz = -gx * strength, -gy * strength, np.ones_like(h)
    n = np.sqrt(nx * nx + ny * ny + nz * nz)
    rgb = np.stack([nx / n, ny / n, nz / n], -1) * 0.5 + 0.5
    return Image.fromarray((rgb * 255).astype(np.uint8), "RGB")


def to_rgb(arr):
    return Image.fromarray(np.clip(arr * 255, 0, 255).astype(np.uint8), "RGB")


def gray(arr):
    return np.repeat(arr[..., None], 3, -1)


CONST_SIZE = 256   # constant-value maps don't need full resolution


# ------------------------------------------------------------------ weathering (D59)
def tnoise(size, cells, seed, aspect=1):
    """Tileable value noise (wraps in U and V): the random grid is tiled 3 x 3 before the
    bicubic resize and the centre is cropped, so facades show no seam every sheet."""
    rng = np.random.default_rng(seed)
    small = rng.random((max(1, cells // aspect), cells)).astype(np.float32)
    big = np.tile(small, (3, 3))
    img = Image.fromarray((big * 255).astype(np.uint8), "L").resize((3 * size, 3 * size), Image.BICUBIC)
    return np.asarray(img, dtype=np.float32)[size:2 * size, size:2 * size] / 255.0


def tfbm(size, seed, octaves=4, base=4):
    acc, amp, tot = np.zeros((size, size), np.float32), 1.0, 0.0
    for o in range(octaves):
        acc += amp * tnoise(size, base * (2 ** o), seed + o)
        tot += amp
        amp *= 0.5
    return acc / tot


def weather(col, seed, dirt=0.18, desat=0.25, moss=0.0, streaks=0.0, spots=0.0):
    """DayZ weathering on a colour map (tileable): desaturate toward grey, mottled grime,
    vertical rain streaks, dark spots (soot / rust) and a green moss tint in the low patches.
    Scale-free features only: the facade-level gradients (rising damp, run-off) are the
    decal_grime overlay quads placed by the generators."""
    size = col.shape[0]
    g = col.mean(-1, keepdims=True)
    col = col * (1 - desat) + g * desat
    m = tfbm(size, seed, octaves=5, base=4)
    col = col * (1 - dirt * gray(np.clip((m - 0.35) * 2.0, 0, 1)))
    if streaks:
        st = np.repeat(tnoise(size, 48, seed + 7, aspect=48)[:1, :], size, 0)
        st = np.clip((st - 0.55) * 4, 0, 1) * tfbm(size, seed + 9, octaves=3, base=2)
        col = col * (1 - streaks * gray(st))
    if spots:
        sp = np.clip((tfbm(size, seed + 13, octaves=4, base=16) - 0.68) * 6, 0, 1)
        col = col * (1 - spots * gray(sp))
    if moss:
        mm = np.clip((tfbm(size, seed + 21, octaves=4, base=6) - 0.62) * 5, 0, 1)[..., None] * moss
        col = col * (1 - mm) + np.array([0.30, 0.36, 0.20], np.float32) * mm
    return col


def smdi(size, spec, gloss):
    if np.ndim(spec) == 0 and np.ndim(gloss) == 0:
        size = min(size, CONST_SIZE)
    s = np.broadcast_to(np.asarray(spec, np.float32), (size, size))
    g = np.broadcast_to(np.asarray(gloss, np.float32), (size, size))
    rgb = np.stack([np.ones((size, size), np.float32), s, g], -1)
    return to_rgb(rgb)


def save(img, out, name):
    path = os.path.join(out, name + ".png")
    img.save(path, optimize=True)
    return path


def band_rows(size, v0, v1):
    return int(size * v0), int(size * v1)


# ------------------------------------------------------------------ materials
def concrete(size, out):
    n = tfbm(size, 11, octaves=5, base=4)                     # D77: tileable (fbm left a seam every sheet)
    fine = tfbm(size, 17, octaves=3, base=64)
    h = np.zeros((size, size), np.float32)
    col = 0.56 + 0.10 * (n - 0.5) + 0.05 * (fine - 0.5)
    ao = np.ones((size, size), np.float32)
    # Band 1 (panel, V 0-0.5): 2 x 1 precast panels, seams + tie holes.
    r0, r1 = band_rows(size, 0.0, 0.5)
    seam = max(2, size // 512)
    for x in (0, size // 2):
        h[r0:r1, x:x + seam] -= 1.0
        ao[r0:r1, x:x + seam] *= 0.6
    h[r1 - seam:r1, :] -= 1.0
    yy, xx = np.mgrid[0:size, 0:size]
    for cy in np.linspace(r0 + size * 0.08, r1 - size * 0.08, 3):
        for cx in np.linspace(size * 0.08, size * 0.92, 6):
            m = (yy - cy) ** 2 + (xx - cx) ** 2 < (size * 0.006) ** 2
            h[m] -= 0.8
            col[m] *= 0.7
            ao[m] *= 0.55
    # Band 2 (board-formed, V 0.5-0.75): horizontal boards with grain.
    r0, r1 = band_rows(size, 0.5, 0.75)
    boards = 8
    bh = (r1 - r0) // boards
    for b in range(boards):
        y = r0 + b * bh
        h[y:y + seam, :] -= 0.7
        ao[y:y + seam, :] *= 0.75
        col[y:y + bh, :] += 0.03 * ((b * 7919) % 5 - 2) / 2
    grain = tnoise(size, 256, 23)
    col[r0:r1, :] += 0.04 * (np.repeat(grain[r0:r1, :1], size, 1) - 0.5)
    # Band 3 (reveal, V 0.75-1): smooth with one recessed groove.
    r0, r1 = band_rows(size, 0.75, 1.0)
    g0 = r0 + (r1 - r0) // 2
    h[g0:g0 + seam * 3, :] -= 1.0
    ao[g0:g0 + seam * 3, :] *= 0.65
    h += 0.15 * fine
    # D77: blowholes (bug holes) and masked hairline shrinkage cracks, in colour, height and AO
    pores = np.clip((tnoise(size, 384, 25) - 0.9) * 10, 0, 1)
    hair = crack_field(size, 27, cells=4, width=0.0025, warp=0.02) * np.clip((tfbm(size, 29, octaves=3, base=3) - 0.5) * 4, 0, 1)
    col = col * (1 - 0.3 * pores - 0.22 * hair)
    h -= 0.7 * pores + 0.5 * hair
    ao *= 1 - 0.3 * pores
    save(to_rgb(weather(gray(col), 19, dirt=0.25, desat=0.0, moss=0.07, streaks=0.15, spots=0.15)), out,
         "sky_concrete_co")                                                                   # D59 weathering
    save(normal_from_height(h, 2.5), out, "sky_concrete_nohq")
    save(smdi(size, 0.12 + 0.05 * fine, 0.25), out, "sky_concrete_smdi")
    save(to_rgb(gray(0.75 + 0.25 * ao)), out, "sky_concrete_as")


def metal(size, out):
    streak = np.repeat(tnoise(size, 512, 31)[:, :1], size, 1)          # D77: tileable
    n = tfbm(size, 37, octaves=3, base=16)
    col = np.zeros((size, size, 3), np.float32)
    spec = np.zeros((size, size), np.float32)
    gloss = np.zeros((size, size), np.float32)
    h = 0.1 * n
    r0, r1 = band_rows(size, 0.0, 0.5)          # brushed aluminium (mullions)
    col[r0:r1] = gray(0.68 + 0.06 * (streak[r0:r1] - 0.5) + 0.02 * (n[r0:r1] - 0.5))
    spec[r0:r1], gloss[r0:r1] = 0.7, 0.6
    r0, r1 = band_rows(size, 0.5, 0.75)         # dark steel
    col[r0:r1] = gray(0.22 + 0.05 * (n[r0:r1] - 0.5))
    spec[r0:r1], gloss[r0:r1] = 0.45, 0.4
    r0, r1 = band_rows(size, 0.75, 1.0)         # painted panel (warm grey), rust bleeding (D59)
    col[r0:r1] = np.array([0.58, 0.57, 0.53]) + 0.03 * gray(n[r0:r1] - 0.5)
    spec[r0:r1], gloss[r0:r1] = 0.25, 0.35
    rs = np.clip((tfbm(size, 41, octaves=4, base=8) - 0.6) * 4, 0, 1)[r0:r1, :, None] * 0.6
    col[r0:r1] = col[r0:r1] * (1 - rs) + np.array([0.40, 0.24, 0.13], np.float32) * rs
    save(to_rgb(col), out, "sky_metal_co")
    save(normal_from_height(h, 1.0), out, "sky_metal_nohq")
    save(smdi(size, spec, gloss), out, "sky_metal_smdi")
    save(to_rgb(gray(np.full((CONST_SIZE, CONST_SIZE), 0.95, np.float32))), out, "sky_metal_as")


def glassfar(size, out):
    """Opaque far-LOD glass: dark tinted, slight sky gradient, no alpha."""
    size = min(size, 256)
    v = np.linspace(0, 1, size, dtype=np.float32)[:, None] * np.ones((1, size), np.float32)
    rgb = np.stack([0.20 + 0.10 * v, 0.26 + 0.10 * v, 0.31 + 0.08 * v], -1)
    save(to_rgb(rgb), out, "sky_glassfar_co")
    save(normal_from_height(np.zeros((size, size), np.float32), 1.0), out, "sky_glassfar_nohq")
    save(smdi(size, 0.8, 0.8), out, "sky_glassfar_smdi")
    save(to_rgb(gray(np.ones((size, size), np.float32))), out, "sky_glassfar_as")


def glass(size, out):
    size = min(size, 512)                       # flat colour: 512 is plenty
    v = np.linspace(0, 1, size, dtype=np.float32)[:, None] * np.ones((1, size), np.float32)
    rgb = np.stack([0.30 + 0.08 * v, 0.38 + 0.08 * v, 0.44 + 0.06 * v], -1)
    alpha = np.full((size, size), 0.38, np.float32)
    rgba = np.concatenate([rgb, alpha[..., None]], -1)
    Image.fromarray((rgba * 255).astype(np.uint8), "RGBA").save(os.path.join(out, "sky_glass_ca.png"))
    save(normal_from_height(np.zeros((size, size), np.float32), 1.0), out, "sky_glass_nohq")
    save(smdi(size, 0.9, 0.9), out, "sky_glass_smdi")
    save(to_rgb(gray(np.ones((size, size), np.float32))), out, "sky_glass_as")


def tiled(size, out, name, tiles, base_rgb, grout_rgb, grout_px, seed, spec, gloss, tile_var=0.03):
    n = fbm(size, seed, octaves=4, base=8)
    col = np.array(base_rgb, np.float32) + 0.06 * gray(n - 0.5)
    h = 0.2 * n
    ao = np.ones((size, size), np.float32)
    step = size // tiles
    rng = np.random.default_rng(seed)
    for ty in range(tiles):
        for tx in range(tiles):
            col[ty * step:(ty + 1) * step, tx * step:(tx + 1) * step] += tile_var * (rng.random() - 0.5)
    for i in range(tiles + 1):
        p = min(i * step, size - grout_px)
        col[p:p + grout_px, :] = grout_rgb
        col[:, p:p + grout_px] = grout_rgb
        h[p:p + grout_px, :] -= 1.0
        h[:, p:p + grout_px] -= 1.0
        ao[p:p + grout_px, :] *= 0.8
        ao[:, p:p + grout_px] *= 0.8
    save(to_rgb(col), out, name + "_co")
    save(normal_from_height(h, 2.0), out, name + "_nohq")
    save(smdi(size, spec, gloss), out, name + "_smdi")
    save(to_rgb(gray(0.8 + 0.2 * ao)), out, name + "_as")


def carpet(size, out):
    # Carpet tiles: high-frequency fibre noise, 8 x 8 tiles (0.5 m at 4 m mapping).
    fibre = fbm(size, 53, octaves=3, base=256)
    n = fbm(size, 59, octaves=3, base=8)
    col = np.array([0.30, 0.33, 0.37], np.float32) + 0.07 * gray(fibre - 0.5) + 0.04 * gray(n - 0.5)
    step = size // 8
    for i in range(9):
        p = min(i * step, size - 2)
        col[p:p + 2, :] *= 0.85
        col[:, p:p + 2] *= 0.85
    save(to_rgb(col), out, "sky_carpet_co")
    save(normal_from_height(0.5 * fibre, 1.5), out, "sky_carpet_nohq")
    save(smdi(size, 0.03, 0.05), out, "sky_carpet_smdi")
    save(to_rgb(gray(np.full((CONST_SIZE, CONST_SIZE), 0.97, np.float32))), out, "sky_carpet_as")


def wallpaper(size, out):
    n = fbm(size, 71, octaves=4, base=8)
    x = np.linspace(0, 1, size, dtype=np.float32)[None, :] * np.ones((size, 1), np.float32)
    stripes = 0.5 + 0.5 * np.sign(np.sin(x * np.pi * 2 * 32))
    col = np.array([0.80, 0.78, 0.73], np.float32) + 0.02 * gray(stripes - 0.5) + 0.03 * gray(n - 0.5)
    save(to_rgb(col), out, "sky_wallpaper_co")
    save(normal_from_height(0.05 * stripes + 0.1 * n, 1.0), out, "sky_wallpaper_nohq")
    save(smdi(size, 0.08, 0.15), out, "sky_wallpaper_smdi")
    save(to_rgb(gray(np.full((CONST_SIZE, CONST_SIZE), 0.97, np.float32))), out, "sky_wallpaper_as")


def crack_field(size, seed, cells=7, width=0.012, warp=0.01, dist=None):
    """Tileable crack network (D75): edges of a periodic Voronoi diagram (distance to the nearest minus the
    second nearest seed), warped by tileable noise so the cracks wander. Returns 0..1 (1 = in a crack)."""
    if dist is not None:                                  # reuse crack_dist() (perf D77 L6)
        return np.clip(1.0 - dist / width, 0.0, 1.0)
    return np.clip(1.0 - crack_dist(size, seed, cells, warp) / width, 0.0, 1.0)


def crack_dist(size, seed, cells=7, warp=0.01):
    """Second-nearest minus nearest seed distance of the warped periodic Voronoi (0 on a crack)."""
    rng = np.random.default_rng(seed)
    pts = rng.random((cells * cells, 2)).astype(np.float32)
    y, x = np.mgrid[0:size, 0:size].astype(np.float32) / size
    wx = (tfbm(size, seed + 1, octaves=3, base=4) - 0.5) * 2 * warp
    wy = (tfbm(size, seed + 2, octaves=3, base=4) - 0.5) * 2 * warp
    x, y = (x + wx) % 1.0, (y + wy) % 1.0
    d1 = np.full((size, size), 9.0, np.float32)
    d2 = np.full((size, size), 9.0, np.float32)
    for px, py in pts:
        dx = np.abs(x - px)
        dy = np.abs(y - py)
        d = np.sqrt(np.minimum(dx, 1 - dx) ** 2 + np.minimum(dy, 1 - dy) ** 2)    # torus distance: tiles
        closer = d < d1
        d2 = np.where(closer, d1, np.minimum(d2, d))
        d1 = np.where(closer, d, d1)
    return d2 - d1


def asphalt(size, out):
    """Worn asphalt (D75, mapped at 4 m): aggregate grit, a tileable crack network, part of it tar-sealed
    in darker 3-4 cm bands, oil blotches and sun-bleached patches. Height drives the normal map, cracks
    and grit drive spec / gloss (sealant is glossier, cracks hold dust)."""
    n = tfbm(size, 83, octaves=6, base=8)
    grit = (np.random.default_rng(89).random((size, size)) > 0.985).astype(np.float32)
    dist = crack_dist(size, 401, cells=5)
    net = crack_field(size, 401, cells=5, width=0.004, dist=dist)
    keep = np.clip((tfbm(size, 403, octaves=3, base=3) - 0.42) * 5, 0, 1)        # only part of the network cracked
    cracks = net * keep
    near = crack_field(size, 401, cells=5, width=0.014, dist=dist)                        # tar sealant: a band round some cracks
    seal = near * np.clip((tfbm(size, 411, octaves=2, base=2) - 0.55) * 6, 0, 1)
    oil = np.clip((tfbm(size, 419, octaves=4, base=6) - 0.62) * 6, 0, 1)
    bleach = np.clip((tfbm(size, 421, octaves=3, base=3) - 0.5) * 3, 0, 1)
    v = 0.20 + 0.06 * (n - 0.5) + 0.12 * grit + 0.05 * bleach
    v = v * (1 - 0.55 * cracks) * (1 - 0.35 * seal) * (1 - 0.3 * oil)
    save(to_rgb(gray(np.clip(v, 0, 1))), out, "sky_asphalt_co")
    height = 0.4 * n + 0.6 * grit - 1.2 * cracks + 0.2 * seal
    save(normal_from_height(height, 2.0), out, "sky_asphalt_nohq")
    save(smdi(size, 0.06 + 0.1 * grit + 0.12 * seal + 0.1 * oil - 0.04 * cracks, 0.1 + 0.25 * seal + 0.3 * oil), out,
         "sky_asphalt_smdi")
    save(to_rgb(gray(np.clip(0.95 - 0.35 * cracks, 0, 1))), out, "sky_asphalt_as")


def roofmark(size, out):
    """Generic heliport marking: yellow ring + white 'H' on transparent."""
    size = min(size, 1024)
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c, r, w = size // 2, int(size * 0.46), int(size * 0.035)
    d.ellipse([c - r, c - r, c + r, c + r], outline=(222, 184, 40, 235), width=w)
    bw, bh = int(size * 0.07), int(size * 0.42)
    gap = int(size * 0.14)
    d.rectangle([c - gap - bw, c - bh // 2, c - gap, c + bh // 2], fill=(235, 235, 230, 235))
    d.rectangle([c + gap, c - bh // 2, c + gap + bw, c + bh // 2], fill=(235, 235, 230, 235))
    d.rectangle([c - gap, c - bw // 2, c + gap, c + bw // 2], fill=(235, 235, 230, 235))
    img.save(os.path.join(out, "sky_roofmark_ca.png"))
    save(normal_from_height(np.zeros((size, size), np.float32), 1.0), out, "sky_roofmark_nohq")
    save(smdi(size, 0.2, 0.3), out, "sky_roofmark_smdi")
    save(to_rgb(gray(np.ones((size, size), np.float32))), out, "sky_roofmark_as")


KEYCARD_COLOURS = {1: (46, 140, 87), 2: (214, 150, 32), 3: (190, 50, 45)}


def keycards(size, out):
    """512 card textures: tier stripe, chip, generic text. UV: whole card face."""
    size = min(size, 256)
    try:
        font = ImageFont.load_default(size=int(size * 0.07))
    except TypeError:                            # Pillow < 10.1
        font = ImageFont.load_default()
    for tier, rgb in KEYCARD_COLOURS.items():
        img = Image.new("RGB", (size, size), (228, 228, 224))
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, size, int(size * 0.28)], fill=rgb)
        d.rounded_rectangle([int(size * 0.08), int(size * 0.40), int(size * 0.30), int(size * 0.58)],
                            radius=int(size * 0.02), fill=(196, 170, 90), outline=(120, 100, 50), width=3)
        d.text((int(size * 0.08), int(size * 0.07)), "SKYLINE", fill=(250, 250, 250), font=font)
        d.text((int(size * 0.40), int(size * 0.44)), "ACCESS", fill=(60, 60, 60), font=font)
        d.text((int(size * 0.40), int(size * 0.54)), "LEVEL %d" % tier, fill=rgb, font=font)
        d.rectangle([0, int(size * 0.82), size, int(size * 0.90)], fill=(30, 30, 30))   # mag stripe
        img.save(os.path.join(out, "sky_keycard_t%d_co.png" % tier))
    save(normal_from_height(np.zeros((size, size), np.float32), 1.0), out, "sky_keycard_nohq")
    save(smdi(size, 0.3, 0.5), out, "sky_keycard_smdi")


# ------------------------------------------------------------------ street kit (batch 1)
def roadmark(size, out):
    """Road paint sheet (512, alpha-TESTED): V 0-0.25 solid line, 0.25-0.5 dashed
    line (1 dash per U), 0.5-1.0 crosswalk (1 stripe per U). Lines tile along U;
    wear lives in RGB (binary alpha, perf batch-1 M2)."""
    size = min(size, 512)
    q = size // 4
    a = np.zeros((size, size), np.float32)
    a[q // 2 - q // 6:q // 2 + q // 6, :] = 1                                  # solid
    a[q + q // 2 - q // 6:q + q // 2 + q // 6, : size // 2] = 1                # dashed: 50 % duty
    a[2 * q:, size // 4: 3 * size // 4] = 1                                     # crosswalk stripe
    wear = fbm(size, 109, octaves=4, base=8)
    rgb = np.stack([0.91 - 0.25 * wear, 0.90 - 0.25 * wear, 0.86 - 0.25 * wear], -1)
    a *= (wear > 0.28).astype(np.float32)                                     # chipped paint = holes
    Image.fromarray((np.concatenate([rgb, a[..., None]], -1) * 255).astype(np.uint8), "RGBA").save(
        os.path.join(out, "sky_roadmark_ca.png"))


def rust(size, out):
    """Weathered painted metal: V bands = green paint (dumpsters), grey paint
    (barriers/poles), rust (wrecks), burnt (wreck variant). 1024 (perf M5)."""
    size = min(size, 1024)
    n = fbm(size, 113, octaves=6, base=8)
    spots = (fbm(size, 127, octaves=4, base=16) > 0.58).astype(np.float32)
    col = np.zeros((size, size, 3), np.float32)
    bands = [((0.20, 0.33, 0.24), 0.0, 0.25), ((0.42, 0.43, 0.42), 0.25, 0.5),
             ((0.40, 0.25, 0.15), 0.5, 0.75), ((0.12, 0.11, 0.10), 0.75, 1.0)]
    rust_rgb = np.array([0.38, 0.20, 0.10], np.float32)
    for rgb, v0, v1 in bands:
        r0, r1 = band_rows(size, v0, v1)
        base = np.array(rgb, np.float32) + 0.05 * gray(n[r0:r1] - 0.5)
        m = spots[r0:r1, :, None]
        col[r0:r1] = base * (1 - m) + (rust_rgb + 0.06 * gray(n[r0:r1] - 0.5)) * m
    h = 0.5 * n + 0.6 * spots
    save(to_rgb(col), out, "sky_rust_co")
    save(normal_from_height(h, 2.0), out, "sky_rust_nohq")
    save(smdi(size, 0.25 - 0.15 * spots, 0.3 - 0.2 * spots), out, "sky_rust_smdi")


def foliage(size, out):
    """Generic shrub leaves card (alpha-tested), for planters and garden roofs. 512 (perf M5)."""
    size = min(size, 512)
    rng = np.random.default_rng(131)
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for _ in range(900):
        x, y = rng.integers(0, size), rng.integers(int(size * 0.1), size)
        r = int(rng.integers(size // 64, size // 24))
        if (x - size / 2) ** 2 / (size * 0.48) ** 2 + (y - size) ** 2 / (size * 0.9) ** 2 > 1:
            continue
        g = int(rng.integers(70, 130))
        d.ellipse([x - r, y - r // 2, x + r, y + r // 2], fill=(int(g * 0.45), g, int(g * 0.35), 255))
    img.save(os.path.join(out, "sky_foliage_ca.png"))


# Props atlas: 4 x 4 cells of size/4. Cell names must match skyspec.ATLAS.
def _font(px):
    try:
        return ImageFont.load_default(size=px)
    except TypeError:
        return ImageFont.load_default()


def atlas(size, out):
    c = size // 4
    img = Image.new("RGB", (size, size), (128, 128, 128))
    d = ImageDraw.Draw(img)
    h = np.zeros((size, size), np.float32)
    f_big, f_small = _font(c // 8), _font(c // 14)

    def cell(col, row):
        return col * c, row * c, (col + 1) * c, (row + 1) * c

    # (0,0) manhole cover: cast iron disc with radial ribs
    x0, y0, x1, y1 = cell(0, 0)
    d.rectangle([x0, y0, x1, y1], fill=(60, 58, 55))
    d.ellipse([x0 + 8, y0 + 8, x1 - 8, y1 - 8], fill=(48, 47, 45), outline=(80, 78, 74), width=6)
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    for k in range(12):
        a = k * np.pi / 6
        d.line([cx, cy, cx + np.cos(a) * c * 0.42, cy + np.sin(a) * c * 0.42], fill=(78, 76, 72), width=c // 40)
    d.ellipse([cx - c // 10, cy - c // 10, cx + c // 10, cy + c // 10], fill=(72, 70, 66))
    # (1,0) bus timetable panel
    x0, y0, x1, y1 = cell(1, 0)
    d.rectangle([x0, y0, x1, y1], fill=(236, 236, 230))
    d.rectangle([x0, y0, x1, y0 + c // 6], fill=(30, 80, 140))
    d.text((x0 + c // 16, y0 + c // 24), "LINE 7  SKYLINE", fill=(255, 255, 255), font=f_big)
    for i in range(10):
        d.text((x0 + c // 16, y0 + c // 4 + i * c // 15), "%02d:%02d   %02d:%02d   %02d:%02d" % (6 + i, 5, 6 + i, 25, 6 + i, 45),
               fill=(40, 40, 40), font=f_small)
    # (2,0) traffic light face: housing + red/amber/green lenses (vertical)
    x0, y0, x1, y1 = cell(2, 0)
    d.rectangle([x0, y0, x1, y1], fill=(28, 30, 28))
    for i, rgb in enumerate([(170, 30, 25), (190, 130, 20), (30, 150, 70)]):
        yy = y0 + c // 6 + i * c // 3
        d.ellipse([x0 + c // 3, yy - c // 8, x0 + 2 * c // 3, yy + c // 8], fill=rgb, outline=(10, 10, 10), width=4)
    # (3,0) generic street sign blank (blue, white border) - text-free
    x0, y0, x1, y1 = cell(3, 0)
    d.rectangle([x0, y0, x1, y1], fill=(30, 70, 130), outline=(240, 240, 240), width=c // 20)
    # (0,1) vending front: glass product window + selection panel + pickup slot
    x0, y0, x1, y1 = cell(0, 1)
    d.rectangle([x0, y0, x1, y1], fill=(150, 30, 35))
    d.rectangle([x0 + c // 12, y0 + c // 12, x0 + 2 * c // 3, y1 - c // 4], fill=(30, 34, 40))
    for r in range(5):
        for k in range(4):
            px = x0 + c // 12 + 8 + k * (c // 2 // 4 + 4)
            py = y0 + c // 12 + 8 + r * (c // 2 // 4 + 10)
            d.rectangle([px, py, px + c // 10, py + c // 9], fill=(60 + 35 * k, 120 + 20 * r, 90 + 25 * ((k + r) % 3)))
    d.rectangle([x0 + 3 * c // 4, y0 + c // 6, x1 - c // 16, y0 + c // 2], fill=(20, 20, 22))
    for r in range(4):
        for k in range(3):
            bx, by = x0 + 3 * c // 4 + 6 + k * c // 22, y0 + c // 6 + 10 + r * c // 18
            d.rectangle([bx, by, bx + c // 30, by + c // 30], fill=(200, 200, 200))
    d.rectangle([x0 + c // 8, y1 - c // 6, x0 + 5 * c // 8, y1 - c // 16], fill=(15, 15, 15))
    d.text((x0 + c // 12, y1 - c // 4 + 4), "COLD DRINKS", fill=(255, 255, 255), font=f_small)
    # (1,1) server rack front: perforated door with 1U units and status LEDs
    x0, y0, x1, y1 = cell(1, 1)
    d.rectangle([x0, y0, x1, y1], fill=(22, 23, 26))
    u = c // 24
    for i in range(1, 23):
        yy = y0 + i * u
        d.rectangle([x0 + c // 10, yy, x1 - c // 10, yy + u - 3], fill=(34 + 6 * (i % 3), 36, 40))
        for k in range(3):
            d.ellipse([x1 - c // 6 + k * 8, yy + 4, x1 - c // 6 + k * 8 + 4, yy + 8],
                      fill=[(40, 200, 80), (220, 160, 30), (40, 200, 80)][(i + k) % 3])
    # (2,1) control panel: grey box with gauges and switches (mechanical floors)
    x0, y0, x1, y1 = cell(2, 1)
    d.rectangle([x0, y0, x1, y1], fill=(150, 152, 148), outline=(90, 90, 88), width=c // 40)
    for k in range(3):
        gx = x0 + c // 8 + k * c // 4 + c // 16
        d.ellipse([gx - c // 12, y0 + c // 6, gx + c // 12, y0 + c // 6 + c // 6], fill=(235, 235, 228), outline=(30, 30, 30), width=3)
        d.line([gx, y0 + c // 4, gx + c // 20, y0 + c // 5], fill=(170, 20, 20), width=3)
        d.rectangle([gx - c // 40, y0 + c // 2, gx + c // 40, y0 + c // 2 + c // 10], fill=(30, 30, 30))
    d.rectangle([x0 + c // 8, y1 - c // 5, x1 - c // 8, y1 - c // 10], fill=(230, 190, 30))
    d.text((x0 + c // 6, y1 - c // 5 + 4), "DANGER 400V", fill=(20, 20, 20), font=f_small)
    # (3,1) appliance front (fridge): off-white door, handle, seam
    x0, y0, x1, y1 = cell(3, 1)
    d.rectangle([x0, y0, x1, y1], fill=(224, 224, 218))
    d.line([x0, y0 + c // 3, x1, y0 + c // 3], fill=(150, 150, 146), width=4)
    d.rectangle([x0 + c // 12, y0 + c // 10, x0 + c // 12 + c // 40, y0 + c // 4], fill=(170, 172, 175))
    d.rectangle([x0 + c // 12, y0 + c // 3 + c // 12, x0 + c // 12 + c // 40, y0 + 2 * c // 3], fill=(170, 172, 175))
    # (0,2) monitor screen: dark bezel, dim desktop glow (no UI branding)
    x0, y0, x1, y1 = cell(0, 2)
    d.rectangle([x0, y0, x1, y1], fill=(18, 18, 20))
    d.rectangle([x0 + c // 20, y0 + c // 20, x1 - c // 20, y1 - c // 20], fill=(20, 40, 60))
    for k in range(5):
        d.rectangle([x0 + c // 10, y0 + c // 8 + k * c // 7, x0 + c // 10 + c // 12, y0 + c // 8 + k * c // 7 + c // 14],
                    fill=(60, 90, 120))
    # (1,2) extinguisher: red body band with white label (wrapped on the prism)
    x0, y0, x1, y1 = cell(1, 2)
    d.rectangle([x0, y0, x1, y1], fill=(170, 25, 25))
    d.rectangle([x0, y0, x1, y0 + c // 8], fill=(30, 30, 30))
    d.rectangle([x0 + c // 6, y0 + c // 3, x1 - c // 6, y0 + 2 * c // 3], fill=(240, 240, 235))
    d.text((x0 + c // 5, y0 + c // 3 + c // 12), "FIRE", fill=(170, 25, 25), font=f_big)
    # (2,2) signage: building name strip in the top eighth of the cell (original text, D53)
    x0, y0, x1, y1 = cell(2, 2)
    d.rectangle([x0, y0, x1, y1], fill=(36, 38, 42))
    d.rectangle([x0, y0, x1, y0 + c // 8], fill=(22, 24, 28))
    d.rectangle([x0 + 3, y0 + 3, x1 - 3, y0 + c // 8 - 3], outline=(150, 152, 156), width=2)
    fs = _font(c // 14)
    tb = d.textbbox((0, 0), "SKYLINE  TOWER", font=fs)
    d.text((x0 + (c - (tb[2] - tb[0])) // 2 - tb[0], y0 + (c // 8 - (tb[3] - tb[1])) // 2 - tb[1]), "SKYLINE  TOWER",
           fill=(232, 230, 222), font=fs)
    # (3,2) (0,3) (1,3) (2,3): original abstract artworks (framed canvases, D55)
    rng = np.random.default_rng(401)
    palettes = [[(196, 92, 60), (232, 200, 140), (40, 60, 90), (240, 236, 226)],
                [(30, 90, 110), (220, 210, 190), (200, 150, 60), (20, 30, 40)],
                [(120, 140, 100), (230, 225, 210), (170, 70, 70), (60, 60, 70)],
                [(240, 236, 226), (20, 20, 24), (210, 60, 50), (60, 110, 170)]]
    for k, (col_, row_) in enumerate([(3, 2), (0, 3), (1, 3), (2, 3)]):
        x0, y0, x1, y1 = cell(col_, row_)
        pal = palettes[k]
        d.rectangle([x0, y0, x1, y1], fill=(28, 24, 20))                              # frame
        m = c // 16
        d.rectangle([x0 + m, y0 + m, x1 - m, y1 - m], fill=pal[3])                    # canvas
        for _ in range(9 + 3 * k):
            px, py = int(rng.integers(x0 + m, x1 - m - c // 6)), int(rng.integers(y0 + m, y1 - m - c // 6))
            w, h_ = int(rng.integers(c // 12, c // 3)), int(rng.integers(c // 12, c // 3))
            shape = pal[int(rng.integers(0, 3))]
            if (k + _) % 3 == 0:
                d.ellipse([px, py, min(px + w, x1 - m), min(py + h_, y1 - m)], fill=shape)
            else:
                d.rectangle([px, py, min(px + w, x1 - m), min(py + h_, y1 - m)], fill=shape)
    # (3,3): wayfinding plates, 4 x 2 sub-cells: L 1 2 3 / 4 5 R EXIT
    x0, y0, x1, y1 = cell(3, 3)
    sw, sh = c // 4, c // 2
    labels = ["L", "1", "2", "3", "4", "5", "R", "EXIT"]
    fbig = _font(c // 5)
    for i, lab in enumerate(labels):
        sx, sy = x0 + (i % 4) * sw, y0 + (i // 4) * sh
        exit_ = lab == "EXIT"
        d.rectangle([sx, sy, sx + sw - 1, sy + sh - 1], fill=(20, 120, 60) if exit_ else (36, 38, 42))
        d.rectangle([sx + 3, sy + 3, sx + sw - 4, sy + sh - 4], outline=(230, 230, 225), width=2)
        f = _font(c // 14) if exit_ else fbig
        tb = d.textbbox((0, 0), lab, font=f)
        d.text((sx + (sw - (tb[2] - tb[0])) // 2 - tb[0], sy + (sh - (tb[3] - tb[1])) // 2 - tb[1]), lab,
               fill=(245, 245, 240), font=f)
    img.save(os.path.join(out, "sky_atlas_co.png"))   # nohq/smdi/as are procedural in sky_atlas.rvmat


BILLBOARDS = {
    "a": ("SKYLINE TRANSIT", "RIDE THE LINE", (30, 80, 140)),
    "b": ("COLD DRINKS", "ICE COLD - ALL DAY", (200, 60, 40)),
    "c": ("TOWER LOFTS", "NOW LEASING", (40, 40, 48)),
    "d": ("STAY SAFE", "CURFEW 22:00", (230, 180, 30)),
}


def billboards(size, out):
    """Four original poster designs (1024 x 512), swapped via hiddenSelections."""
    w, h = 1024, 512
    for key, (title, sub, rgb) in BILLBOARDS.items():
        img = Image.new("RGB", (w, h), rgb)
        d = ImageDraw.Draw(img)
        rng = np.random.default_rng(ord(key))
        for _ in range(6):                                   # abstract shapes
            x, y, r = rng.integers(0, w), rng.integers(0, h), int(rng.integers(40, 160))
            shade = tuple(int(min(255, v * 1.25 + 20)) for v in rgb)
            d.ellipse([x - r, y - r, x + r, y + r], fill=shade)
        d.rectangle([0, h - 150, w, h], fill=(245, 245, 240))
        d.text((40, 60), title, fill=(255, 255, 255), font=_font(96))
        d.text((40, h - 120), sub, fill=rgb, font=_font(64))
        a = np.asarray(img).astype(np.float32) / 255.0
        a *= (0.88 + 0.12 * fbm(512, 137, octaves=3, base=8)[:h, :, None].repeat(2, 1)[:, :w])   # weathering
        Image.fromarray((a * 255).astype(np.uint8), "RGB").save(os.path.join(out, "sky_billboard_%s_co.png" % key))
    # nohq/smdi/as are procedural in sky_billboard.rvmat (perf M5)


# ------------------------------------------------------------------ batch 2: decals, windows, facades
def _decal_save(out, name, rgba):
    Image.fromarray(np.clip(rgba * 255, 0, 255).astype(np.uint8), "RGBA").save(os.path.join(out, name + "_ca.png"))


def decals(size, out):
    """Alpha decals: dirt streaks (512 x 1024, matches the 2 x 3 m quad), cracks (1024),
    4 graffiti designs (512 each, swapped via hiddenSelections; abstract shapes +
    invented words; no real tags, logos or brands)."""
    size = min(size, 1024)
    # dirt: vertical run-off streaks + base grime band
    n = fbm(size, 151, octaves=5, base=6)
    x = np.linspace(0, 1, size, dtype=np.float32)[None, :]
    y = np.linspace(0, 1, size, dtype=np.float32)[:, None]
    streak = np.repeat(value_noise(size, 64, 157)[:1, :], size, 0)
    a = np.clip((streak - 0.45) * 2.0, 0, 1) * (1 - y) ** 1.5 * 0.7 + np.clip((y - 0.75) * 3, 0, 1) * 0.6
    a = np.clip(a * (0.6 + 0.6 * n), 0, 0.9)
    # fade every edge to 0 so the quad outline never shows (QA batch-2 M1)
    ramp = np.clip(np.minimum(np.minimum(x, 1 - x), np.minimum(y, 1 - y)) / 0.08, 0, 1)
    a *= ramp * ramp * (3 - 2 * ramp)
    rgb = np.stack([0.20 + 0.05 * n, 0.18 + 0.05 * n, 0.15 + 0.04 * n], -1)
    dirt = np.clip(np.concatenate([rgb, a[..., None]], -1) * 255, 0, 255).astype(np.uint8)
    Image.fromarray(dirt, "RGBA").resize((size // 2, size), Image.BICUBIC).save(   # perf batch-2 M2.3
        os.path.join(out, "sky_decal_dirt_ca.png"))
    # cracks: random-walk polylines
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    rng = np.random.default_rng(163)
    for _ in range(7):
        px, py = rng.integers(0, size), rng.integers(0, size)
        ang = rng.random() * 2 * np.pi
        for _s in range(rng.integers(20, 60)):
            ang += rng.normal(0, 0.5)
            nx, ny = px + np.cos(ang) * size / 60, py + np.sin(ang) * size / 60
            d.line([px, py, nx, ny], fill=(25, 24, 22, 230), width=int(rng.integers(2, 5)))   # >= 2 px: survives mips (perf L5)
            px, py = nx, ny
    img.save(os.path.join(out, "sky_decal_cracks_ca.png"))
    # graffiti: 4 original designs (abstract spray shapes + invented words), 512 each,
    # swapped via hiddenSelections like the billboards.
    g = 512
    for key, (w, rgb) in zip("abcd", [("SKY", (220, 60, 160)), ("NO CURFEW", (40, 180, 220)),
                                       ("ZONE 7", (240, 200, 40)), ("RUN", (120, 220, 90))]):
        img = Image.new("RGBA", (g, g), (0, 0, 0, 0))
        dd = ImageDraw.Draw(img)
        for _ in range(5):
            r = int(rng.integers(g // 10, g // 4))
            x0, y0 = int(rng.integers(r, g - r)), int(rng.integers(r, g - r))
            dd.ellipse([x0 - r, y0 - r // 2, x0 + r, y0 + r // 2], fill=rgb + (255,))
        fs = g // 2                                           # shrink until the word fits the tile
        while fs > 12:
            x0b, y0b, x1b, y1b = dd.textbbox((0, 0), w, font=_font(fs))
            if x1b - x0b <= g * 0.84 and y1b - y0b <= g * 0.5:
                break
            fs -= 4
        tx, ty = (g - (x1b - x0b)) // 2 - x0b, (g - (y1b - y0b)) // 2 - y0b
        txt = Image.new("L", (g, g), 0)
        td = ImageDraw.Draw(txt)
        td.text((tx + 4, ty + 4), w, fill=255, font=_font(fs))
        td.text((tx, ty), w, fill=255, font=_font(fs))
        dd.text((tx + 4, ty + 4), w, fill=(20, 20, 20, 255), font=_font(fs))
        dd.text((tx, ty), w, fill=(255, 255, 255, 255), font=_font(fs))
        a = np.asarray(img).astype(np.float32) / 255.0
        keep = np.asarray(txt) > 0                            # lettering stays solid, noise only erodes the spray
        a[..., 3] *= np.maximum(fbm(g, 167 + ord(key), octaves=3, base=8) > 0.3, keep)  # binary alpha
        _decal_save(out, "sky_decal_graffiti_%s" % key, a)
    # nohq/smdi/as of all decals are procedural in their rvmats (no files).


def windows(size, out):
    """Window sets atlas (1024, 4 x 4 cells of 256 px): interiors seen through glass at night.
    Same _co for the unlit (sky_windows) and lit (sky_windows_lit, emissive rvmat) materials.
    1024 keeps ~170 px/m on a 1.5 m window (perf batch-2 L1)."""
    size = min(size, 1024)
    c = size // 4
    rng = np.random.default_rng(173)
    img = Image.new("RGB", (size, size), (20, 22, 26))
    d = ImageDraw.Draw(img)
    for row in range(4):
        for col in range(4):
            x0, y0 = col * c, row * c
            lit = (row * 4 + col) % 3 != 2
            warm = (rng.integers(180, 255), rng.integers(150, 210), rng.integers(90, 150)) if lit else (25, 28, 34)
            d.rectangle([x0 + 4, y0 + 4, x0 + c - 4, y0 + c - 4], fill=tuple(int(v) for v in warm))
            for _ in range(int(rng.integers(1, 4))):                # furniture / blinds silhouettes
                bx = x0 + int(rng.integers(4, c - 30))
                bw, bh = int(rng.integers(15, c // 2)), int(rng.integers(10, c // 3))
                d.rectangle([bx, y0 + c - 4 - bh, bx + bw, y0 + c - 4], fill=(15, 15, 18))
            if rng.random() < 0.5:                                   # blinds
                for k in range(0, c // 2, 6):
                    d.line([x0 + 4, y0 + 4 + k, x0 + c - 4, y0 + 4 + k], fill=(60, 55, 50), width=2)
            d.rectangle([x0, y0, x0 + c - 1, y0 + c - 1], outline=(70, 72, 76), width=3)   # mullion frame
    img.save(os.path.join(out, "sky_windows_co.png"))   # nohq/smdi/as procedural in the window rvmats


def brick(size, out):
    """Brick facade trim: V 0-0.6 running bond, 0.6-0.8 soldier course, 0.8-1 stone sill.
    D82: running bond with bevelled arrises, firing tones, face pits and soft joints (as wall_brick D80);
    tileable noise; tooled sill with a drip groove. D83: soldier course and sill carry relief in _nohq."""
    n = tfbm(size, 181, octaves=4, base=8)
    col = np.zeros((size, size, 3), np.float32)
    h = 0.1 * n
    ao = np.ones((size, size), np.float32)
    rng = np.random.default_rng(191)
    mortar = np.array([0.55, 0.53, 0.50], np.float32)
    r0, r1 = band_rows(size, 0.0, 0.6)
    # 16 bricks across U; with MATERIALS["brick"]["sheet_m"] = 3.44 m per U tile a brick is
    # 21.5 x 6.6 cm at ~595 px/m (perf batch-2 L3).
    bw, bh = size / 16.0, (r1 - r0) / 31.0          # D83: 31 whole courses in the band (was size / 52: a 7 px sliver
                                                    # under the soldier course, perf review M)
    yy, xx = np.mgrid[r0:r1, 0:size].astype(np.float32)
    rr = np.floor((yy - r0) / bh).astype(int)
    fy = (yy - r0) / bh - rr
    u = (xx - (rr % 2) * bw / 2) / bw
    cc = np.floor(u).astype(int) % 16
    fx = u - np.floor(u)
    m = max(1.0, size / 1024.0)
    e = np.minimum(np.minimum(fx, 1 - fx) * bw, np.minimum(fy, 1 - fy) * bh)
    joint = e < m
    bevel = np.clip((e - m) / (2.5 * m), 0, 1)
    T = rng.random((int(rr.max()) + 1, 16)).astype(np.float32)[rr, cc]
    tint = np.array([0.45, 0.22, 0.15], np.float32) * (0.8 + 0.4 * T[..., None])
    tint = np.where((T < 0.06)[..., None], np.array([0.25, 0.13, 0.11], np.float32), tint)
    pits = np.clip((tnoise(size, max(64, size // 6), 193) - 0.8) * 5, 0, 1)[r0:r1]
    band = tint * gray(0.84 + 0.16 * bevel) * gray(1 - 0.22 * pits)
    col[r0:r1] = np.where(joint[..., None], mortar, band)
    sj = 1.0 - np.clip((e - (m - 1.0)) / 2.0, 0, 1)
    h[r0:r1] += 0.3 * bevel - 0.25 * pits - 0.8 * sj
    ao[r0:r1] *= 1 - 0.2 * joint
    r0, r1 = band_rows(size, 0.6, 0.8)                   # soldier course
    ns = max(1, int(round(size / bh)))                                           # whole soldiers per sheet (no cut one at the seam)
    # D83: vectorised like the running bond - bevelled arrises, soft recessed joints, pits, per-brick tone - so
    # the course reads in _nohq too (it was flat colour blocks)
    yy, xx = np.mgrid[r0:r1, 0:size].astype(np.float32)
    us = xx * ns / size
    ci = np.floor(us).astype(int) % ns
    fx, fy = us - np.floor(us), (yy - r0) / max(1, r1 - r0)
    e = np.minimum(np.minimum(fx, 1 - fx) * size / ns, np.minimum(fy, 1 - fy) * (r1 - r0))
    joint = e < m
    bevel = np.clip((e - m) / (2.5 * m), 0, 1)
    Ts = rng.random(ns).astype(np.float32)[ci]
    tint = np.array([0.40, 0.20, 0.14], np.float32) * (0.85 + 0.3 * Ts[..., None])
    pits = np.clip((tnoise(size, max(64, size // 6), 194) - 0.8) * 5, 0, 1)[r0:r1]
    col[r0:r1] = np.where(joint[..., None], mortar, tint * gray(0.84 + 0.16 * bevel) * gray(1 - 0.22 * pits))
    sj = 1.0 - np.clip((e - (m - 1.0)) / 2.0, 0, 1)
    h[r0:r1] += 0.3 * bevel - 0.25 * pits - 0.8 * sj
    ao[r0:r1] *= 1 - 0.2 * joint
    r0, r1 = band_rows(size, 0.8, 1.0)                   # stone sill
    col[r0:r1] = np.array([0.66, 0.64, 0.60]) + 0.04 * gray(n[r0:r1] - 0.5)
    # D83: sill relief - rounded nose along the top arris, three stones per sheet with mortar joints, a bed
    # joint under the sill
    hs = r1 - r0
    yv = (np.arange(hs, dtype=np.float32) + 0.5) / hs
    xs_ = np.arange(size, dtype=np.float32)
    ej = np.abs(((xs_ / (size / 3.0)) + 0.5) % 1.0 - 0.5) * (size / 3.0)           # px to the nearest stone joint
    sjx = 1.0 - np.clip((ej - (m - 1.0)) / 2.0, 0, 1)
    h[r0:r1] -= 0.6 * sjx[None, :]
    col[r0:r1] = col[r0:r1] * (1 - sjx[None, :, None]) + mortar * sjx[None, :, None]
    bed = max(2, int(round(m * 1.5)))
    h[r0:r1] += (0.5 * np.clip((yv - bed / hs) / 0.12, 0, 1) ** 0.5)[:, None]     # nose: rounded over 12 % below the bed joint
    h[r0:r0 + bed, :] -= 0.6
    col[r0:r0 + bed, :] = mortar
    g0, gw = r0 + int((r1 - r0) * 0.8), max(4, size // 256)                       # drip groove under the sill nose:
    prof = 0.5 - 0.5 * np.cos(np.linspace(0, 2 * np.pi, gw, dtype=np.float32))  # cosine profile (perf D82 L)
    h[g0:g0 + gw, :] -= prof[:, None]
    col[g0:g0 + gw, :] *= gray(1 - 0.3 * prof[:, None])
    tooled = tstreak(size, max(32, size // 16), 64, 195)[r0:r1]                  # tooled stone face
    col[r0:r1] *= gray(0.96 + 0.06 * tooled)
    h[r0:r1] += 0.05 * tooled
    col += 0.04 * gray(n - 0.5)
    col *= gray(0.8 + 0.2 * ao)          # AO folded into _co; _as/_smdi are procedural (perf batch-2 M1)
    eff = np.clip((tfbm(size, 197, octaves=4, base=8) - 0.66) * 4, 0, 1)[..., None] * 0.35   # efflorescence
    col = col * (1 - eff) + np.array([0.72, 0.70, 0.66], np.float32) * eff
    col = weather(col, 199, dirt=0.22, desat=0.2, moss=0.06, streaks=0.15, spots=0.12)          # soot, grime (D59)
    save(to_rgb(col), out, "sky_brick_co")
    save(normal_from_height(h, 2.0), out, "sky_brick_nohq")


def concpanel(size, out):
    """Precast concrete panel facade: 2 x 2 panels per sheet with deep window
    reveal band at the top (V 0-0.2) and panel joints."""
    n = tfbm(size, 197, octaves=5, base=8)                      # D82: tileable (fbm left a seam every sheet)
    col = gray(0.66 + 0.06 * (n - 0.5))
    pores = np.clip((tnoise(size, max(64, size // 6), 201) - 0.9) * 10, 0, 1)   # blowholes
    col *= gray(1 - 0.28 * pores)
    h = 0.15 * n - 0.3 * pores                                     # halved nohq: gentle (perf D82 L)
    ao = np.ones((size, size), np.float32)
    j = max(3, size // 256)
    for p in (0, size // 2):
        col[:, p:p + j] *= 0.6
        col[p:p + j, :] *= 0.6
        h[:, p:p + j] -= 1
        h[p:p + j, :] -= 1
        ao[:, p:p + j] *= 0.6
        ao[p:p + j, :] *= 0.6
    r0, r1 = band_rows(size, 0.0, 0.2)
    col[r0:r1] *= 0.85
    h[r1 - j:r1, :] -= 1.5
    col *= gray(0.75 + 0.25 * ao)        # AO folded into _co; _as/_smdi are procedural (perf batch-2 M1)
    # joints weep: dark streaks running down from every horizontal joint (D59)
    yy_i = np.mgrid[0:size, 0:size][0]
    below = ((yy_i % (size // 2)) / (size / 2.0)).astype(np.float32)
    st = np.repeat(tnoise(size, 64, 211, aspect=64)[:1, :], size, 0)
    weep = np.clip((st - 0.5) * 3, 0, 1) * np.clip(1 - below * 2.2, 0, 1) * 0.35
    col = col * (1 - gray(weep))
    col = weather(col, 213, dirt=0.2, desat=0.3, moss=0.05, streaks=0.12, spots=0.18)
    save(to_rgb(col), out, "sky_concpanel_co")
    # mostly low-frequency relief: half-size normal map keeps >= 4 px joints (perf batch-2 L4)
    nh = normal_from_height(h, 2.5)
    save(nh.resize((max(1, size // 2),) * 2, Image.BILINEAR) if size > 1024 else nh, out, "sky_concpanel_nohq")


# ------------------------------------------------------------------ batch 3: interior props
# ------------------------------------------------------------------ texture depth (D77)
def tstreak(size, rows, cols, seed):
    """Tileable noise stretched along U (few columns, many rows): wood pores, fibre runs."""
    rng = np.random.default_rng(seed)
    small = rng.random((rows, cols)).astype(np.float32)
    big = np.tile(small, (3, 3))
    img = Image.fromarray((big * 255).astype(np.uint8), "L").resize((3 * size, 3 * size), Image.BICUBIC)
    return np.asarray(img, dtype=np.float32)[size:2 * size, size:2 * size] / 255.0


def scratches(size, seed, n, length=(0.03, 0.15), width=1):
    """Tileable fine scratch mask (0..1): short straight strokes drawn 3 x 3 and cropped."""
    rng = np.random.default_rng(seed)
    img = Image.new("L", (3 * size, 3 * size), 0)
    d = ImageDraw.Draw(img)
    for _ in range(n):
        x, y = rng.random(2) * size
        a = rng.random() * np.pi
        ln = (length[0] + rng.random() * (length[1] - length[0])) * size
        v = int(120 + rng.random() * 135)
        for ox in (0, size, 2 * size):
            for oy in (0, size, 2 * size):
                d.line([(x + ox, y + oy), (x + ox + np.cos(a) * ln, y + oy + np.sin(a) * ln)], fill=v, width=width)
    return np.asarray(img, dtype=np.float32)[size:2 * size, size:2 * size] / 255.0


def wood(size, out):
    """Furniture wood trim (1024): V 0-0.4 oak, 0.4-0.7 walnut, 0.7-0.95 grey laminate,
    0.95-1 monitor screen (keeps desk monitors in the wood section, perf batch-3 L1).
    D77: flat-sawn grain on boards (seams, per-board tone), open pores, lacquer scratches; real nohq + smdi
    (gloss: oiled oak satin, lacquered walnut, laminate, glass screen). Tiles along U."""
    size = min(size, 1024)
    v = np.linspace(0, 1, size, endpoint=False, dtype=np.float32)[:, None] * np.ones((1, size), np.float32)
    u = np.linspace(0, 1, size, endpoint=False, dtype=np.float32)[None, :] * np.ones((size, 1), np.float32)
    n = tfbm(size, 211, octaves=4, base=4)
    pores = np.clip((tstreak(size, 192, 24, 217) - 0.62) * 5, 0, 1)            # ~5 px rows: stable to mip 1 (perf D77 M1)
    scr = scratches(size, 219, 220, (0.02, 0.09), width=2)
    col = np.zeros((size, size, 3), np.float32)
    h = np.zeros((size, size), np.float32)
    spec = np.zeros((size, size), np.float32)
    gloss = np.zeros((size, size), np.float32)
    rng = np.random.default_rng(213)
    for (v0, v1), base, dark, boards, freq, sp, gl, lt, lm in [
            ((0.0, 0.4), (0.60, 0.44, 0.27), (0.45, 0.31, 0.17), 3, 5.0, 0.12, 0.32, 0.55, 0.6),     # oak: satin oil
            ((0.4, 0.7), (0.38, 0.24, 0.15), (0.22, 0.13, 0.08), 2, 9.0, 0.30, 0.55, 0.72, 0.45)]:    # walnut: lacquer
        r0, r1 = band_rows(size, v0, v1)
        vb, ub = v[r0:r1], u[r0:r1]
        vl = (vb - v0) / (v1 - v0)                                            # 0..1 across the band
        b = np.minimum((vl * boards).astype(int), boards - 1)               # boards run along U (with the grain)
        ph = rng.random(boards).astype(np.float32)[b]
        tone = (rng.random(boards).astype(np.float32)[b] - 0.5) * 0.10
        warp = tfbm(size, 214 + boards, octaves=3, base=2)[r0:r1]
        # flat-sawn figure: growth rings along U, gently arched (U-periodic) and wandering with tileable noise
        arch = 0.18 * np.sin(2 * np.pi * (ub + ph)) + 0.08 * np.sin(2 * np.pi * (2 * ub + 3 * ph))
        ring = np.sin(2 * np.pi * (freq * (vl * boards - b + arch) + 2.2 * warp + 0.6 * n[r0:r1] + ph * 7))
        late = np.clip((ring - lt) * 4.0, 0, 1)                              # thin dark latewood lines
        mix = np.clip(late * lm + 0.3 * pores[r0:r1] + 0.15 * (warp - 0.5), 0, 1)[..., None]
        c = np.array(base, np.float32) * (1 - mix) + np.array(dark, np.float32) * mix
        c = c * (1.0 + tone[..., None]) + 0.03 * gray(n[r0:r1] - 0.5)
        fb = (vl * boards) % 1.0
        seam = (fb < 1.2 * boards / (r1 - r0)) & (b > 0)
        col[r0:r1] = c
        h[r0:r1] = 0.25 * late - 0.6 * pores[r0:r1] - 1.0 * seam
        spec[r0:r1] = sp - 0.05 * pores[r0:r1]
        gloss[r0:r1] = gl - 0.15 * pores[r0:r1] - 0.2 * scr[r0:r1]
        col[r0:r1] += (0.03 if v0 == 0.0 else 0.06) * gray(scr[r0:r1])     # oiled oak hides scratches
    r0, r1 = band_rows(size, 0.7, 0.95)                                          # grey laminate, fine speckle
    fine = tnoise(size, 512, 225)
    col[r0:r1] = gray(0.57 + 0.025 * (fine[r0:r1] - 0.5) + 0.02 * (n[r0:r1] - 0.5)) + 0.05 * gray(scr[r0:r1])
    h[r0:r1] = 0.08 * fine[r0:r1]
    spec[r0:r1], gloss[r0:r1] = 0.2, 0.42 - 0.2 * scr[r0:r1]
    r0, r1 = band_rows(size, 0.95, 1.0)                                          # dead monitor glass
    g = np.linspace(0, 1, r1 - r0, dtype=np.float32)[:, None, None]
    col[r0:r1] = np.array([0.07, 0.11, 0.17], np.float32) + 0.05 * g + 0.02 * gray(n[r0:r1] - 0.5)
    spec[r0:r1], gloss[r0:r1] = 0.6, 0.85
    save(to_rgb(col), out, "sky_wood_co")
    save(normal_from_height(h, 1.5), out, "sky_wood_nohq")
    sm = smdi(size, np.clip(spec, 0, 1), np.clip(gloss, 0, 1))
    sm.resize((min(size, 512),) * 2, Image.BILINEAR).save(os.path.join(out, "sky_wood_smdi.png"))   # 512 (perf D77 L3)


def fabric(size, out):
    """Upholstery trim (512): V 0-0.33 grey, 0.33-0.66 blue, 0.66-1 beige.
    D77: 2/2 twill (8 px period survives mip 1, perf L4), slub yarn streaks, pilling, faint stains."""
    size = min(size, 512)
    yy, xx = np.mgrid[0:size, 0:size]
    twill = ((((xx // 2) + (yy // 2)) % 4) < 2).astype(np.float32)
    slub = tstreak(size, 128, 8, 227)
    n = tfbm(size, 223, octaves=3, base=8)
    pill = np.clip((tnoise(size, 192, 229) - 0.7) * 4, 0, 1)
    stain = np.clip((tfbm(size, 231, octaves=4, base=3) - 0.6) * 3, 0, 1)
    col = np.zeros((size, size, 3), np.float32)
    for (v0, v1), base in [((0.0, 0.33), (0.42, 0.42, 0.44)), ((0.33, 0.66), (0.20, 0.28, 0.45)),
                           ((0.66, 1.0), (0.66, 0.60, 0.50))]:
        r0, r1 = band_rows(size, v0, v1)
        k = 0.9 + 0.08 * twill[r0:r1] + 0.05 * (slub[r0:r1] - 0.5) + 0.04 * pill[r0:r1] - 0.12 * stain[r0:r1]
        col[r0:r1] = np.array(base, np.float32) * gray(k) + 0.03 * gray(n[r0:r1] - 0.5)
    save(to_rgb(col), out, "sky_fabric_co")
    save(normal_from_height(0.3 * twill + 0.15 * slub + 0.2 * pill + 0.1 * n, 1.0), out, "sky_fabric_nohq")


def paver(size, out):
    """Sidewalk pavers: 30 x 30 cm slabs (mapped at 3 m -> 10 x 10 per sheet). D77: three stone tones,
    bevelled arrises, sand joints with moss, chipped corners, gum / oil spots, a few cracked and sunken
    slabs; nohq / as / smdi from the same fields. Tileable (integer grid, tileable noise)."""
    tiles = 10
    step = size / tiles
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    gx, gy = xx / step, yy / step
    ix, iy = np.floor(gx).astype(int) % tiles, np.floor(gy).astype(int) % tiles
    fx, fy = gx - np.floor(gx), gy - np.floor(gy)
    edge = np.minimum(np.minimum(fx, 1 - fx), np.minimum(fy, 1 - fy))       # 0 at the joint, 0.5 centre
    rng = np.random.default_rng(101)
    R = rng.random((tiles, tiles, 6)).astype(np.float32)
    r = R[iy, ix]
    tones = np.array([(0.62, 0.60, 0.57), (0.58, 0.56, 0.54), (0.66, 0.63, 0.58)], np.float32)
    base = tones[np.minimum((r[..., 0] * 3).astype(int), 2)]
    n = tfbm(size, 103, octaves=4, base=8)
    grit = tnoise(size, 256, 105)                                                # 8 px: no normal sparkle (perf D77 M2)
    jw, bw = 0.025, 0.05                                                        # joint half width, bevel (tile units)
    joint = edge < jw
    bevel = np.clip((edge - jw) / bw, 0, 1)
    # chipped corners: a bite out of one corner on ~1 in 5 slabs
    cx = np.where(r[..., 1] < 0.5, fx, 1 - fx)
    cy = np.where(r[..., 2] < 0.5, fy, 1 - fy)
    chip = (r[..., 3] < 0.2) & (cx + cy < 0.12 + 0.05 * n)
    sunk = r[..., 4] < 0.06
    cracked = (r[..., 5] < 0.07) & (np.abs((fx - fy) * 0.7 + 0.1 * (n - 0.5)) < 0.012)
    col = base * gray(0.94 + 0.08 * (n - 0.5) + 0.06 * (grit - 0.5))
    col *= gray(0.85 + 0.15 * bevel)
    col = np.where(sunk[..., None], col * 0.9, col)
    moss = np.clip((tfbm(size, 107, octaves=3, base=5) - 0.5) * 3, 0, 1)
    jcol = np.array([0.44, 0.42, 0.38], np.float32) * (1 - 0.5 * moss[..., None]) + np.array([0.26, 0.31, 0.17], np.float32) * 0.5 * moss[..., None]
    col = np.where((joint | chip)[..., None], jcol * gray(0.8 + 0.2 * grit), col)
    col = np.where(cracked[..., None], col * 0.6, col)
    spots = np.clip((tnoise(size, 160, 109) - 0.93) * 14, 0, 1)                 # gum / drips (sparse)
    oil = np.clip((tfbm(size, 111, octaves=4, base=6) - 0.68) * 4, 0, 1)
    col *= gray(1 - 0.25 * spots - 0.18 * oil)
    h = 0.2 * bevel + 0.08 * grit - 1.0 * joint - 0.8 * chip - 0.5 * cracked - 0.3 * sunk
    ao = 1.0 - 0.35 * joint - 0.15 * (1 - bevel) - 0.25 * chip - 0.1 * sunk
    save(to_rgb(col), out, "sky_paver_co")
    normal_from_height(h, 2.0).resize((min(size, 1024),) * 2, Image.BILINEAR).save(
        os.path.join(out, "sky_paver_nohq.png"))                                  # 1024 (perf D77 M2)
    o = np.asarray(Image.fromarray((oil * 255).astype(np.uint8)).resize((min(size, 256),) * 2, Image.BILINEAR), np.float32) / 255.0
    save(smdi(min(size, 256), 0.12 + 0.1 * o, 0.22 + 0.25 * o), out, "sky_paver_smdi")              # low-frequency oil: 256
    a = to_rgb(gray(np.clip(ao, 0, 1)))
    a.resize((min(size, 1024),) * 2, Image.BILINEAR).save(os.path.join(out, "sky_paver_as.png"))   # AO at 1024 (perf M5)


# ------------------------------------------------------------------ realism pass (D53)
def ceiling(size, out):
    """Suspended ceiling (1024, sheet = MATERIALS["ceiling"]["sheet_m"] = 2.4 m): 4 x 4 grid of
    0.6 m fissured mineral tiles on a white T-bar grid. Light panels are separate emissive
    fixtures in the model (D55), so they line up with the script lights."""
    size = min(size, 1024)
    n = fbm(size, 241, octaves=4, base=16)
    col = gray(0.86 + 0.05 * (n - 0.5))
    h = 0.2 * n
    rng = np.random.default_rng(251)
    speck = rng.random((size, size)) < 0.04
    col[speck] *= 0.9
    h[speck] -= 0.3
    t = size // 4
    g = max(3, size // 160)                                      # 15 mm T-bar
    for k in range(5):
        p = min(size - g, k * t)
        col[:, p:p + g] = 0.95
        col[p:p + g, :] = 0.95
        h[:, p:p + g] += 0.5
        h[p:p + g, :] += 0.5
    save(to_rgb(col), out, "sky_ceiling_co")
    save(normal_from_height(h, 1.5), out, "sky_ceiling_nohq")


# ------------------------------------------------------------------ splendour pass (D55)
def marble(size, out):
    """Polished marble (sheet 2.4 m = 2 x 2 slabs of 1.2 m): warm white with grey veins,
    real nohq (joints), smdi (high gloss, joints matte) and as."""
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32) / size
    warp = fbm(size, 301, octaves=6, base=3)
    veins = np.abs(np.sin((xx * 3.0 + yy * 1.4 + 2.8 * warp) * np.pi))
    veins = np.clip(1.0 - veins * 7.0, 0, 1) ** 2                  # thin dark lines
    fine = fbm(size, 307, octaves=5, base=16)
    col = np.stack([0.90 + 0.04 * (fine - 0.5), 0.89 + 0.04 * (fine - 0.5), 0.86 + 0.04 * (fine - 0.5)], -1)
    col -= 0.35 * veins[..., None] * np.array([1.0, 1.0, 0.95], np.float32)
    rng = np.random.default_rng(311)
    half = size // 2
    j = max(2, size // 512)
    for sy in (0, half):                                            # slab-to-slab tint
        for sx in (0, half):
            col[sy:sy + half, sx:sx + half] *= 0.97 + 0.06 * rng.random()
    gloss = np.full((size, size), 0.85, np.float32)
    h = 0.05 * fine
    for p in (0, half):
        col[p:p + j, :] *= 0.75
        col[:, p:p + j] *= 0.75
        gloss[p:p + j, :] = 0.2
        gloss[:, p:p + j] = 0.2
        h[p:p + j, :] -= 1
        h[:, p:p + j] -= 1
    save(to_rgb(col), out, "sky_marble_co")
    save(normal_from_height(h, 2.0), out, "sky_marble_nohq")
    save(smdi(size, 0.6 * np.ones((size, size), np.float32), gloss), out, "sky_marble_smdi")
    save(to_rgb(gray(np.full((CONST_SIZE, CONST_SIZE), 1.0, np.float32))), out, "sky_marble_as")


def parquet(size, out):
    """Oak plank floor (sheet 2.0 m): 16 rows of 12.5 cm planks, staggered 1 m lengths,
    per-plank tint, grain, bevelled joints in nohq; satin smdi."""
    n = fbm(size, 321, octaves=4, base=8)
    rows = 16
    rh = size // rows
    col = np.zeros((size, size, 3), np.float32)
    h = np.zeros((size, size), np.float32)
    gl = np.full((size, size), 0.45, np.float32)
    rng = np.random.default_rng(331)
    xx = np.linspace(0, 1, size, dtype=np.float32)[None, :]
    for r in range(rows):
        y0, y1 = r * rh, (r + 1) * rh
        off = int(rng.integers(0, size // 2))
        cuts = sorted({(off + k * size // 2) % size for k in range(2)} | {0, size})
        for a, b in zip(cuts, cuts[1:]):
            tint = np.array([0.56, 0.40, 0.25], np.float32) * (0.82 + 0.3 * rng.random())
            grain = 0.5 + 0.5 * np.sin((xx[:, a:b] * 220 + 3 * n[y0:y1, a:b] + rng.random() * 6) * np.pi)
            col[y0:y1, a:b] = tint + 0.06 * gray(grain - 0.5)
            col[y0:y1, a:a + 2] *= 0.6
            h[y0:y1, a:a + 2] -= 1
        col[y0:y0 + 2, :] *= 0.6
        h[y0:y0 + 2, :] -= 1
        gl[y0:y0 + 2, :] = 0.1
    col += 0.03 * gray(n - 0.5)
    save(to_rgb(col), out, "sky_parquet_co")
    save(normal_from_height(h + 0.05 * n, 1.5), out, "sky_parquet_nohq")
    save(smdi(size, 0.35 * np.ones((size, size), np.float32), gl), out, "sky_parquet_smdi")


PAINT = [(0.92, 0.91, 0.88), (0.86, 0.80, 0.70), (0.66, 0.72, 0.62), (0.52, 0.60, 0.68), (0.74, 0.47, 0.36)]


def paint(size, out):
    """Interior wall paint trim (1024): 5 bands - white, warm beige, sage, slate blue,
    terracotta accent; fine roller stipple in nohq (as/smdi procedural)."""
    size = min(size, 1024)
    stip = fbm(size, 341, octaves=3, base=128)
    n = fbm(size, 347, octaves=4, base=4)
    col = np.zeros((size, size, 3), np.float32)
    for i, rgb in enumerate(PAINT):
        r0, r1 = band_rows(size, i * 0.2, (i + 1) * 0.2)
        col[r0:r1] = np.array(rgb, np.float32) + 0.02 * gray(stip[r0:r1] - 0.5) + 0.02 * gray(n[r0:r1] - 0.5)
    save(to_rgb(col), out, "sky_paint_co")
    save(normal_from_height(0.3 * stip, 0.8), out, "sky_paint_nohq")


def stone(size, out):
    """Exterior cladding (sheet 3 m): V 0-0.5 polished dark granite, 0.5-1 honed limestone;
    0.75 m panels with 8 mm joints; real nohq + smdi."""
    rng = np.random.default_rng(353)
    n = tfbm(size, 359, octaves=5, base=12)                       # D77: tileable
    col = np.zeros((size, size, 3), np.float32)
    gl = np.zeros((size, size), np.float32)
    r0, r1 = band_rows(size, 0.0, 0.5)
    speck = rng.random((r1 - r0, size)).astype(np.float32)
    col[r0:r1] = 0.20 + 0.10 * gray(n[r0:r1] - 0.5)
    col[r0:r1][speck > 0.93] = (0.55, 0.53, 0.52)
    col[r0:r1][speck < 0.05] = (0.08, 0.08, 0.09)
    gl[r0:r1] = 0.8
    r0, r1 = band_rows(size, 0.5, 1.0)
    col[r0:r1] = np.array([0.80, 0.76, 0.66], np.float32) + 0.05 * gray(n[r0:r1] - 0.5)
    gl[r0:r1] = 0.3
    h = 0.05 * n
    j = max(3, size // 375)
    step = size // 4
    for k in range(4):                                  # D77: one joint at the wrap, not two (double width)
        p = k * step
        col[:, p:p + j] *= 0.55
        h[:, p:p + j] -= 1
        gl[:, p:p + j] = 0.05
    for v in (0.0, 0.25, 0.5, 0.75):
        p = int(v * size)
        col[p:p + j, :] *= 0.55
        h[p:p + j, :] -= 1
        gl[p:p + j, :] = 0.05
    col = weather(col, 367, dirt=0.18, desat=0.1, moss=0.05, streaks=0.12, spots=0.05)          # D59
    save(to_rgb(col), out, "sky_stone_co")
    save(normal_from_height(h, 2.0), out, "sky_stone_nohq")
    save(smdi(size, 0.5 * np.ones((size, size), np.float32), gl), out, "sky_stone_smdi")
    # D77 fix: sky_stone.rvmat always referenced sky_stone_as.paa but it was never written (missing texture
    # in game). AO from the joints, 512 (perf D77 L5).
    ao = to_rgb(gray(np.clip(0.8 + 0.2 * np.clip(h + 1.0, 0, 1), 0, 1)))
    ao.resize((min(size, 512),) * 2, Image.BILINEAR).save(os.path.join(out, "sky_stone_as.png"))


def textile(size, out):
    """Soft furnishings (1024): V 0-0.3 geometric rug, 0.3-0.6 bordered rug, 0.6-0.8 corridor
    runner, 0.8-1 curtain (vertical folds). nohq from weave; as/smdi procedural."""
    size = min(size, 1024)
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    weave = ((((xx // 3) + (yy // 3)) % 2) * 0.5).astype(np.float32)
    n = fbm(size, 367, octaves=3, base=8)
    col = np.zeros((size, size, 3), np.float32)
    r0, r1 = band_rows(size, 0.0, 0.3)                           # rug A: diamonds
    u = xx[r0:r1] / size * 8
    v = (yy[r0:r1] - r0) / (r1 - r0) * 2
    d = (np.abs((u % 1) - 0.5) + np.abs((v % 1) - 0.5)) < 0.32
    col[r0:r1] = np.where(d[..., None], (0.62, 0.52, 0.38), (0.22, 0.26, 0.34))
    r0, r1 = band_rows(size, 0.3, 0.6)                           # rug B: field + border
    col[r0:r1] = (0.52, 0.16, 0.14)
    b = max(6, (r1 - r0) // 8)
    col[r0:r0 + b] = col[r1 - b:r1] = (0.80, 0.68, 0.45)
    col[r0 + 2 * b:r0 + 2 * b + 4] = col[r1 - 2 * b - 4:r1 - 2 * b] = (0.12, 0.14, 0.22)
    r0, r1 = band_rows(size, 0.6, 0.8)                           # corridor runner
    col[r0:r1] = (0.30, 0.10, 0.12)
    b = max(5, (r1 - r0) // 7)
    col[r0:r0 + b] = col[r1 - b:r1] = (0.70, 0.56, 0.30)
    stripe = ((xx[r0:r1] // (size // 32)) % 4 == 0) & (np.abs(yy[r0:r1] - (r0 + r1) / 2) < (r1 - r0) / 5)
    col[r0:r1][stripe] = (0.45, 0.20, 0.18)
    r0, r1 = band_rows(size, 0.8, 1.0)                           # curtain
    folds = 0.5 + 0.5 * np.sin(xx[r0:r1] / size * np.pi * 2 * 24)
    col[r0:r1] = np.array([0.82, 0.77, 0.66], np.float32) * (0.82 + 0.18 * gray(folds))
    col *= (0.94 + 0.06 * gray(weave))
    col += 0.03 * gray(n - 0.5)
    save(to_rgb(col), out, "sky_textile_co")
    save(normal_from_height(0.4 * weave + 0.3 * n, 1.0), out, "sky_textile_nohq")


# ------------------------------------------------------------------ city wave 1 (D56)
# Chernarus palette (D59): faded, slightly dirty post-Soviet stucco tones
RENDER = [(0.78, 0.73, 0.60), (0.72, 0.57, 0.38), (0.62, 0.62, 0.59), (0.80, 0.79, 0.74)]


def render(size, out):
    """Exterior render / stucco (sheet 4 m): 4 colour bands cream, ochre, grey, white; float
    texture, hairline cracks, rain streaks and dirt toward the bottom of each band (weathering
    is part of the coherent city style)."""
    n = fbm(size, 401, octaves=6, base=8)
    fine = fbm(size, 409, octaves=3, base=128)
    yy = np.linspace(0, 1, size, dtype=np.float32)[:, None] * np.ones((1, size), np.float32)
    streak = fbm(size, 419, octaves=3, base=64)
    streak = np.clip((value_noise(size, 96, 421) - 0.6) * 3, 0, 1) * 0.5 + 0.5 * streak
    col = np.zeros((size, size, 3), np.float32)
    h = 0.2 * fine + 0.1 * n
    for i, rgb in enumerate(RENDER):
        r0, r1 = band_rows(size, i * 0.25, (i + 1) * 0.25)
        t = (yy[r0:r1] - i * 0.25) / 0.25                          # 0 top -> 1 bottom of band
        dirt = 0.10 * t + 0.08 * streak[r0:r1] * (0.3 + t)
        col[r0:r1] = np.array(rgb, np.float32) * (1 - gray(dirt)) + 0.03 * gray(fine[r0:r1] - 0.5)
    crack = np.abs(np.sin((yy * 9 + n * 6) * np.pi)) < 0.012
    col[crack] *= 0.72
    h[crack] -= 0.6
    # plaster loss: small irregular patches showing the brick underneath (D59)
    loss = tfbm(size, 431, octaves=5, base=6) > 0.71
    bw, bh = max(4, size // 24), max(2, size // 80)
    yy_i, xx_i = np.mgrid[0:size, 0:size]
    mortar = ((yy_i % bh) < 2) | (((xx_i + (yy_i // bh % 2) * bw // 2) % bw) < 2)
    brick_rgb = np.where(mortar[..., None], np.array([0.50, 0.48, 0.44], np.float32), np.array([0.46, 0.27, 0.19], np.float32))
    col = np.where(loss[..., None], brick_rgb, col)
    h[loss] -= 0.8
    col = weather(col, 437, dirt=0.16, desat=0.15, moss=0.08, streaks=0.18, spots=0.10)
    save(to_rgb(col), out, "sky_render_co")
    save(normal_from_height(h, 1.2), out, "sky_render_nohq")


def rubble(size, out):
    """Collapse debris (sheet 3 m): broken concrete and brick chunks, dust, rebar stubs;
    real nohq + smdi (matte)."""
    rng = np.random.default_rng(431)
    col = np.zeros((size, size, 3), np.float32) + np.array([0.42, 0.40, 0.37], np.float32)
    h = np.zeros((size, size), np.float32)
    img = Image.new("RGB", (size, size), (107, 102, 94))
    d = ImageDraw.Draw(img)
    hm = Image.new("L", (size, size), 60)
    dh = ImageDraw.Draw(hm)
    for _ in range(1600):
        cx, cy = rng.integers(0, size, 2)
        r = int(rng.integers(size // 120, size // 20))
        k = rng.integers(5, 9)
        ang = np.sort(rng.random(k) * 2 * np.pi)
        pts = [(int(cx + r * (0.6 + 0.4 * rng.random()) * np.cos(a)), int(cy + r * (0.6 + 0.4 * rng.random()) * np.sin(a))) for a in ang]
        brick = rng.random() < 0.3
        base = (150, 70, 52) if brick else (int(rng.integers(120, 175)),) * 3
        f = 0.75 + 0.35 * rng.random()
        tint = tuple(int(c * f) for c in base)
        d.polygon(pts, fill=tint, outline=(60, 58, 55))
        dh.polygon(pts, fill=int(rng.integers(120, 255)))
    for _ in range(40):                                          # rebar
        x0, y0 = rng.integers(0, size, 2)
        a = rng.random() * np.pi
        L = rng.integers(size // 30, size // 10)
        d.line([x0, y0, x0 + L * np.cos(a), y0 + L * np.sin(a)], fill=(80, 50, 35), width=max(2, size // 512))
    col = np.asarray(img, np.float32) / 255.0
    n = fbm(size, 439, octaves=5, base=16)
    col = col * (0.85 + 0.25 * gray(n)) * 0.95 + 0.04
    h = np.asarray(hm, np.float32) / 255.0 + 0.2 * n
    save(to_rgb(col), out, "sky_rubble_co")
    save(normal_from_height(h, 3.0), out, "sky_rubble_nohq")
    save(smdi(size, 0.05, 0.08), out, "sky_rubble_smdi")


SIGNS = ["POLICE", "PHARMACY", "MARKET", "CAFE  ROSA", "OFFICES", "DEPOT  3", "BAKERY", "HARDWARE",
         "CLINIC", "FIRE  STATION", "AUTO  REPAIR", "NEWS", "FUEL", "BANK", "GALERIE  NOVA", "HOSPITAL",
         "SCHOOL  No 4", "TOWN  HALL", "POST", "METRO"]


def signs(size, out):
    """Building sign strips (2048): 20 horizontal bands, invented names, enamel / backlit
    styles; mapped one band per sign (skyspec.SIGN_BAND)."""
    size = min(size, 2048)
    img = Image.new("RGB", (size, size), (30, 30, 34))
    d = ImageDraw.Draw(img)
    styles = [((20, 40, 110), (240, 240, 240)), ((20, 120, 70), (245, 245, 240)), ((170, 40, 35), (250, 240, 220)),
              ((60, 30, 25), (240, 200, 120)), ((40, 44, 50), (230, 230, 225)), ((200, 160, 30), (30, 30, 30)),
              ((120, 70, 40), (250, 236, 200)), ((30, 60, 90), (250, 200, 60)),
              ((240, 240, 236), (20, 110, 60)), ((170, 25, 25), (250, 250, 245)), ((30, 30, 34), (240, 170, 30)),
              ((235, 225, 200), (40, 40, 44)),
              ((200, 30, 30), (250, 250, 250)), ((25, 40, 70), (225, 195, 120)), ((20, 20, 22), (235, 235, 235)),
              ((245, 245, 245), (190, 25, 30)), ((30, 70, 120), (250, 250, 245)), ((210, 200, 175), (50, 45, 40)),
              ((240, 200, 30), (20, 40, 110)), ((150, 20, 30), (250, 250, 250))]
    for i, txt in enumerate(SIGNS):
        bg, fg = styles[i]
        y0 = int(i * size / len(SIGNS))                       # same band edges as skyspec.SIGN_BAND
        bh = int((i + 1) * size / len(SIGNS)) - y0
        d.rectangle([0, y0, size, y0 + bh - 1], fill=bg)
        d.rectangle([4, y0 + 4, size - 5, y0 + bh - 5], outline=fg, width=3)
        f = _font(int(bh * 0.55))
        tb = d.textbbox((0, 0), txt, font=f)
        d.text(((size - (tb[2] - tb[0])) // 2 - tb[0], y0 + (bh - (tb[3] - tb[1])) // 2 - tb[1]), txt, fill=fg, font=f)
    img.save(os.path.join(out, "sky_signs_co.png"))


SIGNS2 = ["HYPERMARKET  GIGANT", "KINO  ZARYA", "CENTRAL  MALL", "BAR  ZUBR", "KINDERGARTEN  No 7", "FC  LOKOMOTIV",
          "LUNAPARK", "PARKING", "MUNICIPAL  LANDFILL", "FOOD  COURT", "TICKETS", "FASHION", "SHOES", "JEWELRY",
          "ELECTRONICS", "STOP  -  DANGER"]


def signs2(size, out):
    """Second sign sheet (2048, D61): 16 bands for the venues (skyspec.SIGN2_NAMES order). Neon-era
    palette: hypermarket red on white, cinema gold on burgundy, mall white on teal, bar amber on black."""
    size = min(size, 2048)
    img = Image.new("RGB", (size, size), (30, 30, 34))
    d = ImageDraw.Draw(img)
    styles = [((245, 245, 242), (200, 30, 30)), ((110, 20, 30), (240, 200, 90)), ((20, 110, 115), (250, 250, 245)),
              ((20, 18, 18), (250, 170, 40)), ((250, 225, 120), (40, 90, 160)), ((25, 70, 40), (245, 245, 240)),
              ((240, 210, 40), (180, 30, 60)), ((30, 70, 150), (250, 250, 250)), ((80, 85, 70), (235, 230, 210)),
              ((200, 90, 30), (255, 245, 225)), ((120, 20, 30), (250, 230, 160)), ((25, 25, 28), (235, 120, 170)),
              ((60, 40, 30), (240, 220, 190)), ((20, 20, 40), (230, 200, 110)), ((15, 30, 60), (110, 220, 250)),
              ((230, 190, 20), (20, 20, 20))]
    for i, txt in enumerate(SIGNS2):
        bg, fg = styles[i]
        y0 = int(i * size / len(SIGNS2))                      # same band edges as skyspec.SIGN_BAND (signs2)
        bh = int((i + 1) * size / len(SIGNS2)) - y0
        d.rectangle([0, y0, size, y0 + bh - 1], fill=bg)
        d.rectangle([5, y0 + 5, size - 6, y0 + bh - 6], outline=fg, width=4)
        if i in (1, 6, 10):                                   # marquee bulbs round the cinema / fair / ticket bands
            for x in range(18, size - 10, 36):
                for yy in (y0 + 14, y0 + bh - 15):
                    d.ellipse([x - 6, yy - 6, x + 6, yy + 6], fill=(255, 236, 170))
        if i == 15:                                           # hazard stripes for the bridge checkpoint
            for x in range(-bh, size, 80):
                d.polygon([(x, y0 + bh - 1), (x + 40, y0 + bh - 1), (x + 40 + bh // 3, y0 + bh - 1 - bh // 3),
                           (x + bh // 3, y0 + bh - 1 - bh // 3)], fill=(20, 20, 20))
        f = _font(int(bh * 0.5))
        tb = d.textbbox((0, 0), txt, font=f)
        d.text(((size - (tb[2] - tb[0])) // 2 - tb[0], y0 + (bh - (tb[3] - tb[1])) // 2 - tb[1] - (6 if i == 15 else 0)),
               txt, fill=fg, font=f)
    img.save(os.path.join(out, "sky_signs2_co.png"))


SIGNS3 = ["PLOSHCHAD  POBEDY", "VOKZALNAYA", "STADION", "TEATRALNAYA", "EXIT  >>", "<<  EXIT", "M   LINE  1",
          "SEWER  -  NO  ENTRY"]


def signs3(size, out):
    """Underground sign sheet (1024, D66): 8 bands = skyspec.SIGN3_NAMES. Station name boards white on
    metro blue with a red M roundel, exit boards green, line board, a yellow/black sewer warning."""
    size = min(size, 1024)
    img = Image.new("RGB", (size, size), (20, 22, 28))
    d = ImageDraw.Draw(img)
    styles = [((25, 60, 140), (245, 245, 240))] * 4 + [((20, 110, 60), (245, 245, 240))] * 2 + \
             [((240, 240, 236), (25, 60, 140)), ((230, 190, 20), (20, 20, 20))]
    n = len(SIGNS3)
    for i, txt in enumerate(SIGNS3):
        bg, fg = styles[i]
        y0 = int(i * size / n)
        bh = int((i + 1) * size / n) - y0
        d.rectangle([0, y0, size, y0 + bh - 1], fill=bg)
        d.rectangle([4, y0 + 4, size - 5, y0 + bh - 5], outline=fg, width=3)
        if i < 4 or i == 6:                                   # red M roundel at the left
            cx, cy, r = int(bh * 0.6), y0 + bh // 2, int(bh * 0.36)
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(200, 30, 35))
            fm = _font(int(r * 1.3))
            tb = d.textbbox((0, 0), "M", font=fm)
            d.text((cx - (tb[2] - tb[0]) // 2 - tb[0], cy - (tb[3] - tb[1]) // 2 - tb[1]), "M", fill=(250, 250, 250), font=fm)
        if i == 7:
            for x in range(-bh, size, 60):
                d.polygon([(x, y0 + bh - 1), (x + 30, y0 + bh - 1), (x + 30 + bh // 4, y0 + bh - 1 - bh // 4),
                           (x + bh // 4, y0 + bh - 1 - bh // 4)], fill=(20, 20, 20))
        f = _font(int(bh * 0.42))
        tb = d.textbbox((0, 0), txt, font=f)
        x = (size - (tb[2] - tb[0])) // 2 - tb[0] + (int(bh * 0.5) if i < 4 else 0)
        d.text((x, y0 + (bh - (tb[3] - tb[1])) // 2 - tb[1] - (4 if i == 7 else 0)), txt, fill=fg, font=f)
    arr = np.asarray(img).astype(np.float32) / 255.0
    arr = weather(arr, 1701, dirt=0.3, desat=0.2, moss=0.0, streaks=0.25, spots=0.2)          # grime from the tunnels
    save(to_rgb(np.clip(arr, 0, 1)), out, "sky_signs3_co")


SIGNS4 = ["UNIVERSAM  RASSVET", "KINO  OKTYABR", "TC  GALAKTIKA", "PIVNAYA  No 1", "FC  TORPEDO", "MOLOKO", "REMONT  OBUVI",
          "SBERKASSA"]                                       # 6-8: spare bands for later variants


def signs4(size, out):
    """Venue variant sign sheet (1024, D69): 8 bands = skyspec.SIGN4_NAMES (6-8 spare). Older Soviet look than signs2:
    painted sheet metal, serif-free capitals, a thin keyline; weathered like the facades."""
    size = min(size, 1024)
    img = Image.new("RGB", (size, size), (30, 30, 34))
    d = ImageDraw.Draw(img)
    styles = [((30, 90, 60), (240, 236, 220)), ((150, 30, 25), (250, 225, 150)), ((35, 40, 90), (240, 200, 70)),
              ((95, 55, 25), (245, 230, 200)), ((15, 15, 15), (240, 240, 240)), ((235, 235, 225), (30, 70, 150)),
              ((60, 60, 65), (240, 200, 60)), ((30, 60, 110), (240, 240, 235))]
    n = len(SIGNS4)
    for i, txt in enumerate(SIGNS4):
        bg, fg = styles[i]
        y0 = int(i * size / n)                                # same band edges as skyspec.SIGN_BAND (signs4)
        bh = int((i + 1) * size / n) - y0
        d.rectangle([0, y0, size, y0 + bh - 1], fill=bg)
        d.rectangle([6, y0 + 6, size - 7, y0 + bh - 7], outline=fg, width=3)
        if i == 1:                                            # marquee bulbs (cinema)
            for x in range(18, size - 10, 32):
                for yy in (y0 + 16, y0 + bh - 17):
                    d.ellipse([x - 5, yy - 5, x + 5, yy + 5], fill=(255, 236, 170))
        if i == 4:                                            # club stripes: black / white
            for x in range(0, size, 64):
                d.rectangle([x, y0 + bh - 18, x + 31, y0 + bh - 8], fill=(240, 240, 240))
        f = _font(int(bh * 0.5))
        tb = d.textbbox((0, 0), txt, font=f)
        d.text(((size - (tb[2] - tb[0])) // 2 - tb[0], y0 + (bh - (tb[3] - tb[1])) // 2 - tb[1]), txt, fill=fg, font=f)
    arr = np.asarray(img).astype(np.float32) / 255.0
    arr = weather(arr, 1901, dirt=0.35, desat=0.25, moss=0.05, streaks=0.35, spots=0.25)
    save(to_rgb(np.clip(arr, 0, 1)), out, "sky_signs4_co")


def fair(size, out):
    """Fairground paint trim (1024, D61): V 0-0.25 Pripyat yellow, 0.25-0.5 signal red, 0.5-0.75 fair
    blue, 0.75-1 cream white. Chalked, flaking to grey primer and rust, rust runs from the top."""
    size = min(size, 1024)
    cols = [(0.86, 0.68, 0.12), (0.66, 0.13, 0.10), (0.16, 0.33, 0.58), (0.86, 0.83, 0.74)]
    n = tfbm(size, 1301, octaves=5, base=8)
    flake = np.clip((tfbm(size, 1303, octaves=4, base=16) - 0.58) * 6, 0, 1)
    rust = np.clip((tfbm(size, 1307, octaves=4, base=8) - 0.62) * 4, 0, 1)
    col = np.zeros((size, size, 3), np.float32)
    for i, c in enumerate(cols):
        r0, r1 = band_rows(size, i * 0.25, (i + 1) * 0.25)
        base = np.array(c, np.float32) * (0.9 + 0.2 * (n[r0:r1, :, None] - 0.5))
        chalk = 0.25 * np.clip(n[r0:r1, :, None] - 0.3, 0, 1)
        base = base * (1 - chalk) + 0.85 * chalk
        f = flake[r0:r1, :, None]
        base = base * (1 - f) + np.array([0.48, 0.46, 0.42], np.float32) * f
        yy = np.linspace(0, 1, r1 - r0, dtype=np.float32)[:, None, None]
        run = rust[r0:r1, :, None] * (1.2 - yy)
        rr = np.clip(run, 0, 0.8)
        base = base * (1 - rr) + np.array([0.38, 0.20, 0.10], np.float32) * rr
        col[r0:r1] = base
    col = weather(col, 1311, dirt=0.15, desat=0.12, moss=0.0, streaks=0.1, spots=0.1)
    save(to_rgb(col), out, "sky_fair_co")
    save(normal_from_height(0.3 * n - 0.6 * flake, 1.5), out, "sky_fair_nohq")


def trash(size, out):
    """Landfill rubbish (2048, tileable 4 m, D61): black / blue / white bin bags, crushed cans,
    paper, rags and dark soil between; mostly low-frequency relief."""
    rng = np.random.default_rng(1401)
    img = Image.new("RGB", (size, size), (58, 50, 40))
    d = ImageDraw.Draw(img)
    bag_cols = [(22, 22, 24)] * 6 + [(34, 34, 38)] * 4 + [(52, 66, 96), (150, 150, 145), (64, 74, 52), (96, 72, 48),
                                                          (120, 100, 70)]
    for _ in range(int(520 * (size / 2048) ** 2)):
        x, y = rng.uniform(0, size), rng.uniform(0, size)
        r = rng.uniform(size / 60, size / 20)
        c = bag_cols[int(rng.integers(0, len(bag_cols)))]
        sh = rng.uniform(0.75, 1.1)
        cc = tuple(int(min(255, v * sh)) for v in c)
        for ox in (-size, 0, size):
            for oy in (-size, 0, size):
                d.ellipse([x + ox - r, y + oy - r * 0.7, x + ox + r, y + oy + r * 0.7], fill=cc)
                if rng.random() < 0.3:
                    d.line([x + ox - r * 0.6, y + oy, x + ox + r * 0.6, y + oy - r * 0.2], fill=(min(255, cc[0] + 40),) * 3, width=2)
    for _ in range(int(500 * (size / 2048) ** 2)):                     # paper, cans, rags
        x, y = rng.uniform(0, size), rng.uniform(0, size)
        w, h = rng.uniform(6, 30) * size / 2048, rng.uniform(4, 18) * size / 2048
        c = [(200, 195, 180), (150, 145, 130), (130, 135, 140), (140, 70, 50), (120, 100, 70)][int(rng.integers(0, 5))]
        d.polygon([(x, y), (x + w, y + h * 0.3), (x + w * 0.8, y + h), (x - w * 0.1, y + h * 0.7)], fill=c)
    arr = np.asarray(img).astype(np.float32) / 255.0
    n = tfbm(size, 1403, octaves=5, base=8)
    arr *= (0.7 + 0.5 * n)[..., None]
    soil = np.clip((tfbm(size, 1405, octaves=4, base=6) - 0.5) * 2.0, 0, 1)[..., None] * 0.55   # dirt washed over it
    arr = arr * (1 - soil) + np.array([0.24, 0.20, 0.15], np.float32) * soil
    arr = weather(arr, 1409, dirt=0.25, desat=0.35, moss=0.04, streaks=0.0, spots=0.2)
    save(to_rgb(np.clip(arr, 0, 1)), out, "sky_trash_co")
    nh = normal_from_height(arr.mean(-1) * 1.5 + 0.5 * n, 2.0)
    save(nh.resize((size // 2,) * 2, Image.BILINEAR), out, "sky_trash_nohq")


def fur(size, out):
    """Short animal fur (1024, D65), 4 horizontal bands = skyspec MATERIALS["fur"]: shepherd tan, black
    saddle, rat grey-brown, horse chestnut. Hair = streaky noise stretched along U, a darker undercoat,
    tip highlights; tileable along U (each band is used with a band UV)."""
    rng = np.random.default_rng(1601)
    bands = [((0.62, 0.47, 0.30), (0.40, 0.28, 0.17)), ((0.10, 0.09, 0.08), (0.20, 0.17, 0.14)),
             ((0.36, 0.33, 0.30), (0.22, 0.20, 0.18)), ((0.45, 0.25, 0.13), (0.28, 0.15, 0.08))]
    hb = size // 4
    arr = np.zeros((size, size, 3), np.float32)
    for i, (tip, under) in enumerate(bands):
        n = rng.random((hb, size // 8)).astype(np.float32)
        streak = np.asarray(Image.fromarray((n * 255).astype(np.uint8)).resize((size, hb), Image.BILINEAR), np.float32) / 255.0
        fine = rng.random((hb, size)).astype(np.float32)
        t = np.clip(0.55 * streak + 0.45 * fine, 0, 1)[..., None]
        arr[i * hb:(i + 1) * hb] = np.array(under, np.float32) * (1 - t) + np.array(tip, np.float32) * t
    arr *= (0.85 + 0.3 * tfbm(size, 1603, octaves=4, base=6))[..., None]
    save(to_rgb(np.clip(arr, 0, 1)), out, "sky_fur_co")
    nh = normal_from_height(arr.mean(-1), 1.5)
    save(nh.resize((size // 2,) * 2, Image.BILINEAR), out, "sky_fur_nohq")


def turf(size, out):
    """Worn football turf (2048, tileable 8 m, D61): mown stripes, bald mud patches, weeds."""
    n = tfbm(size, 1501, octaves=6, base=16)
    m = np.clip((tfbm(size, 1503, octaves=4, base=4) - 0.55) * 3.5, 0, 1)
    xx = np.mgrid[0:size, 0:size][1]
    stripe = ((xx // (size // 8)) % 2).astype(np.float32)
    grass = np.stack([0.24 + 0.06 * n, 0.31 + 0.08 * n + 0.025 * stripe, 0.15 + 0.04 * n], -1)
    dry = np.array([0.45, 0.42, 0.26], np.float32)
    dr = np.clip((tfbm(size, 1507, octaves=4, base=6) - 0.5) * 2.5, 0, 1)[..., None] * 0.6
    grass = grass * (1 - dr) + dry * dr
    mud = np.array([0.30, 0.24, 0.17], np.float32) * (0.85 + 0.3 * n[..., None])
    col = grass * (1 - m[..., None]) + mud * m[..., None]
    col = weather(col, 1509, dirt=0.15, desat=0.3, moss=0.0, streaks=0.0, spots=0.15)
    save(to_rgb(col), out, "sky_turf_co")


def grime(size, out):
    """Facade weathering overlay sheet (alpha-blended like decal_dirt, 1024): 4 horizontal bands,
    each tileable along U so one quad can span a whole facade:
      V 0.00-0.25 rising damp: dark wet band at the bottom with moss specks, ragged top edge
      V 0.25-0.50 run-off: grime from the top edge, vertical streaks fading downwards
      V 0.50-0.75 window streaks: narrow streaks (quad under a sill)
      V 0.75-1.00 moss / lichen patches (plinths, copings, roof edges)"""
    size = min(size, 1024)
    bh = size // 4
    rgba = np.zeros((size, size, 4), np.float32)
    x = np.linspace(0, 1, size, dtype=np.float32)
    t = np.linspace(0, 1, bh, dtype=np.float32)[:, None]                     # 0 top -> 1 bottom of band
    n = tfbm(size, 501, octaves=5, base=8)
    edge = np.repeat((0.6 * tnoise(size, 24, 503, aspect=24) + 0.4 * tnoise(size, 96, 505, aspect=96))[:1, :], bh, 0)
    st = np.repeat(tnoise(size, 64, 509, aspect=64)[:1, :], bh, 0)
    # rising damp
    top = 0.25 + 0.45 * edge                                                    # ragged upper edge
    a = np.clip((t - top) * 3.0, 0, 1) * (0.55 + 0.35 * n[:bh])
    rgb = np.stack([0.17 + 0.04 * n[:bh], 0.18 + 0.05 * n[:bh], 0.12 + 0.03 * n[:bh]], -1)
    moss = (tfbm(size, 511, octaves=4, base=32)[:bh] > 0.62) & (t > 0.6)
    rgb[moss] = (0.24, 0.30, 0.14)
    rgba[:bh] = np.concatenate([rgb, a[..., None]], -1)
    # run-off from the top
    a = (np.clip(1 - t * 3.0, 0, 1) * 0.55 + np.clip((st - 0.45) * 2.5, 0, 1) * (1 - t) ** 1.3 * 0.6) * (0.6 + 0.5 * n[bh:2 * bh])
    rgb = np.stack([0.16 + 0.03 * n[bh:2 * bh], 0.15 + 0.03 * n[bh:2 * bh], 0.13 + 0.02 * n[bh:2 * bh]], -1)
    rgba[bh:2 * bh] = np.concatenate([rgb, np.clip(a * 0.75, 0, 0.7)[..., None]], -1)
    # window streaks (fit to the quad: fade at the sides)
    side = np.clip(np.minimum(x, 1 - x) / 0.25, 0, 1)[None, :]
    st2 = np.repeat(tnoise(size, 16, 521, aspect=16)[:1, :], bh, 0)
    a = np.clip((st2 - 0.35) * 2.2, 0, 1) * (1 - t) ** 1.6 * side * 0.7
    rgb = np.stack([0.18 + 0 * t * x, 0.17 + 0 * t * x, 0.15 + 0 * t * x], -1)
    rgba[2 * bh:3 * bh] = np.concatenate([rgb, a[..., None]], -1)
    # moss / lichen patches
    p = tfbm(size, 531, octaves=5, base=12)[3 * bh:]
    a = np.clip((p - 0.5) * 3.5, 0, 1) * 0.85
    rgb = np.stack([0.28 + 0.1 * p, 0.34 + 0.1 * p, 0.17 + 0.05 * p], -1)
    rgba[3 * bh:] = np.concatenate([rgb, a[..., None]], -1)
    Image.fromarray(np.clip(rgba * 255, 0, 255).astype(np.uint8), "RGBA").save(os.path.join(out, "sky_decal_grime_ca.png"))


# ------------------------------------------------------------------ tileable wall sheets (D59)
# The trim sheets (brick / concpanel / stone / render bands) stretch their last row on faces taller
# than the band; walls get their own sheets that tile in U and V (mapped at world scale).
def _rows(size, n):
    return [int(round(r * size / n)) for r in range(n + 1)]


def wall_brick(size, out):
    """Running-bond brick wall, 3.44 m sheet (16 bricks x 46 courses), tileable, sooty and weathered.
    D80: per-brick firing tones (burnt headers, pale bricks), bevelled arrises, raked sandy mortar, face pits,
    chipped corners and a few spalled bricks; real _as (1024) from the same fields (_smdi stays procedural, perf D80 M1)."""
    rng = np.random.default_rng(701)
    rows, nb = 46, 16
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    ch, bw = size / rows, size / nb
    r = np.floor(yy / ch).astype(int) % rows
    fy = yy / ch - np.floor(yy / ch)
    off = (r % 2) * (bw / 2)
    u = (xx - off) / bw
    c = np.floor(u).astype(int) % nb
    fx = u - np.floor(u)
    m = max(1.0, size / 680.0)                                                  # mortar half-joint: ~10 mm joint
    ex, ey = np.minimum(fx, 1 - fx) * bw, np.minimum(fy, 1 - fy) * ch
    e = np.minimum(ex, ey)
    joint = e < m
    bevel = np.clip((e - m) / (2.5 * m), 0, 1)
    R = rng.random((rows, nb, 6)).astype(np.float32)[r, c]
    base = np.array([0.44, 0.22, 0.15], np.float32) * (0.78 + 0.4 * R[..., 0:1])
    burnt = (R[..., 1] < 0.07)[..., None]
    pale = (R[..., 1] > 0.95)[..., None]
    col = np.where(burnt, np.array([0.24, 0.13, 0.11], np.float32) * (0.9 + 0.2 * R[..., 0:1]), base)
    col = np.where(pale, np.array([0.56, 0.38, 0.27], np.float32), col)
    n = tfbm(size, 703, octaves=5, base=8)
    pits = np.clip((tnoise(size, max(64, size // 6), 711) - 0.8) * 5, 0, 1)
    face = tnoise(size, max(64, size // 12), 713)
    cx = np.where(R[..., 2] < 0.5, fx, 1 - fx) * bw / ch                       # corner distance in course units
    cy = np.where(R[..., 3] < 0.5, fy, 1 - fy)
    chip = (R[..., 4] < 0.08) & (cx + cy < 0.3 + 0.2 * face)
    spall = (R[..., 5] < 0.03) & ~joint
    col = col * gray(0.9 + 0.12 * face - 0.25 * pits) * gray(0.82 + 0.18 * bevel)
    col = np.where(spall[..., None], np.array([0.52, 0.30, 0.20], np.float32) * gray(0.8 + 0.3 * face), col)
    mortar = np.array([0.50, 0.48, 0.45], np.float32) * gray(0.88 + 0.2 * tnoise(size, max(64, size // 4), 715))
    col = np.where(chip[..., None], col * 0.72, col)                            # chipped: broken, shadowed brick
    col = np.where(joint[..., None], mortar, col)
    col += 0.05 * gray(n - 0.5)
    eff = np.clip((tfbm(size, 707, octaves=4, base=8) - 0.66) * 4, 0, 1)[..., None] * 0.3
    col = col * (1 - eff) + np.array([0.70, 0.68, 0.64], np.float32) * eff
    col = weather(col, 709, dirt=0.22, desat=0.2, moss=0.05, streaks=0.15, spots=0.12)
    sj = 1.0 - np.clip((e - (m - 1.0)) / 2.0, 0, 1)                              # soft joint edge for the normals (perf D80 M2)
    h = 0.35 * bevel + 0.08 * face - 0.3 * pits - 0.9 * sj - 0.6 * chip - 0.5 * spall + 0.1 * n
    save(to_rgb(col), out, "sky_wall_brick_co")
    save(normal_from_height(h, 2.0), out, "sky_wall_brick_nohq")
    ao = to_rgb(gray(np.clip(1.0 - 0.35 * joint - 0.12 * (1 - bevel) - 0.2 * chip - 0.15 * spall, 0, 1)))
    ao.resize((min(size, 1024),) * 2, Image.BILINEAR).save(os.path.join(out, "sky_wall_brick_as.png"))


def wall_panel(size, out):
    """Precast concrete panels, 3.0 m sheet (2 x 2 panels of 1.5 m), joints weeping, tileable."""
    n = tfbm(size, 721, octaves=5, base=8)
    col = gray(0.64 + 0.06 * (n - 0.5))
    h = 0.15 * n
    j = max(3, size // 256)
    yy, xx = np.mgrid[0:size, 0:size]
    half = size // 2
    rng = np.random.default_rng(727)
    for py in (0, half):                                     # D80: each casting its own tone
        for px in (0, half):
            col[py:py + half, px:px + half] *= 0.94 + 0.12 * rng.random()
    pores = np.clip((tnoise(size, max(64, size // 6), 729) - 0.9) * 10, 0, 1)
    col *= gray(1 - 0.3 * pores)
    h -= 0.6 * pores
    ao = np.ones((size, size), np.float32)
    for cy in (half // 4, 3 * half // 4):                     # 4 lifting / tie sockets per panel
        for cx in (half // 4, 3 * half // 4):
            for oy in (0, half):
                for ox in (0, half):
                    hole = (yy - cy - oy) ** 2 + (xx - cx - ox) ** 2 < (size * 0.006) ** 2
                    col[hole] *= 0.55
                    h[hole] -= 0.9
                    ao[hole] *= 0.6
    de = np.minimum(np.minimum(xx % half, half - 1 - xx % half), np.minimum(yy % half, half - 1 - yy % half))
    chip = (de < j + max(2, size // 400)) & (tfbm(size, 731, octaves=3, base=16) > 0.68)   # chipped arrises at the joints
    col[chip] *= 0.82
    h[chip] -= 0.5
    for p in (0, half):
        col[:, p:p + j] *= 0.6
        col[p:p + j, :] *= 0.6
        h[:, p:p + j] -= 1
        h[p:p + j, :] -= 1
        ao[:, p:p + j] *= 0.6
        ao[p:p + j, :] *= 0.6
    below = ((yy % (size // 2)) / (size / 2.0)).astype(np.float32)          # 0 just under a joint
    st = np.repeat(tnoise(size, 64, 723, aspect=64)[:1, :], size, 0)
    weep = np.clip((st - 0.5) * 3, 0, 1) * np.clip(1 - below * 2.2, 0, 1) * 0.35
    col = col * (1 - gray(weep))
    col = weather(col, 725, dirt=0.2, desat=0.3, moss=0.05, streaks=0.12, spots=0.18)
    save(to_rgb(col), out, "sky_wall_panel_co")
    nh = normal_from_height(h, 2.5)
    save(nh.resize((max(1, size // 2),) * 2, Image.BILINEAR) if size > 1024 else nh, out, "sky_wall_panel_nohq")
    a = to_rgb(gray(0.75 + 0.25 * ao))                                           # D80: real AO (joints, sockets)
    a.resize((min(size, 512),) * 2, Image.BILINEAR).save(os.path.join(out, "sky_wall_panel_as.png"))      # 512 (perf D80 L1)


def wall_limestone(size, out):
    """Limestone ashlar, 3.0 m sheet: 4 courses of 0.75 m, blocks 1.0 / 0.75 m staggered, tileable.
    D82: bevelled arrises, tooled (drafted) faces, fossil specks, darker weathered blocks, a few lighter
    replacement blocks; soft joints in the height; real _as (512)."""
    rng = np.random.default_rng(741)
    n = tfbm(size, 743, octaves=5, base=12)
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    rows = _rows(size, 4)
    j = max(3, size // 375)
    col = np.zeros((size, size, 3), np.float32) + np.array([0.62, 0.60, 0.55], np.float32)   # mortar where no block lands
    e = np.zeros((size, size), np.float32)                                      # distance to the nearest joint (px)
    tone = np.ones((size, size), np.float32)
    for r in range(4):
        y0, y1 = rows[r], rows[r + 1]
        widths = [3, 2, 3, 2, 2] if r % 2 == 0 else [2, 3, 2, 3, 2]
        x0_ = (size // 16) * (r % 2)
        x = x0_
        cum = 0
        for w in widths:
            cum += w
            x1 = x0_ + int(round(cum * size / 12.0))                            # exact edges: no unwritten column (perf D82 M)
            k = rng.random()
            base = np.array([0.76, 0.72, 0.62], np.float32) * (0.93 + 0.1 * rng.random())
            if k < 0.08:
                base = np.array([0.84, 0.81, 0.72], np.float32)                 # newer replacement block
            elif k > 0.9:
                base = base * 0.86                                              # weathered, darker
            xs = np.arange(x, x1) % size
            col[y0:y1, xs] = base
            ex = np.minimum(np.arange(x1 - x) - 0.0, (x1 - x) - 1 - np.arange(x1 - x)).astype(np.float32)
            ey = np.minimum(np.arange(y1 - y0), (y1 - y0) - 1 - np.arange(y1 - y0)).astype(np.float32)
            e[y0:y1][:, xs] = np.minimum(ey[:, None], ex[None, :])
            x = x1
    joint = e < j / 2.0
    bevel = np.clip((e - j / 2.0) / (2.0 * j), 0, 1)
    tool = tstreak(size, max(64, size // 6), 16, 749)                              # drafted / tooled face
    fos = np.clip((tnoise(size, max(64, size // 10), 751) - 0.9) * 8, 0, 1)
    col = col * gray(0.9 + 0.1 * bevel) * gray(0.97 + 0.05 * (tool - 0.5)) * gray(1 - 0.18 * fos)
    col = np.where(joint[..., None], np.array([0.62, 0.60, 0.55], np.float32), col)
    col += 0.05 * gray(n - 0.5)
    col = weather(col, 747, dirt=0.2, desat=0.1, moss=0.06, streaks=0.14, spots=0.06)
    sj = 1.0 - np.clip((e - (j / 2.0 - 1.0)) / 2.0, 0, 1)
    h = 0.05 * n + 0.3 * bevel + 0.04 * tool - 0.2 * fos - 1.0 * sj
    save(to_rgb(col), out, "sky_wall_limestone_co")
    save(normal_from_height(h, 2.0), out, "sky_wall_limestone_nohq")
    ao = to_rgb(gray(np.clip(1.0 - 0.3 * joint - 0.1 * (1 - bevel), 0, 1)))
    ao.resize((min(size, 512),) * 2, Image.BILINEAR).save(os.path.join(out, "sky_wall_limestone_as.png"))


WALL_RENDER = {"cream": (0.78, 0.73, 0.60), "ochre": (0.72, 0.57, 0.38), "grey": (0.62, 0.62, 0.59), "white": (0.80, 0.79, 0.74)}


def wall_render(size, out):
    """Stucco in the 4 Chernarus colours, 4 m sheet, tileable: float texture, hairline cracks,
    plaster loss showing brick, grime, streaks and moss (one sheet per colour)."""
    fine = tfbm(size, 761, octaves=3, base=64)
    n = tfbm(size, 763, octaves=6, base=8)
    yy_i, xx_i = np.mgrid[0:size, 0:size]
    # D80: hairline crack network (masked periodic Voronoi) instead of sine bands; plaster loss with a dirty rim
    crack_s = crack_field(size, 769, cells=5, width=0.0025, warp=0.03) * np.clip((tfbm(size, 765, octaves=3, base=3) - 0.5) * 4, 0, 1)
    crack = crack_s > 0.35
    loss = tfbm(size, 767, octaves=5, base=6) > 0.72
    rim = (np.roll(loss, 3, 0) | np.roll(loss, -3, 0) | np.roll(loss, 3, 1) | np.roll(loss, -3, 1)) & ~loss
    bw, bh = max(4, size // 24), max(2, size // 80)
    mortar = ((yy_i % bh) < 2) | (((xx_i + (yy_i // bh % 2) * bw // 2) % bw) < 2)
    brick_rgb = np.where(mortar[..., None], np.array([0.50, 0.48, 0.44], np.float32), np.array([0.46, 0.27, 0.19], np.float32))
    for i, (name, rgb) in enumerate(WALL_RENDER.items()):
        col = np.array(rgb, np.float32) * (1 + 0.06 * gray(n - 0.5)) + 0.03 * gray(fine - 0.5)
        col[crack] *= 0.72
        col[rim] *= 0.8
        col = np.where(loss[..., None], brick_rgb, col)
        col = weather(col, 771 + i, dirt=0.18, desat=0.12, moss=0.08, streaks=0.2, spots=0.1)
        save(to_rgb(col), out, "sky_wall_render_%s_co" % name)
    # one nohq for the four colours (gen_configs SHARED_MAPS): float texture, cracks, the plaster step at losses
    h = 0.12 * fine + 0.05 * n - 0.7 * crack_s - 0.8 * loss - 0.3 * (loss & mortar) + 0.15 * rim
    nh = normal_from_height(h.astype(np.float32), 2.0)
    (nh.resize((1024, 1024), Image.BILINEAR) if size > 1024 else nh).save(os.path.join(out, "sky_wall_render_nohq.png"))


VEG_CELLS = ["grass", "weeds", "burdock", "shrub", "ivy", "ivy_hang", "birch_crown", "dead_branches",
             "bark", "litter", "moss", "sapling", "dry_grass", "reeds", "bramble", "ivy_dark"]   # 4 x 4, = skyspec.VEG_ATLAS


def vegetation(size, out):
    """Vegetation atlas (alpha-tested, 2048): 4 x 4 cells of 512 drawn procedurally - grass tufts,
    weeds, burdock, shrub mass, ivy (wall / hanging / dark), birch crown, dead branches, birch
    bark, leaf litter, moss, sapling, dry grass, reeds, bramble. Muted Chernarus greens and
    late-summer browns; every plant is original procedural drawing."""
    size = min(size, 2048)
    c = size // 4
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    rng = np.random.default_rng(601)

    def green(dark=0.0, dry=0.0):
        g = rng.uniform(0.32, 0.52) * (1 - dark)
        r = g * rng.uniform(0.55, 0.8) + dry * 0.25
        b = g * rng.uniform(0.25, 0.4)
        return tuple(int(255 * v) for v in (min(1, r), g, b)) + (255,)

    def box(i):
        col, row = i % 4, i // 4
        return col * c, row * c

    def blades(x0, y0, n, hmax, dry=0.0, width=3):
        for _ in range(n):
            bx = x0 + rng.uniform(0.05, 0.95) * c
            hh = rng.uniform(0.3, 1.0) * hmax
            lean = rng.normal(0, 0.15) * hh
            d.line([bx, y0 + c - 2, bx + lean * 0.5, y0 + c - hh * 0.5, bx + lean, y0 + c - hh], fill=green(0.1, dry), width=width)

    def leaves(x0, y0, cx, cy, rx, ry, n, rmin, rmax, dark=0.0, dry=0.0, ellipse=(1.0, 0.55)):
        for _ in range(n):
            a, rr = rng.uniform(0, 2 * np.pi), np.sqrt(rng.random())
            px, py = x0 + cx + np.cos(a) * rx * rr, y0 + cy + np.sin(a) * ry * rr
            r = rng.uniform(rmin, rmax)
            d.ellipse([px - r * ellipse[0], py - r * ellipse[1], px + r * ellipse[0], py + r * ellipse[1]], fill=green(dark, dry))

    for i, name in enumerate(VEG_CELLS):
        x0, y0 = box(i)
        if name == "grass":
            blades(x0, y0, 260, c * 0.9)
        elif name == "dry_grass":
            blades(x0, y0, 220, c * 0.8, dry=0.6)
        elif name == "reeds":
            blades(x0, y0, 120, c * 0.98, dry=0.3, width=5)
        elif name == "weeds":
            blades(x0, y0, 80, c * 0.6)
            leaves(x0, y0, c / 2, c * 0.55, c * 0.45, c * 0.35, 220, c / 60, c / 28)
        elif name == "burdock":
            for _ in range(14):
                px = x0 + rng.uniform(0.15, 0.85) * c
                py = y0 + rng.uniform(0.35, 0.9) * c
                r = rng.uniform(c / 14, c / 8)
                d.ellipse([px - r, py - r * 0.7, px + r, py + r * 0.7], fill=green(0.15))
                d.line([px, py, px, y0 + c - 2], fill=green(0.4), width=3)
        elif name == "shrub":                                                 # irregular lobes, not a disc
            for _l in range(7):
                lx, ly = c * rng.uniform(0.25, 0.75), c * rng.uniform(0.35, 0.75)
                leaves(x0, y0, lx, ly, c * rng.uniform(0.12, 0.24), c * rng.uniform(0.12, 0.22), 260, c / 90, c / 40)
        elif name in ("ivy", "ivy_dark"):
            # ragged outline: dense in the middle and at the bottom, thinning to the sides and the top,
            # per-column top edge, so a wall patch never shows the card's rectangle
            tops = value_noise(64, 6, 611 + i)[0]
            for _ in range(3200):
                fx, fy = rng.uniform(0, 1), rng.uniform(0, 1)                   # fy: 0 top -> 1 bottom
                top = 0.05 + 0.55 * tops[min(63, int(fx * 64))]
                side = 1.0 - abs(2 * fx - 1) ** 2.5
                if fy < top or rng.random() > side * (0.35 + 0.65 * fy):
                    continue
                px, py = x0 + fx * c, y0 + fy * c
                r = rng.uniform(c / 110, c / 55)
                d.ellipse([px - r, py - r * 0.8, px + r, py + r * 0.8], fill=green(0.35 if name == "ivy_dark" else 0.1))
        elif name == "ivy_hang":
            for _ in range(26):
                px = x0 + rng.uniform(0.05, 0.95) * c
                ln = rng.uniform(0.3, 1.0) * c
                for k in range(int(ln / 6)):
                    py = y0 + k * 6
                    r = rng.uniform(c / 110, c / 60)
                    jx = px + rng.normal(0, 2)
                    d.ellipse([jx - r, py - r, jx + r, py + r], fill=green(0.15))
        elif name == "birch_crown":                                           # loose, drooping lobes
            for _l in range(9):
                lx, ly = c * rng.uniform(0.2, 0.8), c * rng.uniform(0.15, 0.8)
                leaves(x0, y0, lx, ly, c * rng.uniform(0.1, 0.2), c * rng.uniform(0.12, 0.24), 230, c / 120, c / 60,
                       dry=0.15, ellipse=(1.0, 0.7))
            for _b in range(6):                                                # visible branches
                bx = x0 + c / 2 + rng.normal(0, c / 12)
                d.line([x0 + c / 2, y0 + c - 2, bx + rng.normal(0, c / 6), y0 + rng.uniform(0.2, 0.6) * c],
                       fill=(205, 200, 190, 255), width=4)
        elif name == "dead_branches":
            for _ in range(10):
                px, py = x0 + c / 2, y0 + c - 2
                ang = -np.pi / 2 + rng.normal(0, 0.5)
                w = 8
                for _k in range(10):
                    nx, ny = px + np.cos(ang) * c / 12, py + np.sin(ang) * c / 12
                    d.line([px, py, nx, ny], fill=(70, 60, 50, 255), width=max(1, w))
                    px, py, ang, w = nx, ny, ang + rng.normal(0, 0.35), w - 1
        elif name == "bark":
            d.rectangle([x0, y0, x0 + c, y0 + c], fill=(214, 210, 198, 255))
            for _ in range(160):
                py = y0 + rng.uniform(0, c)
                px = x0 + rng.uniform(0, c)
                d.rectangle([px, py, px + rng.uniform(c / 20, c / 6), py + rng.uniform(2, 6)], fill=(40, 38, 34, 255))
        elif name == "litter":
            for _ in range(700):
                px, py = x0 + rng.uniform(0, c), y0 + rng.uniform(0, c)
                r = rng.uniform(c / 90, c / 45)
                br = rng.uniform(0.3, 0.55)
                d.ellipse([px - r, py - r * 0.6, px + r, py + r * 0.6],
                          fill=(int(255 * br), int(255 * br * 0.75), int(255 * br * 0.4), 255))
        elif name == "moss":
            leaves(x0, y0, c / 2, c / 2, c * 0.48, c * 0.48, 3000, c / 200, c / 90, dark=0.2, ellipse=(1.0, 1.0))
        elif name == "sapling":
            d.line([x0 + c / 2, y0 + c - 2, x0 + c / 2, y0 + c * 0.25], fill=(200, 196, 186, 255), width=6)
            leaves(x0, y0, c / 2, c * 0.4, c * 0.3, c * 0.3, 600, c / 100, c / 50, dry=0.1)
        elif name == "bramble":
            for _ in range(30):
                px, py = x0 + rng.uniform(0.1, 0.9) * c, y0 + c - 2
                for _k in range(12):
                    nx, ny = px + rng.normal(0, c / 25), py - rng.uniform(c / 30, c / 14)
                    d.line([px, py, nx, ny], fill=(90, 55, 50, 255), width=3)
                    px, py = nx, ny
            leaves(x0, y0, c / 2, c * 0.6, c * 0.45, c * 0.35, 500, c / 90, c / 45, dark=0.25)
    img.save(os.path.join(out, "sky_vegetation_ca.png"))


def hq_facade(size, out):
    """HQ landmark facade atlas (4096, D60): V 0-0.25 brushed bronze (fins, mullions, cornice),
    0.25-0.5 ribbed bronze spandrel panels (4 x 1.5 m modules, seams, weathered patina at the
    bottom edge), 0.5-0.75 flamed dark granite (piers, plinth), 0.75-1 bronze louvre grille.
    Sheet = 6 m across. 4K: the HQ is the skyline landmark seen up close from the plaza."""
    size = 4096
    n = tfbm(size, 1201, octaves=5, base=16)
    streak = np.repeat(value_noise(size, 1024, 1203)[:, :1], size, 1)
    col = np.zeros((size, size, 3), np.float32)
    h = np.zeros((size, size), np.float32)
    spec = np.zeros((size, size), np.float32)
    gloss = np.zeros((size, size), np.float32)
    bronze = np.array([0.42, 0.30, 0.18], np.float32)
    yy, xx = np.mgrid[0:size, 0:size]
    r0, r1 = band_rows(size, 0.0, 0.25)                 # brushed bronze
    col[r0:r1] = bronze * (0.9 + 0.2 * (streak[r0:r1, :, None] - 0.5)) + 0.03 * gray(n[r0:r1] - 0.5)
    spec[r0:r1], gloss[r0:r1] = 0.75, 0.55
    h[r0:r1] = 0.05 * streak[r0:r1]
    r0, r1 = band_rows(size, 0.25, 0.5)                 # ribbed spandrel panels
    rib = ((xx[r0:r1] % (size // 64)) < (size // 128)).astype(np.float32)
    seam = ((xx[r0:r1] % (size // 4)) < 6) | ((yy[r0:r1] - r0) < 6) | ((r1 - yy[r0:r1]) < 6)
    col[r0:r1] = bronze * (0.8 + 0.15 * rib[..., None]) + 0.03 * gray(n[r0:r1] - 0.5)
    col[r0:r1][seam] *= 0.45
    h[r0:r1] = 0.4 * rib - 1.0 * seam
    pat = np.clip(((yy[r0:r1] - r0) / float(r1 - r0) - 0.6) * 2.5, 0, 1) * np.clip(tfbm(size, 1207, 4, 8)[r0:r1] * 1.4 - 0.3, 0, 1)
    col[r0:r1] = col[r0:r1] * (1 - pat[..., None] * 0.5) + np.array([0.28, 0.40, 0.33], np.float32) * pat[..., None] * 0.5
    spec[r0:r1], gloss[r0:r1] = 0.6 - 0.3 * pat, 0.45 - 0.2 * pat
    r0, r1 = band_rows(size, 0.5, 0.75)                 # flamed dark granite, 1.5 x 0.75 m slabs
    g = tfbm(size, 1211, octaves=6, base=48)[r0:r1]
    speck = (value_noise(size, 1024, 1213)[r0:r1] > 0.82).astype(np.float32)
    col[r0:r1] = gray(0.16 + 0.08 * (g - 0.5)) + 0.18 * gray(speck)
    joint = ((xx[r0:r1] % (size // 4)) < 4) | (((yy[r0:r1] - r0) % ((r1 - r0) // 2)) < 4)
    col[r0:r1][joint] = 0.35
    h[r0:r1] = 0.2 * g - 0.8 * joint
    spec[r0:r1], gloss[r0:r1] = 0.35, 0.5
    r0, r1 = band_rows(size, 0.75, 1.0)                 # louvre grille: blades every 1/32 of the band
    blade = (((yy[r0:r1] - r0) % ((r1 - r0) // 16)) / float((r1 - r0) // 16)).astype(np.float32)
    col[r0:r1] = bronze[None, None] * (0.35 + 0.65 * (1 - blade[..., None]))
    h[r0:r1] = 1 - blade
    spec[r0:r1], gloss[r0:r1] = 0.5, 0.4
    col = weather(col, 1217, dirt=0.12, desat=0.1, moss=0.0, streaks=0.1, spots=0.06)
    save(to_rgb(col), out, "sky_hq_facade_co")
    nh = normal_from_height(h, 2.0)
    save(nh.resize((size // 2,) * 2, Image.BILINEAR), out, "sky_hq_facade_nohq")
    sm = smdi(size, spec, gloss)
    save(sm.resize((size // 4,) * 2, Image.BILINEAR), out, "sky_hq_facade_smdi")


GENERATORS = {
    "concrete": concrete, "metal": metal, "glass": glass, "glassfar": glassfar,
    "tile": lambda s, o: tiled(s, o, "sky_tile", 5, (0.72, 0.71, 0.68), (0.45, 0.45, 0.43), max(3, s // 400), 41, 0.3, 0.5),
    "carpet": carpet, "wallpaper": wallpaper, "asphalt": asphalt,
    "roofmark": roofmark, "keycards": keycards,
    "paver": paver, "roadmark": roadmark, "rust": rust, "foliage": foliage, "atlas": atlas, "billboards": billboards,
    "decals": decals, "windows": windows, "brick": brick, "concpanel": concpanel,
    "wood": wood, "fabric": fabric, "ceiling": ceiling,
    "marble": marble, "parquet": parquet, "paint": paint, "stone": stone, "textile": textile,
    "render": render, "rubble": rubble, "signs": signs, "grime": grime, "vegetation": vegetation,
    "wall_brick": wall_brick, "wall_panel": wall_panel, "wall_limestone": wall_limestone, "wall_render": wall_render,
    "hq_facade": hq_facade, "signs2": signs2, "fair": fair, "trash": trash, "turf": turf,
    "fur": lambda s, o: fur(min(s, 1024), o),                                  # D65 creatures
    "signs3": signs3,                                                          # D66 underground signs
    "signs4": signs4,                                                          # D69 venue variants
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--size", type=int, default=2048)
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    if a.size & (a.size - 1):
        raise SystemExit("--size must be a power of two")
    os.makedirs(a.out, exist_ok=True)
    only = [x for x in a.only.split(",") if x]
    for name, fn in GENERATORS.items():
        if only and name not in only:
            continue
        fn(a.size, a.out)
        print("generated", name)


if __name__ == "__main__":
    main()
