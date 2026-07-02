# -*- coding: utf-8 -*-
"""複合分析：5 策略 + K 線 + LongCat AI。

遵循 CONTEXT.md 架構規則 6：策略組合邏輯歸屬 strategy 套件。
上層只呼叫 run_composite(code)，不用 __import__ 動態載入。
"""
from __future__ import annotations

import os
import time
from datetime import datetime

from rich.align import Align
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

from twstock.db import get_connection
from twstock.display import price_rich, vol_diff_rich, render_kline
from twstock.longcat_vision import analyze_kline_with_longcat
from twstock.strategy._utils import fetch_klines
from twstock.strategy.strategies import STRATEGY_REGISTRY
from twstock.utils import get_stock_name, get_http_session, safe_http_get, safe_float, safe_int
from twstock.terminal import console

# 策略模組 ID 與顯示標籤
_STRATEGY_LABELS = [
    ("1", "1 ⚡ 撐壓分析 (Support/Resistance)"),
    ("2", "2 ⚡ 均線趨勢 (MA Trend)"),
    ("3", "3 ⚡ 籌碼動能 (Institutional Chips)"),
    ("4", "4 ⚡ AI 預測 (Kronos Prediction)"),
    ("5", "5 ⚡ 幾何型態 (Chart Patterns)"),
]


def run_composite(stock_id: str, mobile: bool = False) -> None:
    """執行多重策略的綜合分析面板。"""
    stock_name = get_stock_name(stock_id)
    os.system("cls" if os.name == "nt" else "clear")

    # ── 檢查 DB 是否過期 ──
    try:
        now = datetime.now()
        with get_connection(readonly=True) as conn:
            latest_db = conn.execute(
                "SELECT MAX(date) FROM stock_history"
            ).fetchone()[0]
        if latest_db:
            db_date = datetime.strptime(str(latest_db), "%Y-%m-%d")
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

    # ── Market Status ──
    now = datetime.now()
    mins = now.hour * 60 + now.minute
    is_weekday = now.weekday() < 5
    is_trading = is_weekday and (9 * 60 <= mins <= 13 * 60 + 30)
    today_str = now.strftime("%Y-%m-%d")

    # ── Fetch DB: latest 3 trading days ──
    try:
        with get_connection(readonly=True) as conn:
            rows = conn.execute(
                "SELECT date, close, volume FROM stock_history "
                "WHERE stock_id = ? ORDER BY date DESC LIMIT 3",
                (stock_id,),
            ).fetchall()
    except Exception:
        rows = []

    if len(rows) >= 2:
        d0 = str(rows[0][0]); p0 = float(rows[0][1]); v0 = int(rows[0][2])
        d1 = str(rows[1][0]); p1 = float(rows[1][1]); v1 = int(rows[1][2])
        if len(rows) >= 3:
            p2 = float(rows[2][1]); v2 = int(rows[2][2])
        else:
            p2, v2 = 0.0, 0

        live_price = None
        live_vol = None
        if is_trading:
            live_price, live_vol = _fetch_live_quote(stock_id)

        _render_price_panel(
            mobile, is_trading, today_str, now,
            d0, p0, v0, d1, p1, v1, p2, v2,
            live_price, live_vol,
        )
    else:
        console.print(f"[yellow]⚠️ {stock_id} 歷史資料不足[/yellow]")

    # ── 5 Strategy Modules ──
    _run_strategies(stock_id, mobile)

    # ── K 線圖 ──
    try:
        with get_connection(readonly=True) as conn:
            df_kline = fetch_klines(conn, stock_id, limit=60)
        df_kline = df_kline.dropna(subset=["close"]).sort_values("date")
        if not df_kline.empty:
            console.print()
            console.print(render_kline(df_kline, stock_id, ""))
    except Exception as e:
        console.print(f"[dim]K 線圖渲染跳過: {e}[/dim]")

    # ── LongCat AI 文字分析 ──
    try:
        ai_result = analyze_kline_with_longcat(df_kline, stock_id, "")
        if ai_result:
            console.print()
            console.print(Panel(ai_result, title="🤖 LongCat AI 分析", border_style="magenta"))
    except Exception as e:
        console.print(f"[dim]LongCat AI 分析跳過: {e}[/dim]")

    input("\n按 Enter 鍵返回主選單...")


# ── internal ─────────────────────────────────────────────
def _fetch_live_quote(stock_id: str):
    """從 TWSE MIS 抓取即時報價。回傳 (price, volume) 或 (None, None)。"""
    try:
        session = get_http_session()
        if session is None:
            return None, None
        ex_ch = f"tse_{stock_id}.tw|otc_{stock_id}.tw"
        url = (
            f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp"
            f"?ex_ch={ex_ch}&json=1&delay=0&_={int(time.time() * 1000)}"
        )
        r = safe_http_get(url, session=session, timeout=3, verify=True)
        if not r:
            return None, None
        try:
            data = r.json()
        except ValueError:
            return None, None
        if not data or not data.get("msgArray"):
            return None, None
        for item in data["msgArray"]:
            c = item.get("c", "")
            if c == stock_id or c.zfill(4) == stock_id:
                z = item.get("z", "-")
                v = item.get("v", "0")
                price = None
                if z and z != "-" and z != "0.00":
                    price = safe_float(z)
                else:
                    for key in ("b", "a"):
                        raw = item.get(key, "-")
                        if raw and raw != "-":
                            lst = [x for x in raw.split("_") if x]
                            if lst:
                                price = safe_float(lst[0])
                                break
                vol = safe_int(v)
                if vol:
                    vol *= 1000
                return price, vol if vol else None
    except Exception:
        pass
    return None, None


def _render_price_panel(
    mobile: bool, is_trading: bool, today_str: str, now: datetime,
    d0: str, p0: float, v0: int, d1: str, p1: float, v1: int,
    p2: float, v2: int, live_price, live_vol,
) -> None:
    """渲染價格 + 成交量面板。"""
    if mobile:
        _render_mobile(is_trading, today_str, now, d0, p0, v0, d1, p1, v1, p2, v2, live_price, live_vol)
    else:
        _render_wide(is_trading, today_str, now, d0, p0, v0, d1, p1, v1, p2, v2, live_price, live_vol)


def _render_mobile(
    is_trading: bool, today_str: str, now: datetime,
    d0: str, p0: float, v0: int, d1: str, p1: float, v1: int,
    p2: float, v2: int, live_price, live_vol,
) -> None:
    if is_trading:
        console.print(f"[bright_cyan]▶ 開盤中   {today_str}  {now.strftime('%H:%M')}[/]")
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
    d_hist = d0 if is_trading else d1
    console.print(f"[bright_white]▷ 歷史 {d_hist}[/]")
    if is_trading:
        console.print(f"  股價 {price_rich(p0, p1)}")
        console.print(f"  量 {vol_diff_rich(v0, v1)}")
    else:
        console.print(f"  股價 {price_rich(p1, p2)}")
        console.print(f"  量 {vol_diff_rich(v1, v2)}")


def _render_wide(
    is_trading: bool, today_str: str, now: datetime,
    d0: str, p0: float, v0: int, d1: str, p1: float, v1: int,
    p2: float, v2: int, live_price, live_vol,
) -> None:
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
                f"股價 {price_rich(p0, p1)}",
            )
            info.add_row(
                f"量 {vol_diff_rich(live_vol or v0, v0)}",
                f"量 {vol_diff_rich(v0, v1)}",
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
            f"股價 {price_rich(p1, p2)}",
        )
        info.add_row(
            f"量 {vol_diff_rich(v0, v1)}",
            f"量 {vol_diff_rich(v1, v2)}",
        )

    console.print(Panel(info, border_style="blue", box=box.ROUNDED, padding=(0, 1)))


def _run_strategies(stock_id: str, mobile: bool) -> None:
    """執行所有已註冊策略。"""
    for key, label in _STRATEGY_LABELS:
        console.print(f"\n[bold cyan]{label}[/]")
        try:
            entry = STRATEGY_REGISTRY.get(key)
            if entry is None:
                console.print(f"[dim]策略 {key} 未註冊，跳過[/dim]")
                continue
            mod = entry["module"]
            params = {"code": stock_id, "compact": True, "mobile": mobile}
            mod.run_strategy(params)
        except Exception as e:
            console.print(f"[red]❌ 分析失敗: {e}[/red]")
