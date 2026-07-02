# -*- coding: utf-8 -*-
"""
test_updater_schema_compat.py — updater.py 與 schema 相容性測試

驗證 updater.py 的 upsert_dataframe 不會寫入不存在的欄位
（如 adj_open, adj_high, adj_low, adj_close 在 stock_history 中不存在）。
也驗證 updater.py 不會寫入 tdcc_shareholding VIEW。
"""
from __future__ import annotations


def test_stock_history_has_no_adj_close_column(db_conn, patch_db_path):
    """stock_history 表不應有 adj_close/adj_open/adj_high/adj_low 欄位。"""
    from db_admin import init_db

    init_db()

    rows = db_conn.execute("PRAGMA table_info(stock_history)").fetchall()
    columns = {row[1] for row in rows}

    assert "adj_close" not in columns, "stock_history 不應有 adj_close 欄位（由 klines view 提供）"
    assert "adj_open" not in columns, "stock_history 不應有 adj_open 欄位"
    assert "adj_high" not in columns, "stock_history 不應有 adj_high 欄位"
    assert "adj_low" not in columns, "stock_history 不應有 adj_low 欄位"
    assert "adj_factor" not in columns, "stock_history 不應有 adj_factor 欄位（已拔除）"


def test_save_stock_history_does_not_write_adj_close(db_conn, patch_db_path):
    """processor.upsert_history 不應嘗試寫入 adj_close 欄位。"""
    from db_admin import init_db
    from processor import DataProcessor

    init_db()

    import pandas as pd

    db_conn.execute(
        "INSERT INTO stock_meta (stock_id, stock_name) VALUES ('2330', '台積電')"
    )
    db_conn.commit()

    df = pd.DataFrame([{
        "stock_id": "2330",
        "date": "2026-06-21",
        "open": 950.0,
        "high": 960.0,
        "low": 945.0,
        "close": 958.0,
        "volume": 32000000,
        "amount": 30500000000.0,
        "trade_count": 25000,
        "spread": 15.0,
        "source": "official",
    }])

    # 不應炸
    DataProcessor().upsert_history(df)

    row = db_conn.execute(
        "SELECT close FROM stock_history WHERE stock_id='2330' AND date='2026-06-21'"
    ).fetchone()
    assert row is not None
    assert row[0] == 958.0


def test_updater_does_not_reference_adj_close_in_schema():
    """updater.py 的 stock_history 寫入路徑不應引用 adj_close 等不存在欄位。"""
    from pathlib import Path
    src = Path("twstock/official/updater.py").read_text(encoding="utf-8")

    # 不應在 required 清單中出現 adj_close
    # 檢查 stock_history 區塊的 required 清單
    lines = src.splitlines()
    in_stock_history_block = False
    required_lines = []
    for line in lines:
        if "'stock_history'" in line and "table_name ==" in line:
            in_stock_history_block = True
        if in_stock_history_block:
            required_lines.append(line)
            if "]" in line and "required" in "".join(required_lines):
                break

    block = "\n".join(required_lines)
    assert "adj_close" not in block, (
        f"updater 的 stock_history required 欄位清單不應包含 adj_close:\n{block}"
    )
    assert "adj_open" not in block, "updater 的 stock_history required 不應包含 adj_open"
    assert "adj_high" not in block, "updater 的 stock_history required 不應包含 adj_high"
    assert "adj_low" not in block, "updater 的 stock_history required 不應包含 adj_low"


def test_updater_does_not_query_tdcc_shareholding_view_for_max_date():
    """updater.py 不應從 tdcc_shareholding VIEW 查 MAX(date)，應查 shareholding_unified。"""
    from pathlib import Path
    src = Path("twstock/official/updater.py").read_text(encoding="utf-8")

    # 不應出現 SELECT MAX(date) FROM tdcc_shareholding
    assert "MAX(date) FROM tdcc_shareholding" not in src, (
        "updater 不應從 tdcc_shareholding VIEW 查詢，應查 shareholding_unified"
    )


def test_updater_does_not_insert_into_tdcc_shareholding_view():
    """updater.py 不應呼叫 upsert_dataframe('tdcc_shareholding', ...)，因為它是 VIEW。"""
    from pathlib import Path
    src = Path("twstock/official/updater.py").read_text(encoding="utf-8")

    # 不應有 tdcc_shareholding 作為 upsert_dataframe 的 table_name 參數
    assert "upsert_dataframe('tdcc_shareholding'" not in src, (
        "updater 不應寫入 tdcc_shareholding VIEW，應寫入 shareholding_unified"
    )
