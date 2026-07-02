# -*- coding: utf-8 -*-
"""test_official_trading_calendar.py — official/trading_calendar.py 覆蓋率測試。"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from twstock.official import trading_calendar


class TestDateToInt:
    """_date_to_int / _int_to_date 轉換。"""

    def test_date_to_int(self):
        """datetime → int 轉換。"""
        dt = datetime(2026, 7, 2)
        result = trading_calendar._date_to_int(dt)
        assert result == 20260702

    def test_int_to_date(self):
        """int → datetime 轉換。"""
        result = trading_calendar._int_to_date(20260702)
        assert result == datetime(2026, 7, 2)


class TestIsTradingDay:
    """is_trading_day 測試。"""

    @patch("twstock.official.trading_calendar.sqlite3.connect")
    def test_is_open(self, mock_connect):
        """开盘日应返回 True。"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1,)
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        assert trading_calendar.is_trading_day(20260702) is True
        mock_connect.assert_called_once()

    @patch("twstock.official.trading_calendar.sqlite3.connect")
    def test_not_open(self, mock_connect):
        """非开盘日应返回 False。"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (0,)
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        assert trading_calendar.is_trading_day(20260704) is False

    @patch("twstock.official.trading_calendar.sqlite3.connect")
    def test_no_record(self, mock_connect):
        """无记录应返回 False。"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        assert trading_calendar.is_trading_day(20200101) is False


class TestGetNthTradingDayBack:
    """get_nth_trading_day_back 测试。"""

    @patch("twstock.official.trading_calendar.get_last_trading_day")
    @patch("twstock.official.trading_calendar.is_trading_day")
    def test_n_zero(self, mock_is_open, mock_last):
        """n=0 应返回最近交易日。"""
        mock_last.return_value = 20260702
        mock_is_open.return_value = True

        result = trading_calendar.get_nth_trading_day_back(0)
        assert isinstance(result, datetime)

    @patch("twstock.official.trading_calendar.get_last_trading_day")
    @patch("twstock.official.trading_calendar.is_trading_day")
    def test_n_positive(self, mock_is_open, mock_last):
        """n>0 应往前找 N 个交易日。"""
        mock_last.return_value = 20260702
        mock_is_open.return_value = True

        result = trading_calendar.get_nth_trading_day_back(3)
        assert isinstance(result, datetime)


class TestDateExistsInHistory:
    """date_exists_in_history 测试。"""

    @patch("twstock.official.trading_calendar.sqlite3.connect")
    def test_sufficient_data(self, mock_connect):
        """TSE>500 且 OTC>500 应返回 True。"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (600, 550)
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        assert trading_calendar.date_exists_in_history(20260702) is True

    @patch("twstock.official.trading_calendar.sqlite3.connect")
    def test_insufficient_tse(self, mock_connect):
        """TSE 不足应返回 False。"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (400, 550)
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        assert trading_calendar.date_exists_in_history(20260702) is False

    @patch("twstock.official.trading_calendar.sqlite3.connect")
    def test_null_counts(self, mock_connect):
        """NULL 计数应返回 False。"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (None, None)
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        assert trading_calendar.date_exists_in_history(20260702) is False
