import { forwardRef, useEffect, useRef } from 'react';
import { GearIcon, GlobeIcon } from './Icons.jsx';

const Intake = forwardRef(function Intake({ phase, running, url, setUrl, onSubmit, safety, onOpenSettings }, settingsBtnRef) {
  const urlRef = useRef(null);
  useEffect(() => { urlRef.current && urlRef.current.focus(); }, []);

  const submit = (e) => {
    e.preventDefault();
    const bad = onSubmit();
    if (bad) urlRef.current.focus();
  };

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

      <form className="source" id="runForm" autoComplete="off" onSubmit={submit}>
        <label className="url gb">
          <span className="sr">Website link</span>
          <GlobeIcon />
          <input ref={urlRef} id="url" type="text" spellCheck="false" placeholder="https://old-clinic-2005.com" required
            value={url} readOnly={running} onChange={(e) => setUrl(e.target.value)} />
        </label>
        <button type="submit" className="btn primary" id="runBtn">{running ? 'Stop' : 'Run agents'}</button>
      </form>
    </section>
  );
});

export default Intake;
