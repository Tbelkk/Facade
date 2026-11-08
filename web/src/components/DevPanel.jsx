// TEMPORARY dev tool: replays a recorded agent run through the dashboard as if it were live.
// Shown in `npm run dev`, or in any build with ?dev in the address. Delete this file (and its line in
// App.jsx) once the back end pushes live events through window.facadeEvent.

import { useState } from 'react';

const SPEEDS = [1, 2, 4];

export default function DevPanel({ recorded, running, replaying, onRun, onStop }) {
  const show = import.meta.env.DEV || /[?&]dev\b/.test(window.location.search);
  const [speed, setSpeed] = useState(1);
  const [open, setOpen] = useState(true);
  if (!show) return null;

  const pages = recorded ? recorded.runLog.filter((l) => l.kind === 'page').length : 0;
  const eps = recorded && recorded.ops ? recorded.ops.operations.length : 0;

  return (
    <aside className={'dev-panel' + (open ? '' : ' min')} aria-label="Developer tools">
      <button type="button" className="dev-head" onClick={() => setOpen(!open)}>DEV · test run {open ? '–' : '+'}</button>
      {open && (
        <div className="dev-body">
          {recorded
            ? <p>Recorded run: {pages} pages, {eps} endpoints{recorded.model && recorded.model.site ? ` · ${recorded.model.site.replace(/^https?:\/\//, '')}` : ''}</p>
            : <p>No recorded run found in <code>web/public/run/</code></p>}
          <div className="dev-row">
            {SPEEDS.map((x) => (
              <button type="button" key={x} className={'dev-chip' + (x === speed ? ' on' : '')} onClick={() => setSpeed(x)}>{x}×</button>
            ))}
          </div>
          <div className="dev-row">
            <button type="button" className="dev-btn" disabled={!recorded} onClick={() => onRun(speed)}>
              {replaying ? 'Restart test' : 'Run test'}
            </button>
            {running && <button type="button" className="dev-btn ghost" onClick={onStop}>Stop</button>}
          </div>
        </div>
      )}
    </aside>
  );
}
