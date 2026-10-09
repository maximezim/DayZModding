"""Gate (D94): every committed P3D is exactly what its generator writes today.

The generators are deterministic (plain Python, no add-on since D60), so a re-export into a temporary folder must be
byte-identical to addons/. A difference means a generator changed without a re-export (the model in the PBO is stale)
or a P3D was edited by hand (generated outputs are regenerated, never edited - CLAUDE.md).

    python assets/check_p3d_sync.py [--only build_city,build_kit] [--keep]

Exit 1 on any stale, missing or extra P3D. Takes ~4 min for all ten builders.
"""
import argparse
import filecmp
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
MOD = os.path.dirname(HERE)
ADDONS = os.path.join(MOD, "addons")
BUILDERS = ["build_towera", "build_kit", "build_props", "build_floors", "build_city", "build_landmarks",
            "build_streetprops", "build_underground", "build_creatures", "build_vehicles"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--keep", action="store_true", help="keep the temporary export for inspection")
    a = ap.parse_args()
    builders = [b for b in BUILDERS if not a.only or b in a.only.split(",")]
    tmp = tempfile.mkdtemp(prefix="sky_p3d_sync_")
    out = os.path.join(tmp, "addons")                       # stats land in tmp/assets (run_cli: out/../assets)
    os.makedirs(os.path.join(tmp, "assets"), exist_ok=True)   # build_towera writes its stats there without creating it
    os.makedirs(out, exist_ok=True)
    fails = []
    try:
        for b in builders:
            r = subprocess.run([sys.executable, os.path.join(HERE, "blender", b + ".py"), "--", "--out", out],
                               capture_output=True, text=True)
            if r.returncode != 0:
                fails.append("%s failed: %s" % (b, (r.stdout + r.stderr).strip().splitlines()[-1:]))
        built = set()
        for root, _d, files in os.walk(out):
            for f in files:
                if f.endswith(".p3d"):
                    rel = os.path.relpath(os.path.join(root, f), out)
                    built.add(rel)
                    ref = os.path.join(ADDONS, rel)
                    if not os.path.exists(ref):
                        fails.append("missing in addons/: %s" % rel)
                    elif not filecmp.cmp(os.path.join(root, f), ref, shallow=False):
                        fails.append("stale: %s (re-export with %s)" % (rel, "Build-SkyAssets.ps1 -Models"))
        if not a.only:
            for root, _d, files in os.walk(ADDONS):
                for f in files:
                    rel = os.path.relpath(os.path.join(root, f), ADDONS)
                    if f.endswith(".p3d") and rel not in built:
                        fails.append("extra (no generator writes it): %s" % rel)
    finally:
        if a.keep:
            print("export kept in", tmp)
        else:
            shutil.rmtree(tmp, ignore_errors=True)
    if fails:
        print("P3D SYNC: %d FAILED" % len(fails))
        for f in fails[:50]:
            print("  FAIL", f)
        sys.exit(1)
    print("P3D SYNC: PASS (%d builders, %d models byte-identical)" % (len(builders), len(built)))


if __name__ == "__main__":
    main()
