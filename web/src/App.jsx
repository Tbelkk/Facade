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
import { createRunDriver, loadRecordedRun, replayRun } from './lib/runDriver.js';
import DevPanel from './components/DevPanel.jsx';
import { facadeSettings } from './lib/settings.js';
import { useSettings } from './lib/hooks.js';

function normalize(input) {
  let s = input.trim();
  if (!/^[a-z][a-z0-9+.-]*:\/\//i.test(s)) s = 'https://' + s;
  try { const u = new URL(s); return /^https?:$/.test(u.protocol) ? u : null; } catch { return null; }
}

export default function App() {
  // One dashboard + run driver for the app's lifetime. The driver turns real agent events into tile states.
  const dashboard = useMemo(() => createDashboard(), []);
  const driver = useMemo(() => createRunDriver(dashboard), [dashboard]);
  const replay = useRef(null);
  const [recorded, setRecorded] = useState(null);     // the recorded run in web/public/run/
  const [replaying, setReplaying] = useState(false);
  useEffect(() => { loadRecordedRun().then(setRecorded); }, []);
  useEffect(() => () => { replay.current && replay.current.stop(); driver.stop(); }, [driver]);
  // Globals: the HTML app's dashboard API, plus facadeEvent(evt) so a live back end can push real events.
  useEffect(() => {
    window.dashboard = dashboard; window.facadeSettings = facadeSettings;
    window.facadeEvent = (evt) => driver.handle(evt);
  }, [dashboard, driver]);

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
  const stopRun = () => {
    replay.current && replay.current.stop();
    replay.current = null;
    driver.stop();
    setRunning(false);
    setReplaying(false);
  };

  // Plays the recorded run through the same driver a live run will use.
  const startReplay = (speed = 1) => {
    if (!recorded) { setPhase('No recorded run in web/public/run/'); return; }
    stopRun();
    const r = replayRun(driver, recorded, { speed, onDone: () => setReplaying(false) });
    replay.current = r;
    let u = null; try { u = new URL(r.site); } catch { /* keep the typed link */ }
    if (u) { setUrl(u.href); setHost(u.host); }
    setReplaying(true);
    setRunning(true);
  };

  const onSubmit = () => {
    if (running) { stopRun(); setPhase('Stopped'); return false; }
    const u = normalize(url);
    if (!u) { setPhase('That doesn’t look like a website link'); return true; }
    setUrl(u.href);
    setHost(u.host);
    // A connected back end starts a real run and pushes events through window.facadeEvent.
    if (window.facade && typeof window.facade.runAgents === 'function') {
      driver.begin({ site: u.href });
      window.facade.runAgents(u.href);
      setRunning(true);
      return false;
    }
    // No back end yet: show the recorded run so the dashboard still demonstrates the real flow.
    startReplay(1);
    return false;
  };

  // status line + clock
  useEffect(() => {
    const id = setInterval(() => {
      setSummary(dashboard.summary());
      if (!running) return;
      const s = Math.floor(driver.elapsed());
      setClock(`${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`);
      const active = dashboard.find('working');
      const tag = replaying || (replay.current && !window.facade?.runAgents) ? 'Recorded run · ' : '';
      setPhase(tag + (active
        ? `${active.name} working · ${host}`
        : dashboard.find('live') ? `Live · API + MCP ready for ${host}` : `Starting · ${host}`));
    }, 250);
    return () => clearInterval(id);
  }, [dashboard, driver, running, replaying, host]);

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
        <Board dashboard={dashboard} store={driver.store} working={summary.working} total={summary.total} clock={clock} />
      </main>

      <ExplorerView on={view === 'explorer'} />

      <ApiView store={driver.store} host={host} on={view === 'api'} />

      <SettingsDrawer open={settingsOpen} onClose={closeSettings} />

      <DevPanel recorded={recorded} running={running} replaying={replaying} onRun={startReplay} onStop={stopRun} />
    </>
  );
}
