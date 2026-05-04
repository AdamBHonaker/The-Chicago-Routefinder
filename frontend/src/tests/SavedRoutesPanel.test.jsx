/**
 * SavedRoutesPanel component tests.
 *
 * Covered:
 *  - Renders as a modal dialog with translated aria-label
 *  - Empty state when savedRoutes is empty
 *  - One row per saved route, labeled
 *  - "Go" button click invokes onRouteSelect with origin + destination
 *  - Delete button click invokes onDeleteRoute with route id
 *  - Close (×) button click invokes onClose
 *  - Backdrop click invokes onClose
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import SavedRoutesPanel from "../components/SavedRoutesPanel.jsx";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key) => {
      if (key === "fav_saved_routes_heading") return "Saved Routes";
      if (key === "fav_routes_empty")         return "No saved routes yet";
      if (key === "fav_go")                   return "Go";
      if (key === "fav_delete")               return "Delete";
      if (key === "aria_dismiss")             return "Close";
      if (key === "caps_bookmarks")           return "BOOKMARKS";
      return key;
    },
  }),
}));

const route = (id, label, origin = "A", destination = "B") => ({
  id, label, origin, destination,
});

describe("SavedRoutesPanel", () => {
  it("renders as a dialog with translated aria-label", () => {
    render(<SavedRoutesPanel
      savedRoutes={[]} onDeleteRoute={() => {}} onRouteSelect={() => {}} onClose={() => {}}
    />);
    expect(screen.getByRole("dialog", { name: "Saved Routes" })).toBeInTheDocument();
  });

  it("shows the empty-state message when savedRoutes is empty", () => {
    render(<SavedRoutesPanel
      savedRoutes={[]} onDeleteRoute={() => {}} onRouteSelect={() => {}} onClose={() => {}}
    />);
    expect(screen.getByText("No saved routes yet")).toBeInTheDocument();
  });

  it("renders one row per saved route, labeled", () => {
    render(<SavedRoutesPanel
      savedRoutes={[route("1", "Home → Work"), route("2", "Loop → Wrigley")]}
      onDeleteRoute={() => {}} onRouteSelect={() => {}} onClose={() => {}}
    />);
    expect(screen.getByText("Home → Work")).toBeInTheDocument();
    expect(screen.getByText("Loop → Wrigley")).toBeInTheDocument();
  });

  it("invokes onRouteSelect with origin + destination when Go clicked", () => {
    const onRouteSelect = vi.fn();
    render(<SavedRoutesPanel
      savedRoutes={[route("1", "Home → Work", "Wrigleyville", "Loop")]}
      onDeleteRoute={() => {}} onRouteSelect={onRouteSelect} onClose={() => {}}
    />);
    fireEvent.click(screen.getByRole("button", { name: /Go/ }));
    expect(onRouteSelect).toHaveBeenCalledWith("Wrigleyville", "Loop");
  });

  it("invokes onDeleteRoute with the route id when delete clicked", () => {
    const onDeleteRoute = vi.fn();
    render(<SavedRoutesPanel
      savedRoutes={[route("route-7", "Home → Work")]}
      onDeleteRoute={onDeleteRoute} onRouteSelect={() => {}} onClose={() => {}}
    />);
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(onDeleteRoute).toHaveBeenCalledWith("route-7");
  });

  it("invokes onClose when the close button clicked", () => {
    const onClose = vi.fn();
    render(<SavedRoutesPanel
      savedRoutes={[]} onDeleteRoute={() => {}} onRouteSelect={() => {}} onClose={onClose}
    />);
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("invokes onClose when the backdrop is clicked", () => {
    const onClose = vi.fn();
    const { container } = render(<SavedRoutesPanel
      savedRoutes={[]} onDeleteRoute={() => {}} onRouteSelect={() => {}} onClose={onClose}
    />);
    fireEvent.click(container.querySelector(".settings-backdrop"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("hides the empty-state message when there are saved routes", () => {
    render(<SavedRoutesPanel
      savedRoutes={[route("1", "Some route")]}
      onDeleteRoute={() => {}} onRouteSelect={() => {}} onClose={() => {}}
    />);
    expect(screen.queryByText("No saved routes yet")).toBeNull();
  });
});
