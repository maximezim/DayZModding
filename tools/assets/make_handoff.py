#!/usr/bin/env python3
"""End-of-batch hand-off: git bundle of the current branch + zip of a mod folder.

    python tools/assets/make_handoff.py --label batch1 [--mod mods/SKY_Skyline]

Writes into _handoff/<label>/ (git-ignored):
  <repo>-<branch>-<label>.bundle   restore: git clone <bundle> DayZModding
  <Mod>-<label>.zip                tracked files of the mod folder (working-tree content: commit first)
  HANDOFF.txt                      commit id, file list, how to restore
"""
import argparse
import os
import subprocess
import zipfile

ROOT = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip()


def git(*a):
    return subprocess.check_output(["git", "-C", ROOT] + list(a), text=True).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True)
    ap.add_argument("--mod", default="mods/SKY_Skyline")
    a = ap.parse_args()
    import re
    if not re.match(r"^[A-Za-z0-9_.-]+$", a.label) or a.label in (".", ".."):
        raise SystemExit("--label may only contain letters, digits, '_', '.', '-'")
    base = os.path.realpath(os.path.join(ROOT, "_handoff"))
    out = os.path.realpath(os.path.join(base, a.label))
    if not out.startswith(base + os.sep):
        raise SystemExit("refusing to write outside _handoff/")
    os.makedirs(out, exist_ok=True)
    branch = git("rev-parse", "--abbrev-ref", "HEAD")
    head = git("rev-parse", "--short", "HEAD")
    bundle = os.path.join(out, "DayZModding-%s-%s.bundle" % (branch.replace("/", "_"), a.label))
    git("bundle", "create", bundle, branch)
    git("bundle", "verify", bundle)
    modname = os.path.basename(a.mod.rstrip("/"))
    zpath = os.path.join(out, "%s-%s.zip" % (modname, a.label))
    files = git("ls-files", a.mod).splitlines()
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(os.path.join(ROOT, f), f)       # working tree = checked-out LFS content
    with open(os.path.join(out, "HANDOFF.txt"), "w") as fh:
        fh.write("label: %s\nbranch: %s\ncommit: %s\nfiles in zip: %d\n\n" % (a.label, branch, head, len(files)))
        fh.write("Restore the repository:  git clone %s DayZModding\n" % os.path.basename(bundle))
        fh.write("(LFS objects are not in the bundle; the zip contains the real P3D/PNG files.)\n")
    print(bundle)
    print(zpath)


if __name__ == "__main__":
    main()
