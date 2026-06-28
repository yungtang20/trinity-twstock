#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模組 1：db_admin.py (資料庫層)
職責：
1. 建立 Trinity 統一 Schema
2. 將清洗後 DataFrame 寫入 SQLite
3. 提供 ETL 寫入入口
"""

import os
import sqlite3
import logging
from typing import Iterable, List, Dict, Optional, Sequence

import pandas as pd
from db import DB_PATH # Import unified database path [AI MOD]

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
        source TEXT,
        updated_at TEXT DEFAULT (datetime('now', 'localtime'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS stock_history (
        stock_id TEXT,
        date TEXT,
        open REAL,
        high REAL,
        low REAL,
        close REAL,
        volume INTEGER,
        amount INTEGER,
        trade_count INTEGER,
        spread REAL,
        adj_factor REAL DEFAULT 1.0,
        adj_close REAL,
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
        stock_id TEXT,
        date TEXT,
        foreign_net INTEGER DEFAULT 0,
        trust_net INTEGER DEFAULT 0,
        dealer_net INTEGER DEFAULT 0,
        foreign_buy INTEGER DEFAULT 0,
        foreign_sell INTEGER DEFAULT 0,
        trust_buy INTEGER DEFAULT 0,
        trust_sell INTEGER DEFAULT 0,
        dealer_buy INTEGER DEFAULT 0,
        dealer_sell INTEGER DEFAULT 0,
        institutional_net INTEGER DEFAULT 0,
        source TEXT,
        updated_at TEXT DEFAULT (datetime('now', 'localtime')),
        PRIMARY KEY (stock_id, date)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS shareholding_data (
        stock_id TEXT,
        date TEXT,
        foreign_shares REAL,
        foreign_ratio REAL,
        source TEXT,
        updated_at TEXT DEFAULT (datetime('now', 'localtime')),
        PRIMARY KEY (stock_id, date)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS tdcc_shareholding (
        stock_id TEXT,
        date TEXT,
        total_shares INTEGER,
        whale_ratio REAL,
        retail_ratio REAL,
        source TEXT,
        updated_at TEXT DEFAULT (datetime('now', 'localtime')),
        PRIMARY KEY (stock_id, date)
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
    "CREATE INDEX IF NOT EXISTS idx_stock_history_stock_date ON stock_history(stock_id, date)",
    "CREATE INDEX IF NOT EXISTS idx_dividend_events_stock_date ON dividend_events(stock_id, date)",
    "CREATE INDEX IF NOT EXISTS idx_institutional_stock_date ON institutional_data(stock_id, date)",
    "CREATE INDEX IF NOT EXISTS idx_shareholding_stock_date ON shareholding_data(stock_id, date)",
    "CREATE INDEX IF NOT EXISTS idx_tdcc_stock_date ON tdcc_shareholding(stock_id, date)",
]

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db() -> None:
    """初始化所有資料表（若不存在）"""
    conn = get_connection()
    cursor = conn.cursor()
    for sql in SCHEMA_SQL:
        cursor.execute(sql)
    conn.commit()
    _ensure_institutional_schema(conn)
    conn.commit()
    conn.close()
    print(f"✅ 資料庫初始化完成：{DB_PATH}")


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
            conn.execute(f"ALTER TABLE institutional_data ADD COLUMN {name} {typ} DEFAULT {default}")


def migrate_db() -> None:
    """Migrate existing database schema for institutional_data."""
    conn = get_connection()
    try:
        _ensure_institutional_schema(conn)
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

# ──────────────────────────────────────────────────────────────
# Generic writer
# ──────────────────────────────────────────────────────────────

def _clean_value(v):
    try:
        if pd.isna(v):
            return None
    except Exception:
        pass

    if hasattr(v, "item"):
        try:
            return v.item()
        except Exception:
            return v

    if isinstance(v, pd.Timestamp):
        return v.strftime("%Y-%m-%d")
    return v

def _ensure_date_text(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "date" in out.columns:
        out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    if "updated_at" in out.columns:
        out["updated_at"] = pd.to_datetime(out["updated_at"], errors="coerce").astype(str)
    return out

def upsert_dataframe(conn: sqlite3.Connection, table: str, df: pd.DataFrame, columns: Sequence[str]) -> int:
    """
    將 DataFrame 以 INSERT OR REPLACE 寫入指定表格。
    只寫 columns 指定欄位，避免欄位順序錯位。
    """
    if df is None or df.empty:
        return 0

    cols = [c for c in columns if c in df.columns]
    if not cols:
        return 0

    frame = df[cols].copy()
    frame = _ensure_date_text(frame)
    placeholders = ",".join(["?"] * len(cols))
    col_sql = ",".join(cols)
    sql = f"INSERT OR REPLACE INTO {table} ({col_sql}) VALUES ({placeholders})"

    rows = []
    for _, row in frame.iterrows():
        rows.append(tuple(_clean_value(row[c]) for c in cols))

    conn.executemany(sql, rows)
    return len(rows)

def save_stock_meta(df: pd.DataFrame) -> int:
    if df is None or df.empty:
        return 0
    conn = get_connection()
    try:
        n = upsert_dataframe(
            conn,
            "stock_meta",
            df,
            ["stock_id", "stock_name", "industry_category", "market", "type", "source"],
        )
        conn.commit()
        return n
    finally:
        conn.close()

def save_calendar(df: pd.DataFrame) -> int:
    if df is None or df.empty:
        return 0
    conn = get_connection()
    try:
        n = upsert_dataframe(conn, "stock_trading_calendar", df, ["date", "is_open", "source"])
        conn.commit()
        return n
    finally:
        conn.close()

def save_stock_history(df: pd.DataFrame) -> int:
    if df is None or df.empty:
        return 0
    conn = get_connection()
    try:
        n = upsert_dataframe(
            conn,
            "stock_history",
            df,
            [
                "stock_id", "date", "open", "high", "low", "close",
                "volume", "amount", "trade_count", "spread",
                "adj_factor", "adj_close", "source"
            ],
        )
        conn.commit()
        return n
    finally:
        conn.close()

def save_dividend_events(df: pd.DataFrame) -> int:
    if df is None or df.empty:
        return 0
    conn = get_connection()
    try:
        n = upsert_dataframe(
            conn,
            "dividend_events",
            df,
            [
                "stock_id", "date", "before_price", "after_price",
                "reference_price", "cash_dividend", "stock_dividend", "source"
            ],
        )
        conn.commit()
        return n
    finally:
        conn.close()

def save_institutional_data(df: pd.DataFrame) -> int:
    if df is None or df.empty:
        return 0
    conn = get_connection()
    try:
        n = upsert_dataframe(
            conn,
            "institutional_data",
            df,
            [
                "stock_id", "date", "foreign_net", "trust_net", "dealer_net", "institutional_net",
                "foreign_buy", "foreign_sell", "trust_buy", "trust_sell", "dealer_buy", "dealer_sell",
                "source",
            ],
        )
        conn.commit()
        return n
    finally:
        conn.close()

def save_shareholding_data(df: pd.DataFrame) -> int:
    if df is None or df.empty:
        return 0
    conn = get_connection()
    try:
        n = upsert_dataframe(
            conn,
            "shareholding_data",
            df,
            ["stock_id", "date", "foreign_shares", "foreign_ratio", "source"],
        )
        conn.commit()
        return n
    finally:
        conn.close()

def save_tdcc_shareholding(df: pd.DataFrame) -> int:
    if df is None or df.empty:
        return 0
    conn = get_connection()
    try:
        n = upsert_dataframe(
            conn,
            "tdcc_shareholding",
            df,
            ["stock_id", "date", "total_shares", "whale_ratio", "retail_ratio", "source"],
        )
        conn.commit()
        return n
    finally:
        conn.close()

def log_audit(stock_id: str, action: str, status: str, detail: str = "") -> None:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO audit_log (stock_id, action, status, detail) VALUES (?,?,?,?)",
            (stock_id, action, status, detail),
        )
        conn.commit()
    finally:
        conn.close()

def save_bundle(stock_id: str, bundle: Dict[str, pd.DataFrame]) -> Dict[str, int]:
    """
    寫入 fetcher.fetch_one() 的結果。
    """
    mapping = {
        "price": save_stock_history,
        "dividend": save_dividend_events,
        "institutional": save_institutional_data,
        "shareholding": save_shareholding_data,
        "tdcc": save_tdcc_shareholding,
    }
    result: Dict[str, int] = {}
    for name, df in (bundle or {}).items():
        fn = mapping.get(name)
        if fn is None:
            continue
        n = fn(df)
        result[name] = n
    return result

def save_stock_meta_frame(df: pd.DataFrame) -> int:
    return save_stock_meta(df)

def save_calendar_frame(df: pd.DataFrame) -> int:
    return save_calendar(df)

def interactive_menu():
    print("\n[db_admin] 資料庫管理工具")
    print("1. 初始化資料庫 (建立所有表格)")
    print("2. 檢視現有資料表")
    choice = input("請選擇 (1/2): ").strip()
    if choice == "1":
        init_db()
    elif choice == "2":
        show_tables()
    else:
        print("無效選擇")

if __name__ == "__main__":
    interactive_menu()
