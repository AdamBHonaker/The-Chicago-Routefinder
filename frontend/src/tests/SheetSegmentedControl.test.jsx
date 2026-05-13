/**
 * SheetSegmentedControl tests.
 *
 * Covered:
 *  - Renders three buttons (Home / Alerts / Tools) with translated labels
 *  - No Map button (map is always visible on mobile; Map segment would be redundant)
 *  - Active segment gets aria-selected="true" and aria-current="page"
 *  - Inactive segments get aria-selected="false" and no aria-current
 *  - Click invokes onTabChange with the segment id
 *  - tablist role on the wrapper, with translated aria-label
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import SheetSegmentedControl from "../components/SheetSegmentedControl.jsx";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key) => {
      if (key === "aria_main_nav") return "Main navigation";
      if (key === "tab_home")      return "Home";
      if (key === "tab_alerts")    return "Alerts";
      if (key === "tab_tools")     return "Tools";
      return key;
    },
  }),
}));

describe("SheetSegmentedControl", () => {
  it("renders three segments with translated labels", () => {
    render(<SheetSegmentedControl activeTab="home" onTabChange={() => {}} />);
    expect(screen.getByRole("tab", { name: "Home"   })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Alerts" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Tools"  })).toBeInTheDocument();
  });

  it("does not render a Map segment", () => {
    render(<SheetSegmentedControl activeTab="home" onTabChange={() => {}} />);
    expect(screen.queryByRole("tab", { name: "Map" })).not.toBeInTheDocument();
  });

  it("marks the active segment with aria-selected and aria-current", () => {
    render(<SheetSegmentedControl activeTab="alerts" onTabChange={() => {}} />);
    const alerts = screen.getByRole("tab", { name: "Alerts" });
    expect(alerts).toHaveAttribute("aria-selected", "true");
    expect(alerts).toHaveAttribute("aria-current", "page");
  });

  it("marks inactive segments without aria-current", () => {
    render(<SheetSegmentedControl activeTab="alerts" onTabChange={() => {}} />);
    const home = screen.getByRole("tab", { name: "Home" });
    expect(home).toHaveAttribute("aria-selected", "false");
    expect(home).not.toHaveAttribute("aria-current");
  });

  it("applies the active modifier class", () => {
    const { container } = render(
      <SheetSegmentedControl activeTab="tools" onTabChange={() => {}} />,
    );
    const active = container.querySelector(".sheet-segmented__btn--active");
    expect(active).not.toBeNull();
    expect(active.textContent).toBe("Tools");
  });

  it("calls onTabChange with the segment id when clicked", () => {
    const onTabChange = vi.fn();
    render(<SheetSegmentedControl activeTab="home" onTabChange={onTabChange} />);
    fireEvent.click(screen.getByRole("tab", { name: "Tools" }));
    expect(onTabChange).toHaveBeenCalledWith("tools");
  });

  it("renders a tablist with a translated aria-label", () => {
    render(<SheetSegmentedControl activeTab="home" onTabChange={() => {}} />);
    expect(screen.getByRole("tablist", { name: "Main navigation" })).toBeInTheDocument();
  });
});
