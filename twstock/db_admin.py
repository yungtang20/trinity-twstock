#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
db_admin.py — 資料庫 schema 管理（建立表格、VIEW、migration）

注意：資料寫入已由 processor.py 統一處理。
本檔案只負責 schema 定義與初始化。
"""

import logging
import sqlite3

from twstock.db import get_connection, get_path  # Reuse the single connection entrypoint

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# Schema
# ──────────────────────────────────────────────────────────────

SCHEMA_SQL = [
    """
    CREATE TABLE IF NOT EXISTS stock_meta (
        stock_id TEXT PRIMARY KEY,
        stock_name TEXT NOT NULL,
        industry_category TEXT,
        market TEXT,
        type TEXT,
        source TEXT,
        updated_at TEXT DEFAULT (datetime('now', 'localtime'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS stock_trading_calendar (
        date TEXT PRIMARY KEY,
        is_open INTEGER NOT NULL,
        description TEXT,
        updated_at TEXT DEFAULT (datetime('now', 'localtime'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS stock_history (
        stock_id TEXT NOT NULL,
        date TEXT NOT NULL,
        open REAL NOT NULL,
        high REAL NOT NULL,
        low REAL NOT NULL,
        close REAL NOT NULL,
        volume INTEGER NOT NULL,
        amount INTEGER NOT NULL,
        trade_count INTEGER,
        spread REAL,
        source TEXT,
        updated_at TEXT DEFAULT (datetime('now', 'localtime')),
        PRIMARY KEY (stock_id, date)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS dividend_events (
        stock_id TEXT,
        date TEXT,
        before_price REAL,
        after_price REAL,
        reference_price REAL,
        cash_dividend REAL,
        stock_dividend REAL,
        source TEXT,
        updated_at TEXT DEFAULT (datetime('now', 'localtime')),
        PRIMARY KEY (stock_id, date)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS institutional_data (
        stock_id TEXT NOT NULL,
        date TEXT NOT NULL,
        foreign_net INTEGER DEFAULT 0,
        trust_net INTEGER DEFAULT 0,
        dealer_net INTEGER DEFAULT 0,
        institutional_net INTEGER DEFAULT 0,
        foreign_buy INTEGER DEFAULT 0,
        foreign_sell INTEGER DEFAULT 0,
        trust_buy INTEGER DEFAULT 0,
        trust_sell INTEGER DEFAULT 0,
        dealer_buy INTEGER DEFAULT 0,
        dealer_sell INTEGER DEFAULT 0,
        source TEXT,
        updated_at TEXT DEFAULT (datetime('now', 'localtime')),
        PRIMARY KEY (stock_id, date)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS shareholding_unified (
        stock_id TEXT NOT NULL,
        date TEXT NOT NULL,
        source TEXT NOT NULL,
        total_shares INTEGER,
        whale_ratio REAL,
        retail_ratio REAL,
        foreign_shares INTEGER,
        foreign_ratio REAL,
        total_people INTEGER,
        whale_shares INTEGER,
        whale_people INTEGER,
        updated_at TEXT DEFAULT (datetime('now', 'localtime')),
        PRIMARY KEY (stock_id, date, source)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS audit_log (
        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
        stock_id TEXT,
        action TEXT,
        status TEXT,
        detail TEXT,
        timestamp TEXT DEFAULT (datetime('now', 'localtime'))
    )
    """,
    # ── per_data ───────────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS per_data (
        stock_id TEXT NOT NULL,
        date TEXT NOT NULL,
        per REAL,
        pbr REAL,
        pe_ratio REAL,
        pb_ratio REAL,
        dividend_yield REAL,
        source TEXT,
        updated_at TEXT DEFAULT (datetime('now', 'localtime')),
        PRIMARY KEY (stock_id, date)
    )
    """,
    # ── stock_indicators ───────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS stock_indicators (
        stock_id TEXT NOT NULL,
        date TEXT NOT NULL,
        ma5 REAL,
        ma20 REAL,
        ma25 REAL,
        ma60 REAL,
        ma200 REAL,
        vol_ma5 REAL,
        vol_ma20 REAL,
        vol_ma60 REAL,
        bias_ma25 REAL,
        bias_ma60 REAL,
        bias_ma200 REAL,
        atr14 REAL,
        vwap REAL,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (stock_id, date)
    )
    """,
    # ── Indexes ────────────────────────────────────────────────────────────
    "CREATE INDEX IF NOT EXISTS idx_stock_history_stock_date ON stock_history(stock_id, date)",
    "CREATE INDEX IF NOT EXISTS idx_stock_history_date ON stock_history(date)",
    "CREATE INDEX IF NOT EXISTS idx_dividend_events_stock_date ON dividend_events(stock_id, date)",
    "CREATE INDEX IF NOT EXISTS idx_institutional_stock_date ON institutional_data(stock_id, date)",
    "CREATE INDEX IF NOT EXISTS idx_shareholding_unified_stock_date ON shareholding_unified(stock_id, date)",
    "CREATE INDEX IF NOT EXISTS idx_stock_indicators_stock_date ON stock_indicators(stock_id, date)",
]

# ---------------------------------------------------------------------------
# Views — 在 init_db 中建立
# ---------------------------------------------------------------------------

VIEWS_SQL = [
    # ── tdcc_shareholding（VIEW，非 TABLE）─────────────────────────────────
    """
    CREATE VIEW IF NOT EXISTS tdcc_shareholding AS
    SELECT stock_id, date, total_shares, whale_ratio, retail_ratio,
           source, updated_at
    FROM shareholding_unified
    WHERE source = 'tdcc'
    """,
    # Backward-compatible read-only projection for older consumers.  New code
    # must write shareholding_unified directly because source participates in
    # its primary key.
    """
    CREATE VIEW IF NOT EXISTS shareholding_data AS
    SELECT stock_id, date, foreign_shares, foreign_ratio, source, updated_at
    FROM shareholding_unified
    WHERE foreign_shares IS NOT NULL OR foreign_ratio IS NOT NULL
    """,
    # ── klines（日 K）──────────────────────────────────────────────────────
    """
    CREATE VIEW IF NOT EXISTS klines AS
    SELECT
        stock_id, date,
        open, high, low, close,
        CAST(volume AS REAL) AS volume,
        CAST(amount AS REAL) AS amount
    FROM stock_history
    """,
    # ── klines_indicators（日 K + 技術指標）───────────────────────────────
    """
    CREATE VIEW IF NOT EXISTS klines_indicators AS
    SELECT
        k.stock_id, k.date,
        k.open, k.high, k.low, k.close, k.volume, k.amount,
        i.ma5, i.ma20, i.ma25, i.ma60, i.ma200,
        i.vol_ma5, i.vol_ma20, i.vol_ma60,
        i.bias_ma25, i.bias_ma60, i.bias_ma200,
        i.atr14, i.vwap
    FROM klines k
    LEFT JOIN stock_indicators i
        ON k.stock_id = i.stock_id AND k.date = i.date
    """,
    # ── institutional_daily（向後相容）────────────────────────────────────
    """
    CREATE VIEW IF NOT EXISTS institutional_daily AS
    SELECT * FROM institutional_data
    """,
]


def create_tables(conn: sqlite3.Connection, *, commit: bool = True) -> None:
    """建立所有資料表（若不存在）。可重複執行（idempotent）。"""
    cursor = conn.cursor()
    for sql in SCHEMA_SQL:
        cursor.execute(sql)
    _ensure_institutional_schema(conn)
    if commit:
        conn.commit()


def create_views(conn: sqlite3.Connection, *, commit: bool = True) -> None:
    """建立 / 重建所有 VIEW。可重複執行（idempotent）。"""
    cursor = conn.cursor()
    for sql in VIEWS_SQL:
        cursor.execute(sql)
    if commit:
        conn.commit()


def init_db() -> None:
    """初始化所有資料表 + views（若不存在）"""
    conn = get_connection()
    try:
        create_tables(conn)
        create_views(conn)
    finally:
        conn.close()
    print(f"✅ 資料庫初始化完成：{get_path()}")


def _ensure_institutional_schema(conn: sqlite3.Connection) -> None:
    existing = {row[1] for row in conn.execute("PRAGMA table_info(institutional_data)").fetchall()}
    columns = [
        ("foreign_buy", "INTEGER", "0"),
        ("foreign_sell", "INTEGER", "0"),
        ("trust_buy", "INTEGER", "0"),
        ("trust_sell", "INTEGER", "0"),
        ("dealer_buy", "INTEGER", "0"),
        ("dealer_sell", "INTEGER", "0"),
    ]
    for name, typ, default in columns:
        if name not in existing:
            conn.execute(
                f"ALTER TABLE institutional_data ADD COLUMN {name} {typ} DEFAULT {default}"
            )


def migrate_db() -> None:
    """Apply idempotent additive indexes, columns, and compatibility views."""
    conn = get_connection()
    try:
        create_tables(conn, commit=False)
        create_views(conn, commit=False)
        conn.commit()
    finally:
        conn.close()


def show_tables() -> None:
    """顯示所有資料表名稱"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = cursor.fetchall()
    print("\n📁 資料庫中的資料表：")
    for t in tables:
        print(f"  - {t['name']}")
    conn.close()
