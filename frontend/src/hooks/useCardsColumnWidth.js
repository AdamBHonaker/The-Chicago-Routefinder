import { useEffect, useState } from "react";
import { useLocalStorage } from "./useLocalStorage.js";

// Desktop cards-column width (px). User-resizable via the .panel-splitter
// handle between the cards and map panels. Persisted across sessions.
// Floors at CARDS_MIN_WIDTH; ceilings at viewport - rail - splitter - map min.
//
// Layout constants exported so call-sites that need to know rail/splitter widths
// (e.g. SideRail offset) share the same source of truth.
export const CARDS_MIN_WIDTH = 520;
export const MAP_MIN_WIDTH   = 320;
export const SIDE_RAIL_WIDTH = 60;
export const SPLITTER_WIDTH  = 6;

function computeMax(innerWidth) {
  return Math.max(
    CARDS_MIN_WIDTH,
    innerWidth - SIDE_RAIL_WIDTH - SPLITTER_WIDTH - MAP_MIN_WIDTH,
  );
}

export function useCardsColumnWidth() {
  const [width, setWidth] = useLocalStorage("cards_column_width", CARDS_MIN_WIDTH);
  const [max, setMax] = useState(() =>
    typeof window !== "undefined" ? computeMax(window.innerWidth) : CARDS_MIN_WIDTH
  );

  useEffect(() => {
    if (typeof window === "undefined") return;
    const recompute = () => {
      const next = computeMax(window.innerWidth);
      setMax(next);
      setWidth((prev) => Math.max(CARDS_MIN_WIDTH, Math.min(next, prev)));
    };
    recompute();
    window.addEventListener("resize", recompute);
    return () => window.removeEventListener("resize", recompute);
  }, [setWidth]);

  return { width, setWidth, max, min: CARDS_MIN_WIDTH };
}
