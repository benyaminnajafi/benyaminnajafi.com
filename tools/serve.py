#!/usr/bin/env python3
"""
Serve the mirrored site locally.

A plain `python3 -m http.server` is not quite enough here: the page loads its
bundles as ES modules, and .mjs has to arrive as JavaScript or the browser
refuses to execute it. This also serves site/404.html for unknown paths, the
way the real site does.

Usage:
    python3 tools/serve.py [port]     # default 8000
"""

from __future__ import annotations

import functools
import http.server
import os
import socketserver
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".mjs": "text/javascript",
        ".js": "text/javascript",
        ".json": "application/json",
        ".map": "application/json",
        ".webp": "image/webp",
        ".avif": "image/avif",
        ".woff2": "font/woff2",
        ".woff": "font/woff",
        ".svg": "image/svg+xml",
    }

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def send_error(self, code, message=None, explain=None):
        if code == 404:
            page = os.path.join(SITE, "404.html")
            if os.path.exists(page):
                with open(page, "rb") as fh:
                    body = fh.read()
                self.send_response(404)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                if self.command != "HEAD":
                    self.wfile.write(body)
                return
        super().send_error(code, message, explain)

    def log_message(self, fmt, *args):
        # keep the console readable: only surface failures
        if args and isinstance(args[0], str) and " 200 " not in f" {args[1] if len(args) > 1 else ''} ":
            pass
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    handler = functools.partial(Handler, directory=SITE)
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(("127.0.0.1", port), handler) as httpd:
        print(f"serving {os.path.relpath(SITE, ROOT)}/ at http://127.0.0.1:{port}/")
        print("ctrl-c to stop")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
