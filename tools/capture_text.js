// The words the page renders, for compare_text.py.
//
// Not just `document.body.innerText`. Case rows carry content-visibility:auto
// so their slides are not fetched until they are scrolled to, and innerText
// reports rendered text only — so an unrealised row contributes nothing and
// five case studies go missing from the capture. Realising the rows first
// measures what a reader who scrolls actually reads.
//
// The text is still in the DOM and still indexable either way; this is a
// limitation of innerText, not of the page.
//
// Run through gstack browse:
//   $B eval tools/capture_text.js --out /tmp/candidate.txt --raw

for (const el of document.querySelectorAll('.case')) {
  el.style.contentVisibility = 'visible';
}

document.body.innerText;
