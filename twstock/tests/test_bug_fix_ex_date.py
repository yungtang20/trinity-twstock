"""Bug Fix: main.py 使用 ex_date 但 dividend_events 表只有 date 欄位"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from twstock.db import get_connection


def test_dividend_events_column_is_date_not_ex_date():
    """dividend_events 表的日期欄位叫 date，不叫 ex_date"""
    conn = get_connection(readonly=True)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(dividend_events)").fetchall()}
    conn.close()
    assert "date" in columns, "dividend_events 應有 date 欄位"
    assert "ex_date" not in columns, "dividend_events 不應有 ex_date 欄位"


def test_main_py_sql_uses_date_not_ex_date():
    """main.py 查詢 dividend_events 的 SQL 應使用 date 而非 ex_date"""
    main_path = os.path.join(os.path.dirname(__file__), "..", "main.py")
    with open(main_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "ex_date" not in content, "main.py 不應使用 ex_date，dividend_events 表的欄位叫 date"


def test_intraday_dividend_check_sql_executable():
    """intraday 功能的除權息查詢 SQL 應可正常執行"""
    conn = get_connection(readonly=True)
    try:
        conn.execute(
            "SELECT 1 FROM dividend_events WHERE stock_id = ? AND date = ?",
            ("2330", "2026-06-26"),
        ).fetchone()
    except Exception as e:
        assert False, f"SQL 執行失敗: {e}"
    finally:
        conn.close()
