#!/usr/bin/env python3
"""
Mirror benyaminnajafi.com (a Framer-published site) into a fully local,
editable copy: every page, every JS module chunk, every image variant,
every font.

Why this exists: the site's HTML is served from benyaminnajafi.com (reachable),
but all of its assets live on framerusercontent.com, which is an AWS CloudFront
distribution that blocks Iranian IPs. So each asset is fetched either directly
(fast path, works behind a VPN) or through a public CORS relay (slow fallback).

The direct path is re-probed every round, so turning a VPN on mid-run makes the
rest of the run take the fast path automatically -- no restart needed.

Usage:
    python3 tools/mirror.py            # crawl + download + rewrite
    python3 tools/mirror.py --rewrite  # re-run the rewrite phase only
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote, unquote, urljoin, urlparse

# ---------------------------------------------------------------- config

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")
CDN = os.path.join(SITE, "_cdn")
WORK = os.path.join(ROOT, ".mirror")
ORIG = os.path.join(WORK, "original")  # pristine copies, so rewrite is idempotent
MANIFEST = os.path.join(WORK, "manifest.json")
LOG = os.path.join(WORK, "mirror.log")

ORIGIN = "https://benyaminnajafi.com"

# Optional SOCKS5/HTTP proxy for every request, e.g.
#   MIRROR_PROXY=socks5h://127.0.0.1:1080
# Needed because curl does not pick up macOS system proxy settings on its own.
PROXY = os.environ.get("MIRROR_PROXY", "").strip()

PAGES = {
    "/": "index.html",
    "/404": "404.html",
}

# Hosts whose assets we pull into the mirror.
ASSET_HOSTS = {"framerusercontent.com", "fonts.gstatic.com"}

# Hosts we deliberately never fetch (analytics, editor, outbound links).
SKIP_HOSTS = {
    "events.framer.com",
    "www.clarity.ms",
    "clarity.ms",
    "framer.com",
    "www.framer.com",
    "docs.google.com",
    "www.google.com",
    "www.linkedin.com",
    "chatgpt.com",
    "www.perplexity.ai",
    "www.w3.org",
    "benyaminnajafi.com",
}

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# Relays used only when the direct path is blocked. Each entry is
# (name, build-curl-argv, accepts-this-url, is-degraded), tried in order.
#
# wsrv.nl is an image proxy, so it only gets PNGs -- but it has no rate limit
# and it forwards Framer's ?scale-down-to= params to the origin, so it carries
# the bulk of the site quickly. It re-encodes, so the bytes differ from the
# origin even though the decoded pixels are identical; that is what "degraded"
# marks, and --refetch-degraded replaces those files once a direct route exists.
RELAYS = [
    ("wsrv",
     lambda u: ["https://wsrv.nl/?url=" + quote(u.split("://", 1)[1], safe="")],
     lambda u: ext_of(u) == ".png",
     True),
    ("cors.lol",
     lambda u: ["https://api.cors.lol/?url=" + quote(u, safe="")],
     lambda u: True, False),
    ("allorigins",
     lambda u: ["https://api.allorigins.win/raw?url=" + quote(u, safe="")],
     lambda u: True, False),
    ("codetabs",
     lambda u: ["https://api.codetabs.com/v1/proxy?quest=" + quote(u, safe="")],
     lambda u: True, False),
]

# Relays that showed no rate limiting, so requests to them need no pacing.
UNPACED = {"wsrv"}

TEXT_EXT = {".html", ".mjs", ".js", ".css", ".json", ".map", ".svg", ".txt", ".xml"}

MAGIC = {
    ".png": lambda b: b.startswith(b"\x89PNG"),
    ".jpg": lambda b: b.startswith(b"\xff\xd8\xff"),
    ".jpeg": lambda b: b.startswith(b"\xff\xd8\xff"),
    ".gif": lambda b: b.startswith(b"GIF8"),
    ".webp": lambda b: b.startswith(b"RIFF") and b[8:12] == b"WEBP",
    ".avif": lambda b: b[4:8] == b"ftyp",
    ".woff2": lambda b: b.startswith(b"wOF2"),
    ".woff": lambda b: b.startswith(b"wOFF"),
    ".ttf": lambda b: b[:4] in (b"\x00\x01\x00\x00", b"true", b"ttcf"),
    ".otf": lambda b: b.startswith(b"OTTO") or b[:4] == b"\x00\x01\x00\x00",
    ".mp4": lambda b: b[4:8] == b"ftyp",
    ".mov": lambda b: b[4:8] == b"ftyp",
    ".ico": lambda b: b[:4] in (b"\x00\x00\x01\x00", b"\x89PNG"),
}

# Bodies that mean "the relay failed", not "here is your file".
BAD_BODY = (
    b"Rate limit exceeded",
    b"ERROR: The request could not be satisfied",
    b"The Amazon CloudFront distribution is configured to block",
    b"Do not use this proxy",
    b"corsfix_error",
    b"error code: 5",
    b"banned for abuse",
)

# ---------------------------------------------------------------- state

_print_lock = threading.Lock()
_pick_lock = threading.Lock()
_relay_idx = 0
# Each relay rate-limits independently, so each gets its own lock and its own
# adaptive delay -- that way three requests can be in flight at once instead of
# every relay queueing behind one global pacer.
_relay_state = {
    name: {"lock": threading.Lock(), "delay": 1.5, "next_ok": 0.0, "dead": False}
    for name, _b, _a, _d in RELAYS
}
_direct_cache: dict[str, tuple[float, bool]] = {}
_direct_lock = threading.Lock()

manifest: dict[str, dict] = {}
seen: set[str] = set()
queue: list[str] = []
# every literal spelling of a url we saw in a document (e.g. with &amp;)
url_forms: dict[str, set[str]] = {}


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    with _print_lock:
        print(line, flush=True)
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")


# ---------------------------------------------------------------- url <-> path


def canon(u: str) -> str:
    """Normalise a url as scraped from a document into its real form."""
    u = u.replace("&amp;", "&").strip()
    u = u.rstrip(",;")
    while u and u[-1] in ")'\"":
        u = u[:-1]
    return u


def local_path(u: str) -> str:
    """Map an absolute asset url to its path inside site/_cdn."""
    p = urlparse(u)
    path = unquote(p.path)
    if path.endswith("/") or not path:
        path += "index.html"
    segs = [s for s in path.split("/") if s not in ("", ".", "..")]
    fname = segs[-1]
    if p.query:
        stem, dot, ext = fname.rpartition(".")
        if not dot:
            stem, ext = fname, ""
        slug = re.sub(r"[^A-Za-z0-9]+", "-", p.query).strip("-")
        if len(slug) > 60:
            slug = hashlib.md5(p.query.encode()).hexdigest()[:12]
        fname = f"{stem}__{slug}" + (f".{ext}" if ext else "")
    return os.path.join(CDN, p.netloc, *segs[:-1], fname)


def rel_from(target: str, from_file: str) -> str:
    """Relative href from the document at from_file to the file at target."""
    return os.path.relpath(target, os.path.dirname(from_file)).replace(os.sep, "/")


def ext_of(u: str) -> str:
    return os.path.splitext(urlparse(u).path)[1].lower()


# ---------------------------------------------------------------- fetching


def curl(args: list[str], out: str, timeout: int = 90) -> tuple[int, bytes, str]:
    """Run curl, return (http_code, body, content_type)."""
    cmd = [
        "curl", "-sS", "-L", "--compressed",
        "--max-time", str(timeout),
        "-A", UA,
        "-H", f"Referer: {ORIGIN}/",
        "-o", out,
        "-w", "%{http_code}\t%{content_type}",
    ]
    # curl on macOS ignores the system-wide proxy, so point it at one explicitly:
    #   MIRROR_PROXY=socks5h://127.0.0.1:1080 python3 tools/mirror.py
    if PROXY:
        cmd += ["--proxy", PROXY]
    cmd += args
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout + 20)
    except subprocess.TimeoutExpired:
        return 0, b"", ""
    meta = r.stdout.decode("utf-8", "replace").strip().split("\t")
    code = int(meta[0]) if meta and meta[0].isdigit() else 0
    ctype = meta[1] if len(meta) > 1 else ""
    # curl exits 18 on a partial transfer and 28 on timeout, both of which leave
    # a short file behind with a 200 status. Treat any curl-level failure as a
    # failed fetch rather than trusting the bytes that made it.
    if r.returncode != 0:
        code = 0
    body = b""
    if os.path.exists(out):
        with open(out, "rb") as fh:
            body = fh.read()
    return code, body, ctype


def complete(ext: str, body: bytes) -> tuple[bool, str]:
    """Is this file whole, not just correctly-headed?

    Magic bytes only prove the first four bytes survived. A relay that dies
    mid-response hands back a truncated image that still starts with the right
    signature, so check the trailer or the length recorded in the container.
    """
    try:
        if ext == ".png":
            if not body.endswith(b"IEND\xaeB`\x82"):
                return False, "truncated png (no IEND)"
        elif ext in (".jpg", ".jpeg"):
            if not body.rstrip(b"\x00").endswith(b"\xff\xd9"):
                return False, "truncated jpeg (no EOI)"
        elif ext == ".gif":
            if not body.endswith(b";"):
                return False, "truncated gif"
        elif ext == ".webp":
            declared = int.from_bytes(body[4:8], "little") + 8
            if declared != len(body):
                return False, f"truncated webp ({len(body)} of {declared})"
        elif ext == ".woff2":
            declared = int.from_bytes(body[8:12], "big")
            if declared != len(body):
                return False, f"truncated woff2 ({len(body)} of {declared})"
        elif ext == ".woff":
            declared = int.from_bytes(body[8:12], "big")
            if declared != len(body):
                return False, f"truncated woff ({len(body)} of {declared})"
    except Exception:
        return True, ""
    return True, ""


def js_complete(body: bytes) -> tuple[bool, str]:
    """Catch a bundle that a relay cut off mid-stream.

    Relays here have silently returned a clean 200 with a short body -- one
    module came back as an exact 75KB prefix of a 144KB file. Nothing about the
    header or the first bytes gives that away, but bundled JS always ends at a
    statement boundary, so a file ending in `,` or `:` or a bare identifier was
    cut. Only used to trigger a re-fetch, so a rare false positive is cheap.
    """
    s = body.rstrip()
    if not s:
        return False, "empty js"
    if b"sourceMappingURL=" in s[-200:] or s.endswith(b"*/"):
        return True, ""
    if s[-1:] in (b";", b"}", b")", b"]"):
        return True, ""
    return False, f"truncated js (ends with {s[-24:]!r})"


def valid(u: str, code: int, body: bytes) -> tuple[bool, str]:
    if code != 200:
        return False, f"http {code}"
    if not body:
        return False, "empty"
    head = body[:4096]
    for bad in BAD_BODY:
        if bad in head:
            return False, "relay error page"
    e = ext_of(u)
    if e in MAGIC:
        if not MAGIC[e](body):
            if body[:1] == b"<":
                return False, "got html, expected binary"
            return True, f"warn: {e} magic mismatch (kept)"
        return complete(e, body)
    if e in (".mjs", ".js", ".css"):
        if body.lstrip()[:1] == b"<":
            return False, "got html, expected code"
        return js_complete(body)
    if e in (".json", ".map"):
        try:
            json.loads(body.decode("utf-8", "replace"))
        except Exception:
            return False, "invalid json"
        return True, ""
    return True, ""


def direct_ok(host: str) -> bool:
    """Is this host reachable without a relay? Cached briefly, so flipping a
    VPN on mid-run is picked up within ~45s."""
    now = time.time()
    with _direct_lock:
        hit = _direct_cache.get(host)
        if hit and now - hit[0] < 45:
            return hit[1]
    canary = {
        "framerusercontent.com":
            "https://framerusercontent.com/images/miQRYUiGWzuTa7ZmvTtuS0TxEY.png",
        "fonts.gstatic.com":
            "https://fonts.gstatic.com/s/manrope/v20/"
            "xn7_YHE41ni1AdIRqAuZuw1Bx9mbZk7PFN_P-bnBeA.woff2",
    }.get(host, f"https://{host}/")
    tmp = os.path.join(WORK, f"canary-{host}.bin")
    code, body, _ = curl([canary], tmp, timeout=15)
    ok = code == 200 and bool(body) and not any(b in body[:4096] for b in BAD_BODY)
    with _direct_lock:
        _direct_cache[host] = (time.time(), ok)
    log(f"  direct[{host}] = {'OPEN' if ok else 'blocked'}")
    return ok


def fetch_direct(u: str, dest: str) -> tuple[bool, str, str]:
    code, body, _ = curl([u], dest)
    ok, note = valid(u, code, body)
    return ok, note, "direct"


def probe_relays() -> None:
    """Drop relays that cannot reach us at all, so retries aren't wasted on them."""
    target = "https://framerusercontent.com/images/miQRYUiGWzuTa7ZmvTtuS0TxEY.png"
    for name, build, _accepts, _deg in RELAYS:
        tmp = os.path.join(WORK, f"relay-{name}.bin")
        alive, code, note = False, 0, "unreachable"
        # Two tries: these relays are flaky, and a single transient 5xx is not
        # evidence that the service is gone. Only a relay we cannot reach at
        # all (code 0 -- blocked from here) is written off.
        for _ in range(2):
            code, body, _ = curl(build(target), tmp, timeout=25)
            ok, note = valid(target, code, body)
            if ok or code == 429 or 500 <= code < 600:
                alive = True
                break
        _relay_state[name]["dead"] = not alive
        log(f"  relay[{name}] = {'alive' if alive else 'dead'} ({code} {note})")
    if all(s["dead"] for s in _relay_state.values()):
        log("  ! no relay reachable -- only a VPN/proxy will get the assets")


def _eligible(u: str):
    """Relays that can serve this url, in preference order."""
    return [(n, b, d) for n, b, accepts, d in RELAYS
            if not _relay_state[n]["dead"] and accepts(u)]


def _next_relay(u: str):
    global _relay_idx
    live = _eligible(u)
    if not live:
        return None, None, False
    # The first eligible relay is the preferred one (wsrv for PNGs); rotate
    # through the rest so the rate-limited ones share the load.
    if len(live) == 1:
        return live[0]
    with _pick_lock:
        i = _relay_idx
        _relay_idx += 1
    return live[0] if i % 2 == 0 else live[1 + (i // 2) % (len(live) - 1)]


def fetch_relay(u: str, dest: str) -> tuple[bool, str, str]:
    last = "no relay"
    for attempt in range(9):
        name, build, degraded = _next_relay(u)
        if name is None:
            return False, "all relays dead", "relay"
        st = _relay_state[name]
        if name in UNPACED:
            # No rate limit worth respecting -- let the thread pool run flat out.
            code, body, _ = curl(build(u), dest)
            ok, note = valid(u, code, body)
        else:
            with st["lock"]:
                wait = st["next_ok"] - time.time()
                if wait > 0:
                    time.sleep(wait)
                code, body, _ = curl(build(u), dest)
                ok, note = valid(u, code, body)
                throttled = code == 429 or code == 0 or "rate limit" in note.lower()
                if ok:
                    st["delay"] = max(1.0, st["delay"] * 0.9)
                elif throttled:
                    st["delay"] = min(30.0, st["delay"] * 1.6)
                st["next_ok"] = time.time() + st["delay"]
        if ok:
            if degraded:
                note = (note + "; " if note else "") + "re-encoded (pixels intact)"
            return True, note, name
        last = f"{name}: {note}"
    return False, last, "relay"


def origin_says_absent(note: str, dest: str) -> bool:
    """Did the origin tell us this file simply is not there?

    The bucket behind framerusercontent answers a missing key with S3's
    `403 AccessDenied` rather than a 404 (it does not grant ListBucket), so
    both statuses mean the same thing here: stop looking.
    """
    if note == "http 404":
        return True
    if note == "http 403" and os.path.exists(dest):
        with open(dest, "rb") as fh:
            head = fh.read(400)
        return b"AccessDenied" in head or b"NoSuchKey" in head
    return False


def fetch(u: str) -> dict:
    """Download one url into the mirror. Returns its manifest entry."""
    dest = local_path(u)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    prev = manifest.get(u)
    if prev and prev.get("ok") and os.path.exists(dest) and os.path.getsize(dest) > 0:
        return prev

    # Resume from disk even without a manifest entry, so an interrupted run
    # never re-pays the relay cost for bytes we already have.
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        with open(dest, "rb") as fh:
            body = fh.read()
        ok, note = valid(u, 200, body)
        if ok:
            entry = {
                "ok": True, "local": os.path.relpath(dest, ROOT),
                "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(),
                "via": "on-disk", "note": note,
            }
            manifest[u] = entry
            if ext_of(u) in TEXT_EXT:
                o = os.path.join(ORIG, os.path.relpath(dest, SITE))
                if not os.path.exists(o):
                    os.makedirs(os.path.dirname(o), exist_ok=True)
                    with open(o, "wb") as fh:
                        fh.write(body)
            return entry

    host = urlparse(u).netloc
    ok, note, via = False, "", ""
    gone = False
    if direct_ok(host):
        ok, note, via = fetch_direct(u, dest)
        # Some URLs are inferred rather than observed -- a `sourceMappingURL`
        # comment inside a vendored bundle names a map that was never published
        # at that path. When the origin itself is reachable and says 404, that
        # is the answer; grinding through nine relay attempts cannot change it.
        if not ok and origin_says_absent(note, dest):
            gone, note = True, "not published at this path"
    if not ok and not gone:
        ok, note, via = fetch_relay(u, dest)

    body = b""
    if ok and os.path.exists(dest):
        with open(dest, "rb") as fh:
            body = fh.read()
        # keep a pristine copy of text files so rewriting can be re-run
        if ext_of(u) in TEXT_EXT:
            o = os.path.join(ORIG, os.path.relpath(dest, SITE))
            os.makedirs(os.path.dirname(o), exist_ok=True)
            with open(o, "wb") as fh:
                fh.write(body)
    elif not ok and os.path.exists(dest) and os.path.getsize(dest) < 2048:
        os.remove(dest)  # don't leave error pages lying around

    entry = {
        "ok": ok,
        "local": os.path.relpath(dest, ROOT),
        "bytes": len(body),
        "sha256": hashlib.sha256(body).hexdigest() if body else "",
        "via": via,
        "note": note,
    }
    manifest[u] = entry
    flag = "ok " if ok else "FAIL"
    log(f"  {flag} {len(body):>9,}b {via:<10} {u[:110]}{'  <' + note + '>' if note else ''}")
    checkpoint()
    return entry


_since_save = [0]


def checkpoint() -> None:
    """Persist the manifest periodically. A round can take many minutes on the
    relay path, and losing its bookkeeping to a ctrl-c means re-deriving it."""
    with _print_lock:
        _since_save[0] += 1
        due = _since_save[0] >= 15
        if due:
            _since_save[0] = 0
    if due:
        save_manifest()


# ---------------------------------------------------------------- extraction

ABS_URL = re.compile(r"https?://[^\s\"'<>()\\`]+")
# Source maps normalise their `sources` entries down to a single slash
# ("https:/framerusercontent.com/modules/.../DVH.js"). Those name real modules
# that appear nowhere else, so they have to be recognised and repaired.
ABS_URL_1SLASH = re.compile(
    r"https?:/(?!/)[A-Za-z0-9.-]+\.[A-Za-z]{2,}/[^\s\"'<>()\\`]*"
)
# Framer emits its dynamic page imports as import(`./Foo.hash.mjs`) -- backticks,
# not quotes -- so this has to cover all three string delimiters, and it matches
# any sibling reference rather than only `from`/`import` forms.
REL_IMPORT = re.compile(
    r"""["'`](\.{1,2}/[A-Za-z0-9._~%+-]+\.(?:mjs|js|css|json|map))["'`]"""
)
SOURCEMAP = re.compile(r"sourceMappingURL=([^\s*'\"]+)")
CSS_URL = re.compile(r"""url\(\s*['"]?([^'")]+)['"]?\s*\)""")


def record_form(c: str, literal: str) -> None:
    url_forms.setdefault(c, set()).add(literal)


def enqueue(u: str) -> None:
    if u in seen:
        return
    host = urlparse(u).netloc
    if host not in ASSET_HOSTS:
        return
    seen.add(u)
    queue.append(u)


def extract(base_url: str, text: str) -> None:
    """Find every asset reference in a text document and enqueue it."""
    for m in ABS_URL.finditer(text):
        literal = m.group(0)
        c = canon(literal)
        host = urlparse(c).netloc
        if host in SKIP_HOSTS:
            continue
        if host in ASSET_HOSTS:
            record_form(c, literal)
            # also remember the &amp; spelling, which is what sits in the HTML
            record_form(c, literal.replace("&amp;", "&"))
            enqueue(c)

    for m in ABS_URL_1SLASH.finditer(text):
        c = canon(m.group(0).replace(":/", "://", 1))
        if urlparse(c).netloc in ASSET_HOSTS:
            # Only worth fetching -- the single-slash spelling lives in sourcemap
            # metadata, which is not a reference anything resolves at runtime.
            enqueue(c)

    for m in REL_IMPORT.finditer(text):
        c = canon(urljoin(base_url, m.group(1)))
        record_form(c, m.group(1))
        enqueue(c)

    for m in SOURCEMAP.finditer(text):
        c = canon(urljoin(base_url, m.group(1)))
        enqueue(c)

    if base_url.endswith(".css") or "<style" in text[:2048]:
        for m in CSS_URL.finditer(text):
            v = m.group(1)
            if v.startswith("data:"):
                continue
            c = canon(urljoin(base_url, v))
            if urlparse(c).netloc in ASSET_HOSTS:
                record_form(c, v)
                enqueue(c)


def read_text(path: str) -> str | None:
    try:
        with open(path, "rb") as fh:
            return fh.read().decode("utf-8", "replace")
    except Exception:
        return None


# ---------------------------------------------------------------- phases


def download_pages() -> list[tuple[str, str]]:
    """Fetch the HTML pages from the origin. Returns (local_file, url) pairs."""
    out = []
    for route, name in PAGES.items():
        u = ORIGIN + route
        dest = os.path.join(SITE, name)
        os.makedirs(SITE, exist_ok=True)
        code, body, _ = curl([u], dest)
        # Framer serves the 404 route with a 404 status; that body is still the page.
        if body and body.lstrip()[:1] == b"<":
            o = os.path.join(ORIG, name)
            os.makedirs(os.path.dirname(o), exist_ok=True)
            with open(o, "wb") as fh:
                fh.write(body)
            log(f"page {route} -> site/{name}  ({len(body):,}b, http {code})")
            out.append((dest, u))
            manifest[u] = {
                "ok": True, "local": os.path.relpath(dest, ROOT),
                "bytes": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
                "via": "direct", "note": f"http {code}",
            }
        else:
            log(f"page {route} FAILED (http {code})")
    return out


def reseed() -> None:
    """Re-scan every text asset already on disk for references.

    On a resumed run the manifest pre-loads `seen`, so nothing already fetched
    gets re-queued -- and therefore nothing already fetched gets re-read. That
    matters after a truncated module is repaired: its restored tail can name
    assets that were never visible while the file was cut short.
    """
    n = 0
    for u, e in list(manifest.items()):
        if not e.get("ok") or ext_of(u) not in TEXT_EXT:
            continue
        t = read_text(os.path.join(ROOT, e["local"]))
        if t:
            extract(u, t)
            n += 1
    log(f"reseeded from {n} text assets")


def crawl() -> None:
    pages = download_pages()
    for dest, u in pages:
        t = read_text(dest)
        if t:
            extract(u, t)
    reseed()

    log(f"queued {len(queue)} assets from pages")
    rnd = 0
    while queue:
        rnd += 1
        batch, queue[:] = list(queue), []
        log(f"--- round {rnd}: {len(batch)} assets ---")
        # Split the batch by how expensive each item is to fetch, and run both
        # groups at once. Otherwise every worker grabs a rate-limited font off
        # the front of the queue and blocks on the same relay lock, while the
        # images -- which have an unmetered route -- wait their turn for nothing.
        def is_fast(u: str) -> bool:
            if direct_ok(urlparse(u).netloc):
                return True
            return any(n in UNPACED for n, _b, _d in _eligible(u))

        fast = [u for u in batch if is_fast(u)]
        slow = [u for u in batch if not is_fast(u)]
        paced = max(1, sum(1 for n, s in _relay_state.items()
                           if not s["dead"] and n not in UNPACED))
        log(f"    {len(fast)} on fast routes, {len(slow)} rate-limited")
        with ThreadPoolExecutor(max_workers=8) as fpool, \
             ThreadPoolExecutor(max_workers=paced) as spool:
            futures = [fpool.submit(fetch, u) for u in fast]
            futures += [spool.submit(fetch, u) for u in slow]
            for fut in futures:
                try:
                    fut.result()
                except Exception as e:
                    log(f"  ! worker error: {e}")
        save_manifest()
        # newly downloaded text files may reference more assets
        for u in batch:
            e = manifest.get(u)
            if not e or not e.get("ok") or ext_of(u) not in TEXT_EXT:
                continue
            t = read_text(os.path.join(ROOT, e["local"]))
            if t:
                extract(u, t)


def href_for(target: str, container: str) -> str:
    """How the document at `container` should refer to the file at `target`.

    CSS resolves url() against the stylesheet's own location, so those stay
    file-relative. Everything else -- HTML attributes and, crucially, asset
    URLs embedded as string literals inside JS modules -- is resolved by the
    browser against the *document* base URL, not the module's. Since both
    pages sit at the root of site/, making those paths relative to site/ is
    what actually loads.
    """
    if container.endswith(".css"):
        return rel_from(target, container)
    return os.path.relpath(target, SITE).replace(os.sep, "/")


IMPORT_ABS = re.compile(
    r"""((?:from|import)\s*\(?\s*)(["'`])(https?://[^"'`\s]+)\2"""
)


def fix_imports(text: str, container: str, have: dict[str, str]) -> str:
    """Rewrite absolute URLs that appear as ES module specifiers.

    An import specifier is resolved against the importing module's own URL,
    not the document's, and it must begin with `.` or `/` -- a bare
    `_cdn/foo.js` is read as a package name and fails to resolve. So these get
    a module-relative path, unlike asset URLs elsewhere in the same file.
    """
    def sub(mo: re.Match) -> str:
        head, quote, url = mo.group(1), mo.group(2), mo.group(3)
        target = have.get(canon(url))
        if not target:
            return mo.group(0)
        rel = rel_from(target, container)
        if not rel.startswith((".", "/")):
            rel = "./" + rel
        return f"{head}{quote}{rel}{quote}"

    return IMPORT_ABS.sub(sub, text)


def rewrite() -> None:
    """Point every absolute asset url at its local copy."""
    targets = [os.path.join(SITE, n) for n in PAGES.values()]
    for u, e in manifest.items():
        if e.get("ok") and ext_of(u) in TEXT_EXT and ext_of(u) != ".map":
            targets.append(os.path.join(ROOT, e["local"]))

    # canonical url -> local file, for everything we actually have
    have = {u: os.path.join(ROOT, e["local"])
            for u, e in manifest.items()
            if e.get("ok") and u.startswith("http") and urlparse(u).netloc in ASSET_HOSTS}

    changed = 0
    for f in targets:
        src = os.path.join(ORIG, os.path.relpath(f, SITE))
        base = src if os.path.exists(src) else f
        text = read_text(base)
        if text is None:
            continue
        out = text
        if f.endswith((".js", ".mjs")):
            out = fix_imports(out, f, have)
        # longest first, so .../x.png?width=1 never gets clobbered by .../x.png
        pairs = []
        for c, target in have.items():
            r = href_for(target, f)
            for literal in sorted(url_forms.get(c, {c}), key=len, reverse=True):
                pairs.append((literal, r))
            pairs.append((c, r))
            pairs.append((c.replace("&", "&amp;"), r))
        for literal, r in sorted(set(pairs), key=lambda p: -len(p[0])):
            if literal.startswith("http") and literal in out:
                out = out.replace(literal, r)
        if out != text:
            with open(f, "w", encoding="utf-8") as fh:
                fh.write(out)
            changed += 1
    log(f"rewrote {changed} files")


def save_manifest() -> None:
    os.makedirs(WORK, exist_ok=True)
    with open(MANIFEST, "w", encoding="utf-8") as fh:
        json.dump({"urls": manifest,
                   "forms": {k: sorted(v) for k, v in url_forms.items()}},
                  fh, indent=1)


def load_manifest() -> None:
    global manifest, url_forms
    if os.path.exists(MANIFEST):
        d = json.load(open(MANIFEST, encoding="utf-8"))
        manifest = d.get("urls", {})
        url_forms = {k: set(v) for k, v in d.get("forms", {}).items()}
        for u in manifest:
            seen.add(u)


def verify_all() -> None:
    """Re-check every downloaded file and re-fetch anything that isn't whole."""
    suspect = []
    for u, e in list(manifest.items()):
        if not e.get("ok") or not u.startswith("http"):
            continue
        p = os.path.join(ROOT, e["local"])
        if not os.path.exists(p):
            suspect.append((u, "missing on disk"))
            continue
        with open(p, "rb") as fh:
            body = fh.read()
        ok, note = valid(u, 200, body)
        if not ok:
            suspect.append((u, note))
            os.remove(p)
    log(f"--- verify: {len(suspect)} of {len(manifest)} need re-fetching ---")
    for u, why in suspect:
        log(f"  bad: {why}  {u[:110]}")
        manifest.pop(u, None)
        fetch(u)
    save_manifest()


def refetch_degraded() -> None:
    """Replace every re-encoded file with the origin's exact bytes.

    Only worth running once a direct route exists -- through a relay we would
    just fetch the same re-encoded bytes again.
    """
    if not direct_ok("framerusercontent.com"):
        log("direct route still blocked -- connect the VPN/proxy first")
        return
    deg = [u for u, e in manifest.items()
           if e.get("ok") and e.get("via") in ("wsrv",)]
    log(f"--- refetching {len(deg)} re-encoded files at origin fidelity ---")
    for u in deg:
        p = os.path.join(ROOT, manifest[u]["local"])
        manifest.pop(u, None)
        if os.path.exists(p):
            os.remove(p)
        fetch(u)
    save_manifest()


def report() -> None:
    ok = [u for u, e in manifest.items() if e.get("ok")]
    bad = [(u, e) for u, e in manifest.items() if not e.get("ok")]
    total = sum(e["bytes"] for e in manifest.values() if e.get("ok"))
    log(f"=== {len(ok)} ok, {len(bad)} failed, {total/1e6:.1f} MB ===")
    for u, e in bad:
        log(f"  MISSING {u}  ({e.get('note')})")


def main() -> None:
    os.makedirs(WORK, exist_ok=True)
    os.makedirs(ORIG, exist_ok=True)
    load_manifest()
    if "--refetch-degraded" in sys.argv:
        refetch_degraded()
        rewrite()
        save_manifest()
        report()
        return
    if "--verify" in sys.argv:
        if not all(direct_ok(h) for h in ASSET_HOSTS):
            probe_relays()
        verify_all()
        rewrite()
        save_manifest()
        report()
        return
    if "--rewrite" not in sys.argv:
        if not all(direct_ok(h) for h in ASSET_HOSTS):
            probe_relays()
        crawl()
        # retry anything still missing, now that rate limits may have eased
        missing = [u for u, e in manifest.items() if not e.get("ok")]
        if missing:
            log(f"--- retry pass: {len(missing)} missing ---")
            for u in missing:
                manifest.pop(u, None)
                fetch(u)
            save_manifest()
    rewrite()
    save_manifest()
    report()


if __name__ == "__main__":
    main()
