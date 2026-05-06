/**
 * useServiceAlerts hook tests (TD-FE-021).
 *
 * Covered:
 *  - Fetches /alerts on mount
 *  - Returns empty list initially
 *  - Populates undismissedAlerts after a successful fetch
 *  - Treats non-ok response as empty (no throw)
 *  - Network error → empty list (caught)
 *  - dismiss(id) hides that alert from undismissedAlerts
 *  - dismissed IDs persist to sessionStorage
 *  - Pre-existing dismissed IDs in sessionStorage are honoured
 *  - Aborts in-flight request on unmount
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";

vi.mock("../constants.js", async () => {
  const actual = await vi.importActual("../constants.js");
  return { ...actual, BACKEND_URL: "http://test.local" };
});

import { useServiceAlerts } from "../hooks/useServiceAlerts.js";

function mockAlerts(payload) {
  return vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve(payload),
  });
}

describe("useServiceAlerts", () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    sessionStorage.clear();
  });

  it("starts with no undismissed alerts before fetch resolves", () => {
    vi.stubGlobal("fetch", () => new Promise(() => {})); // never resolves
    const { result } = renderHook(() => useServiceAlerts());
    expect(result.current.undismissedAlerts).toEqual([]);
  });

  it("populates undismissedAlerts on successful fetch", async () => {
    vi.stubGlobal("fetch", mockAlerts({
      alerts: [{ alert_id: "a1", headline: "Red Line delays" }],
    }));
    const { result } = renderHook(() => useServiceAlerts());
    await waitFor(() => expect(result.current.undismissedAlerts).toHaveLength(1));
    expect(result.current.undismissedAlerts[0].alert_id).toBe("a1");
  });

  it("returns empty list when /alerts returns non-ok", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));
    const { result } = renderHook(() => useServiceAlerts());
    // Allow the .then chain to flush
    await waitFor(() => expect(fetch).toHaveBeenCalled());
    expect(result.current.undismissedAlerts).toEqual([]);
  });

  it("returns empty list on network error (swallowed)", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    const { result } = renderHook(() => useServiceAlerts());
    await waitFor(() => expect(fetch).toHaveBeenCalled());
    expect(result.current.undismissedAlerts).toEqual([]);
  });

  it("dismisses an alert and persists the ID to sessionStorage", async () => {
    vi.stubGlobal("fetch", mockAlerts({
      alerts: [
        { alert_id: "a1", headline: "Red Line delays" },
        { alert_id: "a2", headline: "Blue Line reroute" },
      ],
    }));
    const { result } = renderHook(() => useServiceAlerts());
    await waitFor(() => expect(result.current.undismissedAlerts).toHaveLength(2));

    act(() => result.current.dismiss("a1"));
    expect(result.current.undismissedAlerts).toHaveLength(1);
    expect(result.current.undismissedAlerts[0].alert_id).toBe("a2");

    const persisted = JSON.parse(sessionStorage.getItem("dismissed_alert_ids"));
    expect(persisted).toContain("a1");
  });

  it("honours pre-existing dismissed IDs in sessionStorage", async () => {
    sessionStorage.setItem("dismissed_alert_ids", JSON.stringify(["a1"]));
    vi.stubGlobal("fetch", mockAlerts({
      alerts: [
        { alert_id: "a1", headline: "Red Line delays" },
        { alert_id: "a2", headline: "Blue Line reroute" },
      ],
    }));
    const { result } = renderHook(() => useServiceAlerts());
    await waitFor(() => expect(result.current.undismissedAlerts).toHaveLength(1));
    expect(result.current.undismissedAlerts[0].alert_id).toBe("a2");
  });

  it("aborts the in-flight fetch on unmount", () => {
    let capturedSignal;
    vi.stubGlobal("fetch", (_url, opts) => {
      capturedSignal = opts.signal;
      return new Promise(() => {});
    });
    const { unmount } = renderHook(() => useServiceAlerts());
    unmount();
    expect(capturedSignal.aborted).toBe(true);
  });
});
