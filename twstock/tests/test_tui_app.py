# -*- coding: utf-8 -*-
"""Unit tests for tui/app.py — TUIApp initialization and render.

A + ① 組合：_get_input / _wait_for_key / _wait_for_stock_suffix 已移除，
改為 blocking_input。測試只覆蓋 __init__、run 分派、_execute_action。
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

_DIR = "D:/twse"
if _DIR not in __import__("sys").path:
    __import__("sys").path.insert(0, _DIR)

import rich.console

rich.console.Console = lambda **kw: MagicMock()  # type: ignore[misc,assignment]


class TestTUIApp:
    def test_instantiation(self):
        from twstock.tui.app import TUIApp

        app = TUIApp()
        assert app is not None
        assert hasattr(app, "run")

    def test_has_cache(self):
        """TUIApp.run() 不儲存 _cache（① 組合：不即時刷，不需 cache 引用）。"""
        from twstock.tui.app import TUIApp

        app = TUIApp()
        assert not hasattr(app, "_cache"), "_cache 應在 A + ① 組合中移除"

    @patch("twstock.tui.app.run_composite")
    @patch("twstock.tui.app.strategies_menu")
    @patch("twstock.tui.app.run_db_maintenance")
    @patch("twstock.tui.app.run_historical_update_menu")
    @patch("twstock.tui.app.run_daily_update")
    @patch("twstock.tui.app.warmup_market_cache")
    @patch("twstock.tui.app.wait_for_market_cache")
    @patch("twstock.tui.app.render_dashboard")
    @patch("twstock.tui.app.blocking_input")
    def test_run_menu_dispatch(
        self,
        mock_input,
        mock_render,
        mock_wait_market,
        mock_warmup,
        mock_daily,
        mock_hist,
        mock_db,
        mock_strat,
        mock_composite,
    ):
        """run() 應根據輸入分派至對應處理函式。"""
        from twstock.tui.app import TUIApp
        mock_input.side_effect = ["1", "2", "3", "4", "2330", "0"]
        app = TUIApp()
        app.run()

        mock_daily.assert_called_once()
        mock_hist.assert_called_once()
        mock_strat.assert_called_once()
        mock_db.assert_called_once()
        mock_composite.assert_called_once_with("2330", allow_live_quote=True)
        assert mock_warmup.call_count == 6
        mock_wait_market.assert_called_once_with()
        assert mock_render.call_count == 7
        mock_input.assert_called_with("\n🔍 輸入選項或 4 碼股號，再按 Enter：")


# ── render_dashboard ────────────────────────────────────────
class TestRenderDashboard:
    def test_importable(self):
        from twstock.tui.render import make_layout, render_dashboard

        assert callable(render_dashboard)
        assert callable(make_layout)

    def test_make_layout_returns_layout(self):
        from rich.layout import Layout

        from twstock.tui.render import make_layout

        result = make_layout()
        assert isinstance(result, Layout)


# ── _execute_action — each ActionType branch ─────────────────
class TestExecuteAction:
    """_execute_action dispatches to the correct handler per ActionType."""

    @patch("twstock.tui.app.run_composite")
    @patch("twstock.tui.app.run_db_maintenance")
    @patch("twstock.tui.app.strategies_menu")
    @patch("twstock.tui.app.run_historical_update_menu")
    @patch("twstock.tui.app.run_daily_update")
    def test_execute_action_daily(self, mock_daily, mock_hist, mock_strat, mock_db, mock_composite):
        from twstock.tui.app import TUIApp
        from twstock.tui.state_machine import ActionType, StateTransition, TUIState

        t = StateTransition(TUIState.MAIN_MENU, ActionType.RUN_DAILY_UPDATE)
        app = TUIApp()
        app._execute_action(t)
        mock_daily.assert_called_once()

    @patch("twstock.tui.app.run_composite")
    @patch("twstock.tui.app.run_db_maintenance")
    @patch("twstock.tui.app.strategies_menu")
    @patch("twstock.tui.app.run_historical_update_menu")
    @patch("twstock.tui.app.run_daily_update")
    def test_execute_action_historical(
        self, mock_daily, mock_hist, mock_strat, mock_db, mock_composite
    ):
        from twstock.tui.app import TUIApp
        from twstock.tui.state_machine import ActionType, StateTransition, TUIState

        t = StateTransition(TUIState.MAIN_MENU, ActionType.RUN_HISTORICAL_UPDATE)
        app = TUIApp()
        app._execute_action(t)
        mock_hist.assert_called_once()

    @patch("twstock.tui.app.run_composite")
    @patch("twstock.tui.app.run_db_maintenance")
    @patch("twstock.tui.app.strategies_menu")
    @patch("twstock.tui.app.run_historical_update_menu")
    @patch("twstock.tui.app.run_daily_update")
    def test_execute_action_strategy(
        self, mock_daily, mock_hist, mock_strat, mock_db, mock_composite
    ):
        from twstock.tui.app import TUIApp
        from twstock.tui.state_machine import ActionType, StateTransition, TUIState

        t = StateTransition(TUIState.MAIN_MENU, ActionType.RUN_STRATEGY_MENU)
        app = TUIApp()
        app._execute_action(t)
        mock_strat.assert_called_once()

    @patch("twstock.tui.app.run_composite")
    @patch("twstock.tui.app.run_db_maintenance")
    @patch("twstock.tui.app.strategies_menu")
    @patch("twstock.tui.app.run_historical_update_menu")
    @patch("twstock.tui.app.run_daily_update")
    def test_execute_action_db_maintenance(
        self, mock_daily, mock_hist, mock_strat, mock_db, mock_composite
    ):
        from twstock.tui.app import TUIApp
        from twstock.tui.state_machine import ActionType, StateTransition, TUIState

        t = StateTransition(TUIState.MAIN_MENU, ActionType.RUN_DB_MAINTENANCE)
        app = TUIApp()
        app._execute_action(t)
        mock_db.assert_called_once()

    @patch("twstock.tui.app.run_composite")
    @patch("twstock.tui.app.run_db_maintenance")
    @patch("twstock.tui.app.strategies_menu")
    @patch("twstock.tui.app.run_historical_update_menu")
    @patch("twstock.tui.app.run_daily_update")
    def test_execute_action_composite(
        self, mock_daily, mock_hist, mock_strat, mock_db, mock_composite
    ):
        from twstock.tui.app import TUIApp
        from twstock.tui.state_machine import ActionType, StateTransition, TUIState

        t = StateTransition(TUIState.MAIN_MENU, ActionType.RUN_COMPOSITE, "2330")
        app = TUIApp()
        app._execute_action(t)
        mock_composite.assert_called_once_with("2330", allow_live_quote=True)


# ── blocking_input import ───────────────────────────────────
class TestBlockingInputImport:
    def test_blocking_input_importable(self):
        from twstock.input_helper import blocking_input

        assert callable(blocking_input)

    def test_blocking_input_returns_stripped(self):
        from twstock.input_helper import blocking_input

        with patch("builtins.input", return_value="  hello  "):
            result = blocking_input("test: ")
        assert result == "hello"

    def test_blocking_input_empty_on_enter(self):
        from twstock.input_helper import blocking_input

        with patch("builtins.input", return_value=""):
            result = blocking_input("test: ")
        assert result == ""
