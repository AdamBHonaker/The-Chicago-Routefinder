"""NWS-backed weather service for the CTA Transit PWA backend.

Provides WeatherContext (current conditions + hourly forecast + active alerts)
for a given lat/lon. Used by build_prompt() to inject live weather context into
Claude's recommendation.

Data source: weather.gov (NWS) — free, no API key required.
NWS requires a real contact email in the User-Agent header.
"""

import asyncio
import itertools
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from enum import Enum
from typing import Optional

import aiohttp
from cachetools import TTLCache
from pydantic import BaseModel

_NWS_USER_AGENT = f"CTA-Transit-PWA/1.0 ({os.getenv('NWS_CONTACT_EMAIL', 'adambhonaker@gmail.com')})"
_NWS_BASE = "https://api.weather.gov"

# Grid-point URL cache: (lat_2dp, lon_2dp) → (forecast_url, forecast_hourly_url)
# NWS grid point URLs are stable per location; 24 h TTL is safe.
_grid_cache: TTLCache = TTLCache(maxsize=200, ttl=86400)

# Weather data cache: (lat_2dp, lon_2dp) → WeatherContext, TTL 30 min.
# Chicago at 2-decimal resolution has ~100 grid cells; 30-min TTL is safe since
# weather changes slowly and reduces NWS API calls by ~2.5× vs 12-min TTL.
_weather_cache: TTLCache = TTLCache(maxsize=200, ttl=1800)


# ---------------------------------------------------------------------------
# Chunk 1 — Data models
# ---------------------------------------------------------------------------

class PrecipitationType(str, Enum):
    NONE          = "none"
    RAIN          = "rain"
    SNOW          = "snow"
    SLEET         = "sleet"
    FREEZING_RAIN = "freezing_rain"


class PrecipitationInfo(BaseModel):
    type:      PrecipitationType = PrecipitationType.NONE
    intensity: str               = ""  # "light" | "moderate" | "heavy" | ""


class WindInfo(BaseModel):
    speed_mph: float          = 0.0
    gust_mph:  Optional[float] = None


class CurrentWeather(BaseModel):
    temperature_f: float
    feels_like_f:  float
    short_forecast: str              = ""
    precipitation:  PrecipitationInfo = PrecipitationInfo()
    wind:           WindInfo          = WindInfo()


class ForecastPoint(BaseModel):
    hour:           int
    temperature_f:  float
    short_forecast: str               = ""
    precipitation:  PrecipitationInfo = PrecipitationInfo()
    wind:           WindInfo          = WindInfo()


class WeatherContext(BaseModel):
    current:          CurrentWeather
    hourly_forecast:  list[ForecastPoint] = []
    alerts:           list[str]           = []
    fetched_at:       datetime


# ---------------------------------------------------------------------------
# Chunk 2 — WeatherService class (fetch + parse + cache)
# ---------------------------------------------------------------------------

class WeatherService:
    """Fetches, parses, and caches NWS weather data.

    Public interface: ``await get_weather_context(lat, lon) → WeatherContext``.
    Callers should wrap in try/except — weather is always non-fatal.
    Call ``await close()`` on shutdown to release the shared HTTP session.
    """

    def __init__(self) -> None:
        self._session: Optional[aiohttp.ClientSession] = None

    def _get_session(self) -> aiohttp.ClientSession:
        """Return the shared ClientSession, creating it on first use."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={"User-Agent": _NWS_USER_AGENT}
            )
        return self._session

    async def close(self) -> None:
        """Close the shared HTTP session. Call on application shutdown."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def get_weather_context(self, lat: float, lon: float) -> WeatherContext:
        """Return a WeatherContext for the given coordinates.

        Uses rounded lat/lon (2 decimal places) as the cache key so nearby
        requests share a single NWS API round-trip.
        """
        key = (round(lat, 2), round(lon, 2))

        cached = _weather_cache.get(key)
        if cached is not None:
            return cached

        session = self._get_session()
        _, hourly_url = await self._get_grid_urls(session, key, lat, lon)
        forecast_data, alerts_data = await asyncio.gather(
            self._fetch_json(session, hourly_url),
            self._fetch_json(
                session,
                f"{_NWS_BASE}/alerts/active"
                f"?point={round(lat, 4)},{round(lon, 4)}",
            ),
        )

        context = self._parse_nws_response(forecast_data, alerts_data)
        _weather_cache[key] = context
        return context

    # --- Private helpers ---

    async def _get_grid_urls(
        self,
        session: aiohttp.ClientSession,
        key: tuple,
        lat: float,
        lon: float,
    ) -> tuple[str, str]:
        """Return (forecastUrl, forecastHourlyUrl) from /points, using cache."""
        cached = _grid_cache.get(key)
        if cached:
            return cached
        data = await self._fetch_json(
            session, f"{_NWS_BASE}/points/{round(lat, 4)},{round(lon, 4)}"
        )
        props = data.get("properties", {})
        urls: tuple[str, str] = (
            props.get("forecast", ""),
            props.get("forecastHourly", ""),
        )
        if not urls[0] or not urls[1]:
            raise ValueError("NWS returned empty forecast URLs")
        _grid_cache[key] = urls
        return urls

    async def _fetch_json(
        self, session: aiohttp.ClientSession, url: str
    ) -> dict:
        async with session.get(
            url, timeout=aiohttp.ClientTimeout(total=10)
        ) as resp:
            resp.raise_for_status()
            return await resp.json()

    def _parse_precip(self, short_forecast: str) -> PrecipitationInfo:
        """Infer precipitation type and intensity from NWS short-forecast text."""
        fc = short_forecast.lower()

        # Single pass: determine type by priority (sleet > freezing > snow > rain).
        # The else branch handles all non-precipitation forecasts.
        if "sleet" in fc or "ice pellet" in fc:
            ptype = PrecipitationType.SLEET
        elif "freezing" in fc or "ice" in fc:
            ptype = PrecipitationType.FREEZING_RAIN
        elif "snow" in fc or "flurr" in fc or "blizzard" in fc:
            ptype = PrecipitationType.SNOW
        elif "rain" in fc or "drizzle" in fc or "shower" in fc:
            ptype = PrecipitationType.RAIN
        else:
            return PrecipitationInfo(type=PrecipitationType.NONE)

        if "heavy" in fc or "blizzard" in fc:
            intensity = "heavy"
        elif "light" in fc or "drizzle" in fc or "flurr" in fc:
            intensity = "light"
        else:
            intensity = "moderate"

        return PrecipitationInfo(type=ptype, intensity=intensity)

    def _parse_wind(
        self, wind_speed_str: str, wind_gust_str: str = ""
    ) -> WindInfo:
        """Parse NWS wind-speed strings like '10 mph' or '5 to 10 mph'."""
        def _to_mph(s: str) -> float:
            s = s.lower().replace("mph", "").strip()
            if " to " in s:
                parts = s.split(" to ")
                try:
                    return (float(parts[0].strip()) + float(parts[1].strip())) / 2
                except ValueError:
                    return 0.0
            try:
                return float(s.strip()) if s.strip() else 0.0
            except ValueError:
                return 0.0

        speed = _to_mph(wind_speed_str)
        gust  = _to_mph(wind_gust_str) if wind_gust_str.strip() else None
        return WindInfo(speed_mph=speed, gust_mph=gust if gust else None)

    def _feels_like(
        self, temp_f: float, wind_speed_mph: float, humidity_pct: float = 50.0
    ) -> float:
        """Wind chill (≤50°F + wind ≥3 mph) or heat index (≥80°F), else temp_f.

        Uses NWS wind-chill formula and NWS Rothfusz heat-index regression with
        actual relative humidity (not a hardcoded assumption).
        """
        if temp_f <= 50 and wind_speed_mph >= 3:
            # NWS wind-chill formula
            w = wind_speed_mph ** 0.16
            return (
                35.74
                + 0.6215 * temp_f
                - 35.75 * w
                + 0.4275 * temp_f * w
            )
        if temp_f >= 80:
            rh = humidity_pct
            hi = (
                -42.379
                + 2.04901523 * temp_f
                + 10.14333127 * rh
                - 0.22475541 * temp_f * rh
                - 6.83783e-3  * temp_f ** 2
                - 5.481717e-2 * rh ** 2
                + 1.22874e-3  * temp_f ** 2 * rh
                + 8.5282e-4   * temp_f * rh ** 2
                - 1.99e-6     * temp_f ** 2 * rh ** 2
            )
            # NWS adjustment: very low humidity reduces apparent heat
            if rh < 13 and 80 <= temp_f <= 112:
                hi -= (13 - rh) / 4 * ((17 - abs(temp_f - 95)) / 17) ** 0.5
            # NWS adjustment: high humidity + mild heat increases apparent heat
            elif rh > 85 and 80 <= temp_f <= 87:
                hi += (rh - 85) / 10 * (87 - temp_f) / 5
            return max(temp_f, hi)
        return temp_f

    def _parse_nws_response(
        self, forecast_data: dict, alerts_data: dict
    ) -> WeatherContext:
        """Map NWS hourly forecast + alerts JSON → WeatherContext."""
        periods = forecast_data.get("properties", {}).get("periods", [])

        current: CurrentWeather | None = None
        hourly: list[ForecastPoint]   = []

        for period in itertools.islice(periods, 13):  # current period + next 12 hours
            temp_f = float(period.get("temperature", 55))
            if period.get("temperatureUnit", "F") == "C":
                temp_f = temp_f * 9 / 5 + 32

            short_fc = period.get("shortForecast", "")
            wind     = self._parse_wind(
                period.get("windSpeed", ""),
                period.get("windGust", "") or "",
            )
            rh_raw      = period.get("relativeHumidity") or {}
            humidity_pct = float(rh_raw.get("value") or 50.0)
            precip = self._parse_precip(short_fc)
            feels  = round(self._feels_like(temp_f, wind.speed_mph, humidity_pct), 1)

            try:
                hour = datetime.fromisoformat(
                    period.get("startTime", "")
                ).hour
            except Exception:
                hour = 0

            if current is None:
                current = CurrentWeather(
                    temperature_f=temp_f,
                    feels_like_f=feels,
                    short_forecast=short_fc,
                    precipitation=precip,
                    wind=wind,
                )
            else:
                hourly.append(ForecastPoint(
                    hour=hour,
                    temperature_f=temp_f,
                    short_forecast=short_fc,
                    precipitation=precip,
                    wind=wind,
                ))

        if current is None:
            current = CurrentWeather(
                temperature_f=55.0,
                feels_like_f=55.0,
                short_forecast="Unknown",
            )

        seen: set[str] = set()
        alert_headlines: list[str] = []
        for feature in alerts_data.get("features", []):
            props    = feature.get("properties", {})
            headline = props.get("headline") or props.get("event", "")
            if headline and headline not in seen:
                seen.add(headline)
                alert_headlines.append(headline)

        return WeatherContext(
            current=current,
            hourly_forecast=hourly[:6],
            alerts=alert_headlines[:3],
            fetched_at=datetime.now(ZoneInfo("America/Chicago")),
        )
