"""Weather-adjusted route weight scoring (Feature Weather Scoring).

Provides weight_hint_for_weather() — a one-line prompt hint communicated to
Claude. Weights do not numerically re-rank routes (prompt-only path,
scoping decision 1).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from weather_service import WeatherContext

from weather_service import PrecipitationType, CurrentWeather

# Gust threshold above which trains/buses may run with delays or reduced speed.
# 35 mph aligns with NWS Wind Advisory criteria for sustained or gust impacts
# and matches CTA's observed operational threshold for service impacts on
# elevated lines. Tune via env var if seasonal calibration becomes useful.
_HIGH_WIND_GUST_MPH: float = 35.0


def _active_hints(c: CurrentWeather) -> list[str]:
    """Return prompt-hint strings for every weather condition that fires.

    Parameters
    ----------
    c : CurrentWeather
        The now-cast portion of a ``WeatherContext`` (i.e. ``weather.current``).

    Notes
    -----
    Temperature checks are coldest-first (< 0 °F before < 15 °F); only one
    fires per call. "Fires" = the condition matched a threshold and a hint
    string was appended for inclusion in the Claude prompt.
    """
    hints: list[str] = []

    if c.feels_like_f < 0:
        hints.append("outdoor exposure heavily prioritized due to dangerous wind chill")
    elif c.feels_like_f < 15:
        hints.append("outdoor exposure prioritized due to extreme cold")

    if (
        c.precipitation.type != PrecipitationType.NONE
        and c.precipitation.intensity == "heavy"
    ):
        hints.append(f"outdoor exposure prioritized due to heavy {c.precipitation.type.value}")

    if c.wind.gust_mph is not None and c.wind.gust_mph > _HIGH_WIND_GUST_MPH:
        hints.append(f"reliability weighted for high wind gusts ({c.wind.gust_mph:.0f} mph)")

    return hints


def weight_hint_for_weather(weather: "WeatherContext | None") -> str:
    """Return a one-line weight-guidance hint string for the Claude prompt.

    Returns "" when weather is None or no adjustment thresholds are triggered.
    Only active conditions are mentioned; parts are joined with "; ".
    """
    if weather is None:
        return ""

    hints = _active_hints(weather.current)
    if not hints:
        return ""

    return "Weight guidance: " + "; ".join(hints) + "."
