"""
Unit tests for route_scoring.py.

Coverage targets:
  weight_hint_for_weather:
    - None weather → empty string
    - Very cold → hint mentions wind chill
    - Heavy precip → hint mentions precipitation
    - No active conditions → empty string
"""

from unittest.mock import MagicMock

from route_scoring import weight_hint_for_weather
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
