# -*- coding: utf-8 -*-
"""test_input_helper.py — input_helper.py 覆蓋率測試。"""
from __future__ import annotations

import io
import sys
from unittest.mock import MagicMock, patch

import pytest

from twstock.input_helper import (
    _flush_input_buffer,
    _getch_unix,
    _getch_windows,
    _kbhit_unix,
    _kbhit_windows,
    clear_screen,
    get_blocking_key,
    get_interactive_input,
    setup_console_encoding,
)


class TestSetupConsoleEncoding:
    """setup_console_encoding 平台編碼設定。"""

    @patch("twstock.input_helper._IS_WINDOWS", True)
    @patch("twstock.input_helper.os.system")
    def test_windows_encoding(self, mock_system):
        """Windows 應執行 chcp 65001。"""
        setup_console_encoding()
        mock_system.assert_called_once()

    @patch("twstock.input_helper._IS_WINDOWS", False)
    @patch("twstock.input_helper.os.system")
    def test_non_windows_skip(self, mock_system):
        """非 Windows 不應執行 chcp。"""
        setup_console_encoding()
        mock_system.assert_not_called()


class TestClearScreen:
    """clear_screen 跨平台清幕。"""

    @patch("twstock.input_helper._IS_WINDOWS", True)
    @patch("twstock.input_helper.os.system")
    def test_windows_cls(self, mock_system):
        """Windows 應使用 cls。"""
        clear_screen()
        mock_system.assert_called_once_with("cls")

    @patch("twstock.input_helper._IS_WINDOWS", False)
    @patch("twstock.input_helper.os.system")
    def test_unix_clear(self, mock_system):
        """Unix 應使用 clear。"""
        mock_system.return_value = 0
        clear_screen()
        mock_system.assert_called_once_with("clear")


class TestGetchWindows:
    """_getch_windows 讀取單鍵。"""

    @patch("twstock.input_helper.msvcrt")
    def test_returns_char(self, mock_msvcrt):
        """應回傳 msvcrt.getwch() 的結果。"""
        mock_msvcrt.getwch.return_value = "a"
        result = _getch_windows()
        assert result == "a"

    @patch("twstock.input_helper.msvcrt", None)
    def test_no_msvcrt_returns_none(self):
        """無 msvcrt 時應回傳 None。"""
        result = _getch_windows()
        assert result is None


class TestKbhitWindows:
    """_kbhit_windows 檢查按鍵狀態。"""

    @patch("twstock.input_helper.msvcrt")
    def test_kbhit_true(self, mock_msvcrt):
        """有按鍵時應回傳 True。"""
        mock_msvcrt.kbhit.return_value = True
        assert _kbhit_windows() is True

    @patch("twstock.input_helper.msvcrt", None)
    def test_no_msvcrt_returns_false(self):
        """無 msvcrt 時應回傳 False。"""
        assert _kbhit_windows() is False


class TestGetInteractiveInput:
    """get_interactive_input 統一入口。"""

    @patch("twstock.input_helper.input", return_value="1")
    @patch("twstock.input_helper._IS_TTY", False)
    def test_non_tty_fallback(self, mock_input):
        """非 TTY 應 fallback 到 input()。"""
        result = get_interactive_input("prompt: ", "12345")
        assert result == "1"
        mock_input.assert_called_once()


class TestGetBlockingKey:
    """get_blocking_key 阻塞單鍵。"""

    @patch("twstock.input_helper.input", return_value="a")
    @patch("twstock.input_helper._IS_TTY", False)
    def test_non_tty_returns_input(self, mock_input):
        """非 TTY 應 fallback 到 input()。"""
        result = get_blocking_key("")
        assert result == "a"
        mock_input.assert_called_once()


class TestFlushInputBuffer:
    """_flush_input_buffer 清除緩衝區。"""

    @patch("twstock.input_helper.msvcrt")
    def test_flushes_windows(self, mock_msvcrt):
        """Windows 應清除 msvcrt 緩衝區。"""
        mock_msvcrt.kbhit.side_effect = [True, True, False]
        mock_msvcrt.getwch.return_value = "x"
        _flush_input_buffer()
        assert mock_msvcrt.getwch.call_count == 2

    @patch("twstock.input_helper.msvcrt", None)
    @patch("twstock.input_helper.HAS_MSVCRT", False)
    @patch("twstock.input_helper._IS_TTY", False)
    def test_no_msvcrt_no_error(self):
        """無 msvcrt 時不應拋異常。"""
        _flush_input_buffer()
