#!/usr/bin/env python3
"""Inspect unbinarized (MLOD) .p3d files: LODs, face/vertex counts, named
selections, named properties, mass, textures/materials.

Used as the automated "LOD/selection check" step of the asset pipeline:

    python tools/assets/p3d_inspect.py model.p3d                # human summary
    python tools/assets/p3d_inspect.py model.p3d --json         # machine output
    python tools/assets/p3d_inspect.py model.p3d --spec spec.json   # gate: exit 1 on violations

Format reference: MLOD "P3DM" v28.256 (as written by Object Builder and Arma
Toolbox). Binarized ODOL files are rejected - inspect the source P3D instead.
"""
import argparse
import json
import struct
import sys

# Special LOD resolutions used by the Real Virtuality / Enfusion P3D format.
SPECIAL_LODS = {
    1e3: "View Gunner", 1.1e3: "View Pilot", 1.2e3: "View Cargo",
    1e4: "Shadow Volume", 1.001e4: "Shadow Volume 2",
    1e13: "Geometry", 1e15: "Memory", 2e15: "Land Contact", 3e15: "Roadway",
    4e15: "Paths", 5e15: "HitPoints", 6e15: "View Geometry", 7e15: "Fire Geometry",
    8e15: "View Cargo Geometry", 9e15: "View Cargo Fire Geometry",
    1e16: "View Commander", 1.1e16: "View Commander Geometry",
    1.2e16: "View Commander Fire Geometry", 1.3e16: "View Pilot Geometry",
    1.4e16: "View Pilot Fire Geometry", 1.5e16: "View Gunner Geometry",
    1.6e16: "View Gunner Fire Geometry", 1.7e16: "Sub Parts",
    1.8e16: "Shadow Volume View Cargo", 1.9e16: "Shadow Volume View Pilot",
    2e16: "Shadow Volume View Gunner", 2.1e16: "Wreck",
}


def lod_name(res):
    for k, v in SPECIAL_LODS.items():
        if abs(res - k) <= k * 1e-4:
            return v
    if 1e4 <= res < 2e4:
        return "Shadow Volume %g" % (res - 1e4)
    if res < 1e3:
        return "Resolution %g" % res
    return "LOD %g" % res


def lod_kind(name):
    if name.startswith("Resolution"):
        return "Resolution"
    if name.startswith("Shadow Volume"):
        return "Shadow Volume"
    return name


class Reader:
    def __init__(self, data):
        self.d, self.o = data, 0

    def take(self, n):
        b = self.d[self.o:self.o + n]
        if len(b) != n:
            raise ValueError("unexpected end of file at %d" % self.o)
        self.o += n
        return b

    def u32(self):
        return struct.unpack("<I", self.take(4))[0]

    def i32(self):
        return struct.unpack("<i", self.take(4))[0]

    def f32(self):
        return struct.unpack("<f", self.take(4))[0]

    def asciiz(self):
        end = self.d.index(b"\0", self.o)
        s = self.d[self.o:end].decode("latin-1")
        self.o = end + 1
        return s


def parse(path):
    with open(path, "rb") as fh:
        r = Reader(fh.read())
    sig = r.take(4)
    if sig == b"ODOL":
        raise ValueError("%s is binarized (ODOL); inspect the MLOD source" % path)
    if sig != b"MLOD":
        raise ValueError("%s is not a P3D (signature %r)" % (path, sig))
    r.u32()  # version 257
    n_lods = r.u32()
    lods = []
    for _ in range(n_lods):
        if r.take(4) != b"P3DM":
            raise ValueError("unsupported LOD block (expected P3DM)")
        r.u32(); r.u32()  # major 28, minor 256
        n_pts, n_nrm, n_faces = r.u32(), r.u32(), r.u32()
        r.u32()  # flags
        pts = [struct.unpack("<fffI", r.take(16))[:3] for _ in range(n_pts)]
        r.take(12 * n_nrm)
        textures, materials, pairs = set(), set(), set()
        tris = 0
        for _ in range(n_faces):
            nv = r.i32()
            r.take(64)
            r.i32()  # face flags
            tex, mat = r.asciiz(), r.asciiz()
            if tex:
                textures.add(tex)
            if mat:
                materials.add(mat)
            pairs.add((tex, mat))                 # one section per (texture, material) pair (perf audit M4)
            tris += 1 if nv == 3 else 2
        if r.take(4) != b"TAGG":
            raise ValueError("missing TAGG")
        selections, props, mass = {}, {}, None
        while True:
            r.take(1)  # active flag
            name = r.asciiz()
            size = r.u32()
            data = r.take(size)
            if name == "#EndOfFile#":
                break
            if name == "#Property#":
                k = data[:64].split(b"\0")[0].decode("latin-1")
                v = data[64:128].split(b"\0")[0].decode("latin-1")
                props[k] = v
            elif name == "#Mass#":
                mass = sum(struct.unpack("<%df" % n_pts, data[:4 * n_pts])) if n_pts else 0.0
            elif not name.startswith("#"):
                w = data[:n_pts]
                f = data[n_pts:n_pts + n_faces]
                selections[name] = {"points": sum(1 for b in w if b), "faces": sum(1 for b in f if b)}
        res = r.f32()
        xs = [p[0] for p in pts] or [0]
        ys = [p[1] for p in pts] or [0]
        zs = [p[2] for p in pts] or [0]
        lods.append({
            "resolution": res,
            "name": lod_name(res),
            "points": n_pts,
            "faces": n_faces,
            "triangles": tris,
            "selections": selections,
            "properties": props,
            "mass": mass,
            "textures": sorted(textures),
            "materials": sorted(materials),
            "sections": len(pairs),
            "bbox": [[min(xs), min(ys), min(zs)], [max(xs), max(ys), max(zs)]],
        })
    return lods


def check(lods, spec):
    """spec keys: required_lods[], min_resolution_lods, max_triangles{lodName:n},
    required_selections{lodName:[...]}, required_properties{lodName:{k:v}},
    component_lods[] (each selection ComponentXX must exist, Geometry needs mass)."""
    errs = []
    by_name = {l["name"]: l for l in lods}
    for req in spec.get("required_lods", []):
        if req not in by_name:
            errs.append("missing LOD: %s" % req)
    n_res = sum(1 for l in lods if l["name"].startswith("Resolution"))
    if n_res < spec.get("min_resolution_lods", 0):
        errs.append("only %d resolution LODs (need %d)" % (n_res, spec["min_resolution_lods"]))
    for lname, limit in spec.get("max_triangles", {}).items():
        targets = [l for l in lods if l["name"] == lname or (lname == "Resolution0" and l["name"] == "Resolution 0")]
        if lname == "AnyResolution":
            targets = [l for l in lods if l["name"].startswith("Resolution")]
        for l in targets:
            if l["triangles"] > limit:
                errs.append("%s: %d tris > budget %d" % (l["name"], l["triangles"], limit))
    for lname, sels in spec.get("required_selections", {}).items():
        l = by_name.get(lname)
        for s in sels:
            if not l or s not in l["selections"]:
                errs.append("%s: missing selection '%s'" % (lname, s))
    for lname, kv in spec.get("required_properties", {}).items():
        l = by_name.get(lname)
        for k, v in kv.items():
            if not l or l["properties"].get(k) != v:
                errs.append("%s: property %s=%s expected" % (lname, k, v))
    for lname in spec.get("component_lods", []):
        l = by_name.get(lname)
        if l and not any(s.lower().startswith("component") for s in l["selections"]):
            errs.append("%s: no ComponentXX selections (run Find Components)" % lname)
    g = by_name.get("Geometry")
    if g is not None and spec.get("geometry_needs_mass", True) and not g["mass"]:
        errs.append("Geometry: no mass assigned")
    return errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("p3d", nargs="+")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--spec", help="JSON gate spec; exit 1 on violations")
    a = ap.parse_args()
    spec = json.load(open(a.spec)) if a.spec else None
    out, failed = {}, False
    for p in a.p3d:
        lods = parse(p)
        out[p] = lods
        if spec is not None:
            errs = check(lods, spec)
            out[p + "#errors"] = errs
            failed |= bool(errs)
        if not a.json:
            print("== %s (%d LODs)" % (p, len(lods)))
            for l in lods:
                sels = ", ".join(sorted(l["selections"]))
                print("  %-22s tris=%-6d pts=%-6d mass=%-8s sel=[%s]" % (
                    l["name"], l["triangles"], l["points"],
                    ("%.4g" % l["mass"]) if l["mass"] else "-", sels[:160]))
                if l["properties"]:
                    print("      props: %s" % l["properties"])
            if spec is not None:
                for e in out[p + "#errors"]:
                    print("  GATE FAIL: " + e)
                if not out[p + "#errors"]:
                    print("  GATE PASS")
    if a.json:
        print(json.dumps(out, indent=1))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
