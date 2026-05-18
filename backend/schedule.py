"""
Schedule endpoints for FEAT-018 (Published CTA schedule viewer).

Serves two read-only endpoints backed by the static artifacts in
``backend/schedule_data/`` (built offline by
``scripts/build_schedule_index.py``):

  * ``GET /schedule/routes``        → picker manifest (all routes + reverse
                                      stop→routes index for Decision-10
                                      pre-highlighting).
  * ``GET /schedule/{route_id}``    → full published schedule for one route,
                                      bucketed by direction → stop →
                                      service-day.

The endpoints stream the files from disk on each request; the manifest is
small (~few hundred KB) and the per-route files cap at ~2 MB each, so we do
not bother caching them in process memory. Re-reading on every call keeps
schedule data fresh after a maintainer re-runs the build script without
needing a server restart.

If ``backend/schedule_data/`` is empty (the build script has never been
run), ``/schedule/routes`` returns an empty list and ``/schedule/{route_id}``
404s — this is the documented failure mode noted in FEAT-018 Decision 9.

The route-category classifier (``classify_route``) is also re-exported here
so tests can exercise it without importing the build script.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from rate_limit import _check_geocode_rate_limit, _client_ip

logger = logging.getLogger(__name__)

SCHEDULE_DIR = Path(__file__).resolve().parent / "schedule_data"
_MANIFEST_PATH = SCHEDULE_DIR / "_manifest.json"

# Schedule artifacts are rebuilt offline by scripts/build_schedule_index.py and
# don't change between runs — a 24h browser/CDN cache absorbs the bandwidth
# tail and keeps Railway egress bounded under repeated requests (SEC-009).
_SCHEDULE_CACHE_HEADERS = {"Cache-Control": "public, max-age=86400"}

# Route-color taxonomy — mirrors scripts/build_schedule_index.py. Duplicated
# (not imported) so the build script and the runtime server can be edited
# independently per the FEAT-018 "don't couple build artifacts to runtime"
# stance taken by the maintainer for fetch_gtfs / fetch_street_graph.
_BUS_EXPRESS_COLOR = "b71234"
_BUS_FREQUENT_COLOR = "414145"


def classify_route(route_type: str, route_color: str) -> str:
    """FEAT-018 Decision-8 category rule. See ``scripts/build_schedule_index.py``."""
    if route_type == "1":
        return "train"
    if route_type == "3":
        c = (route_color or "").strip().lower()
        if c == _BUS_EXPRESS_COLOR:
            return "bus_express"
        if c == _BUS_FREQUENT_COLOR:
            return "bus_frequent"
        return "bus_regular"
    return "other"


def _safe_route_id(rid: str) -> str:
    """Match the filename-safe rendering used by the build script."""
    return "".join(c if (c.isalnum() or c in ("_", "-")) else "_" for c in rid)


router = APIRouter()


@router.get("/schedule/routes")
async def schedule_routes(request: Request):
    """Picker manifest: ordered route list + stop→routes reverse index."""
    # SEC-009: rate-limit through the shared geocode bucket (60 RPM / 600 RPH)
    # so an attacker can't drive the per-request manifest read into a Railway
    # egress / event-loop DoS.
    if not _check_geocode_rate_limit(_client_ip(request)):
        raise HTTPException(status_code=429, detail="Too many requests")
    if not _MANIFEST_PATH.exists():
        # Build script never run; serve a graceful empty response so the
        # frontend renders an empty picker rather than erroring out.
        return JSONResponse(
            content={"routes": [], "stop_routes": {}},
            headers=_SCHEDULE_CACHE_HEADERS,
        )
    try:
        with open(_MANIFEST_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        # SEC-010: never echo raw exception text — OSError repr would leak
        # the absolute container path of the manifest.
        logger.exception("[schedule] manifest unreadable")
        raise HTTPException(status_code=500, detail="Schedule data unavailable")
    return JSONResponse(content=data, headers=_SCHEDULE_CACHE_HEADERS)


@router.get("/schedule/{route_id}")
async def schedule_for_route(route_id: str, request: Request):
    """Full schedule JSON for one route."""
    # SEC-009: same rate-limit gate as the manifest endpoint. Each per-route
    # file is ~2 MB; without this an attacker could saturate Railway egress.
    if not _check_geocode_rate_limit(_client_ip(request)):
        raise HTTPException(status_code=429, detail="Too many requests")
    safe = _safe_route_id(route_id)
    path = SCHEDULE_DIR / f"{safe}.json"
    if not path.exists():
        raise HTTPException(status_code=404,
                            detail=f"No schedule for route {route_id!r}. "
                                   f"Re-run scripts/build_schedule_index.py?")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        # SEC-010: scrub exception details — the route_id is safe to echo
        # (caller supplied it) but the OSError path leaks /app/backend/...
        logger.exception("[schedule] route %r unreadable", route_id)
        raise HTTPException(status_code=500, detail="Schedule data unavailable")
    return JSONResponse(content=data, headers=_SCHEDULE_CACHE_HEADERS)
