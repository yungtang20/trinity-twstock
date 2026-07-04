# -*- coding: utf-8 -*-
"""test_official_trading_calendar.py — official/trading_calendar.py 覆蓋率測試。"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

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


class TestInitTradingCalendar:
    """init_trading_calendar 初始化測試。"""

    @patch("twstock.official.trading_calendar.sqlite3.connect")
    @patch("twstock.official.trading_calendar.retry_get")
    def test_init_with_holidays(self, mock_retry, mock_connect):
        """有官方日曆資料時應寫入 DB。"""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"Date": "1130101", "Description": "元旦"},
            {"Date": "1130205", "Description": "春節"},
        ]
        mock_retry.return_value = mock_response

        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        # 不應拋異常
        trading_calendar.init_trading_calendar()

    @patch("twstock.official.trading_calendar.retry_get")
    def test_init_no_response(self, mock_retry):
        """無回應時應返回。"""
        mock_retry.return_value = None

        # 不應拋異常
        trading_calendar.init_trading_calendar()

    @patch("twstock.official.trading_calendar.retry_get")
    def test_init_empty_holidays(self, mock_retry):
        """空日曆資料時應返回。"""
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_retry.return_value = mock_response

        trading_calendar.init_trading_calendar()

    @patch("twstock.official.trading_calendar.retry_get")
    def test_init_error(self, mock_retry):
        """錯誤時不應拋異常。"""
        mock_retry.side_effect = Exception("Network error")

        # 不應拋異常
        trading_calendar.init_trading_calendar()


class TestGetLastTradingDay:
    """get_last_trading_day 測試。"""

    @patch("twstock.official.trading_calendar.init_trading_calendar")
    @patch("twstock.official.trading_calendar.sqlite3.connect")
    @patch("twstock.official.trading_calendar.is_trading_day")
    def test_empty_calendar_initializes(self, mock_is_open, mock_connect, mock_init):
        """空日曆應觸發初始化。"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (0,)  # COUNT = 0
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        mock_is_open.return_value = True

        result = trading_calendar.get_last_trading_day()
        mock_init.assert_called_once()

    @patch("twstock.official.trading_calendar.is_trading_day")
    def test_finds_trading_day(self, mock_is_open):
        """應找到最近交易日。"""
        mock_is_open.return_value = True

        result = trading_calendar.get_last_trading_day()
        assert isinstance(result, int)
        assert result > 0


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
