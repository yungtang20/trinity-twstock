# -*- coding: utf-8 -*-
"""互動式子選單流程（daily / historical / maintenance）。"""

from __future__ import annotations

import os
import sqlite3
from datetime import date, datetime

from twstock.db import get_connection
from twstock.db_maintenance import (
    DatabaseHealthReport,
    build_database_health_report,
    run_database_optimize,
    run_guarded_database_vacuum,
)
from twstock.input_helper import blocking_input, setup_console_encoding
from twstock.official import (
    fetch_dividend_events,
    get_recent_official_data_status,
    get_today_suspended,
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

    blocking_input("\n按 Enter 鍵返回主選單...")


def _show_data_progress_summary() -> None:
    """顯示三大類資料的最新進度摘要。"""
    from datetime import datetime
    from twstock.db import get_connection

    try:
        with get_connection(readonly=True) as conn:
            row_t = conn.execute("SELECT MAX(date), COUNT(*) FROM stock_history").fetchone()
            row_i = conn.execute("SELECT MAX(date), COUNT(*) FROM institutional_data").fetchone()
            # TDCC 可能尚未建立（若無自動補爬），用 shareholding_unified
            try:
                # ponytail: 在 SQL 層級排除未來日期，避免 2099-12-31 等髒資料污染 MAX(date)
                today_str = datetime.now().strftime("%Y-%m-%d")
                row_d = conn.execute(
                    "SELECT MAX(date), COUNT(*) FROM shareholding_unified WHERE date <= ?",
                    (today_str,),
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
    """Run the historical backfill and read-only quality menu."""
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
                        "📅 歷史資料更新中心（補缺口、指定重抓、資料健檢）",
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
        t.add_row("1", "檢查並補齊最近 N 日", "同時檢查價量與法人，只下載缺漏日期")
        t.add_row("2", "指定日期區間強制重抓", "重新下載區間內價量與法人，用於修正歷史資料")
        t.add_row("3", "更新最新一期 TDCC", "官方全市場 API 只提供最新一期，不假稱歷史補齊")
        t.add_row("4", "同步除權息事件", "可指定日期區間，預設同步本年度含未來事件")
        t.add_row("5", "唯讀資料品質檢查", "不刪資料，檢查缺漏、異常 OHLC 與 SQLite 結構")
        t.add_row("Enter", "返回主選單", "")

        console.print(Align.left(t))
        ch = blocking_input("\n🔍 輸入任務編號，再按 Enter（直接 Enter 返回）: ")

        if not ch:
            break
        elif ch == "1":
            days = _get_bounded_integer("輸入檢查交易天數（1～800，預設 20）：", 20, 1, 800)
            if days is not None:
                update_official_daily(None, days=days, auto_tdcc=False)
            blocking_input("\n按 Enter 鍵繼續...")
        elif ch == "2":
            start_date = blocking_input("起始日期 YYYY-MM-DD：")
            end_date = blocking_input("結束日期 YYYY-MM-DD：")
            date_range = _parse_date_range(start_date, end_date)
            if date_range is not None:
                start_value, end_value = date_range
                trading_days = _count_trading_days(start_value, end_value)
                if trading_days:
                    console.print(
                        f"[cyan]>> 將強制重抓 {start_value}～{end_value}，" f"共 {trading_days} 個交易日[/cyan]"
                    )
                    update_official_daily(
                        int(end_value.replace("-", "")),
                        days=trading_days,
                        force=True,
                        auto_tdcc=False,
                    )
                else:
                    console.print("[yellow]⚠️ 指定區間內沒有已登錄的交易日[/yellow]")
            blocking_input("\n按 Enter 鍵繼續...")
        elif ch == "3":
            update_tdcc_historical(1)
            blocking_input("\n按 Enter 鍵繼續...")
        elif ch == "4":
            year = date.today().year
            default_start = f"{year}-01-01"
            default_end = f"{year}-12-31"
            start_input = blocking_input(f"起始日期（預設 {default_start}）：") or default_start
            end_input = blocking_input(f"結束日期（預設 {default_end}）：") or default_end
            date_range = _parse_date_range(start_input, end_input)
            if date_range is None:
                blocking_input("\n按 Enter 鍵繼續...")
                continue
            start_value, end_value = date_range
            console.print(f"[cyan]>> 同步除權息事件：{start_value}～{end_value}[/cyan]")
            try:
                df = fetch_dividend_events(start_value, end_value)
                if not df.empty:
                    upsert_dividend_events(df)
                    console.print(f"[green]✅ 已更新 {len(df)} 筆除權息事件[/green]")
                else:
                    console.print("[yellow]⚠️ 此區間無除權息資料[/yellow]")
            except Exception as e:
                console.print(f"[red]❌ 發生錯誤: {e}[/red]")
            blocking_input("\n按 Enter 鍵繼續...")
        elif ch == "5":
            console.print("\n[cyan]>> 執行唯讀資料品質檢查，不會修改或刪除資料...[/cyan]")
            try:
                _render_historical_quality_report()
            except Exception as e:
                console.print(f"[red]❌ 發生錯誤: {e}[/red]")
            blocking_input("\n按 Enter 鍵繼續...")


def _get_bounded_integer(prompt: str, default: int, minimum: int, maximum: int) -> int | None:
    """Read an Enter-confirmed bounded integer and show validation feedback."""
    value = blocking_input(prompt)
    if not value:
        return default
    if not value.isdigit() or not minimum <= int(value) <= maximum:
        console.print(f"[yellow]⚠️ 請輸入 {minimum}～{maximum} 的整數[/yellow]")
        return None
    return int(value)


def _parse_date_range(start_value: str, end_value: str) -> tuple[str, str] | None:
    """Validate and normalize an inclusive ISO date range."""
    try:
        start_date = datetime.strptime(start_value, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_value, "%Y-%m-%d").date()
    except ValueError:
        console.print("[yellow]⚠️ 日期格式錯誤，請使用 YYYY-MM-DD[/yellow]")
        return None
    if start_date > end_date:
        console.print("[yellow]⚠️ 起始日期不可晚於結束日期[/yellow]")
        return None
    return start_date.isoformat(), end_date.isoformat()


def _count_trading_days(start_date: str, end_date: str) -> int:
    """Count registered open sessions in one indexed SQLite query."""
    connection = get_connection(readonly=True)
    try:
        return int(
            connection.execute(
                "SELECT COUNT(*) FROM stock_trading_calendar " "WHERE is_open = 1 AND date BETWEEN ? AND ?",
                (start_date, end_date),
            ).fetchone()[0]
        )
    finally:
        connection.close()


def _render_historical_quality_report(days: int = 250) -> None:
    """Render read-only market completeness and known-corruption diagnostics."""
    statuses = get_recent_official_data_status(days=days)
    quote_gaps = [str(item["date"]) for item in statuses if not item["quotes_complete"]]
    institutional_gaps = [str(item["date"]) for item in statuses if not item["institutional_complete"]]
    console.print(f"  檢查範圍: 最近 {len(statuses)} 個交易日")
    console.print(
        f"  價量缺漏/不完整: {len(quote_gaps)} 天" + (f"（{', '.join(quote_gaps[:8])}）" if quote_gaps else "")
    )
    console.print(
        f"  法人缺漏/不完整: {len(institutional_gaps)} 天"
        + (f"（{', '.join(institutional_gaps[:8])}）" if institutional_gaps else "")
    )
    _check_zero_volume_anomalies(None)

    health = build_database_health_report()
    console.print(f"  SQLite 結構檢查: {health.quick_check}")
    for name, count in health.quality_counts.items():
        console.print(f"  {name}: {count:,}")


def _check_zero_volume_anomalies(suspended: set | list | None) -> None:
    """Inspect latest-session zero-volume or non-positive OHLC rows read-only."""
    conn = get_connection(readonly=True)
    try:
        latest = conn.execute("SELECT MAX(date) FROM stock_history").fetchone()[0]
        if not latest:
            console.print("  [yellow]⚠️ 資料庫沒有價量資料[/yellow]")
            return

        rows = conn.execute(
            "SELECT stock_id, open, high, low, close, volume FROM stock_history "
            "WHERE date = ? AND (volume = 0 OR open <= 0 OR high <= 0 OR low <= 0 OR close <= 0) "
            "ORDER BY stock_id",
            (latest,),
        ).fetchall()

        if not rows:
            console.print(f"  [green]✅ 最新交易日 ({latest}) 無零量或非正價格資料[/green]")
            return

        suspended_set = set(suspended or [])
        classified = latest == date.today().isoformat() and bool(suspended_set)
        expected_zero: set[str] = set()
        needs_review: set[str] = set()
        for r in rows:
            stock_id = str(r[0])
            if classified and stock_id in suspended_set:
                expected_zero.add(stock_id)
            else:
                needs_review.add(stock_id)

        if expected_zero:
            console.print(f"  [cyan]ℹ️ 暫停交易/處置股票 ({latest}): " f"{len(expected_zero)} 支（零量價可解釋）[/cyan]")

        if needs_review:
            console.print(
                f"  [yellow]⚠️ 零量或非正價格資料 ({latest}): "
                f"{len(needs_review)} 支，僅列出供檢查，不自動刪除[/yellow]"
            )
            preview = ", ".join(sorted(needs_review)[:15])
            suffix = "..." if len(needs_review) > 15 else ""
            console.print(f"     {preview}{suffix}")
            if latest != date.today().isoformat():
                console.print("  [dim]資料日期不是今天，不使用今日停牌名單交叉判斷。[/dim]")
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════
# 4. 資料庫維護
# ══════════════════════════════════════════════════════════════
def run_db_maintenance() -> None:
    """Run read-only health checks before any guarded SQLite maintenance."""
    os.system("cls" if os.name == "nt" else "clear")
    print("=" * 60)
    print("資料庫健檢與最佳化")
    print("=" * 60)
    print("🔍 正在執行唯讀結構與資料品質檢查，不會刪除資料...")

    try:
        report = build_database_health_report()
        _render_database_health_report(report)
    except sqlite3.OperationalError as e:
        if "locked" in str(e).lower():
            print(
                "\n❌ 健檢失敗：資料庫被鎖定。請關閉其他可能使用資料庫的程式"
                "（如其他更新排程或資料庫檢視器）後再試一次。"
            )
        else:
            print(f"\n❌ 健檢失敗：{e}")
        blocking_input("\n按 Enter 鍵返回主選單...")
        return
    except Exception as e:
        print(f"\n❌ 健檢失敗：{e}")
        blocking_input("\n按 Enter 鍵返回主選單...")
        return

    print("\n[1] 安全最佳化查詢規劃（PRAGMA optimize）")
    if report.vacuum_recommended:
        print("[2] 建立備份後壓縮資料庫（VACUUM，現在符合執行門檻）")
    else:
        print("[2] 壓縮資料庫（目前不需要，選擇後也不會執行）")
    print("[Enter] 返回主選單")
    choice = blocking_input("\n輸入選項，再按 Enter：")

    if choice == "1":
        try:
            run_database_optimize()
            print("\n✅ SQLite 查詢規劃最佳化完成")
        except Exception as e:
            print(f"\n❌ 最佳化失敗：{e}")
    elif choice == "2":
        if not report.vacuum_recommended:
            print("\nℹ️ 可回收空間未達 5% 或 100 MiB，已安全略過 VACUUM。")
        elif not report.is_healthy:
            print("\n❌ SQLite 結構檢查未通過，禁止執行 VACUUM。")
        else:
            confirmation = blocking_input("輸入 YES 並按 Enter，確認先備份再壓縮：")
            if confirmation == "YES":
                try:
                    backup_path = run_guarded_database_vacuum(report)
                    print(f"\n✅ 資料庫壓縮完成，備份位於：{backup_path}")
                except Exception as e:
                    print(f"\n❌ 壓縮失敗：{e}")
            else:
                print("\nℹ️ 已取消壓縮，資料庫未變更。")
    elif choice:
        print("\n⚠️ 無效選項，未執行任何維護。")

    blocking_input("\n按 Enter 鍵返回主選單...")


def _render_database_health_report(report: DatabaseHealthReport) -> None:
    """Render a database health report without mutating the database."""
    print(f"\nSQLite 結構檢查: {report.quick_check}")
    print(f"資料庫大小: {_format_bytes(report.file_size_bytes)}")
    print(f"WAL 大小: {_format_bytes(report.wal_size_bytes)}")
    print(f"可回收空間: {_format_bytes(report.reclaimable_bytes)} " f"({report.reclaimable_ratio:.2%})")
    print("\n唯讀資料品質統計:")
    labels = {
        "invalid_history": "不合理 OHLC",
        "orphan_indicators": "孤立技術指標",
        "blank_foreign_shareholding": "全空外資持股",
        "future_shareholding": "未來日期持股",
        "tdcc_incomplete_rows": "TDCC 核心欄位不完整列",
        "tdcc_missing_whale_people": "TDCC 缺大戶人數列",
        "tdcc_tiny_periods": "TDCC 覆蓋過少期別",
        "tdcc_weekend_periods": "TDCC 週末推算日期",
        "tdcc_large_gaps": "TDCC 超過 10 天間隔",
        "blank_institutional": "全空法人資料",
    }
    for key, count in report.quality_counts.items():
        print(f"  {labels.get(key, key)}: {count:,}")
    if report.vacuum_recommended:
        print("\n⚠️ 可回收空間已達門檻，可考慮備份後執行 VACUUM。")
    else:
        print("\n✅ 可回收空間未達門檻，不建議執行 VACUUM。")


def _format_bytes(value: int) -> str:
    """Format a byte count for terminal display."""
    size = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if size < 1024 or unit == "TiB":
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} TiB"


# ── 內部輸入工具：blocking_input 已統一於 input_helper ──
# _get_interactive_input 已移除（A 組合：全部進入改 Enter，不再用單鍵）
