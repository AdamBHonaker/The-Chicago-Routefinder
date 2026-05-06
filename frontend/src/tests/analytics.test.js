/**
 * analytics.track() tests (TD-FE-021).
 *
 * Covered:
 *  - POSTs to `${BACKEND_URL}/events` with the event name in the body
 *  - Includes credentials and keepalive flags
 *  - Swallows fetch rejections (analytics must never break the app)
 *  - Swallows synchronous fetch throws (extreme defensive case)
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

vi.mock("../constants.js", async () => {
  const actual = await vi.importActual("../constants.js");
  return { ...actual, BACKEND_URL: "http://test.local" };
});

import { track } from "../analytics.js";

describe("analytics.track", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true }));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("POSTs to /events with the event name as JSON", () => {
    track("recommend_submitted");
    expect(fetch).toHaveBeenCalledTimes(1);
    const [url, opts] = fetch.mock.calls[0];
    expect(url).toBe("http://test.local/events");
    expect(opts.method).toBe("POST");
    expect(opts.headers).toEqual({ "Content-Type": "application/json" });
    expect(JSON.parse(opts.body)).toEqual({ name: "recommend_submitted" });
  });

  it("sets credentials: 'include' so the session cookie travels", () => {
    track("app_loaded");
    expect(fetch.mock.calls[0][1].credentials).toBe("include");
  });

  it("sets keepalive: true so the request survives unmount/navigation", () => {
    track("trip_completed");
    expect(fetch.mock.calls[0][1].keepalive).toBe(true);
  });

  it("swallows fetch rejections without throwing", () => {
    fetch.mockReturnValueOnce(Promise.reject(new Error("network down")));
    expect(() => track("any_event")).not.toThrow();
  });

  it("swallows synchronous fetch throws", () => {
    fetch.mockImplementationOnce(() => { throw new Error("boom"); });
    expect(() => track("any_event")).not.toThrow();
  });
});
