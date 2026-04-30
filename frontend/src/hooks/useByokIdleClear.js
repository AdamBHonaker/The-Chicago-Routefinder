import { useEffect } from "react";
import { BYOK_ENABLED, BYOK_IDLE_TIMEOUT_MS } from "../constants.js";

/**
 * Auto-clears the BYOK API key from sessionStorage after a period of mouse/keyboard
 * inactivity. Only active when a key is stored and BYOK is enabled.
 *
 * @param {string}   byokKey    Current API key value.
 * @param {Function} setByokKey State setter to clear the key.
 */
export function useByokIdleClear(byokKey, setByokKey) {
  useEffect(() => {
    if (!BYOK_ENABLED || !byokKey) return;
    let idleTimer;
    const resetTimer = () => {
      clearTimeout(idleTimer);
      idleTimer = setTimeout(() => {
        sessionStorage.removeItem("byok_api_key");
        setByokKey("");
      }, BYOK_IDLE_TIMEOUT_MS);
    };
    // pointerdown covers mouse, pen, and touch on modern browsers; mousemove
    // and keydown are kept for desktop users who don't generate pointer events
    // unless they click. (BUG-020: previously missed all touch-only input.)
    const events = ["mousemove", "keydown", "pointerdown", "touchstart"];
    events.forEach((ev) => window.addEventListener(ev, resetTimer, { passive: true }));
    resetTimer();
    return () => {
      clearTimeout(idleTimer);
      events.forEach((ev) => window.removeEventListener(ev, resetTimer));
    };
  }, [byokKey, setByokKey]);
}
