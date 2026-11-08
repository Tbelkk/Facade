// DEMO ONLY: fakes the agents' progress so the dashboard can be shown before the back end exists.
//
// When the real agents are ready, delete this file (and its <script> tag) and call
//   dashboard.set('explorer', { status: 'working', progress: 0.4, stat: 'Pages mapped 12 / 30' })
// from the real events instead. Agent ids: explorer, analyst, extractor, builder, worker, verifier.
window.mock = (function () {
  const D = window.dashboard;

  // [agent, starts after (s), takes (s), then becomes]
  const PLAN = [
    ['explorer', 0, 10, 'done'],
    ['analyst', 3, 10, 'done'],
    ['extractor', 8, 16, 'done'],
    ['verifier', 10, 14, 'live'],
    ['builder', 13, 10, 'done'],
    ['worker', 21, 0, 'live'],
  ];

  let timer = null, t0 = 0;

  function tick() {
    const elapsed = (performance.now() - t0) / 1000;
    for (const [id, at, takes, end] of PLAN) {
      const e = elapsed - at;
      if (e < 0) D.set(id, { status: 'idle', progress: 0 });
      else if (takes && e < takes) D.set(id, { status: 'working', progress: e / takes });
      else D.set(id, { status: end, progress: 1 });
    }
  }

  return {
    start() { this.stop(); t0 = performance.now(); tick(); timer = setInterval(tick, 100); },
    stop() { clearInterval(timer); timer = null; D.reset(); },
    elapsed() { return timer ? (performance.now() - t0) / 1000 : 0; },
  };
})();
