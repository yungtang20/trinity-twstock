# -*- coding: utf-8 -*-
"""市場指數快取（背景 thread + TTL + timeout）。"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import Any, Dict, Optional

from .fetcher import fetch_market_indices

logger = logging.getLogger(__name__)

# 整體抓取逾時（秒）：避免單一請求卡住導致 TUI 永久顯示「正在獲取即時數據...」
_FETCH_TIMEOUT = 10.0


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
        self._last_error: Optional[str] = None  # 最後一次抓取錯誤訊息

    # ── public ─────────────────────────────────────────────
    def get(self) -> Optional[Dict[str, Any]]:
        """回傳快取；首次或過期時在背景觸發更新。

        關鍵：失敗後 _last_fetch 會被更新，不會在每次 TUI render 都重試，
        而是等到 refresh_interval（盤中 15s / 盤後 3600s）後才重試。
        """
        now = time.time()
        is_market_open = self._is_market_open()
        refresh_interval = 15 if is_market_open else 3600

        never_attempted = self._last_fetch == 0.0
        data_expired = now - self._last_fetch > refresh_interval

        if (never_attempted or data_expired) and not self._is_fetching:
            self._is_fetching = True
            self._last_error = None
            threading.Thread(target=self._async_fetch_worker, daemon=True).start()

        return self._data

    def get_status(self) -> Dict[str, Any]:
        """回傳快取狀態（供 TUI 顯示）。"""
        return {
            "is_fetching": self._is_fetching,
            "last_error": self._last_error,
            "has_data": self._data is not None,
        }

    def invalidate(self) -> None:
        """清除快取（下次 get() 會重新抓取）。"""
        self._data = None
        self._last_fetch = 0.0
        self._last_error = None

    # ── internal ──────────────────────────────────────────
    @staticmethod
    def _is_market_open() -> bool:
        now = datetime.now()
        mins = now.hour * 60 + now.minute
        return 9 * 60 <= mins <= 13 * 60 + 35

    def _async_fetch_worker(self) -> None:
        """背景抓取，帶整體逾時。"""
        result: Dict[str, Any] = {}
        error_holder: list[str] = []

        def _target():
            try:
                data = fetch_market_indices()
                if data:
                    result.update(data)
                else:
                    error_holder.append("fetch_market_indices 回傳 None")
            except Exception as e:
                error_holder.append(str(e))

        t = threading.Thread(target=_target, daemon=True)
        t.start()
        t.join(timeout=_FETCH_TIMEOUT)

        if t.is_alive():
            # 逾時：thread 仍在跑，但我們不再等待
            self._last_error = f"抓取逾時（>{_FETCH_TIMEOUT:.0f}s）"
            logger.warning("MarketCache: %s", self._last_error)
        elif result:
            self._data = result
            self._last_error = None
        else:
            # 抓取失敗但非逾時
            self._last_error = error_holder[0] if error_holder else "無法取得即時數據"
            logger.warning("MarketCache: %s", self._last_error)

        # 無論成功失敗，都更新 _last_fetch 以防止 TUI 每次 render 都重試
        # 盤中 15 秒後允许重試，盤後 1 小時後允許重試
        self._last_fetch = time.time()
        self._is_fetching = False
