#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
display.py — 臺股標準配色工具 [AI MOD]
漲紅跌綠（臺股慣例，與美股相反）
漲停：紅底白字  跌停：綠底白字
量增紅 / 量縮綠
"""

from rich.text import Text

# ── Constants ──────────────────────────────────────────
# 臺股標準漲跌停幅度（普通股 10%）
LIMIT_UP_PCT = 9.8    # ≥ 9.8% 視為漲停
LIMIT_DN_PCT = -9.8   # ≤ -9.8% 視為跌停

# ── Price Colors ───────────────────────────────────────

def price_color(change: float, pct: float) -> str:
    """
    臺股標準價格配色。
    Args:
        change: 絕對價格變動
        pct: 百分比變動
    Returns:
        Rich style string
    """
    if pct >= LIMIT_UP_PCT:
        return "white on red"       # 漲停：紅底白字
    elif pct <= LIMIT_DN_PCT:
        return "white on green"     # 跌停：綠底白字
    elif change > 0:
        return "bright_red"         # 上漲：紅
    elif change < 0:
        return "bright_green"       # 下跌：綠
    else:
        return "white"              # 平盤：白


def price_str(price: float, prev_price: float, show_sign: bool = True) -> Text:
    """
    價格 + 漲跌幅，臺股標準配色。
    Returns:
        Rich Text object ready for console.print()
    """
    change = price - prev_price
    pct = (change / prev_price * 100) if prev_price else 0.0
    c = price_color(change, pct)

    arrow = "▲" if change > 0 else ("▼" if change < 0 else "─")
    sign = "+" if change > 0 else ""

    if show_sign:
        label = f"{price:.2f} {arrow}{abs(pct):.1f}%({sign}{change:.2f})"
    else:
        label = f"{price:.2f}"

    return Text(label, style=c)


def price_rich(price: float, prev_price: float) -> str:
    """Returns a Rich markup string for inline use in f-strings."""
    change = price - prev_price
    pct = (change / prev_price * 100) if prev_price else 0.0
    c = price_color(change, pct)
    arrow = "▲" if change > 0 else ("▼" if change < 0 else "─")
    sign = "+" if change > 0 else ""
    return f"[{c}]{price:.2f} {arrow}{abs(pct):.1f}%({sign}{change:.2f})[/]"


def chg_color(change: float) -> str:
    """Simple: just the color based on change direction."""
    if change > 0:
        return "bright_red"
    elif change < 0:
        return "bright_green"
    return "white"


def chg_rich(change: float, pct: float) -> str:
    """Rich markup string for a change value (no price)."""
    c = price_color(change, pct)
    sign = "+" if change > 0 else ""
    return f"[{c}]{sign}{change:.2f} ({sign}{pct:.1f}%)[/]"


# ── Volume Colors ──────────────────────────────────────

def vol_color(current: int, previous: int) -> str:
    """
    成交量配色：比昨高紅 / 比昨低綠 / 持平白。
    """
    if current > previous:
        return "bright_red"         # 量增：紅
    elif current < previous:
        return "bright_green"       # 量縮：綠
    return "white"


def vol_rich(current: int, previous: int) -> str:
    """Rich markup for volume with color. Expects volume in shares (股)."""
    c = vol_color(current, previous)
    return f"[{c}]{vol_fmt(current)}[/]"


def vol_diff_rich(current: int, previous: int) -> str:
    """Volume + diff, raw numbers with thousand separators in sheets (張). [AI MOD]"""
    current_sheets = int(round(current / 1000.0))
    previous_sheets = int(round(previous / 1000.0))
    diff_sheets = current_sheets - previous_sheets
    c = vol_color(current, previous)
    sign = "+" if diff_sheets > 0 else ""
    return f"[{c}]{current_sheets:,}[/]張 [dim](差{sign}{diff_sheets:,})[/]"


# ── Volume Formatting ──────────────────────────────────

def vol_fmt(vol: int) -> str:
    """Human-readable volume in 萬/千/個. Expects volume in shares (股), formats as sheets (張)."""
    sheets = vol / 1000.0
    if sheets >= 10000:
        return f"{sheets / 10000:.1f}萬張"
    elif sheets >= 1000:
        return f"{sheets / 1000:.1f}千張"
    return f"{sheets:,.1f}張" if sheets % 1 != 0 else f"{int(sheets):,}張"


# ── MA Colors ──────────────────────────────────────────

def ma_color(trend: str) -> str:
    """
    均線趨勢配色：上揚紅 / 下降綠 / 走平白。
    Args:
        trend: "up" | "down" | "flat"
    Returns:
        Rich style string
    """
    if trend == "up":
        return "bright_red"         # 均線上揚：紅
    elif trend == "down":
        return "bright_green"       # 均線下降：綠
    return "white"                  # 均線走平：白


def ma_str(value: float, trend: str) -> str:
    """Rich markup for MA value with trend color."""
    c = ma_color(trend)
    return f"[{c}]{value:.2f}[/]"


def vol_fmt_short(vol: int) -> str:
    """Short volume. Expects volume in shares (股), formats as sheets (張)."""
    sheets = vol / 1000.0
    if sheets >= 10000:
        return f"{sheets / 10000:.1f}萬"
    elif sheets >= 1000:
        return f"{sheets / 1000:.1f}K"
    return f"{sheets:,.1f}" if sheets % 1 != 0 else f"{int(sheets):,}"


# ── K-Line Chart ────────────────────────────────────────

def render_kline(df, stock_id: str = "", stock_name: str = "", days: int = 60) -> str:
    """
    渲染文字 K 線圖（Rich markup）。
    Args:
        df: DataFrame with columns: date, open, high, low, close, volume
        stock_id: 股票代號
        stock_name: 股票名稱
        days: 顯示天數（預設 60）
    Returns:
        str: Rich markup 字串，可直接用 console.print() 輸出
    """
    if df is None or df.empty:
        return "[yellow]無資料[/]"
    df = df.tail(days).copy().reset_index(drop=True)
    if len(df) < 2:
        return "[yellow]資料不足[/]"
    for col in ['open', 'high', 'low', 'close', 'volume']:
        if col not in df.columns:
            return f"[yellow]缺少 {col} 欄位[/]"

    price_high = float(df['high'].max())
    price_low = float(df['low'].min())
    price_range = price_high - price_low
    if price_range <= 0:
        price_range = 1.0

    chart_height = 15
    vol_height = 4
    lines = []

    # 標題
    title = f"{stock_id} {stock_name}" if stock_id else "K 線圖"
    last_close = float(df['close'].iloc[-1])
    prev_close = float(df['close'].iloc[-2]) if len(df) > 1 else last_close
    change = last_close - prev_close
    pct = (change / prev_close * 100) if prev_close else 0.0
    color = price_color(change, pct)
    arrow = "▲" if change > 0 else ("▼" if change < 0 else "─")
    lines.append(f"[bold]{title}[/]  [{color}]{last_close:.2f} {arrow}{abs(pct):.1f}%[/]")
    lines.append("")

    # K 線主體
    for row in range(chart_height):
        price_at_row = price_high - (row / (chart_height - 1)) * price_range
        if row == 0:
            label = f"{price_high:>8.2f} "
        elif row == chart_height - 1:
            label = f"{price_low:>8.2f} "
        elif row == chart_height // 2:
            mid_price = (price_high + price_low) / 2
            label = f"{mid_price:>8.2f} "
        else:
            label = "          "

        line_chars = []
        for i in range(len(df)):
            o = float(df['open'].iloc[i])
            h = float(df['high'].iloc[i])
            l = float(df['low'].iloc[i])
            c = float(df['close'].iloc[i])
            is_up = c >= o
            body_top = max(o, c)
            body_bot = min(o, c)

            def price_to_row(p):
                return int((price_high - p) / price_range * (chart_height - 1))

            r_h = price_to_row(h)
            r_l = price_to_row(l)
            r_body_top = price_to_row(body_top)
            r_body_bot = price_to_row(body_bot)
            if r_h <= row <= r_l:
                if r_body_top <= row <= r_body_bot:
                    line_chars.append("[bright_red]█[/]" if is_up else "[bright_green]█[/]")
                else:
                    line_chars.append("[dim]│[/]")
            else:
                line_chars.append(" ")
        lines.append(label + "".join(line_chars))

    # 成交量
    lines.append("")
    lines.append("[dim]─ 成交量 ─[/]")
    vol_max = int(df['volume'].max())
    if vol_max <= 0:
        vol_max = 1
    for row in range(vol_height):
        vol_threshold = vol_max * (1 - row / vol_height)
        label = f"{vol_fmt_short(int(vol_threshold)):>8s} " if row == 0 else "          "
        line_chars = []
        for i in range(len(df)):
            v = int(df['volume'].iloc[i])
            is_up = float(df['close'].iloc[i]) >= float(df['open'].iloc[i])
            if v >= vol_threshold:
                line_chars.append("[bright_red]█[/]" if is_up else "[bright_green]█[/]")
            else:
                line_chars.append(" ")
        lines.append(label + "".join(line_chars))

    # 日期標籤
    date_label = "          "
    dates = df['date'].astype(str).tolist()
    if len(dates) > 2:
        lines.append(date_label + dates[0][:5] + " " * (len(dates) - 10) + dates[-1][:5])
    else:
        lines.append(date_label + "  ".join(d[:5] for d in dates))

    return "\n".join(lines)
