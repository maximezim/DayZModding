#!/usr/bin/env python3
"""Regenerate the KIT section of assets/manifest.yaml from skyspec.KIT.

    python mods/SKY_Skyline/assets/gen_manifest.py [--check]

Everything between the '# >>> GENERATED KIT' / '# <<< GENERATED KIT' markers is
rewritten: one entry per KIT asset with class, p3d, category budget (hypothesis),
the unverified assumptions it depends on, and status. Status vocabulary is
'built-unverified' until DayZ testing (nothing may be 'done' before that).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import skyspec as S  # noqa: E402

BEGIN, END = "# >>> GENERATED KIT (assets/gen_manifest.py)", "# <<< GENERATED KIT"


def section():
    lines = [BEGIN, "generated_kit:"]
    for name, e in S.KIT.items():
        b = S.BUDGETS[e["category"]]
        lines.append("  - name: %s" % e["cls"])
        lines.append("    type: %s" % (e["desc"] or name))
        lines.append("    p3d: addons/%s/%s" % (e["pbo"], e["p3d"]))
        lines.append("    category: %s" % e["category"])
        lines.append("    budget: {%s}" % ", ".join("%s: %s" % kv for kv in b.items()))
        if e["uses"]:
            lines.append("    uses: [%s]" % ", ".join(e["uses"]))
        if e["variants"]:
            lines.append("    variants: [%s]" % ", ".join(sorted(e["variants"])))
        lines.append("    status: built-unverified")
    lines.append(END)
    return "\n".join(lines) + "\n"


def main():
    path = os.path.join(HERE, "manifest.yaml")
    text = open(path).read()
    if BEGIN in text:
        pre = text[:text.index(BEGIN)]
        post = text[text.index(END) + len(END) + 1:]
    else:
        pre, post = text.rstrip("\n") + "\n\n", ""
    new = pre + section() + post
    if "--check" in sys.argv:
        sys.exit(0 if new == text else "manifest kit section is stale")
    open(path, "w").write(new)
    print("manifest: %d kit entries" % len(S.KIT))


if __name__ == "__main__":
    main()
