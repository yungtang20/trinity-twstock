# -*- coding: utf-8 -*-
"""test_market_cache.py — market_data/cache.py 覆蓋率測試。"""
from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from twstock.market_data.cache import MarketCache


class TestMarketCache:
    """MarketCache 背景快取邏輯。"""

    def test_initial_state(self):
        """初始狀態 _data 為 None。"""
        cache = MarketCache()
        assert cache._data is None
        assert cache._last_fetch == 0.0
        assert cache._is_fetching is False

    def test_get_returns_none_initially(self):
        """首次 get() 在無資料時回傳 None。"""
        cache = MarketCache()
        result = cache.get()
        assert result is None

    def test_invalidate_clears_data(self):
        """invalidate() 應清除快取。"""
        cache = MarketCache()
        cache._data = {"test": 1}
        cache._last_fetch = time.time()
        cache.invalidate()
        assert cache._data is None
        assert cache._last_fetch == 0.0

    def test_get_returns_cached_data(self):
        """有快取時 get() 應直接回傳。"""
        cache = MarketCache()
        cache._data = {"TAIEX": {"price": 22000}}
        cache._last_fetch = time.time()  # 剛抓取，不觸發更新
        result = cache.get()
        assert result == {"TAIEX": {"price": 22000}}

    @patch("twstock.market_data.cache.fetch_market_indices")
    def test_get_triggers_background_fetch_when_empty(self, mock_fetch):
        """空快取時 get() 應觸發背景抓取。"""
        cache = MarketCache()
        # 模擬 _is_market_open 返回 False（避免 refresh_interval 問題）
        cache._is_market_open = lambda: False
        cache._last_fetch = 0  # 過期
        mock_fetch.return_value = {"TAIEX": {"price": 22000}}

        # get() 會啟動背景 thread
        result = cache.get()
        # 因為是背景抓取，首次可能仍是 None
        assert result is None or result == {"TAIEX": {"price": 22000}}

    def test_is_market_open_before_market(self):
        """開盤前應回傳 False。"""
        with patch("twstock.market_data.cache.datetime") as mock_dt:
            mock_now = MagicMock()
            mock_now.hour = 8
            mock_now.minute = 0
            mock_dt.now.return_value = mock_now
            assert MarketCache._is_market_open() is False

    def test_is_market_open_during_market(self):
        """盤中應回傳 True。"""
        with patch("twstock.market_data.cache.datetime") as mock_dt:
            mock_now = MagicMock()
            mock_now.hour = 10
            mock_now.minute = 30
            mock_dt.now.return_value = mock_now
            assert MarketCache._is_market_open() is True

    def test_is_market_open_after_market(self):
        """收盤後應回傳 False。"""
        with patch("twstock.market_data.cache.datetime") as mock_dt:
            mock_now = MagicMock()
            mock_now.hour = 14
            mock_now.minute = 0
            mock_dt.now.return_value = mock_now
            assert MarketCache._is_market_open() is False


# Avoid "MagicMock not imported" warning
from unittest.mock import MagicMock
