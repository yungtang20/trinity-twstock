# -*- coding: utf-8 -*-
"""test_tui_state_machine.py — tui/state_machine.py 單元測試。

純邏輯測試，無需 I/O mock。
"""
from __future__ import annotations

import pytest

from twstock.tui.state_machine import (
    ActionType,
    HistoricalMenuState,
    HistoricalTransition,
    StateTransition,
    TUIState,
    dispatch_historical_menu,
    dispatch_main_menu,
    route_stock_id,
    should_exit,
)


# ── dispatch_main_menu ────────────────────────────────────


class TestDispatchMainMenu:
    """主選單 dispatch 測試。"""

    def test_input_0_exits(self):
        """輸入 0 應退出。"""
        result = dispatch_main_menu("0")
        assert result.next_state == TUIState.EXIT
        assert result.action == ActionType.NONE

    def test_input_1_daily_update(self):
        """輸入 1 應觸發每日更新。"""
        result = dispatch_main_menu("1")
        assert result.next_state == TUIState.MAIN_MENU
        assert result.action == ActionType.RUN_DAILY_UPDATE

    def test_input_2_historical_update(self):
        """輸入 2 應觸發歷史更新。"""
        result = dispatch_main_menu("2")
        assert result.next_state == TUIState.MAIN_MENU
        assert result.action == ActionType.RUN_HISTORICAL_UPDATE

    def test_input_3_strategy(self):
        """輸入 3 應觸發策略選單。"""
        result = dispatch_main_menu("3")
        assert result.next_state == TUIState.MAIN_MENU
        assert result.action == ActionType.RUN_STRATEGY_MENU

    def test_input_4_maintenance(self):
        """輸入 4 應觸發資料庫維護。"""
        result = dispatch_main_menu("4")
        assert result.next_state == TUIState.MAIN_MENU
        assert result.action == ActionType.RUN_DB_MAINTENANCE

    def test_input_stock_id(self):
        """輸入 4 碼股號應觸發綜合分析。"""
        result = dispatch_main_menu("2330")
        assert result.next_state == TUIState.MAIN_MENU
        assert result.action == ActionType.RUN_COMPOSITE
        assert result.payload == "2330"

    def test_input_empty_stays(self):
        """空輸入應留在主選單。"""
        result = dispatch_main_menu("")
        assert result.next_state == TUIState.MAIN_MENU
        assert result.action == ActionType.NONE

    def test_input_unknown_stays(self):
        """未知輸入應留在主選單。"""
        result = dispatch_main_menu("99")
        assert result.next_state == TUIState.MAIN_MENU

    def test_input_alpha_stays(self):
        """字母輸入應留在主選單。"""
        result = dispatch_main_menu("abc")
        assert result.next_state == TUIState.MAIN_MENU

    def test_all_valid_menu_keys(self):
        """測試所有有效的選單鍵。"""
        valid_actions = {
            "1": ActionType.RUN_DAILY_UPDATE,
            "2": ActionType.RUN_HISTORICAL_UPDATE,
            "3": ActionType.RUN_STRATEGY_MENU,
            "4": ActionType.RUN_DB_MAINTENANCE,
        }
        for key, expected_action in valid_actions.items():
            result = dispatch_main_menu(key)
            assert result.action == expected_action, f"按鍵 {key} 应對應 {expected_action}"


# ── dispatch_historical_menu ─────────────────────────────


class TestDispatchHistoricalMenu:
    """歷史更新子選單 dispatch 測試。"""

    def test_empty_input_exits(self):
        """空輸入應退出子選單。"""
        result = dispatch_historical_menu("")
        assert result.next_state == HistoricalMenuState.EXIT

    def test_input_1_sync_days(self):
        result = dispatch_historical_menu("1")
        assert result.next_state == HistoricalMenuState.LOOP
        assert result.action == "sync_days"

    def test_input_2_sync_tdcc(self):
        result = dispatch_historical_menu("2")
        assert result.action == "sync_tdcc"

    def test_input_3_sync_dividend_range(self):
        result = dispatch_historical_menu("3")
        assert result.action == "sync_dividend_range"

    def test_input_4_sync_dividend_year(self):
        result = dispatch_historical_menu("4")
        assert result.action == "sync_dividend_year"

    def test_input_5_check_anomalies(self):
        result = dispatch_historical_menu("5")
        assert result.action == "check_anomalies"

    def test_unknown_input_stays(self):
        """未知輸入應留在子選單。"""
        result = dispatch_historical_menu("99")
        assert result.next_state == HistoricalMenuState.LOOP


# ── route_stock_id ────────────────────────────────────────


class TestRouteStockId:
    """route_stock_id 股票代號路由。"""

    def test_valid_4_digit(self):
        assert route_stock_id("2330") == "2330"

    def test_valid_another(self):
        assert route_stock_id("0050") == "0050"

    def test_invalid_3_digit(self):
        assert route_stock_id("230") is None

    def test_invalid_5_digit(self):
        assert route_stock_id("23301") is None

    def test_invalid_alpha(self):
        assert route_stock_id("abcd") is None

    def test_empty(self):
        assert route_stock_id("") is None


# ── should_exit ───────────────────────────────────────────


class TestShouldExit:
    """should_exit 退出判断。"""

    def test_zero_exits(self):
        assert should_exit("0") is True

    def test_empty_exits(self):
        assert should_exit("") is True

    def test_nonzero_stays(self):
        assert should_exit("1") is False

    def test_stock_id_stays(self):
        assert should_exit("2330") is False
