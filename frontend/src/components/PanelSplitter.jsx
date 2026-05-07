import { useCallback, useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";

/**
 * Vertical splitter handle between the desktop cards column and the map.
 *
 * Pointer drag updates `value` via `onChange` (rAF-throttled). The final
 * committed value is reported once on `pointerup` via `onCommit`, which is
 * where the parent should persist to localStorage.
 *
 * Keyboard: arrow keys nudge ±16px, Home/End jump to min/max. The handle is
 * focusable and announces a `separator` role with aria-valuenow / min / max
 * for assistive tech. Hidden on mobile via CSS (.panel-splitter display:none
 * inside the @media max-width:800px block).
 *
 * RTL: when i18n.dir() === "rtl" the CSS grid auto-flips, so the side rail
 * sits on the right edge and the cards column to the right of the map. The
 * pointer math inverts accordingly so `value` consistently measures the
 * cards-column width from the rail-side edge.
 */
const KEY_STEP_PX = 16;

export default function PanelSplitter({ value, min, max, onChange, onCommit, offsetLeft = 0 }) {
  const { t, i18n } = useTranslation();
  const ref = useRef(null);
  const draggingRef = useRef(false);
  const rafIdRef = useRef(null);
  const pendingValueRef = useRef(null);
  // Tracks the most recent dragged value so endDrag can commit it without
  // waiting for the parent's setState (driven by onChange) to reflect into
  // the `value` prop. See BUG-010.
  const lastValueRef = useRef(null);

  const clamp = useCallback((v) => Math.max(min, Math.min(max, v)), [min, max]);

  const flushRaf = useCallback(() => {
    rafIdRef.current = null;
    if (pendingValueRef.current != null) {
      onChange(pendingValueRef.current);
      pendingValueRef.current = null;
    }
  }, [onChange]);

  const queueChange = useCallback((next) => {
    pendingValueRef.current = next;
    lastValueRef.current = next;
    if (rafIdRef.current == null) {
      rafIdRef.current = requestAnimationFrame(flushRaf);
    }
  }, [flushRaf]);

  const handlePointerDown = useCallback((e) => {
    if (e.button !== 0 && e.pointerType === "mouse") return;
    e.preventDefault();
    draggingRef.current = true;
    ref.current?.setPointerCapture?.(e.pointerId);
    if (ref.current) ref.current.dataset.dragging = "true";
  }, []);

  const handlePointerMove = useCallback((e) => {
    if (!draggingRef.current) return;
    const isRtl = typeof i18n?.dir === "function" && i18n.dir() === "rtl";
    const next = isRtl
      ? (typeof window !== "undefined" ? window.innerWidth : 0) - e.clientX - offsetLeft
      : e.clientX - offsetLeft;
    queueChange(clamp(next));
  }, [clamp, i18n, offsetLeft, queueChange]);

  const endDrag = useCallback((e) => {
    if (!draggingRef.current) return;
    draggingRef.current = false;
    ref.current?.releasePointerCapture?.(e.pointerId);
    if (ref.current) delete ref.current.dataset.dragging;
    if (rafIdRef.current != null) {
      cancelAnimationFrame(rafIdRef.current);
      flushRaf();
    }
    // Prefer the most recent dragged value (captured synchronously by
    // queueChange) over the prop, which lags by one render after flushRaf's
    // onChange schedules its setState.
    const committed = lastValueRef.current ?? value;
    lastValueRef.current = null;
    onCommit?.(clamp(committed));
  }, [clamp, flushRaf, onCommit, value]);

  // Arrow keys map to writing-direction-natural sides (per WAI-ARIA). In RTL
  // ArrowLeft grows the cards column (which sits on the right) and ArrowRight
  // shrinks it.
  const handleKeyDown = useCallback((e) => {
    const isRtl = typeof i18n?.dir === "function" && i18n.dir() === "rtl";
    let next = null;
    if (e.key === "ArrowLeft")       next = clamp(value + (isRtl ? KEY_STEP_PX : -KEY_STEP_PX));
    else if (e.key === "ArrowRight") next = clamp(value + (isRtl ? -KEY_STEP_PX : KEY_STEP_PX));
    else if (e.key === "Home")       next = min;
    else if (e.key === "End")        next = max;
    if (next != null) {
      e.preventDefault();
      onChange(next);
      onCommit?.(next);
    }
  }, [clamp, i18n, max, min, onChange, onCommit, value]);

  useEffect(() => () => {
    if (rafIdRef.current != null) cancelAnimationFrame(rafIdRef.current);
  }, []);

  return (
    <div
      ref={ref}
      className="panel-splitter"
      role="separator"
      aria-orientation="vertical"
      aria-valuenow={Math.round(value)}
      aria-valuemin={min}
      aria-valuemax={max}
      aria-label={t("splitter_aria_label", { defaultValue: "Resize cards and map panels" })}
      tabIndex={0}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={endDrag}
      onPointerCancel={endDrag}
      onLostPointerCapture={endDrag}
      onKeyDown={handleKeyDown}
    />
  );
}
