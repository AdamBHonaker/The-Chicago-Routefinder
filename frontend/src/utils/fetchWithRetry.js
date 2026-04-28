/**
 * fetchWithRetry — resilient fetch wrapper with exponential back-off (TD-040).
 *
 * Extracted from App.jsx so it can be independently unit-tested.
 *
 * @param {string}    url        URL to fetch.
 * @param {object}    options    Standard fetch init (method, headers, body, signal, …).
 *                               The signal is checked before every attempt and propagated
 *                               to fetch so in-flight requests cancel immediately on abort.
 * @param {number[]}  retryDelays  Array of back-off delays in ms. Length determines max
 *                               retries. Defaults to RETRY_DELAYS_MS from constants.js.
 * @param {function}  [onRetrying]  Called before each retry with the 1-based attempt
 *                               number so callers can render "retrying (1/3)" UI feedback.
 *
 * Retry policy:
 *   • 5xx responses and network errors are retried up to retryDelays.length times.
 *   • 4xx responses are NOT retried — client errors won't self-resolve.
 *   • AbortError is never retried — the caller explicitly cancelled.
 *   • After all retries are exhausted the last Response is returned so the caller
 *     can inspect the status and surface a user-facing error message.
 */
export async function fetchWithRetry(url, options, retryDelays, onRetrying) {
  for (let attempt = 0; attempt <= retryDelays.length; attempt++) {
    if (options.signal?.aborted) throw new DOMException("Aborted", "AbortError");
    let res;
    try {
      res = await fetch(url, options);
    } catch (err) {
      if (err.name === "AbortError") throw err;
      if (attempt < retryDelays.length) {
        onRetrying?.(attempt + 1);
        await new Promise(r => setTimeout(r, retryDelays[attempt]));
        continue;
      }
      throw err;
    }
    if (res.ok || res.status < 500) return res; // success or non-retryable client error
    if (attempt < retryDelays.length) {
      onRetrying?.(attempt + 1);
      await new Promise(r => setTimeout(r, retryDelays[attempt]));
      continue;
    }
    return res; // exhausted retries — caller handles the error response
  }
}
