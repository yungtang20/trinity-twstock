#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略整合_籌碼分析 v12.0 (統一資料庫版)
# [AI MOD] Migrated to taiwan_stock_unified.db + klines view
"""
import os
import sys
import time
import sqlite3
import warnings
import signal
from typing import List, Dict, Optional, Tuple
import urllib.request
import json

import pandas as pd
from rich.table import Table
from rich import box
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

warnings.filterwarnings('ignore')

# [AI MOD] 集中式 Console：解決 Windows cp950 無法渲染 emoji 的問題
from terminal import rconsole

# ── Module path ───────────────────────────────────────────
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_TWSTOCK_DIR = os.path.abspath(os.path.join(_CURRENT_DIR, ".."))
if _TWSTOCK_DIR not in sys.path:
    sys.path.insert(0, _TWSTOCK_DIR)

from db import get_connection, DB_PATH  # [AI MOD]
from strategy._utils import clear_screen, get_stock_name, render_header, fetch_klines
from display import price_rich, vol_fmt, chg_color, vol_color, price_color
from retry import retry_get  # [AI MOD]

try:
    import msvcrt
    HAS_MSVCRT = True
except ImportError:
    HAS_MSVCRT = False

def get_single_key_input(prompt: str, keys: str, auto_four: bool = False) -> str:
    if not HAS_MSVCRT or not sys.stdin.isatty():
        return input(prompt).strip()
    while msvcrt.kbhit():
        msvcrt.getwch()
    sys.stdout.write(prompt)
    sys.stdout.flush()
    buf = ""
    while True:
        if msvcrt.kbhit():
            ch = msvcrt.getwch()
            if ch in ('\r', '\n'):
                sys.stdout.write('\n')
                sys.stdout.flush()
                return buf.strip()
            elif ch == '\b':
                if len(buf) > 0:
                    buf = buf[:-1]
                    sys.stdout.write('\b \b')
                    sys.stdout.flush()
            elif ch in ('\x1b', '\x03'): # ESC or Ctrl+C
                sys.stdout.write('\n')
                sys.stdout.flush()
                return ""
            else:
                if ch.isprintable():
                    buf += ch
                    sys.stdout.write(ch)
                    sys.stdout.flush()
                    if len(buf) == 1 and ch in keys:
                        # 0.4s protection time
                        import time
                        start_wait = time.time()
                        is_single = True
                        while time.time() - start_wait < 0.4:
                            if msvcrt.kbhit():
                                next_ch = msvcrt.getwch()
                                if next_ch in ('\r', '\n'):
                                    break
                                is_single = False
                                buf += next_ch
                                sys.stdout.write(next_ch)
                                sys.stdout.flush()
                                break
                        if is_single:
                            sys.stdout.write('\n')
                            sys.stdout.flush()
                            return buf.strip()

                    if auto_four and len(buf) == 4 and buf.isdigit():
                        sys.stdout.write('\n')
                        sys.stdout.flush()
                        return buf.strip()


# ── Local helpers ─────────────────────────────────────────

def _render_header(title, is_detail=False):
    render_header(title, is_detail=is_detail, console=rconsole)


def _clear_screen():
    clear_screen()


def _wait_for_enter(prompt: str = "\n按 Enter 繼續..."):
    input(prompt)


def _fetch_klines(conn, stock_id, limit=512):
    return fetch_klines(conn, stock_id, limit)


def scan_market(analyzer: StockAnalyzer, min_vol: int = 500, strat_choice: str = None):
    """市場掃描主函數"""
    hist_date, inst_date = analyzer.get_latest_dates()
    if not inst_date:
        return

    rconsole.print(f"\n[bold cyan]🔍 籌碼策略掃描 v12.0 (資料基準日: {inst_date})[/bold cyan]") # [AI MOD]
    rconsole.print(" [1] 投信連買 x 天 (預設 2 天) (預設)") # [AI MOD]
    rconsole.print(" [2] 外資連買 x 天 (預設 2 天)") # [AI MOD]
    rconsole.print(" [3] 集保人數下降，千張大戶增") # [AI MOD]

    if strat_choice in ["1", "2", "3"]:
        choice = strat_choice
    else:
        choice = get_single_key_input("🔢 選擇策略 (預設 1): ", "123") or "1" # [AI MOD]

    if choice in ["1", "2"]:
        investor_type = "trust" if choice == "1" else "foreign" # [AI MOD]
        investor_name = "投信" if choice == "1" else "外資" # [AI MOD]

        n_days_input = get_single_key_input(f"📅 {investor_name}連買天數 (預設 2): ", "123456789") or "2"
        n_days = int(n_days_input) if n_days_input.isdigit() else 2

        sort_input = get_single_key_input("📊 排序基準 [1] 連買天數(由小到大) [2] 法人成交金額(由大到小) [3] VWAP<收盤，乖離10%外 (預設 1): ", "123") or "1"
        sort_choice = int(sort_input) if sort_input in ["1", "2", "3"] else 1

        results = analyzer.analyze_institutional_buying(
            investor_type=investor_type,
            min_consecutive_days=n_days,
            min_volume=min_vol,
            sort_choice=sort_choice,
        )

        if results:
            analyzer.display_institutional_results(results, investor_type, inst_date)
        else:
            rconsole.print(f"[yellow]📭 無符合標的 ({investor_name}連買 >= {n_days} 天)")

    elif choice == "3":
        # [AI MOD] Ask sorting options for Strategy 3
        sort_input = get_single_key_input("📊 排序基準 [1] 千張(人數%)由大到小 [2] 集保(人數%)由大到小 (預設 1): ", "12") or "1"
        sort_choice = int(sort_input) if sort_input in ["1", "2"] else 1
        results = analyzer.analyze_main_force_vs_retail(min_volume=min_vol, sort_choice=sort_choice)
        if results:
            try:
                # [AI MOD] shareholding_unified replaces stock_shareholding_all
                dates = analyzer.conn.execute(
                    "SELECT date FROM shareholding_unified "
                    "GROUP BY date HAVING COUNT(DISTINCT stock_id) > 100 "
                    "ORDER BY date DESC LIMIT 2"
                ).fetchall()
                if len(dates) >= 2:
                    analyzer.display_main_force_results(results, dates[0][0], dates[1][0])
                else:
                    analyzer.display_main_force_results(results, 0, 0)
            except Exception:
                analyzer.display_main_force_results(results, 0, 0)
        else:
            rconsole.print("[yellow]📭 無符合集保人數下降，千張大戶增條件的標的") # [AI MOD]
    else:
        rconsole.print("[red]❌ 無效選擇")


def run_strategy(params: dict):
    code = params.get('code')
    scan = params.get('scan', False)
    vol = params.get('vol', 500)
    strat_choice = params.get('strat_choice')
    compact = params.get('compact', False)
    mobile = params.get('mobile', False)
    with StockAnalyzer() as analyzer:
        if scan:
            scan_market(analyzer, min_vol=vol, strat_choice=strat_choice)
        elif code:
            analyzer.display_single_stock(code, compact=compact, mobile=mobile)
        else:
            main()


def main():
    """主函數"""
    signal.signal(signal.SIGINT, lambda s, f: sys.exit(0))

    with StockAnalyzer() as analyzer:  # [AI MOD] No path arg needed
        while True:
            try:
                _clear_screen()
                _render_header("📘 策略整合：籌碼動能分析 (v12.0 統一版)")
                rconsole.print("\n 指令: [4碼股號] | [1] 投信 | [2] 外資 | [3] 集保 | [0] 退出")

                cmd = rconsole.input("🔍 指令: ").strip()

                if cmd == "0":
                    break
                if cmd in ("1", "2", "3"):
                    scan_market(analyzer, min_vol=0, strat_choice=cmd)
                    _wait_for_enter()
                    continue
                if not cmd:
                    scan_market(analyzer, min_vol=0)
                    _wait_for_enter()
                    continue
                if len(cmd) == 4 and cmd.isdigit():
                    analyzer.display_single_stock(cmd)
                    _wait_for_enter()
                    continue
            except Exception as e:
                rconsole.print(f"[red]❌ 錯誤: {e}")
                _wait_for_enter()


if __name__ == "__main__":
    main()
