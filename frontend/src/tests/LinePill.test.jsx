/**
 * LinePill component smoke tests — first component-level coverage in the suite (TD-111).
 *
 * Demonstrates the @testing-library/react setup. Future component tests should
 * follow the same pattern: render → query by accessible role/text → assert.
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import LinePill from "../components/LinePill.jsx";

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
