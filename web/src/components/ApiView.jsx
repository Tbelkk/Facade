// API page: the endpoints the operator agent designed, appearing as it designs them (Swagger-style).
// "Run" answers from the extracted records with the same rules as operator_agent/query.py, until the
// SpacetimeDB-backed API server is connected.

import { useEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react';
import { runOperation } from '../lib/runDriver.js';
import { ChevronIcon, LockIcon } from './Icons.jsx';

// "/astra/{date}/{building}" → path text with dimmed {params}
function PathText({ path }) {
  return (
    <span className="ep-path">
      {path.split(/(\{\w+\})/).filter(Boolean).map((part, i) => (part.startsWith('{') ? <i key={i}>{part}</i> : part))}
    </span>
  );
}

// pretty JSON with tinted tokens
function Json({ value }) {
  const parts = useMemo(() => {
    const text = JSON.stringify(value, null, 2);
    const re = /("(?:\\u[a-fA-F0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(?:true|false)\b|\bnull\b|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)/g;
    const out = [];
    let last = 0, m, k = 0;
    while ((m = re.exec(text))) {
      if (m.index > last) out.push(text.slice(last, m.index));
      const tok = m[0];
      const cls = /^"/.test(tok) ? (m[2] ? 'j-key' : 'j-str') : /true|false/.test(tok) ? 'j-bool' : tok === 'null' ? 'j-null' : 'j-num';
      out.push(<span key={k++} className={cls}>{tok}</span>);
      last = re.lastIndex;
    }
    out.push(text.slice(last));
    return out;
  }, [value]);
  return <pre className="json">{parts}</pre>;
}

const fill = (path, params) => path.replace(/\{(\w+)\}/g, (_, k) => encodeURIComponent(params[k] ?? `{${k}}`));
const BASE = 'https://api.facade.local/v1';

function CopyButton({ text, label, disabled }) {
  const [shown, setShown] = useState(label);
  const t = useRef(null);
  useEffect(() => () => clearTimeout(t.current), []);
  const copy = async () => {
    if (!text) return;
    try { await navigator.clipboard.writeText(typeof text === 'function' ? text() : text); setShown('Copied'); } catch { setShown('Failed'); }
    clearTimeout(t.current);
    t.current = setTimeout(() => setShown(label), 1200);
  };
  return <button type="button" className="mini" disabled={disabled} onClick={copy}>{shown}</button>;
}

// default inputs: the values from the operator's own example request, so the first Run shows its real example
function exampleValues(op) {
  const vals = Object.fromEntries((op.inputs || []).map((i) => [i.name, '']));
  const req = (op.example && op.example.request) || '';
  try {
    const u = new URL(req, BASE + '/');
    for (const [k, v] of u.searchParams) if (k in vals) vals[k] = v;
    const pathIn = (op.inputs || []).find((i) => i.in === 'path');
    if (pathIn) {
      const tpl = op.path.split('/'), got = u.pathname.split('/');
      tpl.forEach((seg, i) => { if (seg === `{${pathIn.name}}` && got[i]) vals[pathIn.name] = decodeURIComponent(got[i]); });
    }
  } catch { /* no example */ }
  return vals;
}

function Endpoint({ op, flagged, records, server }) {
  const [open, setOpen] = useState(false);
  const [values, setValues] = useState(() => exampleValues(op));
  const [res, setRes] = useState(null);
  const ran = useRef(false);
  const inputs = op.inputs || [];

  const trimmed = () => Object.fromEntries(Object.entries(values).map(([k, v]) => [k, String(v).trim()]));
  const query = () => { const q = inputs.filter((i) => i.in !== 'path' && String(values[i.name] || '').trim()).map((i) => `${i.name}=${encodeURIComponent(String(values[i.name]).trim())}`); return q.length ? '?' + q.join('&') : ''; };
  const url = `${op.method} ${(server && server.api) || BASE}${fill(op.path, trimmed())}${query()}`;

  // The real server when it's running (serve.run); otherwise the same query rules over the extracted records.
  async function run() {
    const t0 = performance.now();
    if (server && server.api) {
      const ctl = new AbortController(), timer = setTimeout(() => ctl.abort(), 2000);
      try {
        const r = await fetch(`${server.api}${fill(op.path, trimmed())}${query()}`, { signal: ctl.signal });
        const body = await r.json();
        setRes({ status: r.status, body, ms: Math.round(performance.now() - t0), from: 'live server' });
        return;
      } catch { /* server not reachable from here: fall back */ } finally { clearTimeout(timer); }
    }
    const r = runOperation(op, trimmed(), records);
    setRes({ ...r, ms: Math.max(1, Math.round(performance.now() - t0)), from: server ? 'extracted data (server not reachable)' : 'extracted data' });
  }
  const toggle = () => { const next = !open; setOpen(next); if (next && !ran.current) { ran.current = true; run(); } };
  const ok = res && res.status < 400;
  const write = op.source === 'legacy' || op.method !== 'GET';

  return (
    <div className={'ep' + (open ? ' open' : '')}>
      <button type="button" className="ep-row" aria-expanded={open} onClick={toggle}>
        <span className="verb">{op.method}</span>
        <PathText path={op.path} />
        <span className="ep-sum">{flagged ? '✕ checker flagged this · Nemotron is fixing it' : op.summary || op.name}</span>
        <ChevronIcon />
        <LockIcon />
      </button>
      <div className="ep-body" hidden={!open}>
        <div className="ep-sec">Parameters</div>
        {inputs.length ? (
          <div className="params">
            {inputs.map((p) => (
              <label className="param" key={p.name}>
                <span className="p-name">{p.name}{p.required || p.in === 'path' ? <em>*</em> : null}</span>
                <span className="p-meta">{p.in} · {p.type}{p.match && p.match !== p.name ? ` · ${p.match}` : ''}</span>
                <input type="text" spellCheck="false" aria-label={p.name} value={values[p.name] ?? ''}
                  placeholder={p.values ? p.values.join(' | ') : ''}
                  onChange={(e) => setValues({ ...values, [p.name]: e.target.value })}
                  onKeyDown={(e) => { if (e.key === 'Enter') run(); }} />
                <span className="p-desc">{p.match === 'search' ? `searches ${(p.fields || []).join(', ')}` : p.field && p.field !== p.name ? `filters ${p.field}` : ''}</span>
              </label>
            ))}
          </div>
        ) : <p className="no-params">No parameters.</p>}

        <div className="req">
          <code className="req-url">{url}</code>
          <div className="req-btns">
            <CopyButton label="Copy curl" text={() => `curl "${(server && server.api) || BASE}${fill(op.path, trimmed())}${query()}"`} />
            <button type="button" className="btn primary small" disabled={write} onClick={run}>Run</button>
          </div>
        </div>

        <div className="ep-sec">Response</div>
        <div className="resp">
          {write ? <p className="no-params">Write endpoints run through the Writer, which isn't connected yet.</p> : res ? (
            <>
              <div className="resp-head">
                <span className={`code ${ok ? 'ok' : 'bad'}`}>{res.status} {ok ? 'OK' : 'Not Found'}</span>
                <span>{res.ms} ms</span>
                <span>application/json</span>
                <span className="mock-tag">{res.from}</span>
                <CopyButton label="Copy JSON" text={() => JSON.stringify(res.body, null, 2)} />
              </div>
              <Json value={res.body} />
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function TagSection({ entity, ops, flagged, records, server, count }) {
  const [open, setOpen] = useState(true);
  return (
    <section className={'tag-sec' + (open ? ' open' : '')}>
      <button type="button" className="tag-head" aria-expanded={open} onClick={() => setOpen(!open)}>
        <h3>{entity}</h3>
        <span className="tag-desc">{(count ?? (records[entity] || []).length).toLocaleString('en-US')} records</span>
        <span className="tag-count">{ops.length}</span>
        <ChevronIcon />
      </button>
      <div className="tag-list">
        {ops.map((op) => <Endpoint key={op.method + op.path} op={op} flagged={flagged.includes(op.name)} records={records} server={server} />)}
      </div>
    </section>
  );
}

export default function ApiView({ store, host, on }) {
  const st = useSyncExternalStore(store.subscribe, store.get);
  const ops = st.operations || [];
  const groups = useMemo(() => {
    const g = new Map();
    for (const op of ops) { if (!g.has(op.entity)) g.set(op.entity, []); g.get(op.entity).push(op); }
    return [...g.entries()];
  }, [ops]);
  const by = st.designedBy;
  // record counts from the live server (the database), not from the rows streamed while exploring
  const [counts, setCounts] = useState({});
  useEffect(() => {
    if (!st.server?.api) { setCounts({}); return; }
    fetch(st.server.api.replace(/\/$/, '') + '/').then((r) => r.json()).then((j) => setCounts(j.records || {})).catch(() => {});
  }, [st.server?.api]);
  const status = !ops.length
    ? (st.phase === 'exploring' || st.phase === 'designing' ? 'The operator agent hasn’t proposed endpoints yet. They appear here as Nemotron designs them.' : 'Run the agents on a site to design its API.')
    : st.flagged.length ? 'Nemotron proposed these. The checker flagged a problem and Nemotron is fixing it.'
      : by ? `Designed by ${by.by === 'nemotron' ? 'Nemotron' : by.by} (${by.model || ''}${by.nemotron_ms ? `, ${(by.nemotron_ms / 1000).toFixed(1)}s` : ''}). Run answers from the extracted records.`
        : 'Endpoints proposed by Nemotron.';
  return (
    <main className={'app view' + (on ? ' on' : '')} id="view-api" aria-label="Generated API">
      <section className="api-head">
        <div className="eyebrow"><span className="live-dot"></span><span>Generated API{host ? ` · ${host}` : ''}</span></div>
        <h1>The plug. <span>Click an endpoint to try it.</span></h1>
        <p className="api-source" id="apiSource">{status}</p>
        <div className="api-meta">
          <code className="api-base" id="apiBase">{st.server ? st.server.api : BASE}</code>
          <span className="chip-tag" id="apiCount">{ops.length} endpoints</span>
          <span className="chip-tag">{ops.length} MCP tools{st.server ? ` · ${st.server.mcp}` : ''}</span>
          {st.server ? <a className="chip-tag" href={st.server.docs} target="_blank" rel="noreferrer">/docs</a> : null}
          <span className="chip-tag solid">{st.server ? 'Server live' : 'Extracted data'}</span>
        </div>
      </section>
      <section id="apiList">
        {groups.map(([entity, list]) => <TagSection key={entity} entity={entity} ops={list} flagged={st.flagged || []} records={st.records || {}} server={st.server} count={counts[entity]} />)}
      </section>
    </main>
  );
}
