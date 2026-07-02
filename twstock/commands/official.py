# -*- coding: utf-8 -*-
"""official 命令：TWSE/TPEx 全市場官方資料抓取。"""
from __future__ import annotations

from twstock.official import update_official_daily, update_tdcc_weekly, update_tdcc_historical
from twstock.terminal import console


def execute(args) -> None:
    """args 需具備以下屬性（可選）：tdcc_only, days, date, with_tdcc, tdcc_weeks。"""
    if getattr(args, "tdcc_only", False):
        console.print("[cyan]抓取最新 TDCC 集保資料...[/cyan]")
        update_tdcc_weekly()
        return

    days = getattr(args, "days", 1)
    date_str = getattr(args, "date", None)
    auto_tdcc = getattr(args, "with_tdcc", False)
    tdcc_weeks = getattr(args, "tdcc_weeks", None)

    if tdcc_weeks is not None:
        console.print(f"[cyan]抓取最近 {tdcc_weeks} 週 TDCC 歷史資料...[/cyan]")
        update_tdcc_historical(tdcc_weeks)
        return

    if date_str:
        try:
            clean_date = date_str.replace("-", "")
            if len(clean_date) == 8 and clean_date.isdigit():
                d_int = int(clean_date)
                console.print(
                    f"[cyan]抓取指定日期 {d_int} 起 {days} 個交易日全市場官方資料...[/cyan]"
                )
                update_official_daily(d_int, days=days, auto_tdcc=auto_tdcc)
            else:
                console.print("[red]日期格式錯誤，請使用 YYYY-MM-DD 或 YYYYMMDD[/red]")
        except Exception as e:
            console.print(f"[red]日期解析錯誤: {e}[/red]")
    else:
        console.print(f"[cyan]抓取最近 {days} 個交易日全市場官方資料...[/cyan]")
        update_official_daily(None, days=days, auto_tdcc=auto_tdcc)
