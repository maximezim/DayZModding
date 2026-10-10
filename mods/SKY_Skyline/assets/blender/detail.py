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
UV_MARBLE = UVWorld(S.MATERIALS["marble"]["sheet_m"])
UV_PARQUET = UVWorld(S.MATERIALS["parquet"]["sheet_m"])


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
        if ax == 2 and (max(p[1] for p in pts) - min(p[1] for p in pts)) > (max(p[0] for p in pts) - min(p[0] for p in pts)):
            along, across = 1, 0                     # D96: horizontal faces run U along their longer side
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


def paint_uv(band):
    """Interior paint colour band (stretched over the face height: the bands are flat colour)."""
    return UVBand(S.MATERIALS["paint"]["bands"][band], 4.0)


def stone_uv(band):
    m = S.MATERIALS["stone"]
    b = m["bands"][band]
    return UVTrim(b, m["sheet_m"], (b[1] - b[0]) * m["sheet_m"])


def band_fit(band_mat, band, x0, x1, y0, y1, axes=(0, 1), u_rep=1.0):
    """Fit a rectangle onto one band of a trim sheet (rugs, runners, curtains)."""
    from skygeo import UVRect
    v0, v1 = S.MATERIALS[band_mat]["bands"][band]
    return UVRect(axes[0], axes[1], (x0, y0), (x1, y1), (0.0, 1.0 - v1, u_rep, 1.0 - v0))


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


def curtain_details(L, z0, z1, side_entrances=None, spandrel=None, fins=True, cornice=True, plinth=0.0,
                    pier_mat="concrete", pier_uv=None, plinth_mat="concrete", plinth_uv=None):
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
                # D96: rail 1 cm shallower than the mullions (their inner faces met in one plane); N / S rails run
                # 4 cm past the corners, W / E rails butt into them (the corner squares overlapped)
                ra, rb = (sd.a0 - 0.035, sd.a1 + 0.035) if sd.axis == "x" else (sd.a0 + CT + 0.01, sd.a1 - CT - 0.01)
                sd.box(L[k], ra, rb, zs - 0.04, zs + 0.04, -0.04, CT + 0.01, mat="metal", uv=UV_ALU,
                       skip=sd.end_keys if sd.axis == "y" else ())
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
                if sd.axis == "y":                     # D96: W / E runs butt into the N / S runs (corners overlapped)
                    a0, a1 = max(a0, sd.a0 + CT + 0.01), min(a1, sd.a1 - CT - 0.01)
                for k in ("res0", "res1"):
                    sd.box(L[k], a0, a1, z0, z0 + plinth, -0.035, CT + 0.01, mat=plinth_mat,   # (corner mullion at -0.04)
                           uv=plinth_uv or UV_CONC_REVEAL, skip=("-z",))
    corner_piers(L, z0, z1, mat=pier_mat, uv=pier_uv)


UV_HQ_BRONZE = UVBand(S.MATERIALS["hqfacade"]["bands"]["bronze"], 3.0)
UV_HQ_SPANDREL = UVBand(S.MATERIALS["hqfacade"]["bands"]["spandrel"], 6.0)
UV_HQ_LOUVRE = UVBand(S.MATERIALS["hqfacade"]["bands"]["louvre"], 3.0)
UV_HQ_GRANITE = UVBand(S.MATERIALS["hqfacade"]["bands"]["granite"], 6.0)


def hq_details(L, z0, z1, spandrel=0.6):
    """HQ landmark curtain wall (D60) on top of build_towera.facade(): a ribbed bronze spandrel
    band over each slab (slab nose + the top `spandrel` m of the storey, read as one 0.9 m band
    across two floors), louvred spandrels in the end bays (plant intakes), bronze fins on every
    1.5 m mullion (Res0; every 3 m in Res1), granite corner piers. All visual except the piers
    (collide, like curtain_details); projections <= DETAIL["fin_d"] outside the footprint."""
    fd = D["fin_d"]
    for key in SIDES:
        sd = Side(key)
        n = int(round((sd.a1 - sd.a0) / 1.5))
        bays = [(sd.a0 + i * (sd.a1 - sd.a0) / n, sd.a0 + (i + 1) * (sd.a1 - sd.a0) / n) for i in range(n)]
        for i, (a0, a1) in enumerate(bays):
            uv = UV_HQ_LOUVRE if i in (1, n - 2) else UV_HQ_SPANDREL
            for k in ("res0", "res1", "res2"):
                sd.quad(L[k], a0, a1, z1 - spandrel, z1, -0.045, mat="hqfacade", uv=uv)
                sd.quad(L[k], a0, a1, z0 - S.SLAB_T, z0, -0.045, mat="hqfacade", uv=UV_HQ_SPANDREL)
            sd.quad(L["res0"], a0, a1, z1 - spandrel, z1, CT / 2 + 0.03, inward=True, mat="metal", uv=UV_PAINT)
        for lod_key, step in (("res0", 1), ("res1", 2)):
            for i in range(step, n, step):
                a = sd.a0 + i * (sd.a1 - sd.a0) / n
                sd.box(L[lod_key], a - 0.04, a + 0.04, z0 - S.SLAB_T, z1, -fd, -0.045, mat="hqfacade", uv=UV_HQ_BRONZE,
                       skip=("-z", "+z", sd.in_key))
        # spandrel edges: thin bronze reveal lines top / bottom of the band (Res0)
        for zz in (z1 - spandrel, z0 - S.SLAB_T):
            sd.box(L["res0"], sd.a0, sd.a1, zz - 0.02, zz + 0.02, -0.07, -0.045, mat="hqfacade", uv=UV_HQ_BRONZE,
                   skip=sd.end_keys + (sd.in_key,))
    corner_piers(L, z0, z1, mat="hqfacade", uv=UV_HQ_GRANITE)


def corner_piers(L, z0, z1, size=None, mat="concrete", uv=None):
    s = size or D["corner_pier"]
    uv = uv or UV_CONC_PANEL
    w = D["cornice_d"] - 0.01            # visual pier wraps the corner mullions (they project 0.04)
    for sx in (-1, 1):
        for sy in (-1, 1):
            for k in ("res0", "res1", "res2", "geo", "view", "fire"):
                o = w if k.startswith("res") else 0.0     # collision stays inside the footprint
                x0, x1 = sorted((sx * (HW + o), sx * (HW - s)))
                y0, y1 = sorted((sy * (HD + o), sy * (HD - s)))
                kw = _kw(k, mat, uv, "concrete")
                if k.startswith("res"):
                    kw["skip"] = ("-z", "+z")
                L[k].box(x0, x1, y0, y1, z0, z1, **kw)


# ------------------------------------------------------------------ ribbon-window facade
def ribbon_facade(L, z0, z1, skin, entrances=None, dress=True, window_boxes=False, inner_mat="wall", inner_uv=None):
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
        iuv = inner_uv or UV_WALL
        for k in ("res0", "res1"):                     # interior finish face of the wall
            sd.quad(L[k], sd.a0, sd.a1, z0, sill, CT, inward=True, mat=inner_mat, uv=iuv)
            sd.quad(L[k], sd.a0, sd.a1, head, z1, CT, inward=True, mat=inner_mat, uv=iuv)
            for a0, a1 in piers:
                sd.quad(L[k], a0, a1, sill, head, CT, inward=True, mat=inner_mat, uv=iuv)
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
            wi = windows.index((a0, a1))
            if dress:
                window_dressing(r0, sd, a0, a1, sill, head)
            if window_boxes and wi % 2 == 0:
                window_box(r0, sd, a0, a1, sill)
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
        zt = z1 - 0.005                         # D96: top 5 mm under the ceiling (partition tops met it in one plane)
        L["res0"].prism(x, y, r, z0, zt, n=16, mat="concrete", uv=UV_CONC_PANEL)
        L["res1"].prism(x, y, r, z0, zt, n=8, mat="concrete", uv=UV_CONC_PANEL)
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
        for k in ("geo", "fire", "view"):                                        # D82: the fan drum on a climbable
            L[k].prism(cx, cy, rr, h, h + 0.3, n=8, **_kw(k, "metal", UV_ALU, "metal"))   # unit collides (head fit in)
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


# ================================================================== splendour pass (D55)
# Interior decoration and light fixtures, baked into the module P3Ds. Visual only unless the
# piece is big enough to walk into (plant pots, lounge chairs, pumps): those get one collision box.
def _uvfit(cell_uv, a_axis, lo, hi):
    from skygeo import UVRect
    u0, v0, u1, v1 = cell_uv
    return UVRect(a_axis, 2, lo, hi, (u0, v0, u1, v1))


def window_dressing(r0, sd, a0, a1, sill, head):
    """Inside a ribbon window (Res0): curtain rod, two drawn-back curtains, radiator under the sill."""
    cw = D["curtain_w"]
    d = CT + 0.07                                       # curtain plane, 7 cm inside the wall face
    sd.box(r0, a0 - 0.25, a1 + 0.25, head + 0.12, head + 0.15, CT + 0.05, CT + 0.08, mat="metal", uv=UV_STEEL,
           skip=(sd.out_key,))
    for c0, c1 in ((a0 - 0.2, a0 - 0.2 + cw), (a1 + 0.2 - cw, a1 + 0.2)):
        uv = band_fit("textile", "curtain", c0, c1, 0.05, head + 0.12, axes=(0 if sd.axis == "x" else 1, 2), u_rep=cw / 0.6)
        sd.quad(r0, c0, c1, 0.05, head + 0.12, d, inward=True, mat="textile", uv=uv)
        sd.quad(r0, c0, c1, 0.05, head + 0.12, d, inward=False, mat="textile", uv=uv)
    m = (a0 + a1) / 2
    sd.box(r0, m - 0.55, m + 0.55, 0.15, 0.7, CT + 0.03, CT + 0.11, mat="paint", uv=paint_uv("white"),
           skip=(sd.out_key, "-z"))


def window_box(r0, sd, a0, a1, sill):
    """Flower box under a ribbon window, outside (Res0, visual)."""
    sd.box(r0, a0 + 0.1, a1 - 0.1, sill - 0.32, sill - 0.08, -0.26, -0.02, mat="wood", uv=UV_WALNUT,
           skip=(sd.in_key,))
    from skygeo import UVRect
    pts = sd.rect(a0 + 0.15, a1 - 0.15, sill - 0.1, sill + 0.28, -0.14)
    ax = 0 if sd.axis == "x" else 1
    r0.quad(pts, sd.out, "foliage", UVRect(ax, 2, (a0 + 0.15, sill - 0.1), (a1 - 0.15, sill + 0.28), (0, 0, 2, 0.6)),
            double=True)


def floor_finish(L, rects, mat, uv, z=0.003, lods=("res0", "res1")):
    """Finish layer over the slab top (parquet in flats, marble in the lobby, runners)."""
    for k in lods:
        for (x0, x1, y0, y1) in rects:
            L[k].hquad(x0, x1, y0, y1, z, mat=mat, uv=uv)


def _overlaps2(a, b):
    return a[0] < b[1] and b[0] < a[1] and a[2] < b[3] and b[2] < a[3]


def light_panels(L, z, exclude=(), lods=("res0", "res1"), mat="lamp_cool"):
    """Recessed 0.6 x 1.2 m light panels on the ceiling tile grid (emissive, facing down)."""
    gx, gy = D["panel_grid"]
    core = (CORE_HOLE[0] - 0.3, CORE_HOLE[1] + 0.3, CORE_HOLE[2] - 0.3, CORE_HOLE[3] + 0.3)
    out = []
    x = -9.0
    while x + 0.6 <= HW - CT - 0.6:
        y = -10.8
        while y + 1.2 <= HD - CT - 0.3:
            r = (x, x + 0.6, y, y + 1.2)
            if not _overlaps2(r, core) and not any(_overlaps2(r, e) for e in exclude):
                out.append(r)
            y += gy
        x += gx
    for k in lods:
        for (x0, x1, y0, y1) in out:
            L[k].hquad(x0, x1, y0, y1, z - 0.003, mat=mat, up=False)
    return out


def downlight(L, x, y, z, r=0.09, mat="lamp"):
    """Round recessed downlight (Res0): emissive disc just under the ceiling."""
    L["res0"].prism(x, y, r, z - 0.012, z, n=10, mat=mat)


def pendant(L, x, y, z_top, drop, r=0.25, mat="lamp"):
    """Pendant lamp: rod, metal shade, emissive diffuser (Res0); shade only in Res1."""
    zb = z_top - drop
    sh = 0.14                         # D82: shallow shade - a 0.25 m drum was a render-only volume a head fit in
    L["res0"].box(x - 0.008, x + 0.008, y - 0.008, y + 0.008, zb + sh, z_top, mat="metal", uv=UV_STEEL, skip=("+z",))
    L["res0"].prism(x, y, r, zb + 0.02, zb + sh, n=16, mat="metal", uv=UV_PAINT)
    L["res0"].prism(x, y, r * 0.85, zb, zb + 0.02, n=16, mat=mat)
    L["res1"].prism(x, y, r, zb, zb + sh, n=8, mat="metal", uv=UV_PAINT)


def sconce(L, x, y, z, face, mat="lamp"):
    """Wall sconce on a wall face; face = outward normal key of that wall face ('+x', '-y', ...)."""
    s = 1 if face[0] == "+" else -1
    if face[1] == "x":
        x0, x1 = sorted((x, x + s * 0.1))
        L["res0"].box(x0, x1, y - 0.09, y + 0.09, z - 0.14, z + 0.14, mat=mat, skip=(("-" if s > 0 else "+") + "x",))
    else:
        y0, y1 = sorted((y, y + s * 0.1))
        L["res0"].box(x - 0.09, x + 0.09, y0, y1, z - 0.14, z + 0.14, mat=mat, skip=(("-" if s > 0 else "+") + "y",))


def wall_art(L, x, y, z, w, h, face, cell, lods=("res0", "res1")):
    """Framed artwork (atlas cell incl. its frame) on a wall face, 3 cm proud."""
    from skygeo import UVRect
    u0, v0, u1, v1 = S.atlas_uv(cell)
    s = 1 if face[0] == "+" else -1
    for k in lods:
        if face[1] == "x":
            fx = x + s * 0.03
            if k == "res0":
                x0, x1 = sorted((x, fx))
                L[k].box(x0, x1, y - w / 2, y + w / 2, z - h / 2, z + h / 2, mat="wood", uv=UV_WALNUT,
                         skip=(("-" if s > 0 else "+") + "x",))
            pts = [(fx + s * 0.002, y - w / 2, z - h / 2), (fx + s * 0.002, y + w / 2, z - h / 2),
                   (fx + s * 0.002, y + w / 2, z + h / 2), (fx + s * 0.002, y - w / 2, z + h / 2)]
            lo, hi = ((y + w / 2, z - h / 2), (y - w / 2, z + h / 2)) if s < 0 else ((y - w / 2, z - h / 2), (y + w / 2, z + h / 2))
            L[k].quad(pts, (s, 0, 0), "atlas", UVRect(1, 2, lo, hi, (u0, v0, u1, v1)))
        else:
            fy = y + s * 0.03
            if k == "res0":
                y0, y1 = sorted((y, fy))
                L[k].box(x - w / 2, x + w / 2, y0, y1, z - h / 2, z + h / 2, mat="wood", uv=UV_WALNUT,
                         skip=(("-" if s > 0 else "+") + "y",))
            pts = [(x - w / 2, fy + s * 0.002, z - h / 2), (x + w / 2, fy + s * 0.002, z - h / 2),
                   (x + w / 2, fy + s * 0.002, z + h / 2), (x - w / 2, fy + s * 0.002, z + h / 2)]
            lo, hi = ((x + w / 2, z - h / 2), (x - w / 2, z + h / 2)) if s > 0 else ((x - w / 2, z - h / 2), (x + w / 2, z + h / 2))
            L[k].quad(pts, (0, s, 0), "atlas", UVRect(0, 2, lo, hi, (u0, v0, u1, v1)))


def plate(L, pts, normal, uv_rect, axes, lo, hi):
    """Atlas sub-rectangle on a quad (wayfinding plates)."""
    from skygeo import UVRect
    L["res0"].quad(pts, normal, "atlas", UVRect(axes[0], axes[1], lo, hi, uv_rect))


def potted_plant(L, x, y, h=1.6, r=0.28, big=False, collide=True, pot_mat="stone", pot_uv=None):
    """Planter pot with crossed foliage cards (alpha-tested). big=True: 3 m indoor tree."""
    from skygeo import UVRect
    pot_uv = pot_uv or stone_uv("granite")
    ph = 0.55 if big else 0.4
    L["res0"].prism(x, y, r, 0.0, ph, n=12, mat=pot_mat, uv=pot_uv)
    L["res1"].prism(x, y, r, 0.0, ph, n=6, mat=pot_mat, uv=pot_uv)
    top = 3.0 if big else h
    w = (1.4 if big else 0.7)
    for k in ("res0",) + (("res1",) if big else ()):
        L[k].quad([(x - w, y, ph), (x + w, y, ph), (x + w, y, top), (x - w, y, top)], (0, -1, 0), "foliage",
                  UVRect(0, 2, (x - w, ph), (x + w, top), (0, 0, 1, 1)), double=True)
        L[k].quad([(x, y - w, ph), (x, y + w, ph), (x, y + w, top), (x, y - w, top)], (1, 0, 0), "foliage",
                  UVRect(1, 2, (y - w, ph), (y + w, top), (1, 0, 2, 1)), double=True)
    if collide:                                       # prism like the render pot: a ruin cut keeps or drops both (D82)
        L["geo"].prism(x, y, r, 0.0, ph, n=8)
        L["fire"].prism(x, y, r, 0.0, ph, n=8, mat="pen_concrete")


def rug(L, x0, x1, y0, y1, band="rug_a", z=0.006):
    L["res0"].hquad(x0, x1, y0, y1, z, mat="textile", uv=band_fit("textile", band, x0, x1, y0, y1))


def wall_band(L, walls, ht, z0, z1, mat, uv, proud=0.015, lods=("res0",), sides=(-1, 1)):
    """Band along partition walls (wainscot, skirting), both faces, broken at the openings."""
    for k in lods:
        for axis, c, a0, a1, ops in walls:
            segs, cur = [], a0
            for o0, o1 in sorted(ops):
                segs.append((cur, o0))
                cur = o1
            segs.append((cur, a1))
            for s in sides:
                f0, f1 = sorted((c + s * ht, c + s * (ht + proud)))
                back = ("-" if s > 0 else "+") + ("y" if axis == "x" else "x")
                for g0, g1 in segs:
                    if g1 - g0 < 0.05:
                        continue
                    if axis == "x":
                        L[k].box(g0, g1, f0, f1, z0, z1, mat=mat, uv=uv, skip=(back, "-z"))
                    else:
                        L[k].box(f0, f1, g0, g1, z0, z1, mat=mat, uv=uv, skip=(back, "-z"))


def core_cladding(L, z0, z1, mat, uv, lods=("res0", "res1"), t=0.015):
    """Finish panels on the core's outer faces seen from this module (door openings kept)."""
    C = S.CORE
    x0, x1 = C["x"]
    y0, y1 = C["y"]
    sd0, sd1 = C["stair_door_x"]
    ed = C["door_w"] / 2
    from skygeo import wall_x, wall_y
    for k in lods:
        kw = {"mat": mat, "uv": uv}
        wall_x(L[k], x0 - t, x1 + t, y0 - t, y0, z0, z1, openings=[(sd0 - 0.1, sd1 + 0.1, z0, z0 + 2.3)], skip=("+y",), **kw)
        wall_x(L[k], x0 - t, x1 + t, y1, y1 + t, z0, z1, openings=[(-ed - 0.12, ed + 0.12, z0, z0 + C["door_h"] + 0.12),
                                                                    (0.83, 1.07, z0 + 1.08, z0 + 1.42)], skip=("-y",), **kw)
        wall_y(L[k], x0 - t, x0, y0, y1, z0, z1, skip=("+x",), **kw)
        wall_y(L[k], x1, x1 + t, y0, y1, z0, z1, skip=("-x",), **kw)


def lounge_chair(L, x, y, face, collide=True):
    """Armchair 0.85 x 0.85 m (fabric seat/back, wood legs): face = direction the sitter looks."""
    from skygeo import UVBand
    fuv = UVBand(S.MATERIALS["fabric"]["bands"]["grey"], 1.0)
    x0, x1, y0, y1 = x - 0.42, x + 0.42, y - 0.42, y + 0.42
    r0 = L["res0"]
    r0.box(x0 + 0.05, x1 - 0.05, y0 + 0.05, y1 - 0.05, 0.12, 0.42, mat="fabric", uv=fuv)
    back = {"+y": (x0, x1, y0, y0 + 0.16), "-y": (x0, x1, y1 - 0.16, y1),
            "+x": (x0, x0 + 0.16, y0, y1), "-x": (x1 - 0.16, x1, y0, y1)}[face]
    r0.box(*back, 0.12, 0.8, mat="fabric", uv=fuv)
    arms = [(x0, x0 + 0.12, y0, y1), (x1 - 0.12, x1, y0, y1)] if face[1] == "y" else [(x0, x1, y0, y0 + 0.12), (x0, x1, y1 - 0.12, y1)]
    for a in arms:
        r0.box(*a, 0.12, 0.6, mat="fabric", uv=fuv)
    for (lx, ly) in ((x0 + 0.06, y0 + 0.06), (x1 - 0.06, y0 + 0.06), (x0 + 0.06, y1 - 0.06), (x1 - 0.06, y1 - 0.06)):
        r0.box(lx - 0.025, lx + 0.025, ly - 0.025, ly + 0.025, 0.0, 0.12, mat="wood", uv=UV_WALNUT, skip=("-z", "+z"))
    L["res1"].box(x0, x1, y0, y1, 0.0, 0.6, mat="fabric", uv=fuv, skip=("-z",))
    if collide:
        L["geo"].box(x0, x1, y0, y1, 0.0, 0.6)
        L["fire"].box(x0, x1, y0, y1, 0.0, 0.6, mat="pen_wood")


def coffee_table(L, x0, x1, y0, y1, collide=True):
    L["res0"].box(x0, x1, y0, y1, 0.38, 0.42, mat="wood", uv=UV_OAK)
    L["res0"].box(x0 + 0.05, x1 - 0.05, y0 + 0.05, y1 - 0.05, 0.0, 0.38, mat="metal", uv=UV_PAINT, skip=("-z", "+z"))
    L["res1"].box(x0, x1, y0, y1, 0.0, 0.42, mat="wood", uv=UV_OAK, skip=("-z",))
    if collide:
        L["geo"].box(x0, x1, y0, y1, 0.0, 0.42)
        L["fire"].box(x0, x1, y0, y1, 0.0, 0.42, mat="pen_wood")


def obstruction_light(L, x, y, z):
    """Small lamp head on top of a mast / corner (emissive, Res0)."""
    L["res0"].prism(x, y, 0.07, z, z + 0.12, n=8, mat="lamp")


# ------------------------------------------------------------------ weathering (D60)
_GRIME = ["damp", "runoff", "streak", "moss", "scuff", "smudge", "stain", "mould"]   # D92: 8 bands (sky_decal_grime_ca)


def grime_v(band):
    """(v0, v1) of a decal_grime band in Blender's v-up convention (image row 0 = v 1), 2 px padding."""
    k = _GRIME.index(band)
    n = len(_GRIME)
    return 1.0 - (k + 1) / n + 0.002, 1.0 - k / n - 0.002


def grime_rect(band, u0=0.0, u1=1.0):
    """UVRect target (u0, v0, u1, v1) of a decal_grime band."""
    v0, v1 = grime_v(band)
    return (u0, v0, u1, v1)


def grime(L, sd, a0, a1, z0, z1, depth, band, tile=4.0, inward=False, lods=("res0",)):
    """Weathering overlay (decal_grime, alpha-blended, Res0) on one facade side: the band's
    height over z0..z1, tiling every `tile` m along the side. depth as Side (< 0 = outside)."""
    from skygeo import UVRect
    v0, v1 = grime_v(band)
    uv = UVRect(0 if sd.axis == "x" else 1, 2, (a0, z0), (a1, z1), (a0 / tile, v0, a1 / tile, v1))
    for lod in lods:
        sd.quad(L[lod], a0, a1, z0, z1, depth, inward=inward, mat="decal_grime", uv=uv)


def weed_tuft(L, x, y, z, size, cell="weeds"):
    """Two crossed double-sided vegetation cards (alpha-tested, Res0 only, no collision)."""
    from skygeo import UVRect
    u0, v0, u1, v1 = S.veg_uv(cell)
    h = size / 2
    box = (u0 + 0.004, v0 + 0.004, u1 - 0.004, v1 - 0.004)
    L["res0"].quad([(x - h, y, z), (x + h, y, z), (x + h, y, z + size), (x - h, y, z + size)], (0, -1, 0),
                   "vegetation", UVRect(0, 2, (x - h, z), (x + h, z + size), box), double=True)
    L["res0"].quad([(x, y - h, z), (x, y + h, z), (x, y + h, z + size), (x, y - h, z + size)], (1, 0, 0),
                   "vegetation", UVRect(1, 2, (y - h, z), (y + h, z + size), box), double=True)


def roof_weathering(L, par_h=1.1, par_t=0.25):
    """Tower roofs (D60): run-off streaks down the outer parapet face, moss along the foot of the
    inner face, weed tufts in the four corners (cracks where water stands). Visual only."""
    for key in SIDES:
        sd = Side(key)
        grime(L, sd, sd.a0, sd.a1, -S.SLAB_T, par_h, -0.004, "runoff", tile=3.0)
        a0, a1 = sd.a0 + par_t, sd.a1 - par_t
        grime(L, sd, a0, a1, 0.0, 0.35, par_t + 0.004, "moss", tile=3.0, inward=True)
    for sx in (-1, 1):
        for sy in (-1, 1):
            weed_tuft(L, sx * (HW - par_t - 0.35), sy * (HD - par_t - 0.35), 0.0, 0.6)
            weed_tuft(L, sx * (HW - par_t - 1.3), sy * (HD - par_t - 0.3), 0.0, 0.4, "dry_grass")


def lobby_weathering(L, plinth=0.3):
    """Tower lobby (D60): rising damp on the corner piers and the plinth, splash-back grime on the
    exposed foundation skirt (sloped sites). Visual only, Res0."""
    w = D["cornice_d"] - 0.01
    s = D["corner_pier"]
    for key in SIDES:
        sd = Side(key)
        grime(L, sd, sd.a0, sd.a1, -2.5, -S.SLAB_T, -0.004, "streak", tile=4.0)
        for a0, a1 in ((sd.a0 - w, sd.a0 + s), (sd.a1 - s, sd.a1 + w)):
            grime(L, sd, a0, a1, 0.0, 0.9, -w - 0.004, "damp", tile=2.0)
