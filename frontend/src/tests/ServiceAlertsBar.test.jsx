/**
 * ServiceAlertsBar component tests.
 *
 * Covered:
 *  - Returns null when alerts is null / undefined / empty
 *  - One element rendered per alert
 *  - Alerts sorted Major → Minor → Planned/Advisory
 *  - severity → CSS modifier mapping
 *  - Routes joined with " · " when present
 *  - Routes element omitted when no affected routes
 *  - Optional short_description rendered when present
 *  - Dismiss button calls onDismiss with alert_id
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import ServiceAlertsBar from "../components/ServiceAlertsBar.jsx";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key) => {
      if (key === "alerts_severity_major")    return "ALERT";
      if (key === "alerts_severity_minor")    return "NOTICE";
      if (key === "alerts_severity_advisory") return "ADVISORY";
      if (key === "alerts_dismiss")           return "Dismiss";
      return key;
    },
  }),
}));

const alert = (overrides = {}) => ({
  alert_id: "1",
  severity: "Major",
  headline: "Red Line delays",
  routes: [],
  ...overrides,
});

describe("ServiceAlertsBar", () => {
  it("renders nothing when alerts is null", () => {
    const { container } = render(<ServiceAlertsBar alerts={null} onDismiss={() => {}} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders nothing when alerts is empty array", () => {
    const { container } = render(<ServiceAlertsBar alerts={[]} onDismiss={() => {}} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders one element per alert", () => {
    const alerts = [
      alert({ alert_id: "1", headline: "First" }),
      alert({ alert_id: "2", headline: "Second" }),
    ];
    render(<ServiceAlertsBar alerts={alerts} onDismiss={() => {}} />);
    expect(screen.getByText("First")).toBeInTheDocument();
    expect(screen.getByText("Second")).toBeInTheDocument();
  });

  it("sorts Major → Minor → Planned/Advisory regardless of input order", () => {
    const alerts = [
      alert({ alert_id: "p", severity: "Planned", headline: "Planned work" }),
      alert({ alert_id: "m", severity: "Minor",   headline: "Minor delay" }),
      alert({ alert_id: "M", severity: "Major",   headline: "Major outage" }),
    ];
    const { container } = render(<ServiceAlertsBar alerts={alerts} onDismiss={() => {}} />);
    const headlines = Array.from(container.querySelectorAll(".special-dispatch__body"))
      .map((el) => el.textContent);
    expect(headlines).toEqual(["Major outage", "Minor delay", "Planned work"]);
  });

  it("applies severity-specific CSS modifier classes", () => {
    const alerts = [
      alert({ alert_id: "1", severity: "Major", headline: "x" }),
      alert({ alert_id: "2", severity: "Minor", headline: "y" }),
      alert({ alert_id: "3", severity: "Planned", headline: "z" }),
    ];
    const { container } = render(<ServiceAlertsBar alerts={alerts} onDismiss={() => {}} />);
    expect(container.querySelector(".special-dispatch--major")).toBeInTheDocument();
    expect(container.querySelector(".special-dispatch--minor")).toBeInTheDocument();
    expect(container.querySelector(".special-dispatch--advisory")).toBeInTheDocument();
  });

  it("joins affected routes with ' · '", () => {
    render(<ServiceAlertsBar
      alerts={[alert({ routes: ["Red", "Blue", "Green"] })]}
      onDismiss={() => {}}
    />);
    expect(screen.getByText("Red · Blue · Green")).toBeInTheDocument();
  });

  it("omits the routes element when no routes affected", () => {
    const { container } = render(<ServiceAlertsBar
      alerts={[alert({ routes: [] })]}
      onDismiss={() => {}}
    />);
    expect(container.querySelector(".special-dispatch__routes")).toBeNull();
  });

  it("renders short_description when present", () => {
    render(<ServiceAlertsBar
      alerts={[alert({ short_description: "Trains delayed 10–20 minutes." })]}
      onDismiss={() => {}}
    />);
    expect(screen.getByText("Trains delayed 10–20 minutes.")).toBeInTheDocument();
  });

  it("calls onDismiss with the alert_id when dismiss button clicked", () => {
    const onDismiss = vi.fn();
    render(<ServiceAlertsBar
      alerts={[alert({ alert_id: "ABC123" })]}
      onDismiss={onDismiss}
    />);
    fireEvent.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(onDismiss).toHaveBeenCalledWith("ABC123");
  });

  it("treats unknown severity as advisory (sorted last)", () => {
    const alerts = [
      alert({ alert_id: "u", severity: "Unknown", headline: "Mystery" }),
      alert({ alert_id: "M", severity: "Major",   headline: "Major" }),
    ];
    const { container } = render(<ServiceAlertsBar alerts={alerts} onDismiss={() => {}} />);
    const order = Array.from(container.querySelectorAll(".special-dispatch__body"))
      .map((el) => el.textContent);
    expect(order[0]).toBe("Major");
    expect(order[1]).toBe("Mystery");
  });
});
