# -*- coding: utf-8 -*-
"""test_official_updater.py — official/updater.py 覆蓋率測試。

測試 updater 的資料轉換與分派邏輯（不需真實 API）。
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from twstock.official import updater


class TestUpsertDataframe:
    """upsert_dataframe 資料轉換測試。"""

    @patch("twstock.official.updater.PROCESSOR_AVAILABLE", True)
    @patch("twstock.official.updater.DataProcessor")
    def test_stock_history_basic(self, mock_proc):
        """stock_history 基本寫入。"""
        df = pd.DataFrame({
            "stock_id": ["2330"],
            "date": ["2026-07-02"],
            "open": [100], "high": [105], "low": [95],
            "close": [102], "volume": [1000],
        })
        updater.upsert_dataframe("stock_history", df)
        mock_proc.return_value.upsert_history.assert_called_once()

    @patch("twstock.official.updater.PROCESSOR_AVAILABLE", True)
    @patch("twstock.official.updater.DataProcessor")
    def test_stock_history_with_turnover(self, mock_proc):
        """stock_history 使用 turnover 替代 amount。"""
        df = pd.DataFrame({
            "stock_id": ["2330"],
            "date": ["2026-07-02"],
            "open": [100], "high": [105], "low": [95],
            "close": [102], "volume": [1000],
            "turnover": [1000000],
        })
        updater.upsert_dataframe("stock_history", df)
        mock_proc.return_value.upsert_history.assert_called_once()

    @patch("twstock.official.updater.PROCESSOR_AVAILABLE", True)
    @patch("twstock.official.updater.DataProcessor")
    def test_stock_history_code_rename(self, mock_proc):
        """stock_history 欄位 code → stock_id 重新命名。"""
        df = pd.DataFrame({
            "code": ["2330"],
            "date": ["2026-07-02"],
            "open": [100], "close": [102],
        })
        updater.upsert_dataframe("stock_history", df)

    @patch("twstock.official.updater.PROCESSOR_AVAILABLE", True)
    @patch("twstock.official.updater.DataProcessor")
    def test_stock_history_date_int(self, mock_proc):
        """stock_history date_int 轉換。"""
        df = pd.DataFrame({
            "stock_id": ["2330"],
            "date_int": [20260702],
            "open": [100], "close": [102],
        })
        updater.upsert_dataframe("stock_history", df)

    @patch("twstock.official.updater.PROCESSOR_AVAILABLE", True)
    @patch("twstock.official.updater.DataProcessor")
    def test_institutional_data(self, mock_proc):
        """institutional_data 計算 net 欄位。"""
        df = pd.DataFrame({
            "stock_id": ["2330"],
            "date": ["2026-07-02"],
            "foreign_buy": [8000],
            "foreign_sell": [5000],
            "trust_buy": [2000],
            "trust_sell": [1000],
            "dealer_buy": [1500],
            "dealer_sell": [1200],
        })
        updater.upsert_dataframe("institutional_data", df)
        mock_proc.return_value.upsert_institutional.assert_called_once()

    @patch("twstock.official.updater.PROCESSOR_AVAILABLE", True)
    @patch("twstock.official.updater.DataProcessor")
    def test_shareholding_unified(self, mock_proc):
        """shareholding_unified 寫入。"""
        df = pd.DataFrame({
            "stock_id": ["2330"],
            "date": ["2026-07-02"],
            "total_shares": [1000000],
            "whale_ratio": [0.8],
            "total_people": [50000],
            "whale_shares": [800000],
        })
        updater.upsert_dataframe("shareholding_unified", df)
        mock_proc.return_value.upsert_shareholding.assert_called_once()

    def test_unknown_table(self):
        """未知表名稱應返回。"""
        df = pd.DataFrame({"test": [1]})
        # 不應拋異常
        updater.upsert_dataframe("unknown_table", df)

    def test_empty_dataframe(self):
        """空 DataFrame 應返回。"""
        updater.upsert_dataframe("stock_history", pd.DataFrame())

    @patch("twstock.official.updater.PROCESSOR_AVAILABLE", False)
    def test_processor_unavailable(self):
        """processor 不可用時應返回。"""
        df = pd.DataFrame({
            "stock_id": ["2330"],
            "date": ["2026-07-02"],
            "open": [100], "close": [102],
        })
        updater.upsert_dataframe("stock_history", df)


class TestUpdateDividendEventsForDateRange:
    """update_dividend_events_for_date_range 測試。"""

    @patch("twstock.official.updater.upsert_dividend_events")
    @patch("twstock.official.updater.fetch_dividend_events")
    def test_with_events(self, mock_fetch, mock_upsert):
        """有事件時應寫入。"""
        mock_fetch.return_value = pd.DataFrame({
            "stock_id": ["2330"],
            "date": ["2026-07-02"],
        })
        updater.update_dividend_events_for_date_range("2026-01-01", "2026-07-02")
        mock_upsert.assert_called_once()

    @patch("twstock.official.updater.upsert_dividend_events")
    @patch("twstock.official.updater.fetch_dividend_events")
    def test_no_events(self, mock_fetch, mock_upsert):
        """無事件時應跳過。"""
        mock_fetch.return_value = pd.DataFrame()
        updater.update_dividend_events_for_date_range("2026-01-01", "2026-07-02")
        mock_upsert.assert_not_called()
