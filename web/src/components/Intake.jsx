import { useEffect, useRef, useState } from 'react';
import { GlobeIcon } from './Icons.jsx';
import { checkUrl, validateUrl } from '../lib/checkUrl.js';
import './intake.css';

const VERDICT = {
  good_fit: { title: 'Good fit · can proceed', line: 'This looks like an older system RESTore can modernize. Starting…' },
  probably_not: { title: 'This may not need modernizing', line: 'RESTore is built for older systems with no API. You can still explore it.' },
  blocked: { title: 'RESTore can’t explore this site', line: 'It isn’t a system RESTore is allowed to access.' },
};

// Start panel: link box + Start exploring. Pressing Start first checks the site (is it an older system worth
// modernizing, and is RESTore allowed to access it?). A good fit starts right away; "probably not" asks first;
// blocked is refused.
export default function Intake({ phase, running, url, setUrl, onStart, onStop }) {
  const urlRef = useRef(null);
  const [check, setCheck] = useState({ status: 'idle' });   // idle | invalid | loading | done | error
  const reqRef = useRef(null);
  const goRef = useRef(null);   // timer that proceeds after a good-fit verdict

  useEffect(() => { urlRef.current && urlRef.current.focus(); }, []);
  useEffect(() => () => { reqRef.current && reqRef.current.abort(); clearTimeout(goRef.current); }, []);

  const editUrl = (v) => {
    setUrl(v);
    clearTimeout(goRef.current);
    if (reqRef.current) { reqRef.current.abort(); reqRef.current = null; }
    if (check.status !== 'idle') setCheck({ status: 'idle' });
  };

  async function checkAndStart() {
    const v = validateUrl(url);
    if (!v.ok) { setCheck({ status: 'invalid', error: v.error }); urlRef.current && urlRef.current.focus(); return; }
    if (reqRef.current) reqRef.current.abort();
    const ctrl = new AbortController(), id = Symbol('check');
    reqRef.current = { id, abort: () => ctrl.abort() };
    setCheck({ status: 'loading', url: v.url });
    try {
      const res = await checkUrl(v.url, { signal: ctrl.signal });
      if (reqRef.current?.id !== id) return;
      reqRef.current = null;
      setCheck({ status: 'done', url: v.url, ...res });
      // a good fit proceeds by itself after a moment, so the person sees why
      if (res.verdict === 'good_fit') goRef.current = setTimeout(() => { setCheck({ status: 'idle' }); onStart(v.url); }, 1400);
    } catch (e) {
      if (ctrl.signal.aborted || reqRef.current?.id !== id) return;
      reqRef.current = null;
      setCheck({ status: 'error', url: v.url, error: e.message || 'The site check failed.' });
    }
  }

  const submit = (e) => { e.preventDefault(); if (!running && check.status !== 'loading') checkAndStart(); };
  const loading = check.status === 'loading';

  return (
    <section className="intake">
      <div className="intake-top">
        <div className="eyebrow"><span className="live-dot"></span><span id="phase">{phase}</span></div>
      </div>

      <h1>Give it a link. <span>Watch the agents work.</span></h1>

      <form className="source" id="runForm" autoComplete="off" onSubmit={submit} noValidate>
        <label className={'url gb' + (check.status === 'invalid' ? ' bad' : '')}>
          <span className="sr">Website link</span>
          <GlobeIcon />
          <input ref={urlRef} id="url" type="text" spellCheck="false" placeholder="https://old-clinic-2005.com"
            value={url} readOnly={running || loading} onChange={(e) => editUrl(e.target.value)}
            aria-describedby="checkNote checkResult" aria-invalid={check.status === 'invalid'} />
        </label>
        {running ? (
          <button type="button" className="btn primary" id="runBtn" onClick={onStop}>Stop</button>
        ) : (
          <button type="submit" className="btn primary" id="startBtn" disabled={loading}>
            {loading ? <><span className="spin" aria-hidden="true"></span>Checking…</> : 'Search'}
          </button>
        )}
      </form>

      {loading && <p className="check-note">Checking {check.url.replace(/^https?:\/\//, '').replace(/\/$/, '')}: is it an older system worth modernizing, and is RESTore allowed to access it?</p>}
      {!running && !loading && check.status === 'idle' && (
        <p className="check-note" id="checkNote">
          Before exploring, RESTore checks that the site is an older system worth modernizing, and refuses sites it isn’t allowed to access.
        </p>
      )}

      <div id="checkResult" aria-live="polite">
        {check.status === 'invalid' && <p className="check-msg bad">{check.error}</p>}
        {check.status === 'error' && (
          <div className="verdict error" role="alert">
            <div><b>The site check didn’t work</b><p>{check.error}</p></div>
            <button type="button" className="btn ghost small" onClick={checkAndStart}>Try again</button>
          </div>
        )}
        {check.status === 'done' && VERDICT[check.verdict] && (
          <div className={`verdict ${check.verdict}`}>
            <div>
              <b>{VERDICT[check.verdict].title}</b>
              <p>{VERDICT[check.verdict].line}</p>
              {check.reasons && check.reasons.length > 0 && <ul>{check.reasons.map((r, i) => <li key={i}>{r}</li>)}</ul>}
            </div>
            {check.verdict === 'probably_not' && (
              <button type="button" className="btn ghost small" id="continueBtn" onClick={() => { const u = check.url; setCheck({ status: 'idle' }); onStart(u); }}>Explore anyway</button>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
