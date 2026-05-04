"""
Admin-only analytics endpoints (``/admin/*``).

All endpoints share a single ``DAU_ADMIN_TOKEN`` Bearer-token gate. Each
returns the raw, internal-shape counters; the public projection at
``/stats/*`` is in ``routes/stats.py``.
"""

from __future__ import annotations

import os
import secrets

from fastapi import APIRouter, Header, HTTPException, Request

import dau
import devices
import geography
import hourly
import referrers
import sessions

router = APIRouter()


def _check_admin_token(request: Request, authorization: str | None) -> None:
    """Shared admin-token gate for /admin/* endpoints. Raises 403 on failure.

    Defense-in-depth: refuse plaintext HTTP in production. Railway terminates
    TLS upstream, so a request reaching us with x-forwarded-proto != https
    indicates either a misconfiguration or a direct internal call.
    """
    token = os.getenv("DAU_ADMIN_TOKEN", "")
    if os.getenv("APP_ENV") == "production":
        proto = request.headers.get("x-forwarded-proto", request.url.scheme)
        if proto != "https":
            raise HTTPException(status_code=403, detail="Forbidden")
    if not token or not authorization:
        raise HTTPException(status_code=403, detail="Forbidden")
    expected = f"Bearer {token}"
    # Constant-time comparison to defeat timing oracles on the admin token.
    if not secrets.compare_digest(authorization, expected):
        raise HTTPException(status_code=403, detail="Forbidden")


@router.get("/admin/dau")
async def admin_dau(
    request: Request,
    authorization: str | None = Header(default=None),
):
    _check_admin_token(request, authorization)
    return await dau.get_counts()


@router.get("/admin/geography")
async def admin_geography(
    request: Request,
    authorization: str | None = Header(default=None),
):
    """Per-day per-city visitor counts (FEAT-003). Requires DAU_ADMIN_TOKEN."""
    _check_admin_token(request, authorization)
    cities = await geography.get_counts()
    metro = await geography.get_metro_summary()
    return {"cities": cities, "metro": metro}


@router.get("/admin/sessions")
async def admin_sessions(
    request: Request,
    authorization: str | None = Header(default=None),
):
    """Per-day session aggregates (FEAT-001)."""
    _check_admin_token(request, authorization)
    return await sessions.get_counts()


@router.get("/admin/hourly")
async def admin_hourly(
    request: Request,
    authorization: str | None = Header(default=None),
):
    """Per-day 24-hour /recommend histogram (FEAT-004)."""
    _check_admin_token(request, authorization)
    return await hourly.get_counts()


@router.get("/admin/devices")
async def admin_devices(
    request: Request,
    authorization: str | None = Header(default=None),
):
    """Per-day device-class counts (FEAT-005)."""
    _check_admin_token(request, authorization)
    return await devices.get_counts()


@router.get("/admin/referrers")
async def admin_referrers(
    request: Request,
    authorization: str | None = Header(default=None),
):
    """Per-day referrer/traffic-source counts (FEAT-008)."""
    _check_admin_token(request, authorization)
    return await referrers.get_counts()
