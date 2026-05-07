"""
HTTP middlewares: request-size cap, security headers, and the
privacy-preserving analytics dispatcher.

``register_middlewares(app, allowed_origins, max_request_bytes)`` wires all
three into the FastAPI app. Centralising them here means a future feature
that splits the analytics-eligible paths, or adds a new one, has one place
to wire in.
"""

from __future__ import annotations

import asyncio
import logging
import os
from urllib.parse import urlparse

from fastapi import FastAPI, Request

import dau
import devices
import geography
import hourly
import referrers
import retention
import sessions
from rate_limit import _client_ip

logger = logging.getLogger(__name__)


def _compute_own_hostnames(allowed_origins: list[str]) -> frozenset[str]:
    """Hostnames the browser would treat as "us" — used by the referrer counter
    to bucket internal navigations as ``direct`` rather than self-referrals.
    """
    out: set[str] = set()
    for origin in allowed_origins:
        h = urlparse(origin).hostname
        if h:
            out.add(h.lower())
    return frozenset(out)


def register_middlewares(
    app: FastAPI,
    *,
    allowed_origins: list[str],
    max_request_bytes: int,
) -> None:
    """Attach request-size, security-headers, and analytics middlewares to ``app``.

    Order matters: middlewares run in *reverse* registration order on the
    request side. Registering size first means it is the *outermost*
    request-side check, so an oversized body is rejected before any
    downstream handler runs.
    """
    own_hostnames = _compute_own_hostnames(allowed_origins)

    @app.middleware("http")
    async def _enforce_request_size(request: Request, call_next):
        """Reject oversized requests before any handler/body parsing runs."""
        cl = request.headers.get("content-length")
        if cl is not None:
            try:
                if int(cl) > max_request_bytes:
                    from fastapi.responses import JSONResponse
                    return JSONResponse(
                        status_code=413,
                        content={"detail": "Request body too large"},
                    )
            except ValueError:
                pass
        return await call_next(request)

    @app.middleware("http")
    async def _add_security_headers(request: Request, call_next):
        """Attach defense-in-depth security headers to every response."""
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = (
            "geolocation=(self), camera=(), microphone=(), payment=()"
        )
        # HSTS only when the request actually arrived over HTTPS — sending it on
        # plain HTTP is a no-op per spec but it's tidier to omit.
        proto = request.headers.get("x-forwarded-proto", request.url.scheme)
        if proto == "https":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        # /recommend echoes user origin/destination + (when BYOK is on) is shaped
        # by an Authorization header. Don't let any layer cache it. Pairs with
        # frontend/vite.config.js where the service worker is set to NetworkOnly
        # for this path.
        if request.url.path == "/recommend":
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.middleware("http")
    async def _analytics_middleware(request: Request, call_next):
        """Record privacy-preserving analytics on /ping and /recommend.

        Centralised here (not in handlers) so a future feature that splits
        these endpoints, or adds a new analytics-eligible path, has one
        place to wire in. Each counter is wrapped in try/except so an
        analytics-layer fault never breaks the user-facing request —
        analytics is best-effort.
        """
        response = await call_next(request)

        path = request.url.path
        if path not in ("/ping", "/recommend"):
            return response

        is_recommend = (path == "/recommend")
        ip = _client_ip(request)

        # All analytics counters use independent asyncio.Locks and write to
        # separate files, so they have no data dependencies between them.
        # Run them concurrently with asyncio.gather so the response isn't
        # held while each one completes one-by-one (OPT-BE-222). Each task
        # is wrapped so an analytics-layer fault never breaks the request.

        async def _safe_dau() -> None:
            try:
                await dau.record_visit(ip)
            except Exception as e:
                logger.debug("[analytics] dau.record_visit failed: %s", e)

        async def _safe_geography() -> None:
            try:
                await geography.record_visit(ip)
            except Exception as e:
                logger.debug("[analytics] geography.record_visit failed: %s", e)

        async def _safe_devices() -> None:
            try:
                await devices.record_visit(request.headers.get("user-agent"))
            except Exception as e:
                logger.debug("[analytics] devices.record_visit failed: %s", e)

        async def _safe_referrers() -> None:
            try:
                await referrers.record_visit(
                    request.headers.get("referer"),
                    own_hostnames=own_hostnames,
                )
            except Exception as e:
                logger.debug("[analytics] referrers.record_visit failed: %s", e)

        async def _safe_hourly() -> None:
            try:
                await hourly.record_recommend()
            except Exception as e:
                logger.debug("[analytics] hourly.record_recommend failed: %s", e)

        async def _safe_sessions() -> str | None:
            try:
                return await sessions.touch(
                    request.cookies.get(sessions.COOKIE_NAME),
                    is_recommend=is_recommend,
                )
            except Exception as e:
                logger.debug("[analytics] sessions.touch failed: %s", e)
                return None

        async def _safe_retention() -> str | None:
            try:
                return await retention.record_visit(
                    request.cookies.get(retention.COOKIE_NAME) or None
                )
            except Exception as e:
                logger.debug("[analytics] retention.record_visit failed: %s", e)
                return None

        # Build the task list per path. sessions/retention return values
        # used to set cookies; capture them by index after gather.
        tasks: list = [_safe_dau(), _safe_geography(), _safe_sessions()]
        sid_idx = 2
        rid_idx: int | None = None
        if is_recommend:
            tasks.append(_safe_hourly())
        else:
            # Device class + referrer fire on /ping, which the frontend hits once
            # per page load on App mount. /recommend reuses the existing session.
            # FEAT-002 retention also fires only on /ping so the same browser
            # opening multiple tabs doesn't inflate the counter.
            tasks.extend([_safe_devices(), _safe_referrers(), _safe_retention()])
            rid_idx = len(tasks) - 1

        results = await asyncio.gather(*tasks)
        sid = results[sid_idx]
        rid = results[rid_idx] if rid_idx is not None else None

        # Cookie attributes — production ships cross-site (Vercel frontend ↔
        # Railway backend, different eTLD+1) so SameSite=Lax would drop the
        # cookie on every fetch/XHR and silently break sessions, the FEAT-007
        # funnel, and FEAT-002 retention. ``samesite=None`` requires
        # ``secure=True`` per spec; both conditions hold in production.
        # Local dev keeps Lax + insecure so cookies still work over plain HTTP.
        is_prod = os.getenv("APP_ENV") == "production"
        cookie_secure = is_prod
        cookie_samesite = "none" if is_prod else "lax"
        if sid is not None:
            response.set_cookie(
                key=sessions.COOKIE_NAME,
                value=sid,
                max_age=sessions.IDLE_TIMEOUT_SECONDS,
                httponly=True,
                secure=cookie_secure,
                samesite=cookie_samesite,
                path="/",
            )
        if rid is not None:
            response.set_cookie(
                key=retention.COOKIE_NAME,
                value=rid,
                max_age=retention.COOKIE_MAX_AGE,
                httponly=True,
                secure=cookie_secure,
                samesite=cookie_samesite,
                path="/",
            )

        return response
