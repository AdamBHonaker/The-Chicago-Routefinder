/**
 * PinnedStopsBoard component tests.
 *
 * Covered:
 *  - Returns null when stops array is null/empty
 *  - One card per pinned stop, each labeled
 *  - Per-stop optional route_hint rendered
 *  - "no arrivals" placeholder when arrivals[stop key] is missing or empty
 *  - Each arrival row renders with route + destination + minutes
 *  - "Due" displayed when minutes === 0 (instead of "0m")
 *  - Unpin button click invokes onUnpin with the stop id
 *  - Refresh button click invokes onRefresh
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import PinnedStopsBoard from "../components/PinnedStopsBoard.jsx";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key, vars) => {
      if (key === "wait_due_short")     return "Due";
      if (key === "no_arrivals")        return "No arrivals";
      if (key === "psb_refresh")        return "Refresh";
      if (key === "psb_unpin_stop")     return "Unpin";
      if (key === "psb_live_data")      return "Live";
      if (key === "signal_lamp_label")  return "LIVE";
      if (key === "caps_stops")         return "STOPS";
      if (key === "pinned_stops_heading") return "Pinned Stops";
      if (key === "unpin_stop"   && vars?.stop) return `Unpin ${vars.stop}`;
      if (key === "map_bus_label" && vars?.code != null) return `Bus ${vars.code}`;
      return key;
    },
  }),
}));

const stop = (id, label, type = "train", overrides = {}) => ({
  id, label, stop_id: `${id}_sid`, type, ...overrides,
});

describe("PinnedStopsBoard", () => {
  it("returns null when stops is null", () => {
    const { container } = render(<PinnedStopsBoard
      stops={null} arrivals={{}} onUnpin={() => {}} onRefresh={() => {}}
    />);
    expect(container.firstChild).toBeNull();
  });

  it("returns null when stops is empty", () => {
    const { container } = render(<PinnedStopsBoard
      stops={[]} arrivals={{}} onUnpin={() => {}} onRefresh={() => {}}
    />);
    expect(container.firstChild).toBeNull();
  });

  it("renders one card per stop, labeled", () => {
    render(<PinnedStopsBoard
      stops={[stop("a", "Howard"), stop("b", "Belmont")]}
      arrivals={{}} onUnpin={() => {}} onRefresh={() => {}}
    />);
    expect(screen.getByText("Howard")).toBeInTheDocument();
    expect(screen.getByText("Belmont")).toBeInTheDocument();
  });

  it("renders the optional route_hint when present", () => {
    render(<PinnedStopsBoard
      stops={[stop("a", "Howard", "train", { route_hint: "Red Line NB" })]}
      arrivals={{}} onUnpin={() => {}} onRefresh={() => {}}
    />);
    expect(screen.getByText("Red Line NB")).toBeInTheDocument();
  });

  it("shows 'no arrivals' placeholder when arrivals are missing", () => {
    render(<PinnedStopsBoard
      stops={[stop("a", "Howard")]}
      arrivals={{}} onUnpin={() => {}} onRefresh={() => {}}
    />);
    expect(screen.getByText("No arrivals")).toBeInTheDocument();
  });

  it("renders arrival rows with destination and minutes", () => {
    const arrivals = {
      "train:a_sid": {
        arrivals: [
          { route: "Red Line", destination: "95th/Dan Ryan", minutes: 4 },
          { route: "Red Line", destination: "Howard",        minutes: 11 },
        ],
      },
    };
    render(<PinnedStopsBoard
      stops={[stop("a", "Howard")]}
      arrivals={arrivals} onUnpin={() => {}} onRefresh={() => {}}
    />);
    expect(screen.getByText("95th/Dan Ryan")).toBeInTheDocument();
    expect(screen.getByText("4m")).toBeInTheDocument();
    expect(screen.getByText("11m")).toBeInTheDocument();
  });

  it("displays 'Due' instead of '0m' when minutes is 0", () => {
    const arrivals = {
      "train:a_sid": { arrivals: [{ route: "Red Line", destination: "Loop", minutes: 0 }] },
    };
    render(<PinnedStopsBoard
      stops={[stop("a", "Howard")]}
      arrivals={arrivals} onUnpin={() => {}} onRefresh={() => {}}
    />);
    expect(screen.getByText("Due")).toBeInTheDocument();
    expect(screen.queryByText("0m")).toBeNull();
  });

  it("invokes onUnpin with the stop id when unpin clicked", () => {
    const onUnpin = vi.fn();
    render(<PinnedStopsBoard
      stops={[stop("howard-id", "Howard")]}
      arrivals={{}} onUnpin={onUnpin} onRefresh={() => {}}
    />);
    fireEvent.click(screen.getByRole("button", { name: "Unpin Howard" }));
    expect(onUnpin).toHaveBeenCalledWith("howard-id");
  });

  it("invokes onRefresh when the refresh button clicked", () => {
    const onRefresh = vi.fn();
    render(<PinnedStopsBoard
      stops={[stop("a", "Howard")]}
      arrivals={{}} onUnpin={() => {}} onRefresh={onRefresh}
    />);
    fireEvent.click(screen.getByRole("button", { name: "Refresh" }));
    expect(onRefresh).toHaveBeenCalledTimes(1);
  });
});
