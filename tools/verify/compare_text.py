#!/usr/bin/env python3
"""
Diff the words a page renders against the reference.

Catches the failure a screenshot cannot: text that is subtly wrong. A rebuilt
page can look identical and still say `platform’s` where the original said
`platform's`, or show a phone number in E.164 instead of the way it was typed.

Three normalisations, each because the DOM shapes differ while the reading does
not. Anything beyond these is a real difference and fails.

Usage:
    python3 tools/verify/compare_text.py <candidate.txt> [reference.txt]
"""

from __future__ import annotations

import difflib
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_REFERENCE = os.path.join(ROOT, ".baseline", "text.txt")

# The carousel hint. The original repeats it once per slide because every slide
# carries its own copy; the rebuild has one per carousel. Same words on screen,
# different count, and counting it would drown the diff.
REPEATED = {"Click or Drag", "Tap or Drag"}


def normalise(text: str) -> list[str]:
    lines: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line in REPEATED:
            continue
        # The original splits a caption and its colon into two text nodes, so
        # innerText puts them on separate lines. Reading is identical.
        if line == ":":
            continue
        line = line.rstrip(":").strip()
        if line:
            lines.append(line)
    return split_caption_links(lines)


# "See how we scaled: Read case study ⤴︎" renders as one line on both builds,
# but the original holds the caption and the link in separate block elements,
# so innerText breaks it in two. Splitting the rebuild's single line the same
# way compares the words rather than the markup — otherwise every case study
# reports two false differences and the gate is noise.
CAPTION_LINK = re.compile(r"^(?P<caption>.+?):\s+(?P<link>(?:Read case study|Visit \S+).*)$")


def split_caption_links(lines: list[str]) -> list[str]:
    out: list[str] = []
    for line in lines:
        m = CAPTION_LINK.match(line)
        if m:
            out.append(m.group("caption").strip())
            out.append(m.group("link").strip())
        else:
            out.append(line)
    return out


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    candidate = normalise(open(sys.argv[1], encoding="utf-8").read())
    reference_path = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_REFERENCE
    reference = normalise(open(reference_path, encoding="utf-8").read())

    diff = [
        line
        for line in difflib.unified_diff(reference, candidate, lineterm="", n=0)
        if not line.startswith(("---", "+++", "@@"))
    ]

    print(f"reference {len(reference)} lines, candidate {len(candidate)} lines")
    if not diff:
        print("identical")
        return

    print(f"\n{len(diff)} DIFFER:")
    for line in diff:
        mark = "missing from the rebuild" if line.startswith("-") else "not on the original"
        print(f"  {line[0]} {line[1:][:90]}   ({mark})")
    sys.exit(1)


if __name__ == "__main__":
    main()
