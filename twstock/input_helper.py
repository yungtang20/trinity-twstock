# -*- coding: utf-8 -*-
"""
input_helper.py — 跨平台統一輸入層（手機 / 電腦通用）

把原本散落在 main.py、strategies.py、各 strategy 模組的 msvcrt /
chcp / cls 全部收攏到此模組，對外只暴露：
  - get_interactive_input(prompt, ...)  — 統一鍵盤輸入
  - clear_screen()                      — 跨平台清幕
  - setup_console_encoding()            - Windows UTF-8 / 手機跳過 chcp

支援平台：
  Windows (msvcrt)  → 即時按鍵、自動送出 4 碼股號
  Linux / macOS / Termux → 用 termios+stty raw fallback
  其他 (CI / pipe)  →  fallback 到標準 input()

使用方式：
  from input_helper import get_interactive_input, clear_screen, setup_console_encoding
"""

from __future__ import annotations

import os
import sys
from typing import Optional

# termios/tty/select only on Unix (Termux/Linux/macOS); Windows uses msvcrt.
# `select` is a stdlib module but select.select() on stdin is only meaningful on Unix,
# so keep it in the same conditional block — patch("twstock.input_helper.select", ...)
# in tests requires it to be importable at module scope when HAS_TERMIOS is True.
try:
    import select
    import termios
    import tty

    HAS_TERMIOS = True
except ImportError:
    select = None  # type: ignore[assignment]
    termios = None  # type: ignore[assignment]
    tty = None  # type: ignore[assignment]
    HAS_TERMIOS = False

# ── 平台偵測 ──────────────────────────────────────────
_IS_WINDOWS = sys.platform == "win32"
_IS_TTY = sys.stdin.isatty() if hasattr(sys.stdin, "isatty") else False

try:
    import msvcrt  # type: ignore[import-untyped]

    HAS_MSVCRT = True
except ImportError:
    msvcrt = None  # type: ignore[assignment]
    HAS_MSVCRT = False


# ── Console 初始化（取代各處重複的 chcp / reconfigure）────
def setup_console_encoding() -> None:
    """Windows 下設定 UTF-8 編碼；非 Windows（Termux/Mac/Linux）跳過 chcp。"""
    if _IS_WINDOWS:
        os.system("chcp 65001 > nul")  # pragma: no cover
        try:
            sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
            sys.stdin.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except AttributeError:
            pass


# ── 跨平台清幕 ─────────────────────────────────────────
def clear_screen() -> None:
    """跨平台清除 terminal（手機 Termux 用 clear，Windows 用 cls）。"""
    if _IS_WINDOWS:
        os.system("cls")  # pragma: no cover
    else:
        # Termux / Mac / Linux 都支援 clear；不支援時寫 ANSI ESC
        if os.system("clear") != 0:
            sys.stdout.write("\033[2J\033[H")
            sys.stdout.flush()


# ── 單鍵讀取（non-blocking） ────────────────────────────
def _getch_windows() -> Optional[str]:
    """Windows: msvcrt 即時按鍵。"""
    if msvcrt is None:
        return None
    return msvcrt.getwch()  # type: ignore[union-attr]


def _getch_unix() -> Optional[str]:  # pragma: no cover — Unix-only, not executed on Windows CI
    """Termux/Linux/macOS: 用 tty raw mode 讀單一字元。"""
    if not _IS_TTY or not HAS_TERMIOS:
        return None
    fd = sys.stdin.fileno()
    try:
        old_settings = termios.tcgetattr(fd)  # type: ignore[attr-defined]
        tty.setraw(fd)  # type: ignore[attr-defined]
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)  # type: ignore[attr-defined]
    return ch


def _kbhit_windows() -> bool:
    if msvcrt is None:
        return False
    return msvcrt.kbhit()  # type: ignore[union-attr]


def _kbhit_unix() -> bool:  # pragma: no cover — Unix-only, not executed on Windows CI
    """non-blocking check via select。"""
    if not _IS_TTY or select is None:
        return False

    r, _, _ = select.select([sys.stdin], [], [], 0)
    return bool(r)


# ── 統一入口 ─────────────────────────────────────────────
def get_interactive_input(
    prompt: str = "\n🔍 指令: ",
    menu_keys: str = "01234",
    auto_four: bool = True,
    timeout: float = 0.4,
) -> str:
    """
    跨平台統一鍵盤輸入。

    Windows (msvcrt): 按鍵即時回應、0.4s 延遲內無第二鍵則視為單鍵選擇、
                     自動 4 碼送出。
    Termux/Linux/macOS: 使用 termios raw mode 模擬；第一次按鍵後等待
                       0.4s 判斷是否單鍵選擇。
    其他 (pipe / CI):  fallback 到標準 input()。
    """
    if not _IS_TTY or (not HAS_MSVCRT and not _is_unix_tty()):
        return input(prompt).strip()

    # Windows fast path — keep original behavior for compatibility
    if HAS_MSVCRT:
        return _get_interactive_input_windows(prompt, menu_keys, auto_four, timeout)

    # Unix/Termux path
    return _get_interactive_input_unix(prompt, menu_keys, auto_four, timeout)


def _is_unix_tty() -> bool:  # pragma: no cover — Unix-only, not executed on Windows CI
    """Confirm stdin is a real terminal (not pipe)。"""
    return _IS_TTY and HAS_TERMIOS and os.isatty(sys.stdin.fileno())


def _flush_input_buffer() -> None:
    """清除鍵盤緩衝區（Windows: msvcrt.kbhit；Unix: tcflush）。"""
    if HAS_MSVCRT:
        while msvcrt.kbhit():  # type: ignore[union-attr]
            msvcrt.getwch()  # type: ignore[union-attr]
    elif _IS_TTY and HAS_TERMIOS:  # pragma: no cover — Unix-only branch, not executed on Windows CI
        try:
            termios.tcflush(sys.stdin, termios.TCIFLUSH)  # type: ignore[attr-defined]
        except Exception as e:
            print(f"[{__name__}] Error flushing stdin: {e}")


def _get_interactive_input_windows(
    prompt: str, menu_keys: str, auto_four: bool, timeout: float
) -> str:
    """Windows 版本：msvcrt（與原版 main.py 行為完全一致）。"""

    _flush_input_buffer()
    sys.stdout.write(prompt)
    sys.stdout.flush()
    buf = ""
    while True:
        if msvcrt.kbhit():  # type: ignore[union-attr]
            ch = msvcrt.getwch()  # type: ignore[union-attr]
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
                if len(buf) == 1 and ch in menu_keys:
                    if _wait_for_second_key_windows(timeout):
                        continue
                    return buf
                if auto_four and len(buf) == 4 and buf.isdigit():
                    if _wait_for_second_key_windows(1.2):
                        has_interrupted = False
                        start = 0.0
                        while start < 1.2:
                            if msvcrt.kbhit():  # type: ignore[union-attr]
                                nc = msvcrt.getwch()  # type: ignore[union-attr]
                                if nc in ("\r", "\n"):
                                    break
                                elif nc == "\b":
                                    if buf:
                                        buf = buf[:-1]
                                        sys.stdout.write("\b \b")
                                        sys.stdout.flush()
                                    has_interrupted = True
                                    break
                                elif nc.isprintable():
                                    buf += nc
                                    sys.stdout.write(nc)
                                    sys.stdout.flush()
                                    has_interrupted = True
                                    break
                            import time as _t

                            _t.sleep(0.01)
                            start += 0.01
                        if not has_interrupted:
                            return buf
        import time as _t

        _t.sleep(0.01)


def _wait_for_second_key_windows(timeout: float) -> bool:
    """Wait `timeout` seconds; return True if a second key was pressed。"""
    if msvcrt is None:
        return False
    import time as _t

    deadline = _t.monotonic() + timeout
    while _t.monotonic() < deadline:
        if msvcrt.kbhit():  # type: ignore[union-attr]
            return True
        _t.sleep(0.01)
    return False


def _get_interactive_input_unix(  # pragma: no cover — Unix-only, not executed on Windows CI
    prompt: str, menu_keys: str, auto_four: bool, timeout: float
) -> str:
    """Termux/Linux/macOS 版本：termios raw mode 模擬。"""
    import time as _t

    _flush_input_buffer()
    sys.stdout.write(prompt)
    sys.stdout.flush()
    buf = ""
    while True:
        r, _, _ = select.select([sys.stdin], [], [], 0.05)
        if r:
            ch = sys.stdin.read(1)
            if ch in ("\r", "\n"):
                return buf.strip()
            elif ch == "\x7f":  # Backspace
                if buf:
                    buf = buf[:-1]
                    sys.stdout.write("\b \b")
                    sys.stdout.flush()
            elif ch in ("\x1b", "\x03"):  # Escape / Ctrl-C
                return "0"
            elif ch.isprintable():
                buf += ch
                sys.stdout.write(ch)
                sys.stdout.flush()
                if len(buf) == 1 and ch in menu_keys:
                    # wait for second key
                    r2, _, _ = select.select([sys.stdin], [], [], timeout)
                    if not r2:
                        return buf
                if auto_four and len(buf) == 4 and buf.isdigit():
                    _t.sleep(0.2)
                    r3, _, _ = select.select([sys.stdin], [], [], 1.0)
                    if not r3:
                        return buf


# ── 阻塞單鍵（供策略模組「按任意鍵選擇」使用）─────────────
def get_blocking_key(prompt: str = "") -> str:
    """阻塞等待第一鍵（Windows msvcrt / Unix termios / fallback input）。

    與 get_interactive_input 不同：不檢查 menu_keys、不自動送出、
    不等待第二鍵。回傳第一個按下的字元（或 input() 整行）。
    """
    if prompt:
        sys.stdout.write(prompt)
        sys.stdout.flush()

    if not _IS_TTY:
        return input().strip()

    if HAS_MSVCRT:
        _flush_input_buffer()
        while True:
            if msvcrt.kbhit():  # type: ignore[union-attr]
                ch = msvcrt.getwch()  # type: ignore[union-attr]
                if ch.isprintable() or ch in ("\r", "\n"):
                    if ch in ("\r", "\n"):
                        sys.stdout.write("\n")
                        sys.stdout.flush()
                        return ""
                    sys.stdout.write(ch + "\n")
                    sys.stdout.flush()
                    return ch
            import time as _t

            _t.sleep(0.01)

    if _is_unix_tty():  # pragma: no cover — Unix-only, not executed on Windows CI
        fd = sys.stdin.fileno()
        try:
            old_settings = termios.tcgetattr(fd)  # type: ignore[attr-defined]
            tty.setraw(fd)  # type: ignore[attr-defined]
            ch = sys.stdin.read(1)
            if ch in ("\r", "\n"):
                sys.stdout.write("\n")
                sys.stdout.flush()
                return ""
            if ch.isprintable():
                sys.stdout.write(ch + "\n")
                sys.stdout.flush()
                return ch
            return ch
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)  # type: ignore[attr-defined]

    return input().strip()


# ── Convenience exports ────────────────────────────────
__all__ = [
    "get_interactive_input",
    "get_blocking_key",
    "clear_screen",
    "setup_console_encoding",
    "HAS_MSVCRT",
    "_IS_WINDOWS",
]
