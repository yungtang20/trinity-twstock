# -*- coding: utf-8 -*-
"""test_commands_official.py — commands/official.py 覆蓋率測試。"""
from __future__ import annotations

from argparse import Namespace
from unittest.mock import MagicMock, patch

import pytest

from twstock.commands import official


class TestOfficialExecute:
    """official.execute 分派邏輯測試。"""

    @patch("twstock.commands.official.update_official_daily")
    @patch("twstock.commands.official.update_tdcc_weekly")
    def test_tdcc_only_mode(self, mock_weekly, mock_daily):
        """tdcc_only=True 應只呼叫 update_tdcc_weekly。"""
        args = Namespace(tdcc_only=True)
        official.execute(args)
        mock_weekly.assert_called_once()
        mock_daily.assert_not_called()

    @patch("twstock.commands.official.update_official_daily")
    @patch("twstock.commands.official.update_tdcc_historical")
    def test_tdcc_weeks(self, mock_historical, mock_daily):
        """tdcc_weeks 參數應呼叫 update_tdcc_historical。"""
        args = Namespace(tdcc_only=False, tdcc_weeks=4, days=1, date=None, with_tdcc=False)
        official.execute(args)
        mock_historical.assert_called_once_with(4)
        mock_daily.assert_not_called()

    @patch("twstock.commands.official.update_official_daily")
    def test_with_date(self, mock_daily):
        """有 date 參數應解析並傳入 update_official_daily。"""
        args = Namespace(tdcc_only=False, tdcc_weeks=None, days=1, date="2026-07-02", with_tdcc=True)
        official.execute(args)
        mock_daily.assert_called_once()
        call_kwargs = mock_daily.call_args
        # 第一個位置參數是 date_int
        assert call_kwargs[0][0] == 20260702 or call_kwargs[1].get("date_int") == 20260702

    @patch("twstock.commands.official.update_official_daily")
    def test_without_date(self, mock_daily):
        """無 date 參數應傳入 None。"""
        args = Namespace(tdcc_only=False, tdcc_weeks=None, days=5, date=None, with_tdcc=False)
        official.execute(args)
        mock_daily.assert_called_once_with(None, days=5, auto_tdcc=False)

    @patch("twstock.commands.official.update_official_daily")
    def test_invalid_date_format(self, mock_daily):
        """無效日期格式應顯示錯誤而非崩潰。"""
        args = Namespace(tdcc_only=False, tdcc_weeks=None, days=1, date="invalid", with_tdcc=False)
        # 不應拋異常
        official.execute(args)
        mock_daily.assert_not_called()
