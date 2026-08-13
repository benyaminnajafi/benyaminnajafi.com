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
    # captionLink's underline and wash used to be waived here for deriving from
    # --accent instead of the original's fixed green. They match now, so the
    # waivers are gone and the gate compares them like anything else.
    ("heroBand", "_box"):
        "1440 vs 1408 wide: the original carries the 16px page gutter on the "
        "hero itself, the rebuild carries it on the page wrapper. The band is "
        "489px tall on both and the content starts at the same x",
    ("heroBand", "padding-left"): "same gutter, different owner",
    ("heroBand", "padding-right"): "same gutter, different owner",
    ("captionLink", "transition-property"):
        "the original also transitions border-radius and corner-shape, neither "
        "of which changes on hover. The three that do are the same",
    ("captionLink", "transition-duration"): "same list, same 0.2s",
    ("carouselHint", "transform"):
        "translateX(-50%) against the original's absolute left offset. Both "
        "land the hint centred on the slide's bottom edge",
    ("carouselHint", "animation-name"):
        "the original drives its 3s-hold-1s-fade pulse from a JavaScript "
        "variant loop; the rebuild uses a keyframe. _opacity and _blend gate "
        "the result",
    ("carouselHint", "animation-duration"): "same pulse, keyframe instead of JS",
    ("slideFrame", "gap"):
        "the original centres its slide with flex; the rebuild sizes the block "
        "directly. _box gates the outcome",
    ("footerBar", "gap"):
        "space-between on a flex row versus a 1fr auto 1fr grid. Same three "
        "positions",
    ("detailsCol", "_box"):
        "28px, from an empty credit slot the first case study renders for an "
        "unused CMS field. Not every case has one, so reproducing it pushed "
        "the three text-driven rows 28px past the reference. The row heights "
        "in caseRows gate what this column actually affects",
}

# Landmarks the rebuild deliberately does not have. Distinct from a waiver: a
# waiver says "these differ and that is fine", this says "this is gone on
# purpose". Both need a written reason, and neither may be added to make a red
# run go green — the point of the gate is that a departure is a decision
# somebody made, not something that drifted.
DEPARTURES = {
    "carouselHint":
        "the pulsing 'Click or Drag' label over each slide, removed by request. "
        "On a pointer the custom cursor already says the strip is draggable; "
        "the label was reading as a watermark on the artwork",
}

# Containers are captured broadly and gated narrowly, and the two builds reach
# the same layout by different means: Framer lays out with flex 1.2/2 where the
# rebuild uses a 1.2fr/2fr grid, sets position: relative and a white background
# on every block, and draws its hairlines with absolutely-positioned divs rather
# than real borders. Diffing display, position, background or border-width
# across that reports thirty-odd differences that no reader could see, and a
# gate that cries wolf is a gate someone turns off.
#
# What survives is what a reader would actually notice: the rendered box, and
# the padding and gaps that set the spacing inside it.
CONTAINER_GATED = {"_box", "padding-top", "padding-bottom", "gap"}
# Containers round differently between a flex and a grid track; the regressions
# that shipped were 17px, 28px and 205px.
BOX_TOLERANCE = 5

# How far the whole-page height may drift before it counts as a regression.
# The rebuild lands 22px off 5457 on rounding; the collapsed-hero build was
# 57px off, so half a percent separates the two.
HEIGHT_TOLERANCE = 0.005
# Per-row slack, in px. Sub-pixel rounding on a 4:3 block costs 1px a row; the
# rows that lost their nesting were 40px out.
ROW_TOLERANCE = 5

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


def within_tolerance(want: str, got: str, slack: int = BOX_TOLERANCE) -> bool:
    """True when two 'WxH' strings agree to within `slack` px on both axes."""
    try:
        w1, h1 = (float(v) for v in want.split("x"))
        w2, h2 = (float(v) for v in got.split("x"))
    except ValueError:
        return False
    return abs(w1 - w2) <= slack and abs(h1 - h2) <= slack


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
    allowed_missing |= set(DEPARTURES)

    # Refuse to compare a light capture against a dark one. localStorage is
    # per-origin, so a theme set on one port does not apply to another, and the
    # resulting mismatch looks exactly like a hundred colour regressions.
    if candidate.get("theme") != reference.get("theme"):
        sys.exit(f"theme mismatch: candidate is {candidate.get('theme')!r}, "
                 f"reference is {reference.get('theme')!r} — recapture")

    # Every box size in the file is width-dependent. There was a theme guard
    # but never a width guard, so a 1280 capture could be diffed against a 1440
    # reference and the noise would look like real regressions.
    cand_vw, ref_vw = candidate.get("viewport"), reference.get("viewport")
    if cand_vw and ref_vw and cand_vw != ref_vw:
        sys.exit(f"viewport mismatch: candidate at {cand_vw}, "
                 f"reference at {ref_vw} — recapture at the same size")
    if not ref_vw:
        print("note: reference predates viewport recording — recapture it")

    diffs: list[tuple[str, str, str, str]] = []
    waived: list[str] = []
    absent: list[str] = []
    compared = 0

    def compare_section(kind: str) -> tuple[list[str], list[str]]:
        """Diff one map of element -> {prop: value}. Returns (missing, extra)."""
        nonlocal compared
        cand_s = candidate.get(kind) or {}
        ref_s = reference.get(kind) or {}
        miss = [k for k in ref_s if k not in cand_s and k not in allowed_missing]
        extra_s = [k for k in cand_s if k not in ref_s]

        for name, ref_style in ref_s.items():
            if name not in cand_s:
                continue
            for prop, ref_value in ref_style.items():
                if prop == "_text":
                    continue
                if kind == "containers" and prop not in CONTAINER_GATED:
                    continue
                # A property the reference has and the candidate does not is a
                # finding, not something to pass over. Skipping it quietly is
                # how whole categories of regression stayed invisible.
                if prop not in cand_s[name]:
                    if (name, prop) not in WAIVERS:
                        absent.append(f"{name}.{prop}")
                    continue
                if type_only and prop in LAYOUT_ONLY:
                    continue
                if name in IMAGE_LANDMARKS and prop in TEXT_ONLY_ON_TEXT:
                    continue
                compared += 1
                got = cand_s[name][prop]
                if prop == "font-family":
                    # Only the first family in the stack ever renders here —
                    # both sides load the same webfont. The rest of the chain
                    # differs because both ship metric-matched fallback faces;
                    # that changes nothing once the font has loaded.
                    got, ref_value = first_family(got), first_family(ref_value)
                if got.strip() == ref_value.strip():
                    continue
                # A box compared exactly turns every rounding difference into a
                # failure. Compared with slack it still catches everything that
                # actually shipped.
                if prop == "_box" and within_tolerance(ref_value, got):
                    continue
                if (name, prop) in WAIVERS:
                    waived.append(f"{name}.{prop}: {ref_value} → {got}")
                    continue
                diffs.append((name, prop, ref_value, got))
        return miss, extra_s

    missing, extra = compare_section("landmarks")
    c_missing, c_extra = compare_section("containers")
    missing += [f"container:{m}" for m in c_missing]
    extra += [f"container:{e}" for e in c_extra]

    # Whole-page height. This was captured from the first run and never once
    # compared — the cheapest signal available, sitting unused in the JSON.
    ref_h = (reference.get("page") or {}).get("scrollHeight")
    cand_h = (candidate.get("page") or {}).get("scrollHeight")
    if ref_h and cand_h:
        slack = max(1, round(ref_h * HEIGHT_TOLERANCE))
        delta = cand_h - ref_h
        status = "ok" if abs(delta) <= slack else "OUT OF RANGE"
        print(f"page height: {cand_h} vs {ref_h} ({delta:+d}px, ±{slack} allowed) — {status}")
        if abs(delta) > slack:
            diffs.append(("page", "scrollHeight", str(ref_h), str(cand_h)))

    # Every case row, not just the first one.
    ref_rows = reference.get("caseRows") or []
    cand_rows = candidate.get("caseRows") or []
    if ref_rows:
        if len(ref_rows) != len(cand_rows):
            diffs.append(("caseRows", "count", str(len(ref_rows)), str(len(cand_rows))))
        for i, (rw, cw) in enumerate(zip(ref_rows, cand_rows), start=1):
            r_w, r_h = (int(float(v)) for v in rw.split("x"))
            c_w, c_h = (int(float(v)) for v in cw.split("x"))
            if abs(r_w - c_w) > ROW_TOLERANCE or abs(r_h - c_h) > ROW_TOLERANCE:
                diffs.append((f"caseRow[{i}]", "_box", rw, cw))
        print(f"{len(cand_rows)} case rows checked (±{ROW_TOLERANCE}px)")

    print(f"{compared} properties compared across "
          f"{len(reference.get('landmarks') or {}) - len(missing)} landmarks and "
          f"{len(reference.get('containers') or {})} containers")
    if waived:
        print(f"\n{len(waived)} waived:")
        for w in waived:
            print(f"  · {w}")
    gone = [k for k in DEPARTURES if k in (reference.get("landmarks") or {})
            and k not in (candidate.get("landmarks") or {})]
    if gone:
        print(f"\n{len(gone)} deliberate departures from the reference:")
        for k in gone:
            print(f"  · {k}: {DEPARTURES[k]}")

    if absent:
        print(f"\n{len(absent)} properties the reference has and the candidate "
              f"does not: {', '.join(absent)}")
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

    if missing or absent:
        sys.exit(1)
    print("\nno unwaived differences")


if __name__ == "__main__":
    main()
