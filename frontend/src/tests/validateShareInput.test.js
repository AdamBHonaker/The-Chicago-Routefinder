import { describe, it, expect } from "vitest";
import { looksHostile, SHARE_INPUT_MAX_CHARS } from "../utils/validateShareInput.js";

describe("looksHostile", () => {
  it("rejects empty / falsy values", () => {
    expect(looksHostile("")).toBe(true);
    expect(looksHostile(null)).toBe(true);
    expect(looksHostile(undefined)).toBe(true);
  });

  it("rejects oversize values", () => {
    expect(looksHostile("a".repeat(SHARE_INPUT_MAX_CHARS + 1))).toBe(true);
  });

  it("accepts values at the size limit", () => {
    expect(looksHostile("a".repeat(SHARE_INPUT_MAX_CHARS))).toBe(false);
  });

  it.each([
    ["javascript:alert(1)"],
    ["JavaScript:alert(1)"],
    ["  javascript:alert(1)"],
    ["data:text/html,<script>"],
    ["vbscript:msgbox"],
    ["file:///etc/passwd"],
  ])("rejects hostile pseudo-URL %s", (value) => {
    expect(looksHostile(value)).toBe(true);
  });

  it.each([
    ["http://evil.example.com/path"],
    ["https://evil.example.com"],
    ["ftp://example.com"],
    ["//cdn.example.com/x"],
  ])("rejects embedded URLs (%s)", (value) => {
    expect(looksHostile(value)).toBe(true);
  });

  it.each([
    ["State & Lake"],
    ["1060 W Addison St, Chicago, IL"],
    ["41.881832,-87.623177"],
    ["Wrigley Field"],
    ["Café Jumping Bean"],
  ])("accepts legitimate location strings (%s)", (value) => {
    expect(looksHostile(value)).toBe(false);
  });
});
