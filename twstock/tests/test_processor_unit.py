# -*- coding: utf-8 -*-
"""test_processor_unit.py — processor.py 覆蓋率提升測試。

使用 in-memory sqlite 測試各 upsert 方法。
"""

from __future__ import annotations

import os
import sqlite3
import sys
from contextlib import contextmanager
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from twstock.core.processor import DataProcessor

# Module-level holder for the "no-close" proxy used by the current test.
# Set by the ``patch_gc`` context-manager fixture below; read by tests
# via ``patch_gc()`` so they don't need to thread an extra fixture param.
_current_patchable = None


class _NonClosingConn:
    """Proxy that delegates everything to a real sqlite3.Connection except close().

    processor.py's upsert methods call conn.close() in a finally block.
    This wrapper lets us pass the in-memory conn through the mocked
    get_connection() without actually closing it, so tests can verify
    the data after the upsert call returns.
    """

    def __init__(self, real_conn: sqlite3.Connection):
        self._real = real_conn

    def __getattr__(self, name):
        return getattr(self._real, name)

    def close(self):
        # no-op: keep the in-memory DB alive for post-upsert assertions
        pass


@pytest.fixture
def in_memory_conn():
    """建立完整的 in-memory sqlite 資料庫（與 db_admin.py SCHEMA 一致）。"""
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from twstock.db_admin import create_tables

    real = sqlite3.connect(":memory:")
    create_tables(real)
    real.commit()
    return real


@contextmanager
def patch_gc(real_conn: sqlite3.Connection):
    """Context manager that patches get_connection() with a no-close proxy.

    Usage::

        with patch_gc(conn):
            proc.upsert_X(df)
        # conn is still open here — safe to query
    """
    proxy = _NonClosingConn(real_conn)
    with patch("twstock.core.processor.get_connection", return_value=proxy):
        yield


class TestDataProcessor:
    """DataProcessor 各 upsert 方法測試。"""

    def test_upsert_history_basic(self, in_memory_conn):
        """基本 history upsert。"""
        proc = DataProcessor.__new__(DataProcessor)
        df = pd.DataFrame(
            {
                "stock_id": ["2330"],
                "date": ["2026-07-02"],
                "open": [100],
                "high": [105],
                "low": [95],
                "close": [102],
                "volume": [1000],
                "amount": [100000],
                "trade_count": [None],
                "spread": [None],
                "source": ["official"],
            }
        )
        with patch_gc(in_memory_conn):
            count = proc.upsert_history(df)
        assert count == 1

    def test_upsert_history_empty(self, in_memory_conn):
        """空 DataFrame 應回傳 0。"""
        proc = DataProcessor.__new__(DataProcessor)
        with patch_gc(in_memory_conn):
            count = proc.upsert_history(pd.DataFrame())
        assert count == 0

    def test_upsert_history_rejects_zero_and_impossible_ohlc(self, in_memory_conn):
        """零價占位列與 high/low 關係錯誤不得寫入日 K。"""
        proc = DataProcessor.__new__(DataProcessor)
        df = pd.DataFrame(
            {
                "stock_id": ["2330", "2330", "2330"],
                "date": ["2026-07-02", "2026-07-03", "2026-07-04"],
                "open": [0, 100, 100],
                "high": [0, 99, 105],
                "low": [0, 95, 95],
                "close": [0, 102, 102],
                "volume": [0, 1000, 1000],
                "amount": [0, 100000, 100000],
            }
        )
        with patch_gc(in_memory_conn):
            count = proc.upsert_history(df)

        assert count == 1
        assert in_memory_conn.execute("SELECT date FROM stock_history").fetchall() == [("2026-07-04",)]

    def test_upsert_history_none(self, in_memory_conn):
        """None 應回傳 0。"""
        proc = DataProcessor.__new__(DataProcessor)
        with patch_gc(in_memory_conn):
            count = proc.upsert_history(None)
        assert count == 0

    def test_upsert_institutional(self, in_memory_conn):
        """institutional_data upsert。"""
        proc = DataProcessor.__new__(DataProcessor)
        df = pd.DataFrame(
            {
                "stock_id": ["2330"],
                "date": ["2026-07-02"],
                "foreign_net": [3000],
                "trust_net": [1000],
                "dealer_net": [500],
                "institutional_net": [4500],
            }
        )
        with patch_gc(in_memory_conn):
            count = proc.upsert_institutional(df)
        assert count == 1

    def test_upsert_tdcc(self, in_memory_conn):
        """TDCC 資料寫入 shareholding_unified。"""
        proc = DataProcessor.__new__(DataProcessor)
        df = pd.DataFrame(
            {
                "stock_id": ["2330"],
                "date": ["2026-07-02"],
                "total_shares": [1000000],
                "whale_ratio": [0.8],
                "retail_ratio": [0.2],
                "total_people": [50000],
                "whale_shares": [800000],
                "whale_people": [100],
            }
        )
        with patch_gc(in_memory_conn):
            proc.upsert_tdcc(df)

    def test_upsert_shareholding(self, in_memory_conn):
        """foreign shareholding 寫入。"""
        proc = DataProcessor.__new__(DataProcessor)
        df = pd.DataFrame(
            {
                "stock_id": ["2330"],
                "date": ["2026-07-02"],
                "foreign_shares": [500000],
                "foreign_ratio": [0.5],
            }
        )
        with patch_gc(in_memory_conn):
            proc.upsert_shareholding(df)

    def test_upsert_dividend_events_empty(self, in_memory_conn):
        """空 dividend 應返回。"""
        proc = DataProcessor.__new__(DataProcessor)
        with patch_gc(in_memory_conn):
            result = proc.upsert_dividend_events(pd.DataFrame())
        assert result is None

    def test_upsert_per_data_empty(self, in_memory_conn):
        """空 per_data 應返回。"""
        proc = DataProcessor.__new__(DataProcessor)
        with patch_gc(in_memory_conn):
            result = proc.upsert_per_data(pd.DataFrame())
        assert result is None

    def test_upsert_meta_empty(self, in_memory_conn):
        """空 meta 應返回。"""
        proc = DataProcessor.__new__(DataProcessor)
        with patch_gc(in_memory_conn):
            result = proc.upsert_meta(pd.DataFrame())
        assert result is None

    def test_upsert_history_with_none_values(self, in_memory_conn):
        """None 值應正確處理。"""
        proc = DataProcessor.__new__(DataProcessor)
        df = pd.DataFrame(
            {
                "stock_id": ["2330"],
                "date": ["2026-07-02"],
                "open": [100],
                "high": [105],
                "low": [95],
                "close": [102],
                "volume": [1000],
                "amount": [100000],
                "trade_count": [np.nan],
                "spread": [np.nan],
                "source": [None],
            }
        )
        with patch_gc(in_memory_conn):
            count = proc.upsert_history(df)
        assert count == 1

    def test_upsert_history_with_source(self, in_memory_conn):
        """指定 source 欄位。"""
        proc = DataProcessor.__new__(DataProcessor)
        df = pd.DataFrame(
            {
                "stock_id": ["2330"],
                "date": ["2026-07-02"],
                "open": [100],
                "high": [105],
                "low": [95],
                "close": [102],
                "volume": [1000],
                "amount": [100000],
                "trade_count": [None],
                "spread": [None],
                "source": ["test"],
            }
        )
        with patch_gc(in_memory_conn):
            count = proc.upsert_history(df)
        assert count == 1

    def test_upsert_history_dropna_close(self, in_memory_conn):
        """close=NaN 應被 drop。"""
        proc = DataProcessor.__new__(DataProcessor)
        df = pd.DataFrame(
            {
                "stock_id": ["2330", "2330"],
                "date": ["2026-07-02", "2026-07-03"],
                "open": [100, 101],
                "high": [105, 106],
                "low": [95, 96],
                "close": [102, np.nan],  # NaN drop
                "volume": [1000, 2000],
                "amount": [100000, 200000],
                "trade_count": [None, None],
                "spread": [None, None],
                "source": ["official", "official"],
            }
        )
        with patch_gc(in_memory_conn):
            count = proc.upsert_history(df)
        # NaN close row 會被 drop
        assert count == 1


# ─────────────────────────────────────────────────────────────────────
# New tests below target uncovered lines reported by baseline coverage.
# ─────────────────────────────────────────────────────────────────────


class TestDataProcessorInit:
    """Test __init__ (line 20)."""

    def test_init_no_op(self, in_memory_conn):
        """__init__ is a no-op; should not raise."""
        proc = DataProcessor()
        assert proc is not None


class TestBatchUpsert:
    """Test _batch_upsert (lines 31-47): INSERT OR REPLACE legacy path."""

    def test_batch_upsert_basic(self, in_memory_conn):
        """_batch_upsert writes rows via INSERT OR REPLACE."""
        df = pd.DataFrame(
            {
                "stock_id": ["2330", "2331"],
                "date": ["2026-07-02", "2026-07-02"],
                "open": [100, 200],
                "high": [105, 210],
                "low": [95, 190],
                "close": [102, 205],
                "volume": [1000, 2000],
                "amount": [100000, 200000],
                "trade_count": [None, None],
                "spread": [None, None],
                "source": ["official", "official"],
            }
        )
        with patch_gc(in_memory_conn):
            count = DataProcessor._batch_upsert("stock_history", df, in_memory_conn)
        assert count == 2

    def test_batch_upsert_empty_dataframe(self, in_memory_conn):
        """Empty df should return 0."""
        count = DataProcessor._batch_upsert("stock_history", pd.DataFrame(), in_memory_conn)
        assert count == 0

    def test_batch_upsert_on_conflict_replaces(self, in_memory_conn):
        """Second call with same PK should replace the row."""
        df1 = pd.DataFrame(
            {
                "stock_id": ["2330"],
                "date": ["2026-07-02"],
                "open": [100],
                "high": [105],
                "low": [95],
                "close": [102],
                "volume": [1000],
                "amount": [100000],
                "trade_count": [None],
                "spread": [None],
                "source": ["v1"],
            }
        )
        df2 = pd.DataFrame(
            {
                "stock_id": ["2330"],
                "date": ["2026-07-02"],
                "open": [110],
                "high": [115],
                "low": [105],
                "close": [112],
                "volume": [2000],
                "amount": [200000],
                "trade_count": [None],
                "spread": [None],
                "source": ["v2"],
            }
        )
        DataProcessor._batch_upsert("stock_history", df1, in_memory_conn)
        DataProcessor._batch_upsert("stock_history", df2, in_memory_conn)
        row = in_memory_conn.execute("SELECT open, source FROM stock_history WHERE stock_id='2330'").fetchone()
        assert row[0] == 110
        assert row[1] == "v2"


class TestUpsertHistoryEdgeCases:
    """Additional upsert_history tests for uncovered lines (56, source default)."""

    def test_upsert_history_source_default_official(self, in_memory_conn):
        """When source column absent, it should default to 'official' (line 56)."""
        proc = DataProcessor.__new__(DataProcessor)
        df = pd.DataFrame(
            {
                "stock_id": ["2330"],
                "date": ["2026-07-02"],
                "open": [100],
                "high": [105],
                "low": [95],
                "close": [102],
                "volume": [1000],
                "amount": [100000],
                # no "source" column — should default to 'official'
            }
        )
        with patch_gc(in_memory_conn):
            count = proc.upsert_history(df)
        assert count == 1
        row = in_memory_conn.execute("SELECT source FROM stock_history WHERE stock_id='2330'").fetchone()
        assert row[0] == "official"

    def test_upsert_history_on_conflict_preserves_existing(self, in_memory_conn):
        """ON CONFLICT should preserve existing non-null columns when excluded is null."""
        proc = DataProcessor.__new__(DataProcessor)
        df1 = pd.DataFrame(
            {
                "stock_id": ["2330"],
                "date": ["2026-07-02"],
                "open": [100],
                "high": [105],
                "low": [95],
                "close": [102],
                "volume": [1000],
                "amount": [100000],
                "trade_count": [123],
                "spread": [10.5],
                "source": ["v1"],
            }
        )
        df2 = pd.DataFrame(
            {
                "stock_id": ["2330"],
                "date": ["2026-07-02"],
                "open": [110],
                "high": [115],
                "low": [105],
                "close": [112],
                "volume": [2000],
                "amount": [200000],
                "trade_count": [None],
                "spread": [None],
                "source": ["v2"],
            }
        )
        with patch_gc(in_memory_conn):
            proc.upsert_history(df1)
            proc.upsert_history(df2)
        row = in_memory_conn.execute("SELECT trade_count, spread FROM stock_history WHERE stock_id='2330'").fetchone()
        # trade_count and spread should be preserved from df1 (CASE WHEN excluded NULL)
        assert row[0] == 123
        assert abs(row[1] - 10.5) < 1e-6


class TestUpsertInstitutionalEdgeCases:
    """Test upsert_institutional None handling (line 102)."""

    def test_upsert_institutional_none(self, in_memory_conn):
        """None input should return 0."""
        proc = DataProcessor.__new__(DataProcessor)
        with patch_gc(in_memory_conn):
            count = proc.upsert_institutional(None)
        assert count == 0

    def test_upsert_institutional_empty(self, in_memory_conn):
        """Empty df should return 0."""
        proc = DataProcessor.__new__(DataProcessor)
        with patch_gc(in_memory_conn):
            count = proc.upsert_institutional(pd.DataFrame())
        assert count == 0

    def test_upsert_institutional_source_default(self, in_memory_conn):
        """When source absent, should default to 'official'."""
        proc = DataProcessor.__new__(DataProcessor)
        df = pd.DataFrame(
            {
                "stock_id": ["2330"],
                "date": ["2026-07-02"],
                "foreign_net": [3000],
                "trust_net": [1000],
                "dealer_net": [500],
                "institutional_net": [4500],
            }
        )
        with patch_gc(in_memory_conn):
            count = proc.upsert_institutional(df)
        assert count == 1
        row = in_memory_conn.execute("SELECT source FROM institutional_data WHERE stock_id='2330'").fetchone()
        assert row[0] == "official"

    def test_upsert_institutional_on_conflict_updates(self, in_memory_conn):
        """ON CONFLICT should update all columns."""
        proc = DataProcessor.__new__(DataProcessor)
        df1 = pd.DataFrame(
            {
                "stock_id": ["2330"],
                "date": ["2026-07-02"],
                "foreign_net": [3000],
                "source": ["v1"],
            }
        )
        df2 = pd.DataFrame(
            {
                "stock_id": ["2330"],
                "date": ["2026-07-02"],
                "foreign_net": [9999],
                "source": ["v2"],
            }
        )
        with patch_gc(in_memory_conn):
            proc.upsert_institutional(df1)
            proc.upsert_institutional(df2)
        row = in_memory_conn.execute(
            "SELECT foreign_net, source FROM institutional_data WHERE stock_id='2330'"
        ).fetchone()
        assert row[0] == 9999
        assert row[1] == "v2"


class TestUpsertTdccEdgeCases:
    """Tests for upsert_tdcc (line 201) and upsert_shareholding (line 221)."""

    def test_upsert_tdcc_empty(self, in_memory_conn):
        """Empty df should return None."""
        proc = DataProcessor.__new__(DataProcessor)
        with patch_gc(in_memory_conn):
            result = proc.upsert_tdcc(pd.DataFrame())
        assert result is None

    def test_upsert_tdcc_source_default(self, in_memory_conn):
        """When source absent, it should default to 'tdcc'."""
        proc = DataProcessor.__new__(DataProcessor)
        df = pd.DataFrame(
            {
                "stock_id": ["2330"],
                "date": ["2026-07-02"],
                "total_shares": [1000000],
                "whale_ratio": [0.8],
                "retail_ratio": [0.2],
                "total_people": [50000],
                "whale_shares": [800000],
                "whale_people": [100],
            }
        )
        with patch_gc(in_memory_conn):
            proc.upsert_tdcc(df)
        row = in_memory_conn.execute("SELECT source FROM shareholding_unified WHERE stock_id='2330'").fetchone()
        assert row[0] == "tdcc"

    def test_upsert_shareholding_empty(self, in_memory_conn):
        """Empty df should return None."""
        proc = DataProcessor.__new__(DataProcessor)
        with patch_gc(in_memory_conn):
            result = proc.upsert_shareholding(pd.DataFrame())
        assert result is None

    def test_upsert_shareholding_sets_source(self, in_memory_conn):
        """Should set source='twse_foreign'."""
        proc = DataProcessor.__new__(DataProcessor)
        df = pd.DataFrame(
            {
                "stock_id": ["2330"],
                "date": ["2026-07-02"],
                "foreign_shares": [500000],
                "foreign_ratio": [0.5],
            }
        )
        with patch_gc(in_memory_conn):
            proc.upsert_shareholding(df)
        row = in_memory_conn.execute(
            "SELECT source, foreign_shares FROM shareholding_unified WHERE stock_id='2330'"
        ).fetchone()
        assert row[0] == "twse_foreign"
        assert row[1] == 500000


class TestUpsertShareholdingUnified:
    """Test upsert_shareholding_unified (lines 238-248)."""

    def test_empty_returns_none(self, in_memory_conn):
        proc = DataProcessor.__new__(DataProcessor)
        with patch_gc(in_memory_conn):
            result = proc.upsert_shareholding_unified(pd.DataFrame())
        assert result is None

    def test_full_row(self, in_memory_conn):
        proc = DataProcessor.__new__(DataProcessor)
        df = pd.DataFrame(
            {
                "stock_id": ["2330"],
                "date": ["2026-07-02"],
                "total_shares": [1000000],
                "whale_ratio": [0.8],
                "retail_ratio": [0.2],
                "foreign_shares": [500000],
                "foreign_ratio": [0.5],
                "total_people": [50000],
                "whale_shares": [800000],
                "whale_people": [100],
                "source": ["tdcc"],
            }
        )
        with patch_gc(in_memory_conn):
            proc.upsert_shareholding_unified(df)
        row = in_memory_conn.execute(
            "SELECT whale_ratio, foreign_shares, total_people FROM shareholding_unified WHERE stock_id='2330'"
        ).fetchone()
        assert abs(row[0] - 0.8) < 1e-6
        assert row[1] == 500000
        assert row[2] == 50000

    def test_on_conflict_preserves_nulls(self, in_memory_conn):
        """Second upsert with NULL should preserve existing values (CASE WHEN logic)."""
        proc = DataProcessor.__new__(DataProcessor)
        df1 = pd.DataFrame(
            {
                "stock_id": ["2330"],
                "date": ["2026-07-02"],
                "total_shares": [1000000],
                "whale_ratio": [0.8],
                "retail_ratio": [0.2],
                "foreign_shares": [500000],
                "foreign_ratio": [0.5],
                "total_people": [50000],
                "whale_shares": [800000],
                "whale_people": [100],
                "source": ["tdcc"],
            }
        )
        df2 = pd.DataFrame(
            {
                "stock_id": ["2330"],
                "date": ["2026-07-02"],
                "total_shares": [1100000],  # only total_shares updated
                "source": ["tdcc"],
            }
        )
        with patch_gc(in_memory_conn):
            proc.upsert_shareholding_unified(df1)
            proc.upsert_shareholding_unified(df2)
        row = in_memory_conn.execute(
            "SELECT total_shares, whale_ratio, foreign_shares FROM shareholding_unified WHERE stock_id='2330'"
        ).fetchone()
        assert row[0] == 1100000
        assert abs(row[1] - 0.8) < 1e-6  # preserved across upsert
        assert row[2] == 500000  # preserved across upsert


class TestUpsertDividendEvents:
    """Test upsert_dividend_events (lines 258-291)."""

    def test_dividend_events_full(self, in_memory_conn):
        """Full row insert."""
        proc = DataProcessor.__new__(DataProcessor)
        df = pd.DataFrame(
            {
                "stock_id": ["2330"],
                "date": ["2026-07-02"],
                "before_price": [100.0],
                "after_price": [95.0],
                "reference_price": [98.0],
                "cash_dividend": [5.0],
                "stock_dividend": [0.0],
                "source": ["official"],
            }
        )
        with patch_gc(in_memory_conn):
            proc.upsert_dividend_events(df)
        row = in_memory_conn.execute(
            "SELECT before_price, after_price, reference_price, cash_dividend, stock_dividend, source "
            "FROM dividend_events WHERE stock_id='2330'"
        ).fetchone()
        assert row[0] == 100.0
        assert row[1] == 95.0
        assert row[2] == 98.0
        assert row[3] == 5.0
        assert row[4] == 0.0
        assert row[5] == "official"

    def test_dividend_events_on_conflict_updates(self, in_memory_conn):
        """ON CONFLICT should update price columns."""
        proc = DataProcessor.__new__(DataProcessor)
        df1 = pd.DataFrame(
            {
                "stock_id": ["2330"],
                "date": ["2026-07-02"],
                "before_price": [100.0],
                "after_price": [95.0],
                "reference_price": [98.0],
                "cash_dividend": [5.0],
                "stock_dividend": [0.0],
                "source": ["v1"],
            }
        )
        df2 = pd.DataFrame(
            {
                "stock_id": ["2330"],
                "date": ["2026-07-02"],
                "before_price": [110.0],
                "after_price": [105.0],
                "reference_price": [108.0],
                "cash_dividend": [6.0],
                "stock_dividend": [0.5],
                "source": ["v2"],
            }
        )
        with patch_gc(in_memory_conn):
            proc.upsert_dividend_events(df1)
            proc.upsert_dividend_events(df2)
        row = in_memory_conn.execute(
            "SELECT before_price, cash_dividend, source FROM dividend_events WHERE stock_id='2330'"
        ).fetchone()
        assert row[0] == 110.0
        assert row[1] == 6.0
        assert row[2] == "v2"

    def test_dividend_events_preserves_null_prices(self, in_memory_conn):
        """NULL excluded prices should preserve existing values (CASE WHEN excluded IS NOT NULL)."""
        proc = DataProcessor.__new__(DataProcessor)
        df1 = pd.DataFrame(
            {
                "stock_id": ["2330"],
                "date": ["2026-07-02"],
                "before_price": [100.0],
                "after_price": [95.0],
                "reference_price": [98.0],
                "cash_dividend": [5.0],
                "stock_dividend": [0.0],
                "source": ["v1"],
            }
        )
        df2 = pd.DataFrame(
            {
                "stock_id": ["2330"],
                "date": ["2026-07-02"],
                "before_price": [np.nan],
                "after_price": [np.nan],
                "reference_price": [np.nan],
                "cash_dividend": [np.nan],
                "stock_dividend": [np.nan],
                "source": ["v2"],
            }
        )
        with patch_gc(in_memory_conn):
            proc.upsert_dividend_events(df1)
            proc.upsert_dividend_events(df2)
        row = in_memory_conn.execute(
            "SELECT before_price, after_price FROM dividend_events WHERE stock_id='2330'"
        ).fetchone()
        assert row[0] == 100.0
        assert row[1] == 95.0


class TestUpsertPerData:
    """Test upsert_per_data (lines 297-339)."""

    def test_per_data_basic(self, in_memory_conn):
        """Basic insert."""
        proc = DataProcessor.__new__(DataProcessor)
        df = pd.DataFrame(
            {
                "stock_id": ["2330"],
                "date": ["2026-07-02"],
                "per": [20.0],
                "pbr": [2.0],
                "pe_ratio": [20.0],
                "pb_ratio": [2.0],
                "dividend_yield": [3.0],
                "source": ["official"],
            }
        )
        with patch_gc(in_memory_conn):
            proc.upsert_per_data(df)
        row = in_memory_conn.execute(
            "SELECT per, pbr, pe_ratio, pb_ratio, dividend_yield FROM per_data WHERE stock_id='2330'"
        ).fetchone()
        assert row[0] == 20.0
        assert row[1] == 2.0
        assert row[2] == 20.0
        assert row[3] == 2.0
        assert row[4] == 3.0

    def test_per_data_alias_per_to_pe_ratio(self, in_memory_conn):
        """When 'per' present but 'pe_ratio' absent, should alias (line 299-300).

        NOTE: per_data's upsert SQL always binds 8 columns
        (stock_id, date, per, pbr, pe_ratio, pb_ratio, dividend_yield, source),
        so the test DataFrame must include every one of them.
        """
        proc = DataProcessor.__new__(DataProcessor)
        df = pd.DataFrame(
            {
                "stock_id": ["2330"],
                "date": ["2026-07-02"],
                "per": [25.0],
                "pbr": [2.5],
                "dividend_yield": [3.0],
                "source": ["official"],
            }
        )
        with patch_gc(in_memory_conn):
            proc.upsert_per_data(df)
        row = in_memory_conn.execute("SELECT per, pe_ratio FROM per_data WHERE stock_id='2330'").fetchone()
        assert row[0] == 25.0
        assert row[1] == 25.0  # aliased from per

    def test_per_data_alias_pbr_to_pb_ratio(self, in_memory_conn):
        """When 'pbr' present but 'pb_ratio' absent, should alias (line 304-305)."""
        proc = DataProcessor.__new__(DataProcessor)
        df = pd.DataFrame(
            {
                "stock_id": ["2330"],
                "date": ["2026-07-02"],
                "per": [20.0],
                "pbr": [3.0],
                "dividend_yield": [3.0],
                "source": ["official"],
            }
        )
        with patch_gc(in_memory_conn):
            proc.upsert_per_data(df)
        row = in_memory_conn.execute("SELECT pbr, pb_ratio FROM per_data WHERE stock_id='2330'").fetchone()
        assert row[0] == 3.0
        assert row[1] == 3.0  # aliased from pbr

    def test_per_data_on_conflict_preserves_nulls(self, in_memory_conn):
        """NULL excluded columns should preserve existing values."""
        proc = DataProcessor.__new__(DataProcessor)
        df1 = pd.DataFrame(
            {
                "stock_id": ["2330"],
                "date": ["2026-07-02"],
                "per": [20.0],
                "pbr": [2.0],
                "dividend_yield": [3.0],
                "source": ["v1"],
            }
        )
        df2 = pd.DataFrame(
            {
                "stock_id": ["2330"],
                "date": ["2026-07-02"],
                "per": [None],
                "pbr": [2.5],
                "dividend_yield": [3.0],
                "source": ["v2"],
            }
        )
        with patch_gc(in_memory_conn):
            proc.upsert_per_data(df1)
            proc.upsert_per_data(df2)
        row = in_memory_conn.execute("SELECT per, pbr FROM per_data WHERE stock_id='2330'").fetchone()
        assert row[0] == 20.0  # preserved
        assert row[1] == 2.5  # updated


class TestUpsertMeta:
    """Test upsert_meta (lines 347-374)."""

    def test_meta_basic(self, in_memory_conn):
        """Basic insert."""
        proc = DataProcessor.__new__(DataProcessor)
        df = pd.DataFrame(
            {
                "stock_id": ["2330"],
                "stock_name": "台積電",
                "industry_category": "半導體",
                "market": "TSE",
                "type": "COMMON",
                "source": ["official"],
            }
        )
        with patch_gc(in_memory_conn):
            proc.upsert_meta(df)
        row = in_memory_conn.execute(
            "SELECT stock_name, industry_category, market, type, source " "FROM stock_meta WHERE stock_id='2330'"
        ).fetchone()
        assert row[0] == "台積電"
        assert row[1] == "半導體"
        assert row[2] == "TSE"
        assert row[3] == "COMMON"
        assert row[4] == "official"

    def test_meta_on_conflict_updates(self, in_memory_conn):
        """ON CONFLICT should update name and industry."""
        proc = DataProcessor.__new__(DataProcessor)
        df1 = pd.DataFrame(
            {
                "stock_id": ["2330"],
                "stock_name": "台積電",
                "industry_category": "半導體",
                "market": "TSE",
                "type": "COMMON",
                "source": ["v1"],
            }
        )
        df2 = pd.DataFrame(
            {
                "stock_id": ["2330"],
                "stock_name": "TSMC",
                "industry_category": "Chip",
                "market": "TSE",
                "type": "COMMON",
                "source": ["v2"],
            }
        )
        with patch_gc(in_memory_conn):
            proc.upsert_meta(df1)
            proc.upsert_meta(df2)
        row = in_memory_conn.execute(
            "SELECT stock_name, industry_category FROM stock_meta WHERE stock_id='2330'"
        ).fetchone()
        assert row[0] == "TSMC"
        assert row[1] == "Chip"

    def test_meta_empty_string_guard(self, in_memory_conn):
        """Empty-string excluded values should NOT overwrite existing (line 361-364)."""
        proc = DataProcessor.__new__(DataProcessor)
        df1 = pd.DataFrame(
            {
                "stock_id": ["2330"],
                "stock_name": "台積電",
                "industry_category": "半導體",
                "market": "TSE",
                "type": "COMMON",
                "source": ["v1"],
            }
        )
        df2 = pd.DataFrame(
            {
                "stock_id": ["2330"],
                "stock_name": "",
                "industry_category": "",
                "market": "",
                "type": "",
                "source": ["v2"],
            }
        )
        with patch_gc(in_memory_conn):
            proc.upsert_meta(df1)
            proc.upsert_meta(df2)
        row = in_memory_conn.execute(
            "SELECT stock_name, industry_category, market, type FROM stock_meta WHERE stock_id='2330'"
        ).fetchone()
        # Empty strings should NOT overwrite existing values
        assert row[0] == "台積電"
        assert row[1] == "半導體"
        assert row[2] == "TSE"
        assert row[3] == "COMMON"


class TestMainGuard:
    """Test __main__ guard (line 378)."""

    def test_main_guard(self, tmp_path):
        """Running the module as __main__ prints the success message (line 378).

        We simulate ``python -m twstock.core.processor`` by writing a small runner
        that inserts the project root on sys.path, then runs the module file
        under the ``__main__`` entry-point.
        """
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # 專案根目錄（twstock 的父目錄）— 讓 from twstock.xxx 能解析
        repo_root = os.path.dirname(project_root)
        processor_src = os.path.join(project_root, "core", "processor.py")
        runner = tmp_path / "_main_runner.py"
        runner.write_text(
            "import runpy, sys\n"
            f"sys.path.insert(0, {repo_root!r})\n"
            f"sys.path.insert(0, {project_root!r})\n"
            f"runpy.run_path({processor_src!r}, run_name='__main__')\n",
            encoding="utf-8",
        )
        import subprocess

        result = subprocess.run(
            [sys.executable, str(runner)],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert "loaded successfully" in result.stdout

    def test_module_import_does_not_run_main(self):
        """Importing processor should not trigger the __main__ block."""
        import twstock.core.processor as proc_mod

        # The module should have __name__ == 'twstock.core.processor', not '__main__'
        assert proc_mod.__name__ == "twstock.core.processor"
        # The reference print exists in source — just verify module is importable
        assert hasattr(proc_mod, "DataProcessor")


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__, "-v"]))
