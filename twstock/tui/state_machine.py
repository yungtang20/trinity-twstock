# -*- coding: utf-8 -*-
"""state_machine.py — 純邏輯狀態機，分離 TUI 狀態轉換與 I/O。

此模組不含任何 I/O（無 print、msvcrt、input），
僅根據当前状态 + 输入 → 回傳下一个状态 + 要执行的動作。
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

# ── States ───────────────────────────────────────────────

class TUIState(Enum):
    """TUI 狀態列舉。"""
    MAIN_MENU = "main_menu"
    EXIT = "exit"


class ActionType(Enum):
    """動作類型（副作用标识）。"""
    NONE = "none"
    RUN_DAILY_UPDATE = "run_daily_update"
    RUN_HISTORICAL_UPDATE = "run_historical_update"
    RUN_STRATEGY_MENU = "run_strategy_menu"
    RUN_DB_MAINTENANCE = "run_db_maintenance"
    RUN_COMPOSITE = "run_composite"


# ── Data ─────────────────────────────────────────────────


@dataclass
class StateTransition:
    """状态转移動作。"""
    next_state: TUIState
    action: ActionType = ActionType.NONE
    payload: Optional[Any] = None  # 例如股號


# ── Pure dispatch functions ──────────────────────────────


def dispatch_main_menu(user_input: str) -> StateTransition:
    """主選單狀態 dispatch。

    Args:
        user_input: 使用者輸入的選擇（已 trim 的字串）

    Returns:
        StateTransition 描述下一个状态与应執行的動作
    """
    if user_input == "0":
        return StateTransition(TUIState.EXIT)
    elif user_input == "1":
        return StateTransition(TUIState.MAIN_MENU, ActionType.RUN_DAILY_UPDATE)
    elif user_input == "2":
        return StateTransition(TUIState.MAIN_MENU, ActionType.RUN_HISTORICAL_UPDATE)
    elif user_input == "3":
        return StateTransition(TUIState.MAIN_MENU, ActionType.RUN_STRATEGY_MENU)
    elif user_input == "4":
        return StateTransition(TUIState.MAIN_MENU, ActionType.RUN_DB_MAINTENANCE)
    elif len(user_input) == 4 and user_input.isdigit():
        return StateTransition(TUIState.MAIN_MENU, ActionType.RUN_COMPOSITE, payload=user_input)
    elif user_input == "":
        return StateTransition(TUIState.MAIN_MENU)
    else:
        # 未知輸入，留在原状态
        return StateTransition(TUIState.MAIN_MENU)


# ── Historical update submenu ────────────────────────────


class HistoricalMenuState(Enum):
    """歷史更新子選單状态。"""
    LOOP = "loop"
    EXIT = "exit"


@dataclass
class HistoricalTransition:
    """歷史更新子選單转移動作。"""
    next_state: HistoricalMenuState
    action: Optional[str] = None
    payload: Optional[Any] = None


def dispatch_historical_menu(user_input: str) -> HistoricalTransition:
    """歷史更新子選單 dispatch。

    Args:
        user_input: 使用者輸入的選擇

    Returns:
        HistoricalTransition
    """
    if not user_input:
        return HistoricalTransition(HistoricalMenuState.EXIT)
    elif user_input == "1":
        return HistoricalTransition(HistoricalMenuState.LOOP, action="sync_days")
    elif user_input == "2":
        return HistoricalTransition(HistoricalMenuState.LOOP, action="sync_tdcc")
    elif user_input == "3":
        return HistoricalTransition(HistoricalMenuState.LOOP, action="sync_dividend_range")
    elif user_input == "4":
        return HistoricalTransition(HistoricalMenuState.LOOP, action="sync_dividend_year")
    elif user_input == "5":
        return HistoricalTransition(HistoricalMenuState.LOOP, action="check_anomalies")
    else:
        return HistoricalTransition(HistoricalMenuState.LOOP)


# ── Input routing helper ─────────────────────────────────


def route_stock_id(user_input: str) -> Optional[str]:
    """驗證並路由股票代號。

    Args:
        user_input: 使用者輸入

    Returns:
        有效的 4 碼股票代號，或 None
    """
    if len(user_input) == 4 and user_input.isdigit():
        return user_input
    return None


def should_exit(user_input: str) -> bool:
    """判斷是否應退出（輸入 0 或空）。

    Args:
        user_input: 使用者輸入

    Returns:
        True 表示應退出
    """
    return user_input == "0" or user_input == ""
