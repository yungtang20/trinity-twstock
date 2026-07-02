# -*- coding: utf-8 -*-
"""test_official_suspended.py — official/suspended.py 覆蓋率測試。"""
from __future__ import annotations

from twstock.official.suspended import get_today_suspended


class TestGetTodaySuspended:
    """get_today_suspended 處置股票查詢。"""

    def test_returns_empty_list(self):
        """應回傳空列表（stub）。"""
        result = get_today_suspended()
        assert result == []

    def test_returns_list(self):
        """應回傳 list 類型。"""
        result = get_today_suspended()
        assert isinstance(result, list)
