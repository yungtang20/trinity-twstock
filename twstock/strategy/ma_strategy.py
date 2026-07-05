#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ma_strategy.py - 均線趨勢策略模組 [AI MOD]
包含移動平均線（季線/年線）計算、扣抵值分析、明日預測與自適應面板呈現。
"""

import os
import sqlite3
import sys

import pandas as pd
from rich import box
from rich.table import Table

# --- Windows Encoding Fix ---
if sys.platform == "win32":
    os.system("chcp 65001 > nul")
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stdin.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

# [AI MOD] 集中式 Console：解決 Windows cp950 無法渲染 emoji 的問題
# [AI MOD] Unified session scan cache to make switching strategy lightning-fast
import time as _time_mod

# Import unified connection factory
from twstock.db import get_connection
from twstock.terminal import console

_CACHE_TTL = 300  # 5 分鐘

_SCAN_CACHE = {
    "date": None,
    "min_volume": None,
    "strat_choice": None,
    "results": None,
    "ts": 0,
}
from twstock.display import ma_color, price_color, price_rich, vol_color  # [AI MOD]
from twstock.strategy._utils import fetch_klines

try:
    from twstock.input_helper import _getch_windows, _kbhit_windows
except ImportError:
    from input_helper import _getch_windows, _kbhit_windows


def _compute_ma_with_deduction(closes: list, period: int):
    """
    計算 MA 值、扣抵值、明日 MA 預測方向。

    Returns:
        dict with keys:
            ma          : 目前 MA 值
            deduction   : 明日扣抵值（即將被移除的舊價格）
            trend       : MA 趨勢方向 ("↑ 上揚" / "↓ 下彎" / "→ 走平")
            tomorrow    : 明日預測方向 ("↑" / "↓" / "→")
    """
    if len(closes) < period:
        return {
            "ma": closes[-1] if len(closes) > 0 else 0,
            "deduction": 0,
            "trend": "→ 走平",
            "tomorrow": "→",
        }

    # 目前 MA
    current_ma = sum(closes[-period:]) / period
    current_price = closes[-1]

    # 扣抵值 = 明天將被移除的價格 = 第 period 個前的收盤價 (即 index 是 -period)
    deduction_price = closes[-period]

    # [AI MOD] Calculate today's MA trend by comparing current price with today's deduction price (closes[-period-1])
    if len(closes) >= period + 1:
        today_deduction = closes[-period - 1]
        if current_price > today_deduction + 0.01:
            trend = "↑ 上揚"
        elif current_price < today_deduction - 0.01:
            trend = "↓ 下彎"
        else:
            trend = "→ 走平"
    else:
        trend = "→ 走平"

    # 明日預測：若扣抵值 < 最新收盤價，MA 會上升
    if deduction_price < current_price * 0.995:
        tomorrow = "↑"
    elif deduction_price > current_price * 1.005:
        tomorrow = "↓"
    else:
        tomorrow = "→"

    return {
        "ma": round(current_ma, 2),
        "deduction": round(deduction_price, 2),
        "trend": trend,
        "tomorrow": tomorrow,
    }


def _render_mobile_ma(data, code, name):
    """Mobile layout with deduction analysis."""
    console.print(f"[dim]{'─ 3 均線 ' + code + ' ' + name}{'─' * 20}[/]")  # [AI MOD]

    close = data["close"]
    prev_close = data.get("prev_close", close)
    ma25 = data.get("ma25")  # [AI MOD]
    ma60 = data["ma60"]  # dict from _compute_ma_with_deduction
    ma200 = data["ma200"]  # dict from _compute_ma_with_deduction
    bias = data["bias"]

    console.print(f"收盤 {price_rich(close, prev_close)}  [{data['color']}]{data['trend']}[/]")

    # MA25 with deduction
    if ma25:
        d25 = ma25["deduction"]
        console.print(
            f"MA25  {ma25['ma']:.2f}  {ma25['trend']}  " f"扣抵 {d25:.2f} {ma25['tomorrow']}"
        )  # [AI MOD]

    # MA60 with deduction
    d60 = ma60["deduction"]
    console.print(f"MA60  {ma60['ma']:.2f}  {ma60['trend']}  " f"扣抵 {d60:.2f} {ma60['tomorrow']}")

    # MA200 with deduction
    d200 = ma200["deduction"]
    console.print(
        f"MA200 {ma200['ma']:.2f}  {ma200['trend']}  " f"扣抵 {d200:.2f} {ma200['tomorrow']}"
    )

    if abs(bias) > 20:
        console.print(f"乖離 {bias:+.1f}%  [bright_red]⚠ 過熱[/]")
    else:
        console.print(f"乖離 {bias:+.1f}%")


def _render_full_ma(data, code, name):
    """Desktop table with deduction column."""
    close = data["close"]
    prev_close = data.get("prev_close", close)
    ma25 = data.get("ma25")  # [AI MOD]
    ma60 = data["ma60"]
    ma200 = data["ma200"]
    bias = data["bias"]

    t = Table(
        title=f"📊 {code} {name} 均線技術分析",
        box=box.ROUNDED,
        border_style="cyan",
        expand=False,
        padding=(0, 1),
        title_style="bold cyan",
    )
    t.add_column("指標", style="bold")
    t.add_column("數值")
    t.add_column("趨勢")

    # Format close price into two lines [AI MOD]
    change = close - prev_close
    pct = (change / prev_close * 100) if prev_close else 0.0
    c = price_color(change, pct)
    arrow = "▲" if change > 0 else ("▼" if change < 0 else "─")
    sign = "+" if change > 0 else ""
    price_two_lines = f"[{c}]{close:.2f}\n{arrow}{abs(pct):.1f}%({sign}{change:.2f})[/]"

    # Format trend text into two lines if it contains parentheses [AI MOD]
    trend_val = data["trend"]
    if " (" in trend_val:
        trend_val = trend_val.replace(" (", "\n(")
    elif "(" in trend_val:
        trend_val = trend_val.replace("(", "\n(")

    t.add_row("目前收盤", price_two_lines, f"[{data['color']}]{trend_val}[/]")
    if ma25:
        t.add_row(
            "MA25 (月線)",
            f"[{ma_color(ma25['trend'])}]{ma25['ma']:.2f}[/]",
            f"[{ma_color(ma25['trend'])}]{ma25['trend']}[/]",
        )
    t.add_row(
        "MA60 (季線)",
        f"[{ma_color(ma60['trend'])}]{ma60['ma']:.2f}[/]",
        f"[{ma_color(ma60['trend'])}]{ma60['trend']}[/]",
    )
    t.add_row(
        "MA200 (年線)",
        f"[{ma_color(ma200['trend'])}]{ma200['ma']:.2f}[/]",
        f"[{ma_color(ma200['trend'])}]{ma200['trend']}[/]",
    )

    bias_color = "bright_red" if abs(bias) > 20 else "white"
    bias_label = "⚠過熱" if abs(bias) > 20 else "正常"
    t.add_row("季線乖離", f"[{bias_color}]{bias:+.2f}%[/]", f"[{bias_color}]{bias_label}[/]")

    console.print(t)

    d60_msg = "明日 MA60 繼續下降" if ma60["deduction"] > close else "明日 MA60 可能上揚/走平"
    d200_msg = "明日 MA200 繼續下降" if ma200["deduction"] > close else "明日 MA200 可能上揚/走平"
    console.print(
        f"  解讀：MA60 扣抵 {ma60['deduction']:.2f} {'<' if ma60['deduction'] < close else '>'} 收盤 {close:.2f}，{d60_msg}"
    )
    console.print(
        f"        MA200 扣抵 {ma200['deduction']:.2f} {'<' if ma200['deduction'] < close else '>'} 收盤 {close:.2f}，{d200_msg}"
    )


def scan_market_stocks(
    conn: sqlite3.Connection,
    min_volume: int = 500,
    strat_choice: str = None,
    sort_choice: str = None,
) -> None:
    import time as _time

    _t0 = _time.time()

    # [AI MOD] 自動刷新缺失指標
    try:
        from twstock.strategy.indicators import ensure_indicators_all

        refreshed = ensure_indicators_all(conn)
        if refreshed:
            console.print(f"[dim]🔄 自動刷新 {refreshed} 檔指標[/dim]")
    except Exception:
        pass

    try:
        latest_date = conn.execute("SELECT MAX(date) FROM stock_indicators").fetchone()[0]
        if not latest_date:
            console.print("[red]❌ 無法獲取資料庫日期[/red]")
            return
    except Exception as e:
        console.print(f"[red]❌ 資料庫錯誤: {e}[/red]")
        return
    # [FIX] Prompt for strat_choice BEFORE the scan loop so the strategy check actually runs
    if not strat_choice:
        console.print("\n[bold yellow]🔍 請選擇掃描策略 (單鍵輸入):[/bold yellow]")
        console.print("  [1] 突破年線 (預設)")
        console.print("  [2] 突破季線")
        console.print("  [3] 2560戰法")

        strat_choice = "1"
        try:
            if _kbhit_windows():
                ch = _getch_windows()
                if ch in ("1", "2", "3"):
                    strat_choice = ch
        except Exception:
            pass

    # [FIX] Update target_ma_map & period after strat_choice is confirmed
    target_ma_map = {"1": "ma200", "2": "ma60", "3": "ma25"}
    target_ma_col = target_ma_map.get(strat_choice, "ma200")
    period_map = {"1": 200, "2": 60, "3": 25}
    period = period_map.get(strat_choice, 200)

    # Check session cache hit
    cache_hit = False
    if (
        _SCAN_CACHE["date"] == latest_date
        and _SCAN_CACHE["min_volume"] == min_volume
        and _SCAN_CACHE["strat_choice"] == strat_choice
        and _SCAN_CACHE["results"] is not None
        and _time_mod.time() - _SCAN_CACHE.get("ts", 0) < _CACHE_TTL
    ):
        cache_hit = True
        all_results = _SCAN_CACHE["results"]
        console.print(
            f"\n[green]⚡ 已載入今日全市場掃描快取數據 (基準日: {latest_date}) [0.00s][/green]"
        )
    else:
        try:
            cursor = conn.execute("SELECT stock_id, stock_name FROM stock_meta")
            name_map = {r[0]: r[1] for r in cursor.fetchall()}
        except Exception:
            name_map = {}

        # === 嚴格三段式掃描 ===
        # 第一段：SQL 撈 stock_history 最新一日 → snapshot (與原版一致)

        snapshot_sql = f"""
            SELECT i.stock_id, h.close, i.{target_ma_col}, i.vol_ma5, i.vol_ma60
            FROM stock_indicators i
            JOIN stock_history h ON i.stock_id = h.stock_id AND i.date = h.date
            WHERE i.date = ? AND h.volume >= ? AND i.stock_id GLOB '[1-9][0-9][0-9][0-9]'
        """
        # h.volume 單位為股，min_volume 單位為張（1張=1000股）
        cursor = conn.execute(snapshot_sql, (latest_date, min_volume * 1000))
        rows = cursor.fetchall()
        total_snapshots = len(rows)

        # 第二段：純記憶體篩選（禁止 fetch_klines / pd.read_sql / rolling）
        # 與原版對齊：只保留 volume>=500, GLOB, target_ma 有值
        hit_list = []
        for row in rows:
            stock_id, close, target_ma, vma5, vma60 = row
            if target_ma is None:
                continue
            hit_list.append(
                {
                    "stock_id": stock_id,
                    "close": close,
                    "target_ma": target_ma,
                    "vol_ma5": vma5,
                    "vol_ma60": vma60,
                }
            )

        # 第三段：只對命中股票 fetch_klines
        from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

        all_results = []
        fetch_count = 0

        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]🚀 正在對命中股票補讀歷史算回踩..."),
            BarColumn(),
            TimeElapsedColumn(),
        ) as prog:
            task = prog.add_task("補讀歷史", total=len(hit_list))
            for stock in hit_list:
                code = stock["stock_id"]
                try:
                    # 只對命中股票 fetch_klines
                    df = pd.read_sql(
                        """
                        SELECT date, open, high, low, close, volume
                        FROM klines
                        WHERE stock_id = ?
                        ORDER BY date DESC
                        LIMIT 250
                    """,
                        conn,
                        params=(code,),
                    )
                    # DESC LIMIT 取最新 N 筆，之後倒序回 ASC 以讓 iloc[-1] 對應到最新日
                    df = df.sort_values("date").reset_index(drop=True)
                    fetch_count += 1

                    if df.empty or len(df) < period:
                        prog.advance(task)
                        continue

                    c = df["close"].values.tolist()
                    v = df["volume"].values.tolist()
                    ma_series = df["close"].rolling(window=period).mean().values.tolist()

                    curr_price = c[-1]
                    prev_price = c[-2] if len(c) >= 2 else curr_price
                    curr_vol = v[-1]
                    prev_vol = v[-2] if len(v) >= 2 else curr_vol

                    # MA 趨勢方向：最後兩天 MA 比較
                    ma_curr = ma_series[-1]
                    ma_prev = ma_series[-2] if len(ma_series) >= 2 else ma_curr
                    if ma_curr is not None and ma_prev is not None and ma_curr > 0 and ma_prev > 0:
                        if ma_curr > ma_prev:
                            ma_trend = "up"
                        elif ma_curr < ma_prev:
                            ma_trend = "down"
                        else:
                            ma_trend = "flat"
                    else:
                        ma_trend = "flat"

                    # 策略條件判斷
                    triggered = []

                    if strat_choice == "1":  # 突破年線
                        if (
                            len(c) >= 200
                            and prev_price <= ma_series[-2]
                            and curr_price > ma_series[-1]
                            and curr_vol > prev_vol
                        ):
                            bias = (
                                (curr_price - ma_series[-1]) / ma_series[-1] * 100
                                if ma_series[-1] > 0
                                else 0.0
                            )
                            vol_ratio = (curr_vol - prev_vol) / prev_vol if prev_vol > 0 else 0.0
                            retraces = _count_retraces_wrapped(ma_series, c, period)
                            triggered.append(
                                {
                                    "code": code,
                                    "name": name_map.get(code, "---"),
                                    "close": curr_price,
                                    "prev_close": prev_price,
                                    "ma60": None,
                                    "ma200": ma_series[-1],
                                    "target_ma": ma_series[-1],
                                    "vol_ratio": vol_ratio,
                                    "bias": bias,
                                    "trend": "突破年線",
                                    "color": "bold yellow",
                                    "vol": int(curr_vol) // 1000,
                                    "prev_vol": int(prev_vol) // 1000,
                                    "amount": (curr_price * curr_vol) / 1e8,
                                    "strat_id": "1",
                                    "retraces": retraces,
                                    "ma_trend": ma_trend,
                                }
                            )
                    elif strat_choice == "2":  # 突破季線
                        if (
                            prev_price <= ma_series[-2]
                            and curr_price > ma_series[-1]
                            and curr_vol > prev_vol
                        ):
                            bias = (
                                (curr_price - ma_series[-1]) / ma_series[-1] * 100
                                if ma_series[-1] > 0
                                else 0.0
                            )
                            vol_ratio = (curr_vol - prev_vol) / prev_vol if prev_vol > 0 else 0.0
                            retraces = _count_retraces_wrapped(ma_series, c, period)
                            triggered.append(
                                {
                                    "code": code,
                                    "name": name_map.get(code, "---"),
                                    "close": curr_price,
                                    "prev_close": prev_price,
                                    "ma60": ma_series[-1],
                                    "ma200": None,
                                    "target_ma": ma_series[-1],
                                    "vol_ratio": vol_ratio,
                                    "bias": bias,
                                    "trend": "突破季線",
                                    "color": "bright_magenta",
                                    "vol": int(curr_vol) // 1000,
                                    "prev_vol": int(prev_vol) // 1000,
                                    "amount": (curr_price * curr_vol) / 1e8,
                                    "strat_id": "2",
                                    "retraces": retraces,
                                    "ma_trend": ma_trend,
                                }
                            )
                    elif strat_choice == "3":  # 2560戰法
                        vol_ma5 = df["volume"].rolling(window=5).mean().values.tolist()
                        vol_ma60 = df["volume"].rolling(window=60).mean().values.tolist()
                        ma25 = df["close"].rolling(window=25).mean().values.tolist()
                        vol_cross = vol_ma5[-2] <= vol_ma60[-2] and vol_ma5[-1] > vol_ma60[-1]
                        retrace = ma25[-1] <= curr_price <= ma25[-1] * 1.10
                        if vol_cross and retrace:
                            found_2560 = False
                            breakout_idx = None
                            for t in range(2, min(60, len(c))):
                                idx = len(c) - t
                                if c[idx - 1] <= ma25[idx - 1] and c[idx] > ma25[idx]:
                                    breakout_idx = idx
                                    break
                            if breakout_idx is not None:
                                if all(c[k] >= ma25[k] for k in range(breakout_idx, len(c))):
                                    found_2560 = True
                            if found_2560:
                                bias = (
                                    (curr_price - ma25[-1]) / ma25[-1] * 100
                                    if ma25[-1] > 0
                                    else 0.0
                                )
                                retraces = _count_retraces_wrapped(ma25, c, 25)
                                triggered.append(
                                    {
                                        "code": code,
                                        "name": name_map.get(code, "---"),
                                        "close": curr_price,
                                        "prev_close": prev_price,
                                        "ma60": None,
                                        "ma200": None,
                                        "target_ma": ma25[-1],
                                        "vol_ratio": (
                                            (curr_vol - prev_vol) / prev_vol
                                            if prev_vol > 0
                                            else 0.0
                                        ),
                                        "bias": bias,
                                        "trend": "2560戰法",
                                        "color": "cyan",
                                        "vol": int(curr_vol) // 1000,
                                        "prev_vol": int(prev_vol) // 1000,
                                        "amount": (curr_price * curr_vol) / 1e8,
                                        "strat_id": "3",
                                        "retraces": retraces,
                                        "ma_trend": ma_trend,
                                    }
                                )

                    if triggered:
                        all_results.extend(triggered)
                except Exception:
                    pass
                prog.advance(task)

        # assert fetch_count == len(hit_list)
        assert fetch_count == len(
            hit_list
        ), f"fetch_count={fetch_count} != len(hit_list)={len(hit_list)}"

        # Store in session cache
        _SCAN_CACHE["date"] = latest_date
        _SCAN_CACHE["min_volume"] = min_volume
        _SCAN_CACHE["strat_choice"] = strat_choice
        _SCAN_CACHE["results"] = all_results
        _SCAN_CACHE["total_snapshots"] = total_snapshots
        _SCAN_CACHE["hit_stocks"] = len(hit_list)
        _SCAN_CACHE["fetch_count"] = fetch_count
        _SCAN_CACHE["old_time"] = _time.time() - _t0
        _SCAN_CACHE["ts"] = _time_mod.time()

    strat_names = {"1": "突破年線", "2": "突破季線", "3": "2560戰法"}
    strat_filters = {
        "1": "收盤突破 MA200，今日量 > 昨日量",
        "2": "收盤突破 MA60，今日量 > 昨日量",
        "3": "股價突破 MA25 後回落 MA25 上 10% 內，VolMA5 上穿 VolMA60",
    }
    sort_names = {"1": "距目標均線由近到遠", "2": "成交量(%)由大到小"}
    if cache_hit:
        console.print(f"👉 已載入戰法：[cyan]{strat_names[strat_choice]}[/cyan]")
    else:
        console.print(f"👉 已選擇策略：[cyan]{strat_names[strat_choice]}[/cyan]")
    console.print(
        f"   篩選條件：[cyan]{strat_filters[strat_choice]}[/cyan] │ 最小成交量 [cyan]{min_volume:,} 張[/cyan] │ 排序：[cyan]{sort_names.get(sort_choice, '距目標均線由近到遠')}[/cyan]"
    )

    # Filter the consolidated results by strat_choice
    results = [r for r in all_results if r["strat_id"] == strat_choice]

    # 排序：由呼叫端傳入，未提供時預設為 "1"
    if not sort_choice:
        sort_choice = "1"

    if sort_choice == "1":
        results.sort(key=lambda x: abs(x["bias"]))
    elif sort_choice == "2":
        results.sort(key=lambda x: x.get("vol_ratio", 0.0), reverse=True)

    _display_scan_results(results, latest_date, sort_choice, strat_choice)


def _analyze_one(conn, code, name_map) -> list:
    df = pd.read_sql(
        """
        SELECT date, open, high, low, close, volume
        FROM klines
        WHERE stock_id = ?
        ORDER BY date DESC
        LIMIT 300
    """,
        conn,
        params=(code,),
    )
    if df.empty or len(df) < 60:
        return []

    df = df.iloc[::-1].reset_index(drop=True)
    c = df["close"].values.tolist()
    v = df["volume"].values.tolist()

    # Calculate MAs
    ma60 = df["close"].rolling(window=60).mean().values.tolist()
    ma200 = (
        df["close"].rolling(window=200).mean().values.tolist() if len(df) >= 200 else None
    )  # [AI MOD] Return None instead of zeros to prevent ma200=0 from leaking downstream
    ma25 = df["close"].rolling(window=25).mean().values.tolist()

    # [AI MOD] Count support-holding retraces to MA during the most recent continuous breakout period
    # Definition: walk backwards from today to find the first day price fell below MA.
    # Exclude the breakout day itself (breakout_start) and count subsequent retraces (MA <= close <= MA * 1.10).
    def _count_retraces(ma_series):
        if (
            ma_series is None or len(df) == 0
        ):  # [AI MOD] Guard against None ma200 (insufficient data)
            return 0

        # Find the start of the current continuous breakout period above MA
        idx_start = len(df) - 1
        while idx_start >= 0:
            m = ma_series[idx_start]
            if m <= 0 or df["close"].iloc[idx_start] < m:
                break
            idx_start -= 1

        breakout_start = idx_start + 1
        if breakout_start >= len(df):
            return 0

        count = 0
        # Exclude the breakout day itself by starting from breakout_start + 1
        for i in range(breakout_start + 1, len(df)):
            m = ma_series[i]
            if m > 0:
                close_val = df["close"].iloc[i]
                if m <= close_val <= m * 1.10:
                    count += 1
        return count

    vol_ma5 = df["volume"].rolling(window=5).mean().values.tolist()
    vol_ma60 = df["volume"].rolling(window=60).mean().values.tolist()

    curr_price = c[-1]
    prev_price = c[-2]
    curr_vol = v[-1]
    prev_vol = v[-2]

    triggered = []

    vol_ratio = (curr_vol - prev_vol) / prev_vol if prev_vol > 0 else 0.0

    # 1. 突破年線
    if (
        len(df) >= 200
        and prev_price <= ma200[-2]
        and curr_price > ma200[-1]
        and curr_vol > prev_vol
    ):
        bias = (curr_price - ma200[-1]) / ma200[-1] * 100 if ma200[-1] > 0 else 0.0
        triggered.append(
            {
                "code": code,
                "name": name_map.get(code, "---"),
                "close": curr_price,
                "prev_close": prev_price,  # [AI MOD] Include prev_close for coloring
                "ma60": ma60[-1],
                "ma200": ma200[-1],
                "target_ma": ma200[-1],
                "vol_ratio": vol_ratio,
                "bias": bias,
                "trend": "突破年線",
                "color": "bold yellow",
                "vol": int(curr_vol) // 1000,
                "amount": (curr_price * curr_vol) / 1e8,
                "strat_id": "1",
                "retraces": _count_retraces(ma200),  # [AI MOD]
            }
        )

    # 2. 突破季線
    if prev_price <= ma60[-2] and curr_price > ma60[-1] and curr_vol > prev_vol:
        bias = (curr_price - ma60[-1]) / ma60[-1] * 100 if ma60[-1] > 0 else 0.0
        triggered.append(
            {
                "code": code,
                "name": name_map.get(code, "---"),
                "close": curr_price,
                "prev_close": prev_price,  # [AI MOD] Include prev_close for coloring
                "ma60": ma60[-1],
                "ma200": (
                    ma200[-1] if ma200 is not None else 0.0
                ),  # [AI MOD] Guard against None ma200
                "target_ma": ma60[-1],
                "vol_ratio": vol_ratio,
                "bias": bias,
                "trend": "突破季線",
                "color": "bright_magenta",
                "vol": int(curr_vol) // 1000,
                "amount": (curr_price * curr_vol) / 1e8,
                "strat_id": "2",
                "retraces": _count_retraces(ma60),  # [AI MOD]
            }
        )

    # 3. 2560戰法
    # 今成交量(volma5向上穿過volma60)
    vol_cross = vol_ma5[-2] <= vol_ma60[-2] and vol_ma5[-1] > vol_ma60[-1]
    # 又回落ma25於上10%內
    retrace = ma25[-1] <= curr_price <= ma25[-1] * 1.10

    if vol_cross and retrace:
        # 股價曾突破ma25後，突破期間未跌破ma25 (往回查最多60天)
        found_2560 = False
        breakout_idx = None
        for t in range(2, min(60, len(c))):
            idx = len(c) - t
            if c[idx - 1] <= ma25[idx - 1] and c[idx] > ma25[idx]:
                breakout_idx = idx
                break

        if breakout_idx is not None:
            # 突破期間未跌破ma25
            if all(c[k] >= ma25[k] for k in range(breakout_idx, len(c))):
                found_2560 = True

        if found_2560:
            bias = (curr_price - ma25[-1]) / ma25[-1] * 100 if ma25[-1] > 0 else 0.0
            triggered.append(
                {
                    "code": code,
                    "name": name_map.get(code, "---"),
                    "close": curr_price,
                    "prev_close": c[-2],  # [AI MOD] Include prev_close for coloring
                    "ma60": ma60[-1],
                    "ma200": (
                        ma200[-1] if ma200 is not None else 0.0
                    ),  # [AI MOD] Guard against None ma200
                    "target_ma": ma25[-1],
                    "vol_ratio": vol_ratio,
                    "bias": bias,
                    "trend": "2560戰法",
                    "color": "cyan",
                    "vol": int(curr_vol) // 1000,
                    "amount": (curr_price * curr_vol) / 1e8,
                    "strat_id": "3",
                    "retraces": _count_retraces(ma25),  # [AI MOD]
                }
            )

    return triggered


def _count_retraces_wrapped(ma_series, closes, period):
    """
    包裝 _count_retraces：顯傳入 ma_series 與 closes，確保索引對齊。
    供兩段式掃描使用（命中股票補讀歷史後呼叫）。
    """
    if ma_series is None or len(closes) == 0:
        return 0

    # 往回找「突破均線的第一天」
    idx_start = len(closes) - 1
    while idx_start >= 0:
        m = ma_series[idx_start]
        if m is None or m <= 0 or closes[idx_start] < m:
            break
        idx_start -= 1

    breakout_start = idx_start + 1
    if breakout_start >= len(closes):
        return 0

    # 計算突破後「回踩均線但沒跌破」的天數（突破當天起算，均線以上、均線以上 9% 以內）
    count = 0
    for i in range(breakout_start, len(closes)):
        m = ma_series[i]
        if m is not None and m > 0:
            if m <= closes[i] <= m * 1.09:
                count += 1
    return count


def _display_scan_results(
    results: list, latest_date: int, sort_choice: str, strat_choice: str
) -> None:
    if not results:
        console.print("[yellow]📭 未發現符合均線信號的標的[/yellow]")
        return

    strat_names = {"1": "突破年線戰法", "2": "突破季線戰法", "3": "2560戰法"}
    strat_name = strat_names.get(strat_choice, "均線戰法")

    sort_names = {"1": "距目標均線由近到遠", "2": "成交量(%)由大到小"}
    sort_name = sort_names.get(sort_choice, "距目標均線由近到遠")

    ds = str(latest_date)
    if len(ds) == 8:
        ds = f"{ds[:4]}-{ds[4:6]}-{ds[6:]}"

    t = Table(
        title=f"📈 {strat_name} 掃描結果 (排序: {sort_name}) 資料庫日期：{ds}",
        box=box.SIMPLE,
        border_style="cyan",
        expand=False,
        padding=(0, 0),
    )

    target_ma_labels = {"1": "MA200", "2": "MA60", "3": "MA25"}
    ma_col_name = target_ma_labels.get(strat_choice, "目標MA")

    t.add_column("代號", style="magenta", no_wrap=True)
    t.add_column("名稱", style="white")
    t.add_column(
        "收盤", justify="right", no_wrap=True
    )  # [AI MOD] Use dynamic color in cell, not column style
    t.add_column("成交張數", no_wrap=True)  # [AI MOD]
    t.add_column("額(億)", style="yellow", no_wrap=True)
    t.add_column(ma_col_name, style="bright_white", no_wrap=True)
    t.add_column("乖離率", style="bright_red", no_wrap=True)
    t.add_column("曾回踩", style="cyan", no_wrap=True)  # [AI MOD]

    for r in results[:40]:
        # 成交量顏色（統一 vol_color）
        from rich.text import Text

        vol_style = vol_color(r["vol"], r.get("prev_vol", r["vol"]))
        vol_growth_text = Text(f"{r['vol']:,}  ({r.get('vol_ratio', 0.0):+.1%})", style=vol_style)

        # 收盤顏色（統一 price_color：漲跌停紅/綠底白字）
        price_change = r["close"] - r.get("prev_close", r["close"])
        prev_close = r.get("prev_close", r["close"])
        pct = (price_change / prev_close * 100) if prev_close else 0.0
        row_close = f"[{price_color(price_change, pct)}]{r['close']:.2f}[/]"

        # 乖離率著色：正=紅，負=綠
        bias_val = r["bias"]
        bias_color = "bright_red" if bias_val >= 0 else "bright_green"
        bias_str = f"[{bias_color}]{bias_val:+.2f}%[/]"

        # MA 顏色（統一 ma_color）
        ma_val = r.get("target_ma", 0.0)
        ma_str = f"[{ma_color(r.get('ma_trend', 'flat'))}]{ma_val:.2f}[/]"

        t.add_row(
            r["code"],
            r["name"],
            row_close,
            vol_growth_text,
            f"{r['amount']:.2f}",
            ma_str,
            bias_str,
            f"{r.get('retraces', 0)}次",
        )
    console.print(t)


def get_latest_date() -> str:
    """供 strategies.py 查詢資料基準日"""
    from db import get_connection  # [FIX] _utils does not export get_connection

    conn = get_connection(readonly=True)
    try:
        return conn.execute("SELECT MAX(date) FROM stock_indicators").fetchone()[0]
    finally:
        conn.close()


def run_strategy(params: dict):
    code = params.get("code")
    scan = params.get("scan", False)
    strat_choice = params.get("strat_choice")
    sort_choice = params.get("sort_choice")
    vol = params.get("vol", 500)
    mobile = params.get("mobile", False)

    conn = get_connection(readonly=True)
    try:
        # [AI MOD] 自動刷新缺失指標
        if code:
            try:
                from twstock.strategy.indicators import ensure_indicators

                ensure_indicators(code, conn)
            except Exception:
                pass

        if scan:
            scan_market_stocks(conn, vol, strat_choice, sort_choice=sort_choice)
            return

        if not code:
            console.print("[red]❌ 請提供股票代號[/red]")
            return

        name = "-"
        row = conn.execute(
            "SELECT stock_name FROM stock_meta WHERE stock_id = ?", (code,)
        ).fetchone()
        if row and row[0]:
            name = row[0]

        df = pd.read_sql(
            """
            SELECT date, open, high, low, close, volume
            FROM klines_indicators
            WHERE stock_id = ?
            ORDER BY date DESC
            LIMIT 300
        """,
            conn,
            params=(code,),
        )
    finally:
        conn.close()

    if df.empty or len(df) < 20:
        console.print(f"[yellow]⚠️ {code} 資料不足，無法分析[/yellow]")
        return

    df = df.iloc[::-1].reset_index(drop=True)

    c = df["close"].values.tolist()

    ma25_data = _compute_ma_with_deduction(c, 25)  # [AI MOD]
    ma60_data = _compute_ma_with_deduction(c, 60)
    ma200_data = _compute_ma_with_deduction(c, 200)

    curr_price = c[-1]
    prev_price = c[-2] if len(c) >= 2 else curr_price

    m60_curr = ma60_data["ma"]
    m200_curr = ma200_data["ma"]
    m60_prev = sum(c[-61:-1]) / 60 if len(c) >= 61 else 0
    m200_prev = sum(c[-201:-1]) / 200 if len(c) >= 201 else 0

    status = "區間震盪"
    color = "white"

    if m60_curr > 0 and m200_curr > 0:
        if curr_price > m60_curr > m200_curr and ma60_data["trend"] == "↑ 上揚":
            status, color = "多頭排列 (強勢攻擊)", "bold red"
        elif curr_price < m60_curr < m200_curr and ma60_data["trend"] == "↓ 下彎":
            status, color = "空頭排列 (弱勢尋底)", "bold green"
        elif m60_curr > m200_curr and m60_prev <= m200_prev:
            status, color = "黃金交叉 (趨勢轉強)", "yellow"
        elif m60_curr < m200_curr and m60_prev >= m200_prev:
            status, color = "死亡交叉 (趨勢轉弱)", "bold green"

    if m60_curr > 0 and prev_price <= m60_prev and curr_price > m60_curr:
        status, color = "突破季線 (短線轉強)", "bright_magenta"
    elif m200_curr > 0 and prev_price <= m200_prev and curr_price > m200_curr:
        status, color = "突破年線 (長線翻多)", "bold yellow"

    bias = (curr_price - m60_curr) / m60_curr * 100 if m60_curr > 0 else 0.0

    data = {
        "close": curr_price,
        "prev_close": prev_price,
        "ma25": ma25_data,  # [AI MOD]
        "ma60": ma60_data,
        "ma200": ma200_data,
        "bias": bias,
        "trend": status,
        "color": color,
    }

    if mobile:
        _render_mobile_ma(data, code, name)
    else:
        _render_full_ma(data, code, name)


class MAStrategy:
    """均線策略 wrapper - 提供統一的 analyze() 介面。"""

    def analyze(self, stock_id: str) -> dict:
        """分析均線信號。回傳 strategy/stock_id/signal。"""
        from db import get_connection

        conn = get_connection()
        try:
            df = fetch_klines(conn, stock_id, limit=250)
            if df is None or df.empty or len(df) < 60:
                return {
                    "strategy": "ma",
                    "stock_id": stock_id,
                    "signal": "neutral",
                    "reason": "資料不足",
                }

            c = df["close"].sort_index().tolist()
            curr = c[-1]

            ma25 = sum(c[-25:]) / 25 if len(c) >= 25 else curr
            ma60 = sum(c[-60:]) / 60 if len(c) >= 60 else curr
            ma200 = sum(c[-200:]) / 200 if len(c) >= 200 else curr

            # 判斷排列
            if curr > ma25 > ma60 > ma200:
                signal = "bullish"
                arrangement = "多頭排列"
            elif curr < ma25 < ma60 < ma200:
                signal = "bearish"
                arrangement = "空頭排列"
            else:
                signal = "neutral"
                arrangement = "區間震盪"

            return {
                "strategy": "ma",
                "stock_id": stock_id,
                "signal": signal,
                "ma25": round(ma25, 2),
                "ma60": round(ma60, 2),
                "ma200": round(ma200, 2),
                "arrangement": arrangement,
            }
        finally:
            conn.close()


if __name__ == "__main__":
    import sys

    code = sys.argv[1] if len(sys.argv) > 1 else "2330"
    run_strategy({"code": code})
