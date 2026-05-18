"""
Forward + reverse geocoding cascade for The Chicago Routefinder.

Forward `resolve_location(query) -> (lat, lon) | None` cascade:
    1. Coord-pair regex                       (instant, no network)
    2. NEIGHBORHOOD_COORDS exact match        (instant, no network)
    3. Fuzzy NEIGHBORHOOD_COORDS match        (instant, no network)
    4. local_search.forward()                 (instant, SQLite mmap)
    5. LocationIQ /search                     (network, Tier-5 fallback)

Reverse `reverse_geocode_point(lat, lon) -> {label, source}` cascade:
    1. cached_reverse SQLite hit
    2. Nearest NEIGHBORHOOD within 200 m       (KDTree + Haversine)
    3. Nearest OSM address within 50 m         (local_search.nearest_address)
    4. LocationIQ /reverse                     (cached on success)
    5. "lat,lon" string fallback               (never cached)

Two rule-by-class systems live in this module, and they are intentionally
distinct:

  1. The CIRCUIT BREAKER protects against LocationIQ 429s. State is a single
     `_circuit_open_until` timestamp plus a consecutive-trip counter. Cool-off
     escalates 60s → 120s → 240s, capped at 300s. The first call after
     cool-off probes; success closes the breaker and resets the counter.
     Both forward and reverse paths share the same breaker — a 429 on either
     leg stops both until the cool-off elapses.

  2. The DAILY CAP is a UTC-day counter (separate from the breaker). It exists
     so a misbehaving caller cannot exhaust the LocationIQ free tier in a
     single afternoon. When the cap is hit, Tier-5 calls silently no-op and
     a one-shot warning fires for that UTC day. Reset is implicit at the
     UTC date rollover. State is in-process only; restart resets the count,
     which is fine because the cap is a defensive cost ceiling, not an SLA.

The hosted-fallback negative-cache (NEG_HIT sentinel) lives in
`cached_forward`. It stops the cascade from re-asking LocationIQ for queries
that have already returned no result, while still allowing positive resolutions
through a different cascade tier if the corpus later grows.

PII redaction in logs: user-typed query text never appears verbatim. `_redact`
hashes it; `_redact_coord` quantizes to ~1 km. The geocoder is the most
PII-adjacent surface in the app (home addresses), so the bar here is higher
than for other modules.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import logging
import os
import re
import sqlite3
import threading
import time
from functools import lru_cache
from pathlib import Path

import requests

import config as _cfg
from utils import (
    CHICAGO_EAST,
    CHICAGO_NORTH,
    CHICAGO_SOUTH,
    CHICAGO_WEST,
    METERS_PER_MILE,
    chicago_bbox_contains,
    haversine_miles,
)

logger = logging.getLogger(__name__)


# ── PII-safe logging helpers ────────────────────────────────────────────────

def _redact(query: str) -> str:
    """Return a short opaque tag for `query` so logs never store typed text."""
    if not query:
        return "<empty>"
    return "q#" + hashlib.sha256(query.encode("utf-8")).hexdigest()[:10]


def _redact_coord(lat: float | None, lon: float | None) -> str:
    """Quantize lat/lon to ~1 km precision for logs.

    Free-text geocoder queries commonly resolve to user homes / workplaces.
    Two decimals (~1.1 km at Chicago's latitude) preserves the diagnostic
    value (is it Chicago? lakefront vs west side?) without pinning the user
    to an address.
    """
    if lat is None or lon is None:
        return "(?, ?)"
    return f"({lat:.2f}, {lon:.2f})"


# ── Exceptions ──────────────────────────────────────────────────────────────

class LocationOutsideChicagoError(Exception):
    """Raised when resolution lands on real coordinates outside the Chicago bbox.

    Distinct from a None return (which means "not found"). Callers translate
    this into a 400 with a Chicago-only hint.
    """

    def __init__(self, query: str, coords: tuple[float, float]):
        super().__init__(f"{query!r} resolved to {coords}, outside Chicago bbox")
        self.query = query
        self.coords = coords


class GeocoderDegradedError(Exception):
    """Raised when a Tier-5 call would have been needed and the breaker is open.

    Only raised for queries that exhaust Tiers 1–4 and require LocationIQ.
    Neighborhood / address / intersection queries served by lower tiers never
    raise this.
    """

    DEFAULT_MESSAGE = (
        "The geocoding service is temporarily overloaded — try a Chicago "
        "neighborhood name (e.g., 'Wrigleyville') instead."
    )


# ── Circuit breaker for LocationIQ 429s ─────────────────────────────────────
#
# Stays in one rule-class: a single open-until timestamp + consecutive-trip
# counter. Both forward and reverse share it — see module docstring.

_CIRCUIT_INITIAL_COOLOFF_S: float = 60.0
_CIRCUIT_MAX_COOLOFF_S: float = 300.0
_circuit_open_until: float = 0.0
_circuit_consecutive_trips: int = 0
_circuit_lock = threading.Lock()


def _circuit_is_open() -> bool:
    return time.time() < _circuit_open_until


def _circuit_trip_429() -> None:
    """Record a 429; open the breaker with exponential backoff."""
    global _circuit_open_until, _circuit_consecutive_trips
    with _circuit_lock:
        _circuit_consecutive_trips += 1
        cooloff = min(
            _CIRCUIT_INITIAL_COOLOFF_S * (2 ** (_circuit_consecutive_trips - 1)),
            _CIRCUIT_MAX_COOLOFF_S,
        )
        _circuit_open_until = time.time() + cooloff
        logger.warning(
            "LocationIQ 429 -- circuit breaker open for %.0fs (trip=%d)",
            cooloff, _circuit_consecutive_trips,
        )


def _circuit_record_success() -> None:
    """Close the breaker after a successful probe."""
    global _circuit_open_until, _circuit_consecutive_trips
    with _circuit_lock:
        if _circuit_consecutive_trips > 0:
            logger.info("LocationIQ recovered -- circuit breaker closed")
        _circuit_open_until = 0.0
        _circuit_consecutive_trips = 0


def _circuit_reset_for_test() -> None:
    """Test hook: force the breaker back to closed/zero state."""
    global _circuit_open_until, _circuit_consecutive_trips
    with _circuit_lock:
        _circuit_open_until = 0.0
        _circuit_consecutive_trips = 0


# ── Daily-cap counter (UTC day) ─────────────────────────────────────────────

_cap_lock = threading.Lock()
_cap_day: str = ""
_cap_count: int = 0
_cap_warned_today: bool = False


def _utc_day_key() -> str:
    return _dt.datetime.now(_dt.timezone.utc).date().isoformat()


def _under_daily_cap() -> bool:
    """Return True if today's call count is below the configured cap.

    Also rolls the counter when the UTC date changes.
    """
    global _cap_day, _cap_count, _cap_warned_today
    with _cap_lock:
        today = _utc_day_key()
        if today != _cap_day:
            _cap_day = today
            _cap_count = 0
            _cap_warned_today = False
        return _cap_count < _cfg.LOCATIONIQ_DAILY_CAP


def _record_locationiq_call() -> None:
    """Increment the daily counter; emit a one-shot warning on cap-cross."""
    global _cap_count, _cap_warned_today
    with _cap_lock:
        _cap_count += 1
        if _cap_count >= _cfg.LOCATIONIQ_DAILY_CAP and not _cap_warned_today:
            logger.warning(
                "LocationIQ daily cap reached: %d/%d -- degrading to local-only "
                "for the rest of today (UTC)",
                _cap_count, _cfg.LOCATIONIQ_DAILY_CAP,
            )
            _cap_warned_today = True


def _cap_reset_for_test() -> None:
    """Test hook: clear the daily counter so the next call is gated freshly."""
    global _cap_day, _cap_count, _cap_warned_today
    with _cap_lock:
        _cap_day = ""
        _cap_count = 0
        _cap_warned_today = False


def _cap_set_for_test(*, count: int, day: str | None = None) -> None:
    """Test hook: pin the daily counter so cap-hit branches are exercisable."""
    global _cap_day, _cap_count, _cap_warned_today
    with _cap_lock:
        _cap_day = day or _utc_day_key()
        _cap_count = count
        _cap_warned_today = False


# ── LocationIQ HTTP client ──────────────────────────────────────────────────

_LOCATIONIQ_BASE = "https://us1.locationiq.com/v1"
_LOCATIONIQ_TIMEOUT_S = 5

# LocationIQ's `viewbox` parameter is `min_lon,max_lat,max_lon,min_lat`
# (NW corner, SE corner) — note the inversion vs GIS conventions. `bounded=1`
# restricts results to the box rather than just preferring them.
_LOCATIONIQ_VIEWBOX = f"{CHICAGO_WEST},{CHICAGO_NORTH},{CHICAGO_EAST},{CHICAGO_SOUTH}"

_http_session = requests.Session()
_missing_api_key_warned: bool = False


def _locationiq_api_key() -> str:
    """Read the API key fresh each call so a runtime env change takes effect."""
    return os.getenv("LOCATIONIQ_API_KEY", "")


def _warn_missing_api_key() -> None:
    global _missing_api_key_warned
    if not _missing_api_key_warned:
        logger.warning("LOCATIONIQ_API_KEY not set -- hosted Tier-5 fallback unavailable")
        _missing_api_key_warned = True


def _locationiq_call_gated() -> bool:
    """Pre-flight gate shared by forward + reverse network paths.

    Returns False (caller should skip the call) when any of these hold:
    feature flag off, API key missing, breaker open, daily cap hit.
    The breaker check still produces a `GeocoderDegradedError` from the
    forward path because callers expect to surface a user-facing message;
    reverse just degrades silently.
    """
    if not _cfg.LOCATIONIQ_ENABLED:
        return False
    if not _locationiq_api_key():
        _warn_missing_api_key()
        return False
    if not _under_daily_cap():
        return False
    return True


# ── SQLite-backed cache (chicago_geocode.db) ────────────────────────────────

_CACHE_DB_PATH = Path(__file__).resolve().parent / "static_data" / "chicago_geocode.db"
_cache_lock = threading.Lock()
_cache_db: sqlite3.Connection | None = None


def _cache_connect() -> sqlite3.Connection | None:
    """Open the writeable cache DB, or return None if the artifact is missing.

    Missing DB is recoverable — Tier 5 calls just skip caching. Expected on
    a fresh clone before the build scripts run.
    """
    global _cache_db
    if _cache_db is not None:
        return _cache_db
    with _cache_lock:
        if _cache_db is not None:
            return _cache_db
        if not _CACHE_DB_PATH.exists():
            logger.warning(
                "%s missing -- LocationIQ responses will not be cached. "
                "Run backend/scripts/build_*.py to populate it.",
                _CACHE_DB_PATH,
            )
            return None
        conn = sqlite3.connect(str(_CACHE_DB_PATH), check_same_thread=False, isolation_level=None)
        # WAL gives non-blocking reads alongside writes. autocommit avoids
        # transaction overhead for the single-row cache updates we do.
        try:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
        except sqlite3.OperationalError:
            pass
        conn.row_factory = sqlite3.Row
        _cache_db = conn
        return _cache_db


def _close_cache_db_for_test() -> None:
    """Test hook: drop the cached writer so tests can swap the DB path."""
    global _cache_db
    with _cache_lock:
        if _cache_db is not None:
            try:
                _cache_db.close()
            except Exception:
                pass
        _cache_db = None


# Sentinel distinguishing "cache miss" (None) from "cached negative result".
# `_cache_get_forward` returns NEG_HIT when the table holds a row with NULL
# coords, so callers don't re-query LocationIQ for known-bad queries.
class _Neg:
    __slots__ = ()
    def __repr__(self) -> str:
        return "<NEG_HIT>"


NEG_HIT = _Neg()


def _cache_get_forward(query: str):
    """Return (lat, lon) on hit, NEG_HIT for a cached negative, or None on miss."""
    db = _cache_connect()
    if db is None:
        return None
    row = db.execute(
        "SELECT lat, lon FROM cached_forward WHERE query = ?", (query,),
    ).fetchone()
    if row is None:
        return None
    if row["lat"] is None or row["lon"] is None:
        return NEG_HIT
    return (float(row["lat"]), float(row["lon"]))


def _cache_set_forward(query: str, coords: tuple[float, float] | None, source: str) -> None:
    """Store (lat, lon) or a negative entry (None) for `query`."""
    db = _cache_connect()
    if db is None:
        return
    lat = coords[0] if coords is not None else None
    lon = coords[1] if coords is not None else None
    try:
        db.execute(
            "INSERT OR REPLACE INTO cached_forward (query, lat, lon, source, fetched_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (query, lat, lon, source, int(time.time())),
        )
    except sqlite3.Error as exc:
        logger.warning("cached_forward write failed for %s: %s", _redact(query), exc)


def _cache_get_reverse(lat: float, lon: float) -> dict | None:
    """Return {"label", "source"} on hit, or None on miss."""
    db = _cache_connect()
    if db is None:
        return None
    lat_q = round(lat * 1e5)
    lon_q = round(lon * 1e5)
    row = db.execute(
        "SELECT label, source FROM cached_reverse WHERE lat_q = ? AND lon_q = ?",
        (lat_q, lon_q),
    ).fetchone()
    if row is None:
        return None
    return {"label": row["label"], "source": row["source"]}


def _cache_set_reverse(lat: float, lon: float, label: str, source: str) -> None:
    db = _cache_connect()
    if db is None:
        return
    try:
        db.execute(
            "INSERT OR REPLACE INTO cached_reverse (lat_q, lon_q, label, source, fetched_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (round(lat * 1e5), round(lon * 1e5), label, source, int(time.time())),
        )
    except sqlite3.Error as exc:
        logger.warning("cached_reverse write failed for %s: %s", _redact_coord(lat, lon), exc)


def _cache_clear_forward_for_test(query: str) -> None:
    """Test hook: drop a single forward-cache entry so synthetic queries hit
    the network path on the next call."""
    db = _cache_connect()
    if db is None:
        return
    try:
        db.execute("DELETE FROM cached_forward WHERE query = ?", (query,))
    except sqlite3.Error:
        pass


def evict_cache_older_than(days: int) -> dict:
    """Delete rows from `cached_forward` and `cached_reverse` whose
    `fetched_at` is older than `days` days. Returns a `{table: rows_deleted}`
    summary. No-op (zero deletes, no error) when the DB is unavailable or
    `days <= 0` (the documented "disable eviction" sentinel).

    Called once from `main.py`'s FastAPI lifespan startup hook. A background
    timer would be overkill — write rate is bounded by `LOCATIONIQ_DAILY_CAP`
    per UTC day, so any rows that age out between deploys age out at the
    next deploy's startup sweep.
    """
    result = {"cached_forward": 0, "cached_reverse": 0}
    if days <= 0:
        return result
    db = _cache_connect()
    if db is None:
        return result
    cutoff = int(time.time()) - days * 86_400
    try:
        cur = db.execute(
            "DELETE FROM cached_forward WHERE fetched_at < ?", (cutoff,),
        )
        result["cached_forward"] = cur.rowcount or 0
        cur = db.execute(
            "DELETE FROM cached_reverse WHERE fetched_at < ?", (cutoff,),
        )
        result["cached_reverse"] = cur.rowcount or 0
    except sqlite3.Error as exc:
        logger.warning("cache TTL eviction failed: %s", exc)
        return result
    if result["cached_forward"] or result["cached_reverse"]:
        logger.info(
            "cache TTL eviction (days=%d): forward=%d reverse=%d",
            days, result["cached_forward"], result["cached_reverse"],
        )
    return result


# ── LocationIQ forward + reverse ────────────────────────────────────────────

def geocode_external(query: str) -> tuple[float, float] | None:
    """Forward-geocode `query` via LocationIQ, biased to Chicago.

    Results (positive + negative) are cached in chicago_geocode.db. Returns
    None on missing key / disabled / cap hit / no match / out-of-bbox.
    Raises `GeocoderDegradedError` when the circuit breaker is open and a
    network call would otherwise have been made.
    """
    # 1. Cache short-circuit (positive or negative).
    cached = _cache_get_forward(query)
    if cached is NEG_HIT:
        return None
    if cached is not None:
        return cached  # type: ignore[return-value]

    # 2. Pre-flight gates -- flag off, key missing, or cap hit -> silent None.
    if not _locationiq_call_gated():
        return None

    # 3. Breaker check -- distinct from the cap; this is the user-visible
    # "geocoder is overloaded" signal.
    if _circuit_is_open():
        raise GeocoderDegradedError(GeocoderDegradedError.DEFAULT_MESSAGE)

    coords: tuple[float, float] | None = None
    cache_negative = False
    biased_query = query if "chicago" in query.lower() else f"{query}, Chicago, IL"
    _record_locationiq_call()
    try:
        resp = _http_session.get(
            f"{_LOCATIONIQ_BASE}/search",
            params={
                "key": _locationiq_api_key(),
                "q": biased_query,
                "format": "json",
                "limit": 1,
                "countrycodes": "us",
                "viewbox": _LOCATIONIQ_VIEWBOX,
                "bounded": 1,
                "normalizeaddress": 1,
            },
            headers={"Accept": "application/json"},
            timeout=_LOCATIONIQ_TIMEOUT_S,
        )

        if resp.status_code == 429:
            _circuit_trip_429()
            raise GeocoderDegradedError(GeocoderDegradedError.DEFAULT_MESSAGE)

        if resp.status_code == 404:
            # Definitive "no match" -- cache negatively.
            cache_negative = True
            _circuit_record_success()
        elif resp.status_code in (401, 403):
            # Bad / missing API key. Don't cache (so a key fix takes effect
            # immediately) and don't probe the breaker (config issue, not
            # rate-limit).
            logger.error(
                "LocationIQ %s for %s -- check LOCATIONIQ_API_KEY",
                resp.status_code, _redact(query),
            )
        elif resp.status_code == 200:
            data = resp.json() if resp.content else []
            if isinstance(data, list) and data:
                entry = data[0]
                try:
                    candidate = (float(entry["lat"]), float(entry["lon"]))
                except (KeyError, TypeError, ValueError):
                    candidate = None
                if candidate is None:
                    cache_negative = True
                elif not chicago_bbox_contains(*candidate):
                    logger.warning(
                        "LocationIQ returned out-of-bbox coords for %s -> %s; ignoring",
                        _redact(query), _redact_coord(*candidate),
                    )
                    cache_negative = True
                else:
                    coords = candidate
                    logger.info(
                        "LocationIQ geocoded %s -> %s",
                        _redact(query), _redact_coord(*coords),
                    )
            else:
                cache_negative = True
            _circuit_record_success()
        else:
            logger.warning(
                "LocationIQ returned unexpected status %s for %s",
                resp.status_code, _redact(query),
            )
    except GeocoderDegradedError:
        raise
    except Exception as exc:
        logger.error("LocationIQ forward failed for %s: %s", _redact(query), exc)

    if coords is not None:
        _cache_set_forward(query, coords, "locationiq")
    elif cache_negative:
        _cache_set_forward(query, None, "locationiq")
    return coords


def _reverse_geocode_external(lat: float, lon: float) -> str | None:
    """Reverse-geocode via LocationIQ. Returns a short label or None.

    Honors the same breaker + cap as forward. The caller writes successful
    labels into `cached_reverse`.
    """
    if not _locationiq_call_gated():
        return None
    if _circuit_is_open():
        return None
    _record_locationiq_call()
    try:
        resp = _http_session.get(
            f"{_LOCATIONIQ_BASE}/reverse",
            params={
                "key": _locationiq_api_key(),
                "lat": lat,
                "lon": lon,
                "format": "json",
                "normalizeaddress": 1,
                "zoom": 18,
            },
            headers={"Accept": "application/json"},
            timeout=_LOCATIONIQ_TIMEOUT_S,
        )
        if resp.status_code == 429:
            _circuit_trip_429()
            return None
        if resp.status_code == 404:
            _circuit_record_success()
            return None
        if resp.status_code in (401, 403):
            logger.error("LocationIQ reverse %s -- check LOCATIONIQ_API_KEY", resp.status_code)
            return None
        if resp.status_code != 200:
            logger.warning("LocationIQ reverse unexpected %s", resp.status_code)
            return None
        data = resp.json() if resp.content else {}
        display = (data.get("display_name") or "").strip()
        _circuit_record_success()
        if not display:
            return None
        # Trim everything after the ZIP for a tighter label; defensive sweep
        # of any trailing ", USA" the regex missed.
        m = re.search(r",\s*(\d{5})(?:-\d{4})?\b", display)
        if m:
            display = display[: m.end()]
        display = re.sub(r",\s*(USA|United States(?: of America)?)\s*$", "", display).strip()
        return display or None
    except Exception as exc:
        logger.error("LocationIQ reverse failed for %s: %s", _redact_coord(lat, lon), exc)
        return None


# ── Forward resolution cascade ──────────────────────────────────────────────

_COORD_RE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$")


def resolve_location(query: str) -> tuple[float, float] | None:
    """Resolve a free-text Chicago location query to (lat, lon).

    Cascade order: coord regex → NEIGHBORHOOD_COORDS exact → fuzzy →
    local_search.forward → LocationIQ. Raises `LocationOutsideChicagoError`
    when a Tier-5 resolution lands outside Chicago's bbox (lower tiers are
    all in-bbox by construction). Returns None when nothing matches.
    """
    if not query:
        return None
    coords = _resolve_inner(query)
    if coords is not None and not chicago_bbox_contains(*coords):
        raise LocationOutsideChicagoError(query, coords)
    return coords


def _resolve_inner(query: str) -> tuple[float, float] | None:
    # Tier 1: coord regex (bypass all geocoding).
    m = _COORD_RE.match(query)
    if m:
        return float(m.group(1)), float(m.group(2))

    q = query.strip().lower()
    # Expand "Ave" → "avenue" etc. so NEIGHBORHOOD_COORDS keys (spelled out)
    # match. Late import keeps this module loadable in isolation.
    from geocode_text import _normalize_street_abbr  # noqa: PLC0415
    q = _normalize_street_abbr(q)

    # Tier 2: NEIGHBORHOOD_COORDS exact + Tier 3: fuzzy. Both live in
    # gtfs_loader (the lru_cache wrapper binds NEIGHBORHOOD_COORDS).
    from gtfs_loader import NEIGHBORHOOD_COORDS, fuzzy_match_neighborhood  # noqa: PLC0415
    coords = NEIGHBORHOOD_COORDS.get(q)
    if coords:
        return coords

    coords, _ = fuzzy_match_neighborhood(q)
    if coords:
        return coords

    # Tier 4: local SQLite-backed search. Lazy import so geocoding.py loads
    # even in fixtures without chicago_geocode.db.
    try:
        from local_search import forward as _local_forward  # noqa: PLC0415
        coords = _local_forward(q)
        if coords:
            return coords
    except Exception as exc:
        logger.warning("local_search.forward failed for %s: %s", _redact(q), exc)

    # Tier 5: LocationIQ (may raise GeocoderDegradedError if breaker is open).
    return geocode_external(q)


# ── Reverse resolution cascade ──────────────────────────────────────────────

# 200 m -- neighborhood tier; 50 m -- address tier. Both in miles since
# haversine_miles is the underlying primitive.
_REV_NEIGHBORHOOD_MI: float = 200.0 / METERS_PER_MILE
_REV_ADDRESS_M: float = 50.0

_neighborhood_kdtree = None
_neighborhood_names: tuple[str, ...] = ()
_neighborhood_kdtree_lock = threading.Lock()


def _get_neighborhood_kdtree():
    """Build a KDTree over NEIGHBORHOOD_COORDS lazily; reused across calls."""
    global _neighborhood_kdtree, _neighborhood_names
    if _neighborhood_kdtree is not None:
        return _neighborhood_kdtree
    with _neighborhood_kdtree_lock:
        if _neighborhood_kdtree is not None:
            return _neighborhood_kdtree
        # scipy is already a backend dependency (used by walking.py + others).
        from scipy.spatial import cKDTree  # noqa: PLC0415
        import numpy as np  # noqa: PLC0415
        from gtfs_loader import NEIGHBORHOOD_COORDS  # noqa: PLC0415

        items = list(NEIGHBORHOOD_COORDS.items())
        names = tuple(name for name, _ in items)
        # KDTree query order matches the array layout below: [lon, lat].
        coords = np.array([[lon, lat] for _, (lat, lon) in items], dtype=float)
        _neighborhood_names = names
        _neighborhood_kdtree = cKDTree(coords)
    return _neighborhood_kdtree


def _reset_kdtree_for_test() -> None:
    """Test hook: drop the cached KDTree so a fresh fixture rebuilds it."""
    global _neighborhood_kdtree, _neighborhood_names
    with _neighborhood_kdtree_lock:
        _neighborhood_kdtree = None
        _neighborhood_names = ()


def reverse_geocode_point(lat: float, lon: float) -> dict:
    """Reverse-geocode (lat, lon) to a human-readable label.

    Returns {"label": str, "source": str}. Source is one of:
        "cached_reverse" | "neighborhood" | "address" | "locationiq" | "coordinates"
    """
    # Tier 1: cache hit.
    cached = _cache_get_reverse(lat, lon)
    if cached is not None:
        return cached

    # Tier 2: nearest neighborhood within 200 m.
    from gtfs_loader import NEIGHBORHOOD_COORDS  # noqa: PLC0415
    tree = _get_neighborhood_kdtree()
    if _neighborhood_names:
        k = min(5, len(_neighborhood_names))
        _, idx = tree.query([lon, lat], k=k)
        candidate_idx = [int(idx)] if k == 1 else [int(i) for i in idx]
        best_name: str | None = None
        best_dist = float("inf")
        for i in candidate_idx:
            name = _neighborhood_names[i]
            nlat, nlon = NEIGHBORHOOD_COORDS[name]
            d = haversine_miles(lat, lon, nlat, nlon)
            if d < best_dist:
                best_dist = d
                best_name = name
        if best_name and best_dist <= _REV_NEIGHBORHOOD_MI:
            result = {"label": best_name.title(), "source": "neighborhood"}
            _cache_set_reverse(lat, lon, result["label"], result["source"])
            return result

    # Tier 3: nearest OSM address within 50 m.
    try:
        from local_search import nearest_address as _local_nearest  # noqa: PLC0415
        addr = _local_nearest(lat, lon, radius_m=_REV_ADDRESS_M)
        if addr is not None:
            result = {"label": addr["raw"], "source": "address"}
            _cache_set_reverse(lat, lon, result["label"], result["source"])
            return result
    except Exception as exc:
        logger.warning("local_search.nearest_address failed: %s", exc)

    # Tier 4: LocationIQ fallback.
    label = _reverse_geocode_external(lat, lon)
    if label:
        result = {"label": label, "source": "locationiq"}
        _cache_set_reverse(lat, lon, result["label"], result["source"])
        return result

    # Tier 5: coordinate fallback -- intentionally NOT cached so a transient
    # network failure doesn't permanently poison this lat/lon.
    return {"label": f"{lat:.5f}, {lon:.5f}", "source": "coordinates"}
