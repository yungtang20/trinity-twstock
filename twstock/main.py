#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模組 6：main.py (主程式) v3.3 [AI MOD] — 統一資料庫版
職責：CLI & TUI 入口，支援 update / indicators / intraday / strategy / official
整合策略調度入口 (strategies.py) 與官方資料抓取 (official 套件)

五個獨立策略模組（各自獨立檔案，不可合併）：
  - strategy/sr_analyzer.py        撐壓分析
  - strategy/ma_strategy.py        均線趨勢
  - strategy/chips_strategy.py     籌碼動能
  - strategy/prediction_strategy.py AI 預測
  - strategy/patterns_strategy.py  幾何型態
# [AI MOD] Aligned docstring order with actual registry map
"""

import argparse
import os
import sys
import time

# [AI MOD] 統一資料庫：路徑僅需指向 twstock 目錄
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if _CURRENT_DIR not in sys.path:
    sys.path.insert(0, _CURRENT_DIR)

import pandas as pd
import sqlite3
import warnings
import shutil
from datetime import datetime, timedelta

from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.align import Align
from rich.layout import Layout
from rich.padding import Padding
from rich import box

# [AI MOD] 集中式 Console：解決 Windows cp950 無法渲染 emoji 的問題
from terminal import console

# [AI MOD] Import unified Taiwan Stock colors & formatters
from display import (
    price_rich, chg_color, vol_fmt, vol_diff_rich,
    vol_color, price_color, render_kline
)

# [AI MOD] 統一 db 模組取代 phone.* 與 trinity_db
from db import get_connection, get_path, file_size_mb
from db_admin import init_db, migrate_db
from fetcher import DataFetcher
from processor import DataProcessor
from calculator import IndicatorEngine
# [AI MOD] 策略套件入口：每個策略為獨立模組
from strategy.strategies import interactive_menu as strategies_menu, run_strategy_cli
from official import update_official_daily, update_tdcc_weekly, update_tdcc_historical
from official.trading_calendar import get_nth_trading_day_back  # [AI MOD]
from official.dividend_crawler import fetch_dividend_events, upsert_dividend_events

warnings.filterwarnings("ignore")


TERM_WIDTH = shutil.get_terminal_size((80, 24)).columns
MOBILE = TERM_WIDTH < 52

# 跨平台輸入層（Windows msvcrt / Termux+termios / fallback input）
from input_helper import setup_console_encoding, HAS_MSVCRT

setup_console_encoding()  # Windows: chcp 65001; 非 Windows: 跳過

# ── 共用工具（來自 utils.py）─────────────────────────────
from utils import (
    safe_float, safe_int,
    default_http_headers as _default_http_headers,
    get_http_session as _safe_requests_session,
    safe_http_get as _safe_http_get,
    get_stock_name, to_roc_date, get_sys_info, get_market_mode,
    format_price_change,
)


def get_token():
    """從 api_config 取得 FinMind token。"""
    from api_config import get_finmind_token
    return get_finmind_token()


# ── 即時盤中資料（委託 market_data 套件）────────────────
from market_data import MarketCache, fetch_market_indices as _fetch_market_indices

# 模組層級 MarketCache 實例（向舊程式相容）
_market_cache = MarketCache()


def fetch_market_indices_cached():
    """向後相容包裝：委託 MarketCache.get()。"""
    return _market_cache.get()


# ── TUI 已搬離至 tui/ 套件 ──────────────────────────────
from tui import render_dashboard, make_layout, TUIApp


# ==================== Core Functions ====================

# ── 策略複合分析（委託 strategy.composites）─────────────
from strategy.composites import run_composite as run_quick_analysis


# ── TUI 子選單（委託 tui.menu）──────────────────────────
from tui.menu import (
    run_daily_update,
    run_historical_update_menu,
    run_db_maintenance,
)


def _fmt_chg(pct, chg):
    c = "bright_red" if chg > 0 else ("bright_green" if chg < 0 else "white")
    arrow = "▲" if chg > 0 else ("▼" if chg < 0 else "─")
    return f"[{c}]{arrow}{abs(pct):.1f}%({chg:+.2f})[/]"


def _vol_str(vol):
    """Format volume in 萬/千/個."""
    if vol >= 10000:
        return f"{vol / 10000:.1f}萬張"
    elif vol >= 1000:
        return f"{vol / 1000:.1f}千張"
    else:
        return f"{vol:,}張"


# 向後相容：run_quick_analysis 已移至 strategy.composites
# 保留舊名稱作為 re-export
    """[AI MOD] 執行多重策略的綜合分析面板"""
    stock_name = get_stock_name(stock_id)
    os.system("cls" if os.name == "nt" else "clear")

    # ── 檢查 DB 是否過期 ── [AI MOD]
    try:
        now = datetime.now()
        with get_connection(readonly=True) as conn:
            latest_db = conn.execute(
                "SELECT MAX(date) FROM stock_history"
            ).fetchone()[0]
        if latest_db:
            db_date = datetime.strptime(str(latest_db), '%Y-%m-%d')
            lag = (now - db_date).days
            if lag > 1:
                console.print(
                    f"[yellow]⚠️ 資料庫最新日期為 {latest_db}（距今 {lag} 天），"
                    f"建議先執行每日更新[/yellow]\n"
                )
    except Exception:
        pass

    console.print(Panel(
        Align.center(Text(f"🚀 {stock_id} {stock_name}", style="bold yellow")),
        box=box.DOUBLE, border_style="yellow"))

    # ═══════════════════════════════════════════
    #  Market Status
    # ═══════════════════════════════════════════
    now = datetime.now()
    mins = now.hour * 60 + now.minute
    is_weekday = now.weekday() < 5
    is_trading = is_weekday and (9 * 60 <= mins <= 13 * 60 + 30)
    today_str = now.strftime('%Y-%m-%d')

    # ═══════════════════════════════════════════
    #  Fetch DB: latest 3 trading days
    #  rows[0] = latest DB = previous trading day
    #  rows[1] = day before that
    #  rows[2] = two days before
    # ═══════════════════════════════════════════
    try:
        with get_connection(readonly=True) as conn:
            rows = conn.execute(
                "SELECT date, close, volume FROM stock_history "
                "WHERE stock_id = ? ORDER BY date DESC LIMIT 3",
                (stock_id,)
            ).fetchall()
    except Exception:
        rows = []

    if len(rows) >= 2:
        # ── Unpack DB rows ──
        d0 = str(rows[0][0]); p0 = float(rows[0][1]); v0 = int(rows[0][2])
        d1 = str(rows[1][0]); p1 = float(rows[1][1]); v1 = int(rows[1][2])
        if len(rows) >= 3:
            p2 = float(rows[2][1]); v2 = int(rows[2][2])
        else:
            p2, v2 = 0.0, 0

        # ── Try real-time during trading ──
        live_price = None
        live_vol = None
        if is_trading:
            try:
                session = _safe_requests_session()
                if session:
                    ex_ch = f"tse_{stock_id}.tw|otc_{stock_id}.tw"
                    url = (
                        f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp"
                        f"?ex_ch={ex_ch}&json=1&delay=0"
                        f"&_={int(time.time() * 1000)}"
                    )
                    r = _safe_http_get(url, session=session, timeout=3, verify=False)
                    if r:
                        try:
                            data = r.json()
                        except ValueError:
                            data = {}
                        if data and data.get('msgArray'):
                            for item in data['msgArray']:
                                c = item.get('c', '')
                                if c == stock_id or c.zfill(4) == stock_id:
                                    z = item.get('z', '-')
                                    v = item.get('v', '0')
                                    if z and z != '-' and z != '0.00':
                                        live_price = float(z)
                                    else:
                                        b_val = item.get('b', '-')
                                        if b_val and b_val != '-':
                                            b_list = [x for x in b_val.split('_') if x]
                                            if b_list:
                                                live_price = float(b_list[0])
                                        if live_price is None:
                                            a_val = item.get('a', '-')
                                            if a_val and a_val != '-':
                                                a_list = [x for x in a_val.split('_') if x]
                                                if a_list:
                                                    live_price = float(a_list[0])
                                    if v and v not in ('-', '0', ''):
                                        live_vol = int(v.replace(',', '')) * 1000  # Convert TWSE MIS sheets (張) to shares (股)
                                    break
            except Exception:
                pass
            
        # ═══════════════════════════════════════
        #  Render
        # ═══════════════════════════════════════
        if MOBILE:
            if is_trading:
                console.print(f"[bright_cyan]▶ 開盤中   {today_str}  "
                              f"{now.strftime('%H:%M')}[/]")
                if live_price is not None:
                    console.print(f"  股價 {price_rich(live_price, p0)}")
                    console.print(f"  量 {vol_diff_rich(live_vol or v0, v0)}")
                else:
                    console.print("  [dim]暫無即時報價[/]")
            else:
                console.print(f"[bright_cyan]▶ 收盤 {d0}[/]")
                console.print(f"  股價 {price_rich(p0, p1)}")
                console.print(f"  量 {vol_diff_rich(v0, v1)}")

            console.print()
            console.print(f"[bright_white]▷ 歷史 {d0 if is_trading else d1}[/]")
            if is_trading:
                console.print(f"  股價 {price_rich(p0, p1)}")
                console.print(f"  量 {vol_diff_rich(v0, v1)}")
            else:
                console.print(f"  股價 {price_rich(p1, p2)}")
                console.print(f"  量 {vol_diff_rich(v1, v2)}")
        else:
            # ── Wide: two-column ──
            info = Table.grid(padding=(0, 2))
            info.add_column()
            info.add_column()

            if is_trading:
                left_title = f"[bold bright_cyan]開盤中[/] [dim]{today_str} {now.strftime('%H:%M')}[/]"
                right_title = f"[bold bright_white]歷史[/] [dim]{d0}[/]"
                info.add_row(left_title, right_title)

                if live_price is not None:
                    info.add_row(
                        f"股價 {price_rich(live_price, p0)}",
                        f"股價 {price_rich(p0, p1)}"
                    )
                    info.add_row(
                        f"量 {vol_diff_rich(live_vol or v0, v0)}",
                        f"量 {vol_diff_rich(v0, v1)}"
                    )
                else:
                    info.add_row("[dim]暫無即時報價[/]", f"股價 {price_rich(p0, p1)}")
                    info.add_row("", f"量 {vol_diff_rich(v0, v1)}")
            else:
                left_title = f"[bold bright_cyan]收盤[/] [dim]{d0}[/]"
                right_title = f"[bold bright_white]歷史[/] [dim]{d1}[/]"
                info.add_row(left_title, right_title)
                info.add_row(
                    f"股價 {price_rich(p0, p1)}",
                    f"股價 {price_rich(p1, p2)}"
                )
                info.add_row(
                    f"量 {vol_diff_rich(v0, v1)}",
                    f"量 {vol_diff_rich(v1, v2)}"
                )

            console.print(Panel(info, border_style="blue",
                                box=box.ROUNDED, padding=(0, 1)))
    else:
        console.print(f"[yellow]⚠️ {stock_id} 歷史資料不足[/yellow]")

    # ═══════════════════════════════════════════
    #  5 Strategy Modules (mobile passed dynamically)
    # ═══════════════════════════════════════════
    strategies = [
        ("1 ⚡ 撐壓分析 (Support/Resistance)",   "sr_analyzer"),
        ("2 ⚡ 均線趨勢 (MA Trend)",   "ma_strategy"),
        ("3 ⚡ 籌碼動能 (Institutional Chips)",   "chips_strategy"),
        ("4 ⚡ AI 預測 (Kronos Prediction)",    "prediction_strategy"),
        ("5 ⚡ 幾何型態 (Chart Patterns)",   "patterns_strategy"),
    ]
    for label, mod_name in strategies:
        console.print(f"\n[bold cyan]{label}[/]")
        try:
            mod = __import__(f"strategy.{mod_name}", fromlist=[mod_name])
            params = {'code': stock_id, 'compact': True, 'mobile': MOBILE}
            mod.run_strategy(params)
        except Exception as e:
            console.print(f"[red]❌ 分析失敗: {e}[/red]")

    # ── K 線圖 ──
    try:
        from strategy._utils import fetch_klines
        df_kline = fetch_klines(conn, stock_id, limit=60)
        df_kline = df_kline.dropna(subset=["close"]).sort_values("date")
        if not df_kline.empty:
            console.print()
            console.print(render_kline(df_kline, stock_id, ""))
    except Exception as e:
        console.print(f"[dim]K 線圖渲染跳過: {e}[/dim]")

    # ── LongCat AI 文字分析（純文字摘要，非視覺）──
    try:
        from longcat_vision import analyze_kline_with_longcat
        ai_result = analyze_kline_with_longcat(df_kline, stock_id, "")
        if ai_result:
            console.print()
            console.print(Panel(ai_result, title="🤖 LongCat AI 分析", border_style="magenta"))
    except Exception as e:
        console.print(f"[dim]LongCat AI 分析跳過: {e}[/dim]")

    input("\n按 Enter 鍵返回主選單...")

# ── 命令已搬離至 commands/ 套件 ─────────────────────────
from commands.update import execute as _update_exec
from commands.indicators import execute as _indicators_exec
from commands.intraday import execute as _intraday_exec
from commands.official import execute as _official_exec
from commands.dividend import execute as _dividend_exec


def update_database(stock_id: str, token: str | None = None) -> bool:
    """向後相容：委託 commands/update.py。"""
    from commands.update import update_single_stock
    return update_single_stock(stock_id, token)


def indicators_command(stock_id: str, token: str | None = None) -> None:
    """向後相容：委託 commands/indicators.py。"""
    from argparse import Namespace
    _indicators_exec(Namespace(stock_id=stock_id, token=token))


def intraday_command(stock_id: str, token: str | None = None) -> None:
    """向後相容：委託 commands/intraday.py。"""
    from argparse import Namespace
    _intraday_exec(Namespace(stock_id=stock_id, token=token))


def official_command(args) -> None:
    """向後相容：委託 commands/official.py。"""
    _official_exec(args)


def dividend_command(args) -> None:
    """向後相容：委託 commands/dividend.py。"""
    _dividend_exec(args)


# ==================== Main Loop & Menus ====================

# ── 子選單已搬離至 tui/menu.py ──────────────────────────
# run_daily_update, run_historical_update_menu, run_db_maintenance
# 皆已從 tui.menu 匯入（見上方）


if __name__ == '__main__':
    # 自動初始化資料庫（只在直接執行時觸發，import 不觸發）
    if not os.path.exists(get_path()):
        console.print("[yellow]首次執行，初始化資料庫...[/yellow]")
        init_db()
    else:
        migrate_db()

    if len(sys.argv) == 1:
        tui_interactive_menu()
    else:
        parser = argparse.ArgumentParser(description="TRINITY 策略系統 v3.3")
        parser.add_argument(
            "action",
            choices=[
                'update', 'indicators', 'intraday',
                'strategy', 'official', 'dividend',
            ],
            help="執行動作",
        )
        parser.add_argument("stock_id", type=str, nargs='?', help="股票代號")
        parser.add_argument("--token", type=str, help="FinMind Token")
        parser.add_argument("--strategy-id", type=str, help="策略編號")
        parser.add_argument("--code", type=str, help="股票代號 (配合策略使用)")
        parser.add_argument("--scan", action="store_true", help="全市場掃描")
        parser.add_argument(
            "--vol", type=int, default=500, help="掃描最小成交量 (張)"
        )
        parser.add_argument(
            "--date", type=str,
            help="指定日期 (YYYY-MM-DD 或 YYYYMMDD)",
        )
        parser.add_argument("--days", type=int, default=1, help="下載幾個交易日")
        parser.add_argument("--tdcc-only", action="store_true", help="僅抓取最新 TDCC")
        parser.add_argument(
            "--with-tdcc", action="store_true", help="更新後自動更新 TDCC"
        )
        parser.add_argument(
            "--tdcc-weeks", type=int, help="抓取最近 N 週 TDCC 歷史"
        )
        parser.add_argument("--start-date", type=str, help="開始日期 (dividend)")
        parser.add_argument("--end-date", type=str, help="結束日期 (dividend)")

        args = parser.parse_args()
        token = args.token or get_token()

        if args.action == 'update':
            if args.stock_id:
                update_database(args.stock_id, token)
            else:
                console.print("[red]update 需要提供 stock_id[/red]")
        elif args.action == 'indicators':
            if args.stock_id:
                indicators_command(args.stock_id, token)
            else:
                console.print("[red]indicators 需要提供 stock_id[/red]")
        elif args.action == 'intraday':
            if args.stock_id:
                intraday_command(args.stock_id, token)
            else:
                console.print("[red]intraday 需要提供 stock_id[/red]")
        elif args.action == 'strategy':
            run_strategy_cli(args)
        elif args.action == 'official':
            official_command(args)
        elif args.action == 'dividend':
            dividend_command(args)