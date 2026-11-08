// Facade landing page: scroll drives a "Nemotron rerender" from 1998 → 2026.
(function () {
  const root = document.documentElement;
  const stage = document.getElementById('stage');
  const oldLayer = document.getElementById('oldLayer');
  const newLayer = document.getElementById('newLayer');
  const hint = document.getElementById('hint');

  const W = 1100, H = 700;
  const START = 0.08, SPAN = 0.78; // hold the 1998 page briefly, finish before the stage ends

  const clamp = (v) => Math.min(1, Math.max(0, v));

  function scale() {
    const vw = root.clientWidth, vh = window.innerHeight;
    const s = Math.min((vw - 24) / W, (vh - 140) / H);
    root.style.setProperty('--s', Math.max(0.25, s).toFixed(4));
  }

  function scrollRange() {
    const top = stage.offsetTop;
    const total = stage.offsetHeight - window.innerHeight;
    return { top, total };
  }

  function render() {
    const { top, total } = scrollRange();
    const raw = total > 0 ? clamp((window.scrollY - top) / total) : 0;
    const p = clamp((raw - START) / SPAN);
    root.style.setProperty('--p', p.toFixed(4));
    hint.classList.toggle('gone', p > 0.05);
    hint.tabIndex = p > 0.05 ? -1 : 0;

    const modern = p >= 0.5;
    newLayer.setAttribute('aria-hidden', String(!modern));
    oldLayer.setAttribute('aria-hidden', String(modern));
  }

  // Jump to the fully modern version
  function goTo(p) {
    const { top, total } = scrollRange();
    window.scrollTo({ top: top + total * (p ? START + SPAN : 0), behavior: 'smooth' });
  }
  hint.addEventListener('click', () => goTo(1));

  // Any link on the 1998 page sends you to the modern version
  oldLayer.addEventListener('click', (e) => {
    if (e.target.closest('a')) {
      e.preventDefault();
      goTo(1);
    }
  });

  let ticking = false;
  window.addEventListener('scroll', () => {
    if (!ticking) {
      ticking = true;
      requestAnimationFrame(() => { ticking = false; render(); });
    }
  }, { passive: true });
  window.addEventListener('resize', () => { scale(); render(); });

  scale();
  render();
})();
