# -*- coding: utf-8 -*-
"""
tests/conftest.py — 共享測試夾具

提供：
- temp_db_path: 臨時 DB 檔案路徑
- db_conn: 已連線到臨時 DB 的 Connection
- patch_db_path: 讓 db.py 指向臨時 DB 的 monkeypatch
"""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    """回傳測試用的臨時 DB 檔案路徑。"""
    return tmp_path / "test_twstock.db"


@pytest.fixture
def db_conn(temp_db_path: Path) -> Iterator[sqlite3.Connection]:
    """建立一個指向臨時 DB 的連線，測試結束後自動關閉。"""
    # [FIX] 移除無效的 os.environ["TWSTOCK_DB_PATH"] 設定 — db.py 不讀此 env var
    # DB_PATH 導向由 patch_db_path fixture 處理（monkeypatch.setattr）
    conn = sqlite3.connect(str(temp_db_path))
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


@pytest.fixture
def patch_db_path(monkeypatch, temp_db_path: Path) -> Path:
    """Monkeypatch db.py 的 DB_PATH，讓它指向臨時 DB。"""
    import twstock.db as db_module

    monkeypatch.setattr(db_module, "DB_PATH", str(temp_db_path))
    os.environ["TWSTOCK_DB_PATH"] = str(temp_db_path)
    return temp_db_path
