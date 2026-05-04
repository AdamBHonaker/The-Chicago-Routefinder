"""
Daily Unique User (DAU) counter.

Privacy design: client IPs are HMAC-SHA256 hashed with a daily salt and kept
only in an in-memory set for the current Chicago (CT) day. When the day rolls over the
set is discarded and only the final count is written to disk. Cross-day
correlation is impossible because the daily salt changes.

No IP address, fingerprint, cookie, or user identifier is ever persisted.
"""

import asyncio
import hashlib
import hmac
import os
import time

import analytics_store

DAU_FILE = analytics_store.data_file("dau.json")

# Daily salt — must be set in Railway env vars (DAILY_SALT).
# Combined with today's Chicago date string before use as the HMAC key.
_DAILY_SALT = os.getenv("DAILY_SALT", "default-insecure-salt")

# Fail-closed in production: a predictable salt makes IP hashes correlatable
# across days, breaking the privacy guarantee in the module docstring.
if _DAILY_SALT == "default-insecure-salt" and os.getenv("APP_ENV") == "production":
    raise RuntimeError(
        "DAILY_SALT env var must be set in production. "
        "Without it, IP hashes use a predictable constant and DAU counters "
        "lose their cross-day privacy guarantee."
    )


_today_chi = analytics_store.today_chi


def _load() -> dict[str, int]:
    return analytics_store.safe_load_json(DAU_FILE, {})


def _save(counts: dict[str, int]) -> None:
    analytics_store.atomic_write_json(DAU_FILE, counts)


# Module-level in-memory state — protected by _lock.
_current_day: str = ""
_seen_hashes: set[bytes] = set()
# Visitors already counted for today before this server process started.
# Loaded from disk when the day initialises so a restart doesn't overwrite them.
_base_count: int = 0
_lock = asyncio.Lock()

# Cached HMAC key for today: (_DAILY_SALT + current_day).encode().
# Recomputed once per day on rollover; avoids per-visit string concat + encode.
_today_hmac_key: bytes = b""

# In-memory mirror of the persisted counts dict — initialised at import time.
# Eliminates the disk read that previously happened on every new unique visitor:
# record_visit() updates this dict and saves it without calling _load() at all
# during normal operation.
_counts_cache: dict[str, int] = _load()

# Batch-write controls: flush to disk every _DAU_WRITE_BATCH new unique visitors
# OR every _DAU_FLUSH_INTERVAL_SECONDS, whichever comes first.
_DAU_WRITE_BATCH = 20
_DAU_FLUSH_INTERVAL_SECONDS = 30
_visitors_since_last_flush: int = 0
_last_flush_time: float = 0.0


async def record_visit(ip: str) -> None:
    """Hash the IP against today's salt and increment today's unique-visitor count."""
    global _current_day, _seen_hashes, _base_count, _today_hmac_key, _visitors_since_last_flush, _last_flush_time

    # Compute the digest before acquiring the lock to shorten the critical
    # section. The key bytes embed today's date string, so if `snap_key` still
    # equals `_today_hmac_key` after we acquire the lock, the precomputed
    # digest used the authoritative key. On server start (snap_key == b"") or
    # when a concurrent coroutine rolls the day forward inside the lock,
    # `snap_key != _today_hmac_key` and we recompute below.
    snap_key = _today_hmac_key
    snap_digest = hmac.new(snap_key, ip.encode(), hashlib.sha256).digest() if snap_key else None

    async with _lock:
        # Recompute today inside the lock so a coroutine that was queued just
        # before midnight cannot observe a stale date after another coroutine
        # has already rolled the day forward.
        today = _today_chi()
        loop = asyncio.get_running_loop()

        if today != _current_day:
            # Day rolled over (or first request after server startup): flush
            # previous day's final count and reset in-memory state.
            if _current_day:
                _counts_cache[_current_day] = _base_count + len(_seen_hashes)
                await loop.run_in_executor(None, _save, _counts_cache)
            # Reload from disk so counts written by a previous process instance
            # (e.g. after a mid-day restart) are not lost.
            new_counts = await loop.run_in_executor(None, _load)
            _counts_cache.clear()
            _counts_cache.update(new_counts)
            _seen_hashes = set()
            _current_day = today
            _today_hmac_key = (_DAILY_SALT + today).encode()
            _base_count = _counts_cache.get(today, 0)
            _visitors_since_last_flush = 0
            _last_flush_time = time.monotonic()

        if snap_digest is not None and snap_key == _today_hmac_key:
            digest = snap_digest
        else:
            digest = hmac.new(_today_hmac_key, ip.encode(), hashlib.sha256).digest()

        if digest in _seen_hashes:
            return  # already counted today

        _seen_hashes.add(digest)
        _counts_cache[today] = _base_count + len(_seen_hashes)
        _visitors_since_last_flush += 1

        if _visitors_since_last_flush >= _DAU_WRITE_BATCH or time.monotonic() - _last_flush_time >= _DAU_FLUSH_INTERVAL_SECONDS:
            now = time.monotonic()
            await loop.run_in_executor(None, _save, _counts_cache)
            _visitors_since_last_flush = 0
            _last_flush_time = now


async def get_counts() -> dict[str, int]:
    """Return current DAU counts, including in-flight visits not yet flushed to disk."""
    async with _lock:
        today = _today_chi()
        snapshot = dict(_counts_cache)
        if _current_day == today:
            snapshot[today] = _base_count + len(_seen_hashes)
        return snapshot
