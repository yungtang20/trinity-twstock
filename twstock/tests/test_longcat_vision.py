# -*- coding: utf-8 -*-
"""test_longcat_vision.py — longcat_vision.py 覆蓋率測試。"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd

from twstock.longcat_vision import _build_kline_summary, _get_api_key, analyze_kline_with_longcat


class TestGetApiKey:
    """_get_api_key API 金鑰取得。"""

    @patch("twstock.longcat_vision.get_longcat_api_key")
    @patch("twstock.longcat_vision._ensure_loaded")
    def test_returns_key(self, mock_ensure, mock_get_key):
        """應回傳 API key。"""
        mock_get_key.return_value = "test_key"
        result = _get_api_key()
        assert result == "test_key"
        mock_ensure.assert_called_once()

    @patch("twstock.longcat_vision.get_longcat_api_key")
    @patch("twstock.longcat_vision._ensure_loaded")
    def test_returns_none_when_no_key(self, mock_ensure, mock_get_key):
        """無 key 時應回傳 None。"""
        mock_get_key.return_value = None
        result = _get_api_key()
        assert result is None


class TestBuildKlineSummary:
    """_build_kline_summary K 線摘要。"""

    def test_empty_df(self):
        """空 DataFrame 應回傳空字串。"""
        result = _build_kline_summary(pd.DataFrame(), "2330", "台積電")
        assert result == ""

    def test_none_df(self):
        """None 應回傳空字串。"""
        result = _build_kline_summary(None, "2330", "台積電")
        assert result == ""

    def test_with_data(self):
        """有資料應產生摘要。"""
        df = pd.DataFrame({
            "date": pd.date_range("2026-01-01", periods=5),
            "open": [100, 101, 102, 103, 104],
            "high": [105, 106, 107, 108, 109],
            "low": [95, 96, 97, 98, 99],
            "close": [102, 103, 104, 105, 106],
            "volume": [1000000, 2000000, 1500000, 1800000, 2200000],
        })
        result = _build_kline_summary(df, "2330", "台積電")
        assert "2330" in result
        assert "台積電" in result
        assert "張" in result

    def test_without_stock_name(self):
        """無股票名稱仍應運作。"""
        df = pd.DataFrame({
            "date": pd.date_range("2026-01-01", periods=3),
            "open": [100, 101, 102],
            "high": [105, 106, 107],
            "low": [95, 96, 97],
            "close": [102, 103, 104],
            "volume": [1000000, 2000000, 1500000],
        })
        result = _build_kline_summary(df, "2330", "")
        assert "2330" in result


class TestAnalyzeKlineWithLongcat:
    """analyze_kline_with_longcat AI 分析。"""

    @patch("twstock.longcat_vision.get_longcat_api_key")
    @patch("twstock.longcat_vision._ensure_loaded")
    def test_no_api_key_returns_none(self, mock_ensure, mock_key):
        """無 API key 應回傳 None。"""
        mock_key.return_value = None
        df = pd.DataFrame({"close": [100, 101]})
        result = analyze_kline_with_longcat(df, "2330", "台積電")
        assert result is None

    @patch("twstock.longcat_vision.get_longcat_model")
    @patch("twstock.longcat_vision.get_longcat_api_url")
    @patch("twstock.longcat_vision.get_longcat_api_key")
    @patch("twstock.longcat_vision._ensure_loaded")
    def test_with_api_key(self, mock_loaded, mock_key, mock_url, mock_model):
        """有 API key 應呼叫 API（mock requests）。"""
        mock_key.return_value = "test_key"
        mock_url.return_value = "https://api.example.com"
        mock_model.return_value = "longcat-2.0"

        import requests
        with patch.object(requests, "post") as mock_post:
            mock_response = MagicMock()
            mock_response.raise_for_status.return_value = None
            mock_response.json.return_value = {
                "choices": [{"message": {"content": "看多"}}]
            }
            mock_post.return_value = mock_response

            df = pd.DataFrame({
                "date": pd.date_range("2026-01-01", periods=5),
                "open": [100, 101, 102, 103, 104],
                "high": [105, 106, 107, 108, 109],
                "low": [95, 96, 97, 98, 99],
                "close": [102, 103, 104, 105, 106],
                "volume": [1000000] * 5,
            })
            result = analyze_kline_with_longcat(df, "2330", "台積電")
            # 不應拋異常
            assert result is None or isinstance(result, str)
