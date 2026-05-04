"""
Shared persistence helpers for the daily-aggregate analytics counters
(``dau``, ``devices``, ``geography``, ``hourly``, ``referrers``, ``sessions``).

Each counter writes a single JSON file under ``backend/data/`` (or
``/app/data/`` in production). They all share the same shape:

  * one Chicago-day key per top-level dict entry
  * an in-memory mirror that takes the disk write off the request hot path
  * a batched flush that persists every N writes
  * an atomic temp-file write so a crash mid-flush never truncates the file

This module owns those four pieces so a fix to (e.g.) the temp-file cleanup
branch is made once instead of in six modules. Counter-specific logic (how
to bucket a UA, how to roll up cities into a metro, etc.) stays in the
counter modules — this module is *only* the persistence skeleton.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from utils import CHICAGO_TZ


def today_chi() -> str:
    """Today's date in Chicago timezone, formatted as YYYY-MM-DD."""
    return datetime.now(CHICAGO_TZ).strftime("%Y-%m-%d")


def data_file(filename: str) -> Path:
    """Resolve a counter's on-disk JSON path, honouring APP_ENV=production.

    In production the persistent volume is mounted at ``/app/data``; in dev
    we write under ``backend/data/`` next to the module. The parent dir is
    created on first call so callers don't have to.
    """
    if os.getenv("APP_ENV") == "production":
        path = Path("/app/data") / filename
    else:
        # Counter modules live in ``backend/`` so the dev path is sibling to them.
        path = Path(__file__).parent / "data" / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def safe_load_json(path: Path, default: Any) -> Any:
    """Load JSON from ``path``, returning ``default`` on missing or corrupt files.

    The counter modules all accept the same two failure modes silently —
    ``FileNotFoundError`` (first run, fresh volume) and ``json.JSONDecodeError``
    (truncated write from before atomic-replace was added). Returning the
    default rather than re-raising keeps server startup robust.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default
    # Counters always serialize a top-level dict; coerce defensively in case a
    # historical record was written with a different shape.
    if isinstance(default, dict) and not isinstance(data, dict):
        return default
    return data


def atomic_write_json(path: Path, data: Any) -> None:
    """Write ``data`` to ``path`` atomically via tempfile + os.replace.

    A crash mid-write leaves the original file intact instead of producing a
    half-truncated JSON blob. The fdopen branch matters: if ``os.fdopen``
    raises (e.g. EBADF after the fd has been moved), we still need to close
    the raw fd before unlinking the tempfile to avoid leaking it on Windows.
    """
    tmp_fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    fdopen_ok = False
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            fdopen_ok = True
            json.dump(data, f)
        os.replace(tmp_path, path)
    except Exception:
        if not fdopen_ok:
            os.close(tmp_fd)
        # best-effort: tmp_path may already be gone on certain replace failures.
        try:
            os.unlink(tmp_path)
        except FileNotFoundError:
            pass
        raise


