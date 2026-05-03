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
    const clearKey = () => {
      sessionStorage.removeItem("byok_api_key");
      setByokKey("");
    };
    const resetTimer = () => {
      clearTimeout(idleTimer);
      idleTimer = setTimeout(clearKey, BYOK_IDLE_TIMEOUT_MS);
    };
    // pointerdown covers mouse, pen, and touch on modern browsers; mousemove
    // and keydown are kept for desktop users who don't generate pointer events
    // unless they click. (BUG-020: previously missed all touch-only input.)
    const events = ["mousemove", "keydown", "pointerdown", "touchstart"];
    events.forEach((ev) => window.addEventListener(ev, resetTimer, { passive: true }));
    // Visibility-based clear: idle events don't fire while the tab is hidden,
    // so a user who walks away with the tab backgrounded would otherwise keep
    // the key alive for the full BYOK_IDLE_TIMEOUT_MS. Wipe after a short grace.
    const onVisibilityChange = () => {
      if (document.visibilityState === "hidden") {
        hiddenTimer = setTimeout(clearKey, BYOK_HIDDEN_GRACE_MS);
      } else {
        clearTimeout(hiddenTimer);
        resetTimer();
      }
    };
    document.addEventListener("visibilitychange", onVisibilityChange);
    resetTimer();
    return () => {
      clearTimeout(idleTimer);
      clearTimeout(hiddenTimer);
      events.forEach((ev) => window.removeEventListener(ev, resetTimer));
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
  }, [byokKey, setByokKey]);
}
