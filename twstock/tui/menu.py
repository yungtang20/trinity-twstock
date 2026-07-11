# -*- coding: utf-8 -*-
"""互動式子選單流程（daily / historical / maintenance）。"""

from __future__ import annotations

import os
import sqlite3

from twstock.db import get_connection
from twstock.input_helper import get_interactive_input, setup_console_encoding
from twstock.official import (
    fetch_dividend_events,
    get_nth_trading_day_back,
    get_today_suspended,
    run_dividend_daily,
    update_official_daily,
    update_tdcc_historical,
    upsert_dividend_events,
)
from twstock.terminal import console

# Windows UTF-8
setup_console_encoding()


# ══════════════════════════════════════════════════════════════
# 1. 每日資料更新
# ══════════════════════════════════════════════════════════════
def run_daily_update() -> None:
    """每日資料更新子選單。"""
    os.system("cls" if os.name == "nt" else "clear")
    from rich import box
    from rich.align import Align
    from rich.panel import Panel
    from rich.text import Text

    console.print(
        Panel(
            Align.center(
                Text(
                    "☀️ 每日資料更新 (最新價量、法人、集保、除權息、處置股票)",
                    style="bold yellow",
                )
            ),
            box=box.DOUBLE,
            border_style="yellow",
        )
    )
    console.print("[cyan]>> 正在從官方網站抓取最新交易日資料與集保數據...[/cyan]")

    # 處置股票
    try:
        get_today_suspended()
    except Exception as e:
        console.print(f"[yellow]⚠️ 處置股票抓取失敗: {e}[/yellow]")

    update_official_daily(days=1, auto_tdcc=True)
    console.print("[green]✅ 每日資料更新完成！[/green]")

    # 顯示最新資料進度摘要
    _show_data_progress_summary()

    input("\n按 Enter 鍵返回主選單...")


def _show_data_progress_summary() -> None:
    """顯示三大類資料的最新進度摘要。"""
    from twstock.db import get_connection

    try:
        with get_connection(readonly=True) as conn:
            row_t = conn.execute("SELECT MAX(date), COUNT(*) FROM stock_history").fetchone()
            row_i = conn.execute("SELECT MAX(date), COUNT(*) FROM institutional_data").fetchone()
            # TDCC 可能尚未建立（若無自動補爬），用 shareholding_unified
            try:
                row_d = conn.execute(
                    "SELECT MAX(date), COUNT(*) FROM shareholding_unified"
                ).fetchone()
            except Exception:
                row_d = (None, 0)
        console.print("\n[cyan]📊 最新資料進度:[/cyan]")
        console.print(f"  [white]價量行情: {row_t[0]} ({row_t[1]:,} 筆)[/white]")
        console.print(f"  [white]三大法人: {row_i[0]} ({row_i[1]:,} 筆)[/white]")
        console.print(f"  [white]集保數據: {row_d[0]} ({row_d[1]:,} 筆)[/white]")
    except Exception as e:
        console.print(f"[dim]  (無法取得進度: {e})[/dim]")


def run_historical_update_menu() -> None:
    """歷史資料更新子選單。"""
    while True:
        os.system("cls" if os.name == "nt" else "clear")
        from rich import box
        from rich.align import Align
        from rich.panel import Panel
        from rich.table import Table
        from rich.text import Text

        console.print(
            Panel(
                Align.center(
                    Text(
                        "📅 歷史資料更新中心 (補齊歷史價量、集保與除權息)",
                        style="bold yellow",
                    )
                ),
                box=box.DOUBLE,
                border_style="yellow",
            )
        )

        t = Table(box=box.SIMPLE, show_header=True, expand=False, padding=(0, 2))
        t.add_column("Key", style="bold cyan")
        t.add_column("抓取任務", style="white")
        t.add_column("說明", style="dim")
        t.add_row("1", "同步幾個歷史交易日", "快速同步多個交易日歷史官方價量與法人")
        t.add_row("2", "抓取歷史 N 週 TDCC 集保", "下載並建立大股東集保分散表歷史")
        t.add_row("3", "同步除權息事件", "爬取特定區間除權息事件並寫入資料庫")
        t.add_row("4", "抓取當年除權息公告", "爬取今年除權息預告並寫入資料庫")
        t.add_row("5", "檢測零量價與異常", "掃描最新交易日中非處置股票卻零量零價的異常名單")
        t.add_row("Enter", "返回主選單", "")

        console.print(Align.left(t))
        ch = _get_interactive_input("\n🔍 選擇任務: ", menu_keys="12345")

        if not ch:
            break
        elif ch == "1":
            days_str = input("輸入下載交易天數 (如 5): ").strip()
            if days_str.isdigit():
                update_official_daily(None, days=int(days_str), auto_tdcc=True)
        elif ch == "2":
            weeks_str = input("輸入週數 (如 5): ").strip()
            if weeks_str.isdigit():
                update_tdcc_historical(int(weeks_str))
        elif ch == "3":
            days_str = input("請輸入回溯交易天數 (如 60，預設 60): ").strip()
            days = int(days_str) if days_str.isdigit() else 60
            end_dt = get_nth_trading_day_back(0)
            start_dt = get_nth_trading_day_back(days)
            start_date = start_dt.strftime("%Y-%m-%d")
            end_date = end_dt.strftime("%Y-%m-%d")
            console.print(
                f"\n[cyan]>> 同步區間: {start_date} ~ {end_date}（過去 {days} 個交易日）[/cyan]"
            )
            console.print("[cyan]>> 開始同步除權息事件...[/cyan]")
            try:
                df = fetch_dividend_events(start_date, end_date)
                if not df.empty:
                    upsert_dividend_events(df)
                    console.print(f"[green]✅ 已更新 {len(df)} 筆除權息事件[/green]")
                else:
                    console.print("[yellow]⚠️ 此區間無除權息資料[/yellow]")
            except Exception as e:
                console.print(f"[red]❌ 發生錯誤: {e}[/red]")
        elif ch == "4":
            console.print("\n[cyan]>> 開始抓取當年除權息公告...[/cyan]")
            try:
                run_dividend_daily()
                console.print("[green]✅ 當年除權息公告抓取完成！[/green]")
            except Exception as e:
                console.print(f"[red]❌ 發生錯誤: {e}[/red]")
            input("\n按 Enter 鍵繼續...")
        elif ch == "5":
            console.print("\n[cyan]>> 開始檢查最近交易日資料異常...[/cyan]")
            try:
                suspended = get_today_suspended()
                _check_zero_volume_anomalies(suspended)
            except Exception as e:
                console.print(f"[red]❌ 發生錯誤: {e}[/red]")
            input("\n按 Enter 鍵繼續...")


def _check_zero_volume_anomalies(suspended: set | list) -> None:
    """檢查最新交易日零成交量異常。"""
    conn = get_connection(readonly=True)
    try:
        latest = conn.execute("SELECT MAX(date) FROM stock_history").fetchone()[0]
        if not latest:
            return

        rows = conn.execute(
            "SELECT stock_id, close FROM stock_history "
            "WHERE date = ? AND volume = 0 ORDER BY stock_id",
            (latest,),
        ).fetchall()

        if not rows:
            console.print(f"  [green]✅ 最新交易日 ({latest}) 所有股票均有成交量[/green]")
            return

        normal_zero = set()
        anomaly_zero = set()
        for r in rows:
            sid = r[0]
            if sid in suspended:
                normal_zero.add(sid)
            else:
                anomaly_zero.add(sid)

        if normal_zero:
            console.print(
                f"  [cyan]ℹ️ 暫停交易/處置股票 ({latest}): "
                f"{len(normal_zero)} 支 (零量價正常)[/cyan]"
            )

        if anomaly_zero:
            console.print(
                f"  [yellow]⚠️ 非處置股票但零量價 ({latest}): " f"{len(anomaly_zero)} 支[/yellow]"
            )
            preview = ", ".join(sorted(anomaly_zero)[:15])
            suffix = "..." if len(anomaly_zero) > 15 else ""
            console.print(f"     {preview}{suffix}")
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════
# 4. 資料庫維護
# ══════════════════════════════════════════════════════════════
def run_db_maintenance() -> None:
    """VACUUM 資料庫維護"""
    os.system("cls" if os.name == "nt" else "clear")
    print("=" * 60)
    print("資料庫維護")
    print("=" * 60)
    print("⏳ 正在執行資料庫重組與壓縮，請稍候（期間請勿關閉程式）...")

    try:
        conn = get_connection()
        try:
            conn.execute("VACUUM")
            print("\n✅ 資料庫維護完成！")
        finally:
            conn.close()
    except sqlite3.OperationalError as e:
        if "locked" in str(e).lower():
            print(
                "\n❌ 維護失敗：資料庫被鎖定。請關閉其他可能使用資料庫的程式"
                "（如其他更新排程或資料庫檢視器）後再試一次。"
            )
        else:
            print(f"\n❌ 維護失敗：{e}")
    except Exception as e:
        print(f"\n❌ 維護失敗：{e}")

    input("\n按 Enter 鍵返回主選單...")


# ── 內部輸入工具：委派至 input_helper（統一實作）──────────
def _get_interactive_input(prompt: str = "\n🔍 指令: ", menu_keys: str = "01234") -> str:
    """單鍵輸入（委派至 twstock.input_helper.get_interactive_input）。"""
    result = get_interactive_input(prompt=prompt, menu_keys=menu_keys)
    # 統一 ESC 行為：input_helper 回傳 "0"，menu.py 預期 ""（break 信號）
    return "" if result == "0" else result
