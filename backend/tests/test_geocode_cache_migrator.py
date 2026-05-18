"""
Tests for backend/scripts/migrate_geocode_cache.py.

The migrator is a one-shot, but the tests exercise it like a library function
(via `migrate(...)` with explicit paths) so they can use tmp_path fixtures
and never touch the real backend/geocode_cache.json on disk.

Covers:
  - Positive + negative entries land in cached_forward correctly.
  - Raw query keys are re-normalized through `_normalize_street_abbr` +
    lowercase + strip, matching what `geocode_external` keys cached_forward by.
  - Journal entries replay on top of the snapshot (last-write-wins).
  - Malformed journal lines are skipped, not fatal.
  - The marker file is written and prevents a second run without --force.
  - --force allows a re-run.
  - --dry-run reports counts but doesn't write the DB or marker.
  - --cleanup deletes the four legacy on-disk files.
  - Synthetic timestamps fall inside the bounded window [1d, 60d] old.
"""
from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
import time
from pathlib import Path

import pytest


_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


def _load(name: str):
    """Load a script module by file path; works whether or not scripts/ is a package."""
    path = _SCRIPTS_DIR / f"{name}.py"
    backend_dir = _SCRIPTS_DIR.parent
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))
    spec = importlib.util.spec_from_file_location(f"_{name}_under_test", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def migrator():
    return _load("migrate_geocode_cache")


@pytest.fixture
def db_path(tmp_path: Path, migrator) -> Path:
    """Build an empty cached_forward-bearing DB at a temp path."""
    from scripts._geocode_db import connect
    p = tmp_path / "chicago_geocode.db"
    conn = connect(p)
    conn.close()
    return p


@pytest.fixture
def empty_workspace(tmp_path: Path, db_path: Path) -> dict:
    """Bundle of tmp paths the migrator's `migrate()` accepts as kwargs."""
    return {
        "snapshot_path": tmp_path / "geocode_cache.json",
        "journal_path":  tmp_path / "geocode_cache.journal",
        "ages_path":     tmp_path / "geocode_cache_ages.json",
        "db_path":       db_path,
        "marker_path":   tmp_path / ".geocode_cache_migrated",
    }


def _cached_forward_rows(db_path: Path) -> list[tuple]:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(
            "SELECT query, lat, lon, source, fetched_at FROM cached_forward "
            "ORDER BY query"
        ).fetchall()
    finally:
        conn.close()


# ── Core migration paths ────────────────────────────────────────────────────

class TestMigrate:
    def test_positive_and_negative_entries_land_correctly(self, migrator, empty_workspace):
        snapshot = {
            "5704 N Artesian Ave": [41.9851504, -87.6910118],
            "wriglevile": None,  # legacy negative
        }
        empty_workspace["snapshot_path"].write_text(json.dumps(snapshot), encoding="utf-8")

        summary = migrator.migrate(**empty_workspace)
        rows = _cached_forward_rows(empty_workspace["db_path"])

        assert summary["inserted_positive"] == 1
        assert summary["inserted_negative"] == 1
        assert summary["rows_written"] == 2

        by_key = {r[0]: r for r in rows}
        # `_normalize_street_abbr` expands `Ave` -> `avenue`; lowercased + stripped.
        positive = by_key["5704 n artesian avenue"]
        assert positive[1] == pytest.approx(41.9851504)
        assert positive[2] == pytest.approx(-87.6910118)
        assert positive[3] == "migrate"

        negative = by_key["wriglevile"]
        assert negative[1] is None and negative[2] is None
        assert negative[3] == "migrate"

    def test_journal_replays_after_snapshot_last_write_wins(self, migrator, empty_workspace):
        empty_workspace["snapshot_path"].write_text(
            json.dumps({"foo": [40.0, -85.0]}), encoding="utf-8",
        )
        # Two journal entries: one updates `foo` to a different coord; one adds `bar`.
        empty_workspace["journal_path"].write_text(
            '["foo", [41.5, -87.5]]\n'
            '["bar", [41.9, -87.6]]\n',
            encoding="utf-8",
        )

        migrator.migrate(**empty_workspace)
        rows = {r[0]: (r[1], r[2]) for r in _cached_forward_rows(empty_workspace["db_path"])}

        # Journal wins for `foo`.
        assert rows["foo"] == pytest.approx((41.5, -87.5))
        assert rows["bar"] == pytest.approx((41.9, -87.6))

    def test_malformed_journal_lines_are_skipped(self, migrator, empty_workspace):
        empty_workspace["snapshot_path"].write_text("{}", encoding="utf-8")
        empty_workspace["journal_path"].write_text(
            '["ok", [41.0, -87.0]]\n'
            'not json at all\n'
            '["wrong shape only one"]\n'
            '\n'  # blank line — silently skipped, not counted as malformed
            '["another ok", [41.1, -87.1]]\n',
            encoding="utf-8",
        )

        summary = migrator.migrate(**empty_workspace)
        assert summary["journal_replayed"] == 2
        assert summary["journal_skipped"] == 2
        rows = {r[0]: (r[1], r[2]) for r in _cached_forward_rows(empty_workspace["db_path"])}
        assert "ok" in rows
        assert "another ok" in rows


# ── Run-once / force / dry-run ──────────────────────────────────────────────

class TestRunOnceSafety:
    def test_marker_blocks_second_run(self, migrator, empty_workspace):
        empty_workspace["snapshot_path"].write_text("{}", encoding="utf-8")
        migrator.migrate(**empty_workspace)
        assert empty_workspace["marker_path"].exists()
        with pytest.raises(SystemExit):
            migrator.migrate(**empty_workspace)

    def test_force_allows_re_run(self, migrator, empty_workspace):
        empty_workspace["snapshot_path"].write_text(
            json.dumps({"foo": [41.0, -87.0]}), encoding="utf-8",
        )
        migrator.migrate(**empty_workspace)
        # Second run with --force, with a different value.
        empty_workspace["snapshot_path"].write_text(
            json.dumps({"foo": [42.0, -88.0]}), encoding="utf-8",
        )
        migrator.migrate(force=True, **empty_workspace)
        rows = {r[0]: (r[1], r[2]) for r in _cached_forward_rows(empty_workspace["db_path"])}
        assert rows["foo"] == pytest.approx((42.0, -88.0))

    def test_dry_run_writes_nothing(self, migrator, empty_workspace):
        empty_workspace["snapshot_path"].write_text(
            json.dumps({"foo": [41.0, -87.0]}), encoding="utf-8",
        )
        summary = migrator.migrate(dry_run=True, **empty_workspace)
        assert summary["dry_run"] is True
        assert summary["rows_written"] == 0
        assert summary["inserted_positive"] == 1
        assert not empty_workspace["marker_path"].exists()
        assert _cached_forward_rows(empty_workspace["db_path"]) == []


# ── Synthetic timestamps ────────────────────────────────────────────────────

class TestSyntheticTimestamps:
    def test_clamps_to_one_to_sixty_days_old(self, migrator, empty_workspace):
        now = 1_700_000_000  # fixed clock
        empty_workspace["snapshot_path"].write_text(
            json.dumps({
                "very-old":   [41.0, -87.0],
                "very-fresh": [41.1, -87.1],
                "moderate":   [41.2, -87.2],
            }),
            encoding="utf-8",
        )
        empty_workspace["ages_path"].write_text(
            json.dumps({
                "very-old":   now - 365 * 86_400,   # ~1 year old
                "very-fresh": now - 60,              # 1 minute old
                "moderate":   now - 10 * 86_400,    # 10 days old
            }),
            encoding="utf-8",
        )

        migrator.migrate(now=now, **empty_workspace)
        rows = {r[0]: r[4] for r in _cached_forward_rows(empty_workspace["db_path"])}

        # Bounds: at least 1 day old, at most 60 days old.
        for ts in rows.values():
            age = now - ts
            assert 1 * 86_400 <= age <= 60 * 86_400

        # The "moderate" age (10 days) should be preserved exactly.
        assert rows["moderate"] == now - 10 * 86_400
        # The 1-year-old entry should be clamped to 60 days.
        assert rows["very-old"] == now - 60 * 86_400
        # The 1-minute-old entry should be clamped to 1 day.
        assert rows["very-fresh"] == now - 1 * 86_400

    def test_missing_ages_default_to_thirty_days(self, migrator, empty_workspace):
        now = 1_700_000_000
        empty_workspace["snapshot_path"].write_text(
            json.dumps({"key-without-age": [41.0, -87.0]}), encoding="utf-8",
        )
        # No ages_path written.
        migrator.migrate(now=now, **empty_workspace)
        rows = _cached_forward_rows(empty_workspace["db_path"])
        assert rows[0][4] == now - 30 * 86_400


# ── Cleanup ─────────────────────────────────────────────────────────────────

class TestCleanup:
    def test_cleanup_via_cli_deletes_legacy_files(self, migrator, tmp_path, db_path):
        snapshot = tmp_path / "geocode_cache.json"
        journal  = tmp_path / "geocode_cache.journal"
        ages     = tmp_path / "geocode_cache_ages.json"
        counter  = tmp_path / "geocode_counter.json"
        marker   = tmp_path / ".geocode_cache_migrated"
        for p in (snapshot, journal, ages, counter):
            p.write_text("{}", encoding="utf-8")

        # Drive via the public CLI entry so we exercise the --cleanup branch.
        rc = migrator._main([
            "--snapshot", str(snapshot),
            "--journal",  str(journal),
            "--ages",     str(ages),
            "--counter",  str(counter),
            "--db",       str(db_path),
            "--marker",   str(marker),
            "--cleanup",
        ])
        assert rc == 0
        for p in (snapshot, journal, ages, counter):
            assert not p.exists(), f"{p} should have been deleted"
        # Marker survives cleanup so a future accidental --force is the only
        # way to re-run.
        assert marker.exists()

    def test_cleanup_with_dry_run_is_a_no_op(self, migrator, tmp_path, db_path):
        snapshot = tmp_path / "geocode_cache.json"
        snapshot.write_text("{}", encoding="utf-8")
        marker = tmp_path / ".geocode_cache_migrated"

        migrator._main([
            "--snapshot", str(snapshot),
            "--journal",  str(tmp_path / "geocode_cache.journal"),
            "--ages",     str(tmp_path / "geocode_cache_ages.json"),
            "--counter",  str(tmp_path / "geocode_counter.json"),
            "--db",       str(db_path),
            "--marker",   str(marker),
            "--cleanup",
            "--dry-run",
        ])
        # Dry-run skips cleanup.
        assert snapshot.exists()
        assert not marker.exists()


# ── Canonicalization edge cases ─────────────────────────────────────────────

class TestCanonicalization:
    def test_collisions_collapse_to_one_row(self, migrator, empty_workspace):
        # Three raw forms of the same address.
        empty_workspace["snapshot_path"].write_text(
            json.dumps({
                "1131 W Winona St":      [41.9746581, -87.658952],
                "1131 w winona street":  [41.9750787, -87.6589633],
                "  1131 W WINONA ST  ":  [41.9760, -87.6580],   # leading/trailing space + caps
            }),
            encoding="utf-8",
        )
        summary = migrator.migrate(**empty_workspace)
        rows = _cached_forward_rows(empty_workspace["db_path"])
        # All three normalize to "1131 w winona street" → one row, last wins.
        assert len(rows) == 1
        assert rows[0][0] == "1131 w winona street"
        # The third (last-iterated) entry wins.
        assert rows[0][1] == pytest.approx(41.9760)
        assert rows[0][2] == pytest.approx(-87.6580)
        assert summary["canonical_collisions"] == 2

    def test_empty_canonical_key_is_dropped(self, migrator, empty_workspace):
        empty_workspace["snapshot_path"].write_text(
            json.dumps({
                "": [41.0, -87.0],
                "   ": [41.0, -87.0],
                "real": [41.0, -87.0],
            }),
            encoding="utf-8",
        )
        summary = migrator.migrate(**empty_workspace)
        assert summary["malformed"] == 2
        rows = _cached_forward_rows(empty_workspace["db_path"])
        assert [r[0] for r in rows] == ["real"]


# ── Missing-DB guard ────────────────────────────────────────────────────────

def test_missing_target_db_exits_cleanly(migrator, tmp_path):
    snapshot = tmp_path / "geocode_cache.json"
    snapshot.write_text("{}", encoding="utf-8")
    with pytest.raises(SystemExit):
        migrator.migrate(
            snapshot_path=snapshot,
            journal_path=tmp_path / "geocode_cache.journal",
            ages_path=tmp_path / "geocode_cache_ages.json",
            db_path=tmp_path / "does_not_exist.db",
            marker_path=tmp_path / ".geocode_cache_migrated",
        )
