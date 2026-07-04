# -*- coding: utf-8 -*-
"""test_fetcher.py — fetcher.py 覆蓋率測試。"""

from __future__ import annotations

from twstock.fetcher import (
    FinMindClient,
    FinMindFetcher,
    TWSEFetcher,
    _RateLimiter,
)


class TestRateLimiter:
    """_RateLimiter 速率限制器。"""

    def test_acquire_within_limit(self):
        """限制內應立即回傳。"""
        limiter = _RateLimiter(max_calls=10, window=60)
        # 第一次呼叫不應阻塞
        limiter.acquire()

    def test_acquire_at_limit(self):
        """達限制時應等待。"""
        limiter = _RateLimiter(max_calls=1, window=0.1)
        limiter.acquire()
        # 第二次應進入等待（但測試中快速完成）
        import time

        time.sleep(0.15)  # 等待窗口過期
        limiter.acquire()  # 現在應該可以


class TestFinMindClient:
    """FinMindClient API 客戶端。"""

    def test_init(self):
        """建構子應初始化。"""
        client = FinMindClient(token="test_token")
        assert client.token == "test_token"


class TestFinMindFetcher:
    """FinMindFetcher 策略API抓取。"""

    def test_init(self):
        """建構子應初始化（需要 db 參數）。"""
        fetcher = FinMindFetcher(api_token="test_token", db=":memory:")
        assert fetcher is not None


class TestTWSEFetcher:
    """TWSEFetcher 證交所抓取。"""

    def test_init(self):
        """建構子應初始化（需要 db 參數）。"""
        fetcher = TWSEFetcher(db=":memory:")
        assert fetcher is not None
