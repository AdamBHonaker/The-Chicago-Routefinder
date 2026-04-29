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
import json
import logging
import os
import tempfile
import time
from datetime import datetime
from pathlib import Path
from utils import CHICAGO_TZ

# Railway production path; fall back to a local path during development.
if os.getenv("APP_ENV") == "production":
    DAU_FILE = Path("/app/data/dau.json")
else:
    DAU_FILE = Path(__file__).parent / "data" / "dau.json"

DAU_FILE.parent.mkdir(parents=True, exist_ok=True)

# Daily salt — must be set in Railway env vars (DAILY_SALT).
# Combined with today's Chicago date string before use as the HMAC key.
_DAILY_SALT = os.getenv("DAILY_SALT", "default-insecure-salt")

if _DAILY_SALT == "default-insecure-salt" and os.getenv("APP_ENV") == "production":
    logging.getLogger(__name__).warning(
        "DAILY_SALT env var is not set in production. "
        "IP hashes are using a predictable constant — set DAILY_SALT in Railway env vars "
        "to restore the cross-day privacy guarantee."
    )


def _today_chi() -> str:
    return datetime.now(CHICAGO_TZ).strftime("%Y-%m-%d")


def _load() -> dict[str, int]:
    try:
        with open(DAU_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save(counts: dict[str, int]) -> None:
    """Atomic write via temp file + os.replace."""
    tmp_fd, tmp_path = tempfile.mkstemp(dir=DAU_FILE.parent, suffix=".tmp")
    fdopen_ok = False
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            fdopen_ok = True
            json.dump(counts, f)
        os.replace(tmp_path, DAU_FILE)
    except Exception:
        if not fdopen_ok:
            os.close(tmp_fd)
        os.unlink(tmp_path)
        raise


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

        # Compute the digest after confirming today is the authoritative date.
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
