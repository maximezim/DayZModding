"""Gate (D77): every SKY texture an rvmat or config.cpp references is written by gen_textures.py.

    python assets/textures/test_texture_refs.py [--size 512] [--dir <already generated PNG folder>]

Runs the generator into a temporary folder at a small size (names do not depend on size) and lists the
references with no generated PNG. Found sky_stone_as.paa: referenced by sky_stone.rvmat since D55, never
written. Exit code 1 on any missing texture.
"""
import argparse
import glob
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ADDONS = os.path.join(HERE, "..", "..", "addons")


def references():
    refs = {}
    for f in glob.glob(os.path.join(ADDONS, "**", "*.rvmat"), recursive=True) + \
            glob.glob(os.path.join(ADDONS, "**", "config.cpp"), recursive=True):
        with open(f, errors="ignore") as fh:
            for m in re.findall(r"(sky_[a-z0-9_]+)\.paa", fh.read(), re.I):
                refs.setdefault(m.lower(), os.path.relpath(f, ADDONS))
    return refs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", type=int, default=512)
    ap.add_argument("--dir", default="", help="check this generated folder instead of running the generator")
    a = ap.parse_args()
    refs = references()
    if a.dir:
        return report(refs, {os.path.splitext(n)[0].lower() for n in os.listdir(a.dir)})
    with tempfile.TemporaryDirectory() as tmp:
        r = subprocess.run([sys.executable, os.path.join(HERE, "gen_textures.py"), "--out", tmp, "--size", str(a.size)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        if r.returncode:
            print(r.stderr[-2000:])
            print("TEXTURE REFS: FAIL (generator exited %d)" % r.returncode)
            return 1
        have = {os.path.splitext(n)[0].lower() for n in os.listdir(tmp)}
    return report(refs, have)


def report(refs, have):
    missing = sorted(k for k in refs if k not in have)
    for k in missing:
        print("MISSING %s.paa (referenced by %s)" % (k, refs[k]))
    print("TEXTURE REFS: %s (%d referenced, %d missing)" % ("FAIL" if missing else "PASS", len(refs), len(missing)))
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
