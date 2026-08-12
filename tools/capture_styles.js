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
  // Motion. Their absence is why a rebuild with no entrance animations at all,
  // and a carousel hint pinned on at full opacity in the wrong corner, both
  // passed a "no differences" run.
  'animation-name', 'animation-duration', 'animation-delay',
  'transition-property', 'transition-duration',
];

// Opacity and blend are read through the ancestor chain, not off the element.
// The original hangs both on wrappers — the carousel hint's own <p> reports
// opacity 1 and mix-blend-mode normal while an ancestor holds it at 0 with
// exclusion blending — so comparing the leaf's own values compares two
// different elements and says nothing about what a reader sees.
const effective = (el) => {
  let opacity = 1;
  let blend = 'normal';
  for (let n = el; n && n !== document.documentElement; n = n.parentElement) {
    const s = getComputedStyle(n);
    opacity *= parseFloat(s.opacity);
    if (s.mixBlendMode && s.mixBlendMode !== 'normal') blend = s.mixBlendMode;
  }
  return { opacity: Number(opacity.toFixed(3)), blend };
};

// Containers carry no text, so the text-based finders above cannot reach them.
// Every spacing regression the first rebuild shipped lived in a container:
// the hero band collapsed from 489px to 284px, the case study rows grew 40px
// each, and the carousel lost its 4:3 lock — none of it visible to a harness
// that only ever measured leaf text nodes.
const BOX_PROPS = [
  'display', 'flex-direction', 'align-items', 'justify-content', 'gap',
  'padding-top', 'padding-bottom', 'padding-left', 'padding-right',
  'margin-top', 'margin-bottom',
  'min-height', 'aspect-ratio', 'position', 'overflow-x',
  'border-top-width', 'border-bottom-width', 'border-radius',
  'background-color',
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
  ['updatedLine', () => leaves().find(e => e.textContent.startsWith('Updated:'))],
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

// Containers are found by their relationship to the landmarks that do have
// text — the lowest element containing both — which holds on either build
// without naming a single generated class.
const chain = (el) => {
  const out = [];
  for (let p = el; p && p !== document.documentElement; p = p.parentElement) out.push(p);
  return out;
};
const commonAncestor = (a, b) => {
  if (!a || !b) return null;
  const up = new Set(chain(a));
  return chain(b).find((p) => up.has(p)) ?? null;
};
const byText = (t) => leaves().find((e) => e.textContent.trim() === t);
const startsWith = (t) => leaves().find((e) => e.textContent.trim().startsWith(t));

const wideImage = [...document.images].find((i) => i.getBoundingClientRect().width > 500);
const caseTitleEl = [...document.querySelectorAll('h3')]
  .find((e) => e.textContent.startsWith('From Source to Publish'));

const CONTAINERS = [
  // The hero band. Its height is the single number that most defines whether
  // the page opens with room to breathe or starts flush against the edge.
  ['heroBand', () => commonAncestor(document.querySelector('h1'), document.images[0])],
  ['sectionHead', () => commonAncestor(byText('Selected Case Studies'), startsWith('Updated:'))],
  ['caseRow', () => commonAncestor(caseTitleEl, wideImage)],
  ['detailsCol', () => commonAncestor(caseTitleEl, byText('Role'))],
  // The coloured block behind the slides: the nearest ancestor of the wide
  // image that actually paints a background.
  ['slideFrame', () => chain(wideImage).find((p) => {
    const bg = getComputedStyle(p).backgroundColor;
    return bg && bg !== 'rgba(0, 0, 0, 0)' && bg !== 'transparent';
  })],
  ['footerBar', () => commonAncestor(byText('Back to Top'), startsWith('© Benyamin Najafi'))],
];

// Settle every animation before measuring. An animated element reports
// whatever phase it happens to be in when the capture runs, so the carousel
// hint reads 0.6 on one run and 0 on the next. Finite animations are jumped to
// their end — the entrance cascade has finished by the time a reader looks —
// and looping ones are pinned to the start of their cycle, which is the state
// both builds rest in.
for (const a of document.getAnimations()) {
  try {
    const iterations = a.effect && a.effect.getTiming ? a.effect.getTiming().iterations : 1;
    if (iterations === Infinity) {
      a.currentTime = 0;
      a.pause();
    } else {
      a.finish();
    }
  } catch { /* an animation that refuses to settle is measured as it is */ }
}

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
  // Without this a capture taken at 1280 could be compared against a 1440
  // reference and the box sizes would disagree for a reason that has nothing
  // to do with the build. There was a theme guard but never a width guard.
  viewport: `${window.innerWidth}x${window.innerHeight}`,
  page: {
    background: getComputedStyle(document.body).backgroundColor,
    scrollHeight: document.body.scrollHeight,
    textLength: document.body.textContent.length,
  },
  landmarks: {},
  containers: {},
  // Every case row, not just the first. Six of the seven were never measured,
  // which is how three of them came to be 40px too tall.
  caseRows: [],
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
  const eff = effective(el);
  style['_opacity'] = String(eff.opacity);
  style['_blend'] = eff.blend;
  style['_text'] = el.textContent.trim().slice(0, 40);
  out.landmarks[label] = style;
}

for (const [label, find] of CONTAINERS) {
  let el = null;
  try { el = find(); } catch { /* a container that moved is reported, not thrown */ }
  if (!el) { out.missing.push(`container:${label}`); continue; }
  const cs = getComputedStyle(el);
  const style = {};
  for (const p of BOX_PROPS) style[p] = cs.getPropertyValue(p);
  const r = el.getBoundingClientRect();
  style['_box'] = `${Math.round(r.width)}x${Math.round(r.height)}`;
  out.containers[label] = style;
}

// A case row is the lowest ancestor of a case title that also holds the wide
// slide image. Walking up from each h3 finds all seven on either build without
// depending on how the rows happen to be wrapped — Framer gives each card its
// own container element, the rebuild does not.
{
  const rows = [];
  for (const h3 of document.querySelectorAll('h3')) {
    const row = chain(h3).find((p) => {
      const img = p.querySelector('img');
      return img && img.getBoundingClientRect().width > 500;
    });
    if (row && !rows.includes(row)) rows.push(row);
  }
  for (const row of rows) {
    const r = row.getBoundingClientRect();
    out.caseRows.push(`${Math.round(r.width)}x${Math.round(r.height)}`);
  }
}

JSON.stringify(out, null, 1);
