"""
Funnel completion counter (FEAT-007).

Tracks the highest funnel stage each session reached. When a session ends
(FEAT-001 idle timeout), ``sessions.py`` calls ``record_finalized(day,
highest_stage)`` here, which increments the day's cumulative per-stage
counts. No per-session data ever reaches disk — only the aggregate array.

Funnel order (index 0 → 5):
  app_loaded → recommend_submitted → recommend_returned →
  route_selected → start_route_tapped → trip_completed

Daily aggregate on disk: ``{date: [n0, n1, n2, n3, n4, n5]}`` where
``n_i`` = number of sessions that reached *at least* stage i. Conversion
rates (e.g. "X% of sessions got a result") are derived at read time as
``n_i / n_0``. The advertiser headline is ``n_2 / n_0`` (recommend_returned
/ app_loaded).

Privacy: identical to FEAT-001 + FEAT-006. No per-session row ever
persists; the in-memory ``funnel_stage`` field in ``sessions._active`` is
discarded when the session finalises.
"""

from __future__ import annotations

import asyncio

import analytics_store

# Canonical funnel order. Do not reorder — the on-disk array is positional.
FUNNEL_STAGES: tuple[str, ...] = (
    "app_loaded",
    "recommend_submitted",
    "recommend_returned",
    "route_selected",
    "start_route_tapped",
    "trip_completed",
)
_STAGE_INDEX: dict[str, int] = {name: i for i, name in enumerate(FUNNEL_STAGES)}
_NUM_STAGES: int = len(FUNNEL_STAGES)

FUNNEL_FILE = analytics_store.data_file("funnel.json")

_lock = asyncio.Lock()
_counts: dict[str, list[int]] = {}
_writes_since_flush: int = 0
# Low flush threshold — each write represents a finalised session (same
# reasoning as sessions.py's _FLUSH_EVERY_N_WRITES = 5).
_FLUSH_EVERY_N_WRITES = 5


def stage_index(name: str) -> int:
    """Return the 0-based funnel index of ``name``, or -1 if not a stage."""
    return _STAGE_INDEX.get(name, -1)


def is_stage(name: str) -> bool:
    return name in _STAGE_INDEX


def _load() -> dict[str, list[int]]:
    raw = analytics_store.safe_load_json(FUNNEL_FILE, {})
    out: dict[str, list[int]] = {}
    for date, arr in raw.items():
        if isinstance(arr, list) and len(arr) == _NUM_STAGES:
            out[date] = [max(0, int(v)) for v in arr]
    return out


def _save(counts: dict[str, list[int]]) -> None:
    analytics_store.atomic_write_json(FUNNEL_FILE, counts)


_counts = _load()


async def record_finalized(day: str, highest_stage: int) -> None:
    """Increment stage-count slots 0..highest_stage for ``day``.

    Called by ``sessions._expire_idle_locked`` and the day-rollover path
    in ``sessions.touch`` when a session is finalised. If ``highest_stage``
    is -1 (session never reached any funnel stage) the call is a no-op.
    """
    if highest_stage < 0:
        return
    global _writes_since_flush
    async with _lock:
        loop = asyncio.get_running_loop()
        arr = _counts.setdefault(day, [0] * _NUM_STAGES)
        for i in range(min(highest_stage + 1, _NUM_STAGES)):
            arr[i] += 1
        _writes_since_flush += 1
        if _writes_since_flush >= _FLUSH_EVERY_N_WRITES:
            await loop.run_in_executor(
                None, _save, {k: list(v) for k, v in _counts.items()}
            )
            _writes_since_flush = 0


async def get_counts() -> dict[str, list[int]]:
    """Return per-day stage-count arrays (deep copy, safe to hand to caller)."""
    async with _lock:
        return {date: list(arr) for date, arr in _counts.items()}


async def force_flush_for_test() -> None:
    """Test helper: flush in-memory counts to disk synchronously."""
    async with _lock:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None, _save, {k: list(v) for k, v in _counts.items()}
        )
