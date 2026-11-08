import { useEffect, useState, useSyncExternalStore } from 'react';
import { facadeSettings } from './settings.js';

/** Current settings; re-renders whenever they change. */
export function useSettings() {
  const [s, setS] = useState(() => facadeSettings.get());
  useEffect(() => facadeSettings.onChange(setS), []);
  return s;
}

/** One tile's status and progress from the dashboard controller. */
export function useTile(dashboard, id) {
  useSyncExternalStore(dashboard.subscribe, () => dashboard.version(id));
  return dashboard.tile(id);
}
