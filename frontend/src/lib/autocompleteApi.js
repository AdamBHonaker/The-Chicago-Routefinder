// Thin client over `GET /autocomplete`. Returns the backend's `suggestions`
// list verbatim (each entry: `{label, value, type}`) plus a normalized error
// path that matches the rest of the API helpers in this app.
//
// The consumer-supplied AbortSignal lets a fresh keystroke cancel an in-flight
// call — the typeahead never lingers past the next character the user types.

import { BACKEND_URL } from "../constants.js";

// Tighter than the route/recommend timeouts — typeahead requests must not
// linger past the next keystroke. 5 s is generous given the local-first
// cascade resolves nearly every query in < 10 ms.
const AUTOCOMPLETE_FETCH_TIMEOUT_MS = 5_000;

/**
 * @param {string}      query
 * @param {Object}      [opts]
 * @param {AbortSignal} [opts.signal]
 * @returns {Promise<Array<{label: string, value: string, type: string}>>}
 */
export async function fetchAutocomplete(query, { signal } = {}) {
  const trimmed = (query || "").trim();
  if (!trimmed) return [];

  // Compose an internal AbortController that aborts both on caller cancel and
  // on our own timeout. The component's per-keystroke abort still fires
  // through `signal`; the timeout is a backstop for a hung backend.
  const controller = new AbortController();
  const timeoutId = setTimeout(
    () => controller.abort(new DOMException("Timeout", "AbortError")),
    AUTOCOMPLETE_FETCH_TIMEOUT_MS,
  );
  const onCallerAbort = () => controller.abort(signal.reason);
  if (signal) {
    if (signal.aborted) {
      clearTimeout(timeoutId);
      throw new DOMException("Aborted", "AbortError");
    }
    signal.addEventListener("abort", onCallerAbort);
  }

  const url = new URL(`${BACKEND_URL}/autocomplete`);
  url.searchParams.set("q", trimmed);

  try {
    const res = await fetch(url.toString(), {
      method: "GET",
      signal: controller.signal,
    });
    if (!res.ok) {
      const err = new Error(`Autocomplete failed (${res.status})`);
      err.status = res.status;
      throw err;
    }
    const data = await res.json();
    return Array.isArray(data?.suggestions) ? data.suggestions : [];
  } finally {
    clearTimeout(timeoutId);
    if (signal) signal.removeEventListener("abort", onCallerAbort);
  }
}
