"""
Unit tests for weather_service.py pure helper methods.

Coverage targets:
  WeatherService._parse_precip:
    - Sunny/clear → NONE
    - Rain words → RAIN
    - Snow/blizzard/flurries → SNOW
    - Sleet/ice pellet → SLEET
    - Freezing / ice → FREEZING_RAIN
    - Intensity: light, moderate, heavy

  WeatherService._parse_wind:
    - "10 mph" → 10.0 speed, no gust
    - "5 to 10 mph" → 7.5 average
    - empty string gust → None
    - malformed string → 0.0

  WeatherService._feels_like:
    - Above 50°F with low wind → returns temp
    - ≤50°F + ≥3 mph wind → wind-chill below temp
    - ≥80°F → heat-index ≥ temp
"""

import pytest
from weather_service import WeatherService, PrecipitationType, PrecipitationInfo


@pytest.fixture
def svc():
    return WeatherService()


# ---------------------------------------------------------------------------
# _parse_precip
# ---------------------------------------------------------------------------

class TestParsePrecip:
    def test_clear_sky_is_none(self, svc):
        result = svc._parse_precip("Sunny")
        assert result.type == PrecipitationType.NONE

    def test_partly_cloudy_is_none(self, svc):
        result = svc._parse_precip("Mostly Cloudy")
        assert result.type == PrecipitationType.NONE

    def test_rain(self, svc):
        result = svc._parse_precip("Chance Rain Showers")
        assert result.type == PrecipitationType.RAIN

    def test_drizzle_is_rain(self, svc):
        result = svc._parse_precip("Light Drizzle")
        assert result.type == PrecipitationType.RAIN

    def test_snow(self, svc):
        result = svc._parse_precip("Snow Likely")
        assert result.type == PrecipitationType.SNOW

    def test_blizzard_is_snow_heavy(self, svc):
        result = svc._parse_precip("Blizzard Conditions")
        assert result.type == PrecipitationType.SNOW
        assert result.intensity == "heavy"

    def test_flurries_is_snow_light(self, svc):
        result = svc._parse_precip("Snow Flurries")
        assert result.type == PrecipitationType.SNOW
        assert result.intensity == "light"

    def test_sleet(self, svc):
        result = svc._parse_precip("Sleet")
        assert result.type == PrecipitationType.SLEET

    def test_ice_pellets_is_sleet(self, svc):
        result = svc._parse_precip("Ice Pellets")
        assert result.type == PrecipitationType.SLEET

    def test_freezing_rain(self, svc):
        result = svc._parse_precip("Freezing Rain")
        assert result.type == PrecipitationType.FREEZING_RAIN

    def test_intensity_light(self, svc):
        result = svc._parse_precip("Light Rain")
        assert result.intensity == "light"

    def test_intensity_heavy(self, svc):
        result = svc._parse_precip("Heavy Rain")
        assert result.intensity == "heavy"

    def test_intensity_moderate_default(self, svc):
        result = svc._parse_precip("Rain")
        assert result.intensity == "moderate"

    def test_empty_string_is_none(self, svc):
        result = svc._parse_precip("")
        assert result.type == PrecipitationType.NONE


# ---------------------------------------------------------------------------
# _parse_wind
# ---------------------------------------------------------------------------

class TestParseWind:
    def test_simple_mph(self, svc):
        wind = svc._parse_wind("10 mph")
        assert wind.speed_mph == pytest.approx(10.0)
        assert wind.gust_mph is None

    def test_range_string_averages(self, svc):
        wind = svc._parse_wind("5 to 10 mph")
        assert wind.speed_mph == pytest.approx(7.5)

    def test_gust_parsed(self, svc):
        wind = svc._parse_wind("10 mph", "20 mph")
        assert wind.gust_mph == pytest.approx(20.0)

    def test_empty_gust_is_none(self, svc):
        wind = svc._parse_wind("10 mph", "")
        assert wind.gust_mph is None

    def test_malformed_returns_zero(self, svc):
        wind = svc._parse_wind("calm")
        assert wind.speed_mph == pytest.approx(0.0)

    def test_zero_speed(self, svc):
        wind = svc._parse_wind("0 mph")
        assert wind.speed_mph == pytest.approx(0.0)

    def test_zero_gust_preserved_not_dropped(self, svc):
        # Regression: '0 mph' gust is a real reading (genuine calm), not "no data".
        # A truthy check would coerce 0.0 → None and lose the distinction.
        wind = svc._parse_wind("5 mph", "0 mph")
        assert wind.gust_mph == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# _feels_like
# ---------------------------------------------------------------------------

class TestFeelsLike:
    def test_mild_temp_no_wind_returns_temp(self, svc):
        # 60°F, 5 mph — no wind chill (>50°F), no heat index (<80°F)
        result = svc._feels_like(60.0, 5.0)
        assert result == pytest.approx(60.0)

    def test_cold_with_wind_chill_lower_than_temp(self, svc):
        # 30°F, 20 mph — wind chill should be well below 30
        result = svc._feels_like(30.0, 20.0)
        assert result < 30.0

    def test_no_wind_chill_below_threshold_speed(self, svc):
        # ≤50°F but wind < 3 mph → no wind chill
        result = svc._feels_like(40.0, 2.0)
        assert result == pytest.approx(40.0)

    def test_heat_index_uses_actual_rh(self, svc):
        # 90°F — heat index should increase with higher humidity
        result_low_rh  = svc._feels_like(90.0, 0.0, humidity_pct=40.0)
        result_high_rh = svc._feels_like(90.0, 0.0, humidity_pct=80.0)
        assert result_low_rh  >= 90.0
        assert result_high_rh >= 90.0
        assert result_high_rh > result_low_rh  # higher RH → hotter apparent temp

    def test_heat_index_default_humidity_param(self, svc):
        # default humidity_pct=50 must match explicit kwarg
        assert svc._feels_like(90.0, 0.0) == pytest.approx(
            svc._feels_like(90.0, 0.0, humidity_pct=50.0)
        )

    def test_heat_index_high_rh_mild_heat_adjustment(self, svc):
        # RH > 85% + 80-87°F triggers NWS upward adjustment
        result_no_adj   = svc._feels_like(85.0, 0.0, humidity_pct=85.0)
        result_with_adj = svc._feels_like(85.0, 0.0, humidity_pct=90.0)
        assert result_with_adj >= result_no_adj

    def test_feels_like_exact_50_with_wind(self, svc):
        # Exactly 50°F with 5 mph → wind chill applies (≤50 AND ≥3)
        result = svc._feels_like(50.0, 5.0)
        assert result < 50.0
