# -*- coding: utf-8 -*-
"""
test_db_schema_bootstrap.py — Schema 建立合同測試

驗證 db_admin.init_db() 建立的所有 table/view 與 DB_SCHEMA.md 一致。
"""
from __future__ import annotations

import sqlite3


# DB_SCHEMA.md 定義的核心 table
REQUIRED_TABLES = {
    "stock_meta",
    "stock_trading_calendar",
    "stock_history",
    "dividend_events",
    "institutional_data",
    "shareholding_unified",
    "per_data",
    "audit_log",
    "stock_indicators",
}

# DB_SCHEMA.md 定義的 view
REQUIRED_VIEWS = {
    "tdcc_shareholding",
    "klines",
    "klines_indicators",
}


def _list_objects(conn: sqlite3.Connection) -> set[tuple[str, str]]:
    rows = conn.execute(
        "SELECT name, type FROM sqlite_master WHERE type IN ('table', 'view')"
    ).fetchall()
    return {(row[0], row[1]) for row in rows}


def test_bootstrap_creates_required_tables(patch_db_path):
    """init_db() 後，所有核心 table 都存在。"""
    from db_admin import init_db

    init_db()

    import db
    conn = db.get_connection()
    objects = _list_objects(conn)
    conn.close()

    tables = {name for name, typ in objects if typ == "table"}
    missing = REQUIRED_TABLES - tables
    assert not missing, f"Missing tables: {missing}"


def test_bootstrap_creates_required_views(patch_db_path):
    """init_db() 後，所有核心 view 都存在。"""
    from db_admin import init_db

    init_db()

    import db
    conn = db.get_connection()
    objects = _list_objects(conn)
    conn.close()

    views = {name for name, typ in objects if typ == "view"}
    missing = REQUIRED_VIEWS - views
    assert not missing, f"Missing views: {missing}"


def test_stock_history_has_no_adj_close(patch_db_path):
    """stock_history 不該有 adj_close 欄位（由 klines view 提供）。"""
    from db_admin import init_db

    init_db()

    import db
    conn = db.get_connection()
    cols = {row[1] for row in conn.execute("PRAGMA table_info(stock_history)")}
    conn.close()

    assert "adj_close" not in cols, (
        "stock_history 不該有 adj_close 欄位，adj_close 由 klines view 計算"
    )


def test_tdcc_shareholding_is_view(patch_db_path):
    """tdcc_shareholding 必須是 VIEW，不是 TABLE。"""
    from db_admin import init_db

    init_db()

    import db
    conn = db.get_connection()
    rows = conn.execute(
        "SELECT type FROM sqlite_master WHERE name = 'tdcc_shareholding'"
    ).fetchall()
    conn.close()

    assert len(rows) == 1, "tdcc_shareholding 不存在"
    assert rows[0][0] == "view", (
        f"tdcc_shareholding 必須是 VIEW，實際是 {rows[0][0]}"
    )


def test_stock_history_columns_match_schema(patch_db_path):
    """stock_history 欄位與 DB_SCHEMA.md 一致。"""
    from db_admin import init_db

    init_db()

    import db
    conn = db.get_connection()
    cols = {row[1] for row in conn.execute("PRAGMA table_info(stock_history)")}
    conn.close()

    expected_cols = {
        "stock_id", "date", "open", "high", "low", "close",
        "volume", "amount", "trade_count", "spread",
        "source", "updated_at",
    }
    missing = expected_cols - cols
    extra = cols - expected_cols
    assert not missing, f"stock_history 缺少欄位: {missing}"
    assert not extra, f"stock_history 多出欄位: {extra}"


def test_institutional_data_columns_match_schema(patch_db_path):
    """institutional_data 欄位與 DB_SCHEMA.md 一致。"""
    from db_admin import init_db

    init_db()

    import db
    conn = db.get_connection()
    cols = {row[1] for row in conn.execute("PRAGMA table_info(institutional_data)")}
    conn.close()

    expected_cols = {
        "stock_id", "date",
        "foreign_net", "trust_net", "dealer_net", "institutional_net",
        "foreign_buy", "foreign_sell",
        "trust_buy", "trust_sell",
        "dealer_buy", "dealer_sell",
        "source", "updated_at",
    }
    missing = expected_cols - cols
    extra = cols - expected_cols
    assert not missing, f"institutional_data 缺少欄位: {missing}"
    assert not extra, f"institutional_data 多出欄位: {extra}"


def test_shareholding_unified_columns_match_schema(patch_db_path):
    """shareholding_unified 欄位與 DB_SCHEMA.md 一致。"""
    from db_admin import init_db

    init_db()

    import db
    conn = db.get_connection()
    cols = {row[1] for row in conn.execute("PRAGMA table_info(shareholding_unified)")}
    conn.close()

    expected_cols = {
        "stock_id", "date", "source",
        "total_shares", "whale_ratio", "retail_ratio",
        "foreign_shares", "foreign_ratio",
        "total_people", "whale_shares", "whale_people",
        "updated_at",
    }
    missing = expected_cols - cols
    extra = cols - expected_cols
    assert not missing, f"shareholding_unified 缺少欄位: {missing}"
    assert not extra, f"shareholding_unified 多出欄位: {extra}"


def test_stock_indicators_columns_match_schema(patch_db_path):
    """stock_indicators 欄位與 DB_SCHEMA.md 一致。"""
    from db_admin import init_db

    init_db()

    import db
    conn = db.get_connection()
    cols = {row[1] for row in conn.execute("PRAGMA table_info(stock_indicators)")}
    conn.close()

    expected_cols = {
        "stock_id", "date",
        "ma5", "ma20", "ma25", "ma60", "ma200",
        "vol_ma5", "vol_ma20", "vol_ma60",
        "bias_ma25", "bias_ma60", "bias_ma200",
        "atr14", "vwap",
        "updated_at",
    }
    missing = expected_cols - cols
    extra = cols - expected_cols
    assert not missing, f"stock_indicators 缺少欄位: {missing}"
    assert not extra, f"stock_indicators 多出欄位: {extra}"
