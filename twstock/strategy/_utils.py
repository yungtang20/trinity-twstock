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


def clear_screen() -> None:
    """Clear terminal screen (cross-platform)."""
    os.system('cls' if os.name == 'nt' else 'clear')


def get_stock_name(conn: sqlite3.Connection, stock_id: str, fallback: dict = None) -> str:
    """Get stock name from database, with optional fallback dict."""
    try:
        row = conn.execute(
            "SELECT stock_name FROM stock_meta WHERE stock_id = ?", (stock_id,)
        ).fetchone()
        if row and row[0]:
            return row[0]
    except Exception:
        pass
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
            console.print(f"\n╔═" * w + "╗")
            console.print(f"║ {title:^{w-2}} ║")
            console.print(f"╚═" * w + "╝")
        else:
            console.print(f"\n═" * w)
            console.print(f"  {title}")
            console.print(f"═" * w)
    else:
        if is_detail:
            print(f"\n╔═" * w + "╗")
            print(f"║ {title:^{w-2}} ║")
            print(f"╚═" * w + "╝")
        else:
            print(f"\n═" * w)
            print(f"  {title}")
            print(f"═" * w)


def fetch_klines(conn: sqlite3.Connection, stock_id: str, limit: int = 512, include_amount: bool = False) -> pd.DataFrame:
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
        f"SELECT {cols} FROM klines_indicators WHERE stock_id = ? ORDER BY date ASC LIMIT ?",
        conn,
        params=(stock_id, limit),
    )
    return df
