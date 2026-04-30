/**
 * RouteCard component tests.
 * Covers: expand/collapse, best-badge, trip footer state, pin button rendering.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import RouteCard from "../components/RouteCard.jsx";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key, opts) => opts ? `${key}(${JSON.stringify(opts)})` : key }),
}));

const WALK_LEG = {
  type: "walk",
  from: "Your location",
  to: "Howard",
  minutes: 3,
  directions: [],
};

const TRANSIT_LEG = {
  type: "transit",
  line: "Red Line",
  line_code: null,
  from: "Howard",
  to: "Lake",
  minutes: 20,
  from_mapid: "40900",
};

const MINIMAL_ROUTE = {
  total_minutes: 25,
  transfers: 0,
  wait_minutes: 5,
  legs: [WALK_LEG, TRANSIT_LEG],
};

const BASE_PROPS = {
  route: MINIMAL_ROUTE,
  index: 0,
  isFirst: false,
  isSelected: false,
  onSelect: vi.fn(),
  tripActive: false,
  activeLegIndex: null,
  completedSteps: new Set(),
  onStartTrip: vi.fn(),
  onStopTrip: vi.fn(),
  tripGeoError: false,
  onDismissTripGeoError: vi.fn(),
  onVehicle: false,
  onToggleVehicle: vi.fn(),
  pinnedStops: [],
  onPinToggle: vi.fn(),
  activeAlertRoutes: new Set(),
};

describe("RouteCard", () => {
  beforeEach(() => vi.clearAllMocks());

  it("displays total minutes in the header", () => {
    render(<RouteCard {...BASE_PROPS} />);
    expect(screen.getByText("25")).toBeInTheDocument();
  });

  it("shows the '★ Best' badge only when isFirst is true", () => {
    const { rerender } = render(<RouteCard {...BASE_PROPS} />);
    expect(screen.queryByText(/badge_best/)).not.toBeInTheDocument();

    rerender(<RouteCard {...BASE_PROPS} isFirst={true} />);
    expect(screen.getByText(/badge_best/)).toBeInTheDocument();
  });

  it("is collapsed by default when isFirst is false", () => {
    render(<RouteCard {...BASE_PROPS} isFirst={false} />);
    expect(screen.queryByRole("list", { name: /legs/i })).not.toBeInTheDocument();
  });

  it("is expanded by default when isFirst is true", () => {
    render(<RouteCard {...BASE_PROPS} isFirst={true} />);
    // Walk leg text should be visible when expanded
    expect(screen.getByText(/walk_from_origin/)).toBeInTheDocument();
  });

  it("toggles expand/collapse when header is clicked", () => {
    render(<RouteCard {...BASE_PROPS} isFirst={false} />);
    const header = screen.getByRole("button", { name: /minutes total/i });

    // Collapsed — leg text not present
    expect(screen.queryByText(/walk_from_origin/)).not.toBeInTheDocument();

    fireEvent.click(header);
    expect(screen.getByText(/walk_from_origin/)).toBeInTheDocument();

    fireEvent.click(header);
    expect(screen.queryByText(/walk_from_origin/)).not.toBeInTheDocument();
  });

  it("calls onSelect when header is clicked", () => {
    render(<RouteCard {...BASE_PROPS} />);
    fireEvent.click(screen.getByRole("button", { name: /minutes total/i }));
    expect(BASE_PROPS.onSelect).toHaveBeenCalledTimes(1);
  });

  it("shows trip footer only when isSelected", () => {
    const { rerender } = render(<RouteCard {...BASE_PROPS} isFirst={true} isSelected={false} />);
    expect(screen.queryByText("route_start_trip")).not.toBeInTheDocument();

    rerender(<RouteCard {...BASE_PROPS} isFirst={true} isSelected={true} />);
    expect(screen.getByText("route_start_trip")).toBeInTheDocument();
  });

  it("shows Stop Trip button when tripActive is true", () => {
    render(<RouteCard {...BASE_PROPS} isFirst={true} isSelected={true} tripActive={true} activeLegIndex={0} />);
    expect(screen.getByText("route_stop_trip")).toBeInTheDocument();
    expect(screen.queryByText("route_start_trip")).not.toBeInTheDocument();
  });

  it("renders a pin button for transit legs when onPinToggle is provided", () => {
    render(<RouteCard {...BASE_PROPS} isFirst={true} />);
    const pinBtn = screen.getByTitle(/pin_stop/);
    expect(pinBtn).toBeInTheDocument();
  });

  it("calls onPinToggle when pin button is clicked", () => {
    render(<RouteCard {...BASE_PROPS} isFirst={true} />);
    fireEvent.click(screen.getByTitle(/pin_stop/));
    expect(BASE_PROPS.onPinToggle).toHaveBeenCalledWith(
      "train", "40900", "Howard", "", false
    );
  });
});
