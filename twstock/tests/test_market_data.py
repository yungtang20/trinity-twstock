# -*- coding: utf-8 -*-
"""Unit tests for twstock/market_data/ — cache and fetcher logic."""

from __future__ import annotations

import sys
import time
from unittest.mock import MagicMock, patch

_DIR = "D:/twse"
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)

from twstock.market_data.cache import MarketCache  # noqa: E402


# ── MarketCache ─────────────────────────────────────────────
class TestMarketCache:
    def test_init(self):
        c = MarketCache()
        assert c._data is None
        assert c._last_fetch == 0.0
        assert c._is_fetching is False

    def test_invalidate(self):
        c = MarketCache()
        c._data = {"fake": True}
        c._last_fetch = time.time()
        c.invalidate()
        assert c._data is None
        assert c._last_fetch == 0.0

    def test_is_market_open(self):
        c = MarketCache()
        result = c._is_market_open()
        assert isinstance(result, bool)

    def test_get_triggers_fetch_when_empty(self):
        c = MarketCache()
        with patch("twstock.market_data.cache.fetch_market_indices") as mock_fetch:
            msg = MagicMock()
            mock_fetch.return_value = msg
            result = c.get()
            # First call may return None (async) or the mock result
            assert result is None or result is msg
            assert mock_fetch.called or c._is_fetching

    def test_get_uses_cache_when_fresh(self):
        c = MarketCache()
        cached = {"price": 100}
        c._data = cached
        c._last_fetch = time.time()
        with patch("twstock.market_data.cache.fetch_market_indices") as mock_fetch:
            result = c.get()
            assert result is cached
            assert not mock_fetch.called


# ── package import ──────────────────────────────────────────
class TestPackageImport:
    def test_cache_importable(self):
        from twstock.market_data import MarketCache as MC

        assert MC is MarketCache
