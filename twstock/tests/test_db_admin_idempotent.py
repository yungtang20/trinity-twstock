# -*- coding: utf-8 -*-
"""
test_db_admin_idempotent.py — db_admin 建立表與 VIEW 的冪等測試

驗證 create_tables() 與 create_views() 可重複執行不拋例外，
且結果一致（表格與 VIEW 都存在）。
"""

from __future__ import annotations


def test_create_tables_is_idempotent(db_conn, patch_db_path):
    """create_tables() 可重複執行不拋例外。"""
    from twstock.db_admin import create_tables

    # 第一次
    create_tables(db_conn)
    # 第二次不應丟例外
    create_tables(db_conn)

    tables = db_conn.execute("""
        SELECT name FROM sqlite_master WHERE type='table'
    """).fetchall()
    table_names = {row[0] for row in tables}

    assert "stock_meta" in table_names
    assert "stock_history" in table_names
    assert "institutional_data" in table_names
    assert "shareholding_unified" in table_names
    assert "stock_indicators" in table_names


def test_create_views_is_idempotent(db_conn, patch_db_path):
    """create_views() 可重複執行不拋例外。"""
    from twstock.db_admin import create_tables, create_views

    create_tables(db_conn)

    # 第一次
    create_views(db_conn)
    # 第二次不應丟例外
    create_views(db_conn)

    views = db_conn.execute("""
        SELECT name FROM sqlite_master WHERE type='view'
    """).fetchall()
    view_names = {row[0] for row in views}

    assert "tdcc_shareholding" in view_names
    assert "klines" in view_names
    assert "klines_indicators" in view_names
    assert "institutional_daily" in view_names


def test_init_db_is_idempotent(db_conn, patch_db_path):
    """init_db() 可重複執行不拋例外。"""
    from twstock.db_admin import init_db

    # 第一次
    init_db()
    # 第二次不應丟例外
    init_db()

    tables = db_conn.execute("""
        SELECT name FROM sqlite_master WHERE type='table'
    """).fetchall()
    table_names = {row[0] for row in tables}

    views = db_conn.execute("""
        SELECT name FROM sqlite_master WHERE type='view'
    """).fetchall()
    view_names = {row[0] for row in views}

    # 表格應存在
    assert "stock_meta" in table_names
    assert "stock_history" in table_names
    assert "institutional_data" in table_names

    # VIEW 應存在
    assert "tdcc_shareholding" in view_names
    assert "klines" in view_names


def test_compatibility_views_exist(db_conn, patch_db_path):
    """向後相容的 VIEW 應存在且可被查詢。"""
    from twstock.db_admin import init_db

    init_db()

    views = db_conn.execute("""
        SELECT name FROM sqlite_master WHERE type='view'
    """).fetchall()
    view_names = {row[0] for row in views}

    # 向後相容 VIEW
    assert "institutional_daily" in view_names, "institutional_daily VIEW 應存在（向後相容）"
    assert "tdcc_shareholding" in view_names, "tdcc_shareholding VIEW 應存在（向後相容）"
