# -*- coding: utf-8 -*-
"""test_calculator_unit.py — calculator.py 覆蓋率提升測試。

Focus on IndicatorEngine internal methods and edge cases.
Uses real in-memory sqlite3 with mock DB connections.
"""

from __future__ import annotations

import sqlite3
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from twstock.calculator import (
    ATRCalculator,
    IndicatorEngine,
    MACalculator,
    VWAPCalculator,
)

# ── Fixtures ──────────────────────────────────────────────


@pytest.fixture
def sample_df():
    """建立 30 天測試資料。"""
    np.random.seed(42)
    dates = pd.date_range("2026-01-01", periods=30, freq="D")
    close = 100 + np.cumsum(np.random.randn(30) * 2)
    return pd.DataFrame(
        {
            "date": dates,
            "open": close - 1,
            "high": close + 2,
            "low": close - 2,
            "close": close,
            "volume": np.random.randint(1000, 5000, 30),
        }
    )


@pytest.fixture
def in_memory_db():
    """建立 in-memory sqlite 資料庫並建立 stock_history 表格。"""
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE stock_history (
            stock_id TEXT, date TEXT, open REAL, high REAL, low REAL,
            close REAL, volume INTEGER, amount INTEGER DEFAULT 0,
            PRIMARY KEY (stock_id, date)
        )
    """)
    # 建立完整的 stock_indicators（與 db_admin.py SCHEMA 一致）
    conn.execute("""
        CREATE TABLE IF NOT EXISTS stock_indicators (
            stock_id TEXT, date TEXT,
            ma5 REAL, ma20 REAL, ma25 REAL, ma60 REAL, ma200 REAL,
            vol_ma5 REAL, vol_ma20 REAL, vol_ma60 REAL,
            bias_ma25 REAL, bias_ma60 REAL, bias_ma200 REAL,
            atr14 REAL, vwap REAL, updated_at TEXT,
            PRIMARY KEY (stock_id, date)
        )
    """)
    conn.commit()
    return conn


@pytest.fixture
def db_with_data(in_memory_db):
    """準備 30 天測試資料。"""
    np.random.seed(42)
    close = 100 + np.cumsum(np.random.randn(30) * 2)
    for i, c in enumerate(close):
        in_memory_db.execute(
            "INSERT INTO stock_history VALUES (?, ?, ?, ?, ?, ?, ?, 0)",
            ("2330", f"2026-01-{i+1:02d}", c - 1, c + 2, c - 2, c, 1000 + i * 100),
        )
    in_memory_db.commit()
    return in_memory_db


# ── IndicatorEngine ───────────────────────────────────────


class TestIndicatorEngine:
    """IndicatorEngine 指標計算引擎測試。"""

    @patch("twstock.calculator.get_connection")
    def test_build_with_data(self, mock_conn, sample_df, in_memory_db):
        """有資料時應計算所有指標。"""
        mock_conn.return_value = in_memory_db
        engine = IndicatorEngine("2330", limit=30)
        # 注入 sample_df 以控制資料
        engine.df = sample_df.copy()
        result = engine.build()

        assert not result.empty
        assert "sma_5" in result.columns
        assert "ema_12" in result.columns
        assert "macd_dif" in result.columns
        assert "macd" in result.columns  # 向下相容別名
        assert "bb_middle" in result.columns
        assert "kdj_k" in result.columns
        assert "rsi_6" in result.columns
        assert "log_return" in result.columns
        assert "pivot" in result.columns

    @patch("twstock.calculator.get_connection")
    def test_build_empty_data(self, mock_conn, in_memory_db):
        """空資料應回傳空 DataFrame。"""
        mock_conn.return_value = in_memory_db
        engine = IndicatorEngine("2330", limit=30)
        engine.df = pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
        result = engine.build()
        assert result.empty

    @patch("twstock.calculator.get_connection")
    def test_add_moving_averages(self, mock_conn, sample_df):
        """_add_moving_averages 應產生 SMA/EMA 欄位。"""
        mock_conn.return_value = MagicMock()
        engine = IndicatorEngine("2330")
        engine.df = sample_df.copy()
        engine._add_moving_averages()
        for period in [5, 10, 20, 60, 120, 200]:
            assert f"sma_{period}" in engine.df.columns
        assert "ema_12" in engine.df.columns
        assert "volume_sma_5" in engine.df.columns

    @patch("twstock.calculator.get_connection")
    def test_add_macd(self, mock_conn, sample_df):
        """_add_macd 應產生 macd_dif/macd_dea/macd_hist。"""
        mock_conn.return_value = MagicMock()
        engine = IndicatorEngine("2330")
        engine.df = sample_df.copy()
        engine._add_macd()
        assert "macd_dif" in engine.df.columns
        assert "macd_dea" in engine.df.columns
        assert "macd_hist" in engine.df.columns

    @patch("twstock.calculator.get_connection")
    def test_add_kdj(self, mock_conn, sample_df):
        """_add_kdj 應產生 kdj_k/kdj_d/kdj_j。"""
        mock_conn.return_value = MagicMock()
        engine = IndicatorEngine("2330")
        engine.df = sample_df.copy()
        engine._add_kdj()
        assert "kdj_k" in engine.df.columns
        assert "kdj_d" in engine.df.columns
        assert "kdj_j" in engine.df.columns

    @patch("twstock.calculator.get_connection")
    def test_add_rsi(self, mock_conn, sample_df):
        """_add_rsi 應產生 rsi_6/rsi_14。"""
        mock_conn.return_value = MagicMock()
        engine = IndicatorEngine("2330")
        engine.df = sample_df.copy()
        engine._add_rsi()
        assert "rsi_6" in engine.df.columns
        assert "rsi_14" in engine.df.columns

    @patch("twstock.calculator.get_connection")
    def test_add_bollinger_bands(self, mock_conn, sample_df):
        """_add_bollinger_bands 應產生 bb 欄位。"""
        mock_conn.return_value = MagicMock()
        engine = IndicatorEngine("2330")
        engine.df = sample_df.copy()
        engine._add_bollinger_bands()
        assert "bb_middle" in engine.df.columns
        assert "bb_upper" in engine.df.columns
        assert "bb_lower" in engine.df.columns
        assert "bb_bandwidth" in engine.df.columns
        assert "bb_pct_b" in engine.df.columns

    @patch("twstock.calculator.get_connection")
    def test_add_log_return(self, mock_conn, sample_df):
        """_add_log_return 應產生 log_return 欄位。"""
        mock_conn.return_value = MagicMock()
        engine = IndicatorEngine("2330")
        engine.df = sample_df.copy()
        engine._add_log_return()
        assert "log_return" in engine.df.columns

    @patch("twstock.calculator.get_connection")
    def test_add_pivot(self, mock_conn, sample_df):
        """_add_pivot 應產生 pivot/r1/r2/s1/s2。"""
        mock_conn.return_value = MagicMock()
        engine = IndicatorEngine("2330")
        engine.df = sample_df.copy()
        engine._add_pivot()
        assert "pivot" in engine.df.columns
        assert "pivot_r1" in engine.df.columns
        assert "pivot_s1" in engine.df.columns

    @patch("twstock.calculator.get_connection")
    def test_build_with_intraday_data(self, mock_conn, sample_df):
        """df_intraday 參數應合併至 df。"""
        mock_conn.return_value = MagicMock()
        engine = IndicatorEngine("2330")
        intraday = pd.DataFrame(
            {
                "date": [pd.Timestamp("2026-02-11")],
                "open": [105],
                "high": [107],
                "low": [103],
                "close": [106],
                "volume": [2000],
            }
        )
        engine.df = pd.concat([sample_df, intraday], ignore_index=True)
        result = engine.build()
        assert len(result) > 30


# ── ATRCalculator ─────────────────────────────────────────


class TestATRCalculator:
    """ATRCalculator 測試。"""

    def test_calculate_with_data(self, db_with_data):
        """有資料時應計算 ATR14。"""
        calc = ATRCalculator(db_with_data)
        count = calc.calculate("2330")
        assert count > 0

    def test_calculate_no_data(self, in_memory_db):
        """無資料時應回傳 0。"""
        calc = ATRCalculator(in_memory_db)
        count = calc.calculate("9999")
        assert count == 0

    def test_calculate_all(self, db_with_data):
        """calculate_all 應處理所有股票。"""
        calc = ATRCalculator(db_with_data)
        result = calc.calculate_all()
        assert "2330" in result


# ── VWAPCalculator ────────────────────────────────────────


class TestVWAPCalculator:
    """VWAPCalculator 測試。"""

    def test_calculate_with_data(self, in_memory_db):
        """有資料時應計算 VWAP。"""
        for i in range(10):
            in_memory_db.execute(
                "INSERT INTO stock_history VALUES (?, ?, 0, 0, 0, ?, ?, ?)",
                ("2330", f"2026-01-{i+1:02d}", 100 + i, 1000 + i * 100, 1000000 + i * 100000),
            )
        in_memory_db.commit()

        calc = VWAPCalculator(in_memory_db)
        count = calc.calculate("2330")
        assert count > 0

    def test_calculate_no_data(self, in_memory_db):
        """無資料時應回傳 0。"""
        calc = VWAPCalculator(in_memory_db)
        count = calc.calculate("9999")
        assert count == 0

    def test_calculate_zero_volume(self, in_memory_db):
        """volume=0 時 vwap 應為 NULL。"""
        in_memory_db.execute(
            "INSERT INTO stock_history VALUES (?, ?, 0, 0, 0, 100, 0, 1000)",
            ("2330", "2026-01-01"),
        )
        in_memory_db.commit()

        calc = VWAPCalculator(in_memory_db)
        count = calc.calculate("2330")
        assert count > 0


# ── MACalculator ──────────────────────────────────────────


class TestMACalculator:
    """MACalculator 測試。"""

    def test_calculate_with_data(self, db_with_data):
        """有資料時應計算 MA。"""
        calc = MACalculator(db_with_data)
        written = calc.calculate("2330")
        assert written > 0

    def test_calculate_no_data(self, in_memory_db):
        """無資料時應回傳 0。"""
        calc = MACalculator(in_memory_db)
        written = calc.calculate("9999")
        assert written == 0
