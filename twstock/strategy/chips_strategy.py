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
    from twstock.input_helper import get_interactive_input
except ImportError:
    from input_helper import get_interactive_input

def get_single_key_input(prompt: str, keys: str, auto_four: bool = False) -> str:
    """向後相容包裝：統一使用 input_helper.get_interactive_input。"""
    return get_interactive_input(prompt=prompt, menu_keys=keys, auto_four=auto_four)


# ── Local helpers ─────────────────────────────────────────

def _render_header(title, is_detail=False):
    render_header(title, is_detail=is_detail, console=rconsole)


def _clear_screen():
    clear_screen()


def _wait_for_enter(prompt: str = "\n按 Enter 繼續..."):
    input(prompt)


class StockAnalyzer:
    """籌碼分析器 - 連接資料庫並提供法人買賣超分析"""

    def __init__(self, conn=None):
        self._owns_conn = conn is None
        self.conn = conn or get_connection()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._owns_conn and self.conn:
            self.conn.close()
            self.conn = None

    def get_latest_dates(self):
        """回傳 (hist_date, inst_date)"""
        cur = self.conn.execute(
            "SELECT MAX(date) FROM stock_history"
        )
        hist_date = cur.fetchone()[0]
        cur = self.conn.execute(
            "SELECT MAX(date) FROM institutional_data"
        )
        row = cur.fetchone()
        inst_date = row[0] if row and row[0] else hist_date
        return hist_date, inst_date

    def analyze_institutional_buying(self, investor_type, min_consecutive_days, sort_choice):
        """分析法人連續買超"""
        net_col = f"{investor_type}_net"
        # 找出最新日期
        latest = self.conn.execute("SELECT MAX(date) FROM institutional_data").fetchone()[0]
        if not latest:
            return []
        # 動態排序
        direction = "ASC" if sort_choice == 1 else "DESC"
        # 找出「連買到最新交易日」的股票：最新日往回連續 N 天都是買超
        sql = f"""
            WITH latest AS (SELECT MAX(date) AS d FROM institutional_data),
            ranked AS (
                SELECT stock_id, date, {net_col},
                       ROW_NUMBER() OVER (PARTITION BY stock_id ORDER BY date DESC) AS rn
                FROM institutional_data, latest
                WHERE date >= date(latest.d, '-30 days')
            ),
            -- 找出最新日有買超的股票，往回數連續買超天數
            streak AS (
                SELECT r1.stock_id,
                       COUNT(*) AS buy_days,
                       SUM(r1.{net_col}) AS total_net,
                       MAX(r1.date) AS last_date
                FROM ranked r1, latest
                WHERE r1.{net_col} > 0
                  AND r1.date >= COALESCE(
                      (SELECT MIN(r2.date) FROM ranked r2, latest
                       WHERE r2.stock_id = r1.stock_id AND r2.rn <= 15
                         AND (r2.{net_col} <= 0 OR r2.date = latest.d)),
                      latest.d)
                  AND r1.date <= latest.d
                GROUP BY r1.stock_id
                HAVING MAX(r1.date) = latest.d
            )
            SELECT s.stock_id, s.buy_days, s.total_net, s.last_date,
                   h.close, h.volume, h2.close AS prev_close, h2.volume AS prev_volume,
                   m.stock_name
            FROM streak s
            JOIN stock_history h ON s.stock_id = h.stock_id AND s.last_date = h.date
            LEFT JOIN stock_history h2 ON s.stock_id = h2.stock_id AND h2.date = date(s.last_date, '-1 day')
            LEFT JOIN stock_meta m ON s.stock_id = m.stock_id
            WHERE s.buy_days >= ?
            ORDER BY s.buy_days {direction}, s.total_net {direction}
            LIMIT 50
        """
        rows = self.conn.execute(sql, (min_consecutive_days,)).fetchall()
        results = []
        for r in rows:
            results.append({
                'stock_id': r[0],
                'name': r[8] or '---',
                'buy_days': r[1],
                'total_net': r[2],
                'date': r[3],
                'close': r[4] or 0.0,
                'volume': r[5] or 0,
                'prev_close': r[6] or r[4] or 0.0,
                'prev_volume': r[7] or r[5] or 0,
            })
        return results

    @staticmethod
    def _fmt_change(val, suffix="", fmt=".2f"):
        """格式化漲跌：正=紅，負=綠，零=白（統一 display.py 配色）"""
        if val is None:
            return "N/A"
        if val > 0:
            color = "bright_red"
        elif val < 0:
            color = "bright_green"
        else:
            color = "white"
        return f"[{color}]{val:+{fmt}}{suffix}[/]"

    def analyze_main_force_vs_retail(self, sort_choice):
        """分析千張大戶 vs 散戶。回傳 (results, latest_date, prev_date)"""
        # 取最近兩週的 shareholding_unified 資料
        dates = self.conn.execute(
            "SELECT date FROM shareholding_unified GROUP BY date HAVING COUNT(DISTINCT stock_id) > 50 ORDER BY date DESC LIMIT 2"
        ).fetchall()
        if len(dates) < 2:
            return [], None, None
        latest_date, prev_date = dates[0][0], dates[1][0]
        # 取得最新交易日與前一日股價/成交量
        kline_dates = self.conn.execute(
            "SELECT date FROM stock_history GROUP BY date ORDER BY date DESC LIMIT 2"
        ).fetchall()
        if len(kline_dates) < 2:
            return [], None, None
        latest_kline, prev_kline = kline_dates[0][0], kline_dates[1][0]
        sql = """
            SELECT s1.stock_id, s1.whale_ratio AS curr_whale, s2.whale_ratio AS prev_whale,
                   s1.whale_ratio - s2.whale_ratio AS whale_change,
                   s1.total_people AS curr_people, s2.total_people AS prev_people,
                   k1.close, k2.close AS prev_close, k1.volume, k2.volume AS prev_volume,
                   m.stock_name
            FROM shareholding_unified s1
            JOIN shareholding_unified s2 ON s1.stock_id = s2.stock_id AND s2.date = ?
            LEFT JOIN stock_history k1 ON s1.stock_id = k1.stock_id AND k1.date = ?
            LEFT JOIN stock_history k2 ON s1.stock_id = k2.stock_id AND k2.date = ?
            LEFT JOIN stock_meta m ON s1.stock_id = m.stock_id
            WHERE s1.date = ?
              AND s1.whale_ratio IS NOT NULL AND s2.whale_ratio IS NOT NULL
              AND s1.whale_ratio > s2.whale_ratio
              AND s1.total_people < s2.total_people
            ORDER BY whale_change DESC
            LIMIT 50
        """
        rows = self.conn.execute(sql, (prev_date, latest_kline, prev_kline, latest_date)).fetchall()
        results = []
        for r in rows:
            people_change = int(r[4] - r[5]) if r[4] is not None and r[5] is not None else 0
            close = float(r[6]) if r[6] is not None else 0.0
            prev_close = float(r[7]) if r[7] is not None else 0.0
            volume = int(r[8]) if r[8] is not None else 0
            prev_volume = int(r[9]) if r[9] is not None else 0
            price_change = ((close - prev_close) / prev_close * 100) if prev_close > 0 else 0.0
            vol_change = ((volume - prev_volume) / prev_volume * 100) if prev_volume > 0 else 0.0
            results.append({
                'stock_id': r[0],
                'name': r[10] or '---',
                'close': close,
                'price_change': price_change,
                'volume': volume,
                'vol_change': vol_change,
                'curr_whale': float(r[1]) if r[1] is not None else 0.0,
                'whale_change': float(r[3]) if r[3] is not None else 0.0,
                'people_change': people_change,
            })
        return results, latest_date, prev_date

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
        table.add_column("收盤", justify="right")
        table.add_column("成交張數", justify="right")
        table.add_column("額(億)", justify="right")
        table.add_column("連買天數", justify="right")
        table.add_column("買超張數", justify="right")
        for r in results:
            net_val = r['total_net'] // 1000
            net_str = self._fmt_change(net_val, "", "d")
            # 收盤顏色
            prev_close = r.get('prev_close', r['close'])
            price_change = r['close'] - prev_close
            pct = (price_change / prev_close * 100) if prev_close else 0.0
            price_str = f"[{price_color(price_change, pct)}]{r['close']:.2f}[/]"
            # 成交量顏色
            vol_sheets = r['volume'] // 1000
            prev_vol = r.get('prev_volume', r['volume'])
            vol_str = f"[{vol_color(r['volume'], prev_vol)}]{vol_sheets:,}[/]"
            # 額(億)
            amount = (r['close'] * r['volume']) / 1e8
            table.add_row(
                r['stock_id'],
                r['name'],
                price_str,
                vol_str,
                f"{amount:.2f}",
                str(r['buy_days']),
                net_str,
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
        table.add_column("收盤", justify="right")
        table.add_column("成交張數", justify="right")
        table.add_column("額(億)", justify="right")
        table.add_column("大戶比例", justify="right")
        table.add_column("變化", justify="right")
        table.add_column("人數變化", justify="right")
        for r in results[:20]:
            pc = r['people_change'] or 0
            # 收盤顏色
            prev_close = r.get('prev_close', r['close'])
            price_change = r['close'] - prev_close
            pct = (price_change / prev_close * 100) if prev_close else 0.0
            price_str = f"[{price_color(price_change, pct)}]{r['close']:.2f}[/]"
            # 成交量顏色
            vol_sheets = r['volume'] // 1000
            prev_vol = r.get('prev_volume', r['volume'])
            vol_str = f"[{vol_color(r['volume'], prev_vol)}]{vol_sheets:,}[/]"
            # 額(億)
            amount = (r['close'] * r['volume']) / 1e8
            whale_str = f"{r['curr_whale']:.2f}%" if r['curr_whale'] else "N/A"
            change_str = self._fmt_change(r['whale_change'], "%")
            people_str = self._fmt_change(pc, "", "d")
            table.add_row(
                r['stock_id'],
                r['name'],
                price_str,
                vol_str,
                f"{amount:.2f}",
                whale_str,
                change_str,
                people_str,
            )
        rconsole.print(table)

    def display_single_stock(self, code, compact=False, mobile=False):
        """顯示單股分析"""
        name = get_stock_name(self.conn, code)
        rconsole.print(f"\n[bold]{code} {name} 籌碼分析[/bold]")
        # 法人買賣超（TWSE T86 不提供自營商明細，只顯示外資/投信/合計）
        rows = self.conn.execute(
            "SELECT date, foreign_net, trust_net, institutional_net "
            "FROM institutional_data WHERE stock_id = ? ORDER BY date DESC LIMIT 10",
            (code,)
        ).fetchall()
        # 取得近60日股價（收盤、成交量）供表格顯示
        # 集保資料每月公佈，需要更多交易日才能匹配到每月對應日期
        kline_rows = self.conn.execute(
            "SELECT date, close, volume FROM stock_history WHERE stock_id = ? ORDER BY date DESC LIMIT 60",
            (code,)
        ).fetchall()
        # NULL 防護：DB 回傳的 close/volume 可能為 NULL，用 0 替代
        kline_map = {r[0]: (float(r[1] or 0), int(r[2] or 0)) for r in kline_rows}  # date -> (close, volume)
        kline_dates = [r[0] for r in kline_rows]  # 依日期 DESC

        def _get_kline(date, idx=0):
            """取得該日 kline 資料，idx=0 為 close, 1 為 volume。
            若 exact match 找不到（例如集保日期為週末），找最近的交易日（<= date）。"""
            v = kline_map.get(date)
            if v is None:
                # 找最近的交易日（kline_dates 是 DESC，所以找第一個 <= date 的）
                nearest = next((d for d in kline_dates if d <= date), None)
                if nearest is not None:
                    v = kline_map.get(nearest)
            if v is None:
                return 0
            return v[idx] if v else 0

        def _prev_kline(date, idx=0):
            """取得前一筆 kline 資料（日期更晚的下一筆）"""
            if date in kline_dates:
                i = kline_dates.index(date)
                if i + 1 < len(kline_dates):
                    return _get_kline(kline_dates[i + 1], idx)
            # exact match 找不到，找小於 date 的最近交易日
            prev = next((d for d in kline_dates if d < date), None)
            if prev is not None:
                return _get_kline(prev, idx)
            return _get_kline(date, idx)

        def _fmt_close(date):
            """格式化收盤價（含顏色）"""
            c = _get_kline(date, 0)
            if not c:
                return "N/A"
            prev_c = _prev_kline(date, 0)
            change = c - prev_c if prev_c else 0
            pct = (change / prev_c * 100) if prev_c else 0.0
            return f"[{price_color(change, pct)}]{c:.2f}[/]"

        def _fmt_vol(date):
            """格式化成交量（含顏色）"""
            v = _get_kline(date, 1)
            prev_v = _prev_kline(date, 1)
            sheets = v // 1000 if v else 0
            if not v:
                return "0"
            return f"[{vol_color(v, prev_v)}]{sheets:,}[/]"

        def _fmt_amount(date):
            """格式化成交額（億）"""
            c = _get_kline(date, 0)
            v = _get_kline(date, 1)
            if not c or not v:
                return "0.00"
            return f"{c * v / 1e8:.2f}"

        if rows:
            rconsole.print("\n[bold cyan]📈 近10日法人買賣超 (千股):[/]")
            tbl = Table(box=box.SIMPLE)
            tbl.add_column("日期")
            tbl.add_column("收盤", justify="right")
            tbl.add_column("成交張數", justify="right")
            tbl.add_column("額(億)", justify="right")
            tbl.add_column("外資", justify="right")
            tbl.add_column("投信", justify="right")
            tbl.add_column("合計", justify="right")
            for row in rows:
                dt = row[0]
                tbl.add_row(
                    dt,
                    _fmt_close(dt),
                    _fmt_vol(dt),
                    _fmt_amount(dt),
                    self._fmt_change(int(row[1] or 0) // 1000, "", "d"),
                    self._fmt_change(int(row[2] or 0) // 1000, "", "d"),
                    self._fmt_change(int(row[3] or 0) // 1000, "", "d"),
                )
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
            tbl2.add_column("收盤", justify="right")
            tbl2.add_column("成交張數", justify="right")
            tbl2.add_column("額(億)", justify="right")
            tbl2.add_column("大戶比例", justify="right")
            tbl2.add_column("總人數", justify="right")
            tbl2.add_column("大戶人數", justify="right")
            for row in sh:
                dt = row[0]
                tbl2.add_row(
                    dt,
                    _fmt_close(dt),
                    _fmt_vol(dt),
                    _fmt_amount(dt),
                    f"{row[1]:.2f}%" if row[1] is not None else "N/A",
                    f"{row[2]:,}" if row[2] is not None else "N/A",
                    # whale_people 若為 NULL，用 whale_ratio 推算
                    f"{int(row[3] * row[1] / 100):,}" if (row[3] is not None and row[1] is not None) else "N/A",
                )
            rconsole.print(tbl2)
        else:
            rconsole.print("  [dim]查不到法人/集保資料[/]")


def scan_market(analyzer: StockAnalyzer, strat_choice: str = None, n_days: int = 2, sort_choice: int = 1):
    """市場掃描主函數（參數由 strategies.py 或 run_strategy 傳入，不再互動提示）"""
    hist_date, inst_date = analyzer.get_latest_dates()
    if not inst_date:
        return

    if strat_choice in ["1", "2"]:
        investor_type = "trust" if strat_choice == "1" else "foreign"
        investor_name = "投信" if strat_choice == "1" else "外資"
        results = analyzer.analyze_institutional_buying(
            investor_type=investor_type,
            min_consecutive_days=n_days,
            sort_choice=sort_choice,
        )
        if results:
            analyzer.display_institutional_results(results, investor_type, inst_date)
        else:
            rconsole.print(f"[yellow]📭 無符合標的 ({investor_name}連買 >= {n_days} 天)")
    elif strat_choice == "3":
        results, latest_date, prev_date = analyzer.analyze_main_force_vs_retail(sort_choice=sort_choice)
        if results:
            analyzer.display_main_force_results(results, latest_date or "N/A", prev_date or "N/A")
        else:
            rconsole.print("[yellow]📭 無符合集保人數下降，千張大戶增條件的標的")
    else:
        rconsole.print("[red]❌ 無效選擇")


def get_latest_date() -> str:
    """供 strategies.py 查詢資料基準日"""
    with StockAnalyzer() as a:
        return a.get_latest_dates()[1]


def run_strategy(params: dict):
    code = params.get('code')
    scan = params.get('scan', False)
    strat_choice = params.get('strat_choice')
    n_days = params.get('n_days', 2)
    sort_choice = params.get('sort_choice', 1)
    compact = params.get('compact', False)
    mobile = params.get('mobile', False)
    with StockAnalyzer() as analyzer:
        if scan:
            scan_market(analyzer, strat_choice=strat_choice, n_days=n_days, sort_choice=sort_choice)
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
                    scan_market(analyzer, strat_choice=cmd)
                    _wait_for_enter()
                    continue
                if not cmd:
                    scan_market(analyzer)
                    _wait_for_enter()
                    continue
                if len(cmd) == 4 and cmd.isdigit():
                    analyzer.display_single_stock(cmd)
                    _wait_for_enter()
                    continue
            except Exception as e:
                rconsole.print(f"[red]❌ 錯誤: {e}")
                _wait_for_enter()


class ChipsStrategy:
    """籌碼策略 wrapper - 提供統一的 analyze() 介面。"""

    def __init__(self, conn=None):
        self._analyzer = StockAnalyzer(conn)

    def analyze(self, stock_id: str) -> dict:
        """分析籌碼信號。回傳 strategy/stock_id/signal。"""
        conn = self._analyzer.conn
        # 計算外資+投信連續買超天數
        cons_f = self._count_consecutive(conn, stock_id, "foreign_net")
        cons_t = self._count_consecutive(conn, stock_id, "trust_net")

        if cons_f >= 3 and cons_t >= 3:
            signal = "bullish"
        elif cons_f <= -3 and cons_t <= -3:
            signal = "bearish"
        else:
            signal = "neutral"

        return {
            "strategy": "chips",
            "stock_id": stock_id,
            "signal": signal,
            "foreignConsecutiveDays": cons_f,
            "trustConsecutiveDays": cons_t,
        }

    @staticmethod
    def _count_consecutive(conn, stock_id: str, net_col: str) -> int:
        """計算連續買超（正）或連續賣超（負）天數。"""
        rows = conn.execute(
            f"SELECT date, {net_col} FROM institutional_data "
            "WHERE stock_id = ? ORDER BY date DESC LIMIT 30",
            (stock_id,),
        ).fetchall()
        if not rows:
            return 0
        cons = 0
        for r in rows:
            val = r[1] or 0
            if cons == 0:
                cons = 1 if val > 0 else (-1 if val < 0 else 0)
            else:
                if (cons > 0 and val > 0):
                    cons += 1
                elif (cons < 0 and val < 0):
                    cons -= 1
                else:
                    break
        return cons


if __name__ == "__main__":
    main()
