#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
twstock — CLI & TUI 入口

職責：
  - 無 args：啟動互動式 TUI（TUIApp）
  - 有 args：根據 action 分派至 commands/*.py 的 execute(args)

所有業務邏輯已搬離：
  - commands/        → CLI 子命令
  - tui/             → 互動式選單
  - market_data/     → 即時盤中抓取與快取
  - utils.py         → 共用工具
  - strategy/composites.py → 複合分析
"""
import argparse
import os
import sys

# 支援雙模式執行：
#   python -m twstock.main        → Python 自動將 D:\twse 加進 sys.path
#   python d:/twse/twstock/main.py → Python 只加 D:\twse\twstock，需手動補兩層：
#     1. 專案根目錄（D:\twse）讓 from twstock.xxx 能解析
#     2. 套件目錄（D:\twse\twstock）讓套件內 from db import ... 隱式相對 import 能解析
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_CURRENT_DIR)
for _p in (_PROJECT_ROOT, _CURRENT_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from twstock.db import get_path
from twstock.db_admin import init_db, migrate_db
from twstock.terminal import console
from twstock.utils import get_token

# 命令分派表
_ACTION_MAP = {
    "update":    "twstock.commands.update",
    "indicators": "twstock.commands.indicators",
    "intraday":  "twstock.commands.intraday",
    "strategy":  "twstock.commands.strategy",
    "official":  "twstock.commands.official",
    "dividend":  "twstock.commands.dividend",
}


class _LazyToken:
    """延遲解析 FinMind token：只在字串被實際取值時才呼叫 get_token()。

    讓 indicators 等不需要 token 的命令可以在無 token 環境下執行。
    """
    def __str__(self) -> str:
        return get_token()

    def __bool__(self) -> bool:
        return True  # 讓 args.token 在未設定時仍為 truthy，避免命令誤判


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TRINITY 策略系統 v3.3")
    parser.add_argument(
        "action",
        choices=list(_ACTION_MAP.keys()),
        help="執行動作",
    )
    parser.add_argument("stock_id", type=str, nargs="?", help="股票代號")
    parser.add_argument("--token", type=str, help="FinMind Token")
    parser.add_argument("--strategy-id", type=str, help="策略編號")
    parser.add_argument("--code", type=str, help="股票代號 (配合策略使用)")
    parser.add_argument("--scan", action="store_true", help="全市場掃描")
    parser.add_argument("--vol", type=int, default=500, help="掃描最小成交量 (張)")
    parser.add_argument("--date", type=str, help="指定日期 (YYYY-MM-DD 或 YYYYMMDD)")
    parser.add_argument("--days", type=int, default=1, help="下載幾個交易日")
    parser.add_argument("--tdcc-only", action="store_true", help="僅抓取最新 TDCC")
    parser.add_argument("--with-tdcc", action="store_true", help="更新後自動更新 TDCC")
    parser.add_argument("--tdcc-weeks", type=int, help="抓取最近 N 週 TDCC 歷史")
    parser.add_argument("--start-date", type=str, help="開始日期 (dividend)")
    parser.add_argument("--end-date", type=str, help="結束日期 (dividend)")
    return parser


def main() -> None:
    # 自動初始化資料庫（只在直接執行時觸發，import 不觸發）
    if not os.path.exists(get_path()):
        console.print("[yellow]首次執行，初始化資料庫...[/yellow]")
        init_db()
    else:
        migrate_db()

    if len(sys.argv) == 1:
        from twstock.tui.app import TUIApp
        TUIApp().run()
        return

    args = build_parser().parse_args()
    # 延遲 token 解析：只在命令真正存取 args.token 時才呼叫 get_token()
    # 如此 indicators（純 DB 讀取）可在無 token 環境下正常執行
    if not args.token:
        args.token = _LazyToken()

    module_path = _ACTION_MAP[args.action]
    mod = __import__(module_path, fromlist=["execute"])

    if args.action in ("update", "indicators", "intraday") and not args.stock_id:
        console.print(f"[red]{args.action} 需要提供 stock_id[/red]")
        return

    mod.execute(args)


if __name__ == "__main__":
    main()
