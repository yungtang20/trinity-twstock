# -*- coding: utf-8 -*-
"""
test_strategy_output_contract.py — 策略輸出格式契約測試

驗證所有策略的 analyze() 回傳格式一致，
確保 strategy_runner 有穩定的輸出基礎。
"""
from __future__ import annotations


# 策略輸出最小共同格式
REQUIRED_KEYS = {"strategy", "stock_id", "signal"}


def assert_strategy_contract(result: dict, stock_id: str = "2330"):
    """驗證策略輸出符合最小 contract。"""
    assert isinstance(result, dict), f"策略輸出應為 dict，實際 {type(result)}"
    assert REQUIRED_KEYS.issubset(result.keys()), (
        f"策略輸出缺少必要欄位。需要 {REQUIRED_KEYS}，實際 {set(result.keys())}"
    )
    assert result["stock_id"] == stock_id, (
        f"stock_id 應為 {stock_id}，實際 {result['stock_id']}"
    )
    assert result["signal"] in ("bullish", "bearish", "neutral"), (
        f"signal 必須是 bullish/bearish/neutral，實際 {result['signal']}"
    )


def _seed_chip_data(db_conn):
    """植入籌碼測試資料。"""
    db_conn.execute("""
        INSERT INTO stock_meta (stock_id, stock_name) VALUES ('2330', '台積電')
    """)
    for i in range(1, 11):
        db_conn.execute(
            "INSERT INTO institutional_data "
            "(stock_id, date, foreign_net, trust_net, dealer_net, institutional_net) "
            "VALUES ('2330', ?, 1000000, 500000, 200000, 1700000)",
            (f"2026-06-{i:02d}",)
        )
    db_conn.commit()


def _seed_ma_data(db_conn):
    """植入均線測試資料（至少 200 天以計算 ma200）。"""
    db_conn.execute("""
        INSERT INTO stock_meta (stock_id, stock_name) VALUES ('2330', '台積電')
    """)
    # 從 2025-09-01 開始植入 200 天資料
    from datetime import date, timedelta
    start = date(2025, 9, 1)
    for i in range(200):
        d = start + timedelta(days=i)
        db_conn.execute(
            "INSERT INTO stock_history (stock_id, date, open, high, low, close, volume, amount) "
            "VALUES ('2330', ?, ?, ?, ?, ?, 1000000, 100000000)",
            (d.isoformat(), 100+i, 105+i, 95+i, 102+i)
        )
    db_conn.commit()


# ── 籌碼策略輸出 contract ──

def test_chips_strategy_output_contract(db_conn, patch_db_path):
    """ChipsStrategy.analyze() 應回傳 strategy/stock_id/signal。"""
    from db_admin import create_tables, create_views
    from strategy.chips_strategy import ChipsStrategy

    create_tables(db_conn)
    create_views(db_conn)
    _seed_chip_data(db_conn)

    result = ChipsStrategy().analyze("2330")
    assert_strategy_contract(result)


# ── 均線策略輸出 contract ──

def test_ma_strategy_output_contract(db_conn, patch_db_path):
    """MAStrategy.analyze() 應回傳 strategy/stock_id/signal。"""
    from db_admin import create_tables, create_views
    from strategy.ma_strategy import MAStrategy

    create_tables(db_conn)
    create_views(db_conn)
    _seed_ma_data(db_conn)

    result = MAStrategy().analyze("2330")
    assert_strategy_contract(result)


# ── 型態策略輸出 contract ──

def test_pattern_strategy_output_contract(db_conn, patch_db_path):
    """PatternStrategy.analyze() 應回傳 strategy/stock_id/signal。"""
    from db_admin import create_tables, create_views
    from strategy.patterns_strategy import PatternStrategy

    create_tables(db_conn)
    create_views(db_conn)
    _seed_ma_data(db_conn)  # 用 200 天資料

    result = PatternStrategy().analyze("2330")
    assert_strategy_contract(result)


# ── 撐壓策略輸出 contract ──

def test_sr_strategy_output_contract(db_conn, patch_db_path):
    """SupportResistanceStrategy.analyze() 應回傳 strategy/stock_id/signal。"""
    from db_admin import create_tables, create_views
    from strategy.sr_analyzer import SupportResistanceStrategy

    create_tables(db_conn)
    create_views(db_conn)
    _seed_ma_data(db_conn)

    result = SupportResistanceStrategy().analyze("2330")
    assert_strategy_contract(result)
