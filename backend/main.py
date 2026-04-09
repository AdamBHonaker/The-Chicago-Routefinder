import asyncio
import os
from contextlib import asynccontextmanager
from difflib import SequenceMatcher

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import anthropic

from gtfs_loader import resolve_location, geocode_nominatim, NEIGHBORHOOD_COORDS
from cta_client import get_train_arrivals, get_bus_arrivals
from transit_graph import find_routes, find_bus_routes, warm_up, get_bus_stop_sequences, WalkLeg, TransitLeg

load_dotenv()

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

    # 2. Fuzzy match — mirrors resolve_location exactly: 0.95 threshold +
    #    word-overlap guard so "chicago art museum" never matches
    #    "chicago history museum" on structural words alone.
    _STOP_WORDS = {"the", "of", "a", "an", "and", "at", "in", "on", "chicago"}
    q_words = set(q.split()) - _STOP_WORDS
    best_score, best_key = 0.0, None
    for key in NEIGHBORHOOD_COORDS:
        score = SequenceMatcher(None, q, key).ratio()
        if score <= best_score:
            continue
        if len(q_words) > 1:
            key_words = set(key.split()) - _STOP_WORDS
            if not q_words & key_words:
                continue
        best_score = score
        best_key = key
    if best_score >= 0.95 and best_key:
        return NEIGHBORHOOD_COORDS[best_key]

    # 3. Nominatim geocoding (result is cached after resolve_location already called it)
    coords = geocode_nominatim(query)
    if coords:
        return coords

    # 4. Centroid of already-resolved nearby stations as last resort
    if stations:
        lats = [s["lat"] for s in stations]
        lons = [s["lon"] for s in stations]
        return (sum(lats) / len(lats), sum(lons) / len(lons))

    return None


def _build_arrival_lookup(train_arrivals: list[dict]) -> dict[tuple[str, str], int]:
    """(line_code, station_mapid) -> next arrival in minutes (earliest only)."""
    lookup: dict[tuple[str, str], int] = {}
    for a in train_arrivals:
        key = (a.get("line_code", ""), a.get("station_mapid", ""))
        if key not in lookup:
            lookup[key] = a["arrives_in_minutes"]
    return lookup


def _rank_routes(
    routes: list,
    arrival_lookup: dict[tuple[str, str], int],
) -> list[tuple[float, int, object]]:
    """
    Add live wait time to each route and sort by total (walk + wait + transit).
    Returns list of (total_with_wait, wait_minutes, route).
    """
    ranked = []
    for route in routes:
        first_transit = next((l for l in route.legs if isinstance(l, TransitLeg)), None)
        wait = 0
        if first_transit:
            key = (first_transit.line_code, first_transit.from_mapid)
            wait = arrival_lookup.get(key, 0)
        total = route.total_minutes_no_wait + wait
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
        if first_transit and first_transit.line in ("Northbound", "Southbound", "Eastbound", "Westbound"):
            wait_note = f", next bus in {wait} min" if wait else ""
        else:
            wait_note = f", next train in {wait} min" if wait else ""
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
                )
            except Exception as exc:
                print(f"[main] Train routing error: {exc}")

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
            except Exception as exc:
                print(f"[main] Bus routing error: {exc}")

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

    message = await _claude_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=750,
        messages=[{"role": "user", "content": prompt}],
    )

    # ── Response ──────────────────────────────────────────────────────────────
    return {
        "recommendation": message.content[0].text,
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
                    }
                    for leg in route.legs
                ],
            }
            for total, wait, route in ranked_routes
        ],
    }
