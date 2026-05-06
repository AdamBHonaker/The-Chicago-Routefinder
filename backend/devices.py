"""
Device-class counter (FEAT-005).

Privacy design: the User-Agent string is sent on every HTTP request anyway and
is parsed in memory only. The raw UA string is **never persisted** — only the
bucket the parser produced (``mobile`` / ``tablet`` / ``desktop`` / ``bot`` /
``unknown``) is. There is no cross-day per-user state.

Bots are recorded in their own bucket but excluded from the public mobile/
tablet/desktop split — they shouldn't reach the engagement-counted endpoints
in practice, but defense-in-depth.

Maintenance:
  * ``ua-parser`` regex DB needs periodic updates as new UA shapes ship.
    Pinned in ``requirements.txt``; bump as part of normal dependency upkeep.
  * iPad-in-desktop-mode (Safari's default since iPadOS 13) parses as
    desktop. Industry convention — accept it; don't try to detect.
"""

import asyncio
import logging
from functools import lru_cache

import analytics_store

logger = logging.getLogger(__name__)

DEVICES_FILE = analytics_store.data_file("devices.json")

_BUCKETS = ("mobile", "tablet", "desktop", "bot", "unknown")

_lock = asyncio.Lock()
_counts: dict[str, dict[str, int]] = {}
_current_day: str = ""
_writes_since_flush: int = 0
_FLUSH_EVERY_N_WRITES = 20

_today_chi = analytics_store.today_chi


def _load() -> dict[str, dict[str, int]]:
    return analytics_store.safe_load_json(DEVICES_FILE, {})


def _save(counts: dict[str, dict[str, int]]) -> None:
    analytics_store.atomic_write_json(DEVICES_FILE, counts)


def classify(user_agent: str | None) -> str:
    """Bucket a UA string into one of ``_BUCKETS``. Pure function — call from tests directly.

    Results are LRU-cached because UA strings repeat heavily across requests
    (one user makes many /ping calls; common Chrome/Safari/iOS UAs repeat
    across users), and the underlying ua-parser regex DB walk is the single
    biggest CPU cost in the analytics middleware (OPT-BE-220).
    """
    if not user_agent:
        return "unknown"
    return _classify_cached(user_agent)


@lru_cache(maxsize=1024)
def _classify_cached(user_agent: str) -> str:
    try:
        from ua_parser import user_agent_parser  # type: ignore
    except ImportError:
        # Library missing: fall back to crude heuristics so we still get *something*.
        ua = user_agent.lower()
        if any(b in ua for b in ("bot", "crawl", "spider", "slurp", "curl/", "wget/", "python-requests")):
            return "bot"
        if "ipad" in ua or "tablet" in ua:
            return "tablet"
        if "mobi" in ua or "android" in ua or "iphone" in ua:
            return "mobile"
        return "desktop"

    parsed = user_agent_parser.Parse(user_agent)
    device_family = (parsed.get("device") or {}).get("family", "") or ""
    os_family = (parsed.get("os") or {}).get("family", "") or ""
    ua_family = (parsed.get("user_agent") or {}).get("family", "") or ""

    fam_lower = (device_family + " " + ua_family).lower()
    if any(b in fam_lower for b in ("bot", "spider", "crawler", "slurp")):
        return "bot"
    if device_family.lower() in ("ipad",) or "tablet" in device_family.lower():
        return "tablet"
    if os_family in ("Android", "iOS") and device_family.lower() not in ("ipad",):
        # Android tablets parse with device_family containing "Tablet"; handled above.
        return "mobile"
    if os_family in ("Windows", "Mac OS X", "Linux", "Chrome OS", "Ubuntu"):
        return "desktop"
    return "unknown"


_counts = _load()


async def record_visit(user_agent: str | None) -> str:
    """Classify the UA and increment today's counter for that bucket. Returns the bucket."""
    global _current_day, _writes_since_flush

    bucket = classify(user_agent)

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

        day = _counts.setdefault(today, {b: 0 for b in _BUCKETS})
        # Defensive: an older on-disk record may pre-date a bucket name change.
        for b in _BUCKETS:
            day.setdefault(b, 0)
        day[bucket] += 1
        _writes_since_flush += 1

        if _writes_since_flush >= _FLUSH_EVERY_N_WRITES:
            await loop.run_in_executor(None, _save, _counts)
            _writes_since_flush = 0

    return bucket


async def get_counts() -> dict[str, dict[str, int]]:
    async with _lock:
        return {date: dict(day) for date, day in _counts.items()}
