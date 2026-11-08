// RESTore dashboard controller: owns the six agent tiles and their canvas animation loop.
//
// Public API, so the back end can drive it:
//   dashboard.set(agentId, { status, progress, stat })
//      status   'idle' | 'working' | 'done' | 'live'
//      progress 0..1   (how far along the agent is)
//      stat     optional text for the tile footer (otherwise the animation's own numbers are shown)
//   dashboard.feed(agentId, payload)   real content for the animation (see agentKinds.js for each agent's payload)
//   dashboard.reset()
//   dashboard.summary() → { working, total }
//   dashboard.agents    → [{ id, name }]
// React components read tile state with dashboard.subscribe / dashboard.tile(id).

import { AGENTS, clamp, live, reduce, ring } from './agentKinds.js';

export function createDashboard() {
  const tiles = AGENTS.map((a) => {
    const tile = { ...a, canvas: null, ctx: null, w: 0, h: 0, status: 'idle', progress: 0, statText: null,
      t: Math.random() * 10, s: {}, pulses: [], statEl: null, lastStat: '', version: 0 };
    a.kind.init(tile);
    return tile;
  });
  const byId = (id) => tiles.find((t) => t.id === id);
  const listeners = new Set();
  const emit = () => listeners.forEach((fn) => fn());

  function size(tile) {
    if (!tile.canvas) return;
    const r = tile.canvas.getBoundingClientRect();
    if (!r.width || !r.height) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    tile.w = r.width; tile.h = r.height;
    tile.canvas.width = Math.round(r.width * dpr); tile.canvas.height = Math.round(r.height * dpr);
    tile.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    tile.kind.layout(tile);
  }

  function render(tile) {
    const c = tile.ctx;
    c.clearRect(0, 0, tile.w, tile.h);
    tile.kind.draw(tile, c);
    for (const p of tile.pulses) ring(c, p.x, p.y, p.r, 0.5 * p.life);
    const stat = tile.statText || tile.kind.stat(tile);
    if (stat !== tile.lastStat && tile.statEl) { tile.statEl.textContent = stat; tile.lastStat = stat; }
  }

  let raf = 0, last = 0, ro = null;
  function frame(now) {
    let dt = Math.min(0.05, (now - last) / 1000);
    last = now;
    if (reduce) dt *= 0.3;
    for (const tile of tiles) {
      if (!tile.w) continue;
      tile.t += dt;
      tile.kind.step(tile, dt);
      for (const p of tile.pulses) { p.r += dt * 40 * p.s; p.life -= dt * 1.6; }
      tile.pulses = tile.pulses.filter((p) => p.life > 0);
      render(tile);
    }
    raf = requestAnimationFrame(frame);
  }

  return {
    agents: AGENTS.map((a) => ({ id: a.id, name: a.name, desc: a.desc, about: a.about })),

    /** Called by each tile component once its canvas and stat element exist. */
    attach(id, canvas, statEl) {
      const tile = byId(id);
      if (!tile) return () => {};
      tile.canvas = canvas; tile.ctx = canvas.getContext('2d'); tile.statEl = statEl; tile.lastStat = '';
      if (!ro) ro = new ResizeObserver((entries) => entries.forEach((e) => { const t = tiles.find((x) => x.canvas === e.target); if (t) size(t); }));
      size(tile);
      ro.observe(canvas);
      return () => { ro && ro.unobserve(canvas); tile.canvas = null; tile.ctx = null; tile.statEl = null; tile.w = 0; };
    },
    start() { if (!raf) { last = performance.now(); raf = requestAnimationFrame(frame); } },
    stop() { cancelAnimationFrame(raf); raf = 0; },

    set(id, { status, progress, stat } = {}) {
      const tile = byId(id);
      if (!tile) return;
      let changed = false;
      if (status && status !== tile.status) { tile.status = status; changed = true; }
      if (typeof progress === 'number') {
        const p = clamp(progress);
        if (Math.round(p * 100) !== Math.round(tile.progress * 100)) changed = true;
        tile.progress = p;
      }
      if (stat !== undefined) tile.statText = stat;
      if (changed) { tile.version++; emit(); }
    },
    /** Adds real content to a tile's animation (a page visit, a field, records, endpoints, a check). */
    feed(id, payload) {
      const tile = byId(id);
      if (tile && tile.kind.feed) tile.kind.feed(tile, payload);
    },
    reset() {
      for (const tile of tiles) {
        tile.kind.reset(tile);
        tile.pulses = [];
        this.set(tile.id, { status: 'idle', progress: 0, stat: null });
      }
    },
    summary() {
      return { working: tiles.filter((t) => live(t)).length, total: tiles.length };
    },
    /** First tile with this status (used for the phase line). */
    find(status) { const t = tiles.find((x) => x.status === status); return t ? { id: t.id, name: t.name } : null; },

    subscribe(fn) { listeners.add(fn); return () => listeners.delete(fn); },
    tile(id) { const t = byId(id); return { status: t.status, progress: t.progress, version: t.version }; },
    version(id) { return byId(id).version; },
  };
}
