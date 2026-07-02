# -*- coding: utf-8 -*-
"""Unit tests for tui/app.py — TUIApp initialization and render."""
from __future__ import annotations

import sys
from unittest.mock import patch, MagicMock

import pytest

_DIR = "D:/twse"
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)

# Suppress rich console output
import io
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
        from twstock.tui.app import TUIApp
        from twstock.market_data.cache import MarketCache
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
        from twstock.tui.render import render_dashboard, make_layout
        assert callable(render_dashboard)
        assert callable(make_layout)

    def test_make_layout_returns_layout(self):
        from twstock.tui.render import make_layout
        from rich.layout import Layout
        result = make_layout()
        assert isinstance(result, Layout)


# ── menu functions importable ──────────────────────────────
class TestMenuFunctions:
    def test_functions_exist(self):
        from twstock.tui.menu import (
            run_daily_update,
            run_historical_update_menu,
            run_db_maintenance,
            _check_zero_volume_anomalies,
        )
        assert callable(run_daily_update)
        assert callable(run_historical_update_menu)
        assert callable(run_db_maintenance)
        assert callable(_check_zero_volume_anomalies)
