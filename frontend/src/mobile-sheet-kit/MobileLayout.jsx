import { useState, useCallback, useEffect, useRef, useMemo } from "react";
import { BottomSheet } from "./BottomSheet.jsx";
import { createSheetSnapStore } from "./sheetSnap.js";

/* ─────────────────────────────────────────────────────────────────────────
 * MobileLayout — recommended composition root for a mobile map screen.
 *
 *   ┌──────────────────────────────────────────────┐
 *   │  optional <masthead/>  (floating, top edge)  │
 *   │                                              │
 *   │      [ map content shows through here ]      │
 *   │                                              │
 *   │  ╭────────────────────────────────────────╮  │
 *   │  │  drag handle                           │  │
 *   │  │  sheet body — snap 0 / 1 / 2           │  │
 *   │  ╰────────────────────────────────────────╯  │
 *   └──────────────────────────────────────────────┘
 *
 * Two integration patterns:
 *
 *   (a) Pass `map` — kit renders a full-bleed map slot inside .mobile-shell.
 *       Simpler. Works when the host can remount the map on layout change.
 *
 *   (b) Don't pass `map` — kit renders just (masthead + sheet). Host
 *       positions its own map element underneath (e.g. as a sibling at the
 *       App level). Recommended when the map's identity must survive
 *       breakpoint flips (MapLibre / Mapbox lose their WebGL context if
 *       remounted, leading to a blank canvas + tile re-fetch).
 *
 * The kit owns one piece of state: the most recent USER-INITIATED snap
 * settle gets persisted (debounced 500 ms). Programmatic snap changes
 * pass through `onSnapChange` for the host to handle but are NOT
 * persisted by the kit. (Why: callers usually want to auto-promote the
 * sheet on certain events without polluting the user's preferred opening
 * height across sessions.)
 *
 * Props:
 *   masthead         — optional floating header JSX
 *   map              — optional map JSX. Omit to use pattern (b).
 *   snap             — controlled snap index (0..n-1)
 *   defaultSnap      — uncontrolled initial snap (default 0)
 *   onSnapChange     — fires on every settle, after debounced persist
 *   onObscuredChange — fires with the px the sheet currently obscures
 *   snapPoints       — override default snap heights
 *   storageKey       — localStorage key for persistence (required)
 *   handleLabel      — i18n'd accessible label on the drag handle
 *   children         — sheet body content
 * ───────────────────────────────────────────────────────────────────── */

const DEFAULT_SNAP_POINTS = ["140px", "50dvh", "88dvh"];

// 500 ms is long enough to coalesce a "drag through 1 to 2" sequence into
// one write, short enough that a quick close + reload still captures the
// user's intent.
const SNAP_PERSIST_DELAY_MS = 500;

export function MobileLayout({
  masthead,
  map,
  snap,
  defaultSnap = 0,
  onSnapChange,
  onObscuredChange,
  snapPoints = DEFAULT_SNAP_POINTS,
  storageKey,
  handleLabel,
  children,
}) {
  if (!storageKey) {
    throw new Error("MobileLayout: storageKey prop is required");
  }
  // Memoise so the persistence store identity is stable for the lifetime
  // of this layout, even if storageKey is a literal string passed inline.
  const store = useMemo(() => createSheetSnapStore(storageKey), [storageKey]);

  const isControlled = snap !== undefined;
  const [internalSnap, setInternalSnap] = useState(defaultSnap);
  const currentSnap = isControlled ? snap : internalSnap;

  const persistTimerRef = useRef(null);
  useEffect(() => () => clearTimeout(persistTimerRef.current), []);

  // BottomSheet.onSnapChange fires from drag releases (not from prop
  // changes), so any value reaching this handler is user-initiated and
  // worth persisting.
  const handleSnapChange = useCallback((idx) => {
    if (!isControlled) setInternalSnap(idx);
    onSnapChange?.(idx);
    clearTimeout(persistTimerRef.current);
    persistTimerRef.current = setTimeout(
      () => store.save(idx),
      SNAP_PERSIST_DELAY_MS,
    );
  }, [isControlled, onSnapChange, store]);

  return (
    <div className="mobile-shell">
      {map && (
        <div className="mobile-shell-map">
          {map}
        </div>
      )}
      {masthead && (
        <div className="mobile-shell-header">
          {masthead}
        </div>
      )}
      <BottomSheet
        snap={currentSnap}
        onSnapChange={handleSnapChange}
        snapPoints={snapPoints}
        obscuredAreaCallback={onObscuredChange}
        handleLabel={handleLabel}
      >
        {children}
      </BottomSheet>
    </div>
  );
}
