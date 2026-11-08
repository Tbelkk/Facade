import { useEffect, useRef } from 'react';
import { LABEL } from '../lib/agentKinds.js';
import { useTile } from '../lib/hooks.js';

function AgentTile({ dashboard, agent, index }) {
  const canvasRef = useRef(null);
  const statRef = useRef(null);
  const { status, progress } = useTile(dashboard, agent.id);

  // Hand the canvas to the animation loop; the loop also writes the footer stat text.
  useEffect(() => dashboard.attach(agent.id, canvasRef.current, statRef.current), [dashboard, agent.id]);

  return (
    <article className="tile" data-status={status} aria-label={`${agent.name} agent`}>
      <div className="tile-head">
        <span className="n">{String(index + 1).padStart(2, '0')}</span>
        <b>{agent.name}</b>
        <span className="chip"><i></i><span>{LABEL[status] || status}</span></span>
      </div>
      <div className="tile-desc">{agent.desc}</div>
      <canvas ref={canvasRef} aria-hidden="true"></canvas>
      <div className="tile-foot">
        <span className="stat" ref={statRef}></span>
        <span className="bar"><i style={{ width: `${Math.round(progress * 100)}%` }}></i></span>
      </div>
    </article>
  );
}

export default function Board({ dashboard, working, total, clock }) {
  useEffect(() => { dashboard.start(); return () => dashboard.stop(); }, [dashboard]);

  return (
    <section className="board" aria-label="Agents">
      <div className="board-head">
        <h2>Agents</h2>
        <span id="working">{working} of {total} working</span>
        <span className="clock" id="clock">{clock}</span>
      </div>
      <div className="grid" id="grid">
        {dashboard.agents.map((a, i) => <AgentTile key={a.id} dashboard={dashboard} agent={a} index={i} />)}
      </div>
    </section>
  );
}
