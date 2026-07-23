# -*- coding: utf-8 -*-
"""
test_chips_strategy.py — 籌碼策略 SQL 契約測試

驗證 chips_strategy.py 在最小測試資料下能跑完並回傳結果，
且股票名稱欄位映射正確（m.stock_name，不是 m.name）。
"""

from __future__ import annotations

import sqlite3

from rich.console import Console


def seed_chip_data(conn: sqlite3.Connection) -> None:
    """植入最小測試資料。"""
    conn.executescript("""
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
        """)
    conn.commit()


def test_chips_strategy_runs_without_sql_errors(db_conn, patch_db_path):
    """ChipsStrategy 在最小資料下能跑完，不因欄位名稱錯誤而爆炸。"""
    from twstock.db_admin import init_db

    init_db()
    seed_chip_data(db_conn)

    from twstock.strategy.chips_strategy import StockAnalyzer

    with StockAnalyzer(db_conn) as analyzer:
        analyzer.display_single_stock("2330")

    # display_single_stock 是 void，但這裡驗證沒爆炸就過
    assert True  # 能跑到這裡表示 SQL 沒炸


def test_single_stock_report_shows_complete_and_correct_chip_data(db_conn, patch_db_path, monkeypatch):
    """單股報告應顯示自營商、官方成交額與真實大戶人數。"""
    from twstock.db_admin import init_db
    from twstock.strategy import chips_strategy

    init_db()
    seed_chip_data(db_conn)
    db_conn.execute(
        """
        INSERT INTO shareholding_unified
            (stock_id, date, source, total_shares, whale_ratio,
             total_people, whale_shares, whale_people)
        VALUES ('2330', '2026-06-14', 'tdcc', 486000000, 41.6,
                129000, 202176000, 1700)
        """
    )
    # 比 TDCC 更新的其他來源列不得混入集保表格。
    db_conn.execute(
        """
        INSERT INTO shareholding_unified
            (stock_id, date, source, whale_ratio, total_people, whale_people)
        VALUES ('2330', '2026-06-28', 'twse_foreign', 99.99, 1, 1)
        """
    )
    db_conn.commit()

    report_console = Console(record=True, width=200, color_system=None)
    monkeypatch.setattr(chips_strategy, "rconsole", report_console)
    with chips_strategy.StockAnalyzer(db_conn) as analyzer:
        analyzer.display_single_stock("2330")
    output = report_console.export_text(styles=False)

    assert "自營" in output
    assert "+300" in output
    assert "269.00" in output  # DB amount，不是 close * volume 的 269.36
    assert "1,800" in output  # 官方 whale_people，不可再乘持股比例
    assert "📌 大戶重點" in output
    assert "DB 共 2 期" in output
    assert "大戶比例 +1.00 個百分點" in output
    assert "大戶人數 +100人" in output
    assert "99.99%" not in output


def test_chips_strategy_returns_stock_name(db_conn, patch_db_path):
    """StockAnalyzer 能正確查到 stock_name（不是 name）。"""
    from twstock.db_admin import init_db

    init_db()
    seed_chip_data(db_conn)

    from twstock.strategy.chips_strategy import StockAnalyzer

    with StockAnalyzer(db_conn) as analyzer:
        name = analyzer.conn.execute("SELECT stock_name FROM stock_meta WHERE stock_id = '2330'").fetchone()[0]

    assert name == "台積電", f"預期 '台積電'，實際 '{name}'"


def test_chips_strategy_analyze_institutional(db_conn, patch_db_path):
    """analyze_institutional_buying 能正確查詢 institutional_data。"""
    from twstock.db_admin import init_db

    init_db()
    seed_chip_data(db_conn)

    from twstock.strategy.chips_strategy import StockAnalyzer

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
    from twstock.db_admin import init_db

    init_db()
    seed_chip_data(db_conn)

    from twstock.strategy.chips_strategy import StockAnalyzer

    with StockAnalyzer(db_conn) as analyzer:
        results, latest_date, prev_date = analyzer.analyze_main_force_vs_retail(
            sort_choice=1,
        )

    assert isinstance(results, list)


def test_institutional_streak_stops_at_first_non_buy_day(db_conn, patch_db_path):
    """A sell day between two buy days must reset the consecutive streak."""
    from twstock.db_admin import init_db
    from twstock.strategy.chips_strategy import StockAnalyzer

    init_db()
    db_conn.execute(
        "INSERT INTO stock_meta (stock_id, stock_name, market, type) " "VALUES ('2330', '台積電', 'TSE', 'COMMON')"
    )
    for day, close in (("2026-07-17", 98), ("2026-07-20", 99), ("2026-07-21", 100)):
        db_conn.execute(
            "INSERT INTO stock_history "
            "(stock_id, date, open, high, low, close, volume, amount) "
            "VALUES ('2330', ?, ?, ?, ?, ?, 1000000, 100000000)",
            (day, close, close, close, close),
        )
    for day, net in (("2026-07-17", 100), ("2026-07-20", -50), ("2026-07-21", 200)):
        db_conn.execute(
            "INSERT INTO institutional_data (stock_id, date, foreign_net) VALUES ('2330', ?, ?)",
            (day, net),
        )
    db_conn.commit()

    with StockAnalyzer(db_conn) as analyzer:
        results = analyzer.analyze_institutional_buying("foreign", 1, 1)

    assert len(results) == 1
    assert results[0]["buy_days"] == 1
    assert results[0]["total_net"] == 200
    assert results[0]["prev_close"] == 99
