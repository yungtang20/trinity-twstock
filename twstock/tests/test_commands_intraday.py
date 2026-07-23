# -*- coding: utf-8 -*-
"""test_commands_intraday.py — commands/intraday.py execute 測試。"""

from __future__ import annotations

from argparse import Namespace
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

import twstock.commands.intraday as intraday_mod


@pytest.fixture
def empty_engine():
    engine = MagicMock()
    engine.df = pd.DataFrame()
    return engine


@pytest.fixture
def populated_engine():
    engine = MagicMock()
    engine.df = pd.DataFrame({"date": ["2025-01-01"], "close": [100.0]})
    engine.build.return_value = pd.DataFrame(
        {
            "close": [105.0],
            "volume": [1000],
            "sma_20": [102.0],
            "macd": [0.5],
            "institutional_net": [500],
        }
    )
    return engine


class TestIntradayExecute:
    @patch("twstock.commands.intraday.get_connection")
    @patch("twstock.commands.intraday.DataFetcher")
    @patch("twstock.commands.intraday.IndicatorEngine")
    @patch("twstock.commands.intraday.console")
    def test_normal_flow(self, mock_console, MockEngine, MockFetcher, mock_conn, populated_engine):
        MockEngine.return_value = populated_engine
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_intraday_snapshot.return_value = {
            "o": "100",
            "h": "110",
            "l": "95",
            "z": "105",
            "v": "1000",
        }
        MockFetcher.return_value = mock_fetcher
        mock_conn.return_value.__enter__ = MagicMock(
            return_value=MagicMock(
                execute=MagicMock(return_value=MagicMock(fetchone=MagicMock(return_value=None)))
            )
        )
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        args = Namespace(stock_id="2330")
        intraday_mod.execute(args)

        mock_fetcher.fetch_intraday_snapshot.assert_called_once_with("2330")
        assert populated_engine.build.called
        assert populated_engine.df.iloc[-1]["volume"] == 1_000_000

    @patch("twstock.commands.intraday.get_connection")
    @patch("twstock.commands.intraday.DataFetcher")
    @patch("twstock.commands.intraday.IndicatorEngine")
    @patch("twstock.commands.intraday.console")
    def test_empty_history_auto_updates(
        self, mock_console, MockEngine, MockFetcher, mock_conn, empty_engine, populated_engine
    ):
        # First call returns empty, second returns populated
        MockEngine.side_effect = [empty_engine, populated_engine]
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_intraday_snapshot.return_value = {
            "z": "105",
            "o": "100",
            "h": "110",
            "l": "95",
            "v": "1000",
        }
        MockFetcher.return_value = mock_fetcher
        mock_conn.return_value.__enter__ = MagicMock(
            return_value=MagicMock(
                execute=MagicMock(return_value=MagicMock(fetchone=MagicMock(return_value=None)))
            )
        )
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        with patch("twstock.commands.update.update_single_stock", return_value=True) as mock_update:
            intraday_mod.execute(Namespace(stock_id="2330"))
            mock_update.assert_called_once_with("2330", None)

    @patch("twstock.commands.intraday.DataFetcher")
    @patch("twstock.commands.intraday.IndicatorEngine")
    @patch("twstock.commands.intraday.console")
    def test_passes_token_to_datafetcher(self, mock_console, MockEngine, MockFetcher):
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_intraday_snapshot.return_value = {
            "z": "105",
            "o": "100",
            "h": "110",
            "l": "95",
            "v": "1000",
        }
        MockFetcher.return_value = mock_fetcher
        engine = MagicMock()
        engine.df = pd.DataFrame({"date": ["2025-01-01"], "close": [100.0]})
        engine.build.return_value = pd.DataFrame(
            {
                "close": [105.0],
                "volume": [1000],
                "sma_20": [102.0],
                "macd": [0.5],
                "institutional_net": [500],
            }
        )
        MockEngine.return_value = engine

        intraday_mod.execute(Namespace(stock_id="2330", token="mytoken"))

        MockFetcher.assert_called_once_with("mytoken")

    @patch("twstock.commands.intraday.DataFetcher")
    @patch("twstock.commands.intraday.IndicatorEngine")
    @patch("twstock.commands.intraday.console")
    def test_no_intraday_data_returns(
        self, mock_console, MockEngine, MockFetcher, populated_engine
    ):
        MockEngine.return_value = populated_engine
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_intraday_snapshot.return_value = None
        MockFetcher.return_value = mock_fetcher

        intraday_mod.execute(Namespace(stock_id="2330"))
        mock_console.print.assert_any_call("[red]❌ 無法取得即時報價 (非交易時段或無資料)[/red]")

    @patch("twstock.commands.intraday.DataFetcher")
    @patch("twstock.commands.intraday.IndicatorEngine")
    @patch("twstock.commands.intraday.console")
    def test_incomplete_quote_is_not_appended_as_zero(
        self, mock_console, MockEngine, MockFetcher, populated_engine
    ):
        """Missing MIS prices must not fall back to a stale daily close."""
        MockEngine.return_value = populated_engine
        MockFetcher.return_value.fetch_intraday_snapshot.return_value = {
            "o": "100",
            "h": "110",
            "l": "95",
            "z": None,
            "v": "1000",
        }

        intraday_mod.execute(Namespace(stock_id="2330"))

        assert not populated_engine.build.called
        printed = " ".join(str(call) for call in mock_console.print.call_args_list)
        assert "不完整" in printed

    @patch("twstock.commands.intraday.get_connection")
    @patch("twstock.commands.intraday.DataFetcher")
    @patch("twstock.commands.intraday.IndicatorEngine")
    @patch("twstock.commands.intraday.console")
    def test_dividend_today_warning(
        self, mock_console, MockEngine, MockFetcher, mock_conn, populated_engine
    ):
        MockEngine.return_value = populated_engine
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_intraday_snapshot.return_value = {
            "z": "105",
            "o": "100",
            "h": "110",
            "l": "95",
            "v": "1000",
        }
        MockFetcher.return_value = mock_fetcher

        mock_db = MagicMock()
        mock_db.execute.return_value.fetchone.return_value = (1,)  # has dividend
        mock_conn.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        intraday_mod.execute(Namespace(stock_id="2330"))
        printed = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "除權息" in printed

    @patch("twstock.commands.intraday.get_connection")
    @patch("twstock.commands.intraday.DataFetcher")
    @patch("twstock.commands.intraday.IndicatorEngine")
    @patch("twstock.commands.intraday.console")
    def test_empty_after_build_returns(self, mock_console, MockEngine, MockFetcher, mock_conn):
        engine = MagicMock()
        engine.df = pd.DataFrame({"date": ["2025-01-01"], "close": [100.0]})
        engine.build.return_value = pd.DataFrame()  # empty
        MockEngine.return_value = engine
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_intraday_snapshot.return_value = {
            "z": "105",
            "o": "100",
            "h": "110",
            "l": "95",
            "v": "1000",
        }
        MockFetcher.return_value = mock_fetcher
        mock_conn.return_value.__enter__ = MagicMock(
            return_value=MagicMock(
                execute=MagicMock(return_value=MagicMock(fetchone=MagicMock(return_value=None)))
            )
        )
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        intraday_mod.execute(Namespace(stock_id="2330"))
        printed = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "無法計算" in printed or "指標" in printed
