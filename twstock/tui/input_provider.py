# -*- coding: utf-8 -*-
"""input_provider.py — 可注入的鍵盤輸入提供者，分離平台相依性。

定義 InputProvider 協定，並提供 Windows、Unix、Mock 三種實作。
Mock 實作供測試使用，可預設按鍵序列。
"""

from __future__ import annotations

import sys
from typing import List, Optional, Protocol, runtime_checkable


@runtime_checkable
class InputProvider(Protocol):
    """**Public API** — 鍵盤輸入提供者協定。

    所有需要鍵盤輸入的模組（app、strategy、menu）必須透過此協定注入，
    不可直接呼叫 msvcrt/input。
    變更此 Protocol 簽名前，須先檢查 dependency_graph.json 中所有依賴方。
    """

    def get_key(self, prompt: str = "") -> str:
        """阻塞讀取單鍵（或整行）。"""
        ...

    def kbhit(self) -> bool:
        """非阻塞檢查是否有鍵盤輸入。"""
        ...

    def flush(self) -> None:
        """清除輸入緩衝區（若可操作）。"""
        ...


class _WindowsInputProvider:
    """Windows 實作（使用 msvcrt）。"""

    def get_key(self, prompt: str = "") -> str:
        import msvcrt

        if prompt:
            sys.stdout.write(prompt)
            sys.stdout.flush()
        return msvcrt.getwch()

    def kbhit(self) -> bool:
        import msvcrt

        return msvcrt.kbhit()

    def flush(self) -> None:
        import msvcrt

        while msvcrt.kbhit():
            msvcrt.getwch()


class _UnixInputProvider:
    """Unix/Linux/Termux 實作（使用 termios + tty）。

    Windows 上建構子不會被 `create_default_provider()` 回傳，但其他 path
    （手動建構 / 第三方套件 import）仍有可能在 Win 上被建出來。
    我們讓 Win 上的方法退化成安全 no-op，**不改動例外合約**。
    """

    def get_key(self, prompt: str = "") -> str:
        if prompt:
            sys.stdout.write(prompt)
            sys.stdout.flush()
        if sys.platform == "win32":
            # Win + 非預期使用此 provider：模擬 EOF（與 MockInputProvider 一致）
            return ""
        fd = sys.stdin.fileno()
        try:
            import termios  # Unix-only POSIX module — guarded
            import tty

            old = termios.tcgetattr(fd)
            tty.setraw(fd)
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)  # type: ignore[attr-defined]
        return ch

    def kbhit(self) -> bool:
        if sys.platform == "win32":
            return False
        if not sys.stdin.isatty():
            return False
        import select

        r, _, _ = select.select([sys.stdin], [], [], 0)
        return bool(r)

    def flush(self) -> None:
        if sys.platform == "win32":
            return
        if sys.stdin.isatty():
            try:
                import termios  # type: ignore[import-untyped,unused-ignore]

                termios.tcflush(sys.stdin, termios.TCIFLUSH)  # type: ignore[attr-defined]
            except Exception:
                pass


class MockInputProvider:
    """Mock 實作（供測試使用）。"""

    def __init__(self, keys: Optional[List[str]] = None):
        self._keys = list(keys) if keys is not None else []
        self._index = 0
        self.prompts: List[str] = []  # 記錄接收到的 prompt

    def get_key(self, prompt: str = "") -> str:
        self.prompts.append(prompt)
        if self._index < len(self._keys):
            key = self._keys[self._index]
            self._index += 1
            return key
        return ""  # 預設行為：空輸入

    def kbhit(self) -> bool:
        return self._index < len(self._keys)

    def flush(self) -> None:
        pass


def create_default_provider() -> InputProvider:
    """根據平台建立預設提供者。"""
    if sys.platform == "win32":
        try:
            import msvcrt  # noqa: F401

            return _WindowsInputProvider()
        except ImportError:
            return _UnixInputProvider()
    return _UnixInputProvider()
