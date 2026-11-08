// API page: lists the generated endpoints (Swagger-style) and shows mock responses.
// Same markup and behavior as app/renderer/apiview.js.

import { useEffect, useMemo, useRef, useState } from 'react';
import { mockApi as api } from '../lib/mockApi.js';
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

function Endpoint({ ep }) {
  const [open, setOpen] = useState(false);
  const [values, setValues] = useState(() => Object.fromEntries(ep.params.map((p) => [p.name, p.example()])));
  const [res, setRes] = useState(null);     // { status, body, ms }
  const [loading, setLoading] = useState(false);
  const ran = useRef(false);

  const trimmed = () => Object.fromEntries(Object.entries(values).map(([k, v]) => [k, v.trim()]));
  const url = `${ep.method} ${api.base}${fill(ep.path, trimmed())}`;

  async function run() {
    setLoading(true);
    const r = await api.call(ep, trimmed());
    setRes(r);
    setLoading(false);
  }

  const toggle = () => {
    const next = !open;
    setOpen(next);
    if (next && !ran.current) { ran.current = true; run(); }   // first open shows mock data right away
  };

  const ok = res && res.status < 400;
  return (
    <div className={'ep' + (open ? ' open' : '')}>
      <button type="button" className="ep-row" aria-expanded={open} onClick={toggle}>
        <span className="verb">{ep.method}</span>
        <PathText path={ep.path} />
        <span className="ep-sum">{ep.summary}</span>
        <ChevronIcon />
        <LockIcon />
      </button>
      <div className="ep-body" hidden={!open}>
        <div className="ep-sec">Parameters</div>
        {ep.params.length ? (
          <div className="params">
            {ep.params.map((p) => (
              <label className="param" key={p.name}>
                <span className="p-name">{p.name}<em>*</em></span>
                <span className="p-meta">path · string</span>
                <input type="text" spellCheck="false" aria-label={p.name} value={values[p.name]}
                  onChange={(e) => setValues({ ...values, [p.name]: e.target.value })}
                  onKeyDown={(e) => { if (e.key === 'Enter') run(); }} />
                <span className="p-desc">{p.description}</span>
              </label>
            ))}
          </div>
        ) : <p className="no-params">No parameters.</p>}

        <div className="req">
          <code className="req-url">{url}</code>
          <div className="req-btns">
            <CopyButton label="Copy curl" text={() => `curl -H "Authorization: Bearer $FACADE_TOKEN" "${api.base}${fill(ep.path, trimmed())}"`} />
            <button type="button" className="btn primary small" disabled={loading} onClick={run}>Run</button>
          </div>
        </div>

        <div className="ep-sec">Response</div>
        <div className="resp">
          {loading ? (
            <div className="loading"><span className="dots"><i></i><i></i><i></i><i></i><i></i></span>Calling mock API…</div>
          ) : res ? (
            <>
              <div className="resp-head">
                <span className={`code ${ok ? 'ok' : 'bad'}`}>{res.status} {ok ? 'OK' : res.status === 404 ? 'Not Found' : 'Bad Request'}</span>
                <span>{res.ms} ms</span>
                <span>application/json</span>
                <span className="mock-tag">mock data</span>
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

function TagSection({ group }) {
  const [open, setOpen] = useState(true);
  return (
    <section className={'tag-sec' + (open ? ' open' : '')}>
      <button type="button" className="tag-head" aria-expanded={open} onClick={() => setOpen(!open)}>
        <h3>{group.tag}</h3>
        <span className="tag-desc">{group.description}</span>
        <span className="tag-count">{group.endpoints.length}</span>
        <ChevronIcon />
      </button>
      <div className="tag-list">
        {group.endpoints.map((ep) => <Endpoint key={ep.method + ep.path} ep={ep} />)}
      </div>
    </section>
  );
}

export default function ApiView({ host, on }) {
  const total = api.spec.reduce((n, g) => n + g.endpoints.length, 0);
  return (
    <main className={'app view' + (on ? ' on' : '')} id="view-api" aria-label="Generated API">
      <section className="api-head">
        <div className="eyebrow"><span className="live-dot"></span><span>Generated API · OpenAPI 3.0</span></div>
        <h1>The plug. <span>Click an endpoint to try it.</span></h1>
        <p className="api-source" id="apiSource">
          {host
            ? `Generated for ${host}. Showing mock data until the back end is connected.`
            : 'Run the agents on a site to generate its API. Showing mock data for now.'}
        </p>
        <div className="api-meta">
          <code className="api-base" id="apiBase">{api.base}</code>
          <span className="chip-tag" id="apiCount">{total} endpoints</span>
          <span className="chip-tag">Bearer auth</span>
          <span className="chip-tag solid">Mock data</span>
        </div>
      </section>
      <section id="apiList">
        {api.spec.map((g) => <TagSection key={g.tag} group={g} />)}
      </section>
    </main>
  );
}
