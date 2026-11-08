import { useSyncExternalStore } from 'react';

/** One tile's status and progress from the dashboard controller. */
export function useTile(dashboard, id) {
  useSyncExternalStore(dashboard.subscribe, () => dashboard.version(id));
  return dashboard.tile(id);
}
