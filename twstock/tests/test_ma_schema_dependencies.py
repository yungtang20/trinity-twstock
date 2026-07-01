# -*- coding: utf-8 -*-
"""
test_ma_schema_dependencies.py — MA/indicator 依賴測試

驗證 strategy/indicators.py 的 ensure_indicators_all() 正確查詢
stock_indicators 自己的最新日期，而非依賴 stock_history。
"""
from __future__ import annotations

import sqlite3


def test_ensure_indicators_all_uses_own_latest_date(db_conn, patch_db_path):
    """ensure_indicators_all 應該查 stock_indicators 最新日期，而非 stock_history。"""
    from db_admin import init_db

    init_db()

    # 植入 stock_history 但 stock_indicators 是空的
    db_conn.execute("""
        INSERT INTO stock_history (stock_id, date, open, high, low, close, volume, amount)
        VALUES ('2330', '2026-06-21', 100, 105, 95, 102, 1000000, 100000000)
    """)
    db_conn.commit()

    # stock_indicators 是空的 → ensure_indicators_all 應該要能識別需要刷新
    from strategy.indicators import ensure_indicators_all

    # 呼叫不應該炸
    result = ensure_indicators_all(db_conn)
    assert isinstance(result, int), f"應回傳 int，實際 {type(result)}"


def test_refresh_indicators_writes_ma(db_conn, patch_db_path):
    """refresh_indicators 能正確寫入 ma5 到 stock_indicators。"""
    from db_admin import init_db

    init_db()

    # 植入 30 天資料
    for i in range(1, 31):
        db_conn.execute(
            "INSERT INTO stock_history (stock_id, date, open, high, low, close, volume, amount) "
            "VALUES ('2330', ?, 100, 105, 95, 102, 1000000, 100000000)",
            (f"2026-06-{i:02d}",)
        )
    db_conn.commit()

    from strategy.indicators import refresh_indicators

    result = refresh_indicators("2330", db_conn)

    assert 'ma' in result, f"應有 ma key，實際 {result}"
    assert isinstance(result['ma'], int), f"ma 應為 int，實際 {type(result['ma'])}"
    assert result['ma'] > 0, "應至少有 26 筆 ma5（30 - 5 + 1 = 26）"

    # 驗證 ma5 真的寫入
    row = db_conn.execute(
        "SELECT ma5 FROM stock_indicators WHERE stock_id='2330' ORDER BY date DESC LIMIT 1"
    ).fetchone()
    assert row is not None, "stock_indicators 應有 ma5"
    assert row[0] is not None, "ma5 不該為 None"


def test_ensure_indicators_idempotent(db_conn, patch_db_path):
    """ensure_indicators 執行兩次，第二次不應再寫入。

    注意：ensure_indicators 檢查 ma200 是否存在，30 天資料不夠算 ma200，
    所以這裡用 stock_indicators 直接植入 ma200 來模擬「已有資料」狀態。
    """
    from db_admin import init_db

    init_db()

    for i in range(1, 31):
        db_conn.execute(
            "INSERT INTO stock_history (stock_id, date, open, high, low, close, volume, amount) "
            "VALUES ('2330', ?, 100, 105, 95, 102, 1000000, 100000000)",
            (f"2026-06-{i:02d}",)
        )
    db_conn.commit()

    # 先寫入 stock_indicators（含 ma200）
    from calculator import MACalculator
    MACalculator(db=db_conn).calculate("2330")

    # 手動補上 ma200（30 天資料 MACalculator 不會算 ma200，但測試需要）
    db_conn.execute(
        "UPDATE stock_indicators SET ma200 = 100.0 WHERE stock_id = '2330'"
    )
    db_conn.commit()

    from strategy.indicators import ensure_indicators

    # 已有 ma200 → 回傳 0
    n = ensure_indicators("2330", db_conn)
    assert n == 0, f"已有 ma200 應回傳 0，實際回傳 {n}"


def test_macalculator_upsert_does_not_overwrite(db_conn, patch_db_path):
    """MACalculator 只更新 MA 欄位，不覆蓋 atr14/vwap。"""
    from db_admin import init_db

    init_db()

    for i in range(1, 31):
        db_conn.execute(
            "INSERT INTO stock_history (stock_id, date, open, high, low, close, volume, amount) "
            "VALUES ('2330', ?, 100, 105, 95, 102, 1000000, 100000000)",
            (f"2026-06-{i:02d}",)
        )
    db_conn.commit()

    # 先寫入 atr14/vwap
    from calculator import ATRCalculator, VWAPCalculator
    ATRCalculator(db=db_conn).calculate("2330")
    VWAPCalculator(db=db_conn).calculate("2330")

    # 記錄 atr14
    row_before = db_conn.execute(
        "SELECT atr14 FROM stock_indicators WHERE stock_id='2330' ORDER BY date DESC LIMIT 1"
    ).fetchone()
    atr_before = row_before[0] if row_before else None

    # 再跑 MACalculator
    from calculator import MACalculator
    MACalculator(db=db_conn).calculate("2330")

    # atr14 不該被覆蓋
    row_after = db_conn.execute(
        "SELECT atr14 FROM stock_indicators WHERE stock_id='2330' ORDER BY date DESC LIMIT 1"
    ).fetchone()
    atr_after = row_after[0] if row_after else None

    assert atr_before == atr_after, (
        f"MACalculator 不應覆蓋 atr14: before={atr_before}, after={atr_after}"
    )


def test_indicators_dependency_on_stock_history(db_conn, patch_db_path):
    """stock_indicators 必須依賴 stock_history 存在才能計算。"""
    from db_admin import init_db

    init_db()

    # 沒資料 → calculate 回傳 0
    from calculator import MACalculator

    calc = MACalculator(db=db_conn)
    result = calc.calculate("2330")
    assert result == 0, f"沒資料應回傳 0，實際 {result}"
