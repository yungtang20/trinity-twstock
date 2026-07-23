# -*- coding: utf-8 -*-
"""test_official_dividend_crawler.py — official/dividend_crawler.py 覆蓋率測試。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from twstock.official import dividend_crawler

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_response(json_payload):
    """Build a fake `requests`-like response exposing ``.json()``."""
    return SimpleNamespace(json=lambda: json_payload)


# ---------------------------------------------------------------------------
# Pure helpers — no mocking
# ---------------------------------------------------------------------------


class TestConvertDate:
    """_convert_date 測試。"""

    def test_yyyymmdd_format(self):
        """YYYYMMDD 格式應正確轉YYYY-MM-DD。"""
        assert dividend_crawler._convert_date("20260702", "YYYYMMDD") == "2026-07-02"

    def test_roc_format(self):
        """YYY/MM/DD 格式應轉成西元年。"""
        assert dividend_crawler._convert_date("115/07/02", "YYY/MM/DD") == "2026-07-02"

    def test_unknown_format_fallback_passthrough(self):
        """未知格式應直接回傳原字串。"""
        assert dividend_crawler._convert_date("2026-07-02", "anything") == "2026-07-02"

    def test_empty_string(self):
        """空字串應直接回傳。"""
        assert dividend_crawler._convert_date("", "unknown") == ""


class TestConvertRocToAd:
    """_convert_roc_to_ad 測試。"""

    def test_slash_format(self):
        """斜線 yyyy/mm/dd 格式轉換。"""
        assert dividend_crawler._convert_roc_to_ad("115/07/02") == "2026-07-02"

    def test_chinese_format(self):
        """中文 yyyy年mm月dd日 格式轉換。"""
        assert dividend_crawler._convert_roc_to_ad("115年07月02日") == "2026-07-02"

    def test_single_digit_month_day_checks_padded(self):
        """個位數月/日應補零。"""
        assert dividend_crawler._convert_roc_to_ad("115/7/2") == "2026-07-02"

    def test_bad_input_returns_none(self):
        """不合法字串應回傳 None。"""
        assert dividend_crawler._convert_roc_to_ad("garbage") is None

    def test_empty_returns_none(self):
        """空字串應回傳 None。"""
        assert dividend_crawler._convert_roc_to_ad("") is None


class TestConvertPercent:
    """_convert_percent 測試。"""

    def test_none(self):
        """None → 0.0。"""
        assert dividend_crawler._convert_percent(None) == 0.0

    def test_zero_string(self):
        """'0' → 0.0。"""
        assert dividend_crawler._convert_percent("0") == 0.0

    def test_empty_string(self):
        """'' → 0.0。"""
        assert dividend_crawler._convert_percent("") == 0.0

    def test_comma_separated(self):
        """含逗號的字串應正確轉 float。"""
        assert dividend_crawler._convert_percent("1,234.5") == 1234.5

    def test_normal_float_string(self):
        """一般浮點數字串。"""
        assert dividend_crawler._convert_percent("12.34") == 12.34

    def test_garbage_returns_zero(self):
        """無法解析字串 → 0.0。"""
        assert dividend_crawler._convert_percent("abc") == 0.0


# ---------------------------------------------------------------------------
# TWSE fetch with mocked retry_get
# ---------------------------------------------------------------------------


class TestFetchTwseDividendEvents:
    """fetch_twse_dividend_events 測試。"""

    @patch("twstock.official.dividend_crawler.retry_get")
    def test_empty_data_returns_empty(self, mock_retry_get):
        """API 回傳無資料時應回傳空 DataFrame。"""
        mock_retry_get.return_value = _fake_response({"data": None})
        result = dividend_crawler.fetch_twse_dividend_events("2026-01-01", "2026-07-01")
        assert isinstance(result, pd.DataFrame)
        assert result.empty

    @patch("twstock.official.dividend_crawler.retry_get")
    def test_cash_dividend_branch(self, mock_retry_get):
        """q_x 含「息」應歸為現金股利。"""
        payload = {
            "data": [
                ["115/07/02", "2330", "台積電", "1,080.0", "1,070.0", "5.0", "息"],
            ]
        }
        mock_retry_get.return_value = _fake_response(payload)
        df = dividend_crawler.fetch_twse_dividend_events("2026-07-01", "2026-07-03")
        assert len(df) == 1
        row = df.iloc[0]
        assert row["stock_id"] == "2330"
        assert row["event_date"] == "2026-07-02"
        assert row["cash_dividend"] == 5.0
        assert row["stock_dividend"] == 0.0
        assert row["source"] == "twse"

    @patch("twstock.official.dividend_crawler.retry_get")
    def test_stock_dividend_branch(self, mock_retry_get):
        """q_x 含「權」且 after_price > 0 應計算股票股利。"""
        payload = {
            "data": [
                ["115/07/02", "2330", "台積電", "1,080.0", "1,070.0", "0", "權"],
            ]
        }
        mock_retry_get.return_value = _fake_response(payload)
        df = dividend_crawler.fetch_twse_dividend_events("2026-07-01", "2026-07-03")
        assert len(df) == 1
        row = df.iloc[0]
        assert row["cash_dividend"] == 0.0
        expected_stk = (1080.0 / 1070.0 - 1.0) * 10.0
        assert row["stock_dividend"] == pytest.approx(expected_stk)

    @patch("twstock.official.dividend_crawler.retry_get")
    def test_stock_dividend_after_price_zero_skipped(self, mock_retry_get):
        """after_price == 0 時股票股利應為 0（不計算）。"""
        payload = {
            "data": [
                ["115/07/02", "2330", "台積電", "1,080.0", "0", "0", "權"],
            ]
        }
        mock_retry_get.return_value = _fake_response(payload)
        df = dividend_crawler.fetch_twse_dividend_events("2026-07-01", "2026-07-03")
        assert len(df) == 1
        assert df.iloc[0]["stock_dividend"] == 0.0

    @patch("twstock.official.dividend_crawler.retry_get")
    def test_invalid_row_too_short_skipped(self, mock_retry_get):
        """row 長度 < 7 應被跳過。"""
        payload = {
            "data": [
                ["115/07/02", "2330", "台積電"],  # too short
            ]
        }
        mock_retry_get.return_value = _fake_response(payload)
        df = dividend_crawler.fetch_twse_dividend_events("2026-07-01", "2026-07-03")
        assert df.empty

    @patch("twstock.official.dividend_crawler.retry_get")
    def test_invalid_date_skipped(self, mock_retry_get):
        """無法解析的日期應被跳過。"""
        payload = {
            "data": [
                ["garbage", "2330", "台積電", "100", "100", "0", "息"],
            ]
        }
        mock_retry_get.return_value = _fake_response(payload)
        df = dividend_crawler.fetch_twse_dividend_events("2026-07-01", "2026-07-03")
        assert df.empty


# ---------------------------------------------------------------------------
# TPEx fetch with mocked retry_get
# ---------------------------------------------------------------------------


class TestFetchTpexDividendEvents:
    """fetch_tpex_dividend_events 測試。"""

    @patch("twstock.official.dividend_crawler.retry_get")
    def test_short_row_skipped(self, mock_retry_get):
        """row 長度 < 15 應被跳過。"""
        # 15 個元素（index 0-14）
        table_payload = {
            "tables": [
                {
                    "data": [
                        ["115/07/02", "5387", "ografia", "20.0", "19.5"] + ["0"] * 10,
                    ]
                }
            ]
        }
        # row 只有 14 個
        table_payload["tables"][0]["data"][0] = table_payload["tables"][0]["data"][0][:14]
        mock_retry_get.return_value = _fake_response(table_payload)
        df = dividend_crawler.fetch_tpex_dividend_events("2026-07-01", "2026-07-03")
        assert df.empty

    @patch("twstock.official.dividend_crawler.retry_get")
    def test_empty_tables_returns_empty(self, mock_retry_get):
        """空 tables 應回傳空 DataFrame。"""
        mock_retry_get.return_value = _fake_response({"tables": []})
        df = dividend_crawler.fetch_tpex_dividend_events("2026-07-01", "2026-07-03")
        assert df.empty

    @patch("twstock.official.dividend_crawler.retry_get")
    def test_normal_parse(self, mock_retry_get):
        """正常 row 應正確解析現金/股票股利。"""
        row = (
            ["115/07/02", "5387", "ografia", "20.0", "19.5"]
            + ["0"] * 8
            + ["2.0", "50.0"]  # idx 13 cash, idx 14 stock (/100)
            + ["x"]  # pad to 16 elements so len >= 15
        )
        table_payload = {"tables": [{"data": [row]}]}
        mock_retry_get.return_value = _fake_response(table_payload)
        df = dividend_crawler.fetch_tpex_dividend_events("2026-07-01", "2026-07-03")
        assert len(df) == 1
        r = df.iloc[0]
        assert r["stock_id"] == "5387"
        assert r["event_date"] == "2026-07-02"
        assert r["cash_dividend"] == 2.0
        assert r["stock_dividend"] == pytest.approx(50.0 / 100.0)
        assert r["source"] == "tpex"


# ---------------------------------------------------------------------------
# Unified fetch_dividend_events
# ---------------------------------------------------------------------------


class TestFetchDividendEvents:
    """fetch_dividend_events 測試。"""

    @patch("twstock.official.dividend_crawler.FINMIND_AVAILABLE", False)
    @patch("twstock.official.dividend_crawler.fetch_tpex_dividend_events")
    @patch("twstock.official.dividend_crawler.fetch_twse_dividend_events")
    def test_both_empty_no_fallback(self, mock_twse, mock_tpex):
        """API 皆空且 FINMIND_AVAILABLE=False 應回傳空 DataFrame。"""
        mock_twse.return_value = pd.DataFrame()
        mock_tpex.return_value = pd.DataFrame()
        df = dividend_crawler.fetch_dividend_events("2026-01-01", "2026-07-01")
        assert isinstance(df, pd.DataFrame)
        assert df.empty

    @patch("twstock.official.dividend_crawler.FINMIND_AVAILABLE", True)
    @patch("twstock.official.dividend_crawler.DataFetcher")
    @patch("twstock.official.dividend_crawler.fetch_tpex_dividend_events")
    @patch("twstock.official.dividend_crawler.fetch_twse_dividend_events")
    def test_finmind_fallback_branch(self, mock_twse, mock_tpex, mock_fetcher_cls):
        """API 皆空且 FINMIND_AVAILABLE 時應走 FinMind fallback 分支。"""
        mock_twse.return_value = pd.DataFrame()
        mock_tpex.return_value = pd.DataFrame()

        mock_fetcher = MagicMock()
        empty_meta = pd.DataFrame()
        mock_fetcher.fetch_stock_meta.return_value = empty_meta
        mock_fetcher_cls.return_value = mock_fetcher

        df = dividend_crawler.fetch_dividend_events("2026-01-01", "2026-07-01")
        assert isinstance(df, pd.DataFrame)
        mock_fetcher.fetch_stock_meta.assert_called_once()

    @patch("twstock.official.dividend_crawler.fetch_tpex_dividend_events")
    @patch("twstock.official.dividend_crawler.fetch_twse_dividend_events")
    def test_non_empty_renames_and_dedups(self, mock_twse, mock_tpex):
        """有資料時應將 event_date 改名、並依 stock_id+date 去重。"""
        twse_df = pd.DataFrame(
            [
                {
                    "stock_id": "2330",
                    "event_date": "2026-07-02",
                    "cash_dividend": 1.0,
                    "stock_dividend": 0.0,
                    "before_price": 100.0,
                    "after_price": 99.0,
                    "reference_price": 99.0,
                    "source": "twse",
                },
                {
                    "stock_id": "2330",
                    "event_date": "2026-07-02",
                    "cash_dividend": 1.0,
                    "stock_dividend": 0.0,
                    "before_price": 100.0,
                    "after_price": 99.0,
                    "reference_price": 99.0,
                    "source": "twse",
                },
            ]
        )
        mock_twse.return_value = twse_df
        mock_tpex.return_value = pd.DataFrame()
        df = dividend_crawler.fetch_dividend_events("2026-07-01", "2026-07-03")
        assert "date" in df.columns
        assert "event_date" not in df.columns
        assert len(df) == 1

    @patch("twstock.official.dividend_crawler.get_finmind_token", return_value="token")
    @patch("twstock.official.dividend_crawler.DividendFetcher")
    @patch("twstock.official.dividend_crawler.DataFetcher")
    @patch("twstock.official.dividend_crawler.fetch_tpex_dividend_events")
    @patch("twstock.official.dividend_crawler.fetch_twse_dividend_events")
    def test_finmind_fallback_uses_dividend_fetcher(
        self, mock_twse, mock_tpex, mock_data_cls, mock_dividend_cls, _mock_token
    ):
        """Regression: DataFetcher has no fetch_dividend method."""
        mock_twse.return_value = pd.DataFrame()
        mock_tpex.return_value = pd.DataFrame()
        mock_data_cls.return_value.fetch_stock_meta.return_value = pd.DataFrame(
            [{"stock_id": "2330"}, {"stock_id": "2317"}]
        )
        dividend = mock_dividend_cls.return_value
        dividend.fetch_dividend.side_effect = [
            {
                "data": [
                    {
                        "stock_id": "2330",
                        "date": "2026-07-01",
                        "beforeDividend": 100,
                        "afterDividend": 95,
                        "reference": 95,
                        "CashDividend": 5,
                        "StockDividend": 0,
                    }
                ]
            },
            {"data": []},
        ]
        dividend._transform.return_value = [
            {
                "stock_id": "2330",
                "date": "2026-07-01",
                "cash_dividend": 5.0,
                "stock_dividend": 0.0,
                "source": "finmind",
            }
        ]

        with patch.object(dividend_crawler, "FINMIND_AVAILABLE", True):
            result = dividend_crawler.fetch_dividend_events("2026-01-01", "2026-07-01")

        assert len(result) == 1
        assert result.iloc[0]["stock_id"] == "2330"
        assert dividend.fetch_dividend.call_count == 2


# ---------------------------------------------------------------------------
# upsert_dividend_events
# ---------------------------------------------------------------------------


class TestUpsertDividendEvents:
    """upsert_dividend_events 測試。"""

    def test_none_returns_early(self):
        """None 輸入應直接回傳、不拋錯。"""
        assert dividend_crawler.upsert_dividend_events(None) is None  # type: ignore[arg-type]

    def test_empty_returns_early(self):
        """空 DataFrame 輸入應直接回傳。"""
        assert dividend_crawler.upsert_dividend_events(pd.DataFrame()) is None

    @patch("twstock.core.processor.DataProcessor")
    def test_happy_path_bulk(self, mock_processor_cls):
        """資料完整時應走批量 upsert 路徑。"""
        mock_processor = MagicMock()
        mock_processor.upsert_dividend_events.return_value = 3
        mock_processor_cls.return_value = mock_processor

        df = pd.DataFrame(
            [
                {
                    "stock_id": "2330",
                    "event_date": "2026-07-02",
                    "cash_dividend": 1.0,
                    "stock_dividend": 0.0,
                    "before_price": 100.0,
                    "after_price": 99.0,
                    "reference_price": 99.0,
                    "source": "twse",
                },
            ]
        )
        dividend_crawler.upsert_dividend_events(df)
        mock_processor_cls.assert_called_once()
        mock_processor.upsert_dividend_events.assert_called_once()
        passed_df = mock_processor.upsert_dividend_events.call_args[0][0]
        assert "date" in passed_df.columns
        assert "event_date" not in passed_df.columns

    @patch("twstock.core.processor.DataProcessor")
    def test_missing_columns_get_defaulted(self, mock_processor_cls):
        """缺少 before/after/reference/source 欄位時應補預設值。"""
        mock_processor = MagicMock()
        mock_processor.upsert_dividend_events.return_value = 1
        mock_processor_cls.return_value = mock_processor

        df = pd.DataFrame(
            [
                {
                    "stock_id": "2330",
                    "event_date": "2026-07-02",
                    "cash_dividend": 1.0,
                    "stock_dividend": 0.0,
                },
            ]
        )
        dividend_crawler.upsert_dividend_events(df)
        passed_df = mock_processor.upsert_dividend_events.call_args[0][0]
        for col in ("before_price", "after_price", "reference_price", "source"):
            assert col in passed_df.columns
        assert passed_df.iloc[0]["source"] == "official"
