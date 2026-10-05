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


def dims(S, arch):
    if arch == "RubbleLot":
        return 12.0, 12.0
    A = S.CITY_ARCHETYPES[arch]
    return A["w"], A["d"]


def party(S, arch):
    if arch == "RubbleLot":
        return True
    b = S.CITY_ARCHETYPES[arch].get("blank", ())
    return "W" in b and "E" in b


def class_of(S, arch, state, rng):
    if arch == "RubbleLot":
        return S.KIT["City_RubbleLot_%s" % rng.choice("ABCD")]["cls"]
    return S.KIT["City_%s_%s" % (arch, S.RUIN_STATES[state])]["cls"]


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


def fill_block(S, block, rect, setback):
    """-> [(cls, arch, state, u, v, yaw_rel, hw, hd)] in the site frame (block rect = site frame)."""
    fill = block.get("fill") or {}
    zone = S.CITY_ZONES[fill["zone"]] if fill else None
    rng = random.Random("%s:%s" % (fill.get("seed", 1), block["id"]))
    u0, u1, v0, v1 = rect[0] + setback, rect[1] - setback, rect[2] + setback, rect[3] - setback
    starts = {"S": (u0, v0, u1 - u0), "N": (u1, v1, u1 - u0), "W": (u0, v1, v1 - v0), "E": (u1, v0, v1 - v0)}
    placed, quads = [], []
    for b in block.get("buildings", []) or []:                              # explicit buildings first
        state = {"intact": 0, "damaged": 1, "ruined": 2}[b.get("ruin", "intact")]
        w, d = dims(S, b["type"])
        u, v = (rect[0] + rect[1]) / 2 + b["at"][0], (rect[2] + rect[3]) / 2 + b["at"][1]
        yaw = float(b.get("yaw", 0.0))
        q = _corners(u, v, w / 2, d / 2, yaw)
        quads.append(q)
        placed.append((class_of(S, b["type"], state, rng), b["type"], state, u, v, yaw, w / 2, d / 2))
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
                is_small = arch != "RubbleLot" and S.CITY_ARCHETYPES[arch]["group"] == "small"
                if is_small and small[0] >= zone.get("small_cap", 1):
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
                r = rng.random()
                p_i, p_d, _p_r = zone["ruin"]
                state = 0 if r < p_i else (1 if r < p_i + p_d else 2)
                quads.append(q)
                placed.append((class_of(S, arch, state, rng), arch, state, cu, cv, yaw, w / 2, d / 2))
                small[0] += 1 if is_small else 0
                a = aa + w
                prev_party = party(S, arch)
                done = True
                break
            if not done:
                a += 1.0
                prev_party = False
            first = False
    return placed
