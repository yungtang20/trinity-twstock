#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
strategy/indicators.py — 指標自動刷新機制
確保策略分析前 stock_indicators 已有最新資料。
"""

from __future__ import annotations

import logging
import sqlite3

import pandas as pd

# 確保 twstock 目錄在 path 中
from twstock.calculator import ATRCalculator, MACalculator, VWAPCalculator
from twstock.db import get_connection
from twstock.db_admin import create_tables

logger = logging.getLogger(__name__)


def _writable_conn(db: sqlite3.Connection | None) -> sqlite3.Connection:
    """確保連線可寫入，若為唯讀則開新連線"""
    if db is None:
        return get_connection()
    try:
        db.execute("SAVEPOINT _write_test")
        db.execute("INSERT INTO stock_indicators (stock_id, date) VALUES ('_w_', '2000-01-01')")
    except sqlite3.OperationalError:
        return get_connection()
    else:
        db.execute("ROLLBACK TO _write_test")
        db.execute("RELEASE _write_test")
        return db


def refresh_indicators(stock_id: str, db: sqlite3.Connection | None = None) -> dict[str, int | str]:
    """
    重新計算指定股票的 MA/ATR/VWAP 指標並寫入 stock_indicators。
    回傳 dict 包含各 Calculator 寫入的筆數。
    """
    owns_connection = db is None
    if db is None:
        db = get_connection()
    supplied_db = db
    db = _writable_conn(db)
    owns_connection = owns_connection or db is not supplied_db

    results: dict[str, int | str] = {}
    try:
        try:
            results["ma"] = MACalculator(db=db).calculate(stock_id, _commit=False)
        except Exception as e:
            results["ma"] = f"error: {e}"

        try:
            results["atr"] = ATRCalculator(db=db).calculate(stock_id, _commit=False)
        except Exception as e:
            results["atr"] = f"error: {e}"

        try:
            results["vwap"] = VWAPCalculator(db=db).calculate(stock_id, _commit=False)
        except Exception as e:
            results["vwap"] = f"error: {e}"

        db.commit()
        return results
    finally:
        if owns_connection:
            db.close()


def ensure_indicators(stock_id: str, db: sqlite3.Connection | None = None) -> int:
    """
    檢查指定股票最新日 K 是否已有指標，若無則執行刷新。
    回筆寫入的指標筆數 (0 表示已有資料無需刷新)。
    """
    owns_connection = db is None
    if db is None:
        db = get_connection()

    try:
        # 最新行情日只要已有指標列就視為處理完成。短歷史股票的 ma200
        # 合理為 NULL，不能因此在每次呼叫時重算完整歷史。
        row = db.execute(
            """
            SELECT i.stock_id
            FROM stock_history h
            LEFT JOIN stock_indicators i
              ON i.stock_id = h.stock_id AND i.date = h.date
            WHERE h.stock_id = ?
            ORDER BY h.date DESC
            LIMIT 1
            """,
            (stock_id,),
        ).fetchone()

        if row is None or row[0] is not None:
            return 0  # 已有資料

        # 無資料 → 刷新
        result = refresh_indicators(stock_id, db)
        return sum(v for v in result.values() if isinstance(v, int))
    finally:
        if owns_connection:
            db.close()


def ensure_indicators_all(db: sqlite3.Connection | None = None) -> int:
    """
    檢查所有股票最新日 K 是否已有指標，若無則執行刷新。
    回傳已刷新的股票數量。
    """
    owns_connection = db is None
    if db is None:
        db = get_connection()
    supplied_db = db
    db = _writable_conn(db)  # 預先轉換，避免迴圈內每筆都開新連線
    owns_connection = owns_connection or db is not supplied_db
    create_tables(db)

    # 找出最新行情日尚無任何指標列的股票。ma200 為 NULL 可能只是歷史
    # 不足 200 日，不能視為未處理。
    rows = db.execute("""
        SELECT DISTINCT h.stock_id
        FROM stock_history h
        WHERE h.date = (SELECT MAX(date) FROM stock_history)
          AND NOT EXISTS (
              SELECT 1 FROM stock_indicators i
              WHERE i.stock_id = h.stock_id AND i.date = h.date
          )
    """).fetchall()

    refreshed = 0
    try:
        stock_ids = [str(row[0]) for row in rows]
        chunk_size = 100
        for start in range(0, len(stock_ids), chunk_size):
            chunk = stock_ids[start : start + chunk_size]
            placeholders = ",".join("?" for _ in chunk)
            history = pd.read_sql_query(
                "SELECT stock_id, date, open, high, low, close, volume, amount "
                f"FROM stock_history WHERE stock_id IN ({placeholders}) "
                "ORDER BY stock_id, date",
                db,
                params=chunk,
            )
            for stock_id, frame in history.groupby("stock_id", sort=False):
                try:
                    MACalculator(db).calculate(
                        str(stock_id), frame, _commit=False, _ensure_schema=False
                    )
                    ATRCalculator(db).calculate(
                        str(stock_id), frame, _commit=False, _ensure_schema=False
                    )
                    VWAPCalculator(db).calculate(
                        str(stock_id), frame, _commit=False, _ensure_schema=False
                    )
                    refreshed += 1
                except Exception as exc:
                    logger.warning("indicator refresh failed for %s: %s", stock_id, exc)
        db.commit()
        return refreshed
    except Exception:
        db.rollback()
        raise
    finally:
        if owns_connection:
            db.close()


if __name__ == "__main__":
    conn = get_connection()
    print("🔄 檢查所有股票指標...")
    refreshed = ensure_indicators_all(conn)
    print(f"✅ 已刷新 {refreshed} 檔股票的指標")
    conn.close()
