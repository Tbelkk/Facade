// Agent tile animations, carried over unchanged from app/renderer/dashboard.js.
// Each agent "kind" has init / layout / reset / step / draw / stat, drawn with white dots on a canvas.

export const reduce = typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const MONO = '"Geist Mono", ui-monospace, Menlo, monospace';

/* ---------------- helpers ---------------- */
function rng(seed) {
  return function () {
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const lerp = (a, b, t) => a + (b - a) * t;
const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
const ease = (t) => (t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2);
const fmt = (n) => Math.round(n).toLocaleString();
const live = (tile) => tile.status === 'working' || tile.status === 'live';

function dot(c, x, y, s, a) { c.fillStyle = `rgba(255,255,255,${a})`; c.fillRect(x - s / 2, y - s / 2, s, s); }
function ring(c, x, y, r, a, w = 1) { c.beginPath(); c.arc(x, y, r, 0, Math.PI * 2); c.strokeStyle = `rgba(255,255,255,${a})`; c.lineWidth = w; c.setLineDash([]); c.stroke(); }
function line(c, x1, y1, x2, y2, a, dash = []) { c.beginPath(); c.moveTo(x1, y1); c.lineTo(x2, y2); c.strokeStyle = `rgba(255,255,255,${a})`; c.lineWidth = 1; c.setLineDash(dash); c.stroke(); c.setLineDash([]); }
function text(c, s, x, y, a, align = 'left', size = 9) {
  c.font = `400 ${size}px ${MONO}`;
  if ('letterSpacing' in c) c.letterSpacing = '1px';
  c.textAlign = align; c.textBaseline = 'middle';
  c.fillStyle = `rgba(255,255,255,${a})`;
  c.fillText(s, x, y);
}
function bez(p0, p1, p2, p3, t) {
  const u = 1 - t;
  return { x: u * u * u * p0.x + 3 * u * u * t * p1.x + 3 * u * t * t * p2.x + t * t * t * p3.x,
           y: u * u * u * p0.y + 3 * u * u * t * p1.y + 3 * u * t * t * p2.y + t * t * t * p3.y };
}
// a bright square with a fading tail; pathAt(t) returns {x,y}
function comet(c, pathAt, t, size = 3.2, alpha = 1, tail = 5, step = 0.035) {
  for (let k = tail; k >= 0; k--) {
    const tt = t - k * step;
    if (tt < 0 || tt > 1) continue;
    const p = pathAt(tt), f = 1 - k / (tail + 1);
    dot(c, p.x, p.y, size * (0.45 + 0.55 * f), alpha * f);
  }
}
function pulse(tile, x, y, size = 1) { tile.pulses.push({ x, y, r: 3, life: 1, s: size }); if (tile.pulses.length > 30) tile.pulses.shift(); }

/* =========================================================
   01 EXPLORER: draws a map of the site as it clicks around
   ========================================================= */
const explorer = {
  N: 26,
  init(tile) {
    const r = rng(7), nodes = [{ p: -1, d: 0, kids: [] }], frontier = [0];
    while (nodes.length < this.N && frontier.length) {
      const i = frontier.shift(), d = nodes[i].d;
      const n = d === 0 ? 5 : d === 1 ? 2 + Math.floor(r() * 2) : Math.floor(r() * 3);
      for (let k = 0; k < n && nodes.length < this.N; k++) {
        nodes.push({ p: i, d: d + 1, kids: [] });
        nodes[i].kids.push(nodes.length - 1);
        if (d + 1 < 3) frontier.push(nodes.length - 1);
      }
    }
    // angular ranges: children split their parent's slice
    nodes[0].a0 = -Math.PI / 2; nodes[0].a1 = Math.PI * 1.5;
    nodes.forEach((n) => {
      const span = (n.a1 - n.a0) / Math.max(1, n.kids.length);
      n.kids.forEach((k, j) => { nodes[k].a0 = n.a0 + span * j; nodes[k].a1 = n.a0 + span * (j + 1); });
      n.a = (n.a0 + n.a1) / 2;
    });
    tile.s = { nodes, claimed: 0, found: 0, scouts: [], wanderers: [] };
  },
  layout(tile) {
    const { w, h } = tile, cx = w / 2, cy = h / 2;
    for (const n of tile.s.nodes) {
      const rad = n.d / 3;
      n.x = cx + Math.cos(n.a) * rad * (w / 2 - 22);
      n.y = cy + Math.sin(n.a) * rad * (h / 2 - 14);
    }
  },
  reset(tile) {
    const s = tile.s;
    s.nodes.forEach((n) => { n.on = false; });
    s.claimed = 0; s.found = 0; s.scouts = []; s.wanderers = [];
  },
  step(tile, dt) {
    const s = tile.s, nodes = s.nodes;
    const target = tile.status === 'idle' ? 0 : Math.max(1, Math.round(tile.progress * nodes.length));
    while (s.claimed < target) {
      const i = s.claimed++;
      if (i === 0) { nodes[0].on = true; s.found = 1; pulse(tile, nodes[0].x, nodes[0].y, 1.4); }
      else s.scouts.push({ from: nodes[i].p, to: i, t: 0, sp: 2 + Math.random() });
    }
    for (let k = s.scouts.length - 1; k >= 0; k--) {
      const sc = s.scouts[k];
      sc.t += dt * sc.sp;
      if (sc.t >= 1) { nodes[sc.to].on = true; s.found++; pulse(tile, nodes[sc.to].x, nodes[sc.to].y); s.scouts.splice(k, 1); }
    }
    // a couple of explorers keep walking the known map
    if (tile.status !== 'idle' && s.found > 2 && s.wanderers.length < 2) s.wanderers.push({ from: 0, to: nodes[0].kids.find((k) => nodes[k].on) ?? 0, t: Math.random() });
    for (const w of s.wanderers) {
      w.t += dt * (live(tile) ? 1.6 : 0.7);
      if (w.t >= 1) {
        const at = w.to, n = nodes[at];
        const options = [...n.kids.filter((k) => nodes[k].on), ...(n.p >= 0 ? [n.p] : [])];
        w.from = at; w.to = options.length ? options[Math.floor(Math.random() * options.length)] : at; w.t = 0;
      }
    }
  },
  draw(tile, c) {
    const { nodes, scouts, wanderers } = tile.s;
    for (const n of nodes) if (n.p >= 0 && n.on && nodes[n.p].on) line(c, nodes[n.p].x, nodes[n.p].y, n.x, n.y, 0.32, [1, 3]);
    for (const sc of scouts) {
      const a = nodes[sc.from], b = nodes[sc.to];
      line(c, a.x, a.y, lerp(a.x, b.x, sc.t), lerp(a.y, b.y, sc.t), 0.55);
    }
    for (const [i, n] of nodes.entries()) {
      if (!n.on) { dot(c, n.x, n.y, 2, 0.13); continue; }
      if (i === 0) { ring(c, n.x, n.y, 6, 0.8); dot(c, n.x, n.y, 3, 1); }
      else dot(c, n.x, n.y, 3.2, 0.9);
    }
    for (const w of wanderers) {
      const a = nodes[w.from], b = nodes[w.to];
      comet(c, (t) => ({ x: lerp(a.x, b.x, t), y: lerp(a.y, b.y, t) }), w.t, 2.6, 0.55, 3, 0.06);
    }
    for (const sc of scouts) {
      const a = nodes[sc.from], b = nodes[sc.to];
      comet(c, (t) => ({ x: lerp(a.x, b.x, t), y: lerp(a.y, b.y, t) }), sc.t, 3.6, 1, 5, 0.05);
    }
    if (tile.status === 'idle') ring(c, nodes[0].x, nodes[0].y, 6 + (tile.t % 2) * 6, 0.25 * (1 - (tile.t % 2) / 2));
  },
  stat(tile) { return tile.status === 'idle' ? 'Waiting for a link' : `Pages mapped ${tile.s.found} / ${tile.s.nodes.length}`; },
};

/* =========================================================
   02 ANALYST: scattered facts sort themselves into entities
   ========================================================= */
const analyst = {
  ENTITIES: [{ name: 'PATIENT', fields: 6 }, { name: 'APPOINTMENT', fields: 5 }, { name: 'INVOICE', fields: 4 }],
  RULES: ['no appointments on sundays', 'one patient → many appointments', 'invoice needs an appointment', 'phone number is required'],
  init(tile) {
    const r = rng(11), parts = [];
    this.ENTITIES.forEach((e, ei) => {
      for (let f = 0; f < e.fields; f++) for (let k = 0; k < 4; k++) parts.push({ e: ei, f, k, hx: r(), hy: r(), thr: r() * 0.82, ph: r() * 6.28, kv: 0 });
    });
    tile.s = { parts };
  },
  layout(tile) {
    const { w, h } = tile;
    this.cols = this.ENTITIES.map((_, i) => w * (0.18 + i * 0.32));
    this.top = 22;
    this.gap = Math.min(15, (h - 52) / 6);
    for (const p of tile.s.parts) {
      p.tx = this.cols[p.e] + (p.k - 1.5) * 8;
      p.ty = this.top + 16 + p.f * this.gap;
      p.x0 = 16 + p.hx * (w - 32);
      p.y0 = 16 + p.hy * (h - 40);
    }
  },
  reset(tile) { tile.s.parts.forEach((p) => { p.kv = 0; }); },
  step(tile, dt) {
    for (const p of tile.s.parts) {
      const want = tile.status === 'idle' ? 0 : clamp((tile.progress - p.thr) / 0.12);
      p.kv += (want - p.kv) * Math.min(1, dt * 3);
    }
  },
  draw(tile, c) {
    const { parts } = tile.s, t = tile.t;
    const formed = this.ENTITIES.map((_, ei) => { const ps = parts.filter((p) => p.e === ei); return ps.reduce((n, p) => n + p.kv, 0) / ps.length; });

    // relationships between entities, once understood
    const relA = clamp((tile.progress - 0.6) / 0.25) * (tile.status === 'idle' ? 0 : 1);
    if (relA > 0) {
      const y = this.top + 16 + this.gap * 2;
      for (let i = 0; i < 2; i++) {
        const x1 = this.cols[i] + 22, x2 = this.cols[i + 1] - 22;
        line(c, x1, y, x2, y, 0.35 * relA, [2, 4]);
        if (live(tile)) { const f = (t * 0.7 + i * 0.5) % 1; dot(c, lerp(x1, x2, f), y, 2.6, 0.8 * relA); }
      }
    }

    for (const p of parts) {
      const e = ease(p.kv);
      const x = lerp(p.x0 + Math.sin(t * 0.6 + p.ph) * 7, p.tx, e);
      const y = lerp(p.y0 + Math.cos(t * 0.5 + p.ph) * 5, p.ty, e);
      dot(c, x, y, p.kv > 0.95 ? 2.6 : 2, 0.22 + 0.68 * p.kv);
    }
    this.ENTITIES.forEach((en, i) => text(c, en.name, this.cols[i], this.top, 0.15 + 0.75 * formed[i], 'center'));

    if (tile.progress > 0.75 && tile.status !== 'idle') {
      const rule = this.RULES[Math.floor(t / 2.4) % this.RULES.length];
      text(c, `rule · ${rule}`, tile.w / 2, tile.h - 9, 0.5 * clamp((tile.progress - 0.75) / 0.1), 'center');
    }
  },
  stat(tile) {
    if (tile.status === 'idle') return 'Waiting for the map';
    const p = tile.progress;
    const entities = this.ENTITIES.filter((_, ei) => { const ps = tile.s.parts.filter((x) => x.e === ei); return ps.every((x) => x.kv > 0.9); }).length;
    const fields = Math.round(p * 15);
    const rules = p > 0.6 ? Math.min(4, Math.floor((p - 0.6) / 0.1) + 1) : 0;
    return `Entities ${entities} · Fields ${fields} · Rules ${rules}`;
  },
};

/* =========================================================
   03 EXTRACTOR: records stream from the old site into a DB grid
   ========================================================= */
const extractor = {
  TOTAL: 3410,
  init(tile) { const r = rng(5); tile.s = { lens: Array.from({ length: 9 }, () => 0.35 + r() * 0.65), packets: [], next: 0, acc: 0, cells: [], refill: 0 }; },
  layout(tile) {
    const { w, h } = tile, s = tile.s;
    s.left = { x0: 16, x1: w * 0.27, y0: 30, y1: h - 14 };
    const x0 = w * 0.5, x1 = w - 16, y0 = 30, y1 = h - 12;
    const cols = Math.max(6, Math.floor((x1 - x0) / 9)), rows = Math.max(4, Math.min(9, Math.floor((y1 - y0) / 9)));
    const old = s.cells;
    s.cells = [];
    for (let r = 0; r < rows; r++) for (let k = 0; k < cols; k++) s.cells.push({ x: x0 + k * 9 + 3, y: y0 + r * 9 + 3, on: 0, flash: 0 });
    if (old.length) { const filled = old.filter((c) => c.on).length; s.cells.forEach((c, i) => { c.on = i < filled ? 1 : 0; }); s.next = Math.min(filled, s.cells.length); }
    s.db = { x: x0, y: 14 };
  },
  reset(tile) { const s = tile.s; s.cells.forEach((c) => { c.on = 0; c.flash = 0; }); s.packets = []; s.next = 0; s.acc = 0; s.refill = 0; },
  step(tile, dt) {
    const s = tile.s, L = s.left;
    if (tile.status === 'done') { s.cells.forEach((c) => { c.on = 1; }); s.packets = []; return; }
    if (tile.status === 'working') {
      s.acc += dt * 18;
      while (s.acc >= 1) {
        s.acc--;
        if (s.next >= s.cells.length || s.packets.length > 40) break;
        const row = Math.floor(Math.random() * s.lens.length);
        const sy = lerp(L.y0, L.y1, row / (s.lens.length - 1));
        s.packets.push({ sx: L.x0 + Math.random() * (L.x1 - L.x0) * s.lens[row], sy, cell: s.next++, t: 0, sp: 1.3 + Math.random() * 0.6 });
      }
    }
    for (let i = s.packets.length - 1; i >= 0; i--) {
      const p = s.packets[i];
      p.t += dt * p.sp;
      if (p.t >= 1) { const c = s.cells[p.cell]; c.on = 1; c.flash = 1; s.packets.splice(i, 1); }
    }
    for (const c of s.cells) c.flash = Math.max(0, c.flash - dt * 3);
    // grid full → next batch
    if (tile.status === 'working' && s.next >= s.cells.length && !s.packets.length) {
      s.refill += dt;
      if (s.refill > 0.5) { s.cells.forEach((c) => { c.on = 0; }); s.next = 0; s.refill = 0; }
    }
  },
  path(p, c) {
    const mid = { x: (p.sx + c.x) / 2, y: Math.min(p.sy, c.y) - 26 };
    return (t) => bez({ x: p.sx, y: p.sy }, { x: lerp(p.sx, mid.x, 0.7), y: mid.y }, { x: lerp(c.x, mid.x, 0.7), y: mid.y }, { x: c.x, y: c.y }, t);
  },
  draw(tile, c) {
    const s = tile.s, L = s.left, active = tile.status !== 'idle';
    text(c, 'OLD SITE', L.x0, 14, 0.45);
    text(c, 'DATABASE', s.db.x, s.db.y, 0.45);
    s.lens.forEach((len, r) => {
      const y = lerp(L.y0, L.y1, r / (s.lens.length - 1));
      for (let x = L.x0; x < L.x0 + (L.x1 - L.x0) * len; x += 4) dot(c, x, y, 1.6, active ? 0.32 : 0.16);
    });
    for (const cell of s.cells) {
      if (cell.on) { dot(c, cell.x, cell.y, 3.6 + cell.flash * 2, 0.55 + 0.4 * cell.on + 0.05 * cell.flash); }
      else dot(c, cell.x, cell.y, 2, 0.1);
    }
    for (const p of s.packets) comet(c, this.path(p, s.cells[p.cell]), p.t, 3, 1, 4, 0.04);
  },
  stat(tile) { return tile.status === 'idle' ? 'Waiting for the schema' : `Records ${fmt(tile.progress * this.TOTAL)} / ${fmt(this.TOTAL)}`; },
};

/* =========================================================
   04 BUILDER: wires the database to API endpoints and MCP tools
   ========================================================= */
const builder = {
  EPS: [['GET', '/patients'], ['GET', '/patients/:id'], ['POST', '/appointments'], ['GET', '/appointments'], ['GET', '/invoices'],
        ['MCP', 'find_patient'], ['MCP', 'book_appointment'], ['MCP', 'send_reminder']],
  init(tile) { tile.s = { built: this.EPS.map(() => 0), traffic: [] }; },
  layout(tile) {
    const { w, h } = tile;
    this.hub = { x: w * 0.16, y: h / 2 };
    this.eps = this.EPS.map((e, i) => ({ x: w * 0.47, y: lerp(14, h - 12, i / (this.EPS.length - 1)) }));
  },
  reset(tile) { tile.s.built = this.EPS.map(() => 0); tile.s.traffic = []; },
  curve(i) {
    const a = this.hub, b = this.eps[i], mx = lerp(a.x, b.x, 0.5);
    return (t) => bez(a, { x: mx, y: a.y }, { x: mx, y: b.y }, b, t);
  },
  step(tile, dt) {
    const s = tile.s, target = tile.status === 'idle' ? 0 : tile.progress * this.EPS.length;
    s.built = s.built.map((b, i) => { const want = clamp(target - i); return b < want ? Math.min(want, b + dt * 1.6) : want; });
    if (tile.status !== 'idle') {
      s.built.forEach((b, i) => {
        if (b >= 1 && Math.random() < dt * (live(tile) ? 0.7 : 0.25)) s.traffic.push({ i, t: 0, dir: Math.random() < 0.5 ? 1 : -1, sp: 1 + Math.random() * 0.6 });
      });
    }
    for (let k = s.traffic.length - 1; k >= 0; k--) { const p = s.traffic[k]; p.t += dt * p.sp; if (p.t >= 1) s.traffic.splice(k, 1); }
  },
  draw(tile, c) {
    const s = tile.s, hub = this.hub;
    // database hub
    c.strokeStyle = 'rgba(255,255,255,.8)'; c.lineWidth = 1; c.setLineDash([]);
    c.strokeRect(hub.x - 11, hub.y - 13, 22, 26);
    for (let r = 0; r < 4; r++) for (let k = 0; k < 3; k++) dot(c, hub.x - 6 + k * 6, hub.y - 7 + r * 5, 1.8, tile.status === 'idle' ? 0.3 : 0.8);
    text(c, 'DB', hub.x, hub.y + 22, 0.45, 'center');

    this.EPS.forEach(([verb, p], i) => {
      const f = s.built[i], ep = this.eps[i], path = this.curve(i);
      if (f > 0) {
        c.beginPath();
        for (let k = 0; k <= 24; k++) { const q = path((k / 24) * f); k ? c.lineTo(q.x, q.y) : c.moveTo(q.x, q.y); }
        c.strokeStyle = `rgba(255,255,255,${f >= 1 ? 0.3 : 0.55})`; c.setLineDash([2, 3]); c.stroke(); c.setLineDash([]);
        if (f < 1) { const q = path(f); dot(c, q.x, q.y, 3.6, 1); }
      }
      const done = f >= 1;
      if (verb === 'MCP') {
        c.save(); c.translate(ep.x, ep.y); c.rotate(Math.PI / 4);
        c.strokeStyle = `rgba(255,255,255,${done ? 0.9 : 0.15})`; c.strokeRect(-2.5, -2.5, 5, 5);
        if (done) { c.fillStyle = '#fff'; c.fillRect(-1.2, -1.2, 2.4, 2.4); }
        c.restore();
      } else dot(c, ep.x, ep.y, done ? 3.4 : 2, done ? 0.9 : 0.15);
      text(c, verb, ep.x + 10, ep.y, done ? 0.4 : 0.15);
      text(c, p, ep.x + 42, ep.y, done ? 0.85 : 0.2);
    });
    for (const p of s.traffic) {
      const path = this.curve(p.i);
      comet(c, p.dir > 0 ? path : (t) => path(1 - t), p.t, 2.8, 0.9, 4, 0.05);
    }
  },
  stat(tile) {
    if (tile.status === 'idle') return 'Waiting for the data';
    const b = tile.s.built;
    return `API ${b.slice(0, 5).filter((x) => x >= 1).length} / 5 · MCP tools ${b.slice(5).filter((x) => x >= 1).length} / 3`;
  },
};

/* =========================================================
   05 WORKER: takes a request, fills the old site's form, reports back
   ========================================================= */
const worker = {
  TASKS: ['book appointment · jane doe · tue 10:00', 'find patient · "smith"', 'send reminder · 4 patients', 'update phone · ann lee', 'cancel appointment · #2041'],
  init(tile) { tile.s = { phase: 'wait', pt: 0, field: 0, fills: [0, 0, 0], cur: null, from: null, task: 0, done: 0 }; },
  layout(tile) {
    const { w, h } = tile;
    this.q = { x: w * 0.1, y: h / 2 - 8 };
    const x0 = w * 0.3, x1 = w - 16, y0 = 10, y1 = h - 26;
    this.win = { x0, x1, y0, y1 };
    this.fields = [0, 1, 2].map((i) => ({ x0: x0 + 56, x1: x1 - 14, y: y0 + 32 + i * ((y1 - y0 - 58) / 2.6) }));
    this.btn = { x: x1 - 40, y: y1 - 14, w: 28, h: 10 };
    if (!tile.s.cur) tile.s.cur = { x: (x0 + x1) / 2, y: (y0 + y1) / 2 };
  },
  reset(tile) { this.init(tile); this.layout(tile); },
  step(tile, dt) {
    const s = tile.s;
    if (!live(tile)) { s.phase = 'wait'; s.pt = 0; return; }
    s.pt += dt;
    const go = (phase) => { s.phase = phase; s.pt = 0; s.from = { ...s.cur }; };
    const at = (target, dur) => { const k = ease(clamp(s.pt / dur)); s.cur = { x: lerp(s.from.x, target.x, k), y: lerp(s.from.y, target.y, k) }; return s.pt >= dur; };
    const F = this.fields[s.field];
    switch (s.phase) {
      case 'wait': if (s.pt > 0.5) go('in'); break;
      case 'in': if (s.pt > 0.6) { s.field = 0; go('move'); } break;
      case 'move': if (at({ x: F.x0 + 4, y: F.y }, 0.35)) go('type'); break;
      case 'type':
        s.fills[s.field] = clamp(s.pt / 0.55);
        s.cur = { x: lerp(F.x0 + 4, F.x1 - 4, s.fills[s.field] * 0.85), y: F.y };
        if (s.pt >= 0.55) { if (s.field < 2) { s.field++; go('move'); } else go('toBtn'); }
        break;
      case 'toBtn': if (at({ x: this.btn.x + this.btn.w / 2, y: this.btn.y + this.btn.h / 2 }, 0.35)) { pulse(tile, this.btn.x + this.btn.w / 2, this.btn.y + this.btn.h / 2, 1.2); go('click'); } break;
      case 'click': if (s.pt > 0.3) go('out'); break;
      case 'out':
        if (s.pt > 0.6) { s.done++; pulse(tile, this.q.x, this.q.y, 1.3); s.fills = [0, 0, 0]; s.task = (s.task + 1) % this.TASKS.length; go('wait'); }
        break;
    }
  },
  draw(tile, c) {
    const s = tile.s, W = this.win, active = live(tile);
    // request queue
    text(c, 'REQUESTS', this.q.x, 14, 0.4, 'center');
    for (let i = 0; i < 5; i++) dot(c, this.q.x, this.q.y - 18 + i * 9, 2.4, active ? (i < 3 ? 0.75 : 0.25) : 0.15);
    // the old website window
    c.strokeStyle = `rgba(255,255,255,${active ? 0.4 : 0.2})`; c.lineWidth = 1; c.setLineDash([2, 3]);
    c.strokeRect(W.x0, W.y0, W.x1 - W.x0, W.y1 - W.y0); c.setLineDash([]);
    line(c, W.x0, W.y0 + 12, W.x1, W.y0 + 12, active ? 0.3 : 0.15);
    for (let i = 0; i < 3; i++) dot(c, W.x0 + 8 + i * 6, W.y0 + 6, 2, 0.4);
    text(c, 'old-clinic-2005', W.x0 + 30, W.y0 + 6.5, 0.3, 'left', 8);
    this.fields.forEach((f, i) => {
      for (let x = W.x0 + 12; x < W.x0 + 44; x += 4) dot(c, x, f.y, 1.4, 0.3);
      c.strokeStyle = 'rgba(255,255,255,.22)'; c.strokeRect(f.x0, f.y - 6, f.x1 - f.x0, 12);
      const fill = s.fills[i];
      for (let x = f.x0 + 5; x < f.x0 + 5 + (f.x1 - f.x0 - 10) * fill; x += 4) dot(c, x, f.y, 2, 0.85);
    });
    c.strokeStyle = `rgba(255,255,255,${s.phase === 'click' ? 0.9 : 0.35})`; c.strokeRect(this.btn.x, this.btn.y, this.btn.w, this.btn.h);
    if (s.phase === 'click') { c.fillStyle = 'rgba(255,255,255,.25)'; c.fillRect(this.btn.x, this.btn.y, this.btn.w, this.btn.h); }

    // request in / result out
    const qa = { x: this.q.x + 8, y: this.q.y }, wa = { x: W.x0, y: W.y0 + 20 };
    if (s.phase === 'in') comet(c, (t) => ({ x: lerp(qa.x, wa.x, t), y: lerp(qa.y, wa.y, t) - Math.sin(t * Math.PI) * 14 }), clamp(s.pt / 0.6), 3.2, 1, 4, 0.06);
    if (s.phase === 'out') comet(c, (t) => ({ x: lerp(wa.x, qa.x, t), y: lerp(wa.y + 30, qa.y, t) + Math.sin(t * Math.PI) * 14 }), clamp(s.pt / 0.6), 3.2, 1, 4, 0.06);

    // cursor
    if (active || Math.floor(tile.t * 2) % 2) { dot(c, s.cur.x, s.cur.y, 4, active ? 1 : 0.4); if (active) ring(c, s.cur.x, s.cur.y, 6, 0.3); }
    if (active) text(c, this.TASKS[s.task], W.x0, tile.h - 10, 0.55, 'left', 8.5);
  },
  stat(tile) {
    if (tile.status === 'idle') return 'Waiting for the API';
    return `Tasks done ${tile.s.done}${tile.status === 'live' ? ' · listening' : ''}`;
  },
};

/* =========================================================
   06 VERIFIER: sweeps every record, re-checks anything that doesn't match
   ========================================================= */
const verifier = {
  init(tile) { tile.s = { scan: 0, cells: [], checks: 0, retries: 0, hold: 0 }; },
  layout(tile) {
    const { w, h } = tile, s = tile.s;
    const cols = Math.max(8, Math.floor((w - 32) / 10)), rows = Math.max(4, Math.min(9, Math.floor((h - 26) / 11)));
    s.cells = [];
    for (let r = 0; r < rows; r++) for (let k = 0; k < cols; k++) s.cells.push({ x: 16 + k * 10 + 4, y: 14 + r * 11 + 4, st: 0, timer: 0 });
    s.x0 = 12; s.x1 = 16 + cols * 10;
  },
  reset(tile) { const s = tile.s; s.scan = 0; s.checks = 0; s.retries = 0; s.hold = 0; s.cells.forEach((c) => { c.st = 0; c.timer = 0; }); },
  step(tile, dt) {
    const s = tile.s;
    for (const c of s.cells) if (c.st === 2) { c.timer -= dt; if (c.timer <= 0) { c.st = 1; s.retries++; s.checks++; pulse(tile, c.x, c.y, 0.8); } }
    if (!live(tile)) return;
    if (s.hold > 0) { s.hold -= dt; if (s.hold <= 0) { s.cells.forEach((c) => { if (c.st === 1) c.st = 0; }); s.scan = 0; } return; }
    s.scan += dt * (tile.status === 'live' ? 0.22 : 0.32);
    const x = lerp(s.x0, s.x1, s.scan);
    for (const c of s.cells) {
      if (c.st || c.x > x) continue;
      if (Math.random() < 0.006) { c.st = 2; c.timer = 0.9; }
      else { c.st = 1; s.checks++; }
    }
    if (s.scan >= 1) { s.scan = 1; s.hold = 0.6; }
  },
  draw(tile, c) {
    const s = tile.s, active = live(tile);
    const x = lerp(s.x0, s.x1, s.scan);
    if (active && s.hold <= 0) {
      const g = c.createLinearGradient(x - 40, 0, x, 0);
      g.addColorStop(0, 'rgba(255,255,255,0)'); g.addColorStop(1, 'rgba(255,255,255,.07)');
      c.fillStyle = g; c.fillRect(x - 40, 6, 40, tile.h - 12);
      line(c, x, 6, x, tile.h - 6, 0.6);
    }
    for (const cell of s.cells) {
      if (cell.st === 2) {
        const a = Math.floor(tile.t * 6) % 2 ? 1 : 0.35;
        c.strokeStyle = `rgba(255,255,255,${a})`; c.lineWidth = 1; c.strokeRect(cell.x - 3.5, cell.y - 3.5, 7, 7);
      } else dot(c, cell.x, cell.y, cell.st ? 2.8 : 2, cell.st ? (s.hold > 0 ? 1 : 0.8) : active ? 0.18 : 0.1);
    }
  },
  stat(tile) {
    if (tile.status === 'idle') return 'Waiting for records';
    return `Checks ${fmt(tile.s.checks)} · ${tile.s.retries} retried${tile.status === 'live' ? ' · watching' : ''}`;
  },
};

/* ---------------- tiles ---------------- */
const AGENTS = [
  { id: 'explorer', name: 'Explorer', desc: 'Clicks through the site and maps every page', kind: explorer },
  { id: 'analyst', name: 'Analyst', desc: 'Works out what’s stored and the rules', kind: analyst },
  { id: 'extractor', name: 'Extractor', desc: 'Copies every record into the database', kind: extractor },
  { id: 'builder', name: 'Builder', desc: 'Builds the API and MCP plug', kind: builder },
  { id: 'worker', name: 'Worker', desc: 'Does real tasks on the old site', kind: worker },
  { id: 'verifier', name: 'Verifier', desc: 'Double-checks every action worked', kind: verifier },
];
const LABEL = { idle: 'Idle', working: 'Working', done: 'Done', live: 'Live' };

export { AGENTS, LABEL, ring, clamp, live };
