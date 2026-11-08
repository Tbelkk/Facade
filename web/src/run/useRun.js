// Connects any Explorer source (replay now, SpacetimeDB later) to React state.

import { useCallback, useEffect, useReducer, useRef, useState } from 'react';
import { initialRun, runReducer } from './runState.js';

export function useRun(source, { speed, timing }) {
  const [run, dispatch] = useReducer(runReducer, undefined, () => initialRun());
  const [records, setRecords] = useState({});
  const [status, setStatus] = useState('idle'); // idle | playing | paused | finished

  useEffect(() => {
    if (!source) return undefined;
    const off = source.subscribe({
      meta: (meta) => { dispatch({ type: 'meta', meta }); },
      records: (r) => setRecords(r),
      event: (evt, index) => dispatch({ type: 'event', evt, index }),
      done: () => { dispatch({ type: 'done' }); setStatus('finished'); },
    });
    setStatus('paused');
    return () => { source.pause && source.pause(); off && off(); };
  }, [source]);

  useEffect(() => { source && source.setSpeed && source.setSpeed(speed); }, [source, speed]);
  useEffect(() => { source && source.setTiming && source.setTiming(timing); }, [source, timing]);

  const doneRef = useRef(false);
  doneRef.current = run.done;

  const play = useCallback(() => { if (source && source.play) { source.play(); setStatus('playing'); } }, [source]);
  const toggle = useCallback(() => {
    if (!source || !source.play) return;
    if (doneRef.current) { source.restart(); setStatus('playing'); return; }
    if (source.playing) { source.pause(); setStatus('paused'); } else { source.play(); setStatus('playing'); }
  }, [source]);
  const restart = useCallback(() => { if (source && source.restart) { source.restart(); setStatus('playing'); } }, [source]);

  return { run, records, status: run.done ? 'finished' : status, play, toggle, restart };
}
