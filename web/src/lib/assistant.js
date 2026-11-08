// "Ask RESTore": the prompt box under the agent tiles.
//
// Two kinds of questions:
//   1. How RESTore works  -> answered from the agents' own descriptions (agentKinds.js).
//   2. Questions about the extracted data -> answered by calling the read APIs the Operator designed,
//      with the same rules as the real server (runOperation = operator_agent/query.py).
//
// When the generated server is live and has a Nemotron endpoint, that is used instead:
//   POST {server.api}/assistant   body { question, history: [{ role, text }] }
//   -> { reply: string, calls: [{ method, path, count }] }
// Until that endpoint exists the built-in answers below are used, and the box says so.

import { AGENTS } from './agentKinds.js';
import { runOperation } from './runDriver.js';

const STOP = new Set(('a an the is are was were be of in on at to for from by with and or what which who whom whose where when how '
  + 'many much do does did show me list find get give all any some there their this that these those i you it its about tell can '
  + 'could would please any every have has had my our your than more less most least over under above below top best latest newest '
  + 'oldest highest lowest first last each per').split(' '));

const plural = (w) => (/s$/.test(w) ? w : /y$/.test(w) ? w.slice(0, -1) + 'ies' : w + 's');
const n0 = (n) => Number(n || 0).toLocaleString('en-US');
const readOps = (s) => (s.operations || []).filter((o) => o.method === 'GET' && (!o.source || o.source === 'database'));
const entities = (s) => [...new Set(readOps(s).map((o) => o.entity).filter(Boolean))];
const count = (s, e) => (s.records && s.records[e] ? s.records[e].length : 0);
const words = (q) => (q.toLowerCase().match(/[a-z0-9][a-z0-9.+#-]*/g) || []);

/** Short text for one record: its title/name if it has one, else its first text field. */
function label(r) {
  for (const k of ['title', 'name', 'subject', 'headline', 'label', 'course', 'description']) if (r[k]) return String(r[k]);
  const v = Object.entries(r).find(([k, x]) => k !== 'legacy_id' && typeof x === 'string' && x.trim());
  return v ? v[1] : `#${r.legacy_id}`;
}
const cut = (t, n = 90) => (t.length > n ? t.slice(0, n - 1) + '…' : t);

/** True once a site has been read and its API designed, so there is real data to ask about. */
export function ready(s) {
  // the Operator's design is final from 'loading' on (exploring / designing = still being built)
  return ['loading', 'serving', 'live', 'done'].includes(s.phase)
    && readOps(s).length > 0 && entities(s).some((e) => count(s, e) > 0);
}

/** What the box shows before the first question. */
export function intro(s) {
  if (!ready(s)) {
    return {
      locked: true,
      text: 'Once RESTore has read a site and built its API, ask questions here to understand the data behind it: '
        + 'what kinds of records it found, how many there are, what\'s in them, and which endpoint answers what.',
      examples: ['What data did RESTore find?', 'How many records are there?', 'Show the top 5 by a number', 'Search the records for a word'],
    };
  }
  const es = entities(s);
  const e0 = es.find((e) => count(s, e) > 0) || es[0];
  const many = plural(e0.toLowerCase());
  // a field the API can sort by, so the example question really works
  let sortField = null;
  for (const o of readOps(s).filter((x) => x.entity === e0)) {
    const si = (o.inputs || []).find((i) => i.match === 'sort' && (i.values || []).length);
    if (si) { sortField = si.values[0].replace(/^-/, '').replace(/_/g, ' '); break; }
  }
  // a real word from the data, so the search example finds something
  const searchable = readOps(s).some((o) => o.entity === e0 && (o.inputs || []).some((i) => i.match === 'search'));
  let word = null;
  if (searchable) {
    for (const r of (s.records[e0] || []).slice(0, 40)) {
      const w = (label(r).match(/[A-Za-z]{5,}/g) || []).find((x) => !STOP.has(x.toLowerCase()));
      if (w) { word = w.toLowerCase(); break; }
    }
  }
  const host = s.site ? s.site.replace(/^https?:\/\//, '').replace(/\/$/, '') : 'this site';
  return {
    locked: false,
    text: `RESTore read ${host} and built an API for it: `
      + es.map((e) => `${plural(e.toLowerCase())} (${n0(count(s, e))})`).join(', ')
      + `, ${readOps(s).length} endpoints in all. Ask a question to better understand the data: what's in it, how much there is, `
      + 'and which endpoint answers what. Each answer shows the API calls it used.',
    examples: [
      'What did RESTore build?',
      `How many ${many} are there?`,
      sortField ? `Show ${many} with the highest ${sortField}` : `Show some ${many}`,
      word ? `Find ${many} about "${word}"` : null,
    ].filter(Boolean),
  };
}

/* ---------------- built-in answers ---------------- */

function howItWorks(q) {
  const one = AGENTS.find((a) => q.includes(a.name.toLowerCase()) || q.includes(a.id));
  if (one) return { text: one.about || one.desc, calls: [] };
  if (/\bagents?\b|\bsteps?\b|\beach\b|\bwho\b/.test(q)) {
    return { text: AGENTS.map((a, i) => `${i + 1}. ${a.name}: ${a.desc}.`).join('\n'), calls: [] };
  }
  if (/\bend\b|\bget\b|\bresults?\b|\boutput\b/.test(q)) {
    return { text: 'At the end you get the old site\'s data in a modern database (SpacetimeDB), a REST API with docs (/docs), and an MCP server so AI assistants can use the data. The old site is never changed.', calls: [] };
  }
  return {
    text: 'You give RESTore the address of an old website that has no API. Four agents take over:\n'
      + AGENTS.map((a, i) => `${i + 1}. ${a.name}: ${a.desc}.`).join('\n')
      + '\nThe old site is only read, never changed. Watch the boxes above while it runs.',
    calls: [],
  };
}

function whatWasBuilt(s) {
  const ops = readOps(s);
  if (!ops.length) return null;
  const by = {};
  for (const o of ops) (by[o.entity] = by[o.entity] || []).push(o);
  const lines = Object.entries(by).map(([e, list]) => `${e} (${n0(count(s, e))} records): `
    + list.map((o) => `${o.method} ${o.path}`).join(', '));
  return {
    text: `RESTore built ${ops.length} read endpoints${s.server ? ' and an MCP tool for each one' : ''}:\n${lines.join('\n')}\n`
      + 'Open the API tab to try any of them, or ask me a question about the data.',
    calls: [],
  };
}

/** Pick the entity the question is about. */
function pickEntity(s, ws) {
  const es = entities(s);
  let best = null, score = 0;
  for (const e of es) {
    const names = [e.toLowerCase(), plural(e.toLowerCase())];
    const m = (s.model || []).find((x) => x.name === e);
    const fields = m ? (m.fields || []).map((f) => f.name.toLowerCase()) : [];
    let sc = 0;
    for (const w of ws) {
      if (names.includes(w)) sc += 3;
      else if (fields.some((f) => f.split('_').includes(w))) sc += 1;
    }
    if (sc > score) { score = sc; best = e; }
  }
  return best || (es.length === 1 ? es[0] : null);
}

const callText = (op, params) => {
  let path = op.path;
  const qs = [];
  for (const [k, v] of Object.entries(params)) {
    if (path.includes(`{${k}}`)) path = path.replace(`{${k}}`, encodeURIComponent(v));
    else qs.push(`${k}=${encodeURIComponent(v)}`);
  }
  return `${path}${qs.length ? '?' + qs.join('&') : ''}`;
};

function aboutData(s, q) {
  const ws = words(q);
  const e = pickEntity(s, ws);
  if (!e) {
    return { text: `I couldn't tell which data you mean. This API has ${entities(s).map((x) => plural(x.toLowerCase())).join(', ')}. Try naming one.`, calls: [] };
  }
  const ops = readOps(s).filter((o) => o.entity === e);
  const list = ops.find((o) => o.kind !== 'get' && !(o.inputs || []).some((i) => i.in === 'path' || i.required));
  const search = ops.find((o) => (o.inputs || []).some((i) => i.match === 'search'));
  const calls = [];
  const call = (op, params) => {
    const res = runOperation(op, params, s.records || {});
    const body = res.body || {};
    calls.push({ method: op.method, path: callText(op, params), count: body.total != null ? body.total : res.status === 200 ? 1 : 0 });
    return body;
  };
  const many = plural(e.toLowerCase());

  // how many
  if (/how many|count|number of|total/.test(q) && list) {
    const body = call(list, { limit: 1 });
    return { text: `There are ${n0(body.total)} ${many}.`, calls };
  }

  // number filters: "more than 100 points", "under 20 comments"
  const params = {};
  if (list) {
    for (const i of list.inputs || []) {
      if (!['gte', 'lte'].includes(i.match)) continue;
      const f = String(i.field || '').toLowerCase().replace(/_/g, ' ');
      if (!f || !q.includes(f.split(' ')[0])) continue;
      const up = q.match(/(?:more than|over|above|at least|>=?)\s*(\d[\d,.]*)/);
      const down = q.match(/(?:less than|under|below|at most|<=?)\s*(\d[\d,.]*)/);
      if (i.match === 'gte' && up) params[i.name] = up[1].replace(/,/g, '');
      if (i.match === 'lte' && down) params[i.name] = down[1].replace(/,/g, '');
    }
    // "highest / most / top X" -> sort descending on X if the API allows it
    const sortIn = (list.inputs || []).find((i) => i.match === 'sort');
    if (sortIn && /highest|most|top|best|largest|biggest|lowest|least|fewest|smallest/.test(q)) {
      const asc = /lowest|least|fewest|smallest/.test(q);
      const opts = (sortIn.values || []).map((v) => v.replace(/^-/, ''));
      const key = opts.find((v) => q.includes(v.replace(/_/g, ' '))) || opts[0];
      if (key) params[sortIn.name] = asc ? key : `-${key}`;
    }
  }

  // free-text words left after removing filler and the entity's own name
  const ent = new Set([e.toLowerCase(), many]);
  const quoted = q.match(/"([^"]+)"|'([^']+)'/);
  const terms = quoted ? [quoted[1] || quoted[2]] : ws.filter((w) => !STOP.has(w) && !ent.has(w) && !/^\d+$/.test(w)
    && !Object.values(params).some((v) => String(v).replace(/^-/, '').includes(w)));

  let body, searched = null;
  if (terms.length && search && !Object.keys(params).length) {
    const qIn = (search.inputs || []).find((i) => i.match === 'search');
    // try the longest word first; fall back to the next ones
    for (const t of [...terms].sort((a, b) => b.length - a.length).slice(0, 3)) {
      body = call(search, { [qIn.name]: t });
      searched = t;
      if (body.total) break;
    }
    if (!body.total) return { text: `No ${many} matched “${terms.join(' ')}”. Try another word.`, calls };
  }
  if (!body && list) body = call(list, { ...params, limit: 5 });
  if (!body) return { text: `There's no endpoint that lists ${many}.`, calls };

  const items = body.items || [];
  if (!items.length) return { text: `No ${many} matched that.`, calls };
  const shown = items.slice(0, 5).map((r) => `• ${cut(label(r))}`).join('\n');
  const sortKey = Object.values(params).find((v) => typeof v === 'string' && /^-?[a-z_]+$/i.test(v) && !/^\d/.test(v));
  const head = sortKey && body.total > 5
    ? `Top 5 ${many} by ${sortKey.replace(/^-/, '').replace(/_/g, ' ')}${sortKey.startsWith('-') ? '' : ' (lowest first)'}, out of ${n0(body.total)}:`
    : `Found ${n0(body.total)} ${body.total === 1 ? e.toLowerCase() : many}${searched ? ` matching “${searched}”` : ''}. ${body.total > 5 ? 'First 5' : 'Here they are'}:`;
  return { text: `${head}\n${shown}`, calls };
}

function builtIn(s, question) {
  const q = question.toLowerCase().trim();
  const hasApi = readOps(s).length > 0;
  if (/\bwhat did .*\bbuild|\bwhat was built|\bsummar|\b(which|what) (apis|endpoints)\b|\bwhat can i ask\b/.test(q)) {
    return whatWasBuilt(s) || { text: 'Nothing is built yet.', calls: [] };
  }
  const about = /\bhow (does|do) (it|restore|this)\b|\bhow it works\b|\bwhat (is|does) restore\b|\bagents?\b|\bexplorer\b|\boperator\b|\bstep|\bwhat will i get\b/;
  if (about.test(q) || !hasApi) {
    if (!hasApi && !(about.test(q) || /\bhow\b|\bwhat (is|does)\b|\bdatabase\b|\bserver\b/.test(q))) {
      return { text: 'There\'s no API to search yet.', calls: [] };
    }
    return howItWorks(q);
  }
  return aboutData(s, q);
}

/** Answer one question. Uses the server's Nemotron assistant when it exists, otherwise the built-in answers. */
export async function ask(s, question, history = []) {
  if (s.server && s.server.api) {
    const ctl = new AbortController();
    const timer = setTimeout(() => ctl.abort(), 30000);
    try {
      const r = await fetch(`${s.server.api}/assistant`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, signal: ctl.signal,
        body: JSON.stringify({ question, history }),
      });
      if (r.ok) {
        const j = await r.json();
        if (j && typeof j.reply === 'string') return { text: j.reply, calls: j.calls || [], by: 'Nemotron' };
      }
    } catch { /* not available: use the built-in answers */ } finally { clearTimeout(timer); }
  }
  return { ...builtIn(s, question), by: 'built-in' };
}
