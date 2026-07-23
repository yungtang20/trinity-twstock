# -*- coding: utf-8 -*-
"""策略選單的單鍵與股號輸入回歸測試。"""

from __future__ import annotations

from unittest.mock import patch

from twstock.strategy import strategies


def test_strategy_root_menu_enter_returns() -> None:
    """策略根選單按 Enter 應立即返回，不要求第二次輸入。"""
    with (
        patch("twstock.strategy.strategies.list_strategies"),
        patch("twstock.strategy.strategies.get_single_key_input", return_value="") as mock_key,
    ):
        strategies.interactive_menu()

    mock_key.assert_called_once_with("按數字鍵選擇策略 (Enter 退出): ", "12345")


def test_sort_menu_uses_single_key() -> None:
    """排序選單按 2 應直接生效。"""
    with patch("twstock.strategy.strategies.get_single_key_input", return_value="2"):
        assert strategies._input_sort_ma() == "2"


def test_kronos_prompt_auto_submits_four_digit_stock() -> None:
    """4 碼股號應由互動輸入層自動送出並路由至 AI 預測。"""
    with (
        patch("twstock.strategy.strategies.get_interactive_input", return_value="2330") as mock_input,
        patch("twstock.strategy.strategies.run_strategy_by_id") as mock_run,
    ):
        strategies._prompt_kronos_ai()

    mock_input.assert_called_once_with(
        "🔍 輸入 4 碼股號，或按 Enter 回到上一頁: ", menu_keys="", auto_four=True
    )
    mock_run.assert_called_once_with("5", {"code": "2330"})
