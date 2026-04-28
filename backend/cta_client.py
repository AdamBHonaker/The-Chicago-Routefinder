"""
Async clients for the CTA Train Tracker and Bus Tracker APIs.

Train Tracker docs:  lapi.transitchicago.com/api/1.0/
Bus Tracker docs:    ctabustracker.com/bustime/api/v3/

Bus stop IDs (stpid) come from CTA GTFS stops.txt (0–29999 range),
resolved by gtfs_loader.find_nearest_bus_stops() and passed in from main.py.
"""

import asyncio
import os
from datetime import datetime

import aiohttp
import config as _cfg
from utils import CHICAGO_TZ

# Tracks raw psgld values seen from the API — logged once per unique value so
# we can verify the actual format against our normalization assumption.

_CTA_TRAIN_BASE = os.getenv("CTA_TRAIN_API_URL", "https://lapi.transitchicago.com/api/1.0")
_CTA_BUS_BASE   = os.getenv("CTA_BUS_API_URL",   "https://www.ctabustracker.com/bustime/api/v3")

# Long-lived session shared across all CTA API calls.
# Initialised by init_session() during FastAPI lifespan startup and closed by
# close_session() at shutdown. Falls back to creating a temporary session if
# called before init (e.g. in isolated unit tests).
_session: aiohttp.ClientSession | None = None


async def init_session() -> None:
    global _session
    _session = aiohttp.ClientSession()


async def close_session() -> None:
    global _session
    if _session is not None:
        await _session.close()
        _session = None


def _get_session() -> aiohttp.ClientSession:
    if _session is not None:
        return _session
    # Fallback for tests / isolated calls — caller is responsible for closing
    return aiohttp.ClientSession()

TRAIN_BASE = f"{_CTA_TRAIN_BASE}/ttarrivals.aspx"
BUS_BASE   = f"{_CTA_BUS_BASE}/getpredictions"

# Human-readable line names keyed by the API's rt abbreviation
LINE_NAMES = {
    "Red":  "Red Line",
    "Blue": "Blue Line",
    "Brn":  "Brown Line",
    "G":    "Green Line",
    "Org":  "Orange Line",
    "P":    "Purple Line",
    "Pink": "Pink Line",
    "Y":    "Yellow Line",
}


# ---------------------------------------------------------------------------
# Train Tracker
# ---------------------------------------------------------------------------

async def _fetch_station_arrivals(
    session: aiohttp.ClientSession,
    mapid: str,
    station_label: str,
    train_key: str,
) -> list[dict]:
    """Fetch live arrivals for one station (by parent station mapid)."""
    params = {
        "key": train_key,
        "mapid": mapid,
        "max": _cfg.CTA_MAX_ARRIVALS_PER_STATION,
        "outputType": "JSON",
    }
    try:
        async with session.get(
            TRAIN_BASE, params=params,
            timeout=aiohttp.ClientTimeout(total=_cfg.CTA_API_TIMEOUT_SECONDS),
        ) as resp:
            data = await resp.json(content_type=None)
    except Exception as exc:
        return [{"_error": True, "exc": f"Train API error for {station_label}: {exc}", "mode": "train"}]

    ctatt = data.get("ctatt", {})
    err_code = ctatt.get("errCd", "0")
    if str(err_code) != "0":
        return [{"_error": True, "exc": f"Train API error {err_code}: {ctatt.get('errNm', '')}", "mode": "train"}]

    now = datetime.now(CHICAGO_TZ)
    arrivals = []

    eta_list = ctatt.get("eta", [])
    # API returns a dict (not list) when there is exactly one result
    if isinstance(eta_list, dict):
        eta_list = [eta_list]

    for eta in eta_list:
        try:
            arr_str = eta["arrT"]
            # Format is either "20240101 14:32:00" or "2024-01-01T14:32:00"
            if "T" in arr_str:
                arr_dt = datetime.fromisoformat(arr_str)
                if arr_dt.tzinfo is not None:
                    arr_dt = arr_dt.astimezone(CHICAGO_TZ)
                else:
                    arr_dt = arr_dt.replace(tzinfo=CHICAGO_TZ)
            else:
                arr_dt = datetime.strptime(arr_str, "%Y%m%d %H:%M:%S").replace(tzinfo=CHICAGO_TZ)

            minutes = max(0, round((arr_dt - now).total_seconds() / 60))

            rt = eta.get("rt", "")
            arrivals.append({
                "type": "train",
                "line": LINE_NAMES.get(rt, rt),
                "line_code": rt,
                "station": eta.get("staNm", station_label),
                "station_mapid": mapid,   # carried through for exact walk-time lookup
                "platform": eta.get("stpDe", ""),
                "destination": eta.get("destNm", ""),
                "arrives_in_minutes": minutes,
                "is_approaching": eta.get("isApp") == "1",
                "is_delayed": eta.get("isDly") == "1",
                "is_scheduled": eta.get("isSch") == "1",
            })
        except Exception:
            continue

    return arrivals


async def get_train_arrivals(
    stations: list[dict],
    train_key: str,
) -> tuple[list[dict], int]:
    """
    Fetch live train arrivals for a list of stations concurrently.
    `stations` is a list of dicts from station_lookup.find_stations().
    Returns (arrivals_sorted_by_minutes, n_errors).
    """
    session = _get_session()
    tasks = [
        _fetch_station_arrivals(session, s["mapid"], s["name"], train_key)
        for s in stations
    ]
    results = await asyncio.gather(*tasks)

    all_arrivals: list[dict] = []
    for result in results:
        all_arrivals.extend(result)

    # Filter out error entries for the sorted list, keep errors for logging
    good = [a for a in all_arrivals if not a.get("_error")]
    errors = [a for a in all_arrivals if a.get("_error")]

    if errors:
        msgs = "; ".join(e["exc"] for e in errors[:3])
        print(f"[cta_client] {len(errors)} train error(s): {msgs}")

    return sorted(good, key=lambda a: a["arrives_in_minutes"]), len(errors)


# ---------------------------------------------------------------------------
# Bus Tracker  (Phase 4: stop IDs populated from GTFS data)
# ---------------------------------------------------------------------------

async def _fetch_bus_chunk(
    session: aiohttp.ClientSession,
    chunk: list[str],
    bus_key: str,
    routes: list[str] | None,
) -> list[dict]:
    """Fetch bus predictions for one chunk of up to 10 stop IDs."""
    params: dict = {
        "key": bus_key,
        "stpid": ",".join(chunk),
        "format": "json",
        "tmres": "s",
    }
    if routes:
        params["rt"] = ",".join(routes[:10])

    try:
        async with session.get(
            BUS_BASE, params=params,
            timeout=aiohttp.ClientTimeout(total=_cfg.CTA_API_TIMEOUT_SECONDS),
        ) as resp:
            data = await resp.json(content_type=None)
    except Exception as exc:
        print(f"[cta_client] Bus API error for {len(chunk)} stops: {exc}")
        # Return a sentinel so get_bus_arrivals can count failures instead of
        # silently dropping them. The list[dict] return type is preserved.
        return [{"_error": True, "exc": str(exc), "mode": "bus"}]

    response = data.get("bustime-response", {})
    prd_list = response.get("prd", [])
    if isinstance(prd_list, dict):
        prd_list = [prd_list]

    arrivals = []
    for prd in prd_list:
        try:
            # Use `or ""` so an explicit API null ("prdctdn": null) defaults to ""
            # rather than raising AttributeError on None.isdigit().
            prdctdn = prd.get("prdctdn") or ""
            # "DUE" and "APPROACHING" both mean ≤0 minutes; any other
            # non-numeric value (unexpected API change) is also treated as 0
            # rather than raising ValueError and silently dropping the arrival.
            if prdctdn.isdigit():
                minutes = int(prdctdn)
            else:
                minutes = 0
            raw_psgld = prd.get("psgld", "")
            # Normalize to UPPER_SNAKE so filter comparisons work regardless
            # of whether CTA sends "HALF EMPTY" (space) or "HALF_EMPTY" (underscore)
            psgld = raw_psgld.replace(" ", "_").upper()

            arrivals.append({
                "type": "bus",
                "route": prd.get("rt", ""),
                "direction": prd.get("rtdir", ""),
                "stop_id": prd.get("stpid", ""),   # GTFS stop ID — used by find_bus_transfer_routes()
                "stop_name": prd.get("stpnm", ""),
                "destination": prd.get("des", ""),
                "arrives_in_minutes": minutes,
                "is_delayed": str(prd.get("dly", "")).lower() in ("true", "1", "yes"),
                "psgld": psgld,  # normalized: EMPTY | HALF_EMPTY | FULL
            })
        except Exception:
            continue

    return arrivals


async def get_bus_arrivals(
    stop_ids: list[str],
    bus_key: str,
    routes: list[str] | None = None,
) -> tuple[list[dict], int]:
    """
    Fetch live bus predictions for a list of stop IDs.

    stop_ids come from CTA GTFS stops.txt (0–29999 range).
    Batches into chunks of 10 (API maximum) and fires all chunks concurrently.
    Returns (arrivals_sorted_by_minutes, n_errors).
    n_errors counts how many chunk requests failed; a non-zero value with an
    empty arrivals list means the Bus API is completely unavailable.
    """
    if not stop_ids:
        return [], 0

    chunks = [stop_ids[i:i + 10] for i in range(0, len(stop_ids), 10)]
    session = _get_session()
    results = await asyncio.gather(
        *[_fetch_bus_chunk(session, chunk, bus_key, routes) for chunk in chunks]
    )

    all_arrivals: list[dict] = []
    n_errors = 0
    for result in results:
        for item in result:
            if item.get("_error"):
                n_errors += 1
            else:
                all_arrivals.append(item)

    return sorted(all_arrivals, key=lambda a: a["arrives_in_minutes"]), n_errors


# ---------------------------------------------------------------------------
# Alerts API  (public — no key required)
# ---------------------------------------------------------------------------

ALERTS_BASE = "https://lapi.transitchicago.com/api/1.0/alerts.aspx"

# Maps app-internal line_code values to the lowercase routeid the Alerts API expects
_TRAIN_LINE_TO_ALERT_ID = {
    "Red": "red", "Blue": "blue", "Brn": "brn", "G": "g",
    "Org": "org", "P": "p", "Pink": "pink", "Y": "y",
}


async def _fetch_alerts_for_route(
    session: aiohttp.ClientSession,
    route_id: str,
) -> list[dict]:
    """Fetch active alerts for a single route id (train line or bus route number)."""
    try:
        params = {"outputType": "JSON", "routeid": route_id}
        async with session.get(
            ALERTS_BASE, params=params, timeout=aiohttp.ClientTimeout(total=5)
        ) as resp:
            data = await resp.json(content_type=None)
    except Exception as exc:
        print(f"[cta_client] WARNING: Alerts API fetch failed for route {route_id!r}: {exc}")
        return []

    alerts_raw = data.get("CTAAlerts", {}).get("Alert", [])
    if isinstance(alerts_raw, dict):
        alerts_raw = [alerts_raw]
    if not isinstance(alerts_raw, list):
        return []

    alerts = []
    for a in alerts_raw:
        try:
            severity = int(a.get("SeverityScore", 0) or 0)
            impacted = a.get("ImpactedService", {}).get("Service", [])
            if isinstance(impacted, dict):
                impacted = [impacted]
            affected_routes = [
                s.get("ServiceId", "") for s in impacted if s.get("ServiceId")
            ]
            event_end = a.get("EventEnd") or None
            if event_end == "":
                event_end = None
            alerts.append({
                "alert_id": str(a.get("AlertId", "")),
                "headline": a.get("Headline", ""),
                "impact": a.get("Impact", ""),
                "severity_score": severity,
                "is_major": severity >= 7,
                "event_end": event_end,
                "affected_routes": affected_routes,
            })
        except Exception:
            continue
    return alerts


async def get_alerts(route_ids: list[str]) -> list[dict]:
    """
    Fetch active CTA alerts for a list of route ids concurrently.
    route_ids are Alerts API ids: lowercase train color or bus route number.
    Deduplicates by alert_id (the same alert can affect multiple requested routes).
    Returns [] if route_ids is empty.
    """
    if not route_ids:
        return []

    session = _get_session()
    results = await asyncio.gather(
        *[_fetch_alerts_for_route(session, rid) for rid in route_ids]
    )

    seen: set[str] = set()
    deduped: list[dict] = []
    for batch in results:
        for alert in batch:
            aid = alert["alert_id"]
            if aid and aid not in seen:
                seen.add(aid)
                deduped.append(alert)

    deduped.sort(key=lambda a: a["severity_score"], reverse=True)
    return deduped


# ---------------------------------------------------------------------------
# Route Status API  (public — no key required)
# ---------------------------------------------------------------------------

ROUTES_BASE = "https://lapi.transitchicago.com/api/1.0/routes.aspx"


async def get_route_statuses() -> list[dict]:
    """
    Fetch current CTA route statuses for all lines.
    Returns a list of dicts with keys: service_id, route, status, status_color.
    Returns [] on any failure.
    """
    try:
        session = _get_session()
        async with session.get(
            ROUTES_BASE,
            params={"outputType": "JSON"},
            timeout=aiohttp.ClientTimeout(total=5),
        ) as resp:
            data = await resp.json(content_type=None)
    except Exception as exc:
        print(f"[cta_client] WARNING: Route Status API fetch failed: {exc}")
        return []

    routes_raw = data.get("CTARoutes", {}).get("RouteInfo", [])
    if isinstance(routes_raw, dict):
        routes_raw = [routes_raw]
    if not isinstance(routes_raw, list):
        return []

    statuses = []
    for r in routes_raw:
        try:
            statuses.append({
                "service_id": r.get("ServiceId", ""),
                "route": r.get("Route", ""),
                "status": r.get("RouteStatus", ""),
                "status_color": r.get("RouteStatusColor", ""),
            })
        except Exception:
            continue
    return statuses
