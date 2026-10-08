"""Baked ambient occlusion on a second UV set (D85 pilot, ASSET_QUALITY_GUIDE section 8 item 3) - plain Python.

Props share atlas / trim UVs (set 0), so a per-prop AO map cannot use them. This module gives a Res0 a unique
second UV set (set 1: every face projected on its own plane at world scale and shelf-packed into one square
sheet) and bakes AO into it by ray casting against the prop's own opaque triangles plus the floor plane (contact
shadow). The rvmat reads the map on Stage4 with uvSource "tex1" (P55). Deterministic: build_props writes the
same set 1 that gen_textures bakes into.

    unwrap(lod, size)          -> per-face UV lists aligned with lod.faces (None for see-through faces)
    bake(lod, uv1, size)       -> float32 (size, size) AO, 1 = unoccluded
"""
import math

import numpy as np

PAD = 3                 # px between charts (mip bleeding at 256 / 128)
RAYS = 48               # hemisphere rays per texel
DIST = 0.45             # m: occluders further away do not darken (contact-scale AO)
FLOOR = True            # props stand on the floor: z = 0 occludes too


def _normal(p):
    n = np.zeros(3)
    for i in range(len(p)):
        a, b = np.asarray(p[i], float), np.asarray(p[(i + 1) % len(p)], float)
        n += np.cross(a, b)
    ln = np.linalg.norm(n)
    return n / ln if ln > 1e-12 else np.array([0.0, 0.0, 1.0])


def _basis(n):
    """Two in-plane axes for a face normal (dominant-axis projection, stable for axis-aligned props)."""
    k = int(np.argmax(np.abs(n)))
    a, b = [i for i in range(3) if i != k]
    return a, b


def _charts(lod, skip):
    out = []
    for fi, (idx, mat, _uv) in enumerate(lod.faces):
        if mat in skip:
            out.append(None)
            continue
        p = [lod.verts[i] for i in idx]
        n = _normal(p)
        a, b = _basis(n)
        q = np.array([[v[a], v[b]] for v in p])
        lo = q.min(0)
        out.append((fi, q - lo, q.max(0) - lo))
    return out


def unwrap(lod, size=512, skip=("glass", "glassfar")):
    """Shelf-pack every face's planar chart at one shared scale (largest that fits). Returns uv1 per face."""
    charts = _charts(lod, set(skip))
    real = [c for c in charts if c is not None]
    order = sorted(real, key=lambda c: (-c[2][1], -c[2][0], c[0]))
    area = sum((c[2][0] + 1e-3) * (c[2][1] + 1e-3) for c in real)
    scale = math.sqrt(0.55 * size * size / max(area, 1e-6))             # px per m, shrunk until everything fits
    for _ in range(40):
        place, x, y, row_h, ok = {}, PAD, PAD, 0, True
        for fi, _q, ext in order:
            w = max(2, int(math.ceil(ext[0] * scale)))
            h = max(2, int(math.ceil(ext[1] * scale)))
            if x + w + PAD > size:
                x, y, row_h = PAD, y + row_h + PAD, 0
            if y + h + PAD > size:
                ok = False
                break
            place[fi] = (x, y, w, h)
            x += w + PAD
            row_h = max(row_h, h)
        if ok:
            break
        scale *= 0.93
    else:
        raise RuntimeError("aobake.unwrap: %d charts do not fit a %d px sheet" % (len(real), size))
    uv1 = [None] * len(lod.faces)
    for c in real:
        fi, q, ext = c
        x, y, w, h = place[fi]
        sx = (w - 1) / ext[0] if ext[0] > 1e-9 else 0.0
        sy = (h - 1) / ext[1] if ext[1] > 1e-9 else 0.0
        # Blender convention (v up), like set 0: the writer stores 1 - v, i.e. the image row / size
        uv1[fi] = [((x + 0.5 + u * sx) / size, 1.0 - (y + 0.5 + v * sy) / size) for u, v in q]
    return uv1


def with_ao(fn, spec):
    """Wrap a builder: its Res0 gets the unique UV set 1 (charts only for the faces that will read the AO map: the
    spec's materials; decals, signs and atlas faces still occlude in the bake) and those faces switch to the
    sky_<mat>_<tag> rvmat variants (D85 pilot, D87 shared by build_props and build_streetprops)."""
    def build():
        lods = fn()
        r0 = [l for l in lods if l.name == "res0"][0]
        keep = set(spec["mats"])
        r0.uv1 = unwrap(r0, spec["size"], skip={m for _i, m, _u in r0.faces if m not in keep})
        r0.faces = [(i, ("%s_%s" % (m, spec["tag"])) if m in keep else m, uv) for (i, m, uv) in r0.faces]
        return lods
    return build


def _hemisphere(n_rays):
    """Fixed cosine-weighted directions around +Z (Fibonacci spiral): the bake is deterministic."""
    i = np.arange(n_rays) + 0.5
    r = np.sqrt(i / n_rays)
    t = math.pi * (1 + 5 ** 0.5) * i
    return np.stack([r * np.cos(t), r * np.sin(t), np.sqrt(1 - r * r)], -1)


def _frame(n):
    t = np.cross(n, [0.0, 0.0, 1.0]) if abs(n[2]) < 0.9 else np.cross(n, [1.0, 0.0, 0.0])
    t /= np.linalg.norm(t)
    return np.stack([t, np.cross(n, t), n], 0)          # rows: tangent, bitangent, normal


def _hits(o, d, T):
    """Any-hit Moller-Trumbore: o, d (R,3); T (N,3,3) -> bool (R,) hit within DIST."""
    if not len(T) or not len(o):
        return np.zeros(len(o), bool)
    T, o, d = T.astype(np.float32), o.astype(np.float32), d.astype(np.float32)
    v0, e1, e2 = T[:, 0], T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]
    hit = np.zeros(len(o), bool)
    step = max(256, int(2e5 // len(T)))                     # bounded temporaries (perf L)
    for s in range(0, len(o), step):
        oo, dd = o[s:s + step, None, :], d[s:s + step, None, :]
        p = np.cross(dd, e2[None])
        det = (e1[None] * p).sum(-1)
        ok = np.abs(det) > 1e-12
        inv = 1.0 / np.where(ok, det, 1.0)
        tv = oo - v0[None]
        u = (tv * p).sum(-1) * inv
        q = np.cross(tv, e1[None])
        v = (dd * q).sum(-1) * inv
        t = (e2[None] * q).sum(-1) * inv
        h = ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 1e-4) & (t < DIST)
        hit[s:s + step] = h.any(1)
    return hit


def bake(lod, uv1, size=512, skip=("glass", "glassfar")):
    """AO per texel of the set-1 charts; empty texels are dilated from their neighbours (no black seams)."""
    tris = []
    for idx, mat, _uv in lod.faces:
        if mat in skip:
            continue
        p = [lod.verts[i] for i in idx]
        for k in range(1, len(p) - 1):
            tris.append((p[0], p[k], p[k + 1]))
    T = np.array(tris, float).reshape(-1, 3, 3)
    tlo, thi = T.min(1), T.max(1)
    H = _hemisphere(RAYS)
    img = np.zeros((size, size), np.float32)
    have = np.zeros((size, size), bool)
    for fi, (idx, mat, _uv) in enumerate(lod.faces):
        if uv1[fi] is None:
            continue
        P = np.array([lod.verts[i] for i in idx], float)
        n = _normal(P)
        UV = np.array([(u, 1.0 - v) for u, v in uv1[fi]]) * size           # back to image pixels (row down)
        x0, y0 = np.floor(UV.min(0)).astype(int)
        x1, y1 = np.ceil(UV.max(0)).astype(int)
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        pts = np.stack([gx.ravel(), gy.ravel()], -1)
        world = np.zeros((len(pts), 3))
        inside = np.zeros(len(pts), bool)
        for k in range(1, len(P) - 1):                       # texel -> barycentric in each fan triangle
            a, b, c = UV[0], UV[k], UV[k + 1]
            m = np.array([[b[0] - a[0], c[0] - a[0]], [b[1] - a[1], c[1] - a[1]]])
            if abs(np.linalg.det(m)) < 1e-12:
                continue
            w = np.linalg.solve(m, (pts - a).T).T
            # texel centres within half a texel of the chart count (edges get filled)
            tol = 0.5 / max(1.0, np.abs(m).max())
            sel = (w[:, 0] >= -tol) & (w[:, 1] >= -tol) & (w.sum(1) <= 1 + tol) & ~inside
            wc = np.clip(w[sel], 0, 1)
            world[sel] = P[0] + wc[:, :1] * (P[k] - P[0]) + wc[:, 1:] * (P[k + 1] - P[0])
            inside |= sel
        if not inside.any():
            continue
        o = world[inside] + n * 0.003
        F = _frame(n)
        D = H @ F                                            # (RAYS, 3) world directions
        oo = np.repeat(o, RAYS, 0)
        dd = np.tile(D, (len(o), 1))
        lo, hi = o.min(0) - DIST, o.max(0) + DIST
        near = np.all((thi >= lo) & (tlo <= hi), 1)
        # only triangles with a vertex in front of the face plane can occlude it (perf L)
        near &= ((T - P[0]) @ n).max(1) > 1e-4
        occ = np.zeros(len(oo), bool)
        if FLOOR:                                            # floor plane z = 0 first (contact shadow under the prop)
            with np.errstate(divide="ignore", invalid="ignore"):
                tz = -oo[:, 2] / dd[:, 2]
            occ = (dd[:, 2] < -1e-6) & (tz > 1e-4) & (tz < DIST)
        rest = ~occ
        occ[rest] = _hits(oo[rest], dd[rest], T[near])
        ao = 1.0 - occ.reshape(len(o), RAYS).mean(1)
        px = pts[inside].astype(int)
        ok = (px[:, 0] >= 0) & (px[:, 0] < size) & (px[:, 1] >= 0) & (px[:, 1] < size)
        img[px[ok, 1], px[ok, 0]] = ao[ok]
        have[px[ok, 1], px[ok, 0]] = True
    for _ in range(PAD + 2):                                 # dilate into the padding
        acc = np.zeros_like(img)
        cnt = np.zeros_like(img)
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            acc += np.roll(np.where(have, img, 0), (dy, dx), (0, 1))
            cnt += np.roll(have.astype(np.float32), (dy, dx), (0, 1))
        fill = ~have & (cnt > 0)
        img[fill] = acc[fill] / cnt[fill]
        have |= fill
    img[~have] = 1.0
    return img
