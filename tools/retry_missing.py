#!/usr/bin/env python3
"""
Patiently re-fetch whatever the main crawl could not get.

mirror.py gives each asset nine quick attempts, which is right for a queue of
two hundred files but wrong for the last handful: those failed precisely because
the relays were rate-limiting, and the fix is to wait much longer between tries
rather than to try harder. This walks the failures one at a time with a long,
growing pause, and stops early on a genuine origin 404 (some sourceMappingURL
comments inside vendored bundles point at map files that were never published).

Files land at the same paths mirror.py uses, so a subsequent
`python3 tools/mirror.py` adopts them from disk and rewrites the references.

Usage:
    python3 tools/retry_missing.py [rounds]
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("mirror", os.path.join(ROOT, "tools", "mirror.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

PAUSE = [20, 30, 45, 60, 60, 90, 90, 120, 120, 150, 150, 180]

# Files the page actually needs come first; a source map that no one published
# should not hold up the module that renders the hero.
def priority(url: str) -> tuple[int, str]:
    if url.endswith(".map"):
        return (2, url)
    if m.ext_of(url) in (".mjs", ".js"):
        return (0, url)
    return (1, url)


def origin_404(body: bytes) -> bool:
    head = body[:400].lower()
    return b"404" in head and (b"not found" in head or b"nosuchkey" in head)


def try_once(url: str, build, dest: str) -> tuple[bool, str]:
    code, body, _ = m.curl(build(url), dest, timeout=120)
    if code == 200:
        ok, note = m.valid(url, code, body)
        if ok:
            return True, note
        why = note
    elif code == 404 or (body and origin_404(body)):
        why = "origin 404 (file does not exist)"
    else:
        why = f"http {code}"
    # A relay's error page or half-a-file must not be left sitting at the
    # asset's path, where the next run would find it and have to re-judge it.
    if os.path.exists(dest):
        os.remove(dest)
    return False, why


def main() -> None:
    sys.stdout.reconfigure(line_buffering=True)  # so progress is visible in a log
    m.load_manifest()
    missing = sorted((u for u, e in m.manifest.items() if not e.get("ok")),
                     key=priority)
    if not missing:
        print("nothing missing", flush=True)
        return
    print(f"retrying {len(missing)} files\n", flush=True)

    for url in missing:
        dest = m.local_path(url)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        if os.path.exists(dest) and os.path.getsize(dest) > 0:
            with open(dest, "rb") as fh:
                if m.valid(url, 200, fh.read())[0]:
                    print(f"  have  {os.path.basename(dest)[:60]}")
                    continue
        got = False
        gone = False
        for i, pause in enumerate(PAUSE):
            for name, build, accepts, _deg in m.RELAYS:
                if name == "codetabs" or not accepts(url):
                    continue
                ok, note = try_once(url, build, dest)
                if ok:
                    print(f"  OK    {os.path.basename(dest)[:60]}  "
                          f"{os.path.getsize(dest):,}b via {name}")
                    got = True
                    break
                if "does not exist" in note:
                    print(f"  GONE  {os.path.basename(dest)[:60]}  ({note})")
                    gone = True
                    break
                print(f"  ..    {os.path.basename(dest)[:44]:<46} {name}: {note}")
            if got or gone:
                break
            time.sleep(pause)
        if not got and not gone:
            print(f"  FAIL  {os.path.basename(dest)[:60]}")

    print("\nnow run: python3 tools/mirror.py")


if __name__ == "__main__":
    main()
