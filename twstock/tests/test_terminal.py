# -*- coding: utf-8 -*-
"""test_terminal.py — terminal.py 初始化覆蓋。"""
from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

_DIR = "D:/twse"
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)


class TestTerminalInit:
    def test_console_exported(self):
        from twstock.terminal import console, rconsole
        assert console is not None
        assert rconsole is not None

    def test_windows_non_utf8_console(self):
        """Windows + non-UTF8 stdout → wraps in TextIOWrapper."""
        with patch("twstock.terminal.sys") as mock_sys:
            mock_sys.platform = "win32"
            mock_stdout = MagicMock()
            mock_stdout.encoding = "cp950"
            mock_stdout.buffer = MagicMock()
            mock_sys.stdout = mock_stdout
            mock_sys.stderr = MagicMock()
            mock_sys.stderr.encoding = "cp950"

            with patch("twstock.terminal.Console") as MockConsole:
                MockConsole.return_value = MagicMock()
                from twstock.terminal import _make_utf8_console
                _make_utf8_console()
                MockConsole.assert_called_once()
                call_kwargs = MockConsole.call_args[1]
                assert "file" in call_kwargs

    def test_unix_console(self):
        """Unix → direct Console."""
        with patch("twstock.terminal.sys") as mock_sys:
            mock_sys.platform = "linux"
            mock_sys.stdout = MagicMock()
            mock_sys.stdout.encoding = "utf-8"

            with patch("twstock.terminal.Console") as MockConsole:
                MockConsole.return_value = MagicMock()
                from twstock.terminal import _make_utf8_console, _make_utf8_stderr_console
                _make_utf8_console()
                _make_utf8_stderr_console()
                assert MockConsole.call_count == 2
