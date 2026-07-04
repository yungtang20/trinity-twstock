# -*- coding: utf-8 -*-
"""test_input_provider.py — tui/input_provider.py 測試。

測試 MockInputProvider（主要使用者）。
Windows/Unix 實作為 thin wrapper，僅驗證接口契約。
"""
from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from twstock.tui.input_provider import (
    MockInputProvider,
    InputProvider,
    create_default_provider,
    _WindowsInputProvider,
    _UnixInputProvider,
)


class TestMockInputProvider:
    """MockInputProvider 測試。"""

    def test_get_key_sequential(self):
        """應按順序回傳預設按鍵。"""
        provider = MockInputProvider(["a", "b", "c"])
        assert provider.get_key() == "a"
        assert provider.get_key() == "b"
        assert provider.get_key() == "c"

    def test_get_key_exhausted_returns_empty(self):
        """用完後應回傳空字串。"""
        provider = MockInputProvider(["a"])
        provider.get_key()
        assert provider.get_key() == ""

    def test_get_key_with_prompt(self):
        """應記錄 prompt。"""
        provider = MockInputProvider(["1"])
        provider.get_key("🔍 選擇: ")
        assert len(provider.prompts) == 1
        assert "選擇" in provider.prompts[0]

    def test_kbhit_true_when_keys_available(self):
        """有按鍵時 kbhit 應回傳 True。"""
        provider = MockInputProvider(["a", "b"])
        assert provider.kbhit() is True

    def test_kbhit_false_when_exhausted(self):
        """無按鍵時 kbhit 應回傳 False。"""
        provider = MockInputProvider(["a"])
        provider.get_key()
        assert provider.kbhit() is False

    def test_kbhit_empty(self):
        """空序列 kbhit 應回傳 False。"""
        provider = MockInputProvider()
        assert provider.kbhit() is False

    def test_flush_no_error(self):
        """flush 不應拋異常。"""
        provider = MockInputProvider()
        provider.flush()

    def test_protocol_compliance(self):
        """應滿足 InputProvider 協定。"""
        provider = MockInputProvider()
        assert isinstance(provider, InputProvider)


class TestCreateDefaultProvider:
    """create_default_provider 測試。"""

    def test_returns_provider(self):
        """應回傳 InputProvider 實作。"""
        provider = create_default_provider()
        assert isinstance(provider, InputProvider)

    def test_has_required_methods(self):
        """應有所有必要方法。"""
        provider = create_default_provider()
        assert hasattr(provider, "get_key")
        assert hasattr(provider, "kbhit")
        assert hasattr(provider, "flush")


class TestCreateDefaultProvider:
    """
    create_default_provider 聽測平台分支（這裡只驗證非 Windows 路徑；
    Windows 路徑因 msvcrt 已存在，不易 mock import）。
    """

    def test_non_windows_returns_unix_provider(self):
        from twstock.tui.input_provider import create_default_provider, _UnixInputProvider
        with patch("twstock.tui.input_provider.sys") as mock_sys:
            mock_sys.platform = "linux"
            provider = create_default_provider()
            assert isinstance(provider, _UnixInputProvider)

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-only test")
    def test_windows_returns_windows_provider(self):
        from twstock.tui.input_provider import create_default_provider, _WindowsInputProvider
        provider = create_default_provider()
        assert isinstance(provider, _WindowsInputProvider)
