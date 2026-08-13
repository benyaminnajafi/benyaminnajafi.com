# Fidelity harness

The rebuild is not "close enough by eye" — it is held to the values the live
Framer site actually resolves.

## What this gate missed once, and why

The first Astro cutover passed with "168 computed properties across 15
landmarks" and shipped a page that was visibly worse: the hero band collapsed
from 489px to 284px, every entrance animation was gone, the bold ran out of the
bio, and three carousels stretched and cropped their screenshots.

None of it was catchable. All 15 landmarks were **leaf text nodes**, so no
container was ever measured and every spacing property in the list resolved to
`0px` on the elements chosen. `page.scrollHeight` was captured and never
compared. Only the first of seven case studies was looked at. And the number
quoted in that commit is exactly what `--type-only` compares, which excludes
box geometry entirely.

The harness now measures containers, all seven case rows, whole-page height,
effective opacity and blend, and animation. A clean run compares **507**
properties, not 168.

## 1. Serve both sides

    npm run reference        # the Framer mirror on :8099
    npm run build && npx astro preview --port 4321

## 2. Capture

    $B goto http://localhost:8099/index.html
    $B eval tools/capture_styles.js --out .baseline/styles-light.json --raw

Do it for both themes and both sides. The theme is `localStorage.theme` and
only takes effect on load, so set it and reload. Assert on the `h1` colour, not
on `body`'s background: the background lives on an inner element and reads
transparent at most widths, which is how the first baseline captured light
twice and nobody noticed.

    light  h1 = rgb(18, 18, 18)      dark  h1 = rgb(240, 240, 240)

Capture at **1440x900**. The viewport is recorded in the file and the compare
step refuses to diff two different sizes — every box in there is
width-dependent, and there used to be a theme guard but no width guard.

## 3. Compare

    $B eval tools/capture_text.js --out /tmp/candidate.txt --raw
    npm run verify:styles -- <candidate.json> <reference.json>
    npm run verify:text   -- <candidate.txt>

Capture the text with that script rather than reading `innerText` directly.
Case rows carry `content-visibility: auto` so their slides are not fetched
until scrolled to, and `innerText` reports rendered text only — five case
studies go missing from a naive capture. Both capture scripts realise the rows
first, for the same reason they settle animations and release reveals.

Differences fail the run unless they are in `WAIVERS`, each with a written
reason. `--allow-missing=a,b` names landmarks a partial fixture lacks.

`--type-only` skips box geometry, for checking type before any layout exists.
**It is not an acceptance run.** It was mistaken for one once.

### What is gated, and what is only recorded

Containers are captured broadly and gated narrowly, on `_box`, `padding-top`,
`padding-bottom` and `gap`. The two builds reach the same layout by different
means — Framer lays out with `flex: 1.2/2` where the rebuild uses a `1.2fr 2fr`
grid, sets `position: relative` and a white background on every block, and
draws its hairlines with absolutely-positioned divs rather than real borders.
Diffing `display`, `position`, `background-color` or `border-width` across that
reports thirty-odd differences no reader could see, and a gate that cries wolf
is a gate someone turns off. The rest is still in the JSON to read.

Opacity and blend are read through the **ancestor chain**, not off the element:
the carousel hint's own `<p>` reports `opacity: 1` while a wrapper holds it at
`0`. Comparing the leaf's own value compares two different elements.

Animations are settled before measuring — finite ones jumped to their end,
looping ones pinned to the start of their cycle — or an animated element
reports whatever phase the capture happened to catch.

## 4. Behaviour

    $B goto http://localhost:4321/
    $B eval tools/verify/check_behaviour.js --raw

Eight assertions the style gate structurally cannot make. All three defects
found in review after the first fix pass — clicking a carousel doing nothing,
the rule under "Selected Case Studies" disappearing when the case rule moved
from top to bottom, and all seven hints pulsing at once — are caught here and
were not caught by the 507-property run. Verified both ways: the script fails
on the build that had them and passes on the one that does not.

Run it at **1440x900**; the offscreen-hint assertion assumes only one carousel
is on screen.

## 5. What is still eyes-only

- the staged entrance cascade, and its order (0.3 / 0.6 / 0.9 / 1.2s)
- dragging a carousel, and that it does not select the caption behind it
- `/#case-studies` actually landing on the case studies
- the page at 1440 / 1280 / 768 / 375, against `.baseline/home-*.png`
- both themes, and the toggle between them

## Why computed styles rather than screenshots

A pixel diff with any tolerance swallows 22px vs 22.4px, `1.5em` vs `1.5`, and
`#f4f4f48c` vs `#f4f4f4d9`. Those are invisible in one screenshot and obvious
across a page. Screenshots are still worth taking — they catch layout the style
dump cannot — but they are the second line, not the first.

## CI

`npm run verify` (content) runs in `deploy.yml`. The style and layout gate does
not: it drives a real browser against the Framer mirror on a second port, which
needs a Playwright runner in CI. Until that exists it is the pre-merge step
above, and it is the one that matters.
