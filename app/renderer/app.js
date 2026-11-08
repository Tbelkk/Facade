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

  // Settings: not wired up yet.
  $('#settingsBtn').addEventListener('click', () => {});

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
      : tiles.every((t) => ['done', 'live'].includes(t.dataset.status)) ? `Live · API + MCP ready for ${host}` : `Starting · ${host}`;
  }, 250);

  $('#url').focus();
})();
