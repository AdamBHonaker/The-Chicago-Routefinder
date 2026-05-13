"""
Schema + scaffolding tests for backend/scripts/_geocode_db.py.

Verifies the four tables + two FTS5 virtual tables exist after connect(),
that the schema is idempotent (second connect on the same file is a no-op),
that FTS5 is compiled into this Python's sqlite3 build, and that --init via
the CLI creates the file.
"""

from __future__ import annotations

import runpy
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

# scripts/ isn't a package; load _geocode_db by absolute file path so this
# test stays decoupled from sys.path setup of the script itself.
_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "_geocode_db.py"


def _load_module():
    import importlib.util

    spec = importlib.util.spec_from_file_location("_geocode_db_under_test", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def gdb(tmp_path):
    """Module loaded with an isolated DB path under tmp_path."""
    mod = _load_module()
    db_path = tmp_path / "test_geocode.db"
    return mod, db_path


class TestSchema:
    def test_fts5_is_available(self):
        """If FTS5 is not compiled in, every downstream chunk breaks. Fail loud here."""
        conn = sqlite3.connect(":memory:")
        try:
            conn.execute(
                "CREATE VIRTUAL TABLE t USING fts5(content, tokenize='unicode61')"
            )
        finally:
            conn.close()

    def test_connect_creates_db_and_all_tables(self, gdb):
        mod, db_path = gdb
        conn = mod.connect(db_path)
        try:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type IN ('table','view')"
                )
            }
        finally:
            conn.close()
        # The four base tables + the two FTS5 virtual tables (each FTS5 vtable
        # registers as a regular `table` row with the same name).
        for expected in (
            "addresses",
            "intersections",
            "cached_forward",
            "cached_reverse",
            "addresses_fts",
            "intersections_fts",
        ):
            assert expected in tables, f"missing table: {expected}"
        assert db_path.exists()

    def test_connect_is_idempotent(self, gdb):
        mod, db_path = gdb
        mod.connect(db_path).close()
        # Insert a row, reconnect, confirm the row survives (schema reapply
        # must not drop or truncate anything).
        conn = mod.connect(db_path)
        try:
            conn.execute(
                "INSERT INTO addresses(normalized, raw, lat, lon) VALUES(?,?,?,?)",
                ("1234 clark", "1234 N Clark St", 41.9, -87.65),
            )
            conn.commit()
        finally:
            conn.close()

        conn = mod.connect(db_path)
        try:
            count = conn.execute("SELECT COUNT(*) FROM addresses").fetchone()[0]
        finally:
            conn.close()
        assert count == 1

    def test_addresses_fts_accepts_inserts_and_matches(self, gdb):
        mod, db_path = gdb
        conn = mod.connect(db_path)
        try:
            conn.execute(
                "INSERT INTO addresses_fts(normalized) VALUES (?)",
                ("1234 clark",),
            )
            conn.commit()
            rows = conn.execute(
                "SELECT normalized FROM addresses_fts WHERE addresses_fts MATCH ?",
                ("clark",),
            ).fetchall()
            assert rows == [("1234 clark",)]
        finally:
            conn.close()

    def test_intersections_fts_accepts_inserts_and_matches(self, gdb):
        mod, db_path = gdb
        conn = mod.connect(db_path)
        try:
            conn.execute(
                "INSERT INTO intersections_fts(name_a, name_b) VALUES (?, ?)",
                ("damen", "milwaukee"),
            )
            conn.commit()
            rows = conn.execute(
                "SELECT name_a, name_b FROM intersections_fts WHERE intersections_fts MATCH ?",
                ("damen",),
            ).fetchall()
            assert rows == [("damen", "milwaukee")]
        finally:
            conn.close()

    def test_cached_forward_supports_null_lat_lon_for_negative_cache(self, gdb):
        """Negative-cache rows store NULL lat/lon — Chunk 5 will rely on this."""
        mod, db_path = gdb
        conn = mod.connect(db_path)
        try:
            conn.execute(
                "INSERT INTO cached_forward(query, lat, lon, source, fetched_at)"
                " VALUES (?, NULL, NULL, ?, ?)",
                ("garbage query", "neg", 0),
            )
            conn.commit()
            row = conn.execute(
                "SELECT lat, lon, source FROM cached_forward WHERE query = ?",
                ("garbage query",),
            ).fetchone()
            assert row == (None, None, "neg")
        finally:
            conn.close()

    def test_cached_reverse_primary_key_is_quantized_pair(self, gdb):
        mod, db_path = gdb
        conn = mod.connect(db_path)
        try:
            conn.execute(
                "INSERT INTO cached_reverse(lat_q, lon_q, label, source, fetched_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (4188100, -8762900, "The Loop", "neighborhood", 0),
            )
            conn.commit()
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO cached_reverse(lat_q, lon_q, label, source, fetched_at)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (4188100, -8762900, "duplicate", "neighborhood", 1),
                )
        finally:
            conn.close()


class TestInitCli:
    def test_init_cli_creates_db(self, tmp_path):
        db_path = tmp_path / "from_cli.db"
        result = subprocess.run(
            [sys.executable, str(_SCRIPT), "--init", "--db", str(db_path)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        assert db_path.exists()
        assert "Initialized" in result.stdout

    def test_no_args_prints_help_and_exits_clean(self, tmp_path):
        result = subprocess.run(
            [sys.executable, str(_SCRIPT)],
            capture_output=True,
            text=True,
            cwd=tmp_path,
        )
        assert result.returncode == 0
        assert "--init" in result.stdout
