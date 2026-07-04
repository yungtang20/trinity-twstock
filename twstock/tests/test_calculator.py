# -*- coding: utf-8 -*-
"""test_calculator.py — calculator.py 覆蓋率測試。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from twstock.calculator import ATRCalculator, IndicatorEngine, VWAPCalculator


class TestIndicatorEngine:
    """IndicatorEngine 指標計算引擎。"""

    @patch("twstock.calculator.MACalculator")
    @patch("twstock.calculator.VWAPCalculator")
    @patch("twstock.calculator.ATRCalculator")
    def test_build_with_empty_data(self, mock_atr, mock_vwap, mock_ma):
        """空 DataFrame 不應崩潰。"""
        engine = IndicatorEngine("2330")
        engine.df = __import__("pandas").DataFrame()  # 空的
        result = engine.build()
        assert result is not None

    def test_init_stores_stock_id(self):
        """建構子應儲存 stock_id。"""
        engine = IndicatorEngine("2330", limit=100)
        assert engine.stock_id == "2330"


class TestATRCalculator:
    """ATRCCalculator 平均真實波幅。"""

    @patch("twstock.calculator.get_connection")
    def test_calculate_all_empty(self, mock_conn):
        """無資料時不應崩潰。"""
        mock_ctx = MagicMock()
        mock_ctx.execute.return_value.fetchall.return_value = []
        mock_conn.return_value.__enter__ = MagicMock(return_value=mock_ctx)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        calc = ATRCalculator.__new__(ATRCalculator)
        calc.db = mock_ctx
        # 不應拋異常
        calc.calculate_all()


class TestVWAPCalculator:
    """VWAPCalculator 成交量加權平均價。"""

    @patch("twstock.calculator.get_connection")
    def test_calculate_all_empty(self, mock_conn):
        """無資料時不應崩潰。"""
        mock_ctx = MagicMock()
        mock_ctx.execute.return_value.fetchall.return_value = []
        mock_conn.return_value.__enter__ = MagicMock(return_value=mock_ctx)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        calc = VWAPCalculator.__new__(VWAPCalculator)
        calc.db = mock_ctx
        calc.calculate_all()
