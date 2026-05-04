"""
Hour-of-day distribution counter (FEAT-004).

Privacy design: per-day 24-int array (Chicago timezone). No PII, no per-
request log — identical privacy posture to the existing DAU counter.

Increment fires only on ``/recommend``: counting *all* requests would inflate
the histogram with health checks and CTA-API polls, while ``/recommend`` is
the truer "user engagement" signal that advertisers care about.

Maintenance: nothing to maintain. The counter is a single 24-int array per
day; no thresholds, no external data sources.
"""

import asyncio
from datetime import datetime

import analytics_store
from utils import CHICAGO_TZ

HOURLY_FILE = analytics_store.data_file("hourly.json")

_lock = asyncio.Lock()
_counts: dict[str, list[int]] = {}
_current_day: str = ""
_writes_since_flush: int = 0
_FLUSH_EVERY_N_WRITES = 20

_today_chi = analytics_store.today_chi


def _now_hour_chi() -> int:
    return datetime.now(CHICAGO_TZ).hour


def _load() -> dict[str, list[int]]:
    raw = analytics_store.safe_load_json(HOURLY_FILE, {})
    # Defensive: coerce any non-list / wrong-length entry into a 24-int array
    # so older on-disk records survive a schema change without crashing.
    return {
        d: (list(map(int, v)) if isinstance(v, list) and len(v) == 24
            else [0] * 24)
        for d, v in raw.items()
    }


def _save(counts: dict[str, list[int]]) -> None:
    analytics_store.atomic_write_json(HOURLY_FILE, counts)


_counts = _load()


async def record_recommend() -> None:
    """Increment today's hourly counter for the current Chicago hour."""
    global _current_day, _writes_since_flush

    async with _lock:
        today = _today_chi()
        hour = _now_hour_chi()
        loop = asyncio.get_running_loop()

        if today != _current_day:
            new_counts = await loop.run_in_executor(None, _load)
            _counts.clear()
            _counts.update(new_counts)
            _current_day = today
            _writes_since_flush = 0

        day = _counts.setdefault(today, [0] * 24)
        day[hour] += 1
        _writes_since_flush += 1

        if _writes_since_flush >= _FLUSH_EVERY_N_WRITES:
            await loop.run_in_executor(None, _save, _counts)
            _writes_since_flush = 0


async def get_counts() -> dict[str, list[int]]:
    async with _lock:
        return {date: list(arr) for date, arr in _counts.items()}
