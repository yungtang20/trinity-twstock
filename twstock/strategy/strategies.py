#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
strategies.py - 策略入口與調度中心 [AI MOD]
職責：整合同目錄下的所有子策略檔案，提供統一的調度介面與互動選單。
"""

import sys
import os
import argparse
from rich.table import Table
from rich import box

# --- Windows Encoding Fix [AI MOD] ---
if sys.platform == "win32":
    os.system('chcp 65001 > nul')
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stdin.reconfigure(encoding='utf-8')
    except AttributeError: pass

# [AI MOD] 集中式 Console：解決 Windows cp950 無法渲染 emoji 的問題
from terminal import console

# --- [AI MOD] Package-aware imports supporting both package import and direct execution ---
try:
    from . import sr_analyzer
    from . import ma_strategy
    from . import chips_strategy
    from . import patterns_strategy
    from . import prediction_strategy
except (ImportError, ValueError):
    import sr_analyzer
    import ma_strategy
    import chips_strategy
    import patterns_strategy
    import prediction_strategy

# ==================== 策略註冊表 [AI MOD] ====================
STRATEGY_REGISTRY = {
    "1": {
        "name": "撐壓分析 (Support/Resistance)",
        "module": sr_analyzer,
        "description": "基於波段高低點、量價密集區、關鍵K棒與靜態水平位的支撐壓力分析",  # [AI MOD] Updated description to reflect actual implementation (no LR/VSBC)
        "params_example": "可使用 '--code 2330' 查詢個股，或 '--scan' 進行全市場掃描"
    },
    "2": {
        "name": "均線趨勢 (MA Trend)",
        "module": ma_strategy,
        "description": "月線(25MA)/季線(60MA)/年線(200MA)趨勢、扣抵值與明日預測分析",  # [AI MOD] Updated description (no general cross scanning)
        "params_example": "--code 2330"
    },
    "3": {
        "name": "籌碼動能 (Institutional Chips)",
        "module": chips_strategy,
        "description": "外資與投信買賣超追蹤、千張大戶與散戶集保籌碼分析",  # [AI MOD] Updated description (only foreign/trust + TDCC)
        "params_example": "--code 2330"
    },
    "4": {
        "name": "AI 預測 (Kronos Prediction)",
        "module": prediction_strategy,
        "description": "利用 Kronos 時序預測模型進行未來 5 日價格預測與評估",
        "params_example": "--code 2330"
    },
    "5": {
        "name": "幾何型態 (Chart Patterns)",
        "module": patterns_strategy,
        "description": "自動偵測雙底/雙頂、通道、旗形等 21 種經典技術幾何型態",  # [AI MOD] Updated description to reflect 21 patterns
        "params_example": "--code 2330"
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
            console.print(f"[red]❌ 策略模組 {strategy_module.__name__} 未提供 run_strategy 函數[/red]")
    except Exception as e:
        console.print(f"[red]❌ 執行策略 {strategy_module.__name__} 失敗: {e}[/red]")

# --- Standalone Single-Key Input Helper for TUI [AI MOD] ---
import time
try:
    import msvcrt
    HAS_MSVCRT = True
except ImportError:
    HAS_MSVCRT = False

def get_single_key_input(prompt: str, keys: str, auto_four: bool = False) -> str:
    if not HAS_MSVCRT or not sys.stdin.isatty():
        return input(prompt).strip()
    while msvcrt.kbhit():
        msvcrt.getwch()
    sys.stdout.write(prompt)
    sys.stdout.flush()
    buf = ""
    while True:
        if msvcrt.kbhit():
            ch = msvcrt.getwch()
            if ch in ('\r', '\n'):
                sys.stdout.write('\n')
                sys.stdout.flush()
                return buf.strip()
            elif ch == '\b':
                if len(buf) > 0:
                    buf = buf[:-1]
                    sys.stdout.write('\b \b')
                    sys.stdout.flush()
            elif ch in ('\x1b', '\x03'): # ESC or Ctrl+C
                sys.stdout.write('\n')
                sys.stdout.flush()
                return "0"
            else:
                if ch.isprintable():
                    buf += ch
                    sys.stdout.write(ch)
                    sys.stdout.flush()
                    if len(buf) == 1 and ch in keys:
                        # 0.4s protection time
                        start_wait = time.time()
                        is_single = True
                        while time.time() - start_wait < 0.4:
                            if msvcrt.kbhit():
                                next_ch = msvcrt.getwch()
                                if next_ch in ('\r', '\n'):
                                    break
                                is_single = False
                                buf += next_ch
                                sys.stdout.write(next_ch)
                                sys.stdout.flush()
                                break
                        if is_single:
                            sys.stdout.write('\n')
                            sys.stdout.flush()
                            return buf.strip()
                    
                    if auto_four and len(buf) == 4 and buf.isdigit():
                        start_wait = time.time()
                        has_interrupted = False
                        # Extend delay to 1.2 seconds for superior typing comfort [AI MOD]
                        while time.time() - start_wait < 1.2:
                            if msvcrt.kbhit():
                                next_ch = msvcrt.getwch()
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
                            sys.stdout.write('\n')
                            sys.stdout.flush()
                            return buf.strip()

def interactive_menu():
    while True:
        console.print("\n[bold yellow]TRINITY 策略系統 - 策略入口[/bold yellow]")
        list_strategies()
        choice = get_single_key_input("請選擇策略編號 (或按 Enter 退出): ", "12345") # [AI MOD]
        if not choice:
            return
        if choice not in STRATEGY_REGISTRY:
            console.print("[red]無效選擇[/red]")
            continue

        if choice == "1":  # 撐壓分析
            while True:
                console.print("\n撐壓分析選項：")
                ans = get_single_key_input("👉 請直接輸入 4 碼股號，或輸入 1 進行「全市場掃描」，或按 Enter 回到上一頁: ", "1", auto_four=True)
                if not ans:
                    break

                vol = 500

                if ans == '1':
                    if HAS_MSVCRT:
                        while msvcrt.kbhit():
                            msvcrt.getwch()
                    vol_str = input("最小成交量 (張, 預設 500): ").strip()
                    vol = int(vol_str) if vol_str.isdigit() else 500
                    run_strategy_by_id(choice, {'scan': True, 'vol': vol})
                elif len(ans) == 4 and ans.isdigit():
                    run_strategy_by_id(choice, {'code': ans})
                else:
                    console.print("[red]無效選擇[/red]")
                    continue

                # 掃描後的遞迴迴圈
                exit_sub = False
                while True:
                    prompt_str = "👉 請直接輸入 4 碼股號，或輸入 1 重新掃描，或按 Enter 回到上一頁: "
                    next_ans = get_single_key_input(prompt_str, "1", auto_four=True)
                    if not next_ans:
                        exit_sub = True
                        break
                    elif next_ans == '1':
                        run_strategy_by_id(choice, {'scan': True, 'vol': vol})
                    elif len(next_ans) == 4 and next_ans.isdigit():
                        run_strategy_by_id(choice, {'code': next_ans})
                    else:
                        console.print("[red]無效選擇[/red]")
                if exit_sub:
                    break
        elif choice == "2":  # 均線趨勢
            while True:
                console.print("\n均線趨勢選項：")
                ans = get_single_key_input("👉 請直接輸入 4 碼股號，或輸入 1 進行「全市場掃描」，或按 Enter 回到上一頁: ", "1", auto_four=True) # [AI MOD]
                if not ans:
                    break
                
                vol = 500
                
                if ans == '1':
                    if HAS_MSVCRT:
                        while msvcrt.kbhit():
                            msvcrt.getwch()
                    vol_str = input("最小成交量 (張, 預設 500): ").strip()
                    vol = int(vol_str) if vol_str.isdigit() else 500
                    run_strategy_by_id(choice, {'scan': True, 'vol': vol})
                elif len(ans) == 4 and ans.isdigit():
                    run_strategy_by_id(choice, {'code': ans})
                else:
                    console.print("[red]無效選擇[/red]")
                    continue
                    
                # Recursive shortcut loop!
                exit_sub = False
                while True:
                    prompt_str = "👉 請直接輸入 4 碼股號，或繼續選擇掃描策略   [1] 突破年線 [2] 突破季線  [3] 2560戰法，或按 Enter 回到上一頁: " # [AI MOD]
                    next_ans = get_single_key_input(prompt_str, "123", auto_four=True)
                    if not next_ans:
                        exit_sub = True
                        break
                    elif next_ans in ('1', '2', '3'):
                        run_strategy_by_id(choice, {'scan': True, 'vol': vol, 'strat_choice': next_ans})
                    elif len(next_ans) == 4 and next_ans.isdigit():
                        run_strategy_by_id(choice, {'code': next_ans})
                    else:
                        console.print("[red]無效選擇[/red]")
                if exit_sub:
                    break
        elif choice == "3":  # 籌碼動能
            while True:
                console.print("\n籌碼動能選項：")
                ans = get_single_key_input("👉 請直接輸入 4 碼股號，或輸入 1投信.2.外資3.集保，或按 Enter 回到上一頁: ", "123", auto_four=True) # [AI MOD]
                if not ans:
                    break
                
                current_strat = None
                if ans in ('1', '2', '3'):
                    current_strat = ans
                    run_strategy_by_id(choice, {'scan': True, 'strat_choice': ans})
                elif len(ans) == 4 and ans.isdigit():
                    run_strategy_by_id(choice, {'code': ans})
                else:
                    console.print("[red]無效選擇[/red]")
                    continue
                    
                # Recursive shortcut loop!
                exit_sub = False
                while True:
                    prompt_str = "👉 請直接輸入 4 碼股號，或繼續選擇掃描策略 1投信.2.外資3.集保，或按 Enter 回到上一頁: " # [AI MOD]
                    next_ans = get_single_key_input(prompt_str, "123", auto_four=True)
                    if not next_ans:
                        exit_sub = True
                        break
                    elif next_ans in ('1', '2', '3'):
                        current_strat = next_ans
                        run_strategy_by_id(choice, {'scan': True, 'strat_choice': next_ans})
                    elif len(next_ans) == 4 and next_ans.isdigit():
                        run_strategy_by_id(choice, {'code': next_ans})
                    else:
                        console.print("[red]無效選擇[/red]")
                if exit_sub:
                    break
        elif choice == "4":  # AI 預測
            while True:
                console.print("\nAI 預測選項：")
                ans = get_single_key_input("👉 請直接輸入 4 碼股號，或輸入 1 進行「全市場掃描」，或按 Enter 回到上一頁: ", "1", auto_four=True) # [AI MOD]
                if not ans:
                    break
                
                vol = 500
                
                if ans == '1':
                    if HAS_MSVCRT:
                        while msvcrt.kbhit():
                            msvcrt.getwch()
                    vol_str = input("最小成交量 (張, 預設 500): ").strip()
                    vol = int(vol_str) if vol_str.isdigit() else 500
                    run_strategy_by_id(choice, {'scan': True, 'vol': vol})
                elif len(ans) == 4 and ans.isdigit():
                    run_strategy_by_id(choice, {'code': ans})
                else:
                    console.print("[red]無效選擇[/red]")
                    continue
                    
                # Recursive shortcut loop!
                exit_sub = False
                while True:
                    prompt_str = "👉 請直接輸入 4 碼股號，or輸入 1 重新掃描 / 切換排序，或按 Enter 回到上一頁: " # [AI MOD]
                    next_ans = get_single_key_input(prompt_str, "1", auto_four=True)
                    if not next_ans:
                        exit_sub = True
                        break
                    elif next_ans == '1':
                        run_strategy_by_id(choice, {'scan': True, 'vol': vol})
                    elif len(next_ans) == 4 and next_ans.isdigit():
                        run_strategy_by_id(choice, {'code': next_ans})
                    else:
                        console.print("[red]無效選擇[/red]")
                if exit_sub:
                    break
        elif choice == "5":  # 幾何型態
            while True:
                console.print("\n幾何型態選項：")
                ans = get_single_key_input("👉 請直接輸入 4 碼股號，或輸入 1 進行「全市場掃描」，或按 Enter 回到上一頁: ", "1", auto_four=True) # [AI MOD]
                if not ans:
                    break
                
                vol = 500
                
                if ans == '1':
                    if HAS_MSVCRT:
                        while msvcrt.kbhit():
                            msvcrt.getwch()
                    vol_str = input("最小成交量 (張, 預設 500): ").strip()
                    vol = int(vol_str) if vol_str.isdigit() else 500
                    run_strategy_by_id(choice, {'scan': True, 'vol': vol})
                elif len(ans) == 4 and ans.isdigit():
                    run_strategy_by_id(choice, {'code': ans})
                else:
                    console.print("[red]無效選擇[/red]")
                    continue
                    
                # Recursive shortcut loop!
                exit_sub = False
                while True:
                    prompt_str = "👉 請直接輸入 4 碼股號，或輸入 1 重新掃描 / 切換排序，或按 Enter 回到上一頁: " # [AI MOD]
                    next_ans = get_single_key_input(prompt_str, "1", auto_four=True)
                    if not next_ans:
                        exit_sub = True
                        break
                    elif next_ans == '1':
                        run_strategy_by_id(choice, {'scan': True, 'vol': vol})
                    elif len(next_ans) == 4 and next_ans.isdigit():
                        run_strategy_by_id(choice, {'code': next_ans})
                    else:
                        console.print("[red]無效選擇[/red]")
                if exit_sub:
                    break
        else:
            console.print("[yellow]該策略尚未實作參數引導，請使用命令列模式[/yellow]")
            continue

def run_strategy_cli(args):
    """
    命令列模式入口，供 main.py 調用
    args: argparse.Namespace 物件，須包含 strategy_id, code, scan, vol 等屬性
    """
    if not hasattr(args, 'strategy_id') or not args.strategy_id:
        console.print("[red]請提供 --strategy-id 參數[/red]")
        return
    params = {}
    if hasattr(args, 'code') and args.code:
        params['code'] = args.code
    if hasattr(args, 'scan') and args.scan:
        params['scan'] = True
        params['vol'] = getattr(args, 'vol', 500)
    run_strategy_by_id(args.strategy_id, params)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TRINITY 策略執行入口")
    parser.add_argument("--strategy-id", type=str, help="要執行的策略編號 (1-5)")
    parser.add_argument("--code", type=str, help="股票代號 (如 2330)")
    parser.add_argument("--scan", action="store_true", help="執行全市場撐壓掃描 (適用於策略 1)")
    parser.add_argument("--vol", type=int, default=500, help="全市場掃描的最低成交量門檻 (張，預設 500)")
    
    args = parser.parse_args()
    
    if len(sys.argv) == 1:
        interactive_menu()
    else:
        run_strategy_cli(args)
