# -*- coding: utf-8 -*-
"""intraday 命令：盤中即時指標。"""
from __future__ import annotations

from datetime import datetime

import pandas as pd

from twstock.calculator import IndicatorEngine
from twstock.db import get_connection
from twstock.fetcher import DataFetcher
from twstock.utils import safe_float, safe_int
from twstock.terminal import console

# Forward declaration for type hint only
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from argparse import Namespace


def execute(args) -> None:
    """args 需具備 stock_id 與選擇性 token 屬性。"""
    from twstock.commands.update import update_single_stock

    stock_id = args.stock_id
    token = getattr(args, "token", None)

    fetcher = DataFetcher()
    engine = IndicatorEngine(stock_id, limit=300)
    if engine.df.empty:
        console.print("[yellow]⚠️ 無歷史資料，自動執行更新...[/yellow]")
        if not update_single_stock(stock_id, token):
            return
        engine = IndicatorEngine(stock_id, limit=300)

    intra = fetcher.fetch_intraday_snapshot(stock_id)
    if not intra or intra.get("z") == "-":
        console.print("[red]❌ 無法取得即時報價 (非交易時段或無資料)[/red]")
        return

    today_str = datetime.today().strftime("%Y-%m-%d")
    with get_connection(readonly=True) as conn:
        row = conn.execute(
            "SELECT 1 FROM dividend_events WHERE stock_id = ? AND date = ?",
            (stock_id, today_str),
        ).fetchone()
        has_div = row is not None
    if has_div:
        console.print("[yellow]⚠️ 今日為除權息交易日，盤中價格僅供參考[/yellow]")

    intra_row = {
        "date": pd.Timestamp.now(),
        "open": safe_float(intra.get("o")),
        "high": safe_float(intra.get("h")),
        "low": safe_float(intra.get("l")),
        "close": safe_float(intra.get("z")),
        "volume": safe_int(intra.get("v")),
    }
    df_intra = pd.DataFrame([intra_row])
    engine.df = pd.concat([engine.df, df_intra], ignore_index=True)
    df = engine.build()
    if df.empty:
        console.print("[yellow]⚠️ 無法計算指標[/yellow]")
        return
    latest = df.iloc[-1]
    console.print(f"[bold green]📈 {stock_id} 盤中即時指標[/bold green]")
    console.print(f"即時價: {latest['close']:.2f}  量: {latest['volume']}")
    console.print(
        f"SMA20: {latest['sma_20']:.2f}  MACD: {latest['macd']:.4f}  "
        f"法人淨買賣: {latest.get('institutional_net', 0):,}"
    )
