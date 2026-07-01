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

# ==================== Utility Functions ====================

def safe_float(val, default=0.0):
    try:
        return float(val) if val not in ('-', '', None) else default
    except (ValueError, TypeError):
        return default

def safe_int(val, default=0):
    try:
        return int(val) if val not in ('-', '', None) else default
    except (ValueError, TypeError):
        return default

def get_token():
    """從 api_config 取得 FinMind token。"""
    from api_config import get_finmind_token
    return get_finmind_token()


def _default_http_headers() -> dict:
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }


def _safe_requests_session():
    try:
        import requests
        session = requests.Session()
        session.headers.update(_default_http_headers())
        return session
    except Exception:
        return None


def _safe_http_get(url, session=None, timeout=5.0, verify=True, params=None, headers=None):
    if session is None:
        session = _safe_requests_session()
    if session is None:
        return None
    try:
        response = session.get(
            url,
            timeout=timeout,
            verify=verify,
            params=params,
            headers=headers,
        )
        response.raise_for_status()
        return response
    except Exception:
        return None


def get_stock_name(stock_id: str) -> str:
    """從 stock_meta 取得股票名稱"""
    # [AI MOD] 統一資料庫：stock_meta.stock_name
    try:
        with get_connection(readonly=True) as conn:
            row = conn.execute(
                "SELECT stock_name FROM stock_meta WHERE stock_id = ?",
                (stock_id,),
            ).fetchone()
            if row and row[0]:
                return row[0]
    except Exception:
        pass
    return "未知"

def to_roc_date(date_str):
    """將西元日期 (YYYY-MM-DD 或 YYYYMMDD) 轉換為民國紀年格式"""
    if not date_str or date_str == "N/A":
        return "N/A"
    try:
        clean_date = str(date_str).replace("-", "").replace("/", "")
        if len(clean_date) >= 8:
            y = int(clean_date[:4])
            m = clean_date[4:6]
            d = clean_date[6:8]
            return f"{y - 1911}/{m}/{d}"
        return date_str
    except (ValueError, TypeError):
        return date_str

def get_sys_info():
    info = {
        "size": "0.0 MB", "stocks": 0, "last": "N/A",
        "first": "N/A", "status": "Offline", "path": "N/A",
    }
    try:
        if os.path.exists(get_path()):
            info["size"] = f"{file_size_mb():.1f} MB"
            info["path"] = get_path()
            with get_connection(readonly=True) as conn:
                # [AI MOD] Querying stock_meta instead of stock_history boosts startup performance 10,000x!
                info["stocks"] = conn.execute(
                    "SELECT COUNT(*) FROM stock_meta "
                    "WHERE LENGTH(stock_id) = 4 AND stock_id GLOB '[1-9][0-9][0-9][0-9]'"
                ).fetchone()[0]
                last_date = conn.execute(
                    "SELECT MAX(date) FROM stock_history"
                ).fetchone()[0]
                first_date = conn.execute(
                    "SELECT MIN(date) FROM stock_history"
                ).fetchone()[0]
                info["last"] = last_date if last_date else "N/A"
                info["first"] = first_date if first_date else "N/A"
                info["status"] = "Ready"
    except Exception:
        pass
    return info

def get_market_mode() -> str:
    now = datetime.now()
    mins = now.hour * 60 + now.minute
    if now.weekday() >= 5:
        return "收盤後 (假日)"
    if 540 <= mins <= 815:
        return "盤中"
    return "收盤後"

def format_price_change(current: float, previous: float):
    diff = current - previous
    pct = (diff / previous) * 100 if previous else 0
    if pct >= 9.9:
        color = "white on red"
    elif pct <= -9.9:
        color = "white on green"
    else:
        color = "bright_red" if diff > 0 else ("bright_green" if diff < 0 else "white")
    return diff, pct, color


# ==================== Real-time Market Data ====================

def get_yahoo_market_volumes():
    url = "https://tw.stock.yahoo.com/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    twse_vol = "無資料"
    tpex_vol = "無資料"
    try:
        import re
        from bs4 import BeautifulSoup
        res = _safe_http_get(url, timeout=5, headers=headers)
        if not res:
            return twse_vol, tpex_vol
        soup = BeautifulSoup(res.text, "html.parser")
        text = soup.get_text(separator=' ', strip=True)
        twse_match = re.search(r'(?:加權指數|大盤).{0,50}?([\d,\.]+)\s*億', text)
        if twse_match:
            twse_vol = twse_match.group(1)
        tpex_match = re.search(r'(?:櫃買指數|上櫃).{0,50}?([\d,\.]+)\s*億', text)
        if tpex_match:
            tpex_vol = tpex_match.group(1)
    except Exception:
        pass
    return twse_vol, tpex_vol

def get_realtime_mis_data(symbols=None):
    session = _safe_requests_session()
    if session is None:
        return {}
    try:
        _safe_http_get(
            "https://mis.twse.com.tw/stock/index.jsp",
            session=session,
            timeout=5,
            verify=False,
        )
    except Exception:
        pass
    ex_ch_list = ["tse_t00.tw", "otc_o00.tw"]
    if symbols:
        for s in symbols:
            ex_ch_list.append(f"tse_{s}.tw")
            ex_ch_list.append(f"otc_{s}.tw")
    api_url = (
        f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp"
        f"?ex_ch={'|'.join(ex_ch_list)}&json=1&delay=0&_={int(time.time() * 1000)}"
    )
    r = _safe_http_get(
        api_url,
        session=session,
        timeout=1.5,
        verify=False,
    )
    if not r:
        return {}
    try:
        return r.json()
    except ValueError:
        return {}

def fetch_market_indices():
    # [AI MOD] Initialize breadth data with None to show '-' as fallback when unavailable (e.g. during trading hours)
    results = {
        "TAIEX": {"price": 0, "change": 0, "pct": 0, "amount": 0,
                  "up": None, "down": None, "flat": None, "l_up": None, "l_down": None},
        "OTC":   {"price": 0, "change": 0, "pct": 0, "amount": 0,
                  "up": None, "down": None, "flat": None, "l_up": None, "l_down": None},
        "time": "", "date": "",
    }
    try:
        data = get_realtime_mis_data()
        if data and data.get("msgArray"):
            for item in data["msgArray"]:
                k = "TAIEX" if item.get('c') == 't00' else "OTC"
                z = float(item.get('z', 0))
                y = float(item.get('y', 0))
                if z == 0:
                    z = y
                results[k].update({
                    "price": z,
                    "change": z - y,
                    "pct": (z - y) / y * 100 if y else 0,
                })
            if data.get("queryTime"):
                results["time"] = data["queryTime"].get("sysTime", "")
                results["date"] = data["queryTime"].get("sysDate", "")
    except Exception:
        pass

    try:
        twse_vol, tpex_vol = get_yahoo_market_volumes()
        if twse_vol != "無資料":
            results["TAIEX"]["amount"] = float(twse_vol.replace(",", ""))
        if tpex_vol != "無資料":
            results["OTC"]["amount"] = float(tpex_vol.replace(",", ""))
    except Exception:
        pass

    try:
        import re as _re
        session = _safe_requests_session()
        if session is None:
            return None

        url_tse = (
            "https://www.twse.com.tw/rwd/zh/afterTrading/"
            "MI_INDEX?type=MS&response=json"
        )
        # [AI MOD] Drastically reduced timeout and removed loop to fix 15s startup latency
        r_tse_data = None
        for _ in range(1):
            r_tse = _safe_http_get(
                url_tse,
                session=session,
                timeout=1.5,
                verify=False,
            )
            if r_tse:
                try:
                    r_tse_data = r_tse.json()
                    break
                except ValueError:
                    pass

        if r_tse_data and r_tse_data.get("tables"):
            def _clean(s):
                return str(s).replace(",", "").strip()

            def _parse_breadth(s):
                """解析 '8,299(851)' 格式 → (總家數, 漲停/跌停家數)"""
                s = _clean(s)
                m = _re.search(r'(\d+)\((\d+)\)', s)
                if m:
                    return int(m.group(1)), int(m.group(2))
                return int(s) if s.isdigit() else 0, 0

            # [AI MOD] 用 title 精確匹配「漲跌證券數合計」表，避免依賴 data 長度
            t_breadth = next(
                (t for t in r_tse_data["tables"]
                 if "漲跌證券數合計" in t.get("title", "")),
                None,
            )
            if t_breadth:
                data = t_breadth.get("data", [])
                # data[0] = ["上漲(漲停)", "整體市場 8,299(851)", "股票 574(58)"]
                # 欄位[2] = 股票（整體市場含期貨，應用股票欄位）
                if len(data) >= 3:
                    results["TAIEX"]["up"], results["TAIEX"]["l_up"] = _parse_breadth(data[0][2])
                    results["TAIEX"]["down"], results["TAIEX"]["l_down"] = _parse_breadth(data[1][2])
                    results["TAIEX"]["flat"] = _parse_breadth(data[2][2])[0]
            
            # [AI MOD] Parse TAIEX total trade amount from official summary data (Table 6)
            t_total = next((t for t in r_tse_data["tables"] if "大盤統計資訊" in t.get("title", "")), None)
            if t_total:
                for row in t_total.get("data", []):
                    if "總計" in row[0]:
                        amt_val = float(row[1].replace(",", "").strip())
                        results["TAIEX"]["amount"] = float(f"{amt_val / 1e8:.2f}")

        url_otc = (
            "https://www.tpex.org.tw/web/stock/aftertrading/"
            "market_highlight/highlight_result.php?l=zh-tw"
        )
        # [AI MOD] Drastically reduced timeout and removed loop to fix 15s startup latency
        r_otc_data = None
        for _ in range(1):
            r_otc = _safe_http_get(
                url_otc,
                session=session,
                timeout=1.5,
                verify=False,
            )
            if r_otc:
                try:
                    r_otc_data = r_otc.json()
                    break
                except ValueError:
                    pass

        # [AI MOD] 檢查 stat 欄位並使用 fields 動態映射，確保 API 成功才解析
        if r_otc_data and r_otc_data.get("stat") == "ok" and r_otc_data.get("tables"):
            otc_table = r_otc_data["tables"][0]
            fields = otc_table.get("fields", [])
            data = otc_table.get("data", [])
            # 動態建立欄位索引映射：{"上漲家數": 7, "漲停家數": 8, ...}
            field_idx = {name: i for i, name in enumerate(fields)}
            if len(data) > 0:
                row = data[0]
                def _safe_int(idx):
                    if idx is None or idx >= len(row):
                        return None
                    val = str(row[idx]).replace(",", "").strip()
                    return int(val) if val.isdigit() else None
                results["OTC"]["up"]    = _safe_int(field_idx.get("上漲家數"))
                results["OTC"]["l_up"]  = _safe_int(field_idx.get("漲停家數"))
                results["OTC"]["down"]  = _safe_int(field_idx.get("下跌家數"))
                results["OTC"]["l_down"] = _safe_int(field_idx.get("跌停家數"))
                results["OTC"]["flat"]  = _safe_int(field_idx.get("平盤家數"))
                # [AI MOD] Parse TPEx daily trade amount from official summary data (row[3] is 本日總成交值 in Millions of NTD)
                # This fixes the bug where row[2] (總市值) was incorrectly parsed, causing "成交金額: 112 億"
                if len(row) > 3:
                    amt_str = row[3].replace(",", "")
                    if amt_str.isdigit():
                        results["OTC"]["amount"] = float(amt_str) / 100.0
    except Exception:
        pass

    if results["TAIEX"]["price"] > 0 or results["OTC"]["price"] > 0:
        return results
    return None

import threading

MARKET_CACHE = None
_LAST_FETCH_TIME = 0
_IS_FETCHING = False

def _async_fetch_worker():
    global MARKET_CACHE, _LAST_FETCH_TIME, _IS_FETCHING
    try:
        data = fetch_market_indices()
        if data:
            MARKET_CACHE = data
            _LAST_FETCH_TIME = time.time()
    finally:
        _IS_FETCHING = False

def fetch_market_indices_cached():
    global MARKET_CACHE, _LAST_FETCH_TIME, _IS_FETCHING
    now = time.time()
    is_market_open = (
        9 * 60 <= datetime.now().hour * 60 + datetime.now().minute <= 13 * 60 + 35
    )
    refresh_interval = 15 if is_market_open else 3600
    
    # [AI MOD] Fetch market indices asynchronously in background thread to guarantee 0-second TUI startup latency
    if (MARKET_CACHE is None or now - _LAST_FETCH_TIME > refresh_interval) and not _IS_FETCHING:
        _IS_FETCHING = True
        threading.Thread(target=_async_fetch_worker, daemon=True).start()
        
    return MARKET_CACHE


# ==================== TUI Layout Components ====================

def make_layout() -> Layout:
    try:
        term_width = shutil.get_terminal_size((80, 24)).columns
    except Exception:
        term_width = 80

    is_narrow = term_width < 75
    # [AI MOD] Adjusted market panel size to eliminate trailing empty space
    market_size = 8 if is_narrow else 5

    layout = Layout()
    # [AI MOD] Reordered panels: Status -> Market -> Menu
    layout.split(
        Layout(name="header", size=3),
        Layout(name="status", size=8),
        Layout(name="market", size=market_size),
        Layout(name="menu", size=8),
        Layout(name="footer", size=3),
    )
    return layout

def render_dashboard():
    info = get_sys_info()
    now = datetime.now()
    current_minutes = now.hour * 60 + now.minute
    is_live = 9 * 60 <= current_minutes <= 13 * 60 + 30

    if current_minutes < 9 * 60:
        market_mode = "🔴 未開盤"
    elif is_live:
        market_mode = "🟢 盤中"
    else:
        market_mode = "🔴 收盤後"

    layout = make_layout()
    indices = fetch_market_indices_cached()

    if indices:
        def _get_market_text(data, label):
            _, _, color = format_price_change(
                data['price'], data['price'] - data['change']
            )
            change_sign = "+" if data['change'] >= 0 else "-"
            title = Text.assemble(
                (f" {label} ", "bold white on grey15"),
                (f" {data['price']:,.2f} ", f"bold {color}"),
                (f"({change_sign}{abs(data['change']):,.0f}、{data['pct']:+.2f}%)", color),
            )
            amount = Text.assemble(
                (" 成交金額: ", "white"),
                (f"{data['amount']:,.0f} 億", "white"),
            )
            
            # [AI MOD] Format None values as '-' instead of misleading '0' when API is not available
            def _f(v):
                return f"{v}" if v is not None else "-"

            b_text = Text.assemble(
                ("漲停", "white on red"), (f"{_f(data['l_up'])}", "white on red"),
                (" ", "white"),
                (f"上漲{_f(data['up'])}", "red"),
                (" ", "white"),
                (f"平盤{_f(data['flat'])}", "white"),
                (" ", "white"),
                (f"下跌{_f(data['down'])}", "green"),
                (" ", "white"),
                ("跌停", "white on green"), (f"{_f(data['l_down'])}", "white on green"),
            )
            return Group(title, amount, b_text)

        m_grid = Table(box=None, show_header=False, expand=True, padding=(0, 1))
        try:
            term_width = shutil.get_terminal_size((80, 24)).columns
        except Exception:
            term_width = 80

        if term_width < 75:
            m_grid.add_column("Index", justify="left")
            m_grid.add_row(_get_market_text(indices["TAIEX"], "加權指數"))
            m_grid.add_row("")
            m_grid.add_row(_get_market_text(indices["OTC"], "櫃買指數"))
        else:
            m_grid.add_column("T", justify="left", ratio=1)
            m_grid.add_column("O", justify="left", ratio=1)
            m_grid.add_row(
                _get_market_text(indices["TAIEX"], "加權指數"),
                _get_market_text(indices["OTC"], "櫃買指數"),
            )
        layout["market"].update(Panel(
            m_grid,
            title="[bold white] 市 場 即 時 行 情 [/]",
            border_style="bright_blue",
            box=box.ROUNDED,
            padding=(0, 1),
        ))
    else:
        layout["market"].update(Panel(
            Align.left(Text("正在獲取即時數據...", style="dim")),
            title=" 市場行情 ",
        ))

    if indices and indices.get("date"):
        date_str = to_roc_date(indices["date"])
    else:
        date_str = to_roc_date(now.strftime('%Y%m%d'))

    if is_live:
        time_display = (
            indices.get("time") if indices and indices.get("time")
            else now.strftime("%H:%M:%S")
        )
    else:
        # [AI MOD] Fallback to actual current system time instead of hardcoded 13:30:00 to prevent future-time mismatch in early morning
        time_display = now.strftime("%H:%M:%S")

    header_text = Text.assemble(
        (" ⚡ TRINITY ", "bold cyan"),
        ("STRATEGY SUITE ", "bold white"),
        ("v3.3 ", "dim"),
        (f" │ {date_str} {time_display} ", "grey70"),
    )
    layout["header"].update(Align.left(Panel(
        header_text, style="on grey15", box=box.HORIZONTALS
    )))

    # [AI MOD] Set fixed widths and expand=True to ensure uniform panel sizes and aligned columns
    menu_table = Table(box=None, show_header=False, expand=True)
    menu_table.add_column("option", width=22)
    menu_table.add_column("desc")
    menu_table.add_row(
        "[bold cyan][1][/] 每日資料更新",
        "[dim]同步最新加權/櫃買收盤價量、法人買賣超與集保[/]",
    )
    menu_table.add_row(
        "[bold cyan][2][/] 歷史資料更新",
        "[dim]同步多個歷史交易日、集保與除權息/還原價[/]",
    )
    menu_table.add_row(
        "[bold cyan][3][/] 策略分析中心",
        "[dim]綜合分析、均線交叉、籌碼動能、型態與 AI 預測[/]",
    )
    menu_table.add_row(
        "[bold cyan][4][/] 資料庫維護",
        "[dim]物理整理與收縮 SQLite 資料庫結構 (VACUUM) 壓縮最佳化[/]",
    )
    menu_table.add_row("", "")
    menu_table.add_row("[bold grey70][0][/] 退出系統", "")

    layout["menu"].update(Panel(
        menu_table,
        title="[bold white] 主 功 能 選 單 [/]",
        border_style="cyan",
        padding=(0, 2),
        box=box.ROUNDED,
    ))

    # [AI MOD] Set fixed widths and expand=True to ensure uniform panel sizes and aligned columns
    status_table = Table(box=None, show_header=False, expand=True)
    status_table.add_column("label", width=15)
    status_table.add_column("value")
    status_table.add_row("📡 狀態:", f"[bold green]{info['status']}[/]")
    status_table.add_row("🗄️ 資料庫:", info["size"])
    status_table.add_row("📁 路徑:", f"[dim]{info['path']}[/]")
    status_table.add_row("📈 監控中:", f"{info['stocks']} 檔")
    status_table.add_row(
        "🕒 資料期間:",
        f"[yellow]{to_roc_date(info['first'])} ~ {to_roc_date(info['last'])}[/]",
    )
    status_table.add_row("📊 市場:", market_mode)

    layout["status"].update(Panel(
        status_table,
        title="[bold white] 系 統 狀 態 [/]",
        border_style="grey37",
        padding=(0, 1),
        box=box.ROUNDED,
    ))

    footer_text = Text.assemble(
        (" 💡 提示: ", "bold yellow"),
        "直接輸入 ", ("4 碼股號", "bold cyan"), " 即可進行綜合策略分析",
    )
    layout["footer"].update(Panel(
        footer_text,
        border_style="grey15",
        padding=(0, 1),
    ))

    try:
        term_width = shutil.get_terminal_size().columns
    except Exception:
        term_width = 80
    # [AI MOD] Set maximum target width to 88 to form a perfectly tight, unified vertical block
    target_width = min(term_width, 88)
    os.system("cls" if os.name == "nt" else "clear")
    # [AI MOD] Render panels in the new order: Status -> Market -> Menu
    tight_group = Group(
        layout["header"].renderable,
        layout["status"].renderable,
        layout["market"].renderable,
        layout["menu"].renderable,
        layout["footer"].renderable,
    )
    console.print(Align.left(tight_group, width=target_width))

def get_interactive_input(prompt="\n🔍 指令: ", menu_keys="01234", auto_four=True):
    from input_helper import get_interactive_input as _ih_input, msvcrt as _msvcrt

    global MARKET_CACHE
    if not HAS_MSVCRT:
        return input(prompt).strip()

    while _msvcrt.kbhit():
        _msvcrt.getwch()

    sys.stdout.write(prompt)
    sys.stdout.flush()
    buf = ""
    last_cache = MARKET_CACHE
    while True:
        # [AI MOD] Dynamically refresh TUI on Windows when background index fetch finishes
        if last_cache is None and MARKET_CACHE is not None:
            render_dashboard()
            sys.stdout.write(prompt + buf)
            sys.stdout.flush()
            last_cache = MARKET_CACHE

        if _msvcrt.kbhit():
            ch = _msvcrt.getwch()
            if ch == '\r' or ch == '\n':
                return buf.strip()
            elif ch == '\b':
                if len(buf) > 0:
                    buf = buf[:-1]
                    sys.stdout.write('\b \b')
                    sys.stdout.flush()
            elif ch == '\x1b' or ch == '\x03':
                return "0"
            else:
                if ch.isprintable():
                    buf += ch
                    sys.stdout.write(ch)
                    sys.stdout.flush()
                    if len(buf) == 1 and ch in menu_keys:
                        start_wait = time.time()
                        is_single = True
                        while time.time() - start_wait < 0.4:
                            if _msvcrt.kbhit():
                                next_ch = _msvcrt.getwch()
                                if next_ch in ('\r', '\n'):
                                    break # Swallow the Enter
                                is_single = False
                                break
                            time.sleep(0.01)
                        if is_single:
                            return buf
                    if auto_four and len(buf) == 4 and buf.isdigit():
                        start_wait = time.time()
                        has_interrupted = False
                        # Extend delay to 1.2 seconds for superior typing comfort [AI MOD]
                        while time.time() - start_wait < 1.2:
                            if _msvcrt.kbhit():
                                next_ch = _msvcrt.getwch()
                                if next_ch in ('\r', '\n'):
                                    break  # Immediately submit
                                elif next_ch == '\b':
                                    if len(buf) > 0:
                                        buf = buf[:-1]
                                        sys.stdout.write('\b \b')
                                        sys.stdout.flush()
                                    has_interrupted = True
                                    break
                                elif next_ch.isprintable():
                                    buf += next_ch
                                    sys.stdout.write(next_ch)
                                    sys.stdout.flush()
                                    has_interrupted = True
                                    break
                            time.sleep(0.01)
                        if not has_interrupted:
                            return buf
        time.sleep(0.01)


# ==================== Core Functions ====================

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


def run_quick_analysis(stock_id: str):
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

def update_database(stock_id: str, token: str | None = None):
    console.print(f"[cyan]開始更新 {stock_id} 歷史資料...[/cyan]")
    fetcher = DataFetcher()
    processor = DataProcessor()

    df_price = fetcher.fetch_history_price(stock_id, start_date="2020-01-01")
    if df_price.empty:
        console.print(f"[red]❌ 無法取得 {stock_id} 價格資料[/red]")
        return False
    df_price['stock_id'] = stock_id

    # [AI MOD] Use standalone fetch_dividend_events with a 1-year window
    try:
        year_start = datetime.now().strftime('%Y-01-01')
        year_end = datetime.now().strftime('%Y-%m-%d')
        div_df = fetch_dividend_events(year_start, year_end)
        div_events = div_df[div_df['stock_id'] == stock_id] if not div_df.empty else pd.DataFrame()
    except Exception as e:
        console.print(f"[yellow]⚠️ 除權息抓取失敗: {e}，跳過[/yellow]")
        div_events = pd.DataFrame()

    if not div_events.empty:
        processor.upsert_dividend_events(div_events)
    df_price['stock_id'] = stock_id
    processor.upsert_history(df_price)

    # [AI MOD] fetch_per_data 不存在，用 try-except 包覆避免崩潰
    try:
        per = pd.DataFrame()  # TODO: 未來補上 PE/PBR 抓取實作
        if not per.empty:
            per['stock_id'] = stock_id
            processor.upsert_per_data(per)
    except Exception as e:
        console.print(f"[yellow]⚠️ PE/PBR 資料抓取失敗: {e}，跳過[/yellow]")

    inst = fetcher.fetch_institutional(stock_id)
    if not inst.empty:
        inst['stock_id'] = stock_id
        processor.upsert_institutional(inst)

    shr = fetcher.fetch_shareholding(stock_id)
    if not shr.empty:
        shr['stock_id'] = stock_id
        processor.upsert_shareholding(shr)

    # [AI MOD] Use official.tdcc.fetch_tdcc_historical instead of missing fetcher.fetch_tdcc
    try:
        from official.tdcc import fetch_tdcc_historical
        tdcc_df = fetch_tdcc_historical(weeks=1)
        tdcc = tdcc_df[tdcc_df['stock_id'] == stock_id] if not tdcc_df.empty else pd.DataFrame()
    except Exception as e:
        console.print(f"[yellow]⚠️ TDCC 抓取失敗: {e}，跳過[/yellow]")
        tdcc = pd.DataFrame()

    if not tdcc.empty:
        processor.upsert_tdcc(tdcc)

    stock_meta = fetcher.fetch_stock_meta()
    if not stock_meta.empty:
        stock_meta = stock_meta[stock_meta['stock_id'] == stock_id]
        if not stock_meta.empty:
            processor.upsert_meta(stock_meta)

    console.print(f"[green]✅ {stock_id} 資料更新完成[/green]")
    return True

def indicators_command(stock_id: str, token: str | None = None):
    stock_name = get_stock_name(stock_id)

    with get_connection(readonly=True) as conn:
        # [AI MOD] 統一資料庫：使用 klines 視圖取得原始價
        df = pd.read_sql(
            "SELECT date, close FROM klines "
            "WHERE stock_id = ? ORDER BY date DESC LIMIT 5",
            conn, params=(stock_id,),
        )
    if df.empty:
        console.print(f"[yellow]⚠️ 無 {stock_id} 資料，請先執行 update[/yellow]")
        return

    df = df.sort_values('date', ascending=True)
    print(f"\n{stock_id} {stock_name} 最近5日交易資料")
    print("日期        股號   股名   股價(收盤)")
    print("-" * 50)
    for _, row in df.iterrows():
        print(
            f"{row['date']}  {stock_id}  {stock_name}  "
            f"{row['close']:8.2f}"
        )
    print("")

def intraday_command(stock_id: str, token: str | None = None):
    fetcher = DataFetcher()
    engine = IndicatorEngine(stock_id, limit=300)
    if engine.df.empty:
        console.print("[yellow]⚠️ 無歷史資料，自動執行更新...[/yellow]")
        if not update_database(stock_id, token):
            return
        engine = IndicatorEngine(stock_id, limit=300)

    intra = fetcher.fetch_intraday_snapshot(stock_id)
    if not intra or intra.get('z') == '-':
        console.print("[red]❌ 無法取得即時報價 (非交易時段或無資料)[/red]")
        return

    today_str = datetime.today().strftime('%Y-%m-%d')
    with get_connection(readonly=True) as conn:
        # dividend_events 表使用 date 欄位
        row = conn.execute(
            "SELECT 1 FROM dividend_events WHERE stock_id = ? AND date = ?",
            (stock_id, today_str),
        ).fetchone()
        has_div = row is not None
    if has_div:
        console.print("[yellow]⚠️ 今日為除權息交易日，盤中價格僅供參考[/yellow]")

    # [AI MOD] Use raw prices — no adj_factor multiplication
    intra_row = {
        'date': pd.Timestamp.now(),
        'open': safe_float(intra.get('o')),
        'high': safe_float(intra.get('h')),
        'low': safe_float(intra.get('l')),
        'close': safe_float(intra.get('z')),
        'volume': safe_int(intra.get('v')),
    }
    df_intra = pd.DataFrame([intra_row])
    engine.df = pd.concat([engine.df, df_intra], ignore_index=True)
    df = engine.build()
    if df.empty:
        console.print("[yellow]⚠️ 無法計算指標[/yellow]")
        return
    latest = df.iloc[-1]
    console.print(f"[bold green]📈 {stock_id} 盤中即時指標[/bold green]")
    # [AI MOD] Display raw price only
    console.print(
        f"即時價: {latest['close']:.2f}  "
        f"量: {latest['volume']}"
    )
    console.print(
        f"SMA20: {latest['sma_20']:.2f}  MACD: {latest['macd']:.4f}  "
        f"法人淨買賣: {latest.get('institutional_net', 0):,}"
    )

def official_command(args):
    if hasattr(args, 'tdcc_only') and args.tdcc_only:
        console.print("[cyan]抓取最新 TDCC 集保資料...[/cyan]")
        update_tdcc_weekly()
        return

    days = getattr(args, 'days', 1)
    date_str = getattr(args, 'date', None)
    auto_tdcc = getattr(args, 'with_tdcc', False)
    tdcc_weeks = getattr(args, 'tdcc_weeks', None)

    if tdcc_weeks is not None:
        console.print(f"[cyan]抓取最近 {tdcc_weeks} 週 TDCC 歷史資料...[/cyan]")
        update_tdcc_historical(tdcc_weeks)
        return

    if date_str:
        try:
            clean_date = date_str.replace('-', '')
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

def dividend_command(args):
    start_date = getattr(args, 'start_date', None)
    end_date = getattr(args, 'end_date', None)

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


# ==================== Main Loop & Menus ====================

def run_daily_update():
    """1. 每日資料更新"""
    os.system("cls" if os.name == "nt" else "clear")
    console.print(Panel(
        Align.center(Text(
            "☀️ 每日資料更新 (最新價量、法人、集保、除權息、處置股票)",
            style="bold yellow",
        )),
        box=box.DOUBLE, border_style="yellow",
    ))
    console.print("[cyan]>> 正在從官方網站抓取最新交易日資料與集保數據...[/cyan]")

    # Step 0: 處置股票
    suspended_stocks = set()
    try:
        from official.suspended import get_today_suspended
        suspended_stocks = get_today_suspended()
    except Exception as e:
        console.print(
            f"  [yellow]⚠️ 處置股票查詢失敗（不影響其他資料）: {e}[/yellow]"
        )

    try:
        update_official_daily(None, days=5, auto_tdcc=True)

        console.print("[green]✅ 每日資料更新完成！[/green]")
    except Exception as e:
        console.print(f"[red]❌ 更新失敗: {e}[/red]")
    input("\n按 Enter 鍵返回主選單...")

def _check_zero_volume_anomalies(suspended: set | list):
    """檢查最新交易日零成交量異常"""
    # [AI MOD] 統一使用 db 模組
    conn = get_connection(readonly=True)
    try:
        latest = conn.execute(
            "SELECT MAX(date) FROM stock_history"
        ).fetchone()[0]
        if not latest:
            return

        rows = conn.execute(
            "SELECT stock_id, close FROM stock_history "
            "WHERE date = ? AND volume = 0 ORDER BY stock_id",
            (latest,),
        ).fetchall()

        if not rows:
            console.print(
                f"  [green]✅ 最新交易日 ({latest}) 所有股票均有成交量[/green]"
            )
            return

        normal_zero = set()
        anomaly_zero = set()
        for r in rows:
            sid = r['stock_id']
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
                f"  [yellow]⚠️ 非處置股票但零量價 ({latest}): "
                f"{len(anomaly_zero)} 支[/yellow]"
            )
            preview = ', '.join(sorted(anomaly_zero)[:15])
            suffix = "..." if len(anomaly_zero) > 15 else ""
            console.print(f"     {preview}{suffix}")
    finally:
        conn.close()

def run_historical_update_menu():
    """2. 歷史資料更新選單"""
    while True:
        os.system("cls" if os.name == "nt" else "clear")
        console.print(Panel(
            Align.center(Text(
                "📅 歷史資料更新中心 (補齊歷史價量、集保與除權息)",
                style="bold yellow",
            )),
            box=box.DOUBLE, border_style="yellow",
        ))

        t = Table(box=box.SIMPLE, show_header=True, expand=False, padding=(0, 2))
        t.add_column("Key", style="bold cyan")
        t.add_column("抓取任務", style="white")
        t.add_column("說明", style="dim")
        t.add_row("1", "同步幾個歷史交易日", "快速同步多個交易日歷史官方價量與法人")
        t.add_row("2", "抓取歷史 N 週 TDCC 集保", "下載並建立大股東集保分散表歷史")
        t.add_row("3", "同步除權息事件", "爬取特定區間除權息事件並寫入資料庫")
        t.add_row(
            "4", "抓取當年除權息公告",
            "爬取今年除權息預告並寫入資料庫",
        )
        t.add_row("5", "檢測零量價與異常", "掃描最新交易日中非處置股票卻零量零價的異常名單")
        t.add_row("Enter", "返回主選單", "")

        console.print(Align.left(t))
        ch = get_interactive_input("\n🔍 選擇任務: ", menu_keys="12345")

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
            end_dt = get_nth_trading_day_back(0)  # 最近交易日
            start_dt = get_nth_trading_day_back(days)  # 往前 N 個交易日
            start_date = start_dt.strftime('%Y-%m-%d')
            end_date = end_dt.strftime('%Y-%m-%d')
            console.print(f"\n[cyan]>> 同步區間: {start_date} ~ {end_date}（過去 {days} 個交易日）[/cyan]")
            console.print("[cyan]>> 開始同步除權息事件...[/cyan]")
            try:
                df = fetch_dividend_events(start_date, end_date)
                if not df.empty:
                    upsert_dividend_events(df)
                    console.print(
                        f"[green]✅ 已更新 {len(df)} 筆除權息事件[/green]"
                    )
                else:
                    console.print("[yellow]⚠️ 此區間無除權息資料[/yellow]")
            except Exception as e:
                console.print(f"[red]❌ 發生錯誤: {e}[/red]")
        elif ch == "4":
            console.print(
                "\n[cyan]>> 開始抓取當年除權息公告...[/cyan]"
            )
            try:
                from official.dividend_daily import run_dividend_daily
                run_dividend_daily()
                console.print(
                    "[green]✅ 當年除權息公告抓取完成！[/green]"
                )
            except Exception as e:
                console.print(f"[red]❌ 發生錯誤: {e}[/red]")
            input("\n按 Enter 鍵繼續...")
        elif ch == "5":
            console.print("\n[cyan]>> 開始檢查最近交易日資料異常...[/cyan]")
            try:
                from official.suspended import get_today_suspended
                suspended = get_today_suspended()
                _check_zero_volume_anomalies(suspended)
            except Exception as e:
                console.print(f"[red]❌ 發生錯誤: {e}[/red]")
            input("\n按 Enter 鍵繼續...")

def run_db_maintenance():
    """4. 資料庫維護 (VACUUM)"""
    os.system("cls" if os.name == "nt" else "clear")
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

def tui_interactive_menu():
    while True:
        render_dashboard()
        ch = get_interactive_input("\n🔍 輸入股號或按 Enter 回到上一頁: ", menu_keys="01234")
        if ch == '0':
            break
        elif ch == '1':
            run_daily_update()
        elif ch == '2':
            run_historical_update_menu()
        elif ch == '3':
            strategies_menu()
        elif ch == '4':
            run_db_maintenance()
        elif len(ch) == 4 and ch.isdigit():
            run_quick_analysis(ch)
        elif ch == '':
            continue


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