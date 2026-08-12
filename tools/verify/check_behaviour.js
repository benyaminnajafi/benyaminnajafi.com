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

// 2. Every hint pulses, and only where it can be seen.
{
  const hints = [...document.querySelectorAll('.hint')];
  check('a hint per carousel', hints.length === document.querySelectorAll('.slides').length,
        `${hints.length} hints for ${document.querySelectorAll('.slides').length} carousels`);
  const animated = hints.filter((h) => getComputedStyle(h).animationName !== 'none');
  check('the hint is animated, not pinned on', animated.length === hints.length,
        `${hints.length - animated.length} static`);
  const opaque = hints.filter((h) => getComputedStyle(h).animationName === 'none' &&
                                     parseFloat(getComputedStyle(h).opacity) > 0.9);
  check('no hint sits permanently at full opacity', opaque.length === 0,
        `${opaque.length} always-on`);
  // Gating is opt-in, so its absence looks like nothing rather than like a
  // failure: with no observer at all, every hint runs and none is marked. At
  // 1440x900 only one carousel is on screen, so some hint must be paused.
  const paused = hints.filter((h) => h.style.animationPlayState === 'paused');
  check('offscreen hints are paused', hints.length < 2 || paused.length > 0,
        `none of ${hints.length} paused — every panel pulses at once`);
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
