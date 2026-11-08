import { useEffect, useRef, useState } from 'react';
import { NODE_W } from '../runState.js';

const fmt = (n) => Number(n).toLocaleString('en-US');
export const typeColor = (t) => ({ list: 'var(--t-list)', detail: 'var(--t-detail)', form: 'var(--t-form)' }[t] || 'var(--t-other)');

function MapNode({ n, active, done }) {
  const [mode, setMode] = useState(null); // 'reading' | 'flash' | null
  const [badge, setBadge] = useState('');
  const seq = n.act ? n.act.seq : 0;

  // Each visit restarts the pulse (Nemotron read) or the flash (reused mapping).
  useEffect(() => {
    if (!n.act) return undefined;
    const { reused, seconds } = n.act;
    let r1, r2, r3, off;
    setMode(null);
    r1 = requestAnimationFrame(() => {
      r2 = requestAnimationFrame(() => {
        if (!reused) {
          const total = seconds || 0, start = performance.now(), dur = Math.min(300 + total * 90, 2000);
          setMode('reading');
          const tick = (now) => {
            const f = Math.min((now - start) / dur, 1);
            setBadge(f < 1 ? `Nemotron reading… ${(total * f).toFixed(1)}s` : `Nemotron read · ${total.toFixed(1)}s`);
            if (f < 1) r3 = requestAnimationFrame(tick);
          };
          r3 = requestAnimationFrame(tick);
          off = setTimeout(() => setMode(null), dur + 250);
        } else {
          setBadge('reused');
          setMode('flash');
          off = setTimeout(() => setMode(null), 500);
        }
      });
    });
    return () => { cancelAnimationFrame(r1); cancelAnimationFrame(r2); cancelAnimationFrame(r3); clearTimeout(off); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seq]);

  // Only one node reads at a time; the end of the run stops any pulse.
  useEffect(() => { if ((!active || done) && mode === 'reading') setMode(null); }, [active, done, mode]);

  const cls = ['node', mode, n.failed ? 'failed' : null].filter(Boolean).join(' ');
  return (
    <div className={cls} style={{ left: n.x, top: n.y, '--c': typeColor(n.type) }} title={n.purpose || undefined}>
      <span className="badge">{badge}</span>
      <div className="top"><span className="name">{n.label}</span><span className="times">×{fmt(n.count)}</span></div>
      <div className="pat" title={n.patterns.join('  ')}>{n.patterns.join('  ') || n.key}</div>
      <div className="meta">
        <span className="type-chip">{n.failed ? 'failed' : n.type}</span>
        <span>+{fmt(n.recs)} records</span>
        <span className="ai-n">{n.aiReads ? `AI ×${n.aiReads}` : ''}</span>
      </div>
    </div>
  );
}

function RootNode({ n, site }) {
  return (
    <div className="node root" style={{ left: n.x, top: n.y }}>
      <div className="top"><span className="name">Site</span></div>
      <div className="pat">{site || 'waiting for the first page'}</div>
      <div className="meta"><span className="type-chip">start</span></div>
    </div>
  );
}

export default function SiteMap({ run }) {
  const wrapRef = useRef(null);
  const nodes = run.order.map((k) => run.nodes[k]);
  const width = Math.max(...nodes.map((n) => n.x + NODE_W + 30));
  const height = Math.max(...nodes.map((n) => n.y + 90));

  // keep the active node in view
  useEffect(() => {
    const wrap = wrapRef.current, n = run.nodes[run.activeKey];
    if (!wrap || !n) return;
    const left = n.x + NODE_W + 20 > wrap.scrollLeft + wrap.clientWidth || n.x < wrap.scrollLeft ? Math.max(0, n.x - 40) : wrap.scrollLeft;
    const top = n.y + 96 > wrap.scrollTop + wrap.clientHeight || n.y < wrap.scrollTop ? Math.max(0, n.y - 30) : wrap.scrollTop;
    if (left !== wrap.scrollLeft || top !== wrap.scrollTop) wrap.scrollTo({ left, top, behavior: 'smooth' });
  }, [run.actSeq, run.activeKey, run.nodes]);

  return (
    <section className="run-panel" aria-label="Site map">
      <div className="run-ph">
        <h2>Site map</h2>
        <div className="legend">
          <span style={{ '--c': 'var(--t-list)' }}>list</span>
          <span style={{ '--c': 'var(--t-detail)' }}>detail</span>
          <span style={{ '--c': 'var(--t-form)' }}>form</span>
          <span className="ai">Nemotron reading</span>
          <span className="fast">reused</span>
        </div>
      </div>
      <div className="mapwrap" ref={wrapRef}>
        <div className="map" style={{ width, height }}>
          <svg width={width} height={height} style={{ width, height }} aria-hidden="true">
            {run.edges.map((ed) => {
              const a = run.nodes[ed.from], b = run.nodes[ed.to];
              if (b.depth < 2) {   // side by side
                const x1 = a.x + NODE_W, y1 = a.y + 34, x2 = b.x, y2 = b.y + 34, mx = (x1 + x2) / 2;
                return <path key={ed.id} className="edge new" d={`M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`} />;
              }
              const x1 = a.x + NODE_W / 2, y1 = a.y + 74, x2 = b.x + NODE_W / 2, y2 = b.y, my = (y1 + y2) / 2;   // hub above
              return <path key={ed.id} className="edge new" d={`M${x1},${y1} C${x1},${my} ${x2},${my} ${x2},${y2}`} />;
            })}
          </svg>
          {nodes.map((n) => (n.root
            ? <RootNode key={n.key} n={n} site={run.site} />
            : <MapNode key={n.key} n={n} active={run.activeKey === n.key} done={run.done} />))}
        </div>
      </div>
    </section>
  );
}
