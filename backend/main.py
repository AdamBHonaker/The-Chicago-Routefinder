import asyncio
import os
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
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
    find_routes, find_bus_routes, warm_up, get_bus_stop_sequences,
    WalkLeg, TransitLeg, get_station_coords, get_station_by_name,
)

# Anthropic client — created once at startup, reused across all requests
_claude_client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))

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
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


class RouteRequest(BaseModel):
    origin: str
    destination: str
    transit_mode: str = "All"   # "All" | "Train" | "Bus"
    bus_fullness: str = "All"   # "All" | "Empty" | "Half-Full" | "Full"


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
    dest_lat: float | None = None,
    dest_lon: float | None = None,
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
async def recommend(request: RouteRequest):
    train_key = os.getenv("CTA_TRAIN_API_KEY", "")
    bus_key   = os.getenv("CTA_BUS_API_KEY", "")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")

    if not train_key:
        raise HTTPException(status_code=500, detail="CTA_TRAIN_API_KEY not configured in backend/.env")
    if not anthropic_key or anthropic_key == "your_api_key_here":
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured in backend/.env")
    if request.transit_mode in ("Bus", "All") and not bus_key:
        raise HTTPException(status_code=500, detail="CTA_BUS_API_KEY not configured in backend/.env")

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

    if request.transit_mode == "Bus":
        train_arrivals = []
    else:
        train_arrivals = await get_train_arrivals(origin_stations, train_key)
        for a in train_arrivals:
            a["walk_minutes"] = walk_lookup.get(a.get("station_mapid"), 0)

    # ── Bus arrivals ──────────────────────────────────────────────────────────
    bus_arrivals: list[dict] = []
    if request.transit_mode in ("Bus", "All") and bus_key and origin_bus_stops:
        stop_ids = [s["stop_id"] for s in origin_bus_stops]
        bus_arrivals = await get_bus_arrivals(stop_ids, bus_key)

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
                        n_routes=3,
                    ),
                    arrival_lookup,
                    dest_lat=dest_coords[0],
                    dest_lon=dest_coords[1],
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
                ranked_routes = sorted(
                    ranked_routes + bus_ranked,
                    key=lambda x: x[0],
                )[:5]
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
        message = await _claude_client.messages.create(
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
    return {
        "recommendation": recommendation,
        "origin_coords": list(origin_coords) if origin_coords else None,
        "dest_coords":   list(dest_coords)   if dest_coords   else None,
        "train_arrivals": train_arrivals,
        "bus_arrivals": bus_arrivals,
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
                            else {"path": leg.path_points, "directions": leg.directions}
                        ),
                    }
                    for leg in route.legs
                ],
            }
            for total, wait, route in ranked_routes
        ],
    }
