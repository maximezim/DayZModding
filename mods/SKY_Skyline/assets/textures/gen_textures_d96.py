"""D96 texture pass: realistic replacements for the sheets that read as flat or cartoon in the first in-game test
(TESTING CT-13) and new sheets for the detail uplift. Imported by gen_textures.py (GENERATORS); deterministic.

    wall_render  exterior plaster in the four Chernarus colours (4 m sheet): trowelled float finish, patch repairs in
                 a slightly different tone, hairline cracks, rare small spalls showing brick, soft soot / wash-down
                 (no vertical banding, no cartoon brick blobs)
    rooftile     clay pantiles (4 x 4 m sheet, tileable both ways: roofs are mapped along the slope at world scale)
    roofslate    natural slate, 4 x 4 m sheet
    facadekit    door / shutter atlas (2048): 4 x 2 cells of 512 x 1024 px drawn as height fields (panels, mouldings,
                 louvres, boards, ironmongery) with baked occlusion, matching _nohq and _smdi
    rust         painted metal with chipped edges, rust bloom at the chips and vertical rust runs (no camouflage blobs)
"""
import os
import sys

import numpy as np
from PIL import Image

from gen_textures import gray, normal_from_height, save, smdi, tfbm, tnoise, to_rgb, tstreak

WALL_RENDER = {"cream": (0.78, 0.73, 0.60), "ochre": (0.73, 0.58, 0.40), "grey": (0.63, 0.63, 0.60),
               "white": (0.82, 0.81, 0.77)}


def blur(a, r):
    """Separable box blur with wrap (tileable), r px."""
    if r < 1:
        return a
    k = 2 * r + 1
    for ax in (0, 1):
        c = np.cumsum(np.concatenate([np.take(a, range(-r - 1, 0), axis=ax), a, np.take(a, range(0, r), axis=ax)], ax), ax)
        sl_hi = [slice(None)] * a.ndim
        sl_lo = [slice(None)] * a.ndim
        sl_hi[ax] = slice(k, None)
        sl_lo[ax] = slice(0, -k)
        a = (c[tuple(sl_hi)] - c[tuple(sl_lo)]) / k
    return a


def bake_light(col, h, strength, k=0.35):
    """Soft top-left key light from the height field, multiplied into the colour: panels, louvres, tile rolls read
    in the colour map too (the game's normal map adds the view-dependent part)."""
    gx = 0.5 * (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * strength
    gy = 0.5 * (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * strength
    nz = 1.0 / np.sqrt(gx * gx + gy * gy + 1.0)
    nx, ny = -gx * nz, -gy * nz
    lx, ly, lz = -0.45, -0.55, 0.70
    d = np.clip(nx * lx + ny * ly + nz * lz, 0, 1) / lz
    return col * np.clip(1.0 - k + k * d, 0.4, 1.3)[..., None]


def voronoi_cells(size, n, seed):
    """Tileable Voronoi: (cell id, distance to nearest seed, distance to second) on a size x size grid (n seeds)."""
    rng = np.random.default_rng(seed)
    pts = rng.random((n, 2)) * size
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    d1 = np.full((size, size), 1e9, np.float32)
    d2 = np.full((size, size), 1e9, np.float32)
    idx = np.zeros((size, size), np.int32)
    for i, (px, py) in enumerate(pts):
        dx = np.abs(xx - px)
        dx = np.minimum(dx, size - dx)
        dy = np.abs(yy - py)
        dy = np.minimum(dy, size - dy)
        d = np.sqrt(dx * dx + dy * dy)
        closer = d < d1
        d2 = np.where(closer, d1, np.minimum(d2, d))
        idx = np.where(closer, i, idx)
        d1 = np.where(closer, d, d1)
    return idx, d1, d2


# ------------------------------------------------------------------ plaster
def wall_render(size, out):
    """Exterior plaster, 4 m sheet (512 px/m at 2048), tileable; one colour map per Chernarus colour, one shared nohq."""
    fine = tnoise(size, size // 2, 9601)                                       # sand grain (2 px)
    grain = tfbm(size, 9603, octaves=3, base=size // 16)
    trowel_a = tfbm(size, 9605, octaves=4, base=6)                             # broad float strokes
    trowel = blur(tfbm(size, 9607, octaves=3, base=24), 4)
    low = tfbm(size, 9611, octaves=5, base=3)
    # patch repairs: soft-edged blocks of newer plaster (a tone apart, smoother)
    cid, d1, d2 = voronoi_cells(size, 9, 9613)
    rng = np.random.default_rng(9615)
    patch_on = rng.random(9) < 0.35
    patch = blur((patch_on[cid] & (tfbm(size, 9617, 4, 4) > 0.42)).astype(np.float32), 10)
    # hairline cracks: Voronoi edges, masked to a few regions, thin
    _c, e1, e2 = voronoi_cells(size, 22, 9619)
    crack = np.clip(1.0 - (e2 - e1) / 2.2, 0, 1) * np.clip((tfbm(size, 9621, 3, 3) - 0.56) * 6, 0, 1)
    # rare spalls showing brick (small, with a broken, dark rim)
    spall_f = tfbm(size, 9623, octaves=5, base=10)
    spall = spall_f > 0.80
    rim = blur(spall.astype(np.float32), 3) > 0.02
    rim &= ~spall
    bw, bh = size // 16, size // 54                                             # 25 x 7.4 cm bricks at 4 m / sheet
    yy, xx = np.mgrid[0:size, 0:size]
    mortar = ((yy % bh) < 3) | (((xx + (yy // bh % 2) * bw // 2) % bw) < 3)
    btone = tnoise(size, 64, 9625)
    brick = np.where(mortar[..., None], np.array([0.55, 0.53, 0.49], np.float32),
                     np.array([0.50, 0.31, 0.22], np.float32) * (0.85 + 0.3 * btone[..., None]))
    # soot / wash-down: soft, broad, low contrast; dirt collects under nothing in particular (the decals do edges)
    wash = blur(np.clip((tstreak(size, 6, 48, 9627) - 0.5) * 1.5, 0, 1), 24) * low * 0.6
    mottle = tfbm(size, 9629, octaves=4, base=5)                                # warm / cool mottling
    h_pl = (0.35 * trowel_a + 0.25 * trowel + 0.18 * grain + 0.12 * fine - 1.2 * crack - 1.6 * spall + 0.2 * rim).astype(np.float32)
    shade = (1.0 - 0.07 * (low - 0.5) - 0.035 * (trowel_a - 0.5) - 0.03 * (grain - 0.5) - 0.025 * (fine - 0.5)
             - 0.06 * wash - 0.05 * crack)
    for name, rgb in WALL_RENDER.items():
        base = np.array(rgb, np.float32)
        newer = base * np.array([1.03, 1.02, 1.0], np.float32)                 # patch plaster: fresher, cooler
        col = base * (1 - patch[..., None]) + newer * patch[..., None]
        col = col * shade[..., None]
        col = col * (1 + 0.03 * (mottle[..., None] - 0.5) * np.array([1.0, 0.2, -0.8], np.float32))
        g = col.mean(-1, keepdims=True)                                         # dirt desaturates a little
        col = col * (1 - 0.15 * wash[..., None]) + g * 0.15 * wash[..., None]
        col = np.where(rim[..., None], col * 0.82, col)
        col = np.where(spall[..., None], brick, col)
        col = bake_light(col, h_pl, 3.0, 0.12)
        save(to_rgb(col), out, "sky_wall_render_%s_co" % name)
    h = (0.35 * trowel_a + 0.25 * trowel + 0.18 * grain + 0.12 * fine - 0.25 * patch * (grain - 0.5)
         - 1.2 * crack - 1.6 * spall - 0.5 * (spall & mortar) + 0.2 * rim)
    nh = normal_from_height(h.astype(np.float32), 3.0)
    (nh.resize((1024, 1024), Image.LANCZOS) if size > 1024 else nh).save(os.path.join(out, "sky_wall_render_nohq.png"))


# ------------------------------------------------------------------ roofs
def rooftile(size, out):
    """Clay pantiles, 4 x 4 m sheet (12 courses x 19 tiles), tileable in U and V. Each tile: S-profile across its
    width (roll + pan), overlap shadow at its foot, per-tile firing tone, lichen and soot; the course above casts a
    soft shadow on the one below. V runs down the slope (row 0 at the ridge side)."""
    rng = np.random.default_rng(9701)
    nc, nt = 12, 19
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    ch = size / nc
    tw = size / nt
    row = np.floor(yy / ch).astype(int)
    off = (row % 2) * 0.0                                                        # pantiles align (no stagger)
    t_in = (yy - row * ch) / ch                                                  # 0 top (under the course above) -> 1 foot
    col_i = np.floor((xx + off * tw) / tw).astype(int) % nt
    s = ((xx + off * tw) / tw) % 1.0                                             # 0..1 across the tile
    prof = np.where(s < 0.62, -np.cos((s / 0.62) * np.pi) * 0.5 + 0.5, 0.5 + 0.5 * np.cos(((s - 0.62) / 0.38) * np.pi))
    prof = 1.0 - prof                                                           # pan low, roll high
    roll = np.clip((s - 0.62) / 0.38, 0, 1)
    roll = np.sin(roll * np.pi)
    height = 0.55 * (1 - s) * (s < 0.62) + 0.9 * roll
    foot = np.clip((t_in - 0.9) / 0.1, 0, 1)                                    # the visible thick foot of the tile
    shadow = np.clip(1.0 - t_in / 0.18, 0, 1) ** 1.5                            # under the course above
    tone = rng.random((nc, nt)).astype(np.float32)
    tile_tone = tone[row % nc, col_i]
    hue = rng.random((nc, nt)).astype(np.float32)[row % nc, col_i]
    base = (np.array([0.58, 0.30, 0.18], np.float32) * (1 - hue[..., None] * 0.35)
            + np.array([0.45, 0.32, 0.25], np.float32) * hue[..., None] * 0.35)
    base = base * (0.82 + 0.3 * tile_tone[..., None])
    n = tfbm(size, 9703, octaves=5, base=8)
    fine = tnoise(size, size // 3, 9705)
    lichen = np.clip((tfbm(size, 9707, octaves=5, base=24) - 0.74) * 4, 0, 1) * (0.4 + 0.4 * t_in) * 0.7
    soot = np.clip((tfbm(size, 9709, octaves=4, base=4) - 0.45) * 1.5, 0, 1)
    col = base * (1 - 0.18 * soot[..., None]) * (0.92 + 0.12 * fine[..., None]) * (0.95 + 0.1 * n[..., None])
    col = col * (0.72 + 0.28 * (0.4 + 0.6 * height))[..., None]                 # crest lit, pan darker
    col = col * (1 - 0.55 * shadow[..., None])
    col = col * (1 - 0.25 * foot[..., None] * (1 - roll[..., None]))
    col = col * (1 - lichen[..., None]) + np.array([0.55, 0.52, 0.36], np.float32) * lichen[..., None] * (0.85 + 0.2 * fine[..., None])
    edge = (np.abs(s - 0.0) < 0.012) | (s > 0.988)
    col = np.where(edge[..., None], col * 0.6, col)
    h = 1.6 * height - 2.2 * shadow + 0.6 * foot + 0.06 * fine + 0.3 * lichen
    col = bake_light(col, blur(h.astype(np.float32), 2), 6.0, 0.5)
    save(to_rgb(col), out, "sky_rooftile_co")
    save(normal_from_height(h.astype(np.float32), 6.0), out, "sky_rooftile_nohq")
    save(smdi(min(size, 512), 0.18, 0.25), out, "sky_rooftile_smdi")


def roofslate(size, out):
    """Natural slate, 4 x 4 m sheet: 16 courses (25 cm gauge) of 50 cm wide slates, half-bond, tileable; riven
    surface, a few chipped corners and lighter replacement slates, damp darker feet."""
    rng = np.random.default_rng(9721)
    nc, ns = 16, 8
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    ch, sw = size / nc, size / ns
    row = np.floor(yy / ch).astype(int)
    xo = xx + (row % 2) * sw / 2
    cidx = np.floor(xo / sw).astype(int) % ns
    s = (xo / sw) % 1.0
    t_in = (yy - row * ch) / ch
    tone = rng.random((nc, ns)).astype(np.float32)[row % nc, cidx]
    riven = blur(tstreak(size, 12, 220, 9723), 2)
    fine = tnoise(size, size // 3, 9725)
    base = np.array([0.24, 0.25, 0.28], np.float32) * (0.85 + 0.35 * tone[..., None])
    repl = rng.random((nc, ns))[row % nc, cidx] < 0.05
    base = np.where(repl[..., None], np.array([0.33, 0.33, 0.35], np.float32), base)
    shadow = np.clip(1.0 - t_in / 0.14, 0, 1) ** 1.5
    joint = (s < 0.01) | (s > 0.99)
    col = base * (0.9 + 0.2 * riven[..., None]) * (0.95 + 0.08 * fine[..., None])
    col = col * (1 - 0.5 * shadow[..., None]) * (1 - 0.1 * t_in[..., None])
    col = np.where(joint[..., None], col * 0.45, col)
    lich = np.clip((tfbm(size, 9727, 5, 20) - 0.76) * 4, 0, 1) * 0.6
    col = col * (1 - lich[..., None]) + np.array([0.55, 0.56, 0.45], np.float32) * lich[..., None]
    h = 0.6 * t_in + 0.25 * riven + 0.05 * fine - 1.6 * shadow - 1.0 * joint
    col = bake_light(col, blur(h.astype(np.float32), 1), 5.0, 0.4)
    save(to_rgb(col), out, "sky_roofslate_co")
    save(normal_from_height(h.astype(np.float32), 5.0), out, "sky_roofslate_nohq")
    save(smdi(min(size, 512), 0.35, 0.45), out, "sky_roofslate_smdi")


# ------------------------------------------------------------------ doors and shutters
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from skyspec import FACADEKIT  # noqa: E402  (cell -> (column, row) in the 4 x 2 grid; each cell 1 : 2, U : V)


def _bevel_rect(h, x0, y0, x1, y1, depth, bevel, sign=1.0):
    """Add a raised (sign 1) or sunk (-1) panel with a linear bevel to height h (in place)."""
    H, W = h.shape
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    d = np.minimum(np.minimum(xx - x0, x1 - xx), np.minimum(yy - y0, y1 - yy))
    m = np.clip(d / bevel, 0, 1)
    h += sign * depth * m * (d >= 0)
    return d >= 0


def _cell(name, cw, chh, rng):
    """(rgb, height, spec, gloss) for one cell of cw x chh px."""
    H, W = chh, cw
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    h = np.zeros((H, W), np.float32)
    fine = tnoise(max(H, W), max(H, W) // 3, int(rng.integers(1 << 30)))[:H, :W]
    grain = tstreak(max(H, W), 40, 600, int(rng.integers(1 << 30)))[:H, :W]   # vertical wood grain (V runs down)
    grain = grain.T[:H, :W] if False else grain
    spec = np.full((H, W), 0.1, np.float32)
    gloss = np.full((H, W), 0.2, np.float32)
    fx, fy = W / 1.0, H / 2.1                                                  # px per metre (door 1.0 x 2.1 m)
    if name.startswith("door_") and name != "door_shop":
        frame = 0.07
        h += 0.2
        if name in ("door_green", "door_oak"):
            rails = [(0.12, 0.62), (0.75, 1.30), (1.43, 1.98)] if name == "door_green" else [(0.12, 0.92), (1.05, 1.98)]
            panes = []
            for (a, b) in rails:
                for (c0, c1) in ((0.12, 0.47), (0.53, 0.88)):
                    _bevel_rect(h, c0 * fx, a * fy, c1 * fx, b * fy, -0.25, 0.04 * fx)
                    _bevel_rect(h, (c0 + 0.05) * fx, (a + 0.05) * fy, (c1 - 0.05) * fx, (b - 0.05) * fy, 0.18, 0.03 * fx)
                    panes.append((c0, a, c1, b))
            if name == "door_oak":                                             # glazed top panels
                glass = ((yy > 0.12 * fy) & (yy < 0.92 * fy) & (((xx > 0.17 * fx) & (xx < 0.42 * fx)) | ((xx > 0.58 * fx) & (xx < 0.83 * fx))))
            else:
                glass = np.zeros_like(h, bool)
            if name == "door_green":
                paint = np.array([0.16, 0.27, 0.22], np.float32)
                chip = np.clip((tfbm(max(H, W), 9741, 5, 24)[:H, :W] - 0.72) * 6, 0, 1)
                col = paint * (0.9 + 0.15 * fine[..., None]) * (1 - chip[..., None]) + np.array([0.42, 0.33, 0.22], np.float32) * chip[..., None]
                spec[:], gloss[:] = 0.25, 0.35
            else:
                ring = np.sin(xx / W * 60 + 9 * grain) * 0.5 + 0.5
                col = np.array([0.36, 0.22, 0.12], np.float32) * (0.8 + 0.25 * ring[..., None]) * (0.92 + 0.1 * fine[..., None])
                spec[:], gloss[:] = 0.3, 0.5
            col = np.where(glass[..., None], np.array([0.06, 0.08, 0.10], np.float32) + 0.04 * fine[..., None], col)
            h[glass] = -0.3
            spec[glass], gloss[glass] = 0.8, 0.9
        elif name == "door_steel":
            _bevel_rect(h, 0.08 * fx, 0.1 * fy, 0.92 * fx, 2.0 * fy, -0.08, 0.02 * fx)
            lv = (yy > 1.55 * fy) & (yy < 1.9 * fy) & (xx > 0.25 * fx) & (xx < 0.75 * fx)
            slat = ((yy / (0.025 * fy)) % 1.0)
            h[lv] = (-0.4 + 0.5 * slat)[lv]
            rust = np.clip((tfbm(max(H, W), 9743, 5, 16)[:H, :W] - 0.7) * 4, 0, 1) * (0.4 + 0.6 * yy / H)
            col = np.array([0.40, 0.42, 0.42], np.float32) * (0.93 + 0.1 * fine[..., None])
            col = col * (1 - rust[..., None]) + np.array([0.36, 0.20, 0.11], np.float32) * rust[..., None]
            spec[:], gloss[:] = 0.35 - 0.2 * rust, 0.35 - 0.2 * rust
        else:                                                                  # ledged boards, weathered
            nb = 7
            bx = (xx / W * nb) % 1.0
            gap = (bx < 0.03) | (bx > 0.97)
            h += 0.08 * grain - 0.5 * gap
            for (a, b) in ((0.2, 0.32), (0.95, 1.07), (1.7, 1.82)):              # ledges
                _bevel_rect(h, 0.02 * fx, a * fy, 0.98 * fx, b * fy, 0.35, 0.01 * fx)
            tone = np.floor(xx / W * nb)
            col = np.array([0.43, 0.38, 0.31], np.float32) * (0.82 + 0.06 * (tone % 3)[..., None]) * (0.85 + 0.25 * grain[..., None])
            col = np.where(gap[..., None], col * 0.3, col)
        # handle + lock plate
        hp = (np.abs(xx - 0.85 * fx) < 0.02 * fx) & (np.abs(yy - 1.05 * fy) < 0.12 * fy)
        h[hp] += 0.5
        col = np.where(hp[..., None], np.array([0.55, 0.50, 0.40], np.float32), col)
        spec[hp], gloss[hp] = 0.7, 0.7
        _ = frame
    elif name == "door_shop":
        h += 0.3
        g = (xx > 0.09 * fx) & (xx < 0.91 * fx) & (yy > 0.09 * fy) & (yy < 1.75 * fy)
        h[g] = 0.0
        bar = (np.abs(yy - 1.05 * fy) < 0.025 * fy) & g
        h[bar] = 0.35
        col = np.array([0.62, 0.63, 0.64], np.float32) * (0.95 + 0.06 * fine[..., None])
        col = np.where(g[..., None], np.array([0.08, 0.10, 0.12], np.float32) + 0.05 * (yy / H)[..., None], col)
        col = np.where(bar[..., None], np.array([0.70, 0.70, 0.71], np.float32), col)
        spec[:], gloss[:] = 0.5, 0.6
        spec[g], gloss[g] = 0.9, 0.95
    else:                                                                       # louvred shutter, 0.5 x 1.4 m in the cell
        sx, sy = W / 0.5, H / 1.4
        paint = {"shutter_sage": (0.47, 0.55, 0.45), "shutter_brown": (0.33, 0.22, 0.14), "shutter_blue": (0.30, 0.40, 0.50)}[name]
        st = 0.06
        h += 0.5
        inner = (xx > st * sx) & (xx < (0.5 - st) * sx) & (yy > st * sy) & (yy < (1.4 - st) * sy)
        mid = np.abs(yy - 0.7 * sy) < 0.04 * sy
        lou = inner & ~mid
        slat = ((yy - st * sy) / (0.045 * sy)) % 1.0
        h[lou] = (0.1 + 0.6 * slat)[lou]                                       # each slat tilts: dark gap at its foot
        shade = np.where(lou, 0.55 + 0.45 * slat, 1.0)
        chip = np.clip((tfbm(max(H, W), 9745, 5, 20)[:H, :W] - 0.70) * 5, 0, 1)
        col = np.array(paint, np.float32) * shade[..., None] * (0.92 + 0.1 * fine[..., None])
        col = col * (1 - chip[..., None]) + np.array([0.45, 0.38, 0.30], np.float32) * chip[..., None] * shade[..., None]
        col = np.where((lou & (slat > 0.92))[..., None], col * 0.35, col)
        spec[:], gloss[:] = 0.15, 0.25
    # baked occlusion from the height field (cavities darker)
    occ = np.clip(1.0 - 1.2 * np.clip(blur(h, max(2, W // 64)) - h, 0, 1), 0.45, 1.0)
    col = col * occ[..., None]
    col = bake_light(col, blur(h, 1), 40.0, 0.45)
    return col, h, spec, gloss


def facadekit(size, out):
    size = 2048
    cw, ch = size // 4, size // 2
    col = np.zeros((size, size, 3), np.float32)
    h = np.zeros((size, size), np.float32)
    sp = np.zeros((size, size), np.float32)
    gl = np.zeros((size, size), np.float32)
    rng = np.random.default_rng(9731)
    for name, (cx, cy) in FACADEKIT.items():
        c, hh, s, g = _cell(name, cw, ch, rng)
        col[cy * ch:(cy + 1) * ch, cx * cw:(cx + 1) * cw] = c
        h[cy * ch:(cy + 1) * ch, cx * cw:(cx + 1) * cw] = hh
        sp[cy * ch:(cy + 1) * ch, cx * cw:(cx + 1) * cw] = s
        gl[cy * ch:(cy + 1) * ch, cx * cw:(cx + 1) * cw] = g
    save(to_rgb(col), out, "sky_facadekit_co")
    save(normal_from_height(h, 4.0), out, "sky_facadekit_nohq")
    smdi(size, np.clip(sp, 0, 1), np.clip(gl, 0, 1)).resize((1024, 1024), Image.BILINEAR).save(
        os.path.join(out, "sky_facadekit_smdi.png"))


# ------------------------------------------------------------------ painted metal
RUST_PAINTS = [("green", (0.20, 0.31, 0.23)), ("grey", (0.44, 0.45, 0.44)), ("rust", None), ("burnt", (0.08, 0.075, 0.07)),
               ("beige", (0.66, 0.60, 0.48)), ("terracotta", (0.55, 0.28, 0.20)), ("white", (0.76, 0.76, 0.73)),
               ("slate", (0.27, 0.33, 0.40))]                      # = skyspec MATERIALS["rust"]["bands"] (8 x 1/8, rows top first)


def rust(size, out):
    """Painted steel, 1024 x 2048 (D96: 8 bands - green, grey, rust, burnt + beige, terracotta, white, slate for car
    bodies and props): paint keeps most of the surface; chips sit where edges and knocks are (fine-scale mask), each
    with a rust bloom; vertical rust runs below the chips; the rust band is fully corroded steel with pitting, the
    burnt band blistered black paint over rust."""
    W = min(size, 1024)
    H = 2 * W
    big = tfbm(H, 9753, octaves=5, base=16)
    n = big[:, :W]
    fine = tnoise(H, H // 2, 9751)[:, :W]
    chips = np.clip((tfbm(H, 9755, octaves=6, base=64)[:, :W] - 0.70) * 8, 0, 1)
    bloom = np.clip(blur(chips, 3) * 3, 0, 1)
    runs = blur(np.clip((tstreak(H, 8, 180, 9757)[:, :W] - 0.6) * 3, 0, 1), 1) * np.clip(blur(chips, 18) * 6, 0, 1)
    pits = np.clip((fine - 0.8) * 5, 0, 1)
    col = np.zeros((H, W, 3), np.float32)
    h = np.zeros((H, W), np.float32)
    spec = np.zeros((H, W), np.float32)
    gloss = np.zeros((H, W), np.float32)
    rust_c = np.array([0.36, 0.19, 0.09], np.float32)
    nb = len(RUST_PAINTS)
    for i, (name, paint) in enumerate(RUST_PAINTS):
        sl = slice(i * H // nb, (i + 1) * H // nb)
        if paint is None:
            c = rust_c * (0.75 + 0.45 * n[sl, :, None]) * (0.9 + 0.15 * fine[sl, :, None])
            col[sl] = c * (1 - 0.3 * pits[sl, :, None])
            h[sl] = 0.3 * n[sl] - 0.6 * pits[sl] + 0.1 * fine[sl]
            spec[sl], gloss[sl] = 0.12, 0.15
            continue
        p = np.array(paint, np.float32) * (0.94 + 0.08 * fine[sl, :, None]) * (0.95 + 0.08 * n[sl, :, None])
        k = 1.4 if name == "burnt" else 1.0
        cm = np.clip(chips[sl] * k, 0, 1)[..., None]
        bm = np.clip(bloom[sl] * 0.5 * k, 0, 1)[..., None]
        rm = np.clip(runs[sl] * 0.6, 0, 1)[..., None]
        c = p * (1 - bm) + (p * 0.6 + rust_c * 0.4) * bm
        c = c * (1 - rm) + (rust_c * 0.8) * rm
        col[sl] = c * (1 - cm) + rust_c * (0.8 + 0.3 * n[sl, :, None]) * cm
        h[sl] = 0.2 * fine[sl] - 0.8 * chips[sl] + 0.1 * bloom[sl]
        spec[sl] = 0.3 - 0.2 * chips[sl]
        gloss[sl] = 0.4 - 0.3 * chips[sl] - 0.1 * runs[sl]
    save(to_rgb(col), out, "sky_rust_co")
    save(normal_from_height(h, 2.5), out, "sky_rust_nohq")
    sm = np.stack([np.ones_like(spec), np.clip(spec, 0, 1), np.clip(gloss, 0, 1)], -1)
    save(to_rgb(sm), out, "sky_rust_smdi")
