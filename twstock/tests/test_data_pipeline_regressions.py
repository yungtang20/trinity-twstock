"""Offline regression tests for the repaired ingestion paths."""

from __future__ import annotations

import sqlite3
from unittest.mock import MagicMock, patch

import pandas as pd

from twstock.core.processor import DataProcessor
from twstock.market_data.historical_fetcher import DataFetcher
from twstock.official.institutional import fetch_tpex_institutional, fetch_twse_institutional


class _Response:
    """Small response double for the official API parser."""

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class _NonClosingConnection:
    """Keep an in-memory database available after the writer's finally block."""

    def __init__(self, connection: sqlite3.Connection):
        self._connection = connection

    def __getattr__(self, name):
        return getattr(self._connection, name)

    def close(self):
        pass


def test_datafetcher_maps_finmind_max_min_and_marks_source():
    """Manual FinMind updates must not silently replace high/low with zero."""
    fetcher = DataFetcher(token="test-token")
    fetcher._client = MagicMock()
    fetcher._client.get.return_value = pd.DataFrame(
        [
            {
                "stock_id": "2330",
                "date": "2026-07-20",
                "open": "100",
                "max": "105",
                "min": "99",
                "close": "103",
                "Trading_Volume": "1000000",
                "Trading_money": "103000000",
            }
        ]
    )

    result = fetcher.fetch_history_price("2330")

    assert result.loc[0, "high"] == 105
    assert result.loc[0, "low"] == 99
    assert result.loc[0, "source"] == "finmind"


def test_datafetcher_stock_meta_includes_source():
    """The metadata fetcher must match DataProcessor's six-column contract."""
    fetcher = DataFetcher(token="test-token")
    fetcher._client = MagicMock()
    fetcher._client.get.return_value = pd.DataFrame(
        [
            {
                "stock_id": "2330",
                "stock_name": "台積電",
                "industry_category": "半導體",
                "market": "TSE",
                "type": "COMMON",
            }
        ]
    )

    result = fetcher.fetch_stock_meta()

    assert list(result.columns) == [
        "stock_id",
        "stock_name",
        "industry_category",
        "market",
        "type",
        "source",
    ]
    assert result.loc[0, "source"] == "finmind"


def test_upsert_tdcc_accepts_date_int_and_preserves_tdcc_source():
    """Legacy TDCC date_int payloads must produce a valid TDCC row."""
    from twstock.db_admin import create_tables

    connection = sqlite3.connect(":memory:")
    create_tables(connection)
    connection.commit()
    processor = DataProcessor()
    payload = pd.DataFrame(
        {
            "stock_id": ["2330"],
            "date_int": [20260718],
            "total_shares": [1000000],
            "whale_ratio": [80.0],
            "retail_ratio": [20.0],
            "total_people": [50000],
            "whale_shares": [800000],
            "whale_people": [100],
        }
    )

    with (
        patch("twstock.core.processor.get_connection", return_value=_NonClosingConnection(connection)),
        patch.object(DataProcessor, "_valid_stock_ids", return_value=None),
    ):
        processor.upsert_tdcc(payload)

    row = connection.execute(
        "SELECT date, source, total_shares, whale_ratio, retail_ratio "
        "FROM shareholding_unified WHERE stock_id = '2330'"
    ).fetchone()
    connection.close()

    assert row == ("2026-07-18", "tdcc", 1000000, 80.0, 20.0)


def test_tpex_institutional_keeps_normalized_flow_columns():
    """TPEx parser must retain values needed by the institutional writer."""
    row = [
        "6488",  # stock_id
        "環球晶",  # name
        "1,000",  # g1 foreign buy
        "400",  # g1 foreign sell
        "600",  # g1 net
        "20",  # g2 foreign dealer buy
        "10",  # g2 foreign dealer sell
        "10",  # g2 net
        "1,020",  # g3 foreign total buy
        "410",  # g3 foreign total sell
        "610",  # g3 net
        "200",  # g4 trust buy
        "50",  # g4 trust sell
        "150",  # g4 net
        "120",  # g5 dealer total buy
        "60",  # g5 dealer total sell
        "60",  # g5 net
        "70",  # g6 proprietary buy
        "40",  # g6 proprietary sell
        "30",  # g6 net
        "50",  # g7 hedge buy
        "20",  # g7 hedge sell
        "30",  # g7 net
        "810",  # total net
    ]
    with patch(
        "twstock.official.institutional.retry_get", return_value=_Response({"aaData": [row]})
    ):
        result = fetch_tpex_institutional(20260720)

    assert result.loc[0, "foreign_buy"] == 1000
    assert result.loc[0, "foreign_sell"] == 400
    assert result.loc[0, "trust_buy"] == 200
    assert result.loc[0, "dealer_buy"] == 120
    assert result.loc[0, "dealer_sell"] == 60
    assert result.loc[0, "date"] == "2026-07-20"


def test_twse_institutional_sums_dealer_components():
    fields = [
        "證券代號",
        "外陸資買進股數(不含外資自營商)",
        "外陸資賣出股數(不含外資自營商)",
        "投信買進股數",
        "投信賣出股數",
        "自營商買進股數(自行買賣)",
        "自營商賣出股數(自行買賣)",
        "自營商買進股數(避險)",
        "自營商賣出股數(避險)",
    ]
    payload = {
        "fields": fields,
        "data": [["2330", "1,000", "400", "200", "50", "70", "40", "50", "20"]],
    }
    with patch(
        "twstock.official.institutional.retry_get", return_value=_Response(payload)
    ):
        result = fetch_twse_institutional(20260720)

    assert result.loc[0, "dealer_buy"] == 120
    assert result.loc[0, "dealer_sell"] == 60
