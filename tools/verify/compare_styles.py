#!/usr/bin/env python3
"""
Diff a rebuilt page's computed styles against the reference captured from Framer.

This is the layer that actually guarantees fidelity. A pixel diff with any
tolerance at all swallows 22px vs 22.4px, 1.5em vs 1.5, #f4f4f48c vs #f4f4f4d9 —
differences that are invisible in one screenshot and obvious across a page.
Comparing resolved values catches them exactly.

Only properties that the reference and the candidate both report are compared,
and only for landmarks present in both. Anything missing is reported rather than
skipped quietly.

Usage:
    python3 tools/verify/compare_styles.py <candidate.json> <reference.json> [--waivers f]
"""

from __future__ import annotations

import json
import os
import sys

# Deliberate, signed-off differences. Each needs a reason, and a reason that is
# about the design — "it was wrong before" — not about convenience.
WAIVERS = {
    ("name", "_box"):
        "the glyphs are identical — 'Senior Product Designer' measures 245px in "
        "both — and only the container around them differs. Framer's block is "
        "289 wide with 44px of slack; nothing visible changes",
    ("jobTitle", "_box"): "same container slack as name",
    ("captionLink", "_box"):
        "6px, from the spaces Framer keeps either side of the link text. The "
        "rendered words and their underline are identical",
    ("caseBody", "padding-bottom"):
        "Framer ends every block with a <br><br>; the rebuild uses one line of "
        "padding instead. Same space, same box height, different mechanism",
    ("caseBullet", "padding-bottom"):
        "same as caseBody",
    ("captionLink", "text-decoration-color"):
        "the original hard-coded this off the dark-theme green so it never "
        "switched with the theme; derived from --accent now, which fixes light mode",
    ("captionLink", "background-color"):
        "same hard-coded dark-theme green, same fix",
}

# Box geometry belongs to the layout gate, not the type gate.
# Text properties resolve on an <img> but never render. Comparing them just
# reports whatever the two containers happened to inherit.
TEXT_ONLY_ON_TEXT = {"font-family", "font-size", "font-weight", "line-height",
                     "letter-spacing", "font-variation-settings",
                     "text-decoration-line", "text-decoration-style",
                     "text-decoration-color", "text-underline-offset",
                     "text-decoration-thickness", "color"}
IMAGE_LANDMARKS = {"caseImage"}

LAYOUT_ONLY = {"_box", "_boxTolerance", "display", "flex-direction", "align-items",
               "justify-content", "gap", "margin-top", "margin-bottom",
               "padding-top", "padding-bottom", "border-radius",
               "border-top-width", "border-top-color", "background-color"}


def first_family(value: str) -> str:
    """The first family in a font stack, unquoted."""
    return value.split(",")[0].strip().strip('"\'')


def main() -> None:
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    candidate = json.load(open(sys.argv[1], encoding="utf-8"))
    reference = json.load(open(sys.argv[2], encoding="utf-8"))
    type_only = "--type-only" in sys.argv
    # A partial fixture legitimately lacks some landmarks; naming them makes the
    # omission deliberate instead of a silently tolerated gap.
    allowed_missing = {
        a.split("=", 1)[1] for a in sys.argv if a.startswith("--allow-missing=")
    }
    allowed_missing = {n for spec in allowed_missing for n in spec.split(",")}

    # Refuse to compare a light capture against a dark one. localStorage is
    # per-origin, so a theme set on one port does not apply to another, and the
    # resulting mismatch looks exactly like a hundred colour regressions.
    if candidate.get("theme") != reference.get("theme"):
        sys.exit(f"theme mismatch: candidate is {candidate.get('theme')!r}, "
                 f"reference is {reference.get('theme')!r} — recapture")

    cand = candidate["landmarks"]
    ref = reference["landmarks"]

    missing = [k for k in ref if k not in cand and k not in allowed_missing]
    extra = [k for k in cand if k not in ref]

    diffs: list[tuple[str, str, str, str]] = []
    waived: list[str] = []
    compared = 0

    for name, ref_style in ref.items():
        if name not in cand:
            continue
        for prop, ref_value in ref_style.items():
            # `_box` is the element's rendered size and is the whole point of a
            # layout gate — skipping every underscore key quietly excluded it,
            # which is how a rebuild whose text wrapped differently and whose
            # page was 200px shorter passed a "no differences" run.
            if prop == "_text" or prop not in cand[name]:
                continue
            if type_only and prop in LAYOUT_ONLY:
                continue
            if name in IMAGE_LANDMARKS and prop in TEXT_ONLY_ON_TEXT:
                continue
            compared += 1
            got = cand[name][prop]
            if prop == "font-family":
                # Only the first family in the stack ever renders here — both
                # sides load the same webfont. The rest of the chain differs
                # because Framer shipped metric-matched "… Placeholder" faces as
                # its fallback; that changes nothing once the font has loaded.
                got, ref_value = first_family(got), first_family(ref_value)
            if got.strip() == ref_value.strip():
                continue
            if (name, prop) in WAIVERS:
                waived.append(f"{name}.{prop}: {ref_value} → {got}")
                continue
            diffs.append((name, prop, ref_value, got))

    print(f"{compared} properties compared across {len(ref) - len(missing)} landmarks")
    if waived:
        print(f"\n{len(waived)} waived:")
        for w in waived:
            print(f"  · {w}")
    if missing:
        print(f"\nlandmarks not found in the candidate: {', '.join(missing)}")
    if extra:
        print(f"landmarks only in the candidate: {', '.join(extra)}")

    if diffs:
        print(f"\n{len(diffs)} DIFFER:")
        width = max(len(f"{n}.{p}") for n, p, _, _ in diffs)
        for name, prop, want, got in diffs:
            print(f"  ✗ {f'{name}.{prop}':<{width}}  want {want!r}  got {got!r}")
        sys.exit(1)

    if missing:
        sys.exit(1)
    print("\nno unwaived differences")


if __name__ == "__main__":
    main()
