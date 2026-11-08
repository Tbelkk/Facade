// Turns the Facade agent's output files into the shapes the Explorer panels use.
// Field names follow the real run: run_log.jsonl, site_map.json, data_model.json, records/<Entity>.jsonl.

export function parseJSONL(text) {
  const out = [];
  for (const line of text.split(/\r?\n/)) {
    const s = line.trim();
    if (!s) continue;
    try { out.push(JSON.parse(s)); } catch { out.push({ kind: 'unparsed', raw: s.slice(0, 200) }); }
  }
  return out;
}

/** "https://news.ycombinator.com/newest?next=1&n=31" → "/newest?n=&next=" (same shape site_map.json uses) */
export function patternFromUrl(url) {
  try {
    const u = new URL(url);
    const keys = [...new Set([...u.searchParams.keys()])].sort();
    return u.pathname + (keys.length ? '?' + keys.map((k) => k + '=').join('&') : '');
  } catch { return url || '(no url)'; }
}

/** Node key: the path part of the pattern, so "/" and "/?p=" (pagination) are one node. */
export const groupOf = (pattern) => (pattern.split('?')[0] || '/');

/** site_map.json → Map(url → { pattern, pageType, entity, purpose }) */
export function indexSiteMap(sm) {
  const byUrl = new Map();
  const pages = (sm && (sm.pages || sm.patterns)) || [];
  for (const p of pages) {
    if (!p.url) continue;
    const v = { pattern: p.url_pattern || patternFromUrl(p.url), pageType: p.page_type, entity: p.entity, purpose: p.purpose };
    byUrl.set(p.url, v);
    byUrl.set(p.url.replace(/\/$/, ''), v);
  }
  return { site: sm && sm.site, byUrl };
}

/** data_model.json → [{ name, recordCount, fields: [{ name, type, required }] }] */
export function normalizeModel(dm) {
  const ents = (dm && dm.entities) || [];
  return ents.map((e) => ({
    name: e.name,
    recordCount: e.record_count ?? null,
    rules: e.rules || [],
    fields: (e.fields || []).map((f) => ({ name: f.name, type: f.type || '', required: !!f.required })),
  }));
}

/** Plain-language names for the model's types. */
export const TYPE_NAME = { string: 'text', textarea: 'long text', int: 'number', integer: 'number', float: 'number', number: 'number', date: 'date', datetime: 'date', bool: 'yes/no', boolean: 'yes/no', url: 'link' };

/** One run_log.jsonl line → normalized event. */
export function normalizeEvent(raw, site) {
  const kind = String(raw.kind || 'unknown');
  const url = raw.url || '';
  const sm = site.byUrl.get(url) || site.byUrl.get(url.replace(/\/$/, ''));
  const pattern = raw.url_pattern || (sm && sm.pattern) || (url ? patternFromUrl(url) : '');
  const ms = raw.nemotron_ms ?? (raw.duration_ms ?? null);
  return {
    kind,
    url,
    pattern,
    group: url ? groupOf(pattern) : null,
    pageType: String(raw.page_type || (sm && sm.pageType) || 'other').toLowerCase(),
    entity: raw.entity || (sm && sm.entity) || null,
    purpose: raw.purpose || (sm && sm.purpose) || '',
    reachedBy: raw.reached_by || '',
    recordsNew: Number(raw.records_new || 0),
    reused: raw.reused_mapping === true,
    seconds: ms !== null && ms !== undefined ? ms / 1000 : null,
    ts: typeof raw.ts === 'number' ? (raw.ts > 1e12 ? raw.ts : raw.ts * 1000) : (raw.ts ? Date.parse(raw.ts) : null),
    reason: raw.reason || raw.stop_reason || '',
    pages: raw.pages ?? null,
    minutes: raw.minutes ?? null,
    error: raw.error || '',
    detail: raw.column || raw.field || raw.problems || raw.note || raw.message || '',
    raw,
  };
}

/** Records: numbers stored as text ("62") become numbers for fields the model calls int. */
export function typeRecords(rows, entity) {
  const numeric = new Set((entity ? entity.fields : []).filter((f) => TYPE_NAME[f.type] === 'number').map((f) => f.name));
  return rows.map((r) => {
    const o = { ...r };
    for (const k of numeric) if (typeof o[k] === 'string' && /^-?\d+(\.\d+)?$/.test(o[k].replace(/,/g, ''))) o[k] = Number(o[k].replace(/,/g, ''));
    return o;
  });
}
