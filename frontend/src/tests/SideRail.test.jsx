/**
 * SideRail component tests.
 *
 * Covered:
 *  - Renders all four nav tabs (home/map/alerts/saved)
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
  it("renders all four navigation tabs with their codes", () => {
    render(<SideRail activeTab="home" onTabChange={() => {}} />);
    expect(screen.getByText("H")).toBeInTheDocument();
    expect(screen.getByText("M")).toBeInTheDocument();
    expect(screen.getByText("A")).toBeInTheDocument();
    expect(screen.getByText("S")).toBeInTheDocument();
  });

  it("uses translated aria-labels for each tab", () => {
    render(<SideRail activeTab="home" onTabChange={() => {}} />);
    expect(screen.getByRole("button", { name: "Home"   })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Map"    })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Alerts" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Saved"  })).toBeInTheDocument();
  });

  it("marks the active tab with aria-current='page'", () => {
    render(<SideRail activeTab="map" onTabChange={() => {}} />);
    expect(screen.getByRole("button", { name: "Map" })).toHaveAttribute("aria-current", "page");
  });

  it("does not mark inactive tabs with aria-current", () => {
    render(<SideRail activeTab="map" onTabChange={() => {}} />);
    expect(screen.getByRole("button", { name: "Home"   })).not.toHaveAttribute("aria-current");
    expect(screen.getByRole("button", { name: "Alerts" })).not.toHaveAttribute("aria-current");
    expect(screen.getByRole("button", { name: "Saved"  })).not.toHaveAttribute("aria-current");
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
