// Link box + Settings button + dashboard status line.
(function () {
  const $ = (s) => document.querySelector(s);
  if (window.facade && window.facade.platform === 'darwin') document.body.classList.add('mac');

  let running = false;
  let host = '';

  function normalize(input) {
    let s = input.trim();
    if (!/^[a-z][a-z0-9+.-]*:\/\//i.test(s)) s = 'https://' + s;
    try { const u = new URL(s); return /^https?:$/.test(u.protocol) ? u : null; } catch { return null; }
  }

  function setRunning(on) {
    running = on;
    document.body.classList.toggle('running', on);
    $('#runBtn').textContent = on ? 'Stop' : 'Run agents';
    $('#url').readOnly = on;
  }

  $('#runForm').addEventListener('submit', (e) => {
    e.preventDefault();
    if (running) {
      window.mock.stop();
      setRunning(false);
      $('#phase').textContent = 'Stopped';
      return;
    }
    const u = normalize($('#url').value);
    if (!u) { $('#phase').textContent = 'That doesn’t look like a website link'; $('#url').focus(); return; }
    $('#url').value = u.href;
    host = u.host;
    window.mock.start(u.href);   // ← swap for the real back end later
    setRunning(true);
  });

  /* ---------------- settings: safety ---------------- */
  const S = window.facadeSettings;
  const drawer = $('#settings'), scrim = $('#scrim');
  const ASK_HINT = {
    always: 'Every change waits for your OK.',
    destructive: 'Cancels, deletes and overwrites wait for your OK. Adds and lookups go ahead.',
    never: 'Agents act on their own. Every action is still verified and logged.',
  };
  let savedTimer = null;

  function paintRange(input) {
    const min = +input.min, max = +input.max;
    input.style.setProperty('--fill', `${((+input.value - min) / (max - min)) * 100}%`);
  }

  function renderSettings() {
    const s = S.get();
    $('#sReadOnly').setAttribute('aria-checked', String(s.readOnly));
    document.querySelectorAll('#sAsk button').forEach((b) => {
      b.setAttribute('aria-checked', String(b.dataset.v === s.askBeforeActing));
      b.disabled = s.readOnly;
    });
    $('#askBlock').classList.toggle('off', s.readOnly);
    $('#askHint').textContent = s.readOnly ? 'Read-only is on, so agents won’t change anything.' : ASK_HINT[s.askBeforeActing];
    $('#sPpm').value = s.pagesPerMinute; $('#oPpm').textContent = `${s.pagesPerMinute} / min`;
    $('#sPause').value = s.clickPauseSec; $('#oPause').textContent = `${s.clickPauseSec.toFixed(1)} s`;
    $('#sMaxPages').value = s.maxPages;
    $('#sMaxTime').value = s.maxRunMinutes;
    ['#sPpm', '#sPause'].forEach((id) => paintRange($(id)));

    const chip = $('#safetyChip');
    chip.textContent = s.readOnly ? 'Read-only' : s.askBeforeActing === 'never' ? 'Can act' : 'Can act · asks first';
    chip.classList.toggle('acting', !s.readOnly);
  }

  // set slider/number ranges from the store's limits
  for (const el of document.querySelectorAll('#settings [data-key]')) {
    const [min, max, step] = S.LIMITS[el.dataset.key];
    Object.assign(el, { min, max, step });
  }

  function saved() {
    $('#savedNote').textContent = 'Saved';
    clearTimeout(savedTimer);
    savedTimer = setTimeout(() => { $('#savedNote').textContent = ''; }, 1400);
  }
  S.onChange(() => { renderSettings(); saved(); });

  $('#sReadOnly').addEventListener('click', () => S.set({ readOnly: !S.get().readOnly }));
  document.querySelectorAll('#sAsk button').forEach((b) => b.addEventListener('click', () => S.set({ askBeforeActing: b.dataset.v })));
  $('#sAsk').addEventListener('keydown', (e) => {          // arrow keys move between the three options
    if (!['ArrowLeft', 'ArrowRight'].includes(e.key) || S.get().readOnly) return;
    const opts = ['always', 'destructive', 'never'];
    const i = opts.indexOf(S.get().askBeforeActing) + (e.key === 'ArrowRight' ? 1 : -1);
    if (i >= 0 && i < opts.length) { S.set({ askBeforeActing: opts[i] }); $(`#sAsk [data-v="${opts[i]}"]`).focus(); }
  });
  for (const id of ['#sPpm', '#sPause']) {
    $(id).addEventListener('input', (e) => S.set({ [e.target.dataset.key]: +e.target.value }));
  }
  for (const id of ['#sMaxPages', '#sMaxTime']) {
    $(id).addEventListener('change', (e) => S.set({ [e.target.dataset.key]: +e.target.value }));
  }
  $('#resetSettings').addEventListener('click', () => S.reset());

  function openSettings() {
    renderSettings();
    drawer.inert = false;
    drawer.setAttribute('aria-hidden', 'false');
    drawer.classList.add('open');
    scrim.hidden = false;
    setTimeout(() => $('#sReadOnly').focus(), 60);
  }
  function closeSettings() {
    if (!drawer.classList.contains('open')) return;
    drawer.classList.remove('open');
    drawer.setAttribute('aria-hidden', 'true');
    drawer.inert = true;
    scrim.hidden = true;
    $('#settingsBtn').focus();
  }
  $('#settingsBtn').addEventListener('click', openSettings);
  $('#closeSettings').addEventListener('click', closeSettings);
  $('#doneSettings').addEventListener('click', closeSettings);
  scrim.addEventListener('click', closeSettings);
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeSettings(); });
  renderSettings();

  // status line + clock
  setInterval(() => {
    const { working, total } = window.dashboard.summary();
    $('#working').textContent = `${working} of ${total} working`;
    if (!running) return;
    const s = Math.floor(window.mock.elapsed());
    $('#clock').textContent = `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
    const tiles = [...document.querySelectorAll('.tile')];
    const active = tiles.find((t) => t.dataset.status === 'working');
    $('#phase').textContent = active
      ? `${active.querySelector('b').textContent} working · ${host}`
      : tiles.some((t) => t.dataset.status === 'live') ? `Live · API + MCP ready for ${host}` : `Starting · ${host}`;
  }, 250);

  // Dashboard / API pages
  function showView(name) {
    document.querySelectorAll('.tabs-nav button').forEach((b) => b.setAttribute('aria-selected', String(b.dataset.view === name)));
    document.querySelectorAll('.view').forEach((v) => v.classList.toggle('on', v.id === `view-${name}`));
    if (name === 'api') window.apiView.setSource(host);
  }
  document.querySelectorAll('.tabs-nav button').forEach((b) => b.addEventListener('click', () => showView(b.dataset.view)));
  window.apiView.setSource(null);

  $('#url').focus();
})();
