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
    gy, gx = np.gradient(h)
    nx, ny, nz = -gx * strength, -gy * strength, np.ones_like(h)
    n = np.sqrt(nx * nx + ny * ny + nz * nz)
    rgb = np.stack([nx / n, ny / n, nz / n], -1) * 0.5 + 0.5
    return Image.fromarray((rgb * 255).astype(np.uint8), "RGB")


def to_rgb(arr):
    return Image.fromarray(np.clip(arr * 255, 0, 255).astype(np.uint8), "RGB")


def gray(arr):
    return np.repeat(arr[..., None], 3, -1)


CONST_SIZE = 256   # constant-value maps don't need full resolution


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
    n = fbm(size, 11)
    fine = fbm(size, 17, octaves=3, base=64)
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
    grain = value_noise(size, 256, 23)
    col[r0:r1, :] += 0.04 * (np.repeat(grain[r0:r1, :1], size, 1) - 0.5)
    # Band 3 (reveal, V 0.75-1): smooth with one recessed groove.
    r0, r1 = band_rows(size, 0.75, 1.0)
    g0 = r0 + (r1 - r0) // 2
    h[g0:g0 + seam * 3, :] -= 1.0
    ao[g0:g0 + seam * 3, :] *= 0.65
    h += 0.15 * fine
    save(to_rgb(gray(col)), out, "sky_concrete_co")
    save(normal_from_height(h, 2.5), out, "sky_concrete_nohq")
    save(smdi(size, 0.12 + 0.05 * fine, 0.25), out, "sky_concrete_smdi")
    save(to_rgb(gray(0.75 + 0.25 * ao)), out, "sky_concrete_as")


def metal(size, out):
    streak = np.repeat(value_noise(size, 512, 31)[:, :1], size, 1)
    n = fbm(size, 37, octaves=3, base=16)
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
    r0, r1 = band_rows(size, 0.75, 1.0)         # painted panel (warm grey)
    col[r0:r1] = np.array([0.62, 0.60, 0.56]) + 0.03 * gray(n[r0:r1] - 0.5)
    spec[r0:r1], gloss[r0:r1] = 0.25, 0.35
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


def asphalt(size, out):
    n = fbm(size, 83, octaves=6, base=8)
    grit = (np.random.default_rng(89).random((size, size)) > 0.985).astype(np.float32)
    col = gray(0.20 + 0.06 * (n - 0.5) + 0.12 * grit)
    save(to_rgb(col), out, "sky_asphalt_co")
    save(normal_from_height(0.4 * n + 0.6 * grit, 2.0), out, "sky_asphalt_nohq")
    save(smdi(size, 0.06 + 0.1 * grit, 0.1), out, "sky_asphalt_smdi")
    save(to_rgb(gray(np.full((CONST_SIZE, CONST_SIZE), 0.95, np.float32))), out, "sky_asphalt_as")


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
def paver(size, out):
    """Sidewalk pavers: 30 x 30 cm stone blocks (mapped at 3 m -> 10 x 10 per tile)."""
    tiled(size, out, "sky_paver", 10, (0.62, 0.60, 0.57), (0.36, 0.35, 0.33), max(3, size // 512), 101, 0.15, 0.25, tile_var=0.08)
    p = os.path.join(out, "sky_paver_as.png")                 # AO at 1024 is plenty (perf M5)
    Image.open(p).resize((min(size, 1024),) * 2, Image.BILINEAR).save(p)


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
    """Brick facade trim: V 0-0.6 running bond, 0.6-0.8 soldier course, 0.8-1 stone sill."""
    n = fbm(size, 181, octaves=4, base=8)
    col = np.zeros((size, size, 3), np.float32)
    h = 0.1 * n
    ao = np.ones((size, size), np.float32)
    rng = np.random.default_rng(191)
    mortar = np.array([0.55, 0.53, 0.50], np.float32)
    r0, r1 = band_rows(size, 0.0, 0.6)
    # 16 bricks across U; with MATERIALS["brick"]["sheet_m"] = 3.44 m per U tile a brick is
    # 21.5 x 6.6 cm at ~595 px/m (perf batch-2 L3).
    bw, bh = size // 16, size // 52
    for row, y in enumerate(range(r0, r1, bh)):
        off = (bw // 2) * (row % 2)
        for x in range(-bw, size, bw):
            tint = np.array([0.45, 0.22, 0.15]) * (0.8 + 0.4 * rng.random())
            xa, xb = max(0, x + off + 2), min(size, x + off + bw - 2)
            if xb > xa:
                col[y + 2:min(y + bh - 2, r1), xa:xb] = tint
        col[y:y + 2, :] = mortar
        h[y:y + 2, :] -= 0.8
        ao[y:y + 2, :] *= 0.8
    m = col[r0:r1].sum(-1) == 0
    col[r0:r1][m] = mortar
    r0, r1 = band_rows(size, 0.6, 0.8)                   # soldier course
    for x in range(0, size, bh):
        tint = np.array([0.40, 0.20, 0.14]) * (0.85 + 0.3 * rng.random())
        col[r0 + 2:r1 - 2, x + 2:x + bh - 2] = tint
    col[r0:r1][col[r0:r1].sum(-1) == 0] = mortar
    r0, r1 = band_rows(size, 0.8, 1.0)                   # stone sill
    col[r0:r1] = np.array([0.66, 0.64, 0.60]) + 0.04 * gray(n[r0:r1] - 0.5)
    col += 0.04 * gray(n - 0.5)
    col *= gray(0.8 + 0.2 * ao)          # AO folded into _co; _as/_smdi are procedural (perf batch-2 M1)
    save(to_rgb(col), out, "sky_brick_co")
    save(normal_from_height(h, 2.0), out, "sky_brick_nohq")


def concpanel(size, out):
    """Precast concrete panel facade: 2 x 2 panels per sheet with deep window
    reveal band at the top (V 0-0.2) and panel joints."""
    n = fbm(size, 197, octaves=5, base=8)
    col = gray(0.66 + 0.06 * (n - 0.5))
    h = 0.15 * n
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
    save(to_rgb(col), out, "sky_concpanel_co")
    # mostly low-frequency relief: half-size normal map keeps >= 4 px joints (perf batch-2 L4)
    nh = normal_from_height(h, 2.5)
    save(nh.resize((max(1, size // 2),) * 2, Image.BILINEAR) if size > 1024 else nh, out, "sky_concpanel_nohq")


# ------------------------------------------------------------------ batch 3: interior props
def wood(size, out):
    """Furniture wood trim (1024): V 0-0.4 oak, 0.4-0.7 walnut, 0.7-0.95 grey laminate,
    0.95-1 monitor screen (keeps desk monitors in the wood section, perf batch-3 L1)."""
    size = min(size, 1024)
    y = np.linspace(0, 1, size, dtype=np.float32)[:, None]
    x = np.linspace(0, 1, size, dtype=np.float32)[None, :]
    n = fbm(size, 211, octaves=4, base=4)
    grain = 0.5 + 0.5 * np.sin((x * 60 + 6 * n) * np.pi)          # long grain along U
    col = np.zeros((size, size, 3), np.float32)
    for (v0, v1), base, amp in [((0.0, 0.4), (0.62, 0.45, 0.28), 0.10),
                                ((0.4, 0.7), (0.36, 0.23, 0.15), 0.08),
                                ((0.7, 0.95), (0.58, 0.58, 0.56), 0.02),
                                ((0.95, 1.0), (0.10, 0.16, 0.24), 0.0)]:
        r0, r1 = band_rows(size, v0, v1)
        col[r0:r1] = np.array(base, np.float32) + amp * gray(grain[r0:r1] - 0.5) + 0.03 * gray(n[r0:r1] - 0.5)
    save(to_rgb(col), out, "sky_wood_co")              # nohq/smdi/as procedural (perf batch-3 L4)


def fabric(size, out):
    """Upholstery trim (512): V 0-0.33 grey, 0.33-0.66 blue, 0.66-1 beige weave."""
    size = min(size, 512)
    yy, xx = np.mgrid[0:size, 0:size]
    weave = (((xx // 4) + (yy // 4)) % 2).astype(np.float32)        # 8 px period survives mip 1 (perf L4)
    n = fbm(size, 223, octaves=3, base=8)
    col = np.zeros((size, size, 3), np.float32)
    for (v0, v1), base in [((0.0, 0.33), (0.42, 0.42, 0.44)), ((0.33, 0.66), (0.20, 0.28, 0.45)),
                           ((0.66, 1.0), (0.66, 0.60, 0.50))]:
        r0, r1 = band_rows(size, v0, v1)
        col[r0:r1] = np.array(base, np.float32) * (0.92 + 0.08 * gray(weave[r0:r1])) + 0.04 * gray(n[r0:r1] - 0.5)
    save(to_rgb(col), out, "sky_fabric_co")
    save(normal_from_height(0.3 * weave + 0.2 * n, 1.0), out, "sky_fabric_nohq")


# ------------------------------------------------------------------ realism pass (D53)
def ceiling(size, out):
    """Suspended ceiling (1024, sheet = MATERIALS["ceiling"]["sheet_m"] = 2.4 m): 4 x 4 grid of
    0.6 m mineral tiles on a white T-bar grid, one 0.6 x 1.2 m recessed light panel per sheet."""
    size = min(size, 1024)
    n = fbm(size, 241, octaves=4, base=16)
    col = gray(0.86 + 0.05 * (n - 0.5))
    h = 0.2 * n
    rng = np.random.default_rng(251)
    speck = rng.random((size, size)) < 0.04                     # fissured mineral tile
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
    x0, y0 = t + g, t + g                                        # light panel over tiles (1,1)-(1,2)
    x1, y1 = 2 * t - g, 3 * t - g
    col[y0:y1, x0:x1] = 0.98
    for yy in range(y0 + t // 8, y1, t // 4):                    # prismatic louvres
        col[yy:yy + 2, x0:x1] = 0.8
    h[y0:y1, x0:x1] -= 0.6
    save(to_rgb(col), out, "sky_ceiling_co")
    save(normal_from_height(h, 1.5), out, "sky_ceiling_nohq")


GENERATORS = {
    "concrete": concrete, "metal": metal, "glass": glass, "glassfar": glassfar,
    "tile": lambda s, o: tiled(s, o, "sky_tile", 5, (0.72, 0.71, 0.68), (0.45, 0.45, 0.43), max(3, s // 400), 41, 0.3, 0.5),
    "carpet": carpet, "wallpaper": wallpaper, "asphalt": asphalt,
    "roofmark": roofmark, "keycards": keycards,
    "paver": paver, "roadmark": roadmark, "rust": rust, "foliage": foliage, "atlas": atlas, "billboards": billboards,
    "decals": decals, "windows": windows, "brick": brick, "concpanel": concpanel,
    "wood": wood, "fabric": fabric, "ceiling": ceiling,
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
