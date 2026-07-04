# -*- coding: utf-8 -*-
"""indicators 命令：最近 N 日價量查詢。"""
from __future__ import annotations

import pandas as pd

from twstock.db import get_connection
from twstock.terminal import console
from twstock.utils import get_stock_name


def execute(args) -> None:
    """args 需具備 stock_id 屬性。"""
    stock_id = args.stock_id
    stock_name = get_stock_name(stock_id)

    with get_connection(readonly=True) as conn:
        df = pd.read_sql(
            "SELECT date, close FROM klines "
            "WHERE stock_id = ? ORDER BY date DESC LIMIT 5",
            conn, params=(stock_id,),
        )
    if df.empty:
        console.print(f"[yellow]⚠️ 無 {stock_id} 資料，請先執行 update[/yellow]")
        return

    df = df.sort_values("date", ascending=True)
    console.print(f"\n{stock_id} {stock_name} 最近5日交易資料")
    console.print("日期        股號   股名   股價(收盤)")
    console.print("-" * 50)
    for _, row in df.iterrows():
        console.print(f"{row['date']}  {stock_id}  {stock_name}  {row['close']:8.2f}")
    console.print("")
