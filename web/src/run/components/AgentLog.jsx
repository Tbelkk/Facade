import { useLayoutEffect, useRef } from 'react';
import { typeColor } from './SiteMap.jsx';

const fmt = (n) => Number(n).toLocaleString('en-US');
const short = (u) => String(u || '').replace(/^https?:\/\//, '');
const text = (d) => (typeof d === 'object' ? JSON.stringify(d) : String(d));

function view(e) {
  const extra = e.detail ? <span className="fast"> · {text(e.detail)}</span> : null;
  switch (e.kind) {
    case 'page': {
      const how = e.reused
        ? <span className="fast">(reused{e.seconds ? `, ${e.seconds.toFixed(1)}s` : ''})</span>
        : <span className="ai">({e.seconds !== null ? `${e.seconds.toFixed(1)}s ` : ''}Nemotron)</span>;
      return { c: typeColor(e.pageType), cls: '', m: <>Read <span className="u">{short(e.url)}</span> → {e.pageType} of {e.entity || 'page'}, +{fmt(e.recordsNew)} records {how}</> };
    }
    case 'split_column': return { c: '#fff', cls: '', m: <>Nemotron repaired a pattern{extra}</> };
    case 'mapping_problems': return { c: 'var(--t-form)', cls: '', m: <>Checked answer, sent it back to fix{extra}</> };
    case 'analyze_failed': return { c: 'var(--bad)', cls: 'bad', m: <>Couldn’t read <span className="u">{short(e.url)}</span>{e.error ? ` · ${e.error}` : ''}</> };
    case 'done': return { c: '#fff', cls: 'done', m: <>Done · {e.reason || 'finished'}{e.pages ? ` · ${fmt(e.pages)} pages` : ''}{e.minutes ? ` in ${e.minutes} min` : ''}</> };
    default: return { c: 'var(--mute)', cls: '', m: <><span className="fast">{e.kind}</span> {JSON.stringify(e.raw).slice(0, 160)}</> };
  }
}

export default function AgentLog({ run }) {
  const ref = useRef(null);
  const atBottom = useRef(true);

  useLayoutEffect(() => {
    if (atBottom.current && ref.current) ref.current.scrollTop = ref.current.scrollHeight;
  }, [run.logN]);

  const onScroll = () => { const el = ref.current; atBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 40; };

  return (
    <section className="run-panel" aria-label="Agent log">
      <div className="run-ph"><h2>Agent log</h2><span className="note">{run.logN ? `${fmt(run.logN)} lines` : ''}</span></div>
      <div className="log" ref={ref} onScroll={onScroll}>
        {run.log.length === 0 && <div className="empty">Press Play to replay the run. Each line of run_log.jsonl shows up here.</div>}
        {run.log.map((r) => {
          const v = view(r.evt);
          return (
            <div key={r.id} className={'row ' + v.cls} style={{ '--c': v.c }}>
              <span className="t">{r.t}</span><span className="d"></span><span className="m">{v.m}</span>
            </div>
          );
        })}
      </div>
    </section>
  );
}
