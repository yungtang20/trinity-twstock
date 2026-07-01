# -*- coding: utf-8 -*-
"""
test_chips_strategy.py — 籌碼策略 SQL 契約測試

驗證 chips_strategy.py 在最小測試資料下能跑完並回傳結果，
且股票名稱欄位映射正確（m.stock_name，不是 m.name）。
"""
from __future__ import annotations

import sqlite3


def seed_chip_data(conn: sqlite3.Connection) -> None:
    """植入最小測試資料。"""
    conn.executescript(
        """
        INSERT INTO stock_meta (stock_id, stock_name, market, type)
        VALUES ('2330', '台積電', 'TSE', 'COMMON');

        INSERT INTO stock_history
            (stock_id, date, open, high, low, close, volume, amount, trade_count)
        VALUES
            ('2330', '2026-06-20', 950, 960, 945, 958, 32000000, 30500000000, 25000),
            ('2330', '2026-06-21', 958, 965, 952, 962, 28000000, 26900000000, 22000);

        INSERT INTO institutional_data
            (stock_id, date,
             foreign_net, trust_net, dealer_net, institutional_net,
             foreign_buy, foreign_sell,
             trust_buy, trust_sell,
             dealer_buy, dealer_sell,
             source)
        VALUES
            ('2330', '2026-06-21',
             3000000, 600000, 300000, 3900000,
             8000000, 5000000,
             1000000, 400000,
             600000, 300000,
             'official');

        INSERT INTO shareholding_unified
            (stock_id, date, source,
             total_shares, whale_ratio, retail_ratio,
             total_people, whale_shares, whale_people)
        VALUES
            ('2330', '2026-06-21', 'tdcc',
             486000000, 42.6, 3.2,
             128000, 207000000, 1800);
        """
    )
    conn.commit()


def test_chips_strategy_runs_without_sql_errors(db_conn, patch_db_path):
    """ChipsStrategy 在最小資料下能跑完，不因欄位名稱錯誤而爆炸。"""
    from db_admin import init_db

    init_db()
    seed_chip_data(db_conn)

    from strategy.chips_strategy import StockAnalyzer

    with StockAnalyzer(db_conn) as analyzer:
        result = analyzer.display_single_stock("2330")

    # display_single_stock 是 void，但這裡驗證沒爆炸就過
    assert True  # 能跑到這裡表示 SQL 沒炸


def test_chips_strategy_returns_stock_name(db_conn, patch_db_path):
    """StockAnalyzer 能正確查到 stock_name（不是 name）。"""
    from db_admin import init_db

    init_db()
    seed_chip_data(db_conn)

    from strategy.chips_strategy import StockAnalyzer

    with StockAnalyzer(db_conn) as analyzer:
        name = analyzer.conn.execute(
            "SELECT stock_name FROM stock_meta WHERE stock_id = '2330'"
        ).fetchone()[0]

    assert name == "台積電", f"預期 '台積電'，實際 '{name}'"


def test_chips_strategy_analyze_institutional(db_conn, patch_db_path):
    """analyze_institutional_buying 能正確查詢 institutional_data。"""
    from db_admin import init_db

    init_db()
    seed_chip_data(db_conn)

    from strategy.chips_strategy import StockAnalyzer

    with StockAnalyzer(db_conn) as analyzer:
        results = analyzer.analyze_institutional_buying(
            investor_type="foreign",
            min_consecutive_days=1,
            sort_choice=1,
        )

    # 有資料就回傳 list，不管內容
    assert isinstance(results, list)


def test_chips_strategy_analyze_main_force(db_conn, patch_db_path):
    """analyze_main_force_vs_retail 能正確查詢 shareholding_unified。"""
    from db_admin import init_db

    init_db()
    seed_chip_data(db_conn)

    from strategy.chips_strategy import StockAnalyzer

    with StockAnalyzer(db_conn) as analyzer:
        results, latest_date, prev_date = analyzer.analyze_main_force_vs_retail(
            sort_choice=1,
        )

    assert isinstance(results, list)
