/**
 * AlertsFilterBar component tests.
 *
 * Covered:
 *  - L popover renders one row per LINE_COLORS entry.
 *  - Bus popover renders one row per availableBusRoutes entry, sorted as
 *    specified (numerics → express → night → other), and shows helper text.
 *  - Toggling a checkbox passes a new Set to the parent (multi-select).
 *  - "Clear" empties the filter.
 *  - Click-outside and Escape close the popover.
 *  - Button label includes count when selections > 0.
 *  - Bus popover shows the empty state when availableBusRoutes is empty.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import AlertsFilterBar from "../components/AlertsFilterBar.jsx";
import { LINE_COLORS } from "../lineColors.js";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key, opts) => {
      if (key === "alerts_filter_l_label")            return "L";
      if (key === "alerts_filter_bus_label")          return "Bus Route";
      if (key === "alerts_filter_l_count")            return `L (${opts?.count ?? 0})`;
      if (key === "alerts_filter_bus_count")          return `Bus Route (${opts?.count ?? 0})`;
      if (key === "alerts_filter_l_aria")             return "Filter notices by L line";
      if (key === "alerts_filter_bus_aria")           return "Filter notices by bus route";
      if (key === "alerts_filter_clear")              return "Clear";
      if (key === "alerts_bus_filter_help")           return "Only bus routes with active notices appear here — an absent route is a quiet route.";
      if (key === "alerts_empty")                     return "No active service alerts.";
      return key;
    },
  }),
}));

function renderBar(overrides = {}) {
  const props = {
    selectedLines: new Set(),
    selectedBuses: new Set(),
    onSelectedLinesChange: vi.fn(),
    onSelectedBusesChange: vi.fn(),
    availableBusRoutes: ["22", "X9", "N5", "151", "J14", "9"],
    ...overrides,
  };
  const utils = render(<AlertsFilterBar {...props} />);
  return { ...utils, props };
}

describe("AlertsFilterBar", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders both filter buttons closed by default", () => {
    renderBar();
    expect(screen.getByRole("button", { name: "Filter notices by L line" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Filter notices by bus route" })).toBeInTheDocument();
    expect(screen.queryByRole("menu")).toBeNull();
  });

  it("opens the L popover with one row per LINE_COLORS entry", () => {
    renderBar();
    fireEvent.click(screen.getByRole("button", { name: "Filter notices by L line" }));
    const checkboxes = screen.getAllByRole("menuitemcheckbox");
    expect(checkboxes).toHaveLength(Object.keys(LINE_COLORS).length);
    // Spot-check Red Line label appears
    expect(screen.getByText("Red Line")).toBeInTheDocument();
  });

  it("opens the Bus popover with helper text and a row per available route, sorted", () => {
    renderBar();
    fireEvent.click(screen.getByRole("button", { name: "Filter notices by bus route" }));
    expect(screen.getByText(/Only bus routes with active notices/)).toBeInTheDocument();
    const labels = screen
      .getAllByRole("menuitemcheckbox")
      .map((row) => row.textContent.trim());
    // Numerics ascending → express → night → other letter prefixes
    expect(labels).toEqual(["9", "22", "151", "X9", "N5", "J14"]);
  });

  it("calls onSelectedLinesChange with a new Set including the toggled line", () => {
    const { props } = renderBar();
    fireEvent.click(screen.getByRole("button", { name: "Filter notices by L line" }));
    const redCheckbox = screen.getByRole("menuitemcheckbox", { name: /Red Line/ })
      .querySelector("input[type=checkbox]");
    fireEvent.click(redCheckbox);
    expect(props.onSelectedLinesChange).toHaveBeenCalledTimes(1);
    const next = props.onSelectedLinesChange.mock.calls[0][0];
    expect(next).toBeInstanceOf(Set);
    expect(next.has("Red")).toBe(true);
  });

  it("supports multi-select: starting from {Red}, adding Blue yields {Red, Blue}", () => {
    const { props } = renderBar({ selectedLines: new Set(["Red"]) });
    fireEvent.click(screen.getByRole("button", { name: /Filter notices by L line/ }));
    const blueCheckbox = screen.getByRole("menuitemcheckbox", { name: /Blue Line/ })
      .querySelector("input[type=checkbox]");
    fireEvent.click(blueCheckbox);
    const next = props.onSelectedLinesChange.mock.calls[0][0];
    expect(next.has("Red")).toBe(true);
    expect(next.has("Blue")).toBe(true);
  });

  it("toggling an already-selected line removes it from the Set", () => {
    const { props } = renderBar({ selectedLines: new Set(["Red"]) });
    fireEvent.click(screen.getByRole("button", { name: /Filter notices by L line/ }));
    const redCheckbox = screen.getByRole("menuitemcheckbox", { name: /Red Line/ })
      .querySelector("input[type=checkbox]");
    fireEvent.click(redCheckbox);
    const next = props.onSelectedLinesChange.mock.calls[0][0];
    expect(next.has("Red")).toBe(false);
  });

  it("Clear empties the L filter", () => {
    const { props } = renderBar({ selectedLines: new Set(["Red", "Blue"]) });
    fireEvent.click(screen.getByRole("button", { name: /Filter notices by L line/ }));
    fireEvent.click(screen.getByRole("button", { name: "Clear" }));
    expect(props.onSelectedLinesChange).toHaveBeenCalledWith(new Set());
  });

  it("button label shows count when selections > 0", () => {
    renderBar({ selectedLines: new Set(["Red", "Blue"]), selectedBuses: new Set(["22"]) });
    expect(screen.getByRole("button", { name: "Filter notices by L line" }))
      .toHaveTextContent("L (2)");
    expect(screen.getByRole("button", { name: "Filter notices by bus route" }))
      .toHaveTextContent("Bus Route (1)");
  });

  it("Escape closes the open popover", () => {
    renderBar();
    fireEvent.click(screen.getByRole("button", { name: /Filter notices by L line/ }));
    expect(screen.getByRole("menu")).toBeInTheDocument();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("menu")).toBeNull();
  });

  it("click-outside closes the open popover", () => {
    renderBar();
    fireEvent.click(screen.getByRole("button", { name: /Filter notices by L line/ }));
    expect(screen.getByRole("menu")).toBeInTheDocument();
    fireEvent.mouseDown(document.body);
    expect(screen.queryByRole("menu")).toBeNull();
  });

  it("opening the Bus popover closes the L popover (one open at a time)", () => {
    renderBar();
    fireEvent.click(screen.getByRole("button", { name: /Filter notices by L line/ }));
    expect(screen.getByRole("menu", { name: /Filter notices by L line/ })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Filter notices by bus route/ }));
    expect(screen.queryByRole("menu", { name: /Filter notices by L line/ })).toBeNull();
    expect(screen.getByRole("menu", { name: /Filter notices by bus route/ })).toBeInTheDocument();
  });

  it("Bus popover shows the empty message when availableBusRoutes is empty", () => {
    renderBar({ availableBusRoutes: [] });
    fireEvent.click(screen.getByRole("button", { name: /Filter notices by bus route/ }));
    expect(screen.getByText("No active service alerts.")).toBeInTheDocument();
    expect(screen.queryAllByRole("menuitemcheckbox")).toHaveLength(0);
  });
});
