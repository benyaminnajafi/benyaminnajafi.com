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

// querySelectorAll('*') also returns <style>, <script>, <title> and friends.
// They have no children and their text content is real text, so a finder
// looking for a leaf by its words will happily match the CSS that *mentions*
// the words rather than the element that renders them.
const RENDERED = (el) =>
  !['STYLE', 'SCRIPT', 'TITLE', 'META', 'LINK', 'HEAD', 'HTML'].includes(el.tagName);

const leaves = () =>
  [...document.querySelectorAll('*')].filter((e) => e.children.length === 0 && RENDERED(e));

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
  ['sectionTitle', () => leaves()
      .find(e => e.textContent.trim() === 'Selected Case Studies')],
  ['updatedLine', () => [...document.querySelectorAll('p,div')]
      .find(e => e.children.length === 0 && e.textContent.startsWith('Updated:'))],
  ['caseTitle', () => [...document.querySelectorAll('h3')]
      .find(e => e.textContent.startsWith('From Source to Publish'))],
  ['caseBody', () => [...document.querySelectorAll('p')]
      .find(e => e.textContent.startsWith('Revaal puts AI'))],
  ['caseBullet', () => [...document.querySelectorAll('li')]
      .find(e => e.textContent.includes('Designed for the constraint'))],
  ['metaLabel', () => leaves()
      .find(e => e.textContent.trim() === 'Role')],
  ['metaValue', () => leaves()
      .find(e => e.textContent.trim() === 'Founding Product Designer')],
  ['captionLink', () => [...document.querySelectorAll('a')]
      .find(e => e.textContent.includes('Read case study'))],
  ['carouselHint', () => leaves()
      .find(e => /Click or Drag|Tap or Drag/.test(e.textContent))],
  // Filenames are content-hashed on both sides and carry no meaning. The first
  // wide image below the hero is the first case study's slide on either build.
  ['caseImage', () => [...document.images]
      .find(i => i.getBoundingClientRect().width > 500)],
  ['footer', () => leaves()
      .find(e => e.textContent.includes('© Benyamin Najafi'))],
];

// Which theme actually rendered, decided by the one probe that works at every
// width. Asserting on body's background silently passes when the theme never
// applied — it is transparent at most widths — which is how a baseline once
// captured light twice and called half of it dark.
const H1 = getComputedStyle(document.querySelector('h1')).color;
const RESOLVED = H1 === 'rgb(240, 240, 240)' ? 'dark'
               : H1 === 'rgb(18, 18, 18)' ? 'light'
               : 'unknown';

const out = {
  theme: RESOLVED,
  themeProbe: H1,
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
