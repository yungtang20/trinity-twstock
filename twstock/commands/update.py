# -*- coding: utf-8 -*-
"""update 命令：單股歷史資料更新。"""
from __future__ import annotations

from datetime import datetime

import pandas as pd

from twstock.fetcher import DataFetcher
from twstock.processor import DataProcessor
from twstock.official.dividend_crawler import fetch_dividend_events
from twstock.official.tdcc import fetch_tdcc_historical
from twstock.terminal import console


def update_single_stock(stock_id: str, token: str | None = None) -> bool:
    """更新單一股票所有資料。成功回傳 True。"""
    console.print(f"[cyan]開始更新 {stock_id} 歷史資料...[/cyan]")
    fetcher = DataFetcher()
    processor = DataProcessor()

    df_price = fetcher.fetch_history_price(stock_id, start_date="2020-01-01")
    if df_price.empty:
        console.print(f"[red]❌ 無法取得 {stock_id} 價格資料[/red]")
        return False
    df_price["stock_id"] = stock_id

    try:
        year_start = datetime.now().strftime("%Y-01-01")
        year_end = datetime.now().strftime("%Y-%m-%d")
        div_df = fetch_dividend_events(year_start, year_end)
        div_events = div_df[div_df["stock_id"] == stock_id] if not div_df.empty else pd.DataFrame()
    except Exception as e:
        console.print(f"[yellow]⚠️ 除權息抓取失敗: {e}，跳過[/yellow]")
        div_events = pd.DataFrame()

    if not div_events.empty:
        processor.upsert_dividend_events(div_events)
    processor.upsert_history(df_price)

    inst = fetcher.fetch_institutional(stock_id)
    if not inst.empty:
        inst["stock_id"] = stock_id
        processor.upsert_institutional(inst)

    shr = fetcher.fetch_shareholding(stock_id)
    if not shr.empty:
        shr["stock_id"] = stock_id
        processor.upsert_shareholding(shr)

    try:
        tdcc_df = fetch_tdcc_historical(weeks=1)
        tdcc = tdcc_df[tdcc_df["stock_id"] == stock_id] if not tdcc_df.empty else pd.DataFrame()
    except Exception as e:
        console.print(f"[yellow]⚠️ TDCC 抓取失敗: {e}，跳過[/yellow]")
        tdcc = pd.DataFrame()

    if not tdcc.empty:
        processor.upsert_tdcc(tdcc)

    stock_meta = fetcher.fetch_stock_meta()
    if not stock_meta.empty:
        stock_meta = stock_meta[stock_meta["stock_id"] == stock_id]
        if not stock_meta.empty:
            processor.upsert_meta(stock_meta)

    console.print(f"[green]✅ {stock_id} 資料更新完成[/green]")
    return True


def execute(args) -> None:
    """args 需具備 stock_id 與選擇性 token 屬性。"""
    update_single_stock(args.stock_id, getattr(args, "token", None))
