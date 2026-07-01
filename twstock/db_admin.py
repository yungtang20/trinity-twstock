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
from db import DB_PATH, get_connection  # [FIX] Reuse the single connection entrypoint (was: local sqlite3.connect() with no busy_timeout/WAL)

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

def create_tables(conn: sqlite3.Connection) -> None:
    """建立所有資料表（若不存在）。可重複執行（idempotent）。"""
    cursor = conn.cursor()
    for sql in SCHEMA_SQL:
        cursor.execute(sql)
    _ensure_institutional_schema(conn)
    conn.commit()


def create_views(conn: sqlite3.Connection) -> None:
    """建立 / 重建所有 VIEW。可重複執行（idempotent）。"""
    cursor = conn.cursor()
    for sql in VIEWS_SQL:
        cursor.execute(sql)
    conn.commit()


def init_db() -> None:
    """初始化所有資料表 + views（若不存在）"""
    conn = get_connection()
    try:
        create_tables(conn)
        create_views(conn)
    finally:
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
    """寫入 stock_meta：用 ON CONFLICT 區域更新，避免漏帶欄位時把舊資料洗掉"""
    if df is None or df.empty:
        return 0
    conn = get_connection()
    try:
        # 整理欄位（只取 stock_meta 實際有的欄位）
        expected_cols = ["stock_id", "stock_name", "industry_category", "market", "type", "source"]
        cols = [c for c in expected_cols if c in df.columns]
        if not cols:
            return 0

        frame = df[cols].copy()
        frame = _ensure_date_text(frame)

        # 組成資料列
        rows = []
        for _, row in frame.iterrows():
            rows.append(tuple(_clean_value(row[c]) for c in cols))

        # 動態組合 INSERT ... ON CONFLICT DO UPDATE
        # 更新規則：新值為空字串或 NULL 時保留舊值（COALESCE(NULLIF(...))）
        col_list = ",".join(cols)
        placeholders = ",".join(["?"] * len(cols))

        # 決定哪些欄位要做條件更新（排除主鍵 stock_id）
        update_cols = [c for c in cols if c != "stock_id"]
        if update_cols:
            # 新值為空字串或 NULL 時保留舊值，否則用新值
            set_clauses = [
                f"{c}=CASE WHEN excluded.{c} IS NOT NULL AND excluded.{c} != '' "
                f"THEN excluded.{c} ELSE stock_meta.{c} END"
                for c in update_cols
            ]
            update_sql = ",".join(set_clauses)
            sql = (f"INSERT INTO stock_meta ({col_list}) VALUES ({placeholders}) "
                   f"ON CONFLICT(stock_id) DO UPDATE SET {update_sql}")
        else:
            # 只有 stock_id，用 DO NOTHING 避免重複
            sql = (f"INSERT INTO stock_meta ({col_list}) VALUES ({placeholders}) "
                   f"ON CONFLICT(stock_id) DO NOTHING")

        conn.executemany(sql, rows)
        conn.commit()
        return len(rows)
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
                "source"
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
    """寫入 shareholding_unified（舊 shareholding_data 已統一）。"""
    if df is None or df.empty:
        return 0
    conn = get_connection()
    try:
        n = upsert_dataframe(
            conn,
            "shareholding_unified",
            df,
            ["stock_id", "date", "source", "total_shares", "whale_ratio", "retail_ratio",
             "foreign_shares", "foreign_ratio", "total_people", "whale_shares", "whale_people"],
        )
        conn.commit()
        return n
    finally:
        conn.close()

def save_tdcc_shareholding(df: pd.DataFrame) -> int:
    """寫入 shareholding_unified（tdcc_shareholding 是 VIEW，不可直接寫入）。"""
    if df is None or df.empty:
        return 0
    df = df.copy()
    if "source" not in df.columns:
        df["source"] = "tdcc"
    conn = get_connection()
    try:
        n = upsert_dataframe(
            conn,
            "shareholding_unified",
            df,
            ["stock_id", "date", "source", "total_shares", "whale_ratio", "retail_ratio"],
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
