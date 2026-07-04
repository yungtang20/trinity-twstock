# -*- coding: utf-8 -*-
"""Unit tests for tui/app.py — TUIApp initialization and render."""
from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

_DIR = "D:/twse"
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)

# Suppress rich console output
import rich.console

rich.console.Console = lambda **kw: MagicMock()


# ── TUIApp ──────────────────────────────────────────────────
class TestTUIApp:
    def test_instantiation(self):
        from twstock.tui.app import TUIApp
        app = TUIApp()
        assert app is not None
        assert hasattr(app, "run")
        assert hasattr(app, "_cache")

    def test_has_cache(self):
        from twstock.market_data.cache import MarketCache
        from twstock.tui.app import TUIApp
        app = TUIApp()
        assert isinstance(app._cache, MarketCache)

    @patch("twstock.tui.app.run_composite")
    @patch("twstock.tui.app.strategies_menu")
    @patch("twstock.tui.app.run_db_maintenance")
    @patch("twstock.tui.app.run_historical_update_menu")
    @patch("twstock.tui.app.run_daily_update")
    @patch("twstock.tui.app.render_dashboard")
    @patch("twstock.tui.app.TUIApp._get_input")
    def test_run_menu_dispatch(
        self, mock_input, mock_render, mock_daily, mock_hist,
        mock_db, mock_strat, mock_composite
    ):
        """run() 應根據輸入分派至對應處理函式。"""
        from twstock.tui.app import TUIApp

        # 模擬使用者依次選擇 1, 2, 3, 4, 0（退出）
        mock_input.side_effect = ["1", "2", "3", "4", "2330", "0"]
        app = TUIApp()
        app.run()

        mock_daily.assert_called_once()
        mock_hist.assert_called_once()
        mock_strat.assert_called_once()
        mock_db.assert_called_once()
        mock_composite.assert_called_once_with("2330")


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
        mock_composite.assert_called_once_with("2330")


# ── _get_input — Windows msvcrt path ─────────────────────────
class TestGetInput:
    """_get_input on Windows (msvcrt) path.

    IMPORTANT: The initial flush loop runs `while msvcrt.kbhit(): msvcrt.getwch()`,
    so kbhit.side_effect MUST start with one True (consume stale key) then False
    to exit the flush loop before the read loop begins.

    time must be mocked to prevent real sleeps.
    """

    @patch("twstock.tui.app.HAS_MSVCRT", True)
    @patch("twstock.tui.app.render_dashboard")
    @patch("twstock.tui.app.msvcrt")
    @patch("twstock.tui.app.sys")
    def test_get_input_enter_key(self, mock_sys, mock_msvcrt, _mock_render):
        """Enter key (\r) returns buf.strip()."""
        from twstock.tui.app import TUIApp
        mock_msvcrt.kbhit.side_effect = [True, False, True]
        mock_msvcrt.getwch.side_effect = ["x", "\r"]
        mock_sys.stdout = MagicMock()
        app = TUIApp()
        app._cache = MagicMock()
        app._cache.get.return_value = "cached"
        result = app._get_input()
        assert result == ""

    @patch("twstock.tui.app.HAS_MSVCRT", True)
    @patch("twstock.tui.app.render_dashboard")
    @patch("twstock.tui.app.msvcrt")
    @patch("twstock.tui.app.sys")
    def test_get_input_backspace(self, mock_sys, mock_msvcrt, _mock_render):
        """Backspace (\b) truncates buf."""
        from twstock.tui.app import TUIApp
        mock_msvcrt.kbhit.side_effect = [True, False, True, True, True, True]
        mock_msvcrt.getwch.side_effect = ["x", "a", "b", "\b", "\r"]
        mock_sys.stdout = MagicMock()
        app = TUIApp()
        app._cache = MagicMock()
        app._cache.get.return_value = "cached"
        result = app._get_input()
        assert result == "a"

    @patch("twstock.tui.app.HAS_MSVCRT", True)
    @patch("twstock.tui.app.render_dashboard")
    @patch("twstock.tui.app.msvcrt")
    @patch("twstock.tui.app.sys")
    def test_get_input_esc_returns_zero(self, mock_sys, mock_msvcrt, _mock_render):
        """ESC (\x1b) returns '0'."""
        from twstock.tui.app import TUIApp
        mock_msvcrt.kbhit.side_effect = [True, False, True]
        mock_msvcrt.getwch.side_effect = ["x", "\x1b"]
        mock_sys.stdout = MagicMock()
        app = TUIApp()
        app._cache = MagicMock()
        app._cache.get.return_value = "cached"
        result = app._get_input()
        assert result == "0"

    @patch("twstock.tui.app.HAS_MSVCRT", True)
    @patch("twstock.tui.app.render_dashboard")
    @patch("twstock.tui.app.msvcrt")
    @patch("twstock.tui.app.sys")
    def test_get_input_printable_chars(self, mock_sys, mock_msvcrt, _mock_render):
        """Printable chars append to buf (menu_keys="" skips single-key wait)."""
        from twstock.tui.app import TUIApp
        mock_msvcrt.kbhit.side_effect = [True, False, True, True, True, True, True]
        mock_msvcrt.getwch.side_effect = ["x", "2", "3", "3", "0", "\r"]
        mock_sys.stdout = MagicMock()
        app = TUIApp()
        app._cache = MagicMock()
        app._cache.get.return_value = "cached"
        result = app._get_input(menu_keys="", auto_four=False)
        assert result == "2330"

    @patch("time.sleep", MagicMock())
    @patch("time.time", side_effect=[0.0, 0.5])
    @patch("twstock.tui.app.HAS_MSVCRT", True)
    @patch("twstock.tui.app.render_dashboard")
    @patch("twstock.tui.app.msvcrt")
    @patch("twstock.tui.app.sys")
    def test_get_input_single_key_menu_auto_commit(self, mock_sys, mock_msvcrt, _mock_render, _mock_time):
        """Single key menu (e.g. '1') auto-commits when no second key within timeout."""
        from twstock.tui.app import TUIApp
        # flush: True+False; read: True (key '1'); _wait_for_key: False,False,False → timeout
        mock_msvcrt.kbhit.side_effect = [True, False, True, False, False, False]
        mock_msvcrt.getwch.side_effect = ["x", "1"]
        mock_sys.stdout = MagicMock()
        app = TUIApp()
        app._cache = MagicMock()
        app._cache.get.return_value = "cached"
        result = app._get_input(menu_keys="01234")
        assert result == "1"

    @patch("twstock.tui.app.HAS_MSVCRT", True)
    @patch("twstock.tui.app.msvcrt")
    @patch("twstock.tui.app.sys")
    @patch("twstock.tui.app.MarketCache")
    def test_get_input_cache_refresh_triggers_rerender(self, mock_cache_cls, mock_sys, mock_msvcrt):
        """Cache refresh (None→value) triggers re-render during input."""
        from twstock.tui.app import TUIApp
        mock_msvcrt.kbhit.side_effect = [False, False, True]
        mock_msvcrt.getwch.return_value = "\r"
        mock_sys.stdout = MagicMock()
        # First cache.get() returns None (no data yet), then "value" (data arrived)
        mock_cache_cls.return_value.get.side_effect = [None, "value", "value"]
        app = TUIApp()
        result = app._get_input()
        assert result == ""


# ── _wait_for_key ────────────────────────────────────────────
class TestWaitForKey:
    """_wait_for_key waits for key press within timeout.

    time.sleep is mocked to be instant — wall-clock still advances,
    so time.time() based loop terminates normally within ~100ms for timeout=0.1.
    """

    @patch("time.sleep", MagicMock())
    @patch("twstock.tui.app.msvcrt")
    def test_wait_for_key_with_key(self, mock_msvcrt):
        """kbhit True → returns True."""
        from twstock.tui.app import TUIApp
        mock_msvcrt.kbhit.return_value = True
        mock_msvcrt.getwch.return_value = "a"
        result = TUIApp._wait_for_key(0.1)
        assert result is True

    @patch("time.sleep", MagicMock())
    @patch("twstock.tui.app.msvcrt")
    def test_wait_for_key_timeout(self, mock_msvcrt):
        """kbhit always False → timeout → returns False."""
        from twstock.tui.app import TUIApp
        mock_msvcrt.kbhit.return_value = False
        result = TUIApp._wait_for_key(0.01)  # small timeout for test speed
        assert result is False

    @patch("time.sleep", MagicMock())
    @patch("twstock.tui.app.msvcrt")
    def test_wait_for_key_enter_swallowed(self, mock_msvcrt):
        """Enter key (\r) swallowed but still returns True."""
        from twstock.tui.app import TUIApp
        mock_msvcrt.kbhit.return_value = True
        mock_msvcrt.getwch.return_value = "\r"
        result = TUIApp._wait_for_key(0.1)
        assert result is True


# ── _wait_for_stock_suffix ───────────────────────────────────
class TestWaitForStockSuffix:
    """_wait_for_stock_suffix waits for 4-digit suffix input."""

    @patch("time.sleep", MagicMock())
    @patch("twstock.tui.app.msvcrt")
    def test_wait_for_stock_suffix_enter(self, mock_msvcrt):
        """Enter key breaks loop → returns buf."""
        from twstock.tui.app import TUIApp
        mock_msvcrt.kbhit.side_effect = [True, False]
        mock_msvcrt.getwch.return_value = "\r"
        result = TUIApp._wait_for_stock_suffix(0.1, "2330")
        assert result == "2330"

    @patch("time.sleep", MagicMock())
    @patch("twstock.tui.app.msvcrt")
    @patch("twstock.tui.app.sys")
    def test_wait_for_stock_suffix_backspace(self, mock_sys, mock_msvcrt):
        """Backspace interrupts → returns None, truncates buf."""
        from twstock.tui.app import TUIApp
        mock_msvcrt.kbhit.side_effect = [True, False]
        mock_msvcrt.getwch.return_value = "\b"
        mock_sys.stdout = MagicMock()
        result = TUIApp._wait_for_stock_suffix(0.1, "2330")
        assert result is None

    @patch("time.sleep", MagicMock())
    @patch("twstock.tui.app.msvcrt")
    @patch("twstock.tui.app.sys")
    def test_wait_for_stock_suffix_printable_interrupts(self, mock_sys, mock_msvcrt):
        """Printable char after 4 digits → has_interrupted=True → returns None."""
        from twstock.tui.app import TUIApp
        mock_msvcrt.kbhit.side_effect = [True, False]
        mock_msvcrt.getwch.return_value = "a"
        mock_sys.stdout = MagicMock()
        result = TUIApp._wait_for_stock_suffix(0.1, "2330")
        assert result is None

    @patch("time.sleep", MagicMock())
    @patch("twstock.tui.app.msvcrt")
    def test_wait_for_stock_suffix_timeout_no_interrupt(self, mock_msvcrt):
        """Timeout with no interrupt → returns buf."""
        from twstock.tui.app import TUIApp
        mock_msvcrt.kbhit.return_value = False
        result = TUIApp._wait_for_stock_suffix(0.01, "2330")
        assert result == "2330"


# ── _get_input — non-msvcrt fallback ─────────────────────────
class TestGetInputFallback:
    """_get_input when HAS_MSVCRT is False (fallback to input())."""

    @patch("twstock.tui.app.HAS_MSVCRT", False)
    @patch("twstock.tui.app.input")
    def test_get_input_fallback_to_stdin(self, mock_input):
        """Without msvcrt, delegates to input().strip()."""
        from twstock.tui.app import TUIApp
        mock_input.return_value = "hello"
        app = TUIApp()
        result = app._get_input()
        assert result == "hello"
        mock_input.assert_called_once()
