# -*- coding: utf-8 -*-
"""
_utils.py — 策略模組共用工具函式

所有 strategy/*.py 檔案應從此模組匯入共用工具，避免重複實作。
"""

import os
import sqlite3
import warnings
from typing import Optional

import pandas as pd

warnings.filterwarnings("ignore")


# 清幕：統一使用 input_controller 版本（避免重複實作）
from twstock.input_helper import clear_screen  # noqa: F401  (re-export for backwards compat)


def _lookup_stock_name(conn: sqlite3.Connection, stock_id: str) -> Optional[str]:
    """內部實作：從 stock_meta 查名稱，失敗回傳 None。"""
    try:
        row = conn.execute(
            "SELECT stock_name FROM stock_meta WHERE stock_id = ?", (stock_id,)
        ).fetchone()
        if row and row[0]:
            return row[0]
    except Exception:
        pass
    return None


def get_stock_name(conn: sqlite3.Connection, stock_id: str, fallback: Optional[dict] = None) -> str:
    """Get stock name from database, with optional fallback dict."""
    name = _lookup_stock_name(conn, stock_id)
    if name:
        return name
    if fallback and stock_id in fallback:
        return fallback[stock_id]
    return "-"


def render_header(title: str, is_detail: bool = False, console=None) -> None:
    """Render a box-drawing header.

    Args:
        title: Header text
        is_detail: If True, use double-border box; else simple line
        console: Rich console instance (rconsole or console). Falls back to print.
    """
    try:
        w = min(65, os.get_terminal_size().columns)
    except Exception:
        w = 65

    if console:
        if is_detail:
            console.print("\n╔═" * w + "╗")
            console.print(f"║ {title:^{w-2}} ║")
            console.print("╚═" * w + "╝")
        else:
            console.print("\n═" * w)
            console.print(f"  {title}")
            console.print("═" * w)
    else:
        if is_detail:
            print("\n╔═" * w + "╗")
            print(f"║ {title:^{w-2}} ║")
            print("╚═" * w + "╝")
        else:
            print("\n═" * w)
            print(f"  {title}")
            print("═" * w)


def fetch_klines(
    conn: sqlite3.Connection, stock_id: str, limit: int = 512, include_amount: bool = False
) -> pd.DataFrame:
    """Fetch OHLCV data from klines view.

    Args:
        conn: Database connection
        stock_id: Stock code (e.g. '2330')
        limit: Max rows to fetch
        include_amount: Whether to include amount column

    Returns:
        DataFrame with columns: date, open, high, low, close, volume[, amount]
    """
    cols = "date, open, high, low, close, volume"
    if include_amount:
        cols += ", amount"
    df = pd.read_sql(
        f"SELECT {cols} FROM klines_indicators WHERE stock_id = ? ORDER BY date DESC LIMIT ?",
        conn,
        params=(stock_id, limit),
    )
    # ponytail: DESC LIMIT 取最新 N 筆，再 sort 回 ASC 讓 iloc[-1]=最新
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    return df
