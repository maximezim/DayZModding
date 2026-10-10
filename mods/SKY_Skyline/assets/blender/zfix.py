"""Z-fighting finder and resolver for graphical LODs (D96, TESTING CT-13 "glitched textures").

Two faces that face the same way, lie in the same plane (closer than ZF_EPS) and overlap cannot be ordered by the depth
buffer: in game they flicker between the two textures. The generators build many small parts flush with bigger ones
(window frames in the wall plane, stair nosings on treads, cushions on sofas, decals on decals). `resolve()` runs on
every Resolution LOD at export: of the two primitives (one box / solid / quad call, tracked in Lod.vprim) the smaller
one is made DELTA proud - a solid is scaled about its centre so every face moves out by DELTA with no crack at its edges,
a flat part (decal, plate) is moved DELTA along its normal - so the detail wins and the larger surface stays put.
What cannot be resolved is left for the gate (test_quality.py), which fails on it.
"""
import numpy as np

ZF_EPS = 0.0025        # m: same-facing faces closer than this share one depth at Res0 / Res1 viewing distances
ZF_AREA = 0.0025       # m2: overlap that shows (5 x 5 cm); slivers at frame corners do not read
DELTA = 0.004          # m: how far the smaller primitive is made proud (invisible as a step, enough depth separation)
MAX_PASSES = 24
OVERLAY = ("decal", "vegetation", "foliage", "roadmark", "roofmark")   # alpha overlays always go on top


def newell(p):
    n = np.zeros(3)
    for i in range(len(p)):
        a, b = p[i], p[(i + 1) % len(p)]
        n += ((a[1] - b[1]) * (a[2] + b[2]), (a[2] - b[2]) * (a[0] + b[0]), (a[0] - b[0]) * (a[1] + b[1]))
    ln = np.linalg.norm(n)
    return n / ln if ln > 1e-12 else None


def basis(n):
    a = np.array([1.0, 0, 0]) if abs(n[0]) < 0.9 else np.array([0, 1.0, 0])
    u = np.cross(n, a)
    u /= np.linalg.norm(u)
    return u, np.cross(n, u)


def clip(subject, clipper):
    """Sutherland-Hodgman: convex polygon intersection in 2D (both counter-clockwise)."""
    out = subject
    for i in range(len(clipper)):
        if not out:
            break
        a, b = clipper[i], clipper[(i + 1) % len(clipper)]
        inp, out = out, []
        for j in range(len(inp)):
            p, q = inp[j], inp[(j + 1) % len(inp)]
            sp = (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
            sq = (b[0] - a[0]) * (q[1] - a[1]) - (b[1] - a[1]) * (q[0] - a[0])
            if sp >= 0:
                out.append(p)
            if (sp >= 0) != (sq >= 0):
                t = sp / (sp - sq)
                out.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
    return out


def area2(poly):
    if len(poly) < 3:
        return 0.0
    return 0.5 * sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
                     for i in range(len(poly)))


def ccw(poly):
    return poly if area2(poly) >= 0 else poly[::-1]


def _uv_at(q2, uv, pts):
    A = np.c_[np.asarray(q2, float), np.ones(len(q2))]
    M, *_ = np.linalg.lstsq(A, np.asarray(uv, float), rcond=None)
    return np.c_[np.asarray(pts, float), np.ones(len(pts))] @ M


def same_look(fa, fb, qa, qb, ov):
    """Same material and the same texture coordinates over the overlap: the fight cannot be seen."""
    if fa[3] != fb[3]:
        return False
    if fa[4] is None and fb[4] is None:
        return True
    if fa[4] is None or fb[4] is None:
        return False
    return bool(np.abs(_uv_at(qa, fa[4], ov) - _uv_at(qb, fb[4], ov)).max() < 2e-3)


def zfight(lod, eps=ZF_EPS, min_area=ZF_AREA):
    """[(area, material a, material b, centre, face a, face b)] for same-facing overlapping faces in one plane."""
    groups, info = {}, []
    for k, (idx, mat, uv) in enumerate(lod.faces):
        p = np.asarray([lod.verts[i] for i in idx], float)
        n = newell(p)
        if n is None:
            info.append(None)
            continue
        info.append((n, float(n @ p.mean(0)), p, mat, uv))
        groups.setdefault(tuple(np.round(n * 200).astype(int)), []).append(k)
    hits = []

    def hidden(key, d, u, v, ov):
        """The overlap lies on the back of an opposite-facing coplanar surface (a part resting on a floor, two boxes
        face to face): nobody sees it from either side."""
        opp = groups.get(tuple(-x for x in key), ())
        need = 0.9 * area2(ov)
        got = 0.0
        for k in opp:
            if abs(info[k][1] + d) >= eps:
                continue
            q = ccw([(float(x @ u), float(x @ v)) for x in info[k][2]])
            got += area2(clip(ccw(list(ov)), q))
            if got >= need:
                return True
        return False
    for key, ks in groups.items():
        if len(ks) < 2:
            continue
        ks.sort(key=lambda k: info[k][1])
        n0 = info[ks[0]][0]
        u, v = basis(n0)
        start = 0
        while start < len(ks):
            end = start + 1
            while end < len(ks) and info[ks[end]][1] - info[ks[end - 1]][1] < eps:
                end += 1
            cl = ks[start:end]
            start = end
            if len(cl) < 2:
                continue
            p2 = [[(float(q @ u), float(q @ v)) for q in info[k][2]] for k in cl]
            bb = np.array([[min(a for a, _ in q), max(a for a, _ in q), min(b for _, b in q), max(b for _, b in q)]
                           for q in p2])
            order = np.argsort(bb[:, 0], kind="stable")
            for ii, i in enumerate(order):
                for j in order[ii + 1:]:
                    if bb[j, 0] >= bb[i, 1] - 1e-6:
                        break
                    if abs(info[cl[i]][1] - info[cl[j]][1]) >= eps:
                        continue
                    ox = min(bb[i, 1], bb[j, 1]) - max(bb[i, 0], bb[j, 0])
                    oy = min(bb[i, 3], bb[j, 3]) - max(bb[i, 2], bb[j, 2])
                    if ox <= 1e-4 or oy <= 1e-4 or ox * oy < min_area:
                        continue
                    ov = clip(ccw(p2[i]), ccw(p2[j]))
                    a = area2(ov)
                    if a >= min_area and not same_look(info[cl[i]], info[cl[j]], p2[i], p2[j], ov) \
                            and not hidden(key, info[cl[i]][1], u, v, ov):
                        c = n0 * info[cl[i]][1] + u * np.mean([q[0] for q in ov]) + v * np.mean([q[1] for q in ov])
                        hits.append((a, info[cl[i]][3], info[cl[j]][3], tuple(float(x) for x in np.round(c, 2)),
                                     cl[i], cl[j]))
    return hits


def _prim_of(lod, k):
    idx = lod.faces[k][0]
    i = idx[0]
    p = lod.vprim[i] if i < len(lod.vprim) else -1
    return p if p > 0 else ("f", k)


def _prim_verts(lod, prim, k):
    if isinstance(prim, tuple):
        return sorted(set(lod.faces[k][0]))
    return [i for i, p in enumerate(lod.vprim) if p == prim]


def offset_solid(lod, vs, faces, d, base=None):
    """Move every face of a solid out by d along its own normal. Corners shared by several faces (same position,
    separate vertices in the Resolution LODs) move by d x the sum of their distinct face normals, so coincident
    vertices stay together and no crack opens at an edge (exact for boxes, rotated or not)."""
    base = lod.verts if base is None else base
    normals = {}
    for k in faces:
        n = newell(np.asarray([base[i] for i in lod.faces[k][0]], float))
        if n is None:
            continue
        for i in lod.faces[k][0]:
            key = tuple(np.round(base[i], 5))
            lst = normals.setdefault(key, [])
            if not any(float(n @ m) > 0.999 for m in lst):
                lst.append(n)
    out = {}
    for i in vs:
        p = np.asarray(base[i], float)
        lst = normals.get(tuple(np.round(base[i], 5)), [])
        out[i] = p + d * (np.sum(lst, 0) if lst else 0.0)
    return out


def _record(lod, layer, info):
    """lod.zfix_layer_map: {primitive: (layers, size m, material)} for the gate (test_quality: how far a part moved)."""
    lod.zfix_layers = max(layer.values()) if layer else 0
    lod.zfix_layer_map = {pr: (lay, info[pr][0], lod.faces[info[pr][2]][1]) for pr, lay in layer.items()}


def resolve(lod):
    """Give every fighting primitive a layer and make it layer x DELTA proud (from its original position): of two
    primitives that fight, the smaller one always sits at least one layer above the larger one (layers follow the
    size order, so a stack of equal boards becomes 1, 2, 3 ... layers instead of trading places). Repeated until no
    fight is left - a raised part can meet a new surface - or MAX_PASSES. Returns (fights on the first pass, left)."""
    vp_index = {}
    for i, p in enumerate(lod.vprim):
        if p > 0:
            vp_index.setdefault(p, []).append(i)
    orig = list(lod.verts)
    layer, info, pfaces, edges = {}, {}, {}, {}
    first = None
    for _pass in range(MAX_PASSES):
        hits = zfight(lod)
        if first is None:
            first = len(hits)
        if not hits:
            _record(lod, layer, info)
            return first, 0
        for h in hits:
            for k in (h[4], h[5]):
                pr = _prim_of(lod, k)
                if pr not in info:
                    vs = vp_index.get(pr) if not isinstance(pr, tuple) else sorted(set(lod.faces[k][0]))
                    pts = np.asarray([orig[i] for i in vs], float)
                    over = (lod.faces[k][1] or "").startswith(OVERLAY)
                    info[pr] = (float(np.linalg.norm(pts.max(0) - pts.min(0))), vs, k, over)
        rank = lambda pr: (info[pr][3], -info[pr][0], str(pr))   # opaque before overlays, then larger first (below)
        for h in hits:
            a_, b_ = _prim_of(lod, h[4]), _prim_of(lod, h[5])
            if a_ == b_:                                      # a primitive folded onto itself: no layer can help
                continue                                      # (left for the gate - fix the shape in its generator)
            lo_, hi_ = sorted((a_, b_), key=rank)
            e = edges.setdefault(hi_, {})                     # hi_ (smaller) must sit e[lo_] layers above lo_ (larger)
            e[lo_] = e.get(lo_, 0) + 1                        # still fighting after a pass: one more layer apart
        changed, guard = True, 0
        while changed and guard <= len(edges) + 2:            # longest-path layering over the (acyclic) "above" relation
            changed, guard = False, guard + 1
            for pr in sorted(edges, key=rank):
                need = max(layer.get(q, 0) + g for q, g in edges[pr].items())
                if layer.get(pr, 0) < need:
                    layer[pr] = need
                    changed = True
        lod.verts = list(orig)
        for k, f in enumerate(lod.faces):
            pr = _prim_of(lod, k)
            if pr in layer:
                pfaces.setdefault(pr, set()).add(k)
        for pr, lay in layer.items():
            _size, vs, k, _over = info[pr]
            d = DELTA * lay
            n = newell(np.asarray([orig[i] for i in lod.faces[k][0]], float))
            pts = np.asarray([orig[i] for i in vs], float)
            if float(np.ptp((pts - pts.mean(0)) @ n)) < 1e-4:       # decal / plate: lift it off the surface
                new = {i: pts[j] + n * d for j, i in enumerate(vs)}
            else:
                new = offset_solid(lod, vs, sorted(pfaces.get(pr, {k})), d, orig)
            for i, q in new.items():
                lod.verts[i] = tuple(float(x) for x in q)
    _record(lod, layer, info)
    return first, len(zfight(lod))


def resolve_lods(lods):
    """resolve() on every graphical LOD; returns {lod name: (found, left)} for the ones that had fights."""
    from skygeo import LOD_RES
    out = {}
    for l in lods:
        if l.lod == LOD_RES and l.faces:
            f, left = resolve(l)
            if f:
                out[l.name] = (f, left)
    return out
