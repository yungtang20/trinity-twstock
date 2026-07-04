# -*- coding: utf-8 -*-
"""dividend 命令：抓取除權息資料。"""

from __future__ import annotations

from twstock.official import fetch_dividend_events, upsert_dividend_events
from twstock.terminal import console


def execute(args) -> None:
    """args 需具備 start_date / end_date 屬性。"""
    start_date = getattr(args, "start_date", None)
    end_date = getattr(args, "end_date", None)

    if not start_date or not end_date:
        console.print("[red]請提供 --start-date 和 --end-date 參數[/red]")
        return

    console.print(f"[cyan]抓取除權息資料：{start_date} ~ {end_date}[/cyan]")
    try:
        df = fetch_dividend_events(start_date, end_date)
        if df.empty:
            console.print("[yellow]此期間內無除權息資料[/yellow]")
            return
        upsert_dividend_events(df)
        console.print(f"[green]✅ 已寫入 {len(df)} 筆除權息事件[/green]")
    except Exception as e:
        console.print(f"[red]❌ 處理除權息資料時發生錯誤: {e}[/red]")
