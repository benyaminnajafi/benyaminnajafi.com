// Dump the computed style of every landmark on the page, both themes.
//
// This is the reference the rebuild is measured against, and it is measured
// rather than transcribed: a design-token document tells you what the CSS says,
// this tells you what the browser actually resolved. Those differ — Framer
// routes colour through per-container aliases, and the inline var() fallbacks
// beside every token are stale.
//
// Landmarks are found by TEXT, never by class name. Class names are generated
// and will not survive the rebuild; the words on the page will.
//
// Run through gstack browse:
//   $B eval tools/capture_styles.js --out .baseline/styles-<theme>.json --raw

const PROPS = [
  'font-family', 'font-size', 'font-weight', 'font-variation-settings',
  'line-height', 'letter-spacing', 'color', 'background-color',
  'text-decoration-line', 'text-decoration-style', 'text-decoration-color',
  'text-underline-offset', 'text-decoration-thickness',
  'border-top-width', 'border-top-color', 'border-radius',
  'margin-top', 'margin-bottom', 'padding-top', 'padding-bottom',
  'display', 'flex-direction', 'align-items', 'justify-content', 'gap',
];

// [label, how to find it]. Order is document order, top to bottom.
const LANDMARKS = [
  ['name', () => document.querySelector('h1')],
  ['jobTitle', () => [...document.querySelectorAll('h1,p,div')]
      .find(e => e.children.length === 0 && e.textContent.trim() === 'Senior Product Designer')],
  ['bio', () => [...document.querySelectorAll('p')]
      .find(e => e.textContent.startsWith('10+ years of experience'))],
  ['contactLink', () => [...document.querySelectorAll('a')]
      .find(e => e.textContent.includes('@gmail.com'))],
  ['sectionTitle', () => [...document.querySelectorAll('*')]
      .find(e => e.children.length === 0 && e.textContent.trim() === 'Selected Case Studies')],
  ['updatedLine', () => [...document.querySelectorAll('p,div')]
      .find(e => e.children.length === 0 && e.textContent.startsWith('Updated:'))],
  ['caseTitle', () => document.querySelector('[data-framer-name="project-title"] h3')],
  ['caseBody', () => [...document.querySelectorAll('p')]
      .find(e => e.textContent.startsWith('Revaal puts AI'))],
  ['caseBullet', () => document.querySelector('li')],
  ['metaLabel', () => [...document.querySelectorAll('p,div,span')]
      .find(e => e.children.length === 0 && e.textContent.trim() === 'Role')],
  ['metaValue', () => [...document.querySelectorAll('p,div,span')]
      .find(e => e.children.length === 0 && e.textContent.trim() === 'Founding Product Designer')],
  ['captionLink', () => [...document.querySelectorAll('a')]
      .find(e => e.textContent.includes('Read case study'))],
  ['carouselHint', () => [...document.querySelectorAll('p,div,span')]
      .find(e => e.children.length === 0 && /Click or Drag|Tap or Drag/.test(e.textContent))],
  ['caseImage', () => [...document.images]
      .find(i => /Shot\d/.test(i.currentSrc || i.src))],
  ['footer', () => [...document.querySelectorAll('p,div,span')]
      .find(e => e.children.length === 0 && e.textContent.includes('© Benyamin Najafi'))],
];

const out = {
  theme: getComputedStyle(document.querySelector('h1')).color,
  page: {
    background: getComputedStyle(document.body).backgroundColor,
    scrollHeight: document.body.scrollHeight,
    textLength: document.body.textContent.length,
  },
  landmarks: {},
  missing: [],
};

for (const [label, find] of LANDMARKS) {
  let el = null;
  try { el = find(); } catch { /* a landmark that moved is reported, not thrown */ }
  if (!el) { out.missing.push(label); continue; }
  const cs = getComputedStyle(el);
  const style = {};
  for (const p of PROPS) style[p] = cs.getPropertyValue(p);
  const r = el.getBoundingClientRect();
  style['_box'] = `${Math.round(r.width)}x${Math.round(r.height)}`;
  style['_text'] = el.textContent.trim().slice(0, 40);
  out.landmarks[label] = style;
}

JSON.stringify(out, null, 1);
