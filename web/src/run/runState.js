// Pure state for the Explorer view, built only from normalized events.

export const NODE_W = 214;
const GAP_X = 28, ROW_Y = 100, COLS = 3, LOG_CAP = 2000;

const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);
// Top row: Site → first page. Every other page type fills a 3-column grid below it.
const pos = (depth, row) => (depth < 2
  ? { x: 20 + depth * (NODE_W + GAP_X), y: 20 }
  : { x: 20 + (row % COLS) * (NODE_W + GAP_X), y: 20 + ROW_Y + 24 + Math.floor(row / COLS) * ROW_Y });

export function initialRun(meta = { site: '', model: [], total: 0 }) {
  return {
    site: meta.site, model: meta.model, total: meta.total, done: false, reason: '',
    nodes: { __root: { key: '__root', root: true, depth: 0, row: 0, ...pos(0, 0) } },
    order: ['__root'], edges: [], cols: [1], named: {},
    counts: {}, pages: 0, ai: 0, aiS: 0, reused: 0, reusedS: 0, failed: 0,
    t0: null, log: [], logN: 0, processed: 0, activeKey: null, actSeq: 0,
  };
}

export function runReducer(s, a) {
  if (a.type === 'meta') return initialRun(a.meta);
  if (a.type === 'done') return { ...s, done: true };
  if (a.type === 'event') return apply(s, a.evt, a.index);
  return s;
}

function addNode(s, e, failed) {
  // The first page becomes the hub; every other page type hangs off it.
  const hub = s.order.length > 1 ? s.order[1] : '__root';
  const parent = s.nodes[hub];
  const depth = parent.depth + 1;
  const cols = s.cols.slice();
  const row = cols[depth] || 0;
  cols[depth] = row + 1;
  s.cols = cols;
  const type = failed ? 'other' : e.pageType;
  const base = `${e.entity || 'Page'} ${type === 'other' ? 'page' : type}`;
  const seg = e.group === '/' ? 'Home' : cap(e.group.replace(/^\//, '').split('/')[0] || 'page');
  const label = failed ? seg : s.named[base] ? `${seg} · ${base}` : base;
  if (!failed) s.named = { ...s.named, [base]: true };
  s.order = [...s.order, e.group];
  s.edges = [...s.edges, { id: parent.key + '>' + e.group, from: parent.key, to: e.group }];
  return { key: e.group, depth, row, ...pos(depth, row), label, type, patterns: [], purpose: e.purpose,
    count: 0, recs: 0, aiReads: 0, failed: false, act: null };
}

function apply(s0, e, index) {
  const s = { ...s0, nodes: { ...s0.nodes } };
  if (s.t0 === null && e.ts) s.t0 = e.ts;

  if (e.kind === 'page' && e.group) {
    let n = s.nodes[e.group] || addNode(s, e, false);
    s.actSeq = s0.actSeq + 1;
    n = { ...n,
      count: n.count + 1, recs: n.recs + e.recordsNew, aiReads: n.aiReads + (e.reused ? 0 : 1),
      patterns: n.patterns.includes(e.pattern) ? n.patterns : [...n.patterns, e.pattern],
      act: { seq: s.actSeq, reused: e.reused, seconds: e.seconds } };
    s.nodes[e.group] = n;
    s.activeKey = e.group;
    s.pages = s0.pages + 1;
    if (e.reused) { s.reused = s0.reused + 1; s.reusedS = s0.reusedS + (e.seconds || 0); }
    else { s.ai = s0.ai + 1; s.aiS = s0.aiS + (e.seconds || 0); }
    if (e.recordsNew) { const ent = e.entity || 'Record'; s.counts = { ...s0.counts, [ent]: (s0.counts[ent] || 0) + e.recordsNew }; }
  } else if (e.kind === 'analyze_failed') {
    s.failed = s0.failed + 1;
    if (e.group) {
      const n = s.nodes[e.group] || addNode(s, e, true);
      s.actSeq = s0.actSeq + 1;
      s.nodes[e.group] = { ...n, failed: true, act: null, patterns: n.patterns.includes(e.pattern) ? n.patterns : [...n.patterns, e.pattern] };
      s.activeKey = e.group;
    }
  } else if (e.kind === 'done') {
    s.done = true;
    s.reason = e.reason;
  }

  s.logN = s0.logN + 1;
  const d = e.ts && s.t0 !== null ? Math.round((e.ts - s.t0) / 1000) : null;
  const t = d === null ? '#' + s.logN : `${String(Math.floor(d / 60)).padStart(2, '0')}:${String(d % 60).padStart(2, '0')}`;
  const log = s0.log.length >= LOG_CAP ? s0.log.slice(-(LOG_CAP - 1)) : s0.log.slice();
  log.push({ id: s.logN, t, evt: e });
  s.log = log;
  s.processed = index + 1;
  return s;
}
