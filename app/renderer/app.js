// Facade desktop app: renderer.
// Talks to the Python core over ws://127.0.0.1:8765 (FACADE-TEAM-PLAN §6.5).
// When the core isn't running, it falls back to demo data so the UI still works.
(function () {
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const store = {
    get(k, d) { try { return localStorage.getItem(k) ?? d; } catch { return d; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch {} },
  };

  if (window.facade && window.facade.platform === 'darwin') document.body.classList.add('mac');

  /* ---------------- demo data ---------------- */
  const APPS = [
    { key: 'OpenDental.exe', name: 'Open Dental', initials: 'OD', color: '#2A7F7B', mode: 'Structure', screens: 14, status: 'Modernized',
      source: ['#2E7D7A', '#F0F0F0', '#D4D0C8', '#000080', '#FFFFFF'], tokens: ['#2A7F7B', '#FAFBFB', '#EEF2F2', '#1F4FA8', '#1B2524'],
      traits: 'Teal module headers, dense data grids, icon toolbar on the left, compact spacing.' },
    { key: 'mmc.exe', name: 'Event Viewer', initials: 'EV', color: '#3B5B8C', mode: 'Structure + Vision', screens: 6, status: 'Modernized',
      source: ['#D4D0C8', '#FFFFFF', '#0A246A', '#808080', '#000000'], tokens: ['#3B5B8C', '#FBFCFE', '#EDF1F7', '#C2410C', '#16202E'],
      traits: 'Classic MMC chrome, three-pane layout, severity icons, tree navigation on the left.' },
    { key: 'notepad.exe', name: 'Notepad', initials: 'N', color: '#64748B', mode: 'Assist', screens: 1, status: 'Idle',
      source: ['#FFFFFF', '#F0F0F0', '#000000'], tokens: ['#475569', '#FFFFFF', '#F1F5F9'],
      traits: 'Single text area, menu bar, no custom-drawn regions.' },
  ];

  const MODES = {
    faithful: 'Same positions and layout as the original. Only the rendering is modernized. Best for people with muscle memory.',
    enhanced: 'Same structure, grouped into clean sections, clutter hidden and labels in plain English. Best for most people.',
    reimagined: 'Nemotron restructures each screen around tasks. Coming soon.',
  };

  const log = [
    { t: '18:42:10', model: 'nano-omni', purpose: 'Label screen', ms: 2140, summary: 'Open Dental › Family: 214 nodes, 4 groups, confidence 0.86' },
    { t: '18:42:13', model: 'nano-omni', purpose: 'Style profile', ms: 1830, summary: 'Teal headers, dense grids, compact density' },
    { t: '18:44:02', model: 'super-120b', purpose: 'Plan task', ms: 1240, summary: '5 steps: read schedule → find unconfirmed → approve → SMS → mark sent' },
    { t: '18:44:05', model: 'nano-omni', purpose: 'Visual read', ms: 980, summary: 'Appointment grid: 4 unconfirmed for 11/08' },
  ];

  /* ---------------- navigation ---------------- */
  function show(view) {
    $$('.nav button').forEach((b) => b.classList.toggle('on', b.dataset.view === view));
    $$('.view').forEach((v) => v.classList.toggle('on', v.id === 'view-' + view));
    store.set('facade.view', view);
  }
  $$('.nav button').forEach((b) => b.addEventListener('click', () => show(b.dataset.view)));

  /* ---------------- render: apps ---------------- */
  function appIcon(a) { return `<div class="app-ic" style="background:${a.color}">${esc(a.initials)}</div>`; }

  $('#homeApps').innerHTML = APPS.map((a) => `
    <li>${appIcon(a)}
      <div class="app-meta"><b>${esc(a.name)}</b><small>${esc(a.mode)} mode · ${a.screens} screen${a.screens === 1 ? '' : 's'} cached</small></div>
      <span class="pill ${a.status === 'Idle' ? 'idle' : ''}">${esc(a.status)}</span>
    </li>`).join('');

  $('#appsGrid').innerHTML = APPS.map((a) => `
    <div class="card app-card">
      <div class="top">${appIcon(a)}<div><b>${esc(a.name)}</b><small>${esc(a.key)} · ${esc(a.mode)}</small></div>
        <span class="pill ${a.status === 'Idle' ? 'idle' : ''}">${esc(a.status)}</span></div>
      <div class="swatches">
        <span>Original</span><div class="row src">${a.source.map((c) => `<i style="background:${c}" title="${c}"></i>`).join('')}</div>
        <span>Facade</span><div class="row">${a.tokens.map((c) => `<i style="background:${c}" title="${c}"></i>`).join('')}</div>
      </div>
      <p class="traits">${esc(a.traits)}</p>
    </div>`).join('');

  /* ---------------- render: activity ---------------- */
  function renderLog(flashFirst) {
    $('#logBody').innerHTML = log.slice().reverse().map((r, i) => `
      <tr class="${flashFirst && i === 0 ? 'new' : ''}"><td>${esc(r.t)}</td><td>${esc(r.model)}</td><td>${esc(r.purpose)}</td><td>${Number(r.ms).toLocaleString()} ms</td><td>${esc(r.summary)}</td></tr>`).join('');
  }
  function addLog(model, purpose, ms, summary) {
    log.push({ t: new Date().toTimeString().slice(0, 8), model, purpose, ms, summary });
    renderLog(true);
  }
  renderLog(false);

  /* ---------------- power + mode ---------------- */
  let mode = store.get('facade.mode', 'enhanced');
  let on = store.get('facade.on', '1') === '1';

  function renderPower() {
    $('#power').setAttribute('aria-checked', String(on));
    $('#powerLabel').textContent = on ? 'Facade is ON' : 'Facade is OFF';
    $('#powerSub').textContent = on ? 'Originals are never changed' : 'Showing original apps';
    document.body.classList.toggle('off', !on);
    $$('#homeApps .pill').forEach((p, i) => { if (APPS[i].status !== 'Idle') p.textContent = on ? 'Modernized' : 'Original'; });
  }
  function renderMode() {
    $$('#modeSeg button').forEach((b) => b.setAttribute('aria-checked', String(b.dataset.mode === mode)));
    $('#modeDesc').textContent = MODES[mode];
  }
  $('#power').addEventListener('click', () => {
    on = !on; store.set('facade.on', on ? '1' : '0'); renderPower();
    send({ type: 'set_mode', mode: on ? mode : 'off' });
  });
  $$('#modeSeg button').forEach((b) => b.addEventListener('click', () => {
    if (b.disabled) return;
    mode = b.dataset.mode; store.set('facade.mode', mode); renderMode();
    if (on) send({ type: 'set_mode', mode });
  }));
  renderPower(); renderMode();

  /* ---------------- core connection ---------------- */
  let ws = null, retry = null;
  const coreUrl = $('#coreUrl');
  coreUrl.value = store.get('facade.core', 'ws://127.0.0.1:8765');

  function setCore(state) {
    const el = $('#coreStatus');
    el.dataset.state = state;
    el.querySelector('span').textContent = state === 'live' ? 'Core connected' : state === 'connecting' ? 'Connecting…' : 'Demo mode';
    $('#connText').textContent = state === 'live' ? 'Connected to ' + coreUrl.value : 'Not connected. Showing demo data.';
  }
  const live = () => ws && ws.readyState === WebSocket.OPEN;
  function send(msg) { if (live()) ws.send(JSON.stringify({ ts: Math.floor(Date.now() / 1000), ...msg })); }

  function connect(manual) {
    clearTimeout(retry);
    if (ws) { ws.onclose = null; ws.close(); }
    if (manual) setCore('connecting');
    try { ws = new WebSocket(coreUrl.value); } catch { setCore('demo'); return; }
    ws.onopen = () => { setCore('live'); send({ type: 'set_mode', mode: on ? mode : 'off' }); };
    ws.onclose = () => { setCore('demo'); retry = setTimeout(connect, 5000); };
    ws.onerror = () => {};
    ws.onmessage = (e) => { try { handle(JSON.parse(e.data)); } catch {} };
  }
  $('#reconnect').addEventListener('click', () => { store.set('facade.core', coreUrl.value.trim()); connect(true); });

  function handle(m) {
    switch (m.type) {
      case 'nemotron_log': addLog(m.model, m.purpose, m.ms, m.summary); break;
      case 'plan_update': renderPlan(m.steps.map((s) => ({ text: s.text, status: s.status }))); break;
      case 'approval_request': askApproval(m.summary, (ok) => send({ type: 'approval_response', approval_id: m.approval_id, approved: ok })); break;
      case 'task_done': finish(m.summary); break;
    }
  }

  /* ---------------- agent ---------------- */
  let busy = false;
  let approvalCb = null;

  function renderPlan(steps) {
    $('#planCard').hidden = false;
    $('#planSteps').innerHTML = steps.map((s) => `<li class="${s.status}"><span class="dot"></span><span>${esc(s.text)}</span></li>`).join('');
  }
  function setBadge(text, cls) { const b = $('#planBadge'); b.textContent = text; b.className = 'badge ' + (cls || ''); }
  function askApproval(text, cb) {
    approvalCb = cb;
    $('#approvalText').textContent = text;
    $('#approval').hidden = false;
    setBadge('Waiting for you', 'wait');
  }
  function answer(ok) {
    $('#approval').hidden = true;
    setBadge(ok ? 'Running' : 'Stopped', ok ? '' : 'fail');
    const cb = approvalCb; approvalCb = null; if (cb) cb(ok);
  }
  $('#approve').addEventListener('click', () => answer(true));
  $('#deny').addEventListener('click', () => answer(false));

  function finish(summary, failed) {
    busy = false; $('#agentRun').disabled = false;
    setBadge(failed ? 'Stopped' : 'Done', failed ? 'fail' : 'done');
    $('#planResult').hidden = false;
    $('#planResult').textContent = summary;
    if (!failed) { const el = $('#mTasks'); el.textContent = (parseInt(el.textContent, 10) + 1).toString(); }
  }

  function run(text) {
    text = text.trim();
    if (!text || busy) return;
    show('agent');
    $('#agentInput').value = text;
    $('#planTitle').textContent = text;
    $('#planResult').hidden = true;
    $('#approval').hidden = true;
    setBadge('Planning…');
    busy = true; $('#agentRun').disabled = true;

    if (live()) { renderPlan([{ text: 'Sending to Facade core…', status: 'running' }]); send({ type: 'command', text }); return; }
    demo(text);
  }

  // Demo agent: a believable plan, step by step, with an approval for risky steps.
  function demoPlan(text) {
    const t = text.toLowerCase();
    if (/(text|sms|remind)/.test(t)) return {
      steps: ['Open the appointment book for tomorrow', 'Read the schedule (vision · custom-drawn grid)', 'Find unconfirmed appointments',
        { text: 'Send 4 reminder texts via Twilio', approve: 'Send 4 SMS reminders to patients with unconfirmed appointments tomorrow?' }, 'Mark reminders sent in the real app'],
      result: 'Texted 4 patients and marked each appointment “Reminder sent” in Open Dental.' };
    if (/(shut ?down|crash|why)/.test(t)) return {
      steps: ['Open Event Viewer › System log', 'Filter for events 41, 6008 and 1074 yesterday', 'Read the matching events', 'Explain the cause in plain English'],
      result: 'Event 41 (Kernel-Power) at 3:12 PM with no clean shutdown first: the PC lost power or was held off by the power button. No update or user restart was logged.' };
    if (/(add|new patient)/.test(t)) return {
      steps: ['Search for an existing patient with this name', 'Validate the address with Smarty', 'Open “Add patient”',
        { text: 'Fill in name and address', approve: 'Create a new patient record for Jane Doe?' }, 'Read back every field to verify'],
      result: 'Added Jane Doe (no duplicate found). Address standardized to 123 Main St, Dallas, TX 75201.' };
    return {
      steps: ['Read the current screen', 'Find the controls this task needs', 'Carry out the task', 'Verify the result with a read-back'],
      result: 'Done. Every change was read back from the real app and logged in Activity.' };
  }

  function demo(text) {
    const plan = demoPlan(text);
    const steps = plan.steps.map((s) => (typeof s === 'string' ? { text: s } : s)).map((s) => ({ ...s, status: 'pending' }));
    renderPlan(steps);
    const wait = (ms) => new Promise((r) => setTimeout(r, ms));

    (async () => {
      await wait(700);
      addLog('super-120b', 'Plan task', 900 + Math.round(Math.random() * 700), `${steps.length} steps for “${text}”`);
      setBadge('Running');
      for (const s of steps) {
        s.status = 'running'; renderPlan(steps);
        await wait(900 + Math.random() * 600);
        if (s.approve) {
          s.status = 'waiting'; renderPlan(steps);
          const ok = await new Promise((r) => askApproval(s.approve, r));
          if (!ok) { s.status = 'failed'; renderPlan(steps); finish('Stopped: you denied this step. Nothing was changed.', true); return; }
          s.status = 'running'; renderPlan(steps);
          await wait(700);
        }
        s.status = 'done'; renderPlan(steps);
        if (/read|find|filter|search/i.test(s.text)) addLog('nano-omni', 'Read screen', 700 + Math.round(Math.random() * 1400), s.text);
      }
      finish(plan.result);
    })();
  }

  $('#agentForm').addEventListener('submit', (e) => { e.preventDefault(); run($('#agentInput').value); });
  $('#quickForm').addEventListener('submit', (e) => { e.preventDefault(); run($('#quickInput').value); $('#quickInput').value = ''; });
  $$('#suggest button').forEach((b) => b.addEventListener('click', () => run(b.textContent)));

  /* ---------------- start ---------------- */
  show(store.get('facade.view', 'home'));
  connect();
})();
