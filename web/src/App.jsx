// RESTore app: Dashboard and API pages.

import { useEffect, useMemo, useRef, useState } from 'react';
import Titlebar from './components/Titlebar.jsx';
import Intake from './components/Intake.jsx';
import Board from './components/Board.jsx';
import ApiView from './components/ApiView.jsx';
import { createDashboard } from './lib/dashboard.js';
import { createRunDriver, loadRecordedRun, replayRun } from './lib/runDriver.js';
import DevPanel from './components/DevPanel.jsx';

export default function App() {
  // One dashboard + run driver for the app's lifetime. The driver turns real agent events into tile states.
  const dashboard = useMemo(() => createDashboard(), []);
  const driver = useMemo(() => createRunDriver(dashboard), [dashboard]);
  const replay = useRef(null);
  const [recorded, setRecorded] = useState(null);     // the recorded run in web/public/run/
  const [replaying, setReplaying] = useState(false);
  useEffect(() => { loadRecordedRun().then(setRecorded); }, []);
  useEffect(() => () => { replay.current && replay.current.stop(); driver.stop(); }, [driver]);
  // Globals: window.dashboard, plus facadeEvent(evt) so a live back end can push real events.
  useEffect(() => {
    window.dashboard = dashboard;
    window.facadeEvent = (evt) => driver.handle(evt);
  }, [dashboard, driver]);

  const [view, setView] = useState('dashboard');
  const [url, setUrl] = useState('');
  const [running, setRunning] = useState(false);
  const [host, setHost] = useState('');
  const [phase, setPhase] = useState('Ready');
  const [clock, setClock] = useState('00:00');
  const [summary, setSummary] = useState(() => dashboard.summary());

  // body classes the stylesheet uses
  useEffect(() => { document.body.classList.toggle('running', running); }, [running]);

  const stopRun = () => {
    replay.current && replay.current.stop();
    replay.current = null;
    driver.stop();
    setRunning(false);
    setReplaying(false);
    setPhase('Stopped');
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

  // Start exploring: the URL has already passed the fit-check and the authorization box (see Intake.jsx).
  // A real run will be started here and push events through window.facadeEvent
  // (call driver.begin({ site }) first). Until then the recorded run plays so the dashboard still shows the real flow.
  const startExploring = (checkedUrl) => {
    const u = new URL(checkedUrl);
    setHost(u.host);
    startReplay(1);
  };

  // status line + clock
  useEffect(() => {
    const id = setInterval(() => {
      setSummary(dashboard.summary());
      if (!running) return;
      const s = Math.floor(driver.elapsed());
      setClock(`${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`);
      const active = dashboard.find('working');
      const tag = replaying || replay.current ? 'Recorded run · ' : '';
      setPhase(tag + (active
        ? `${active.name} working · ${host}`
        : dashboard.find('live') ? `Live · API + MCP ready for ${host}` : `Starting · ${host}`));
    }, 250);
    return () => clearInterval(id);
  }, [dashboard, driver, running, replaying, host]);

  return (
    <>
      <div className="dither" aria-hidden="true"></div>

      <Titlebar view={view} onView={setView} />

      <main className={'app view' + (view === 'dashboard' ? ' on' : '')} id="view-dashboard">
        <Intake phase={phase} running={running} url={url} setUrl={setUrl}
          onStart={startExploring} onStop={stopRun} />
        <Board dashboard={dashboard} store={driver.store} working={summary.working} total={summary.total} clock={clock} />
      </main>

      <ApiView store={driver.store} host={host} on={view === 'api'} />

      <DevPanel recorded={recorded} running={running} replaying={replaying} onRun={startReplay} onStop={stopRun} />
    </>
  );
}
