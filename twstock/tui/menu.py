# -*- coding: utf-8 -*-
"""互動式子選單流程（daily / historical / official / maintenance）。"""
from __future__ import annotations

import os
import sys

from twstock.commands.official import execute as official_execute
from twstock.commands.update import update_single_stock
from twstock.db import get_connection
from twstock.db_admin import init_db, migrate_db
from twstock.official.dividend_daily import run_dividend_daily
from twstock.official.suspended import get_today_suspended
from twstock.strategy.strategies import run_strategy_cli
from twstock.utils import get_token, to_roc_date
from twstock.terminal import console


# ══════════════════════════════════════════════════════════════
# 1. 每日資料更新
# ══════════════════════════════════════════════════════════════
def run_daily_update() -> None:
    """每日資料更新子選單。"""
    os.system("cls" if os.name == "nt" else "clear")
    from rich.align import Align
    from rich.panel import Panel
    from rich.text import Text
    from rich import box

    console.print(Panel(
        Align.center(Text(
            "☀️ 每日資料更新 (最新價量、法人、集保、除權息、處置股票)",
            style="bold yellow",
        )),
        box=box.DOUBLE, border_style="yellow",
    ))
    console.print("[cyan]>> 正在從官方網站抓取最新交易日資料與集保數據...[/cyan]")

    # 處置股票
    suspended_stocks = set()
    try:
        suspended_stocks = get_today_suspended()
    except Exception as e:
        console.print(f"[yellow]⚠️ 處置股票抓取失敗: {e}[/yellow]")

    # 使用 official 套件執行每日更新
    from twstock.official import update_official_daily, update_tdcc_weekly
    update_official_daily(days=1, auto_tdcc=True)
    console.print("[green]✅ 每日資料更新完成！[/green]")
    input("\n按 Enter 鍵返回主選單...")


# ══════════════════════════════════════════════════════════════
# 2. 歷史資料更新
# ══════════════════════════════════════════════════════════════
def run_historical_update_menu() -> None:
    """歷史資料更新子選單。"""
    os.system("cls" if os.name == "nt" else "clear")
    from rich.align import Align
    from rich.panel import Panel
    from rich.text import Text
    from rich import box

    console.print(Panel(
        Align.center(Text(
            "📚 歷史資料更新（多個交易日、集保、除權息）",
            style="bold yellow",
        )),
        box=box.DOUBLE, border_style="yellow",
    ))

    days_str = input("請輸入要更新的交易日數量（預設 5）: ").strip()
    days = int(days_str) if days_str.isdigit() else 5

    from twstock.official import update_official_daily
    update_official_daily(days=days, auto_tdcc=True)
    console.print(f"[green]✅ 最近 {days} 個交易日資料更新完成！[/green]")
    input("\n按 Enter 鍵返回主選單...")


# ══════════════════════════════════════════════════════════════
# 4. 資料庫維護
# ══════════════════════════════════════════════════════════════
def run_db_maintenance() -> None:
    """VACUUM 資料庫維護。"""
    os.system("cls" if os.name == "nt" else "clear")
    from rich.align import Align
    from rich.panel import Panel
    from rich.text import Text
    from rich import box

    console.print(Panel(
        Align.center(Text("🔧 資料庫結構重整與維護", style="bold yellow")),
        box=box.DOUBLE, border_style="yellow",
    ))
    console.print("[cyan]>> 正在重整 SQLite 資料庫 (VACUUM)...[/cyan]")
    try:
        with get_connection() as conn:
            conn.execute("VACUUM")
        console.print("[green]✅ 資料庫結構優化與物理壓縮完成！[/green]")
    except Exception as e:
        console.print(f"[red]❌ 維護失敗: {e}[/red]")
    input("\n按 Enter 鍵返回主選單...")
