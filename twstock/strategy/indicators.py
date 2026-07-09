#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
strategy/indicators.py — 指標自動刷新機制
確保策略分析前 stock_indicators 已有最新資料。
"""

import os
import sqlite3
import sys

# 確保 twstock 目錄在 path 中
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_TWSTOCK_DIR = os.path.abspath(os.path.join(_CURRENT_DIR, ".."))
if _TWSTOCK_DIR not in sys.path:
    sys.path.insert(0, _TWSTOCK_DIR)

from twstock.calculator import ATRCalculator, MACalculator, VWAPCalculator  # noqa: E402
from twstock.db import get_connection  # noqa: E402


def _writable_conn(db):
    """確保連線可寫入，若為唯讀則開新連線"""
    try:
        db.execute("CREATE TEMP TABLE IF NOT EXISTS _write_test (id INTEGER)")
        db.execute("DROP TABLE IF EXISTS _write_test")
        return db
    except sqlite3.OperationalError:
        return get_connection()


def refresh_indicators(stock_id, db=None):
    """
    重新計算指定股票的 MA/ATR/VWAP 指標並寫入 stock_indicators。
    回傳 dict 包含各 Calculator 寫入的筆數。
    """
    if db is None:
        db = get_connection()
    db = _writable_conn(db)

    results = {}
    try:
        results["ma"] = MACalculator(db=db).calculate(stock_id)
    except Exception as e:
        results["ma"] = f"error: {e}"

    try:
        results["atr"] = ATRCalculator(db=db).calculate(stock_id)
    except Exception as e:
        results["atr"] = f"error: {e}"

    try:
        results["vwap"] = VWAPCalculator(db=db).calculate(stock_id)
    except Exception as e:
        results["vwap"] = f"error: {e}"

    db.commit()
    return results


def ensure_indicators(stock_id, db=None):
    """
    檢查指定股票最新日 K 是否已有指標，若無則執行刷新。
    回筆寫入的指標筆數 (0 表示已有資料無需刷新)。
    """
    if db is None:
        db = get_connection()

    # 檢查最新日的 ma200 是否存在
    row = db.execute(
        "SELECT ma200 FROM stock_indicators WHERE stock_id = ? " "ORDER BY date DESC LIMIT 1",
        (stock_id,),
    ).fetchone()

    if row is not None and row[0] is not None:
        return 0  # 已有資料

    # 無資料 → 刷新
    result = refresh_indicators(stock_id, db)
    total = sum(v for v in result.values() if isinstance(v, int))
    return total


def ensure_indicators_all(db=None):
    """
    檢查所有股票最新日 K 是否已有指標，若無則執行刷新。
    回傳已刷新的股票數量。
    """
    if db is None:
        db = get_connection()
    db = _writable_conn(db)  # 預先轉換，避免迴圈內每筆都開新連線

    # 找出需要刷新的股票 (最新日無 ma200 者)
    rows = db.execute("""
        SELECT DISTINCT h.stock_id
        FROM stock_history h
        WHERE h.date = (SELECT MAX(date) FROM stock_history)
          AND NOT EXISTS (
              SELECT 1 FROM stock_indicators i
              WHERE i.stock_id = h.stock_id AND i.date = h.date AND i.ma200 IS NOT NULL
          )
    """).fetchall()

    refreshed = 0
    for (stock_id,) in rows:  # noqa: PERF203 — 刻意保留：單股刷新失敗不可中斷迴圈
        try:
            refresh_indicators(stock_id, db)
            refreshed += 1
        except Exception:
            pass

    return refreshed


def refresh_indicators_all(db=None):
    """
    強制重新計算所有股票的指標 (全量刷新)。
    回傳 dict：{stock_id: count}
    """
    if db is None:
        db = get_connection()
    db = _writable_conn(db)

    cur = db.execute("SELECT DISTINCT stock_id FROM stock_history")
    stock_ids = [row[0] for row in cur.fetchall()]

    results = {}
    for stock_id in stock_ids:  # noqa: PERF203 — 刻意保留：單股刷新失败要記 error 而非中斷
        try:
            results[stock_id] = refresh_indicators(stock_id, db)
        except Exception as e:
            results[stock_id] = {"error": str(e)}

    db.commit()
    return results


if __name__ == "__main__":
    conn = get_connection()
    print("🔄 檢查所有股票指標...")
    refreshed = ensure_indicators_all(conn)
    print(f"✅ 已刷新 {refreshed} 檔股票的指標")
    conn.close()
