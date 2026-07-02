# -*- coding: utf-8 -*-
"""test_output_writer.py — OutputWriter 協定與實作測試。"""
from __future__ import annotations

import io
import json
from unittest.mock import MagicMock, patch

import pytest

from twstock.output_writer import ConsoleWriter, JsonWriter


# ── ConsoleWriter ──────────────────────────────────────────


class TestConsoleWriter:
    """ConsoleWriter 使用 rich Console 渲染結果。"""

    def test_write_result_basic(self, capsys):
        """基本結果輸出應包含 stock_id 與策略名稱。"""
        mock_console = MagicMock()
        writer = ConsoleWriter(output_console=mock_console)

        data = {
            "strategy": "ma",
            "stock_id": "2330",
            "status": "ok",
            "score": 85,
        }
        writer.write_result(data)

        # 驗證有呼叫 console.print
        assert mock_console.print.called
        output = " ".join(str(call) for call in mock_console.print.call_args_list)
        assert "2330" in output

    def test_write_result_empty(self):
        """空資料不應崩潰。"""
        mock_console = MagicMock()
        writer = ConsoleWriter(output_console=mock_console)
        writer.write_result({})
        # 空 dict 直接 return，不呼叫 print
        mock_console.print.assert_not_called()

    def test_write_result_no_result_status(self):
        """status=no_result 應顯示警告。"""
        mock_console = MagicMock()
        writer = ConsoleWriter(output_console=mock_console)

        data = {"strategy": "chips", "stock_id": "2330", "status": "no_result"}
        writer.write_result(data)

        output = " ".join(str(call) for call in mock_console.print.call_args_list)
        assert "2330" in output
        assert "chips" in output

    def test_write_result_with_error(self):
        """包含 error 欄位應顯示錯誤。"""
        mock_console = MagicMock()
        writer = ConsoleWriter(output_console=mock_console)

        data = {"error": "資料不足"}
        writer.write_result(data)

        output = " ".join(str(call) for call in mock_console.print.call_args_list)
        assert "資料不足" in output

    def test_write_result_with_nested_dict(self):
        """巢狀 dict 應能處理。"""
        mock_console = MagicMock()
        writer = ConsoleWriter(output_console=mock_console)

        data = {
            "strategy": "sr",
            "stock_id": "2330",
            "levels": {"support": 100, "resistance": 120},
        }
        writer.write_result(data)
        assert mock_console.print.called

    def test_write_result_with_list(self):
        """list 值應顯示長度。"""
        mock_console = MagicMock()
        writer = ConsoleWriter(output_console=mock_console)

        data = {"strategy": "ma", "stock_id": "2330", "predictions": [1, 2, 3]}
        writer.write_result(data)

        output = " ".join(str(call) for call in mock_console.print.call_args_list)
        assert "3 項" in output

    def test_write_error(self):
        """write_error 應輸出錯誤訊息。"""
        mock_console = MagicMock()
        writer = ConsoleWriter(output_console=mock_console)

        writer.write_error("連線失敗")

        output = " ".join(str(call) for call in mock_console.print.call_args_list)
        assert "連線失敗" in output


# ── JsonWriter ─────────────────────────────────────────────


class TestJsonWriter:
    """JsonWriter 輸出合法 JSON 到 stream。"""

    def test_write_result_outputs_valid_json(self):
        """write_result 應輸出合法 JSON。"""
        stream = io.StringIO()
        writer = JsonWriter(output_stream=stream)

        data = {"strategy": "ma", "stock_id": "2330", "score": 85}
        writer.write_result(data)

        output = stream.getvalue()
        parsed = json.loads(output.strip())
        assert parsed["strategy"] == "ma"
        assert parsed["stock_id"] == "2330"
        assert parsed["score"] == 85

    def test_write_result_unicode(self):
        """Unicode 字元不應被 escape。"""
        stream = io.StringIO()
        writer = JsonWriter(output_stream=stream)

        data = {"strategy": "ma", "label": "看多"}
        writer.write_result(data)

        output = stream.getvalue()
        assert "看多" in output  # 不應被 escape 成 看多

    def test_write_error_outputs_json(self):
        """write_error 應輸出 JSON 格式錯誤。"""
        stream = io.StringIO()
        writer = JsonWriter(output_stream=stream)

        writer.write_error("資料不足")

        output = stream.getvalue()
        parsed = json.loads(output.strip())
        assert "error" in parsed
        assert parsed["error"] == "資料不足"

    def test_write_result_multiple_calls(self):
        """多次寫入應產生多行 JSON。"""
        stream = io.StringIO()
        writer = JsonWriter(output_stream=stream)

        writer.write_result({"a": 1})
        writer.write_result({"b": 2})

        lines = stream.getvalue().strip().split("\n")
        # 每次寫入一行（含 indent=2 可能多行，但這裡是單行 dict）
        assert len(lines) >= 2


# ── Protocol 契約 ──────────────────────────────────────────


class TestOutputWriterProtocol:
    """驗證 OutputWriter 協定契約。"""

    def test_console_writer_satisfies_protocol(self):
        """ConsoleWriter 應滿足 OutputWriter 協定。"""
        from twstock.output_writer import OutputWriter

        writer = ConsoleWriter()
        assert isinstance(writer, OutputWriter)

    def test_json_writer_satisfies_protocol(self):
        """JsonWriter 應滿足 OutputWriter 協定。"""
        from twstock.output_writer import OutputWriter

        writer = JsonWriter()
        assert isinstance(writer, OutputWriter)
