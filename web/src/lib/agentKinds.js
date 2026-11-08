// Agent tiles: one per real stage of the RESTore pipeline. Every word drawn here comes from the run itself
// (page paths, Nemotron's summaries, extracted rows, endpoint paths, checker messages, database counts).
//   dashboard.feed(agentId, payload)              real content for that tile
//   dashboard.set(agentId, { status, progress, stat })
// Idle tiles draw nothing. Each kind has init / layout / reset / step / draw / stat and an optional feed.

export const reduce = typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const MONO = '"Geist Mono", ui-monospace, Menlo, monospace';

/* ---------------- helpers ---------------- */
const lerp = (a, b, t) => a + (b - a) * t;
const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
const ease = (t) => (t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2);
const fmt = (n) => Math.round(n).toLocaleString('en-US');
const live = (tile) => tile.status === 'working' || tile.status === 'live';
const active = (tile) => tile.status !== 'idle';

function dot(c, x, y, s, a) { c.fillStyle = `rgba(255,255,255,${a})`; c.fillRect(x - s / 2, y - s / 2, s, s); }
function ring(c, x, y, r, a, w = 1) { c.beginPath(); c.arc(x, y, r, 0, Math.PI * 2); c.strokeStyle = `rgba(255,255,255,${a})`; c.lineWidth = w; c.setLineDash([]); c.stroke(); }
function line(c, x1, y1, x2, y2, a, dash = []) { c.beginPath(); c.moveTo(x1, y1); c.lineTo(x2, y2); c.strokeStyle = `rgba(255,255,255,${a})`; c.lineWidth = 1; c.setLineDash(dash); c.stroke(); c.setLineDash([]); }
function font(c, size) { c.font = `400 ${size}px ${MONO}`; if ('letterSpacing' in c) c.letterSpacing = '0.3px'; }
function text(c, s, x, y, a, align = 'left', size = 9, maxW = 0) {
  font(c, size);
  c.textAlign = align; c.textBaseline = 'middle';
  c.fillStyle = `rgba(255,255,255,${a})`;
  let str = s == null ? '' : String(s);
  if (maxW > 0 && c.measureText(str).width > maxW) {
    while (str.length > 1 && c.measureText(str + '…').width > maxW) str = str.slice(0, -1);
    str += '…';
  }
  c.fillText(str, x, y);
}
function box(c, x, y, w, h, a, dash = []) { c.strokeStyle = `rgba(255,255,255,${a})`; c.lineWidth = 1; c.setLineDash(dash); c.strokeRect(x + 0.5, y + 0.5, w, h); c.setLineDash([]); }
function fillBox(c, x, y, w, h, a) { c.fillStyle = `rgba(255,255,255,${a})`; c.fillRect(x, y, w, h); }
function bez(p0, p1, p2, p3, t) {
  const u = 1 - t;
  return { x: u * u * u * p0.x + 3 * u * u * t * p1.x + 3 * u * t * t * p2.x + t * t * t * p3.x,
           y: u * u * u * p0.y + 3 * u * u * t * p1.y + 3 * u * t * t * p2.y + t * t * t * p3.y };
}
function curve(a, b) { const mx = lerp(a.x, b.x, 0.5); return (t) => bez(a, { x: mx, y: a.y }, { x: mx, y: b.y }, b, t); }
function strokePath(c, path, upTo, a, dash = [1, 3]) {
  c.beginPath(); for (let k = 0; k <= 24; k++) { const q = path((k / 24) * upTo); k ? c.lineTo(q.x, q.y) : c.moveTo(q.x, q.y); }
  c.strokeStyle = `rgba(255,255,255,${a})`; c.lineWidth = 1; c.setLineDash(dash); c.stroke(); c.setLineDash([]);
}
function comet(c, pathAt, t, size = 3.2, alpha = 1, tail = 5, step = 0.035) {
  for (let k = tail; k >= 0; k--) {
    const tt = t - k * step;
    if (tt < 0 || tt > 1) continue;
    const p = pathAt(tt), f = 1 - k / (tail + 1);
    dot(c, p.x, p.y, size * (0.45 + 0.55 * f), alpha * f);
  }
}
function pulse(tile, x, y, size = 1) { tile.pulses.push({ x, y, r: 3, life: 1, s: size }); if (tile.pulses.length > 30) tile.pulses.shift(); }
const hurry = (n) => (n > 20 ? 0.06 : n > 8 ? 0.18 : n > 3 ? 0.45 : 1);
const cell = (v) => (v == null || v === '' ? '—' : typeof v === 'number' ? fmt(v) : v);
const plural = (w) => (/s$/.test(w) ? w : /y$/.test(w) ? w.slice(0, -1) + 'ies' : w + 's');
// plain-language name for a page type: "List of posts", "One post", "Post form"
function human(v) {
  const e = (v.entity || 'item').toLowerCase();
  if (v.pageType === 'list') return `List of ${plural(e)}`;
  if (v.pageType === 'detail') return `One ${e}`;
  if (v.pageType === 'form') return `${e[0].toUpperCase() + e.slice(1)} form`;
  return 'Other page';
}

/* =========================================================
   01 EXPLORER: explore.agent reads the site page by page.
   left:  the page it is on now: its path, Nemotron's one-line summary, and the real rows it pulled from it
   right: the site map of page types found so far, with visit counts
   feed({ key, path, purpose, pageType, ai, seconds, records, rows: [[...]], columns })
   ========================================================= */
const explorer = {
  MAX: 7,
  init(tile) { tile.s = { nodes: [], queue: [], cur: null, shown: null, trips: [], pages: 0, records: 0 }; },
  layout() {},
  reset(tile) { this.init(tile); },
  feed(tile, v) { if (v.opening) tile.s.opening = v.opening; else tile.s.queue.push(v); },
  geo(tile) {
    const card = { x: 10, y: 6, w: Math.min(tile.w * 0.56, 330), h: tile.h - 12 };
    const root = { x: card.x + card.w + 22, y: tile.h / 2 };
    return { card, root, colX: Math.max(root.x + 96, card.x + card.w + (tile.w - card.w) * 0.5) };
  },
  nodePos(tile, i) {
    const g = this.geo(tile), kids = Math.min(this.MAX, Math.max(1, tile.s.nodes.length - 1));
    if (i === 0) return g.root;
    const k = Math.min(i, this.MAX) - 1;
    return { x: g.colX, y: kids === 1 ? tile.h / 2 : lerp(14, tile.h - 16, k / (kids - 1)) };
  },
  step(tile, dt) {
    const s = tile.s;
    if (!s.cur && s.queue.length) {
      const v = s.queue.shift();
      const base = v.ai ? 2.2 : 0.35;
      s.cur = { ...v, t: 0, dur: base * hurry(s.queue.length) };
      s.shown = s.cur;
    }
    if (s.cur) {
      s.cur.t += dt;
      if (s.cur.t >= s.cur.dur) {
        const v = s.cur;
        let i = s.nodes.findIndex((n) => n.key === v.key);
        if (i < 0) { s.nodes.push({ key: v.key, name: human(v), count: 0, ai: false, type: v.pageType }); i = s.nodes.length - 1; }
        s.nodes[i].count++; s.nodes[i].ai = s.nodes[i].ai || v.ai;
        s.pages++; s.records += v.records || 0;
        const g = this.geo(tile);
        s.trips.push({ from: { x: g.card.x + g.card.w, y: g.card.y + 20 }, to: this.nodePos(tile, i), t: 0 });
        s.cur = null;
      }
    }
    for (const tr of s.trips) tr.t += dt * 2.4;
    for (const tr of s.trips.filter((x) => x.t >= 1)) pulse(tile, tr.to.x, tr.to.y, 0.9);
    s.trips = s.trips.filter((x) => x.t < 1);
  },
  draw(tile, c) {
    if (!active(tile)) return;
    const s = tile.s, g = this.geo(tile), C = g.card, v = s.cur || s.shown;
    box(c, C.x, C.y, C.w, C.h, 0.3);
    if (!v && s.opening) {
      text(c, s.opening, C.x + 7, C.y + 8.5, 0.95, 'left', 9, C.w - 120);
      text(c, 'NEMOTRON READING…', C.x + C.w - 7, C.y + 8.5, 0.85, 'right', 8);
      const y = C.y + 20 + ((tile.t * 0.6) % 1) * (C.h - 24);
      line(c, C.x + 1, y, C.x + C.w, y, 0.5);
      text(c, 'opening the first page and working out what it is', C.x + 7, C.y + 26, 0.5, 'left', 8.5, C.w - 14);
    }
    if (v) {
      const k = s.cur ? clamp(s.cur.t / s.cur.dur) : 1;
      // header: path + how it was read
      fillBox(c, C.x + 1, C.y + 1, C.w - 1, 15, 0.05);
      font(c, 9);
      const nm = human(v), nmW = c.measureText(nm).width;
      text(c, nm, C.x + 7, C.y + 8.5, 0.95, 'left', 9, C.w - 120);
      text(c, v.path, C.x + 14 + nmW, C.y + 8.5, 0.4, 'left', 8, Math.max(0, C.w - 134 - nmW));
      const how = v.ai ? `NEMOTRON READ${v.seconds ? ' · ' + v.seconds.toFixed(1) + 's' : ''}` : 'REUSED MAPPING ⚡';
      text(c, how, C.x + C.w - 7, C.y + 8.5, v.ai ? 0.85 : 0.5, 'right', 8);
      // Nemotron's summary of the page, typed out while it reads
      const sum = v.purpose || (v.pageType ? `${v.pageType} page` : '');
      const typed = v.ai && s.cur ? sum.slice(0, Math.ceil(sum.length * Math.min(1, k * 1.6))) : sum;
      text(c, typed ? `“${typed}${typed.length < sum.length ? '' : '”'}` : '', C.x + 7, C.y + 26, 0.6, 'left', 8.5, C.w - 14);
      line(c, C.x, C.y + 35, C.x + C.w, C.y + 35, 0.15);
      // the real rows pulled from this page
      const rows = v.rows || [], rowH = 13, max = Math.max(0, Math.floor((C.h - 58) / rowH));
      const visible = Math.min(rows.length, max, Math.ceil(rows.length * Math.min(1, k * 1.4 + (s.cur ? 0 : 1))));
      if (rows.length) {
        const cols = (v.columns || []).length || rows[0].length, wFirst = C.w * 0.62, wRest = (C.w - wFirst - 14) / Math.max(1, cols - 1);
        for (let r = 0; r < visible; r++) {
          const y = C.y + 46 + r * rowH, fresh = s.cur && r === visible - 1;
          if (fresh) fillBox(c, C.x + 1, y - 6, C.w - 1, 12, 0.07);
          rows[r].forEach((val, ci) => {
            const x = ci === 0 ? C.x + 7 : C.x + 7 + wFirst + (ci - 1) * wRest;
            text(c, cell(val), x, y, ci === 0 ? 0.85 : 0.55, 'left', 8.5, (ci === 0 ? wFirst : wRest) - 8);
          });
        }
        const more = (v.records || rows.length) - visible;
        text(c, more > 0 ? `+${fmt(more)} more rows from this page` : `${fmt(v.records || rows.length)} rows from this page`, C.x + 7, C.y + C.h - 9, 0.45, 'left', 8);
      } else {
        text(c, v.pageType === 'detail' ? 'detail page: learned its layout (no new rows)' : v.pageType === 'form' ? 'form: read the fields, never submitted' : 'no new rows on this page', C.x + 7, C.y + 48, 0.45, 'left', 8.5, C.w - 14);
      }
      if (s.cur && v.ai) { const y = lerp(C.y + 38, C.y + C.h - 4, k); line(c, C.x + 1, y, C.x + C.w, y, 0.5); }
    }
    // site map of page types
    const n = s.nodes;
    // when several page types share a plain name ("List of posts"), add which section it is ("newest")
    const dup = {}; for (const x of n) dup[x.name] = (dup[x.name] || 0) + 1;
    const nameOf = (x) => (dup[x.name] > 1 && x.key !== '/' ? `${x.name} · ${x.key.replace(/^\//, '').split('/')[0]}` : x.name);
    if (n.length) {
      const root = this.nodePos(tile, 0);
      for (let i = 1; i < Math.min(n.length, this.MAX + 1); i++) {
        const p = this.nodePos(tile, i);
        strokePath(c, curve(root, p), 1, 0.22);
        if (n[i].ai) ring(c, p.x, p.y, 4.5, 0.7); else dot(c, p.x, p.y, 3, 0.85);
        if (i === this.MAX && n.length > this.MAX + 1) { text(c, `+${n.length - this.MAX} more page types`, p.x + 9, p.y, 0.6, 'left', 8.5); continue; }
        text(c, `${nameOf(n[i])} ×${n[i].count}`, p.x + 9, p.y - 5, 0.85, 'left', 8.5, tile.w - p.x - 12);
        text(c, n[i].key, p.x + 9, p.y + 6, 0.38, 'left', 8, tile.w - p.x - 12);
      }
      ring(c, root.x, root.y, 6, 0.8); dot(c, root.x, root.y, 3, 1);
      text(c, `${nameOf(n[0])} ×${n[0].count}`, root.x - 4, root.y + 16, 0.8, 'left', 8.5, g.colX - root.x - 10);
      text(c, `start · ${n[0].key}`, root.x - 4, root.y + 27, 0.38, 'left', 8, g.colX - root.x - 10);
    }
    for (const tr of s.trips) comet(c, curve(tr.from, tr.to), tr.t, 3, 1, 5, 0.04);
  },
  stat(tile) {
    if (!active(tile)) return 'Waiting for a link';
    const s = tile.s;
    return `Pages ${s.pages} · page types ${s.nodes.length} · rows ${fmt(s.records)}`;
  },
};

/* =========================================================
   02 OPERATOR: operator_agent designs the API from the extracted data.
   reads the data model → Nemotron drafts endpoints → checker → fix → live, with real example calls
   feed({ phase: 'reading'|'drafting'|'proposed'|'fixed'|'done', model: { name, fields, rows },
          endpoints: [{ method, path, name, summary, example, total, first }], problems: [...] })
   ========================================================= */
// Many endpoints (3 per entity) don't fit a tile: show one row per resource ("/courses  list · by id · search").
const baseOf = (path) => '/' + String(path || '').split('/').filter(Boolean)[0];
const kindOf = (path, base) => (path === base ? 'list' : /\{/.test(path) ? 'by id' : path.endsWith('/search') ? 'search' : path.slice(base.length + 1));
function groupByBase(list, pathOf) {
  const out = [], by = {};
  for (const x of list) {
    const b = baseOf(pathOf(x));
    if (!by[b]) { by[b] = { base: b, items: [] }; out.push(by[b]); }
    by[b].items.push(x);
  }
  return out;
}
// how many rows fit, keeping the last one for "+N more" when needed
function fitRows(n, top, bot, rowH) {
  const max = Math.max(1, Math.floor((bot - top) / rowH) + 1);
  return n <= max ? n : max - 1;
}

const operator = {
  init(tile) { tile.s = { phase: '', model: null, eps: [], problems: [], traffic: [], think: 0, fixedAt: 0 }; },
  layout() {},
  reset(tile) { this.init(tile); },
  feed(tile, d) {
    const s = tile.s;
    if (d.phase) s.phase = d.phase;
    if (d.model) s.model = d.model;
    if (d.endpoints) for (const e of d.endpoints) {
      const have = s.eps.find((x) => x.method === e.method && x.path === e.path);
      if (have) Object.assign(have, e); else s.eps.push({ ...e, t: 0 });
    }
    if (d.problems) s.problems = d.problems;
    if (d.phase === 'fixed') { s.problems = []; s.fixedAt = 1; }
  },
  step(tile, dt) {
    const s = tile.s;
    s.think += dt;
    s.fixedAt = Math.max(0, s.fixedAt - dt * 0.5);
    let ready = true;
    for (const e of s.eps) { if (ready) e.t = Math.min(1, e.t + dt * 3); ready = e.t >= 1; }
    if (s.phase === 'done' && s.rowCount && s.traffic.length < 4 && Math.random() < dt * 1.2) s.traffic.push({ i: Math.floor(Math.random() * s.rowCount), t: 0, dir: 1 });
    for (const p of s.traffic) { p.t += dt * 1.2; if (p.t >= 1 && p.dir === 1) { p.dir = -1; p.t = 0; } }
    s.traffic = s.traffic.filter((x) => x.t < 1);
  },
  draw(tile, c) {
    if (!active(tile)) return;
    const s = tile.s, m = s.model;
    // input: the data model it designs from
    const M = { x: 10, y: 6, w: Math.min(150, tile.w * 0.3), h: tile.h - 30 };
    box(c, M.x, M.y, M.w, M.h, 0.3);
    text(c, m ? m.name.toUpperCase() : 'DATA', M.x + 7, M.y + 9, 0.95, 'left', 9);
    if (m) text(c, `${fmt(m.rows || 0)} rows`, M.x + M.w - 7, M.y + 9, 0.5, 'right', 8);
    line(c, M.x, M.y + 17, M.x + M.w, M.y + 17, 0.15);
    const fields = (m && m.fields) || [];
    const maxF = Math.floor((M.h - 24) / 12);
    fields.slice(0, maxF).forEach((f, i) => {
      text(c, f.name, M.x + 7, M.y + 26 + i * 12, 0.75, 'left', 8.5, M.w * 0.6);
      text(c, f.type, M.x + M.w - 7, M.y + 26 + i * 12, 0.4, 'right', 8);
    });
    if (fields.length > maxF) text(c, `+${fields.length - maxF}`, M.x + 7, M.y + M.h - 6, 0.4, 'left', 8);
    const src = { x: M.x + M.w, y: M.y + M.h / 2 };
    const colX = M.x + M.w + 40, bottom = tile.h - 10;

    if (!s.eps.length) {
      for (let i = 0; i < 12; i++) {
        const a = s.think * (1.1 + (i % 3) * 0.35) + i * 0.52, r = 16 + (i % 4) * 8;
        dot(c, colX + 70 + Math.cos(a) * r, src.y + Math.sin(a) * r * 0.6, 2.2, 0.3 + 0.55 * ((i % 3) / 2));
      }
      text(c, s.phase === 'drafting' ? 'Nemotron is drafting endpoints from this model…' : 'reading the data model…', colX, bottom, 0.6, 'left', 8.5, tile.w - colX - 10);
      return;
    }
    const groups = groupByBase(s.eps, (e) => e.path);
    const top = 14, bot = tile.h - 34, shown = fitRows(groups.length, top, bot, 26);
    const rows = groups.length > shown ? shown + 1 : shown;
    const rowY = (i) => (rows === 1 ? (top + bot) / 2 : top + i * ((bot - top) / (rows - 1)));
    const bad = new Set(s.problems.map((p) => String(p).split(':')[0].trim()));
    s.rowCount = shown;
    groups.slice(0, shown).forEach((g, i) => {
      const t = Math.max(...g.items.map((e) => e.t));
      const p = { x: colX, y: rowY(i) }, path = curve(src, p);
      strokePath(c, path, t, 0.3, [2, 3]);
      if (t < 1) { const q = path(t); dot(c, q.x, q.y, 3.4, 1); return; }
      const isBad = g.items.some((e) => bad.has(e.name));
      if (isBad) { const b = Math.floor(tile.t * 4) % 2 ? 1 : 0.4; line(c, p.x - 3, p.y - 3, p.x + 3, p.y + 3, b); line(c, p.x - 3, p.y + 3, p.x + 3, p.y - 3, b); }
      else dot(c, p.x, p.y, 3.2, 0.95);
      const ready = g.items.filter((e) => e.t >= 1);
      text(c, ready[0].method, p.x + 9, p.y - 5, 0.5, 'left', 8);
      text(c, g.base + '   ' + ready.map((e) => kindOf(e.path, g.base)).join(' · '), p.x + 42, p.y - 5, isBad ? 0.5 : 0.95, 'left', 9, tile.w - p.x - 50);
      const main = g.items.find((e) => e.path === g.base) || g.items[0];
      text(c, main.summary || main.name, p.x + 42, p.y + 6, 0.42, 'left', 8, tile.w - p.x - 50);
    });
    if (groups.length > shown) {
      const rest = groups.slice(shown), p = { x: colX, y: rowY(shown) };
      dot(c, p.x, p.y, 2.2, 0.4);
      text(c, `+${rest.length} more: ${rest.map((g) => g.base).join(', ')}`, p.x + 42, p.y, 0.5, 'left', 8.5, tile.w - p.x - 50);
    }
    for (const t of s.traffic) {
      const i = Math.min(t.i, Math.max(0, shown - 1)), p = { x: colX, y: rowY(i) }, path = curve(src, p);
      comet(c, t.dir === 1 ? (x) => path(1 - x) : path, t.t, 2.8, 0.9, 4, 0.05);
    }
    let msg, a = 0.55;
    if (s.problems.length) { msg = `✕ checker: ${s.problems[0]}`; a = 0.85; }
    else if (s.fixedAt > 0) { msg = '↻ Nemotron fixed it · checker: 0 problems'; a = 0.85; }
    else if (s.phase === 'done') {
      const e = s.eps[Math.floor(tile.t / 2.6) % s.eps.length];
      msg = e.example ? `${e.method} ${e.example}${e.total != null ? ` → ${fmt(e.total)} rows` : ''}${e.first ? `  “${e.first}”` : ''}` : `${e.method} ${e.path}`;
    } else msg = 'checking the design against the real data…';
    text(c, msg, colX, bottom, a, 'left', 8.5, tile.w - colX - 10);
  },
  stat(tile) {
    if (!active(tile)) return 'Waiting for the extracted data';
    const s = tile.s, n = s.eps.filter((e) => e.t >= 1).length;
    return n ? `API ${n} · MCP tools ${n}${s.phase === 'done' ? ' · ready' : ''}` : 'Designing…';
  },
};

/* =========================================================
   03 DATABASE: store.load_run puts everything into SpacetimeDB.
   one bar per table, filling with the real row counts
   feed({ target, tables: [{ name, done, total, note }] })
   ========================================================= */
const database = {
  init(tile) { tile.s = { target: '', tables: [], drops: [] }; },
  layout() {},
  reset(tile) { this.init(tile); },
  feed(tile, d) {
    const s = tile.s;
    if (d.target) s.target = d.target;
    for (const t of d.tables || []) {
      const have = s.tables.find((x) => x.name === t.name);
      if (have) { if (t.done > have.done) for (let k = 0; k < Math.min(6, t.done - have.done); k++) s.drops.push({ table: t.name, t: -k * 0.06 }); Object.assign(have, t); }
      else s.tables.push({ ...t, shown: 0 });
    }
  },
  step(tile, dt) {
    const s = tile.s;
    for (const t of s.tables) t.shown += (t.done - t.shown) * Math.min(1, dt * 4);
    for (const d of s.drops) d.t += dt * 2;
    s.drops = s.drops.filter((d) => d.t < 1);
  },
  draw(tile, c) {
    if (!active(tile)) return;
    const s = tile.s;
    text(c, s.target || 'SpacetimeDB', 10, 10, 0.55, 'left', 8.5, tile.w - 20);
    const top = 28, rowH = Math.min(30, (tile.h - top - 8) / Math.max(1, s.tables.length));
    const barX = 120, barW = tile.w - barX - 110;
    s.tables.forEach((t, i) => {
      const y = top + i * rowH + 8;
      text(c, t.name, 10, y, 0.9, 'left', 9);
      if (t.note) text(c, t.note, 10, y + 11, 0.4, 'left', 8, barX - 16);
      box(c, barX, y - 4, barW, 8, 0.25);
      const f = t.total ? clamp(t.shown / t.total) : 0;
      for (let x = barX + 3; x < barX + 3 + (barW - 6) * f; x += 4) dot(c, x, y, 2, 0.85);
      text(c, `${fmt(t.shown)}${t.total ? ' / ' + fmt(t.total) : ''}`, tile.w - 10, y, 0.75, 'right', 8.5);
      for (const d of s.drops.filter((x) => x.table === t.name && x.t > 0)) dot(c, barX + (barW - 6) * f, lerp(y - 18, y, d.t), 2.4, 1 - d.t * 0.5);
    });
  },
  stat(tile) {
    if (!active(tile)) return 'Waiting for the API design';
    const rec = tile.s.tables.find((t) => t.name === 'record');
    return rec ? `record rows ${fmt(rec.done)}${rec.total ? ' / ' + fmt(rec.total) : ''}` : 'Connecting…';
  },
};

/* =========================================================
   04 SERVER: serve.run turns the design into a running REST API + MCP server and self-tests both.
   left: the data it serves · middle: the server · right: every route and MCP tool, each tested with a real request
   feed({ phase: 'loading', source, records }) · feed({ phase: 'built', routes: [[m, p]], tools: [name] })
   feed({ test: { kind: 'route' | 'tool', key, ok, total, label } }) · feed({ phase: 'live', api, mcp, passed, tested })
   ========================================================= */
const server = {
  init(tile) { tile.s = { phase: '', source: '', records: 0, items: [], queue: [], cur: null, api: '', mcp: '', passed: 0, tested: 0, traffic: [] }; },
  layout() {},
  reset(tile) { this.init(tile); },
  feed(tile, d) {
    const s = tile.s;
    if (d.phase) s.phase = d.phase;
    if (d.source) s.source = d.source;
    if (d.records != null) s.records = d.records;
    if (d.routes) for (const [m, p] of d.routes) if (!s.items.find((x) => x.key === `${m} ${p}`)) s.items.push({ kind: 'route', key: `${m} ${p}`, m, label: p, t: 0, state: '' });
    if (d.tools) for (const n of d.tools) if (!s.items.find((x) => x.key === n)) s.items.push({ kind: 'tool', key: n, m: 'MCP', label: n, t: 0, state: '' });
    if (d.test) s.queue.push(d.test);
    if (d.api) {
      s.api = d.api; s.mcp = d.mcp; s.passed = d.passed; s.tested = d.tested;
      // going live: finish any test the animation hasn't shown yet, so the tiles never disagree with the result
      for (const q of [s.cur, ...s.queue].filter(Boolean)) {
        const it = s.items.find((x) => x.key === q.key);
        if (it) { it.t = 1; it.state = q.ok === false ? 'bad' : 'ok'; it.total = q.total; }
      }
      s.cur = null; s.queue = [];
    }
  },
  geo(tile) {
    const db = { x: 30, y: tile.h / 2 - 8 };
    const srv = { x: Math.max(110, tile.w * 0.24), y: tile.h / 2 - 8, w: 74, h: 54 };
    return { db, srv, colX: srv.x + srv.w + 50 };
  },
  // rows: one per resource (its routes together), then one row for all MCP tools, then "+N more" if needed
  rows(tile) {
    const s = tile.s, top = 12, bot = tile.h - 28;
    const groups = groupByBase(s.items.filter((x) => x.kind === 'route'), (x) => x.label)
      .map((g) => ({ kind: 'route', label: g.base, items: g.items }));
    const tools = s.items.filter((x) => x.kind === 'tool');
    const room = fitRows(groups.length + (tools.length ? 1 : 0), top, bot, 20) - (tools.length ? 1 : 0);
    const shown = groups.slice(0, Math.max(1, room));
    const out = [...shown];
    if (groups.length > shown.length) out.push({ kind: 'more', label: `+${groups.length - shown.length} more`, items: groups.slice(shown.length).flatMap((g) => g.items) });
    if (tools.length) out.push({ kind: 'tool', label: 'MCP', items: tools });
    return out;
  },
  rowOf(tile, key) { return Math.max(0, this.rows(tile).findIndex((r) => r.items.some((x) => x.key === key))); },
  pos(tile, i) {
    const n = Math.max(1, this.rows(tile).length), top = 12, bot = tile.h - 28;
    return { x: this.geo(tile).colX, y: n === 1 ? (top + bot) / 2 : lerp(top, bot, i / (n - 1)) };
  },
  step(tile, dt) {
    const s = tile.s;
    let ready = true;
    for (const it of s.items) { if (ready) it.t = Math.min(1, it.t + dt * 4); ready = it.t >= 1; }
    const built = (key) => { const it = s.items.find((x) => x.key === key); return !it || it.t >= 1; };
    if (!s.cur && s.queue.length && built(s.queue[0].key)) {
      const q = s.queue.shift();
      s.cur = { ...q, t: 0, dur: 1.1 * hurry(s.queue.length) };
    }
    if (s.cur) {
      s.cur.t += dt / s.cur.dur;
      if (s.cur.t >= 1) {
        const it = s.items.find((x) => x.key === s.cur.key);
        if (it) { it.state = s.cur.ok === false ? 'bad' : 'ok'; it.total = s.cur.total; const p = this.pos(tile, this.rowOf(tile, it.key)); pulse(tile, p.x, p.y, 0.9); }
        s.cur = null;
      }
    }
    if (s.phase === 'live' && s.items.length && s.traffic.length < 4 && Math.random() < dt * 1.1) s.traffic.push({ i: Math.floor(Math.random() * this.rows(tile).length), t: 0 });
    for (const p of s.traffic) p.t += dt * 0.9;
    s.traffic = s.traffic.filter((p) => p.t < 1);
  },
  draw(tile, c) {
    if (!active(tile)) return;
    const s = tile.s, g = this.geo(tile), db = g.db, S = g.srv;
    // data source
    box(c, db.x - 12, db.y - 14, 24, 28, 0.8);
    for (let r = 0; r < 4; r++) for (let k = 0; k < 3; k++) dot(c, db.x - 6 + k * 6, db.y - 8 + r * 5.5, 1.8, 0.8);
    text(c, /spacetime/i.test(s.source) ? 'SPACETIMEDB' : 'DATA', db.x, db.y + 24, 0.5, 'center', 8);
    text(c, s.records ? `${fmt(s.records)} rows` : '', db.x, db.y + 35, 0.4, 'center', 8);
    line(c, db.x + 13, db.y, S.x, db.y, 0.3, [2, 3]);
    // the server
    box(c, S.x, S.y - S.h / 2, S.w, S.h, s.phase === 'live' ? 0.9 : 0.5);
    text(c, 'SERVER', S.x + S.w / 2, S.y - S.h / 2 + 10, 0.85, 'center', 8.5);
    text(c, 'REST API', S.x + S.w / 2, S.y - 2, 0.55, 'center', 8);
    text(c, 'MCP', S.x + S.w / 2, S.y + 10, 0.55, 'center', 8);
    if (!s.items.length) { text(c, s.phase === 'loading' ? 'loading the API design + records…' : 'starting…', g.colX, tile.h / 2, 0.55, 'left', 8.5); }
    const from = { x: S.x + S.w, y: S.y };
    this.rows(tile).forEach((row, i) => {
      const p = this.pos(tile, i), path = curve(from, p), its = row.items;
      const t = Math.max(...its.map((x) => x.t));
      strokePath(c, path, t, 0.3, [2, 3]);
      if (t < 1) { const q = path(t); dot(c, q.x, q.y, 3.2, 1); return; }
      const ok = its.filter((x) => x.state === 'ok').length, bad = its.some((x) => x.state === 'bad');
      const state = bad ? 'bad' : ok === its.length ? 'ok' : '';
      if (row.kind === 'tool') { c.save(); c.translate(p.x, p.y); c.rotate(Math.PI / 4); box(c, -3, -3, 6, 6, state ? 0.95 : 0.35); if (state === 'ok') fillBox(c, -1.5, -1.5, 3, 3, 1); c.restore(); }
      else dot(c, p.x, p.y, state ? 3.4 : 2.4, state ? 0.95 : 0.35);
      let label = row.label;
      if (row.kind === 'route') label = `${row.label}   ${its.map((x) => kindOf(x.label, row.label)).join(' · ')}`;
      if (row.kind === 'tool') label = `${its.length} tools for AI assistants`;
      text(c, row.kind === 'tool' ? 'MCP' : row.kind === 'more' ? '' : 'GET', p.x + 9, p.y, 0.45, 'left', 8);
      text(c, label, p.x + 40, p.y, state ? 0.95 : 0.5, 'left', 8.5, tile.w - p.x - 140);
      const list = its.find((x) => x.label === row.label && x.total != null);
      const res = bad ? '✕ failed' : ok ? `✓ ${ok}/${its.length} ok${list ? ` · ${fmt(list.total)} rows` : ''}` : 'not tested yet';
      text(c, res, tile.w - 10, p.y, state ? 0.8 : 0.3, 'right', 8);
    });
    // the request being tested travels server → data → server → route
    if (s.cur) {
      const p = this.pos(tile, this.rowOf(tile, s.cur.key)), k = s.cur.t;
      if (k < 0.5) comet(c, (t) => ({ x: lerp(S.x, db.x + 13, t), y: S.y }), k * 2, 3, 1, 4, 0.06);
      else comet(c, curve(from, p), (k - 0.5) * 2, 3, 1, 4, 0.06);
      text(c, `testing ${s.cur.label}`, 10, tile.h - 9, 0.7, 'left', 8.5, tile.w - 20);
    } else if (s.phase === 'live') {
      text(c, `LIVE · ${s.api}  ·  MCP ${s.mcp}`, 10, tile.h - 9, 0.85, 'left', 8.5, tile.w - 20);
    }
    const nRows = this.rows(tile).length;
    for (const t of s.traffic) { const p = this.pos(tile, Math.min(t.i, nRows - 1)); comet(c, curve(from, p), t.t, 2.6, 0.8, 4, 0.05); }
  },
  stat(tile) {
    if (!active(tile)) return 'Waiting for the database';
    const s = tile.s, r = s.items.filter((x) => x.kind === 'route').length, m = s.items.length - r;
    return s.phase === 'live' ? `Live · ${r} routes · ${m} MCP tools · self-test ${s.passed}/${s.tested}` : `Routes ${r} · MCP tools ${m}`;
  },
};

/* ---------------- tiles ---------------- */
const AGENTS = [
  { id: 'explorer', name: 'Explorer', desc: 'Reads the site page by page and pulls out the records', kind: explorer,
    about: 'The Explorer turns the website into a table. It visits the pages one by one, and whenever it meets a new kind of page, Nemotron looks at it and decides what the page is, what the records on it are called and which column holds what. After that, plain code does the repetitive work: it copies every row, follows the next-page links, reuses what Nemotron learned on pages with the same layout, and never submits a form or clicks delete or logout.' },
  { id: 'operator', name: 'Operator', desc: 'Designs the API and MCP tools from the extracted data', kind: operator,
    about: 'The Operator turns that table into an API: a fixed set of questions other apps and AI assistants can ask about the data. Nemotron proposes the endpoints, what to call them and which filters make sense for each column (and, if the site had forms, which writes are possible). The code then checks every endpoint against the real data, sends mistakes back to Nemotron once, and tries each endpoint on the real records before it is accepted.' },
  { id: 'database', name: 'Database', desc: 'Loads the data, model and API design into SpacetimeDB', kind: database,
    about: 'The Database step saves everything to SpacetimeDB: the records, the description of the data and the API design, so the API and this dashboard read from one place. No AI is involved here; the loader sends every record (8 at a time) and then checks that the database really has them all.' },
  { id: 'server', name: 'Server', desc: 'Starts the real REST API and MCP server and tests them', kind: server,
    about: 'The Server turns the design into something you can actually use. It reads the API design and the records back from SpacetimeDB and starts two front doors to the same data: a REST API for apps (with /docs) and an MCP server for AI assistants like Claude. Before going live it tests itself: it calls every route with the Operator\u2019s own example request and checks the answer matches, then connects to the MCP server like an AI client would and calls every tool. No AI is involved in this step; it is plain code that proves the result works.' },
];
const LABEL = { idle: 'Idle', working: 'Working', done: 'Done', live: 'Live' };

export { AGENTS, LABEL, ring, clamp, live };
