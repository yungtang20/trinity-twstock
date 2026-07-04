# -*- coding: utf-8 -*-
"""test_composites.py — strategy/composites.py 覆蓋率測試。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from twstock.strategy import composites


class TestRunComposite:
    """run_composite 完整流程測試。"""

    @patch("twstock.strategy.composites.input")
    @patch("twstock.strategy.composites.console")
    @patch("twstock.strategy.composites.get_connection")
    @patch("twstock.strategy.composites._run_strategies")
    @patch("twstock.strategy.composites._render_price_panel")
    @patch("twstock.strategy.composites._fetch_live_quote")
    def test_run_composite_with_valid_stock(
        self, mock_quote, mock_render, mock_strategies, mock_conn, console_mock, mock_input
    ):
        """有效股號應執行完整流程。"""
        mock_quote.return_value = (100.0, 1000)
        mock_ctx = MagicMock()
        # 模擬 DB 返回 3 筆交易紀錄
        mock_ctx.execute.return_value.fetchone.return_value = ("2026-07-02",)
        mock_ctx.execute.return_value.fetchall.return_value = [
            ("2026-07-02", 100.0, 1000),
            ("2026-07-01", 99.0, 900),
            ("2026-06-30", 98.0, 800),
        ]
        mock_conn.return_value.__enter__ = MagicMock(return_value=mock_ctx)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)
        mock_input.return_value = ""

        composites.run_composite("2330", mobile=False)

        mock_render.assert_called_once()
        mock_strategies.assert_called_once_with("2330", False)

    @patch("twstock.strategy.composites.input")
    @patch("twstock.strategy.composites.console")
    @patch("twstock.strategy.composites._fetch_live_quote")
    def test_run_composite_no_data(self, mock_quote, console_mock, mock_input):
        """無資料時應顯示警告。"""
        mock_quote.return_value = (None, None, None, None, None, None, None, None)
        mock_input.return_value = ""

        # 不應拋異常
        composites.run_composite("9999", mobile=False)


class TestFetchLiveQuote:
    """_fetch_live_quote 資料抓取。"""

    @patch("twstock.strategy.composites.safe_http_get")
    @patch("twstock.strategy.composites.get_http_session")
    def test_fetch_live_quote_returns_tuple(self, mock_session, mock_get):
        """應回傳 (price, volume) 或 (None, None)。"""
        mock_session.return_value = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {"msgArray": [{"c": "2330", "z": "100.00", "v": "1000"}]}
        mock_get.return_value = mock_response

        result = composites._fetch_live_quote("2330")
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert result[0] == 100.0
        assert result[1] == 1000000  # volume * 1000

    @patch("twstock.strategy.composites.get_http_session")
    def test_fetch_live_quote_no_session(self, mock_session):
        """無 session 時應回傳 (None, None)。"""
        mock_session.return_value = None
        result = composites._fetch_live_quote("2330")
        assert result == (None, None)
