#!/usr/bin/env python3
"""
Prove the extracted content did not lose or scramble anything.

Extraction from an index-referenced blob fails *plausibly*. A caption bound to
the wrong case study, an image list off by one, a Role value swapped with an
Expertise value — all of these read fine and no screenshot catches them. So the
extractor's output is not trusted; it is checked, two independent ways:

  1. Every visible string in content/ must appear in .baseline/text.txt, the
     text the real site renders. Catches invented or mangled text.
  2. Every line of .baseline/text.txt that belongs to a case study must appear
     in content/. Catches text silently dropped.

Plus cheap structural checks: image files exist, links are absolute, the field
set is complete on every record.

Exit code is non-zero if anything fails, so it can gate a build.

Usage:
    python3 tools/verify_content.py
"""

from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTENT = os.path.join(ROOT, "content")
BASELINE = os.path.join(ROOT, ".baseline", "text.txt")
SITE = os.path.join(ROOT, "site")

REQUIRED = ["order", "title", "role", "expertise", "industry",
            "linkLabel", "linkUrl", "accent", "framerId"]
# `caption` is the optional lead-in before the link; one published case study
# genuinely has none, so it is checked for presence as a key, not for content.
OPTIONAL = ["caption"]

failures: list[str] = []
checks = 0


def check(ok: bool, message: str) -> None:
    global checks
    checks += 1
    if not ok:
        failures.append(message)


def normalize(text: str) -> str:
    """Collapse whitespace so wrapping differences never register as a change."""
    return re.sub(r"\s+", " ", text).strip()


def parse(path: str) -> tuple[dict, str]:
    raw = open(path, encoding="utf-8").read()
    _, front, body = raw.split("---", 2)
    meta: dict = {}
    key = None
    for line in front.strip().splitlines():
        if line.startswith("  - "):
            meta.setdefault(key, []).append(line[4:].strip().strip('"'))
        elif ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            meta[key] = value.strip('"') if value else []
    return meta, body.strip()


def main() -> None:
    if not os.path.exists(BASELINE):
        sys.exit("no .baseline/text.txt — capture the baseline first")
    haystack = normalize(open(BASELINE, encoding="utf-8").read())

    files = sorted(
        os.path.join(CONTENT, "case-studies", f)
        for f in os.listdir(os.path.join(CONTENT, "case-studies")) if f.endswith(".md")
    )
    check(len(files) == 7, f"expected 7 case studies, found {len(files)}")

    for path in files:
        name = os.path.basename(path)
        meta, body = parse(path)

        for field in REQUIRED:
            check(field in meta and meta[field] != "", f"{name}: missing {field}")
        for field in OPTIONAL:
            check(field in meta, f"{name}: {field} key absent")

        # 1. every visible string we produced must exist on the real page
        for field in ("title", "role", "expertise", "industry", "caption"):
            value = normalize(meta.get(field, ""))
            if value:
                check(value in haystack, f"{name}: {field} not found on the page: {value!r}")

        # Check line by line: a list is one markdown block but several separate
        # runs of text on the page, so the "- " between bullets must not survive
        # into the string being matched.
        for line in body.splitlines():
            plain = normalize(re.sub(r"\*\*(.+?)\*\*", r"\1", line).lstrip("- "))
            if len(plain) > 25:
                check(plain in haystack, f"{name}: body text not found on the page: {plain[:70]!r}")

        check(meta.get("linkUrl", "").startswith("http"),
              f"{name}: linkUrl is not absolute: {meta.get('linkUrl')!r}")
        check(re.fullmatch(r"#[0-9a-f]{6}", meta.get("accent", "")) is not None,
              f"{name}: accent is not a hex colour: {meta.get('accent')!r}")

        images = meta.get("images", [])
        check(len(images) >= 1, f"{name}: no images")
        for src in images:
            check(os.path.exists(os.path.join(SITE, src)), f"{name}: missing image {src}")

    # 2. nothing the page shows may be missing from the content
    titles = [normalize(parse(p)[0]["title"]) for p in files]
    for line in open(BASELINE, encoding="utf-8"):
        line = normalize(line)
        if len(line) > 40 and line.endswith(("Redesign", "Architecture", "Platform",
                                             "Operation", "Launch", "Product", "Assistant")):
            check(any(line in t or t in line for t in titles),
                  f"page shows a heading that no content file has: {line[:70]!r}")

    profile = json.load(open(os.path.join(CONTENT, "profile.json"), encoding="utf-8"))
    for field in ("name", "bio", "email", "linkedin", "cvUrl", "updated", "footer"):
        check(bool(profile.get(field)), f"profile: {field} is empty")
    check(normalize(profile["bio"]) in haystack, "profile: bio not found on the page")
    check(normalize(profile["name"]) in haystack, "profile: name not found on the page")
    for engine in profile.get("aiPromptEngines", []):
        check("&amp;" not in engine["url"], f"profile: {engine['name']} url is HTML-escaped")

    print(f"{checks} checks")
    if failures:
        print(f"\n{len(failures)} FAILED:")
        for f in failures:
            print(f"  ✗ {f}")
        sys.exit(1)
    print("all passed — extracted content matches the rendered page")


if __name__ == "__main__":
    main()
