# Data Retrievable from NWS (Weather.gov) API

The NWS API provides free, open data with no API key required (but a User-Agent header is mandatory, including contact info).

## Main Endpoints

- `/points/{lat},{lon}` — Returns grid point coordinates (x,y) and forecast office for a location. Used to get URLs for other endpoints.
- `/gridpoints/{wfo}/{x},{y}/forecast` — 12-hour forecast periods (e.g., day/night summaries).
- `/gridpoints/{wfo}/{x},{y}/forecast/hourly` — Hourly forecast data (up to ~156 hours ahead).
- `/alerts/active?point={lat},{lon}` — Active weather alerts (e.g., severe weather warnings) for a point.
- `/stations/{stationId}/observations/latest` — Latest current conditions from a weather station (requires finding nearest station via `/stations` or `/points`).

## Data Types in Hourly Forecast (`/forecast/hourly`)

- Temperature (°F)
- Dewpoint (°F)
- Wind speed/direction (mph/degrees)
- Precipitation probability/type/amount (inches)
- Relative humidity (%)
- Short/detailed forecast descriptions
- Feels-like temperature (not directly provided; must derive from wind chill/heat index formulas)

## Data Types in Current Observations (`/observations/latest`)

- Temperature, dewpoint, wind speed/direction
- Visibility (miles)
- Relative humidity (%)
- Barometric pressure
- Precipitation (last hour/3 hours)

## Geographical Granularity

- **Forecasts:** Grid-based (~2.5 km resolution in the US; denser in populated areas like Chicago).
- **Observations:** Station-based (specific weather stations; nearest to lat/lon query).
- **Alerts:** Zone-based (covers areas like counties or cities).

## Limitations

- No dedicated "current conditions" endpoint; use first hourly period or latest observation.
- Rate limits exist (not publicly specified, but generous for typical use; retries after ~5 seconds if exceeded).
- Data updates vary (forecasts every 1–6 hours; observations real-time from stations).
