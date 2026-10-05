"""Shared realism kit for SKY buildings (D53, docs/ASSET_QUALITY_GUIDE.md section 9).

Detail layer used by build_towera.py and build_floors.py on top of the gameplay shell.
Rules (so detail never changes gameplay):
  * Collision (Geometry) only where a player could otherwise clip into a solid that looks
    solid (columns, corner piers, benches, planters, units); everything thin or out of reach
    is visual (Res LODs) + Fire Geometry where bullets should stop.
  * Nothing in Geometry leaves the 24 x 24 footprint or enters the core clear zones; visual
    projections outside the footprint (cornices, fins, sills) stay <= 0.2 m.
  * Res0 carries the fine detail (frames, fins, trims), Res1 the bands and big forms, Res2 /
    Res3 only outer faces with opaque materials (no alpha far away).
Dimensions come from skyspec.DETAIL; no module-specific numbers here except defaults.
"""
import skyspec as S
from skygeo import UVBand, UVWorld, floor_quads_with_hole

HW, HD = S.TOWER_A["footprint"][0] / 2, S.TOWER_A["footprint"][1] / 2
CT = S.CURTAIN_T
CORE_HOLE = (S.CORE["x"][0], S.CORE["x"][1], S.CORE["y"][0], S.CORE["y"][1])
D = S.DETAIL

UV_ALU = UVBand(S.MATERIALS["metal"]["bands"]["alu"], 3.0)
UV_STEEL = UVBand(S.MATERIALS["metal"]["bands"]["steel"], 1.0)
UV_PAINT = UVBand(S.MATERIALS["metal"]["bands"]["painted"], 2.0)
UV_CONC_PANEL = UVBand(S.MATERIALS["concrete"]["bands"]["panel"], 3.0)
UV_CONC_REVEAL = UVBand(S.MATERIALS["concrete"]["bands"]["reveal"], 3.0)
UV_OAK = UVBand(S.MATERIALS["wood"]["bands"]["oak"], 2.0)
UV_WALNUT = UVBand(S.MATERIALS["wood"]["bands"]["walnut"], 2.0)
UV_WALL = UVWorld(4.0)
UV_GLASS = UVWorld(3.0)
UV_CEILING = UVWorld(S.MATERIALS["ceiling"]["sheet_m"])


class UVTrim:
    """Trim band at true scale: U every `scale` m along the face, V measured in metres from
    the face bottom over a band `band_m` tall (UVBand stretches the band over any face
    height; this keeps brick courses / panel joints at their real size on short faces)."""

    def __init__(self, band, scale, band_m):
        self.v0, self.v1 = band
        self.scale, self.band_m = scale, band_m

    def __call__(self, pts, normal):
        ax = max(range(3), key=lambda i: abs(normal[i]))
        along, across = {0: (1, 2), 1: (0, 2), 2: (0, 1)}[ax]
        c0 = min(p[across] for p in pts)
        return [(p[along] / self.scale,
                 1.0 - (self.v1 - min(1.0, (p[across] - c0) / self.band_m) * (self.v1 - self.v0))) for p in pts]


def _brick_uv(band):
    m = S.MATERIALS["brick"]
    b = m["bands"][band]
    # sheet is square: a band of height (v1 - v0) covers (v1 - v0) * sheet_m metres
    return UVTrim(b, m["sheet_m"], (b[1] - b[0]) * m["sheet_m"])


def _panel_uv(band):
    m = S.MATERIALS["concpanel"]
    b = m["bands"][band]
    return UVTrim(b, m["sheet_m"], (b[1] - b[0]) * m["sheet_m"])


# Facade skins for the ribbon-window facade (apartments = brick, hotel = precast panels).
SKINS = {
    "brick": {"mat": "brick", "uv": _brick_uv("bond"), "sill_uv": _brick_uv("sill"),
              "soldier_uv": _brick_uv("soldier"), "pen": "masonry"},
    "panel": {"mat": "concpanel", "uv": _panel_uv("panel"), "sill_uv": UV_CONC_REVEAL, "sill_mat": "concrete",
              "soldier_uv": None, "pen": "concrete"},
}


def _kw(k, mat, uv, pen):
    if k.startswith("res"):
        return {"mat": mat, "uv": uv}
    return {"mat": "pen_" + pen} if k == "fire" else {}


# ------------------------------------------------------------------ facade sides
SIDES = {"S": ("x", -HD), "N": ("x", HD), "W": ("y", -HW), "E": ("y", HW)}


class Side:
    """One facade side. `a` runs along the side, `d` is the depth measured INWARD from the
    outer face (d < 0 = outside the footprint), z is height. trim=True shortens the E/W
    sides by CT at both ends so they butt into the N/S sides (no coplanar corner overlap)."""

    def __init__(self, key, trim=False):
        self.axis, self.plane = SIDES[key]
        self.sgn = 1 if self.plane > 0 else -1
        span = HW if self.axis == "x" else HD
        self.a0, self.a1 = -span, span
        if trim and self.axis == "y":
            self.a0, self.a1 = -span + CT, span - CT
        ax = "y" if self.axis == "x" else "x"
        self.out_key = ("+" if self.sgn > 0 else "-") + ax
        self.in_key = ("-" if self.sgn > 0 else "+") + ax
        self.end_keys = ("-" + self.axis, "+" + self.axis)
        self.out = (0, self.sgn, 0) if self.axis == "x" else (self.sgn, 0, 0)
        self.inward = tuple(-v for v in self.out)

    def _d(self, depth):
        return self.plane - self.sgn * depth

    def box(self, lod, a0, a1, z0, z1, d0, d1, **kw):
        p, q = sorted((self._d(d0), self._d(d1)))
        if self.axis == "x":
            lod.box(a0, a1, p, q, z0, z1, **kw)
        else:
            lod.box(p, q, a0, a1, z0, z1, **kw)

    def rect(self, a0, a1, z0, z1, depth):
        c = self._d(depth)
        if self.axis == "x":
            return [(a0, c, z0), (a1, c, z0), (a1, c, z1), (a0, c, z1)]
        return [(c, a0, z0), (c, a1, z0), (c, a1, z1), (c, a0, z1)]

    def quad(self, lod, a0, a1, z0, z1, depth, inward=False, **kw):
        lod.quad(self.rect(a0, a1, z0, z1, depth), self.inward if inward else self.out, **kw)


def _outside(a, entrances):
    return not any(e0 - 0.05 < a < e1 + 0.05 for (e0, e1, _top) in entrances)


def curtain_details(L, z0, z1, side_entrances=None, spandrel=None, fins=True, cornice=True, plinth=0.0):
    """Realism layer for build_towera.facade() (curtain wall):
    spandrel  opaque back-panel behind the glass in the top `spandrel` m of the storey (hides the
              ceiling void, the classic office band) + horizontal mullion at its bottom edge
    fins      deep vertical aluminium fins every DETAIL["fin_step"] m (Res0)
    cornice   slab-nose band at the floor line, projecting DETAIL["cornice_d"] (Res0-Res2)
    corners   concrete-clad corner piers (Res0-Res2 + Geometry/View/Fire: they look solid)
    plinth    stone base band of this height (lobby), skipped at the entrances"""
    side_entrances = side_entrances or {}
    sp = D["spandrel"] if spandrel is None else spandrel
    for key in SIDES:
        sd = Side(key)
        ent = side_entrances.get(key, [])
        if sp > 0:
            zs = z1 - sp
            for k in ("res0", "res1"):
                # painted back-panel (metal sheet: no extra section per floor, perf D53)
                sd.quad(L[k], sd.a0, sd.a1, zs, z1, CT / 2 + 0.03, mat="metal", uv=UV_PAINT)
                sd.quad(L[k], sd.a0, sd.a1, zs, z1, CT / 2 + 0.031, inward=True, mat="metal", uv=UV_PAINT)
                sd.box(L[k], sd.a0, sd.a1, zs - 0.04, zs + 0.04, -0.04, CT + 0.02, mat="metal", uv=UV_ALU,
                       skip=sd.end_keys)
        if fins:
            step = D["fin_step"]
            n = int(round((sd.a1 - sd.a0) / step))
            for i in range(1, n):
                a = sd.a0 + i * (sd.a1 - sd.a0) / n
                if not _outside(a, ent):
                    continue
                sd.box(L["res0"], a - 0.03, a + 0.03, z0, z1, -D["fin_d"], 0.0, mat="metal", uv=UV_ALU,
                       skip=("-z", "+z", sd.in_key))
        if cornice:
            ext = D["cornice_d"] if sd.axis == "x" else 0.0          # N/S wrap the corners
            for k in ("res0", "res1", "res2"):
                sd.box(L[k], sd.a0 - ext, sd.a1 + ext, z0 - S.SLAB_T - 0.02, z0 + 0.02, -D["cornice_d"], 0.0,
                       mat="metal", uv=UV_ALU, skip=(sd.in_key,))
        if plinth > 0:
            segs, cur = [], sd.a0
            for e0, e1, _top in sorted(ent):
                segs.append((cur, e0))
                cur = e1
            segs.append((cur, sd.a1))
            for a0, a1 in segs:
                for k in ("res0", "res1"):
                    sd.box(L[k], a0, a1, z0, z0 + plinth, -0.04, CT + 0.01, mat="concrete", uv=UV_CONC_REVEAL,
                           skip=("-z",))
    corner_piers(L, z0, z1)


def corner_piers(L, z0, z1, size=None):
    s = size or D["corner_pier"]
    w = D["cornice_d"] - 0.01            # visual pier wraps the corner mullions (they project 0.04)
    for sx in (-1, 1):
        for sy in (-1, 1):
            for k in ("res0", "res1", "res2", "geo", "view", "fire"):
                o = w if k.startswith("res") else 0.0     # collision stays inside the footprint
                x0, x1 = sorted((sx * (HW + o), sx * (HW - s)))
                y0, y1 = sorted((sy * (HD + o), sy * (HD - s)))
                kw = _kw(k, "concrete", UV_CONC_PANEL, "concrete")
                if k.startswith("res"):
                    kw["skip"] = ("-z", "+z")
                L[k].box(x0, x1, y0, y1, z0, z1, **kw)


# ------------------------------------------------------------------ ribbon-window facade
def ribbon_facade(L, z0, z1, skin, entrances=None):
    """Masonry facade with recessed ribbon windows (apartments / hotel). Per side: sill band
    (z0..sill), head band (head..z1), piers every bay, windows recessed DETAIL["reveal"] m with
    frames, a centre mullion, a projecting sill stone and (brick) a soldier course.
    Inner face of the wall = plane - CT (same as the curtain wall: furniture / loot unchanged).
    Geometry: one box per side (as before); View / Fire: bands + piers (+ pen_glass panes)."""
    R = D["ribbon"]
    sk = SKINS[skin]
    sill, head, pier = R["sill"], R["head"], R["pier"]
    mat, uv = sk["mat"], sk["uv"]
    rec = CT - D["reveal_back"]                       # glass plane depth (recessed from the outer face)
    for key in SIDES:
        sd = Side(key, trim=True)
        span = sd.a1 - sd.a0
        n = int(round(span / R["bay"]))
        posts = [sd.a0 + i * span / n for i in range(n + 1)]
        corner = CT if sd.axis == "y" else 0.0         # E/W end piers continue the N/S corner pier
        piers = []
        for i, p in enumerate(posts):
            if i == 0:
                piers.append((p, p + pier - corner))
            elif i == n:
                piers.append((p - pier + corner, p))
            else:
                piers.append((p - pier / 2, p + pier / 2))
        windows = [(piers[i][1], piers[i + 1][0]) for i in range(n)]
        # --- bands + piers
        for k in ("res0", "res1", "res2", "view", "fire"):
            if k == "res2":
                sd.quad(L[k], sd.a0, sd.a1, z0, sill, 0.0, mat=mat, uv=uv)
                sd.quad(L[k], sd.a0, sd.a1, head, z1, 0.0, mat=mat, uv=uv)
                for a0, a1 in piers:
                    sd.quad(L[k], a0, a1, sill, head, 0.0, mat=mat, uv=uv)
                continue
            kw = _kw(k, mat, uv, sk["pen"])
            res = k.startswith("res")
            sd.box(L[k], sd.a0, sd.a1, z0, sill, 0.0, CT, skip=("-z", sd.in_key) if res else (), **kw)
            sd.box(L[k], sd.a0, sd.a1, head, z1, 0.0, CT, skip=("+z", sd.in_key) if res else (), **kw)
            for a0, a1 in piers:
                sd.box(L[k], a0, a1, sill, head, 0.0, CT, skip=("-z", "+z", sd.in_key) if res else (), **kw)
        for k in ("res0", "res1"):                     # interior plaster face of the wall
            sd.quad(L[k], sd.a0, sd.a1, z0, sill, CT, inward=True, mat="wall", uv=UV_WALL)
            sd.quad(L[k], sd.a0, sd.a1, head, z1, CT, inward=True, mat="wall", uv=UV_WALL)
            for a0, a1 in piers:
                sd.quad(L[k], a0, a1, sill, head, CT, inward=True, mat="wall", uv=UV_WALL)
        # --- windows
        for a0, a1 in windows:
            L["res0"].quad(sd.rect(a0, a1, sill, head, rec), sd.out, "glass", UV_GLASS, double=True)
            L["res1"].quad(sd.rect(a0, a1, sill, head, rec), sd.out, "glass", UV_GLASS)
            L["res2"].quad(sd.rect(a0, a1, sill, head, rec), sd.out, "glassfar", UV_GLASS)
            sd.box(L["fire"], a0, a1, sill, head, 0.0, CT, mat="pen_glass")
            r0 = L["res0"]
            fw, fd = D["frame_w"], D["frame_d"]
            f0, f1 = rec - fd / 2, rec + fd / 2
            sb = sill + D["sill_stone"][1]             # top of the sill stone
            # sill stone: projects outward, runs under the frame
            sd.box(r0, a0 - 0.04, a1 + 0.04, sill - D["sill_stone"][0], sb, -D["sill_stone"][2], f1,
                   mat=sk.get("sill_mat", mat), uv=sk["sill_uv"], skip=(sd.in_key,))
            # frame: jambs, head, bottom rail, centre mullion (painted aluminium)
            fkw = {"mat": "metal", "uv": UV_PAINT}
            sd.box(r0, a0, a0 + fw, sb, head, f0, f1, skip=("-z", "+z", sd.end_keys[0]), **fkw)
            sd.box(r0, a1 - fw, a1, sb, head, f0, f1, skip=("-z", "+z", sd.end_keys[1]), **fkw)
            sd.box(r0, a0 + fw, a1 - fw, head - fw, head, f0, f1, skip=("+z",) + sd.end_keys, **fkw)
            sd.box(r0, a0 + fw, a1 - fw, sb, sb + fw, f0, f1, skip=("-z",) + sd.end_keys, **fkw)
            m = (a0 + a1) / 2
            sd.box(r0, m - fw / 2, m + fw / 2, sb + fw, head - fw, f0, f1, skip=("-z", "+z"), **fkw)
            if sk["soldier_uv"] is not None:           # soldier course over the opening
                sd.quad(r0, a0 - 0.1, a1 + 0.1, head, head + D["soldier_h"], -0.004, mat=mat, uv=sk["soldier_uv"])
    # Geometry: one solid per side over the full storey (unchanged collision, 4 components)
    for key in SIDES:
        sd = Side(key, trim=True)
        sd.box(L["geo"], sd.a0, sd.a1, z0, z1, 0.0, CT)


def ribbon_far(L, z0, z1, skin):
    """Res3 for ribbon floors: three stacked bands (masonry / dark glass / masonry), 24 tris."""
    R = D["ribbon"]
    sk = SKINS[skin]
    for (b0, b1), mat, uv in (((z0 - S.SLAB_T, R["sill"]), sk["mat"], sk["uv"]),
                              ((R["sill"], R["head"]), "glassfar", UV_GLASS),
                              ((R["head"], z1), sk["mat"], sk["uv"])):
        L["res3"].box(-HW, HW, -HD, HD, b0, b1, mat=mat, uv=uv, skip=("+z", "-z"))


# ------------------------------------------------------------------ interiors
def ceiling(L, z, mat="ceiling", uv=None, inset=CT, lods=("res0", "res1")):
    """Downward-facing ceiling over the storey (core hole kept). Seen from above it is
    invisible (single-sided), so it never hides the slab of the module above."""
    for k in lods:
        floor_quads_with_hole(L[k], HW - inset, HD - inset, CORE_HOLE, z, mat=mat, uv=uv or UV_CEILING, up=False)


def door_trims(L, walls, ht, z_top=2.1, mat="wood", uv=None, lods=("res0",)):
    """Architraves on both faces of every partition opening.
    walls: [("x"|"y", c, a0, a1, [(o0, o1), ...])] (build_floors.partitions format), ht = half wall thickness."""
    w, p = D["trim_w"], D["trim_d"]
    uv = uv or UV_OAK
    for k in lods:
        for axis, c, _a0, _a1, ops in walls:
            for (o0, o1) in ops:
                for s in (-1, 1):
                    f0, f1 = sorted((c + s * ht, c + s * (ht + p)))
                    back = ("-" if s > 0 else "+") + ("y" if axis == "x" else "x")
                    pieces = [(o0 - w, o0, 0.0, z_top + w), (o1, o1 + w, 0.0, z_top + w), (o0, o1, z_top, z_top + w)]
                    for a0, a1, b0, b1 in pieces:
                        if axis == "x":
                            L[k].box(a0, a1, f0, f1, b0, b1, mat=mat, uv=uv, skip=(back, "-z"))
                        else:
                            L[k].box(f0, f1, a0, a1, b0, b1, mat=mat, uv=uv, skip=(back, "-z"))


def skirting(L, walls, ht, h=0.08, mat="wood", uv=None, lods=("res0",)):
    """Skirting boards along partition walls (both faces, broken at the openings)."""
    for k in lods:
        for axis, c, a0, a1, ops in walls:
            cuts = sorted(ops)
            segs, cur = [], a0
            for o0, o1 in cuts:
                segs.append((cur, o0))
                cur = o1
            segs.append((cur, a1))
            for s in (-1, 1):
                f0, f1 = sorted((c + s * ht, c + s * (ht + 0.012)))
                back = ("-" if s > 0 else "+") + ("y" if axis == "x" else "x")
                for g0, g1 in segs:
                    if g1 - g0 < 0.05:
                        continue
                    kw = {"mat": mat, "uv": uv or UV_WALNUT, "skip": (back, "-z")}
                    if axis == "x":
                        L[k].box(g0, g1, f0, f1, 0.0, h, **kw)
                    else:
                        L[k].box(f0, f1, g0, g1, 0.0, h, **kw)


def columns(L, pts, z0, z1, r=None):
    """Round concrete columns (Res0 16 sides, Res1 8); collision / view = inscribed box
    (12 tris, keeps Geometry inside its triangle budget), Fire = octagon."""
    r = r or D["column_r"]
    for (x, y) in pts:
        L["res0"].prism(x, y, r, z0, z1, n=16, mat="concrete", uv=UV_CONC_PANEL)
        L["res1"].prism(x, y, r, z0, z1, n=8, mat="concrete", uv=UV_CONC_PANEL)
        b = 0.9 * r
        L["geo"].box(x - b, x + b, y - b, y + b, z0, z1)
        L["view"].box(x - b, x + b, y - b, y + b, z0, z1)
        L["fire"].prism(x, y, r, z0, z1, n=8, mat="pen_concrete")


# ------------------------------------------------------------------ furniture-scale fixed parts
def bench(L, x0, x1, y0, y1, h=0.45, collide=True):
    """Fixed bench: oak slats on two concrete legs (Res0), one block (Res1), one collision box."""
    along_x = (x1 - x0) >= (y1 - y0)
    L["res0"].box(x0, x1, y0, y1, h - 0.06, h, mat="wood", uv=UV_OAK)
    for t in (0.15, 0.85):
        if along_x:
            a = x0 + t * (x1 - x0)
            L["res0"].box(a - 0.06, a + 0.06, y0 + 0.05, y1 - 0.05, 0.0, h - 0.06, mat="concrete", uv=UV_CONC_REVEAL,
                          skip=("-z", "+z"))
        else:
            a = y0 + t * (y1 - y0)
            L["res0"].box(x0 + 0.05, x1 - 0.05, a - 0.06, a + 0.06, 0.0, h - 0.06, mat="concrete", uv=UV_CONC_REVEAL,
                          skip=("-z", "+z"))
    L["res1"].box(x0, x1, y0, y1, 0.0, h, mat="wood", uv=UV_OAK, skip=("-z",))
    if collide:
        L["geo"].box(x0, x1, y0, y1, 0.0, h)
        L["fire"].box(x0, x1, y0, y1, 0.0, h, mat="pen_wood")


def unit(L, x0, x1, y0, y1, h, grille=None, fan=True, far=False):
    """Plant / HVAC unit: steel body with a plinth, a control-panel face (atlas) and a fan
    housing. grille = side key ('-x', '+x', '-y', '+y') carrying the panel, or None."""
    for k in ("res0", "res1", "geo", "view", "fire") + (("res2",) if far else ()):
        kw = _kw(k, "metal", UV_STEEL, "metal")
        if k.startswith("res"):
            kw["skip"] = ("-z",)
        L[k].box(x0, x1, y0, y1, 0.0, h, **kw)
    r0 = L["res0"]
    r0.box(x0 - 0.04, x1 + 0.04, y0 - 0.04, y1 + 0.04, 0.0, 0.12, mat="concrete", uv=UV_CONC_REVEAL, skip=("-z",))
    r0.box(x0 - 0.02, x1 + 0.02, y0 - 0.02, y1 + 0.02, h - 0.08, h + 0.02, mat="metal", uv=UV_PAINT, skip=("-z",))
    if grille:
        atlas_panel(r0, x0, x1, y0, y1, h, grille)
    if fan:
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        rr = min(0.6, (min(x1 - x0, y1 - y0)) / 2 - 0.1)
        r0.prism(cx, cy, rr, h, h + 0.3, n=12, mat="metal", uv=UV_ALU)
        r0.prism(cx, cy, rr * 0.25, h + 0.3, h + 0.36, n=6, mat="metal", uv=UV_PAINT)
        L["res1"].prism(cx, cy, rr, h, h + 0.3, n=6, mat="metal", uv=UV_ALU)


def atlas_panel(lod, x0, x1, y0, y1, h, side, cell="panel", size=(1.0, 1.0)):
    """Atlas-textured panel on one face of a box (control panel, signage)."""
    from skygeo import UVRect
    u0, v0, u1, v1 = S.atlas_uv(cell)
    w, ph = size
    zc = min(h - 0.2, 1.4)
    if side in ("-y", "+y"):
        y = (y0 - 0.01) if side == "-y" else (y1 + 0.01)
        xc = (x0 + x1) / 2
        pts = [(xc - w / 2, y, zc - ph / 2), (xc + w / 2, y, zc - ph / 2), (xc + w / 2, y, zc + ph / 2), (xc - w / 2, y, zc + ph / 2)]
        uvm = UVRect(0, 2, (xc - w / 2, zc - ph / 2), (xc + w / 2, zc + ph / 2), (u0, v0, u1, v1))
        if side == "+y":
            uvm = UVRect(0, 2, (xc + w / 2, zc - ph / 2), (xc - w / 2, zc + ph / 2), (u0, v0, u1, v1))
        lod.quad(pts, (0, -1 if side == "-y" else 1, 0), "atlas", uvm)
    else:
        x = (x0 - 0.01) if side == "-x" else (x1 + 0.01)
        yc = (y0 + y1) / 2
        pts = [(x, yc - w / 2, zc - ph / 2), (x, yc + w / 2, zc - ph / 2), (x, yc + w / 2, zc + ph / 2), (x, yc - w / 2, zc + ph / 2)]
        uvm = UVRect(1, 2, (yc - w / 2, zc - ph / 2), (yc + w / 2, zc + ph / 2), (u0, v0, u1, v1))
        if side == "-x":
            uvm = UVRect(1, 2, (yc + w / 2, zc - ph / 2), (yc - w / 2, zc + ph / 2), (u0, v0, u1, v1))
        lod.quad(pts, (-1 if side == "-x" else 1, 0, 0), "atlas", uvm)


def mast(L, x, y, h):
    """Antenna / lightning mast: steel pole with two cross arms (visual + Fire; too thin to collide)."""
    L["res0"].prism(x, y, 0.06, 0.0, h, n=8, mat="metal", uv=UV_STEEL)
    L["res1"].prism(x, y, 0.06, 0.0, h, n=4, mat="metal", uv=UV_STEEL)
    L["res0"].prism(x, y, 0.2, 0.0, 0.15, n=8, mat="concrete", uv=UV_CONC_REVEAL)
    for z in (h * 0.6, h * 0.85):
        L["res0"].box(x - 0.5, x + 0.5, y - 0.02, y + 0.02, z, z + 0.04, mat="metal", uv=UV_STEEL)
    L["fire"].prism(x, y, 0.06, 0.0, h, n=4, mat="pen_metal")


def coping(L, h, t, lods=("res0", "res1")):
    """Aluminium coping on a parapet of height h and thickness t (overhangs 3 cm both sides)."""
    o = 0.03
    rings = [(-HW - o, HW + o, -HD - o, -HD + t + o), (-HW - o, HW + o, HD - t - o, HD + o),
             (-HW - o, -HW + t + o, -HD + t + o, HD - t - o), (HW - t - o, HW + o, -HD + t + o, HD - t - o)]
    for k in lods:
        for (x0, x1, y0, y1) in rings:
            L[k].box(x0, x1, y0, y1, h, h + 0.05, mat="metal", uv=UV_ALU, skip=("-z",))
