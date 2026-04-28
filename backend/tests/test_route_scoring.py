"""
Unit tests for route_scoring.py.

Coverage targets:
  adjust_weights_for_weather:
    - None weather → returns copy of base weights unchanged
    - Very cold (feels_like < 0) → outdoor_exposure +0.20, travel_time -0.10
    - Extreme cold (0 ≤ feels_like < 15) → outdoor_exposure +0.10, travel_time -0.05
    - Mild temp → no temperature adjustment
    - Heavy precip → outdoor_exposure +0.15, travel_time -0.10
    - High gusts → reliability +0.05
    - Weights always sum to 1.0 after normalization
    - Negative weights clamped to 0.0

  weight_hint_for_weather:
    - None weather → empty string
    - Very cold → hint mentions wind chill
    - Heavy precip → hint mentions precipitation
    - No active conditions → empty string
"""

import pytest
from unittest.mock import MagicMock

from route_scoring import (
    DEFAULT_WEIGHTS,
    adjust_weights_for_weather,
    weight_hint_for_weather,
)
from weather_service import PrecipitationType


def _make_weather(feels_like_f=55.0, precip_type=PrecipitationType.NONE,
                  precip_intensity="", gust_mph=None):
    """Build a minimal WeatherContext-like mock."""
    weather = MagicMock()
    weather.current.feels_like_f = feels_like_f
    weather.current.precipitation.type = precip_type
    weather.current.precipitation.intensity = precip_intensity
    weather.current.wind.gust_mph = gust_mph
    return weather


# ---------------------------------------------------------------------------
# adjust_weights_for_weather
# ---------------------------------------------------------------------------

class TestAdjustWeightsForWeather:
    def test_none_weather_returns_copy(self):
        result = adjust_weights_for_weather(DEFAULT_WEIGHTS, None)
        assert result == DEFAULT_WEIGHTS
        assert result is not DEFAULT_WEIGHTS  # must be a copy

    def test_weights_sum_to_one_after_adjustment(self):
        weather = _make_weather(feels_like_f=-10.0)
        result = adjust_weights_for_weather(DEFAULT_WEIGHTS, weather)
        assert sum(result.values()) == pytest.approx(1.0, abs=1e-3)

    def test_very_cold_raises_outdoor_exposure(self):
        weather = _make_weather(feels_like_f=-5.0)
        result = adjust_weights_for_weather(DEFAULT_WEIGHTS, weather)
        baseline = adjust_weights_for_weather(DEFAULT_WEIGHTS, _make_weather(60.0))
        assert result["outdoor_exposure"] > baseline["outdoor_exposure"]

    def test_extreme_cold_less_adjustment_than_very_cold(self):
        very_cold = adjust_weights_for_weather(DEFAULT_WEIGHTS, _make_weather(-5.0))
        extreme_cold = adjust_weights_for_weather(DEFAULT_WEIGHTS, _make_weather(10.0))
        mild = adjust_weights_for_weather(DEFAULT_WEIGHTS, _make_weather(60.0))
        assert very_cold["outdoor_exposure"] > extreme_cold["outdoor_exposure"] > mild["outdoor_exposure"]

    def test_mild_temp_no_temperature_adjustment(self):
        mild = adjust_weights_for_weather(DEFAULT_WEIGHTS, _make_weather(60.0))
        none = adjust_weights_for_weather(DEFAULT_WEIGHTS, None)
        assert mild == none

    def test_heavy_precip_raises_outdoor_exposure(self):
        weather = _make_weather(feels_like_f=55.0,
                                precip_type=PrecipitationType.RAIN,
                                precip_intensity="heavy")
        result = adjust_weights_for_weather(DEFAULT_WEIGHTS, weather)
        none_result = adjust_weights_for_weather(DEFAULT_WEIGHTS, None)
        assert result["outdoor_exposure"] > none_result["outdoor_exposure"]

    def test_non_heavy_precip_no_adjustment(self):
        weather = _make_weather(feels_like_f=55.0,
                                precip_type=PrecipitationType.RAIN,
                                precip_intensity="moderate")
        result = adjust_weights_for_weather(DEFAULT_WEIGHTS, weather)
        none_result = adjust_weights_for_weather(DEFAULT_WEIGHTS, None)
        assert result == none_result

    def test_high_gusts_raises_reliability(self):
        weather = _make_weather(gust_mph=40.0)
        result = adjust_weights_for_weather(DEFAULT_WEIGHTS, weather)
        none_result = adjust_weights_for_weather(DEFAULT_WEIGHTS, None)
        assert result["reliability"] > none_result["reliability"]

    def test_low_gusts_no_adjustment(self):
        weather = _make_weather(gust_mph=20.0)
        result = adjust_weights_for_weather(DEFAULT_WEIGHTS, weather)
        none_result = adjust_weights_for_weather(DEFAULT_WEIGHTS, None)
        assert result["reliability"] == pytest.approx(none_result["reliability"], abs=1e-3)

    def test_no_negative_weights(self):
        # Combine multiple heavy conditions — weights must stay ≥ 0
        weather = _make_weather(feels_like_f=-20.0,
                                precip_type=PrecipitationType.SNOW,
                                precip_intensity="heavy",
                                gust_mph=50.0)
        result = adjust_weights_for_weather(DEFAULT_WEIGHTS, weather)
        for key, val in result.items():
            assert val >= 0.0, f"Weight {key} went negative: {val}"


# ---------------------------------------------------------------------------
# weight_hint_for_weather
# ---------------------------------------------------------------------------

class TestWeightHintForWeather:
    def test_none_weather_returns_empty(self):
        assert weight_hint_for_weather(None) == ""

    def test_very_cold_mentions_wind_chill(self):
        weather = _make_weather(feels_like_f=-5.0)
        hint = weight_hint_for_weather(weather)
        assert hint != ""
        assert "wind chill" in hint.lower() or "cold" in hint.lower()

    def test_mild_weather_returns_empty(self):
        weather = _make_weather(feels_like_f=55.0)
        assert weight_hint_for_weather(weather) == ""

    def test_heavy_precip_returns_nonempty(self):
        weather = _make_weather(feels_like_f=55.0,
                                precip_type=PrecipitationType.RAIN,
                                precip_intensity="heavy")
        assert weight_hint_for_weather(weather) != ""
