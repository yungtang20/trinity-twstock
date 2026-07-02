# -*- coding: utf-8 -*-
"""Dashboard 渲染（Rich layout components）。"""
from __future__ import annotations

import os
import shutil
from datetime import datetime

from rich.align import Align
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box
from rich.console import Group

from twstock.display import price_rich, vol_fmt, render_kline, chg_color, vol_diff_rich, vol_color
from twstock.utils import (
    get_sys_info, to_roc_date, format_price_change, fetch_market_indices_cached,
)
from twstock.terminal import console


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

    _render_market_panel(layout, indices)
    _render_header(layout, indices, now, is_live, current_minutes)
    _render_menu(layout)
    _render_status(layout, info, market_mode)
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
def _render_market_panel(layout, indices) -> None:
    if not indices:
        layout["market"].update(Panel(
            Align.left(Text("正在獲取即時數據...", style="dim")),
            title=" 市場行情 ",
        ))
        return

    def _get_market_text(data, label):
        _, _, color = format_price_change(data["price"], data["price"] - data["change"])
        change_sign = "+" if data["change"] >= 0 else "-"
        title = Text.assemble(
            (f" {label} ", "bold white on grey15"),
            (f" {data['price']:,.2f} ", f"bold {color}"),
            (f"({change_sign}{abs(data['change']):,.0f}、{data['pct']:+.2f}%)", color),
        )
        amount = Text.assemble(
            (" 成交金額: ", "white"),
            (f"{data['amount']:,.0f} 億", "white"),
        )

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


def _render_header(layout, indices, now, is_live, current_minutes) -> None:
    if indices and indices.get("date"):
        date_str = to_roc_date(indices["date"])
    else:
        date_str = to_roc_date(now.strftime("%Y%m%d"))

    if is_live:
        time_display = (
            indices.get("time") if indices and indices.get("time")
            else now.strftime("%H:%M:%S")
        )
    else:
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


def _render_status(layout, info, market_mode) -> None:
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


def _render_footer(layout) -> None:
    footer_text = Text.assemble(
        (" 💡 提示: ", "bold yellow"),
        "直接輸入 ", ("4 碼股號", "bold cyan"), " 即可進行綜合策略分析",
    )
    layout["footer"].update(Panel(
        footer_text,
        border_style="grey15",
        padding=(0, 1),
    ))
