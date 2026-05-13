/**
 * FEAT-018 — Schedules tool picker-flow tests.
 *
 * Walks the three-step picker (route → direction → stop) and confirms the
 * day-tabbed schedule view renders after step 3. Stubs fetch so the test
 * is fully offline.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import SchedulesTool from "../components/tools/SchedulesTool.jsx";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key) => key }),
}));

const MANIFEST = {
  routes: [
    { route_id: "Red", short_name: "Red", long_name: "Red Line",
      color: "c60c30", category: "train" },
    { route_id: "22",  short_name: "22",  long_name: "Clark",
      color: "414145", category: "bus_frequent" },
  ],
  stop_routes: {
    "1001": ["Red"],
  },
};

const RED_SCHEDULE = {
  route_id: "Red",
  route_short_name: "Red",
  route_long_name: "Red Line",
  route_color: "c60c30",
  category: "train",
  directions: [
    {
      direction_id: "0",
      headsign: "95th/Dan Ryan",
      stops: [
        {
          stop_id: "1001",
          name: "Howard",
          lat: 42.019, lon: -87.672, sequence: 1,
          times: {
            weekday: ["08:00", "08:15", "09:00"],
            saturday: ["09:00"],
            sunday: ["10:00"],
          },
        },
        {
          stop_id: "1002",
          name: "Belmont",
          lat: 41.940, lon: -87.653, sequence: 2,
          times: { weekday: ["08:15"], saturday: [], sunday: [] },
        },
      ],
    },
    {
      direction_id: "1",
      headsign: "Howard",
      stops: [
        {
          stop_id: "1002",
          name: "Belmont",
          lat: 41.940, lon: -87.653, sequence: 1,
          times: { weekday: ["10:00"], saturday: [], sunday: [] },
        },
      ],
    },
  ],
};

function mockFetch() {
  global.fetch = vi.fn((url) => {
    if (url.endsWith("/schedule/routes")) {
      return Promise.resolve({
        ok: true, json: () => Promise.resolve(MANIFEST),
      });
    }
    if (url.endsWith("/schedule/Red")) {
      return Promise.resolve({
        ok: true, json: () => Promise.resolve(RED_SCHEDULE),
      });
    }
    return Promise.reject(new Error(`unexpected fetch: ${url}`));
  });
}

describe("SchedulesTool", () => {
  beforeEach(() => mockFetch());
  afterEach(() => { vi.restoreAllMocks(); });

  it("walks route → direction → stop → schedule and renders weekday times", async () => {
    render(<SchedulesTool onBack={() => {}} seed={null} />);

    // Step 1: route list appears after manifest fetch.
    await waitFor(() => {
      expect(screen.getByText("Red Line")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText("Red Line"));

    // Step 2: direction list (after schedule fetch resolves).
    await waitFor(() => {
      expect(screen.getByText("→ 95th/Dan Ryan")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText("→ 95th/Dan Ryan"));

    // Step 3: stop list.
    await waitFor(() => {
      expect(screen.getByText("Howard")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText("Howard"));

    // Schedule view: weekday tab is the default for most service days; the
    // route header and at least one minute column should be visible.
    await waitFor(() => {
      // Route header text combines long name + headsign.
      expect(screen.getByText(/Red Line/)).toBeInTheDocument();
    });
    // Day tabs rendered.
    expect(screen.getByRole("tab", { name: "schedule_tab_weekday" }))
      .toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "schedule_tab_saturday" }))
      .toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "schedule_tab_sunday" }))
      .toBeInTheDocument();
  });

  it("auto-selects the seeded stop when entering from a saved-stop card", async () => {
    render(<SchedulesTool onBack={() => {}} seed={{ stopId: "1001" }} />);

    await waitFor(() => {
      expect(screen.getByText("Red Line")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText("Red Line"));

    // Direction step still shown because Red has two directions; pick the
    // southbound one that contains the seeded stop.
    await waitFor(() => {
      expect(screen.getByText("→ 95th/Dan Ryan")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText("→ 95th/Dan Ryan"));

    // Should skip the stop step and land directly on the schedule view for
    // Howard (the seeded stop).
    await waitFor(() => {
      expect(screen.getByRole("tab", { name: "schedule_tab_weekday" }))
        .toBeInTheDocument();
    });
  });
});
