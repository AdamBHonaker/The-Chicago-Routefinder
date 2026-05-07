"""
Sessions counter (FEAT-001).

Privacy design:
  * The session ID is a UUID-strength random token (``secrets.token_urlsafe``)
    set in an ``httpOnly`` ``Secure`` cookie with a 30-min sliding TTL.
    SameSite is ``None`` in production (cross-site Vercel↔Railway requires
    it for the cookie to be sent on fetch) and ``Lax`` in local dev.
    The cookie is *never* persisted across days — a fresh session begins
    after midnight Chicago even if the same browser returns.
  * The raw session ID is held in memory only for the lifetime of the
    cookie. Before any internal logging or comparison the ID is
    HMAC-SHA256-hashed with the same daily-rotating salt that ``dau.py``
    uses, so any debugging breadcrumb is uncorrelatable across days.
  * Server stores **only** an aggregate-per-day record:
    ``{date, sessions, total_duration_seconds, bounces}``. There is no
    per-session row anywhere on disk.
  * Bounce definition: a session that recorded fewer than two
    ``/recommend`` requests. Documented here and in docs/PRIVACY.md so
    advertiser-quoted bounce-rate numbers are interpretable.
  * "Session end" uses server-side idle timeout (30 min after last
    request) — simpler than a frontend ``beforeunload`` ping and good
    enough for industry-comparable numbers. Mean session length therefore
    inflates by up to 30 min for the visitor's last request; this is
    documented in the public dashboard footer.

Maintenance: ``DAILY_SALT`` is reused (no separate ``SESSION_SALT``) so
secret-management stays simple. If a strict separation is later wanted,
rotate the two on independent cadences.
"""

import asyncio
import hashlib
import hmac
import logging
import os
import secrets
import time

import analytics_store
import funnel as _funnel

logger = logging.getLogger(__name__)

SESSIONS_FILE = analytics_store.data_file("sessions.json")

_DAILY_SALT = os.getenv("DAILY_SALT", "default-insecure-salt")
if _DAILY_SALT == "default-insecure-salt" and os.getenv("APP_ENV") == "production":
    raise RuntimeError(
        "DAILY_SALT env var must be set in production. sessions.py shares the "
        "DAU module's salt; without it session-ID hashes are correlatable."
    )

# 30-min sliding TTL — both cookie and server-side idle expiry.
IDLE_TIMEOUT_SECONDS = 30 * 60
COOKIE_NAME = "sid"
# Bounces = sessions that issued fewer than this many /recommend requests
# before idle-expiring. "Only one /recommend" is the documented definition.
_BOUNCE_RECOMMEND_THRESHOLD = 2

_lock = asyncio.Lock()

# Active in-memory sessions. Key = HMAC of raw sid against today's salt.
# Value = {start, last_seen, recommend_count, day} where ``day`` is the
# Chicago date the session began on (used to attribute bounce/duration to
# that day at idle-expiry, not whatever day the cleanup happens to fire on).
_active: dict[bytes, dict] = {}

# Daily aggregates: {date: {sessions, total_duration_seconds, bounces}}.
_daily: dict[str, dict[str, int]] = {}

_current_day: str = ""
_writes_since_flush: int = 0
_FLUSH_EVERY_N_WRITES = 5  # smaller than other counters because each "write" is a finalised session


_today_chi = analytics_store.today_chi


def _hash_sid(raw_sid: str, day: str) -> bytes:
    key = (_DAILY_SALT + day).encode()
    return hmac.new(key, raw_sid.encode(), hashlib.sha256).digest()


def _load() -> dict[str, dict[str, int]]:
    return analytics_store.safe_load_json(SESSIONS_FILE, {})


def _save(daily: dict[str, dict[str, int]]) -> None:
    analytics_store.atomic_write_json(SESSIONS_FILE, daily)


_daily = _load()


def new_session_id() -> str:
    """Cryptographically random session token. ~32 chars of url-safe base64."""
    return secrets.token_urlsafe(24)


def _finalise_locked(state: dict) -> None:
    """Move an active session into the daily aggregate. Caller holds the lock."""
    day_key = state["day"]
    duration = max(0, int(state["last_seen"] - state["start"]))
    bucket = _daily.setdefault(day_key, {"sessions": 0, "total_duration_seconds": 0, "bounces": 0})
    bucket["sessions"] = int(bucket.get("sessions", 0)) + 1
    bucket["total_duration_seconds"] = int(bucket.get("total_duration_seconds", 0)) + duration
    if state["recommend_count"] < _BOUNCE_RECOMMEND_THRESHOLD:
        bucket["bounces"] = int(bucket.get("bounces", 0)) + 1
    # FEAT-007: funnel.record_finalized is async — collected and awaited by
    # the calling async function (_expire_idle_locked / touch day-rollover).


async def _expire_idle_locked(now: float, loop) -> None:
    """Finalise sessions whose last_seen is older than IDLE_TIMEOUT_SECONDS."""
    global _writes_since_flush
    cutoff = now - IDLE_TIMEOUT_SECONDS
    expired = [(h, s) for h, s in _active.items() if s["last_seen"] < cutoff]
    if not expired:
        return
    for h, s in expired:
        _finalise_locked(s)
        _active.pop(h, None)
        _writes_since_flush += 1
    if _writes_since_flush >= _FLUSH_EVERY_N_WRITES:
        await loop.run_in_executor(None, _save, _daily)
        _writes_since_flush = 0
    # FEAT-007: record funnel stage for each expired session after the
    # sessions lock is still held (funnel uses its own independent lock).
    for _, s in expired:
        await _funnel.record_finalized(s["day"], s.get("funnel_stage", -1))


async def touch(raw_sid: str | None, *, is_recommend: bool) -> str:
    """Update or create the session for ``raw_sid``. Returns the (possibly new) raw sid.

    If ``raw_sid`` is None or unknown to us, a new session is started and a
    fresh sid is returned (the middleware sets it as a cookie). The hash key
    used for in-memory bookkeeping rotates with the daily salt; sessions
    started today will not match a cookie issued yesterday, so the day
    boundary cleanly resets bookkeeping without any explicit "midnight
    rollover" code.
    """
    global _current_day, _writes_since_flush

    now = time.time()
    async with _lock:
        today = _today_chi()
        loop = asyncio.get_running_loop()

        if today != _current_day:
            # Day rolled over. Finalise every still-active session against
            # whichever day it began on (its ``day`` field), then drop the
            # in-memory map — the new day's hashes won't match anyway.
            # Capture funnel stages before clearing _active (FEAT-007).
            rollover_funnel = [
                (s["day"], s.get("funnel_stage", -1))
                for s in _active.values()
            ]
            for s in list(_active.values()):
                _finalise_locked(s)
            _active.clear()
            new_daily = await loop.run_in_executor(None, _load)
            for d, v in new_daily.items():
                if d not in _daily:
                    _daily[d] = v
            # Persist the freshly-finalised previous-day rows immediately so a
            # restart between rollover and the next idle-flush boundary doesn't
            # silently drop them from disk.
            await loop.run_in_executor(None, _save, _daily)
            _current_day = today
            _writes_since_flush = 0
            # Record funnel stages for rolled-over sessions (FEAT-007).
            for day, stage in rollover_funnel:
                await _funnel.record_finalized(day, stage)

        # Lazy idle cleanup: cheap because _active is small in practice.
        await _expire_idle_locked(now, loop)

        sid = raw_sid
        h = _hash_sid(sid, today) if sid else None
        if not h or h not in _active:
            sid = new_session_id()
            h = _hash_sid(sid, today)
            _active[h] = {
                "start": now,
                "last_seen": now,
                "recommend_count": 1 if is_recommend else 0,
                "day": today,
                "funnel_stage": -1,  # FEAT-007: highest funnel stage reached
            }
        else:
            s = _active[h]
            s["last_seen"] = now
            if is_recommend:
                s["recommend_count"] += 1
        return sid  # type: ignore[return-value]


async def advance_funnel_stage(raw_sid: str | None, event_name: str) -> None:
    """Advance the funnel stage for the session identified by ``raw_sid``.

    Called from the ``POST /events`` handler and from the ``/recommend``
    handler (for the server-side ``recommend_returned`` event). If the event
    is not a funnel stage, or the session is not currently active (expired /
    cross-day), the call is a silent no-op.
    """
    if not raw_sid:
        return
    stage = _funnel.stage_index(event_name)
    if stage < 0:
        return
    async with _lock:
        today = _today_chi()
        h = _hash_sid(raw_sid, today)
        s = _active.get(h)
        if s is None:
            return
        if stage > s.get("funnel_stage", -1):
            s["funnel_stage"] = stage


async def get_counts() -> dict[str, dict[str, float | int]]:
    """Return per-day aggregates, decorated with derived avg-duration and bounce-rate."""
    async with _lock:
        out: dict[str, dict[str, float | int]] = {}
        for date, bucket in _daily.items():
            sessions = int(bucket.get("sessions", 0))
            total = int(bucket.get("total_duration_seconds", 0))
            bounces = int(bucket.get("bounces", 0))
            avg = (total / sessions) if sessions else 0.0
            bounce_rate = (100.0 * bounces / sessions) if sessions else 0.0
            out[date] = {
                "sessions": sessions,
                "total_duration_seconds": total,
                "bounces": bounces,
                "avg_duration_seconds": round(avg, 1),
                "bounce_rate_pct": round(bounce_rate, 1),
            }
        return out


async def force_flush_for_test() -> None:
    """Test helper: persist the in-memory aggregates to disk synchronously."""
    async with _lock:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _save, _daily)
