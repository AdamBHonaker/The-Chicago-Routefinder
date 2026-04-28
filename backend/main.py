import asyncio
import collections
import os
import time
import traceback
from contextlib import asynccontextmanager
from datetime import datetime

import aiohttp

from fastapi import FastAPI, HTTPException, Request, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from dotenv import load_dotenv
import anthropic


# load_dotenv() must be called before importing local modules.
# gtfs_loader.py reads GOOGLE_MAPS_API_KEY at module level (import time),
# so the .env file must be loaded into os.environ first.
load_dotenv()

import dau

from gtfs_loader import (
    resolve_location, geocode_google, NEIGHBORHOOD_COORDS,
    fuzzy_match_neighborhood, _normalize_street_abbr, _load_stops,
)
from cta_client import get_train_arrivals, get_bus_arrivals, get_alerts, get_route_statuses, _TRAIN_LINE_TO_ALERT_ID, LINE_NAMES, init_session as _init_cta_session, close_session as _close_cta_session
from transit_graph import (
    find_routes, find_bus_transfer_routes, warm_up, get_bus_stop_sequences,
    WalkLeg, TransitLeg, Route, get_station_coords, get_station_by_name,
    get_last_departure,
)
from walking import (
    walk_minutes as _walk_minutes,
    walk_directions as _walk_directions,
    walk_path as _walk_path,
)
from weather_service import WeatherService, WeatherContext, PrecipitationType
from route_scoring import weight_hint_for_weather
from crowdedness import (
    classify_time_period, estimate_crowdedness, rtdir_to_inbound_outbound,
    CrowdednessLevel, CROWDEDNESS_LEVEL_ORDER,
)
from utils import CHICAGO_TZ as _CHICAGO_TZ

# Anthropic client — created once at startup, reused across all requests
_claude_client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))

# Weather service — module-level singleton, manages its own TTL caches internally
weather_service = WeatherService()

# ---------------------------------------------------------------------------
# Response cache
# ---------------------------------------------------------------------------
# key → (expires_at: float via time.monotonic(), response: dict)
# OrderedDict preserves insertion order so eviction of the oldest entry is O(1)
# via popitem(last=False) rather than O(n) via min() over all entries.
_response_cache: collections.OrderedDict[str, tuple[float, dict]] = collections.OrderedDict()
_CACHE_TTL_SECONDS = 120      # seconds
_CACHE_MAX_SIZE    = 500      # entries

# Cache hit/miss counters — logged every _CACHE_LOG_INTERVAL requests for tuning.
_cache_hits:   int = 0
_cache_misses: int = 0
_cache_requests_total: int = 0
_CACHE_LOG_INTERVAL = 100

# Squared degree threshold for treating origin == destination (≈0.07 miles at Chicago's latitude).
_SAME_LOCATION_THRESHOLD_DEG2: float = 0.001 ** 2   # degrees²

# ---------------------------------------------------------------------------
# /stop-arrivals cache (Feature Pinned Stops + Feature Last Train)
# ---------------------------------------------------------------------------
_STOP_ARRIVALS_TTL = 30   # seconds
_stop_arrivals_cache: collections.OrderedDict[str, tuple[float, dict]] = collections.OrderedDict()


def _cache_key(origin: str, destination: str, transit_mode: str, bus_fullness: str,
               byok: bool = False, ai_enabled: bool = False, language: str = "en",
               walk_speed: float = 1.0) -> str:
    # Include a BYOK flag so BYOK and shared-quota requests never share cache
    # entries — a non-BYOK user would otherwise be served a response whose
    # Claude call was paid for by a BYOK user (and vice-versa).
    # Include ai_enabled because the recommendation field differs between AI-on and AI-off responses.
    # Include language so responses in different languages are cached separately.
    # Include walk_speed so different pace preferences are cached separately.
    return "|".join([
        origin.lower().strip(),
        destination.lower().strip(),
        transit_mode,
        bus_fullness,
        "byok" if byok else "",
        "ai" if ai_enabled else "",
        language or "en",
        str(walk_speed),
    ])

# ---------------------------------------------------------------------------
# Rate limiting (disabled by default — set RATE_LIMIT_ENABLED=true to activate)
# ---------------------------------------------------------------------------
# To enable: add RATE_LIMIT_ENABLED=true to backend/.env (or Railway env vars).
# Tune the caps with RATE_LIMIT_RPM (per minute) and RATE_LIMIT_RPH (per hour).
# Both limits must pass on every request — the stricter one wins.
# BYOK requests count against per-IP limits just like shared-quota requests.
_RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "false").lower() == "true"
_RATE_LIMIT_RPM     = int(os.getenv("RATE_LIMIT_RPM", "10"))   # max requests per minute per IP
_RATE_LIMIT_RPH     = int(os.getenv("RATE_LIMIT_RPH", "50"))   # max requests per hour per IP

# Shared lock protecting both _rate_store and _response_cache.
# asyncio.Lock() is correct here (not threading.Lock) because recommend() is an
# async def that awaits between the cache read and cache write — the await yields
# control to the event loop, allowing a second coroutine to observe a stale miss
# and launch a duplicate expensive request, or to interleave partial reads/writes.
# Holding the lock around the check+read and again around the write eliminates
# both the duplicate-computation stampede and the eviction double-pop.
_store_lock = asyncio.Lock()

# ip → deque of monotonic timestamps for this IP's recent requests
_rate_store: dict[str, collections.deque] = {}


def _client_ip(http_request: Request) -> str:
    """Extract client IP, using Railway's trusted proxy headers to prevent spoofing.

    Clients can freely forge any entries at the start of X-Forwarded-For. Railway's
    load balancer appends the actual connection IP at the end of the chain, so reading
    the last entry gives the IP Railway observed — which a client cannot forge.
    X-Real-IP (if present) is preferred as it is set exclusively by the Railway LB.
    """
    real_ip = http_request.headers.get("x-real-ip", "").strip()
    if real_ip:
        return real_ip
    forwarded = http_request.headers.get("x-forwarded-for", "")
    if forwarded:
        # Use the last (rightmost) entry — appended by Railway's LB, not client-supplied
        return forwarded.split(",")[-1].strip()
    return http_request.client.host if http_request.client else "unknown"


def _check_rate_limit(ip: str) -> bool:
    """
    Return True (request allowed) or False (rate-limited).
    Always returns True when _RATE_LIMIT_ENABLED is False.

    Sliding-window approach: per-minute AND per-hour caps must both pass.
    Callers must hold _store_lock before calling this function.
    """
    if not _RATE_LIMIT_ENABLED:
        return True
    now = time.monotonic()
    window = _rate_store.setdefault(ip, collections.deque())
    # Evict timestamps older than one hour to bound memory growth
    while window and now - window[0] > 3600:
        window.popleft()
    # Per-hour check
    if len(window) >= _RATE_LIMIT_RPH:
        return False
    # Per-minute check — iterate from the right (newest entries) and stop as
    # soon as we exceed the 60-second window. Because the deque is insertion-
    # ordered (ascending), the rightmost entry is always the most recent, so
    # we stop early as soon as we hit a timestamp older than 60 s instead of
    # scanning all hourly entries.
    recent = 0
    for t in reversed(window):
        if now - t <= 60:
            recent += 1
        else:
            break
    if recent >= _RATE_LIMIT_RPM:
        return False
    window.append(now)
    return True


# ---------------------------------------------------------------------------
# BYOK — Bring Your Own API Key (disabled by default — set BYOK_ENABLED=true)
# ---------------------------------------------------------------------------
# To enable: add BYOK_ENABLED=true to backend/.env (or Railway env vars), then
# also set VITE_BYOK_ENABLED=true in frontend/.env so the settings panel appears.
# Users who supply their own Anthropic API key bypass the app's shared Claude
# quota; their usage is billed to their own account. Per-IP rate limits still
# apply (same _check_rate_limit call as shared-quota requests).
_BYOK_ENABLED = os.getenv("BYOK_ENABLED", "false").lower() == "true"

# Bus Tracker fullness field values → normalized psgld value mapping.
# psgld is normalized in cta_client.py (_fetch_bus_chunk) to UPPER_SNAKE before
# storage, so these values must also be UPPER_SNAKE regardless of what the API sends.
_FULLNESS_API_VALUES = {
    "Empty":     "EMPTY",
    "Half-Full": "HALF_EMPTY",
    "Full":      "FULL",
}

# CORS origins — always allow localhost for local dev.
# Set ALLOWED_ORIGINS in Railway env vars to your Vercel URL, e.g.:
#   ALLOWED_ORIGINS=https://cta-transit.vercel.app
_extra_origins = os.getenv("ALLOWED_ORIGINS", "")
ALLOWED_ORIGINS = ["http://localhost:5173"] + [
    o.strip() for o in _extra_origins.split(",") if o.strip()
]


# ---------------------------------------------------------------------------
# Autocomplete index — built once at startup from GTFS + neighborhood data
# ---------------------------------------------------------------------------
_ac_train_names: list[str] = []   # train parent-station display names
_ac_neighborhood_names: list[str] = []  # title-cased neighborhood/landmark names
_ac_bus_names: list[str] = []     # deduplicated bus stop display names
# Master list of all suggestion dicts — each entry stored exactly once.
_ac_master: list[dict] = []
# Inverted prefix index: 2- and 3-char lowercase prefixes → [(tier, score, idx)]
# idx is an integer index into _ac_master; avoids storing duplicate dict refs.
# score 0 = full-name prefix (first word), score 1 = inner-word prefix
_ac_prefix_index: dict[str, list[tuple[int, int, int]]] = {}


def _build_autocomplete_index() -> None:
    global _ac_train_names, _ac_neighborhood_names, _ac_bus_names
    global _ac_master, _ac_prefix_index
    train_stations, bus_stops = _load_stops()
    _ac_train_names = [s["name"] for s in train_stations]
    _ac_neighborhood_names = [name.title() for name in NEIGHBORHOOD_COORDS.keys()]
    seen: set[str] = set()
    bus_names: list[str] = []
    for s in bus_stops:
        nl = s["name"].lower()
        if nl not in seen:
            seen.add(nl)
            bus_names.append(s["name"])
    _ac_bus_names = bus_names

    master: list[dict] = []
    index: dict[str, list[tuple[int, int, int]]] = {}

    def _index_entry(name: str, tier: int, label_type: str) -> None:
        suggestion = {"label": name, "value": name, "type": label_type}
        idx = len(master)
        master.append(suggestion)
        nl = name.lower()
        added: set[str] = set()
        for i, word in enumerate(nl.split()):
            score = 0 if i == 0 else 1
            for length in (2, 3):
                if len(word) >= length:
                    key = word[:length]
                    if key not in added:
                        index.setdefault(key, []).append((tier, score, idx))
                        added.add(key)

    for name in _ac_train_names:
        _index_entry(name, 0, "train")
    for name in _ac_neighborhood_names:
        _index_entry(name, 1, "neighborhood")
    for name in _ac_bus_names:
        _index_entry(name, 2, "bus")

    _ac_master = master
    _ac_prefix_index = index
    print(
        f"[autocomplete] Index built: {len(_ac_train_names)} train stations, "
        f"{len(_ac_neighborhood_names)} neighborhoods, {len(_ac_bus_names)} bus stop names, "
        f"{len(index)} prefix keys, {len(master)} master entries"
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _init_cta_session()
    print("[main] Warming up transit graph ...")
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, warm_up)
    _build_autocomplete_index()
    print("[main] Ready.")
    yield
    await _close_cta_session()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)


_VALID_TRANSIT_MODES  = {"All", "Train", "Bus", "Walk"}
_VALID_BUS_FULLNESS   = {"All", "Empty", "Half-Full", "Full"}


class RouteRequest(BaseModel):
    origin: str
    destination: str
    transit_mode: str = "All"   # "All" | "Train" | "Bus" | "Walk"
    bus_fullness: str = "All"   # "All" | "Empty" | "Half-Full" | "Full"
    # BYOK — only honoured when BYOK_ENABLED=true in backend/.env.
    # When BYOK is disabled, this field is accepted but silently ignored so the
    # frontend does not need to know whether BYOK is active on the server.
    anthropic_api_key: str | None = None
    # AI toggle — when False (default), the Claude call is skipped entirely.
    # response.recommendation will be null. Future paywall gate lives here.
    ai_enabled: bool = False
    # BCP-47 language code (e.g. "es", "ar", "ja"). When non-null and not "en",
    # build_prompt() appends a language instruction so Claude responds in that language.
    language: str | None = None
    # Walking pace multiplier. 1.0 = standard (~15 min/mile). Applied as:
    #   adjusted_minutes = baseline_minutes / walk_speed
    # Slow: 0.75 (33% longer), Standard: 1.0 (no-op), Brisk: 1.25 (20% shorter).
    walk_speed: float = Field(default=1.0, ge=0.5, le=2.0)

    @field_validator("transit_mode")
    @classmethod
    def validate_transit_mode(cls, v: str) -> str:
        if v not in _VALID_TRANSIT_MODES:
            raise ValueError(f"transit_mode must be one of {sorted(_VALID_TRANSIT_MODES)}")
        return v

    @field_validator("bus_fullness")
    @classmethod
    def validate_bus_fullness(cls, v: str) -> str:
        if v not in _VALID_BUS_FULLNESS:
            raise ValueError(f"bus_fullness must be one of {sorted(_VALID_BUS_FULLNESS)}")
        return v

    @field_validator("anthropic_api_key")
    @classmethod
    def validate_anthropic_key(cls, v: str | None) -> str | None:
        # Only strip/nullify here — format validation happens in _validate_api_keys
        # after the BYOK_ENABLED guard, so invalid strings are silently ignored
        # when BYOK is disabled rather than returning HTTP 422.
        if v is not None:
            v = v.strip()
            if not v:
                return None
        return v


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _coords_for_location(
    query: str,
    stations: list[dict] | None = None,
) -> tuple[float, float] | None:
    """
    Return (lat, lon) for a location query using the same 3-step resolution
    as resolve_location(): exact dict match → fuzzy match (0.95) → Nominatim.
    If all three fail and nearby stations were already resolved, returns their
    centroid as a last resort so the routing engine always has coordinates.
    """
    q = query.lower().strip()
    q = _normalize_street_abbr(q)

    # 1. Exact match
    coords = NEIGHBORHOOD_COORDS.get(q)
    if coords:
        return coords

    # 2. Fuzzy match — delegate to shared helper in gtfs_loader so the
    #    threshold (0.95) and stop-word list stay in sync with resolve_location.
    coords, _ = fuzzy_match_neighborhood(q)
    if coords:
        return coords

    # 3. Google Maps geocoding (result is cached after resolve_location already called it)
    coords = geocode_google(q)
    if coords:
        return coords

    # 4. Centroid of already-resolved nearby stations as last resort
    if stations:
        lats = [s["lat"] for s in stations]
        lons = [s["lon"] for s in stations]
        return (sum(lats) / len(lats), sum(lons) / len(lons))

    return None


def _build_arrival_lookup(
    train_arrivals: list[dict],
    bus_arrivals: list[dict] | None = None,
    bus_stop_walk_map: dict[str, float] | None = None,
) -> dict[tuple[str, str], dict[str, int]]:
    """
    (line_code, station_mapid) -> {destNm: earliest_catchable_minutes}

    Groups arrivals by destination so _rank_routes can select the one going in
    the correct direction.  Arrivals where arrives_in_minutes < walk_minutes
    are skipped — the user cannot reach the stop in time.

    For trains: keyed by (line_code, station_mapid).
    For buses:  keyed by (route, stop_id) — bus_stop_walk_map provides the
    walk time to each stop so uncatchable buses are filtered the same way.
    """
    lookup: dict[tuple[str, str], dict[str, int]] = {}
    for a in train_arrivals:
        key = (a.get("line_code", ""), a.get("station_mapid", ""))
        dest = a.get("destination", "")
        minutes = a["arrives_in_minutes"]
        walk = a.get("walk_minutes", 0)
        if minutes < walk:
            continue
        dests = lookup.setdefault(key, {})
        if dest not in dests or minutes < dests[dest]:
            dests[dest] = minutes
    if bus_arrivals and bus_stop_walk_map is not None:
        for a in bus_arrivals:
            stop_id = a.get("stop_id", "")
            route   = a.get("route", "")
            if not stop_id or not route:
                continue
            key = (route, stop_id)
            dest = a.get("destination", "")
            minutes = a["arrives_in_minutes"]
            walk = bus_stop_walk_map.get(stop_id, 0.0)
            if minutes < walk:
                continue
            dests = lookup.setdefault(key, {})
            if dest not in dests or minutes < dests[dest]:
                dests[dest] = minutes
    return lookup


def _pick_wait(
    dest_map: dict[str, int],
    from_mapid: str,
    to_mapid: str,
) -> int | None:
    """
    Pick live wait minutes from a destination→minutes map using a dot-product
    bearing test to resolve multi-direction stations. Returns None when
    dest_map is empty (no live data).

    When multiple arrival directions exist (e.g. Howard vs 95th/Dan Ryan on
    the Red Line), selects the terminal whose vector from the boarding station
    is most aligned with the boarding→exit vector. Falls back to earliest
    arrival if coordinates are unavailable.
    """
    if not dest_map:
        return None
    if len(dest_map) == 1:
        return next(iter(dest_map.values()))
    from_coords = get_station_coords(from_mapid)
    to_coords   = get_station_coords(to_mapid)
    if not from_coords or not to_coords:
        return min(dest_map.values())
    dlat = to_coords[0] - from_coords[0]
    dlon = to_coords[1] - from_coords[1]
    if dlat == 0.0 and dlon == 0.0:
        return min(dest_map.values())
    best_score = float("-inf")
    best_wait: int | None = None
    for dest_name, minutes in dest_map.items():
        term = get_station_by_name(dest_name)
        if term is None:
            continue
        tlat = term[0] - from_coords[0]
        tlon = term[1] - from_coords[1]
        score = dlat * tlat + dlon * tlon
        if score > best_score:
            best_score = score
            best_wait  = minutes
    return best_wait if best_wait is not None else min(dest_map.values())


def _rank_routes(
    routes: list,
    arrival_lookup: dict[tuple[str, str], dict[str, int]],
) -> list[tuple[float, int, object]]:
    """
    Add live wait time to each route and sort by total (walk + wait + transit).
    Returns list of (total_with_wait, wait_minutes, route).
    Bearing-based direction selection is delegated to _pick_wait().

    wait (arrives_in_minutes) is the time from NOW until the train arrives.
    The station wait is (wait - first_walk), so total = arrives_in_minutes +
    transit + other_walks — the first walk is not double-counted.
    """
    ranked = []
    for route in routes:
        first_transit = (
            route.legs[route.first_transit_leg_index]
            if route.first_transit_leg_index is not None
            else None
        )
        wait: int | None = None
        if first_transit:
            key = (first_transit.line_code, first_transit.from_mapid)
            dest_map = arrival_lookup.get(key, {})
            wait = _pick_wait(dest_map, first_transit.from_mapid, first_transit.to_mapid)
        if wait is not None:
            first_walk = next(
                (l.minutes for l in route.legs
                 if isinstance(l, WalkLeg) and l.from_name == "Your location"),
                0.0,
            )
            station_wait = max(0.0, wait - first_walk)
            total = route.total_minutes_no_wait + station_wait
        else:
            total = route.total_minutes_no_wait
        ranked.append((total, wait, route))
    ranked.sort(key=lambda x: x[0])
    return ranked


def _rank_bus_routes(
    bus_ranked: list[tuple],
) -> list[tuple[float, "int | None", object]]:
    """
    Normalise wait semantics for bus routes returned by
    find_bus_transfer_routes().

    find_bus_transfer_routes() computes the first-leg wait from live arrivals
    and stores it as a plain int (defaulting to 0 when no data). This function
    re-expresses the wait as int | None to match _rank_routes() output:
      - wait > 0  → keep as-is (bus is N minutes away)
      - wait == 0 → keep as 0 (bus is Due — not "no data"; bus routes are only
                    built when a live arrival exists, so 0 always means Due)
      - wait is None → keep as None (should not occur but handled defensively)

    The total is already correct (computed inside find_bus_transfer_routes as
    route.total_minutes_no_wait + wait_min). We return it unchanged.

    Returns list of (total, wait, route) with wait typed as int | None,
    re-sorted by total ascending.
    """
    result: list[tuple] = []
    for total, wait, route in bus_ranked:
        normalised_wait: "int | None" = int(wait) if wait is not None else None
        result.append((float(total), normalised_wait, route))
    result.sort(key=lambda x: x[0])
    return result


async def _empty() -> list:
    """Coroutine that immediately returns an empty list. Used as a no-op placeholder
    in asyncio.gather() when a transfer fetch is not needed."""
    return []


def _extract_transfer_stops(
    ranked_routes: list[tuple],
) -> tuple[list[dict], list[str]]:
    """
    Scan ranked_routes for transfer boarding legs (TransitLegs where an earlier
    leg in the same route is also a TransitLeg). Returns two deduped collections:
      - train_stations: [{mapid, name}] for train transfer stops
      - bus_stop_ids: [stop_id] for bus transfer stops
    """
    train_stops: dict[str, dict] = {}
    bus_stop_ids: list[str] = []
    bus_seen: set[str] = set()
    for _total, _wait, route in ranked_routes:
        seen_transit = False
        for leg in route.legs:
            if isinstance(leg, TransitLeg):
                if seen_transit:
                    if leg.line_code in LINE_NAMES:
                        if leg.from_mapid not in train_stops:
                            train_stops[leg.from_mapid] = {
                                "mapid": leg.from_mapid,
                                "name": leg.from_station,
                            }
                    else:
                        if leg.from_mapid not in bus_seen:
                            bus_seen.add(leg.from_mapid)
                            bus_stop_ids.append(leg.from_mapid)
                seen_transit = True
    return list(train_stops.values()), bus_stop_ids


def _build_bus_transfer_lookup(
    bus_arrivals: list[dict],
) -> dict[tuple[str, str], int]:
    """(route, stop_id) -> earliest arrival minutes for transfer bus stops."""
    lookup: dict[tuple[str, str], int] = {}
    for a in bus_arrivals:
        key = (a.get("route", ""), a.get("stop_id", ""))
        minutes = a["arrives_in_minutes"]
        if key not in lookup or minutes < lookup[key]:
            lookup[key] = minutes
    return lookup


def _format_transfer_arrivals(arrivals: list[dict]) -> str:
    """Format combined train+bus transfer arrivals grouped by stop/station name."""
    groups: dict[str, list[dict]] = {}
    for a in arrivals:
        stop = a.get("station") or a.get("stop_name", "Unknown stop")
        groups.setdefault(stop, []).append(a)
    lines = []
    for stop, stop_arrivals in groups.items():
        lines.append(f"{stop}:")
        for a in sorted(stop_arrivals, key=lambda x: x["arrives_in_minutes"])[:3]:
            route_label = a.get("line_code") or a.get("route", "?")
            dest = a.get("destination", "")
            mins = a["arrives_in_minutes"]
            due_str = "Due" if mins == 0 else f"{mins} min"
            lines.append(f"  {route_label} \u2192 {dest}: {due_str}")
    return "\n".join(lines)


def _is_simple_query(ranked_routes: list[tuple]) -> bool:
    """
    A query is 'simple' if there is exactly one ranked route and that route
    contains at most one TransitLeg (walk-only or direct ride, no transfer).
    Walk legs are not counted. Simple queries are routed to Haiku for cost
    savings; all others use Sonnet.
    """
    if len(ranked_routes) != 1:
        return False
    _, _, route = ranked_routes[0]
    transit_legs = [leg for leg in route.legs if isinstance(leg, TransitLeg)]
    return len(transit_legs) <= 1


def _alert_ids_from_routes(ranked_routes: list[tuple]) -> list[str]:
    """Return deduplicated Alerts API route ids for all transit legs in ranked_routes."""
    seen: set[str] = set()
    ids: list[str] = []
    for _total, _wait, route in ranked_routes:
        for leg in route.legs:
            if not isinstance(leg, TransitLeg):
                continue
            code = leg.line_code or ""
            alert_id = _TRAIN_LINE_TO_ALERT_ID.get(code, code)
            if alert_id and alert_id not in seen:
                seen.add(alert_id)
                ids.append(alert_id)
    return ids


# ---------------------------------------------------------------------------
# recommend() sub-steps — each handles one distinct concern
# ---------------------------------------------------------------------------

def _validate_api_keys(request: RouteRequest, byok_key: str | None) -> None:
    """Raise HTTPException if any required API key is absent."""
    train_key     = os.getenv("CTA_TRAIN_API_KEY", "")
    bus_key       = os.getenv("CTA_BUS_API_KEY", "")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not train_key and request.transit_mode != "Walk":
        raise HTTPException(status_code=500, detail="CTA_TRAIN_API_KEY not configured in backend/.env")
    if byok_key and not byok_key.startswith("sk-ant-"):
        raise HTTPException(status_code=422, detail="anthropic_api_key does not look like a valid Anthropic API key")
    if request.ai_enabled and not byok_key and (not anthropic_key or anthropic_key == "your_api_key_here"):
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured in backend/.env")
    if request.transit_mode in ("Bus", "All") and not bus_key:
        raise HTTPException(status_code=500, detail="CTA_BUS_API_KEY not configured in backend/.env")


async def _resolve_locations(
    loop: asyncio.AbstractEventLoop,
    request: RouteRequest,
) -> tuple:
    """Resolve origin and destination to stations, bus stops, and coordinates.

    Returns (origin_stations, origin_bus_stops, dest_stations, dest_bus_stops,
             dest_match, origin_coords, dest_coords).
    Raises HTTPException(400) if either location is unresolvable or they are
    the same location.
    """
    origin_stations, origin_bus_stops, _ = await loop.run_in_executor(
        None, resolve_location, request.origin
    )
    if not origin_stations and not origin_bus_stops:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Could not find CTA stops near '{request.origin}'. "
                "Try a neighborhood name like 'Wrigleyville', 'Lincoln Park', or 'River North'."
            ),
        )

    dest_stations, dest_bus_stops, dest_match = await loop.run_in_executor(
        None, resolve_location, request.destination
    )
    if not dest_stations and not dest_bus_stops:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Could not find CTA stops near '{request.destination}'. "
                "We currently cover the area from Howard St to 50th St, "
                "Lakefront to Pulaski Rd. Your destination may be outside our coverage area."
            ),
        )

    origin_coords, dest_coords = await asyncio.gather(
        loop.run_in_executor(None, _coords_for_location, request.origin, origin_stations),
        loop.run_in_executor(None, _coords_for_location, request.destination, dest_stations),
    )

    if origin_coords and dest_coords:
        dlat = origin_coords[0] - dest_coords[0]
        dlon = origin_coords[1] - dest_coords[1]
        if (dlat * dlat + dlon * dlon) < _SAME_LOCATION_THRESHOLD_DEG2:
            raise HTTPException(
                status_code=400,
                detail="Your origin and destination appear to be the same location.",
            )

    return (
        origin_stations, origin_bus_stops,
        dest_stations, dest_bus_stops, dest_match,
        origin_coords, dest_coords,
    )


async def _fetch_arrivals(
    request: RouteRequest,
    origin_stations: list[dict],
    origin_bus_stops: list[dict],
) -> tuple[list[dict], list[dict], int, int]:
    """Fetch train and bus live arrivals for the origin.

    Returns (train_arrivals, bus_arrivals, n_train_errors, n_bus_errors).
    """
    train_key   = os.getenv("CTA_TRAIN_API_KEY", "")
    bus_key     = os.getenv("CTA_BUS_API_KEY", "")
    # Pre-filter to the 3 closest stations by walk time to avoid extra CTA API calls.
    origin_stations = sorted(origin_stations, key=lambda s: s.get("walk_minutes", 0))[:3]
    walk_lookup = {s["mapid"]: s.get("walk_minutes", 0) for s in origin_stations}

    n_train_errors = 0
    if request.transit_mode == "Bus":
        train_arrivals: list[dict] = []
    else:
        train_arrivals, n_train_errors = await get_train_arrivals(origin_stations, train_key)
        for a in train_arrivals:
            a["walk_minutes"] = walk_lookup.get(a.get("station_mapid"), 0)

    bus_arrivals: list[dict] = []
    n_bus_errors = 0
    if request.transit_mode in ("Bus", "All") and bus_key and origin_bus_stops:
        stop_ids = [s["stop_id"] for s in origin_bus_stops]
        bus_arrivals, n_bus_errors = await get_bus_arrivals(stop_ids, bus_key)
        if request.bus_fullness != "All":
            target_load = _FULLNESS_API_VALUES.get(request.bus_fullness, "")
            bus_arrivals = [a for a in bus_arrivals if a.get("psgld", "") == target_load]

    return train_arrivals, bus_arrivals, n_train_errors, n_bus_errors


def _scale_walk_legs(routes: list, walk_speed: float) -> None:
    """Multiply every WalkLeg.minutes by 1/walk_speed in-place, then update walk_minutes_total.

    walk_speed=1.0 is a no-op (standard pace). Called before _rank_routes so
    ranking and displayed times both reflect the user's actual walking pace.
    """
    if walk_speed == 1.0:
        return
    factor = 1.0 / walk_speed
    for route in routes:
        scaled_walk = 0.0
        for leg in route.legs:
            if isinstance(leg, WalkLeg):
                leg.minutes = round(leg.minutes * factor, 1)
                scaled_walk += leg.minutes
        route.walk_minutes_total = round(scaled_walk, 1)


def _precip_walk_factor(weather: "WeatherContext | None") -> float:
    """Return a multiplicative walk-speed factor (<=1.0) based on precipitation, wind, and cold.

    Combines three penalties: precipitation type/intensity, wind gusts >35 mph (x0.90),
    and feels_like <0F (x0.88). Floor of 0.60 prevents absurd stacked-penalty results.
    """
    if weather is None:
        return 1.0
    c = weather.current
    ptype = c.precipitation.type
    intensity = c.precipitation.intensity  # "light" | "moderate" | "heavy" | ""

    if ptype == PrecipitationType.NONE:
        base_factor = 1.0
    elif ptype in (PrecipitationType.FREEZING_RAIN, PrecipitationType.SLEET):
        base_factor = 0.78
    elif ptype == PrecipitationType.RAIN:
        if intensity == "heavy":
            base_factor = 0.82
        elif intensity == "moderate":
            base_factor = 0.90
        else:
            base_factor = 0.96
    elif ptype == PrecipitationType.SNOW:
        if intensity == "heavy":
            base_factor = 0.74
        elif intensity == "moderate":
            base_factor = 0.84
        else:
            base_factor = 0.92
    else:
        base_factor = 1.0

    factor = base_factor
    if c.wind.gust_mph and c.wind.gust_mph > 35:
        factor *= 0.90
    if c.feels_like_f < 0:
        factor *= 0.88

    return max(0.60, factor)


async def _run_routing(
    request: RouteRequest,
    origin_coords: tuple | None,
    dest_coords: tuple | None,
    origin_stations: list[dict],
    origin_bus_stops: list[dict],
    train_arrivals: list[dict],
    bus_arrivals: list[dict],
    weather: "WeatherContext | None" = None,
) -> list[tuple]:
    """Run the unified routing engine and return ranked (total, wait, route) tuples."""
    ranked_routes: list[tuple] = []
    if not origin_coords or not dest_coords:
        return ranked_routes

    precip_factor = _precip_walk_factor(weather)
    effective_speed = request.walk_speed * precip_factor

    # Unified-graph routing (trains + direct bus + intermodal).
    # Feature J (2026-04-18): find_routes() is the sole source of direct
    # bus-only itineraries; Bus mode post-filters to drop routes with train legs.
    try:
        bus_stop_walk_map = {s["stop_id"]: s["walk_minutes"] for s in origin_bus_stops}
        arrival_lookup = _build_arrival_lookup(train_arrivals, bus_arrivals, bus_stop_walk_map)
        raw_routes = find_routes(
            origin_lat=origin_coords[0],
            origin_lon=origin_coords[1],
            dest_lat=dest_coords[0],
            dest_lon=dest_coords[1],
            origin_stations=origin_stations,
            n_routes=5,
        )
        _scale_walk_legs(raw_routes, effective_speed)
        ranked_routes = _rank_routes(raw_routes, arrival_lookup)
        if request.transit_mode == "Bus":
            ranked_routes = [
                (total, wait, route)
                for total, wait, route in ranked_routes
                if not any(
                    isinstance(leg, TransitLeg) and leg.line_code in LINE_NAMES
                    for leg in route.legs
                )
            ]
    except Exception as exc:
        print(f"[recommend] unified-graph routing error: {exc}")

    # Bus-to-bus transfer routes — find_routes() does not model these as graph
    # edges, so find_bus_transfer_routes() handles them separately.
    if request.transit_mode in ("Bus", "All") and bus_arrivals and origin_bus_stops:
        try:
            transfer_ranked_raw = find_bus_transfer_routes(
                origin_lat=origin_coords[0],
                origin_lon=origin_coords[1],
                dest_lat=dest_coords[0],
                dest_lon=dest_coords[1],
                bus_arrivals=bus_arrivals,
                origin_bus_stops=origin_bus_stops,
                n_routes=2,
            )
            if transfer_ranked_raw:
                _scale_walk_legs(
                    [r for _t, _w, r in transfer_ranked_raw],
                    effective_speed,
                )
                # Rebuild totals after walk scaling (total was computed before scaling)
                transfer_ranked_raw = [
                    (route.total_minutes_no_wait + (w or 0), w, route)
                    for _t, w, route in transfer_ranked_raw
                ]
                transfer_ranked = _rank_bus_routes(transfer_ranked_raw)
            else:
                transfer_ranked = []
            ranked_routes = sorted(
                ranked_routes + transfer_ranked,
                key=lambda x: x[0],
            )[:5]
        except Exception as exc:
            print(f"[recommend] bus transfer routing error: {exc}")

    return ranked_routes


async def _fetch_transfer_arrivals(ranked_routes: list[tuple]) -> list[dict]:
    """Fetch live arrivals at transfer stops (Feature D) and annotate legs in-place.

    Returns combined train + bus transfer arrival dicts.
    """
    if not ranked_routes:
        return []

    train_key = os.getenv("CTA_TRAIN_API_KEY", "")
    bus_key   = os.getenv("CTA_BUS_API_KEY", "")

    transfer_train_stations, transfer_bus_stop_ids = _extract_transfer_stops(ranked_routes)
    xfer_train_task = (
        get_train_arrivals(transfer_train_stations, train_key)
        if transfer_train_stations and train_key
        else _empty()
    )
    xfer_bus_task = (
        get_bus_arrivals(transfer_bus_stop_ids, bus_key)
        if transfer_bus_stop_ids and bus_key
        else _empty()
    )
    xfer_train_result, xfer_bus_result = await asyncio.gather(xfer_train_task, xfer_bus_task)

    transfer_train_arrivals: list[dict] = (
        xfer_train_result[0] if isinstance(xfer_train_result, tuple) else xfer_train_result
    )
    transfer_bus_arrivals: list[dict] = (
        xfer_bus_result[0] if isinstance(xfer_bus_result, tuple) else xfer_bus_result
    )

    # Annotate transfer legs in-place with live wait data
    train_xfer_lookup = _build_arrival_lookup(transfer_train_arrivals)
    bus_xfer_lookup   = _build_bus_transfer_lookup(transfer_bus_arrivals)
    for _total, _wait, route in ranked_routes:
        seen_transit = False
        for leg in route.legs:
            if isinstance(leg, TransitLeg):
                if seen_transit:
                    if leg.line_code in LINE_NAMES:
                        dest_map = train_xfer_lookup.get(
                            (leg.line_code, leg.from_mapid), {}
                        )
                        leg.transfer_wait_minutes = _pick_wait(
                            dest_map, leg.from_mapid, leg.to_mapid
                        )
                    else:
                        leg.transfer_wait_minutes = bus_xfer_lookup.get(
                            (leg.line_code, leg.from_mapid)
                        )
                seen_transit = True

    return transfer_train_arrivals + transfer_bus_arrivals


# Static system instruction passed to every Claude request.
# Marked ephemeral so the Anthropic API caches it server-side (5-min TTL),
# avoiding re-billing these tokens on every call.
_CLAUDE_SYSTEM_PROMPT = "You are a helpful Chicago transit assistant."


async def _call_claude(
    claude_client: anthropic.AsyncAnthropic,
    prompt: str,
    ranked_routes: list[tuple],
) -> tuple[str, str]:
    """Call Claude with prompt, selecting model by query complexity.

    Returns (recommendation_text, model_label) where model_label is 'haiku' or 'sonnet'.
    Raises HTTPException(502) on Claude API failure.
    """
    simple     = _is_simple_query(ranked_routes)
    _simple_model  = os.getenv("CLAUDE_SIMPLE_MODEL",  "claude-haiku-4-5-20251001")
    _complex_model = os.getenv("CLAUDE_COMPLEX_MODEL", "claude-sonnet-4-6")
    model      = _simple_model if simple else _complex_model
    max_tokens = 300 if simple else 400
    print(f"[claude model={'haiku' if simple else 'sonnet'} simple={simple}]")

    try:
        message = await claude_client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=[{
                "type": "text",
                "text": _CLAUDE_SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{"role": "user", "content": prompt}],
        )
        text_block = next((c for c in message.content if hasattr(c, "text")), None)
        if not text_block:
            raise ValueError("No text block in Claude response")
        return text_block.text, ("haiku" if simple else "sonnet")
    except Exception as exc:
        print(f"[recommend] Claude API error: {exc}")
        raise HTTPException(status_code=502, detail=f"Claude API error: {exc}")


def _format_response(
    recommendation: str,
    model_used: str,
    origin_coords: tuple | None,
    dest_coords: tuple | None,
    train_arrivals: list[dict],
    bus_arrivals: list[dict],
    n_train_errors: int,
    n_bus_errors: int,
    origin_stations: list[dict],
    alerts: list[dict],
    ranked_routes: list[tuple],
    weather: "WeatherContext | None" = None,
) -> dict:
    """Assemble the final JSON-serialisable response dict."""
    return {
        "recommendation": recommendation,
        "model_used": model_used,
        "weather": (
            {
                "temperature_f":           round(weather.current.temperature_f),
                "feels_like_f":            round(weather.current.feels_like_f),
                "short_forecast":          weather.current.short_forecast,
                "precipitation_type":      weather.current.precipitation.type.value,
                "precipitation_intensity": weather.current.precipitation.intensity,
                "wind_gust_mph":           weather.current.wind.gust_mph,
                "alerts":                  weather.alerts,
            }
            if weather is not None else None
        ),
        "origin_coords": list(origin_coords) if origin_coords else None,
        "dest_coords":   list(dest_coords)   if dest_coords   else None,
        "train_arrivals": train_arrivals,
        "bus_arrivals": bus_arrivals,
        "train_errors": n_train_errors,
        "bus_errors":   n_bus_errors,
        "origin_stations": [s["name"] for s in origin_stations],
        "alerts": [
            {
                "alert_id":       a["alert_id"],
                "headline":       a["headline"],
                "impact":         a["impact"],
                "severity_score": a["severity_score"],
                "is_major":       a["is_major"],
                "event_end":      a["event_end"],
                "affected_routes": a["affected_routes"],
            }
            for a in alerts
        ],
        "routes": [
            {
                "total_minutes": round(total),
                "wait_minutes":  wait,
                "transfers":     route.transfers,
                "legs": [
                    {
                        "type":      leg.leg_type,
                        "line":      getattr(leg, "line", None),
                        "line_code": getattr(leg, "line_code", None),
                        "from": leg.from_name    if isinstance(leg, WalkLeg) else leg.from_station,
                        "to":   leg.to_name      if isinstance(leg, WalkLeg) else leg.to_station,
                        "minutes": round(leg.minutes, 1),
                        **(
                            {
                                "shape":                 leg.shape_points,
                                "from_coords":           leg.shape_points[0]  if leg.shape_points else None,
                                "to_coords":             leg.shape_points[-1] if leg.shape_points else None,
                                "transfer_wait_minutes": leg.transfer_wait_minutes,
                                "from_mapid":            leg.from_mapid,
                            }
                            if isinstance(leg, TransitLeg)
                            else {
                                "path":       leg.path_points,
                                "directions": leg.directions,
                                "exit_label": leg.exit_label,
                            }
                        ),
                    }
                    for leg in route.legs
                ],
            }
            for total, wait, route in ranked_routes
        ],
    }


# ---------------------------------------------------------------------------
# Feature Weather — helpers
# ---------------------------------------------------------------------------

async def _safe_weather(
    origin_coords: tuple | None,
) -> "WeatherContext | None":
    """Fetch weather for origin_coords; return None on any failure (non-fatal)."""
    if not origin_coords:
        return None
    try:
        return await weather_service.get_weather_context(
            origin_coords[0], origin_coords[1]
        )
    except Exception:
        traceback.print_exc()
        return None


def _format_weather_for_prompt(weather: WeatherContext, hint: str = "") -> str:
    """Format a one-line weather summary for the Claude prompt.

    hint is from _departure_window_hint(); when non-empty it is appended to the
    current-conditions line so the full weather context stays on one line.
    """
    c = weather.current

    if c.precipitation.type == PrecipitationType.NONE:
        precip_str = "none"
    elif c.precipitation.intensity:
        precip_str = f"{c.precipitation.type.value} ({c.precipitation.intensity})"
    else:
        precip_str = c.precipitation.type.value

    gust_str = ""
    if c.wind.gust_mph and c.wind.gust_mph >= 15:
        gust_str = f", wind gusts {c.wind.gust_mph:.0f} mph"

    hint_str = f" {hint}" if hint else ""

    line = (
        f"Current weather: {c.short_forecast}, {c.temperature_f:.0f}°F "
        f"(feels like {c.feels_like_f:.0f}°F), precipitation: {precip_str}{gust_str}{hint_str}"
    )

    if weather.alerts:
        line += f"\nWeather alerts: {'; '.join(weather.alerts[:2])}"

    return line


def _departure_window_hint(weather: "WeatherContext | None") -> str:
    """Return a short departure-timing hint based on the hourly forecast.

    Scans the next 3 forecast periods for a precipitation transition:
      - Improving (rain/snow clears): "(forecast: clears in ~Nh)"
      - Worsening (precipitation starts): "(forecast: {type} starts in ~Nh)"
    Only emits when the qualifying period is index >= 1 (index 0 is imminent,
    not actionable). Returns "" when no relevant transition is found.
    """
    if weather is None or len(weather.hourly_forecast) < 2:
        return ""
    current_type = weather.current.precipitation.type
    for i, fp in enumerate(weather.hourly_forecast[:3]):
        if i < 1:
            continue
        if (
            current_type != PrecipitationType.NONE
            and fp.precipitation.type == PrecipitationType.NONE
        ):
            return f"(forecast: clears in ~{i + 1}h)"
        if (
            current_type == PrecipitationType.NONE
            and fp.precipitation.type != PrecipitationType.NONE
        ):
            return f"(forecast: {fp.precipitation.type.value} starts in ~{i + 1}h)"
    return ""


# ---------------------------------------------------------------------------
# Feature Crowdedness — helpers
# ---------------------------------------------------------------------------

_CROWDEDNESS_LABELS: dict[CrowdednessLevel, str] = {
    CrowdednessLevel.LOW:       "light",
    CrowdednessLevel.MODERATE:  "moderate",
    CrowdednessLevel.HIGH:      "busy",
    CrowdednessLevel.VERY_HIGH: "very crowded",
}

# 1-minute cache for (time_period, day_type, hour) — these change at most once
# every 15–30 minutes so re-computing on every leg of every request is wasteful.
_crowdedness_period_cached: tuple | None = None
_crowdedness_period_cache_ts: float = 0.0
_CROWDEDNESS_PERIOD_TTL = 60.0  # seconds


def _get_crowdedness_period() -> tuple:
    """Return (time_period, day_type, hour), recomputing at most once per minute."""
    global _crowdedness_period_cached, _crowdedness_period_cache_ts
    now_mono = time.monotonic()
    if _crowdedness_period_cached is None or now_mono - _crowdedness_period_cache_ts > _CROWDEDNESS_PERIOD_TTL:
        now = datetime.now(_CHICAGO_TZ)
        _crowdedness_period_cached = (*classify_time_period(now), now.hour)
        _crowdedness_period_cache_ts = now_mono
    return _crowdedness_period_cached


def _crowdedness_for_routes(ranked: list[tuple]) -> dict[int, str]:
    """
    Compute a crowdedness label for each ranked route (keyed by 1-based index).

    Uses current Chicago time to classify the time period.  For each route,
    takes the worst crowdedness level across all TransitLegs and converts it
    to a human-readable label for the Claude prompt.
    """
    time_period, day_type, now_hour = _get_crowdedness_period()

    labels: dict[int, str] = {}
    for i, (_total, _wait, route) in enumerate(ranked, 1):
        leg_levels: list[CrowdednessLevel] = []
        for leg in route.legs:
            if not isinstance(leg, TransitLeg):
                continue
            is_bus = leg.line in ("Northbound", "Southbound", "Eastbound", "Westbound")
            direction = (
                rtdir_to_inbound_outbound(leg.line_code, leg.line)
                if is_bus else "inbound"
            )
            est = estimate_crowdedness(
                route_id=leg.line_code or "",
                direction=direction,
                stop_id=leg.from_mapid or "",
                stop_sequence_position=1,
                total_stops=2,
                time_period=time_period,
                day_type=day_type,
                current_hour=now_hour,
            )
            leg_levels.append(est.level)
        if leg_levels:
            worst = max(leg_levels, key=lambda lvl: CROWDEDNESS_LEVEL_ORDER[lvl])
            labels[i] = _CROWDEDNESS_LABELS[worst]
    return labels


# ---------------------------------------------------------------------------
# Language support
# ---------------------------------------------------------------------------

LANGUAGE_NAMES: dict[str, str] = {
    "en":  "English",
    "es":  "Spanish",
    "fr":  "French",
    "it":  "Italian",
    "pl":  "Polish",
    "ro":  "Romanian",
    "uk":  "Ukrainian",
    "ru":  "Russian",
    "zh":  "Mandarin Chinese",
    "yue": "Cantonese Chinese",
    "ja":  "Japanese",
    "ko":  "Korean",
    "tl":  "Filipino (Tagalog)",
    "vi":  "Vietnamese",
    "hi":  "Hindi",
    "gu":  "Gujarati",
    "pa":  "Punjabi",
    "ne":  "Nepali",
    "ur":  "Urdu",
    "ar":  "Arabic",
    "ps":  "Pashto",
    "yo":  "Yoruba",
}

# ---------------------------------------------------------------------------
# Prompt building
# ---------------------------------------------------------------------------

def _format_routes(ranked: list[tuple]) -> str:
    """Format ranked (total, wait, route) list into a text block for Claude.
    Handles both train and bus TransitLegs."""
    crowd_labels = _crowdedness_for_routes(ranked)
    lines = []
    for i, (total, wait, route) in enumerate(ranked, 1):
        first_transit = next((l for l in route.legs if isinstance(l, TransitLeg)), None)
        is_bus = first_transit and first_transit.line in (
            "Northbound", "Southbound", "Eastbound", "Westbound"
        )
        if wait is None:
            wait_note = ""                                        # no live data
        elif wait == 0:
            wait_note = ", next bus Due" if is_bus else ", next train Due"
        else:
            wait_note = (
                f", next bus in {wait} min" if is_bus
                else f", next train in {wait} min"
            )
        leg_parts = []
        for leg in route.legs:
            if isinstance(leg, WalkLeg):
                if leg.from_name == "Your location":
                    leg_parts.append(f"walk {leg.minutes:.0f} min to {leg.to_name}")
                elif leg.to_name == "Your destination":
                    leg_parts.append(f"walk {leg.minutes:.0f} min to destination")
                else:
                    leg_parts.append(f"transfer walk {leg.minutes:.0f} min")
            else:
                if leg.line in ("Northbound", "Southbound", "Eastbound", "Westbound"):
                    leg_parts.append(
                        f"Route {leg.line_code} {leg.line} "
                        f"{leg.from_station} to {leg.to_station} "
                        f"({leg.minutes:.0f} min in-vehicle)"
                    )
                else:
                    leg_parts.append(
                        f"{leg.line} {leg.from_station} to {leg.to_station} "
                        f"({leg.minutes:.0f} min in-vehicle)"
                    )
        xfers = f", {route.transfers} transfer{'s' if route.transfers != 1 else ''}" if route.transfers else ""
        crowd_tag = f" [est. crowdedness: {crowd_labels[i]}]" if i in crowd_labels else ""
        lines.append(
            f"Option {i}: {' | '.join(leg_parts)}{wait_note} "
            f"[~{total:.0f} min total{xfers}]{crowd_tag}"
        )
    return "\n".join(lines)


def _format_bus_arrivals(bus_arrivals: list[dict]) -> str:
    lines = []
    for a in bus_arrivals[:6]:
        due = "Due" if a["arrives_in_minutes"] == 0 else f"{a['arrives_in_minutes']} min"
        delay = " (DELAYED)" if a["is_delayed"] else ""
        load = a.get("psgld", "")
        load_note = f" [{load.replace('_', ' ').title()}]" if load else ""
        lines.append(
            f"  * Route {a['route']} toward {a['destination']} — {due}{delay}{load_note}"
            f" | {a['stop_name']}"
        )
    return "\n".join(lines)


def build_prompt(
    origin: str,
    destination: str,
    train_arrivals: list[dict],
    bus_arrivals: list[dict],
    transit_mode: str = "All",
    ranked_routes: list[tuple] | None = None,
    bus_fullness: str = "All",
    alerts: list[dict] | None = None,
    route_statuses: list[dict] | None = None,
    transfer_arrivals: list[dict] | None = None,
    language: str | None = None,
    weather: "WeatherContext | None" = None,
) -> str:
    mode_constraints = {
        "Train": "The rider wants TRAIN options only. Do not mention buses.",
        "Bus":   "The rider wants BUS options only. Do not mention trains.",
        "All":   "The rider is open to trains and buses.",
        "Walk":  "The rider wants to WALK. Provide a brief summary of the walking route and estimated time. Do not mention transit.",
    }
    mode_note = mode_constraints.get(transit_mode, mode_constraints["All"])

    has_data = ranked_routes or train_arrivals or bus_arrivals
    if not has_data:
        if transit_mode == "Bus":
            return (
                f"A Chicago CTA rider at {origin} wants to get to {destination} by bus only. "
                "No live bus arrivals are available right now. "
                "Suggest they check the Ventra app or transitchicago.com for bus times."
            )
        return (
            f"A Chicago CTA rider wants to get from {origin} to {destination}. "
            "No live arrivals are currently available. "
            "Suggest they check the Ventra app or transitchicago.com."
        )

    sections = []

    if ranked_routes:
        routes_text = _format_routes(ranked_routes)
        sections.append(
            "Calculated route options (sorted by total time: walk + wait + in-vehicle):\n"
            + routes_text
        )

    if transfer_arrivals:
        sections.append(
            "Live arrivals at transfer stop(s):\n"
            + _format_transfer_arrivals(transfer_arrivals)
        )

    if not ranked_routes and bus_arrivals and transit_mode in ("Bus", "All"):
        # Fallback: raw bus arrivals when bus routing produced no structured routes
        fullness_note = (
            f" (filtered to {bus_fullness} buses only)" if bus_fullness != "All" else ""
        )
        bus_text = _format_bus_arrivals(bus_arrivals)
        sections.append(
            f"Live bus arrivals at nearby stops{fullness_note} (unstructured fallback):\n"
            + bus_text
        )

    # Fallback: raw train arrivals when routing engine produced nothing
    if not ranked_routes and train_arrivals:
        arr_lines = []
        for a in train_arrivals[:6]:
            delay = " (DELAYED)" if a["is_delayed"] else ""
            sched = " (schedule-based)" if a["is_scheduled"] else ""
            due   = "Due" if a["arrives_in_minutes"] == 0 else f"{a['arrives_in_minutes']} min"
            walk  = a.get("walk_minutes", 0)
            arr_lines.append(
                f"  * {a['line']} toward {a['destination']} — {due}{delay}{sched}"
                + (f" | {walk} min walk to {a['station']}" if walk else f" | {a['station']}")
            )
        sections.append("Live train arrivals at nearby stations:\n" + "\n".join(arr_lines))

    body = "\n\n".join(sections)

    alert_section = ""
    significant_alerts = [a for a in (alerts or []) if a.get("severity_score", 0) >= 40]
    if significant_alerts:
        alert_lines = []
        for a in significant_alerts:
            prefix = "⚠ MAJOR — " if a.get("is_major") else ""
            impact = f" [{a['impact']}]" if a.get("impact") else ""
            alert_lines.append(f"  * {prefix}{a['headline']}{impact}")
        alert_section = "\n\nActive service alerts on your route:\n" + "\n".join(alert_lines)

    route_status_section = ""
    disrupted = [r for r in (route_statuses or []) if r.get("status", "").lower() != "normal service"]
    if disrupted:
        status_lines = [f"  * {r['route']}: {r['status']}" for r in disrupted]
        route_status_section = "\n\nCurrent system-wide route disruptions:\n" + "\n".join(status_lines)

    lang_instruction = ""
    if language and language != "en":
        if language == "ja":
            lang_instruction = (
                "\n\nRespond in Japanese. Use standard Japanese (a natural mix of hiragana, "
                "katakana, and kanji). Add furigana in parentheses after each kanji compound "
                "to aid readability — for example: 電車（でんしゃ）."
            )
        elif language in LANGUAGE_NAMES:
            lang_instruction = f"\n\nRespond in {LANGUAGE_NAMES[language]}."

    departure_hint = _departure_window_hint(weather)

    weather_section = ""
    if weather is not None:
        weather_section = "\n\n" + _format_weather_for_prompt(weather, departure_hint)
        scoring_hint = weight_hint_for_weather(weather)
        if scoring_hint:
            weather_section += "\n" + scoring_hint

    weather_hint = (
        " incorporate weather context naturally within those sentences, not as a separate paragraph."
        if weather is not None
        else " the rider is probably standing outside."
    )

    departure_instruction = (
        " If conditions improve soon, mention the optimal departure window."
        if departure_hint
        else ""
    )

    return (
        f"A rider is at {origin} and wants to get to {destination}.\n\n"
        f"Rider preference: {mode_note}\n\n"
        f"{body}{alert_section}{route_status_section}{weather_section}\n\n"
        "Lead with the single best option and explain why in plain English. "
        "Factor in total trip time including walking and waiting. "
        f"Note any delays or active service alerts. Keep it to 3-4 sentences —{weather_hint}"
        f"{departure_instruction}"
        f"{lang_instruction}"
    )


# ---------------------------------------------------------------------------
# /stop-arrivals helpers (Feature Pinned Stops + Feature Last Train)
# ---------------------------------------------------------------------------

def _parse_gtfs_time_mins(t: str) -> float:
    """GTFS HH:MM:SS → minutes since midnight. Handles 24:xx/25:xx post-midnight times."""
    parts = t.strip().split(":")
    h, m, s = int(parts[0]), int(parts[1]), int(parts[2])
    return h * 60.0 + m + s / 60.0


def _last_dep_minutes(mapid: str, now_chicago: datetime) -> int | None:
    """
    Return minutes until the last scheduled train departure from a station
    (across both directions), or None if outside the 0–120 minute window.

    Post-midnight CTA service is encoded as "24:xx"/"25:xx" in GTFS.
    Current times between 00:00–02:59 are treated as continuation of the
    previous service day by offsetting now_mins by +1440 (24 h) so they
    compare correctly against post-midnight departure times.
    """
    now_mins = now_chicago.hour * 60.0 + now_chicago.minute + now_chicago.second / 60.0
    # 00:00–02:59 → still "last night's" service day
    if now_chicago.hour < 3:
        now_mins += 24 * 60.0

    best: int | None = None
    for did in ("0", "1"):
        dep_str = get_last_departure(mapid, did)
        if dep_str is None:
            continue
        try:
            dep_mins = _parse_gtfs_time_mins(dep_str)
        except Exception:
            continue
        minutes_until = dep_mins - now_mins
        if 0 <= minutes_until <= 120:
            rounded = round(minutes_until)
            if best is None or rounded > best:
                best = rounded
    return best


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/ping")
async def ping(http_request: Request):
    ip = _client_ip(http_request)
    await dau.record_visit(ip)
    return {"ok": True}


@app.get("/stop-arrivals")
async def stop_arrivals(stops: list[str] = Query(default=[])):
    """
    Return live arrivals for a list of pinned stops (Feature Pinned Stops).
    Each stop is specified as "<type>:<stop_id>" — e.g. "train:40500" or "bus:1234".
    Maximum 10 stops per request.

    Response: { "arrivals": { "<stop_id>": { "arrivals": [...], "last_departure_minutes"?: int } } }
    "last_departure_minutes" is included for train stops when within 0–120 min of last run.
    """
    if len(stops) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 stops per request")

    cache_key = ",".join(sorted(stops))
    now_mono = time.monotonic()
    cached = _stop_arrivals_cache.get(cache_key)
    if cached and now_mono < cached[0]:
        return cached[1]

    train_stop_ids: list[str] = []
    bus_stop_ids:   list[str] = []
    for item in stops:
        if ":" not in item:
            continue
        typ, sid = item.split(":", 1)
        if typ == "train":
            train_stop_ids.append(sid)
        elif typ == "bus":
            bus_stop_ids.append(sid)

    train_key = os.getenv("CTA_TRAIN_API_KEY", "")
    bus_key   = os.getenv("CTA_BUS_API_KEY", "")

    train_station_dicts = [{"mapid": sid, "name": sid} for sid in train_stop_ids]
    train_task = (
        get_train_arrivals(train_station_dicts, train_key)
        if train_station_dicts and train_key else _empty()
    )
    bus_task = (
        get_bus_arrivals(bus_stop_ids, bus_key)
        if bus_stop_ids and bus_key else _empty()
    )

    train_result, bus_result = await asyncio.gather(train_task, bus_task)
    train_arrs: list[dict] = train_result[0] if isinstance(train_result, tuple) else train_result
    bus_arrs:   list[dict] = bus_result[0]   if isinstance(bus_result,   tuple) else bus_result

    arrivals: dict[str, dict] = {}

    for a in train_arrs:
        sid = a.get("station_mapid", "")
        if not sid:
            continue
        entry = arrivals.setdefault(sid, {"arrivals": []})
        if len(entry["arrivals"]) < 3:
            entry["arrivals"].append({
                "route":       a.get("line_code", ""),
                "destination": a.get("destination", ""),
                "minutes":     a.get("arrives_in_minutes", 0),
            })

    for a in bus_arrs:
        sid = a.get("stop_id", "")
        if not sid:
            continue
        entry = arrivals.setdefault(sid, {"arrivals": []})
        if len(entry["arrivals"]) < 3:
            entry["arrivals"].append({
                "route":       a.get("route", ""),
                "destination": a.get("destination", ""),
                "minutes":     a.get("arrives_in_minutes", 0),
            })

    # Ensure every requested stop appears in the response even if no arrivals came back
    for item in stops:
        if ":" not in item:
            continue
        _, sid = item.split(":", 1)
        arrivals.setdefault(sid, {"arrivals": []})

    # Feature Last Train: add last_departure_minutes for train stops within window
    now_chicago = datetime.now(_CHICAGO_TZ)
    for sid in train_stop_ids:
        mins = _last_dep_minutes(sid, now_chicago)
        if mins is not None:
            arrivals.setdefault(sid, {"arrivals": []})["last_departure_minutes"] = mins

    result = {"arrivals": arrivals}

    _stop_arrivals_cache[cache_key] = (now_mono + _STOP_ARRIVALS_TTL, result)
    if len(_stop_arrivals_cache) > 200:
        _stop_arrivals_cache.popitem(last=False)

    return result


@app.get("/admin/dau")
async def admin_dau(authorization: str | None = Header(default=None)):
    token = os.getenv("DAU_ADMIN_TOKEN", "")
    expected = f"Bearer {token}" if token else None
    if not expected or authorization != expected:
        raise HTTPException(status_code=403, detail="Forbidden")
    return await dau.get_counts()


@app.get("/autocomplete")
async def autocomplete(q: str = Query("", min_length=0)):
    """
    Return up to 8 location suggestions matching query q (min 2 chars).
    Priority order: train stations → neighborhoods/landmarks → bus stop names.
    Within each tier: prefix > word-start match.
    """
    query = q.strip().lower()
    if len(query) < 2:
        return {"suggestions": []}

    # O(1) prefix lookup: use 3-char key for queries ≥ 3 chars, else 2-char key.
    key = query[:3] if len(query) >= 3 else query
    candidates = _ac_prefix_index.get(key, [])

    ranked: list[tuple[int, int, int]] = []
    seen: set[str] = set()
    for tier, _base_score, idx in candidates:
        suggestion = _ac_master[idx]
        nl = suggestion["label"].lower()
        if nl.startswith(query):
            score = 0
        elif any(w.startswith(query) for w in nl.split()):
            score = 1
        else:
            continue
        label = suggestion["label"]
        if label not in seen:
            seen.add(label)
            ranked.append((tier, score, idx))

    ranked.sort(key=lambda x: (x[0], x[1]))
    return {"suggestions": [_ac_master[idx] for _, _, idx in ranked[:8]]}


# ---------------------------------------------------------------------------
# /alerts cache — 5-minute TTL, single static key "alerts"
# ---------------------------------------------------------------------------
_ALERTS_CACHE_TTL = 300  # 5 minutes
_alerts_cache: collections.OrderedDict[str, tuple[float, dict]] = collections.OrderedDict()
_CTA_CUSTOMER_ALERTS_URL = "https://www.transitchicago.com/api/1.0/alerts.aspx"
_ALERTS_SEVERITY_ORDER = {"Major": 0, "Minor": 1, "Planned": 2}


@app.get("/alerts")
async def alerts_endpoint():
    """
    Fetch all active CTA service alerts from the Customer Alerts API.
    Returns { "alerts": [...] } with a 5-minute TTL cache.
    Each alert: { alert_id, headline, short_description, routes, severity }.
    severity is "Major" (score>=70), "Minor" (40-69), or "Planned" (<40).
    routes is a list of short route names, e.g. ["Red", "22"].
    Returns empty list on CTA API failure; never raises.
    """
    cache_key = "alerts"
    now_mono = time.monotonic()
    cached = _alerts_cache.get(cache_key)
    if cached and now_mono < cached[0]:
        return cached[1]

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                _CTA_CUSTOMER_ALERTS_URL,
                params={"outputType": "XML", "accessibility": "N"},
                timeout=aiohttp.ClientTimeout(total=8),
            ) as resp:
                text = await resp.text()

        import xml.etree.ElementTree as ET  # lazy import — only used in this endpoint
        root = ET.fromstring(text)
        parsed: list[dict] = []
        for alert_el in root.findall("Alert"):
            try:
                severity_score = int(alert_el.findtext("SeverityScore", "0") or 0)
                if severity_score >= 70:
                    severity = "Major"
                elif severity_score >= 40:
                    severity = "Minor"
                else:
                    severity = "Planned"

                routes: list[str] = []
                impacted = alert_el.find("ImpactedService")
                if impacted is not None:
                    for svc in impacted.findall("Service"):
                        name = (svc.findtext("ServiceName") or "").strip()
                        # Normalize "Red Line" → "Red" so names match route pill labels
                        name = name.removesuffix(" Line")
                        if name:
                            routes.append(name)

                parsed.append({
                    "alert_id":          alert_el.findtext("AlertId", ""),
                    "headline":          alert_el.findtext("Headline", ""),
                    "short_description": alert_el.findtext("ShortDescription", ""),
                    "routes":            routes,
                    "severity":          severity,
                })
            except Exception:
                continue

        parsed.sort(key=lambda a: _ALERTS_SEVERITY_ORDER.get(a["severity"], 3))
        result: dict = {"alerts": parsed}
    except Exception:
        traceback.print_exc()
        result = {"alerts": []}

    _alerts_cache[cache_key] = (now_mono + _ALERTS_CACHE_TTL, result)
    if len(_alerts_cache) > 10:
        _alerts_cache.popitem(last=False)

    return result


@app.post("/recommend")
async def recommend(request: RouteRequest, http_request: Request):
    ip = _client_ip(http_request)

    # If BYOK is enabled and the user supplied a valid key, create a throwaway
    # client scoped to this request. A new AsyncAnthropic() is cheap — it holds
    # no persistent connection.
    byok_key = request.anthropic_api_key if _BYOK_ENABLED else None
    claude_client = (
        anthropic.AsyncAnthropic(api_key=byok_key) if byok_key else _claude_client
    )

    _validate_api_keys(request, byok_key)

    key = _cache_key(
        request.origin, request.destination, request.transit_mode,
        request.bus_fullness, byok=bool(byok_key), ai_enabled=request.ai_enabled,
        language=request.language or "en", walk_speed=request.walk_speed,
    )

    # Hold _store_lock for the rate-limit check and cache read atomically.
    # This prevents two concurrent requests with the same key from both seeing a
    # cache miss and both launching the full expensive pipeline (stampede), and
    # ensures the rate-limit timestamp is written before any await yields control.
    async with _store_lock:
        global _cache_hits, _cache_misses, _cache_requests_total
        if not _check_rate_limit(ip):
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please wait a minute before trying again.",
            )
        _cache_requests_total += 1
        cached = _response_cache.get(key)
        if cached:
            if time.monotonic() < cached[0]:
                _response_cache.move_to_end(key)  # promote to MRU position (LRU eviction)
                _cache_hits += 1
                if _cache_requests_total % _CACHE_LOG_INTERVAL == 0:
                    print(
                        f"[cache] {_cache_requests_total} requests | "
                        f"hits={_cache_hits} misses={_cache_misses} "
                        f"hit_rate={_cache_hits/_cache_requests_total:.1%} "
                        f"size={len(_response_cache)}"
                    )
                return {**cached[1], "cache_hit": True}
            _response_cache.pop(key, None)  # evict stale entry
        _cache_misses += 1
        if _cache_requests_total % _CACHE_LOG_INTERVAL == 0:
            print(
                f"[cache] {_cache_requests_total} requests | "
                f"hits={_cache_hits} misses={_cache_misses} "
                f"hit_rate={_cache_hits/_cache_requests_total:.1%} "
                f"size={len(_response_cache)}"
            )

    loop = asyncio.get_running_loop()

    # Walk mode — skip all CTA API calls; resolve coordinates and route via walking graph only.
    if request.transit_mode == "Walk":
        origin_coords, dest_coords = await asyncio.gather(
            loop.run_in_executor(None, _coords_for_location, request.origin, None),
            loop.run_in_executor(None, _coords_for_location, request.destination, None),
        )
        if not origin_coords:
            raise HTTPException(status_code=400, detail=f"Could not geocode '{request.origin}'.")
        if not dest_coords:
            raise HTTPException(status_code=400, detail=f"Could not geocode '{request.destination}'.")
        dlat = origin_coords[0] - dest_coords[0]
        dlon = origin_coords[1] - dest_coords[1]
        if (dlat * dlat + dlon * dlon) < _SAME_LOCATION_THRESHOLD_DEG2:
            raise HTTPException(status_code=400, detail="Your origin and destination appear to be the same location.")

        walk_min, directions, path, walk_weather = await asyncio.gather(
            loop.run_in_executor(None, _walk_minutes, origin_coords[0], origin_coords[1], dest_coords[0], dest_coords[1]),
            loop.run_in_executor(None, _walk_directions, origin_coords[0], origin_coords[1], dest_coords[0], dest_coords[1]),
            loop.run_in_executor(None, _walk_path, origin_coords[0], origin_coords[1], dest_coords[0], dest_coords[1]),
            _safe_weather(origin_coords),
        )
        walk_effective_speed = request.walk_speed * _precip_walk_factor(walk_weather)
        if walk_effective_speed != 1.0:
            walk_min = round(walk_min / walk_effective_speed, 1)

        leg = WalkLeg(
            from_name="Your location",
            to_name="Your destination",
            minutes=walk_min,
            path_points=path,
            directions=directions,
        )
        route = Route(legs=[leg], walk_minutes_total=walk_min)
        ranked_routes = [(walk_min, None, route)]

        prompt = build_prompt(
            origin=request.origin,
            destination=request.destination,
            train_arrivals=[],
            bus_arrivals=[],
            transit_mode="Walk",
            ranked_routes=ranked_routes,
            language=request.language,
            weather=walk_weather,
        )
        recommendation = None
        model_used = None
        if request.ai_enabled:
            recommendation, model_used = await _call_claude(claude_client, prompt, ranked_routes)

        response = _format_response(
            recommendation=recommendation,
            model_used=model_used,
            origin_coords=origin_coords,
            dest_coords=dest_coords,
            train_arrivals=[],
            bus_arrivals=[],
            n_train_errors=0,
            n_bus_errors=0,
            origin_stations=[],
            alerts=[],
            ranked_routes=ranked_routes,
            weather=walk_weather,
        )
        async with _store_lock:
            _response_cache[key] = (time.monotonic() + _CACHE_TTL_SECONDS, response)
            _response_cache.move_to_end(key)
            if len(_response_cache) > _CACHE_MAX_SIZE:
                _response_cache.popitem(last=False)
        return response

    (
        origin_stations, origin_bus_stops,
        dest_stations, dest_bus_stops, dest_match,
        origin_coords, dest_coords,
    ) = await _resolve_locations(loop, request)
    destination_label = dest_match or request.destination

    train_arrivals, bus_arrivals, n_train_errors, n_bus_errors = await _fetch_arrivals(
        request, origin_stations, origin_bus_stops
    )

    weather = await _safe_weather(origin_coords)

    ranked_routes = await _run_routing(
        request, origin_coords, dest_coords,
        origin_stations, origin_bus_stops, train_arrivals, bus_arrivals,
        weather=weather,
    )

    transfer_arrivals_combined = await _fetch_transfer_arrivals(ranked_routes)

    alert_ids = _alert_ids_from_routes(ranked_routes)
    alerts, route_statuses = await asyncio.gather(
        get_alerts(alert_ids),
        get_route_statuses(),
    )

    prompt = build_prompt(
        origin=request.origin,
        destination=destination_label,
        train_arrivals=train_arrivals,
        bus_arrivals=bus_arrivals,
        transit_mode=request.transit_mode,
        ranked_routes=ranked_routes or None,
        bus_fullness=request.bus_fullness,
        alerts=alerts,
        route_statuses=route_statuses,
        transfer_arrivals=transfer_arrivals_combined or None,
        language=request.language,
        weather=weather,
    )

    recommendation = None
    model_used = None
    if request.ai_enabled:
        recommendation, model_used = await _call_claude(claude_client, prompt, ranked_routes)

    response = _format_response(
        recommendation=recommendation,
        model_used=model_used,
        origin_coords=origin_coords,
        dest_coords=dest_coords,
        train_arrivals=train_arrivals,
        bus_arrivals=bus_arrivals,
        n_train_errors=n_train_errors,
        n_bus_errors=n_bus_errors,
        origin_stations=origin_stations,
        alerts=alerts,
        ranked_routes=ranked_routes,
        weather=weather,
    )

    # Assign then move_to_end so existing keys shift to the "newest" position
    # without a separate membership test. Lock prevents concurrent writes from
    # both evicting an item (double-pop) when the cache is exactly at capacity.
    async with _store_lock:
        _response_cache[key] = (time.monotonic() + _CACHE_TTL_SECONDS, response)
        _response_cache.move_to_end(key)
        if len(_response_cache) > _CACHE_MAX_SIZE:
            _response_cache.popitem(last=False)  # O(1) — drops the oldest insertion

    return response
