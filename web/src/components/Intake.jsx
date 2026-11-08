// Start panel: the link box, the URL fit-check, and Start exploring.
//
// Start exploring is enabled only when all of these hold:
//   the "I own this system…" box is ticked,
//   the URL now in the box is the one that was checked,
//   and the verdict is good_fit, or probably_not with "Continue anyway" clicked.
// blocked can never start.

import { forwardRef, useEffect, useRef, useState } from 'react';
import { GearIcon, GlobeIcon } from './Icons.jsx';
import { CHECK_ENDPOINT, checkMode, checkUrl, validateUrl } from '../lib/checkUrl.js';
import './intake.css';

const VERDICT = {
  good_fit: { title: 'Good fit', line: 'This looks like a legacy system Facade can explore.' },
  probably_not: { title: 'Probably not a fit', line: 'Facade is built for older systems with no API. You can still continue.' },
  blocked: { title: 'Can’t explore this site', line: 'Facade won’t run on this address.' },
};

const Intake = forwardRef(function Intake({ phase, running, url, setUrl, onStart, onStop, safety, onOpenSettings }, settingsBtnRef) {
  const urlRef = useRef(null);
  const [authorized, setAuthorized] = useState(false);
  // check: idle | invalid | loading | done | error
  const [check, setCheck] = useState({ status: 'idle' });
  const [continued, setContinued] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const reqRef = useRef(null);   // { id, abort } of the check in flight

  useEffect(() => { urlRef.current && urlRef.current.focus(); }, []);
  useEffect(() => () => reqRef.current && reqRef.current.abort(), []);

  // seconds counter while a check runs
  useEffect(() => {
    if (check.status !== 'loading') return undefined;
    setElapsed(0);
    const t0 = Date.now();
    const id = setInterval(() => setElapsed(Math.floor((Date.now() - t0) / 1000)), 500);
    return () => clearInterval(id);
  }, [check.status, check.url]);

  // Editing the URL throws away the old result (and stops a check in flight).
  const editUrl = (v) => {
    setUrl(v);
    if (reqRef.current) { reqRef.current.abort(); reqRef.current = null; }
    if (check.status !== 'idle') setCheck({ status: 'idle' });
    setContinued(false);
  };

  async function runCheck() {
    const v = validateUrl(url);
    if (!v.ok) { setCheck({ status: 'invalid', error: v.error }); urlRef.current && urlRef.current.focus(); return; }
    if (reqRef.current) reqRef.current.abort();
    const ctrl = new AbortController();
    const id = Symbol('check');
    reqRef.current = { id, abort: () => ctrl.abort() };
    setContinued(false);
    setCheck({ status: 'loading', url: v.url });
    try {
      const res = await checkUrl(v.url, { signal: ctrl.signal });
      if (reqRef.current?.id !== id) return;       // a newer check or an edit replaced this one
      reqRef.current = null;
      setCheck({ status: 'done', url: v.url, ...res });
    } catch (e) {
      if (ctrl.signal.aborted || reqRef.current?.id !== id) return;
      reqRef.current = null;
      setCheck({ status: 'error', url: v.url, error: e.message || 'The URL check failed.' });
    }
  }

  const current = validateUrl(url);
  const checkedThis = check.status === 'done' && current.ok && current.url === check.url;
  const verdictOk = checkedThis && (check.verdict === 'good_fit' || (check.verdict === 'probably_not' && continued));
  const canStart = authorized && verdictOk;

  // What's still missing, shown under the buttons so the disabled state explains itself.
  let need = '';
  if (!running && !canStart) {
    if (check.status === 'loading' || check.status === 'error' || check.status === 'invalid') need = '';
    else if (checkedThis && check.verdict === 'blocked') need = '';
    else if (!checkedThis) need = 'Check the URL to continue.';
    else if (check.verdict === 'probably_not' && !continued) need = authorized ? 'Choose Continue anyway to start.' : 'Tick the box and choose Continue anyway to start.';
    else if (!authorized) need = 'Tick the box above to start.';
  }

  const submit = (e) => {
    e.preventDefault();
    if (running) return;
    if (canStart) start();
    else if (check.status !== 'loading') runCheck();
  };
  const start = () => { if (canStart) onStart(check.url); };

  const loading = check.status === 'loading';

  return (
    <section className="intake">
      <div className="intake-top">
        <div className="eyebrow"><span className="live-dot"></span><span id="phase">{phase}</span></div>
        <div className="top-right">
          <span className={'safety-chip' + (safety.acting ? ' acting' : '')} id="safetyChip" title="Current safety mode (change in Settings)">
            {safety.label}
          </span>
          <button type="button" className="settings-btn gb" id="settingsBtn" aria-haspopup="dialog" aria-controls="settings"
            ref={settingsBtnRef} onClick={onOpenSettings}>
            <GearIcon />
            Settings
          </button>
        </div>
      </div>

      <h1>Give it a link. <span>Watch the agents work.</span></h1>

      <p className="fit-note" id="fitNote">
        For older web systems your business uses that have no API or export: patient systems, vendor portals, admin tools.
      </p>

      <form className="source" id="runForm" autoComplete="off" onSubmit={submit} noValidate>
        <label className={'url gb' + (check.status === 'invalid' ? ' bad' : '')}>
          <span className="sr">Website link</span>
          <GlobeIcon />
          <input ref={urlRef} id="url" type="text" spellCheck="false" placeholder="https://old-clinic-2005.com"
            value={url} readOnly={running} onChange={(e) => editUrl(e.target.value)}
            aria-describedby="fitNote checkResult" aria-invalid={check.status === 'invalid'} />
        </label>
        {running ? (
          <button type="button" className="btn primary" id="runBtn" onClick={onStop}>Stop</button>
        ) : (
          <>
            <button type="button" className="btn ghost" id="checkBtn" onClick={runCheck} disabled={loading}>
              {loading ? <><span className="spin" aria-hidden="true"></span>Checking…</> : 'Check URL'}
            </button>
            <button type="button" className="btn primary" id="startBtn" onClick={start} disabled={!canStart}>Start exploring</button>
          </>
        )}
      </form>

      <label className="consent">
        <input type="checkbox" id="authorized" checked={authorized} onChange={(e) => setAuthorized(e.target.checked)} disabled={running} />
        <span className="box" aria-hidden="true"></span>
        <span>I own this system or am authorized to automate it.</span>
      </label>

      <div id="checkResult" aria-live="polite">
        {check.status === 'invalid' && <p className="check-msg bad">{check.error}</p>}

        {loading && (
          <div className="verdict loading">
            <span className="dots" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i></span>
            <div>
              <b>Checking {check.url.replace(/^https?:\/\//, '').replace(/\/$/, '')}…</b>
              <p>This can take up to 20 seconds. {elapsed > 0 ? `${elapsed}s` : ''}</p>
            </div>
          </div>
        )}

        {check.status === 'error' && (
          <div className="verdict error" role="alert">
            <div>
              <b>The URL check didn’t work</b>
              <p>{check.error}</p>
            </div>
            <button type="button" className="btn ghost small" onClick={runCheck}>Retry</button>
          </div>
        )}

        {check.status === 'done' && (
          <div className={`verdict ${check.verdict}`}>
            <div>
              <b>{VERDICT[check.verdict].title}{check.mock && <span className="mock-tag"> · mock</span>}</b>
              <p>{VERDICT[check.verdict].line}</p>
              {check.reasons.length > 0 && <ul>{check.reasons.map((r, i) => <li key={i}>{r}</li>)}</ul>}
            </div>
            {check.verdict === 'probably_not' && (
              continued
                ? <span className="continued">Continuing anyway</span>
                : <button type="button" className="btn ghost small" id="continueBtn" onClick={() => setContinued(true)}>Continue anyway</button>
            )}
          </div>
        )}

        {need && <p className="check-msg">{need}</p>}
        {checkMode() === 'mock' && !running && <p className="check-mode">URL check is in mock mode. The real check will call {CHECK_ENDPOINT}.</p>}
      </div>
    </section>
  );
});

export default Intake;
