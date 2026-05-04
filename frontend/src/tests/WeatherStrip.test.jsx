/**
 * WeatherStrip component tests.
 *
 * Covered:
 *  - Returns null when no weather data
 *  - Temperature rendered when present, omitted when missing
 *  - Feels-like only shown when ≥2°F divergence from temperature
 *  - Precipitation label translated for known keys; raw value for unknown
 *  - Precipitation intensity appended when given
 *  - Wind gusts shown only at ≥15 mph
 *  - First alert displayed (truncated to 80 chars)
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import WeatherStrip from "../components/WeatherStrip.jsx";

// Replicate i18next interpolation for the keys WeatherStrip uses
vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key, vars) => {
      if (key === "weather_label") return "weather";
      if (key === "weather_feels_like" && vars?.temp != null) return `feels like ${vars.temp}°`;
      if (key === "weather_gusts"      && vars?.mph  != null) return `gusts ${vars.mph} mph`;
      if (key === "precip_rain")          return "rain";
      if (key === "precip_snow")          return "snow";
      if (key === "precip_sleet")         return "sleet";
      if (key === "precip_freezing_rain") return "freezing rain";
      return key;
    },
  }),
}));

describe("WeatherStrip", () => {
  it("renders nothing when weather is null", () => {
    const { container } = render(<WeatherStrip weather={null} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders nothing when weather is undefined", () => {
    const { container } = render(<WeatherStrip />);
    expect(container.firstChild).toBeNull();
  });

  it("renders rounded temperature with degree sign", () => {
    render(<WeatherStrip weather={{ temperature_f: 72.4, short_forecast: "Sunny" }} />);
    expect(screen.getByText(/72°/)).toBeInTheDocument();
    expect(screen.getByText(/Sunny/)).toBeInTheDocument();
  });

  it("omits temperature when temperature_f is missing", () => {
    const { container } = render(<WeatherStrip weather={{ short_forecast: "Foggy" }} />);
    expect(container.querySelector(".weather-strip__temp")).toBeNull();
  });

  it("hides feels-like when divergence from temperature is < 2°F", () => {
    // 70 vs 71 — 1° apart, should NOT show feels-like
    const { container } = render(<WeatherStrip
      weather={{ temperature_f: 70, feels_like_f: 71, short_forecast: "Mild" }}
    />);
    expect(container.querySelector(".weather-strip__feels")).toBeNull();
  });

  it("shows feels-like when divergence ≥ 2°F", () => {
    // 30 vs 18 — 12° apart with wind chill
    render(<WeatherStrip
      weather={{ temperature_f: 30, feels_like_f: 18, short_forecast: "Windy" }}
    />);
    expect(screen.getByText(/feels like 18°/)).toBeInTheDocument();
  });

  it("shows translated precipitation label for known precip type", () => {
    render(<WeatherStrip weather={{
      temperature_f: 40, short_forecast: "Cloudy",
      precipitation_type: "snow", precipitation_intensity: "heavy",
    }} />);
    expect(screen.getByText(/snow \(heavy\)/)).toBeInTheDocument();
  });

  it("falls back to raw type string when precip type is unknown", () => {
    render(<WeatherStrip weather={{
      temperature_f: 40, short_forecast: "Mist",
      precipitation_type: "fog",
    }} />);
    // Unknown type displayed verbatim (no intensity → no parens)
    expect(screen.getByText(/Mist · fog/)).toBeInTheDocument();
  });

  it("hides precipitation entirely when type is 'none'", () => {
    const { container } = render(<WeatherStrip weather={{
      temperature_f: 60, short_forecast: "Clear",
      precipitation_type: "none",
    }} />);
    expect(container.textContent).not.toMatch(/none/);
  });

  it("shows wind gusts when ≥ 15 mph", () => {
    render(<WeatherStrip weather={{
      temperature_f: 50, short_forecast: "Breezy", wind_gust_mph: 25,
    }} />);
    expect(screen.getByText(/gusts 25 mph/)).toBeInTheDocument();
  });

  it("hides wind gusts when < 15 mph", () => {
    const { container } = render(<WeatherStrip weather={{
      temperature_f: 50, short_forecast: "Calm", wind_gust_mph: 10,
    }} />);
    expect(container.textContent).not.toMatch(/gusts/);
  });

  it("displays the first alert with warning sigil", () => {
    render(<WeatherStrip weather={{
      temperature_f: 40, short_forecast: "Stormy",
      alerts: ["Tornado watch in effect"],
    }} />);
    expect(screen.getByText(/Tornado watch in effect/)).toBeInTheDocument();
    expect(screen.getByText(/⚠/)).toBeInTheDocument();
  });

  it("truncates alert text to 80 characters", () => {
    const longAlert = "x".repeat(200);
    render(<WeatherStrip weather={{
      temperature_f: 40, short_forecast: "Stormy", alerts: [longAlert],
    }} />);
    const alertEl = document.querySelector(".weather-strip__alert");
    // Includes the "⚠ " prefix (2 chars) plus 80 chars
    expect(alertEl.textContent.length).toBe(82);
  });

  it("renders no alert element when alerts array is empty", () => {
    const { container } = render(<WeatherStrip weather={{
      temperature_f: 40, short_forecast: "Clear", alerts: [],
    }} />);
    expect(container.querySelector(".weather-strip__alert")).toBeNull();
  });
});
