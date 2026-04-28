/**
 * useLocalStorage — centralised localStorage hook (TD-039).
 *
 * Replaces scattered raw `localStorage.getItem` / `JSON.parse` / `setItem`
 * calls in App.jsx with a single abstraction that:
 *  - Handles JSON serialisation and deserialisation consistently
 *  - Recovers from JSON.parse errors (returns `defaultValue` instead of
 *    throwing — important for private-browsing environments where
 *    localStorage.getItem can return garbage or throw SecurityError)
 *  - Silently ignores write failures (e.g. storage quota exceeded,
 *    Firefox private-browsing restrictions) so the UI stays functional
 *
 * API is intentionally identical to useState so it can replace useState+
 * localStorage init pairs with zero refactoring of downstream code.
 *
 * @param {string} key           localStorage key
 * @param {*}      defaultValue  Value used when key is absent or unreadable
 * @returns {[value, setValue]}  Tuple matching useState's return shape
 */
import { useState, useCallback } from "react";

export function useLocalStorage(key, defaultValue) {
  const [value, setValueState] = useState(() => {
    try {
      const raw = localStorage.getItem(key);
      if (raw === null) return defaultValue;
      return JSON.parse(raw);
    } catch {
      return defaultValue;
    }
  });

  const setValue = useCallback((nextOrFn) => {
    setValueState(prev => {
      const next = typeof nextOrFn === "function" ? nextOrFn(prev) : nextOrFn;
      try {
        if (next === null || next === undefined) {
          localStorage.removeItem(key);
        } else {
          localStorage.setItem(key, JSON.stringify(next));
        }
      } catch {
        // Storage unavailable — state still updates in memory
      }
      return next;
    });
  }, [key]);

  return [value, setValue];
}
