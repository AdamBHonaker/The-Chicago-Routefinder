import { useState, useRef, useEffect, useLayoutEffect, useCallback, useMemo } from "react";

/* ─────────────────────────────────────────────────────────────────────────
 * BottomSheet — portable, project-agnostic draggable sheet.
 *
 * Design rules (read before editing):
 *
 *  • Snap-by-translate. The sheet's height in DOM is always the LARGEST
 *    snap. Smaller snaps are achieved by translating the sheet downward
 *    via transform: translateY(N px). This keeps the body's scroll
 *    position stable across snap changes — height-based snapping caused
 *    visible scrollbar jumps.
 *
 *  • Body-scroll handoff. Pointer-down inside the body is observed but not
 *    captured. On the first pointermove past BODY_DRAG_DEADZONE_PX:
 *      scrollTop === 0 + downward → drag the sheet (capture pointer)
 *      anything else              → release; let the body scroll natively
 *    Once committed, no mid-gesture flips. This avoids the "scroll-vs-drag"
 *    fight that single-handler implementations always lose.
 *
 *  • Velocity-aware settle. On release we look at the trailing
 *    SHEET_VELOCITY_WINDOW_MS of pointer samples. A flick above
 *    SHEET_VELOCITY_THRESHOLD px/ms promotes/demotes ONE snap in the
 *    direction of motion; below threshold, we settle to the nearest snap.
 *    Reduced-motion users always get nearest (the velocity feel is itself
 *    a motion signal).
 *
 *  • Theming via CSS variables only. The component reads --bsk-*
 *    custom properties (paper, ink, mute-fog, ease, dur, safe-bottom,
 *    shadow, handle-focus). The host project binds these to its own design
 *    tokens. Zero hardcoded colors / timings — that's what makes this kit
 *    portable across projects.
 *
 *  • i18n. The drag handle's accessible name comes from the `handleLabel`
 *    prop. The kit ships no hardcoded user-facing strings; the host
 *    supplies pre-translated text.
 *
 *  • Haptic on settle. navigator.vibrate(10) fires only when the snap
 *    actually changed AND reduced-motion is off. iOS Safari ignores it
 *    silently (no-op); Android Chrome honours it.
 * ───────────────────────────────────────────────────────────────────── */

// Tunables. Exported so unit tests and host projects can introspect them.
export const SHEET_VELOCITY_THRESHOLD = 0.8;     // px/ms; above this = flick
export const SHEET_VELOCITY_WINDOW_MS = 80;      // trailing window for velocity
export const BODY_DRAG_DEADZONE_PX    = 8;       // travel before commit

function pointerNow() {
  if (typeof performance !== "undefined" && typeof performance.now === "function") {
    return performance.now();
  }
  return Date.now();
}

// Resolve a snap-point string ("120px" / "50%" / "88dvh") to pixels against
// a parent-element height. Numbers pass through. Exported for tests.
export function resolveSnapPx(value, containerHeight) {
  if (typeof value === "number") return value;
  const m = String(value).trim().match(/^(-?\d*\.?\d+)(px|%|dvh|vh)?$/);
  if (!m) return 0;
  const n = parseFloat(m[1]);
  const unit = m[2] || "px";
  if (unit === "px") return n;
  if (unit === "%")  return Math.round((containerHeight || 0) * n / 100);
  if (unit === "dvh" || unit === "vh") {
    const vh = typeof window !== "undefined" ? window.innerHeight : (containerHeight || 0);
    return Math.round(vh * n / 100);
  }
  return n;
}

// Pure function picking the snap to settle on after a drag release.
// Exported for tests. See "Velocity-aware settle" in the file header.
export function decideSnap({ samples, currentSnap, finalTranslate, snapPx, maxHeightPx, reducedMotion }) {
  let nearestIdx = 0;
  let nearestDist = Infinity;
  for (let i = 0; i < snapPx.length; i++) {
    const rest = Math.max(0, maxHeightPx - snapPx[i]);
    const dist = Math.abs(rest - finalTranslate);
    if (dist < nearestDist) { nearestDist = dist; nearestIdx = i; }
  }
  if (reducedMotion || !samples || samples.length < 2) return nearestIdx;

  const last = samples[samples.length - 1];
  let firstIdx = samples.length - 1;
  for (let i = samples.length - 1; i >= 0; i--) {
    if (last.t - samples[i].t <= SHEET_VELOCITY_WINDOW_MS) firstIdx = i;
    else break;
  }
  const first = samples[firstIdx];
  const dt = last.t - first.t;
  if (dt <= 0) return nearestIdx;
  const velocity = (last.y - first.y) / dt; // px/ms; negative = upward
  if (Math.abs(velocity) <= SHEET_VELOCITY_THRESHOLD) return nearestIdx;
  // Pointer y decreases as the user drags up, which exposes a *larger*
  // snap (snapPoints is ascending), so an upward fling raises the index.
  const sign = velocity < 0 ? +1 : -1;
  return Math.max(0, Math.min(snapPx.length - 1, currentSnap + sign));
}

export function BottomSheet({
  open = true,
  snapPoints = ["140px", "50dvh", "88dvh"],
  snap,
  defaultSnap = 1,
  onSnapChange,
  obscuredAreaCallback,
  handleLabel = "Drag to resize panel",
  children,
  style = {},
  className = "",
  ...rest
}) {
  const containerRef = useRef(null);
  const dragStateRef = useRef(null);   // { startY, startTranslate, pointerId, samples }
  const bodyDragRef  = useRef(null);   // body-drag state machine
  const reducedMotionRef = useRef(false);

  const [containerHeight, setContainerHeight] = useState(0);
  const [internalSnap, setInternalSnap] = useState(defaultSnap);
  const [isDragging, setIsDragging] = useState(false);
  const [dragTranslate, setDragTranslate] = useState(null);

  const isControlled = snap !== undefined;
  const currentSnap = isControlled ? snap : internalSnap;

  // Memoised so the useCallbacks below stay cached across renders.
  const snapPx = useMemo(
    () => snapPoints.map(p => resolveSnapPx(p, containerHeight)),
    [snapPoints, containerHeight],
  );
  const sheetHeight   = snapPx[currentSnap] ?? snapPx[snapPx.length - 1] ?? 0;
  const maxHeightPx   = snapPx[snapPx.length - 1] ?? 0;
  const restingTranslate = Math.max(0, maxHeightPx - sheetHeight);
  const translateY = isDragging && dragTranslate != null ? dragTranslate : restingTranslate;

  // Track parent height so % / dvh snap points stay current across resizes.
  useLayoutEffect(() => {
    const el = containerRef.current;
    if (!el || !el.parentElement) return;
    const parent = el.parentElement;
    const update = () => {
      const h = parent.clientHeight || (typeof window !== "undefined" ? window.innerHeight : 0);
      setContainerHeight(h);
    };
    update();
    let ro;
    if (typeof ResizeObserver !== "undefined") {
      ro = new ResizeObserver(update);
      ro.observe(parent);
    }
    if (typeof window !== "undefined") window.addEventListener("resize", update);
    return () => {
      ro?.disconnect();
      if (typeof window !== "undefined") window.removeEventListener("resize", update);
    };
  }, []);

  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const mql = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => { reducedMotionRef.current = mql.matches; };
    update();
    mql.addEventListener?.("change", update);
    return () => mql.removeEventListener?.("change", update);
  }, []);

  useEffect(() => {
    if (obscuredAreaCallback) obscuredAreaCallback(sheetHeight);
  }, [sheetHeight, obscuredAreaCallback]);

  const settleToSnap = useCallback((idx) => {
    const clamped = Math.max(0, Math.min(snapPx.length - 1, idx));
    if (!isControlled) setInternalSnap(clamped);
    onSnapChange?.(clamped);
  }, [snapPx.length, isControlled, onSnapChange]);

  const onPointerDown = useCallback((e) => {
    if (e.button != null && e.button !== 0) return;
    e.currentTarget.setPointerCapture?.(e.pointerId);
    dragStateRef.current = {
      startY: e.clientY,
      startTranslate: restingTranslate,
      pointerId: e.pointerId,
      samples: [{ t: pointerNow(), y: e.clientY }],
    };
    setIsDragging(true);
    setDragTranslate(restingTranslate);
  }, [restingTranslate]);

  const onPointerMove = useCallback((e) => {
    const ds = dragStateRef.current;
    if (!ds || ds.pointerId !== e.pointerId) return;
    const delta = e.clientY - ds.startY;
    const next = Math.max(0, Math.min(maxHeightPx, ds.startTranslate + delta));
    setDragTranslate(next);
    ds.samples.push({ t: pointerNow(), y: e.clientY });
    if (ds.samples.length > 6) ds.samples.shift();
  }, [maxHeightPx]);

  // Shared settle path used by both the handle's pointerup and the body's
  // pointerup-while-dragging branch (TD-FE-022). Runs decideSnap, fires the
  // haptic pulse if the snap actually changed, clears the supplied drag-state
  // ref, and commits the settle. Keeps the two release sites in lock-step.
  const commitDragRelease = useCallback((samples, stateRef) => {
    const finalTranslate = dragTranslate ?? restingTranslate;
    const targetIdx = decideSnap({
      samples,
      currentSnap,
      finalTranslate,
      snapPx,
      maxHeightPx,
      reducedMotion: reducedMotionRef.current,
    });
    if (
      targetIdx !== currentSnap
      && !reducedMotionRef.current
      && typeof navigator !== "undefined"
      && typeof navigator.vibrate === "function"
    ) {
      try { navigator.vibrate(10); } catch { /* not supported */ }
    }
    stateRef.current = null;
    setIsDragging(false);
    setDragTranslate(null);
    settleToSnap(targetIdx);
  }, [dragTranslate, restingTranslate, snapPx, maxHeightPx, settleToSnap, currentSnap]);

  const onPointerUp = useCallback((e) => {
    const ds = dragStateRef.current;
    if (!ds || ds.pointerId !== e.pointerId) return;
    e.currentTarget.releasePointerCapture?.(e.pointerId);
    commitDragRelease(ds.samples, dragStateRef);
  }, [commitDragRelease]);

  // Body-drag with scroll handoff (see "Body-scroll handoff" in header).
  const onBodyPointerDown = useCallback((e) => {
    if (e.button != null && e.button !== 0) return;
    bodyDragRef.current = {
      phase: "pending",
      startY: e.clientY,
      startScrollTop: e.currentTarget.scrollTop || 0,
      startTranslate: restingTranslate,
      pointerId: e.pointerId,
      samples: [{ t: pointerNow(), y: e.clientY }],
    };
  }, [restingTranslate]);

  const onBodyPointerMove = useCallback((e) => {
    const bs = bodyDragRef.current;
    if (!bs || bs.pointerId !== e.pointerId) return;
    const delta = e.clientY - bs.startY;

    if (bs.phase === "pending") {
      if (Math.abs(delta) < BODY_DRAG_DEADZONE_PX) return;
      const goingDown = delta > 0;
      if (goingDown && bs.startScrollTop === 0) {
        e.currentTarget.setPointerCapture?.(e.pointerId);
        bs.phase = "dragging";
        setIsDragging(true);
        setDragTranslate(Math.max(0, Math.min(maxHeightPx, bs.startTranslate + delta)));
        bs.samples.push({ t: pointerNow(), y: e.clientY });
      } else {
        bs.phase = "released";
      }
      return;
    }

    if (bs.phase === "dragging") {
      const next = Math.max(0, Math.min(maxHeightPx, bs.startTranslate + delta));
      setDragTranslate(next);
      bs.samples.push({ t: pointerNow(), y: e.clientY });
      if (bs.samples.length > 6) bs.samples.shift();
    }
    // released: let the browser handle native scroll.
  }, [maxHeightPx]);

  const onBodyPointerUp = useCallback((e) => {
    const bs = bodyDragRef.current;
    if (!bs || bs.pointerId !== e.pointerId) return;
    if (bs.phase === "dragging") {
      e.currentTarget.releasePointerCapture?.(e.pointerId);
      commitDragRelease(bs.samples, bodyDragRef);
      return;
    }
    bodyDragRef.current = null;
  }, [commitDragRelease]);

  if (!open) return null;

  // While dragging: instant tracking. While settling: transition with the
  // host project's easing/duration tokens. Reduced motion → 0ms.
  const transition = isDragging
    ? "none"
    : reducedMotionRef.current
      ? "transform 0ms"
      : `transform var(--bsk-dur, 320ms) var(--bsk-ease, cubic-bezier(.22,.61,.36,1))`;

  return (
    <div
      ref={containerRef}
      className={`bottom-sheet ${className}`.trim()}
      style={{
        position: "absolute",
        left: 0,
        right: 0,
        bottom: 0,
        height: maxHeightPx || "auto",
        transform: `translateY(${translateY}px)`,
        transition,
        zIndex: 20,
        ...style,
      }}
      role="dialog"
      aria-modal="false"
      {...rest}
    >
      <button
        type="button"
        className="bottom-sheet__handle"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        aria-label={handleLabel}
      >
        <span aria-hidden="true" className="bottom-sheet__handle-pill" />
        <span aria-hidden="true" className="bottom-sheet__handle-rule" />
      </button>
      <div
        className="bottom-sheet__body"
        onPointerDown={onBodyPointerDown}
        onPointerMove={onBodyPointerMove}
        onPointerUp={onBodyPointerUp}
        onPointerCancel={onBodyPointerUp}
      >
        {children}
      </div>
    </div>
  );
}
