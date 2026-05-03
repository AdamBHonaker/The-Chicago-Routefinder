/**
 * LinePill component smoke tests — first component-level coverage in the suite (TD-111).
 *
 * Demonstrates the @testing-library/react setup. Future component tests should
 * follow the same pattern: render → query by accessible role/text → assert.
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import LinePill from "../components/LinePill.jsx";

// LinePill calls `t("map_bus_label", { code })` for the bus aria-label.
// Without a mock the bare key is returned instead of the interpolated string.
// Replicate i18next's `{{var}}` substitution so tests can assert on the real
// rendered label.
vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key, vars) => {
      if (key === "map_bus_label" && vars?.code != null) return `Bus ${vars.code}`;
      return key;
    },
  }),
}));

describe("LinePill", () => {
  it("renders the abbreviated train line code", () => {
    render(<LinePill line="Red Line" isBus={false} size="sm" />);
    expect(screen.getByText("RD")).toBeInTheDocument();
  });

  it("renders the bus route code when isBus is true", () => {
    render(<LinePill line="22" isBus={true} lineCode="22" size="sm" />);
    const pill = screen.getByLabelText("Bus 22");
    expect(pill).toBeInTheDocument();
    expect(pill).toHaveTextContent("22");
  });

  it("uses the full line name at size lg", () => {
    render(<LinePill line="Blue Line" isBus={false} size="lg" />);
    expect(screen.getByText("Blue Line")).toBeInTheDocument();
  });

  it("applies dark text only for Yellow Line, light text otherwise", () => {
    const { rerender } = render(<LinePill line="Yellow Line" isBus={false} size="sm" />);
    expect(screen.getByText("YL")).toHaveStyle({ color: "rgb(17, 17, 17)" });

    rerender(<LinePill line="Red Line" isBus={false} size="sm" />);
    expect(screen.getByText("RD")).toHaveStyle({ color: "rgb(255, 255, 255)" });
  });
});
