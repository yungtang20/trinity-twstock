# -*- coding: utf-8 -*-
"""TUIApp — 互動式選單主循環（狀態封裝）。"""

from __future__ import annotations

import sys

from twstock.input_helper import HAS_MSVCRT, msvcrt
from twstock.strategy.composites import run_composite
from twstock.strategy.strategies import interactive_menu as strategies_menu
from twstock.tui.menu import (
    run_daily_update,
    run_db_maintenance,
    run_historical_update_menu,
)
from twstock.tui.render import render_dashboard
from twstock.tui.state_machine import (
    ActionType,
    TUIState,
    dispatch_main_menu,
)
from twstock.utils import get_token  # noqa: F401


class TUIApp:
    """封裝 TUI 狀態與主循環。

    Usage:
        app = TUIApp()
        app.run()
    """

    def __init__(self):
        # 使用 render 模組的共享快取實例（與 render_dashboard 使用同一個）
        from twstock.tui.render import _market_cache

        self._cache = _market_cache

    # ── public ─────────────────────────────────────────────
    def run(self) -> None:
        """進入主選單 loop（直到使用者按 0）。

        使用 state_machine.dispatch_main_menu 進行狀態分派。
        """
        state = TUIState.MAIN_MENU
        while state != TUIState.EXIT:
            render_dashboard()
            # 每次 render 後檢查 cache，確保 background fetch 完成時立即顯示
            cache_data = self._cache.get()
            if cache_data and cache_data.get("TAIEX", {}).get("price", 0) > 0:
                # 已有資料，直接顯示
                pass
            ch = self._get_input(
                "\n🔍 輸入股號或按 Enter 回到上一頁: ",
                menu_keys="01234",
            )
            transition = dispatch_main_menu(ch)
            state = transition.next_state
            self._execute_action(transition)

    def _execute_action(self, transition) -> None:
        """執行動作（副作用）。"""
        if transition.action == ActionType.RUN_DAILY_UPDATE:
            run_daily_update()
        elif transition.action == ActionType.RUN_HISTORICAL_UPDATE:
            run_historical_update_menu()
        elif transition.action == ActionType.RUN_STRATEGY_MENU:
            strategies_menu()
        elif transition.action == ActionType.RUN_DB_MAINTENANCE:
            run_db_maintenance()
        elif transition.action == ActionType.RUN_COMPOSITE:
            run_composite(transition.payload)

    # ── input ─────────────────────────────────────────────
    def _get_input(
        self, prompt: str = "\n🔍 指令: ", menu_keys: str = "01234", auto_four: bool = True
    ) -> str:
        """互動式鍵盤輸入（msvcrt on Windows, fallback to input()）。"""
        if not HAS_MSVCRT:
            return input(prompt).strip()

        while msvcrt.kbhit():
            msvcrt.getwch()

        sys.stdout.write(prompt)
        sys.stdout.flush()
        buf = ""
        last_cache = self._cache.get()

        while True:
            # 動態刷新 TUI 當背景指數抓取完成
            current_cache = self._cache.get()
            if last_cache is None and current_cache is not None:
                render_dashboard()
                sys.stdout.write(prompt + buf)
                sys.stdout.flush()
                last_cache = current_cache

            if msvcrt.kbhit():
                ch = msvcrt.getwch()
                if ch in ("\r", "\n"):
                    return buf.strip()
                elif ch == "\b":
                    if buf:
                        buf = buf[:-1]
                        sys.stdout.write("\b \b")
                        sys.stdout.flush()
                elif ch in ("\x1b", "\x03"):
                    return "0"
                elif ch.isprintable():
                    buf += ch
                    sys.stdout.write(ch)
                    sys.stdout.flush()
                    # 單鍵選單（0.4s 內無新鍵則送出）
                    if len(buf) == 1 and ch in menu_keys:
                        if not self._wait_for_key(0.4):
                            return buf
                    # 4 碼股號自動送出（1.2s 延遲）
                    if auto_four and len(buf) == 4 and buf.isdigit():
                        result = self._wait_for_stock_suffix(1.2, buf)
                        if result is not None:
                            return result
            import time

            time.sleep(0.05)  # ponytail: 50ms 仍足夠回應，降低 CPU 空轉

    @staticmethod
    def _wait_for_key(timeout: float) -> bool:
        """等待 timeout 秒內有無新鍵。有則回傳 True。"""
        import time

        start = time.time()
        while time.time() - start < timeout:
            if msvcrt.kbhit():
                next_ch = msvcrt.getwch()
                if next_ch in ("\r", "\n"):
                    pass  # swallow Enter
                return True
            time.sleep(0.05)  # ponytail: 降低 CPU 使用率，TUI 刷新無需 10ms
        return False

    @staticmethod
    def _wait_for_stock_suffix(timeout: float, buf: str) -> str | None:
        """等待 4 碼後的按鍵。若無新鍵回傳 buf，有則回傳 None（表示繼續輸入）。"""
        import time

        start = time.time()
        has_interrupted = False
        while time.time() - start < timeout:
            if msvcrt.kbhit():
                next_ch = msvcrt.getwch()
                if next_ch in ("\r", "\n"):
                    break
                elif next_ch == "\b":
                    if buf:
                        buf = buf[:-1]
                        sys.stdout.write("\b \b")
                        sys.stdout.flush()
                    has_interrupted = True
                    break
                elif next_ch.isprintable():
                    buf += next_ch
                    sys.stdout.write(next_ch)
                    sys.stdout.flush()
                    has_interrupted = True
                    break
            time.sleep(0.05)  # ponytail: 與主迴圈一致
        if not has_interrupted:
            return buf
        return None
