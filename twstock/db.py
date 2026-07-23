# -*- coding: utf-8 -*-
"""Single, package-qualified entry point for SQLite connections."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

_PROJECT_DIR = Path(__file__).resolve().parent
_DEFAULT_DB_PATH = _PROJECT_DIR / "taiwan_stock_unified.db"

# The environment override makes isolated CLI/test runs possible without
# monkeypatching a second, top-level ``db`` module.  Normal users keep the
# project-local database path unchanged.
DB_PATH = os.environ.get("TWSTOCK_DB_PATH", str(_DEFAULT_DB_PATH))


def get_connection(readonly: bool = False) -> sqlite3.Connection:
    """Open the configured SQLite database with consistent safety settings.

    Read-only connections use SQLite's URI mode and never enable WAL.  Write
    connections keep WAL for concurrent readers and use a bounded busy timeout.
    """
    if readonly:
        database_uri = Path(DB_PATH).resolve().as_uri() + "?mode=ro"
        connection = sqlite3.connect(database_uri, uri=True, timeout=10)
    else:
        connection = sqlite3.connect(DB_PATH, timeout=10)
        connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA busy_timeout=5000")
    connection.row_factory = sqlite3.Row
    return connection


def get_path() -> str:
    """Return the absolute path to the active database file."""
    return str(Path(DB_PATH).resolve())


def file_size_mb() -> float:
    """Return the active database file size in MiB, or zero when absent."""
    database_path = Path(DB_PATH)
    return database_path.stat().st_size / (1024 * 1024) if database_path.exists() else 0.0
