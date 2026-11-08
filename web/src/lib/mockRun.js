// DEMO ONLY: fakes the agents' progress so the dashboard can be shown before the back end exists.
// Same plan and timings as app/renderer/mock.js.
//
// When the real agents are ready, stop using this and call
//   dashboard.set('explorer', { status: 'working', progress: 0.4, stat: 'Pages mapped 12 / 30' })
// from the real events instead. Agent ids: explorer, analyst, extractor, builder, worker, verifier.

export function createMock(D, settings) {
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
      // Read-only mode: the Worker never acts on the old site
      if (id === 'worker' && settings.get().readOnly) { D.set(id, { status: 'idle', progress: 0, stat: 'Read-only mode · no actions' }); continue; }
      if (id === 'worker') D.set(id, { stat: null });
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
}
