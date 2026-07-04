# -*- coding: utf-8 -*-
"""output_writer.py — 輸出抽象層，分離策略計算與輸出格式。

提供兩個實作：
  - ConsoleWriter: 使用 rich.console.Console 渲染（TUI 模式）
  - JsonWriter: 輸出 JSON 到 stdout（CLI --json 模式）

Usage:
    writer = ConsoleWriter()
    writer.write_result({"strategy": "ma", "score": 85})
    writer.write_error("資料不足")
"""

from __future__ import annotations

import json
import sys
from typing import Protocol, runtime_checkable

from twstock.terminal import console


@runtime_checkable
class OutputWriter(Protocol):
    """**Public API** — 輸出寫入器協定。

    所有策略分析結果的輸出必須透過此協定，不可繞過直接呼叫 rich。
    變更此 Protocol 簽名前，須先檢查 dependency_graph.json 中所有依賴方。
    """

    def write_result(self, data: dict) -> None:
        """寫入策略分析結果。"""
        ...

    def write_error(self, message: str) -> None:
        """寫入錯誤訊息。"""
        ...


class ConsoleWriter:
    """使用 rich Console 輸出（人類可讀格式）。"""

    def __init__(self, output_console=None):
        self._console = output_console or console

    def write_result(self, data: dict) -> None:
        """格式化輸出策略結果。"""
        if not data:
            return

        strategy = data.get("strategy", "unknown")
        stock_id = data.get("stock_id", "")
        status = data.get("status", "ok")

        if status == "no_result":
            self._console.print(f"[yellow]⚠️ {stock_id} 無 {strategy} 分析結果[/yellow]")
            return

        if "error" in data:
            self._console.print(f"[red]❌ {data['error']}[/red]")
            return

        self._console.print(f"[bold cyan]{stock_id} 策略分析結果:[/bold cyan]")
        for key, value in data.items():
            if key in ("strategy", "stock_id", "status", "source"):
                continue
            if isinstance(value, dict):
                self._console.print(f"  [dim]{key}:[/dim]")
                for k, v in value.items():
                    self._console.print(f"    {k}: {v}")
            elif isinstance(value, list):
                self._console.print(f"  [dim]{key}:[/dim] {len(value)} 項")
            else:
                self._console.print(f"  [dim]{key}:[/dim] {value}")

    def write_error(self, message: str) -> None:
        self._console.print(f"[red]❌ {message}[/red]")


class JsonWriter:
    """輸出 JSON 到 stdout（適合 CLI --json 模式）。"""

    def __init__(self, output_stream=None):
        self._stream = output_stream or sys.stdout

    def write_result(self, data: dict) -> None:
        """輸出 JSON 格式結果。"""
        json.dump(data, self._stream, ensure_ascii=False, indent=2)
        self._stream.write("\n")
        self._stream.flush()

    def write_error(self, message: str) -> None:
        """輸出 JSON 格式錯誤。"""
        json.dump({"error": message}, self._stream, ensure_ascii=False)
        self._stream.write("\n")
        self._stream.flush()
