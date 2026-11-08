// Settings drawer: how the Explorer runs on the old site.
// Every Explorer setting maps to a flag of `python -m facade.run` (core/facade/run.py),
// and the drawer shows the exact command for the current settings.
// Start exploring doesn't launch the agent yet, so the command is how you run it with these settings today.

import { useEffect, useRef, useState } from 'react';
import { facadeSettings as S } from '../lib/settings.js';
import { useSettings } from '../lib/hooks.js';
import { validateUrl } from '../lib/checkUrl.js';
import { CloseIcon } from './Icons.jsx';
import './settings.css';

const ASK_HINT = {
  always: 'Every change waits for your OK.',
  destructive: 'Cancels, deletes and overwrites wait for your OK. Adds and lookups go ahead.',
  never: 'Agents act on their own. Every action is still verified and logged.',
};
const ASK_OPTS = [['always', 'Always'], ['destructive', 'Destructive'], ['never', 'Never']];

/** The command that runs the whole workflow with these settings. */
export function runCommand(s, url) {
  const v = validateUrl(url);
  const parts = ['python', '-m', 'facade.run', v.ok ? `"${v.url}"` : '"<url>"'];
  if (s.pauseSec > 0) parts.push('--pause', String(s.pauseSec));
  parts.push('--pages', String(s.maxPages), '--minutes', String(s.maxRunMinutes));
  if (s.login) parts.push('--login');
  if (s.full) parts.push('--full');
  if (s.headed) parts.push('--headed');
  if (!s.live) parts.push('--no-live');
  return 'cd core && ' + parts.join(' ');
}

function Flag({ children }) { return <code className="flag">{children}</code>; }

function Switch({ id, label, hint, flag, value, onChange }) {
  return (
    <div className="set-row sub">
      <div className="set-text">
        <b id={id + 'Label'}>{label} {flag && <Flag>{flag}</Flag>}</b>
        <small>{hint}</small>
      </div>
      <button type="button" className="switch" id={id} role="switch" aria-checked={value} aria-labelledby={id + 'Label'} onClick={() => onChange(!value)}></button>
    </div>
  );
}

// Number inputs save on blur/Enter.
function NumberField({ id, k, value }) {
  const [min, max, step] = S.LIMITS[k];
  const [draft, setDraft] = useState(String(value));
  useEffect(() => { setDraft(String(value)); }, [value]);
  const commit = () => { S.set({ [k]: +draft }); setDraft(String(S.get()[k])); };
  return (
    <input type="number" id={id} data-key={k} min={min} max={max} step={step} value={draft}
      onChange={(e) => setDraft(e.target.value)} onBlur={commit} onKeyDown={(e) => { if (e.key === 'Enter') commit(); }} />
  );
}

export default function SettingsDrawer({ open, onClose, url }) {
  const s = useSettings();
  const drawerRef = useRef(null);
  const firstRef = useRef(null);
  const askRefs = useRef({});
  const [saved, setSaved] = useState('');
  const [copied, setCopied] = useState('Copy');
  const savedTimer = useRef(null);
  const first = useRef(true);

  useEffect(() => {
    if (first.current) { first.current = false; return; }
    setSaved('Saved');
    clearTimeout(savedTimer.current);
    savedTimer.current = setTimeout(() => setSaved(''), 1400);
  }, [s]);
  useEffect(() => () => clearTimeout(savedTimer.current), []);

  useEffect(() => {
    const el = drawerRef.current;
    if (open) { el.inert = false; const t = setTimeout(() => firstRef.current && firstRef.current.focus(), 60); return () => clearTimeout(t); }
    el.inert = true;
    return undefined;
  }, [open]);

  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  const askKeys = (e) => {
    if (!['ArrowLeft', 'ArrowRight'].includes(e.key) || S.get().readOnly) return;
    const opts = ASK_OPTS.map((o) => o[0]);
    const i = opts.indexOf(S.get().askBeforeActing) + (e.key === 'ArrowRight' ? 1 : -1);
    if (i >= 0 && i < opts.length) { S.set({ askBeforeActing: opts[i] }); askRefs.current[opts[i]] && askRefs.current[opts[i]].focus(); }
  };

  const [pMin, pMax, pStep] = S.LIMITS.pauseSec;
  const cmd = runCommand(s, url);
  const copy = async () => {
    try { await navigator.clipboard.writeText(cmd); setCopied('Copied'); } catch { setCopied('Select it and copy'); }
    setTimeout(() => setCopied('Copy'), 1400);
  };

  return (
    <>
      <div className="scrim" id="scrim" hidden={!open} onClick={onClose}></div>
      <aside ref={drawerRef} className={'drawer' + (open ? ' open' : '')} id="settings" role="dialog" aria-modal="true"
        aria-labelledby="settingsTitle" aria-hidden={!open}>
        <div className="drawer-head">
          <div>
            <div className="eyebrow"><span>Settings</span></div>
            <h2 className="drawer-title" id="settingsTitle">Explorer</h2>
            <p className="drawer-sub">How the agents run on the old site.</p>
          </div>
          <button type="button" className="icon-btn" id="closeSettings" aria-label="Close settings" onClick={onClose}>
            <CloseIcon />
          </button>
        </div>

        {/* speed */}
        <div className="set-block">
          <div className="set-text">
            <b>Speed limit <Flag>--pause</Flag></b>
            <small>Wait between page loads so a fragile old server isn’t overloaded. 0 loads pages as fast as the site answers.</small>
          </div>
          <label className="range-row">
            <span>Pause between pages</span>
            <input ref={firstRef} type="range" id="sPause" min={pMin} max={pMax} step={pStep} value={s.pauseSec}
              style={{ '--fill': `${((s.pauseSec - pMin) / (pMax - pMin)) * 100}%` }}
              onChange={(e) => S.set({ pauseSec: +e.target.value })} />
            <output id="oPause">{s.pauseSec.toFixed(1)} s</output>
          </label>
          <p className="set-hint">
            {s.pauseSec > 0 ? `At most about ${Math.floor(60 / s.pauseSec)} pages a minute.` : 'No speed limit.'}
          </p>
        </div>

        {/* stop limits */}
        <div className="set-block">
          <div className="set-text">
            <b>Stop limits <Flag>--pages</Flag> <Flag>--minutes</Flag></b>
            <small>The Explorer stops on its own when nothing new is left; these are the ceilings.</small>
          </div>
          <div className="num-grid">
            <label className="num"><span>Max pages</span><div><NumberField id="sMaxPages" k="maxPages" value={s.maxPages} /><em>pages</em></div></label>
            <label className="num"><span>Max run time</span><div><NumberField id="sMaxTime" k="maxRunMinutes" value={s.maxRunMinutes} /><em>min</em></div></label>
          </div>
        </div>

        {/* how it runs */}
        <div className="set-block">
          <div className="set-text">
            <b>How it runs</b>
          </div>
          <Switch id="sLogin" label="Log in first" flag="--login" value={s.login} onChange={(v) => S.set({ login: v })}
            hint="Opens the browser so you can sign in by hand. Needed for systems behind a login; the session is reused." />
          <Switch id="sFull" label="Read every page" flag="--full" value={s.full} onChange={(v) => S.set({ full: v })}
            hint="Page through every list to the end. Gets every record; slow on big sites." />
          <Switch id="sLive" label="Live updates" value={s.live} onChange={(v) => S.set({ live: v })}
            hint="Stream progress to SpacetimeDB so the Console updates while it works." />
          <Switch id="sHeaded" label="Show the browser" flag="--headed" value={s.headed} onChange={(v) => S.set({ headed: v })}
            hint="Watch the agent click through the site. Useful for checking a run." />
        </div>

        {/* actions on the old site */}
        <div className="set-block">
          <div className="set-row">
            <div className="set-text">
              <b id="roLabel">Read-only mode</b>
              <small>The Explorer always only reads. This controls write actions (book, cancel, update) once they’re connected.</small>
            </div>
            <button type="button" className="switch" id="sReadOnly" role="switch" aria-checked={s.readOnly}
              aria-labelledby="roLabel" onClick={() => S.set({ readOnly: !S.get().readOnly })}></button>
          </div>
          <div className={'ask' + (s.readOnly ? ' off' : '')} id="askBlock">
            <div className="set-text" style={{ marginTop: 14 }}>
              <b id="askLabel">Ask before acting</b>
            </div>
            <div className="seg" id="sAsk" role="radiogroup" aria-labelledby="askLabel" onKeyDown={askKeys}>
              {ASK_OPTS.map(([v, label]) => (
                <button key={v} ref={(el) => { askRefs.current[v] = el; }} type="button" role="radio" data-v={v}
                  aria-checked={s.askBeforeActing === v} disabled={s.readOnly} onClick={() => S.set({ askBeforeActing: v })}>
                  {label}
                </button>
              ))}
            </div>
            <p className="set-hint" id="askHint">{s.readOnly ? 'Read-only is on, so agents won’t change anything.' : ASK_HINT[s.askBeforeActing]}</p>
          </div>
        </div>

        {/* the command */}
        <div className="set-block">
          <div className="set-text">
            <b>Run with these settings</b>
            <small>Start exploring doesn’t launch the agents yet. Run this from the Facade folder to use these settings now.</small>
          </div>
          <pre className="cmd" id="runCmd">{cmd}</pre>
          <button type="button" className="link-btn" onClick={copy}>{copied}</button>
        </div>

        <div className="drawer-foot">
          <button type="button" className="link-btn" id="resetSettings" onClick={() => S.reset()}>Reset to defaults</button>
          <span className="saved" id="savedNote" aria-live="polite">{saved}</span>
          <button type="button" className="btn primary small" id="doneSettings" onClick={onClose}>Done</button>
        </div>
      </aside>
    </>
  );
}
