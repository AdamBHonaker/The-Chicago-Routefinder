"""
Referrer / traffic-source counter (FEAT-008).

Privacy design: the ``Referer`` header is sent by the browser on every cross-
site navigation anyway. We extract only the **hostname** (path and query
stripped server-side, before any storage, so accidental UTM-params containing
PII never reach disk) and bucket into ``direct`` / ``search`` / ``social`` /
``other``. The "other" bucket itself stores per-hostname counts so a press
mention from e.g. ``chicagotribune.com`` is visible.

There is no cross-day per-user state and no per-request log — only the daily
aggregate.

Maintenance:
  * The search and social hostname lists churn slowly. Hardcoded constants
    here; edit when a new search engine or social platform becomes
    significant in real referrer traffic.
  * UTM params (``utm_source`` / ``utm_campaign``) are deliberately not
    captured — they cross into "tracking" since they often identify a
    specific outreach. Re-add as a separate feature only if a marketing
    campaign actually launches.
"""

import asyncio
from typing import Any
from urllib.parse import urlparse

import analytics_store

REFERRERS_FILE = analytics_store.data_file("referrers.json")

_SEARCH_HOSTS: frozenset[str] = frozenset({
    "duckduckgo.com", "ecosia.org", "kagi.com", "brave.com", "yahoo.com",
    "yandex.com", "baidu.com", "qwant.com", "startpage.com", "you.com",
    "perplexity.ai", "search.marginalia.nu",
})
# Patterns matched as suffix because Google/Bing have many TLDs (.com, .co.uk,
# .com.au, etc.) and their subdomains (www.google.com, m.google.com).
_SEARCH_SUFFIXES: tuple[str, ...] = (
    ".google.com", ".google.co.uk", ".google.ca", ".google.de", ".google.fr",
    "google.com", "bing.com", ".bing.com",
)

_SOCIAL_HOSTS: frozenset[str] = frozenset({
    "facebook.com", "m.facebook.com", "l.facebook.com",
    "x.com", "twitter.com", "t.co", "mobile.twitter.com",
    "instagram.com", "l.instagram.com",
    "threads.net",
    "reddit.com", "old.reddit.com", "new.reddit.com", "i.reddit.com",
    "linkedin.com", "lnkd.in", "www.linkedin.com",
    "tiktok.com", "vm.tiktok.com",
    "youtube.com", "m.youtube.com", "youtu.be",
    "bsky.app", "bsky.social",
    "mastodon.social",
    "pinterest.com", "pin.it",
})

_lock = asyncio.Lock()
# {date: {"direct": int, "search": int, "social": int, "other": {hostname: int}}}
_counts: dict[str, dict[str, Any]] = {}
_current_day: str = ""
_writes_since_flush: int = 0
_FLUSH_EVERY_N_WRITES = 20


_today_chi = analytics_store.today_chi


def _load() -> dict[str, dict[str, Any]]:
    return analytics_store.safe_load_json(REFERRERS_FILE, {})


def _save(counts: dict[str, dict[str, Any]]) -> None:
    analytics_store.atomic_write_json(REFERRERS_FILE, counts)


def classify(referer: str | None, *, own_hostnames: frozenset[str] = frozenset()) -> tuple[str, str | None]:
    """Bucket a Referer header into (bucket, hostname).

    Returns one of:
      * ("direct", None)     — empty/missing Referer or self-referral
      * ("search", host)     — known search engine
      * ("social", host)     — known social platform
      * ("other", host)      — anything else, with the bare hostname

    ``hostname`` is provided for ``other`` so the per-hostname long tail can
    be aggregated; ``search`` and ``social`` return the host for completeness
    but the public projection collapses them into the bucket only.

    Path and query string are stripped before any storage decision is made.
    """
    if not referer:
        return ("direct", None)
    try:
        parsed = urlparse(referer.strip())
    except Exception:
        return ("direct", None)
    host = (parsed.hostname or "").lower()
    if not host:
        return ("direct", None)
    # Self-referral counts as direct (e.g. an internal navigation).
    if host in own_hostnames:
        return ("direct", None)
    if host in _SEARCH_HOSTS or any(host.endswith(s) for s in _SEARCH_SUFFIXES):
        return ("search", host)
    if host in _SOCIAL_HOSTS:
        return ("social", host)
    return ("other", host)


_counts = _load()


async def record_visit(referer: str | None, *, own_hostnames: frozenset[str] = frozenset()) -> str:
    """Classify the Referer and increment today's counter. Returns the bucket name."""
    global _current_day, _writes_since_flush

    bucket, host = classify(referer, own_hostnames=own_hostnames)

    async with _lock:
        today = _today_chi()
        loop = asyncio.get_running_loop()

        if today != _current_day:
            new_counts = await loop.run_in_executor(None, _load)
            _counts.clear()
            _counts.update(new_counts)
            _current_day = today
            _writes_since_flush = 0

        day = _counts.setdefault(today, {"direct": 0, "search": 0, "social": 0, "other": {}})
        # Backfill missing fields for a record written before a schema tweak.
        day.setdefault("direct", 0); day.setdefault("search", 0)
        day.setdefault("social", 0); day.setdefault("other", {})

        if bucket == "other" and host:
            day["other"][host] = int(day["other"].get(host, 0)) + 1
        else:
            day[bucket] = int(day[bucket]) + 1

        _writes_since_flush += 1
        if _writes_since_flush >= _FLUSH_EVERY_N_WRITES:
            await loop.run_in_executor(None, _save, _counts)
            _writes_since_flush = 0

    return bucket


async def get_counts() -> dict[str, dict[str, Any]]:
    async with _lock:
        out: dict[str, dict[str, Any]] = {}
        for date, day in _counts.items():
            out[date] = {
                "direct": int(day.get("direct", 0)),
                "search": int(day.get("search", 0)),
                "social": int(day.get("social", 0)),
                "other": dict(day.get("other", {})),
            }
        return out
