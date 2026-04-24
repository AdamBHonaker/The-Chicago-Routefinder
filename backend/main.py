import asyncio
import collections
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
from dotenv import load_dotenv
import anthropic

# load_dotenv() must be called before importing local modules.
# gtfs_loader.py reads GOOGLE_MAPS_API_KEY at module level (import time),
# so the .env file must be loaded into os.environ first.
load_dotenv()

import dau

from gtfs_loader import (
    resolve_location, geocode_google, NEIGHBORHOOD_COORDS,
    fuzzy_match_neighborhood, _normalize_street_abbr,
)
from cta_client import get_train_arrivals, get_bus_arrivals, get_alerts, _TRAIN_LINE_TO_ALERT_ID, LINE_NAMES
from transit_graph import (
    find_routes, find_bus_transfer_routes, warm_up, get_bus_stop_sequences,
    WalkLeg, TransitLeg, get_station_coords, get_station_by_name,
)

# Anthropic client — created once at startup, reused across all requests
_claude_client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))

# ---------------------------------------------------------------------------
# Response cache
# ---------------------------------------------------------------------------
# key → (expires_at: float via time.monotonic(), response: dict)
# OrderedDict preserves insertion order so eviction of the oldest entry is O(1)
# via popitem(last=False) rather than O(n) via min() over all entries.
_response_cache: collections.OrderedDict[str, tuple[float, dict]] = collections.OrderedDict()
_CACHE_TTL_SECONDS = 45       # seconds
_CACHE_MAX_SIZE    = 500      # entries

# Squared degree threshold for treating origin == destination (≈0.07 miles at Chicago's latitude).
_SAME_LOCATION_THRESHOLD_DEG2: float = 0.001 ** 2   # degrees²


def _cache_key(origin: str, destination: str, transit_mode: str, bus_fullness: str,
               byok: bool = False, ai_enabled: bool = False, language: str = "en") -> str:
    # Include a BYOK flag so BYOK and shared-quota requests never share cache
    # entries — a non-BYOK user would otherwise be served a response whose
    # Claude call was paid for by a BYOK user (and vice-versa).
    # Include ai_enabled because the recommendation field differs between AI-on and AI-off responses.
    # Include language so responses in different languages are cached separately.
    return "|".join([
        origin.lower().strip(),
        destination.lower().strip(),
        transit_mode,
        bus_fullness,
        "byok" if byok else "",
        "ai" if ai_enabled else "",
        language or "en",
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
    """Extract client IP, honoring X-Forwarded-For when behind Railway/Vercel proxy."""
    forwarded = http_request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
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
    # Per-minute check (count entries in the last 60 s)
    recent = sum(1 for t in window if now - t <= 60)
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[main] Warming up transit graph ...")
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, warm_up)
    print("[main] Ready.")
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)


_VALID_TRANSIT_MODES  = {"All", "Train", "Bus"}
_VALID_BUS_FULLNESS   = {"All", "Empty", "Half-Full", "Full"}


class RouteRequest(BaseModel):
    origin: str
    destination: str
    transit_mode: str = "All"   # "All" | "Train" | "Bus"
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
        if v is not None:
            v = v.strip()
            if not v:
                return None
            if not v.startswith("sk-ant-"):
                raise ValueError(
                    "anthropic_api_key does not look like a valid Anthropic API key"
                )
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
) -> dict[tuple[str, str], dict[str, int]]:
    """
    (line_code, station_mapid) -> {destNm: earliest_catchable_minutes}

    Groups arrivals by destination so _rank_routes can select the one going in
    the correct direction.  Arrivals where arrives_in_minutes < walk_minutes
    are skipped — the user cannot reach the station in time for those trains.
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
    contains exactly one TransitLeg (direct ride, no transfer). Walk legs are
    not counted. Simple queries are routed to Haiku for cost savings; all
    others use Sonnet.
    """
    if len(ranked_routes) != 1:
        return False
    _, _, route = ranked_routes[0]
    transit_legs = [leg for leg in route.legs if isinstance(leg, TransitLeg)]
    return len(transit_legs) == 1


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
    if not train_key:
        raise HTTPException(status_code=500, detail="CTA_TRAIN_API_KEY not configured in backend/.env")
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

    origin_coords = await loop.run_in_executor(
        None, _coords_for_location, request.origin, origin_stations
    )
    dest_coords = await loop.run_in_executor(
        None, _coords_for_location, request.destination, dest_stations
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


async def _run_routing(
    request: RouteRequest,
    origin_coords: tuple | None,
    dest_coords: tuple | None,
    origin_stations: list[dict],
    origin_bus_stops: list[dict],
    train_arrivals: list[dict],
    bus_arrivals: list[dict],
) -> list[tuple]:
    """Run the unified routing engine and return ranked (total, wait, route) tuples."""
    ranked_routes: list[tuple] = []
    if not origin_coords or not dest_coords:
        return ranked_routes

    # Unified-graph routing (trains + direct bus + intermodal).
    # Feature J (2026-04-18): find_routes() is the sole source of direct
    # bus-only itineraries; Bus mode post-filters to drop routes with train legs.
    try:
        arrival_lookup = _build_arrival_lookup(train_arrivals)
        ranked_routes = _rank_routes(
            find_routes(
                origin_lat=origin_coords[0],
                origin_lon=origin_coords[1],
                dest_lat=dest_coords[0],
                dest_lon=dest_coords[1],
                origin_stations=origin_stations,
                n_routes=5,
            ),
            arrival_lookup,
        )
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
            transfer_ranked = find_bus_transfer_routes(
                origin_lat=origin_coords[0],
                origin_lon=origin_coords[1],
                dest_lat=dest_coords[0],
                dest_lon=dest_coords[1],
                bus_arrivals=bus_arrivals,
                origin_bus_stops=origin_bus_stops,
                n_routes=2,
            )
            if transfer_ranked:
                transfer_ranked = _rank_bus_routes(transfer_ranked)
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
) -> dict:
    """Assemble the final JSON-serialisable response dict."""
    return {
        "recommendation": recommendation,
        "model_used": model_used,
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
        lines.append(
            f"Option {i}: {' | '.join(leg_parts)}{wait_note} "
            f"[~{total:.0f} min total{xfers}]"
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
    transfer_arrivals: list[dict] | None = None,
    language: str | None = None,
) -> str:
    mode_constraints = {
        "Train": "The rider wants TRAIN options only. Do not mention buses.",
        "Bus":   "The rider wants BUS options only. Do not mention trains.",
        "All":   "The rider is open to trains and buses.",
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
    significant_alerts = [a for a in (alerts or []) if a.get("severity_score", 0) >= 5]
    if significant_alerts:
        alert_lines = []
        for a in significant_alerts:
            prefix = "⚠ MAJOR — " if a.get("is_major") else ""
            impact = f" [{a['impact']}]" if a.get("impact") else ""
            alert_lines.append(f"  * {prefix}{a['headline']}{impact}")
        alert_section = "\n\nActive service alerts on your route:\n" + "\n".join(alert_lines)

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

    return (
        f"You are a helpful Chicago transit assistant. "
        f"A rider is at {origin} and wants to get to {destination}.\n\n"
        f"Rider preference: {mode_note}\n\n"
        f"{body}{alert_section}\n\n"
        "Lead with the single best option and explain why in plain English. "
        "Factor in total trip time including walking and waiting. "
        "Note any delays or active service alerts. Keep it to 3-4 sentences — the rider is probably standing outside."
        f"{lang_instruction}"
    )


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


@app.get("/admin/dau")
async def admin_dau(authorization: str | None = Header(default=None)):
    token = os.getenv("DAU_ADMIN_TOKEN", "")
    expected = f"Bearer {token}" if token else None
    if not expected or authorization != expected:
        raise HTTPException(status_code=403, detail="Forbidden")
    return await dau.get_counts()


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
        language=request.language or "en",
    )

    # Hold _store_lock for the rate-limit check and cache read atomically.
    # This prevents two concurrent requests with the same key from both seeing a
    # cache miss and both launching the full expensive pipeline (stampede), and
    # ensures the rate-limit timestamp is written before any await yields control.
    async with _store_lock:
        if not _check_rate_limit(ip):
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please wait a minute before trying again.",
            )
        cached = _response_cache.get(key)
        if cached:
            if time.monotonic() < cached[0]:
                _response_cache.move_to_end(key)  # promote to MRU position (LRU eviction)
                return {**cached[1], "cache_hit": True}
            _response_cache.pop(key, None)  # evict stale entry

    loop = asyncio.get_running_loop()
    (
        origin_stations, origin_bus_stops,
        dest_stations, dest_bus_stops, dest_match,
        origin_coords, dest_coords,
    ) = await _resolve_locations(loop, request)
    destination_label = dest_match or request.destination

    train_arrivals, bus_arrivals, n_train_errors, n_bus_errors = await _fetch_arrivals(
        request, origin_stations, origin_bus_stops
    )

    ranked_routes = await _run_routing(
        request, origin_coords, dest_coords,
        origin_stations, origin_bus_stops, train_arrivals, bus_arrivals,
    )

    transfer_arrivals_combined = await _fetch_transfer_arrivals(ranked_routes)

    alert_ids = _alert_ids_from_routes(ranked_routes)
    alerts: list[dict] = await get_alerts(alert_ids) if alert_ids else []

    prompt = build_prompt(
        origin=request.origin,
        destination=destination_label,
        train_arrivals=train_arrivals,
        bus_arrivals=bus_arrivals,
        transit_mode=request.transit_mode,
        ranked_routes=ranked_routes or None,
        bus_fullness=request.bus_fullness,
        alerts=alerts,
        transfer_arrivals=transfer_arrivals_combined or None,
        language=request.language,
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
