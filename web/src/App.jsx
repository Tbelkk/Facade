// Facade app: Dashboard and API pages plus the Settings drawer.
// Same behavior as app/renderer/app.js.

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Titlebar from './components/Titlebar.jsx';
import Intake from './components/Intake.jsx';
import Board from './components/Board.jsx';
import ApiView from './components/ApiView.jsx';
import SettingsDrawer from './components/SettingsDrawer.jsx';
import { createDashboard } from './lib/dashboard.js';
import { createMock } from './lib/mockRun.js';
import { facadeSettings } from './lib/settings.js';
import { useSettings } from './lib/hooks.js';

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

  // Start exploring: stub until the Explorer back end can be called from here.
  // The URL has already passed the fit-check and the authorization box (see Intake.jsx).
  const startExploring = (checkedUrl) => {
    const u = new URL(checkedUrl);
    setHost(u.host);
    console.info('[facade] start exploring (stub):', checkedUrl);
    mock.start(checkedUrl);   // ← swap for the real Explorer start call later
    setRunning(true);
  };
  const stopRun = () => {
    mock.stop();
    setRunning(false);
    setPhase('Stopped');
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
          onStart={startExploring} onStop={stopRun} safety={safety} onOpenSettings={openSettings} />
        <Board dashboard={dashboard} working={summary.working} total={summary.total} clock={clock} />
      </main>

      <ApiView host={host} on={view === 'api'} />

      <SettingsDrawer open={settingsOpen} onClose={closeSettings} url={url} />
    </>
  );
}
