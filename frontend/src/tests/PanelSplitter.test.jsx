/**
 * PanelSplitter tests.
 *
 * Covered:
 *  - Renders with role="separator" and the correct aria-* attributes
 *  - Keyboard ArrowLeft/ArrowRight nudge value by 16px and clamp to bounds
 *  - Home/End jump to min/max
 *  - Pointer drag updates value via onChange (rAF-throttled)
 *  - onCommit fires on pointerup with the final value
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import PanelSplitter from "../components/PanelSplitter.jsx";

// Per-test override of the dir() return value. Default LTR; RTL tests below
// set this to "rtl" before render.
let mockDir = "ltr";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key, opts) => (opts && opts.defaultValue) || key,
    i18n: { dir: () => mockDir },
  }),
}));

beforeEach(() => {
  // jsdom: stub rAF so we can flush synchronously
  vi.stubGlobal("requestAnimationFrame", (cb) => setTimeout(cb, 0));
  vi.stubGlobal("cancelAnimationFrame", (id) => clearTimeout(id));
  mockDir = "ltr";
});

afterEach(() => {
  vi.unstubAllGlobals();
  mockDir = "ltr";
});

describe("PanelSplitter", () => {
  it("renders a vertical separator with the correct aria attributes", () => {
    render(<PanelSplitter value={520} min={520} max={1200} onChange={() => {}} />);
    const sep = screen.getByRole("separator");
    expect(sep).toHaveAttribute("aria-orientation", "vertical");
    expect(sep).toHaveAttribute("aria-valuenow", "520");
    expect(sep).toHaveAttribute("aria-valuemin", "520");
    expect(sep).toHaveAttribute("aria-valuemax", "1200");
    expect(sep).toHaveAttribute("tabIndex", "0");
  });

  it("nudges right by 16px on ArrowRight, calling onCommit with the clamped result", () => {
    const onChange = vi.fn();
    const onCommit = vi.fn();
    // value is 5px below max → ArrowRight (16px nudge) clamps to max
    render(
      <PanelSplitter value={615} min={520} max={620} onChange={onChange} onCommit={onCommit} />
    );
    const sep = screen.getByRole("separator");
    fireEvent.keyDown(sep, { key: "ArrowRight" });
    expect(onChange).toHaveBeenCalledWith(620);
    expect(onCommit).toHaveBeenCalledWith(620);
  });

  it("nudges left by 16px on ArrowLeft and clamps at min", () => {
    const onChange = vi.fn();
    render(
      <PanelSplitter value={530} min={520} max={1200} onChange={onChange} />
    );
    const sep = screen.getByRole("separator");
    fireEvent.keyDown(sep, { key: "ArrowLeft" });
    // 530-16 = 514 → clamped to 520
    expect(onChange).toHaveBeenCalledWith(520);
  });

  it("jumps to min on Home and max on End", () => {
    const onChange = vi.fn();
    render(<PanelSplitter value={700} min={520} max={1200} onChange={onChange} />);
    const sep = screen.getByRole("separator");
    fireEvent.keyDown(sep, { key: "Home" });
    expect(onChange).toHaveBeenCalledWith(520);
    fireEvent.keyDown(sep, { key: "End" });
    expect(onChange).toHaveBeenCalledWith(1200);
  });

  it("commits the final value on pointer up", () => {
    const onCommit = vi.fn();
    const onChange = vi.fn();
    render(
      <PanelSplitter value={600} min={520} max={1200} onChange={onChange} onCommit={onCommit} offsetLeft={60} />
    );
    const sep = screen.getByRole("separator");
    sep.setPointerCapture = vi.fn();
    sep.releasePointerCapture = vi.fn();
    fireEvent.pointerDown(sep, { button: 0, pointerType: "mouse", pointerId: 1, clientX: 600 });
    fireEvent.pointerUp(sep, { pointerId: 1 });
    expect(onCommit).toHaveBeenCalled();
  });

  // BUG-010 regression: when the last pointer move happens after the last
  // committed onChange, endDrag must still commit the most recent dragged
  // value — not the stale prop captured before the move landed.
  it("commits the latest dragged value, not the stale prop, when rAF coalesces the last move", () => {
    const onCommit = vi.fn();
    const onChange = vi.fn();
    render(
      <PanelSplitter value={600} min={520} max={1200} onChange={onChange} onCommit={onCommit} offsetLeft={60} />
    );
    const sep = screen.getByRole("separator");
    sep.setPointerCapture = vi.fn();
    sep.releasePointerCapture = vi.fn();
    fireEvent.pointerDown(sep, { button: 0, pointerType: "mouse", pointerId: 1, clientX: 600 });
    // Simulate pointer move whose rAF hasn't fired yet — value prop never
    // updated because the parent re-render is synchronous-but-not-applied
    // in this isolated test (no parent state). endDrag must still commit
    // 800, not 600.
    fireEvent.pointerMove(sep, { pointerId: 1, clientX: 860 }); // 860 - offsetLeft 60 = 800
    fireEvent.pointerUp(sep, { pointerId: 1 });
    expect(onCommit).toHaveBeenLastCalledWith(800);
  });

  // RTL: when the writing direction is RTL the layout grid auto-flips, so
  // the cards column sits on the right and the side-rail on the right edge.
  // The drag math must invert so dragging the splitter handle visually-left
  // grows the cards column (which extends leftward from the right edge).
  describe("RTL", () => {
    it("inverts pointer-move math: (window.innerWidth - clientX - offsetLeft)", () => {
      mockDir = "rtl";
      // jsdom default window.innerWidth is 1024 unless overridden.
      Object.defineProperty(window, "innerWidth", { configurable: true, value: 1200 });
      const onChange = vi.fn();
      const onCommit = vi.fn();
      render(
        <PanelSplitter value={520} min={520} max={1000} onChange={onChange} onCommit={onCommit} offsetLeft={60} />
      );
      const sep = screen.getByRole("separator");
      sep.setPointerCapture = vi.fn();
      sep.releasePointerCapture = vi.fn();
      fireEvent.pointerDown(sep, { button: 0, pointerType: "mouse", pointerId: 1, clientX: 600 });
      fireEvent.pointerMove(sep, { pointerId: 1, clientX: 340 }); // 1200 - 340 - 60 = 800
      fireEvent.pointerUp(sep, { pointerId: 1 });
      expect(onCommit).toHaveBeenLastCalledWith(800);
    });

    it("ArrowLeft grows the cards column, ArrowRight shrinks it", () => {
      mockDir = "rtl";
      const onChange = vi.fn();
      render(
        <PanelSplitter value={700} min={520} max={1200} onChange={onChange} />
      );
      const sep = screen.getByRole("separator");
      fireEvent.keyDown(sep, { key: "ArrowLeft" });
      expect(onChange).toHaveBeenLastCalledWith(716); // 700 + 16
      fireEvent.keyDown(sep, { key: "ArrowRight" });
      expect(onChange).toHaveBeenLastCalledWith(684); // 700 - 16
    });
  });
});
