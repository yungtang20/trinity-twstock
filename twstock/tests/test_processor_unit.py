# -*- coding: utf-8 -*-
"""test_processor_unit.py — processor.py 覆蓋率提升測試。

使用 in-memory sqlite 測試各 upsert 方法。
"""
from __future__ import annotations

import sqlite3
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from twstock.processor import DataProcessor


@pytest.fixture
def in_memory_conn():
    """建立完整的 in-memory sqlite 資料庫（與 db_admin.py SCHEMA 一致）。"""
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from db_admin import create_tables

    conn = sqlite3.connect(":memory:")
    create_tables(conn)
    conn.commit()
    return conn


class TestDataProcessor:
    """DataProcessor 各 upsert 方法測試。"""

    def test_upsert_history_basic(self, in_memory_conn):
        """基本 history upsert。"""
        proc = DataProcessor.__new__(DataProcessor)
        df = pd.DataFrame({
            "stock_id": ["2330"],
            "date": ["2026-07-02"],
            "open": [100], "high": [105], "low": [95],
            "close": [102], "volume": [1000], "amount": [100000],
            "trade_count": [None], "spread": [None], "source": ["official"],
        })
        with patch("twstock.processor.get_connection", return_value=in_memory_conn):
            count = proc.upsert_history(df)
        assert count == 1

    def test_upsert_history_empty(self, in_memory_conn):
        """空 DataFrame 應回傳 0。"""
        proc = DataProcessor.__new__(DataProcessor)
        with patch("twstock.processor.get_connection", return_value=in_memory_conn):
            count = proc.upsert_history(pd.DataFrame())
        assert count == 0

    def test_upsert_history_none(self, in_memory_conn):
        """None 應回傳 0。"""
        proc = DataProcessor.__new__(DataProcessor)
        with patch("twstock.processor.get_connection", return_value=in_memory_conn):
            count = proc.upsert_history(None)
        assert count == 0

    def test_upsert_institutional(self, in_memory_conn):
        """institutional_data upsert。"""
        proc = DataProcessor.__new__(DataProcessor)
        df = pd.DataFrame({
            "stock_id": ["2330"],
            "date": ["2026-07-02"],
            "foreign_net": [3000],
            "trust_net": [1000],
            "dealer_net": [500],
            "institutional_net": [4500],
        })
        with patch("twstock.processor.get_connection", return_value=in_memory_conn):
            count = proc.upsert_institutional(df)
        assert count == 1

    def test_upsert_tdcc(self, in_memory_conn):
        """TDCC 資料寫入 shareholding_unified。"""
        proc = DataProcessor.__new__(DataProcessor)
        df = pd.DataFrame({
            "stock_id": ["2330"],
            "date": ["2026-07-02"],
            "total_shares": [1000000],
            "whale_ratio": [0.8],
            "retail_ratio": [0.2],
            "total_people": [50000],
            "whale_shares": [800000],
            "whale_people": [100],
        })
        with patch("twstock.processor.get_connection", return_value=in_memory_conn):
            proc.upsert_tdcc(df)

    def test_upsert_shareholding(self, in_memory_conn):
        """foreign shareholding 寫入。"""
        proc = DataProcessor.__new__(DataProcessor)
        df = pd.DataFrame({
            "stock_id": ["2330"],
            "date": ["2026-07-02"],
            "foreign_shares": [500000],
            "foreign_ratio": [0.5],
        })
        with patch("twstock.processor.get_connection", return_value=in_memory_conn):
            proc.upsert_shareholding(df)

    def test_upsert_dividend_events_empty(self, in_memory_conn):
        """空 dividend 應返回。"""
        proc = DataProcessor.__new__(DataProcessor)
        with patch("twstock.processor.get_connection", return_value=in_memory_conn):
            result = proc.upsert_dividend_events(pd.DataFrame())
        assert result is None

    def test_upsert_per_data_empty(self, in_memory_conn):
        """空 per_data 應返回。"""
        proc = DataProcessor.__new__(DataProcessor)
        with patch("twstock.processor.get_connection", return_value=in_memory_conn):
            result = proc.upsert_per_data(pd.DataFrame())
        assert result is None

    def test_upsert_meta_empty(self, in_memory_conn):
        """空 meta 應返回。"""
        proc = DataProcessor.__new__(DataProcessor)
        with patch("twstock.processor.get_connection", return_value=in_memory_conn):
            result = proc.upsert_meta(pd.DataFrame())
        assert result is None

    def test_upsert_history_with_none_values(self, in_memory_conn):
        """None 值應正確處理。"""
        import numpy as np
        proc = DataProcessor.__new__(DataProcessor)
        df = pd.DataFrame({
            "stock_id": ["2330"],
            "date": ["2026-07-02"],
            "open": [100], "high": [105], "low": [95],
            "close": [102], "volume": [1000], "amount": [100000],
            "trade_count": [np.nan], "spread": [np.nan], "source": [None],
        })
        with patch("twstock.processor.get_connection", return_value=in_memory_conn):
            count = proc.upsert_history(df)
        assert count == 1

    def test_upsert_history_with_source(self, in_memory_conn):
        """指定 source 欄位。"""
        proc = DataProcessor.__new__(DataProcessor)
        df = pd.DataFrame({
            "stock_id": ["2330"],
            "date": ["2026-07-02"],
            "open": [100], "high": [105], "low": [95],
            "close": [102], "volume": [1000], "amount": [100000],
            "trade_count": [None], "spread": [None], "source": ["test"],
        })
        with patch("twstock.processor.get_connection", return_value=in_memory_conn):
            count = proc.upsert_history(df)
        assert count == 1

    def test_upsert_history_dropna_close(self, in_memory_conn):
        """close=NaN 應被 drop。"""
        proc = DataProcessor.__new__(DataProcessor)
        import numpy as np
        df = pd.DataFrame({
            "stock_id": ["2330", "2330"],
            "date": ["2026-07-02", "2026-07-03"],
            "open": [100, 101], "high": [105, 106], "low": [95, 96],
            "close": [102, np.nan],  # NaN drop
            "volume": [1000, 2000], "amount": [100000, 200000],
            "trade_count": [None, None], "spread": [None, None], "source": ["official", "official"],
        })
        with patch("twstock.processor.get_connection", return_value=in_memory_conn):
            count = proc.upsert_history(df)
        # NaN close row 會被 drop
        assert count == 1


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
