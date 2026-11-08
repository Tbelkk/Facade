// "Ask RESTore": prompt box under the agent tiles. Answers come from lib/assistant.js.
import './assistant.css';

import { useEffect, useRef, useState, useSyncExternalStore } from 'react';
import { ask, intro, ready } from '../lib/assistant.js';

export default function Assistant({ store }) {
  const st = useSyncExternalStore(store.subscribe, store.get);
  const [msgs, setMsgs] = useState([]);          // { role: 'user' | 'ai', text, calls?, by? }
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const logRef = useRef(null);
  const inputRef = useRef(null);
  const start = intro(st);
  const open = ready(st);

  // a new run starts a new conversation
  useEffect(() => { setMsgs([]); setDraft(''); }, [st.site]);
  useEffect(() => { const el = logRef.current; if (el) el.scrollTop = el.scrollHeight; }, [msgs, busy]);

  const send = async (text) => {
    const q = String(text || '').trim();
    if (!q || busy || !ready(store.get())) return;
    const history = msgs.map((m) => ({ role: m.role === 'ai' ? 'assistant' : 'user', text: m.text }));
    setMsgs((m) => [...m, { role: 'user', text: q }]);
    setDraft('');
    setBusy(true);
    try {
      const a = await ask(store.get(), q, history);
      setMsgs((m) => [...m, { role: 'ai', ...a }]);
    } catch (e) {
      setMsgs((m) => [...m, { role: 'ai', text: `Something went wrong: ${e.message || e}`, calls: [] }]);
    } finally {
      setBusy(false);
      inputRef.current && inputRef.current.focus();
    }
  };

  return (
    <section className={'assistant' + (open ? '' : ' locked')} aria-labelledby="askTitle">
      <div className="ask-head">
        <h2 id="askTitle">Ask RESTore</h2>
        {open && <span className="ask-state">Ready · ask about the API data</span>}
        {msgs.length > 0 && <button type="button" className="mini" onClick={() => setMsgs([])}>Clear</button>}
      </div>

      <div className="ask-log" ref={logRef} aria-live="polite">
        {msgs.length === 0 ? (
          <div className="ask-empty">
            <p>{start.text}</p>
            <b className="ask-eg">{start.locked ? 'You’ll be able to ask things like' : 'Try asking'}</b>
            <div className="ask-chips">
              {start.examples.map((x) => <button type="button" key={x} className="ask-chip" disabled={!open} onClick={() => send(x)}>{x}</button>)}
            </div>
          </div>
        ) : msgs.map((m, i) => (
          <div key={i} className={'ask-msg ' + m.role}>
            <p>{m.text}</p>
            {m.calls && m.calls.length > 0 && (
              <ul className="ask-calls" aria-label="API calls used">
                {m.calls.map((c, j) => <li key={j}><b>{c.method}</b> {c.path}<span>{c.count} result{c.count === 1 ? '' : 's'}</span></li>)}
              </ul>
            )}
          </div>
        ))}
        {busy && <div className="ask-msg ai thinking"><span className="dots" aria-hidden="true"><i></i><i></i><i></i></span><span className="sr">Thinking</span></div>}
      </div>

      <form className="ask-form" onSubmit={(e) => { e.preventDefault(); send(draft); }}>
        <label className="ask-input">
          <span className="sr">Ask a question</span>
          <input ref={inputRef} type="text" value={draft} onChange={(e) => setDraft(e.target.value)} autoComplete="off" disabled={!open}
            placeholder={!open ? 'Available once a site has been read and its API built' : msgs.length ? 'Ask a follow-up…' : 'Ask about the data RESTore found…'} />
        </label>
        <button type="submit" className="btn primary" disabled={!open || !draft.trim() || busy}>Ask</button>
      </form>
    </section>
  );
}
