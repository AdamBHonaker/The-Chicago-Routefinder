/**
 * useShareLink hook tests (TD-FE-021).
 *
 * Covered:
 *  - Calls onShare({ from, to, routeIndex }) when both ?from and ?to are present
 *  - Defaults routeIndex to 0 when ?route is absent
 *  - Parses ?route as int; non-numeric falls back to 0
 *  - Skips entirely when from is missing
 *  - Skips entirely when to is missing
 *  - Skips when from is hostile (javascript:, data:, embedded URL)
 *  - Skips when to is hostile
 *  - Fires only once even on re-render (mount-only effect)
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook } from "@testing-library/react";
import { useShareLink } from "../hooks/useShareLink.js";

function setLocationSearch(search) {
  // jsdom allows location.search assignment via the search setter
  window.history.replaceState(null, "", `/${search}`);
}

describe("useShareLink", () => {
  beforeEach(() => {
    setLocationSearch("");
  });

  afterEach(() => {
    setLocationSearch("");
  });

  it("calls onShare with from/to and routeIndex when both params valid", () => {
    setLocationSearch("?from=Wilson&to=Belmont&route=2");
    const onShare = vi.fn();
    renderHook(() => useShareLink(onShare));
    expect(onShare).toHaveBeenCalledTimes(1);
    expect(onShare).toHaveBeenCalledWith({ from: "Wilson", to: "Belmont", routeIndex: 2 });
  });

  it("defaults routeIndex to 0 when ?route is absent", () => {
    setLocationSearch("?from=A&to=B");
    const onShare = vi.fn();
    renderHook(() => useShareLink(onShare));
    expect(onShare).toHaveBeenCalledWith({ from: "A", to: "B", routeIndex: 0 });
  });

  it("falls back to 0 for non-numeric ?route values", () => {
    setLocationSearch("?from=A&to=B&route=banana");
    const onShare = vi.fn();
    renderHook(() => useShareLink(onShare));
    expect(onShare).toHaveBeenCalledWith({ from: "A", to: "B", routeIndex: 0 });
  });

  it("does not fire when ?from is missing", () => {
    setLocationSearch("?to=Belmont");
    const onShare = vi.fn();
    renderHook(() => useShareLink(onShare));
    expect(onShare).not.toHaveBeenCalled();
  });

  it("does not fire when ?to is missing", () => {
    setLocationSearch("?from=Wilson");
    const onShare = vi.fn();
    renderHook(() => useShareLink(onShare));
    expect(onShare).not.toHaveBeenCalled();
  });

  it("rejects javascript: pseudo-protocol in from", () => {
    setLocationSearch("?from=javascript:alert(1)&to=Belmont");
    const onShare = vi.fn();
    renderHook(() => useShareLink(onShare));
    expect(onShare).not.toHaveBeenCalled();
  });

  it("rejects data: pseudo-protocol in to", () => {
    setLocationSearch("?from=Wilson&to=data:text/html,foo");
    const onShare = vi.fn();
    renderHook(() => useShareLink(onShare));
    expect(onShare).not.toHaveBeenCalled();
  });

  it("rejects embedded URL scheme (https://) in from", () => {
    setLocationSearch("?from=https://evil.example.com&to=Belmont");
    const onShare = vi.fn();
    renderHook(() => useShareLink(onShare));
    expect(onShare).not.toHaveBeenCalled();
  });

  it("rejects protocol-relative // prefix", () => {
    setLocationSearch("?from=//evil.example.com&to=Belmont");
    const onShare = vi.fn();
    renderHook(() => useShareLink(onShare));
    expect(onShare).not.toHaveBeenCalled();
  });

  it("does not re-fire on re-render", () => {
    setLocationSearch("?from=A&to=B");
    const onShare = vi.fn();
    const { rerender } = renderHook(() => useShareLink(onShare));
    rerender();
    rerender();
    expect(onShare).toHaveBeenCalledTimes(1);
  });
});
