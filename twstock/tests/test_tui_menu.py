# -*- coding: utf-8 -*-
"""test_tui_menu.py — tui/menu.py 覆蓋率測試。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from twstock.tui import menu


class TestRunDbMaintenance:
    """run_db_maintenance 執行 VACUUM。"""

    @patch("twstock.tui.menu.get_connection")
    @patch("twstock.tui.menu.input")
    def test_vacuum_success(self, mock_input, mock_conn):
        """成功 VACUUM 不應拋異常。"""
        mock_ctx = MagicMock()
        mock_conn.return_value.__enter__ = MagicMock(return_value=mock_ctx)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)
        mock_input.return_value = ""
        # 不應拋異常
        menu.run_db_maintenance()

    @patch("twstock.tui.menu.get_connection")
    @patch("twstock.tui.menu.input")
    def test_vacuum_error(self, mock_input, mock_conn):
        """VACUUM 失敗時應顯示錯誤而非崩潰。"""
        mock_conn.side_effect = Exception("DB locked")
        mock_input.return_value = ""
        # 不應拋異常
        menu.run_db_maintenance()


class TestGetInteractiveInput:
    """_get_interactive_input 委派至 input_helper。"""

    @patch("twstock.tui.menu.get_interactive_input")
    def test_delegates_to_input_helper(self, mock_ih):
        """應委派至 input_helper.get_interactive_input。"""
        mock_ih.return_value = "1"
        result = menu._get_interactive_input("prompt", "12345")
        mock_ih.assert_called_once_with(prompt="prompt", menu_keys="12345")
        assert result == "1"

    @patch("twstock.tui.menu.get_interactive_input")
    def test_esc_returns_empty(self, mock_ih):
        """ESC (回傳 '0') 應轉為空字串。"""
        mock_ih.return_value = "0"
        result = menu._get_interactive_input("prompt", "12345")
        assert result == ""


class TestCheckZeroVolumeAnomalies:
    """_check_zero_volume_anomalies 處理異常清單。"""

    @patch("twstock.tui.menu.get_connection")
    @patch("twstock.tui.menu.input")
    def test_no_anomalies(self, mock_input, mock_conn):
        """無異常時不應崩潰。"""
        mock_ctx = MagicMock()
        mock_ctx.execute.return_value.fetchall.return_value = []
        mock_conn.return_value.__enter__ = MagicMock(return_value=mock_ctx)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)
        mock_input.return_value = ""
        menu._check_zero_volume_anomalies(suspended=set())

    @patch("twstock.tui.menu.get_connection")
    @patch("twstock.tui.menu.input")
    def test_with_anomalies(self, mock_input, mock_conn):
        """有異常時應顯示。"""
        mock_ctx = MagicMock()
        mock_ctx.execute.return_value.fetchall.return_value = [
            ("2330", 0.0),
            ("2331", 0.0),
            ("2332", 0.0),
        ]
        mock_conn.return_value.__enter__ = MagicMock(return_value=mock_ctx)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)
        mock_input.return_value = ""
        menu._check_zero_volume_anomalies(suspended={"2330"})


class TestRunDailyUpdate:
    @patch("twstock.tui.menu.input", return_value="")
    @patch("twstock.tui.menu.update_official_daily")
    @patch("twstock.tui.menu.get_today_suspended", return_value=set())
    def test_success(self, mock_sus, mock_update, mock_input):
        menu.run_daily_update()
        mock_update.assert_called_once_with(days=1, auto_tdcc=True)

    @patch("twstock.tui.menu.input", return_value="")
    @patch("twstock.tui.menu.update_official_daily")
    @patch("twstock.tui.menu.get_today_suspended", side_effect=Exception("boom"))
    def test_suspended_error(self, mock_sus, mock_update, mock_input):
        menu.run_daily_update()
        mock_update.assert_called_once()


class TestHistoricalMenuBranches:
    def _ch(self, ch):
        return patch("twstock.tui.menu._get_interactive_input", side_effect=[ch, ""])

    @patch("twstock.tui.menu.update_official_daily")
    def test_sync_days(self, mock_update):
        with self._ch("1"), patch("twstock.tui.menu.input", return_value="5"):
            menu.run_historical_update_menu()
        mock_update.assert_called_once_with(None, days=5, auto_tdcc=True)

    @patch("twstock.tui.menu.update_official_daily")
    def test_sync_days_nondigit(self, mock_update):
        with self._ch("1"), patch("twstock.tui.menu.input", return_value="abc"):
            menu.run_historical_update_menu()
        mock_update.assert_not_called()

    @patch("twstock.tui.menu.update_tdcc_historical")
    def test_sync_tdcc(self, mock_tdcc):
        with self._ch("2"), patch("twstock.tui.menu.input", return_value="3"):
            menu.run_historical_update_menu()
        mock_tdcc.assert_called_once_with(3)

    @patch("twstock.tui.menu.upsert_dividend_events")
    @patch("twstock.tui.menu.fetch_dividend_events")
    @patch("twstock.tui.menu.get_nth_trading_day_back")
    def test_dividend_range_with_data(self, mock_day, mock_fetch, mock_upsert):
        import datetime as _dt

        mock_day.return_value = _dt.datetime(2024, 1, 1)
        import pandas as pd

        mock_fetch.return_value = pd.DataFrame({"stock_id": ["2330"]})
        with self._ch("3"), patch("twstock.tui.menu.input", return_value="60"):
            menu.run_historical_update_menu()
        mock_upsert.assert_called_once()

    @patch("twstock.tui.menu.fetch_dividend_events")
    @patch("twstock.tui.menu.get_nth_trading_day_back")
    def test_dividend_range_empty(self, mock_day, mock_fetch):
        import pandas as pd

        mock_fetch.return_value = pd.DataFrame()
        with self._ch("3"), patch("twstock.tui.menu.input", return_value="60"):
            menu.run_historical_update_menu()

    @patch("twstock.tui.menu.run_dividend_daily")
    @patch("twstock.tui.menu.input", return_value="")
    def test_dividend_year(self, mock_input, mock_run):
        with self._ch("4"):
            menu.run_historical_update_menu()
        mock_run.assert_called_once()

    @patch("twstock.tui.menu._check_zero_volume_anomalies")
    @patch("twstock.tui.menu.get_today_suspended", return_value=set())
    @patch("twstock.tui.menu.input", return_value="")
    def test_anomalies(self, mock_input, mock_sus, mock_check):
        with self._ch("5"):
            menu.run_historical_update_menu()
        mock_check.assert_called_once()

    def test_unknown_key_no_crash(self):
        with self._ch("9"):
            menu.run_historical_update_menu()
