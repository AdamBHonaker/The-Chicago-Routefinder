import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { ARRIVED_TOAST_DISMISS_MS } from "../constants.js";

// Trip-completion toast. Mounted unconditionally at the App root; renders
// only when `tripActive` flips from true → false with the user near the
// destination (App fires `onArrived` via the MapView's arrived latch).
//
// Owns its own timer + visibility state so App.jsx doesn't carry the
// show/auto-dismiss/reset-on-trip-end scaffolding (TD-FE-020).
//
// API: provide `arrivedSignal` — any value that changes when a new arrival
// should be shown. Pass `tripActive` so the toast clears the moment the
// trip ends rather than waiting out the auto-dismiss timer.
export default function ArrivedToast({ arrivedSignal, tripActive }) {
  const { t } = useTranslation();
  const [show, setShow] = useState(false);

  // Reveal whenever arrivedSignal changes to a truthy value.
  useEffect(() => {
    if (arrivedSignal) setShow(true);
  }, [arrivedSignal]);

  // Clear when the trip ends.
  useEffect(() => {
    if (!tripActive) setShow(false);
  }, [tripActive]);

  // Auto-dismiss after the configured timeout.
  useEffect(() => {
    if (!show) return;
    const id = setTimeout(() => setShow(false), ARRIVED_TOAST_DISMISS_MS);
    return () => clearTimeout(id);
  }, [show]);

  if (!show) return null;
  return (
    <div
      className="special-dispatch special-dispatch--arrived"
      role="alert"
      onClick={() => setShow(false)}
    >
      <span className="special-dispatch__kicker">{t("map_arrived_kicker")}</span>
      <p className="special-dispatch__body">{t("map_arrived_body")}</p>
    </div>
  );
}
