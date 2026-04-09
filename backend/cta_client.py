"""
Async clients for the CTA Train Tracker and Bus Tracker APIs.

Train Tracker docs:  lapi.transitchicago.com/api/1.0/
Bus Tracker docs:    ctabustracker.com/bustime/api/v3/

Bus stop IDs (stpid) come from CTA GTFS stops.txt (0–29999 range),
resolved by gtfs_loader.find_nearest_bus_stops() and passed in from main.py.
"""

import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

import aiohttp

# Tracks raw psgld values seen from the API — logged once per unique value so
# we can verify the actual format against our normalization assumption.
_psgld_seen: set[str] = set()

CHICAGO_TZ = ZoneInfo("America/Chicago")

TRAIN_BASE = "https://lapi.transitchicago.com/api/1.0/ttarrivals.aspx"
BUS_BASE   = "https://www.ctabustracker.com/bustime/api/v3/getpredictions"

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
        "max": 6,
        "outputType": "JSON",
    }
    try:
        async with session.get(TRAIN_BASE, params=params, timeout=aiohttp.ClientTimeout(total=8)) as resp:
            data = await resp.json(content_type=None)
    except Exception as exc:
        return [{"error": f"Train API error for {station_label}: {exc}"}]

    ctatt = data.get("ctatt", {})
    err_code = ctatt.get("errCd", "0")
    if str(err_code) != "0":
        return [{"error": f"Train API error {err_code}: {ctatt.get('errNm', '')}"}]

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
                arr_dt = datetime.fromisoformat(arr_str).replace(tzinfo=CHICAGO_TZ)
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
) -> list[dict]:
    """
    Fetch live train arrivals for a list of stations concurrently.
    `stations` is a list of dicts from station_lookup.find_stations().
    Returns arrivals sorted by minutes_until_arrival.
    """
    async with aiohttp.ClientSession() as session:
        tasks = [
            _fetch_station_arrivals(session, s["mapid"], s["name"], train_key)
            for s in stations
        ]
        results = await asyncio.gather(*tasks)

    all_arrivals: list[dict] = []
    for result in results:
        all_arrivals.extend(result)

    # Filter out error entries for the sorted list, keep errors for logging
    good = [a for a in all_arrivals if "error" not in a]
    errors = [a for a in all_arrivals if "error" in a]

    if errors:
        # Log but don't crash — partial results are fine
        for e in errors:
            print(f"[cta_client] {e['error']}")

    return sorted(good, key=lambda a: a["arrives_in_minutes"])


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
            BUS_BASE, params=params, timeout=aiohttp.ClientTimeout(total=8)
        ) as resp:
            data = await resp.json(content_type=None)
    except Exception as exc:
        print(f"[cta_client] Bus API error for stops {chunk}: {exc}")
        return []

    response = data.get("bustime-response", {})
    prd_list = response.get("prd", [])
    if isinstance(prd_list, dict):
        prd_list = [prd_list]

    arrivals = []
    for prd in prd_list:
        try:
            prdctdn = prd.get("prdctdn", "")
            minutes = 0 if prdctdn == "DUE" else int(prdctdn)
            raw_psgld = prd.get("psgld", "")
            if raw_psgld and raw_psgld not in _psgld_seen:
                _psgld_seen.add(raw_psgld)
                print(f"[cta_client] psgld raw value from API: {raw_psgld!r}")
            # Normalize to UPPER_SNAKE so filter comparisons work regardless
            # of whether CTA sends "HALF EMPTY" (space) or "HALF_EMPTY" (underscore)
            psgld = raw_psgld.replace(" ", "_").upper()

            arrivals.append({
                "type": "bus",
                "route": prd.get("rt", ""),
                "direction": prd.get("rtdir", ""),
                "stop_id": prd.get("stpid", ""),   # GTFS stop ID — used by find_bus_routes()
                "stop_name": prd.get("stpnm", ""),
                "destination": prd.get("des", ""),
                "arrives_in_minutes": minutes,
                "is_delayed": prd.get("dly", False) is True or prd.get("dly") == "true",
                "psgld": psgld,  # normalized: EMPTY | HALF_EMPTY | FULL
            })
        except Exception:
            continue

    return arrivals


async def get_bus_arrivals(
    stop_ids: list[str],
    bus_key: str,
    routes: list[str] | None = None,
) -> list[dict]:
    """
    Fetch live bus predictions for a list of stop IDs.

    stop_ids come from CTA GTFS stops.txt (0–29999 range).
    Batches into chunks of 10 (API maximum) and fires all chunks concurrently.
    Returns an empty list if no stop_ids are provided.
    """
    if not stop_ids:
        return []

    chunks = [stop_ids[i:i + 10] for i in range(0, len(stop_ids), 10)]
    async with aiohttp.ClientSession() as session:
        results = await asyncio.gather(
            *[_fetch_bus_chunk(session, chunk, bus_key, routes) for chunk in chunks]
        )

    all_arrivals: list[dict] = []
    for result in results:
        all_arrivals.extend(result)

    return sorted(all_arrivals, key=lambda a: a["arrives_in_minutes"])
