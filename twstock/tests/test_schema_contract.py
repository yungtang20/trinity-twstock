# -*- coding: utf-8 -*-
"""
test_schema_contract.py — Schema 核心欄位與相容層 contract 測試

防止文件與實作分裂：驗證 schema 的核心欄位、型別、視圖定義。
"""

from __future__ import annotations


def _get_columns(db_conn, table_name: str) -> dict[str, str]:
    """取得資料表的欄位名稱與型別 mapping。"""
    rows = db_conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {row[1]: row[2] for row in rows}


def _get_tables_and_views(db_conn) -> dict[str, str]:
    """取得所有資料表與視圖及其類型（table/view）。"""
    rows = db_conn.execute(
        "SELECT name, type FROM sqlite_master WHERE type IN ('table', 'view')"
    ).fetchall()
    return {row[0]: row[1] for row in rows}


# ── stock_history 核心欄位 ─────────────────────────────────


def test_stock_history_core_columns(db_conn):
    """stock_history 應包含所有核心欄位。"""
    from twstock.db_admin import create_tables

    create_tables(db_conn)

    columns = _get_columns(db_conn, "stock_history")

    expected = {
        "stock_id",
        "date",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "amount",
        "trade_count",
        "spread",
    }

    assert expected.issubset(columns.keys()), f"缺少欄位: {expected - set(columns.keys())}"


def test_stock_history_no_adj_close(db_conn):
    """stock_history 不應包含 adj_close（由 klines view 計算）。"""
    from twstock.db_admin import create_tables

    create_tables(db_conn)

    columns = _get_columns(db_conn, "stock_history")

    assert "adj_close" not in columns, "adj_close 不該存在於 stock_history"
    assert "adj_open" not in columns, "adj_open 不該存在於 stock_history"
    assert "adj_high" not in columns, "adj_high 不該存在於 stock_history"
    assert "adj_low" not in columns, "adj_low 不該存在於 stock_history"


def test_stock_history_volume_amount_are_integer(db_conn):
    """volume 與 amount 應為 INTEGER（存原始值：股 / 元）。"""
    from twstock.db_admin import create_tables

    create_tables(db_conn)

    columns = _get_columns(db_conn, "stock_history")

    assert columns.get("volume") == "INTEGER", f"volume 應為 INTEGER，實際 {columns.get('volume')}"
    assert columns.get("amount") == "INTEGER", f"amount 應為 INTEGER，實際 {columns.get('amount')}"


# ── 相容層 VIEW ─────────────────────────────────────────────


def test_tdcc_shareholding_is_view(db_conn):
    """tdcc_shareholding 應是 VIEW，不是 TABLE。"""
    from twstock.db_admin import create_tables, create_views

    create_tables(db_conn)
    create_views(db_conn)

    objects = _get_tables_and_views(db_conn)

    assert "tdcc_shareholding" in objects, "缺少 tdcc_shareholding view"
    assert (
        objects["tdcc_shareholding"] == "view"
    ), f"tdcc_shareholding 應為 view，實際 {objects['tdcc_shareholding']}"


def test_expected_views_exist(db_conn):
    """所有向後相容 VIEW 都應存在。"""
    from twstock.db_admin import create_tables, create_views

    create_tables(db_conn)
    create_views(db_conn)

    objects = _get_tables_and_views(db_conn)
    expected_views = {
        "tdcc_shareholding",
        "klines",
        "klines_indicators",
        "institutional_daily",
    }

    for name in expected_views:
        assert name in objects, f"缺少 view: {name}"
        assert objects[name] == "view", f"{name} 應為 view，實際 {objects[name]}"
