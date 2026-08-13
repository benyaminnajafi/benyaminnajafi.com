// Behavioural checks — the things a computed-style dump structurally cannot see.
//
// Every defect this file tests for shipped to production at least once, and
// every one of them passed compare_styles.py on the way out:
//
//   · "Click or Drag" was rendered, but clicking did nothing. The only way to
//     reach slides two and up was to guess the strip could be dragged.
//   · Moving the case rule from border-top to border-bottom silently deleted
//     the line under "Selected Case Studies", because that line used to come
//     from the first card's top border.
//   · The carousel hint animated on all seven panels from page load, so every
//     panel on the page lit up at once.
//
// A style dump misses all three: the first is behaviour, the second is a line
// whose absence is invisible unless you know it should be there, and the third
// only shows up in time.
//
// Run through gstack browse against a served build:
//   $B goto http://localhost:4321/
//   $B eval tools/verify/check_behaviour.js --raw

const failures = [];
const checks = [];

const check = (name, ok, detail) => {
  checks.push(name);
  if (!ok) failures.push(`${name}${detail ? ` — ${detail}` : ''}`);
};

// 1. Clicking a carousel advances it by one slide.
//
// The scroll is animated, so its result is not readable in this tick. Watching
// the scrollTo call instead asserts what the handler intended, which is the
// part that regressed — there was no handler at all.
{
  const track = document.querySelector('.track');
  if (!track) {
    check('carousel present', false);
  } else {
    const step = track.clientWidth;
    const calls = [];
    const real = track.scrollTo;
    track.scrollTo = (opts) => { calls.push(opts); };

    const r = track.getBoundingClientRect();
    const x = r.left + r.width / 2;
    const y = r.top + r.height / 2;
    for (const type of ['pointerdown', 'pointerup']) {
      track.dispatchEvent(new PointerEvent(type, {
        bubbles: true, clientX: x, clientY: y,
        pointerType: 'mouse', button: 0, isPrimary: true,
      }));
    }
    track.scrollTo = real;

    check('click advances the carousel',
          calls.length === 1 && Math.abs((calls[0] && calls[0].left) - step) <= 8,
          calls.length === 0
            ? 'clicking the strip did nothing'
            : `scrolled to ${calls[0].left}, expected ${step}`);
  }
}

// 2. No label printed over the artwork. Removed by request, so its return
//    would be a regression rather than a restoration.
{
  const label = [...document.querySelectorAll('.slides *')]
    .find((e) => /Click or Drag|Tap or Drag/i.test(e.textContent || ''));
  check('no hint text over the slides', !label);
}

// 3. Items reveal as they come into view, and nothing is left hidden.
{
  const reveal = [...document.querySelectorAll('.reveal')];
  check('case studies are revealable', reveal.length > 0);

  if (reveal.length) {
    const ready = document.documentElement.hasAttribute('data-reveal-ready');
    const still = matchMedia('(prefers-reduced-motion: reduce)').matches;
    check('reveal is armed by script, not by CSS', ready || still,
          'the hidden state would strand the page with no JavaScript');

    // Whatever is on screen right now must already be released, or the top of
    // the page would sit blank waiting for a scroll that never comes.
    const onscreen = reveal.filter((el) => {
      const r = el.getBoundingClientRect();
      return r.top < innerHeight && r.bottom > 0;
    });
    const stuck = onscreen.filter((el) =>
      !el.classList.contains('is-visible') && parseFloat(getComputedStyle(el).opacity) < 0.5);
    check('nothing on screen is left hidden', stuck.length === 0,
          `${stuck.length} of ${onscreen.length} still invisible`);
  }
}

// 4. In-page links ease rather than jump.
{
  const html = getComputedStyle(document.documentElement);
  const still = matchMedia('(prefers-reduced-motion: reduce)').matches;
  check('in-page links scroll smoothly',
        still ? html.scrollBehavior === 'auto' : html.scrollBehavior === 'smooth',
        `scroll-behavior: ${html.scrollBehavior}`);
  // A dragged carousel must track the pointer exactly, so the strip itself
  // must not inherit the smooth behaviour.
  const track = document.querySelector('.track');
  if (track) {
    check('the carousel strip still scrolls instantly under a drag',
          getComputedStyle(track).scrollBehavior === 'auto',
          `scroll-behavior: ${getComputedStyle(track).scrollBehavior}`);
  }
}

// 3. The horizontal rules are actually painted.
{
  const head = document.querySelector('.section-head');
  check('rule under the section head',
        head && getComputedStyle(head).borderBottomWidth === '1px');
  const cases = [...document.querySelectorAll('.case')];
  const ruled = cases.filter((c) => getComputedStyle(c).borderBottomWidth === '1px');
  check('rule under every case study', ruled.length === cases.length,
        `${ruled.length}/${cases.length}`);
}

// 4. Nothing reintroduces a scroll hijacker.
{
  check('no smooth-scroll library on the page',
        !('lenis' in window) && !document.documentElement.classList.contains('lenis'));
}

// 5. The theme switch cross-fades its icon rather than snapping.
//
// The first build swapped display, so the change happened between frames. The
// original animates the outgoing icon to scale(0.5) rotate(120deg) at opacity
// 0 — a rotation and a fade, not an instant replacement.
{
  const button = document.querySelector('.theme-toggle');
  const sun = button && button.querySelector('.sun');
  const moon = button && button.querySelector('.moon');
  check('theme switch present', !!(button && sun && moon));

  if (sun && moon) {
    const both = [sun, moon].map((i) => getComputedStyle(i));
    check('both icons stay in the box',
          both.every((s) => s.display !== 'none'),
          'one is display: none, so the change cannot animate');
    check('the icon change is animated',
          both.every((s) => parseFloat(s.transitionDuration) > 0),
          `transition ${both.map((s) => s.transitionDuration).join(' / ')}`);
    // Exactly one is showing, and the other is rotated out of the way.
    const shown = both.filter((s) => parseFloat(s.opacity) > 0.5);
    check('exactly one icon is visible', shown.length === 1,
          `${shown.length} visible`);
    const hidden = both.find((s) => parseFloat(s.opacity) <= 0.5);
    check('the hidden icon is scaled and rotated away',
          !!hidden && hidden.transform !== 'none',
          `transform ${hidden && hidden.transform}`);

    // The glyphs are the original's, not redrawn. A hand-drawn sun with
    // rounded stroke rays reads as a different mark next to this one.
    const sunPath = sun.querySelector('path');
    check('the sun is the original glyph',
          !!sunPath && (sunPath.getAttribute('d') || '').startsWith('M 4.995 10'),
          'the icon has been redrawn');
    const moonPath = moon.querySelector('path');
    check('the moon is the original glyph',
          !!moonPath && (moonPath.getAttribute('d') || '').startsWith('M 8.006 16'),
          'the icon has been redrawn');

    // The lag guard. Softening the swap by transitioning every element made
    // the page set up and tear down a transition per node; ordinary content
    // must carry no long transition of its own.
    const inert = [...document.querySelectorAll('.case img, .t-body, .meta-row, .slides')];
    const dragging = inert.filter((e) => parseFloat(getComputedStyle(e).transitionDuration) > 0.25);
    check('no blanket transition on ordinary elements', dragging.length === 0,
          `${dragging.length} of ${inert.length} carry one`);

    // The swap is synchronous on purpose: anything that defers it, including a
    // view transition's snapshot frame, reads as hesitation on the click.
    const before = document.documentElement.dataset.theme;
    button.click();
    check('the switch flips the theme',
          document.documentElement.dataset.theme !== before,
          `still ${document.documentElement.dataset.theme}`);
    check('the choice is remembered',
          localStorage.getItem('theme') === document.documentElement.dataset.theme);
    button.click(); // put it back
  }
}

// 6. The custom cursor: mounted, blended, out of the way, and switching state.
//
// This assumes a fine pointer. On touch the element removes itself and the
// page keeps its ordinary cursor, which is the point of the ready flag.
{
  const cursor = document.querySelector('[data-cursor]');
  const fine = matchMedia('(hover: hover) and (pointer: fine)').matches;

  if (!fine) {
    check('cursor absent on a coarse pointer', !cursor);
    check('the real cursor is left alone on a coarse pointer',
          !document.documentElement.hasAttribute('data-cursor-ready'));
  } else {
    check('cursor mounted', !!cursor);
    check('page gives up its cursor only once the script ran',
          document.documentElement.hasAttribute('data-cursor-ready'));

    if (cursor) {
      const cs = getComputedStyle(cursor);
      check('cursor inverts against its backdrop',
            cs.mixBlendMode === 'exclusion' && cs.filter === 'invert(1)',
            `blend ${cs.mixBlendMode}, filter ${cs.filter}`);
      // Without this the dot would eat every click on the page.
      check('cursor does not intercept the pointer', cs.pointerEvents === 'none');

      const move = (target) => target.dispatchEvent(new PointerEvent('pointermove', {
        bubbles: true, clientX: 300, clientY: 300, pointerType: 'mouse',
      }));

      const link = document.querySelector('a');
      const track = document.querySelector('.track');
      const dotSize = () => Math.round(
        parseFloat(getComputedStyle(cursor.querySelector('.dot')).width));

      if (link) {
        move(link);
        check('cursor grows over a link', cursor.dataset.state === 'hover',
              `state ${cursor.dataset.state}`);
      }
      if (track) {
        move(track);
        check('cursor switches to drag over a carousel',
              cursor.dataset.state === 'drag', `state ${cursor.dataset.state}`);
      }
      move(document.body);
      check('cursor returns to its default state',
            cursor.dataset.state === 'default', `state ${cursor.dataset.state}`);
      // Sizes are transitioned, so read the declared value rather than a
      // mid-flight one: the default dot is 12px.
      check('default dot is 12px', dotSize() > 0 && dotSize() <= 32, `${dotSize()}px`);
    }
  }
}

JSON.stringify({
  ran: checks.length,
  failures,
  ok: failures.length === 0,
}, null, 1);
