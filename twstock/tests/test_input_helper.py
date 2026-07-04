# -*- coding: utf-8 -*-
"""test_input_helper.py - input_helper.py coverage tests."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

# Unix-only functions are # pragma: no cover in source — skip tests on Windows
_IS_UNIX = sys.platform != "win32"

from twstock.input_helper import (
    _flush_input_buffer,
    _get_interactive_input_windows,
    _getch_unix,
    _getch_windows,
    _kbhit_unix,
    _kbhit_windows,
    _wait_for_second_key_windows,
    clear_screen,
    get_blocking_key,
    get_interactive_input,
    setup_console_encoding,
)


class TestSetupConsoleEncoding:
    @patch("twstock.input_helper._IS_WINDOWS", True)
    @patch("twstock.input_helper.os.system")
    def test_windows_encoding(self, mock_system):
        setup_console_encoding()
        mock_system.assert_called_once()

    @patch("twstock.input_helper._IS_WINDOWS", False)
    @patch("twstock.input_helper.os.system")
    def test_non_windows_skip(self, mock_system):
        setup_console_encoding()
        mock_system.assert_not_called()


class TestClearScreen:
    @patch("twstock.input_helper._IS_WINDOWS", True)
    @patch("twstock.input_helper.os.system")
    def test_windows_cls(self, mock_system):
        clear_screen()
        mock_system.assert_called_once_with("cls")

    @patch("twstock.input_helper._IS_WINDOWS", False)
    @patch("twstock.input_helper.os.system")
    def test_unix_clear(self, mock_system):
        mock_system.return_value = 0
        clear_screen()
        mock_system.assert_called_once_with("clear")


class TestGetchWindows:
    @patch("twstock.input_helper.msvcrt")
    def test_returns_char(self, mock_msvcrt):
        mock_msvcrt.getwch.return_value = "a"
        result = _getch_windows()
        assert result == "a"

    @patch("twstock.input_helper.msvcrt", None)
    def test_no_msvcrt_returns_none(self):
        result = _getch_windows()
        assert result is None


class TestKbhitWindows:
    @patch("twstock.input_helper.msvcrt")
    def test_kbhit_true(self, mock_msvcrt):
        mock_msvcrt.kbhit.return_value = True
        assert _kbhit_windows() is True

    @patch("twstock.input_helper.msvcrt", None)
    def test_no_msvcrt_returns_false(self):
        assert _kbhit_windows() is False


class TestGetInteractiveInput:
    @patch("twstock.input_helper.input", return_value="1")
    @patch("twstock.input_helper._IS_TTY", False)
    def test_non_tty_fallback(self, mock_input):
        result = get_interactive_input("prompt: ", "12345")
        assert result == "1"
        mock_input.assert_called_once()


class TestGetBlockingKey:
    @patch("twstock.input_helper.input", return_value="a")
    @patch("twstock.input_helper._IS_TTY", False)
    def test_non_tty_returns_input(self, mock_input):
        result = get_blocking_key("")
        assert result == "a"
        mock_input.assert_called_once()


class TestFlushInputBuffer:
    @patch("twstock.input_helper.msvcrt")
    def test_flushes_windows(self, mock_msvcrt):
        mock_msvcrt.kbhit.side_effect = [True, True, False]
        mock_msvcrt.getwch.side_effect = ["x", "y"]
        _flush_input_buffer()
        assert mock_msvcrt.getwch.call_count == 2

    @patch("twstock.input_helper._IS_TTY", False)
    def test_no_msvcrt_no_error(self):
        with (
            patch("twstock.input_helper.msvcrt", None),
            patch("twstock.input_helper.HAS_MSVCRT", False),
        ):
            _flush_input_buffer()


class TestSetupConsoleEncodingExceptions:
    @patch("twstock.input_helper._IS_WINDOWS", True)
    @patch("twstock.input_helper.os.system")
    @patch("twstock.input_helper.sys")
    def test_reconfigure_attribute_error(self, mock_sys, mock_system):
        mock_sys.stdout.reconfigure.side_effect = AttributeError("no reconfigure")
        mock_sys.stdin.reconfigure.side_effect = AttributeError("no reconfigure")
        setup_console_encoding()
        mock_system.assert_called_once()


class TestClearScreenAnsiFallback:
    @patch("twstock.input_helper._IS_WINDOWS", False)
    @patch("twstock.input_helper.os.system")
    def test_clear_screen_ansi_fallback(self, mock_system):
        mock_system.return_value = 1
        mock_stdout = MagicMock()
        with patch("twstock.input_helper.sys.stdout", mock_stdout):
            clear_screen()
        mock_stdout.write.assert_any_call("\x1b[2J\x1b[H")
        mock_stdout.flush.assert_called()


class TestGetInteractiveInputRouting:
    @patch("twstock.input_helper._get_interactive_input_windows")
    def test_windows_path(self, mock_windows):
        mock_windows.return_value = "1"
        with (
            patch("twstock.input_helper._IS_TTY", True),
            patch("twstock.input_helper.HAS_MSVCRT", True),
        ):
            result = get_interactive_input("prompt: ", "12345")
        assert result == "1"
        mock_windows.assert_called_once()

    @patch("twstock.input_helper._get_interactive_input_unix")
    def test_unix_path(self, mock_unix):
        mock_unix.return_value = "2"
        with (
            patch("twstock.input_helper._IS_TTY", True),
            patch("twstock.input_helper.HAS_MSVCRT", False),
            patch("twstock.input_helper.HAS_TERMIOS", True),
            patch("twstock.input_helper.os.isatty", return_value=True),
            patch("twstock.input_helper.sys.stdin.fileno", return_value=0),
        ):
            result = get_interactive_input("prompt: ", "12345")
        assert result == "2"
        mock_unix.assert_called_once()


class TestWaitForSecondKeyWindows:
    def test_no_msvcrt_returns_false(self):
        with patch("twstock.input_helper.msvcrt", None):
            assert _wait_for_second_key_windows(0.4) is False

    def test_key_pressed_within_deadline(self):
        fake_msvcrt = MagicMock()
        fake_msvcrt.kbhit.return_value = True
        with (
            patch("twstock.input_helper.msvcrt", fake_msvcrt),
            patch("time.monotonic", side_effect=[0.0, 0.0]),
        ):
            assert _wait_for_second_key_windows(0.4) is True

    def test_deadline_expires(self):
        fake_msvcrt = MagicMock()
        fake_msvcrt.kbhit.return_value = False
        with (
            patch("twstock.input_helper.msvcrt", fake_msvcrt),
            patch("time.monotonic", side_effect=[0.0, 0.5]),
            patch("time.sleep"),
        ):
            assert _wait_for_second_key_windows(0.4) is False


def _make_smart_msvcrt(getwch_chars):
    chars = list(getwch_chars)
    idx = [0]

    def kbhit():
        return idx[0] < len(chars)

    def getwch():
        ch = chars[idx[0]]
        idx[0] += 1
        return ch

    fake = MagicMock()
    fake.kbhit.side_effect = kbhit
    fake.getwch.side_effect = getwch
    return fake


class TestGetInteractiveInputWindows:
    def test_enter_returns_empty(self):
        fake = _make_smart_msvcrt(["\r"])
        with (
            patch("twstock.input_helper.msvcrt", fake),
            patch("twstock.input_helper.sys.stdout"),
            patch("time.sleep"),
            patch("twstock.input_helper._flush_input_buffer"),
        ):
            result = _get_interactive_input_windows("prompt:", "01234", True, 0.4)

    def test_backspace_truncates(self):
        fake = _make_smart_msvcrt(["2", "3", "\x08", "\r"])
        with (
            patch("twstock.input_helper.msvcrt", fake),
            patch("twstock.input_helper.sys.stdout"),
            patch("time.sleep"),
            patch("twstock.input_helper._flush_input_buffer"),
        ):
            result = _get_interactive_input_windows("prompt:", "01234", True, 0.4)
        assert result == "2"

    def test_esc_returns_zero(self):
        fake = _make_smart_msvcrt(["\x1b"])
        with (
            patch("twstock.input_helper.msvcrt", fake),
            patch("twstock.input_helper.sys.stdout"),
            patch("time.sleep"),
            patch("twstock.input_helper._flush_input_buffer"),
        ):
            result = _get_interactive_input_windows("prompt:", "01234", True, 0.4)
        assert result == "0"

    def test_ctrl_c_returns_zero(self):
        fake = _make_smart_msvcrt(["\x03"])
        with (
            patch("twstock.input_helper.msvcrt", fake),
            patch("twstock.input_helper.sys.stdout"),
            patch("time.sleep"),
            patch("twstock.input_helper._flush_input_buffer"),
        ):
            result = _get_interactive_input_windows("prompt:", "01234", True, 0.4)
        assert result == "0"

    def test_menu_key_auto_commit(self):
        fake = _make_smart_msvcrt(["1"])
        with (
            patch("twstock.input_helper.msvcrt", fake),
            patch("twstock.input_helper.sys.stdout"),
            patch("time.sleep"),
            patch("twstock.input_helper._flush_input_buffer"),
            patch(
                "twstock.input_helper._wait_for_second_key_windows", return_value=False
            ) as mock_wait,
        ):
            result = _get_interactive_input_windows("prompt:", "01234", True, 0.4)
        assert result == "1"
        mock_wait.assert_called_once_with(0.4)

    def test_menu_key_with_second_key(self):
        fake = _make_smart_msvcrt(["1", "2", "\r"])
        with (
            patch("twstock.input_helper.msvcrt", fake),
            patch("twstock.input_helper.sys.stdout"),
            patch("time.sleep"),
            patch("twstock.input_helper._flush_input_buffer"),
            patch("twstock.input_helper._wait_for_second_key_windows", return_value=True),
        ):
            result = _get_interactive_input_windows("prompt:", "01234", True, 0.4)
        assert result == "12"

    def test_four_digit_auto_commit(self):
        fake = _make_smart_msvcrt(["5", "6", "7", "8"])
        with (
            patch("twstock.input_helper.msvcrt", fake),
            patch("twstock.input_helper.sys.stdout"),
            patch("time.sleep"),
            patch("twstock.input_helper._flush_input_buffer"),
            patch("twstock.input_helper._wait_for_second_key_windows", return_value=True),
        ):
            result = _get_interactive_input_windows("prompt:", "01234", True, 0.4)
        assert result == "5678"

    def test_four_digit_with_backspace_interrupt(self):
        fake = _make_smart_msvcrt(["5", "6", "7", "8", "\x08", "\r"])
        with (
            patch("twstock.input_helper.msvcrt", fake),
            patch("twstock.input_helper.sys.stdout"),
            patch("time.sleep"),
            patch("twstock.input_helper._flush_input_buffer"),
            patch("twstock.input_helper._wait_for_second_key_windows", return_value=True),
        ):
            result = _get_interactive_input_windows("prompt:", "01234", True, 0.4)
        assert result == "567"

    def test_four_digit_with_printable_interrupt(self):
        fake = _make_smart_msvcrt(["5", "6", "7", "8", "9", "\r"])
        with (
            patch("twstock.input_helper.msvcrt", fake),
            patch("twstock.input_helper.sys.stdout"),
            patch("time.sleep"),
            patch("twstock.input_helper._flush_input_buffer"),
            patch("twstock.input_helper._wait_for_second_key_windows", return_value=True),
        ):
            result = _get_interactive_input_windows("prompt:", "01234", True, 0.4)
        assert result == "56789"


class TestGetBlockingKeyWindows:
    def test_printable_char(self):
        fake = _make_smart_msvcrt(["a"])
        with (
            patch("twstock.input_helper.msvcrt", fake),
            patch("twstock.input_helper.HAS_MSVCRT", True),
            patch("twstock.input_helper._IS_TTY", True),
            patch("twstock.input_helper.sys.stdout"),
            patch("twstock.input_helper._flush_input_buffer"),
            patch("time.sleep"),
        ):
            result = get_blocking_key("")
        assert result == "a"

    def test_enter_returns_empty(self):
        fake = _make_smart_msvcrt(["\r"])
        with (
            patch("twstock.input_helper.msvcrt", fake),
            patch("twstock.input_helper.HAS_MSVCRT", True),
            patch("twstock.input_helper._IS_TTY", True),
            patch("twstock.input_helper.sys.stdout"),
            patch("twstock.input_helper._flush_input_buffer"),
            patch("time.sleep"),
        ):
            result = get_blocking_key("")
        assert result == ""

    def test_prompt_writes(self):
        fake = _make_smart_msvcrt(["x"])
        mock_stdout = MagicMock()
        with (
            patch("twstock.input_helper.msvcrt", fake),
            patch("twstock.input_helper.HAS_MSVCRT", True),
            patch("twstock.input_helper._IS_TTY", True),
            patch("twstock.input_helper.sys.stdout", mock_stdout),
            patch("twstock.input_helper._flush_input_buffer"),
            patch("time.sleep"),
        ):
            result = get_blocking_key("choice: ")
        assert result == "x"
        mock_stdout.write.assert_any_call("choice: ")


class TestOuterPollLoop:
    """Cover line 214-216 (outer poll sleep in _get_interactive_input_windows)."""

    def test_poll_iteration_before_keypress(self):
        """前幾次 kbhit=False 時，outer poll 走 time.sleep(0.01) 迴圈。"""
        # kbhit returns False 5 times (drives outer sleep), then True + '\r' returns.
        kbhit_vals = [False, False, False, False, False, True]
        fake = MagicMock()
        fake.kbhit.side_effect = kbhit_vals
        fake.getwch.return_value = "\r"
        with (
            patch("twstock.input_helper.msvcrt", fake),
            patch("twstock.input_helper.sys.stdout"),
            patch("time.sleep"),
            patch("twstock.input_helper._flush_input_buffer"),
        ):
            result = _get_interactive_input_windows("prompt:", "01234", True, 0.4)
        assert result == ""


class TestBlockingKeyFallback:
    """Cover line 324 (get_blocking_key final fallback input())."""

    def test_fallback_path(self):
        """TTY=True, HAS_MSVCRT=False, not unix-tty → 走到 input() fallback。"""
        with (
            patch("twstock.input_helper._IS_TTY", True),
            patch("twstock.input_helper.HAS_MSVCRT", False),
            patch("twstock.input_helper._is_unix_tty", return_value=False),
            patch("twstock.input_helper.input", return_value="fallback") as mock_input,
        ):
            result = get_blocking_key()
        assert result == "fallback"
        mock_input.assert_called_once()


class TestGetchUnix:
    def test_returns_char_from_raw_mode(self):
        mock_termios = MagicMock()
        mock_tty = MagicMock()
        mock_stdin = MagicMock()
        mock_stdin.fileno.return_value = 0
        mock_stdin.read.return_value = "x"
        mock_termios.tcgetattr.return_value = [{"fake": "settings"}]

        with (
            patch("twstock.input_helper._IS_TTY", True),
            patch("twstock.input_helper.HAS_TERMIOS", True),
            patch("twstock.input_helper.termios", mock_termios),
            patch("twstock.input_helper.tty", mock_tty),
            patch("twstock.input_helper.sys.stdin", mock_stdin),
        ):
            result = _getch_unix()
        assert result == "x"
        mock_tty.setraw.assert_called_once_with(0)
        mock_termios.tcgetattr.assert_called_once_with(0)
        mock_termios.tcsetattr.assert_called_once()

    def test_returns_none_when_not_tty(self):
        with patch("twstock.input_helper._IS_TTY", False):
            assert _getch_unix() is None

    def test_returns_none_when_no_termios(self):
        with (
            patch("twstock.input_helper._IS_TTY", True),
            patch("twstock.input_helper.HAS_TERMIOS", False),
        ):
            assert _getch_unix() is None


@pytest.mark.skipif(not _IS_UNIX, reason="Unix-only function")
class TestKbhitUnix:
    def test_kbhit_true(self):
        mock_select = MagicMock()
        mock_select.select.return_value = ([MagicMock()], [], [])
        with (
            patch("twstock.input_helper._IS_TTY", True),
            patch("twstock.input_helper.select", mock_select),
            patch("twstock.input_helper.sys.stdin", MagicMock()),
        ):
            result = _kbhit_unix()
        assert result is True
        mock_select.select.assert_called_once()

    def test_kbhit_false(self):
        mock_select = MagicMock()
        mock_select.select.return_value = ([], [], [])
        with (
            patch("twstock.input_helper._IS_TTY", True),
            patch("twstock.input_helper.select", mock_select),
            patch("twstock.input_helper.sys.stdin", MagicMock()),
        ):
            result = _kbhit_unix()
        assert result is False

    def test_returns_false_when_not_tty(self):
        with patch("twstock.input_helper._IS_TTY", False):
            assert _kbhit_unix() is False


@pytest.mark.skipif(not _IS_UNIX, reason="Unix-only function")
class TestIsUnixTty:
    def test_true_when_all_conditions_met(self):
        with (
            patch("twstock.input_helper._IS_TTY", True),
            patch("twstock.input_helper.HAS_TERMIOS", True),
            patch("twstock.input_helper.os.isatty", return_value=True),
            patch("twstock.input_helper.sys.stdin", MagicMock()),
        ):
            from twstock.input_helper import _is_unix_tty

            assert _is_unix_tty() is True

    def test_false_when_is_tty_false(self):
        with (
            patch("twstock.input_helper._IS_TTY", False),
            patch("twstock.input_helper.HAS_TERMIOS", True),
            patch("twstock.input_helper.os.isatty", return_value=True),
        ):
            from twstock.input_helper import _is_unix_tty

            assert _is_unix_tty() is False

    def test_false_when_has_termios_false(self):
        with (
            patch("twstock.input_helper._IS_TTY", True),
            patch("twstock.input_helper.HAS_TERMIOS", False),
            patch("twstock.input_helper.os.isatty", return_value=True),
        ):
            from twstock.input_helper import _is_unix_tty

            assert _is_unix_tty() is False

    def test_false_when_os_isatty_false(self):
        with (
            patch("twstock.input_helper._IS_TTY", True),
            patch("twstock.input_helper.HAS_TERMIOS", True),
            patch("twstock.input_helper.os.isatty", return_value=False),
        ):
            from twstock.input_helper import _is_unix_tty

            assert _is_unix_tty() is False


@pytest.mark.skipif(not _IS_UNIX, reason="Unix-only function")
class TestFlushInputBufferUnix:
    def test_unix_tcflush_path(self):
        mock_termios = MagicMock()
        with (
            patch("twstock.input_helper.HAS_MSVCRT", False),
            patch("twstock.input_helper._IS_TTY", True),
            patch("twstock.input_helper.HAS_TERMIOS", True),
            patch("twstock.input_helper.termios", mock_termios),
            patch("twstock.input_helper.sys.stdin", MagicMock()),
        ):
            _flush_input_buffer()
        mock_termios.tcflush.assert_called_once()

    def test_unix_tcflush_exception_handled(self):
        mock_termios = MagicMock()
        mock_termios.tcflush.side_effect = OSError("device busy")
        with (
            patch("twstock.input_helper.HAS_MSVCRT", False),
            patch("twstock.input_helper._IS_TTY", True),
            patch("twstock.input_helper.HAS_TERMIOS", True),
            patch("twstock.input_helper.termios", mock_termios),
            patch("twstock.input_helper.sys.stdin", MagicMock()),
        ):
            _flush_input_buffer()
        # Should not raise; exception is caught


@pytest.mark.skipif(not _IS_UNIX, reason="Unix-only function")
class TestGetInteractiveInputUnix:
    def _mock_unix_env(self):
        """Return common mocks for Unix interactive input tests."""
        mock_stdout = MagicMock()
        mock_stdin = MagicMock()
        mock_stdin.fileno.return_value = 0
        mock_termios = MagicMock()
        mock_tty = MagicMock()
        mock_select = MagicMock()
        return mock_stdout, mock_stdin, mock_termios, mock_tty, mock_select

    def test_enter_returns_stripped_buf(self):
        mock_stdout, mock_stdin, mock_termios, mock_tty, mock_select = self._mock_unix_env()
        # First call: newline triggers return
        mock_select.select.side_effect = [([mock_stdin], [], []), ([], [], [])]
        mock_stdin.read.side_effect = ["\r"]

        with (
            patch("twstock.input_helper._IS_TTY", True),
            patch("twstock.input_helper.HAS_MSVCRT", False),
            patch("twstock.input_helper.HAS_TERMIOS", True),
            patch("twstock.input_helper._is_unix_tty", return_value=True),
            patch("twstock.input_helper.termios", mock_termios),
            patch("twstock.input_helper.tty", mock_tty),
            patch("twstock.input_helper.os.isatty", return_value=True),
            patch("twstock.input_helper.sys.stdin", mock_stdin),
            patch("twstock.input_helper.sys.stdout", mock_stdout),
            patch("twstock.input_helper.select", mock_select),
            patch("twstock.input_helper._flush_input_buffer"),
        ):
            result = _get_interactive_input_unix("prompt:", "01234", True, 0.4)
        assert result == ""
        mock_stdout.write.assert_called_with("prompt:")

    def test_backspace_truncates(self):
        mock_stdout, mock_stdin, mock_termios, mock_tty, mock_select = self._mock_unix_env()
        # Two keys: 'a' then backspace then newline
        mock_select.select.side_effect = [
            ([mock_stdin], [], []),
            ([mock_stdin], [], []),
            ([mock_stdin], [], []),
            ([], [], []),
        ]
        mock_stdin.read.side_effect = ["a", "\x7f", "\r"]

        with (
            patch("twstock.input_helper._IS_TTY", True),
            patch("twstock.input_helper.HAS_MSVCRT", False),
            patch("twstock.input_helper.HAS_TERMIOS", True),
            patch("twstock.input_helper._is_unix_tty", return_value=True),
            patch("twstock.input_helper.termios", mock_termios),
            patch("twstock.input_helper.tty", mock_tty),
            patch("twstock.input_helper.os.isatty", return_value=True),
            patch("twstock.input_helper.sys.stdin", mock_stdin),
            patch("twstock.input_helper.sys.stdout", mock_stdout),
            patch("twstock.input_helper.select", mock_select),
            patch("twstock.input_helper._flush_input_buffer"),
        ):
            result = _get_interactive_input_unix("prompt:", "01234", True, 0.4)
        assert result == ""
        # backspace writes "\b \b"
        mock_stdout.write.assert_any_call("\b \b")

    def test_esc_returns_zero(self):
        mock_stdout, mock_stdin, mock_termios, mock_tty, mock_select = self._mock_unix_env()
        mock_select.select.side_effect = [([mock_stdin], [], []), ([], [], [])]
        mock_stdin.read.side_effect = ["\x1b"]

        with (
            patch("twstock.input_helper._IS_TTY", True),
            patch("twstock.input_helper.HAS_MSVCRT", False),
            patch("twstock.input_helper.HAS_TERMIOS", True),
            patch("twstock.input_helper._is_unix_tty", return_value=True),
            patch("twstock.input_helper.termios", mock_termios),
            patch("twstock.input_helper.tty", mock_tty),
            patch("twstock.input_helper.os.isatty", return_value=True),
            patch("twstock.input_helper.sys.stdin", mock_stdin),
            patch("twstock.input_helper.sys.stdout", mock_stdout),
            patch("twstock.input_helper.select", mock_select),
            patch("twstock.input_helper._flush_input_buffer"),
        ):
            result = _get_interactive_input_unix("prompt:", "01234", True, 0.4)
        assert result == "0"

    def test_printable_buffering(self):
        mock_stdout, mock_stdin, mock_termios, mock_tty, mock_select = self._mock_unix_env()
        mock_select.select.side_effect = [
            ([mock_stdin], [], []),
            ([mock_stdin], [], []),
            ([], [], []),
        ]
        mock_stdin.read.side_effect = ["1", "2", "\r"]

        with (
            patch("twstock.input_helper._IS_TTY", True),
            patch("twstock.input_helper.HAS_MSVCRT", False),
            patch("twstock.input_helper.HAS_TERMIOS", True),
            patch("twstock.input_helper._is_unix_tty", return_value=True),
            patch("twstock.input_helper.termios", mock_termios),
            patch("twstock.input_helper.tty", mock_tty),
            patch("twstock.input_helper.os.isatty", return_value=True),
            patch("twstock.input_helper.sys.stdin", mock_stdin),
            patch("twstock.input_helper.sys.stdout", mock_stdout),
            patch("twstock.input_helper.select", mock_select),
            patch("twstock.input_helper._flush_input_buffer"),
        ):
            result = _get_interactive_input_unix("prompt:", "01234", True, 0.4)
        assert result == "12"

    def test_menu_key_single_press_auto_commit(self):
        mock_stdout, mock_stdin, mock_termios, mock_tty, mock_select = self._mock_unix_env()
        # First select returns key, second select (wait for 2nd key) returns empty
        mock_select.select.side_effect = [
            ([mock_stdin], [], []),  # first key arrives
            ([], [], []),  # no second key within timeout
        ]
        mock_stdin.read.side_effect = ["1"]

        with (
            patch("twstock.input_helper._IS_TTY", True),
            patch("twstock.input_helper.HAS_MSVCRT", False),
            patch("twstock.input_helper.HAS_TERMIOS", True),
            patch("twstock.input_helper._is_unix_tty", return_value=True),
            patch("twstock.input_helper.termios", mock_termios),
            patch("twstock.input_helper.tty", mock_tty),
            patch("twstock.input_helper.os.isatty", return_value=True),
            patch("twstock.input_helper.sys.stdin", mock_stdin),
            patch("twstock.input_helper.sys.stdout", mock_stdout),
            patch("twstock.input_helper.select", mock_select),
            patch("twstock.input_helper._flush_input_buffer"),
        ):
            result = _get_interactive_input_unix("prompt:", "01234", True, 0.4)
        assert result == "1"

    def test_four_digit_auto_commit(self):
        mock_stdout, mock_stdin, mock_termios, mock_tty, mock_select = self._mock_unix_env()
        # Four keys arrive, then empty selects for auto-commit waits
        mock_select.select.side_effect = [
            ([mock_stdin], [], []),  # 1st digit
            ([mock_stdin], [], []),  # 2nd digit
            ([mock_stdin], [], []),  # 3rd digit
            ([mock_stdin], [], []),  # 4th digit
            ([], [], []),  # sleep 0.2 + select for 1.0 (no interrupt)
        ]
        mock_stdin.read.side_effect = ["1", "2", "3", "4"]

        with (
            patch("twstock.input_helper._IS_TTY", True),
            patch("twstock.input_helper.HAS_MSVCRT", False),
            patch("twstock.input_helper.HAS_TERMIOS", True),
            patch("twstock.input_helper._is_unix_tty", return_value=True),
            patch("twstock.input_helper.termios", mock_termios),
            patch("twstock.input_helper.tty", mock_tty),
            patch("twstock.input_helper.os.isatty", return_value=True),
            patch("twstock.input_helper.sys.stdin", mock_stdin),
            patch("twstock.input_helper.sys.stdout", mock_stdout),
            patch("twstock.input_helper.select", mock_select),
            patch("twstock.input_helper._flush_input_buffer"),
            patch("time.sleep"),
        ):
            result = _get_interactive_input_unix("prompt:", "01234", True, 0.4)
        assert result == "1234"

    def test_four_digit_backspace_interrupt(self):
        mock_stdout, mock_stdin, mock_termios, mock_tty, mock_select = self._mock_unix_env()
        mock_select.select.side_effect = [
            ([mock_stdin], [], []),  # 1st digit
            ([mock_stdin], [], []),  # 2nd
            ([mock_stdin], [], []),  # 3rd
            ([mock_stdin], [], []),  # 4th
            ([mock_stdin], [], []),  # backspace interrupt
            ([], [], []),  # final select
        ]
        mock_stdin.read.side_effect = ["1", "2", "3", "4", "\x7f"]

        with (
            patch("twstock.input_helper._IS_TTY", True),
            patch("twstock.input_helper.HAS_MSVCRT", False),
            patch("twstock.input_helper.HAS_TERMIOS", True),
            patch("twstock.input_helper._is_unix_tty", return_value=True),
            patch("twstock.input_helper.termios", mock_termios),
            patch("twstock.input_helper.tty", mock_tty),
            patch("twstock.input_helper.os.isatty", return_value=True),
            patch("twstock.input_helper.sys.stdin", mock_stdin),
            patch("twstock.input_helper.sys.stdout", mock_stdout),
            patch("twstock.input_helper.select", mock_select),
            patch("twstock.input_helper._flush_input_buffer"),
            patch("time.sleep"),
        ):
            result = _get_interactive_input_unix("prompt:", "01234", True, 0.4)
        assert result == "123"


@pytest.mark.skipif(not _IS_UNIX, reason="Unix-only function")
class TestGetBlockingKeyUnix:
    def test_unix_printable_char(self):
        mock_termios = MagicMock()
        mock_tty = MagicMock()
        mock_stdin = MagicMock()
        mock_stdin.fileno.return_value = 0
        mock_stdin.read.return_value = "a"
        mock_stdout = MagicMock()
        mock_termios.tcgetattr.return_value = [{}]

        with (
            patch("twstock.input_helper._IS_TTY", True),
            patch("twstock.input_helper.HAS_MSVCRT", False),
            patch("twstock.input_helper._is_unix_tty", return_value=True),
            patch("twstock.input_helper.termios", mock_termios),
            patch("twstock.input_helper.tty", mock_tty),
            patch("twstock.input_helper.os.isatty", return_value=True),
            patch("twstock.input_helper.sys.stdin", mock_stdin),
            patch("twstock.input_helper.sys.stdout", mock_stdout),
        ):
            result = get_blocking_key("")
        assert result == "a"
        mock_stdout.write.assert_any_call("a\n")

    def test_unix_enter_returns_empty(self):
        mock_termios = MagicMock()
        mock_tty = MagicMock()
        mock_stdin = MagicMock()
        mock_stdin.fileno.return_value = 0
        mock_stdin.read.return_value = "\r"
        mock_stdout = MagicMock()
        mock_termios.tcgetattr.return_value = [{}]

        with (
            patch("twstock.input_helper._IS_TTY", True),
            patch("twstock.input_helper.HAS_MSVCRT", False),
            patch("twstock.input_helper._is_unix_tty", return_value=True),
            patch("twstock.input_helper.termios", mock_termios),
            patch("twstock.input_helper.tty", mock_tty),
            patch("twstock.input_helper.os.isatty", return_value=True),
            patch("twstock.input_helper.sys.stdin", mock_stdin),
            patch("twstock.input_helper.sys.stdout", mock_stdout),
        ):
            result = get_blocking_key("")
        assert result == ""
        mock_stdout.write.assert_any_call("\n")

    def test_unix_non_printable_returns_ch(self):
        mock_termios = MagicMock()
        mock_tty = MagicMock()
        mock_stdin = MagicMock()
        mock_stdin.fileno.return_value = 0
        mock_stdin.read.return_value = "\x01"
        mock_stdout = MagicMock()
        mock_termios.tcgetattr.return_value = [{}]

        with (
            patch("twstock.input_helper._IS_TTY", True),
            patch("twstock.input_helper.HAS_MSVCRT", False),
            patch("twstock.input_helper._is_unix_tty", return_value=True),
            patch("twstock.input_helper.termios", mock_termios),
            patch("twstock.input_helper.tty", mock_tty),
            patch("twstock.input_helper.os.isatty", return_value=True),
            patch("twstock.input_helper.sys.stdin", mock_stdin),
            patch("twstock.input_helper.sys.stdout", mock_stdout),
        ):
            result = get_blocking_key("")
        assert result == "\x01"

    def test_unix_prompt_writes(self):
        mock_termios = MagicMock()
        mock_tty = MagicMock()
        mock_stdin = MagicMock()
        mock_stdin.fileno.return_value = 0
        mock_stdin.read.return_value = "x"
        mock_stdout = MagicMock()
        mock_termios.tcgetattr.return_value = [{}]

        with (
            patch("twstock.input_helper._IS_TTY", True),
            patch("twstock.input_helper.HAS_MSVCRT", False),
            patch("twstock.input_helper._is_unix_tty", return_value=True),
            patch("twstock.input_helper.termios", mock_termios),
            patch("twstock.input_helper.tty", mock_tty),
            patch("twstock.input_helper.os.isatty", return_value=True),
            patch("twstock.input_helper.sys.stdin", mock_stdin),
            patch("twstock.input_helper.sys.stdout", mock_stdout),
        ):
            result = get_blocking_key("press: ")
        assert result == "x"
        mock_stdout.write.assert_any_call("press: ")

    def test_fallback_input_when_not_unix_tty(self):
        """HAS_MSVCRT=False + _is_unix_tty=False → falls through to input()."""
        mock_input = MagicMock(return_value="fallback")
        with (
            patch("twstock.input_helper._IS_TTY", True),
            patch("twstock.input_helper.HAS_MSVCRT", False),
            patch("twstock.input_helper._is_unix_tty", return_value=False),
            patch("twstock.input_helper.input", mock_input),
        ):
            result = get_blocking_key("")
        assert result == "fallback"
        mock_input.assert_called_once()


class TestGetBlockingKeyNonTty:
    def test_non_tty_returns_input_strip(self):
        mock_input = MagicMock(return_value="  hello  ")
        with (
            patch("twstock.input_helper._IS_TTY", False),
            patch("twstock.input_helper.input", mock_input),
        ):
            result = get_blocking_key("")
        assert result == "hello"
        mock_input.assert_called_once()
