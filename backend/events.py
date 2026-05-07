"""
Event-counter (FEAT-006).

Privacy design: only a daily aggregate ``{date: {event_name: count}}`` is
persisted. There is no per-event row, no per-session event trail, no IP, no
UA. The session-cookie ``sid`` may be passed in by the analytics middleware
so a future funnel feature (FEAT-007) can mark "session reached state X" in
memory; FEAT-006 itself does not store anything per-session.

Allowlist enforcement: unknown event names are rejected at the API edge so a
metric-poisoning attempt (junk names flooding the file with one-off keys)
can't expand the on-disk schema. The allowlist is hardcoded here; adding a
new event is a code change, not an env-var flip.

Maintenance:
  * ``EVENT_ALLOWLIST`` is the canonical list. Add a name when a new
    instrumented action lands; never remove a name without a docs entry,
    since the on-disk file may already contain historical counts under it.
  * ``_FLUSH_EVERY_N_WRITES`` (20) matches the other counters; events are
    bursty but each is a single int increment, so a kill -9 between flushes
    drops at most 20 events — acceptable for an aggregate counter.
"""

from __future__ import annotations

import asyncio

import analytics_store

EVENTS_FILE = analytics_store.data_file("events.json")

# Hardcoded allowlist. ``recommend_returned`` is fired server-side from the
# /recommend handler; the rest fire from the frontend via the track() helper.
# ``house_ad_clicked`` has no call site yet — reserved for the upcoming house-
# ad surface so the on-disk schema doesn't need a backfill when that lands.
EVENT_ALLOWLIST: frozenset[str] = frozenset({
    "app_loaded",
    "recommend_submitted",
    "recommend_returned",
    "route_selected",
    "start_route_tapped",
    "map_opened",
    "house_ad_clicked",
    "trip_completed",
    "trip_off_route",
    "trip_rerouted",
    "off_route_dismissed",
})

_lock = asyncio.Lock()
_counts: dict[str, dict[str, int]] = {}
_current_day: str = ""
_writes_since_flush: int = 0
_FLUSH_EVERY_N_WRITES = 20

_today_chi = analytics_store.today_chi


def _load() -> dict[str, dict[str, int]]:
    raw = analytics_store.safe_load_json(EVENTS_FILE, {})
    out: dict[str, dict[str, int]] = {}
    for date, day in raw.items():
        if not isinstance(day, dict):
            continue
        out[date] = {k: int(v) for k, v in day.items() if isinstance(v, (int, float))}
    return out


def _save(counts: dict[str, dict[str, int]]) -> None:
    analytics_store.atomic_write_json(EVENTS_FILE, counts)


_counts = _load()


def is_allowed(name: str) -> bool:
    return name in EVENT_ALLOWLIST


async def record(name: str) -> None:
    """Increment today's counter for ``name``. Caller must have validated against
    ``EVENT_ALLOWLIST`` first — this function asserts on unknown names so a
    future contributor can't bypass the API-edge check by calling record()
    directly."""
    if name not in EVENT_ALLOWLIST:
        raise ValueError(f"Unknown event name: {name!r}")

    global _current_day, _writes_since_flush
    async with _lock:
        today = _today_chi()
        loop = asyncio.get_running_loop()

        if today != _current_day:
            # Flush any pending in-memory updates first so up to
            # _FLUSH_EVERY_N_WRITES - 1 unflushed previous-day increments
            # aren't discarded by the reload.
            if _counts and _writes_since_flush > 0:
                await loop.run_in_executor(None, _save, _counts)
            new_counts = await loop.run_in_executor(None, _load)
            # Merge instead of clearing so any in-memory rows that the disk
            # snapshot lacks are preserved.
            for d, day_counts in new_counts.items():
                if d not in _counts:
                    _counts[d] = day_counts
            _current_day = today
            _writes_since_flush = 0

        day = _counts.setdefault(today, {})
        day[name] = int(day.get(name, 0)) + 1
        _writes_since_flush += 1

        if _writes_since_flush >= _FLUSH_EVERY_N_WRITES:
            await loop.run_in_executor(None, _save, _counts)
            _writes_since_flush = 0


async def get_counts() -> dict[str, dict[str, int]]:
    async with _lock:
        return {date: dict(day) for date, day in _counts.items()}


async def force_flush_for_test() -> None:
    """Test helper: persist the in-memory counts synchronously."""
    async with _lock:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _save, _counts)
