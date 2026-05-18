"""
One-shot migrator for the legacy Google geocode cache into the SQLite
`cached_forward` table that Chunk 5 of the Geocoding & Autocomplete plan
introduced. Chunk 10 of that plan.

Source files (all gitignored, only ever existed on the maintainer's box):
    backend/geocode_cache.json         - snapshot dict: {raw_query: [lat, lon] | null}
    backend/geocode_cache.journal      - append-only JSONL delta of the same shape
    backend/geocode_cache_ages.json    - sidecar: {raw_query: float_unix_ts}
    backend/geocode_counter.json       - monthly Google API call counter (not migrated;
                                         the new cascade replaces the monthly cap with
                                         `LOCATIONIQ_DAILY_CAP` + per-row negative-cache)

Target:
    backend/static_data/chicago_geocode.db -> cached_forward(query, lat, lon, source, fetched_at)

Why this exists:
    The old Google forward geocoder stored its hits in flat JSON on disk
    (`geocode_cache.json` + journal + ages sidecar). Chunk 5 retired both the
    reader code AND the writer code in one swing; the on-disk files were
    deliberately left in place so this migrator could fold them into the
    SQLite store one last time. Without the migration, every formerly-cached
    query that's not already in the local OSM corpus would hit LocationIQ on
    its next encounter — wasted budget against the 4 900/day cap.

What the migrator does:
    1.  Refuse to run if `.geocode_cache_migrated` marker exists (unless --force).
    2.  Load the snapshot (handle missing file or empty snapshot gracefully).
    3.  Replay the journal line-by-line on top of the snapshot — preserves the
        legacy reader's "last write wins" semantics. Skips torn / corrupt lines
        with a warning rather than aborting.
    4.  Load the ages sidecar if present (used as the fetched_at source for each
        row that has one; falls back to a synthetic 30-days-ago timestamp).
    5.  Re-normalize each raw key through `_normalize_street_abbr(key.lower().strip())`
        so the migrated rows match what the new `geocode_external` cache layer
        keys by (it stores `_normalize_street_abbr(query.strip().lower())`).
        Multiple raw keys can collapse onto a single canonical key — the later
        replay wins via `INSERT OR REPLACE`, mirroring legacy semantics.
    6.  Insert positive hits as `(lat, lon)` rows; insert negatives as NULL-coord
        rows (the NEG_HIT sentinel honored by `_cache_get_forward`).
    7.  Bounded synthetic timestamps: clamp to >= 1 day old and <= 60 days old
        so the startup TTL eviction sweep (added in `geocoding.evict_cache_older_than`,
        default 90 days via `LOCATIONIQ_CACHE_TTL_DAYS`) does not immediately
        wipe the migrated rows AND does not preserve them indefinitely (the
        lower bound also prevents a "fresh" classification that would defeat
        any "freshness boost" the cache might gain later).
    8.  Write the marker file.
    9.  If --cleanup is passed, delete the legacy on-disk files.

Run:
    python -m backend.scripts.migrate_geocode_cache             # migrate only
    python -m backend.scripts.migrate_geocode_cache --cleanup   # migrate + delete legacy files
    python -m backend.scripts.migrate_geocode_cache --force     # ignore the marker and re-run
    python -m backend.scripts.migrate_geocode_cache --dry-run   # parse + report; no DB writes, no cleanup
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

# Make `from geocode_text import ...` resolvable when this module is run as
# a script (`python -m backend.scripts.migrate_geocode_cache`) or imported
# by tests via spec_from_file_location.
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from geocode_text import _normalize_street_abbr  # noqa: E402


# Default on-disk locations. All overridable via CLI flags so tests can point
# the migrator at temp directories.
DEFAULT_SNAPSHOT = _BACKEND_DIR / "geocode_cache.json"
DEFAULT_JOURNAL  = _BACKEND_DIR / "geocode_cache.journal"
DEFAULT_AGES     = _BACKEND_DIR / "geocode_cache_ages.json"
DEFAULT_COUNTER  = _BACKEND_DIR / "geocode_counter.json"
DEFAULT_DB       = _BACKEND_DIR / "static_data" / "chicago_geocode.db"
DEFAULT_MARKER   = _BACKEND_DIR / ".geocode_cache_migrated"

# Synthetic-timestamp bounds (seconds). See module docstring step 7.
_MIN_SYNTHETIC_AGE_S: int = 1 * 86_400    # 1 day
_MAX_SYNTHETIC_AGE_S: int = 60 * 86_400   # 60 days


# ── Parsing helpers ─────────────────────────────────────────────────────────

def _canonicalize(raw: str) -> str:
    """Mirror what `geocode_external` keys `cached_forward` by.

    `geocoding._resolve_inner` passes `_normalize_street_abbr(query.strip().lower())`
    down to `geocode_external`, which uses that string as the `cached_forward.query`
    PRIMARY KEY. Migrating to the same canonical form ensures a hit.
    """
    return _normalize_street_abbr((raw or "").strip().lower())


def _coerce_coords(raw_value) -> "tuple[float, float] | None":
    """Coerce a snapshot/journal value into (lat, lon) or None.

    Legacy snapshot rows are either `null` (negative cache hit) or a 2-element
    list `[lat, lon]`. The journal rows use the same shape. Anything else is
    discarded as malformed."""
    if raw_value is None:
        return None
    if isinstance(raw_value, (list, tuple)) and len(raw_value) == 2:
        try:
            return float(raw_value[0]), float(raw_value[1])
        except (TypeError, ValueError):
            return "INVALID"  # type: ignore[return-value]
    return "INVALID"  # type: ignore[return-value]


def load_legacy_cache(
    snapshot_path: Path,
    journal_path: Path,
) -> "tuple[dict, int, int]":
    """Replay snapshot + journal into a single dict.

    Returns (cache, journal_replayed, journal_skipped). The cache value is
    the raw value from the legacy file (None for negatives; [lat, lon] for
    positives; the marker `"INVALID"` for malformed entries the caller
    should drop).
    """
    cache: dict[str, object] = {}
    if snapshot_path.exists():
        try:
            cache = json.loads(snapshot_path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(
                f"[migrate] snapshot {snapshot_path} unreadable; treating as "
                f"empty: {exc}", file=sys.stderr,
            )
            cache = {}

    replayed = 0
    skipped = 0
    if journal_path.exists():
        with journal_path.open("r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    pair = json.loads(line)
                    if not (isinstance(pair, list) and len(pair) == 2):
                        raise ValueError("not a 2-element list")
                    key, value = pair
                    if not isinstance(key, str):
                        raise ValueError("non-string key")
                    cache[key] = value
                    replayed += 1
                except Exception as exc:
                    skipped += 1
                    print(
                        f"[migrate] journal line {line_no} skipped: {exc}",
                        file=sys.stderr,
                    )
    return cache, replayed, skipped


def load_ages(ages_path: Path) -> "dict[str, float]":
    if not ages_path.exists():
        return {}
    try:
        raw = json.loads(ages_path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            return {str(k): float(v) for k, v in raw.items() if isinstance(v, (int, float))}
    except Exception as exc:
        print(f"[migrate] ages {ages_path} unreadable; ignoring: {exc}", file=sys.stderr)
    return {}


def _synthetic_fetched_at(raw_key: str, ages: "dict[str, float]", now: int) -> int:
    """Return a bounded `fetched_at` timestamp for one migrated row.

    Preserves the recorded age when one exists; otherwise synthesizes a
    "moderately old" timestamp 30 days back. Then clamps to
    [_MIN_SYNTHETIC_AGE_S, _MAX_SYNTHETIC_AGE_S] seconds old so the row sits
    well inside the configured TTL window (default 90 days via
    `LOCATIONIQ_CACHE_TTL_DAYS`) while not appearing brand-new.
    """
    recorded = ages.get(raw_key)
    if recorded is not None and recorded > 0:
        candidate = int(recorded)
    else:
        candidate = now - 30 * 86_400
    age_s = now - candidate
    if age_s < _MIN_SYNTHETIC_AGE_S:
        return now - _MIN_SYNTHETIC_AGE_S
    if age_s > _MAX_SYNTHETIC_AGE_S:
        return now - _MAX_SYNTHETIC_AGE_S
    return candidate


# ── Main migrate routine ────────────────────────────────────────────────────

def migrate(
    *,
    snapshot_path: Path = DEFAULT_SNAPSHOT,
    journal_path: Path = DEFAULT_JOURNAL,
    ages_path: Path = DEFAULT_AGES,
    db_path: Path = DEFAULT_DB,
    marker_path: Path = DEFAULT_MARKER,
    force: bool = False,
    dry_run: bool = False,
    now: "int | None" = None,
) -> dict:
    """Run the migration. Returns a summary dict suitable for tests + CLI."""
    if marker_path.exists() and not force:
        raise SystemExit(
            f"Migration already ran ({marker_path} exists). Pass --force to re-run."
        )
    if not db_path.exists():
        raise SystemExit(
            f"Target DB not found at {db_path}. Run "
            "`python -m backend.scripts._geocode_db --init` first."
        )

    now = now if now is not None else int(time.time())
    cache, journal_replayed, journal_skipped = load_legacy_cache(snapshot_path, journal_path)
    ages = load_ages(ages_path)

    inserted_positive = 0
    inserted_negative = 0
    malformed = 0
    canonical_collisions = 0

    seen_canonical: set[str] = set()

    # Order: dict iteration is insertion order, so snapshot rows come first,
    # then journal rows clobber where keys overlap — preserving the legacy
    # "journal wins" replay semantics.
    rows: list[tuple] = []
    for raw_key, raw_value in cache.items():
        coords = _coerce_coords(raw_value)
        if coords == "INVALID":
            malformed += 1
            continue
        canonical = _canonicalize(raw_key)
        if not canonical:
            malformed += 1
            continue
        if canonical in seen_canonical:
            canonical_collisions += 1
        seen_canonical.add(canonical)
        fetched_at = _synthetic_fetched_at(raw_key, ages, now)
        if coords is None:
            inserted_negative += 1
            rows.append((canonical, None, None, "migrate", fetched_at))
        else:
            inserted_positive += 1
            lat, lon = coords
            rows.append((canonical, lat, lon, "migrate", fetched_at))

    if not dry_run:
        # Use the schema-applying connect() helper so a missing-table state on
        # a half-built DB still works.
        from scripts._geocode_db import connect as _connect_db  # noqa: PLC0415
        conn = _connect_db(db_path)
        try:
            with conn:
                conn.executemany(
                    "INSERT OR REPLACE INTO cached_forward "
                    "(query, lat, lon, source, fetched_at) VALUES (?, ?, ?, ?, ?)",
                    rows,
                )
        finally:
            conn.close()
        marker_path.write_text(
            f"migrated {len(rows)} rows at {now} (Unix epoch)\n",
            encoding="utf-8",
        )

    return {
        "snapshot_keys": len(cache),
        "journal_replayed": journal_replayed,
        "journal_skipped": journal_skipped,
        "inserted_positive": inserted_positive,
        "inserted_negative": inserted_negative,
        "malformed": malformed,
        "canonical_collisions": canonical_collisions,
        "ages_known": len(ages),
        "rows_written": 0 if dry_run else len(rows),
        "dry_run": dry_run,
    }


def cleanup_legacy_files(paths: "list[Path]") -> list[Path]:
    """Delete legacy on-disk files; return list of paths actually deleted."""
    deleted: list[Path] = []
    for p in paths:
        try:
            if p.exists():
                p.unlink()
                deleted.append(p)
        except OSError as exc:
            print(f"[migrate] could not delete {p}: {exc}", file=sys.stderr)
    return deleted


# ── CLI ─────────────────────────────────────────────────────────────────────

def _main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Migrate the legacy Google geocode cache (geocode_cache.json + "
            "journal + ages) into the new SQLite cached_forward table. "
            "Chunk 10 of the Geocoding & Autocomplete plan."
        ),
    )
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument("--journal",  type=Path, default=DEFAULT_JOURNAL)
    parser.add_argument("--ages",     type=Path, default=DEFAULT_AGES)
    parser.add_argument("--db",       type=Path, default=DEFAULT_DB)
    parser.add_argument("--marker",   type=Path, default=DEFAULT_MARKER)
    parser.add_argument("--counter",  type=Path, default=DEFAULT_COUNTER,
                        help="Only used by --cleanup; not migrated (counter is retired).")
    parser.add_argument("--force",   action="store_true",
                        help="Re-run even if the marker file exists.")
    parser.add_argument("--cleanup", action="store_true",
                        help="After a successful migration, delete the four legacy on-disk files.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Parse and report; do not touch the DB or write the marker.")
    args = parser.parse_args(argv)

    summary = migrate(
        snapshot_path=args.snapshot,
        journal_path=args.journal,
        ages_path=args.ages,
        db_path=args.db,
        marker_path=args.marker,
        force=args.force,
        dry_run=args.dry_run,
    )

    print(
        "[migrate] snapshot_keys={snapshot_keys} "
        "journal_replayed={journal_replayed} journal_skipped={journal_skipped} "
        "ages_known={ages_known} "
        "positives={inserted_positive} negatives={inserted_negative} "
        "malformed={malformed} canonical_collisions={canonical_collisions} "
        "rows_written={rows_written} dry_run={dry_run}".format(**summary)
    )

    if args.cleanup and not args.dry_run:
        deleted = cleanup_legacy_files(
            [args.snapshot, args.journal, args.ages, args.counter]
        )
        if deleted:
            print("[migrate] deleted legacy files:")
            for p in deleted:
                print(f"  - {p}")
        else:
            print("[migrate] no legacy files to delete.")
    elif not args.dry_run:
        print(
            "[migrate] migration complete. "
            "Re-run with --cleanup once you've spot-checked the result to "
            "delete the legacy on-disk files."
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
