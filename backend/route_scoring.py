"""Weather-adjusted route weight scoring (Feature Weather Scoring).

Provides DEFAULT_WEIGHTS and adjust_weights_for_weather() to produce a
weight dict that shifts scoring priorities based on live weather conditions.
The weights are communicated to Claude as a one-line prompt hint — they do not
numerically re-rank routes (prompt-only path, scoping decision 1).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from weather_service import WeatherContext

from weather_service import PrecipitationType


DEFAULT_WEIGHTS: dict[str, float] = {
    "travel_time":      0.35,
    "outdoor_exposure": 0.25,
    "crowdedness":      0.20,
    "reliability":      0.15,
    "transfers":        0.05,
}


def adjust_weights_for_weather(
    base_weights: dict[str, float],
    weather: "WeatherContext | None",
) -> dict[str, float]:
    """Return a copy of base_weights adjusted for current weather conditions.

    Threshold-based deltas (scoping decision 3):
    - feels_like_f < 0  → outdoor_exposure +0.20, travel_time -0.10
    - feels_like_f < 15 → outdoor_exposure +0.10, travel_time -0.05
    - Heavy precipitation → outdoor_exposure +0.15, travel_time -0.10
    - Wind gusts > 35 mph → reliability +0.05

    Temperature checks are coldest-first (< 0 before < 15); only one fires.
    All weights are clamped to ≥ 0.0 and then normalized to sum to 1.0.
    Returns a plain copy of base_weights when weather is None.
    """
    if weather is None:
        return dict(base_weights)

    weights = dict(base_weights)
    c = weather.current

    # Temperature thresholds — coldest first; only one fires
    if c.feels_like_f < 0:
        weights["outdoor_exposure"] += 0.20
        weights["travel_time"]      -= 0.10
    elif c.feels_like_f < 15:
        weights["outdoor_exposure"] += 0.10
        weights["travel_time"]      -= 0.05

    # Heavy precipitation
    if (
        c.precipitation.type != PrecipitationType.NONE
        and c.precipitation.intensity == "heavy"
    ):
        weights["outdoor_exposure"] += 0.15
        weights["travel_time"]      -= 0.10

    # High gusts
    if c.wind.gust_mph is not None and c.wind.gust_mph > 35:
        weights["reliability"] += 0.05

    # Clamp negatives, then normalize to 1.0
    weights = {k: max(0.0, v) for k, v in weights.items()}
    total = sum(weights.values())
    if total > 0:
        weights = {k: round(v / total, 4) for k, v in weights.items()}

    return weights


def weight_hint_for_weather(weather: "WeatherContext | None") -> str:
    """Return a one-line weight-guidance hint string for the Claude prompt.

    Returns "" when weather is None or no adjustment thresholds are triggered.
    Only active conditions are mentioned; parts are joined with "; ".
    """
    if weather is None:
        return ""

    c = weather.current
    parts: list[str] = []

    # Temperature hints — coldest first; only one fires (mirrors adjust_weights_for_weather)
    if c.feels_like_f < 0:
        parts.append("outdoor exposure heavily prioritized due to dangerous wind chill")
    elif c.feels_like_f < 15:
        parts.append("outdoor exposure prioritized due to extreme cold")

    # Heavy precipitation hint
    if (
        c.precipitation.type != PrecipitationType.NONE
        and c.precipitation.intensity == "heavy"
    ):
        ptype = c.precipitation.type.value
        parts.append(f"outdoor exposure prioritized due to heavy {ptype}")

    # High-gust hint
    if c.wind.gust_mph is not None and c.wind.gust_mph > 35:
        parts.append(f"reliability weighted for high wind gusts ({c.wind.gust_mph:.0f} mph)")

    if not parts:
        return ""

    return "Weight guidance: " + "; ".join(parts) + "."
