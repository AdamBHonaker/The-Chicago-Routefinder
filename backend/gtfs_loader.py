"""
GTFS-based stop resolver for the CTA Transit app.

Loads stops.txt from the downloaded GTFS feed and provides functions
to find the nearest train stations and bus stops to any location.

Stop ID ranges (per CTA GTFS / Train Tracker docs):
  0     – 29999  →  Bus stops
  30000 – 39999  →  Train platform stops (direction-specific)
  40000 – 49999  →  Train parent stations (used by Train Tracker API as mapid)

Stops are parsed from stops.txt once per process and also persisted to a
binary pickle cache (stops_cache.pkl) in the same directory. On subsequent
starts the pickle is loaded instead of re-parsing CSV, provided the mtime of
stops.txt has not changed. The pickle is written atomically so a crash during
the write never leaves a corrupt cache file.

Geocoding strategy:
  1. Exact match against NEIGHBORHOOD_COORDS (instant, no network)
  2. Fuzzy match against NEIGHBORHOOD_COORDS (instant, no network)
  3. Google Maps Geocoding API (~100ms, biased to Chicago bounding box)

Geographic scope: Howard St (north) to 50th St (south), lakefront (east) to
Pulaski Rd (west). Walk times outside this rectangle fall back to Haversine
estimates and no CTA stops will be found beyond the boundary.
"""

import atexit
import csv
import datetime
import heapq
import json
import math
import os
import pickle
import re
import threading
import time
from collections import Counter
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path

import requests

# Persistent HTTP session — reuses keep-alive connections across geocode calls.
_http_session = requests.Session()

from walking import walk_minutes
from utils import haversine_miles as _haversine_miles, CHICAGO_BBOX_GOOGLE, SpatialGrid
import config as _cfg

GTFS_DIR = Path(__file__).parent / "gtfs_data"
_STOPS_CACHE_PATH = GTFS_DIR / "stops_cache.pkl"

# Google Maps Geocoding API
_GOOGLE_MAPS_GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
_GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")
# Chicago bounding box for geocoding bias (SW lat,lon | NE lat,lon)
_CHICAGO_BOUNDS = CHICAGO_BBOX_GOOGLE

# Persistent geocode cache — survives server restarts.
# Writes use a snapshot file + append-only journal so frequent flushes are O(delta),
# not O(cache size). The journal is replayed over the snapshot on load and compacted
# back into the snapshot periodically (see _GEOCODE_COMPACT_* below).
_GEOCODE_CACHE_PATH = Path(__file__).parent / "geocode_cache.json"
_GEOCODE_JOURNAL_PATH = Path(__file__).parent / "geocode_cache.journal"
# Sidecar: maps each cached address key to the Unix timestamp it was first stored.
# Used for age-based eviction — entries older than GEOCODE_CACHE_MAX_AGE_DAYS are removed.
_GEOCODE_AGES_PATH = Path(__file__).parent / "geocode_cache_ages.json"


def _restrict_perms(path: Path) -> None:
    """Restrict file mode to 0600 (owner-only). Geocode caches contain user
    search history; even on a single-tenant host this keeps the data out of
    other-user reach if the host is later shared. No-op on Windows where
    os.chmod only toggles the read-only flag."""
    try:
        os.chmod(path, 0o600)
    except OSError:
        # Best-effort: a chmod failure shouldn't crash the whole save path.
        pass

# Monthly geocode call cap — prevents runaway API costs.
# Override with env var GEOCODE_MONTHLY_LIMIT (e.g. set to 0 to disable).
# Google's free tier is ~40,000 calls/month; default leaves a 30,500-call buffer.
_GEOCODE_CALL_LIMIT = int(os.getenv("GEOCODE_MONTHLY_LIMIT", "9500"))
_GEOCODE_COUNTER_PATH = Path(__file__).parent / "geocode_counter.json"


def _load_geocode_counter() -> dict:
    """Load the monthly geocode call counter from disk, keeping only the current month."""
    month_key = datetime.date.today().strftime("%Y-%m")
    if _GEOCODE_COUNTER_PATH.exists():
        try:
            raw = json.loads(_GEOCODE_COUNTER_PATH.read_text(encoding="utf-8"))
            # Prune stale month entries; only current month is relevant
            return {month_key: raw[month_key]} if month_key in raw else {}
        except Exception as exc:
            print(f"[gtfs_loader] Could not load geocode counter: {exc}")
    return {}


def _save_geocode_counter(counter: dict) -> None:
    """Persist the monthly geocode call counter to disk using atomic rename."""
    tmp = _GEOCODE_COUNTER_PATH.with_suffix(".counter.tmp")
    try:
        tmp.write_text(json.dumps(counter, indent=2), encoding="utf-8")
        tmp.replace(_GEOCODE_COUNTER_PATH)
        _restrict_perms(_GEOCODE_COUNTER_PATH)
    except Exception as exc:
        print(f"[gtfs_loader] Could not save geocode counter: {exc}")
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass


def _geocode_call_count() -> int:
    """Return the number of Google geocoding API calls made this calendar month."""
    month_key = datetime.date.today().strftime("%Y-%m")
    return _geocode_call_counter.get(month_key, 0)


def _increment_geocode_call_count() -> int:
    """Record one Google geocoding API call for the current calendar month. Returns the new count.

    Must be called under _geocode_lock. Marks the counter dirty for the next
    background flush rather than writing to disk immediately.
    """
    global _geocode_counter_dirty
    month_key = datetime.date.today().strftime("%Y-%m")
    _geocode_call_counter[month_key] = _geocode_call_counter.get(month_key, 0) + 1
    _geocode_counter_dirty = True
    return _geocode_call_counter[month_key]


# Loaded once at import time; dirty flag is flushed by the background thread.
_geocode_call_counter: dict = _load_geocode_counter()
_geocode_counter_dirty: bool = False

# Protects _geocode_cache writes, _geocode_pending, _geocode_ages, and the
# monthly call counter.  Held only for the pre-flight quota check and the
# post-flight result store — released during the actual HTTP call so that
# concurrent requests for *different* queries can proceed in parallel.
_geocode_lock = threading.Lock()


def _load_geocode_cache() -> dict[str, tuple[float, float] | None]:
    """Load the geocode cache from disk: snapshot JSON + any appended journal lines."""
    cache: dict[str, tuple[float, float] | None] = {}
    if _GEOCODE_CACHE_PATH.exists():
        try:
            raw = json.loads(_GEOCODE_CACHE_PATH.read_text(encoding="utf-8"))
            # JSON stores lists; convert [lat, lon] back to tuples (or None)
            cache = {k: tuple(v) if v is not None else None for k, v in raw.items()}
        except Exception as exc:
            print(f"[gtfs_loader] Could not load geocode cache snapshot: {exc}")
    if _GEOCODE_JOURNAL_PATH.exists():
        try:
            with _GEOCODE_JOURNAL_PATH.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        k, v = json.loads(line)
                    except Exception:
                        # Skip torn/corrupt trailing lines rather than failing startup
                        continue
                    cache[k] = tuple(v) if v is not None else None
        except Exception as exc:
            print(f"[gtfs_loader] Could not replay geocode journal: {exc}")
    return cache


def _save_geocode_cache(cache: dict) -> bool:
    """Write the full snapshot atomically and drop the journal it subsumes.

    Returns True on success, False on failure.
    """
    tmp = _GEOCODE_CACHE_PATH.with_suffix(".tmp")
    try:
        tmp.write_text(
            json.dumps(cache, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        tmp.replace(_GEOCODE_CACHE_PATH)
        _restrict_perms(_GEOCODE_CACHE_PATH)
        # Snapshot now contains every key the journal replayed — drop it.
        try:
            _GEOCODE_JOURNAL_PATH.unlink(missing_ok=True)
        except Exception:
            pass
        return True
    except Exception as exc:
        print(f"[gtfs_loader] Could not save geocode cache: {exc}")
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass
        return False


def _load_geocode_ages() -> dict[str, float]:
    """Load the per-entry insertion timestamps from the sidecar ages file."""
    if _GEOCODE_AGES_PATH.exists():
        try:
            return json.loads(_GEOCODE_AGES_PATH.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"[gtfs_loader] Could not load geocode ages: {exc}")
    return {}


def _save_geocode_ages(ages: dict[str, float]) -> None:
    """Atomically persist the ages dict to disk."""
    tmp = _GEOCODE_AGES_PATH.with_suffix(".ages.tmp")
    try:
        tmp.write_text(json.dumps(ages, indent=2), encoding="utf-8")
        tmp.replace(_GEOCODE_AGES_PATH)
        _restrict_perms(_GEOCODE_AGES_PATH)
    except Exception as exc:
        print(f"[gtfs_loader] Could not save geocode ages: {exc}")
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass


def _evict_old_geocode_entries() -> int:
    """Remove geocode entries whose recorded age exceeds _GEOCODE_MAX_AGE_SECONDS.

    Must be called under _geocode_lock.  Mutates _geocode_cache and _geocode_ages
    in-place, then persists the trimmed ages file.  Returns the number of entries
    removed.
    """
    now = time.time()
    cutoff = now - _GEOCODE_MAX_AGE_SECONDS
    stale = [k for k, ts in _geocode_ages.items() if ts < cutoff]
    for k in stale:
        _geocode_cache.pop(k, None)
        _geocode_ages.pop(k, None)
    if stale:
        print(
            f"[gtfs_loader] Age-based eviction removed {len(stale)} geocode "
            f"entries older than {_cfg.GEOCODE_CACHE_MAX_AGE_DAYS} days"
        )
        _save_geocode_ages(_geocode_ages)
    return len(stale)


# Loaded once at import time; dirty entries are flushed by background thread.
_geocode_cache: dict[str, tuple[float, float] | None] = _load_geocode_cache()

# {address_key: Unix timestamp of first insertion} — persisted to _GEOCODE_AGES_PATH.
# Entries without a recorded age are treated as immortal (survive any eviction sweep)
# so that pre-existing cache files are never silently cleared on first upgrade.
_geocode_ages: dict[str, float] = _load_geocode_ages()

# Age-based eviction settings.
_GEOCODE_MAX_AGE_SECONDS: float = _cfg.GEOCODE_CACHE_MAX_AGE_DAYS * 24 * 3600

# Apply age-based eviction at startup so stale entries never survive a restart.
# Safe to call without _geocode_lock here — no other threads exist at import time.
_evict_old_geocode_entries()

# Entries added since the last journal append. Always mutated under _geocode_lock.
_geocode_pending: dict[str, tuple[float, float] | None] = {}
_GEOCODE_FLUSH_INTERVAL = 30        # seconds between background flushes
_GEOCODE_COMPACT_INTERVAL = 3600    # seconds between full snapshot rewrites
_GEOCODE_COMPACT_THRESHOLD = 500    # journal entries that force an early compaction
_GEOCODE_JOURNAL_LINE_LIMIT = 1000  # journal lines that force compaction regardless of entry count
_geocode_last_compact: float = time.monotonic()
_geocode_journal_entries: int = 0   # lines appended since last full snapshot

# Age-based eviction schedule.
_GEOCODE_EVICT_INTERVAL: int = _cfg.GEOCODE_EVICT_INTERVAL_SECONDS
_geocode_last_eviction: float   = time.monotonic()


def _append_geocode_journal(entries: dict[str, tuple[float, float] | None]) -> None:
    """Append new cache entries to the journal as JSONL — O(delta) per flush."""
    try:
        new_file = not _GEOCODE_JOURNAL_PATH.exists()
        with _GEOCODE_JOURNAL_PATH.open("a", encoding="utf-8") as f:
            for k, v in entries.items():
                f.write(json.dumps([k, list(v) if v is not None else None], ensure_ascii=False) + "\n")
            f.flush()
        if new_file:
            _restrict_perms(_GEOCODE_JOURNAL_PATH)
            try:
                os.fsync(f.fileno())
            except OSError:
                # fsync not supported on this fd (e.g. some network FS); tolerable.
                pass
    except Exception as exc:
        print(f"[gtfs_loader] Could not append to geocode journal: {exc}")


def _flush_geocode_cache_if_dirty() -> None:
    """Append pending entries to the journal; compact to a full snapshot periodically.

    Also flushes the monthly API call counter and runs age-based eviction once per
    _GEOCODE_EVICT_INTERVAL (weekly by default) so the cache does not grow unbounded
    even when compaction thresholds are never hit.
    """
    global _geocode_pending, _geocode_last_compact, _geocode_journal_entries
    global _geocode_last_eviction, _geocode_counter_dirty
    with _geocode_lock:
        # Weekly age-based sweep — independent of compaction thresholds.
        now_mono = time.monotonic()
        if now_mono - _geocode_last_eviction >= _GEOCODE_EVICT_INTERVAL:
            _evict_old_geocode_entries()
            _geocode_last_eviction = now_mono

        # Persist the monthly call counter if it has been incremented since the last flush.
        if _geocode_counter_dirty:
            _save_geocode_counter(_geocode_call_counter)
            _geocode_counter_dirty = False

        if not _geocode_pending:
            # Even with no new entries, honor a time-based compaction so any prior
            # journal growth gets folded back into the snapshot eventually.
            if (
                _geocode_journal_entries > 0
                and now_mono - _geocode_last_compact >= _GEOCODE_COMPACT_INTERVAL
            ):
                _save_geocode_cache(_geocode_cache)
                _geocode_journal_entries = 0
                _geocode_last_compact = now_mono
            return
        pending = _geocode_pending
        _geocode_pending = {}
        now = time.monotonic()
        should_compact = (
            _geocode_journal_entries + len(pending) >= _GEOCODE_COMPACT_THRESHOLD
            or _geocode_journal_entries >= _GEOCODE_JOURNAL_LINE_LIMIT
            or now - _geocode_last_compact >= _GEOCODE_COMPACT_INTERVAL
        )
        if should_compact:
            if _save_geocode_cache(_geocode_cache):
                _geocode_journal_entries = 0
                _geocode_last_compact = now
            else:
                # Save failed — restore pending so entries aren't lost on next flush
                _geocode_pending.update(pending)
        else:
            _append_geocode_journal(pending)
            _geocode_journal_entries += len(pending)


def _start_geocode_flush_thread() -> None:
    """Start a background daemon thread that flushes the cache every 30 s."""
    stop_event = threading.Event()

    def _flush_loop() -> None:
        while not stop_event.wait(timeout=_GEOCODE_FLUSH_INTERVAL):
            _flush_geocode_cache_if_dirty()

    t = threading.Thread(target=_flush_loop, name="geocode-cache-flusher", daemon=True)
    t.start()
    # Guarantee a final flush even if the process exits before the next tick.
    atexit.register(_flush_geocode_cache_if_dirty)


_start_geocode_flush_thread()


# ---------------------------------------------------------------------------
# Neighborhood / landmark coordinates — fast cache
# Geographic scope: Howard St (north) → 50th St (south) | Lakefront → Pulaski Rd (west)
# Entries outside this rectangle are omitted — they would find no nearby CTA stops.
# ---------------------------------------------------------------------------

NEIGHBORHOOD_COORDS: dict[str, tuple[float, float]] = {

    # ── ROGERS PARK / FAR NORTH ──────────────────────────────────────────────
    "rogers park":          (42.0085, -87.6688),
    "loyola":               (41.9998, -87.6586),
    "loyola university":    (41.9998, -87.6586),
    "granville":            (41.9943, -87.6579),
    "thorndale":            (41.9898, -87.6577),
    "morse":                (41.9832, -87.6590),
    "jarvis":               (41.9930, -87.6693),

    # ── EDGEWATER ────────────────────────────────────────────────────────────
    "edgewater":            (41.9889, -87.6600),
    "bryn mawr":            (41.9834, -87.6590),
    "foster beach":         (41.9791, -87.6403),
    "foster avenue beach":  (41.9791, -87.6403),

    # ── ANDERSONVILLE ────────────────────────────────────────────────────────
    "andersonville":        (41.9800, -87.6682),
    "berwyn":               (41.9778, -87.6593),
    "berwyn station":       (41.9778, -87.6593),
    "swedish american museum": (41.9799, -87.6690),

    # ── UPTOWN ───────────────────────────────────────────────────────────────
    "uptown":               (41.9650, -87.6550),
    "wilson":               (41.9648, -87.6575),
    "lawrence":             (41.9688, -87.6580),
    "argyle":               (41.9735, -87.6580),
    "sheridan":             (41.9542, -87.6537),
    "montrose beach":       (41.9643, -87.6384),
    "montrose harbor":      (41.9643, -87.6384),
    "uptown theatre":       (41.9648, -87.6545),
    "green mill":           (41.9656, -87.6556),
    "illinois masonic":     (41.9437, -87.6561),
    "advocate illinois masonic": (41.9437, -87.6561),

    # ── LINCOLN SQUARE / RAVENSWOOD ──────────────────────────────────────────
    "lincoln square":       (41.9679, -87.6848),
    "ravenswood":           (41.9656, -87.6741),

    # ── WRIGLEYVILLE / LAKEVIEW ──────────────────────────────────────────────
    "wrigleyville":         (41.9476, -87.6553),
    "wrigley field":        (41.9484, -87.6553),
    "lakeview":             (41.9433, -87.6513),
    "east lakeview":        (41.9395, -87.6420),
    "boystown":             (41.9444, -87.6491),
    "addison":              (41.9476, -87.6542),
    "belmont":              (41.9394, -87.6527),
    "southport corridor":   (41.9416, -87.6641),
    "southport":            (41.9416, -87.6641),
    "diversey":             (41.9321, -87.6527),
    "wellington":           (41.9360, -87.6545),
    "paulina":              (41.9437, -87.6705),
    "diversey harbor":      (41.9321, -87.6385),
    "theater on the lake":  (41.9258, -87.6334),

    # ── LINCOLN PARK ─────────────────────────────────────────────────────────
    "lincoln park":         (41.9228, -87.6482),
    "lincoln park zoo":     (41.9220, -87.6332),
    "fullerton":            (41.9253, -87.6527),
    "armitage":             (41.9175, -87.6513),
    "depaul":               (41.9253, -87.6554),
    "depaul university":    (41.9253, -87.6554),
    "north avenue beach":   (41.9168, -87.6354),
    "oz park":              (41.9257, -87.6395),
    "chicago history museum": (41.9218, -87.6318),
    "peggy notebaert nature museum": (41.9218, -87.6341),
    "steppenwolf theatre":  (41.9119, -87.6316),
    "steppenwolf":          (41.9119, -87.6316),

    # ── OLD TOWN ─────────────────────────────────────────────────────────────
    "old town":             (41.9101, -87.6364),
    "sedgwick":             (41.9101, -87.6386),
    "north/clybourn":       (41.9103, -87.6486),
    "north clybourn":       (41.9103, -87.6486),
    "second city":          (41.9101, -87.6356),
    "wells street":         (41.9101, -87.6340),

    # ── GOLD COAST ───────────────────────────────────────────────────────────
    "gold coast":           (41.9016, -87.6298),
    "clark/division":       (41.9046, -87.6312),
    "clark division":       (41.9046, -87.6312),
    "newberry library":     (41.9019, -87.6317),
    "washington square park": (41.9019, -87.6317),
    "lurie childrens hospital": (41.9049, -87.6241),
    "lurie children's hospital": (41.9049, -87.6241),
    "ann & robert h. lurie": (41.9049, -87.6241),
    "chicago water tower":  (41.9007, -87.6235),
    "water tower place":    (41.9007, -87.6235),
    "pumping station":      (41.9007, -87.6233),

    # ── RIVER NORTH ──────────────────────────────────────────────────────────
    "river north":          (41.8944, -87.6333),
    "merchandise mart":     (41.8883, -87.6360),
    "chicago avenue":       (41.8966, -87.6269),
    "chicago station":      (41.8966, -87.6280),
    "gallery district":     (41.8933, -87.6348),

    # ── NEAR NORTH / STREETERVILLE / MAG MILE ────────────────────────────────
    "near north":           (41.8976, -87.6271),
    "streeterville":        (41.8924, -87.6196),
    "magnificent mile":     (41.8951, -87.6249),
    "mag mile":             (41.8951, -87.6249),
    "michigan avenue":      (41.8847, -87.6240),
    "navy pier":            (41.8919, -87.6053),
    "grand":                (41.8912, -87.6276),
    "john hancock":         (41.8988, -87.6232),
    "875 north michigan":   (41.8988, -87.6232),
    "875 n michigan":       (41.8988, -87.6232),
    "northwestern memorial hospital": (41.8951, -87.6218),
    "northwestern memorial": (41.8951, -87.6218),
    "prentice women's hospital": (41.8951, -87.6218),
    "northwestern university chicago": (41.8951, -87.6218),

    # ── THE LOOP ─────────────────────────────────────────────────────────────
    "loop":                 (41.8827, -87.6326),
    "the loop":             (41.8827, -87.6326),
    "downtown":             (41.8827, -87.6326),
    "downtown chicago":     (41.8827, -87.6326),
    "millennium park":      (41.8827, -87.6233),
    "maggie daley park":    (41.8832, -87.6196),
    "grant park":           (41.8757, -87.6189),
    "art institute":            (41.8796, -87.6237),
    "art institute of chicago": (41.8796, -87.6237),
    "chicago art museum":       (41.8796, -87.6237),
    "art museum":               (41.8796, -87.6237),
    "the art institute":        (41.8796, -87.6237),
    "theater district":     (41.8854, -87.6295),
    "chicago theatre":      (41.8854, -87.6295),
    "state street":         (41.8800, -87.6278),
    "union station":        (41.8789, -87.6401),
    "ogilvie":              (41.8821, -87.6416),
    "ogilvie transportation center": (41.8821, -87.6416),
    "lasalle street station": (41.8757, -87.6315),
    "museum campus":        (41.8666, -87.6151),
    "soldier field":        (41.8623, -87.6167),
    "shedd aquarium":       (41.8676, -87.6139),
    "field museum":         (41.8663, -87.6168),
    "adler planetarium":    (41.8664, -87.6069),
    "harold washington library": (41.8762, -87.6286),
    "harold washington library center": (41.8762, -87.6286),
    "chicago cultural center": (41.8838, -87.6248),
    "millennium station":   (41.8844, -87.6244),
    "willis tower":         (41.8789, -87.6359),
    "sears tower":          (41.8789, -87.6359),
    "wrigley building":     (41.8891, -87.6244),
    "tribune tower":        (41.8902, -87.6245),
    "chicago riverwalk":    (41.8876, -87.6291),
    "lyric opera":          (41.8855, -87.6371),
    "auditorium theatre":   (41.8762, -87.6263),
    "chicago symphony orchestra": (41.8796, -87.6263),
    "symphony center":      (41.8796, -87.6263),
    "columbia college":     (41.8723, -87.6247),
    "columbia college chicago": (41.8723, -87.6247),
    "school of the art institute": (41.8796, -87.6237),
    "saic":                 (41.8796, -87.6237),
    "daley plaza":          (41.8840, -87.6318),
    "city hall":            (41.8840, -87.6318),

    # ── SOUTH LOOP / NEAR SOUTH ──────────────────────────────────────────────
    "south loop":           (41.8674, -87.6278),
    "printers row":         (41.8723, -87.6278),
    "printer's row":        (41.8723, -87.6278),
    "chinatown":            (41.8508, -87.6326),
    "armour square":        (41.8500, -87.6350),
    "bridgeport":           (41.8350, -87.6450),
    "canaryville":          (41.8220, -87.6350),
    "fuller park":          (41.8100, -87.6350),

    # ── NEAR WEST SIDE ───────────────────────────────────────────────────────
    "near west side":       (41.8750, -87.6600),
    "greektown":            (41.8775, -87.6475),
    "little italy":         (41.8725, -87.6550),
    "uic":                  (41.8700, -87.6500),
    "university village":   (41.8700, -87.6500),
    "united center":        (41.8806, -87.6742),
    "medical district":     (41.8700, -87.6730),

    # ── WEST TOWN / UKRAINIAN VILLAGE / WICKER PARK ──────────────────────────
    "west town":            (41.9000, -87.6700),
    "ukrainian village":    (41.8950, -87.6800),
    "wicker park":          (41.9090, -87.6800),
    "bucktown":             (41.9190, -87.6800),
    "noble square":         (41.8980, -87.6650),
    "east village":         (41.8980, -87.6750),

    # ── LOGAN SQUARE / HUMBOLDT PARK ─────────────────────────────────────────
    "logan square":         (41.9290, -87.7000),
    "humboldt park":        (41.9000, -87.7200),
    "palmer square":        (41.9230, -87.7000),

    # ── AVONDALE / HERMOSA ───────────────────────────────────────────────────
    # (belmont cragin, montclare, galewood omitted — west of Pulaski)
    "avondale":             (41.9400, -87.7100),
    "hermosa":              (41.9200, -87.7200),

    # ── IRVING PARK / NORTH PARK ─────────────────────────────────────────────
    # (portage park, albany park omitted — west of Pulaski)
    "irving park":          (41.9540, -87.7200),
    "mayfair":              (41.9730, -87.7100),
    "north park":           (41.9800, -87.7200),
    "west ridge":           (41.9990, -87.6950),
    "sauganash":            (41.9900, -87.7200),

    # ── EAST GARFIELD PARK / NORTH LAWNDALE ──────────────────────────────────
    # (west garfield park, austin, dunning, jefferson park,
    #  norwood park, forest glen, edison park omitted — west of Pulaski)
    "east garfield park":   (41.8800, -87.7200),
    "north lawndale":       (41.8650, -87.7200),

    # ── SOUTH LAWNDALE / PILSEN / BACK OF THE YARDS ──────────────────────────
    # (west elsdon, gage park, chicago lawn, west lawn omitted — south of 50th)
    "little village":       (41.8250, -87.7200),
    "south lawndale":       (41.8250, -87.7200),
    "pilsen":               (41.8550, -87.6600),
    "18th street":          (41.8575, -87.6700),
    "back of the yards":    (41.8100, -87.6550),
    "new city":             (41.8100, -87.6550),
    "mckinley park":        (41.8290, -87.6750),
    "brighton park":        (41.8250, -87.6950),
    "archer heights":       (41.8200, -87.7250),

    # ── BRONZEVILLE / DOUGLAS / GRAND BOULEVARD ──────────────────────────────
    # (washington park, u of c, university of chicago omitted — south of 50th)
    "bronzeville":          (41.8350, -87.6150),
    "douglas":              (41.8420, -87.6200),
    "grand boulevard":      (41.8200, -87.6150),
    "sox-35th":             (41.8312, -87.6304),
    "35th street":          (41.8312, -87.6304),

    # ── KENWOOD ──────────────────────────────────────────────────────────────
    # (hyde park, woodlawn, south shore, greater grand crossing omitted — south of 50th)
    "kenwood":              (41.8100, -87.6050),

    # ── KEY CTA STATIONS (within coverage area) ───────────────────────────────
    # (95th/dan ryan, 87th, 79th, 69th, garfield, harlem/lake, cicero omitted
    #  — south of 50th or west of Pulaski)
    "cermak-chinatown":     (41.8534, -87.6306),
    "pulaski":              (41.8866, -87.7260),
    "kedzie":               (41.8864, -87.7063),

    # ── LOOP TRAIN STATIONS (direct CTA name lookups) ────────────────────────
    "lake":                 (41.8849, -87.6278),
    "monroe":               (41.8806, -87.6278),
    "jackson":              (41.8781, -87.6278),
    "harrison":             (41.8742, -87.6278),
    "roosevelt":            (41.8674, -87.6278),
    "clark/lake":           (41.8858, -87.6310),
    "state/lake":           (41.8858, -87.6278),
    "washington/wabash":    (41.8832, -87.6258),
    "washington/wells":     (41.8829, -87.6340),
    "adams/wabash":         (41.8796, -87.6258),
    "quincy":               (41.8784, -87.6340),
    "lasalle/van buren":    (41.8757, -87.6315),
    "clinton":              (41.8749, -87.6408),
}


# ---------------------------------------------------------------------------
# Google Maps geocoding
# ---------------------------------------------------------------------------

def geocode_google(query: str) -> tuple[float, float] | None:
    """
    Geocode a free-text address, building name, or intersection to (lat, lon)
    using the Google Maps Geocoding API. Results are biased to Chicago.

    Returns None on any failure (network error, no result, missing key).
    Requires GOOGLE_MAPS_API_KEY in the environment.
    """
    # Fast path: already cached (no lock needed — dict reads are thread-safe)
    if query in _geocode_cache:
        return _geocode_cache[query]

    # Pre-flight check: validate API key and quota under the lock, then release
    # before the network call so concurrent requests for *different* queries can
    # proceed in parallel.  Two concurrent requests for the *same* uncached query
    # may both pass this gate; the inner lock below handles that race at store time.
    with _geocode_lock:
        if query in _geocode_cache:
            return _geocode_cache[query]

        if not _GOOGLE_MAPS_API_KEY:
            print("[gtfs_loader] GOOGLE_MAPS_API_KEY not set — geocoding unavailable")
            return None

        # Monthly call cap (configurable via GEOCODE_MONTHLY_LIMIT; 0 = unlimited)
        current_count = _geocode_call_count()
        if _GEOCODE_CALL_LIMIT > 0 and current_count >= _GEOCODE_CALL_LIMIT:
            print(
                f"[gtfs_loader] Monthly geocoding limit reached "
                f"({current_count}/{_GEOCODE_CALL_LIMIT}) — skipping API call for '{query}'"
            )
            return None

    # Network I/O outside the lock.
    try:
        resp = _http_session.get(
            _GOOGLE_MAPS_GEOCODE_URL,
            params={
                "address": query if ("chicago" in query.lower() or ", il" in query.lower() or "illinois" in query.lower()) else query + ", Chicago, IL",
                "key": _GOOGLE_MAPS_API_KEY,
                "components": "country:US",
                "bounds": _CHICAGO_BOUNDS,
            },
            timeout=5,
        )
        data = resp.json()
    except Exception as exc:
        print(f"[gtfs_loader] Google geocoding failed for '{query}': {exc}")
        # Don't cache transient network/timeout errors — allow retries.
        return None

    # Re-acquire lock to store the result atomically and increment the quota counter.
    with _geocode_lock:
        # Re-check: another thread may have stored the result while we were in flight.
        if query in _geocode_cache:
            return _geocode_cache[query]

        if data.get("status") == "OK" and data.get("results"):
            loc = data["results"][0]["geometry"]["location"]
            coords: tuple[float, float] = (float(loc["lat"]), float(loc["lng"]))
            _geocode_cache[query] = coords
            _geocode_pending[query] = coords
            _geocode_ages[query] = time.time()  # record insertion time for age-based eviction
            new_count = _increment_geocode_call_count()
            print(
                f"[gtfs_loader] Geocoded and cached '{query}' -> {coords} "
                f"(monthly calls: {new_count}/{_GEOCODE_CALL_LIMIT})"
            )
            return coords

        status = data.get("status")
        print(f"[gtfs_loader] Google geocoding returned status '{status}' for '{query}'")
        # Only cache permanent misses (ZERO_RESULTS = address genuinely doesn't exist).
        # Transient errors (OVER_QUERY_LIMIT, REQUEST_DENIED, UNKNOWN_ERROR, etc.)
        # must not be cached so future requests can retry.
        if status == "ZERO_RESULTS":
            # BUG-029: ZERO_RESULTS still costs one API credit — count it
            _increment_geocode_call_count()
            _geocode_cache[query] = None
            _geocode_pending[query] = None
            _geocode_ages[query] = time.time()

    return None


def reverse_geocode_google(lat: float, lon: float) -> str | None:
    """
    Reverse geocode (lat, lon) to a human-readable address string using the
    Google Maps Geocoding API.  Returns None on any failure or missing key.

    The returned string has the zip code and country stripped so it fits
    cleanly in the location input, e.g. "78 E Washington St, Chicago, IL".
    """
    if not _GOOGLE_MAPS_API_KEY:
        return None
    try:
        resp = _http_session.get(
            _GOOGLE_MAPS_GEOCODE_URL,
            params={
                "latlng": f"{lat},{lon}",
                "key": _GOOGLE_MAPS_API_KEY,
            },
            timeout=5,
        )
        data = resp.json()
    except Exception as exc:
        print(f"[gtfs_loader] Reverse geocoding failed for ({lat},{lon}): {exc}")
        return None

    if data.get("status") == "OK" and data.get("results"):
        addr = data["results"][0].get("formatted_address", "")
        # Strip zip code and country suffix, e.g. ", 60602, USA" or ", IL 60602, USA"
        addr = re.sub(r",\s*\d{5}(-\d{4})?(?=,|$)", "", addr)
        addr = re.sub(r",\s*(United States|USA)$", "", addr)
        return addr.strip() or None
    return None


# ---------------------------------------------------------------------------
# GTFS stop loader (cached after first call)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _load_stops() -> tuple[list[dict], list[dict]]:
    """
    Parse stops.txt and return (train_stations, bus_stops).

    On first call after a GTFS update the CSV is parsed and the result is
    persisted to stops_cache.pkl alongside the source file's mtime.  On
    subsequent starts the pickle is loaded instead, skipping CSV parsing
    entirely.  The pickle is written atomically (tmp → rename) so a crash
    during the write never leaves a corrupt cache.

    Called once per process; result is also kept in the lru_cache.
    """
    stops_file = GTFS_DIR / "stops.txt"
    if not stops_file.exists():
        raise FileNotFoundError(
            f"GTFS stops file not found at {stops_file}. "
            "Run `python fetch_gtfs.py` to download the data."
        )

    current_mtime: float = stops_file.stat().st_mtime

    # Try the binary cache first.
    if _STOPS_CACHE_PATH.exists():
        try:
            with _STOPS_CACHE_PATH.open("rb") as f:
                cached_mtime, train_stations, bus_stops = pickle.load(f)
            if cached_mtime == current_mtime:
                return train_stations, bus_stops
            # mtime mismatch — fall through to re-parse.
        except Exception as exc:
            print(f"[gtfs_loader] Could not load stops cache (will re-parse): {exc}")

    train_stations: list[dict] = []
    bus_stops: list[dict] = []

    with open(stops_file, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                stop_id_int = int(row["stop_id"].strip())
                lat = float(row["stop_lat"].strip())
                lon = float(row["stop_lon"].strip())
            except (ValueError, KeyError):
                continue

            name = row.get("stop_name", "").strip()
            location_type = row.get("location_type", "0").strip()
            stop_id_str = str(stop_id_int)

            if 40000 <= stop_id_int <= 49999 and location_type == "1":
                train_stations.append({
                    "mapid": stop_id_str,
                    "name": name,
                    "lat": lat,
                    "lon": lon,
                    "type": "train_station",
                })

            elif stop_id_int <= 29999 and location_type in ("0", ""):
                bus_stops.append({
                    "stop_id": stop_id_str,
                    "name": name,
                    "lat": lat,
                    "lon": lon,
                    "type": "bus_stop",
                })

    # Persist the parsed result atomically so the next startup can skip CSV parsing.
    tmp = _STOPS_CACHE_PATH.with_suffix(".tmp")
    try:
        with tmp.open("wb") as f:
            pickle.dump((current_mtime, train_stations, bus_stops), f)
        tmp.replace(_STOPS_CACHE_PATH)
    except Exception as exc:
        print(f"[gtfs_loader] Could not save stops cache: {exc}")
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass

    return train_stations, bus_stops


# ---------------------------------------------------------------------------
# Spatial index for nearest-stop queries
# ---------------------------------------------------------------------------
#
# Cell size of ~1 mile in each axis means a 1.0-mile radius query touches
# at most a 3×3 block of cells (9 cells), regardless of catalog size.
# SpatialGrid from utils handles bucketing, bounding-box prefilter, and
# Haversine postfilter in one shared implementation.

_SPATIAL_CELL_LAT_DEG = 1.0 / 69.0    # ~1 mile of latitude
_SPATIAL_CELL_LON_DEG = 1.0 / 51.35   # ~1 mile of longitude at Chicago's latitude


@lru_cache(maxsize=2)
def _spatial_index(kind: str) -> SpatialGrid:
    """
    Build a SpatialGrid for either "train" or "bus" stops.
    Built once on first use and cached for the process lifetime.
    """
    train_stations, bus_stops = _load_stops()
    stops = train_stations if kind == "train" else bus_stops
    grid = SpatialGrid(cell_lat_deg=_SPATIAL_CELL_LAT_DEG, cell_lon_deg=_SPATIAL_CELL_LON_DEG)
    for s in stops:
        grid.add(s["lat"], s["lon"], s)
    return grid


def _candidates_within(
    kind: str,
    lat: float,
    lon: float,
    radius_miles: float,
) -> list[tuple[float, dict]]:
    """Return (distance_miles, stop) pairs for every stop of `kind` within radius_miles of (lat, lon)."""
    return _spatial_index(kind).query(lat, lon, radius_miles)


# ---------------------------------------------------------------------------
# Public lookup functions
# ---------------------------------------------------------------------------

def find_nearest_train_stations(
    lat: float,
    lon: float,
    max_distance_miles: float = 0.5,
    max_results: int = 3,
    walk_to_station: bool = True,
) -> list[dict]:
    """
    Return the closest train parent stations within walking distance,
    each annotated with real street-network walk_minutes.

    walk_to_station=True  (default): walk_minutes computed from (lat,lon) → station.
                                     Use for origin: user walks TO the station.
    walk_to_station=False:           walk_minutes computed from station → (lat,lon).
                                     Use for destination: user walks FROM the station.
    """
    hits = _candidates_within("train", lat, lon, max_distance_miles)
    candidates = [{**s} for _, s in heapq.nsmallest(max_results, hits, key=lambda item: item[0])]

    for s in candidates:
        if walk_to_station:
            s["walk_minutes"] = walk_minutes(lat, lon, s["lat"], s["lon"])
        else:
            s["walk_minutes"] = walk_minutes(s["lat"], s["lon"], lat, lon)

    return sorted(candidates, key=lambda s: s["walk_minutes"])


def find_nearest_bus_stops(
    lat: float,
    lon: float,
    max_distance_miles: float = 0.25,
    max_results: int = 5,
) -> list[dict]:
    """
    Return the closest bus stops within reach, each annotated with real
    street-network walk_minutes.  Probes the spatial index at the maximum
    radius once and partitions client-side by ring (0.25 → 0.5 → 0.75 → 1.0)
    so a sparse area still gets the "expand outward" behavior without
    re-querying the spatial index multiple times.
    """
    rings = [r for r in (0.25, 0.5, 0.75, 1.0) if r <= max_distance_miles]
    if not rings or rings[-1] < max_distance_miles:
        rings.append(max_distance_miles)
    max_radius = rings[-1]

    # One spatial query at the largest radius. The grid cost dominates over
    # the per-stop distance test we'll re-do in the partition step.
    all_hits = _candidates_within("bus", lat, lon, max_radius)
    if not all_hits:
        return []

    # Walk outward through the rings until we find at least one stop. This
    # preserves the original "prefer closest, expand only if empty" behaviour.
    hits: list[tuple[float, dict]] = []
    for radius in rings:
        hits = [item for item in all_hits if item[0] <= radius]
        if hits:
            break

    candidates = [{**s} for _, s in heapq.nsmallest(max_results, hits, key=lambda item: item[0])]

    for s in candidates:
        s["walk_minutes"] = walk_minutes(lat, lon, s["lat"], s["lon"])

    return sorted(candidates, key=lambda s: s["walk_minutes"])


_FUZZY_STOP_WORDS: frozenset[str] = frozenset(
    {"the", "of", "a", "an", "and", "at", "in", "on", "chicago"}
)


@lru_cache(maxsize=1)
def _neighborhood_word_index() -> dict[str, frozenset[str]]:
    """
    Inverted index: meaningful word → frozenset of NEIGHBORHOOD_COORDS keys
    containing that word. Built once; lets multi-word fuzzy queries skip
    keys that can't possibly share a meaningful token.
    """
    word_keys: dict[str, set[str]] = {}
    for key in NEIGHBORHOOD_COORDS:
        for w in set(key.split()) - _FUZZY_STOP_WORDS:
            word_keys.setdefault(w, set()).add(key)
    return {w: frozenset(ks) for w, ks in word_keys.items()}


@lru_cache(maxsize=1024)
def fuzzy_match_neighborhood(query: str) -> tuple[tuple[float, float] | None, str | None]:
    """
    Fuzzy-match a lowercased, stripped query against NEIGHBORHOOD_COORDS.

    Requires both a similarity score ≥ 0.95 AND at least one meaningful word
    in common (multi-word queries only) so that "chicago art museum" never
    matches "chicago history museum" on structural words alone.

    Returns (coords, matched_key) if a match is found, else (None, None).
    This is a shared helper used by both resolve_location() (here) and
    _coords_for_location() in main.py so the threshold and stop-word list
    stay in sync automatically.
    """
    q_words = set(query.split()) - _FUZZY_STOP_WORDS

    # Multi-word queries must share a meaningful word with the matched key
    # — use the inverted index to skip keys that can't possibly qualify.
    # Single-word / stop-word-only queries scan the full map (behavior
    # preserved — those never had the word-overlap requirement).
    if len(q_words) > 1:
        word_index = _neighborhood_word_index()
        candidates: set[str] = set()
        for w in q_words:
            hits = word_index.get(w)
            if hits:
                candidates.update(hits)
        if not candidates:
            return None, None
        iterable: "object" = candidates
    else:
        iterable = NEIGHBORHOOD_COORDS

    # SequenceMatcher caches info about seq2, so hold `query` as seq2 and
    # swap seq1 per key — this is the documented fast pattern for "one vs many".
    matcher = SequenceMatcher()
    matcher.set_seq2(query)

    best_score, best_key = 0.0, None
    for key in iterable:
        matcher.set_seq1(key)
        # quick_ratio() is a cheap upper bound on ratio(); if it can't beat
        # the current best we can skip the expensive real computation.
        if matcher.quick_ratio() <= best_score:
            continue
        score = matcher.ratio()
        if score <= best_score:
            continue
        best_score = score
        best_key = key
        # A ratio of 1.0 means exact match — nothing can beat it.
        if best_score >= 0.99:
            break
    if best_score >= 0.95 and best_key:
        return NEIGHBORHOOD_COORDS[best_key], best_key
    return None, None


# ---------------------------------------------------------------------------
# Street abbreviation normalization
# ---------------------------------------------------------------------------

# Defined as a tuple of (abbr, expansion) pairs rather than a dict literal so
# that a duplicate key is caught at import time instead of silently winning.
_ABBR_PAIRS: tuple[tuple[str, str], ...] = (
    ("blvd", "boulevard"),
    ("pkwy", "parkway"),
    ("expy", "expressway"),
    ("terr", "terrace"),
    ("ter",  "terrace"),
    ("hwy",  "highway"),
    ("ave",  "avenue"),
    ("cir",  "circle"),
    ("st",   "street"),
    ("dr",   "drive"),
    ("ln",   "lane"),
    ("ct",   "court"),
    ("rd",   "road"),
    ("pl",   "place"),
    ("sq",   "square"),
)
_ABBR_MAP: dict[str, str] = dict(_ABBR_PAIRS)
_dup_abbr_keys = [k for k, n in Counter(p[0] for p in _ABBR_PAIRS).items() if n > 1]
assert not _dup_abbr_keys, f"_ABBR_PAIRS contains duplicate keys: {_dup_abbr_keys}"
del _dup_abbr_keys
# Sort longest-first so longer patterns are tried before shorter ones
_sorted_abbrs = sorted(_ABBR_MAP, key=len, reverse=True)
_COORD_RE = re.compile(r"^(-?\d{1,3}\.?\d*),\s*(-?\d{1,3}\.?\d*)$")

_STREET_ABBR_RE = re.compile(
    # Lookahead (?=\s*(?:,|$)) requires the token to be at end-of-string or
    # immediately before a comma.  This prevents "St." in "St. Michael's Church"
    # from matching (it's followed by more words), while still matching
    # "123 N Clark St" (end of string) and "123 N Clark St, Chicago" (before comma).
    r"\b(" + "|".join(re.escape(a) + r"\.?" for a in _sorted_abbrs) + r")\b(?=\s*(?:,|$))",
    re.IGNORECASE,
)


def _street_abbr_replace(m: re.Match) -> str:
    token = m.group(0).lower().rstrip(".")
    return _ABBR_MAP.get(token, m.group(0))


def _normalize_street_abbr(query: str) -> str:
    """
    Expand USPS street suffix abbreviations (e.g. "Ave" → "avenue",
    "Blvd." → "boulevard") in a lowercased address string.

    Directional prefixes (N/S/E/W) are intentionally not expanded.
    """
    return _STREET_ABBR_RE.sub(_street_abbr_replace, query)


def resolve_location(query: str) -> tuple[list[dict], list[dict], str | None]:
    """
    Convert a free-text location query to nearby train stations and bus stops.

    Resolution order:
      1. Exact match against NEIGHBORHOOD_COORDS
      2. Fuzzy match against NEIGHBORHOOD_COORDS (threshold: 0.95 similarity)
      3. Google Maps Geocoding API (network call, ~100ms, biased to Chicago)

    Returns:
        (train_stations, bus_stops, matched_name)
        matched_name is the dict key or the original query if geocoded.
    """
    original_query = query.strip()

    # Fast-path: GPS coordinate strings (e.g. "41.893,-87.631") bypass all fuzzy
    # matching and geocoding so they never hit geocode_google(), avoiding extra latency.
    m = _COORD_RE.match(original_query)
    if m:
        lat, lon = float(m.group(1)), float(m.group(2))
        return (
            find_nearest_train_stations(lat, lon),
            find_nearest_bus_stops(lat, lon),
            original_query,
        )

    q = original_query.lower()
    q = _normalize_street_abbr(q)          # expand "Ave" → "avenue", etc.

    # 1. Exact match
    coords = NEIGHBORHOOD_COORDS.get(q)
    matched_name = original_query if coords else None

    # 2. Fuzzy match via shared helper (0.95 threshold + meaningful-word guard)
    if coords is None:
        coords, matched_name = fuzzy_match_neighborhood(q)

    # 3. Google Maps geocoding fallback
    if coords is None:
        coords = geocode_google(q)
        if coords:
            matched_name = original_query

    if coords is None:
        return [], [], None

    lat, lon = coords
    return (
        find_nearest_train_stations(lat, lon),
        find_nearest_bus_stops(lat, lon),
        matched_name,
    )


def coords_for_location(
    query: str,
    fallback_stations: list[dict] | None = None,
) -> tuple[float, float] | None:
    """Return (lat, lon) for a location query: exact dict → fuzzy → Google → station centroid."""
    q = _normalize_street_abbr(query.lower().strip())
    coords = NEIGHBORHOOD_COORDS.get(q)
    if coords:
        return coords
    coords, _ = fuzzy_match_neighborhood(q)
    if coords:
        return coords
    coords = geocode_google(q)
    if coords:
        return coords
    if fallback_stations:
        lats = [s["lat"] for s in fallback_stations]
        lons = [s["lon"] for s in fallback_stations]
        return (sum(lats) / len(lats), sum(lons) / len(lons))
    return None
