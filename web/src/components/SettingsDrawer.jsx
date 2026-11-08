// Settings drawer: same markup, behavior and store as app/renderer (settings.js + app.js).

import { useEffect, useRef, useState } from 'react';
import { facadeSettings as S } from '../lib/settings.js';
import { useSettings } from '../lib/hooks.js';
import { CloseIcon } from './Icons.jsx';

const ASK_HINT = {
  always: 'Every change waits for your OK.',
  destructive: 'Cancels, deletes and overwrites wait for your OK. Adds and lookups go ahead.',
  never: 'Agents act on their own. Every action is still verified and logged.',
};
const ASK_OPTS = [['always', 'Always'], ['destructive', 'Destructive'], ['never', 'Never']];

function Range({ id, k, value, onInput }) {
  const [min, max, step] = S.LIMITS[k];
  const fillPct = `${((value - min) / (max - min)) * 100}%`;
  return (
    <input type="range" id={id} data-key={k} min={min} max={max} step={step} value={value}
      style={{ '--fill': fillPct }} onChange={(e) => onInput(+e.target.value)} />
  );
}

// Number inputs save on change (blur/Enter), like the original.
function NumberField({ id, k, value }) {
  const [min, max, step] = S.LIMITS[k];
  const [draft, setDraft] = useState(String(value));
  useEffect(() => { setDraft(String(value)); }, [value]);
  const commit = () => { S.set({ [k]: +draft }); setDraft(String(S.get()[k])); };
  return (
    <input type="number" id={id} data-key={k} min={min} max={max} step={step} value={draft}
      onChange={(e) => setDraft(e.target.value)} onBlur={commit}
      onKeyDown={(e) => { if (e.key === 'Enter') commit(); }} />
  );
}

export default function SettingsDrawer({ open, onClose }) {
  const s = useSettings();
  const drawerRef = useRef(null);
  const readOnlyRef = useRef(null);
  const askRefs = useRef({});
  const [saved, setSaved] = useState('');
  const savedTimer = useRef(null);
  const first = useRef(true);

  // "Saved" flash after every change
  useEffect(() => {
    if (first.current) { first.current = false; return; }
    setSaved('Saved');
    clearTimeout(savedTimer.current);
    savedTimer.current = setTimeout(() => setSaved(''), 1400);
  }, [s]);
  useEffect(() => () => clearTimeout(savedTimer.current), []);

  // inert + focus the first control when it opens
  useEffect(() => {
    const el = drawerRef.current;
    if (open) { el.inert = false; const t = setTimeout(() => readOnlyRef.current && readOnlyRef.current.focus(), 60); return () => clearTimeout(t); }
    el.inert = true;
  }, [open]);

  // Escape closes
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  const askKeys = (e) => {   // arrow keys move between the three options
    if (!['ArrowLeft', 'ArrowRight'].includes(e.key) || S.get().readOnly) return;
    const opts = ASK_OPTS.map((o) => o[0]);
    const i = opts.indexOf(S.get().askBeforeActing) + (e.key === 'ArrowRight' ? 1 : -1);
    if (i >= 0 && i < opts.length) { S.set({ askBeforeActing: opts[i] }); askRefs.current[opts[i]] && askRefs.current[opts[i]].focus(); }
  };

  return (
    <>
      <div className="scrim" id="scrim" hidden={!open} onClick={onClose}></div>
      <aside ref={drawerRef} className={'drawer' + (open ? ' open' : '')} id="settings" role="dialog" aria-modal="true"
        aria-labelledby="settingsTitle" aria-hidden={!open}>
        <div className="drawer-head">
          <div>
            <div className="eyebrow"><span>Settings</span></div>
            <h2 className="drawer-title" id="settingsTitle">Safety</h2>
            <p className="drawer-sub">What the agents are allowed to do on the old site.</p>
          </div>
          <button type="button" className="icon-btn" id="closeSettings" aria-label="Close settings" onClick={onClose}>
            <CloseIcon />
          </button>
        </div>

        {/* read-only */}
        <div className="set-block">
          <div className="set-row">
            <div className="set-text">
              <b id="roLabel">Read-only mode</b>
              <small>Explore and copy data only. Agents never submit a form or change anything.</small>
            </div>
            <button ref={readOnlyRef} type="button" className="switch" id="sReadOnly" role="switch" aria-checked={s.readOnly}
              aria-labelledby="roLabel" onClick={() => S.set({ readOnly: !S.get().readOnly })}></button>
          </div>
        </div>

        {/* ask before acting */}
        <div className={'set-block' + (s.readOnly ? ' off' : '')} id="askBlock">
          <div className="set-text">
            <b id="askLabel">Ask before acting</b>
            <small>When agents are allowed to change data (book, cancel, update), when do they need your approval?</small>
          </div>
          <div className="seg" id="sAsk" role="radiogroup" aria-labelledby="askLabel" onKeyDown={askKeys}>
            {ASK_OPTS.map(([v, label]) => (
              <button key={v} ref={(el) => { askRefs.current[v] = el; }} type="button" role="radio" data-v={v}
                aria-checked={s.askBeforeActing === v} disabled={s.readOnly} onClick={() => S.set({ askBeforeActing: v })}>
                {label}
              </button>
            ))}
          </div>
          <p className="set-hint" id="askHint">
            {s.readOnly ? 'Read-only is on, so agents won’t change anything.' : ASK_HINT[s.askBeforeActing]}
          </p>
        </div>

        {/* speed */}
        <div className="set-block">
          <div className="set-text">
            <b>Speed limit</b>
            <small>Go easy on a fragile 2005 server.</small>
          </div>
          <label className="range-row">
            <span>Pages per minute</span>
            <Range id="sPpm" k="pagesPerMinute" value={s.pagesPerMinute} onInput={(v) => S.set({ pagesPerMinute: v })} />
            <output id="oPpm">{s.pagesPerMinute} / min</output>
          </label>
          <label className="range-row">
            <span>Pause between clicks</span>
            <Range id="sPause" k="clickPauseSec" value={s.clickPauseSec} onInput={(v) => S.set({ clickPauseSec: v })} />
            <output id="oPause">{s.clickPauseSec.toFixed(1)} s</output>
          </label>
        </div>

        {/* stop limits */}
        <div className="set-block">
          <div className="set-text">
            <b>Stop limits</b>
            <small>Agents stop when either limit is reached.</small>
          </div>
          <div className="num-grid">
            <label className="num"><span>Max pages to explore</span><div><NumberField id="sMaxPages" k="maxPages" value={s.maxPages} /><em>pages</em></div></label>
            <label className="num"><span>Max run time</span><div><NumberField id="sMaxTime" k="maxRunMinutes" value={s.maxRunMinutes} /><em>min</em></div></label>
          </div>
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
