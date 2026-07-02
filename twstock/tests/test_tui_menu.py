# -*- coding: utf-8 -*-
"""test_tui_menu.py — tui/menu.py 覆蓋率測試。"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

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
            {"stock_id": "2330", "stock_name": "台積電", "close": 0, "volume": 0}
        ]
        mock_conn.return_value.__enter__ = MagicMock(return_value=mock_ctx)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)
        mock_input.return_value = ""
        menu._check_zero_volume_anomalies(suspended={"2330"})
