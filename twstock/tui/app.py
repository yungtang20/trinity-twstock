# -*- coding: utf-8 -*-
"""TUIApp — 互動式選單主循環（狀態封裝）。"""
from __future__ import annotations

import sys

from twstock.input_helper import setup_console_encoding, HAS_MSVCRT, msvcrt
from twstock.market_data import MarketCache
from twstock.tui import render_dashboard
from twstock.tui import menu as tui_menu
from twstock.strategy.composites import run_composite
from twstock.strategy.strategies import interactive_menu as strategies_menu
from twstock.utils import get_token
from twstock.terminal import console


class TUIApp:
    """封裝 TUI 狀態與主循環。

    Usage:
        app = TUIApp()
        app.run()
    """

    def __init__(self):
        self._cache = MarketCache()

    # ── public ─────────────────────────────────────────────
    def run(self) -> None:
        """進入主選單 loop（直到使用者按 0）。"""
        while True:
            render_dashboard()
            ch = self._get_input(
                "\n🔍 輸入股號或按 Enter 回到上一頁: ",
                menu_keys="01234",
            )
            if ch == "0":
                break
            elif ch == "1":
                tui_menu.run_daily_update()
            elif ch == "2":
                tui_menu.run_historical_update_menu()
            elif ch == "3":
                strategies_menu()
            elif ch == "4":
                tui_menu.run_db_maintenance()
            elif len(ch) == 4 and ch.isdigit():
                run_composite(ch)
            elif ch == "":
                continue

    # ── input ─────────────────────────────────────────────
    def _get_input(self, prompt: str = "\n🔍 指令: ",
                   menu_keys: str = "01234",
                   auto_four: bool = True) -> str:
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
            time.sleep(0.01)

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
            time.sleep(0.01)
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
            time.sleep(0.01)
        if not has_interrupted:
            return buf
        return None
