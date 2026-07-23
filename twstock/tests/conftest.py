# -*- coding: utf-8 -*-
"""Isolated SQLite fixtures shared by the test suite."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    """Return a per-test database path."""
    return tmp_path / "test_twstock.db"


@pytest.fixture
def patch_db_path(monkeypatch: pytest.MonkeyPatch, temp_db_path: Path) -> Path:
    """Point the canonical package DB module at this test's temporary file."""
    import twstock.db as db_module

    monkeypatch.setattr(db_module, "DB_PATH", str(temp_db_path))
    monkeypatch.setenv("TWSTOCK_DB_PATH", str(temp_db_path))
    return temp_db_path


@pytest.fixture
def db_conn(patch_db_path: Path) -> Iterator[sqlite3.Connection]:
    """Open the exact temporary DB used by production package code."""
    from twstock.db import get_connection

    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()
