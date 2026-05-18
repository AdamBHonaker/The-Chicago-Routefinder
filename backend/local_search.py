"""
Local-first search facade for the geocoder cascade.

This module owns the query layer over `backend/static_data/chicago_geocode.db`
(populated by Chunks 2 + 3 of the Geocoding & Autocomplete plan) plus an
in-memory index over neighborhoods and GTFS train/bus stops. No network calls
live here — the Tier-5 LocationIQ fallback is in `geocoding.py` (Chunk 5).

Two rule-by-class systems live in this module, and they are intentionally
distinct:

  1. Source TIERS — for ranking + per-tier cap enforcement. Higher tier always
     beats lower tier regardless of score:

         train_station > neighborhood > intersection > bus_stop > address

     The `autocomplete()` function fills the result list tier-by-tier from
     highest to lowest, taking at most `per_tier_cap` from each tier before
     descending, until the total `limit` is reached (Decision 8 of the
     chunked plan). This means a barrage of address matches can never starve
     the neighborhood tier — the cap protects the higher tiers from below
     and ensures result diversity.

  2. Score COMPONENTS — for ordering WITHIN a tier only. Built from:
         + tier base (source priority, dominates across tiers)
         + exact-match bonus (+100)
         + in-bbox bonus (+50)
         - distance-from-Chicago-center penalty (in miles)

     Cross-tier ordering is enforced by the tier-greedy merge above, not by
     these scores. The base term is kept large enough that scores never
     "cross over" between tiers — useful when callers want a single sorted
     debug view, but never load-bearing for ranking.

The cross-tier dedupe step (also Decision 8) collapses suggestions that
collide on either (source, label_lower) or a 5-decimal coord bucket. The
quantized-coord key catches OSM intersections that model one real crossroads
as 2–4 graph nodes a few meters apart.

DB connection is opened once at first use with mmap (128 MB) so concurrent
request threads can read with negligible overhead.
"""

from __future__ import annotations

import bisect
import logging
import math
import re
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from geocode_text import normalize_address, normalize_street_name
from utils import (
    METERS_PER_MILE,
    chicago_bbox_contains,
    haversine_miles,
)

logger = logging.getLogger(__name__)

# Mirrors the path convention enforced in scripts/_geocode_db.py: must be
# `static_data/` (not `data/`) so Railway's persistent analytics volume
# doesn't overlay the corpus at deploy time.
DB_PATH = Path(__file__).resolve().parent / "static_data" / "chicago_geocode.db"

# Loop / Millennium Park area — used as the tie-breaker anchor when several
# candidates within a tier score identically on everything else. Pulls
# ambiguous queries like "730 N Franklin" toward the downtown row over a
# similarly-named address that happens to sit inside the wider Chicago bbox.
_CHICAGO_CENTER: tuple[float, float] = (41.8827, -87.6326)

# Decision-8 default per-tier soft cap. Exposed via the autocomplete()
# parameter so /autocomplete handlers can override per-request if needed.
AUTOCOMPLETE_PER_TIER_CAP: int = 3

@dataclass(frozen=True)
class Suggestion:
    """One ranked autocomplete result."""

    label: str           # human-readable display
    lat: float
    lon: float
    source: str          # 'train_station' | 'neighborhood' | 'intersection' | 'bus_stop' | 'address'
    score: float = 0.0   # higher is better; ordering WITHIN a tier only


def _quantize_coord(lat: float, lon: float) -> tuple[int, int]:
    """Quantize (lat, lon) to ~1 m precision for the dedupe key.

    Mirrors the same 5-decimal quantization used by build_address_points.py
    at ingest time, so a dedupe lookup here matches the corpus's own
    near-duplicate collapse.
    """
    return round(lat * 1e5), round(lon * 1e5)


# ── Lazy DB connection ──────────────────────────────────────────────────────

_db_lock = threading.Lock()
_db: sqlite3.Connection | None = None


def _connect() -> sqlite3.Connection | None:
    """Return a process-wide read-only SQLite connection over chicago_geocode.db.

    Returns None when the DB artifact is missing — callers in this module
    short-circuit to an empty result rather than opening a `:memory:` stub
    that would later raise `OperationalError: no such table` on the first
    `addresses` / `intersections` query.
    """
    global _db
    if _db is not None:
        return _db
    with _db_lock:
        if _db is not None:
            return _db
        if not DB_PATH.exists():
            logger.warning("%s missing -- local_search will only resolve neighborhoods/stations", DB_PATH)
            return None
        conn = sqlite3.connect(
            f"file:{DB_PATH}?mode=ro",
            uri=True,
            check_same_thread=False,
        )
        try:
            conn.execute("PRAGMA mmap_size = 134217728")  # 128 MB
            conn.execute("PRAGMA temp_store = MEMORY")
        except sqlite3.OperationalError:
            pass
        conn.row_factory = sqlite3.Row
        _db = conn
    return _db


def _reset_db_for_test() -> None:
    """Test hook: drop the cached connection so tests can use a fresh DB path."""
    global _db
    with _db_lock:
        if _db is not None:
            try:
                _db.close()
            except Exception:
                pass
        _db = None


# ── Cross-street query parser ───────────────────────────────────────────────

# Common prefixes a user might type before "Clark and Belmont".
_CROSS_PREFIX_RE = re.compile(
    r"^(?:the\s+)?(?:intersection|corner)\s+of\s+",
    re.IGNORECASE,
)
# Separators that mean "A intersects B". Word-like separators (`and`, `at`,
# `x`, `&`, `@`) require whitespace on both sides so they don't split inside
# ordinary words ("boxwood" must not become "bo wood"); slash and backslash
# accept optional whitespace because users frequently type "Clark/Belmont"
# without spaces.
_CROSS_SEP_RE = re.compile(
    r"(?:\s+(?:and|&|@|\bat\b|\bx\b)\s+|\s*[/\\]\s*)",
    re.IGNORECASE,
)


def parse_cross_street(query: str) -> tuple[str, str] | None:
    """If `query` looks like a cross-street, return canonical (name_a, name_b).

    Accepts: "Clark and Belmont", "Clark & Belmont", "Clark/Belmont",
    "Clark at Belmont", "intersection of Clark and Belmont", "Clark x Belmont".
    """
    if not query:
        return None
    s = _CROSS_PREFIX_RE.sub("", query.strip())
    parts = _CROSS_SEP_RE.split(s, maxsplit=1)
    if len(parts) != 2:
        return None
    a = normalize_street_name(parts[0])
    b = normalize_street_name(parts[1])
    if not a or not b or a == b:
        return None
    return (a, b)


# ── In-memory indexes (neighborhoods + train/bus stations) ──────────────────

_in_mem_lock = threading.Lock()
_in_mem_built = False
# Each entry: (name_lower_for_prefix_window, display_label, lat, lon)
_neighborhood_index: list[tuple[str, str, float, float]] = []
_train_index: list[tuple[str, str, float, float]] = []
_bus_index: list[tuple[str, str, float, float]] = []
# Parallel key-only arrays held in lockstep with the index lists above, for
# `bisect`-based prefix windowing.
_neighborhood_keys: list[str] = []
_train_keys: list[str] = []
_bus_keys: list[str] = []


def _ensure_in_mem_index() -> None:
    """Build sorted prefix lists for neighborhoods + train + bus once per process."""
    global _in_mem_built
    if _in_mem_built:
        return
    with _in_mem_lock:
        if _in_mem_built:
            return
        # Late imports avoid pulling gtfs_loader (and its heavy GTFS-parse
        # startup cost) into modules that only need the cross-street parser
        # or the DB-backed query layer in isolation.
        from gtfs_loader import NEIGHBORHOOD_COORDS, _load_stops  # noqa: PLC0415

        for name, (lat, lon) in NEIGHBORHOOD_COORDS.items():
            _neighborhood_index.append((name, name.title(), lat, lon))
        _neighborhood_index.sort(key=lambda t: t[0])
        _neighborhood_keys.extend(t[0] for t in _neighborhood_index)

        try:
            train_stations, bus_stops = _load_stops()
        except Exception as exc:
            # Tests / CI may run without a real GTFS feed. Neighborhoods +
            # DB still work; just skip the station tiers.
            logger.warning("station index unavailable: %s", exc)
            train_stations, bus_stops = [], []

        for s in train_stations:
            nm = (s.get("name") or "").strip()
            if not nm:
                continue
            _train_index.append((nm.lower(), nm, float(s["lat"]), float(s["lon"])))
        _train_index.sort(key=lambda t: t[0])
        _train_keys.extend(t[0] for t in _train_index)

        # Dedupe bus stops by lowercased name — multiple physical stops at
        # the same intersection collapse to one suggestion. Preserves the
        # behavior of the prior `/autocomplete` index path (retired in
        # Chunk 6 of the Geocoding & Autocomplete plan). Platform-level
        # disambiguation is FEAT-015's job, not this chunk's.
        seen_bus: set[str] = set()
        for s in bus_stops:
            nm = (s.get("name") or "").strip()
            if not nm:
                continue
            key = nm.lower()
            if key in seen_bus:
                continue
            seen_bus.add(key)
            _bus_index.append((key, nm, float(s["lat"]), float(s["lon"])))
        _bus_index.sort(key=lambda t: t[0])
        _bus_keys.extend(t[0] for t in _bus_index)

        _in_mem_built = True


def _reset_in_mem_for_test() -> None:
    """Test hook: clear the in-memory index so the next call rebuilds it."""
    global _in_mem_built
    with _in_mem_lock:
        _neighborhood_index.clear()
        _neighborhood_keys.clear()
        _train_index.clear()
        _train_keys.clear()
        _bus_index.clear()
        _bus_keys.clear()
        _in_mem_built = False


def _prefix_window(keys: list[str], q: str) -> tuple[int, int]:
    """Return [lo, hi) such that every key in that slice has `q` as a prefix.

    `keys` must be lexicographically sorted. Empty `q` returns the full range,
    matching the loop semantics every key is a prefix of "". `lo` is
    `bisect_left(keys, q)`; `hi` walks forward while the prefix still holds.
    """
    if not q:
        return (0, len(keys))
    lo = bisect.bisect_left(keys, q)
    hi = lo
    n = len(keys)
    while hi < n and keys[hi].startswith(q):
        hi += 1
    return (lo, hi)


# ── Ranking + dedupe helpers ────────────────────────────────────────────────

# Tier ordering (Decision 8 + this project's destination conventions).
# train_station first because riders most often think in named-station terms;
# bus_stop sits below intersection because a stop named for a cross-street is
# typically less useful as a destination than the intersection itself.
_SOURCE_PRIORITY: dict[str, float] = {
    "train_station": 1100.0,
    "neighborhood":  1000.0,
    "intersection":   800.0,
    "bus_stop":       700.0,
    "address":        600.0,
}

# Ordered tier list — drives the tier-greedy merge in autocomplete().
_TIER_ORDER: tuple[str, ...] = (
    "train_station", "neighborhood", "intersection", "bus_stop", "address",
)


def _score(source: str, lat: float, lon: float, *, exact: bool) -> float:
    """Higher is better. WITHIN-TIER ordering only; see module docstring."""
    base = _SOURCE_PRIORITY.get(source, 0.0)
    base += 100.0 if exact else 0.0
    if chicago_bbox_contains(lat, lon):
        base += 50.0
    d = haversine_miles(_CHICAGO_CENTER[0], _CHICAGO_CENTER[1], lat, lon)
    base -= d
    return base


def _dedupe(suggestions: Iterable[Suggestion]) -> list[Suggestion]:
    """Drop later suggestions that collide on label or quantized coord (~1 m)."""
    seen_keys: set[tuple[int, int]] = set()
    seen_labels: set[tuple[str, str]] = set()
    out: list[Suggestion] = []
    for s in suggestions:
        key = _quantize_coord(s.lat, s.lon)
        label_key = (s.source, s.label.lower())
        if key in seen_keys or label_key in seen_labels:
            continue
        seen_keys.add(key)
        seen_labels.add(label_key)
        out.append(s)
    return out


# ── Autocomplete ────────────────────────────────────────────────────────────

def autocomplete(
    query: str,
    limit: int = 8,
    per_tier_cap: int = AUTOCOMPLETE_PER_TIER_CAP,
    in_bbox_only: bool = True,
) -> list[Suggestion]:
    """Return up to `limit` ranked suggestions across all local sources.

    Tier-greedy fill (Decision 8): take up to `per_tier_cap` from each tier
    in priority order, stopping when `limit` is reached. Cross-tier dedupe
    runs after the merge so collisions on a higher-tier row consume the
    lower-tier duplicate.
    """
    if not query or not query.strip():
        return []
    q = query.strip()
    q_lower = q.lower()

    _ensure_in_mem_index()

    by_tier: dict[str, list[Suggestion]] = {t: [] for t in _TIER_ORDER}

    # 1. Train stations — bisect prefix window.
    t_lo, t_hi = _prefix_window(_train_keys, q_lower)
    for j in range(t_lo, t_hi):
        name_lower, display, lat, lon = _train_index[j]
        exact = name_lower == q_lower
        by_tier["train_station"].append(Suggestion(
            display, lat, lon, "train_station",
            _score("train_station", lat, lon, exact=exact),
        ))

    # 2. Neighborhoods — same bisect trick.
    n_lo, n_hi = _prefix_window(_neighborhood_keys, q_lower)
    for j in range(n_lo, n_hi):
        name, display, lat, lon = _neighborhood_index[j]
        exact = name == q_lower
        by_tier["neighborhood"].append(Suggestion(
            display, lat, lon, "neighborhood",
            _score("neighborhood", lat, lon, exact=exact),
        ))

    # 3. Intersections — two-leg cross-street parse, else single-name prefix
    # (only when the query is a single word with no leading house number).
    parsed = parse_cross_street(q)
    norm_addr = normalize_address(q)
    has_house_num = bool(norm_addr and norm_addr[0].isdigit())
    if parsed is not None:
        a, b = parsed
        by_tier["intersection"].extend(_query_intersections_exact(a, b))
    else:
        norm_street = normalize_street_name(q)
        if norm_street and " " not in norm_street and not has_house_num:
            by_tier["intersection"].extend(
                _query_intersections_prefix(norm_street, limit=limit * 2)
            )

    # 4. Bus stops — bisect prefix window over deduped names.
    b_lo, b_hi = _prefix_window(_bus_keys, q_lower)
    for j in range(b_lo, b_hi):
        name_lower, display, lat, lon = _bus_index[j]
        exact = name_lower == q_lower
        by_tier["bus_stop"].append(Suggestion(
            display, lat, lon, "bus_stop",
            _score("bus_stop", lat, lon, exact=exact),
        ))

    # 5. Addresses — only meaningful when the query has a leading house number.
    if has_house_num:
        by_tier["address"].extend(_query_addresses_prefix(norm_addr, limit=limit * 2))

    if in_bbox_only:
        for tier, items in by_tier.items():
            by_tier[tier] = [s for s in items if chicago_bbox_contains(s.lat, s.lon)]

    # Sort each tier by score, then tier-greedy merge with per_tier_cap.
    merged: list[Suggestion] = []
    for tier in _TIER_ORDER:
        items = sorted(by_tier[tier], key=lambda s: -s.score)
        merged.extend(items[:per_tier_cap])
        if len(merged) >= limit * 2:  # plenty of headroom for dedupe to chew through
            break

    return _dedupe(merged)[:limit]


def _query_intersections_exact(a: str, b: str) -> list[Suggestion]:
    db = _connect()
    if db is None:
        return []
    rows = db.execute(
        "SELECT raw_a, raw_b, lat, lon FROM intersections "
        "WHERE (name_a = ? AND name_b = ?) OR (name_a = ? AND name_b = ?) "
        "LIMIT 20",
        (a, b, b, a),
    ).fetchall()
    return [
        Suggestion(
            f"{r['raw_a']} & {r['raw_b']}",
            r["lat"], r["lon"], "intersection",
            _score("intersection", r["lat"], r["lon"], exact=True),
        )
        for r in rows
    ]


def _query_intersections_prefix(name: str, limit: int) -> list[Suggestion]:
    """Return intersections where one canonical name starts with `name`."""
    db = _connect()
    if db is None:
        return []
    rows = db.execute(
        "SELECT raw_a, raw_b, lat, lon FROM intersections "
        "WHERE name_a = ? OR name_b = ? "
        "LIMIT ?",
        (name, name, limit),
    ).fetchall()
    return [
        Suggestion(
            f"{r['raw_a']} & {r['raw_b']}",
            r["lat"], r["lon"], "intersection",
            _score("intersection", r["lat"], r["lon"], exact=False),
        )
        for r in rows
    ]


def _query_addresses_prefix(norm: str, limit: int) -> list[Suggestion]:
    db = _connect()
    if db is None:
        return []
    rows = db.execute(
        "SELECT raw, lat, lon, (normalized = ?) AS is_exact "
        "FROM addresses WHERE normalized LIKE ? LIMIT ?",
        (norm, norm + "%", limit),
    ).fetchall()
    return [
        Suggestion(
            r["raw"], r["lat"], r["lon"], "address",
            _score("address", r["lat"], r["lon"], exact=bool(r["is_exact"])),
        )
        for r in rows
    ]


# ── Forward ─────────────────────────────────────────────────────────────────

def forward(query: str) -> tuple[float, float] | None:
    """Resolve `query` to a single (lat, lon) using the local cascade.

    Returns None on miss so the caller can fall back to Tier 5 (LocationIQ).
    """
    top = autocomplete(query, limit=1)
    if top:
        return (top[0].lat, top[0].lon)
    return None


# ── Reverse ─────────────────────────────────────────────────────────────────

def nearest_address(lat: float, lon: float, radius_m: float = 50.0) -> dict | None:
    """Return the nearest address row within `radius_m` meters.

    Implemented with a small bounding-box prefilter plus per-candidate
    Haversine. For the few hundred candidates this scans at most, the
    overhead is < 1 ms and avoids a second KDTree in process memory.
    """
    db = _connect()
    if db is None:
        return None
    max_miles = radius_m / METERS_PER_MILE
    # 1° latitude ≈ 69 mi; 1° longitude ≈ 69 mi · cos(lat). Using a single
    # /69 denominator would make the longitude box narrower than max_miles at
    # Chicago's latitude (~42°), silently excluding in-range candidates.
    span_lat = max_miles / 69.0
    cos_lat = math.cos(math.radians(lat))
    span_lon = max_miles / (69.0 * cos_lat) if cos_lat > 1e-6 else span_lat
    rows = db.execute(
        "SELECT raw, lat, lon FROM addresses "
        "WHERE lat BETWEEN ? AND ? AND lon BETWEEN ? AND ?",
        (lat - span_lat, lat + span_lat, lon - span_lon, lon + span_lon),
    ).fetchall()
    best: dict | None = None
    best_d = max_miles
    for r in rows:
        d = haversine_miles(lat, lon, r["lat"], r["lon"])
        if d < best_d:
            best_d = d
            best = {
                "raw": r["raw"],
                "lat": r["lat"],
                "lon": r["lon"],
                "distance_miles": d,
            }
    return best
