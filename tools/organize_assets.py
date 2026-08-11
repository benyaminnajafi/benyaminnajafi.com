#!/usr/bin/env python3
"""
Collect the assets the site actually uses into src/assets/, named by hand.

Framer's asset tree is content-hashed and flat: 138 image files under one
directory, 52 fonts behind opaque fontshare ids, and no way to tell from a
filename what anything is. This copies out only what is live, into a shape a
person can read, and reports what was left behind.

Copies, never moves — site/ is still what deploys until cutover, so it must not
lose a byte. site/ is deleted in one step at the end of the migration.

What counts as live:
  images  every master referenced by content/case-studies/*.md, plus the portrait
  fonts   only the files the browser actually requests. 47 of the 52 on disk are
          never fetched: their @font-face rules are gated by unicode-range for
          scripts this site never renders, so they cost disk and nothing else.

Rewrites the image paths in content/ to point at the new locations.

Usage:
    python3 tools/organize_assets.py
"""

from __future__ import annotations

import json
import os
import re
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")
CONTENT = os.path.join(ROOT, "content", "case-studies")
ASSETS = os.path.join(ROOT, "src", "assets")

# The five files the browser actually requests, measured from the network log.
# Everything else under site/_cdn is dead weight: 47 more woff2 whose @font-face
# rules are gated by unicode-range for scripts this page never renders.
LIVE_FONTS = [
    "K4ZMLVLHYIFVTTTWGVOTVGOFUUX7NVGI.woff2",
    "xn7_YHE41ni1AdIRqAuZuw1Bx9mbZk7PFN_C-bk.woff2",
    "6P4FPMFQH7CCC7RZ4UU4NKSGJ2RLF7V5.woff2",
    "DEPNXL2T77QGX4DXZAN3G53TXHO2JEFP.woff2",
    "JNU3GNMUBPWW6V6JTED3S27XL5HN7NM5.woff2",
]


def font_names(page: str) -> dict:
    """Name each live font from its own @font-face rule, never by hand.

    These filenames are opaque hashes. Assigning weights to them by eye gets it
    wrong — a first pass here mislabelled four of the five, which would have
    shipped every heading at the wrong weight while still looking like Manrope.
    """
    names = {}
    for face in re.findall(r"@font-face\s*\{([^}]*)\}", page):
        for filename in LIVE_FONTS:
            if filename not in face:
                continue
            family = re.search(r"font-family:\s*['\"]?([^;'\"]+)", face)
            weight = re.search(r"font-weight:\s*(\d+)", face)
            if not family or not weight:
                raise SystemExit(f"@font-face for {filename} has no family or weight")
            stem = family.group(1).strip().lower().replace(" ", "-")
            # One file covers the whole range; its declared 400 is not a weight.
            names[filename] = (f"{stem}.woff2" if "variable" in stem
                               else f"{stem}-{weight.group(1)}.woff2")
    missing = [f for f in LIVE_FONTS if f not in names]
    if missing:
        raise SystemExit(f"no @font-face rule found for: {', '.join(missing)}")
    return names


def slug_of(filename: str) -> str:
    return re.sub(r"^\d+-", "", filename[:-3])


def find(name: str) -> str | None:
    for base, _, files in os.walk(SITE):
        if name in files:
            return os.path.join(base, name)
    return None


def main() -> None:
    report: dict = {"images": [], "fonts": [], "skipped": {}}
    kept_bytes = 0
    page = open(os.path.join(SITE, "index.html"), encoding="utf-8").read()

    # --- images -----------------------------------------------------------
    for filename in sorted(os.listdir(CONTENT)):
        if not filename.endswith(".md"):
            continue
        slug = slug_of(filename)
        path = os.path.join(CONTENT, filename)
        text = open(path, encoding="utf-8").read()
        sources = re.findall(r'^  - "([^"]+)"', text, re.M)

        out_dir = os.path.join(ASSETS, "case-studies", slug)
        os.makedirs(out_dir, exist_ok=True)

        for n, src in enumerate(sources, start=1):
            source_path = os.path.join(SITE, src)
            if not os.path.exists(source_path):
                report["skipped"].setdefault("missingImage", []).append(src)
                continue
            ext = os.path.splitext(src)[1]
            dest_name = f"{n:02d}{ext}"
            shutil.copy2(source_path, os.path.join(out_dir, dest_name))
            kept_bytes += os.path.getsize(source_path)
            new_ref = f"../../src/assets/case-studies/{slug}/{dest_name}"
            text = text.replace(f'"{src}"', f'"{new_ref}"')
            report["images"].append(f"{slug}/{dest_name}")

        open(path, "w", encoding="utf-8").write(text)

    # The portrait is in the markup, not the CMS payload. Match the full-size
    # master, and bound the pattern: a srcset holds several comma-separated URLs
    # inside one attribute, so anything greedy up to the closing quote swallows
    # the lot and yields a filename that cannot exist.
    portrait = re.search(r"images/([A-Za-z0-9]+__width-\d+-height-\d+\.jpe?g)", page)
    if not portrait:
        raise SystemExit("portrait not found in site/index.html — pattern is stale")
    found = find(portrait.group(1))
    if not found:
        raise SystemExit(f"portrait {portrait.group(1)} referenced but not on disk")
    shutil.copy2(found, os.path.join(ASSETS, "portrait.jpeg"))
    kept_bytes += os.path.getsize(found)
    report["images"].append("portrait.jpeg")

    # --- fonts ------------------------------------------------------------
    os.makedirs(os.path.join(ASSETS, "fonts"), exist_ok=True)
    for original, friendly in font_names(page).items():
        found = find(original)
        if not found:
            report["skipped"].setdefault("missingFont", []).append(original)
            continue
        shutil.copy2(found, os.path.join(ASSETS, "fonts", friendly))
        kept_bytes += os.path.getsize(found)
        report["fonts"].append(friendly)

    # --- what stays behind ------------------------------------------------
    all_fonts = [f for _, _, fs in os.walk(SITE) for f in fs if f.endswith(".woff2")]
    all_images = os.listdir(os.path.join(SITE, "_cdn", "framerusercontent.com", "images"))
    site_bytes = sum(
        os.path.getsize(os.path.join(b, f))
        for b, _, fs in os.walk(SITE) for f in fs
    )
    report["summary"] = {
        "keptFiles": len(report["images"]) + len(report["fonts"]),
        "keptBytes": kept_bytes,
        "siteBytes": site_bytes,
        "deadFonts": len(all_fonts) - len(report["fonts"]),
        "deadImageFiles": len(all_images) - len(report["images"]) + 1,
    }

    open(os.path.join(ROOT, "src", "assets", "_report.json"), "w", encoding="utf-8").write(
        json.dumps(report, indent=2) + "\n")

    s = report["summary"]
    print(f"kept {s['keptFiles']} files, {s['keptBytes'] / 1048576:.1f} MB")
    print(f"  {len(report['images'])} images, {len(report['fonts'])} fonts")
    print(f"left behind in site/: {s['deadFonts']} fonts, "
          f"{s['deadImageFiles']} image files")
    print(f"site/ is {s['siteBytes'] / 1048576:.1f} MB and stays until cutover")


if __name__ == "__main__":
    main()
