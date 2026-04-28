/**
 * useApiQuery — lightweight server-state hook (TD-038).
 *
 * Centralises the data / loading / error pattern that previously appeared
 * ad-hoc throughout App.jsx. Drop-in alternative to adding TanStack Query as
 * a dependency: smaller bundle, same interface for this app's simple use cases.
 *
 * Features:
 *  - Automatic loading / error state tracking
 *  - AbortController — in-flight request is cancelled on unmount or when
 *    `deps` change, preventing stale-state updates
 *  - Optional polling via `refetchInterval` (milliseconds)
 *  - Manual refetch via the returned `refetch()` function
 *
 * @param {() => Promise<Response>} fetcher  Async function that returns a
 *   fetch Response. Receives an AbortSignal as its sole argument.
 * @param {Array}  deps           React dependency array — query reruns when
 *   any dep changes (same semantics as useEffect deps). IMPORTANT: this array
 *   is spread directly into a useEffect dep list, so its length MUST be
 *   constant across renders (React rules of hooks). Never pass a deps array
 *   whose length varies — use a single stable derived key instead.
 * @param {object} [opts]
 * @param {number} [opts.refetchInterval]  Poll every N ms. 0 or omit to disable.
 * @param {boolean} [opts.enabled=true]    Set false to skip the fetch entirely.
 *
 * @returns {{ data, loading, error, refetch }}
 */
import { useState, useEffect, useCallback, useRef } from "react";

export function useApiQuery(fetcher, deps = [], { refetchInterval = 0, enabled = true } = {}) {
  const [data, setData]       = useState(null);
  const [loading, setLoading] = useState(enabled);
  const [error, setError]     = useState(null);
  // Stable refetch trigger — incrementing fires a new fetch without needing a
  // dep-array change (avoids including `refetch` itself in the caller's deps).
  const [tick, setTick] = useState(0);
  const intervalRef = useRef(null);

  const refetch = useCallback(() => setTick(t => t + 1), []);

  useEffect(() => {
    if (!enabled) {
      setLoading(false);
      return;
    }

    const ctrl = new AbortController();
    setLoading(true);
    setError(null);

    fetcher(ctrl.signal)
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then(json => {
        if (!ctrl.signal.aborted) {
          setData(json);
          setLoading(false);
        }
      })
      .catch(err => {
        if (!ctrl.signal.aborted) {
          setError(err);
          setLoading(false);
        }
      });

    return () => ctrl.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, tick, ...deps]);

  // Polling — restart the interval whenever refetchInterval or enabled changes.
  useEffect(() => {
    if (!enabled || !refetchInterval) return;
    intervalRef.current = setInterval(() => setTick(t => t + 1), refetchInterval);
    return () => clearInterval(intervalRef.current);
  }, [enabled, refetchInterval]);

  return { data, loading, error, refetch };
}
