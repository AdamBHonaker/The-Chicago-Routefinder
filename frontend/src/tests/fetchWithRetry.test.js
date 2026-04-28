/**
 * Unit tests for fetchWithRetry (TD-040).
 *
 * Coverage targets:
 *  - First-attempt success (no retries consumed)
 *  - Success after a transient network error on attempt 1
 *  - 4xx response returned immediately (not retried)
 *  - 5xx responses retried up to delays.length times, then returned
 *  - Network errors retried; thrown after all retries exhausted
 *  - AbortError propagated immediately without retry
 *  - Pre-abort signal check (aborted before the loop starts)
 *  - onRetrying callback called with correct attempt numbers
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { fetchWithRetry } from "../utils/fetchWithRetry.js";

// Zero-delay array for tests — same length as production [1000,2000,4000] so
// the retry count is identical but tests don't wait 7 seconds.
const NO_WAIT = [0, 0, 0];

function makeResponse(status, ok = status >= 200 && status < 300) {
  return { ok, status, statusText: String(status), json: async () => ({}) };
}

beforeEach(() => {
  vi.useFakeTimers();
  global.fetch = vi.fn();
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("fetchWithRetry — success paths", () => {
  it("returns the response immediately on a 200", async () => {
    const resp = makeResponse(200);
    global.fetch.mockResolvedValue(resp);

    const result = await fetchWithRetry("http://test/", {}, NO_WAIT);

    expect(result).toBe(resp);
    expect(global.fetch).toHaveBeenCalledTimes(1);
  });

  it("succeeds after one network error then a 200", async () => {
    global.fetch
      .mockRejectedValueOnce(new TypeError("Network error"))
      .mockResolvedValue(makeResponse(200));

    const promise = fetchWithRetry("http://test/", {}, NO_WAIT);
    // Advance timers past the first retry delay (0 ms in NO_WAIT)
    await vi.runAllTimersAsync();
    const result = await promise;

    expect(result.ok).toBe(true);
    expect(global.fetch).toHaveBeenCalledTimes(2);
  });

  it("calls onRetrying with 1-based attempt number", async () => {
    global.fetch
      .mockRejectedValueOnce(new TypeError("Network error"))
      .mockResolvedValue(makeResponse(200));

    const onRetrying = vi.fn();
    const promise = fetchWithRetry("http://test/", {}, NO_WAIT, onRetrying);
    await vi.runAllTimersAsync();
    await promise;

    expect(onRetrying).toHaveBeenCalledTimes(1);
    expect(onRetrying).toHaveBeenCalledWith(1);
  });
});

describe("fetchWithRetry — 4xx not retried", () => {
  it("returns a 400 on the first attempt without retrying", async () => {
    const resp = makeResponse(400, false);
    global.fetch.mockResolvedValue(resp);

    const result = await fetchWithRetry("http://test/", {}, NO_WAIT);

    expect(result.status).toBe(400);
    expect(global.fetch).toHaveBeenCalledTimes(1);
  });

  it("returns a 404 on the first attempt without retrying", async () => {
    global.fetch.mockResolvedValue(makeResponse(404, false));
    const onRetrying = vi.fn();

    await fetchWithRetry("http://test/", {}, NO_WAIT, onRetrying);

    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(onRetrying).not.toHaveBeenCalled();
  });
});

describe("fetchWithRetry — 5xx retried then returned", () => {
  it("retries all 3 times on 503 then returns the last response", async () => {
    const resp503 = makeResponse(503, false);
    global.fetch.mockResolvedValue(resp503);

    const promise = fetchWithRetry("http://test/", {}, NO_WAIT);
    await vi.runAllTimersAsync();
    const result = await promise;

    // 1 initial + 3 retries = 4 calls total
    expect(global.fetch).toHaveBeenCalledTimes(4);
    expect(result.status).toBe(503);
  });

  it("calls onRetrying for each retry attempt", async () => {
    global.fetch.mockResolvedValue(makeResponse(500, false));
    const onRetrying = vi.fn();

    const promise = fetchWithRetry("http://test/", {}, NO_WAIT, onRetrying);
    await vi.runAllTimersAsync();
    await promise;

    // 3 retries → onRetrying called with 1, 2, 3
    expect(onRetrying).toHaveBeenCalledTimes(3);
    expect(onRetrying).toHaveBeenNthCalledWith(1, 1);
    expect(onRetrying).toHaveBeenNthCalledWith(2, 2);
    expect(onRetrying).toHaveBeenNthCalledWith(3, 3);
  });

  it("succeeds on the 3rd retry after two 503s", async () => {
    global.fetch
      .mockResolvedValueOnce(makeResponse(503, false))
      .mockResolvedValueOnce(makeResponse(503, false))
      .mockResolvedValueOnce(makeResponse(200));

    const promise = fetchWithRetry("http://test/", {}, NO_WAIT);
    await vi.runAllTimersAsync();
    const result = await promise;

    expect(result.ok).toBe(true);
    expect(global.fetch).toHaveBeenCalledTimes(3);
  });
});

describe("fetchWithRetry — network errors exhausted", () => {
  it("throws after all retries exhausted on persistent network errors", async () => {
    // Use real timers for this test: fake timers cause a pre-rejected-promise
    // ordering issue where Vitest sees a momentary unhandled rejection.
    // NO_WAIT delays are 0 ms so real timers complete synchronously.
    vi.useRealTimers();

    const networkErr = new TypeError("Failed to fetch");
    global.fetch.mockRejectedValue(networkErr);

    await expect(
      fetchWithRetry("http://test/", {}, NO_WAIT)
    ).rejects.toThrow("Failed to fetch");

    // 1 initial + 3 retries = 4 total attempts
    expect(global.fetch).toHaveBeenCalledTimes(4);
  });
});

describe("fetchWithRetry — AbortError", () => {
  it("propagates AbortError from fetch without retrying", async () => {
    const abortErr = new DOMException("Aborted", "AbortError");
    global.fetch.mockRejectedValue(abortErr);
    const onRetrying = vi.fn();

    await expect(
      fetchWithRetry("http://test/", {}, NO_WAIT, onRetrying)
    ).rejects.toThrow("Aborted");

    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(onRetrying).not.toHaveBeenCalled();
  });

  it("throws immediately when signal is already aborted before the loop", async () => {
    const ctrl = new AbortController();
    ctrl.abort();
    const onRetrying = vi.fn();

    await expect(
      fetchWithRetry("http://test/", { signal: ctrl.signal }, NO_WAIT, onRetrying)
    ).rejects.toThrow("Aborted");

    expect(global.fetch).not.toHaveBeenCalled();
    expect(onRetrying).not.toHaveBeenCalled();
  });
});
