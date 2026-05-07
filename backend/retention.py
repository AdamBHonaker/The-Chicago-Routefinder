"""
New vs returning visitor tracking (FEAT-002).

Privacy design:
  * A 90-day opaque random ID (``returnId``) is set in an ``httpOnly``
    ``Secure`` cookie. SameSite is ``None`` in production (cross-site
    Vercel↔Railway requires it) and ``Lax`` in local dev. The raw value is
    held in memory for the duration of the request only; it is HMAC-SHA256-
    hashed with a stable per-deployment retention key before any comparison
    or storage.
  * The raw ``returnId`` value is never written to disk.
  * The only persistent cross-day artifact is the Bloom filter bit array,
    which stores fixed-salt fingerprints. Even with the filter in hand an
    attacker cannot reverse the fingerprint back to ``returnId`` because
    HMAC is a one-way function.
  * Daily aggregate: ``{date, new: int, returning: int}``. "Returning" =
    the visitor's fingerprint was probably seen on a previous day (subject
    to the Bloom filter's false-positive rate).
  * Bloom filter FPR: ≤1% when the filter holds ≤BLOOM_CAPACITY items.
    At BLOOM_CAPACITY = 10 000 and current ~200 DAU, the filter fills in
    roughly 50 days. When the count exceeds BLOOM_CAPACITY the module logs
    a warning and auto-resets the filter so FPR stays bounded.

Accepted privacy tradeoff (from FEAT-002 scope):
  The Bloom filter uses a stable retention key (DAILY_SALT + ":retention")
  rather than the daily-rotating salt. This means the same browser can be
  recognised across days — you can ask "is this fingerprint probably in the
  set?" but not "who is this user?". The returnId is an opaque random token
  with no PII linkage. This tradeoff is explicitly documented in
  docs/PRIVACY.md.

Maintenance: see docs/ANALYTICS_MAINTENANCE.md.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import math
import os
import secrets

import analytics_store

logger = __import__("logging").getLogger(__name__)

# ---------------------------------------------------------------------------
# Bloom filter parameters — 1% FPR at 10 000 unique fingerprints (~12 KB)
# ---------------------------------------------------------------------------
BLOOM_CAPACITY = 10_000
_BLOOM_FPR = 0.01
BLOOM_M: int = max(1, int(-BLOOM_CAPACITY * math.log(_BLOOM_FPR) / (math.log(2) ** 2)) + 1)
BLOOM_K: int = max(1, round((BLOOM_M / BLOOM_CAPACITY) * math.log(2)))

# ---------------------------------------------------------------------------
# Cookie
# ---------------------------------------------------------------------------
COOKIE_NAME = "rid"
COOKIE_MAX_AGE = 90 * 24 * 60 * 60  # 90 days in seconds

# ---------------------------------------------------------------------------
# Retention HMAC key — stable across days (intentional; see module docstring)
# ---------------------------------------------------------------------------
_DAILY_SALT = os.getenv("DAILY_SALT", "default-insecure-salt")
if _DAILY_SALT == "default-insecure-salt" and os.getenv("APP_ENV") == "production":
    raise RuntimeError(
        "DAILY_SALT env var must be set in production. retention.py derives "
        "the retention key from DAILY_SALT; without it fingerprints are "
        "trivially reversible."
    )
_RETENTION_KEY: bytes = (_DAILY_SALT + ":retention").encode()

# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------
RETENTION_FILE = analytics_store.data_file("retention.json")

_today_chi = analytics_store.today_chi

_lock = asyncio.Lock()

# In-memory state — protected by _lock.
_current_day: str = ""
_daily: dict[str, dict[str, int]] = {}          # {date: {new, returning}}
_bloom_bits: bytearray = bytearray(math.ceil(BLOOM_M / 8))
_bloom_count: int = 0                            # items added to filter so far
_today_fingerprints: set[bytes] = set()          # fingerprints seen today (dedup)
_writes_since_flush: int = 0
_FLUSH_EVERY_N_WRITES = 10


# ---------------------------------------------------------------------------
# Bloom filter helpers
# ---------------------------------------------------------------------------

def _bloom_bit_positions(fingerprint: bytes) -> list[int]:
    """Return BLOOM_K bit positions for ``fingerprint`` in [0, BLOOM_M).

    Uses Kirsch–Mitzenmacher double hashing: one SHA-256 of the fingerprint is
    split into two 16-byte halves h1, h2, and the K positions are derived as
    (h1 + i*h2) mod BLOOM_M. This produces the same false-positive rate as K
    independent hashes (proven in Kirsch & Mitzenmacher 2008) at the cost of
    one SHA-256 per call instead of K (~7×) — a meaningful saving on every
    /ping where retention.record_visit fires both check and add (OPT-BE-219).
    """
    digest = hashlib.sha256(fingerprint).digest()
    h1 = int.from_bytes(digest[:16], "big")
    h2 = int.from_bytes(digest[16:], "big") | 1  # force h2 odd so it's coprime with most BLOOM_M values
    return [(h1 + i * h2) % BLOOM_M for i in range(BLOOM_K)]


def _bloom_add(bits: bytearray, fingerprint: bytes) -> None:
    for bit in _bloom_bit_positions(fingerprint):
        bits[bit >> 3] |= 1 << (bit & 7)


def _bloom_check(bits: bytearray, fingerprint: bytes) -> bool:
    return all(
        bits[bit >> 3] & (1 << (bit & 7))
        for bit in _bloom_bit_positions(fingerprint)
    )


def _new_bloom() -> bytearray:
    return bytearray(math.ceil(BLOOM_M / 8))


# ---------------------------------------------------------------------------
# Fingerprinting
# ---------------------------------------------------------------------------

def _fingerprint(raw_id: str) -> bytes:
    """Stable HMAC fingerprint for ``raw_id`` (intentionally not day-keyed)."""
    return hmac.new(_RETENTION_KEY, raw_id.encode(), hashlib.sha256).digest()


def new_return_id() -> str:
    """Cryptographically random 90-day return ID. ~32 url-safe base64 chars."""
    return secrets.token_urlsafe(24)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def _load() -> dict:
    """Load {daily, filter, filter_count} from disk, returning safe defaults."""
    raw = analytics_store.safe_load_json(RETENTION_FILE, {})
    if not isinstance(raw, dict):
        raw = {}
    daily = raw.get("daily") or {}
    if not isinstance(daily, dict):
        daily = {}
    b64 = raw.get("filter") or ""
    try:
        bits = bytearray(base64.b64decode(b64)) if b64 else _new_bloom()
        if len(bits) != math.ceil(BLOOM_M / 8):
            bits = _new_bloom()
    except Exception:
        bits = _new_bloom()
    count = int(raw.get("filter_count") or 0)
    return {"daily": daily, "bits": bits, "count": count}


def _save(daily: dict, bits: bytearray, count: int) -> None:
    analytics_store.atomic_write_json(RETENTION_FILE, {
        "daily": daily,
        "filter": base64.b64encode(bytes(bits)).decode(),
        "filter_count": count,
    })


# Initialise module state from disk at import time.
_init = _load()
_daily = _init["daily"]
_bloom_bits = _init["bits"]
_bloom_count = _init["count"]
del _init


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def record_visit(raw_id: str | None) -> str:
    """Record a visit and return the (possibly new) raw return ID.

    If ``raw_id`` is None or an empty string a fresh ID is issued.
    The returned value must be set as the ``rid`` cookie by the caller.
    """
    global _current_day, _daily, _bloom_bits, _bloom_count
    global _today_fingerprints, _writes_since_flush

    if not raw_id:
        raw_id = new_return_id()

    fp = _fingerprint(raw_id)

    async with _lock:
        today = _today_chi()
        loop = asyncio.get_running_loop()

        if today != _current_day:
            # Day rolled over — persist accumulated state then reset.
            if _current_day:
                await loop.run_in_executor(None, _save, _daily, _bloom_bits, _bloom_count)
            new_state = await loop.run_in_executor(None, _load)
            # Merge persisted data — keep both in-memory and on-disk records.
            for d, v in new_state["daily"].items():
                if d not in _daily:
                    _daily[d] = v
            _bloom_bits = new_state["bits"]
            _bloom_count = new_state["count"]
            _today_fingerprints = set()
            _current_day = today
            _writes_since_flush = 0

        # Auto-reset filter when it's full to keep FPR bounded.
        if _bloom_count >= BLOOM_CAPACITY:
            logger.warning(
                "[retention] Bloom filter at capacity (%d items). Resetting "
                "to restore FPR ≤1%%. Run check_retention.py to verify.",
                _bloom_count,
            )
            _bloom_bits = _new_bloom()
            _bloom_count = 0
            _today_fingerprints = set()

        if fp in _today_fingerprints:
            return raw_id  # same visitor, same day — already counted

        is_returning = _bloom_check(_bloom_bits, fp)

        bucket = _daily.setdefault(today, {"new": 0, "returning": 0})
        if is_returning:
            bucket["returning"] = int(bucket.get("returning", 0)) + 1
        else:
            bucket["new"] = int(bucket.get("new", 0)) + 1

        # Add to today's dedup set and to the persistent Bloom filter so
        # tomorrow's visitors can be detected as returning.
        _today_fingerprints.add(fp)
        _bloom_add(_bloom_bits, fp)
        _bloom_count += 1
        _writes_since_flush += 1

        if _writes_since_flush >= _FLUSH_EVERY_N_WRITES:
            await loop.run_in_executor(None, _save, _daily, _bloom_bits, _bloom_count)
            _writes_since_flush = 0

    return raw_id


async def get_counts() -> dict[str, dict[str, int]]:
    """Return per-day {new, returning, total, returning_pct} aggregates."""
    async with _lock:
        out: dict[str, dict[str, int]] = {}
        for date, bucket in sorted(_daily.items()):
            new = int(bucket.get("new", 0))
            ret = int(bucket.get("returning", 0))
            total = new + ret
            pct = round(100.0 * ret / total, 1) if total else 0.0
            out[date] = {
                "new": new,
                "returning": ret,
                "total": total,
                "returning_pct": pct,
            }
        return out


async def get_filter_stats() -> dict:
    """Return Bloom filter diagnostic info for the admin endpoint."""
    async with _lock:
        return {
            "capacity": BLOOM_CAPACITY,
            "count": _bloom_count,
            "utilisation_pct": round(100.0 * _bloom_count / BLOOM_CAPACITY, 1),
            "bloom_m_bits": BLOOM_M,
            "bloom_k_hashes": BLOOM_K,
            "fpr_at_capacity_pct": round(_BLOOM_FPR * 100, 1),
        }


async def force_flush_for_test() -> None:
    """Test helper: persist current in-memory state to disk."""
    async with _lock:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _save, _daily, _bloom_bits, _bloom_count)
