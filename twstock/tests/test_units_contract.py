# -*- coding: utf-8 -*-
"""
test_units_contract.py — 單位轉換契約測試

驗證 DB 層存原始值（volume=股, amount=元），
顯示層（display.py）才轉 張/萬/億。
"""
from __future__ import annotations


def test_stock_history_stores_volume_in_shares(db_conn, patch_db_path):
    """stock_history.volume 存股，不存張。"""
    from db_admin import init_db

    init_db()

    db_conn.execute("""
        INSERT INTO stock_history (stock_id, date, open, high, low, close, volume, amount)
        VALUES ('2330', '2026-06-21', 950, 960, 945, 958, 32000000, 30500000000)
    """)
    db_conn.commit()

    row = db_conn.execute(
        "SELECT volume FROM stock_history WHERE stock_id='2330'"
    ).fetchone()

    # 32000000 股，不是 32000 張
    assert row[0] == 32000000, (
        f"volume 應存股（32000000），實際 {row[0]}"
    )


def test_stock_history_stores_amount_in_yuan(db_conn, patch_db_path):
    """stock_history.amount 存元，不存千萬元。"""
    from db_admin import init_db

    init_db()

    db_conn.execute("""
        INSERT INTO stock_history (stock_id, date, open, high, low, close, volume, amount)
        VALUES ('2330', '2026-06-21', 950, 960, 945, 958, 32000000, 30500000000)
    """)
    db_conn.commit()

    row = db_conn.execute(
        "SELECT amount FROM stock_history WHERE stock_id='2330'"
    ).fetchone()

    # 30500000000 元，不是 30500 千萬元
    assert row[0] == 30500000000, (
        f"amount 應存元（30500000000），實際 {row[0]}"
    )


def test_display_vol_fmt_converts_to_sheets():
    """display.py 的 vol_fmt 正確把股轉張。"""
    from display import vol_fmt

    # 1000 股 = 1 張
    assert vol_fmt(1000) == "1張"
    # 5000 股 = 5 張
    assert vol_fmt(5000) == "5張"
    # 15000 股 = 15 張
    assert vol_fmt(15000) == "15張"
    # 10000000 股 = 10000 張 = 1.0萬張
    result = vol_fmt(10000000)
    assert "萬" in result, f"10000000 股應顯示為萬單位: {result}"


def test_display_vol_rich_shows_sheets():
    """vol_rich 顯示張。"""
    from display import vol_rich

    result = vol_rich(10000, 5000)
    # 10000 股 = 10 張
    assert "10" in result, f"10000 股應顯示 10 張: {result}"


def test_institutional_data_stores_shares(db_conn, patch_db_path):
    """institutional_data 的 net/buy/sell 存股。"""
    from db_admin import init_db

    init_db()

    db_conn.execute("""
        INSERT INTO institutional_data
            (stock_id, date, foreign_net, trust_net, dealer_net, institutional_net,
             foreign_buy, foreign_sell, trust_buy, trust_sell, dealer_buy, dealer_sell)
        VALUES ('2330', '2026-06-21', 3000000, 600000, 300000, 3900000,
                8000000, 5000000, 1000000, 400000, 600000, 300000)
    """)
    db_conn.commit()

    row = db_conn.execute(
        "SELECT foreign_net, foreign_buy FROM institutional_data WHERE stock_id='2330'"
    ).fetchone()

    # foreign_net = 3000000 股
    assert row[0] == 3000000, f"foreign_net 應存股，實際 {row[0]}"
    assert row[1] == 8000000, f"foreign_buy 應存股，實際 {row[1]}"


def test_shareholding_unified_stores_shares(db_conn, patch_db_path):
    """shareholding_unified.total_shares 存股。"""
    from db_admin import init_db

    init_db()

    db_conn.execute("""
        INSERT INTO shareholding_unified
            (stock_id, date, source, total_shares, whale_ratio, retail_ratio)
        VALUES ('2330', '2026-06-21', 'tdcc', 486000000, 42.6, 3.2)
    """)
    db_conn.commit()

    row = db_conn.execute(
        "SELECT total_shares FROM shareholding_unified WHERE stock_id='2330'"
    ).fetchone()

    assert row[0] == 486000000, (
        f"total_shares 應存股（486000000），實際 {row[0]}"
    )


