import { useEffect } from "react";
import { looksHostile } from "../utils/validateShareInput.js";

// Reads ?from= / ?to= / ?route= from the URL on mount and triggers an
// auto-submit through `onShare`. Extracted from App.jsx (TD-FE-006).
//
// The callback signature mirrors what App needs:
//   onShare({ from, to, routeIndex }) — should update form state and
//   call performSearch. Effect runs only once on mount; the caller is
//   responsible for ensuring the callback closes over fresh enough refs.
export function useShareLink(onShare) {
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const from = params.get("from");
    const to   = params.get("to");
    const routeIndex = parseInt(params.get("route") ?? "0", 10) || 0;
    if (from && to && !looksHostile(from) && !looksHostile(to)) {
      onShare({ from, to, routeIndex });
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
}
