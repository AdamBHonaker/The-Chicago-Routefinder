"""
Public-stats endpoints (``/stats/*`` and ``/privacy``).

Each route hits the corresponding raw counter and runs the result through
``public_stats``' projection — which is the single load-bearing privacy
check that strips admin-only fields before they reach the wire.

Rate-limited via the geocode bucket because these are bursty page loads.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse

import dau
import devices
import events
import funnel
import geography
import hourly
import public_stats
import referrers
import retention
import sessions
from rate_limit import _check_geocode_rate_limit, _client_ip

router = APIRouter()

# 5-minute browser/CDN cache absorbs page-load bursts without hammering disk.
_PUBLIC_STATS_CACHE_HEADERS = {"Cache-Control": "public, max-age=300"}


def _gate(request: Request) -> None:
    if not _check_geocode_rate_limit(_client_ip(request)):
        raise HTTPException(status_code=429, detail="Too many requests")


@router.get("/stats/dau")
async def public_dau(request: Request):
    _gate(request)
    raw = await dau.get_counts()
    return JSONResponse(
        content=public_stats.project_dau(raw),
        headers=_PUBLIC_STATS_CACHE_HEADERS,
    )


@router.get("/stats/geography")
async def public_geography(request: Request):
    _gate(request)
    metro = await geography.get_metro_summary()
    return JSONResponse(
        content=public_stats.project_geography(metro),
        headers=_PUBLIC_STATS_CACHE_HEADERS,
    )


@router.get("/stats/sessions")
async def public_sessions(request: Request):
    _gate(request)
    raw = await sessions.get_counts()
    return JSONResponse(
        content=public_stats.project_sessions(raw),
        headers=_PUBLIC_STATS_CACHE_HEADERS,
    )


@router.get("/stats/hourly")
async def public_hourly(request: Request):
    _gate(request)
    raw = await hourly.get_counts()
    return JSONResponse(
        content=public_stats.project_hourly(raw),
        headers=_PUBLIC_STATS_CACHE_HEADERS,
    )


@router.get("/stats/devices")
async def public_devices(request: Request):
    _gate(request)
    raw = await devices.get_counts()
    return JSONResponse(
        content=public_stats.project_devices(raw),
        headers=_PUBLIC_STATS_CACHE_HEADERS,
    )


@router.get("/stats/referrers")
async def public_referrers(request: Request):
    _gate(request)
    raw = await referrers.get_counts()
    return JSONResponse(
        content=public_stats.project_referrers(raw),
        headers=_PUBLIC_STATS_CACHE_HEADERS,
    )


@router.get("/stats/events")
async def public_events(request: Request):
    _gate(request)
    raw = await events.get_counts()
    return JSONResponse(
        content=public_stats.project_events(raw),
        headers=_PUBLIC_STATS_CACHE_HEADERS,
    )


@router.get("/stats/funnel")
async def public_funnel(request: Request):
    _gate(request)
    raw = await funnel.get_counts()
    return JSONResponse(
        content=public_stats.project_funnel(raw),
        headers=_PUBLIC_STATS_CACHE_HEADERS,
    )


@router.get("/stats/retention")
async def public_retention(request: Request):
    _gate(request)
    raw = await retention.get_counts()
    return JSONResponse(
        content=public_stats.project_retention(raw),
        headers=_PUBLIC_STATS_CACHE_HEADERS,
    )


@router.get("/privacy")
async def public_privacy(request: Request):
    """Plaintext privacy notes for visitors who follow the dashboard footer
    link. Text lives in ``public_stats.PRIVACY_TEXT`` (the docs/PRIVACY.md
    file isn't copied into the production image)."""
    _gate(request)
    return PlainTextResponse(
        content=public_stats.PRIVACY_TEXT,
        headers=_PUBLIC_STATS_CACHE_HEADERS,
    )


@router.get("/stats")
async def public_stats_page(request: Request):
    """Public dashboard. Today's headline numbers are server-rendered so the
    noscript fallback shows the same values JS would surface on hydration."""
    _gate(request)
    dau_payload       = public_stats.project_dau(await dau.get_counts())
    metro_payload     = public_stats.project_geography(await geography.get_metro_summary())
    sessions_payload  = public_stats.project_sessions(await sessions.get_counts())
    hourly_payload    = public_stats.project_hourly(await hourly.get_counts())
    devices_payload   = public_stats.project_devices(await devices.get_counts())
    referrers_payload = public_stats.project_referrers(await referrers.get_counts())
    events_payload    = public_stats.project_events(await events.get_counts())
    funnel_payload    = public_stats.project_funnel(await funnel.get_counts())
    retention_payload = public_stats.project_retention(await retention.get_counts())
    return HTMLResponse(content=public_stats.render_html(
        dau_today=dau_payload.get("today"),
        metro_today=metro_payload.get("today"),
        sessions_today=sessions_payload.get("today"),
        hourly_today=hourly_payload.get("today"),
        devices_today=devices_payload.get("today"),
        referrers_today=referrers_payload.get("today"),
        events_today=events_payload.get("today"),
        funnel_today=funnel_payload.get("today"),
        retention_today=retention_payload.get("today"),
    ), headers={
        **_PUBLIC_STATS_CACHE_HEADERS,
        "Content-Security-Policy": (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "connect-src 'self'; "
            "img-src 'self' data:; "
            "frame-ancestors 'none'"
        ),
    })
