# -*- coding: utf-8 -*-
"""Unit tests for commands/ — verify execute() interface and delegation."""
from __future__ import annotations

import sys
from argparse import Namespace
from unittest.mock import patch, MagicMock

import pytest

_DIR = "D:/twse"
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)


# ── dividend ────────────────────────────────────────────────
class TestDividendCommand:
    def test_missing_dates_returns_early(self):
        from twstock.commands.dividend import execute
        args = Namespace(start_date=None, end_date=None)
        # Should not raise, just print error
        execute(args)

    def test_with_valid_dates(self):
        from twstock.commands.dividend import execute
        args = Namespace(start_date="2026-01-01", end_date="2026-07-02")
        with patch("twstock.commands.dividend.fetch_dividend_events") as mock_fetch:
            import pandas as pd
            mock_fetch.return_value = pd.DataFrame(columns=["stock_id"])
            execute(args)
            assert mock_fetch.called


# ── indicators ──────────────────────────────────────────────
class TestIndicatorsCommand:
    def test_missing_data(self):
        from twstock.commands.indicators import execute
        args = Namespace(stock_id="0000")
        with patch("twstock.commands.indicators.get_connection") as mock_conn:
            mock_ctx = MagicMock()
            mock_conn.return_value.__enter__ = MagicMock(return_value=mock_ctx)
            mock_conn.return_value.__exit__ = MagicMock(return_value=False)
            # Return empty query result
            mock_ctx.execute.return_value.fetchall.return_value = []
            execute(args)  # Should not raise


# ── update ──────────────────────────────────────────────────
class TestUpdateCommand:
    def test_update_single_stock(self):
        from twstock.commands.update import update_single_stock
        with patch("twstock.commands.update.DataProcessor") as mock_proc_cls, \
             patch("twstock.commands.update.DataFetcher") as mock_fetcher_cls:
            mock_proc = MagicMock()
            mock_proc_cls.return_value = mock_proc
            mock_fetcher = MagicMock()
            mock_fetcher_cls.return_value = mock_fetcher
            import pandas as pd
            mock_fetcher.fetch_history_price.return_value = pd.DataFrame(columns=["date"])
            # Should not raise
            update_single_stock("2330", None)


# ── strategy ────────────────────────────────────────────────
class TestStrategyCommand:
    def test_delegates_to_run_strategy_cli(self):
        from twstock.commands.strategy import execute
        with patch("twstock.commands.strategy.run_strategy_cli") as mock_run:
            args = Namespace()
            execute(args)
            assert mock_run.called
