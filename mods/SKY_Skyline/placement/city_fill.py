"""City block fill (D57): packs procedural city buildings into street blocks. Used by sky_layout.py.

A block with `fill: {zone: <CITY_ZONES key>, seed: N}` is filled lot by lot along its four street
edges. Every building's front (model -Y) faces the street on its edge; the walk along an edge
starts at the corner on the building's left so corner shops (shopfront on their left side) sit on
the block corner. Archetypes are drawn from the zone's weights, the ruin state from the zone's
(intact, damaged, ruined) mix, rubble lots with the zone's `lots` chance. Party-wall types (blank
left and right sides) sit flush; detached ones keep the zone's gap. Every footprint is checked
against everything already in the block (SAT); the caller checks streets, towers and the survey.
`buildings:` places explicit ones: {type, ruin: intact|damaged|ruined, at: [u, v], yaw}.
Deterministic: the same layout + seed always gives the same city.
"""
import math
import random

EDGES = {  # yaw (front faces out of the block), start corner selector
    "S": 0.0, "N": 180.0, "W": 90.0, "E": 270.0,
}


def _rot(u, v, yaw_deg):
    a = math.radians(yaw_deg)
    return (u * math.cos(a) + v * math.sin(a), -u * math.sin(a) + v * math.cos(a))


def _corners(cx, cz, hw, hd, yaw):
    return [(cx + dx, cz + dz) for dx, dz in (_rot(u, v, yaw) for u, v in ((-hw, -hd), (hw, -hd), (hw, hd), (-hw, hd)))]


def _sat(a, b, eps=1e-6):
    for poly in (a, b):
        for i in range(len(poly)):
            x1, z1 = poly[i]
            x2, z2 = poly[(i + 1) % len(poly)]
            nx, nz = z2 - z1, x1 - x2
            pa = [nx * x + nz * z for x, z in a]
            pb = [nx * x + nz * z for x, z in b]
            if max(pa) <= min(pb) + eps or max(pb) <= min(pa) + eps:
                return False
    return True


def footprint(S, arch):
    """(w, d, oy): footprint size and the model origin's offset from the footprint centre along
    model +Y (forecourt buildings: the body sits at the back of the footprint, D58)."""
    if arch in S.CITY_PIECES:
        _k, w, d = S.CITY_PIECES[arch]
        return w, d, 0.0
    x0, x1, y0, y1 = S.city_footprint(S.CITY_ARCHETYPES[arch])
    return x1 - x0, y1 - y0, -(y0 + y1) / 2


def dims(S, arch):
    w, d, _oy = footprint(S, arch)
    return w, d


def party(S, arch):
    if arch == "RubbleLot":
        return True
    if arch in S.CITY_PIECES:
        return False
    b = S.CITY_ARCHETYPES[arch].get("blank", ())
    return "W" in b and "E" in b


def is_small(S, arch):
    return arch not in S.CITY_PIECES and S.CITY_ARCHETYPES[arch]["group"] == "small"


def class_of(S, arch, state, rng):
    if arch in S.CITY_PIECES:
        return S.KIT[rng.choice(S.CITY_PIECES[arch][0])]["cls"]
    return S.KIT["City_%s_%s" % (arch, S.RUIN_STATES[state])]["cls"]


def _origin(S, arch, cu, cv, yaw):
    """Model origin (site frame) of a building whose footprint centre is (cu, cv)."""
    _w, _d, oy = footprint(S, arch)
    du, dv = _rot(0.0, oy, yaw)
    return cu + du, cv + dv


def _weighted_order(rng, weights):
    """All archetypes once, ordered by a weighted random draw without replacement."""
    pool = dict(weights)
    out = []
    while pool:
        tot = sum(pool.values())
        r = rng.random() * tot
        for k in sorted(pool):
            r -= pool[k]
            if r <= 0:
                out.append(k)
                del pool[k]
                break
        else:
            k = sorted(pool)[-1]
            out.append(k)
            del pool[k]
    return out


def _gap(a, b):
    """Clear distance between two footprints (all yaws are multiples of 90: axis-aligned boxes)."""
    ax0, ax1 = min(x for x, _z in a), max(x for x, _z in a)
    az0, az1 = min(z for _x, z in a), max(z for _x, z in a)
    bx0, bx1 = min(x for x, _z in b), max(x for x, _z in b)
    bz0, bz1 = min(z for _x, z in b), max(z for _x, z in b)
    dx, dz = max(0.0, bx0 - ax1, ax0 - bx1), max(0.0, bz0 - az1, az0 - bz1)
    return (dx * dx + dz * dz) ** 0.5


MIN_GAP = 0.8                     # buildings touch (party walls / corners) or keep >= 0.8 m: no slivers


def fill_block(S, block, rect, setback, ground=None, stats=None):
    """-> [(cls, arch, state, u, v, yaw_rel, hw, hd, ou, ov)] in the site frame (block rect = site
    frame): footprint centre (u, v) and half sizes for the overlap checks, model origin (ou, ov).
    ground(arch, u, v, hw, hd, yaw) -> None or a reason string: a lot the terrain cannot take (too
    steep for the skirt, entrance off the sidewalk, an existing object) is given to the next, smaller
    archetype or left as an overgrown yard instead of failing the run (D59). stats collects counts."""
    stats = stats if stats is not None else {}
    fill = block.get("fill") or {}
    zone = S.CITY_ZONES[fill["zone"]] if fill else None
    rng = random.Random("%s:%s" % (fill.get("seed", 1), block["id"]))
    u0, u1, v0, v1 = rect[0] + setback, rect[1] - setback, rect[2] + setback, rect[3] - setback
    starts = {"S": (u0, v0, u1 - u0), "N": (u1, v1, u1 - u0), "W": (u0, v1, v1 - v0), "E": (u1, v0, v1 - v0)}
    placed, quads, used = [], [], set()
    # D69 (perf review M): venues behind a "rare" chance are rolled once per block, not on every slot draw
    allowed = {a for a, p in sorted((zone or {}).get("rare", {}).items()) if rng.random() < p}
    for b in block.get("buildings", []) or []:                              # explicit buildings first
        state = {"intact": 0, "damaged": 1, "ruined": 2}[b.get("ruin", "intact")]
        w, d = dims(S, b["type"])
        u, v = (rect[0] + rect[1]) / 2 + b["at"][0], (rect[2] + rect[3]) / 2 + b["at"][1]
        yaw = float(b.get("yaw", 0.0))
        q = _corners(u, v, w / 2, d / 2, yaw)
        quads.append(q)
        placed.append((class_of(S, b["type"], state, rng), b["type"], state, u, v, yaw, w / 2, d / 2)
                      + _origin(S, b["type"], u, v, yaw))
        used.add(b["type"])
    if not zone:
        return placed
    small = [0]
    for edge in ("S", "N", "W", "E"):
        yaw = EDGES[edge]
        ex = _rot(1.0, 0.0, yaw)
        inw = _rot(0.0, 1.0, yaw)
        su, sv, length = starts[edge]
        a, first, prev_party = 0.0, True, False
        while a < length - 2.0:
            order = _weighted_order(rng, zone["weights"])
            if first and zone["corner"] and rng.random() < 0.7:
                order = rng.sample(zone["corner"], len(zone["corner"])) + order
            if rng.random() < zone["lots"]:
                order = ["RubbleLot"] + order
            done = False
            for arch in order:
                small_one = is_small(S, arch)
                if small_one and small[0] >= zone.get("small_cap", 1):
                    continue
                if arch in zone.get("once", ()) and arch in used:          # landmarks: one per block
                    continue
                if arch in zone.get("rare", {}) and arch not in allowed:    # D69 venues: only in blocks that rolled them
                    continue
                w, d = dims(S, arch)
                gap = 0.0 if (a == 0.0 or (prev_party and party(S, arch))) else zone["gap"]
                aa = a + gap
                if aa + w > length + 1e-6:
                    continue
                cu = su + ex[0] * (aa + w / 2) + inw[0] * (d / 2)
                cv = sv + ex[1] * (aa + w / 2) + inw[1] * (d / 2)
                q = _corners(cu, cv, w / 2, d / 2, yaw)
                if any(not (u0 - 1e-6 <= x <= u1 + 1e-6 and v0 - 1e-6 <= z <= v1 + 1e-6) for x, z in q):
                    continue
                if any(_sat(q, o) for o in quads):
                    continue
                if any(0.0 < _gap(q, o) < MIN_GAP for o in quads):
                    stats["slivers_avoided"] = stats.get("slivers_avoided", 0) + 1
                    continue
                why = ground(arch, cu, cv, w / 2, d / 2, yaw) if ground else None
                if why:
                    stats.setdefault("terrain_skips", []).append("%s: %s" % (arch, why))
                    continue
                r = rng.random()
                p_i, p_d, _p_r = zone["ruin"]
                state = 0 if r < p_i else (1 if r < p_i + p_d else 2)
                if arch in S.CITY_PIECES:
                    state = 2 if arch == "RubbleLot" else 0                 # lots are ruins; kit pieces: one state
                quads.append(q)
                placed.append((class_of(S, arch, state, rng), arch, state, cu, cv, yaw, w / 2, d / 2)
                              + _origin(S, arch, cu, cv, yaw))
                used.add(arch)
                small[0] += 1 if small_one else 0
                a = aa + w
                prev_party = party(S, arch)
                done = True
                break
            if not done:
                a += 1.0
                prev_party = False
            first = False
    placed += scatter_vegetation(S, zone, rng, (u0, u1, v0, v1), placed, quads, ground, stats)
    return placed


def scatter_vegetation(S, zone, rng, box, placed, quads, ground, stats):
    """Overgrowth in the free parts of the block (yards, gaps, empty lots) and in the yards of
    perimeter blocks: jittered grid, zone density and mix, >= 1 m clear of every building, seeded."""
    veg = zone.get("veg")
    if not veg:
        return []
    u0, u1, v0, v1 = box
    out = []
    step = veg["step"]
    mix = veg["mix"]
    cap = veg.get("cap", 24)
    occupied = list(quads)
    yards = []
    for (_c, arch, _st, _u, _v, yaw, _hw, _hd, ou, ov) in placed:
        A = S.CITY_ARCHETYPES.get(arch)
        if A and A.get("yard"):
            yards.append((ou, ov, A["yard"] / 2 - 1.5))
    pts = []                                                                # (u, v, trees allowed)
    u = u0 + step / 2
    while u < u1:
        v = v0 + step / 2
        while v < v1:
            pts.append((u + (rng.random() - 0.5) * step * 0.8, v + (rng.random() - 0.5) * step * 0.8, True))
            v += step
        u += step
    fine = veg.get("fine", 0)
    if fine:                                                                # weeds in gaps and yards: finer grid
        u = u0 + fine / 2
        while u < u1:
            v = v0 + fine / 2
            while v < v1:
                pts.append((u + (rng.random() - 0.5) * fine * 0.6, v + (rng.random() - 0.5) * fine * 0.6, False))
                v += fine
            u += fine
    for (yu, yv, r) in yards:                                               # perimeter-block yards
        for k in range(veg.get("yard", 3)):
            pts.append((yu + (rng.random() - 0.5) * 2 * r, yv + (rng.random() - 0.5) * 2 * r, True))
    small_mix = {k: w for k, w in mix.items() if k in ("Veg_Weeds", "Veg_Bush")}
    for (pu, pv, trees) in pts:
        if len(out) >= cap:
            break
        if rng.random() > veg["chance"]:
            continue
        piece = _weighted_order(rng, mix if (trees or veg.get("fine_trees")) else small_mix)[0]   # fine grid: weeds / bushes
        _k, w, _d = S.CITY_PIECES[piece]
        q = _corners(pu, pv, w / 2, w / 2, 0.0)
        if any(not (u0 - 1e-6 <= x <= u1 + 1e-6 and v0 - 1e-6 <= z <= v1 + 1e-6) for x, z in q):
            continue
        in_yard = any(abs(pu - yu) <= r and abs(pv - yv) <= r for (yu, yv, r) in yards)
        clear_m = 0.3 if piece == "Veg_Weeds" else 1.0                     # weeds may hug walls and fill gaps
        blocked = [o for o in occupied if _sat(q, o) or _gap(q, o) < clear_m]
        if in_yard:                                                         # the yard is inside its building's footprint
            blocked = [o for o in blocked if o not in quads]
        if blocked:
            continue
        if ground and ground(piece, pu, pv, w / 2, w / 2, 0.0):
            continue
        yaw = round(rng.random() * 3) * 90.0
        occupied.append(q)
        name = S.KIT[piece]["cls"]
        vanilla = getattr(S, "VANILLA_TREES", [])
        if piece == "Veg_Birch" and vanilla and rng.random() < S.VANILLA_TREE_SHARE:    # P13 (off while empty)
            name = vanilla[int(rng.random() * len(vanilla)) % len(vanilla)]
            yaw = rng.random() * 360.0
        out.append((name, piece, 0, pu, pv, yaw, w / 2, w / 2, pu, pv))
    stats["vegetation"] = stats.get("vegetation", 0) + len(out)
    return out
