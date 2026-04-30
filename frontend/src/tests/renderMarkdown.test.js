import { describe, it, expect } from "vitest";
import { renderMarkdown } from "../utils/renderMarkdown.js";

describe("renderMarkdown", () => {
  it("strips h1/h2/h3 heading markers", () => {
    expect(renderMarkdown("# Title")).toBe("Title");
    expect(renderMarkdown("## Sub")).toBe("Sub");
    expect(renderMarkdown("### Deep")).toBe("Deep");
  });

  it("strips bold **text**", () => {
    expect(renderMarkdown("Take the **Red Line**")).toBe("Take the Red Line");
  });

  it("strips italic *text*", () => {
    expect(renderMarkdown("Walk *quickly*")).toBe("Walk quickly");
  });

  it("strips italic _text_", () => {
    expect(renderMarkdown("Walk _quickly_")).toBe("Walk quickly");
  });

  it("strips inline code `text`", () => {
    expect(renderMarkdown("Use `platform 1`")).toBe("Use platform 1");
  });

  it("strips markdown links [label](url)", () => {
    expect(renderMarkdown("See [CTA](https://cta.com) for info")).toBe("See CTA for info");
  });

  it("strips bullet markers", () => {
    expect(renderMarkdown("- Take the Red Line")).toBe("Take the Red Line");
    expect(renderMarkdown("* Take the Red Line")).toBe("Take the Red Line");
  });

  it("strips blockquote markers", () => {
    expect(renderMarkdown("> Note: transfers apply")).toBe("Note: transfers apply");
  });

  it("trims surrounding whitespace", () => {
    expect(renderMarkdown("  hello  ")).toBe("hello");
  });

  it("leaves plain text unchanged", () => {
    const text = "Walk north on State St for 2 blocks.";
    expect(renderMarkdown(text)).toBe(text);
  });
});
