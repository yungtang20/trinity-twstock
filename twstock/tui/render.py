# -*- coding: utf-8 -*-
"""Dashboard 渲染（Rich layout components）。"""

from __future__ import annotations

import os
import shutil
from datetime import datetime

from rich import box
from rich.align import Align
from rich.console import Group
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from twstock.market_data.cache import MarketCache
from twstock.terminal import console
from twstock.utils import (
    format_price_change,
    get_sys_info,
    to_roc_date,
)

# 模組層級快取實例（與 main.py 行為一致）
_market_cache = MarketCache()


def fetch_market_indices_cached():
    """向後相容包裝。"""
    return _market_cache.get()


def warmup_market_cache():
    """進入主循環時觸發一次非阻塞市場行情更新。"""
    _market_cache.warmup()


def wait_for_market_cache() -> bool:
    """等待首次背景行情完成，讓首頁在顯示提示後做一次重畫。"""
    return _market_cache.wait_for_fetch()


# ══════════════════════════════════════════════════════════════
# Layout
# ══════════════════════════════════════════════════════════════
def make_layout() -> Layout:
    try:
        term_width = shutil.get_terminal_size((80, 24)).columns
    except Exception:
        term_width = 80

    is_narrow = term_width < 75
    market_size = 8 if is_narrow else 5

    layout = Layout()
    layout.split(
        Layout(name="header", size=3),
        Layout(name="status", size=8),
        Layout(name="market", size=market_size),
        Layout(name="menu", size=8),
        Layout(name="footer", size=3),
    )
    return layout


# ══════════════════════════════════════════════════════════════
# Dashboard renderer
# ══════════════════════════════════════════════════════════════
def render_dashboard() -> None:
    """渲染完整 TUI dashboard（含市場行情、狀態、選單、提示）。"""
    info = get_sys_info()
    now = datetime.now()

    layout = make_layout()
    indices = fetch_market_indices_cached()
    market_mode = _market_cache.get_market_mode()

    _render_market_panel(layout, indices, market_mode, now)
    _render_header(layout, now)
    _render_menu(layout)
    _render_status(layout, info)
    _render_footer(layout)

    try:
        term_width = shutil.get_terminal_size().columns
    except Exception:
        term_width = 80
    target_width = min(term_width, 88)

    os.system("cls" if os.name == "nt" else "clear")
    tight_group = Group(
        layout["header"].renderable,
        layout["status"].renderable,
        layout["market"].renderable,
        layout["menu"].renderable,
        layout["footer"].renderable,
    )
    console.print(Align.left(tight_group, width=target_width))


# ── panel helpers ──────────────────────────────────────────
def _render_market_panel(
    layout, indices, market_mode: str = "🔴 盤後", now: datetime | None = None
) -> None:
    display_now = now or datetime.now()
    market_title = _build_market_title(display_now, market_mode)
    # 嘗試從 cache 取得資料（即使 background fetch 尚未完全結束）
    if not indices:
        indices = _market_cache.get()

    taiex = indices.get("TAIEX") if isinstance(indices, dict) else None
    otc = indices.get("OTC") if isinstance(indices, dict) else None
    has_taiex = isinstance(taiex, dict) and bool(taiex.get("price", 0))
    has_otc = isinstance(otc, dict) and bool(otc.get("price", 0))
    if not indices or not (has_taiex or has_otc):
        # 資料尚未到達或全部失敗
        status = _market_cache.get_status()
        if status["is_fetching"]:
            msg = "正在獲取即時數據..."
        elif status["last_error"]:
            msg = f"⚠️ 即時行情失敗：{status['last_error']}"
        else:
            msg = "⚠️ 無法取得即時行情"
        layout["market"].update(
            Panel(
                Align.left(Text(msg, style="dim")),
                title=market_title,
            )
        )
        return

    def _get_market_text(data, label):
        _, _, color = format_price_change(data["price"], data["price"] - data["change"])
        change_sign = "+" if data["change"] >= 0 else "-"
        title = Text.assemble(
            (f" {label} ", "bold white on grey15"),
            (f" {data['price']:,.2f} ", f"bold {color}"),
            (f"({change_sign}{abs(data['change']):,.0f}、{data['pct']:+.2f}%)", color),
        )
        is_live_session = "開盤" in market_mode
        if is_live_session:
            amount = Text(" 成交金額：盤後公布", style="dim")
        elif data.get("amount") is None:
            amount = Text(" 成交金額：暫無資料", style="dim")
        else:
            amount = Text.assemble(
                (" 成交金額: ", "white"),
                (f"{data['amount']:,.0f} 億", "white"),
            )

        def _f(v):
            return f"{v}" if v is not None else "-"

        if is_live_session:
            b_text = Text(" 漲跌家數：盤後公布", style="dim")
        else:
            b_text = Text.assemble(
                ("漲停", "white on red"),
                (f"{_f(data['l_up'])}", "white on red"),
                (" ", "white"),
                (f"上漲{_f(data['up'])}", "red"),
                (" ", "white"),
                (f"平盤{_f(data['flat'])}", "white"),
                (" ", "white"),
                (f"下跌{_f(data['down'])}", "green"),
                (" ", "white"),
                ("跌停", "white on green"),
                (f"{_f(data['l_down'])}", "white on green"),
            )
        return Group(title, amount, b_text)

    m_grid = Table(box=None, show_header=False, expand=True, padding=(0, 1))
    try:
        term_width = shutil.get_terminal_size((80, 24)).columns
    except Exception:
        term_width = 80

    if term_width < 75:
        m_grid.add_column("Index", justify="left")
        if has_taiex:
            m_grid.add_row(_get_market_text(taiex, "加權指數"))
        if has_taiex and has_otc:
            m_grid.add_row("")
        if has_otc:
            m_grid.add_row(_get_market_text(otc, "櫃買指數"))
    else:
        m_grid.add_column("T", justify="left", ratio=1)
        m_grid.add_column("O", justify="left", ratio=1)
        m_grid.add_row(
            _get_market_text(taiex, "加權指數") if has_taiex else Text("加權指數暫無資料", style="dim"),
            _get_market_text(otc, "櫃買指數") if has_otc else Text("櫃買指數暫無資料", style="dim"),
        )
    layout["market"].update(
        Panel(
            m_grid,
            title=market_title,
            border_style="bright_blue",
            box=box.ROUNDED,
            padding=(0, 1),
        )
    )


def _build_market_title(now: datetime, market_mode: str) -> str:
    """以系統時鐘建立市場標題；行情資料時間不再冒充目前時間。"""
    roc_date = to_roc_date(now.strftime("%Y%m%d")).replace("/", "-")
    return f"📊 市場: {roc_date} {now:%H:%M:%S} {market_mode}"


def _render_header(layout, now) -> None:
    # [AI MOD] 日期/時間一律使用系統時鐘,避免休市日 API 回傳最後一次交易日舊日期造成誤解。
    date_str = to_roc_date(now.strftime("%Y%m%d"))
    time_display = now.strftime("%H:%M:%S")

    header_text = Text.assemble(
        (" ⚡ TRINITY ", "bold cyan"),
        ("STRATEGY SUITE ", "bold white"),
        ("v3.3 ", "dim"),
        (f" │ {date_str} {time_display} ", "grey70"),
    )
    layout["header"].update(Align.left(Panel(header_text, style="on grey15", box=box.HORIZONTALS)))


def _render_menu(layout) -> None:
    menu_table = Table(box=None, show_header=False, expand=True)
    menu_table.add_column("option", width=22)
    menu_table.add_column("desc")
    menu_table.add_row(
        "[bold cyan][1][/] 每日資料更新",
        "[dim]同步最新加權/櫃買收盤價量、法人買賣超與集保[/]",
    )
    menu_table.add_row(
        "[bold cyan][2][/] 歷史資料更新",
        "[dim]檢查價量/法人缺口、指定重抓、TDCC、除權息與唯讀品質報告[/]",
    )
    menu_table.add_row(
        "[bold cyan][3][/] 策略分析中心",
        "[dim]綜合分析、均線交叉、籌碼動能、型態與 AI 預測[/]",
    )
    menu_table.add_row(
        "[bold cyan][4][/] 資料庫健檢與最佳化",
        "[dim]先做唯讀檢查；有足夠可回收空間才允許備份後壓縮[/]",
    )
    menu_table.add_row("", "")
    menu_table.add_row("[bold grey70][0][/] 退出系統", "")

    layout["menu"].update(
        Panel(
            menu_table,
            title="[bold white] 主 功 能 選 單 [/]",
            border_style="cyan",
            padding=(0, 2),
            box=box.ROUNDED,
        )
    )


def _render_status(layout, info) -> None:
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
    # [AI MOD] 移除「📊 市場: <market_mode>」一行：盤中/盤後標記已顯示於
    # _render_market_panel 的市場行情框標題（render.py:180），系統狀態框內重複顯示為多餘。

    layout["status"].update(
        Panel(
            status_table,
            title="[bold white] 系 統 狀 態 [/]",
            border_style="grey37",
            padding=(0, 1),
            box=box.ROUNDED,
        )
    )


def _render_footer(layout) -> None:
    footer_text = Text.assemble(
        (" 💡 提示: ", "bold yellow"),
        "直接輸入 ",
        ("4 碼股號", "bold cyan"),
        " 即可進行綜合策略分析",
    )
    layout["footer"].update(
        Panel(
            footer_text,
            border_style="grey15",
            padding=(0, 1),
        )
    )
