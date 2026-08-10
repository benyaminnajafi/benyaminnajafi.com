# Visual baseline — the reference the rebuild is measured against

Captured from the local mirror at http://127.0.0.1:8000/ (byte-identical to the
live site). Regenerate with tools/verify/ once that exists.

## Theme probe

The site's background lives on an inner element, not on `body` or `html` — both
report `rgba(0,0,0,0)` at most widths. Asserting on them silently passes even
when the theme never switched, which is how the first capture of this baseline
produced eight files containing only four distinct images.

Probe the `h1` text colour instead:

    light  h1 color = rgb(18, 18, 18)
    dark   h1 color = rgb(240, 240, 240)

The theme is set by `localStorage.theme` (`light` | `dark`), read on load.
Set it, then reload — changing it on a live page does not repaint.

## Contents

  home-{1440x900,1280x800,768x1024,375x812}-{light,dark}.png
  structure.json   element counts and page height
  text.txt         document.body.innerText, the content-equality reference

All eight PNGs must be distinct. If any two match, the capture is broken.
