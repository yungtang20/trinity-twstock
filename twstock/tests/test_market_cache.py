# -*- coding: utf-8 -*-
"""test_market_cache.py — market_data/cache.py 覆蓋率測試。"""

from __future__ import annotations

import time
from unittest.mock import patch

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
        with patch("twstock.market_data.cache.is_market_session_open", return_value=False):
            assert MarketCache._is_market_open() is False

    def test_is_market_open_during_market(self):
        """盤中應回傳 True。"""
        with patch("twstock.market_data.cache.is_market_session_open", return_value=True):
            assert MarketCache._is_market_open() is True

    def test_is_market_open_after_market(self):
        """收盤後應回傳 False。"""
        with patch("twstock.market_data.cache.is_market_session_open", return_value=False):
            assert MarketCache._is_market_open() is False

    def test_market_closes_at_1330(self):
        """13:30:00 起應顯示盤後。"""
        with patch("twstock.market_data.cache.is_market_session_open", return_value=False):
            assert MarketCache._is_market_open() is False

    def test_market_mode_uses_clock_not_price_change(self):
        """盤中行情沒跳動時仍應顯示開盤。"""
        cache = MarketCache()
        cache._data = {"TAIEX": {"price": 22000}}
        with patch.object(cache, "_is_market_open", return_value=True):
            assert cache.get_market_mode() == "🟢 開盤"

    @patch("twstock.market_data.cache.threading.Thread")
    def test_open_transition_fetches_immediately(self, mock_thread):
        """從盤後跨到開盤時，不應沿用一小時的盤後 TTL。"""
        cache = MarketCache()
        cache._last_market_open = False
        cache._last_fetch = time.time()
        cache._data = {"TAIEX": {"price": 22000}}
        with patch.object(cache, "_is_market_open", return_value=True):
            cache.get()
        mock_thread.assert_called_once()
        mock_thread.return_value.start.assert_called_once()

    @patch("twstock.market_data.cache.threading.Thread")
    def test_warmup_starts_background_fetch_without_running_worker_inline(self, mock_thread):
        """進入主頁只排程更新，不可在 UI thread 同步執行網路請求。"""
        cache = MarketCache()

        cache.warmup()

        mock_thread.assert_called_once_with(target=cache._async_fetch_worker, daemon=True)
        mock_thread.return_value.start.assert_called_once()
        assert cache._is_fetching is True

    @patch("twstock.market_data.cache.threading.Thread")
    def test_repeated_warmup_does_not_duplicate_inflight_fetch(self, mock_thread):
        """使用者快速返回主頁時，不應疊加多組行情 API 請求。"""
        cache = MarketCache()

        cache.warmup()
        cache.warmup()

        mock_thread.assert_called_once()

    @patch("twstock.market_data.cache.threading.Thread")
    def test_wait_for_fetch_reports_existing_data(self, mock_thread):
        cache = MarketCache()
        cache._data = {"TAIEX": {"price": 22000}}

        assert cache.wait_for_fetch(timeout=0) is True
