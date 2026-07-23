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
LIMIT_UP_PCT = 9.8  # ≥ 9.8% 視為漲停
LIMIT_DN_PCT = -9.8  # ≤ -9.8% 視為跌停

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
        return "white on red"  # 漲停：紅底白字
    elif pct <= LIMIT_DN_PCT:
        return "white on green"  # 跌停：綠底白字
    elif change > 0:
        return "bright_red"  # 上漲：紅
    elif change < 0:
        return "bright_green"  # 下跌：綠
    else:
        return "white"  # 平盤：白


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
        return "bright_red"  # 量增：紅
    elif current < previous:
        return "bright_green"  # 量縮：綠
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
        trend: "up" | "↑ 上揚" | "上揚" | "down" | "↓ 下彎" | "下彎" | "flat" | "→ 走平" | "走平"
    Returns:
        Rich style string
    """
    if trend in ("up", "↑ 上揚", "上揚"):
        return "bright_red"  # 均線上揚：紅
    elif trend in ("down", "↓ 下彎", "下彎"):
        return "bright_green"  # 均線下降：綠
    return "white"  # 均線走平：白


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


def render_kline(df, stock_id: str = "", stock_name: str = "", days: int = 10) -> str:
    """渲染適合終端閱讀的逐日 K 線與成交量。

    每日以一根橫向 K 棒呈現，數字同時列出 OHLC、較昨收漲跌與成交量。
    K 棒顏色依收盤與開盤比較；漲跌顏色依收盤與前收比較。
    """
    if df is None or df.empty:
        return "[yellow]無資料[/]"
    for col in ["date", "open", "high", "low", "close", "volume"]:
        if col not in df.columns:
            return f"[yellow]缺少 {col} 欄位[/]"

    clean = (
        df.copy().dropna(subset=["open", "high", "low", "close", "volume"]).sort_values("date").reset_index(drop=True)
    )
    if len(clean) < 2:
        return "[yellow]資料不足[/]"

    display_days = max(2, int(days))
    start_index = max(0, len(clean) - display_days)
    view = clean.iloc[start_index:].reset_index(drop=True)
    first_prev_close = float(clean["close"].iloc[start_index - 1]) if start_index > 0 else float(view["open"].iloc[0])
    lines: list[str] = []

    # 標題
    title = f"{stock_id} {stock_name}" if stock_id else "K 線圖"
    last_close = float(view["close"].iloc[-1])
    prev_close = float(clean["close"].iloc[-2])
    change = last_close - prev_close
    pct = (change / prev_close * 100) if prev_close else 0.0
    color = price_color(change, pct)
    arrow = "▲" if change > 0 else ("▼" if change < 0 else "─")
    sign = "+" if change > 0 else ""
    lines.append(f"[bold]{title}[/]  [{color}]{last_close:.2f} " f"{arrow}{abs(pct):.1f}% ({sign}{change:.2f})[/]")
    lines.append(
        "[white on red] 漲停 [/] [bright_red]漲／買[/]  "
        "[white]平[/]  [bright_green]跌／賣[/] [white on green] 跌停 [/]"
    )
    lines.append("[dim]K 棒：紅 K＝收盤＞開盤；綠 K＝收盤＜開盤；白＝開收相同[/]")
    lines.append("[dim]圖例：○開盤　●收盤　◆開收相同　━K棒實體　─當日最低到最高[/]")
    lines.append("")

    closes = [float(value) for value in view["close"]]

    def _daily_change(index: int) -> tuple[float, float]:
        previous = closes[index - 1] if index > 0 else first_prev_close
        current = closes[index]
        delta = current - previous
        percentage = (delta / previous * 100) if previous else 0.0
        return delta, percentage

    def _k_style(open_price: float, close_price: float) -> tuple[str, str]:
        if close_price > open_price:
            return "bright_red", "紅K"
        if close_price < open_price:
            return "bright_green", "綠K"
        return "white", "十字"

    def _horizontal_candle(low_price: float, high_price: float, open_price: float, close_price: float) -> str:
        """建立單日橫向 K 棒：兩端為低/高，○為開盤，●為收盤。"""
        width = 14
        span = high_price - low_price
        if span <= 0:
            return "├" + " " * (width // 2) + "◆" + " " * (width - width // 2 - 1) + "┤"

        def position(price: float) -> int:
            mapped = round((price - low_price) / span * (width - 1))
            return max(0, min(width - 1, mapped))

        open_pos = position(open_price)
        close_pos = position(close_price)
        chars = ["─"] * width
        for pos in range(min(open_pos, close_pos), max(open_pos, close_pos) + 1):
            chars[pos] = "━"
        if open_pos == close_pos:
            chars[open_pos] = "◆"
        else:
            chars[open_pos] = "○"
            chars[close_pos] = "●"
        return "├" + "".join(chars) + "┤"

    period_high = float(view["high"].max())
    period_low = float(view["low"].min())
    period_start = float(view["close"].iloc[0])
    period_change = last_close - period_start
    period_pct = (period_change / period_start * 100) if period_start else 0.0
    lines.append(f"[bold white]最近 {len(view)} 個交易日逐日 K 線（日期由舊到新）[/]")
    lines.append(
        f"[dim]區間最低 {period_low:.2f}　最高 {period_high:.2f}　"
        f"收盤 {period_start:.2f} → {last_close:.2f}　[/]"
        f"[{price_color(period_change, period_pct)}]{period_pct:+.1f}%[/]"
    )
    lines.append("[dim]日期       K棒   最低  │─○開盤━●收盤─│  最高    開盤→收盤       較昨收       成交量（張）[/]")

    max_volume = max(int(value) for value in view["volume"])
    for i in range(len(view)):
        open_price = float(view["open"].iloc[i])
        high_price = float(view["high"].iloc[i])
        low_price = float(view["low"].iloc[i])
        close_price = closes[i]
        volume = int(view["volume"].iloc[i])
        delta, percentage = _daily_change(i)
        change_style = price_color(delta, percentage)
        k_style, k_label = _k_style(open_price, close_price)
        arrow = "▲" if delta > 0 else ("▼" if delta < 0 else "─")
        volume_width = round(volume / max_volume * 10) if max_volume > 0 else 0
        if volume > 0:
            volume_width = max(1, volume_width)
        volume_bar = "█" * volume_width
        volume_style = "bright_red" if delta > 0 else "bright_green" if delta < 0 else "white"
        candle = _horizontal_candle(low_price, high_price, open_price, close_price)
        date_text = str(view["date"].iloc[i]).split(" ", 1)[0]
        lines.append(
            f"{date_text:<10} [{k_style}]{k_label:<3} {low_price:>7.2f} {candle} {high_price:>7.2f}  "
            f"{open_price:>7.2f}→{close_price:<7.2f}[/] "
            f"[{change_style}]{arrow}{abs(percentage):>5.1f}%[/]  "
            f"[{volume_style}]{vol_fmt(volume):>9} {volume_bar}[/]"
        )

    return "\n".join(lines)
