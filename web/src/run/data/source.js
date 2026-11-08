// Where Explorer data comes from. This is the only part to change for SpacetimeDB.
//
// Every source follows one contract:
//   source.label
//   source.subscribe({ meta, records, event, done }) → unsubscribe()
//     meta({ site, model, total })        once before events (and again on restart)
//     records({ Post: [...] })            whenever records change
//     event(evt, index)                   one normalized run_log line
//     done()                              the run finished
//   Replay sources also have play() pause() restart() setSpeed(x) setTiming('fixed' | 'real') and .playing.
//   A live source (SpacetimeDB) can leave those out.

import { indexSiteMap, normalizeEvent, normalizeModel, parseJSONL, typeRecords } from './normalize.js';

/** Turns raw file contents into the parsed bundle a replay plays. */
export function makeBundle({ label, runLog, siteMap, dataModel, records }) {
  const site = indexSiteMap(siteMap);
  const model = normalizeModel(dataModel);
  const events = runLog.map((l) => normalizeEvent(l, site));
  const typed = {};
  for (const [name, rows] of Object.entries(records || {})) typed[name] = typeRecords(rows, model.find((m) => m.name === name));
  const host = site.site ? site.site.replace(/^https?:\/\//, '') : (events.find((e) => e.url) || {}).url?.replace(/^https?:\/\//, '').split('/')[0] || '';
  return { label, host, model, events, records: typed };
}

/** Loads a run published next to the app (web/public/run/). Returns null if there is none. */
export async function loadPublicRun(base = './run/') {
  const get = async (path, json) => {
    try {
      const r = await fetch(base + path);
      if (!r.ok) return null;
      if ((r.headers.get('content-type') || '').includes('text/html')) return null; // dev server fallback page
      return json ? r.json() : r.text();
    } catch { return null; }
  };
  const log = await get('run_log.jsonl');
  if (!log) return null;
  const [siteMap, dataModel, posts] = await Promise.all([get('site_map.json', true), get('data_model.json', true), get('records/Post.jsonl')]);
  const model = normalizeModel(dataModel);
  const records = {};
  if (posts) records.Post = parseJSONL(posts);
  // other entities named in the model
  for (const e of model) if (e.name !== 'Post') { const t = await get(`records/${e.name}.jsonl`); if (t) records[e.name] = parseJSONL(t); }
  return makeBundle({ label: 'run_log.jsonl', runLog: parseJSONL(log), siteMap, dataModel, records });
}

/** Reads files the person dropped or picked (the run folder or the files themselves). */
export async function loadFileRun(files) {
  const parts = { runLog: null, siteMap: null, dataModel: null, records: {} };
  for (const f of files) {
    const name = f.name.toLowerCase();
    if (!/\.(jsonl|json|ndjson)$/.test(name)) continue;
    const text = await f.text();
    if (name.startsWith('run_log')) parts.runLog = parseJSONL(text);
    else if (name.startsWith('site_map')) parts.siteMap = JSON.parse(text);
    else if (name.startsWith('data_model')) parts.dataModel = JSON.parse(text);
    else if (/\.(jsonl|ndjson)$/.test(name)) parts.records[f.name.replace(/\.(jsonl|ndjson)$/i, '')] = parseJSONL(text);
  }
  if (!parts.runLog) throw new Error('No run_log.jsonl in what you added. Add it with the other run files.');
  return makeBundle({ label: [...files].map((f) => f.name).filter((n) => /\.(jsonl|json)$/i.test(n)).join(' · '), ...parts });
}

/** Walks a dropped folder into a flat list of files. */
export async function filesFromDrop(dataTransfer) {
  const items = [...(dataTransfer.items || [])];
  const out = [];
  async function walk(entry) {
    if (entry.isFile) await new Promise((r) => entry.file((f) => { out.push(f); r(); }, r));
    else if (entry.isDirectory) {
      const rd = entry.createReader();
      let batch;
      do { batch = await new Promise((r) => rd.readEntries(r, () => r([]))); for (const en of batch) await walk(en); } while (batch.length);
    }
  }
  if (items.length && items[0].webkitGetAsEntry) { for (const en of items.map((i) => i.webkitGetAsEntry()).filter(Boolean)) await walk(en); }
  else out.push(...dataTransfer.files);
  return out;
}

/** Plays a bundle line by line: 300 ms per line, or the real gaps between "ts" values. */
export function createReplaySource(bundle) {
  const { events } = bundle;
  let h = null, i = 0, timer = null, playing = false, speed = 1, timing = 'fixed';

  function delayAfter(k) {
    const e = events[k], n = events[k + 1];
    if (timing === 'real' && e.ts && n && n.ts) return Math.min(Math.max(n.ts - e.ts, 40), 4000) / speed;
    // An AI read holds the screen a little longer so the slow-then-fast contrast is visible.
    const ai = e.kind === 'page' && !e.reused && e.seconds;
    return (ai ? 300 + Math.min(e.seconds * 90, 1700) : 300) / speed;
  }
  function step() {
    if (!playing || !h) return;
    if (i >= events.length) { playing = false; h.done(); return; }
    const k = i++;
    h.event(events[k], k);
    timer = setTimeout(step, delayAfter(k));
  }
  function sendMeta() {
    h.meta({ site: bundle.host, model: bundle.model, total: events.length });
    h.records(bundle.records);
  }
  return {
    label: bundle.label,
    subscribe(handlers) { h = handlers; sendMeta(); return () => { playing = false; clearTimeout(timer); h = null; }; },
    play() { if (playing) return; playing = true; step(); },
    pause() { playing = false; clearTimeout(timer); },
    restart() { this.pause(); i = 0; if (h) sendMeta(); this.play(); },
    setSpeed(x) { speed = x; },
    setTiming(m) { timing = m; },
    get playing() { return playing; },
  };
}

/* SpacetimeDB later: same contract, rows arrive live instead of from a timer.
export function createSpacetimeSource(conn) {
  return {
    label: 'SpacetimeDB · live',
    subscribe(h) {
      const site = indexSiteMap(conn.siteMap());
      h.meta({ site: site.site, model: normalizeModel(conn.dataModel()), total: 0 });
      const offLog = conn.onRunLogInsert((row, seq) => h.event(normalizeEvent(row, site), seq));
      const offRecs = conn.onRecordsChange((byEntity) => h.records(byEntity));
      return () => { offLog(); offRecs(); };
    },
  };
} */
