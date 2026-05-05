// Tiny event-tracking helper (FEAT-006). Fire-and-forget POST to /events;
// failures are swallowed because analytics is best-effort and must never
// degrade the user experience. ``keepalive: true`` lets the request finish
// even if the page unmounts immediately after the call (matters for the
// trip_completed event, which often fires near a navigation away).
//
// The session cookie travels via ``credentials: "include"`` so the backend
// can correlate this event to the same FEAT-001 session that /ping started.
// No client-side queueing, no retries — the server-side allowlist is the
// only meaningful contract.

import { BACKEND_URL } from "./constants.js";

export function track(name) {
  try {
    fetch(`${BACKEND_URL}/events`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      keepalive: true,
      body: JSON.stringify({ name }),
    }).catch(() => {});
  } catch {
    // ignore — analytics must never throw past this boundary
  }
}
