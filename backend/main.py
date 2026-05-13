import asyncio
import logging
import os
import time
import xml.etree.ElementTree as ET
from contextlib import asynccontextmanager
from datetime import datetime

import aiohttp
from cachetools import TTLCache

from fastapi import FastAPI, HTTPException, Request, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from dotenv import load_dotenv
import anthropic


# load_dotenv() must be called before importing local modules.
# gtfs_loader.py reads GOOGLE_MAPS_API_KEY at module level (import time),
# so the .env file must be loaded into os.environ first.
load_dotenv()

from gtfs_loader import (
    resolve_location, geocode_google, reverse_geocode_google, NEIGHBORHOOD_COORDS,
    fuzzy_match_neighborhood, _load_stops, coords_for_location,
)
from geocode_text import _normalize_street_abbr
from cta_client import get_train_arrivals, get_bus_arrivals, get_alerts, get_route_statuses, TRAIN_LINE_TO_ALERT_ID, LINE_NAMES, init_session as _init_cta_session, close_session as _close_cta_session, _get_session as _get_cta_session
from transit_graph import (
    find_routes, find_routes_with_status, find_bus_transfer_routes, warm_up,
    get_bus_stop_sequences,
    WalkLeg, TransitLeg, Route, get_station_coords, get_station_by_name,
    get_last_departure, get_stop_sequence_position,
    to_parent_mapid,
    compute_route_total,
)
from walking import (
    walk_minutes as _walk_minutes,
    walk_directions as _walk_directions,
    walk_path as _walk_path,
    walk_all as _walk_all,
    get_fallback_metrics as _walk_fallback_metrics,
)
from weather_service import WeatherService, WeatherContext, PrecipitationType
from utils import CHICAGO_TZ as _CHICAGO_TZ, TRANSFER_PENALTY_MINUTES

logger = logging.getLogger(__name__)

# API keys and model names read once at startup — these never change at runtime.
_CTA_TRAIN_KEY        = os.getenv("CTA_TRAIN_API_KEY", "")
_CTA_BUS_KEY          = os.getenv("CTA_BUS_API_KEY", "")
_ANTHROPIC_KEY        = os.getenv("ANTHROPIC_API_KEY", "")
_CLAUDE_SIMPLE_MODEL  = os.getenv("CLAUDE_SIMPLE_MODEL",  "claude-haiku-4-5-20251001")
_CLAUDE_COMPLEX_MODEL = os.getenv("CLAUDE_COMPLEX_MODEL", "claude-sonnet-4-6")

# Anthropic client — created once at startup, reused across all requests
_claude_client = anthropic.AsyncAnthropic(api_key=_ANTHROPIC_KEY)

# Weather service — module-level singleton, manages its own TTL caches internally
weather_service = WeatherService()

# ---------------------------------------------------------------------------
# Response cache
# ---------------------------------------------------------------------------
_CACHE_TTL_SECONDS = 120      # seconds
_CACHE_MAX_SIZE    = 500      # entries
_response_cache: TTLCache = TTLCache(maxsize=_CACHE_MAX_SIZE, ttl=_CACHE_TTL_SECONDS)
# Set RESPONSE_CACHE_ENABLED=false to bypass the cache (e.g. to reduce Railway memory while
# traffic is low). Default true. Re-enable by setting the var to "true" or removing it.
_CACHE_ENABLED: bool = os.getenv("RESPONSE_CACHE_ENABLED", "true").lower() == "true"

# Cache hit/miss counters — logged every _CACHE_LOG_INTERVAL requests for tuning.
_cache_hits:   int = 0
_cache_misses: int = 0
_cache_requests_total: int = 0
_CACHE_LOG_INTERVAL = 100


def _maybe_log_cache_stats() -> None:
    """Emit a one-line cache hit-rate summary every _CACHE_LOG_INTERVAL requests."""
    if _cache_requests_total % _CACHE_LOG_INTERVAL != 0:
        return
    print(
        f"[cache] {_cache_requests_total} requests | "
        f"hits={_cache_hits} misses={_cache_misses} "
        f"hit_rate={_cache_hits/_cache_requests_total:.1%} "
        f"size={len(_response_cache)}"
    )

# Squared degree threshold for treating origin == destination (≈0.07 miles at Chicago's latitude).
_SAME_LOCATION_THRESHOLD_DEG2: float = 0.001 ** 2   # degrees²

# ---------------------------------------------------------------------------
# /stop-arrivals cache (Feature Pinned Stops)
# ---------------------------------------------------------------------------
_STOP_ARRIVALS_TTL = 30   # seconds
_stop_arrivals_cache: TTLCache = TTLCache(maxsize=200, ttl=_STOP_ARRIVALS_TTL)


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
        f"{round(walk_speed, 2):.2f}",
    ])

# ---------------------------------------------------------------------------
# Rate limiting + per-request analytics middlewares — owned by their own
# modules so a future tweak (Redis, token-bucket, additional middleware)
# touches one file. Everything imported here is re-used inside /recommend.
# ---------------------------------------------------------------------------
from rate_limit import (
    _check_daily_quota,
    _check_events_rate_limit,
    _check_geocode_rate_limit,
    _check_rate_limit,
    _client_ip,
    _daily_quota_store,
    _geocode_lock,
    _geocode_rate_store,
    _rate_store,
    _store_lock,
)
import events as _events
import sessions as _sessions


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
#   ALLOWED_ORIGINS=https://the-chicago-routefinder.vercel.app
_extra_origins = os.getenv("ALLOWED_ORIGINS", "")
_extra_origin_list = [o.strip() for o in _extra_origins.split(",") if o.strip()]
# Fail-closed in production: if ALLOWED_ORIGINS is unset, refuse to start so a
# misconfigured deployment never falls back to the localhost-only allowlist.
if os.getenv("APP_ENV") == "production" and not _extra_origin_list:
    raise RuntimeError(
        "ALLOWED_ORIGINS env var must be set in production "
        "(e.g. ALLOWED_ORIGINS=https://your-frontend.vercel.app)."
    )
ALLOWED_ORIGINS = ["http://localhost:5173", "http://localhost:5174"] + _extra_origin_list

# Hard cap on POST body size. /recommend bodies are <1 KB in normal use; 16 KB
# leaves generous headroom while preventing OOM/DoS via giant payloads.
_MAX_REQUEST_BYTES = 16 * 1024


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
        nl = name.lower()
        suggestion = {"label": name, "value": name, "type": label_type, "_nl": nl, "_words": nl.split()}
        idx = len(master)
        master.append(suggestion)
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
    await weather_service.close()


app = FastAPI(lifespan=lifespan)

# Request-size cap, security headers, and analytics dispatcher all live in
# middleware.py. CORS stays here because allow_origins is built from a
# main-only env var and including it in the helper would just push that
# coupling into another module.
from middleware import register_middlewares
register_middlewares(
    app,
    allowed_origins=ALLOWED_ORIGINS,
    max_request_bytes=_MAX_REQUEST_BYTES,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["POST", "GET"],
    allow_headers=["Content-Type", "Accept", "Accept-Language", "Authorization"],
    # FEAT-001: the session cookie is httpOnly + Secure, and SameSite=None in
    # production (so it survives the cross-site Vercel↔Railway hop) or Lax in
    # local dev. For the browser to send/receive it cross-origin the response
    # must include `Access-Control-Allow-Credentials: true`, and ALLOWED_ORIGINS
    # must be an explicit list (not "*"). Both conditions hold here.
    allow_credentials=True,
    max_age=3600,
)

# Admin and public-stats endpoints — see routes/admin.py and routes/stats.py.
from routes.admin import router as _admin_router
from routes.stats import router as _stats_router
app.include_router(_admin_router)
app.include_router(_stats_router)

# FEAT-018: published CTA schedule viewer endpoints.
from schedule import router as _schedule_router
app.include_router(_schedule_router)


_VALID_TRANSIT_MODES  = {"All", "Train", "Bus", "Walk"}
_VALID_BUS_FULLNESS   = {"All", "Empty", "Half-Full", "Full"}


class RouteRequest(BaseModel):
    origin: str = Field(..., min_length=1, max_length=200)
    destination: str = Field(..., min_length=1, max_length=200)
    transit_mode: str = "All"   # "All" | "Train" | "Bus" | "Walk"
    bus_fullness: str = "All"   # "All" | "Empty" | "Half-Full" | "Full"
    # NOTE: BYOK keys used to live on this model as `anthropic_api_key`. They
    # now arrive via the Authorization: Bearer header instead, so the body
    # never carries credentials. Pydantic ignores unknown fields by default,
    # so older clients that still include the field won't 422 — the value is
    # just dropped on the floor.
    # AI toggle — when False (default), the Claude call is skipped entirely.
    # response.recommendation will be null. Future paywall gate lives here.
    ai_enabled: bool = False
    # BCP-47 language code (e.g. "es", "ar", "ja"). When non-null and not "en",
    # build_prompt() appends a language instruction so Claude responds in that language.
    language: str | None = Field(default=None, max_length=20)
    # Walking pace multiplier. 1.0 = standard (~15 min/mile). Applied as:
    #   adjusted_minutes = baseline_minutes / walk_speed
    # Slow: 0.75 (33% longer), Standard: 1.0 (no-op), Brisk: 1.25 (20% shorter).
    walk_speed: float = Field(default=1.0, ge=0.5, le=2.0)
    # Optional planned departure time, Chicago wall-clock (BUG-051). When set,
    # the routing engine picks the service-period graph variant (weekday peak,
    # weekday midday, weekday evening, weekend, or owl) whose service window
    # contains this time. None → use server-side datetime.now(CHICAGO_TZ).
    # ISO-8601 strings are accepted by Pydantic; naive values are treated as
    # already Chicago-local; tz-aware values are converted to Chicago time.
    departure_time: datetime | None = None

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


# BUG-046 thresholds for _pick_wait robustness.
# _PICK_WAIT_SHORT_HOP_DEG: if the boarding→exit vector is shorter than this
#   (≈0.35 mi in lat/lon degrees), the bearing is noise-sensitive — use the
#   route's further-downstream station as a longer baseline if available.
# _PICK_WAIT_AMBIGUOUS_MARGIN: minimum gap between the top two normalized
#   cosine similarities. Below this, the direction is genuinely ambiguous
#   and we fall back to the earliest arrival across all directions.
_PICK_WAIT_SHORT_HOP_DEG = 0.005
_PICK_WAIT_AMBIGUOUS_MARGIN = 0.15


def _pick_wait(
    dest_map: dict[str, int],
    from_mapid: str,
    to_mapid: str,
    fallback_to_mapid: str | None = None,
) -> int | None:
    """
    Pick live wait minutes from a destination→minutes map using a normalized
    cosine-similarity bearing test to resolve multi-direction stations.
    Returns None when dest_map is empty (no live data).

    When multiple arrival directions exist (e.g. Howard vs 95th/Dan Ryan on
    the Red Line), selects the terminal whose unit-bearing from the boarding
    station is most aligned with the boarding→exit unit-bearing.

    BUG-046 guards against fragile selection at near-orthogonal vectors:
      * If the boarding→exit vector is very short (one- or two-stop hop),
        fallback_to_mapid (a further-downstream station from the same route)
        is used for a longer, more stable baseline vector when provided.
      * Comparisons use normalized cosine similarity, not raw dot products,
        so vector magnitudes do not dominate. If the top two scores differ
        by less than _PICK_WAIT_AMBIGUOUS_MARGIN, the direction is genuinely
        ambiguous and we return the earliest arrival across directions —
        matching user expectations of "show the train coming sooner".

    Falls back to earliest arrival if coordinates are unavailable.
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
    dmag = (dlat * dlat + dlon * dlon) ** 0.5
    if dmag < _PICK_WAIT_SHORT_HOP_DEG and fallback_to_mapid and fallback_to_mapid != to_mapid:
        far = get_station_coords(fallback_to_mapid)
        if far:
            flat = far[0] - from_coords[0]
            flon = far[1] - from_coords[1]
            fmag = (flat * flat + flon * flon) ** 0.5
            if fmag > dmag:
                dlat, dlon, dmag = flat, flon, fmag
    if dmag == 0.0:
        return min(dest_map.values())
    scored: list[tuple[float, int]] = []
    for dest_name, minutes in dest_map.items():
        term = get_station_by_name(dest_name)
        if term is None:
            continue
        tlat = term[0] - from_coords[0]
        tlon = term[1] - from_coords[1]
        tmag = (tlat * tlat + tlon * tlon) ** 0.5
        if tmag == 0.0:
            continue
        cos_sim = (dlat * tlat + dlon * tlon) / (dmag * tmag)
        scored.append((cos_sim, minutes))
    if not scored:
        return min(dest_map.values())
    # BUG-060: if every candidate points opposite the boarding→exit vector,
    # the "highest" cosine similarity is still the least-wrong of two wrong
    # answers — fall back to the earliest arrival instead.
    scored = [(cs, m) for cs, m in scored if cs > 0.0]
    if not scored:
        return min(dest_map.values())
    scored.sort(key=lambda x: x[0], reverse=True)
    if len(scored) >= 2 and (scored[0][0] - scored[1][0]) < _PICK_WAIT_AMBIGUOUS_MARGIN:
        return min(dest_map.values())
    return scored[0][1]


def _route_last_transit_to_mapid(route) -> str | None:
    """Return the to_mapid of the last TransitLeg in the route, or None."""
    for leg in reversed(route.legs):
        if isinstance(leg, TransitLeg):
            return leg.to_mapid
    return None


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
            final_to = _route_last_transit_to_mapid(route)
            wait = _pick_wait(
                dest_map,
                first_transit.from_mapid,
                first_transit.to_mapid,
                fallback_to_mapid=final_to if final_to != first_transit.to_mapid else None,
            )
        if wait is not None:
            first_walk = next(
                (l.minutes for l in route.legs
                 if isinstance(l, WalkLeg) and l.from_name == "Your location"),
                0.0,
            )
            station_wait = max(0.0, wait - first_walk)
        else:
            station_wait = 0.0
        # Per-transfer waits are unknown at this point; compute_route_total fills
        # each one with the shared TRANSFER_PENALTY_MINUTES fallback.
        # _apply_transfer_wait_estimates later replaces those fallbacks with live
        # data — also through compute_route_total — keeping the formula in one place.
        total = compute_route_total(route, station_wait)
        ranked.append((total, wait, route))
    ranked.sort(key=lambda x: x[0])
    return ranked


def _apply_transfer_wait_estimates(
    ranked_routes: list[tuple],
) -> list[tuple[float, "int | None", object]]:
    """Re-total each route using live transfer-leg waits when available.

    Called after _fetch_transfer_arrivals() has annotated each transit leg
    (other than the first) with leg.transfer_wait_minutes from live CTA data.
    For each route, rebuilds the total via compute_route_total() — the single
    arithmetic authority — substituting live transfer waits where available
    and falling back to TRANSFER_PENALTY_MINUTES otherwise.

    The first-leg wait baked into the previous `total` is recovered by
    subtracting compute_route_total's estimate-only baseline; this keeps
    `route.total_minutes_no_wait` arithmetic inside compute_route_total
    (BUG-050 invariant).

    Returns a re-sorted list of (total, wait, route) tuples.
    """
    updated: list[tuple[float, "int | None", object]] = []
    for total, wait, route in ranked_routes:
        if route.transfers <= 0:
            updated.append((total, wait, route))
            continue
        # Recover first_leg_wait without touching route.total_minutes_no_wait
        # directly: the previous total was compute_route_total(route, fl, None),
        # so fl = total - compute_route_total(route, 0, None).
        first_leg_wait = total - compute_route_total(route, 0.0, None)
        # Collect live transfer waits per non-first transit leg, in leg order.
        live_waits: list = []
        seen_first = False
        for leg in route.legs:
            if not isinstance(leg, TransitLeg):
                continue
            if not seen_first:
                seen_first = True
                continue
            live_waits.append(leg.transfer_wait_minutes)
        adjusted = compute_route_total(route, first_leg_wait, live_waits)
        updated.append((adjusted, wait, route))
    updated.sort(key=lambda x: x[0])
    return updated


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


# Prompt construction, language map, crowdedness cache, and all related
# formatting helpers all live in prompt_builder.py.
from prompt_builder import (
    LANGUAGE_NAMES,
    _crowdedness_for_routes,
    _departure_window_hint,
    _format_bus_arrivals,
    _format_routes,
    _format_transfer_arrivals,
    _format_weather_for_prompt,
    _get_crowdedness_period,
    _is_simple_query,
    build_prompt,
)


def _alert_ids_from_routes(ranked_routes: list[tuple]) -> list[str]:
    """Return deduplicated Alerts API route ids for all transit legs in ranked_routes."""
    seen: set[str] = set()
    ids: list[str] = []
    for _total, _wait, route in ranked_routes:
        for leg in route.legs:
            if not isinstance(leg, TransitLeg):
                continue
            code = leg.line_code or ""
            alert_id = TRAIN_LINE_TO_ALERT_ID.get(code, code)
            if alert_id and alert_id not in seen:
                seen.add(alert_id)
                ids.append(alert_id)
    return ids


# ---------------------------------------------------------------------------
# recommend() sub-steps — each handles one distinct concern
# ---------------------------------------------------------------------------

def _validate_api_keys(request: RouteRequest, byok_key: str | None) -> None:
    """Raise HTTPException if any required API key is absent."""
    train_key     = _CTA_TRAIN_KEY
    bus_key       = _CTA_BUS_KEY
    anthropic_key = _ANTHROPIC_KEY
    if not train_key and request.transit_mode != "Walk":
        raise HTTPException(status_code=500, detail="CTA_TRAIN_API_KEY not configured in backend/.env")
    if byok_key and not byok_key.startswith("sk-ant-"):
        raise HTTPException(status_code=422, detail="Invalid API key")
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
    (
        (origin_stations, origin_bus_stops, _, origin_coords),
        (dest_stations,   dest_bus_stops,   dest_match, dest_coords),
    ) = await asyncio.gather(
        loop.run_in_executor(None, resolve_location, request.origin),
        loop.run_in_executor(None, resolve_location, request.destination),
    )
    if not origin_stations and not origin_bus_stops:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Could not find CTA stops near '{request.origin}'. "
                "Try a neighborhood name like 'Wrigleyville', 'Lincoln Park', or 'River North'."
            ),
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

    # If resolve_location produced stations but no coords (rare — e.g. the
    # geocoder cache has a None entry but find_nearest_* still returned hits
    # via a previous resolution path), fall back to coords_for_location's
    # station-centroid logic so routing still has a starting point.
    if origin_coords is None or dest_coords is None:
        fallback_origin, fallback_dest = await asyncio.gather(
            loop.run_in_executor(None, coords_for_location, request.origin, origin_stations),
            loop.run_in_executor(None, coords_for_location, request.destination, dest_stations),
        )
        origin_coords = origin_coords or fallback_origin
        dest_coords   = dest_coords   or fallback_dest

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
    train_key   = _CTA_TRAIN_KEY
    bus_key     = _CTA_BUS_KEY
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
    dest_bus_stops: list[dict] | None = None,
) -> tuple[list[tuple], dict]:
    """Run the unified routing engine and return (ranked_routes, status_info).

    `status_info` carries the BUG-047 routing-coverage signal:
        {"status": "ok" | "out_of_coverage" | "no_path",
         "side":   "origin" | "destination" | "both" | None,
         "max_radius_searched": float | None}
    so the API response, prompt builder, and frontend can surface a clear
    explanation for out-of-coverage queries instead of an unexplained blank
    result.
    """
    ranked_routes: list[tuple] = []
    status_info: dict = {"status": "ok", "side": None, "max_radius_searched": None}
    if not origin_coords or not dest_coords:
        return ranked_routes, status_info

    precip_factor = _precip_walk_factor(weather)
    effective_speed = request.walk_speed * precip_factor

    # Unified-graph routing (trains + direct bus + intermodal).
    # Feature J (2026-04-18): find_routes() is the sole source of direct
    # bus-only itineraries; Bus mode post-filters to drop routes with train legs.
    try:
        bus_stop_walk_map = {s["stop_id"]: s["walk_minutes"] for s in origin_bus_stops}
        arrival_lookup = _build_arrival_lookup(train_arrivals, bus_arrivals, bus_stop_walk_map)
        # BUG-047: capture the typed routing result so out-of-coverage is
        # surfaced explicitly rather than being indistinguishable from a
        # transient backend failure.
        routing_result = find_routes_with_status(
            origin_lat=origin_coords[0],
            origin_lon=origin_coords[1],
            dest_lat=dest_coords[0],
            dest_lon=dest_coords[1],
            origin_stations=origin_stations,
            n_routes=5,
            origin_bus_stops=origin_bus_stops,
            dest_bus_stops=dest_bus_stops,
            effective_speed=effective_speed,
            departure_time=request.departure_time,
        )
        raw_routes = routing_result.routes
        status_info = {
            "status": routing_result.status,
            "side": routing_result.side,
            "max_radius_searched": routing_result.max_radius_searched,
        }
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
                effective_speed=effective_speed,
            )
            if transfer_ranked_raw:
                _scale_walk_legs(
                    [r for _t, _w, r in transfer_ranked_raw],
                    effective_speed,
                )
                # Rebuild totals after walk scaling using compute_route_total —
                # the single arithmetic authority shared with _rank_routes and
                # _apply_transfer_wait_estimates. compute_route_total fills any
                # missing per-transfer waits with TRANSFER_PENALTY_MINUTES, so
                # this matches the train-route shape and keeps the live-wait
                # adjustment step correct for bus+bus routes too (BUG-050).
                transfer_ranked_raw = [
                    (compute_route_total(route, w or 0), w, route)
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

    # BUG-047: if bus+bus transfers salvaged routes after the unified graph
    # came back out_of_coverage, promote status back to "ok" so the API
    # response/UI doesn't claim no coverage when we actually have results.
    if ranked_routes and status_info.get("status") != "ok":
        status_info = {"status": "ok", "side": None, "max_radius_searched": None}

    return ranked_routes, status_info


async def _fetch_transfer_arrivals(ranked_routes: list[tuple]) -> list[dict]:
    """Fetch live arrivals at transfer stops (Feature D) and annotate legs in-place.

    Returns combined train + bus transfer arrival dicts.
    """
    if not ranked_routes:
        return []

    train_key = _CTA_TRAIN_KEY
    bus_key   = _CTA_BUS_KEY

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
                        final_to = _route_last_transit_to_mapid(route)
                        leg.transfer_wait_minutes = _pick_wait(
                            dest_map,
                            leg.from_mapid,
                            leg.to_mapid,
                            fallback_to_mapid=final_to if final_to != leg.to_mapid else None,
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
    simple = _is_simple_query(ranked_routes)
    model  = _CLAUDE_SIMPLE_MODEL if simple else _CLAUDE_COMPLEX_MODEL
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
    except Exception:
        # Log the full exception server-side; return a generic message so the
        # client never sees raw SDK error text (which can include request IDs,
        # internal URLs, or other infrastructure detail).
        logger.exception("Claude API error")
        raise HTTPException(status_code=502, detail="AI recommendation unavailable")


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
    routing_status: dict | None = None,
) -> dict:
    """Assemble the final JSON-serialisable response dict."""
    # BUG-047: surface the routing-coverage signal so the frontend can render a
    # clear "you're outside CTA coverage" empty state instead of mistaking an
    # out-of-coverage query for a transient backend failure.
    status_payload = routing_status or {
        "status": "ok",
        "side": None,
        "max_radius_searched": None,
    }
    return {
        "recommendation": recommendation,
        "model_used": model_used,
        "routing_status": status_payload,
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
        logger.exception("Failed to fetch weather context")
        return None


# Prompt construction, language map, crowdedness cache, and all related
# formatting helpers all live in prompt_builder.py. The imports above this
# block re-export them onto the main module so existing test imports
# (`from main import build_prompt`) keep working.


# ---------------------------------------------------------------------------
# /last-departure helpers (Last Train tool)
# ---------------------------------------------------------------------------

def _parse_gtfs_time_mins(t: str) -> float:
    """GTFS HH:MM:SS → minutes since midnight. Handles 24:xx/25:xx post-midnight times."""
    parts = t.strip().split(":")
    h, m, s = int(parts[0]), int(parts[1]), int(parts[2])
    return h * 60.0 + m + s / 60.0


def _normalize_gtfs_time_to_wall_clock(gtfs_hhmmss: str) -> str:
    """
    Normalize a GTFS time string ("HH:MM:SS", HH may be 24-29 for post-midnight
    CTA service) to a 24-hour wall-clock "HH:MM" string. "25:30:00" → "01:30".
    """
    parts = gtfs_hhmmss.strip().split(":")
    h = int(parts[0]) % 24
    m = int(parts[1])
    return f"{h:02d}:{m:02d}"


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok", "walking": _walk_fallback_metrics()}


@app.get("/ping")
async def ping(http_request: Request):
    # All analytics counters are wired up via _analytics_middleware (above);
    # this handler only needs to acknowledge the heartbeat.
    return {"ok": True}


class EventBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    # Accepted for forward-compatibility with FEAT-007 (funnel) but ignored
    # here — the session cookie set by /ping already carries the sid, and the
    # cookie is httpOnly so the frontend can't read it anyway. Older clients
    # that send a body sessionId won't 422; the field is just dropped.
    sessionId: str | None = Field(default=None, max_length=128)


@app.post("/events")
async def post_event(body: EventBody, http_request: Request):
    """Record a named behavioral event (FEAT-006). Best-effort, fire-and-forget
    from the frontend. Unknown event names are rejected so the on-disk
    schema can't expand by way of metric poisoning."""
    if not _check_events_rate_limit(_client_ip(http_request)):
        raise HTTPException(status_code=429, detail="Too many requests")
    if not _events.is_allowed(body.name):
        raise HTTPException(status_code=400, detail="Unknown event name")
    try:
        await _events.record(body.name)
    except Exception:
        # Analytics is best-effort — never fail the user-facing call. The
        # outer middleware would also catch this, but the explicit guard
        # documents intent.
        logger.exception("[events] record failed")
    # FEAT-007: advance the session's funnel stage if this event is a stage.
    try:
        raw_sid = http_request.cookies.get(_sessions.COOKIE_NAME)
        await _sessions.advance_funnel_stage(raw_sid, body.name)
    except Exception:
        logger.debug("[funnel] advance_funnel_stage failed for %s", body.name)
    return {"ok": True}


@app.get("/stop-arrivals")
async def stop_arrivals(stops: list[str] = Query(default=[])):
    """
    Return live arrivals for a list of pinned stops (Feature Pinned Stops).
    Each stop is specified as "<type>:<stop_id>" — e.g. "train:40500" or "bus:1234".
    Maximum 10 stops per request.

    Response: { "arrivals": { "<type>:<stop_id>": { "arrivals": [...] } } }
    Keys are typed (e.g. "train:40900", "bus:1234") so bus stop IDs and train
    mapids do not collide when they share a numeric value.
    """
    if len(stops) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 stops per request")

    cache_key = ",".join(sorted(stops))
    cached = _stop_arrivals_cache.get(cache_key)
    if cached is not None:
        return cached

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

    train_key = _CTA_TRAIN_KEY
    bus_key   = _CTA_BUS_KEY

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
        key = f"train:{sid}"
        entry = arrivals.setdefault(key, {"arrivals": []})
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
        key = f"bus:{sid}"
        entry = arrivals.setdefault(key, {"arrivals": []})
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
        typ, sid = item.split(":", 1)
        if typ not in ("train", "bus"):
            continue
        arrivals.setdefault(f"{typ}:{sid}", {"arrivals": []})

    result = {"arrivals": arrivals}
    _stop_arrivals_cache[cache_key] = result
    return result


@app.get("/last-departure")
async def last_departure(
    route_id: str = Query(..., min_length=1, max_length=32),
    direction_id: str = Query(..., min_length=1, max_length=2),
    stop_id: str = Query(..., min_length=1, max_length=32),
):
    """
    Last Train tool — return the last scheduled GTFS departure for a specific
    (route, direction, parent station), with the current minutes-until-departure
    countdown computed against Chicago wall-clock time.

    Response:
      {
        "time": "23:58",          // wall-clock 24-h HH:MM (post-midnight runs
                                  // like "25:30:00" normalize to "01:30")
        "minutes_until": 510,     // null when already departed
        "departed": false
      }

    Times 00:00–02:59 Chicago are treated as a continuation of the previous
    service day (offset +1440 min) so a 2 AM lookup against a 1 AM last-train
    correctly reports "departed."

    404 when there is no last-departure on record for the supplied combination
    (e.g. the picker's manifest drifted from the GTFS feed currently loaded).

    Accepts either a platform stop_id (30xxx, as published in schedule_data and
    consumed by the Last Train picker) or a parent station mapid (40xxx); both
    resolve to the same parent for the lookup.
    """
    mapid = to_parent_mapid(stop_id)
    dep_str = get_last_departure(route_id, direction_id, mapid)
    if dep_str is None:
        raise HTTPException(status_code=404, detail="No last departure on record")

    try:
        dep_mins = _parse_gtfs_time_mins(dep_str)
    except (ValueError, IndexError):
        raise HTTPException(status_code=500, detail="Malformed GTFS time on record")

    now_chicago = datetime.now(_CHICAGO_TZ)
    now_mins = now_chicago.hour * 60.0 + now_chicago.minute + now_chicago.second / 60.0
    if now_chicago.hour < 3:
        now_mins += 24 * 60.0  # continuation of previous service day

    delta = dep_mins - now_mins
    time_label = _normalize_gtfs_time_to_wall_clock(dep_str)

    if delta < 0:
        return {"time": time_label, "minutes_until": None, "departed": True}
    return {"time": time_label, "minutes_until": round(delta), "departed": False}


# /admin/* and /stats/* + /privacy endpoints live in routes/admin.py and
# routes/stats.py (registered onto `app` via include_router above).


@app.get("/autocomplete")
async def autocomplete(
    http_request: Request,
    q: str = Query("", min_length=0, max_length=200),
):
    """
    Return up to 8 location suggestions matching query q (min 2 chars).
    Priority order: train stations → neighborhoods/landmarks → bus stop names.
    Within each tier: prefix > word-start match.
    """
    query = q.strip().lower()
    if len(query) < 2:
        return {"suggestions": []}
    if not _check_geocode_rate_limit(_client_ip(http_request)):
        raise HTTPException(status_code=429, detail="Too many requests")

    # O(1) prefix lookup: use 3-char key for queries ≥ 3 chars, else 2-char key.
    key = query[:3] if len(query) >= 3 else query
    candidates = _ac_prefix_index.get(key, [])

    ranked: list[tuple[int, int, int]] = []
    seen: set[str] = set()
    for tier, _base_score, idx in candidates:
        suggestion = _ac_master[idx]
        nl = suggestion["_nl"]
        if nl.startswith(query):
            score = 0
        elif any(w.startswith(query) for w in suggestion["_words"]):
            score = 1
        else:
            continue
        label = suggestion["label"]
        if label not in seen:
            seen.add(label)
            ranked.append((tier, score, idx))

    ranked.sort(key=lambda x: (x[0], x[1]))
    # Project to the public shape so internal indexing fields (_nl, _words)
    # don't leak into the response payload (OPT-BE-223).
    return {
        "suggestions": [
            {"label": s["label"], "value": s["value"], "type": s["type"]}
            for s in (_ac_master[idx] for _, _, idx in ranked[:8])
        ]
    }


# ---------------------------------------------------------------------------
# /alerts cache — 5-minute TTL, single static key "alerts"
# ---------------------------------------------------------------------------
_ALERTS_CACHE_TTL = 300  # 5 minutes
_alerts_cache: TTLCache = TTLCache(maxsize=10, ttl=_ALERTS_CACHE_TTL)
_CTA_CUSTOMER_ALERTS_URL = "https://www.transitchicago.com/api/1.0/alerts.aspx"
_ALERTS_SEVERITY_ORDER = {"Major": 0, "Minor": 1, "Planned": 2}
_ALERTS_API_TIMEOUT = aiohttp.ClientTimeout(total=8)


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
    cached = _alerts_cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        async with _get_cta_session().get(
            _CTA_CUSTOMER_ALERTS_URL,
            params={"outputType": "XML", "accessibility": "false"},
            timeout=_ALERTS_API_TIMEOUT,
        ) as resp:
            text = await resp.text()

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
        logger.exception("Failed to fetch alerts")
        result = {"alerts": []}

    _alerts_cache[cache_key] = result
    return result


# ---------------------------------------------------------------------------
# Route statuses cache — 60-second TTL
# ---------------------------------------------------------------------------
_ROUTE_STATUSES_CACHE_TTL = 60
_route_statuses_cache: TTLCache = TTLCache(maxsize=10, ttl=_ROUTE_STATUSES_CACHE_TTL)


async def _get_route_statuses_cached() -> list[dict]:
    cache_key = "route_statuses"
    cached = _route_statuses_cache.get(cache_key)
    if cached is not None:
        return cached
    result = await get_route_statuses()
    _route_statuses_cache[cache_key] = result
    return result


@app.post("/recommend")
async def recommend(
    request: RouteRequest,
    http_request: Request,
    authorization: str | None = Header(default=None),
):
    ip = _client_ip(http_request)

    # BYOK key arrives via Authorization: Bearer <sk-ant-...>. Parsed here so it
    # never enters the request body (which is logged/cached by intermediaries).
    # Cap at 256 chars defensively — Anthropic keys are ~108 chars today; a far
    # longer string is either an attack or a malformed paste, and we don't want
    # to even pass it to compare/format checks.
    byok_key: str | None = None
    if _BYOK_ENABLED and authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() == "bearer":
            token = token.strip()
            if token and len(token) <= 256:
                byok_key = token

    # If BYOK is enabled and the user supplied a valid key, create a throwaway
    # client scoped to this request. A new AsyncAnthropic() is cheap — it holds
    # no persistent connection.
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
        # Rolling-24h cap defends the Anthropic budget against an attacker who
        # paces requests slowly enough to slip past the per-minute/per-hour caps.
        if not _check_daily_quota(ip):
            raise HTTPException(
                status_code=429,
                detail="Daily request limit reached. Try again tomorrow.",
            )
        _cache_requests_total += 1
        cached = _response_cache.get(key) if _CACHE_ENABLED else None
        if cached is not None:
            _cache_hits += 1
            _maybe_log_cache_stats()
            return {**cached, "cache_hit": True}
        _cache_misses += 1
        _maybe_log_cache_stats()

    loop = asyncio.get_running_loop()

    # Walk mode — skip all CTA API calls; resolve coordinates and route via walking graph only.
    if request.transit_mode == "Walk":
        origin_coords, dest_coords = await asyncio.gather(
            loop.run_in_executor(None, coords_for_location, request.origin, None),
            loop.run_in_executor(None, coords_for_location, request.destination, None),
        )
        if not origin_coords:
            raise HTTPException(status_code=400, detail=f"Could not geocode '{request.origin}'.")
        if not dest_coords:
            raise HTTPException(status_code=400, detail=f"Could not geocode '{request.destination}'.")
        dlat = origin_coords[0] - dest_coords[0]
        dlon = origin_coords[1] - dest_coords[1]
        if (dlat * dlat + dlon * dlon) < _SAME_LOCATION_THRESHOLD_DEG2:
            raise HTTPException(status_code=400, detail="Your origin and destination appear to be the same location.")

        (walk_min, directions, path), walk_weather = await asyncio.gather(
            loop.run_in_executor(None, _walk_all, origin_coords[0], origin_coords[1], dest_coords[0], dest_coords[1]),
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
        if _CACHE_ENABLED:
            async with _store_lock:
                _response_cache[key] = response
        try:
            await _events.record("recommend_returned")
        except Exception as e:
            logger.debug("[events] recommend_returned record failed: %s", e)
        try:
            await _sessions.advance_funnel_stage(
                http_request.cookies.get(_sessions.COOKIE_NAME), "recommend_returned"
            )
        except Exception as e:
            logger.debug("[funnel] advance_funnel_stage failed: %s", e)
        return response

    (
        origin_stations, origin_bus_stops,
        dest_stations, dest_bus_stops, dest_match,
        origin_coords, dest_coords,
    ) = await _resolve_locations(loop, request)
    destination_label = dest_match or request.destination

    (train_arrivals, bus_arrivals, n_train_errors, n_bus_errors), weather = await asyncio.gather(
        _fetch_arrivals(request, origin_stations, origin_bus_stops),
        _safe_weather(origin_coords),
    )

    ranked_routes, routing_status = await _run_routing(
        request, origin_coords, dest_coords,
        origin_stations, origin_bus_stops, train_arrivals, bus_arrivals,
        weather=weather,
        dest_bus_stops=dest_bus_stops,
    )

    transfer_arrivals_combined = await _fetch_transfer_arrivals(ranked_routes)
    ranked_routes = _apply_transfer_wait_estimates(ranked_routes)

    alert_ids = _alert_ids_from_routes(ranked_routes)
    alerts, route_statuses = await asyncio.gather(
        get_alerts(alert_ids),
        _get_route_statuses_cached(),
    )

    recommendation = None
    model_used = None
    if request.ai_enabled:
        # build_prompt() is skipped entirely when AI is off — its output is only
        # consumed by _call_claude(), and the prep work it does (formatting routes,
        # crowdedness sections, alerts/route-status text) is otherwise unused.
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
            routing_status=routing_status,
        )
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
        routing_status=routing_status,
    )

    if _CACHE_ENABLED:
        async with _store_lock:
            _response_cache[key] = response

    try:
        await _events.record("recommend_returned")
    except Exception as e:
        logger.debug("[events] recommend_returned record failed: %s", e)
    try:
        await _sessions.advance_funnel_stage(
            http_request.cookies.get(_sessions.COOKIE_NAME), "recommend_returned"
        )
    except Exception as e:
        logger.debug("[funnel] advance_funnel_stage failed: %s", e)

    return response


@app.get("/reverse-geocode")
async def reverse_geocode_endpoint(
    http_request: Request,
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
):
    """
    Convert GPS coordinates to a human-readable address string.
    Used by the frontend after geolocation to display a place name instead of raw coordinates.
    Falls back to "lat,lon" if the Google Maps API is unavailable.
    """
    if not _check_geocode_rate_limit(_client_ip(http_request)):
        raise HTTPException(status_code=429, detail="Too many requests")
    loop = asyncio.get_running_loop()
    address = await loop.run_in_executor(None, reverse_geocode_google, lat, lon)
    return {"address": address or f"{lat:.6f},{lon:.6f}"}
