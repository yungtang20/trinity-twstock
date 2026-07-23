# -*- coding: utf-8 -*-
"""市場指數快取（背景 thread + TTL + timeout）。"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import Any, Dict, Optional

from twstock.utils import is_market_open as is_market_session_open

from .fetcher import fetch_market_indices

logger = logging.getLogger(__name__)

# 整體抓取逾時（秒）。公開端點依序有多個短 timeout；實測完整成功回應
# 可能超過 10 秒，因此背景工作保留 30 秒，但不再阻塞 TUI。
_FETCH_TIMEOUT = 30.0


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
        self._last_market_open: Optional[bool] = None
        self._state_lock = threading.Lock()
        self._fetch_done = threading.Event()
        self._fetch_done.set()

    # ── public ─────────────────────────────────────────────
    def get(self) -> Optional[Dict[str, Any]]:
        """回傳快取；首次或過期時在背景觸發更新。

        關鍵：失敗後 _last_fetch 會被更新，不會在每次 TUI render 都重試，
        而是等到 refresh_interval（盤中 15s / 盤後 3600s）後才重試。
        """
        now = time.time()
        is_market_open = self._is_market_open()
        refresh_interval = 15 if is_market_open else 3600

        # 開盤／收盤邊界立即更新，不沿用上一個時段的 TTL。
        market_state_changed = (
            self._last_market_open is not None
            and self._last_market_open != is_market_open
        )
        self._last_market_open = is_market_open

        never_attempted = self._last_fetch == 0.0
        data_expired = now - self._last_fetch > refresh_interval

        if never_attempted or data_expired or market_state_changed:
            self._start_background_fetch()

        return self._data

    def get_status(self) -> Dict[str, Any]:
        """回傳快取狀態（供 TUI 顯示）。"""
        return {
            "is_fetching": self._is_fetching,
            "last_error": self._last_error,
            "has_data": self._data is not None,
        }

    def wait_for_fetch(self, timeout: float = _FETCH_TIMEOUT + 1.0) -> bool:
        """等待目前這一次背景更新結束；只供首次首頁的一次性重畫使用。"""
        self._fetch_done.wait(timeout=max(0.0, timeout))
        return self._data is not None

    def invalidate(self) -> None:
        """清除快取（下次 get() 會重新抓取）。"""
        self._data = None
        self._last_fetch = 0.0
        self._last_error = None
        self._last_market_open = None

    def get_market_mode(self) -> str:
        """依台灣股市交易時段回傳「開盤」或「盤後」。

        行情短暫沒有跳動不代表收盤，因此狀態只使用系統日期與時間判斷。
        """
        return "🟢 開盤" if self._is_market_open() else "🔴 盤後"

    # ── internal ──────────────────────────────────────────
    @staticmethod
    def _is_market_open() -> bool:
        return is_market_session_open(datetime.now())

    def warmup(self) -> None:
        """要求更新行情但不阻塞 TUI。

        主頁每次進入都會呼叫此方法。舊實作在 UI thread 同步等待外部 API，
        最壞會令主頁空白停住 10 秒；現在保留上一份可用快取並在背景更新。
        """
        with self._state_lock:
            self._last_fetch = 0.0
        self._start_background_fetch()

    def _start_background_fetch(self) -> bool:
        """若目前沒有抓取工作，啟動一個背景更新並立即返回。"""
        with self._state_lock:
            if self._is_fetching:
                return False
            self._is_fetching = True
            self._last_error = None
            self._fetch_done.clear()
        threading.Thread(target=self._async_fetch_worker, daemon=True).start()
        return True

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
        with self._state_lock:
            self._last_fetch = time.time()
            self._is_fetching = False
            self._fetch_done.set()
