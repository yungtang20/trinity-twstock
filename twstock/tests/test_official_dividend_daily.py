# -*- coding: utf-8 -*-
"""test_official_dividend_daily.py — official/dividend_daily.py 覆蓋率測試。"""
from __future__ import annotations

from unittest.mock import patch

import pandas as pd

from twstock.official import dividend_daily


class TestFetchCurrentYearDividends:
    """fetch_current_year_dividends 測試。"""

    @patch("twstock.official.dividend_daily.fetch_dividend_events")
    def test_returns_dataframe(self, mock_fetch):
        """應回傳 DataFrame。"""
        mock_fetch.return_value = pd.DataFrame({"test": [1, 2, 3]})
        result = dividend_daily.fetch_current_year_dividends()
        assert isinstance(result, pd.DataFrame)
        assert not result.empty

    @patch("twstock.official.dividend_daily.fetch_dividend_events")
    def test_error_returns_empty(self, mock_fetch):
        """錯誤時應回傳空 DataFrame。"""
        mock_fetch.side_effect = Exception("API error")
        result = dividend_daily.fetch_current_year_dividends()
        assert isinstance(result, pd.DataFrame)
        assert result.empty


class TestWriteDividendEvents:
    """write_dividend_events 測試。"""

    @patch("twstock.official.dividend_daily.upsert_dividend_events")
    def test_write_non_empty(self, mock_upsert):
        """有資料時應寫入。"""
        df = pd.DataFrame({"stock_id": ["2330"], "date": ["2026-07-02"]})
        count = dividend_daily.write_dividend_events(df)
        assert count == 1
        mock_upsert.assert_called_once()

    def test_write_empty(self):
        """空 DataFrame 應回傳 0。"""
        count = dividend_daily.write_dividend_events(pd.DataFrame())
        assert count == 0

    @patch("twstock.official.dividend_daily.upsert_dividend_events")
    def test_write_error(self, mock_upsert):
        """寫入錯誤應回傳 0。"""
        mock_upsert.side_effect = Exception("DB error")
        df = pd.DataFrame({"stock_id": ["2330"]})
        count = dividend_daily.write_dividend_events(df)
        assert count == 0


class TestRunDividendDaily:
    """run_dividend_daily 測試。"""

    @patch("twstock.official.dividend_daily.write_dividend_events")
    @patch("twstock.official.dividend_daily.fetch_current_year_dividends")
    def test_run_with_data(self, mock_fetch, mock_write):
        """有資料時應執行完整流程。"""
        mock_fetch.return_value = pd.DataFrame({"test": [1]})
        mock_write.return_value = 1

        # 不應拋異常
        dividend_daily.run_dividend_daily()

    @patch("twstock.official.dividend_daily.write_dividend_events")
    @patch("twstock.official.dividend_daily.fetch_current_year_dividends")
    def test_run_no_data(self, mock_fetch, mock_write):
        """無資料時應跳過寫入。"""
        mock_fetch.return_value = pd.DataFrame()

        dividend_daily.run_dividend_daily()

        mock_write.assert_not_called()
