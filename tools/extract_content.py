#!/usr/bin/env python3
"""
Lift the site's content out of the Framer build into plain files.

The seven case studies live in the `framer/handover` payload baked into
site/index.html: a flat array where every value sits at its own index and
records point at those indices. Their bodies are a Framer richtext AST
(1 = fragment, 4 = [tag, props, ...children], 5 = text). The personal details
are not in that payload at all — they are markup, so they come from the page.

Output:
    content/profile.json                 name, title, bio, contacts, footer
    content/case-studies/NNN-slug.md     frontmatter + markdown body
    content/_extraction-report.json      what was read, and what was ignored

Nothing here touches site/. Run it as often as you like.

The output is NOT trusted on its own — verify_content.py re-renders the visible
text from these files and diffs it against .baseline/text.txt. Extraction from
an index-referenced blob fails *plausibly*: a caption bound to the wrong case
study reads fine and no screenshot will ever catch it.

Usage:
    python3 tools/extract_content.py
"""

from __future__ import annotations

import html as htmllib
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(ROOT, "site", "index.html")
OUT = os.path.join(ROOT, "content")

# Field ids, read off the published records.
FIELDS = {
    "title": "ICoj6VqKx",
    "body": "PdnagZZTF",
    "roleLabel": "cQ9wunk_K", "role": "NkejAtqzw",
    "expertiseLabel": "GJMt2cfz0", "expertise": "XM4Tow5R3",
    "industryLabel": "jji2ZrVdA", "industry": "odo6NfOM2",
    "caption": "E4SdgXSNx",
    "linkLabel": "cZAzhhJLQ",
    "linkUrl": "Kd5jM1aEC",
    "id": "id",
}
IMAGE_FIELDS = ["kELz1ETD1", "Ad6s1AoR8", "fKp164tJa", "j6Hv1l21u", "fJ8vgAFmQ", "aw2IwBwCX"]
COLOR_FIELDS = ["sHblk1LhN", "pm5lqVub7", "ly1yPFttY", "AdldRwrka", "xvEJJaLdL", "cXkAFUH3q"]


def load_payload() -> list:
    html = open(PAGE, encoding="utf-8").read()
    m = re.search(r'id="__framer__handoverData">(.*?)</script>', html, re.S)
    if not m:
        sys.exit("handover payload not found in site/index.html")
    return json.loads(m.group(1)), html


def unwrap(d: list, index):
    """Fields are wrapped {type, value}; return the plain value behind one."""
    if index is None:
        return None
    cell = d[index]
    if isinstance(cell, dict) and "value" in cell:
        return d[cell["value"]]
    return cell


def richtext_to_markdown(node, depth: int = 0) -> str:
    """Framer richtext AST → markdown. 1 fragment, 4 element, 5 text."""
    if not isinstance(node, list):
        return ""
    kind = node[0]

    if kind == 5:
        return node[1]

    if kind == 1:
        return "\n\n".join(
            p for p in (richtext_to_markdown(c, depth) for c in node[1:]) if p.strip()
        )

    if kind == 4:
        tag, props, children = node[1], node[2] or {}, node[3:]
        inner = "".join(richtext_to_markdown(c, depth + 1) for c in children)
        if tag == "br":
            # Two kinds of <br> and they mean opposite things. Framer closes every
            # block with `trailing-break` padding, which is spacing. A bare <br> is
            # a real line break, and a pair of them is a paragraph break — some case
            # studies are a single <p> holding three paragraphs that way. Dropping
            # both kinds glues those paragraphs together.
            return "" if props.get("className") == "trailing-break" else "\n"
        if tag == "strong":
            return f"**{inner.strip()}**" if inner.strip() else ""
        if tag == "em":
            return f"*{inner.strip()}*" if inner.strip() else ""
        if tag == "a":
            href = (node[2] or {}).get("href", "")
            return f"[{inner.strip()}]({href})"
        if tag == "li":
            return "- " + inner.strip()
        if tag == "ul":
            return "\n".join(
                richtext_to_markdown(c, depth + 1) for c in children
            )
        if tag in ("p", "div"):
            # Runs of line breaks inside one <p> are paragraph boundaries.
            return "\n\n".join(
                p.strip() for p in re.split(r"\n{2,}", inner) if p.strip()
            )
        return inner

    return ""


def slugify(title: str) -> str:
    base = title.split(":")[0].lower()
    base = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
    return re.sub(r"-{2,}", "-", base)[:48]


def yaml_str(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def extract_profile(html: str) -> dict:
    """The personal details are markup, not CMS fields — read them off the page."""
    def first(pattern, default=""):
        m = re.search(pattern, html)
        # Attributes are HTML-escaped in the source; `&amp;` in a query string is a
        # broken link, not a stylistic detail.
        return htmllib.unescape(m.group(1)).strip() if m else default

    links = dict.fromkeys(
        htmllib.unescape(u) for u in re.findall(r'href="(https://[^"]+)"', html)
    )
    return {
        "name": first(r"<h1[^>]*>(?:<[^>]+>)*([^<]+)"),
        "jobTitle": "Senior Product Designer",
        "bio": first(r'content="(10\+ years of experience[^"]+)"'),
        "email": first(r'href="mailto:([^"]+)"'),
        "phone": first(r'href="tel:([^"]+)"'),
        "linkedin": next((u for u in links if "linkedin.com" in u), ""),
        "cvUrl": next((u for u in links if "docs.google.com" in u), ""),
        "updated": first(r"Updated: ([A-Z][a-z]+ \d{2}, \d{4})"),
        "aiPromptEngines": [
            {"name": n, "url": u}
            for n, u in (("Gemini", "google.com/search"), ("ChatGPT", "chatgpt.com"),
                         ("Perplexity", "perplexity.ai"))
            for u in [next((x for x in links if u in x), "")] if u
        ],
        "footer": first(r"(© Benyamin Najafi, \d{4})"),
    }


def main() -> None:
    d, html = load_payload()
    records = d[3]
    os.makedirs(os.path.join(OUT, "case-studies"), exist_ok=True)

    report = {"payloadEntries": len(d), "records": len(records), "cases": [], "ignored": []}
    seen_indices: set = set()

    for order, rec_index in enumerate(records, start=1):
        rec = d[rec_index]
        seen_indices.add(rec_index)

        def field(name):
            idx = rec.get(FIELDS[name])
            if idx is not None:
                seen_indices.add(idx)
            return unwrap(d, idx)

        title = field("title")
        body_cell = field("body")
        markdown = ""
        if isinstance(body_cell, dict) and "pointer" in body_cell:
            markdown = richtext_to_markdown(json.loads(d[body_cell["pointer"]]))

        images = []
        for f in IMAGE_FIELDS:
            val = unwrap(d, rec.get(f))
            if isinstance(val, dict) and "src" in val:
                src = d[val["src"]] if isinstance(val["src"], int) else val["src"]
                master = re.sub(r"__scale-down-to-\d+", "__", src)
                if master not in images:
                    images.append(master)

        # Colours arrive as `var(--token-<uuid>, rgb(r, g, b))`. The token name is a
        # Framer id that means nothing outside Framer, so keep the literal colour.
        colors = []
        for f in COLOR_FIELDS:
            val = unwrap(d, rec.get(f))
            if not isinstance(val, str) or not val:
                continue
            m = re.search(r"rgba?\(([\d.,\s]+)\)", val)
            if m:
                parts = [int(float(x)) for x in m.group(1).split(",")[:3]]
                val = "#%02x%02x%02x" % tuple(parts)
            if val not in colors:
                colors.append(val)

        slug = slugify(title)
        front = {
            "order": order * 10,
            "title": title,
            "role": field("role"),
            "expertise": field("expertise"),
            "industry": field("industry"),
            "caption": (field("caption") or "").strip(),
            "linkLabel": (field("linkLabel") or "").strip(),
            "linkUrl": field("linkUrl") or "",
            "accent": colors[0] if colors else "",
            "framerId": field("id"),
        }

        lines = ["---"]
        for k, v in front.items():
            lines.append(f"{k}: {v}" if isinstance(v, int) else f"{k}: {yaml_str(str(v))}")
        lines.append("images:")
        for src in images:
            lines.append(f"  - {yaml_str(src)}")
        lines += ["---", "", markdown, ""]

        path = os.path.join(OUT, "case-studies", f"{order * 10:03d}-{slug}.md")
        open(path, "w", encoding="utf-8").write("\n".join(lines))
        report["cases"].append({
            "file": os.path.relpath(path, ROOT), "title": title,
            "images": len(images), "bodyChars": len(markdown),
            "hasLink": bool(front["linkUrl"]),
        })

    profile = extract_profile(html)
    open(os.path.join(OUT, "profile.json"), "w", encoding="utf-8").write(
        json.dumps(profile, indent=2, ensure_ascii=False) + "\n")
    report["profile"] = {k: bool(v) for k, v in profile.items()}

    open(os.path.join(OUT, "_extraction-report.json"), "w", encoding="utf-8").write(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n")

    print(f"{len(records)} case studies → {os.path.relpath(OUT, ROOT)}/case-studies/")
    for c in report["cases"]:
        print(f"  {c['images']} img  {c['bodyChars']:5d} chars  "
              f"{'link' if c['hasLink'] else '    '}  {c['title'][:52]}")
    missing = [k for k, v in profile.items() if not v]
    print(f"profile.json — {len(profile) - len(missing)}/{len(profile)} fields"
          + (f", MISSING: {', '.join(missing)}" if missing else ""))


if __name__ == "__main__":
    main()
