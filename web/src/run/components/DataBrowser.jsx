import { useEffect, useMemo, useState } from 'react';

const PAGE = 50;
const fmt = (n) => Number(n).toLocaleString('en-US');

export default function DataBrowser({ records, model }) {
  const ents = Object.keys(records);
  const [entity, setEntity] = useState(null);
  const [sort, setSort] = useState(null);
  const [dir, setDir] = useState(1);
  const [input, setInput] = useState('');
  const [q, setQ] = useState('');
  const [page, setPage] = useState(0);
  const current = ents.includes(entity) ? entity : ents[0] || null;
  const rows = records[current] || [];

  useEffect(() => { setPage(0); }, [records]);
  useEffect(() => { const t = setTimeout(() => { setQ(input.trim().toLowerCase()); setPage(0); }, 150); return () => clearTimeout(t); }, [input]);

  // Columns: the model's fields that have values, in model order, then anything else; the record link last.
  const { cols, empty } = useMemo(() => {
    const m = model.find((x) => x.name === current);
    const present = new Set();
    for (const r of rows) for (const k of Object.keys(r)) if (r[k] !== '' && r[k] !== null && r[k] !== undefined) present.add(k);
    const order = [];
    const missing = [];
    if (m) for (const f of m.fields) (present.has(f.name) ? order : missing).push(f.name);
    for (const k of present) if (!order.includes(k) && k !== '_key') order.push(k);
    if (present.has('_key')) order.push('_key');
    return { cols: order, empty: missing };
  }, [rows, model, current]);

  const list = useMemo(() => {
    let l = q ? rows.filter((r) => cols.some((c) => r[c] !== undefined && String(r[c]).toLowerCase().includes(q))) : rows.slice();
    if (sort) l = l.sort((a, b) => {
      const x = a[sort], y = b[sort];
      const xe = x === undefined || x === '', ye = y === undefined || y === '';
      if (xe || ye) return xe && ye ? 0 : xe ? 1 : -1;   // blanks last either way
      return (typeof x === 'number' && typeof y === 'number' ? x - y : String(x).localeCompare(String(y), undefined, { numeric: true })) * dir;
    });
    return l;
  }, [rows, cols, q, sort, dir]);

  const pages = Math.max(1, Math.ceil(list.length / PAGE));
  const pg = Math.min(page, pages - 1);
  const slice = list.slice(pg * PAGE, (pg + 1) * PAGE);
  const clickSort = (c) => { if (sort === c) setDir(-dir); else { setSort(c); setDir(c === 'points' || c === 'comments' ? -1 : 1); } };
  const head = (c) => (c === '_key' ? 'link' : c);

  return (
    <section className="run-panel browser" aria-label="Data browser">
      <div className="run-ph">
        {ents.length > 1 && (
          <select id="runEntity" aria-label="Entity" value={current || ''} onChange={(e) => { setEntity(e.target.value); setSort(null); setPage(0); }}>
            {ents.map((e) => <option key={e} value={e}>{e} ({fmt(records[e].length)})</option>)}
          </select>
        )}
        <input id="runSearch" className="search" type="search" spellCheck="false" placeholder={`Search ${current ? current + 's' : 'records'}…`}
          aria-label="Search records" value={input} onChange={(e) => setInput(e.target.value)} />
        <span className="note">{empty.length ? `No values yet for ${empty.join(', ')}` : ''}</span>
      </div>
      <div className="tablewrap">
        <table>
          <thead>
            <tr>{cols.map((c) => (
              <th key={c}><button type="button" data-sort={sort === c ? '' : undefined} onClick={() => clickSort(c)}>
                {head(c)}{sort === c ? (dir > 0 ? ' ↑' : ' ↓') : ''}
              </button></th>
            ))}</tr>
          </thead>
          <tbody>
            {slice.length ? slice.map((r, i) => (
              <tr key={(r._key || '') + i}>
                {cols.map((c) => {
                  const v = r[c];
                  if (c === '_key' && v) return <td key={c}><a href={v} target="_blank" rel="noopener noreferrer">{v.replace(/^https?:\/\/[^/]+/, '')}</a></td>;
                  if (typeof v === 'number') return <td key={c} className="n">{fmt(v)}</td>;
                  return <td key={c} className={c === 'title' ? 'title' : undefined} title={v === undefined ? '' : String(v)}>{v === undefined ? '' : String(v)}</td>;
                })}
              </tr>
            )) : (
              <tr><td colSpan={cols.length || 1} className="empty">
                {rows.length ? 'No records match that search.' : 'No records loaded yet. They come from records/Post.jsonl.'}
              </td></tr>
            )}
          </tbody>
        </table>
      </div>
      <div className="pager">
        <span>{list.length ? `${fmt(pg * PAGE + 1)}–${fmt(Math.min(list.length, (pg + 1) * PAGE))} of ${fmt(list.length)}${q ? ` (filtered from ${fmt(rows.length)})` : ''}` : ''}</span>
        <span className="sp"></span>
        <button type="button" className="mini" disabled={pg === 0} onClick={() => setPage(pg - 1)}>Previous</button>
        <button type="button" className="mini" disabled={pg >= pages - 1} onClick={() => setPage(pg + 1)}>Next</button>
      </div>
    </section>
  );
}
