# -*- coding: utf-8 -*-
"""test_strategy_utils.py — strategy._utils 單元測試。"""

from __future__ import annotations

import os
import sqlite3
from unittest.mock import MagicMock, patch

from twstock.strategy import _utils


class TestGetStockName:
    def test_returns_name_from_db(self):
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = ("台積電",)
        assert _utils.get_stock_name(conn, "2330") == "台積電"

    def test_fallback_when_no_row(self):
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = None
        assert _utils.get_stock_name(conn, "2330", {"2330": "TSMC"}) == "TSMC"

    def test_dash_when_no_fallback(self):
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = None
        assert _utils.get_stock_name(conn, "2330") == "-"

    def test_dash_when_exception(self):
        conn = MagicMock()
        conn.execute.side_effect = sqlite3.OperationalError("no such table")
        assert _utils.get_stock_name(conn, "2330", {"2330": "TSMC"}) == "TSMC"


class TestRenderHeader:
    def test_default_header_with_console(self):
        console = MagicMock()
        with patch(
            "twstock.strategy._utils.os.get_terminal_size", return_value=os.terminal_size((80, 24))
        ):
            _utils.render_header("My Title", console=console)
        console.print.assert_called()

    def test_detail_header_with_console(self):
        console = MagicMock()
        with patch(
            "twstock.strategy._utils.os.get_terminal_size", return_value=os.terminal_size((80, 24))
        ):
            _utils.render_header("Detail", is_detail=True, console=console)
        console.print.assert_called()

    def test_fallback_width(self):
        console = MagicMock()
        with patch("twstock.strategy._utils.os.get_terminal_size", side_effect=OSError):
            _utils.render_header("Title", console=console)
        console.print.assert_called()


class TestFetchKlines:
    def test_basic_fetch(self, tmp_path):
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("""CREATE TABLE klines_indicators (
            stock_id TEXT, date TEXT, open REAL, high REAL, low REAL,
            close REAL, volume INTEGER, amount REAL
        )""")
        conn.executemany(
            "INSERT INTO klines_indicators VALUES (?,?,?,?,?,?,?,?)",
            [
                ("2330", "2025-01-01", 100, 110, 95, 105, 1000, 105000),
                ("2330", "2025-01-02", 105, 115, 100, 110, 2000, 220000),
                ("2330", "2025-01-03", 110, 120, 108, 118, 1500, 177000),
            ],
        )
        conn.commit()

        df = _utils.fetch_klines(conn, "2330", limit=512)
        assert len(df) == 3
        assert list(df.columns) == ["date", "open", "high", "low", "close", "volume"]
        # Sorted ascending
        assert df["date"].is_monotonic_increasing
        conn.close()

    def test_include_amount(self, tmp_path):
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("""CREATE TABLE klines_indicators (
            stock_id TEXT, date TEXT, open REAL, high REAL, low REAL,
            close REAL, volume INTEGER, amount REAL
        )""")
        conn.execute(
            "INSERT INTO klines_indicators VALUES (?,?,?,?,?,?,?,?)",
            ("2330", "2025-01-01", 100, 110, 95, 105, 1000, 105000),
        )
        conn.commit()

        df = _utils.fetch_klines(conn, "2330", include_amount=True)
        assert "amount" in df.columns
        conn.close()

    def test_limit_applied(self, tmp_path):
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("""CREATE TABLE klines_indicators (
            stock_id TEXT, date TEXT, open REAL, high REAL, low REAL,
            close REAL, volume INTEGER
        )""")
        for i in range(10):
            conn.execute(
                "INSERT INTO klines_indicators VALUES (?,?,?,?,?,?,?)",
                ("2330", f"2025-01-{i+1:02d}", 100, 110, 95, 105, 1000),
            )
        conn.commit()

        df = _utils.fetch_klines(conn, "2330", limit=5)
        assert len(df) == 5
        conn.close()
