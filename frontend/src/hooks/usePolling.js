import { useEffect, useRef } from 'react';

/**
 * Generic polling hook. Calls `callback` immediately, then every `intervalMs`.
 * Stops polling when the component unmounts or `enabled` is false.
 */
export function usePolling(callback, intervalMs = 5000, enabled = true) {
  const savedCallback = useRef(callback);

  useEffect(() => {
    savedCallback.current = callback;
  }, [callback]);

  useEffect(() => {
    if (!enabled) return;

    let cancelled = false;

    const tick = async () => {
      if (cancelled) return;
      try {
        await savedCallback.current();
      } catch {
        // silently swallow — caller handles errors in their callback
      }
    };

    tick();
    const id = setInterval(tick, intervalMs);

    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [intervalMs, enabled]);
}
