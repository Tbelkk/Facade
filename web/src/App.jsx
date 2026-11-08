// RESTore app: Dashboard and API pages.

import { useEffect, useMemo, useRef, useState } from 'react';
import Titlebar from './components/Titlebar.jsx';
import Intake from './components/Intake.jsx';
import Board from './components/Board.jsx';
import ApiView from './components/ApiView.jsx';
import { createDashboard } from './lib/dashboard.js';
import { createRunDriver, loadRecordedRun, replayRun } from './lib/runDriver.js';
import DevPanel from './components/DevPanel.jsx';
import Assistant from './components/Assistant.jsx';
import { API_BASE } from './lib/checkUrl.js';

// POST /runs body. The run uses the back end's defaults (the Settings drawer was removed).
function runBody(url) {
  return { url };
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

  const liveRun = useRef(null);   // { stop } while following a real run from the API

  const stopRun = () => {
    replay.current && replay.current.stop();
    replay.current = null;
    liveRun.current && liveRun.current.stop();
    liveRun.current = null;
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

  // Start exploring (the URL already passed the site check, see Intake.jsx): ask the RESTore API to run the
  // real agents on it (POST /runs), then follow their events live (GET /runs/{id}/events) into the tiles.
  const startExploring = async (checkedUrl) => {
    const u = new URL(checkedUrl);
    stopRun();
    setUrl(u.href);
    setHost(u.host);
    let id;
    try {
      const res = await fetch(`${API_BASE}/runs`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(runBody(u.href)) });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) { setPhase(body.detail || `Couldn’t start the agents (${res.status})`); return; }
      id = body.id;
    } catch {
      setPhase(`Couldn’t reach the RESTore API at ${API_BASE}. Start it from the RESTore folder: uvicorn api.main:app --port 8000`);
      return;
    }
    driver.begin({ site: u.href });
    setRunning(true);
    let after = 0, stopped = false, timer = null;
    const poll = async () => {
      if (stopped) return;
      try {
        const r = await fetch(`${API_BASE}/runs/${id}/events?after=${after}`);
        const d = await r.json();
        for (const e of d.events || []) driver.handle(e);
        after = d.next ?? after;
        if (d.status === 'failed') { stopped = true; setRunning(false); setPhase(`The run stopped: ${d.error || 'unknown error'}`); return; }
      } catch { /* API briefly unreachable: keep trying */ }
      timer = setTimeout(poll, 600);
    };
    liveRun.current = { stop() { stopped = true; clearTimeout(timer); } };
    poll();
  };

  // status line + clock
  useEffect(() => {
    const id = setInterval(() => {
      setSummary(dashboard.summary());
      if (!running) return;
      const s = Math.floor(driver.elapsed());
      setClock(`${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`);
      const active = dashboard.find('working');
      const tag = replaying ? 'Recorded run · ' : '';
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
        <Assistant store={driver.store} />
      </main>

      <ApiView store={driver.store} host={host} on={view === 'api'} />

      <DevPanel recorded={recorded} running={running} replaying={replaying} onRun={startReplay} onStop={stopRun} />
    </>
  );
}
