#!/usr/bin/env python3
"""Heuristic Enforce Script cross-reference (no compiler needed).

Checks a mod's scripts against the vanilla scripts (P:\\scripts on Windows, or
a checkout of BohemiaInteractive/DayZ-Script-Diff):
  - balanced { } ( ) [ ]
  - every called method / constructed class / cast type is declared somewhere
    in vanilla or in the mod itself

    python tools/assets/enscript_xref.py --vanilla P:\\scripts --mod mods/SKY_Skyline/addons/sky_scripts/scripts

It is a lint, not a compiler: it catches typos and APIs that do not exist in
the target game version. The game's own script compile (script_*.log) stays the
final authority.
"""
import argparse
import glob
import os
import re
import sys

# A declaration needs a return type token before the name (calls never have one).
DECL_FN = re.compile(r"\b(?:void|int|float|bool|string|vector|typename|auto|func|Class|"
                     r"(?:array|map|set|ref)\s*<[^;{()]*?>|[A-Z]\w*)\s+(\w+)\s*\([^;{)]*\)\s*(?:\{|;)")
DECL_TYPE = re.compile(r"\b(?:class|enum)\s+(\w+)|\btypedef\s+[\w<>,\s]+?\s(\w+)\s*;")


def strip(code):
    code = re.sub(r"/\*.*?\*/", "", code, flags=re.S)
    code = re.sub(r"//[^\n]*", "", code)
    return re.sub(r'"(?:\\.|[^"\\])*"', '""', code)


def read_all(root):
    out = {}
    for f in glob.glob(os.path.join(root, "**", "*.c"), recursive=True):
        with open(f, encoding="utf-8", errors="ignore") as fh:
            out[f] = strip(fh.read())
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vanilla", required=True)
    ap.add_argument("--mod", required=True)
    a = ap.parse_args()
    van, mod = read_all(a.vanilla), read_all(a.mod)
    if not van:
        sys.exit("no vanilla scripts under " + a.vanilla)
    everything = "\n".join(list(van.values()) + list(mod.values()))
    fns = set(DECL_FN.findall(everything))
    types = {x or y for x, y in DECL_TYPE.findall(everything)}
    problems = []
    for f, body in sorted(mod.items()):
        rel = os.path.relpath(f, a.mod)
        for o, c in (("{", "}"), ("(", ")"), ("[", "]")):
            if body.count(o) != body.count(c):
                problems.append("%s: unbalanced %s%s (%d/%d)" % (rel, o, c, body.count(o), body.count(c)))
        calls = set(re.findall(r"\.(\w+)\s*\(", body)) | set(re.findall(r"(?<![\w.])([A-Z]\w+)\s*\(", body))
        for m in sorted(calls):
            if m not in fns and m not in types:
                problems.append("%s: call '%s' not declared" % (rel, m))
        used = set(re.findall(r"(\w+)\.Cast\(", body)) | set(re.findall(r"\bnew\s+(\w+)", body))
        for t in sorted(used):
            if t not in types:
                problems.append("%s: type '%s' not declared" % (rel, t))
    print("\n".join(problems) if problems else "OK: %d files, all calls/types resolve" % len(mod))
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
