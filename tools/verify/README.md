# Fidelity harness

The rebuild is not "close enough by eye" — it is held to the values the live
Framer site actually resolves. Three artefacts, one command each.

## 1. Capture the reference (once, and after any change to the live site)

    $B goto http://127.0.0.1:8000/
    $B eval tools/capture_styles.js --out .baseline/styles-light.json --raw

Do it for both themes. The theme is `localStorage.theme` and only takes effect
on load, so set it and reload. Assert on the `h1` colour, not on `body`'s
background: the background lives on an inner element and reads transparent at
most widths, which is how the first baseline captured light twice and nobody
noticed.

    light  h1 = rgb(18, 18, 18)      dark  h1 = rgb(240, 240, 240)

## 2. Compare a candidate

    python3 tools/verify/compare_styles.py <candidate.json> <reference.json> \
        [--type-only] [--allow-missing=a,b]

`--type-only` skips box geometry, for checking type before any layout exists.
`--allow-missing` names landmarks a partial fixture legitimately lacks.

Differences fail the run unless they are in `WAIVERS` in that file, each with a
written reason. There is one waiver today and it documents a real bug that was
fixed rather than reproduced: the caption link's underline and background were
hard-coded off the dark-theme green, so in light mode a dark-green word sat on a
light-green wash. They now derive from `--accent`.

## 3. The type fixture

`type-fixture.html` renders every type role with no layout around it, so the
type can be proven correct before the page exists. Serve the repo root and open
`/tools/verify/type-fixture.html`.

## Why computed styles rather than screenshots

A pixel diff with any tolerance swallows 22px vs 22.4px, `1.5em` vs `1.5`, and
`#f4f4f48c` vs `#f4f4f4d9`. Those are invisible in one screenshot and obvious
across a page. Screenshots are still worth taking — they catch layout the style
dump cannot — but they are the second line, not the first.
