import { useEffect } from "react";
import { BYOK_ENABLED, BYOK_IDLE_TIMEOUT_MS } from "../constants.js";

/**
 * Auto-clears the BYOK API key from sessionStorage after a period of mouse/keyboard
 * inactivity. Only active when a key is stored and BYOK is enabled.
 *
 * @param {string}   byokKey    Current API key value.
 * @param {Function} setByokKey State setter to clear the key.
 */
// Grace period before clearing the key after the tab is backgrounded. Short
// tab-switches (Alt-Tabbing to copy something, glancing at a calendar) shouldn't
// nuke an in-progress key entry, but leaving the tab hidden for more than a
// minute on a shared device is a clear "user walked away" signal.
const BYOK_HIDDEN_GRACE_MS = 60 * 1000;

export function useByokIdleClear(byokKey, setByokKey) {
  useEffect(() => {
    if (!BYOK_ENABLED || !byokKey) return;
    let idleTimer;
    let hiddenTimer;
    // Activity events update only this timestamp — no timer churn (OPT-FE-203).
    // A single self-rescheduling idleTimer polls the timestamp at most once per
    // BYOK_IDLE_TIMEOUT_MS, so mousemove at desktop refresh rates costs one
    // ref write per event instead of clearTimeout+setTimeout.
    let lastActivity = Date.now();
    const clearKey = () => {
      sessionStorage.removeItem("byok_api_key");
      setByokKey("");
    };
    const checkIdle = () => {
      const elapsed = Date.now() - lastActivity;
      if (elapsed >= BYOK_IDLE_TIMEOUT_MS) {
        clearKey();
        return;
      }
      idleTimer = setTimeout(checkIdle, BYOK_IDLE_TIMEOUT_MS - elapsed);
    };
    const onActivity = () => { lastActivity = Date.now(); };
    // pointerdown covers mouse, pen, and touch on modern browsers; mousemove
    // and keydown are kept for desktop users who don't generate pointer events
    // unless they click. (BUG-020: previously missed all touch-only input.)
    const events = ["mousemove", "keydown", "pointerdown", "touchstart"];
    events.forEach((ev) => window.addEventListener(ev, onActivity, { passive: true }));
    // Visibility-based clear: idle events don't fire while the tab is hidden,
    // so a user who walks away with the tab backgrounded would otherwise keep
    // the key alive for the full BYOK_IDLE_TIMEOUT_MS. Wipe after a short grace.
    const onVisibilityChange = () => {
      if (document.visibilityState === "hidden") {
        hiddenTimer = setTimeout(clearKey, BYOK_HIDDEN_GRACE_MS);
      } else {
        clearTimeout(hiddenTimer);
        lastActivity = Date.now();
      }
    };
    document.addEventListener("visibilitychange", onVisibilityChange);
    idleTimer = setTimeout(checkIdle, BYOK_IDLE_TIMEOUT_MS);
    return () => {
      clearTimeout(idleTimer);
      clearTimeout(hiddenTimer);
      events.forEach((ev) => window.removeEventListener(ev, onActivity));
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
  }, [byokKey, setByokKey]);
}
