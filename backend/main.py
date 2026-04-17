import asyncio
import collections
import os
import time
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
from dotenv import load_dotenv
import anthropic

# load_dotenv() must be called before importing local modules.
# gtfs_loader.py reads GOOGLE_MAPS_API_KEY at module level (import time),
# so the .env file must be loaded into os.environ first.
load_dotenv()

from gtfs_loader import (
    resolve_location, geocode_google, NEIGHBORHOOD_COORDS,
    fuzzy_match_neighborhood,
)
from cta_client import get_train_arrivals, get_bus_arrivals
from transit_graph import (
    find_routes, find_bus_routes, find_bus_transfer_routes, warm_up, get_bus_stop_sequences,
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
_CACHE_TTL_SECONDS = 45
_CACHE_MAX_SIZE    = 500


def _cache_key(origin: str, destination: str, transit_mode: str, bus_fullness: str,
               byok: bool = False) -> str:
    # Include a BYOK flag so BYOK and shared-quota requests never share cache
    # entries — a non-BYOK user would otherwise be served a response whose
    # Claude call was paid for by a BYOK user (and vice-versa).
    return "|".join([
        origin.lower().strip(),
        destination.lower().strip(),
        transit_mode,
        bus_fullness,
        "byok" if byok else "",
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
    No locking needed — FastAPI runs on a single asyncio event loop and
    _check_rate_limit is called outside any await point, so no concurrent
    mutation can occur between the deque reads and the append.
    """
    if not _RATE_LIMIT_ENABLED:
        return True
    now = time.monotonic()
    window = _rate_store.setdefault(ip, collections.deque())
    # Evict timestamps older than one hour to bound memory growth
    while window and now - window[0] > 3600:
        window.popleft()
    # If all entries expired and the deque is now empty, remove the dict entry
    # so IPs that never return don't accumulate indefinitely.  `window` still
    # holds the deque reference, so the append below works for this request —
    # it just won't persist to _rate_store (next request starts fresh).
    if not window:
        del _rate_store[ip]
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
    coords = geocode_google(query)
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
    (line_code, station_mapid) -> {destNm: earliest_minutes}

    Groups all arrivals by destination so _rank_routes can select the one
    going in the correct direction rather than blindly taking the earliest.
    """
    lookup: dict[tuple[str, str], dict[str, int]] = {}
    for a in train_arrivals:
        key = (a.get("line_code", ""), a.get("station_mapid", ""))
        dest = a.get("destination", "")
        minutes = a["arrives_in_minutes"]
        dests = lookup.setdefault(key, {})
        if dest not in dests or minutes < dests[dest]:
            dests[dest] = minutes
    return lookup


def _rank_routes(
    routes: list,
    arrival_lookup: dict[tuple[str, str], dict[str, int]],
) -> list[tuple[float, int, object]]:
    """
    Add live wait time to each route and sort by total (walk + wait + transit).
    Returns list of (total_with_wait, wait_minutes, route).

    When multiple arrival directions exist at the boarding station (e.g. Howard
    vs 95th/Dan Ryan on the Red Line), uses the direction of the transit leg to
    select the correct one via a dot-product bearing test:
      - Compute vector A→B where A = boarding station, B = exit station
      - For each destNm, compute vector A→terminal
      - Pick the terminal whose direction is closest to A→B (positive dot product)
    Falls back to the earliest arrival if coordinates are unavailable.
    """
    ranked = []
    for route in routes:
        first_transit = next((l for l in route.legs if isinstance(l, TransitLeg)), None)
        # None = no live arrival data found; 0 = train/bus is Due right now
        wait: int | None = None
        if first_transit:
            key = (first_transit.line_code, first_transit.from_mapid)
            dest_map = arrival_lookup.get(key, {})

            if not dest_map:
                wait = None  # no live data for this station/line
            elif len(dest_map) == 1:
                # Only one direction at this station — no ambiguity
                wait = next(iter(dest_map.values()))
            else:
                # Multiple directions — use bearing to pick the right one
                from_coords = get_station_coords(first_transit.from_mapid)
                to_coords   = get_station_coords(first_transit.to_mapid)
                best_wait: int | None = None

                if from_coords and to_coords:
                    # Direction vector of this transit leg
                    dlat = to_coords[0] - from_coords[0]
                    dlon = to_coords[1] - from_coords[1]

                    if dlat == 0.0 and dlon == 0.0:
                        # Degenerate: boarding and alighting station share coordinates
                        print(f"[_rank_routes] degenerate bearing for leg "
                              f"{first_transit.from_mapid}→{first_transit.to_mapid}; "
                              f"falling back to min wait")
                    else:
                        best_score = float("-inf")
                        for dest_name, minutes in dest_map.items():
                            term = get_station_by_name(dest_name)
                            if term is None:
                                continue
                            # Vector from boarding station to this terminal
                            tlat = term[0] - from_coords[0]
                            tlon = term[1] - from_coords[1]
                            # Dot product > 0 means terminal is ahead of us
                            score = dlat * tlat + dlon * tlon
                            if score > best_score:
                                best_score = score
                                best_wait  = minutes

                # Fall back to earliest arrival if bearing test failed
                wait = best_wait if best_wait is not None else min(dest_map.values())

        total = route.total_minutes_no_wait + (wait if wait is not None else 0)
        ranked.append((total, wait, route))
    ranked.sort(key=lambda x: x[0])
    return ranked


def _rank_bus_routes(
    bus_ranked: list[tuple],
) -> list[tuple[float, "int | None", object]]:
    """
    Normalise wait semantics for bus routes returned by find_bus_routes() or
    find_bus_transfer_routes().

    find_bus_routes() internally computes wait from live arrivals and stores it
    as a plain int (defaulting to 0 when no data).  This function re-expresses
    the wait as int | None to match _rank_routes() output:
      - wait > 0  → keep as-is (bus is N minutes away)
      - wait == 0 → keep as 0 (bus is Due — not "no data"; bus routes are only
                    built when a live arrival exists, so 0 always means Due)
      - wait is None → keep as None (should not occur but handled defensively)

    The total is already correct (computed inside find_bus_routes as
    route.total_minutes_no_wait + wait_min).  We return it unchanged.

    Returns list of (total, wait, route) with wait typed as int | None,
    re-sorted by total ascending.
    """
    result: list[tuple] = []
    for total, wait, route in bus_ranked:
        normalised_wait: "int | None" = int(wait) if wait is not None else None
        result.append((float(total), normalised_wait, route))
    result.sort(key=lambda x: x[0])
    return result


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

    return (
        f"You are a helpful Chicago transit assistant. "
        f"A rider is at {origin} and wants to get to {destination}.\n\n"
        f"Rider preference: {mode_note}\n\n"
        f"{body}\n\n"
        "Lead with the single best option and explain why in plain English. "
        "Factor in total trip time including walking and waiting. "
        "Note any delays. Keep it to 3-4 sentences — the rider is probably standing outside."
    )


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/recommend")
async def recommend(request: RouteRequest, http_request: Request):
    # ── Rate limiting ──────────────────────────────────────────────────────────
    ip = _client_ip(http_request)
    if not _check_rate_limit(ip):
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please wait a minute before trying again.",
        )

    # ── BYOK — select Anthropic client for this request ────────────────────────
    # If BYOK is enabled and the user supplied a valid key, create a throwaway
    # client scoped to this request. Otherwise fall back to the shared singleton.
    # A new AsyncAnthropic() is cheap — it holds no persistent connection.
    byok_key = request.anthropic_api_key if _BYOK_ENABLED else None
    claude_client = (
        anthropic.AsyncAnthropic(api_key=byok_key)
        if byok_key
        else _claude_client
    )

    train_key = os.getenv("CTA_TRAIN_API_KEY", "")
    bus_key   = os.getenv("CTA_BUS_API_KEY", "")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")

    if not train_key:
        raise HTTPException(status_code=500, detail="CTA_TRAIN_API_KEY not configured in backend/.env")
    if not byok_key and (not anthropic_key or anthropic_key == "your_api_key_here"):
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured in backend/.env")
    if request.transit_mode in ("Bus", "All") and not bus_key:
        raise HTTPException(status_code=500, detail="CTA_BUS_API_KEY not configured in backend/.env")

    # ── Cache check (before any I/O) ──────────────────────────────────────────
    key = _cache_key(request.origin, request.destination, request.transit_mode, request.bus_fullness,
                     byok=bool(byok_key))
    cached = _response_cache.get(key)
    if cached and time.monotonic() < cached[0]:
        return {**cached[1], "cache_hit": True}
    # Evict stale entry if present so we don't carry dead keys
    if cached:
        del _response_cache[key]

    loop = asyncio.get_running_loop()
    origin_stations, origin_bus_stops, origin_match = await loop.run_in_executor(
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
    destination_label = dest_match or request.destination

    # ── Train arrivals ────────────────────────────────────────────────────────
    walk_lookup = {s["mapid"]: s.get("walk_minutes", 0) for s in origin_stations}

    n_train_errors = 0
    if request.transit_mode == "Bus":
        train_arrivals = []
    else:
        train_arrivals, n_train_errors = await get_train_arrivals(origin_stations, train_key)
        for a in train_arrivals:
            a["walk_minutes"] = walk_lookup.get(a.get("station_mapid"), 0)

    # ── Bus arrivals ──────────────────────────────────────────────────────────
    bus_arrivals: list[dict] = []
    n_bus_errors = 0
    if request.transit_mode in ("Bus", "All") and bus_key and origin_bus_stops:
        stop_ids = [s["stop_id"] for s in origin_bus_stops]
        bus_arrivals, n_bus_errors = await get_bus_arrivals(stop_ids, bus_key)

        # Apply bus_fullness filter
        if request.bus_fullness != "All":
            target_load = _FULLNESS_API_VALUES.get(request.bus_fullness, "")
            bus_arrivals = [
                a for a in bus_arrivals
                if a.get("psgld", "") == target_load
            ]

    # ── Routing engine ────────────────────────────────────────────────────────
    ranked_routes: list[tuple] = []

    origin_coords = await loop.run_in_executor(
        None, _coords_for_location, request.origin, origin_stations
    )
    dest_coords = await loop.run_in_executor(
        None, _coords_for_location, request.destination, dest_stations
    )

    if origin_coords and dest_coords:
        # Guard: same-location check (~100 m threshold using squared degree distance)
        dlat = origin_coords[0] - dest_coords[0]
        dlon = origin_coords[1] - dest_coords[1]
        if (dlat * dlat + dlon * dlon) < (0.001 ** 2):
            raise HTTPException(
                status_code=400,
                detail="Your origin and destination appear to be the same location.",
            )

        # Train routing
        if request.transit_mode != "Bus":
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
            except Exception:
                traceback.print_exc()

        # Bus routing
        if request.transit_mode in ("Bus", "All") and bus_arrivals and origin_bus_stops:
            try:
                bus_ranked = find_bus_routes(
                    origin_lat=origin_coords[0],
                    origin_lon=origin_coords[1],
                    dest_lat=dest_coords[0],
                    dest_lon=dest_coords[1],
                    bus_arrivals=bus_arrivals,
                    origin_bus_stops=origin_bus_stops,
                    n_routes=3,
                )
                # If no direct bus routes found, try bus+bus transfer routing
                if not bus_ranked:
                    try:
                        bus_ranked = find_bus_transfer_routes(
                            origin_lat=origin_coords[0],
                            origin_lon=origin_coords[1],
                            dest_lat=dest_coords[0],
                            dest_lon=dest_coords[1],
                            bus_arrivals=bus_arrivals,
                            origin_bus_stops=origin_bus_stops,
                            n_routes=3,
                        )
                    except Exception:
                        traceback.print_exc()
                # Normalise bus wait semantics (int | None) to match
                # _rank_routes() output before merging with train results.
                if bus_ranked:
                    bus_ranked = _rank_bus_routes(bus_ranked)
                ranked_routes = sorted(
                    ranked_routes + bus_ranked,
                    key=lambda x: x[0],
                )[:5]

                # Deduplicate routes with identical leg fingerprints — the
                # unified graph may surface bus-only paths that duplicate
                # find_bus_routes() results; keep only the first occurrence.
                def _route_fingerprint(route):
                    return tuple(
                        (leg.leg_type,
                         getattr(leg, "line_code", ""),
                         getattr(leg, "from_mapid", ""),
                         getattr(leg, "to_mapid", ""))
                        for leg in route.legs
                    )
                seen_fps: set = set()
                deduped: list = []
                for _total, _wait, _route in ranked_routes:
                    fp = _route_fingerprint(_route)
                    if fp not in seen_fps:
                        seen_fps.add(fp)
                        deduped.append((_total, _wait, _route))
                ranked_routes = deduped
            except Exception:
                traceback.print_exc()

    # ── Build prompt and call Claude ──────────────────────────────────────────
    prompt = build_prompt(
        origin=request.origin,
        destination=destination_label,
        train_arrivals=train_arrivals,
        bus_arrivals=bus_arrivals,
        transit_mode=request.transit_mode,
        ranked_routes=ranked_routes or None,
        bus_fullness=request.bus_fullness,
    )

    try:
        message = await claude_client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        text_block = next((c for c in message.content if hasattr(c, "text")), None)
        if not text_block:
            raise ValueError("No text block in Claude response")
        recommendation = text_block.text
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=502, detail=f"Claude API error: {exc}")

    # ── Response ──────────────────────────────────────────────────────────────
    response = {
        "recommendation": recommendation,
        "origin_coords": list(origin_coords) if origin_coords else None,
        "dest_coords":   list(dest_coords)   if dest_coords   else None,
        "train_arrivals": train_arrivals,
        "bus_arrivals": bus_arrivals,
        "train_errors": n_train_errors,
        "bus_errors":   n_bus_errors,
        "origin_stations": [s["name"] for s in origin_stations],
        "routes": [
            {
                "total_minutes": round(total),
                "wait_minutes": wait,
                "transfers": route.transfers,
                "legs": [
                    {
                        "type": leg.leg_type,
                        "line": getattr(leg, "line", None),
                        "line_code": getattr(leg, "line_code", None),
                        "from": leg.from_name if isinstance(leg, WalkLeg) else leg.from_station,
                        "to":   leg.to_name   if isinstance(leg, WalkLeg) else leg.to_station,
                        "minutes": round(leg.minutes, 1),
                        **(
                            {
                                "shape":       leg.shape_points,
                                "from_coords": leg.shape_points[0]  if leg.shape_points else None,
                                "to_coords":   leg.shape_points[-1] if leg.shape_points else None,
                            }
                            if isinstance(leg, TransitLeg)
                            else {"path": leg.path_points, "directions": leg.directions, "exit_label": leg.exit_label}
                        ),
                    }
                    for leg in route.legs
                ],
            }
            for total, wait, route in ranked_routes
        ],
    }

    # ── Cache write ───────────────────────────────────────────────────────────
    # Re-insert at end so existing keys move to the "newest" position.
    if key in _response_cache:
        del _response_cache[key]
    _response_cache[key] = (time.monotonic() + _CACHE_TTL_SECONDS, response)
    if len(_response_cache) > _CACHE_MAX_SIZE:
        _response_cache.popitem(last=False)   # O(1) — drops the oldest insertion

    return response
