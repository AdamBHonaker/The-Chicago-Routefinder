"""
Approximate-geography counter (FEAT-003).

Privacy design: the request IP is fed to MaxMind GeoLite2-City **in memory only**
to derive a coarse city name. The IP itself is never written to disk and the
mapping IP→city is never persisted; only a per-day, per-city integer counter is.
Cities seen fewer times than ``_OTHER_BUCKET_THRESHOLD`` for the day collapse
into an ``"Other"`` bucket on read so a rare suburb never identifies a single
visitor. The "Chicago metro" rollup is computed at read time from
``_CHICAGO_METRO_CITIES`` — never stored — so the metro list can be edited
without rewriting historical data.

No PII, fingerprint, or cookie is involved. The DB itself is downloaded at
Docker build time (or vendored locally) and is treated as read-only data.

Maintenance:
  * GeoLite2-City must be refreshed monthly. MaxMind publishes updates on
    Tuesdays; the Dockerfile pulls the latest at every image build, so a deploy
    cadence of at least monthly keeps the DB fresh. If deploys go quiet, set a
    calendar reminder to redeploy on the first Tuesday of each month.
  * ``geoip2`` python SDK pin is in ``requirements.txt`` — bump in lockstep
    with security advisories.
  * ``_OTHER_BUCKET_THRESHOLD`` is the privacy floor: cities below this count
    on a given day are bucketed into ``"Other"`` at read time. Reduce only if
    DAU grows enough that 5 stops being a meaningful disclosure threshold.
  * ``_CHICAGO_METRO_CITIES`` is the canonical metro rollup list (Cook + the
    five collar counties' principal municipalities). Edit when adding suburbs.
  * If MaxMind retires the free tier, swap the reader for ``geoip-lite`` or a
    different provider; the rest of this module is provider-agnostic.
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

import analytics_store

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------
GEO_FILE = analytics_store.data_file("geography.json")

# GeoLite2-City DB path. The Dockerfile downloads to /app/GeoLite2-City.mmdb;
# during local dev MAXMIND_DB_PATH may override.
_DEFAULT_DB_PATH = (
    "/app/GeoLite2-City.mmdb"
    if os.getenv("APP_ENV") == "production"
    else str(Path(__file__).parent / "GeoLite2-City.mmdb")
)
_DB_PATH = os.getenv("MAXMIND_DB_PATH", _DEFAULT_DB_PATH)

# ---------------------------------------------------------------------------
# Tunables (read by docs/ANALYTICS_MAINTENANCE.md too — keep in sync)
# ---------------------------------------------------------------------------
_OTHER_BUCKET_THRESHOLD: int = 5  # cities below this daily count → "Other" on read

# Cook + collar counties: principal municipalities used for the "Chicago metro"
# rollup. Lower-case for case-insensitive matching against MaxMind's city field.
_CHICAGO_METRO_CITIES: frozenset[str] = frozenset({
    # Chicago + close-in
    "chicago", "evanston", "skokie", "oak park", "cicero", "berwyn",
    "forest park", "river forest", "elmwood park", "harwood heights",
    "norridge", "rosemont", "park ridge", "niles", "lincolnwood",
    "morton grove", "des plaines", "wilmette", "kenilworth", "winnetka",
    "glenview", "northbrook", "northfield", "highland park", "deerfield",
    # Cook County south + west
    "lansing", "calumet city", "south holland", "blue island", "harvey",
    "markham", "oak lawn", "burbank", "bridgeview", "bedford park",
    "summit", "stickney", "lyons", "la grange", "western springs",
    "hinsdale", "willowbrook", "burr ridge", "oak brook", "downers grove",
    "westmont", "lombard", "addison", "elmhurst", "villa park",
    "schaumburg", "hoffman estates", "palatine", "arlington heights",
    "mount prospect", "rolling meadows", "hanover park", "streamwood",
    "elk grove village", "wheeling", "buffalo grove", "lake zurich",
    # DuPage
    "naperville", "wheaton", "glen ellyn", "carol stream", "bloomingdale",
    "bensenville", "itasca", "warrenville", "west chicago",
    # Will
    "joliet", "bolingbrook", "romeoville", "plainfield", "tinley park",
    "orland park", "mokena", "frankfort", "new lenox", "lockport",
    # Kane
    "aurora", "elgin", "south elgin", "saint charles", "geneva", "batavia",
    "north aurora", "carpentersville", "east dundee", "west dundee",
    # Lake (IL)
    "waukegan", "north chicago", "gurnee", "libertyville", "vernon hills",
    "mundelein", "round lake", "round lake beach", "grayslake", "antioch",
    "lake forest", "lake bluff", "highwood",
    # McHenry
    "crystal lake", "mchenry", "woodstock", "huntley", "algonquin",
    "lake in the hills", "cary",
})

# ---------------------------------------------------------------------------
# In-memory state
# ---------------------------------------------------------------------------
_lock = asyncio.Lock()
# {date: {city_name: count}}
_counts: dict[str, dict[str, int]] = {}
_current_day: str = ""
_writes_since_flush: int = 0
_FLUSH_EVERY_N_WRITES = 20
_reader: Any | None = None  # geoip2.database.Reader, lazy-init


_today_chi = analytics_store.today_chi


def _load() -> dict[str, dict[str, int]]:
    return analytics_store.safe_load_json(GEO_FILE, {})


def _save(counts: dict[str, dict[str, int]]) -> None:
    analytics_store.atomic_write_json(GEO_FILE, counts)


def _get_reader() -> Any | None:
    """Lazy-load the GeoLite2 reader. Returns None if the DB is unavailable.

    The DB is optional: if missing, geography counting silently no-ops so dev
    environments without a MaxMind license key still boot. Production fails
    closed at admin-endpoint read time only if the DB was never present —
    record_visit always swallows lookup errors.
    """
    global _reader
    if _reader is not None:
        return _reader
    try:
        import geoip2.database  # type: ignore
    except ImportError:
        logger.warning("[geography] geoip2 not installed — geography counting disabled")
        return None
    if not Path(_DB_PATH).is_file():
        logger.warning("[geography] DB not found at %s — geography counting disabled", _DB_PATH)
        return None
    try:
        _reader = geoip2.database.Reader(_DB_PATH)
    except Exception as e:
        logger.warning("[geography] failed to open DB %s: %s", _DB_PATH, e)
        return None
    return _reader


def _city_for_ip(ip: str) -> str | None:
    """Resolve an IP to a city name. Returns None on any lookup failure."""
    reader = _get_reader()
    if reader is None:
        return None
    try:
        resp = reader.city(ip)
    except Exception:
        # AddressNotFoundError, ValueError (private IP), etc. — all non-fatal.
        return None
    name = resp.city.name if resp and resp.city else None
    if not name:
        return None
    return name


# Initial in-memory mirror so reads don't hit disk per request.
_counts = _load()


async def record_visit(ip: str) -> None:
    """Increment today's per-city counter for the supplied IP. No-op on errors."""
    global _current_day, _writes_since_flush

    # Resolve outside the lock — reader is thread-safe and the bulk of the work.
    # The mmdb is memory-mapped, so warm pages are fast, but cold pages can
    # block on disk I/O. Run in the default executor so the event loop stays
    # free for other requests.
    loop = asyncio.get_running_loop()
    city = await loop.run_in_executor(None, _city_for_ip, ip)
    if city is None:
        return

    async with _lock:
        today = _today_chi()

        if today != _current_day:
            # Day rolled over (or first request): refresh the in-memory mirror
            # so a previous-process run's counts aren't clobbered.
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
        day[city] = day.get(city, 0) + 1
        _writes_since_flush += 1

        if _writes_since_flush >= _FLUSH_EVERY_N_WRITES:
            await loop.run_in_executor(None, _save, _counts)
            _writes_since_flush = 0


def _project_day(raw_day: dict[str, int]) -> dict[str, int]:
    """Apply the privacy floor: cities below ``_OTHER_BUCKET_THRESHOLD`` collapse to ``Other``.

    Pure function — no I/O, no module state. Exported so tests and the public
    projection module can call it directly.
    """
    out: dict[str, int] = {}
    other = 0
    for city, n in raw_day.items():
        if n < _OTHER_BUCKET_THRESHOLD:
            other += n
        else:
            out[city] = n
    if other:
        out["Other"] = out.get("Other", 0) + other
    return out


def chicago_metro_share(day: dict[str, int]) -> tuple[int, int]:
    """Return (metro_count, total_count) for the supplied day's *raw* counts.

    Uses the un-bucketed counts so a city below the privacy floor still
    contributes to the metro rollup (the floor protects the per-city panel,
    not the metro aggregate).
    """
    total = sum(day.values())
    metro = sum(n for city, n in day.items() if city.lower() in _CHICAGO_METRO_CITIES)
    return metro, total


async def get_counts() -> dict[str, dict[str, int]]:
    """Return all days' per-city counters with the privacy floor applied."""
    async with _lock:
        return {date: _project_day(day) for date, day in _counts.items()}


async def get_metro_summary() -> dict[str, dict[str, float | int]]:
    """Return per-day metro totals: ``{date: {metro, total, share_pct}}``."""
    async with _lock:
        out: dict[str, dict[str, float | int]] = {}
        for date, day in _counts.items():
            metro, total = chicago_metro_share(day)
            share = (100.0 * metro / total) if total else 0.0
            out[date] = {"metro": metro, "total": total, "share_pct": round(share, 1)}
        return out
