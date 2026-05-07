/**
 * RouteAlertsBanner component tests.
 *
 * Covered:
 *  - Present state renders as a button with the present copy + CTA.
 *  - Absent state renders as a static <p> with no click target.
 *  - Click on present banner invokes onView once.
 *  - aria-label set on the present (clickable) variant.
 *  - Severity-style modifier classes match the design spec.
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import RouteAlertsBanner from "../components/RouteAlertsBanner.jsx";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key) => {
      if (key === "route_alerts_banner_present")       return "PRESENT BODY";
      if (key === "route_alerts_banner_present_cta")   return "PRESENT CTA";
      if (key === "route_alerts_banner_present_aria")  return "View notices for this route in Notices & Delays.";
      if (key === "route_alerts_banner_absent")        return "ABSENT BODY";
      if (key === "caps_advisories")                   return "ADVISORIES";
      return key;
    },
  }),
}));

describe("RouteAlertsBanner", () => {
  it("renders the present body and CTA when hasAlerts is true", () => {
    render(<RouteAlertsBanner hasAlerts={true} onView={() => {}} />);
    expect(screen.getByText("PRESENT BODY")).toBeInTheDocument();
    expect(screen.getByText("PRESENT CTA")).toBeInTheDocument();
    expect(screen.queryByText("ABSENT BODY")).toBeNull();
  });

  it("renders as a button with aria-label when alerts are present", () => {
    render(<RouteAlertsBanner hasAlerts={true} onView={() => {}} />);
    const btn = screen.getByRole("button", { name: "View notices for this route in Notices & Delays." });
    expect(btn).toBeInTheDocument();
    expect(btn.tagName).toBe("BUTTON");
  });

  it("invokes onView when the present banner is clicked", () => {
    const onView = vi.fn();
    render(<RouteAlertsBanner hasAlerts={true} onView={onView} />);
    fireEvent.click(screen.getByRole("button"));
    expect(onView).toHaveBeenCalledTimes(1);
  });

  it("renders the absent body when hasAlerts is false", () => {
    render(<RouteAlertsBanner hasAlerts={false} />);
    expect(screen.getByText("ABSENT BODY")).toBeInTheDocument();
    expect(screen.queryByText("PRESENT BODY")).toBeNull();
    expect(screen.queryByText("PRESENT CTA")).toBeNull();
  });

  it("renders the absent variant as a non-interactive <p> (no button role)", () => {
    const { container } = render(<RouteAlertsBanner hasAlerts={false} />);
    expect(screen.queryByRole("button")).toBeNull();
    expect(container.querySelector("p.route-alerts-banner--absent")).toBeInTheDocument();
  });

  it("applies the advisory severity modifier when alerts are present", () => {
    const { container } = render(<RouteAlertsBanner hasAlerts={true} onView={() => {}} />);
    expect(container.querySelector(".special-dispatch--advisory")).toBeInTheDocument();
    expect(container.querySelector(".special-dispatch--quiet")).toBeNull();
  });

  it("applies the quiet severity modifier when no alerts are present", () => {
    const { container } = render(<RouteAlertsBanner hasAlerts={false} />);
    expect(container.querySelector(".special-dispatch--quiet")).toBeInTheDocument();
    expect(container.querySelector(".special-dispatch--advisory")).toBeNull();
  });
});
