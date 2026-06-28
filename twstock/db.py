# -*- coding: utf-8 -*-
# [AI MOD]
"""
Single entry point for database connections.
All modules must retrieve database connections from this module instead of defining DB_PATH independently.
"""
import sqlite3
import os
from pathlib import Path

_DIR = Path(__file__).resolve().parent
DB_PATH = str(_DIR / "taiwan_stock_unified.db")


def get_connection(readonly: bool = False) -> sqlite3.Connection:
    """
    Unified database connection factory.

    Args:
        readonly: If True, opens connection in read-only (ro) immutable mode for safety.
    Returns:
        sqlite3.Connection with Row row_factory configured.
    """
    if readonly:
        uri = f"file:{DB_PATH}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=10)
    else:
        conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.row_factory = sqlite3.Row
    return conn


def get_path() -> str:
    """
    Returns the absolute path to the unified database file.
    Useful for checking file existence or size.
    """
    return DB_PATH


def file_size_mb() -> float:
    """
    Returns the file size of the unified database in Megabytes.
    """
    return os.path.getsize(DB_PATH) / (1024 * 1024) if os.path.exists(DB_PATH) else 0.0
