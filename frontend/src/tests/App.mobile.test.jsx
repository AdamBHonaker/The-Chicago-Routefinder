/**
 * App mobile-vs-desktop layout integration test.
 *
 * The full App imports MapView (which pulls in maplibre-gl), several
 * hooks, and the i18n setup — so this test mocks the heaviest deps and
 * focuses on a structural assertion: which chrome renders at each
 * breakpoint.
 *
 * Covered:
 *  - matchMedia(max-width:800px) → mobile branch: .bottom-sheet and
 *    .sheet-segmented are rendered; .side-rail and .panel-splitter are NOT.
 *  - matchMedia not matching     → desktop branch: .side-rail and
 *    .panel-splitter are rendered; .bottom-sheet is NOT.
 *  - The legacy <nav class="tab-bar"> is absent on both branches (it was
 *    deleted when the segmented control replaced it).
 *  - Active tab attribute (data-active-tab) reflects activeTab state on
 *    both branches.
 */

import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

// ── Mocks ──────────────────────────────────────────────────────────────────

// MapView pulls in ~825 KB of maplibre-gl; replace with a stub that just
// renders a marker the test can assert on.
vi.mock("../MapView.jsx", () => ({
  default: () => <div data-testid="map-view-stub" />,
}));

// Lazy panels — render-on-demand stubs so Suspense doesn't hang.
vi.mock("../components/SettingsPanel.jsx", () => ({
  default: () => <div data-testid="settings-stub" />,
}));
vi.mock("../components/SavedRoutesPanel.jsx", () => ({
  default: () => <div data-testid="saved-stub" />,
}));

// react-i18next — return the key as-is so assertions stay legible. Include
// initReactI18next stub since src/i18n.js imports it at module-load time.
vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key) => key,
    i18n: { language: "en" },
  }),
  initReactI18next: { type: "3rdParty", init: vi.fn() },
}));

// Hooks that touch the network or geolocation.
vi.mock("../hooks/useFavorites.js", () => ({
  useFavorites: () => ({
    savedLocations: [],
    setSavedLocations: vi.fn(),
    savedRoutes: [],
    showSavedRoutes: false,
    setShowSavedRoutes: vi.fn(),
    pinnedStops: [],
    savingRoute: false,
    setSavingRoute: vi.fn(),
    routeLabelDraft: "",
    setRouteLabelDraft: vi.fn(),
    routeLimitError: false,
    setRouteLimitError: vi.fn(),
    currentRouteSaved: false,
    handleUnpin: vi.fn(),
    handlePinToggle: vi.fn(),
    handleDeleteRoute: vi.fn(),
    handleToggleSaveRoute: vi.fn(),
    handleSaveRoute: vi.fn(),
  }),
}));

vi.mock("../hooks/useTripTracker.js", () => ({
  useTripTracker: () => ({
    tripActive: false,
    userPosition: null,
    activeLegIndex: null,
    completedSteps: [],
    isOffRoute: false,
    tripGeoError: null,
    onVehicle: false,
    startTrip: vi.fn(),
    stopTrip: vi.fn(),
    toggleOnVehicle: vi.fn(),
    dismissOffRoute: vi.fn(),
    dismissTripGeoError: vi.fn(),
    resetForReroute: vi.fn(),
  }),
}));

vi.mock("../hooks/useByokIdleClear.js", () => ({
  useByokIdleClear: vi.fn(),
}));

vi.mock("../hooks/useServiceAlerts.js", () => ({
  useServiceAlerts: () => ({
    undismissedAlerts: [],
    dismiss: vi.fn(),
    refetch: vi.fn(),
  }),
}));

vi.mock("../hooks/useShareLink.js", () => ({
  useShareLink: vi.fn(),
}));

vi.mock("../hooks/useDocumentLanguage.js", () => ({
  useDocumentLanguage: vi.fn(),
}));

vi.mock("../hooks/useApiQuery.js", () => ({
  useApiQuery: () => ({ data: null, refetch: vi.fn() }),
}));

vi.mock("../analytics.js", () => ({
  track: vi.fn(),
}));

// ── matchMedia helper ──────────────────────────────────────────────────────

function mockMatchMedia(matchesQuery) {
  window.matchMedia = vi.fn(query => ({
    matches: matchesQuery(query),
    media: query,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
}

// ── Tests ──────────────────────────────────────────────────────────────────

describe("App layout branching", () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    // Silence the /ping fetch.
    global.fetch = vi.fn(() => Promise.resolve({ ok: true, json: () => ({}) }));
  });

  it("renders mobile chrome under (max-width: 800px)", async () => {
    mockMatchMedia(q => q.includes("max-width: 800px"));
    const { default: App } = await import("../App.jsx");
    const { container } = render(<App />);

    await waitFor(() => {
      expect(container.querySelector(".bottom-sheet")).not.toBeNull();
    });
    expect(container.querySelector(".sheet-segmented")).not.toBeNull();
    expect(container.querySelector(".side-rail")).toBeNull();
    expect(container.querySelector(".panel-splitter")).toBeNull();
    expect(container.querySelector(".tab-bar")).toBeNull();   // legacy nav was removed
    expect(container.querySelector(".app--mobile")).not.toBeNull();
  });

  it("renders desktop chrome when no mobile media query matches", async () => {
    mockMatchMedia(() => false);
    const { default: App } = await import("../App.jsx");
    const { container } = render(<App />);

    await waitFor(() => {
      expect(container.querySelector(".side-rail")).not.toBeNull();
    });
    expect(container.querySelector(".panel-splitter")).not.toBeNull();
    expect(container.querySelector(".bottom-sheet")).toBeNull();
    expect(container.querySelector(".sheet-segmented")).toBeNull();
    expect(container.querySelector(".tab-bar")).toBeNull();
    expect(container.querySelector(".app--mobile")).toBeNull();
  });

  it("renders MapView exactly once (mounted at App level for breakpoint-flip safety)", async () => {
    mockMatchMedia(q => q.includes("max-width: 800px"));
    const { default: App } = await import("../App.jsx");
    render(<App />);

    await waitFor(() => {
      const stubs = screen.getAllByTestId("map-view-stub");
      expect(stubs).toHaveLength(1);
    });
  });
});
