// Explorer tab: replays a real run of the Explorer agent as if it were live.
// Panels read only the state from useRun; where the data comes from lives in ./data/source.js.

import { useEffect, useRef, useState } from 'react';
import './run.css';
import { useRun } from './useRun.js';
import { createReplaySource, filesFromDrop, loadFileRun, loadPublicRun } from './data/source.js';
import SiteMap from './components/SiteMap.jsx';
import AgentLog from './components/AgentLog.jsx';
import DataModel from './components/DataModel.jsx';
import DataBrowser from './components/DataBrowser.jsx';

const fmt = (n) => Number(n).toLocaleString('en-US');
const plural = (e) => (/s$/.test(e) ? e : /y$/.test(e) ? e.slice(0, -1) + 'ies' : e + 's');
const SPEEDS = [1, 2, 5, 20];

export default function ExplorerView({ on }) {
  const [source, setSource] = useState(null);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState('');
  const [speed, setSpeed] = useState(1);
  const [timing, setTiming] = useState('fixed');
  const [sub, setSub] = useState('live');
  const [dragging, setDragging] = useState(false);
  const fileRef = useRef(null);
  const dirRef = useRef(null);
  const started = useRef(false);

  const { run, records, status, play, toggle, restart } = useRun(source, { speed, timing });

  // Load the run published with the app (web/public/run/).
  // To go live later: setSource(createSpacetimeSource(conn)) instead.
  useEffect(() => {
    let alive = true;
    loadPublicRun().then((b) => {
      if (!alive) return;
      if (b) setSource(createReplaySource(b));
      setLoading(false);
    });
    return () => { alive = false; };
  }, []);

  // Start playing the first time the tab is opened.
  useEffect(() => {
    if (on && source && !started.current) { started.current = true; play(); }
  }, [on, source, play]);

  async function loadFiles(files) {
    try {
      setMessage('');
      const b = await loadFileRun(files);
      started.current = true;
      setSource(createReplaySource(b));
      setTimeout(() => setSub('live'), 0);
    } catch (err) { setMessage(err.message || String(err)); }
  }
  useEffect(() => { if (source && started.current && status === 'paused' && run.processed === 0) play(); }, [source, status, run.processed, play]);

  // Drop the run folder or files anywhere while this tab is open.
  useEffect(() => {
    if (!on) return undefined;
    let n = 0;
    const enter = (e) => { if (![...(e.dataTransfer?.types || [])].includes('Files')) return; e.preventDefault(); n++; setDragging(true); };
    const leave = () => { n = Math.max(0, n - 1); if (!n) setDragging(false); };
    const over = (e) => e.preventDefault();
    const drop = async (e) => { e.preventDefault(); n = 0; setDragging(false); loadFiles(await filesFromDrop(e.dataTransfer)); };
    addEventListener('dragenter', enter); addEventListener('dragleave', leave); addEventListener('dragover', over); addEventListener('drop', drop);
    return () => { removeEventListener('dragenter', enter); removeEventListener('dragleave', leave); removeEventListener('dragover', over); removeEventListener('drop', drop); };
  }, [on]);

  const pick = (e) => { loadFiles([...e.target.files]); e.target.value = ''; };

  const ents = Object.keys(run.counts);
  const names = ents.length ? ents : run.model.length ? run.model.map((m) => m.name) : ['Post'];
  const expected = run.model.reduce((n, m) => n + (m.recordCount || 0), 0);
  const got = Object.values(run.counts).reduce((a, b) => a + b, 0);
  const bar = expected ? got / expected : run.total ? run.processed / run.total : 0;
  const recTotal = Object.values(records).reduce((a, r) => a + r.length, 0);
  const playText = status === 'finished' ? 'Replay' : status === 'playing' ? 'Pause' : 'Play';
  const statusText = { idle: 'ready', paused: run.processed ? 'paused' : 'ready', playing: 'replaying', finished: run.reason || 'finished' }[status];

  return (
    <main className={'app view' + (on ? ' on' : '')} id="view-explorer" aria-label="Explorer run">
      <section className="run-head">
        <div className="run-title">
          <div className="eyebrow"><span className="live-dot"></span><span>Explorer agent · {source ? 'replay of a real run' : 'no run loaded'}</span></div>
          <h1>The map. <span>Learned once, then reused.</span></h1>
          <p className="run-src">
            {source ? `${run.site || 'site'} · ${fmt(run.total)} log lines · ${source.label}` : loading ? 'Looking for a run…' : 'Drop a run folder here, or use Load run files.'}
          </p>
          {message && <p className="run-msg">{message}</p>}
        </div>
        <div className="run-ctrl">
          <button type="button" className="btn primary small" onClick={toggle} disabled={!source}>{playText}</button>
          <button type="button" className="mini" onClick={restart} disabled={!source}>Restart</button>
          <div className="seg" role="radiogroup" aria-label="Timing">
            {[['fixed', '300 ms'], ['real', 'Real time']].map(([v, l]) => (
              <button key={v} type="button" role="radio" aria-checked={timing === v} onClick={() => setTiming(v)}>{l}</button>
            ))}
          </div>
          <div className="seg" role="radiogroup" aria-label="Speed">
            {SPEEDS.map((x) => <button key={x} type="button" role="radio" aria-checked={speed === x} onClick={() => setSpeed(x)}>{x}×</button>)}
          </div>
          <button type="button" className="mini" onClick={() => fileRef.current.click()}>Load run files</button>
          <button type="button" className="mini" onClick={() => dirRef.current.click()}>Load folder</button>
          <input ref={fileRef} type="file" multiple accept=".jsonl,.json,.ndjson" hidden onChange={pick} />
          <input ref={dirRef} type="file" webkitdirectory="" hidden onChange={pick} />
        </div>
      </section>

      <section className="run-stats" aria-label="Run totals">
        {names.map((n) => (
          <div className="run-count" key={n}><span className="l">{plural(n)}</span><span className="n">{fmt(run.counts[n] || 0)}</span></div>
        ))}
        <div className="run-prog">
          <div className="track"><i style={{ width: `${Math.min(100, bar * 100)}%` }}></i></div>
          <div className="k">
            <span>{expected ? `${fmt(got)} of ${fmt(expected)} records` : `line ${fmt(run.processed)} of ${fmt(run.total)}`}</span>
            <span>{statusText}</span>
          </div>
        </div>
        <div className="run-stat"><span className="k">Pages</span><span className="v">{fmt(run.pages)}</span></div>
        <div className="run-stat"><span className="k">Nemotron reads</span><span className="v ai">{fmt(run.ai)} · {run.aiS.toFixed(1)}s</span></div>
        <div className="run-stat"><span className="k">Reused</span><span className="v fast">{fmt(run.reused)}</span></div>
        {run.failed > 0 && <div className="run-stat"><span className="k">Failed</span><span className="v bad">{fmt(run.failed)}</span></div>}
      </section>

      <section>
        <div className="seg run-tabs" role="tablist" aria-label="Explorer views">
          <button type="button" role="tab" aria-selected={sub === 'live'} onClick={() => setSub('live')}>Live run</button>
          <button type="button" role="tab" aria-selected={sub === 'data'} onClick={() => setSub('data')}>
            Data browser{recTotal ? ` · ${fmt(recTotal)}` : ''}
          </button>
        </div>
      </section>

      {sub === 'live' ? (
        <>
          <section className="run-live">
            <SiteMap run={run} />
            <AgentLog run={run} />
          </section>
          <section><DataModel model={run.model} /></section>
        </>
      ) : (
        <section><DataBrowser records={records} model={run.model} /></section>
      )}

      {dragging && <div className="drop-hint">Drop the run folder or files</div>}
    </main>
  );
}
