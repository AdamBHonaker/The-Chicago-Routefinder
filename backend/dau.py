"""
Daily Unique User (DAU) counter.

Privacy design: client IPs are HMAC-SHA256 hashed with a daily salt and kept
only in an in-memory set for the current UTC day. When the day rolls over the
set is discarded and only the final count is written to disk. Cross-day
correlation is impossible because the daily salt changes.

No IP address, fingerprint, cookie, or user identifier is ever persisted.
"""

import asyncio
import hashlib
import hmac
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

# Railway production path; fall back to a local path during development.
if os.getenv("APP_ENV") == "production":
    DAU_FILE = Path("/app/data/dau.json")
else:
    DAU_FILE = Path(__file__).parent / "data" / "dau.json"

DAU_FILE.parent.mkdir(parents=True, exist_ok=True)

# Module-level in-memory state — protected by _lock.
_current_day: str = ""
_seen_hashes: set[str] = set()
_lock = asyncio.Lock()

# Daily salt — must be set in Railway env vars (DAILY_SALT).
# Combined with today's UTC date string before use as the HMAC key.
_DAILY_SALT = os.getenv("DAILY_SALT", "default-insecure-salt")


def _today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _load() -> dict[str, int]:
    try:
        with open(DAU_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save(counts: dict[str, int]) -> None:
    """Atomic write via temp file + os.replace."""
    tmp_fd, tmp_path = tempfile.mkstemp(dir=DAU_FILE.parent, suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            json.dump(counts, f)
        os.replace(tmp_path, DAU_FILE)
    except Exception:
        os.unlink(tmp_path)
        raise


async def record_visit(ip: str) -> None:
    """Hash the IP against today's salt and increment today's unique-visitor count."""
    global _current_day, _seen_hashes

    today = _today_utc()
    hmac_key = (_DAILY_SALT + today).encode()
    digest = hmac.new(hmac_key, ip.encode(), hashlib.sha256).hexdigest()

    async with _lock:
        if today != _current_day:
            # Day rolled over: flush previous day's count and reset state.
            if _current_day:
                counts = _load()
                counts[_current_day] = len(_seen_hashes)
                _save(counts)
            _seen_hashes = set()
            _current_day = today

        if digest in _seen_hashes:
            return  # already counted today

        _seen_hashes.add(digest)
        counts = _load()
        counts[today] = len(_seen_hashes)
        _save(counts)


async def get_counts() -> dict[str, int]:
    """Return the persisted DAU counts dict (does not include today's live in-memory count)."""
    return _load()
