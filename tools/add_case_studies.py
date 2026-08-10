#!/usr/bin/env python3
"""
Add the case studies that are not in the Framer project to site/index.html.

The five published case studies come from a Framer CMS collection. Framer bakes
that collection into the page as a `framer/handover` payload — a flat JSON array
where every value lives at its own index and records point at those indices. At
hydration React re-renders the list from that payload, which is why editing the
server-rendered markup alone does nothing: the payload wins and the edit is
discarded.

So this appends real records to the payload instead. Each record carries the
title, a richtext body, the role / expertise / industry pairs, the six carousel
images, and the section colours.

Idempotent: records are keyed by `id`, and an existing one with the same id is
replaced rather than duplicated. Re-run after `mirror.py --rewrite`, which
restores index.html from the pristine origin copy and drops these records.

Usage:
    python3 tools/add_case_studies.py
"""

from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(ROOT, "site", "index.html")
IMG_DIR = "_cdn/framerusercontent.com/images"

# The record we clone field-for-field. Anything not overridden below keeps the
# donor's value, which is how the colours, enums and spacing stay consistent.
DONOR = 0


def rich(paragraphs: list[str], bullets: list[tuple[str, str]]) -> str:
    """Build Framer's richtext pointer: 4 = element, 5 = text, 1 = fragment."""
    br = [[4, "br", None], [4, "br", {"className": "trailing-break"}]]
    out: list = [1]
    for text in paragraphs:
        out.append([4, "p", {"dir": "auto"}, [5, text], *br])
    if bullets:
        items = []
        for label, body in bullets:
            kids = []
            if label:
                kids.append([4, "strong", None, [5, label]])
            kids.append([5, body])
            items.append([4, "li", {"data-preset-tag": "p"}, [4, "p", None, *kids, *br]])
        out.append([4, "ul", {"dir": "auto"}, *items])
    return json.dumps(out, ensure_ascii=False)


CASES = [
    {
        "id": "revaalCase01",
        "title": "From Source to Publish on One Canvas: Designing an Agentic Workflow Product",
        "role": "Founding Product Designer",
        "expertise": "0→1 & Agentic Workflow Design",
        "industry": "AI Tooling (Editorial)",
        "label": "From source to publish",
        "link_label": " Visit revaal.app ⤴︎ ",
        "link": "https://revaal.app/",
        # Slot order is the carousel order; slot 1 is the frame shown at rest.
        "images": ["revaalShot1Kv3", "revaalShot2Kv3", "revaalShot3Kv3",
                   "revaalShot4Kv3", "revaalShot5Kv3", "revaalShot1Kv3"],
        "body": rich(
            [
                "Revaal puts AI agents on a canvas a content team can see, wire, run and "
                "audit — connect a source, arrange the steps, let the last step publish, "
                "no code.",
            ],
            [
                ("Designed for the constraint:",
                 " Iranian sources read from inside, models called from outside, settlement "
                 "in Toman: all three in the architecture, not a workaround."),
                ("Made trust a feature:",
                 " per-node token and cost accounting, an append-only audit log, a separate "
                 "permission grant per tool."),
                ("Proved it on real work:",
                 " 119 sources across 16 beats, crawled, clustered and drafted daily for a "
                 "financial news desk."),
            ],
        ),
    },
    {
        "id": "benanCase01",
        "title": "Five Specialists Behind One Conversation: A Voice-First Investment Assistant",
        "role": "Founding Product Designer",
        "expertise": "0→1 & Conversational Design",
        "industry": "Fintech (AI Assistant)",
        "label": "Talk to the assistant",
        "link_label": " Visit benan.app ⤴︎ ",
        "link": "https://benan.app/",
        "images": ["benanShot1Kv3", "benanShot2Kv3", "benanShot3Kv3",
                   "benanShot1Kv3", "benanShot2Kv3", "benanShot3Kv3"],
        "body": rich(
            [
                "Benan is a Persian, right-to-left investment assistant you talk to: tap the "
                "orb and a voice agent answers out loud, or type and the same assistant "
                "replies in the chat bar.",
            ],
            [
                ("Framed it around five specialties:",
                 " market analysis, live prices, news, tax, financial health — with the "
                 "assistant routing between them rather than the user picking a tool."),
                ("Made voice the primary surface:",
                 " the orb is the main action on screen; the typed chat bar sits under it."),
                ("Kept the secret off the client:",
                 " the backend mints a short-lived signed URL per session, so the API key "
                 "never reaches the browser."),
            ],
        ),
    },
]

# Field ids in the collection, read off the published records.
F_TITLE, F_BODY, F_ID = "ICoj6VqKx", "PdnagZZTF", "id"
F_ROLE, F_EXPERTISE, F_INDUSTRY = "NkejAtqzw", "XM4Tow5R3", "odo6NfOM2"
F_LABEL, F_LINK_LABEL, F_LINK = "E4SdgXSNx", "cZAzhhJLQ", "Kd5jM1aEC"

# The published "Scaling to 4.5M Users" record puts its whole caption in the linked
# field, so the lead-in is underlined and coloured along with the link — every other
# record splits it. Move the lead-in back to the plain label field.
FIXES = {
    "bnVQcA4Jz": {F_LABEL: "See how we scaled", F_LINK_LABEL: " Read case study ⤴︎ "},
}
F_IMAGES = ["kELz1ETD1", "Ad6s1AoR8", "fKp164tJa", "j6Hv1l21u", "fJ8vgAFmQ", "aw2IwBwCX"]


# Plain text swaps. The "Updated" line is not a CMS field — it is hardcoded in the
# page component, which is what re-renders over the server markup at hydration, so
# every copy has to change or the old date comes back.
TEXT_SWAPS = [
    ("Updated: April 04, 2026", "Updated: August 10, 2026"),
]
SWAP_FILES = [
    "site/index.html",
    "site/_cdn/framerusercontent.com/sites/mnhZz3KMNsz6199efSvaG/"
    "jP_Nbd8-iKLTKkYl_6yHIXSK-i5c9TdDEXX0_5UdBjQ.Cd6yfcyS.mjs",
    "site/_cdn/framerusercontent.com/sites/mnhZz3KMNsz6199efSvaG/searchIndex-I4uTarR1MJXC.json",
    "site/_cdn/framerusercontent.com/sites/mnhZz3KMNsz6199efSvaG/searchIndex-C75LgRKp5B9H.json",
]


def apply_text_swaps() -> None:
    for rel in SWAP_FILES:
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            continue
        text = open(path, encoding="utf-8").read()
        swapped = text
        for old, new in TEXT_SWAPS:
            swapped = swapped.replace(old, new)
        if swapped != text:
            open(path, "w", encoding="utf-8").write(swapped)


def main() -> None:
    apply_text_swaps()
    html = open(PAGE, encoding="utf-8").read()
    m = re.search(r'(id="__framer__handoverData">)(.*?)(</script>)', html, re.S)
    if not m:
        sys.exit("handover payload not found — is site/index.html the mirrored page?")
    d = json.loads(m.group(2))
    items = d[3]

    def put(value) -> int:
        d.append(value)
        return len(d) - 1

    def typed(type_name: str, value) -> int:
        return put({"type": put(type_name), "value": put(value)})

    def image(slug: str) -> int:
        stem = f"{IMG_DIR}/{slug}"
        size = "width-1920-height-1440"
        return typed("responsiveimage", {
            "src": put(f"{stem}__{size}.png"),
            "srcSet": put(
                f"{stem}__scale-down-to-512-{size}.png 512w,"
                f"{stem}__scale-down-to-1024-{size}.png 1024w,"
                f"{stem}__{size}.png 1920w"),
            "pixelWidth": put(1920),
            "pixelHeight": put(1440),
        })

    def record_id(index: int):
        """Record ids are wrapped like every other field: {type, value}."""
        cell = d[d[index][F_ID]]
        return d[cell["value"]] if isinstance(cell, dict) and "value" in cell else cell

    # Drop records this script added on an earlier run, so it stays idempotent.
    wanted = {c["id"] for c in CASES}
    items = [i for i in items if record_id(i) not in wanted]

    # Clone a published record so the colours, enums and spacing come along. Taken
    # after the filter above, so a re-run never clones one of our own records.
    donor = d[items[DONOR]]

    added = []
    for case in CASES:
        rec = dict(donor)
        rec[F_TITLE] = typed("string", case["title"])
        rec[F_ROLE] = typed("string", case["role"])
        rec[F_EXPERTISE] = typed("string", case["expertise"])
        rec[F_INDUSTRY] = typed("string", case["industry"])
        rec[F_BODY] = typed("richtext", {
            "collectionId": d[d[donor[F_BODY]]["value"]]["collectionId"],
            "pointer": put(case["body"]),
        })
        rec[F_LABEL] = typed("string", case["label"])
        rec[F_LINK_LABEL] = typed("string", case["link_label"])
        rec[F_LINK] = typed("link", case["link"])
        for field, slug in zip(F_IMAGES, case["images"]):
            rec[field] = image(slug)
        rec[F_ID] = typed("string", case["id"])
        added.append(put(rec))

    for index in items:
        patch = FIXES.get(record_id(index))
        if patch:
            for field, text in patch.items():
                d[index][field] = typed("string", text)

    # These two lead the list; the published five keep their own order behind them.
    d[3] = added + items
    payload = json.dumps(d, ensure_ascii=False, separators=(",", ":"))
    if "</script" in payload.lower():
        sys.exit("payload would close its own script tag — refusing to write")

    open(PAGE, "w", encoding="utf-8").write(html[:m.start(2)] + payload + html[m.end(2):])
    print(f"{len(CASES)} case studies added — {len(d[3])} records, {len(d)} payload entries")


if __name__ == "__main__":
    main()
