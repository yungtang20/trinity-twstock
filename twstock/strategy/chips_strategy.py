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


class StockAnalyzer:
    """籌碼分析器 - 連接資料庫並提供法人買賣超分析"""

    def __init__(self, conn=None):
        self.conn = conn or get_connection()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def get_latest_dates(self):
        """回傳 (hist_date, inst_date)"""
        cur = self.conn.execute(
            "SELECT MAX(date) FROM stock_history"
        )
        hist_date = cur.fetchone()[0]
        cur = self.conn.execute(
            "SELECT MAX(date) FROM institutional_daily"
        )
        row = cur.fetchone()
        inst_date = row[0] if row and row[0] else hist_date
        return hist_date, inst_date

    def analyze_institutional_buying(self, investor_type, min_consecutive_days, min_volume, sort_choice):
        """分析法人連續買超"""
        net_col = f"{investor_type}_net"
        buy_col = f"{investor_type}_buy"
        # 找出最新日期
        latest = self.conn.execute("SELECT MAX(date) FROM institutional_data").fetchone()[0]
        if not latest:
            return []
        # 找出連續買超 min_consecutive_days 天的股票
        sql = f"""
            WITH ranked AS (
                SELECT stock_id, date, {net_col}, {buy_col},
                       ROW_NUMBER() OVER (PARTITION BY stock_id ORDER BY date DESC) AS rn
                FROM institutional_data
                WHERE date >= date(?, '-30 days')
            ),
            consecutive AS (
                SELECT stock_id,
                       COUNT(*) AS buy_days,
                       SUM({buy_col}) AS total_buy,
                       MAX(date) AS last_date
                FROM ranked
                WHERE rn <= 15 AND {net_col} > 0
                GROUP BY stock_id
                HAVING COUNT(*) >= ?
            )
            SELECT c.stock_id, c.buy_days, c.total_buy, c.last_date, h.volume, m.name
            FROM consecutive c
            JOIN stock_history h ON c.stock_id = h.stock_id AND c.last_date = h.date
            LEFT JOIN stock_meta m ON c.stock_id = m.stock_id
            WHERE h.volume >= ?
            ORDER BY c.buy_days DESC, c.total_buy DESC
            LIMIT 50
        """
        rows = self.conn.execute(sql, (latest, min_consecutive_days, min_volume)).fetchall()
        results = []
        for r in rows:
            results.append({
                'stock_id': r[0],
                'name': r[5] or '---',
                'buy_days': r[1],
                'total_buy': r[2],
                'date': r[3],
                'volume': r[4],
            })
        return results

    def analyze_main_force_vs_retail(self, min_volume, sort_choice):
        """分析千張大戶 vs 散戶"""
        # 取最近兩週的 shareholding_unified 資料
        dates = self.conn.execute(
            "SELECT date FROM shareholding_unified GROUP BY date HAVING COUNT(DISTINCT stock_id) > 50 ORDER BY date DESC LIMIT 2"
        ).fetchall()
        if len(dates) < 2:
            return []
        latest_date, prev_date = dates[0][0], dates[1][0]
        sql = """
            SELECT s1.stock_id, s1.whale_ratio AS curr_whale, s2.whale_ratio AS prev_whale,
                   s1.whale_ratio - s2.whale_ratio AS whale_change,
                   s1.total_people AS curr_people, s2.total_people AS prev_people,
                   h.volume, m.name
            FROM shareholding_unified s1
            JOIN shareholding_unified s2 ON s1.stock_id = s2.stock_id AND s2.date = ?
            JOIN stock_history h ON s1.stock_id = h.stock_id AND s1.date = h.date
            LEFT JOIN stock_meta m ON s1.stock_id = m.stock_id
            WHERE s1.date = ? AND h.volume >= ?
              AND s1.whale_ratio IS NOT NULL AND s2.whale_ratio IS NOT NULL
            ORDER BY whale_change DESC
            LIMIT 50
        """
        rows = self.conn.execute(sql, (prev_date, latest_date, min_volume)).fetchall()
        results = []
        for r in rows:
            people_change = r[4] - r[5] if r[4] and r[5] else 0
            results.append({
                'stock_id': r[0],
                'name': r[6] or '---',
                'curr_whale': r[1],
                'prev_whale': r[2],
                'whale_change': r[3],
                'curr_people': r[4],
                'prev_people': r[5],
                'people_change': people_change,
                'volume': r[7],
            })
        return results

    def display_institutional_results(self, results, investor_type, date):
        """顯示法人分析結果"""
        investor_name = "投信" if investor_type == "trust" else "外資"
        if not results:
            rconsole.print(f"[yellow]📭 無符合{investor_name}連買條件的標的 ({date})[/]")
            return
        rconsole.print(f"\n[bold]📊 {investor_name}連買分析 ({date}):[/]")
        table = Table(box=box.SIMPLE_HEAVY)
        table.add_column("代號", style="cyan")
        table.add_column("名稱")
        table.add_column("連買天數", justify="right")
        table.add_column("買超張數", justify="right")
        table.add_column("成交張數", justify="right")
        table.add_column("日期", justify="center")
        for r in results:
            table.add_row(
                r['stock_id'],
                r['name'],
                str(r['buy_days']),
                f"{r['total_buy'] // 1000:,}",
                f"{r['volume'] // 1000:,}",
                r['date'],
            )
        rconsole.print(table)

    def display_main_force_results(self, results, date1, date2):
        """顯示大戶分析結果"""
        if not results:
            rconsole.print(f"[yellow]📭 無符合條件標的 ({date1} vs {date2})[/]")
            return
        rconsole.print(f"\n[bold]📊 千張大戶分析結果 ({date1} vs {date2}):[/]")
        table = Table(box=box.SIMPLE_HEAVY)
        table.add_column("代號", style="cyan")
        table.add_column("名稱")
        table.add_column("大戶比例", justify="right")
        table.add_column("變化", justify="right")
        table.add_column("人數變化", justify="right")
        for r in results[:20]:
            change_str = f"{r['whale_change']:+.2f}%" if r['whale_change'] else "N/A"
            table.add_row(
                r['stock_id'],
                r['name'],
                f"{r['curr_whale']:.2f}%" if r['curr_whale'] else "N/A",
                change_str,
                f"{r['people_change']:+d}",
            )
        rconsole.print(table)

    def display_single_stock(self, code, compact=False, mobile=False):
        """顯示單股分析"""
        name = get_stock_name(self.conn, code)
        rconsole.print(f"\n[bold]{code} {name} 籌碼分析[/bold]")
        # 法人買賣超
        rows = self.conn.execute(
            "SELECT date, foreign_net, trust_net, dealer_net, institutional_net "
            "FROM institutional_data WHERE stock_id = ? ORDER BY date DESC LIMIT 10",
            (code,)
        ).fetchall()
        if rows:
            rconsole.print("\n[bold cyan]📈 近10日法人買賣超 (千股):[/]")
            tbl = Table(box=box.SIMPLE)
            tbl.add_column("日期")
            tbl.add_column("外資", justify="right")
            tbl.add_column("投信", justify="right")
            tbl.add_column("自營", justify="right")
            tbl.add_column("合計", justify="right")
            for row in rows:
                tbl.add_row(row[0], f"{row[1]//1000:+,}", f"{row[2]//1000:+,}", f"{row[3]//1000:+,}", f"{row[4]//1000:+,}")
            rconsole.print(tbl)
        # 集保資料
        sh = self.conn.execute(
            "SELECT date, whale_ratio, total_people, whale_people, whale_shares "
            "FROM shareholding_unified WHERE stock_id = ? ORDER BY date DESC LIMIT 5",
            (code,)
        ).fetchall()
        if sh:
            rconsole.print("\n[bold cyan]📊 集保持股分布:[/]")
            tbl2 = Table(box=box.SIMPLE)
            tbl2.add_column("日期")
            tbl2.add_column("大戶比例", justify="right")
            tbl2.add_column("總人數", justify="right")
            tbl2.add_column("大戶人數", justify="right")
            for row in sh:
                tbl2.add_row(row[0], f"{row[1]:.2f}%" if row[1] else "N/A",
                             f"{row[2]:,}" if row[2] else "N/A",
                             f"{row[3]:,}" if row[3] else "N/A")
            rconsole.print(tbl2)
        else:
            rconsole.print("  [dim]查不到法人/集保資料[/]")


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
