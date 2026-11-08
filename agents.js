// Facade Agents: a live network of agents passing work to each other.
//   • Tasks stream in from the screen edges along dotted lanes to an agent.
//   • Agents hand work to each other along links, then deliver results to the hub card.
//   • Cursor pushes the dots aside; clicking sends a shockwave and assigns a new task.
(function () {
  const canvas = document.getElementById('flow');
  const ctx = canvas.getContext('2d');
  const hub = document.getElementById('hub');
  const foot = canvas.parentElement.querySelector('.foot');   // only text that shares the canvas's area
  const busList = document.getElementById('bus');
  const busCount = document.getElementById('busCount');
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  const AGENTS = [
    { name: 'Reader',    verb: 'fields extracted' },
    { name: 'Planner',   verb: 'plan ready' },
    { name: 'Executor',  verb: 'action complete' },
    { name: 'Verifier',  verb: 'read-back ok' },
    { name: 'Watcher',   verb: 'change spotted' },
    { name: 'Messenger', verb: 'team notified' },
  ];
  // Who can hand work to whom.
  const LINKS = [[0, 1], [1, 2], [2, 3], [3, 0], [4, 1], [4, 5], [5, 3], [1, 3], [0, 4], [2, 5]];

  // Wide screens: agents sit left and right of the card. Narrow screens: above and below it.
  const WIDE_ANGLES = [145, 180, 215, 325, 0, 35];
  const NARROW_ANGLES = [-130, -90, -50, 50, 90, 130];

  let W = 0, H = 0, cx = 0, cy = 0, narrow = false;
  let hubRect = { left: 0, right: 0, top: 0, bottom: 0 };
  let contentBottom = 0;
  let lanes = [];
  const packets = [];
  const waves = [];
  const sparks = [];
  const mouse = { x: -9999, y: -9999, on: false };
  let handoffs = 0;
  let time = 0;

  const agents = AGENTS.map((a, i) => ({
    ...a, i, x: 0, y: 0, pulses: [], queue: 0, cool: Math.random(), status: 'idle', statusT: 0,
    wobble: Math.random() * Math.PI * 2,
  }));
  const links = LINKS.map(([a, b]) => ({ a, b, heat: 0 }));

  const rand = (a, b) => a + Math.random() * (b - a);
  const lerp = (a, b, t) => a + (b - a) * t;
  const pick = (arr) => arr[(Math.random() * arr.length) | 0];

  function bez(p0, p1, p2, p3, t) {
    const u = 1 - t;
    return {
      x: u * u * u * p0.x + 3 * u * u * t * p1.x + 3 * u * t * t * p2.x + t * t * t * p3.x,
      y: u * u * u * p0.y + 3 * u * u * t * p1.y + 3 * u * t * t * p2.y + t * t * t * p3.y,
    };
  }

  /* ---------------- layout ---------------- */
  function measureHub() {
    // everything is measured relative to the canvas, so it also works when the canvas scrolls with the page
    const c = canvas.getBoundingClientRect(), r = hub.getBoundingClientRect();
    hubRect = { left: r.left - c.left - 4, right: r.right - c.left + 4, top: r.top - c.top - 4, bottom: r.bottom - c.top + 4 };
    contentBottom = (foot ? foot.getBoundingClientRect().bottom : r.bottom) - c.top;
  }

  function placeAgents() {
    if (narrow) {
      // Phones: a row of three above the card and a row of three below the footer text.
      const topY = Math.max(70, hubRect.top - 64);
      const botY = Math.min(H - 44, contentBottom + 48);
      agents.forEach((a, i) => {
        const col = i % 3, row = i < 3 ? 0 : 1;
        const arc = col === 1 ? (row === 0 ? -18 : 18) : 0;
        const wob = Math.sin(time * 0.6 + a.wobble) * 4;
        a.x = W * (0.2 + col * 0.3) + wob;
        a.y = (row === 0 ? topY : botY) + arc + Math.cos(time * 0.5 + a.wobble) * 3;
      });
      return;
    }
    const angles = narrow ? NARROW_ANGLES : WIDE_ANGLES;
    const rx = narrow ? W * 0.36 : Math.min(W * 0.38, 640);
    const ry = narrow ? Math.min(H * 0.43, (hubRect.bottom - hubRect.top) / 2 + 120) : Math.min(H * 0.32, 300);
    agents.forEach((a, i) => {
      const wob = Math.sin(time * 0.35 + a.wobble) * 0.07;
      const breathe = 1 + Math.sin(time * 0.5 + i * 1.7) * 0.035;
      const ang = (angles[i] * Math.PI) / 180 + wob;
      a.x = cx + Math.cos(ang) * rx * breathe;
      a.y = cy + Math.sin(ang) * ry * breathe;
    });
  }

  function buildLanes() {
    const area = (W * H) / (1440 * 900);
    const perAgent = Math.max(4, Math.round(12 * Math.min(1.3, Math.max(0.5, area))));
    lanes = [];
    agents.forEach((a) => {
      for (let k = 0; k < perAgent; k++) {
        const fromLeft = narrow ? k % 2 === 0 : a.x < cx;
        lanes.push({
          agent: a.i,
          side: fromLeft ? 0 : 1,
          fy: a.y / H + rand(-0.55, 0.55),
          t: Math.random(),
          speed: rand(0.08, 0.2),
        });
      }
    });
  }

  function resize() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const box = canvas.getBoundingClientRect();
    W = box.width || window.innerWidth;
    H = box.height || window.innerHeight;
    canvas.width = Math.round(W * dpr);
    canvas.height = Math.round(H * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    narrow = W < 760;
    measureHub();
    cx = (hubRect.left + hubRect.right) / 2;
    cy = (hubRect.top + hubRect.bottom) / 2;
    placeAgents();
    buildLanes();
  }

  /* ---------------- curves ---------------- */
  function laneCurve(l) {
    const a = agents[l.agent];
    const p0 = { x: l.side === 0 ? -20 : W + 20, y: l.fy * H };
    return [p0, { x: lerp(p0.x, a.x, 0.45), y: p0.y }, { x: lerp(p0.x, a.x, 0.82), y: a.y }, a];
  }

  function linkCurve(a, b) {
    const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
    const m = { x: lerp(mx, cx, 0.32), y: lerp(my, cy, 0.32) };
    return [a, { x: lerp(a.x, m.x, 0.66), y: lerp(a.y, m.y, 0.66) }, { x: lerp(b.x, m.x, 0.66), y: lerp(b.y, m.y, 0.66) }, b];
  }

  // Where the line from an agent toward the center first touches the hub card.
  function hubEntry(a) {
    const dx = cx - a.x, dy = cy - a.y;
    const tx = dx > 0 ? (hubRect.left - a.x) / dx : dx < 0 ? (hubRect.right - a.x) / dx : -1;
    const ty = dy > 0 ? (hubRect.top - a.y) / dy : dy < 0 ? (hubRect.bottom - a.y) / dy : -1;
    let s = Math.max(tx, ty);
    if (!(s > 0 && s < 1)) s = 0.9;
    return { x: a.x + dx * s, y: a.y + dy * s };
  }

  function spokeCurve(a) {
    const e = hubEntry(a);
    return [a, { x: lerp(a.x, e.x, 0.6), y: a.y }, { x: lerp(a.x, e.x, 0.92), y: lerp(a.y, e.y, 0.6) }, e];
  }

  function freeCurve(from, a) {
    const mx = (from.x + a.x) / 2, my = (from.y + a.y) / 2;
    const nx = -(a.y - from.y) * 0.25, ny = (a.x - from.x) * 0.25;
    const m = { x: mx + nx, y: my + ny };
    return [from, m, m, a];
  }

  /* ---------------- forces ---------------- */
  function displace(p) {
    let x = p.x, y = p.y;
    for (const w of waves) {
      const dx = p.x - w.x, dy = p.y - w.y;
      const d = Math.hypot(dx, dy) || 1;
      const band = Math.abs(d - w.r);
      if (band < 110) {
        const f = (1 - band / 110) * w.life * 70;
        x += (dx / d) * f; y += (dy / d) * f;
      }
    }
    if (mouse.on) {
      const dx = p.x - mouse.x, dy = p.y - mouse.y;
      const d = Math.hypot(dx, dy) || 1;
      if (d < 130) {
        const f = (1 - d / 130) ** 2 * 34;
        x += (dx / d) * f; y += (dy / d) * f;
      }
    }
    return { x, y };
  }

  /* ---------------- events between agents ---------------- */
  let pendingLog = null, logTimer = 0;

  function log(from, to, note) {
    pendingLog = { from, to, note };
  }

  function flushLog() {
    if (!pendingLog || !busList) return;
    const { from, to, note } = pendingLog;
    pendingLog = null;
    const li = document.createElement('li');
    li.innerHTML = `<b>${from}</b><i>→</i><b>${to}</b><em>${note}</em>`;
    busList.prepend(li);
    while (busList.children.length > 3) busList.lastElementChild.remove();
    if (busCount) busCount.textContent = handoffs.toLocaleString() + (handoffs === 1 ? ' handoff' : ' handoffs');
  }

  function pulse(a, strength) {
    a.pulses.push({ r: 6, life: 1, s: strength });
    if (a.pulses.length > 4) a.pulses.shift();
  }

  function setStatus(a, text) { a.status = text; a.statusT = 2.2; }

  let pingTimer = null;
  function pingHub() {
    hub.classList.add('ping');
    clearTimeout(pingTimer);
    pingTimer = setTimeout(() => hub.classList.remove('ping'), 120);
  }

  function emit(a) {
    if (packets.length > 110) return;
    const neighbors = links.filter((l) => l.a === a.i || l.b === a.i);
    if (Math.random() < 0.58 && neighbors.length) {
      const link = pick(neighbors);
      const to = agents[link.a === a.i ? link.b : link.a];
      packets.push({ kind: 'hand', from: a, to, link, t: 0, speed: rand(0.45, 0.7) });
      setStatus(a, 'handing off');
    } else {
      packets.push({ kind: 'deliver', from: a, t: 0, speed: rand(0.5, 0.8) });
      setStatus(a, 'delivering');
    }
  }

  function arrive(p) {
    if (p.kind === 'hand') {
      p.to.queue = Math.min(6, p.to.queue + 1);
      pulse(p.to, 1);
      setStatus(p.to, 'from ' + p.from.name.toLowerCase());
      handoffs++;
      log(p.from.name, p.to.name, p.from.verb);
    } else if (p.kind === 'deliver') {
      const e = hubEntry(p.from);
      for (let k = 0; k < 7; k++) sparks.push({ x: e.x, y: e.y, vx: rand(-60, 60), vy: rand(-60, 60), life: 1 });
      pingHub();
      handoffs++;
      log(p.from.name, 'Gateway', p.from.verb);
    } else if (p.kind === 'assign') {
      p.to.queue = Math.min(6, p.to.queue + 2);
      pulse(p.to, 1.6);
      setStatus(p.to, 'new task');
      log('You', p.to.name, 'task assigned');
    }
  }

  // Click / button: shockwave + new tasks to the nearest agents.
  function assign(x, y) {
    waves.push({ x, y, r: 0, life: 1 });
    const near = agents.slice().sort((a, b) => Math.hypot(a.x - x, a.y - y) - Math.hypot(b.x - x, b.y - y)).slice(0, 2);
    near.forEach((a, n) => {
      for (let k = 0; k < 3; k++) {
        packets.push({ kind: 'assign', origin: { x, y }, to: a, t: -k * 0.12 - n * 0.06, speed: rand(0.9, 1.2) });
      }
    });
  }

  const local = (e) => { const c = canvas.getBoundingClientRect(); return { x: e.clientX - c.left, y: e.clientY - c.top, inside: e.clientY >= c.top && e.clientY <= c.bottom }; };
  window.addEventListener('click', (e) => {
    if (reduce || e.target.closest('.card, a, button, input')) return;
    const p = local(e);
    if (p.inside) assign(p.x, p.y);
  });
  const assignBtn = document.getElementById('assign');
  if (assignBtn) assignBtn.addEventListener('click', () => {
    if (reduce) return;
    assign(cx, hubRect.top);
  });
  window.addEventListener('pointermove', (e) => { const p = local(e); mouse.x = p.x; mouse.y = p.y; mouse.on = e.pointerType === 'mouse' && p.inside; });
  window.addEventListener('mouseout', (e) => { if (!e.relatedTarget) mouse.on = false; });
  window.addEventListener('resize', resize);

  /* ---------------- drawing ---------------- */
  function strokeCurve(c, alpha, dash, width) {
    ctx.beginPath();
    ctx.moveTo(c[0].x, c[0].y);
    ctx.bezierCurveTo(c[1].x, c[1].y, c[2].x, c[2].y, c[3].x, c[3].y);
    ctx.strokeStyle = `rgba(255,255,255,${alpha})`;
    ctx.lineWidth = width || 1;
    ctx.setLineDash(dash);
    ctx.stroke();
  }

  function dot(x, y, size, alpha) {
    ctx.fillStyle = `rgba(255,255,255,${alpha})`;
    ctx.fillRect(x - size / 2, y - size / 2, size, size);
  }

  // A square with a fading tail sampled from the same curve.
  function traveller(c, t, size, alpha, tail, step) {
    for (let k = tail; k >= 0; k--) {
      const tt = t - k * step;
      if (tt < 0) continue;
      const p = displace(bez(c[0], c[1], c[2], c[3], Math.min(1, tt)));
      const f = 1 - k / (tail + 1);
      dot(p.x, p.y, size * (0.45 + 0.55 * f), alpha * f);
    }
  }

  function drawAgents() {
    const mono = '"Geist Mono", ui-monospace, Menlo, monospace';
    for (const a of agents) {
      for (const p of a.pulses) {
        ctx.beginPath();
        ctx.arc(a.x, a.y, p.r, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(255,255,255,${0.5 * p.life})`;
        ctx.lineWidth = 1;
        ctx.setLineDash([]);
        ctx.stroke();
      }
      // node: ring + core, core grows with how busy the agent is
      ctx.setLineDash([]);
      ctx.beginPath();
      ctx.arc(a.x, a.y, 7, 0, Math.PI * 2);
      ctx.fillStyle = '#000';
      ctx.fill();
      ctx.strokeStyle = 'rgba(255,255,255,.85)';
      ctx.lineWidth = 1.2;
      ctx.stroke();
      // orbiting tick shows the agent is "thinking"
      const ang = time * (1.4 + a.queue * 0.5) + a.wobble;
      dot(a.x + Math.cos(ang) * 11, a.y + Math.sin(ang) * 11, 2, 0.7);
      dot(a.x, a.y, 3 + a.queue * 0.6, 1);

      // label
      const left = a.x < cx - 4;
      const lx = a.x + (left ? -18 : 18);
      ctx.textAlign = narrow ? 'center' : left ? 'right' : 'left';
      const tx = narrow ? a.x : lx;
      const ty = narrow ? (a.y < cy ? a.y - 28 : a.y + 26) : a.y - 3;
      if ('letterSpacing' in ctx) ctx.letterSpacing = '2px';
      ctx.font = `500 10px ${mono}`;
      ctx.fillStyle = 'rgba(255,255,255,.82)';
      ctx.fillText(a.name.toUpperCase(), tx, ty);
      if ('letterSpacing' in ctx) ctx.letterSpacing = '1px';
      ctx.font = `400 9.5px ${mono}`;
      ctx.fillStyle = `rgba(255,255,255,${a.statusT > 0 ? 0.5 : 0.26})`;
      ctx.fillText(a.statusT > 0 ? a.status : 'idle', tx, ty + 13);
    }
    if ('letterSpacing' in ctx) ctx.letterSpacing = '0px';
  }

  function draw() {
    ctx.clearRect(0, 0, W, H);

    // lanes (incoming tasks)
    for (const l of lanes) strokeCurve(laneCurve(l), 0.2, [1, 5]);
    // links between agents: brighter while carrying work
    for (const l of links) strokeCurve(linkCurve(agents[l.a], agents[l.b]), 0.16 + l.heat * 0.4, [2, 6], 1 + l.heat * 0.4);
    // spokes into the hub
    for (const a of agents) strokeCurve(spokeCurve(a), 0.2, [1, 4]);
    ctx.setLineDash([]);

    // incoming task dots
    for (const l of lanes) traveller(laneCurve(l), l.t, 2.6, 0.8, 3, 0.012);

    // packets in flight
    for (const p of packets) {
      if (p.t < 0) continue;
      if (p.kind === 'hand') traveller(linkCurve(p.from, p.to), p.t, 3.4, 1, 6, 0.02);
      else if (p.kind === 'deliver') traveller(spokeCurve(p.from), p.t, 3.4, 1, 7, 0.022);
      else traveller(freeCurve(p.origin, p.to), p.t, 3, 1, 5, 0.025);
    }

    // shockwaves
    for (const w of waves) {
      ctx.beginPath();
      ctx.arc(w.x, w.y, w.r, 0, Math.PI * 2);
      ctx.strokeStyle = `rgba(255,255,255,${0.22 * w.life})`;
      ctx.lineWidth = 1;
      ctx.stroke();
    }
    // sparks where results enter the hub
    for (const s of sparks) dot(s.x, s.y, 2, s.life * 0.9);

    drawAgents();
  }

  /* ---------------- simulation ---------------- */
  function step(dt) {
    time += dt;
    placeAgents();

    for (const l of lanes) {
      l.t += l.speed * dt;
      if (l.t >= 1) {
        l.t = 0;
        l.fy = Math.min(1.25, Math.max(-0.25, l.fy + rand(-0.03, 0.03)));
        const a = agents[l.agent];
        if (Math.random() < 0.55) { a.queue = Math.min(6, a.queue + 1); pulse(a, 0.6); setStatus(a, 'receiving'); }
      }
    }

    for (const a of agents) {
      a.cool -= dt;
      a.statusT -= dt;
      if (a.queue > 0 && a.cool <= 0) { a.queue--; a.cool = rand(0.35, 1.1); emit(a); }
      for (const p of a.pulses) { p.r += dt * 60 * p.s; p.life -= dt * 1.4; }
      a.pulses = a.pulses.filter((p) => p.life > 0);
    }

    for (const l of links) l.heat = Math.max(0, l.heat - dt * 1.5);
    for (let i = packets.length - 1; i >= 0; i--) {
      const p = packets[i];
      p.t += p.speed * dt;
      if (p.kind === 'hand') p.link.heat = Math.min(1, p.link.heat + dt * 4);
      if (p.t >= 1) { arrive(p); packets.splice(i, 1); }
    }

    for (const w of waves) { w.r += dt * 700; w.life -= dt * 0.9; }
    for (let i = waves.length - 1; i >= 0; i--) if (waves[i].life <= 0) waves.splice(i, 1);
    for (const s of sparks) { s.x += s.vx * dt; s.y += s.vy * dt; s.life -= dt * 2.2; }
    for (let i = sparks.length - 1; i >= 0; i--) if (sparks[i].life <= 0) sparks.splice(i, 1);

    logTimer -= dt;
    if (logTimer <= 0 && pendingLog) { flushLog(); logTimer = 0.9; }
  }

  let last = performance.now();
  let hubCheck = 0;
  // pause when the animation is scrolled out of view
  let visible = true;
  if ('IntersectionObserver' in window) new IntersectionObserver((es) => { visible = es[0].isIntersecting; }).observe(canvas);
  function frame(now) {
    const dt = Math.min(0.05, (now - last) / 1000);
    last = now;
    if (!visible) { requestAnimationFrame(frame); return; }
    hubCheck -= dt;
    if (hubCheck <= 0) { measureHub(); hubCheck = 0.5; }
    step(dt);
    draw();
    requestAnimationFrame(frame);
  }

  resize();
  if (reduce) {
    // Still picture: a few packets frozen mid-handoff.
    links.forEach((l, i) => { if (i % 2 === 0) packets.push({ kind: 'hand', from: agents[l.a], to: agents[l.b], link: l, t: 0.5, speed: 0 }); });
    draw();
    window.addEventListener('resize', () => draw());
  } else {
    requestAnimationFrame(frame);
  }
})();
