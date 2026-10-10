"""Gate (D83, P53): ruin cuts agree between render and collision.

RLod cuts boxes and quads per cut cell (D82), but extrudes, solids and prisms are kept or dropped whole by their
centre. Every piece the ruin layer handles in a region is logged per LOD (Res0, Geometry, Fire) as kept (with
its kept box) or dropped. Two failures:
  * a thick (>= 0.2 m) Res0 piece kept whole more than 0.3 m above the lowest cut it overlaps, without Geometry
    AND Fire pieces covering it (bullets through a visible wall / walking through it);
  * a Geometry or Fire piece kept whole that high with no Res0 over it (an invisible wall), or dropped whole
    while kept Res0 still covers its volume (render with no collision).
Cover = the kept counterparts overlap the piece on each axis by at least COVER of its extent (a slightly inset
collision box passes; an unrelated slab next to it does not).

    python assets/blender/test_ruin_cuts.py [--only A,B]
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import build_city as B  # noqa: E402

THIN = 0.2      # m: render-only pieces thinner than this on their short side need no collision (D76 rule)
RISE = 0.3      # m: a whole piece this far above the lowest cut it overlaps would be cut differently as a box
COVER = 0.6     # share of each axis extent the counterparts must overlap
LODS = ("res0", "geo", "fire")

_LOG = []       # (model, lod, kind, kept, rise, box)
_ORIG = {k: getattr(B.RLod, k) for k in ("solid", "prism", "extrude_x", "extrude_y", "box")}


def _bbox(kind, args):
    if kind == "solid":
        xs, ys, zs = zip(*args[0])
        return min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)
    if kind == "prism":
        cx, cy, r, z0, z1 = args[:5]
        return cx - r, cx + r, cy - r, cy + r, z0, z1
    prof, a, b = args[0], args[1], args[2]
    u, z = [p[0] for p in prof], [p[1] for p in prof]
    return (a, b, min(u), max(u), min(z), max(z)) if kind == "extrude_x" else (min(u), max(u), a, b, min(z), max(z))


def _rise(ruin, box):
    r, C = ruin.region, B.CUT_CELL
    x0, x1, y0, y1, _z0, z1 = box
    cuts = [ruin.cut(C * i + C / 2, C * j + C / 2)
            for i in range(math.floor(max(x0, r[0]) / C), math.floor((min(x1, r[1]) - 1e-6) / C) + 1)   # (a piece ending
            for j in range(math.floor(max(y0, r[2]) / C), math.floor((min(y1, r[3]) - 1e-6) / C) + 1)]  # on a cell line)
    return z1 - min(cuts)


def _in_region(r, b):
    return b[0] < r[1] and r[0] < b[1] and b[2] < r[3] and r[2] < b[3] and b[5] > r[4] + 0.35


def _wrap(kind):
    def f(self, *args, **kw):
        r = self.ruin.region
        name = getattr(self.lod, "name", "")
        if r is None or name not in LODS:
            return _ORIG[kind](self, *args, **kw)
        if kind == "box":                                    # cut pieces: log what the cells keep (sec review H2)
            real = self.lod.box
            kept = []

            def rec(a, b, c, d, z0, z1, **k2):
                kept.append((a, b, c, d, z0, z1))
                return real(a, b, c, d, z0, z1, **k2)
            self.lod.box = rec
            try:
                _ORIG[kind](self, *args, **kw)
            finally:
                del self.lod.box
            for bx in kept:
                if _in_region(r, bx):
                    _LOG.append((self.ruin.name, name, "box", True, 0.0, bx))
            return
        if kind in ("extrude_x", "extrude_y"):               # D96: mouldings are cut into runs per cell: log the runs
            real = getattr(self.lod, kind)
            runs = []

            def rec_e(prof, a, b, **k2):
                runs.append((prof, a, b))
                return real(prof, a, b, **k2)
            setattr(self.lod, kind, rec_e)
            try:
                _ORIG[kind](self, *args, **kw)
            finally:
                delattr(self.lod, kind)
            whole = _bbox(kind, args)
            kept_boxes = [_bbox(kind, ru) for ru in runs]
            for bx in kept_boxes:
                if _in_region(r, bx):
                    _LOG.append((self.ruin.name, name, kind, True, _rise(self.ruin, bx), bx))
            if not kept_boxes and _in_region(r, whole):
                _LOG.append((self.ruin.name, name, kind, False, _rise(self.ruin, whole), whole))
            return
        box = _bbox(kind, args)
        n0 = len(self.lod.faces)
        _ORIG[kind](self, *args, **kw)
        if _in_region(r, box):
            _LOG.append((self.ruin.name, name, kind, len(self.lod.faces) > n0, _rise(self.ruin, box), box))
    return f


def _cover(e, others):
    """Share of e's extent overlapped by the union bounding box of the counterparts that touch it, worst axis."""
    b = e[5]
    touch = [o[5] for o in others if all(o[5][2 * i] < b[2 * i + 1] and b[2 * i] < o[5][2 * i + 1] for i in range(3))]
    if not touch:
        return 0.0
    worst = 1.0
    for i in range(3):
        lo, hi = b[2 * i], b[2 * i + 1]
        if hi - lo < 1e-6:
            continue
        # merged overlap length of the counterparts' intervals on this axis
        iv = sorted((max(lo, t[2 * i]), min(hi, t[2 * i + 1])) for t in touch)
        tot, cur = 0.0, None
        for a, c in iv:
            if cur is None or a > cur[1]:
                if cur:
                    tot += cur[1] - cur[0]
                cur = [a, c]
            else:
                cur[1] = max(cur[1], c)
        tot += cur[1] - cur[0]
        worst = min(worst, tot / (hi - lo))
    return worst


def main():
    for k in _ORIG:
        setattr(B.RLod, k, _wrap(k))
    mods = {n: f for n, (f, _p, _f) in B.modules().items()}
    argv = sys.argv[1:]
    names = argv[argv.index("--only") + 1].split(",") if "--only" in argv else \
        [n for n in mods if n.endswith(("_Damaged", "_Ruined"))]
    fails, checked = [], 0
    for n in names:
        del _LOG[:]
        mods[n]()
        kept = {lod: [e for e in _LOG if e[1] == lod and e[3]] for lod in LODS}
        for e in _LOG:
            if e[2] == "box":
                continue
            short = min(e[5][1] - e[5][0], e[5][3] - e[5][2])
            if e[3] and e[4] > RISE:
                checked += 1
                if e[1] == "res0" and short >= THIN:
                    miss = [lod for lod in ("geo", "fire") if _cover(e, kept[lod]) < COVER]
                    if miss:
                        fails.append("%s: res0 %s kept %.2f m above the lowest cut, not covered by %s, box %s" % (
                            n, e[2], e[4], "/".join(miss), tuple(round(v, 2) for v in e[5])))
                elif e[1] != "res0" and _cover(e, kept["res0"]) < COVER:
                    fails.append("%s: %s %s kept %.2f m above the lowest cut with no res0 over it, box %s" % (
                        n, e[1], e[2], e[4], tuple(round(v, 2) for v in e[5])))
            elif not e[3] and e[1] != "res0" and short >= THIN:
                checked += 1                                    # collision dropped: the render there must be gone too
                if _cover(e, kept["res0"]) >= COVER:
                    fails.append("%s: %s %s dropped while res0 still covers it, box %s" % (
                        n, e[1], e[2], tuple(round(v, 2) for v in e[5])))
    for f in fails:
        print("  FAIL", f)
    print("RUIN CUT TEST: %s (%d models, %d whole pieces checked)" % (
        "%d FAILED" % len(fails) if fails else "PASS", len(names), checked))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
