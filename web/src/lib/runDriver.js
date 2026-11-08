// Drives the dashboard tiles AND the API tab from REAL agent events (replaces mockRun.js / mockApi.js).
//
// Everything goes through driver.handle(evt). Today the events come from a recorded run (replayRun below);
// later the same events come live from the back end through window.facadeEvent(evt).
//
// Event contract (one object per event):
//   { stage: 'run', kind: 'start', site }
//   { stage: 'model', entities: [{ name, record_count, fields: [{ name, type }] }] }        the data model
//   { stage: 'explore', ...one run_log.jsonl line, rows?: [[...]] }   explore.agent (page, done, ...)
//   { stage: 'records', entity, records: [{...}] }                    extracted records (for the API tab)
//   { stage: 'operator', kind: 'start' | 'tidied' | 'proposed' | 'fixed' | 'done', operations?, problems?, designed_by?, report? }
//   { stage: 'database', target, tables: [{ name, done, total, note }] }   store.load_run progress
//   { stage: 'run', kind: 'done' }
//
// The tiles are the real pipeline: Explorer (explore.agent) → Operator (operator_agent) → Database (load_run)
// → Server (serve.run: REST API + MCP server, self-tested).
//   { stage: 'server', kind: 'start' | 'built' | 'route' | 'tool' | 'live', ... }   serve.run (fields as in server.json)

const pathOf = (url) => { try { const u = new URL(url); return u.pathname + (u.search ? u.search.slice(0, 28) + (u.search.length > 28 ? '…' : '') : ''); } catch { return String(url || '/'); } };
const groupOf = (url) => { try { return new URL(url).pathname || '/'; } catch { return String(url || '/').split('?')[0]; } };
const soft = (n, k) => 1 - Math.exp(-n / k);
const NUM = new Set(['int', 'integer', 'float', 'number']);

/** _key "https://site/item?id=42" → "42" (same rule as operator_agent/inputs.py legacy_id_of). */
export function legacyId(r) {
  if (r.legacy_id != null) return String(r.legacy_id);
  const key = String(r._key || '');
  try {
    const u = new URL(key);
    for (const v of u.searchParams.values()) if (/^[\w-]+$/.test(v) && /\d/.test(v)) return v;
    const seg = u.pathname.split('/').filter(Boolean);
    return seg.length ? seg[seg.length - 1] : key;
  } catch { return key; }
}

/** Plain record with real types: { legacy_id, ...fields } (numbers stored as text become numbers). */
function typed(r, fields) {
  const d = r.data && typeof r.data === 'object' ? r.data : r;
  const out = { legacy_id: legacyId(r) };
  for (const [k, v] of Object.entries(d)) {
    if (k.startsWith('_') || k === 'legacy_id' || k === 'hash' || k === 'extracted_at') continue;
    const f = fields.find((x) => x.name === k);
    out[k] = f && NUM.has(f.type) && typeof v === 'string' && /^-?\d+(\.\d+)?$/.test(v.replace(/,/g, '')) ? Number(v.replace(/,/g, '')) : v;
  }
  return out;
}

/** Runs one designed read operation over the extracted records (same rules as operator_agent/query.py). */
export function runOperation(op, params, records) {
  const rows = records[op.entity] || [];
  const inputs = Object.fromEntries((op.inputs || []).map((i) => [i.name, i]));
  if (op.kind === 'get') {
    const pid = (op.inputs || []).find((i) => i.in === 'path');
    const hit = rows.find((r) => r.legacy_id === String(params[pid ? pid.name : 'id']));
    return hit ? { status: 200, body: hit } : { status: 404, body: { error: 'not found' } };
  }
  const match = (value, want, how) => {
    if (how === 'eq') return value != null && String(value).toLowerCase() === String(want).toLowerCase();
    if (how === 'contains') return value != null && String(value).toLowerCase().includes(String(want).toLowerCase());
    if (value == null) return false;
    const a = typeof value === 'number' ? value : value, b = typeof value === 'number' ? Number(want) : want;
    return how === 'gte' ? a >= b : a <= b;
  };
  let out = rows, limit = 50, offset = 0, sort = null;
  for (const [name, val] of Object.entries(params)) {
    const i = inputs[name];
    if (!i || val === '' || val == null) continue;
    if (i.match === 'limit') limit = parseInt(val, 10) || 50;
    else if (i.match === 'offset') offset = parseInt(val, 10) || 0;
    else if (i.match === 'sort') sort = String(val);
    else if (i.match === 'search') out = out.filter((r) => (i.fields || []).some((f) => match(r[f], val, 'contains')));
    else out = out.filter((r) => match(r[i.field], val, i.match));
  }
  if (sort) {
    const key = sort.replace(/^-/, ''), rev = sort.startsWith('-');
    out = [...out].sort((a, b) => ((a[key] == null) - (b[key] == null)) || (a[key] < b[key] ? -1 : a[key] > b[key] ? 1 : 0) * (rev ? -1 : 1));
  }
  return { status: 200, body: { total: out.length, limit, offset, items: out.slice(offset, offset + limit) } };
}

/* ---------------- shared run state (the API tab reads this) ---------------- */
function createStore() {
  let state = { site: '', phase: 'idle', model: [], operations: [], flagged: [], designedBy: null, records: {}, dbTarget: '', notes: {}, server: null };
  const listeners = new Set();
  return {
    get: () => state,
    set(patch) { state = { ...state, ...patch }; listeners.forEach((fn) => fn()); },
    subscribe(fn) { listeners.add(fn); return () => listeners.delete(fn); },
  };
}

const plural = (w) => (/s$/.test(w) ? w : /y$/.test(w) ? w.slice(0, -1) + 'ies' : w + 's');
const kindName = (type, entity) => {
  const e = (entity || 'item').toLowerCase();
  return type === 'list' ? `list of ${plural(e)}` : type === 'detail' ? `page for one ${e}` : type === 'form' ? `${e} form` : 'page';
};
const n0 = (n) => Number(n || 0).toLocaleString('en-US');

export function createRunDriver(D) {
  const store = createStore();
  let s = null;
  // plain-language notes per agent: { now: what it is doing, log: recent steps }
  function note(id, now, logLine) {
    const notes = { ...store.get().notes };
    const cur = notes[id] || { now: '', log: [] };
    notes[id] = { now, log: logLine ? [logLine, ...cur.log].slice(0, 8) : cur.log };
    store.set({ notes });
  }
  const fresh = () => ({ pages: 0, ai: 0, records: 0, expectPages: 0, total: 0, model: [], columns: [], pool: [], poolAt: 0, t0: performance.now() });

  function modelCard() {
    const e = s.model[0];
    return e ? { name: e.name, rows: e.record_count || s.records, fields: e.fields.map((f) => ({ name: f.name, type: ({ int: 'number', integer: 'number', string: 'text', textarea: 'long text', bool: 'yes/no' })[f.type] || f.type })) } : null;
  }

  function page(e) {
    const ai = !e.reused_mapping;
    s.pages++; if (ai) s.ai++;
    const n = Number(e.records_new || 0);
    let rows = e.rows;
    if (!rows && n > 0 && s.pool.length) { rows = s.pool.slice(s.poolAt, s.poolAt + n); s.poolAt += n; }
    s.records += n;
    D.feed('explorer', { key: groupOf(e.url), path: pathOf(e.url), purpose: e.purpose, pageType: e.page_type, entity: e.entity, ai,
      seconds: ai && e.nemotron_ms ? e.nemotron_ms / 1000 : null, records: n,
      columns: s.columns, rows: (rows || []).map((r) => (Array.isArray(r) ? r : s.columns.map((c) => r[c]))) });
    D.set('explorer', { status: 'working', progress: Math.min(0.98, s.expectPages ? s.pages / s.expectPages : soft(s.pages, 15)), stat: null });
    const what = kindName(e.page_type, e.entity), where = pathOf(e.url);
    const got = n > 0 ? `copied ${n0(n)} ${plural((e.entity || 'record').toLowerCase())} (${n0(s.records)} so far)` : e.page_type === 'form' ? 'read the form fields without submitting' : 'no new records here';
    const now = ai
      ? `New kind of page: Nemotron read ${where} in ${e.nemotron_ms ? (e.nemotron_ms / 1000).toFixed(1) + 's' : 'a few seconds'} and decided it's a ${what}${e.purpose ? ` (“${e.purpose}”)` : ''}. Then ${got}.`
      : `${where} looks like a ${what} it already learned, so it reused that mapping with no AI call and ${got}.`;
    note('explorer', now, `${ai ? 'Nemotron read' : 'Reused'} ${where} · ${what} · ${n > 0 ? '+' + n0(n) : got}`);
  }

  return {
    store,
    elapsed() { return s ? (performance.now() - s.t0) / 1000 : 0; },

    begin({ site = '', expectPages = 0 } = {}) {
      D.reset();
      s = fresh();
      s.expectPages = expectPages;
      store.set({ site, phase: 'exploring', model: [], operations: [], flagged: [], designedBy: null, records: {}, dbTarget: '', notes: {}, server: null });
      if (site) note('explorer', `Opening ${site}. Nemotron will look at the first page and work out what kind of page it is and what data it holds.`, `Started at ${site}`);
      if (site) { D.feed('explorer', { opening: pathOf(site) === '/' ? site.replace(/^https?:\/\//, '') : pathOf(site) }); D.set('explorer', { status: 'working', progress: 0.02, stat: null }); }
    },

    /** The 3 fields filled most often in the real records (model order), for the Explorer's row preview. */
    pickColumns() {
      const e = s.model[0];
      if (!e) return;
      const fields = e.fields.map((f) => f.name);
      const recs = store.get().records[e.name] || [];
      const filled = (f) => recs.reduce((k, r) => k + (r[f] != null && r[f] !== '' ? 1 : 0), 0);
      const top = new Set([...fields].sort((a, b) => filled(b) - filled(a)).slice(0, 3));
      s.columns = fields.filter((f) => top.has(f));
    },

    /** Replays only: the real records, so each page can show the rows it produced. */
    setRecordPool(rows) { if (s) s.pool = rows; },

    handle(evt) {
      if (!s) this.begin({});
      if (evt.stage === 'run' && evt.kind === 'start') { this.begin(evt); if (evt.models) store.set({ models: { ...(store.get().models || {}), ...Object.fromEntries(Object.entries(evt.models).map(([k, m]) => [k, { model: m }])) } }); return; }
      if (evt.stage === 'run' && evt.kind === 'done') { if (store.get().phase !== 'live') store.set({ phase: 'done' }); return; }
      if (evt.stage === 'model') {
        s.model = evt.entities || [];
        store.set({ model: s.model });
        this.pickColumns();
        return;
      }
      if (evt.stage === 'records') {
        const e = s.model.find((m) => m.name === evt.entity) || { fields: [] };
        const recs = { ...store.get().records, [evt.entity]: (evt.records || []).map((r) => typed(r, e.fields)) };
        store.set({ records: recs });
        this.pickColumns();
        return;
      }
      if (evt.stage === 'explore') {
        if (evt.kind === 'page') page(evt);
        else if (evt.kind === 'analyze_failed' || evt.kind === 'error') note('explorer', `Couldn't make sense of ${pathOf(evt.url)} (${String(evt.error || 'no usable answer').slice(0, 80)}). Skipped it and kept going.`, `Skipped ${pathOf(evt.url)}`);
        else if (evt.kind === 'split_column') note('explorer', `One column held several values at once, so Nemotron wrote a pattern to split it; the code tested it on every row${(evt.repaired_rate || 0) > (evt.first_rate || 0) ? ' and had Nemotron fix it' : ''}.`, `Split column ${evt.column}`);
        else if (evt.kind === 'mapping_problems') note('explorer', `The code caught a mistake in Nemotron's reading (${String((evt.problems || [])[0] || '').slice(0, 80)}) and sent it back to be fixed.`, 'Caught a bad reading');
        else if (evt.kind === 'skipped_invented_link') note('explorer', `Nemotron suggested a link that isn't on the page (${pathOf(evt.url)}); the code ignored it.`, 'Ignored a made-up link');
        else if (evt.kind === 'done') {
          D.set('explorer', { status: 'done', progress: 1, stat: `${s.pages} pages · ${s.records.toLocaleString('en-US')} rows · ${evt.minutes ?? '?'} min` });
          note('explorer', `Done. Read ${n0(s.pages)} pages in ${evt.minutes ?? '?'} min (Nemotron only had to read ${s.ai} of them) and copied ${n0(s.records)} records. Stopped because: ${evt.reason || 'finished'}.`, 'Finished');
          store.set({ phase: 'designing' });
        }
        return;
      }
      if (evt.stage === 'operator') {
        if (evt.kind === 'tidied') {
          const rep = evt.report || {};
          const parts = [
            ...(rep.renamed || []).filter((r) => r.from !== r.to).map((r) => `${r.from} → ${r.to}`),
            ...(rep.merged || []).map((m) => `merged ${m.from} into ${m.into}`),
            ...(rep.moved || []).map((m) => `moved ${m.count} ${m.from} rows from ${m.page} into ${m.to}`),
            ...(rep.dropped_entities || []).map((d) => `dropped ${d.entity} (${d.why})`),
          ];
          const nf = (rep.renamed || []).reduce((n, r) => n + Object.keys(r.fields || {}).length, 0);
          D.set('operator', { status: 'working', progress: 0.25, stat: null });
          note('operator', parts.length || nf
            ? `Cleaned up the names before designing, so endpoints say what they return: ${parts.join('; ') || 'entity names kept'}${nf ? `; ${nf} fields renamed to say what they hold` : ''}.`
            : 'Checked the names: they already describe the data, nothing to clean up.', 'Cleaned up names');
          return;
        }
        if (evt.designed_by && evt.designed_by.model) {   // the model that actually answered (Super, or Nano after a fallback)
          store.set({ models: { ...(store.get().models || {}), operator: { model: evt.designed_by.model } } });
        }
        if (evt.kind === 'start') {
          D.feed('operator', { phase: 'drafting', model: modelCard() });
          D.set('operator', { status: 'working', progress: 0.1, stat: null });
          const m = modelCard();
          note('operator', m ? `Reading what the Explorer found: ${n0(m.rows)} ${plural(m.name.toLowerCase())}, each with ${m.fields.length} fields (${m.fields.map((f) => f.name).join(', ')}). Asking Nemotron to design an API for it.` : 'Asking Nemotron to design an API for the extracted data.', 'Started designing');
        } else if (evt.kind === 'proposed') {
          const ops = evt.operations || [];
          const flagged = (evt.problems || []).map((p) => String(p).split(':')[0].trim());
          D.feed('operator', { phase: 'proposed', endpoints: ops.map(epCard), problems: evt.problems || [] });
          D.set('operator', { status: 'working', progress: 0.55, stat: null });
          store.set({ operations: ops, flagged, phase: 'designing' });
          note('operator', `Nemotron proposed ${ops.length} endpoints: ${ops.map((o) => `${o.method} ${o.path}`).join(', ')}.${(evt.problems || []).length ? ` The checker found a problem: “${evt.problems[0]}”. Sent it back to Nemotron to fix.` : ' The checker found no problems.'}`, `Proposed ${ops.length} endpoints${(evt.problems || []).length ? ', 1 flagged' : ''}`);
        } else if (evt.kind === 'fixed') {
          D.feed('operator', { phase: 'fixed' });
          D.set('operator', { status: 'working', progress: 0.8, stat: null });
          store.set({ flagged: [] });
          note('operator', `Nemotron fixed the flagged endpoint. ${(evt.problems || []).length ? (evt.problems || []).length + ' problem(s) left.' : 'The checker now finds no problems.'}`, 'Fixed by Nemotron');
        } else if (evt.kind === 'done') {
          const ops = evt.operations || store.get().operations;
          D.feed('operator', { phase: 'done', endpoints: ops.map(epCard) });
          D.set('operator', { status: 'live', progress: 1, stat: null });
          store.set({ operations: ops, flagged: [], designedBy: evt.designed_by || null, phase: 'loading' });
          const ex = ops.map(epCard).find((e) => e.example && e.total != null);
          note('operator', `API ready: ${ops.length} endpoints, each also an MCP tool for AI assistants. Every one was tried on the real data${ex ? ` (e.g. ${ex.method} ${ex.example} → ${n0(ex.total)} results)` : ''}. Try them on the API tab.`, 'API ready');
        }
        return;
      }
      if (evt.stage === 'server') {
        const k = evt.kind;
        if (k === 'start') {
          D.feed('server', { phase: 'loading', source: evt.source, records: evt.records });
          D.set('server', { status: 'working', progress: 0.1, stat: null });
          note('server', `Reading the API design and ${n0(evt.records)} records back from ${/spacetime/i.test(evt.source || '') ? 'SpacetimeDB' : 'the saved files'}, to start the servers from them.`, 'Loaded design + records');
        } else if (k === 'built') {
          D.feed('server', { phase: 'built', routes: evt.routes || [], tools: evt.tools || [] });
          D.set('server', { status: 'working', progress: 0.35, stat: null });
          note('server', `Started a REST API with ${(evt.routes || []).length} routes (plus /docs) and an MCP server with ${(evt.tools || []).length} tools, both from the same design. Now testing each one with a real request.`, `Built ${(evt.routes || []).length} routes + ${(evt.tools || []).length} tools`);
        } else if (k === 'route' || k === 'tool') {
          const key = k === 'route' ? `${evt.method} ${evt.path}` : evt.name;
          const label = k === 'route' ? (evt.request || evt.path) : `${evt.name}(${Object.entries(evt.args || {}).map(([a, v]) => `${a}=${v}`).join(', ')})`;
          D.feed('server', { test: { kind: k, key, ok: evt.ok, total: evt.total, label } });
          const res = evt.ok === false ? `failed${evt.expected != null ? ` (expected ${n0(evt.expected)})` : ''}` : evt.total != null ? `${n0(evt.total)} results` : 'ok';
          note('server', `${k === 'route' ? 'Called' : 'An AI-style client called the MCP tool'} ${label} → ${res}${k === 'route' && evt.expected != null && evt.ok ? ', the same answer as the Operator\u2019s example' : ''}.`, `${evt.ok === false ? '✕' : '✓'} ${label} → ${res}`);
        } else if (k === 'live') {
          D.feed('server', { phase: 'live', api: evt.api, mcp: evt.mcp, passed: evt.passed, tested: evt.tested });
          D.set('server', { status: 'live', progress: 1, stat: null });
          store.set({ server: { api: evt.api, mcp: evt.mcp, docs: evt.docs }, phase: 'live' });
          note('server', `Live. Apps can call ${evt.api} (docs at ${evt.docs}) and AI assistants can connect to the MCP server at ${evt.mcp}. Self-test: ${evt.passed} of ${evt.tested} checks passed.`, 'Live');
        }
        return;
      }
      if (evt.stage === 'database') {   // the SpacetimeDB load is shown on the Server tile (it is code, not an agent)
        const rec = (evt.tables || []).find((t) => t.name === 'record');
        const all = (evt.tables || []).every((t) => !t.total || t.done >= t.total);
        D.feed('server', { phase: 'loading', source: evt.target || 'SpacetimeDB', records: rec ? rec.done : 0 });
        D.set('server', { status: 'working', progress: all ? 0.4 : 0.2, stat: null });
        if (evt.target) store.set({ dbTarget: evt.target });
        if (all) { store.set({ phase: 'serving' }); note('server', `Saved ${n0(rec ? rec.total : 0)} records, the data description and the API design to SpacetimeDB. Starting the API from it.`, 'Saved to SpacetimeDB'); }
        else if (rec) note('server', `Saving to SpacetimeDB: ${n0(rec.done)} of ${n0(rec.total)} records so far.`, rec.done === 0 ? 'Connected to SpacetimeDB' : null);
        return;
      }
      if (evt.stage === 'parser') {
        D.feed('parser', evt);
        if (evt.kind === 'start') {
          D.set('parser', { status: 'working', progress: 0.05, stat: null });
          note('parser', 'Watching every page the Explorer reads for PDFs and document images. Each one is read by NVIDIA Nemotron Parse.', 'Started');
        } else if (evt.kind === 'found') {
          note('parser', `Found ${evt.doc_kind === 'pdf' ? 'a PDF' : 'an image'}: \u201c${evt.title}\u201d. Queued for Nemotron Parse.`, `Found ${evt.title}`);
        } else if (evt.kind === 'parsed') {
          D.set('parser', { status: 'working', progress: 0.5, stat: null });
          note('parser', `Nemotron Parse read page ${evt.page} of ${evt.of} of \u201c${evt.title}\u201d in ${(evt.ms / 1000).toFixed(1)}s (${n0(evt.chars)} characters)${evt.preview ? `, starting \u201c${evt.preview}\u201d` : ''}.`, `Read ${evt.title} p${evt.page}`);
        } else if (evt.kind === 'failed') {
          note('parser', `Could not read \u201c${evt.title}\u201d: ${evt.error}`, `Skipped ${evt.title}`);
        } else if (evt.kind === 'done') {
          D.set('parser', { status: evt.docs ? 'live' : 'done', progress: 1, stat: null });
          note('parser', evt.docs ? `Done: read ${evt.pages} pages from ${evt.docs} documents. They become Document records with a searchable /documents endpoint.` : 'Done: the site had no PDFs or document images on the pages the Explorer read.', 'Done');
        }
        return;
      }
    },

    stop() { D.reset(); s = null; store.set({ phase: 'idle', server: null }); },
  };
}

function epCard(op) {
  const ex = op.example || {}, res = ex.response || {};
  const first = Array.isArray(res.items) && res.items[0] ? (res.items[0].title || res.items[0].name || res.items[0].legacy_id) : res.title || null;
  return { method: op.method, path: op.path, name: op.name, summary: op.summary || '', example: ex.request || '',
    total: typeof res.total === 'number' ? res.total : null, first: first ? String(first) : null };
}

/* ---------------- recorded run → timed events ---------------- */

const parseJSONL = (t) => t.split(/\r?\n/).filter((l) => l.trim()).map((l) => { try { return JSON.parse(l); } catch { return null; } }).filter(Boolean);

/** Loads the recorded run published with the app (web/public/run/). */
export async function loadRecordedRun(base = './run/') {
  const get = async (p, json) => {
    try {
      const r = await fetch(base + p);
      if (!r.ok || (r.headers.get('content-type') || '').includes('text/html')) return null;
      return json ? r.json() : r.text();
    } catch { return null; }
  };
  const [log, model, ops, server] = await Promise.all([get('run_log.jsonl'), get('data_model.json', true), get('operations.json', true), get('server.json', true)]);
  if (!log) return null;
  const records = {};
  for (const e of (model && model.entities) || []) { const t = await get(`records/${e.name}.jsonl`); if (t) records[e.name] = parseJSONL(t); }
  return { runLog: parseJSONL(log), model, ops, records, server };
}

/** Turns a recorded run into [{ at (ms), evt }], paced like a live run (Nemotron reads take longer). */
export function timeline(run) {
  const out = [];
  let at = 0;
  const pages = run.runLog.filter((l) => l.kind === 'page');
  const site = (run.model && run.model.site) || (pages[0] && pages[0].url) || '';
  const ents = (run.model && run.model.entities) || [];
  out.push({ at, evt: { stage: 'run', kind: 'start', site, expectPages: pages.length } });
  out.push({ at, evt: { stage: 'model', entities: ents } });
  for (const [name, recs] of Object.entries(run.records || {})) out.push({ at, evt: { stage: 'records', entity: name, records: recs } });
  for (const l of run.runLog) {
    const ai = l.kind === 'page' && !l.reused_mapping;
    at += ai ? 1400 + Math.min((l.nemotron_ms || 0) / 8, 2000) : l.kind === 'page' ? 420 : 250;
    out.push({ at, evt: { stage: 'explore', ...l } });
  }
  const ops = run.ops;
  if (ops && ops.operations) {
    const meta = ops.designed_by || {};
    at += 800; out.push({ at, evt: { stage: 'operator', kind: 'start' } });
    at += Math.min(Math.max((meta.nemotron_ms || 3000) / 8, 2200), 4000);
    out.push({ at, evt: { stage: 'operator', kind: 'proposed', operations: ops.operations, problems: meta.problems_found || [] } });
    if ((meta.problems_found || []).length) { at += 2600; out.push({ at, evt: { stage: 'operator', kind: 'fixed', problems: meta.problems_after_fix || [] } }); }
    at += 1600; out.push({ at, evt: { stage: 'operator', kind: 'done', operations: ops.operations, designed_by: meta } });
  }
  // store.load_run: site + schema, then records in batches, then the agent log
  const total = ents.reduce((n, e) => n + (e.record_count || 0), 0);
  const target = 'SpacetimeDB · maincloud / facade';
  const tables = (rec, ev) => [
    { name: 'site', done: 1, total: 1, note: 'site map + model + API design' },
    { name: 'entity_schema', done: ents.length, total: ents.length, note: ents.map((e) => e.name).join(', ') },
    { name: 'record', done: rec, total, note: 'extracted rows' },
    { name: 'event', done: ev, total: run.runLog.length, note: 'agent log' },
  ];
  at += 600; out.push({ at, evt: { stage: 'database', target, tables: tables(0, 0) } });
  for (let k = 1; k <= 10; k++) { at += 260; out.push({ at, evt: { stage: 'database', target, tables: tables(Math.round(total * k / 10), 0) } }); }
  at += 400; out.push({ at, evt: { stage: 'database', target, tables: tables(total, run.runLog.length) } });
  // serve.run: start the servers, test every route and MCP tool (results from the run's server.json)
  const sv = run.server;
  if (sv) {
    at += 900; out.push({ at, evt: { stage: 'server', kind: 'start', source: 'SpacetimeDB', records: sv.records } });
    at += 1100; out.push({ at, evt: { stage: 'server', kind: 'built', routes: (sv.routes || []).map((r) => [r.method, r.path]), tools: (sv.tools || []).map((t) => t.name) } });
    at += 900;
    for (const r of sv.routes || []) { at += 1300; out.push({ at, evt: { stage: 'server', kind: 'route', ...r } }); }
    for (const t of sv.tools || []) { at += 1300; out.push({ at, evt: { stage: 'server', kind: 'tool', ...t } }); }
    at += 900; out.push({ at, evt: { stage: 'server', kind: 'live', api: sv.api, mcp: sv.mcp, docs: sv.docs, passed: sv.passed, tested: sv.tested } });
  }
  out.push({ at: at + 200, evt: { stage: 'run', kind: 'done' } });
  return { site, events: out };
}

/** Plays a recorded run into the driver. Returns { stop, site }. */
export function replayRun(driver, run, { speed = 1, onDone } = {}) {
  const { site, events } = timeline(run);
  const first = run.model && run.model.entities && run.model.entities[0];
  const pool = first ? (run.records[first.name] || []).map((r) => typed(r, first.fields || [])) : [];
  const timers = events.map(({ at, evt }) => setTimeout(() => {
    driver.handle(evt);
    if (evt.stage === 'run' && evt.kind === 'start') driver.setRecordPool(pool);
    if (evt.stage === 'run' && evt.kind === 'done' && onDone) onDone();
  }, at / speed));
  return { site, stop() { timers.forEach(clearTimeout); } };
}
