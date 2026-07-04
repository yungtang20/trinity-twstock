#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
terminal.py — 集中管理所有 Rich Console 實體
解決 Windows cp950 終端無法渲染 emoji 的問題
"""

import io
import sys

from rich.console import Console


def _make_utf8_console(**kwargs) -> Console:
    """建立強制 UTF-8 輸出的 Console，相容 Windows cp950 終端"""
    # 明確指定 color_system，避免 TextIOWrapper 包裝後偵測不到終端顏色
    kwargs.setdefault("color_system", "truecolor")
    # 判斷是否為 Windows 且 stdout 非 UTF-8
    if sys.platform == "win32" and getattr(sys.stdout, "encoding", "").lower() not in (
        "utf-8",
        "utf8",
    ):
        utf8_file = io.TextIOWrapper(
            sys.stdout.buffer,
            encoding="utf-8",
            errors="replace",
            line_buffering=True,
        )
        return Console(file=utf8_file, **kwargs)

    # 非 Windows 或已是 UTF-8，直接建立
    return Console(**kwargs)


def _make_utf8_stderr_console(**kwargs) -> Console:
    """stderr 版本（給 rconsole 用）"""
    kwargs.setdefault("color_system", "truecolor")
    if sys.platform == "win32" and getattr(sys.stderr, "encoding", "").lower() not in (
        "utf-8",
        "utf8",
    ):
        utf8_file = io.TextIOWrapper(
            sys.stderr.buffer,
            encoding="utf-8",
            errors="replace",
            line_buffering=True,
        )
        return Console(file=utf8_file, stderr=True, **kwargs)

    return Console(stderr=True, **kwargs)


# ── 對外匯出的實體 ──────────────────────────────────────────
console = _make_utf8_console()
rconsole = _make_utf8_stderr_console()
