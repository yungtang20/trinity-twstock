# -*- coding: utf-8 -*-
"""test_tui_menu.py — tui/menu.py 覆蓋率測試。

A + ① 組合：所有進入改 blocking_input，_get_interactive_input 已移除。
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

from twstock.db_maintenance import DatabaseHealthReport
from twstock.tui import menu


class TestRunDbMaintenance:
    """run_db_maintenance defaults to read-only health reporting."""

    @staticmethod
    def _report(*, vacuum_recommended: bool = False) -> DatabaseHealthReport:
        reclaimable = 120 * 1024 * 1024 if vacuum_recommended else 1024
        ratio = 0.06 if vacuum_recommended else 0.001
        return DatabaseHealthReport(
            database_path=Path("test.db"),
            file_size_bytes=1024 * 1024,
            wal_size_bytes=0,
            page_size=4096,
            page_count=256,
            freelist_count=1,
            reclaimable_bytes=reclaimable,
            reclaimable_ratio=ratio,
            quick_check="ok",
            quality_counts={"invalid_history": 0},
        )

    @patch("twstock.tui.menu.build_database_health_report")
    @patch("twstock.tui.menu.blocking_input")
    def test_read_only_health_success(self, mock_input, mock_health):
        mock_health.return_value = self._report()
        mock_input.return_value = ""
        menu.run_db_maintenance()
        mock_health.assert_called_once()

    @patch("twstock.tui.menu.run_database_optimize")
    @patch("twstock.tui.menu.build_database_health_report")
    @patch("twstock.tui.menu.blocking_input")
    def test_optimize_requires_enter_choice(self, mock_input, mock_health, mock_optimize):
        mock_health.return_value = self._report()
        mock_input.side_effect = ["1", ""]
        menu.run_db_maintenance()
        mock_optimize.assert_called_once()

    @patch("twstock.tui.menu.build_database_health_report", side_effect=Exception("DB locked"))
    @patch("twstock.tui.menu.blocking_input", return_value="")
    def test_health_error(self, mock_input, mock_health):
        menu.run_db_maintenance()


class TestRunDailyUpdate:
    @patch("twstock.tui.menu.blocking_input", return_value="")
    @patch("twstock.tui.menu.update_official_daily")
    @patch("twstock.tui.menu.get_today_suspended", return_value=set())
    def test_success(self, mock_sus, mock_update, mock_input):
        menu.run_daily_update()
        mock_update.assert_called_once_with(days=1, auto_tdcc=True)

    @patch("twstock.tui.menu.blocking_input", return_value="")
    @patch("twstock.tui.menu.update_official_daily")
    @patch("twstock.tui.menu.get_today_suspended", side_effect=Exception("boom"))
    def test_suspended_error(self, mock_sus, mock_update, mock_input):
        menu.run_daily_update()
        mock_update.assert_called_once()


class TestCheckZeroVolumeAnomalies:
    """_check_zero_volume_anomalies 處理異常清單。"""

    @patch("twstock.tui.menu.get_connection")
    def test_no_anomalies(self, mock_conn):
        """無異常時不應崩潰。"""
        latest_result = MagicMock()
        latest_result.fetchone.return_value = ("2026-07-21",)
        rows_result = MagicMock()
        rows_result.fetchall.return_value = []
        connection = MagicMock()
        connection.execute.side_effect = [latest_result, rows_result]
        mock_conn.return_value = connection
        menu._check_zero_volume_anomalies(suspended=set())

    @patch("twstock.tui.menu.get_connection")
    def test_with_anomalies(self, mock_conn):
        """有異常時應顯示。"""
        latest_result = MagicMock()
        latest_result.fetchone.return_value = ("2026-07-21",)
        rows_result = MagicMock()
        rows_result.fetchall.return_value = [
            ("2330", 0.0, 0.0, 0.0, 0.0, 0),
            ("2331", 0.0, 0.0, 0.0, 0.0, 0),
            ("2332", 0.0, 0.0, 0.0, 0.0, 0),
        ]
        connection = MagicMock()
        connection.execute.side_effect = [latest_result, rows_result]
        mock_conn.return_value = connection
        menu._check_zero_volume_anomalies(suspended={"2330"})


class TestHistoricalMenuBranches:
    """run_historical_update_menu 各分支。"""

    def _inputs(self, *values):
        """Mock complete lines; every value represents one Enter press."""
        return patch("twstock.tui.menu.blocking_input", side_effect=values)

    @patch("twstock.tui.menu.update_official_daily")
    def test_sync_days(self, mock_update):
        with self._inputs("1", "5", "", ""):
            menu.run_historical_update_menu()
        mock_update.assert_called_once_with(None, days=5, auto_tdcc=False)

    @patch("twstock.tui.menu.update_official_daily")
    def test_sync_days_nondigit(self, mock_update):
        with self._inputs("1", "abc", "", ""):
            menu.run_historical_update_menu()
        mock_update.assert_not_called()

    @patch("twstock.tui.menu.update_tdcc_historical")
    def test_sync_tdcc(self, mock_tdcc):
        with self._inputs("3", "", ""):
            menu.run_historical_update_menu()
        mock_tdcc.assert_called_once_with(1)

    @patch("twstock.tui.menu._count_trading_days", return_value=3)
    @patch("twstock.tui.menu.update_official_daily")
    def test_force_date_range(self, mock_update, mock_count):
        with self._inputs("2", "2026-07-01", "2026-07-03", "", ""):
            menu.run_historical_update_menu()
        mock_update.assert_called_once_with(
            20260703, days=3, force=True, auto_tdcc=False
        )

    @patch("twstock.tui.menu.upsert_dividend_events")
    @patch("twstock.tui.menu.fetch_dividend_events")
    def test_dividend_range_with_data(self, mock_fetch, mock_upsert):
        mock_fetch.return_value = pd.DataFrame({"stock_id": ["2330"]})
        with self._inputs("4", "2026-01-01", "2026-12-31", "", ""):
            menu.run_historical_update_menu()
        mock_upsert.assert_called_once()

    @patch("twstock.tui.menu.fetch_dividend_events")
    def test_dividend_range_empty(self, mock_fetch):
        mock_fetch.return_value = pd.DataFrame()
        with self._inputs("4", "2026-01-01", "2026-12-31", "", ""):
            menu.run_historical_update_menu()

    @patch("twstock.tui.menu._render_historical_quality_report")
    def test_quality_report(self, mock_report):
        with self._inputs("5", "", ""):
            menu.run_historical_update_menu()
        mock_report.assert_called_once()

    def test_unknown_key_no_crash(self):
        with self._inputs("9", ""):
            menu.run_historical_update_menu()
