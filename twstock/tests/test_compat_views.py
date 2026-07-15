# -*- coding: utf-8 -*-
"""
test_compat_views.py — 相容層 VIEW 測試

驗證向後相容的 VIEW 存在且資料可讀。
這些 VIEW 是舊名稱的alias，在未完成全 repo 收斂前不可移除。
"""

from __future__ import annotations


def test_compatibility_views_exist(db_conn, patch_db_path):
    """所有向後相容的 VIEW 應存在。"""
    from twstock.db_admin import init_db

    init_db()

    rows = db_conn.execute("""
        SELECT name, type
        FROM sqlite_master
        WHERE type = 'view'
    """).fetchall()
    names = {row[0] for row in rows}

    assert "tdcc_shareholding" in names, "tdcc_shareholding VIEW 應存在（向後相容）"
    assert "institutional_daily" in names, "institutional_daily VIEW 應存在（向後相容）"
    assert "klines" in names, "klines VIEW 應存在"
    assert "klines_indicators" in names, "klines_indicators VIEW 應存在"


def test_tdcc_shareholding_view_reads_from_unified(db_conn, patch_db_path):
    """tdcc_shareholding VIEW 應能讀取 shareholding_unified 中 source='tdcc' 的資料。"""
    import pandas as pd
    from twstock.core.processor import DataProcessor

    from twstock.db_admin import init_db

    init_db()

    df = pd.DataFrame(
        [
            {
                "stock_id": "2330",
                "date": "2026-06-21",
                "total_shares": 486000000,
                "whale_ratio": 42.6,
                "retail_ratio": 3.2,
            }
        ]
    )
    DataProcessor().upsert_tdcc(df)

    # 透過 VIEW 讀取
    row = db_conn.execute(
        "SELECT stock_id, total_shares FROM tdcc_shareholding WHERE stock_id='2330'"
    ).fetchone()

    assert row is not None, "tdcc_shareholding VIEW 應能讀取資料"
    assert row[1] == 486000000, f"total_shares 應為 486000000，實際 {row[1]}"


def test_institutional_daily_view_reads_from_institutional_data(db_conn, patch_db_path):
    """institutional_daily VIEW 應能讀取 institutional_data 的資料。"""
    import pandas as pd
    from twstock.core.processor import DataProcessor

    from twstock.db_admin import init_db

    init_db()

    df = pd.DataFrame(
        [
            {
                "stock_id": "2330",
                "date": "2026-06-21",
                "foreign_net": 3000000,
                "trust_net": 600000,
                "dealer_net": 300000,
                "institutional_net": 3900000,
            }
        ]
    )
    DataProcessor().upsert_institutional(df)

    # 透過 VIEW 讀取
    row = db_conn.execute(
        "SELECT stock_id, foreign_net FROM institutional_daily WHERE stock_id='2330'"
    ).fetchone()

    assert row is not None, "institutional_daily VIEW 應能讀取資料"
    assert row[1] == 3000000, f"foreign_net 應為 3000000，實際 {row[1]}"


def test_klines_indicators_view_joins_indicators(db_conn, patch_db_path):
    """klines_indicators VIEW 應 JOIN klines 與 stock_indicators。"""

    from twstock.db_admin import init_db

    init_db()

    # 寫入 stock_history
    db_conn.execute("""
        INSERT INTO stock_history (stock_id, date, open, high, low, close, volume, amount)
        VALUES ('2330', '2026-06-21', 950, 960, 945, 958, 32000000, 30500000000)
    """)
    # 寫入 stock_indicators
    db_conn.execute("""
        INSERT INTO stock_indicators (stock_id, date, ma5, ma20, ma60)
        VALUES ('2330', '2026-06-21', 950.0, 940.0, 920.0)
    """)
    db_conn.commit()

    # 透過 VIEW 讀取
    row = db_conn.execute(
        "SELECT ma5, ma20, ma60 FROM klines_indicators WHERE stock_id='2330'"
    ).fetchone()

    assert row is not None, "klines_indicators VIEW 應能讀取資料"
    assert row[0] == 950.0, f"ma5 應為 950.0，實際 {row[0]}"
    assert row[1] == 940.0, f"ma20 應為 940.0，實際 {row[1]}"
    assert row[2] == 920.0, f"ma60 應為 920.0，實際 {row[2]}"
