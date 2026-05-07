/**
 * MobileLayout (kit) tests.
 *
 * Covered:
 *  - Throws when storageKey is missing (catches host-integration mistakes)
 *  - Renders masthead, body content, and the sheet
 *  - Renders the map slot only when `map` prop is provided
 *  - Forwards handleLabel to the BottomSheet's drag handle
 *  - Mount does not write to storage prematurely
 *
 * The drag-release → debounced-persist path is exercised end-to-end by
 * the App.mobile.test integration test. The unit-level persistence
 * contract is covered by sheetSnap.test (createSheetSnapStore).
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MobileLayout } from "../mobile-sheet-kit/MobileLayout.jsx";

describe("MobileLayout (kit)", () => {
  it("throws when storageKey is missing", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => render(<MobileLayout>child</MobileLayout>)).toThrow(/storageKey/);
    spy.mockRestore();
  });

  it("renders masthead and body content", () => {
    render(
      <MobileLayout
        storageKey="test:snap"
        masthead={<div data-testid="masthead">M</div>}
        handleLabel="Drag"
      >
        <p>body</p>
      </MobileLayout>,
    );
    expect(screen.getByTestId("masthead")).toBeInTheDocument();
    expect(screen.getByText("body")).toBeInTheDocument();
  });

  it("omits the map slot when no `map` prop is provided", () => {
    const { container } = render(
      <MobileLayout storageKey="test:snap" handleLabel="Drag">
        <p>body</p>
      </MobileLayout>,
    );
    expect(container.querySelector(".mobile-shell-map")).toBeNull();
  });

  it("renders the map slot when a `map` prop is provided", () => {
    render(
      <MobileLayout
        storageKey="test:snap"
        map={<div data-testid="map" />}
        handleLabel="Drag"
      >
        <p>body</p>
      </MobileLayout>,
    );
    expect(screen.getByTestId("map")).toBeInTheDocument();
  });

  it("forwards handleLabel to the drag handle", () => {
    render(
      <MobileLayout storageKey="test:snap" handleLabel="Drag the panel">
        <p>body</p>
      </MobileLayout>,
    );
    expect(
      screen.getByRole("button", { name: "Drag the panel" }),
    ).toBeInTheDocument();
  });

  it("does not write to storage on mount", () => {
    localStorage.clear();
    render(
      <MobileLayout storageKey="myapp:snap" handleLabel="Drag">
        <p>body</p>
      </MobileLayout>,
    );
    expect(localStorage.getItem("myapp:snap")).toBe(null);
  });
});
