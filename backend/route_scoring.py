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


def _active_conditions(c) -> list[tuple[dict[str, float], str]]:
    """Evaluate weather thresholds once; return (weight_deltas, hint_text) pairs.

    Temperature checks are coldest-first (< 0 before < 15); only one fires.
    """
    conditions: list[tuple[dict[str, float], str]] = []

    if c.feels_like_f < 0:
        conditions.append((
            {"outdoor_exposure": +0.20, "travel_time": -0.10},
            "outdoor exposure heavily prioritized due to dangerous wind chill",
        ))
    elif c.feels_like_f < 15:
        conditions.append((
            {"outdoor_exposure": +0.10, "travel_time": -0.05},
            "outdoor exposure prioritized due to extreme cold",
        ))

    if (
        c.precipitation.type != PrecipitationType.NONE
        and c.precipitation.intensity == "heavy"
    ):
        ptype = c.precipitation.type.value
        conditions.append((
            {"outdoor_exposure": +0.15, "travel_time": -0.10},
            f"outdoor exposure prioritized due to heavy {ptype}",
        ))

    if c.wind.gust_mph is not None and c.wind.gust_mph > 35:
        conditions.append((
            {"reliability": +0.05},
            f"reliability weighted for high wind gusts ({c.wind.gust_mph:.0f} mph)",
        ))

    return conditions


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

    All weights are clamped to ≥ 0.0 and then normalized to sum to 1.0.
    Returns a plain copy of base_weights when weather is None or no thresholds fire.
    """
    if weather is None:
        return dict(base_weights)

    conditions = _active_conditions(weather.current)
    if not conditions:
        return dict(base_weights)

    weights = dict(base_weights)
    for deltas, _ in conditions:
        for k, delta in deltas.items():
            weights[k] += delta

    clamped = [max(0.0, v) for v in weights.values()]
    total = sum(clamped)
    return {k: round(v / total, 4) for k, v in zip(weights.keys(), clamped)}


def weight_hint_for_weather(weather: "WeatherContext | None") -> str:
    """Return a one-line weight-guidance hint string for the Claude prompt.

    Returns "" when weather is None or no adjustment thresholds are triggered.
    Only active conditions are mentioned; parts are joined with "; ".
    """
    if weather is None:
        return ""

    conditions = _active_conditions(weather.current)
    if not conditions:
        return ""

    parts = [hint for _, hint in conditions]
    return "Weight guidance: " + "; ".join(parts) + "."
