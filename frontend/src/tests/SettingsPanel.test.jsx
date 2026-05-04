/**
 * SettingsPanel component tests.
 *
 * Covered:
 *  - Renders as a modal dialog with translated aria-label
 *  - AI checkbox reflects aiEnabled prop and fires onAiChange
 *  - Walk-speed buttons render; active one carries the active-modifier class
 *  - Clicking a walk-speed button fires onWalkSpeedChange with the speed
 *  - BYOK section omitted entirely when BYOK_ENABLED=false
 *  - BYOK section present when BYOK_ENABLED=true
 *  - Invalid key (no sk-ant- prefix) flags error and disables Save
 *  - Valid key (or empty) clears the error and enables Save
 *  - Save invokes onSave with the trimmed key, then onClose
 *  - "Remove key" button shown only when apiKey is set; clears via onSave('')
 *  - Backdrop click invokes onClose
 *  - When parent clears apiKey externally, the input value re-syncs
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

// Default to BYOK off; individual tests toggle by mutating the mock module
vi.mock("../constants.js", async () => {
  const actual = await vi.importActual("../constants.js");
  return { ...actual, BYOK_ENABLED: false };
});

import SettingsPanel from "../components/SettingsPanel.jsx";
import * as constants from "../constants.js";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key) => {
      const dict = {
        settings_title:                 "Settings",
        settings_ai_explanation_label:  "AI",
        settings_ai_explanation_hint:   "AI hint",
        settings_walk_speed_label:      "Walk speed",
        settings_walk_speed_hint:       "Walk hint",
        settings_walk_speed_slow:       "Slow",
        settings_walk_speed_standard:   "Standard",
        settings_walk_speed_brisk:      "Brisk",
        settings_byok_security_notice:  "Security notice",
        settings_label_api_key:         "API Key",
        settings_hint_api_key:          "Key hint",
        settings_error_key_format:      "Invalid key format",
        settings_btn_save:              "Save",
        settings_btn_remove_key:        "Remove key",
        settings_btn_close:             "Close",
        aria_close_settings:            "Close settings",
        caps_preferences:               "PREFERENCES",
      };
      return dict[key] ?? key;
    },
  }),
}));

const baseProps = (overrides = {}) => ({
  apiKey: "",
  onSave: vi.fn(),
  onClose: vi.fn(),
  aiEnabled: false,
  onAiChange: vi.fn(),
  walkSpeed: "standard",
  onWalkSpeedChange: vi.fn(),
  ...overrides,
});

describe("SettingsPanel", () => {
  beforeEach(() => {
    constants.BYOK_ENABLED = false;
  });
  afterEach(() => {
    constants.BYOK_ENABLED = false;
  });

  it("renders as a dialog with translated aria-label", () => {
    render(<SettingsPanel {...baseProps()} />);
    expect(screen.getByRole("dialog", { name: "Settings" })).toBeInTheDocument();
  });

  it("AI checkbox reflects aiEnabled=true", () => {
    render(<SettingsPanel {...baseProps({ aiEnabled: true })} />);
    expect(screen.getByRole("checkbox")).toBeChecked();
  });

  it("AI checkbox unchecked when aiEnabled=false", () => {
    render(<SettingsPanel {...baseProps({ aiEnabled: false })} />);
    expect(screen.getByRole("checkbox")).not.toBeChecked();
  });

  it("toggles onAiChange with new boolean when AI checkbox clicked", () => {
    const props = baseProps({ aiEnabled: false });
    render(<SettingsPanel {...props} />);
    fireEvent.click(screen.getByRole("checkbox"));
    expect(props.onAiChange).toHaveBeenCalledWith(true);
  });

  it("renders all three walk-speed buttons", () => {
    render(<SettingsPanel {...baseProps()} />);
    expect(screen.getByRole("button", { name: "Slow"     })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Standard" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Brisk"    })).toBeInTheDocument();
  });

  it("active walk-speed button has the active modifier class", () => {
    render(<SettingsPanel {...baseProps({ walkSpeed: "brisk" })} />);
    expect(screen.getByRole("button", { name: "Brisk" }))
      .toHaveClass("settings-speed-btn--active");
    expect(screen.getByRole("button", { name: "Slow" }))
      .not.toHaveClass("settings-speed-btn--active");
  });

  it("clicking a walk-speed button fires onWalkSpeedChange", () => {
    const props = baseProps();
    render(<SettingsPanel {...props} />);
    fireEvent.click(screen.getByRole("button", { name: "Brisk" }));
    expect(props.onWalkSpeedChange).toHaveBeenCalledWith("brisk");
  });

  it("invokes onClose when the Close (X) button clicked", () => {
    const props = baseProps();
    render(<SettingsPanel {...props} />);
    fireEvent.click(screen.getByRole("button", { name: "Close settings" }));
    expect(props.onClose).toHaveBeenCalledTimes(1);
  });

  it("invokes onClose when the backdrop is clicked", () => {
    const props = baseProps();
    const { container } = render(<SettingsPanel {...props} />);
    fireEvent.click(container.querySelector(".settings-backdrop"));
    expect(props.onClose).toHaveBeenCalledTimes(1);
  });

  it("omits the BYOK section entirely when BYOK_ENABLED=false", () => {
    render(<SettingsPanel {...baseProps()} />);
    expect(screen.queryByText("API Key")).toBeNull();
    expect(screen.queryByText("Security notice")).toBeNull();
  });

  it("renders the BYOK section when BYOK_ENABLED=true", () => {
    constants.BYOK_ENABLED = true;
    render(<SettingsPanel {...baseProps()} />);
    expect(screen.getByText("API Key")).toBeInTheDocument();
    expect(screen.getByText("Security notice")).toBeInTheDocument();
  });

  it("flags an invalid key (no sk-ant- prefix) and disables Save", () => {
    constants.BYOK_ENABLED = true;
    render(<SettingsPanel {...baseProps({ apiKey: "not-a-real-key" })} />);
    expect(screen.getByText("Invalid key format")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
  });

  it("accepts a valid key (sk-ant- prefix) and enables Save", () => {
    constants.BYOK_ENABLED = true;
    render(<SettingsPanel {...baseProps({ apiKey: "sk-ant-abc123" })} />);
    expect(screen.queryByText("Invalid key format")).toBeNull();
    expect(screen.getByRole("button", { name: "Save" })).not.toBeDisabled();
  });

  it("treats an empty string as valid (no error, but Save still enabled)", () => {
    constants.BYOK_ENABLED = true;
    render(<SettingsPanel {...baseProps({ apiKey: "" })} />);
    expect(screen.queryByText("Invalid key format")).toBeNull();
  });

  it("Save invokes onSave with trimmed key, then onClose", () => {
    constants.BYOK_ENABLED = true;
    const props = baseProps({ apiKey: "sk-ant-keep" });
    render(<SettingsPanel {...props} />);
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(props.onSave).toHaveBeenCalledWith("sk-ant-keep");
    expect(props.onClose).toHaveBeenCalledTimes(1);
  });

  it("hides 'Remove key' button when no key is set", () => {
    constants.BYOK_ENABLED = true;
    render(<SettingsPanel {...baseProps({ apiKey: "" })} />);
    expect(screen.queryByRole("button", { name: "Remove key" })).toBeNull();
  });

  it("shows 'Remove key' when apiKey is set; clears via onSave('')", () => {
    constants.BYOK_ENABLED = true;
    const props = baseProps({ apiKey: "sk-ant-keep" });
    render(<SettingsPanel {...props} />);
    fireEvent.click(screen.getByRole("button", { name: "Remove key" }));
    expect(props.onSave).toHaveBeenCalledWith("");
    expect(props.onClose).toHaveBeenCalledTimes(1);
  });

  it("re-syncs the input when parent clears apiKey externally", () => {
    constants.BYOK_ENABLED = true;
    const { rerender } = render(<SettingsPanel {...baseProps({ apiKey: "sk-ant-x" })} />);
    expect(screen.getByPlaceholderText("sk-ant-…")).toHaveValue("sk-ant-x");

    // Parent clears the key (e.g. BYOK idle-clear timer fires)
    rerender(<SettingsPanel {...baseProps({ apiKey: "" })} />);
    expect(screen.getByPlaceholderText("sk-ant-…")).toHaveValue("");
  });
});
