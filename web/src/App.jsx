// Facade app: Dashboard and API pages plus the Settings drawer.
// Same behavior as app/renderer/app.js.

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Titlebar from './components/Titlebar.jsx';
import Intake from './components/Intake.jsx';
import Board from './components/Board.jsx';
import ApiView from './components/ApiView.jsx';
import SettingsDrawer from './components/SettingsDrawer.jsx';
import ExplorerView from './run/ExplorerView.jsx';
import { createDashboard } from './lib/dashboard.js';
import { createMock } from './lib/mockRun.js';
import { facadeSettings } from './lib/settings.js';
import { useSettings } from './lib/hooks.js';

function normalize(input) {
  let s = input.trim();
  if (!/^[a-z][a-z0-9+.-]*:\/\//i.test(s)) s = 'https://' + s;
  try { const u = new URL(s); return /^https?:$/.test(u.protocol) ? u : null; } catch { return null; }
}

export default function App() {
  // One dashboard + mock for the app's lifetime. Swap the mock for real back-end events later.
  const dashboard = useMemo(() => createDashboard(), []);
  const mock = useMemo(() => createMock(dashboard, facadeSettings), [dashboard]);
  useEffect(() => () => mock.stop(), [mock]);
  // Expose the same globals the HTML app had, so back-end code can keep calling them.
  useEffect(() => { window.dashboard = dashboard; window.facadeSettings = facadeSettings; }, [dashboard]);

  const [view, setView] = useState('dashboard');
  const [url, setUrl] = useState('');
  const [running, setRunning] = useState(false);
  const [host, setHost] = useState('');
  const [phase, setPhase] = useState('Ready');
  const [clock, setClock] = useState('00:00');
  const [summary, setSummary] = useState(() => dashboard.summary());
  const [settingsOpen, setSettingsOpen] = useState(false);
  const settingsBtnRef = useRef(null);
  const settings = useSettings();

  // body classes the stylesheet uses
  useEffect(() => { document.body.classList.toggle('running', running); }, [running]);
  useEffect(() => { if (window.facade && window.facade.platform === 'darwin') document.body.classList.add('mac'); }, []);

  // Returns true when the link is bad, so the form can refocus the input.
  const onSubmit = () => {
    if (running) {
      mock.stop();
      setRunning(false);
      setPhase('Stopped');
      return false;
    }
    const u = normalize(url);
    if (!u) { setPhase('That doesn’t look like a website link'); return true; }
    setUrl(u.href);
    setHost(u.host);
    mock.start(u.href);   // ← swap for the real back end later
    setRunning(true);
    return false;
  };

  // status line + clock
  useEffect(() => {
    const id = setInterval(() => {
      setSummary(dashboard.summary());
      if (!running) return;
      const s = Math.floor(mock.elapsed());
      setClock(`${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`);
      const active = dashboard.find('working');
      setPhase(active
        ? `${active.name} working · ${host}`
        : dashboard.find('live') ? `Live · API + MCP ready for ${host}` : `Starting · ${host}`);
    }, 250);
    return () => clearInterval(id);
  }, [dashboard, mock, running, host]);

  const openSettings = () => setSettingsOpen(true);
  const closeSettings = useCallback(() => {
    setSettingsOpen((wasOpen) => {
      if (wasOpen) setTimeout(() => settingsBtnRef.current && settingsBtnRef.current.focus(), 0);
      return false;
    });
  }, []);

  const safety = {
    label: settings.readOnly ? 'Read-only' : settings.askBeforeActing === 'never' ? 'Can act' : 'Can act · asks first',
    acting: !settings.readOnly,
  };

  return (
    <>
      <div className="dither" aria-hidden="true"></div>

      <Titlebar view={view} onView={setView} />

      <main className={'app view' + (view === 'dashboard' ? ' on' : '')} id="view-dashboard">
        <Intake ref={settingsBtnRef} phase={phase} running={running} url={url} setUrl={setUrl}
          onSubmit={onSubmit} safety={safety} onOpenSettings={openSettings} />
        <Board dashboard={dashboard} working={summary.working} total={summary.total} clock={clock} />
      </main>

      <ExplorerView on={view === 'explorer'} />

      <ApiView host={host} on={view === 'api'} />

      <SettingsDrawer open={settingsOpen} onClose={closeSettings} />
    </>
  );
}
