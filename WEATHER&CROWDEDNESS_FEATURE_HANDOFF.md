# Chicago Family Transit PWA — Weather & Crowdedness Feature Handoff

## Project Context

This is a personal family transit PWA for Chicago. The existing platform integrates:

- **Google Maps Geocoding API** — location/address resolution (`gtfs_loader.py`)
- **CTA Bus Tracker API** — live bus arrival data (`cta_client.py`)
- **CTA Train Tracker API** — live train arrival data (`cta_client.py`)
- **Anthropic Claude API (Sonnet 4.6)** — natural-language route recommendation (`main.py`)
- **OSMnx street graph** — pedestrian walk routing (`walking.py`)
- **NetworkX transit graph** — train + bus route finding (`transit_graph.py`)

**Tech Stack:** Python (FastAPI) backend + React (Vite PWA) frontend

**Current Phase:** All pre-Phase 6 work is complete. **This feature is planned for post-Phase 6 (after deployment).** Do not begin implementation before deployment is live (Railway + Vercel accounts required first).

**Goal:** Extend the platform with two new capabilities:
1. Live weather data integration
2. Crowdedness/fullness estimation for transit vehicles

These features will feed into a weather-adjusted route scoring system and enrich the Claude recommendation prompt.

---

## Existing Infrastructure Relevant to This Feature

Before implementing anything, read and understand the following:

- **[backend/main.py](backend/main.py)** — FastAPI `/recommend` endpoint. `_rank_routes()` is the existing route scoring function. `build_prompt()` is where all context is assembled before the Claude call. Weather context will be injected here.
- **[backend/cta_client.py](backend/cta_client.py)** — `psgld` field already retrieved from Bus Tracker API and normalized to `EMPTY | HALF_EMPTY | FULL`. Bus fullness filter (`bus_fullness` request param) is already wired end-to-end. **The UI filter is currently hidden because CTA's `psgld` field returns empty strings as of 2026-04-09** — the backend logic is intact, just awaiting real data.
- **[backend/gtfs_loader.py](backend/gtfs_loader.py)** — GTFS data already downloaded and parsed. `backend/gtfs_data/` contains `routes.txt`, `stops.txt`, `stop_times.txt`, `trips.txt`, etc. Do NOT re-download or create a new GTFS loader. `stop_times.txt` is 5.8 M rows / 354 MB — already streamed at startup; never load fully into memory.
- **[backend/transit_graph.py](backend/transit_graph.py)** — `get_bus_stop_sequences()` + `_build_shape_lookup()` already parse stop sequences and route structure from GTFS.
- **[frontend/src/App.jsx](frontend/src/App.jsx)** — `bus_fullness` filter state + hidden UI toggle already present. Unhide and extend when real crowdedness data is available.

**File structure convention:** The backend uses a **flat directory** — all Python modules live directly in `backend/`. Do not create nested subdirectories (`models/`, `services/`, etc.). Add new modules as `backend/weather_service.py`, `backend/crowdedness.py`, etc.

---

## Work Packages Overview

| Package | Name | Dependencies |
|---------|------|--------------|
| WP-1 | Weather API Integration | None |
| WP-2 | Time Period Classification | None |
| WP-3 | Crowdedness Estimation | WP-2 |
| WP-4 | Weather-Adjusted Route Scoring | WP-1, WP-3 |

---

# WP-1: Weather API Integration

## Objective
Integrate a weather API to provide current conditions and short-term forecasts relevant to transit routing decisions in Chicago.

## API Options Analysis

| Provider | Free Tier | Key Strengths | Key Weaknesses | Recommendation |
|----------|-----------|---------------|----------------|----------------|
| **Weather.gov (NWS API)** | Unlimited, no key | Free, reliable, no rate limits, good for US cities | Slower responses, less polished DX | ✅ **Primary choice** |
| **OpenWeatherMap** | 1,000 calls/day | Well-documented, good forecast data, easy to use | Rate limits on free tier | ✅ **Secondary/supplement** |
| **Open-Meteo** | Unlimited, no key | Free, no API key, solid hourly data | Less real-time granularity | Good alternative |
| **Tomorrow.io** | 500 calls/day | Excellent minute-level precipitation | Limited free tier | Optional enhancement |

## Recommended Approach
Implement **Weather.gov (NWS API)** as the primary source. Optionally add **OpenWeatherMap** as a fallback or for minute-level precipitation data.

## Implementation Requirements

### 1.1 — Weather Data Model

Add to a new file `backend/weather_service.py` (flat structure, not `backend/models/`):

```python
from pydantic import BaseModel
from typing import Optional, List
from enum import Enum

class PrecipitationType(str, Enum):
    NONE = "none"
    RAIN = "rain"
    SNOW = "snow"
    SLEET = "sleet"
    FREEZING_RAIN = "freezing_rain"

class PrecipitationInfo(BaseModel):
    type: PrecipitationType
    intensity: Optional[str]  # "light", "moderate", "heavy"
    probability: float  # 0.0 - 1.0

class WindInfo(BaseModel):
    speed_mph: float
    gusts_mph: Optional[float]

class CurrentWeather(BaseModel):
    temp_f: float
    feels_like_f: float
    condition: str  # e.g., "Cloudy", "Snow", "Clear"
    precipitation: PrecipitationInfo
    wind: WindInfo
    visibility_miles: Optional[float] = None   # May require station observations endpoint
    humidity_percent: Optional[float] = None   # May require station observations endpoint

class ForecastPoint(BaseModel):
    time: str  # ISO 8601
    temp_f: float
    condition: str
    precipitation: PrecipitationInfo
    wind: WindInfo

class WeatherContext(BaseModel):
    current: CurrentWeather
    forecast_hourly: List[ForecastPoint]  # Next 6-12 hours
    alerts: List[str]  # Active weather alerts
    fetched_at: str  # ISO 8601 timestamp
```

### 1.2 — Weather Service Class

Use `aiohttp` for HTTP calls — it's already a dependency in `requirements.txt` (used by `cta_client.py`). Do not add a new HTTP library.

```python
# All in backend/weather_service.py
import aiohttp

class WeatherService:
    def __init__(self, cache_ttl_minutes: int = 15):
        ...

    async def get_weather_context(self, lat: float, lon: float) -> WeatherContext:
        """
        Fetches current + forecast weather for given coordinates.
        Uses cache if data is fresh.
        
        Two-step NWS flow:
        1. GET /points/{lat},{lon} → returns forecast URLs (cache this 24h)
        2. GET the forecastHourly URL from step 1 → returns actual weather (cache 10-15 min)
        Also fetches /alerts/active?point={lat},{lon} for weather alerts.
        """
        ...

    def _parse_nws_response(self, forecast: dict, alerts: dict) -> WeatherContext:
        ...

    def _is_cache_valid(self) -> bool:
        ...
```

### 1.3 — Weather.gov API Details

**Endpoints:**
1. Get grid point: `https://api.weather.gov/points/{lat},{lon}`
   - Returns `forecastHourly` and `forecast` URLs
2. Get hourly forecast: Use URL from above response
3. Get alerts: `https://api.weather.gov/alerts/active?point={lat},{lon}`

**Headers required:**
```python
headers = {
    "User-Agent": "(FamilyTransitPWA, your-real-email@example.com)"  # NWS requires a real contact email/URL — replace placeholder
}
```

**No API key required.**

**NWS API parsing notes:**
- There is no dedicated "current conditions" endpoint. Use the **first period** of the hourly forecast as "current" conditions.
- `feels_like_f` is not returned directly — calculate it from temperature + wind speed (wind chill below ~50°F) or temperature + humidity (heat index above ~80°F). The hourly forecast may include a `windChill` field when applicable.
- `windSpeed` is returned as a string like `"10 mph"` or `"5 to 10 mph"` — requires parsing.
- `visibility_miles` and `humidity_percent` may not be in the hourly forecast. If needed, fetch from the nearest observation station: `GET /stations/{stationId}/observations/latest`. Otherwise, drop these from the `CurrentWeather` model to keep it simple.

### 1.4 — Caching Strategy

Use an in-memory TTL-based cache. Note: `walking.py` uses `lru_cache`, but that has no time-based expiry — not suitable for weather data that goes stale. Use `cachetools.TTLCache` (add `cachetools` to `requirements.txt`) or a manual timestamp check:
- **Cache key:** Rounded lat/lon (to 2 decimal places)
- **TTL:** 10-15 minutes for current conditions
- **Grid point URL caching:** The NWS `/points/{lat},{lon}` response (which returns the forecast URL) is stable for a given location. Cache it separately with a much longer TTL (24 hours) to avoid the extra round-trip on every weather fetch.
- **Invalidation:** Force refresh if user explicitly requests

### 1.5 — Integration Point in main.py

The `WeatherService` instance should be created at module level (alongside the existing `_claude_client = anthropic.AsyncAnthropic(...)`). In the `/recommend` endpoint, call `get_weather_context()` using `origin_coords` (already resolved earlier in the handler).

**Important:** `get_weather_context()` is an `async` method — await it directly in the async endpoint handler, the same way `get_train_arrivals()` and `get_bus_arrivals()` are awaited. Do **not** wrap it in `loop.run_in_executor()`, which is only for the CPU-bound graph operations (`resolve_location`, `find_routes`, etc.):

```python
# In /recommend handler, after origin_coords is resolved:
weather = None
if origin_coords:
    try:
        weather = await weather_service.get_weather_context(
            origin_coords[0], origin_coords[1]
        )
    except Exception:
        traceback.print_exc()  # Non-fatal — proceed without weather
```

Pass the resulting `WeatherContext` to `build_prompt()` as a new optional parameter — Claude's natural-language output is the primary "display" of weather context to the user.

### 1.6 — Deliverables Checklist

- [ ] `backend/weather_service.py` — `WeatherContext` models + `WeatherService` class
- [ ] TTL-based cache for weather data (10-15 min) + longer cache for NWS grid point URL (24h). Add `cachetools` to `requirements.txt` if using `TTLCache`.
- [ ] Error handling for API failures (follow existing try/except + `traceback.print_exc()` pattern from `main.py`)
- [ ] Integration into `build_prompt()` in `main.py`

---

# WP-2: Time Period Classification

## Objective
Create a utility to classify any given datetime into peak, regular, or off-peak periods for CTA service, accounting for weekdays, weekends, and holidays.

## Time Period Definitions (Chicago CTA)

| Period | Weekday | Weekend |
|--------|---------|---------|
| **Peak** | 06:30–09:30, 15:30–18:30 | N/A |
| **Regular** | 09:30–15:30, 18:30–21:00 | 09:00–21:00 |
| **Off-Peak** | 21:00–06:30 | 21:00–09:00 |

## Implementation Requirements

### 2.1 — Time Period Enum and Configuration

Add to `backend/crowdedness.py` (co-locate with WP-3 since this is only used for crowdedness estimation):

```python
from enum import Enum

class TimePeriod(str, Enum):
    PEAK = "peak"
    REGULAR = "regular"
    OFF_PEAK = "off_peak"

class DayType(str, Enum):
    WEEKDAY = "weekday"
    WEEKEND = "weekend"
    HOLIDAY = "holiday"  # Treat as weekend

TIME_PERIOD_CONFIG = {
    "weekday": {
        TimePeriod.PEAK: [
            ("06:30", "09:30"),
            ("15:30", "18:30")
        ],
        TimePeriod.REGULAR: [
            ("09:30", "15:30"),
            ("18:30", "21:00")
        ],
        TimePeriod.OFF_PEAK: [
            ("21:00", "23:59"),
            ("00:00", "06:30")
        ]
    },
    "weekend": {
        TimePeriod.PEAK: [],
        TimePeriod.REGULAR: [
            ("09:00", "21:00")
        ],
        TimePeriod.OFF_PEAK: [
            ("21:00", "23:59"),
            ("00:00", "09:00")
        ]
    }
}
```

### 2.2 — Classification Function

```python
from datetime import datetime
from typing import Optional, Set

def classify_time_period(
    dt: datetime,
    holidays: Optional[Set[str]] = None  # Set of "YYYY-MM-DD" strings
) -> tuple[TimePeriod, DayType]:
    """
    Classifies a datetime into (TimePeriod, DayType).
    
    Args:
        dt: The datetime to classify (should be Chicago local time — use CHICAGO_TZ defined locally)
        holidays: Optional set of holiday dates (treated as weekends)
    
    Returns:
        Tuple of (TimePeriod, DayType)
    """
    ...
```

Note: Define `CHICAGO_TZ = ZoneInfo("America/Chicago")` locally in `crowdedness.py` — the same one-liner used in `cta_client.py`. Do not import it from `cta_client.py`; that would create an unnecessary coupling between the crowdedness module and the API client.

### 2.3 — Holiday Handling

```python
# Option 1: Static list (simpler, no new dependency)
CHICAGO_HOLIDAYS = {
    "2026-01-01",  # New Year's Day
    "2026-07-04",  # Independence Day
    "2026-11-26",  # Thanksgiving
    "2026-12-25",  # Christmas
    # Update annually
}

# Option 2: Use `holidays` library (add to requirements.txt)
# pip install holidays
import holidays
us_holidays = holidays.US(state="IL")
```

### 2.4 — Deliverables Checklist

- [ ] `TimePeriod`, `DayType` enums and `TIME_PERIOD_CONFIG` in `backend/crowdedness.py`
- [ ] `classify_time_period()` function in `backend/crowdedness.py`
- [ ] Edge cases tested: boundary times, holidays, weekend off-peak

---

# WP-3: Crowdedness Estimation

## Objective
Estimate crowdedness/fullness of CTA buses and trains based on:
- Time period (from WP-2)
- Route
- Direction of travel
- Position along route
- Known high-traffic stops

## Existing Data Sources

### CTA Bus Tracker `psgld` field (already integrated)
- **Status:** Field is already retrieved and normalized in `cta_client.py` to `EMPTY | HALF_EMPTY | FULL`
- **Problem:** As of 2026-04-09, CTA's API returns empty strings for `psgld` on all bus arrivals
- **Action:** The heuristic estimation below provides a fallback when `psgld` is empty. When/if CTA fixes their API, the live value should take priority over the heuristic.

### CTA GTFS Static Feed (already downloaded)
- **Location:** `backend/gtfs_data/` — already present, do NOT re-download
- **Key files already parsed by transit_graph.py:** `routes.txt`, `stops.txt`, `stop_times.txt`, `trips.txt`
- **Existing helpers:** `get_bus_stop_sequences()` in `transit_graph.py` already returns stop sequences per route/direction — use this instead of building a new GTFS parser.

## Implementation Requirements

### 3.1 — Crowdedness Score Model

Add to `backend/crowdedness.py`:

```python
from pydantic import BaseModel
from enum import Enum

class CrowdednessLevel(str, Enum):
    LOW = "low"              # 0.0 - 0.3: Likely seats available
    MODERATE = "moderate"    # 0.3 - 0.6: Standing room expected
    HIGH = "high"            # 0.6 - 0.8: Crowded
    VERY_HIGH = "very_high"  # 0.8 - 1.0: Very crowded

class CrowdednessEstimate(BaseModel):
    score: float  # 0.0 to 1.0
    level: CrowdednessLevel
    confidence: str  # "low", "medium", "high"
    factors: dict  # Explainability: what contributed to this score
```

### 3.2 — Estimation Logic

```python
def estimate_crowdedness(
    route_id: str,
    direction: str,  # "inbound" or "outbound" (see mapping note below)
    stop_id: str,
    stop_sequence_position: int,
    total_stops: int,
    time_period: TimePeriod,
    day_type: DayType,
    live_psgld: str = ""  # Pass through from cta_client if available
) -> CrowdednessEstimate:
    """
    Estimates crowdedness based on heuristics.
    If live_psgld is non-empty (EMPTY/HALF_EMPTY/FULL), use it directly
    with HIGH confidence instead of the heuristic.
    
    Heuristic factors:
    1. Base score from time period
    2. Direction multiplier (inbound busier AM peak, outbound busier PM peak)
    3. Stop position curve (mid-route typically most crowded)
    4. High-traffic stop bonus
    """
    ...
```

**Direction mapping required:** The Bus Tracker API returns `rtdir` as `"Northbound"`, `"Southbound"`, `"Eastbound"`, or `"Westbound"` (see `cta_client.py`). `get_bus_stop_sequences()` keys on GTFS `direction_id` which is `"0"` or `"1"`. Neither maps directly to "inbound/outbound". You will need a mapping step — "inbound" conventionally means toward the Loop (generally southbound/eastbound on most CTA routes). Implement this as a helper dict or function keyed on `(route_short_name, rtdir)` rather than assuming a universal rule, since some routes run east–west and the convention breaks down.

### 3.3 — Heuristic Components

**Base scores by time period:**
```python
BASE_SCORES = {
    TimePeriod.PEAK: 0.75,
    TimePeriod.REGULAR: 0.45,
    TimePeriod.OFF_PEAK: 0.20
}
```

**Direction multiplier:**

Note: `TimePeriod.PEAK` covers both AM (06:30–09:30) and PM (15:30–18:30). To distinguish them, pass the current hour as a parameter — the `TimePeriod` enum alone is not sufficient.

```python
def direction_multiplier(direction: str, time_period: TimePeriod, current_hour: int) -> float:
    """
    AM peak: inbound (toward Loop) is busier
    PM peak: outbound (away from Loop) is busier
    """
    if time_period != TimePeriod.PEAK:
        return 1.0
    
    is_am_peak = current_hour < 12
    # Morning peak inbound = 1.2, outbound = 0.8
    # Evening peak inbound = 0.8, outbound = 1.2
    if is_am_peak:
        return 1.2 if direction == "inbound" else 0.8
    else:
        return 0.8 if direction == "inbound" else 1.2
```

**Stop position curve:**
```python
def stop_position_factor(position: int, total: int) -> float:
    """
    Bell curve: middle of route is typically most crowded.
    First and last stops are least crowded.
    """
    normalized = position / total  # 0.0 to 1.0
    # Peak around 0.4-0.6 of the route
    return 0.6 + 0.4 * math.sin(normalized * math.pi)
```

**High-traffic stops:**

Train stations use `mapid` (40000–49999 range); bus stops use GTFS `stop_id` (0–29999 range). Keep them in separate dicts to avoid confusion:

```python
# Verify all IDs against backend/gtfs_data/stops.txt before hardcoding
HIGH_TRAFFIC_TRAIN_STATIONS: dict[str, float] = {
    # mapid (40000-49999) → multiplier
    # "40380": 1.3,  # Clark/Lake — VERIFY against stops.txt
    # "40260": 1.3,  # State/Lake — VERIFY against stops.txt
    # Add more after checking actual mapids in gtfs_data/
}

HIGH_TRAFFIC_BUS_STOPS: dict[str, float] = {
    # stop_id (0-29999) → multiplier
    # Add based on CTA knowledge + stops.txt
}
```

**Do not trust mapids from memory** — verify all IDs by checking `backend/gtfs_data/stops.txt` directly before populating these dicts. A wrong ID silently has no effect.

### 3.4 — Deliverables Checklist

- [ ] `backend/crowdedness.py` — all enums, models, and estimation logic (WP-2 + WP-3 co-located)
- [ ] `HIGH_TRAFFIC_TRAIN_STATIONS` + `HIGH_TRAFFIC_BUS_STOPS` dicts in `backend/crowdedness.py` (verified against `gtfs_data/stops.txt`)
- [ ] Live `psgld` passthrough takes priority over heuristic when non-empty
- [ ] Integration: call `estimate_crowdedness()` per route leg in `main.py`; attach results to ranked tuples so `_format_routes()` can include them inline

---

# WP-4: Weather-Adjusted Route Scoring

## Objective
Augment the existing route ranking system with weather and crowdedness context. The primary mechanism is enriching the **Claude prompt** — Claude already generates the final user-facing recommendation and handles nuanced trade-offs well. A lightweight numeric scoring layer can supplement this for ordering route cards in the UI.

## Integration Point: Existing `_rank_routes()` in main.py

**Do not replace** `_rank_routes()`. It currently ranks routes by `total_minutes_no_wait + wait_time`. The weather-adjusted scoring should be an additive step that can optionally reorder routes after the existing time-based ranking, and always feeds into the Claude prompt.

## Dependencies
- WP-1 (`WeatherContext`)
- WP-3 (`CrowdednessEstimate`)

## Implementation Requirements

### 4.1 — Scoring Weight Configuration

Add to `backend/weather_service.py` or a new `backend/route_scoring.py`:

```python
DEFAULT_WEIGHTS = {
    "travel_time": 0.35,
    "outdoor_exposure": 0.25,
    "crowdedness": 0.20,
    "reliability": 0.15,
    "transfers": 0.05
}
```

### 4.2 — Weather-Based Weight Adjustment

```python
def adjust_weights_for_weather(
    base_weights: dict,
    weather: WeatherContext
) -> dict:
    """
    Dynamically adjusts scoring weights based on weather.
    
    Examples:
    - Heavy precipitation → increase outdoor_exposure weight
    - Extreme cold → increase outdoor_exposure weight
    - High wind + elevated trains → factor into reliability
    - Mild weather → default weights
    """
    adjusted = base_weights.copy()
    
    # Precipitation adjustment
    if weather.current.precipitation.type != PrecipitationType.NONE:
        if weather.current.precipitation.intensity == "heavy":
            adjusted["outdoor_exposure"] += 0.15
            adjusted["travel_time"] -= 0.10
    
    # Temperature adjustment (check coldest threshold first — order matters)
    if weather.current.feels_like_f < 0:  # Dangerously cold
        adjusted["outdoor_exposure"] += 0.20
        adjusted["travel_time"] -= 0.10
    elif weather.current.feels_like_f < 15:  # Very cold
        adjusted["outdoor_exposure"] += 0.10
        adjusted["travel_time"] -= 0.05
    
    # Wind adjustment for elevated trains
    if weather.current.wind.gusts_mph and weather.current.wind.gusts_mph > 35:
        adjusted["reliability"] += 0.05
    
    # Normalize weights to sum to 1.0
    total = sum(adjusted.values())
    return {k: v / total for k, v in adjusted.items()}
```

### 4.3 — Claude Prompt Integration (Primary Integration)

The most impactful change is adding weather context to `build_prompt()` in `main.py`. Claude already does the nuanced recommendation — giving it weather data allows it to naturally say things like "given the freezing temperatures, the Red Line is preferable to the 22 Clark bus since you'll spend less time waiting outside."

```python
def build_prompt(
    origin: str,
    destination: str,
    train_arrivals: list[dict],
    bus_arrivals: list[dict],
    transit_mode: str = "All",
    ranked_routes: list[tuple] | None = None,
    bus_fullness: str = "All",
    weather: WeatherContext | None = None,          # NEW
) -> str:
    ...
    # Add weather context (keep concise — one line is enough for Claude)
    if weather:
        wind_note = ""
        if weather.current.wind.gusts_mph and weather.current.wind.gusts_mph > 25:
            wind_note = f", wind gusts {weather.current.wind.gusts_mph:.0f} mph"
        sections.append(
            f"Current weather: {weather.current.condition}, "
            f"{weather.current.temp_f:.0f}°F (feels like {weather.current.feels_like_f:.0f}°F), "
            f"precipitation: {weather.current.precipitation.type.value}"
            + (f" ({weather.current.precipitation.intensity})" if weather.current.precipitation.intensity else "")
            + wind_note
        )
        if weather.alerts:
            sections.append("Weather alerts: " + "; ".join(weather.alerts))
    ...
```

**Crowdedness in prompt:** Do not add a separate `crowdedness_by_route` parameter to `build_prompt()`. Instead, extend `_format_routes()` in `main.py` to include crowdedness info inline with each route option — e.g. appending `[est. crowdedness: moderate]` to each option line. This keeps the information co-located with the route it describes, making it easier for Claude to reason about trade-offs. The ranked tuples `(total, wait, route)` can be extended to `(total, wait, route, crowdedness)` to carry this data through.

### 4.4 — Outdoor Exposure Estimation

To score `outdoor_exposure`, use the existing `Route.walk_minutes_total` attribute from the `Route` dataclass in `transit_graph.py` (line 102) — it already sums all walk legs. No new helper function is needed:

```python
# The Route dataclass already has this:
#   walk_minutes_total: float = 0.0  # sum of all walk legs
# So in scoring code, just use:
outdoor = route.walk_minutes_total
```

### 4.5 — Deliverables Checklist

- [ ] `adjust_weights_for_weather()` in `backend/route_scoring.py` (or `backend/weather_service.py`)
- [ ] Outdoor exposure scoring uses existing `Route.walk_minutes_total` — no new helper needed
- [ ] `build_prompt()` in `backend/main.py` — add `weather` param; extend `_format_routes()` to include crowdedness inline per route option
- [ ] Weather context section added to prompt string (include wind when gusty)
- [ ] Optional: lightweight numeric re-ranking of `ranked_routes` after weather adjustment (secondary to Claude prompt enrichment)

---

# Integration Notes

## Actual File Structure (flat backend/)

```
backend/
├── main.py                  # Existing — add weather/crowdedness calls here
├── cta_client.py            # Existing — psgld already retrieved
├── transit_graph.py         # Existing — get_bus_stop_sequences() usable for WP-3
├── gtfs_loader.py           # Existing — GTFS already parsed
├── walking.py               # Existing — walk_minutes(), walk_path(), walk_directions()
├── weather_service.py       # NEW (WP-1) — WeatherContext models + WeatherService
├── crowdedness.py           # NEW (WP-2 + WP-3) — TimePeriod + CrowdednessEstimate
├── route_scoring.py         # NEW (WP-4, optional) — weight adjustment logic
├── gtfs_data/               # Existing — do not re-download
└── requirements.txt         # Add: aiohttp already present; add `cachetools` (WP-1) and `holidays` (WP-2 Option 2) if used
```

## Execution Order

1. **WP-1** and **WP-2** can be done in parallel (no dependencies)
2. **WP-3** requires WP-2 to be complete
3. **WP-4** requires WP-1 and WP-3 to be complete

## Key Constraints

- **`stop_times.txt` is 5.8 M rows / 354 MB** — already streamed at startup in `transit_graph.py`. Never load it into a new dataframe or list in WP-3. Use `get_bus_stop_sequences()` from `transit_graph.py` instead.
- **Backend coord convention:** `[lat, lon]` throughout Python. MapLibre/GeoJSON swaps to `[lon, lat]` in `MapView.jsx` via the `toGeo` helper — do not change this.
- **Cost awareness:** Always confirm with user before adding new Anthropic API calls during development. The existing `/recommend` call costs money; weather context adds input token length. Keep weather summary concise in the prompt (one line is enough for Claude to act on it).
- **`max_tokens=400` and Claude instruction:** The response token cap is already set to 400 in `main.py`. The current end-of-prompt instruction says "Keep it to 3-4 sentences." When weather context is added, update this instruction to tell Claude to incorporate weather naturally within those same 3-4 sentences — not as a separate paragraph — so the response length doesn't creep up.
- **Rate limiting still absent:** `/recommend` has no rate limiting as of deployment. This is a known issue — add it before or shortly after public launch regardless of weather feature status.

## Testing Strategy

Each work package should include:
- Unit tests with mocked external dependencies
- Edge case coverage (NWS API down, psgld empty string, freezing rain vs snow classification)
- Integration test stubs for when packages are combined

---

# Summary

| WP | New File | Key Outcome |
|----|----------|-------------|
| WP-1 | `backend/weather_service.py` | `WeatherContext` injected into Claude prompt |
| WP-2 | `backend/crowdedness.py` | `classify_time_period()` returns TimePeriod + DayType |
| WP-3 | `backend/crowdedness.py` | `estimate_crowdedness()` returns CrowdednessEstimate; uses live `psgld` when available |
| WP-4 | `backend/route_scoring.py` | Weather-adjusted weights + enriched `build_prompt()` in `main.py` |

**Reminder:** This feature is post-Phase-6. Complete Railway + Vercel deployment first.

---

*End of handoff document.*
