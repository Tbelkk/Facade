// Facade settings store (front end). Saved in this computer's browser storage.
//
// For the back end:
//   facadeSettings.get()          → current settings object (see DEFAULTS)
//   facadeSettings.onChange(fn)   → fn(settings) whenever something changes
window.facadeSettings = (function () {
  const KEY = 'facade.settings.v1';
  const DEFAULTS = Object.freeze({
    readOnly: true,          // explore and copy data only; never submit forms
    askBeforeActing: 'always', // 'always' | 'destructive' | 'never'
    pagesPerMinute: 20,      // speed limit for the Explorer
    clickPauseSec: 1,        // pause between clicks on the old site
    maxPages: 200,           // stop after this many pages
    maxRunMinutes: 30,       // stop after this long
  });
  const LIMITS = {
    pagesPerMinute: [1, 60, 1],
    clickPauseSec: [0, 5, 0.5],
    maxPages: [10, 5000, 10],
    maxRunMinutes: [1, 240, 1],
  };

  const listeners = new Set();
  let state = load();

  function clean(s) {
    const out = { ...DEFAULTS };
    if (typeof s.readOnly === 'boolean') out.readOnly = s.readOnly;
    if (['always', 'destructive', 'never'].includes(s.askBeforeActing)) out.askBeforeActing = s.askBeforeActing;
    for (const [k, [min, max, step]] of Object.entries(LIMITS)) {
      const n = Number(s[k]);
      if (Number.isFinite(n)) out[k] = Math.min(max, Math.max(min, Math.round(n / step) * step));
    }
    return out;
  }
  function load() {
    try { return clean(JSON.parse(localStorage.getItem(KEY)) || {}); } catch { return { ...DEFAULTS }; }
  }
  function save() {
    try { localStorage.setItem(KEY, JSON.stringify(state)); } catch {}
    listeners.forEach((fn) => fn({ ...state }));
  }

  return {
    DEFAULTS,
    LIMITS,
    get: () => ({ ...state }),
    set(patch) { state = clean({ ...state, ...patch }); save(); return { ...state }; },
    reset() { state = { ...DEFAULTS }; save(); return { ...state }; },
    onChange(fn) { listeners.add(fn); return () => listeners.delete(fn); },
  };
})();
