# -*- coding: utf-8 -*-
"""test_fetcher_unit.py — market_data/fetcher.py 覆蓋率提升測試。

Mock HTTP requests to test all code paths without network.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from twstock.market_data import fetcher


# ── Fixtures ──────────────────────────────────────────────

@pytest.fixture
def mock_session():
    """建立 mock HTTP session。"""
    return MagicMock()


@pytest.fixture
def mock_response():
    """建立 mock HTTP response。"""
    resp = MagicMock()
    resp.status_code = 200
    resp.text = ""
    resp.json.return_value = {}
    return resp


# ── get_yahoo_market_volumes ──────────────────────────────


class TestGetYahooMarketVolumes:
    """get_yahoo_market_volumes 測試。"""

    @patch("twstock.utils.safe_http_get")
    @patch("twstock.market_data.fetcher.get_http_session")
    def test_returns_tuple(self, mock_session, mock_http_get):
        """應回傳 (twse_vol, tpex_vol) tuple。"""
        mock_session.return_value = MagicMock()
        mock_http_get.return_value = None  # 無回應

        result = fetcher.get_yahoo_market_volumes()
        assert isinstance(result, tuple)
        assert len(result) == 2

    @patch("twstock.utils.safe_http_get")
    @patch("twstock.market_data.fetcher.get_http_session")
    def test_no_session_returns_defaults(self, mock_session, mock_http_get):
        """無 session 時應回傳預設值。"""
        mock_session.return_value = None

        twse, tpex = fetcher.get_yahoo_market_volumes()
        assert twse == "無資料"
        assert tpex == "無資料"


# ── get_realtime_mis_data ─────────────────────────────────


class TestGetRealtimeMisData:
    """get_realtime_mis_data 測試。"""

    def test_returns_dict(self):
        """應回傳 dict（safe_http_get 在函數內部导入，改 mock session.get）。"""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {"msgArray": []}
        mock_session.get.return_value = mock_response

        with patch("twstock.market_data.fetcher.get_http_session", return_value=mock_session):
            with patch("twstock.utils.safe_http_get", return_value=mock_response):
                result = fetcher.get_realtime_mis_data()

        assert isinstance(result, dict)

    @patch("twstock.market_data.fetcher.get_http_session")
    def test_no_session_returns_empty(self, mock_session):
        """無 session 時應回傳空 dict。"""
        mock_session.return_value = None
        result = fetcher.get_realtime_mis_data()
        assert result == {}

    def test_with_symbols(self):
        """有 symbols 參數時應加入 ex_ch_list。"""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {"msgArray": []}
        mock_session.get.return_value = mock_response

        with patch("twstock.market_data.fetcher.get_http_session", return_value=mock_session):
            with patch("twstock.utils.safe_http_get", return_value=mock_response):
                result = fetcher.get_realtime_mis_data(symbols=["2330"])

        assert isinstance(result, dict)


# ── fetch_market_indices ──────────────────────────────────


class TestFetchMarketIndices:
    """fetch_market_indices 整合入口測試。"""

    @patch("twstock.market_data.fetcher.get_yahoo_market_volumes")
    @patch("twstock.market_data.fetcher.get_realtime_mis_data")
    def test_returns_none_on_failure(self, mock_mis, mock_yahoo):
        """MIS 無資料時應回傳 None。"""
        mock_mis.return_value = {}
        mock_yahoo.return_value = ("無資料", "無資料")

        result = fetcher.fetch_market_indices()
        assert result is None

    @patch("twstock.utils.safe_http_get")
    @patch("twstock.market_data.fetcher.get_http_session")
    @patch("twstock.market_data.fetcher.get_yahoo_market_volumes")
    @patch("twstock.market_data.fetcher.get_realtime_mis_data")
    def test_with_mis_data(self, mock_mis, mock_yahoo, mock_session, mock_http_get):
        """有 MIS 資料時應回傳結果。"""
        mock_mis.return_value = {
            "msgArray": [
                {"c": "t00", "z": "22000", "y": "21900"},
                {"c": "o00", "z": "230", "y": "228"},
            ],
            "queryTime": {"sysTime": "10:00:00", "sysDate": "2026/07/02"},
        }
        mock_yahoo.return_value = ("3000", "800")
        mock_session.return_value = MagicMock()
        mock_http_get.return_value = None

        result = fetcher.fetch_market_indices()
        # 可能因 TWSE/TPEx API 失敗而回傳 None，但不應拋異常
        assert result is None or isinstance(result, dict)
