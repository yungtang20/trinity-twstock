#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
klines_helper.py — 統一的 K 線資料擷取輔助模組 [AI MOD]
所有策略模組共用此 helper 來從 stock_history 表讀取資料。

重要：這個模組不得直接或間接 import twstock/polars.py（它會遞歸爆炸）。
改為回傳 pandas DataFrame，由各策略模組自行轉換。
"""

import sqlite3
import pandas as pd


def fetch_klines(
    conn: sqlite3.Connection,
    stock_id: str,
    limit: int = 512,
    include_amount: bool = False,
) -> pd.DataFrame:
    """從 stock_history 表擷取 K 線資料，回傳 pandas DataFrame。

    各策略模組得到 pandas DataFrame 後，用 pl.from_pandas(df) 轉為 polars。
    但考量到 twstock/polars.py 是相容層，直接用 pandas 亦可。

    Args:
        conn: SQLite 連線
        stock_id: 股票代號 (如 '2330')
        limit: 最多回傳筆數 (預設 512)
        include_amount: 是否包含成交金額欄位

    Returns:
        pandas DataFrame，含 date, open, high, low, close, volume
        (若 include_amount=True 則額外包含 amount 欄位)
    """
    columns = "date, open, high, low, close, volume"
    if include_amount:
        columns = "date, open, high, low, close, volume, amount"

    query = (
        f"SELECT {columns} FROM stock_history "
        f"WHERE stock_id = ? ORDER BY date DESC LIMIT ?"
    )

    df = pd.read_sql_query(query, conn, params=(stock_id, limit))

    if df.empty:
        return df

    # 按日期升序排列
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)

    return df


def fetch_klines_with_id(
    conn: sqlite3.Connection,
    stock_id: str,
    limit: int = 512,
) -> pd.DataFrame:
    """與 fetch_klines 相同，但額外包含 stock_id 欄位。"""
    df = fetch_klines(conn, stock_id, limit, include_amount=True)
    if not df.empty:
        df['stock_id'] = stock_id
    return df