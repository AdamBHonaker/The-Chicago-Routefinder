/**
 * Unit tests for useApiQuery hook (TD-038).
 *
 * Coverage targets:
 *  - Returns { data: null, loading: true } on mount when enabled
 *  - Returns data after successful fetch
 *  - Sets error when fetch returns non-ok response
 *  - Sets error on network failure
 *  - Does not fetch when enabled=false
 *  - refetch() triggers a new fetch
 *  - Aborts in-flight request on unmount
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { useApiQuery } from "../hooks/useApiQuery.js";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function okFetcher(data) {
  return (_signal) => Promise.resolve({
    ok: true,
    json: () => Promise.resolve(data),
  });
}

function errorFetcher(status = 500) {
  return (_signal) => Promise.resolve({ ok: false, status });
}

function rejectFetcher(message = "Network error") {
  return (_signal) => Promise.reject(new Error(message));
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useApiQuery", () => {
  it("starts with loading=true and data=null when enabled", async () => {
    let resolvePromise;
    const fetcher = (_signal) => new Promise((resolve) => { resolvePromise = resolve; });
    const { result } = renderHook(() => useApiQuery(fetcher, []));
    expect(result.current.loading).toBe(true);
    expect(result.current.data).toBeNull();
    resolvePromise({ ok: true, json: () => Promise.resolve({}) });
  });

  it("sets data on successful fetch", async () => {
    const { result } = renderHook(() =>
      useApiQuery(okFetcher({ routes: [1, 2, 3] }), [])
    );
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.data).toEqual({ routes: [1, 2, 3] });
    expect(result.current.error).toBeNull();
  });

  it("sets error on HTTP error response", async () => {
    const { result } = renderHook(() =>
      useApiQuery(errorFetcher(404), [])
    );
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).toBeInstanceOf(Error);
    expect(result.current.data).toBeNull();
  });

  it("sets error on network failure", async () => {
    const { result } = renderHook(() =>
      useApiQuery(rejectFetcher("Connection refused"), [])
    );
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).toBeInstanceOf(Error);
  });

  it("does not fetch when enabled=false", () => {
    const fetcher = vi.fn(okFetcher({}));
    renderHook(() => useApiQuery(fetcher, [], { enabled: false }));
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("starts with loading=false when enabled=false", () => {
    const { result } = renderHook(() =>
      useApiQuery(okFetcher({}), [], { enabled: false })
    );
    expect(result.current.loading).toBe(false);
  });

  it("refetch() triggers a new request", async () => {
    const fetcher = vi.fn(okFetcher({ count: 1 }));
    const { result } = renderHook(() => useApiQuery(fetcher, []));
    await waitFor(() => expect(result.current.loading).toBe(false));
    const callsBefore = fetcher.mock.calls.length;
    act(() => result.current.refetch());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(fetcher.mock.calls.length).toBeGreaterThan(callsBefore);
  });

  it("returns a stable refetch function reference", async () => {
    const { result, rerender } = renderHook(() =>
      useApiQuery(okFetcher({}), [])
    );
    await waitFor(() => expect(result.current.loading).toBe(false));
    const refetch1 = result.current.refetch;
    rerender();
    expect(result.current.refetch).toBe(refetch1);
  });
});
