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

JSON.stringify({
  ran: checks.length,
  failures,
  ok: failures.length === 0,
}, null, 1);
