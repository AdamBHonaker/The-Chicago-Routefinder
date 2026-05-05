"""
Per-IP rate limiting for /recommend and the geocode endpoints.

Owns the three sliding-window stores (RPM/RPH for /recommend, rolling-24h for
the Anthropic-budget cap, and a separate bucket for /autocomplete +
/reverse-geocode) plus the ``_client_ip`` helper that extracts an
unspoofable IP from Railway's trusted proxy headers.

All state lives here so a future tweak to the limiter (e.g. moving to a
token-bucket or to Redis) only touches this module.
"""

from __future__ import annotations

import asyncio
import collections
import os
import threading
import time

from fastapi import Request

# ---------------------------------------------------------------------------
# Configuration — env-driven so deployments can tune without a code change
# ---------------------------------------------------------------------------
# To enable: add RATE_LIMIT_ENABLED=true to backend/.env (or Railway env vars).
# Tune the caps with RATE_LIMIT_RPM (per minute) and RATE_LIMIT_RPH (per hour).
# Both limits must pass on every request — the stricter one wins.
# BYOK requests count against per-IP limits just like shared-quota requests.
_RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "false").lower() == "true"
_RATE_LIMIT_RPM     = int(os.getenv("RATE_LIMIT_RPM", "10"))   # max /recommend per minute per IP
_RATE_LIMIT_RPH     = int(os.getenv("RATE_LIMIT_RPH", "50"))   # max /recommend per hour per IP
# Per-IP rolling-24h cap on /recommend so a single attacker can't drain the
# Anthropic budget overnight. Independent of RPM/RPH; the stricter limit wins.
_RATE_LIMIT_DAILY   = int(os.getenv("RATE_LIMIT_DAILY", "50"))
# Geocode-bucket caps cover /autocomplete + /reverse-geocode. UI typing is
# bursty so RPM is set higher than /recommend; per-hour caps the long tail.
_GEOCODE_RPM        = int(os.getenv("GEOCODE_RPM", "60"))
_GEOCODE_RPH        = int(os.getenv("GEOCODE_RPH", "600"))
# Events-bucket caps cover /events (FEAT-006). Higher than geocode because
# a normal session naturally fires several events back-to-back (app_loaded,
# recommend_submitted, route_selected, start_route_tapped, …) and we don't
# want a chatty-but-legitimate user to trip the limit. Still tight enough
# to make metric-poisoning expensive.
_EVENTS_RPM         = int(os.getenv("EVENTS_RPM", "120"))
_EVENTS_RPH         = int(os.getenv("EVENTS_RPH", "1200"))

# ---------------------------------------------------------------------------
# Locks — note: two distinct lock kinds because /recommend handlers are async
# and the geocode handlers run in FastAPI's threadpool.
# ---------------------------------------------------------------------------
# Shared lock protecting both _rate_store and _response_cache (held by main.py
# during the rate-limit + cache-read critical section in /recommend).
# asyncio.Lock() is correct here (not threading.Lock) because recommend() is
# async and awaits between cache read and cache write — the await yields
# control to the event loop, allowing a second coroutine to observe a stale
# miss and launch a duplicate expensive request, or to interleave partial
# reads/writes. Holding the lock around the check+read and again around the
# write eliminates both the duplicate-computation stampede and the eviction
# double-pop.
_store_lock = asyncio.Lock()

# Geocode endpoints have sync handlers (called from FastAPI's threadpool),
# so a threading.Lock — not asyncio.Lock — is needed when their rate-limit
# checks race with each other across threads.
_geocode_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Stores — ip → deque of monotonic timestamps. Each rate-limit "bucket" gets
# its own dict so /recommend caps don't share state with autocomplete bursts.
# ---------------------------------------------------------------------------
_rate_store:          dict[str, collections.deque] = {}   # /recommend RPM/RPH
_daily_quota_store:   dict[str, collections.deque] = {}   # /recommend rolling 24h
_geocode_rate_store:  dict[str, collections.deque] = {}   # /autocomplete + /reverse-geocode
_events_rate_store:   dict[str, collections.deque] = {}   # /events (FEAT-006)


def _client_ip(http_request: Request) -> str:
    """Extract client IP, using Railway's trusted proxy headers to prevent spoofing.

    Clients can freely forge any entries at the start of X-Forwarded-For. Railway's
    load balancer appends the actual connection IP at the end of the chain, so reading
    the last entry gives the IP Railway observed — which a client cannot forge.
    X-Real-IP (if present) is preferred as it is set exclusively by the Railway LB.
    """
    real_ip = http_request.headers.get("x-real-ip", "").strip()
    if real_ip:
        return real_ip
    forwarded = http_request.headers.get("x-forwarded-for", "")
    if forwarded:
        # Use the last (rightmost) entry — appended by Railway's LB, not client-supplied
        return forwarded.split(",")[-1].strip()
    return http_request.client.host if http_request.client else "unknown"


def _check_rate_limit(
    ip: str,
    *,
    store: dict[str, collections.deque] | None = None,
    rpm: int | None = None,
    rph: int | None = None,
    window_seconds: int = 3600,
) -> bool:
    """
    Return True (request allowed) or False (rate-limited).
    Always returns True when _RATE_LIMIT_ENABLED is False.

    Sliding-window: per-minute AND per-`window_seconds` caps must both pass.
    Default args target the /recommend bucket; pass `store`/`rpm`/`rph` to
    enforce a separate bucket (e.g. geocode endpoints).

    Callers must hold the lock that guards the chosen `store`.
    """
    if not _RATE_LIMIT_ENABLED:
        return True
    if store is None:
        store = _rate_store
    if rpm is None:
        rpm = _RATE_LIMIT_RPM
    if rph is None:
        rph = _RATE_LIMIT_RPH
    now = time.monotonic()
    window = store.get(ip)
    if window is None:
        window = collections.deque()
    else:
        # Evict timestamps older than the window to bound memory growth
        while window and now - window[0] > window_seconds:
            window.popleft()
        # If the deque emptied during eviction, drop the key so the store does
        # not accumulate one entry per unique IP forever. The deque is
        # reattached to the dict below only if we actually record a timestamp.
        if not window:
            del store[ip]
    # Per-window check
    if len(window) >= rph:
        return False
    # Per-minute check — iterate from the right (newest entries) and stop as
    # soon as we exceed the 60-second window. Because the deque is insertion-
    # ordered (ascending), the rightmost entry is always the most recent, so
    # we stop early as soon as we hit a timestamp older than 60 s instead of
    # scanning all hourly entries.
    recent = 0
    for t in reversed(window):
        if now - t <= 60:
            recent += 1
        else:
            break
    if recent >= rpm:
        return False
    window.append(now)
    store[ip] = window
    return True


def _check_daily_quota(ip: str) -> bool:
    """Per-IP rolling-24h cap on /recommend. Caller must hold _store_lock."""
    if not _RATE_LIMIT_ENABLED:
        return True
    now = time.monotonic()
    window = _daily_quota_store.get(ip)
    if window is None:
        window = collections.deque()
    else:
        while window and now - window[0] > 86400:
            window.popleft()
        if not window:
            del _daily_quota_store[ip]
    if len(window) >= _RATE_LIMIT_DAILY:
        return False
    window.append(now)
    _daily_quota_store[ip] = window
    return True


def _check_geocode_rate_limit(ip: str) -> bool:
    """Rate-limit for /autocomplete + /reverse-geocode. Acquires its own lock."""
    with _geocode_lock:
        return _check_rate_limit(
            ip,
            store=_geocode_rate_store,
            rpm=_GEOCODE_RPM,
            rph=_GEOCODE_RPH,
        )


def _check_events_rate_limit(ip: str) -> bool:
    """Rate-limit for /events (FEAT-006). Reuses _geocode_lock — a separate
    threading.Lock would be wasteful for two sync handlers that both rarely
    contend, and the lock only protects deque ops (microseconds)."""
    with _geocode_lock:
        return _check_rate_limit(
            ip,
            store=_events_rate_store,
            rpm=_EVENTS_RPM,
            rph=_EVENTS_RPH,
        )
