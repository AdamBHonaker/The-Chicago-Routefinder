/**
 * SideRail component tests.
 *
 * Covered:
 *  - Renders the three desktop nav tabs (home/alerts/saved). The Map tab was
 *    removed from the desktop side rail when the persistent-map layout shipped
 *    — the map is always visible on desktop so a Map tab there is redundant.
 *    Mobile retains a 4-tab bar (Home/Map/Alerts/Saved) in App.jsx.
 *  - Each tab shows its single-letter code
 *  - Active tab gets aria-current="page"
 *  - Inactive tabs do not get aria-current
 *  - Clicking a tab calls onTabChange with the tab id
 *  - nav has translated aria-label
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import SideRail from "../components/SideRail.jsx";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key) => {
      if (key === "aria_main_nav") return "Main navigation";
      if (key === "app_title")     return "Routefinder";
      if (key === "tab_home")      return "Home";
      if (key === "tab_map")       return "Map";
      if (key === "tab_alerts")    return "Alerts";
      if (key === "tab_saved")     return "Saved";
      return key;
    },
  }),
}));

describe("SideRail", () => {
  it("renders the three desktop navigation tabs with their codes", () => {
    render(<SideRail activeTab="home" onTabChange={() => {}} />);
    expect(screen.getByText("H")).toBeInTheDocument();
    expect(screen.getByText("A")).toBeInTheDocument();
    expect(screen.getByText("S")).toBeInTheDocument();
  });

  it("does not render a Map tab (map is persistent on desktop)", () => {
    render(<SideRail activeTab="home" onTabChange={() => {}} />);
    expect(screen.queryByText("M")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Map" })).not.toBeInTheDocument();
  });

  it("uses translated aria-labels for each tab", () => {
    render(<SideRail activeTab="home" onTabChange={() => {}} />);
    expect(screen.getByRole("button", { name: "Home"   })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Alerts" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Saved"  })).toBeInTheDocument();
  });

  it("marks the active tab with aria-current='page'", () => {
    render(<SideRail activeTab="alerts" onTabChange={() => {}} />);
    expect(screen.getByRole("button", { name: "Alerts" })).toHaveAttribute("aria-current", "page");
  });

  it("does not mark inactive tabs with aria-current", () => {
    render(<SideRail activeTab="alerts" onTabChange={() => {}} />);
    expect(screen.getByRole("button", { name: "Home"  })).not.toHaveAttribute("aria-current");
    expect(screen.getByRole("button", { name: "Saved" })).not.toHaveAttribute("aria-current");
  });

  it("applies the active modifier class to the active tab", () => {
    const { container } = render(<SideRail activeTab="alerts" onTabChange={() => {}} />);
    const active = container.querySelector(".side-rail__tab--active");
    expect(active).not.toBeNull();
    expect(active.textContent).toBe("A");
  });

  it("calls onTabChange with the tab id when clicked", () => {
    const onTabChange = vi.fn();
    render(<SideRail activeTab="home" onTabChange={onTabChange} />);
    fireEvent.click(screen.getByRole("button", { name: "Saved" }));
    expect(onTabChange).toHaveBeenCalledWith("saved");
  });

  it("uses a translated aria-label on the nav", () => {
    render(<SideRail activeTab="home" onTabChange={() => {}} />);
    expect(screen.getByRole("navigation", { name: "Main navigation" })).toBeInTheDocument();
  });
});
