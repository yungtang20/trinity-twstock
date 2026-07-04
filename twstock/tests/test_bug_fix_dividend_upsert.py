import inspect
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_no_delete_loop():
    from official.dividend_crawler import upsert_dividend_events

    source = inspect.getsource(upsert_dividend_events)
    assert "DELETE FROM" not in source, "應使用 ON CONFLICT 而非逐筆 DELETE"


def test_no_bare_sqlite3_connect():
    from official.dividend_crawler import upsert_dividend_events

    source = inspect.getsource(upsert_dividend_events)
    assert "sqlite3.connect(" not in source, "應使用 get_connection() 統一入口"


def test_duplicate_writes_ok():
    import pandas as pd
    from db import get_connection
    from official.dividend_crawler import upsert_dividend_events

    test_df = pd.DataFrame(
        [
            {
                "stock_id": "9999",
                "date": "2099-01-01",
                "before_price": 100.0,
                "after_price": 95.0,
                "reference_price": 95.0,
                "cash_dividend": 5.0,
                "stock_dividend": 0.0,
                "source": "test",
            }
        ]
    )
    try:
        upsert_dividend_events(test_df)
        upsert_dividend_events(test_df)  # 第二次不應報錯
    finally:
        conn = get_connection()
        conn.execute("DELETE FROM dividend_events WHERE stock_id='9999' AND date='2099-01-01'")
        conn.commit()
        conn.close()
