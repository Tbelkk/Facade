// Facade settings store (front end). Saved in this computer's browser storage.
//
// For the back end:
//   facadeSettings.get()          → current settings object (see DEFAULTS)
//   facadeSettings.onChange(fn)   → fn(settings) whenever something changes
export const facadeSettings = (function () {
  const KEY = 'facade.settings.v2';
  // Each Explorer setting maps to a flag of `python -m facade.run` (see FLAGS in SettingsDrawer.jsx).
  const DEFAULTS = Object.freeze({
    pauseSec: 1,             // --pause    seconds between page loads (speed limit for old servers)
    maxPages: 200,           // --pages    stop after this many pages
    maxRunMinutes: 30,       // --minutes  stop after this long
    login: false,            // --login    log in by hand in the browser first
    full: false,             // --full     page through every list to the end
    headed: false,           // --headed   show the browser window
    live: true,              // (--no-live when off) stream progress to SpacetimeDB
    readOnly: true,          // explore and copy data only; never submit forms
    askBeforeActing: 'always', // 'always' | 'destructive' | 'never'
  });
  const LIMITS = {
    pauseSec: [0, 10, 0.5],
    maxPages: [10, 5000, 10],
    maxRunMinutes: [1, 240, 1],
  };
  const FLAGS = ['login', 'full', 'headed', 'live', 'readOnly'];

  const listeners = new Set();
  let state = load();

  function clean(s) {
    const out = { ...DEFAULTS };
    for (const k of FLAGS) if (typeof s[k] === 'boolean') out[k] = s[k];
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
