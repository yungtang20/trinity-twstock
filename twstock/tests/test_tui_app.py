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
