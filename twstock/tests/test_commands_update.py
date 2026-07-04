# -*- coding: utf-8 -*-
"""test_commands_update.py — commands/update.py 單元測試。"""
from __future__ import annotations
from argparse import Namespace
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

import twstock.commands.update as update_mod


@pytest.fixture
def mock_fetcher():
    fetcher = MagicMock()
    fetcher.fetch_history_price.return_value = pd.DataFrame(
        {"date": ["2025-01-01"], "close": [100.0]}
    )
    fetcher.fetch_institutional.return_value = pd.DataFrame()
    fetcher.fetch_shareholding.return_value = pd.DataFrame()
    fetcher.fetch_stock_meta.return_value = pd.DataFrame()
    return fetcher


@pytest.fixture
def mock_processor():
    return MagicMock()


class TestUpdateSingleStock:
    @patch("twstock.commands.update.fetch_tdcc_historical")
    @patch("twstock.commands.update.fetch_dividend_events")
    @patch("twstock.commands.update.DataProcessor")
    @patch("twstock.commands.update.DataFetcher")
    @patch("twstock.commands.update.console")
    def test_success_with_empty_institutional(
        self, mock_console, MockFetcher, MockProcessor, mock_div, mock_tdcc,
        mock_fetcher, mock_processor
    ):
        MockFetcher.return_value = mock_fetcher
        MockProcessor.return_value = mock_processor
        mock_div.return_value = pd.DataFrame()
        mock_tdcc.return_value = pd.DataFrame()

        result = update_mod.update_single_stock("2330")

        assert result is True
        mock_fetcher.fetch_history_price.assert_called_once()
        mock_processor.upsert_history.assert_called_once()

    @patch("twstock.commands.update.fetch_tdcc_historical")
    @patch("twstock.commands.update.fetch_dividend_events")
    @patch("twstock.commands.update.DataProcessor")
    @patch("twstock.commands.update.DataFetcher")
    @patch("twstock.commands.update.console")
    def test_returns_false_when_no_price(
        self, mock_console, MockFetcher, MockProcessor, mock_div, mock_tdcc
    ):
        fetcher = MagicMock()
        fetcher.fetch_history_price.return_value = pd.DataFrame()
        MockFetcher.return_value = fetcher

        result = update_mod.update_single_stock("2330")

        assert result is False
        mock_div.assert_not_called()
        mock_tdcc.assert_not_called()

    @patch("twstock.commands.update.fetch_tdcc_historical")
    @patch("twstock.commands.update.fetch_dividend_events")
    @patch("twstock.commands.update.DataProcessor")
    @patch("twstock.commands.update.DataFetcher")
    @patch("twstock.commands.update.console")
    def test_with_all_data_sources(
        self, mock_console, MockFetcher, MockProcessor, mock_div, mock_tdcc,
        mock_processor
    ):
        fetcher = MagicMock()
        fetcher.fetch_history_price.return_value = pd.DataFrame({"date": ["2025-01-01"], "close": [100]})
        fetcher.fetch_institutional.return_value = pd.DataFrame({"date": ["2025-01-01"], "foreign": [1000]})
        fetcher.fetch_shareholding.return_value = pd.DataFrame({"date": ["2025-01-01"], "level": [1]})
        fetcher.fetch_stock_meta.return_value = pd.DataFrame({"stock_id": ["2330"], "stock_name": ["台積電"]})

        MockFetcher.return_value = fetcher
        MockProcessor.return_value = mock_processor
        mock_div.return_value = pd.DataFrame({"stock_id": ["2330"]})
        mock_tdcc.return_value = pd.DataFrame({"stock_id": ["2330"]})

        result = update_mod.update_single_stock("2330")

        assert result is True
        mock_processor.upsert_institutional.assert_called_once()
        mock_processor.upsert_shareholding.assert_called_once()
        mock_processor.upsert_dividend_events.assert_called_once()
        mock_processor.upsert_tdcc.assert_called_once()
        mock_processor.upsert_meta.assert_called_once()

    @patch("twstock.commands.update.fetch_tdcc_historical")
    @patch("twstock.commands.update.fetch_dividend_events")
    @patch("twstock.commands.update.DataProcessor")
    @patch("twstock.commands.update.DataFetcher")
    @patch("twstock.commands.update.console")
    def test_dividend_exception_handled(
        self, mock_console, MockFetcher, MockProcessor, mock_div, mock_tdcc,
        mock_fetcher, mock_processor
    ):
        MockFetcher.return_value = mock_fetcher
        MockProcessor.return_value = mock_processor
        mock_div.side_effect = Exception("network error")
        mock_tdcc.return_value = pd.DataFrame()

        result = update_mod.update_single_stock("2330")

        assert result is True
        # div_events should be empty → upsert not called for dividend
        mock_processor.upsert_dividend_events.assert_not_called()

    @patch("twstock.commands.update.fetch_tdcc_historical")
    @patch("twstock.commands.update.fetch_dividend_events")
    @patch("twstock.commands.update.DataProcessor")
    @patch("twstock.commands.update.DataFetcher")
    @patch("twstock.commands.update.console")
    def test_tdcc_exception_handled(
        self, mock_console, MockFetcher, MockProcessor, mock_div, mock_tdcc,
        mock_fetcher, mock_processor
    ):
        MockFetcher.return_value = mock_fetcher
        MockProcessor.return_value = mock_processor
        mock_div.return_value = pd.DataFrame()
        mock_tdcc.side_effect = Exception("tdcc network error")

        result = update_mod.update_single_stock("2330")
        assert result is True
        mock_processor.upsert_tdcc.assert_not_called()


class TestExecute:
    @patch("twstock.commands.update.update_single_stock")
    def test_execute_dispatches(self, mock_update):
        args = Namespace(stock_id="2330", token="mytoken")
        update_mod.execute(args)
        mock_update.assert_called_once_with("2330", "mytoken")

    @patch("twstock.commands.update.update_single_stock")
    def test_execute_without_token(self, mock_update):
        args = Namespace(stock_id="2330")
        update_mod.execute(args)
        mock_update.assert_called_once_with("2330", None)
