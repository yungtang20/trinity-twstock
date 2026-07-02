# -*- coding: utf-8 -*-
"""市場指數快取（背景 thread + TTL）。"""
from __future__ import annotations

import threading
import time
from datetime import datetime
from typing import Any, Dict, Optional

from .fetcher import fetch_market_indices


class MarketCache:
    """封裝即時市場指數的背景快取邏輯。

    Usage:
        cache = MarketCache()
        data = cache.get()  # 回傳快取或 None（首次背景觸發）
    """

    def __init__(self):
        self._data: Optional[Dict[str, Any]] = None
        self._last_fetch: float = 0.0
        self._is_fetching: bool = False

    # ── public ─────────────────────────────────────────────
    def get(self) -> Optional[Dict[str, Any]]:
        """回傳目前快取；若過期則在背景觸發更新。"""
        now = time.time()
        is_market_open = self._is_market_open()
        refresh_interval = 15 if is_market_open else 3600

        if (self._data is None or now - self._last_fetch > refresh_interval) and not self._is_fetching:
            self._is_fetching = True
            threading.Thread(target=self._async_fetch_worker, daemon=True).start()

        return self._data

    def invalidate(self) -> None:
        """清除快取（下次 get() 會重新抓取）。"""
        self._data = None
        self._last_fetch = 0.0

    # ── internal ──────────────────────────────────────────
    @staticmethod
    def _is_market_open() -> bool:
        now = datetime.now()
        mins = now.hour * 60 + now.minute
        return 9 * 60 <= mins <= 13 * 60 + 35

    def _async_fetch_worker(self) -> None:
        try:
            data = fetch_market_indices()
            if data:
                self._data = data
                self._last_fetch = time.time()
        finally:
            self._is_fetching = False
