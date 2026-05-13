"""
Shared SQLite schema + helper for backend/static_data/chicago_geocode.db.

The database holds four tables used by the local-first geocoder cascade:

  addresses        Every Chicago street address from OSM Overpass.
                   Searched via addresses_fts (FTS5) for autocomplete.

  intersections    Cross-streets derived from the pedestrian/street graph.
                   One row per node where two or more named streets meet.
                   Searched via intersections_fts (FTS5).

  cached_forward   Runtime LocationIQ hits (positive + negative). Initially
                   seeded from the legacy `backend/geocode_cache.json` by a
                   one-shot run of `migrate_geocode_cache.py` (Chunk 10).

  cached_reverse   Runtime LocationIQ reverse hits. Same one-shot seed
                   path as cached_forward.

Where this file lives matters: the DB MUST be under `backend/static_data/`,
not `backend/data/`. Railway overlays `backend/data/` with the persistent
analytics volume at runtime, which would destroy the corpus on every deploy.
`backend/static_data/` is the repo's convention for committed/built fixtures
that survive deploys; the DB itself is gitignored (large derived artifact),
but its location convention is shared with `neighborhoods.json` and the like.

Each ingestion script (`build_intersections.py`, `build_address_points.py`,
`migrate_geocode_cache.py` — all forthcoming chunks) imports `connect()`
from this module, which opens the DB and applies the schema idempotently.
Scripts can run in any order, independently.

Read-only mmap'd reads (local_search, Chunk 4) and WAL writes for the
runtime cache (geocoding, Chunk 5) each open their own connection variants
to the same file — see those modules for the consumer-specific patterns.
This module owns only the schema and the schema-applying writeable connect.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

# Make `from geocode_text import ...` resolvable when this module is run as a
# script (`python -m backend.scripts._geocode_db`) or imported by sibling
# build scripts. backend/ is the parent of scripts/.
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

# Re-exported so the forthcoming build scripts can import normalize helpers
# from `scripts._geocode_db` without each one re-establishing the sys.path
# dance above.
from geocode_text import normalize_address, normalize_street_name  # noqa: F401, E402

DB_PATH: Path = _BACKEND_DIR / "static_data" / "chicago_geocode.db"

# Plain (non-content-linked) FTS5 tables so each ingestion script can write
# to its base table and the FTS shadow in a single transaction without
# trigger maintenance. The duplicated `normalized` text adds a few MB but
# keeps the build scripts trivially correct.
_SCHEMA = """
CREATE TABLE IF NOT EXISTS addresses (
    id          INTEGER PRIMARY KEY,
    normalized  TEXT    NOT NULL,
    raw         TEXT    NOT NULL,
    lat         REAL    NOT NULL,
    lon         REAL    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_addresses_normalized ON addresses(normalized);

CREATE VIRTUAL TABLE IF NOT EXISTS addresses_fts USING fts5(
    normalized, tokenize='unicode61'
);

CREATE TABLE IF NOT EXISTS intersections (
    id      INTEGER PRIMARY KEY,
    name_a  TEXT    NOT NULL,
    name_b  TEXT    NOT NULL,
    raw_a   TEXT    NOT NULL,
    raw_b   TEXT    NOT NULL,
    lat     REAL    NOT NULL,
    lon     REAL    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_intersections_ab ON intersections(name_a, name_b);

CREATE VIRTUAL TABLE IF NOT EXISTS intersections_fts USING fts5(
    name_a, name_b, tokenize='unicode61'
);

CREATE TABLE IF NOT EXISTS cached_forward (
    query       TEXT    PRIMARY KEY,
    lat         REAL,
    lon         REAL,
    source      TEXT    NOT NULL,
    fetched_at  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS cached_reverse (
    lat_q       INTEGER NOT NULL,
    lon_q       INTEGER NOT NULL,
    label       TEXT    NOT NULL,
    source      TEXT    NOT NULL,
    fetched_at  INTEGER NOT NULL,
    PRIMARY KEY (lat_q, lon_q)
);
"""


def connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Open the geocode DB, apply the schema idempotently, return the connection.

    Used by ingest scripts and tests. The runtime read-only and WAL-write
    connections live in their respective consumer modules — see this file's
    module docstring."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(_SCHEMA)
    conn.commit()
    return conn


def _main() -> int:
    parser = argparse.ArgumentParser(description="Initialize the geocode SQLite store.")
    parser.add_argument(
        "--init",
        action="store_true",
        help="Create an empty DB at the default path and apply the schema.",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DB_PATH,
        help=f"Override the DB path (default: {DB_PATH}).",
    )
    args = parser.parse_args()

    if not args.init:
        parser.print_help()
        return 0

    conn = connect(args.db)
    # Verify FTS5 is actually compiled into this SQLite build by running a
    # trivial query against one of the virtual tables. A missing FTS5
    # capability surfaces here as a clean OperationalError rather than at
    # ingest time deep inside a transaction.
    conn.execute("SELECT count(*) FROM addresses_fts").fetchone()
    conn.close()
    print(f"Initialized {args.db}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
