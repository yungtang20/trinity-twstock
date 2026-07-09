#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
strategies.py - 策略入口與調度中心 [AI MOD]
職責：整合同目錄下的所有子策略檔案，提供統一的調度介面與互動選單。
"""

import argparse
import os
import sys
from typing import Any, Dict

from rich import box
from rich.table import Table

# 確保 twstock 在 sys.path（讓 from twstock.xxx import 能運作）
_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)

# --- Windows Encoding Fix [AI MOD] ---
if sys.platform == "win32":
    os.system("chcp 65001 > nul")
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        sys.stdin.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except AttributeError:
        pass

# 子策略模組
from twstock.strategy import (
    chips_strategy,
    ma_strategy,
    patterns_strategy,
    prediction_strategy,
    sr_analyzer,
)
from twstock.terminal import console

# ==================== 策略註冊表 [AI MOD] ====================
STRATEGY_REGISTRY: Dict[str, Dict[str, Any]] = {
    "1": {
        "name": "撐壓分析 (Support/Resistance)",
        "module": sr_analyzer,
        "description": "基於波段高低點、量價密集區、關鍵K棒與靜態水平位的支撐壓力分析",  # [AI MOD] Updated description to reflect actual implementation (no LR/VSBC)
        "params_example": "可使用 '--code 2330' 查詢個股，或 '--scan' 進行全市場掃描",
    },
    "2": {
        "name": "均線趨勢 (MA Trend)",
        "module": ma_strategy,
        "description": "月線(25MA)/季線(60MA)/年線(200MA)趨勢、扣抵值與明日預測分析",  # [AI MOD] Updated description (no general cross scanning)
        "params_example": "--code 2330",
    },
    "3": {
        "name": "籌碼動能 (Institutional Chips)",
        "module": chips_strategy,
        "description": "外資與投信買賣超追蹤、千張大戶與散戶集保籌碼分析",  # [AI MOD] Updated description (only foreign/trust + TDCC)
        "params_example": "--code 2330",
    },
    "4": {
        "name": "幾何型態 (Chart Patterns)",
        "module": patterns_strategy,
        "description": "自動偵測雙底/雙頂、通道、旗形等 21 種經典技術幾何型態",
        "params_example": "--code 2330",
    },
    "5": {
        "name": "AI 預測 (Kronos Prediction)",
        "module": prediction_strategy,
        "description": "利用 Kronos 時序預測模型進行未來 5 日價格預測與評估",
        "params_example": "--code 2330",
    },
}


def list_strategies():
    table = Table(title="📋 可用策略清單", box=box.SIMPLE)
    table.add_column("編號", style="cyan", no_wrap=True)
    table.add_column("策略名稱", style="green")
    table.add_column("說明", style="white")
    for key, info in STRATEGY_REGISTRY.items():
        table.add_row(key, info["name"], info["description"])
    console.print(table)


def run_strategy_by_id(strategy_id, params):
    if strategy_id not in STRATEGY_REGISTRY:
        console.print(f"[red]❌ 無效的策略編號: {strategy_id}[/red]")
        return
    strategy_module = STRATEGY_REGISTRY[strategy_id]["module"]
    try:
        if hasattr(strategy_module, "run_strategy"):
            strategy_module.run_strategy(params)
        else:
            console.print(
                f"[red]❌ 策略模組 {strategy_module.__name__} 未提供 run_strategy 函數[/red]"
            )
    except Exception as e:
        console.print(f"[red]❌ 執行策略 {strategy_module.__name__} 失敗: {e}[/red]")


# --- 統一輸入層（input_helper）---
from twstock.input_helper import _flush_input_buffer, get_interactive_input


def get_single_key_input(prompt: str, keys: str, auto_four: bool = False) -> str:
    """向後相容包裝：統一使用 input_helper.get_interactive_input。"""
    return get_interactive_input(prompt=prompt, menu_keys=keys, auto_four=auto_four)


def _flush_msvcrt():
    """清除鍵盤緩衝區（委派至 input_helper）。"""
    _flush_input_buffer()


def _input_vol(prompt: str = "最小成交量 (預設 500 張): ") -> int:
    """通用最小成交量輸入"""
    _flush_msvcrt()
    vol_str = input(prompt).strip()
    return int(vol_str) if vol_str.isdigit() else 500


def _input_sort_ma() -> str:
    """均線趨勢排序選擇"""
    console.print("\n📊 請選擇掃描結果排序方式 (單鍵輸入):")
    console.print("  [1] 距目標均線由近到遠")
    console.print("  [2] 成交量(%)由大到小")
    console.print("  [Enter] 回到上一頁")
    sort_input = get_single_key_input("👉 ", "12")
    return sort_input if sort_input in ("1", "2") else ""


def _prompt_kronos_ai():
    """掃描後提示：輸入股號或按 Enter 回到上一頁"""
    _flush_msvcrt()
    ans = input("🔍 輸入股號或按 Enter 回到上一頁: ").strip()

    if not ans:
        return  # 回到上一頁

    if len(ans) == 4 and ans.isdigit():
        # 呼叫 prediction_strategy 進行 Kronos+AI 預測（策略 5）
        run_strategy_by_id("5", {"code": ans})
    else:
        console.print("[red]❌ 請輸入 4 碼股號[/]")


def interactive_menu():
    while True:
        console.print("\n[bold yellow]TRINITY 策略系統 - 策略入口[/bold yellow]")
        list_strategies()
        choice = get_single_key_input("請選擇策略編號 (或按 Enter 退出): ", "12345")  # [AI MOD]
        if not choice:
            return
        if choice not in STRATEGY_REGISTRY:
            console.print("[red]無效選擇[/red]")
            continue

        if choice == "1":  # 撐壓分析
            while True:
                try:
                    base_date = sr_analyzer.get_latest_date()
                except Exception:
                    base_date = "N/A"
                console.print(f"\n撐壓分析選項：(資料基準日: {base_date})")
                console.print("  [1] POC 量價密集區上10%")
                console.print("  [2] VWAP上10%")
                console.print("  [3] 長期支撐上10%")
                console.print("  [4] 短期支撐上10%")
                console.print("  [5] 前低支撐上10%")
                console.print("  [Enter] 回到上一頁")
                ans = get_single_key_input(
                    "🔍 輸入股號或按 Enter 回到上一頁: ", "12345", auto_four=True
                )
                if not ans:
                    break

                if len(ans) == 4 and ans.isdigit():
                    run_strategy_by_id(choice, {"code": ans})
                    continue

                filter_map = {
                    "1": "poc",
                    "2": "vwap",
                    "3": "long_sup",
                    "4": "short_sup",
                    "5": "front_low",
                }
                if ans in filter_map:
                    vol = _input_vol()
                    run_strategy_by_id(
                        choice, {"scan": True, "vol": vol, "filter": filter_map[ans]}
                    )
                    _prompt_kronos_ai()
                    continue

                console.print("[red]無效選擇[/red]")

        elif choice == "2":  # 均線趨勢
            while True:
                try:
                    base_date = ma_strategy.get_latest_date()
                except Exception:
                    base_date = "N/A"
                console.print(f"\n均線趨勢選項：(資料基準日: {base_date})")
                console.print("  [1] 突破年線")
                console.print("  [2] 突破季線")
                console.print("  [3] 2560戰法")
                console.print("  [Enter] 回到上一頁")
                ans = get_single_key_input(
                    "🔍 輸入股號或按 Enter 回到上一頁: ", "123", auto_four=True
                )
                if not ans:
                    break

                if len(ans) == 4 and ans.isdigit():
                    run_strategy_by_id(choice, {"code": ans})
                    continue

                if ans in ("1", "2", "3"):
                    vol = _input_vol()
                    sort_choice = _input_sort_ma()
                    if not sort_choice:
                        break
                    run_strategy_by_id(
                        choice,
                        {"scan": True, "vol": vol, "strat_choice": ans, "sort_choice": sort_choice},
                    )
                    _prompt_kronos_ai()
                    continue

                console.print("[red]無效選擇[/red]")

        elif choice == "3":  # 籌碼動能
            while True:
                try:
                    base_date = chips_strategy.get_latest_date()
                except Exception:
                    base_date = "N/A"
                console.print(f"\n籌碼策略選項：(資料基準日: {base_date})")
                console.print("  [1] 投信連買 x 天 (預設 2 天)")
                console.print("  [2] 外資連買 x 天 (預設 2 天)")
                console.print("  [3] 集保人數下降，千張大戶增")
                console.print("  [Enter] 回到上一頁")
                ans = get_single_key_input(
                    "🔍 輸入股號或按 Enter 回到上一頁: ", "123", auto_four=True
                )
                if not ans:
                    break

                if len(ans) == 4 and ans.isdigit():
                    run_strategy_by_id(choice, {"code": ans})
                    continue

                if ans in ("1", "2"):
                    # 重顯示分類選單（填入篩選天數）
                    console.print("\n  [1] 投信連買 x 天 (預設 2 天)")
                    console.print("  [2] 外資連買 x 天 (預設 2 天)")
                    console.print("  [3] 集保人數下降，千張大戶增")
                    console.print("  [Enter] 回到上一頁")
                    _flush_msvcrt()
                    n_days_str = input("📅 連買天數 (預設 2): ").strip()
                    if not n_days_str:
                        break  # 回到上一頁
                    n_days = int(n_days_str) if n_days_str.isdigit() else 2
                    console.print("\n📊 排序基準:")
                    console.print("  [1] 連買天數(由小到大) (預設)")
                    console.print("  [2] 法人成交量(%)(由大到小)")
                    console.print("  [3] VSBC 加速帶上10%")
                    console.print("  [Enter] 回到上一頁")
                    _flush_msvcrt()
                    sort_str = input("👉 ").strip()
                    if not sort_str:
                        break  # 回到上一頁
                    sort_choice = int(sort_str) if sort_str in ("1", "2", "3") else 1
                    run_strategy_by_id(
                        choice,
                        {
                            "scan": True,
                            "strat_choice": ans,
                            "n_days": n_days,
                            "sort_choice": sort_choice,
                        },
                    )
                    _prompt_kronos_ai()
                    continue

                if ans == "3":
                    console.print("\n📊 排序基準:")
                    console.print("  [1] 千張(人數%)由大到小 (預設)")
                    console.print("  [2] 集保(人數%)由大到小")
                    console.print("  [Enter] 回到上一頁")
                    _flush_msvcrt()
                    sort_str = input("👉 ").strip()
                    if not sort_str:
                        break  # 回到上一頁
                    sort_choice = int(sort_str) if sort_str in ("1", "2") else 1
                    run_strategy_by_id(
                        choice, {"scan": True, "strat_choice": "3", "sort_choice": sort_choice}
                    )
                    _prompt_kronos_ai()
                    continue

                console.print("[red]無效選擇[/red]")

        elif choice == "4":  # 幾何型態
            while True:
                try:
                    base_date = patterns_strategy.get_latest_date()
                except Exception:
                    base_date = "N/A"
                console.print(f"\n幾何型態選項：(資料基準日: {base_date})")
                console.print(
                    "  [1] 看漲型態（W底·N字底·頸肩底·三重底·V反轉·圓弧底·上升三角·下降楔形·上升通道·牛旗）"
                )
                console.print("  [2] 區間整理（箱型·對稱三角）")
                console.print(
                    "  [3] 看跌型態（M頭·頸肩頂·三重頂·倒V·圓弧頂·下降三角·上升楔形·下降通道·熊旗）"
                )
                console.print("  [4] 全部")
                console.print("  [Enter] 回到上一頁")
                ans = get_single_key_input(
                    "🔍 輸入股號或按 Enter 回到上一頁: ", "1234", auto_four=True
                )
                if not ans:
                    break

                if len(ans) == 4 and ans.isdigit():
                    run_strategy_by_id(choice, {"code": ans})
                    continue

                filter_map = {"1": "bullish", "2": "neutral", "3": "bearish", "4": None}
                if ans in filter_map:
                    vol = _input_vol()
                    run_strategy_by_id(
                        choice, {"scan": True, "vol": vol, "pattern_filter": filter_map[ans]}
                    )
                    _prompt_kronos_ai()
                    continue

                console.print("[red]無效選擇[/red]")

        elif choice == "5":  # AI 預測（只接受 4 碼股號查個股，無全掃）
            while True:
                try:
                    base_date = prediction_strategy.get_latest_date()
                except Exception:
                    base_date = "N/A"
                console.print(f"\nAI 預測選項：(資料基準日: {base_date})")
                _flush_msvcrt()
                ans = input("🔍 輸入股號或按 Enter 回到上一頁: ").strip()
                if not ans:
                    break

                if len(ans) == 4 and ans.isdigit():
                    run_strategy_by_id(choice, {"code": ans})
                    continue

                console.print("[red]❌ 請輸入 4 碼股號[/]")
        else:
            console.print("[yellow]該策略尚未實作參數引導，請使用命令列模式[/yellow]")
            continue


def run_strategy_cli(args):
    """
    命令列模式入口，供 main.py 調用
    args: argparse.Namespace 物件，須包含 strategy_id, code, scan, vol 等屬性
    """
    if not hasattr(args, "strategy_id") or not args.strategy_id:
        console.print("[red]請提供 --strategy-id 參數[/red]")
        return
    params = {}
    if hasattr(args, "code") and args.code:
        params["code"] = args.code
    if hasattr(args, "scan") and args.scan:
        params["scan"] = True
        params["vol"] = getattr(args, "vol", 500)
    run_strategy_by_id(args.strategy_id, params)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TRINITY 策略執行入口")
    parser.add_argument("--strategy-id", type=str, help="要執行的策略編號 (1-5)")
    parser.add_argument("--code", type=str, help="股票代號 (如 2330)")
    parser.add_argument("--scan", action="store_true", help="執行全市場撐壓掃描 (適用於策略 1)")
    parser.add_argument(
        "--vol", type=int, default=500, help="全市場掃描的最低成交量門檻 (張，預設 500)"
    )

    args = parser.parse_args()

    if len(sys.argv) == 1:
        interactive_menu()
    else:
        run_strategy_cli(args)
