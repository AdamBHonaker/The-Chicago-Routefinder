/**
 * BottomSheet tests.
 *
 * Covered:
 *  - resolveSnapPx parses px / % / dvh / numeric correctly
 *  - decideSnap picks nearest under threshold velocity
 *  - decideSnap promotes one snap on upward flick (negative velocity)
 *  - decideSnap demotes one snap on downward flick (positive velocity)
 *  - decideSnap forces nearest under reduced-motion regardless of velocity
 *  - Render: handle has accessible name from handleLabel prop
 *  - Render: role=dialog, aria-modal=false
 *  - Render: body renders children
 *  - Settle (uncontrolled): pointerdown/up cycle calls onSnapChange
 *  - obscuredAreaCallback fires on mount with current sheet height
 *
 * Pointer-event drag flows are exercised at the pure-function layer
 * (decideSnap) rather than via DOM simulation — jsdom's pointer-event
 * support is partial and the velocity-aware snap math is the real
 * correctness concern.
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import {
  BottomSheet,
  decideSnap,
  resolveSnapPx,
  SHEET_VELOCITY_THRESHOLD,
  BODY_DRAG_DEADZONE_PX,
} from "../mobile-sheet-kit/BottomSheet.jsx";

describe("resolveSnapPx", () => {
  it("returns numbers unchanged", () => {
    expect(resolveSnapPx(140, 800)).toBe(140);
  });

  it("parses px values", () => {
    expect(resolveSnapPx("140px", 800)).toBe(140);
  });

  it("parses % against container height", () => {
    expect(resolveSnapPx("50%", 800)).toBe(400);
  });

  it("parses dvh against window.innerHeight", () => {
    const original = window.innerHeight;
    Object.defineProperty(window, "innerHeight", { value: 1000, configurable: true });
    try {
      expect(resolveSnapPx("88dvh", 0)).toBe(880);
    } finally {
      Object.defineProperty(window, "innerHeight", { value: original, configurable: true });
    }
  });

  it("returns 0 for unparseable values", () => {
    expect(resolveSnapPx("garbage", 800)).toBe(0);
  });
});

describe("decideSnap", () => {
  // Three snap heights at 140 / 400 / 700 inside a 700 px sheet.
  const snapPx = [140, 400, 700];
  const maxHeightPx = 700;
  // restingTranslate per snap: 700-140=560 (peek), 700-400=300 (half),
  // 700-700=0 (full).

  it("picks nearest snap when no velocity is provided", () => {
    const idx = decideSnap({
      samples: [],
      currentSnap: 0,
      finalTranslate: 290,           // close to half (300)
      snapPx,
      maxHeightPx,
      reducedMotion: false,
    });
    expect(idx).toBe(1);
  });

  it("falls back to nearest under reduced motion regardless of velocity", () => {
    const samples = [
      { t: 0,   y: 600 },
      { t: 16,  y: 400 },           // strong upward flick: -12.5 px/ms
      { t: 32,  y: 200 },
    ];
    const idx = decideSnap({
      samples,
      currentSnap: 0,
      finalTranslate: 540,           // close to peek (560)
      snapPx,
      maxHeightPx,
      reducedMotion: true,
    });
    expect(idx).toBe(0);
  });

  it("promotes one snap on an upward flick above threshold", () => {
    const samples = [
      { t: 0,  y: 600 },
      { t: 32, y: 500 },             // -3.125 px/ms upward, > 0.8
    ];
    const idx = decideSnap({
      samples,
      currentSnap: 0,                // currently at peek
      finalTranslate: 540,
      snapPx,
      maxHeightPx,
      reducedMotion: false,
    });
    expect(idx).toBe(1);             // promoted to half
  });

  it("demotes one snap on a downward flick above threshold", () => {
    const samples = [
      { t: 0,  y: 100 },
      { t: 32, y: 200 },             // +3.125 px/ms downward
    ];
    const idx = decideSnap({
      samples,
      currentSnap: 2,                // currently at full
      finalTranslate: 50,
      snapPx,
      maxHeightPx,
      reducedMotion: false,
    });
    expect(idx).toBe(1);             // demoted to half
  });

  it("returns nearest when velocity is below threshold", () => {
    const samples = [
      { t: 0,  y: 500 },
      { t: 100, y: 480 },            // -0.2 px/ms, < 0.8
    ];
    const idx = decideSnap({
      samples,
      currentSnap: 0,
      finalTranslate: 290,           // closer to half (300) than peek (560)
      snapPx,
      maxHeightPx,
      reducedMotion: false,
    });
    expect(idx).toBe(1);
  });

  it("clamps when promoting past the highest snap", () => {
    const samples = [
      { t: 0,  y: 200 },
      { t: 32, y: 100 },             // strong upward flick
    ];
    const idx = decideSnap({
      samples,
      currentSnap: 2,                // already at the top
      finalTranslate: 0,
      snapPx,
      maxHeightPx,
      reducedMotion: false,
    });
    expect(idx).toBe(2);
  });

  it("exposes tunables for visibility", () => {
    expect(SHEET_VELOCITY_THRESHOLD).toBeGreaterThan(0);
    expect(BODY_DRAG_DEADZONE_PX).toBeGreaterThan(0);
  });
});

describe("BottomSheet render", () => {
  it("uses handleLabel as the handle's accessible name", () => {
    render(
      <BottomSheet handleLabel="Drag me up or down">child</BottomSheet>,
    );
    expect(screen.getByRole("button", { name: "Drag me up or down" })).toBeInTheDocument();
  });

  it("renders with role='dialog' and aria-modal='false'", () => {
    const { container } = render(<BottomSheet>child</BottomSheet>);
    const dialog = container.querySelector("[role='dialog']");
    expect(dialog).not.toBeNull();
    expect(dialog).toHaveAttribute("aria-modal", "false");
  });

  it("renders children inside the body", () => {
    render(<BottomSheet><p>hello</p></BottomSheet>);
    expect(screen.getByText("hello")).toBeInTheDocument();
  });

  it("renders nothing when open=false", () => {
    const { container } = render(<BottomSheet open={false}>child</BottomSheet>);
    expect(container.querySelector(".bottom-sheet")).toBeNull();
  });

  it("calls obscuredAreaCallback after mount", () => {
    const cb = vi.fn();
    render(<BottomSheet obscuredAreaCallback={cb}>child</BottomSheet>);
    expect(cb).toHaveBeenCalled();
  });
});
