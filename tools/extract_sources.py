#!/usr/bin/env python3
"""
Recover original source files from the published source maps.

Framer ships .map files alongside its JS bundles, and those maps carry
sourcesContent -- the pre-bundle source of every module, including the code
generated for each of the site's own components. Extracting them turns the
minified mirror into something you can actually read and edit.

Output goes to sources/, mirroring each map's own source paths.

Usage:
    python3 tools/extract_sources.py
"""

from __future__ import annotations

import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CDN = os.path.join(ROOT, "site", "_cdn")
OUT = os.path.join(ROOT, "sources")


def safe_rel(name: str) -> str:
    """Turn a sourcemap 'sources' entry into a safe relative path."""
    name = re.sub(r"^(?:https?://[^/]+/)?", "", name)
    name = name.replace("\x00", "")
    # strip webpack/rollup-style prefixes and any traversal
    name = re.sub(r"^(?:webpack://|rollup://|\.{1,2}/|/)+", "", name)
    parts = [p for p in name.split("/") if p not in ("", ".", "..")]
    if not parts:
        parts = ["unnamed"]
    parts = [re.sub(r'[<>:"|?*]', "_", p) for p in parts]
    # keep filenames sane on macOS
    parts[-1] = parts[-1][:180] or "unnamed"
    return os.path.join(*parts)


def main() -> None:
    maps = []
    for dirpath, _dirs, files in os.walk(CDN):
        for f in files:
            if f.endswith(".map"):
                maps.append(os.path.join(dirpath, f))

    if not maps:
        print("no .map files found under site/_cdn -- run tools/mirror.py first")
        return

    written = 0
    skipped = 0
    per_map = []
    for m in sorted(maps):
        try:
            with open(m, encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception as e:
            print(f"  ! cannot parse {os.path.relpath(m, ROOT)}: {e}")
            continue
        sources = data.get("sources") or []
        contents = data.get("sourcesContent") or []
        n = 0
        for i, src in enumerate(sources):
            if i >= len(contents):
                break
            body = contents[i]
            if body is None:
                skipped += 1
                continue
            dest = os.path.join(OUT, safe_rel(src))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "w", encoding="utf-8") as fh:
                fh.write(body)
            n += 1
            written += 1
        per_map.append((os.path.basename(m), len(sources), n))

    for name, total, n in per_map:
        print(f"  {name:<52} {n}/{total} sources")
    print(f"\nwrote {written} source files to sources/ ({skipped} had no content)")


if __name__ == "__main__":
    main()
