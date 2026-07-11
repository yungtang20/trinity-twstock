# -*- coding: utf-8 -*-
"""test_official_updater.py - official/updater.py coverage tests."""

from __future__ import annotations

from datetime import datetime as _dt
from unittest.mock import MagicMock, patch

import pandas as pd

from twstock.official import updater


class TestUpsertDataframe:
    """upsert_dataframe tests."""

    @patch("twstock.official.updater.PROCESSOR_AVAILABLE", True)
    @patch("twstock.official.updater.DataProcessor")
    def test_stock_history_basic(self, mock_proc):
        df = pd.DataFrame(
            {
                "stock_id": ["2330"],
                "date": ["2026-07-02"],
                "open": [100],
                "high": [105],
                "low": [95],
                "close": [102],
                "volume": [1000],
            }
        )
        updater.upsert_dataframe("stock_history", df)
        mock_proc.return_value.upsert_history.assert_called_once()

    @patch("twstock.official.updater.PROCESSOR_AVAILABLE", True)
    @patch("twstock.official.updater.DataProcessor")
    def test_stock_history_with_turnover(self, mock_proc):
        df = pd.DataFrame(
            {
                "stock_id": ["2330"],
                "date": ["2026-07-02"],
                "open": [100],
                "high": [105],
                "low": [95],
                "close": [102],
                "volume": [1000],
                "turnover": [1000000],
            }
        )
        updater.upsert_dataframe("stock_history", df)
        mock_proc.return_value.upsert_history.assert_called_once()

    @patch("twstock.official.updater.PROCESSOR_AVAILABLE", True)
    @patch("twstock.official.updater.DataProcessor")
    def test_stock_history_code_rename(self, mock_proc):
        df = pd.DataFrame(
            {
                "code": ["2330"],
                "date": ["2026-07-02"],
                "open": [100],
                "close": [102],
            }
        )
        updater.upsert_dataframe("stock_history", df)

    @patch("twstock.official.updater.PROCESSOR_AVAILABLE", True)
    @patch("twstock.official.updater.DataProcessor")
    def test_stock_history_date_int(self, mock_proc):
        df = pd.DataFrame(
            {
                "stock_id": ["2330"],
                "date_int": [20260702],
                "open": [100],
                "close": [102],
            }
        )
        updater.upsert_dataframe("stock_history", df)

    @patch("twstock.official.updater.PROCESSOR_AVAILABLE", True)
    @patch("twstock.official.updater.DataProcessor")
    def test_institutional_data(self, mock_proc):
        df = pd.DataFrame(
            {
                "stock_id": ["2330"],
                "date": ["2026-07-02"],
                "foreign_buy": [8000],
                "foreign_sell": [5000],
                "trust_buy": [2000],
                "trust_sell": [1000],
                "dealer_buy": [1500],
                "dealer_sell": [1200],
            }
        )
        updater.upsert_dataframe("institutional_data", df)
        mock_proc.return_value.upsert_institutional.assert_called_once()

    @patch("twstock.official.updater.PROCESSOR_AVAILABLE", True)
    @patch("twstock.official.updater.DataProcessor")
    def test_shareholding_unified(self, mock_proc):
        df = pd.DataFrame(
            {
                "stock_id": ["2330"],
                "date": ["2026-07-02"],
                "total_shares": [1000000],
                "whale_ratio": [0.8],
                "total_people": [50000],
                "whale_shares": [800000],
            }
        )
        updater.upsert_dataframe("shareholding_unified", df)
        mock_proc.return_value.upsert_shareholding.assert_called_once()

    def test_unknown_table(self):
        df = pd.DataFrame({"test": [1]})
        updater.upsert_dataframe("unknown_table", df)

    def test_empty_dataframe(self):
        updater.upsert_dataframe("stock_history", pd.DataFrame())

    @patch("twstock.official.updater.PROCESSOR_AVAILABLE", False)
    def test_processor_unavailable(self):
        df = pd.DataFrame(
            {
                "stock_id": ["2330"],
                "date": ["2026-07-02"],
                "open": [100],
                "close": [102],
            }
        )
        updater.upsert_dataframe("stock_history", df)


class TestUpsertDataframeEdgeCases:
    """Extra branch coverage."""

    @patch("twstock.official.updater.PROCESSOR_AVAILABLE", True)
    @patch("twstock.official.updater.DataProcessor")
    def test_code_column_renamed(self, mock_proc):
        df = pd.DataFrame({"code": ["2330"], "date": ["2026-07-02"], "open": [100], "close": [102]})
        updater.upsert_dataframe("stock_history", df)
        called_df = mock_proc.return_value.upsert_history.call_args[0][0]
        assert "stock_id" in called_df.columns
        assert "code" not in called_df.columns

    @patch("twstock.official.updater.PROCESSOR_AVAILABLE", True)
    @patch("twstock.official.updater.DataProcessor")
    def test_date_int_becomes_date(self, mock_proc):
        df = pd.DataFrame(
            {"stock_id": ["2330"], "date_int": [20260702], "open": [100], "close": [102]}
        )
        updater.upsert_dataframe("stock_history", df)
        called_df = mock_proc.return_value.upsert_history.call_args[0][0]
        assert "date" in called_df.columns
        assert called_df["date"].iloc[0] == "2026-07-02"

    @patch("twstock.official.updater.PROCESSOR_AVAILABLE", True)
    @patch("twstock.official.updater.DataProcessor")
    def test_turnover_to_amount(self, mock_proc):
        df = pd.DataFrame(
            {
                "stock_id": ["2330"],
                "date": ["2026-07-02"],
                "open": [100],
                "close": [102],
                "turnover": [999],
            }
        )
        updater.upsert_dataframe("stock_history", df)
        called_df = mock_proc.return_value.upsert_history.call_args[0][0]
        assert "amount" in called_df.columns
        assert called_df["amount"].iloc[0] == 999

    def test_unknown_returns_none(self):
        assert updater.upsert_dataframe("weird", pd.DataFrame({"x": [1]})) is None

    def test_empty_returns_none(self):
        assert updater.upsert_dataframe("stock_history", pd.DataFrame()) is None

    @patch("twstock.official.updater.PROCESSOR_AVAILABLE", False)
    def test_unavailable_returns_none(self):
        df = pd.DataFrame(
            {"stock_id": ["2330"], "date": ["2026-07-02"], "open": [100], "close": [102]}
        )
        assert updater.upsert_dataframe("stock_history", df) is None


class TestUpdateDividendEvents:
    @patch("twstock.official.updater.upsert_dividend_events")
    @patch("twstock.official.updater.fetch_dividend_events")
    def test_with_events(self, mock_fetch, mock_upsert):
        mock_fetch.return_value = pd.DataFrame({"stock_id": ["2330"], "date": ["2026-07-02"]})
        updater.update_dividend_events_for_date_range("2026-01-01", "2026-07-02")
        mock_upsert.assert_called_once()

    @patch("twstock.official.updater.upsert_dividend_events")
    @patch("twstock.official.updater.fetch_dividend_events")
    def test_no_events(self, mock_fetch, mock_upsert):
        mock_fetch.return_value = pd.DataFrame()
        updater.update_dividend_events_for_date_range("2026-01-01", "2026-07-02")
        mock_upsert.assert_not_called()

    @patch("twstock.official.updater.upsert_dividend_events")
    @patch("twstock.official.updater.fetch_dividend_events")
    def test_returns_ids(self, mock_fetch, mock_upsert):
        mock_fetch.return_value = pd.DataFrame(
            {
                "stock_id": ["2330", "2330", "2317"],
                "date": ["2026-07-02", "2026-07-02", "2026-08-01"],
            }
        )
        result = updater.update_dividend_events_for_date_range("2026-01-01", "2026-12-31")
        assert result == ["2330", "2317"]

    @patch("twstock.official.updater.upsert_dividend_events")
    @patch("twstock.official.updater.fetch_dividend_events")
    def test_returns_empty(self, mock_fetch, mock_upsert):
        mock_fetch.return_value = pd.DataFrame()
        assert updater.update_dividend_events_for_date_range("2026-01-01", "2026-12-31") == []


class TestAutoUpdateTdcc:
    @patch("twstock.official.updater.update_tdcc_weekly")
    @patch("twstock.official.updater.get_connection")
    def test_stale(self, mock_conn, mock_weekly):
        cursor = MagicMock()
        cursor.fetchone.return_value = ["2026-06-01"]
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_conn.return_value = conn
        updater._auto_update_tdcc()
        mock_weekly.assert_called_once()

    @patch("twstock.official.updater.update_tdcc_weekly")
    @patch("twstock.official.updater.get_connection")
    def test_fresh(self, mock_conn, mock_weekly):
        cursor = MagicMock()
        cursor.fetchone.return_value = ["2099-12-31"]
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_conn.return_value = conn
        updater._auto_update_tdcc()
        mock_weekly.assert_not_called()

    @patch("twstock.official.updater.update_tdcc_weekly")
    @patch("twstock.official.updater.get_connection")
    def test_none(self, mock_conn, mock_weekly):
        cursor = MagicMock()
        cursor.fetchone.return_value = [None]
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_conn.return_value = conn
        updater._auto_update_tdcc()
        mock_weekly.assert_called_once()

    @patch("twstock.official.updater.update_tdcc_weekly")
    @patch("twstock.official.updater.get_connection")
    def test_exception(self, mock_conn, mock_weekly):
        mock_conn.side_effect = RuntimeError("boom")
        updater._auto_update_tdcc()
        mock_weekly.assert_not_called()


class TestUpdateTdcc:
    @patch("twstock.official.updater.upsert_dataframe")
    @patch("twstock.official.updater.tdcc.fetch_tdcc_historical")
    def test_weekly(self, mock_fetch, mock_upsert):
        fake = pd.DataFrame({"stock_id": ["2330"], "date": ["2026-07-02"]})
        mock_fetch.return_value = fake
        updater.update_tdcc_weekly()
        mock_fetch.assert_called_once_with(weeks=1)
        mock_upsert.assert_called_once_with("shareholding_unified", fake)

    @patch("twstock.official.updater.upsert_dataframe")
    @patch("twstock.official.updater.tdcc.fetch_tdcc_historical")
    def test_historical_default(self, mock_fetch, mock_upsert):
        fake = pd.DataFrame({"stock_id": ["2330"], "date": ["2026-07-02"]})
        mock_fetch.return_value = fake
        updater.update_tdcc_historical()
        mock_fetch.assert_called_once_with(weeks=1)
        mock_upsert.assert_called_once_with("shareholding_unified", fake)

    @patch("twstock.official.updater.upsert_dataframe")
    @patch("twstock.official.updater.tdcc.fetch_tdcc_historical")
    def test_historical_custom(self, mock_fetch, mock_upsert):
        fake = pd.DataFrame({"stock_id": ["2330"], "date": ["2026-07-02"]})
        mock_fetch.return_value = fake
        updater.update_tdcc_historical(weeks=4)
        mock_fetch.assert_called_once_with(weeks=4)
        mock_upsert.assert_called_once_with("shareholding_unified", fake)

    @patch("twstock.official.updater.upsert_dataframe")
    @patch("twstock.official.updater.tdcc.fetch_tdcc_historical")
    def test_empty(self, mock_fetch, mock_upsert):
        mock_fetch.return_value = pd.DataFrame()
        updater.update_tdcc_historical(weeks=2)
        mock_fetch.assert_called_once_with(weeks=2)
        mock_upsert.assert_not_called()


class TestUpdateOfficialDaily:
    """update_official_daily with all downstream deps mocked."""

    @staticmethod
    def _quote():
        return pd.DataFrame(
            {
                "stock_id": ["2330"],
                "name": ["TSMC"],
                "volume": [1000],
                "amount": [50000],
                "open": [100],
                "high": [105],
                "low": [95],
                "close": [102],
                "date": ["2026-07-02"],
                "market": ["TSE"],
            }
        )

    @staticmethod
    def _inst():
        return pd.DataFrame(
            {
                "stock_id": ["2330"],
                "date": ["2026-07-02"],
                "foreign_buy": [10],
                "foreign_sell": [5],
                "trust_buy": [3],
                "trust_sell": [1],
                "dealer_buy": [2],
                "dealer_sell": [1],
            }
        )

    @staticmethod
    def _conn():
        c = MagicMock()
        c.fetchone.return_value = [1]
        m = MagicMock()
        m.cursor.return_value = c
        return m

    @patch("twstock.official.updater._auto_update_tdcc")
    @patch("twstock.official.updater.update_dividend_events_for_date_range")
    @patch("twstock.official.updater.upsert_dataframe")
    @patch("twstock.official.updater.quotes.update_stock_meta_from_df")
    @patch("twstock.official.updater.quotes.fetch_tpex_quotes")
    @patch("twstock.official.updater.quotes.fetch_twse_quotes")
    @patch("twstock.official.updater.institutional.fetch_all_institutional")
    @patch("twstock.official.updater.get_connection")
    @patch("twstock.official.updater.cal.init_trading_calendar")
    @patch("twstock.official.updater.cal.get_last_trading_day", return_value=20260702)
    @patch("twstock.official.updater.cal._int_to_date")
    @patch("twstock.official.updater.cal.is_trading_day", return_value=True)
    @patch("twstock.official.updater.cal.date_exists_in_history", return_value=True)
    @patch("twstock.official.updater.cal._date_to_int", return_value=20260702)
    def test_date_int_none(
        self,
        mock_d2i,
        mock_exists,
        mock_is_td,
        mock_i2d,
        mock_last_td,
        mock_init,
        mock_conn,
        mock_inst,
        mock_twse,
        mock_tpex,
        mock_meta,
        mock_upsert,
        mock_div,
        mock_tdcc,
    ):
        mock_i2d.return_value = _dt(2026, 7, 2)
        mock_conn.return_value = self._conn()
        mock_twse.return_value = self._quote()
        mock_tpex.return_value = self._quote()
        mock_inst.return_value = self._inst()
        updater.update_official_daily(date_int=None, days=1, force=False, auto_tdcc=False)
        mock_last_td.assert_called_once()

    @patch("twstock.official.updater._auto_update_tdcc")
    @patch("twstock.official.updater.update_dividend_events_for_date_range")
    @patch("twstock.official.updater.upsert_dataframe")
    @patch("twstock.official.updater.quotes.update_stock_meta_from_df")
    @patch("twstock.official.updater.quotes.fetch_tpex_quotes")
    @patch("twstock.official.updater.quotes.fetch_twse_quotes")
    @patch("twstock.official.updater.institutional.fetch_all_institutional")
    @patch("twstock.official.updater.get_connection")
    @patch("twstock.official.updater.cal.init_trading_calendar")
    @patch("twstock.official.updater.cal.get_last_trading_day", return_value=20260702)
    @patch("twstock.official.updater.cal._int_to_date")
    @patch("twstock.official.updater.cal.is_trading_day", return_value=True)
    @patch("twstock.official.updater.cal.date_exists_in_history", return_value=True)
    @patch("twstock.official.updater.cal._date_to_int", return_value=20260702)
    def test_invalid_date_int(
        self,
        mock_d2i,
        mock_exists,
        mock_is_td,
        mock_i2d,
        mock_last_td,
        mock_init,
        mock_conn,
        mock_inst,
        mock_twse,
        mock_tpex,
        mock_meta,
        mock_upsert,
        mock_div,
        mock_tdcc,
    ):
        mock_i2d.return_value = None
        mock_conn.return_value = self._conn()
        updater.update_official_daily(date_int=99999999, days=1, force=False, auto_tdcc=False)
        mock_twse.assert_not_called()

    @patch("twstock.official.updater._auto_update_tdcc")
    @patch("twstock.official.updater.update_dividend_events_for_date_range")
    @patch("twstock.official.updater.upsert_dataframe")
    @patch("twstock.official.updater.quotes.update_stock_meta_from_df")
    @patch("twstock.official.updater.quotes.fetch_tpex_quotes")
    @patch("twstock.official.updater.quotes.fetch_twse_quotes")
    @patch("twstock.official.updater.institutional.fetch_all_institutional")
    @patch("twstock.official.updater.get_connection")
    @patch("twstock.official.updater.cal.init_trading_calendar")
    @patch("twstock.official.updater.cal.get_last_trading_day", return_value=20260702)
    @patch("twstock.official.updater.cal._int_to_date")
    @patch("twstock.official.updater.cal.is_trading_day")
    @patch("twstock.official.updater.cal.date_exists_in_history", return_value=True)
    @patch("twstock.official.updater.cal._date_to_int", return_value=20260702)
    def test_non_trading_day(
        self,
        mock_d2i,
        mock_exists,
        mock_is_td,
        mock_i2d,
        mock_last_td,
        mock_init,
        mock_conn,
        mock_inst,
        mock_twse,
        mock_tpex,
        mock_meta,
        mock_upsert,
        mock_div,
        mock_tdcc,
    ):
        mock_i2d.return_value = _dt(2026, 7, 2)
        mock_is_td.side_effect = [False, False, False, True] + [True] * 20
        mock_conn.return_value = self._conn()
        mock_twse.return_value = self._quote()
        mock_tpex.return_value = self._quote()
        mock_inst.return_value = self._inst()
        updater.update_official_daily(date_int=20260702, days=1, force=False, auto_tdcc=False)
        assert mock_is_td.call_count >= 4

    @patch("twstock.official.updater._auto_update_tdcc")
    @patch("twstock.official.updater.update_dividend_events_for_date_range")
    @patch("twstock.official.updater.upsert_dataframe")
    @patch("twstock.official.updater.quotes.update_stock_meta_from_df")
    @patch("twstock.official.updater.quotes.fetch_tpex_quotes")
    @patch("twstock.official.updater.quotes.fetch_twse_quotes")
    @patch("twstock.official.updater.institutional.fetch_all_institutional")
    @patch("twstock.official.updater.get_connection")
    @patch("twstock.official.updater.cal.init_trading_calendar")
    @patch("twstock.official.updater.cal.get_last_trading_day", return_value=20260702)
    @patch("twstock.official.updater.cal._int_to_date")
    @patch("twstock.official.updater.cal.is_trading_day", return_value=True)
    @patch("twstock.official.updater.cal.date_exists_in_history")
    @patch("twstock.official.updater.cal._date_to_int")
    def test_normal_path(
        self,
        mock_d2i,
        mock_exists,
        mock_is_td,
        mock_i2d,
        mock_last_td,
        mock_init,
        mock_conn,
        mock_inst,
        mock_twse,
        mock_tpex,
        mock_meta,
        mock_upsert,
        mock_div,
        mock_tdcc,
    ):
        # 讓 _date_to_int 逐次遞減以模擬真實的日期回溯
        d2i_counter = [20260702]
        def _d2i_side_effect(dt):
            result = d2i_counter[0]
            d2i_counter[0] -= 1
            return result
        mock_d2i.side_effect = _d2i_side_effect

        # 當日期 >= 20260708 時回傳 True（表示該日有完整資料），< 20260708 則回傳 False
        def _exists_side_effect(date_int):
            return date_int >= 20260708
        mock_exists.side_effect = _exists_side_effect

        mock_i2d.return_value = _dt(2026, 7, 2)
        mock_conn.return_value = self._conn()
        mock_twse.return_value = self._quote()
        mock_tpex.return_value = self._quote()
        mock_inst.return_value = self._inst()
        updater.update_official_daily(date_int=20260702, days=1, force=False, auto_tdcc=False)
        assert mock_twse.call_count >= 1
        assert mock_tpex.call_count >= 1
        mock_meta.assert_called()
        mock_upsert.assert_called()
        mock_div.assert_called_once()

    @patch("twstock.official.updater._auto_update_tdcc")
    @patch("twstock.official.updater.update_dividend_events_for_date_range")
    @patch("twstock.official.updater.upsert_dataframe")
    @patch("twstock.official.updater.quotes.update_stock_meta_from_df")
    @patch("twstock.official.updater.quotes.fetch_tpex_quotes")
    @patch("twstock.official.updater.quotes.fetch_twse_quotes")
    @patch("twstock.official.updater.institutional.fetch_all_institutional")
    @patch("twstock.official.updater.get_connection")
    @patch("twstock.official.updater.cal.init_trading_calendar")
    @patch("twstock.official.updater.cal.get_last_trading_day", return_value=20260702)
    @patch("twstock.official.updater.cal._int_to_date")
    @patch("twstock.official.updater.cal.is_trading_day", return_value=True)
    @patch("twstock.official.updater.cal.date_exists_in_history", return_value=False)
    @patch("twstock.official.updater.cal._date_to_int", return_value=20260702)
    def test_both_empty(
        self,
        mock_d2i,
        mock_exists,
        mock_is_td,
        mock_i2d,
        mock_last_td,
        mock_init,
        mock_conn,
        mock_inst,
        mock_twse,
        mock_tpex,
        mock_meta,
        mock_upsert,
        mock_div,
        mock_tdcc,
    ):
        from datetime import datetime as _dt2

        mock_i2d.return_value = _dt2(2026, 7, 2)
        mock_conn.return_value = self._conn()
        mock_twse.return_value = pd.DataFrame()
        mock_tpex.return_value = pd.DataFrame()
        mock_inst.return_value = pd.DataFrame()
        updater.update_official_daily(date_int=20260702, days=1, force=False, auto_tdcc=False)
        mock_upsert.assert_not_called()
        mock_div.assert_called_once()

    @patch("twstock.official.updater._auto_update_tdcc")
    @patch("twstock.official.updater.update_dividend_events_for_date_range")
    @patch("twstock.official.updater.upsert_dataframe")
    @patch("twstock.official.updater.quotes.update_stock_meta_from_df")
    @patch("twstock.official.updater.quotes.fetch_tpex_quotes")
    @patch("twstock.official.updater.quotes.fetch_twse_quotes")
    @patch("twstock.official.updater.institutional.fetch_all_institutional")
    @patch("twstock.official.updater.get_connection")
    @patch("twstock.official.updater.cal.init_trading_calendar")
    @patch("twstock.official.updater.cal.get_last_trading_day", return_value=20260702)
    @patch("twstock.official.updater.cal._int_to_date")
    @patch("twstock.official.updater.cal.is_trading_day", return_value=True)
    @patch("twstock.official.updater.cal.date_exists_in_history", return_value=True)
    @patch("twstock.official.updater.cal._date_to_int", return_value=20260702)
    def test_fetch_dates_empty(
        self,
        mock_d2i,
        mock_exists,
        mock_is_td,
        mock_i2d,
        mock_last_td,
        mock_init,
        mock_conn,
        mock_inst,
        mock_twse,
        mock_tpex,
        mock_meta,
        mock_upsert,
        mock_div,
        mock_tdcc,
    ):
        mock_i2d.return_value = _dt(2026, 7, 2)
        mock_conn.return_value = self._conn()
        updater.update_official_daily(date_int=20260702, days=1, force=False, auto_tdcc=False)
        mock_twse.assert_not_called()

    @patch("twstock.official.updater._auto_update_tdcc")
    @patch("twstock.official.updater.update_dividend_events_for_date_range")
    @patch("twstock.official.updater.upsert_dataframe")
    @patch("twstock.official.updater.quotes.update_stock_meta_from_df")
    @patch("twstock.official.updater.quotes.fetch_tpex_quotes")
    @patch("twstock.official.updater.quotes.fetch_twse_quotes")
    @patch("twstock.official.updater.institutional.fetch_all_institutional")
    @patch("twstock.official.updater.get_connection")
    @patch("twstock.official.updater.cal.init_trading_calendar")
    @patch("twstock.official.updater.cal.get_last_trading_day", return_value=20260702)
    @patch("twstock.official.updater.cal._int_to_date")
    @patch("twstock.official.updater.cal.is_trading_day", return_value=True)
    @patch("twstock.official.updater.cal.date_exists_in_history", return_value=False)
    @patch("twstock.official.updater.cal._date_to_int", return_value=20260702)
    def test_per_date_exception(
        self,
        mock_d2i,
        mock_exists,
        mock_is_td,
        mock_i2d,
        mock_last_td,
        mock_init,
        mock_conn,
        mock_inst,
        mock_twse,
        mock_tpex,
        mock_meta,
        mock_upsert,
        mock_div,
        mock_tdcc,
    ):
        mock_i2d.return_value = _dt(2026, 7, 2)
        mock_conn.return_value = self._conn()
        mock_twse.side_effect = RuntimeError("api boom")
        mock_tpex.return_value = self._quote()
        mock_inst.return_value = pd.DataFrame()
        updater.update_official_daily(date_int=20260702, days=1, force=False, auto_tdcc=False)
        mock_div.assert_called_once()

    @patch("twstock.official.updater._auto_update_tdcc")
    @patch("twstock.official.updater.update_dividend_events_for_date_range")
    @patch("twstock.official.updater.upsert_dataframe")
    @patch("twstock.official.updater.quotes.update_stock_meta_from_df")
    @patch("twstock.official.updater.quotes.fetch_tpex_quotes")
    @patch("twstock.official.updater.quotes.fetch_twse_quotes")
    @patch("twstock.official.updater.institutional.fetch_all_institutional")
    @patch("twstock.official.updater.get_connection")
    @patch("twstock.official.updater.cal.init_trading_calendar")
    @patch("twstock.official.updater.cal.get_last_trading_day", return_value=20260702)
    @patch("twstock.official.updater.cal._int_to_date")
    @patch("twstock.official.updater.cal.is_trading_day", return_value=True)
    @patch("twstock.official.updater.cal.date_exists_in_history", return_value=False)
    @patch("twstock.official.updater.cal._date_to_int", return_value=20260702)
    def test_auto_tdcc_flag(
        self,
        mock_d2i,
        mock_exists,
        mock_is_td,
        mock_i2d,
        mock_last_td,
        mock_init,
        mock_conn,
        mock_inst,
        mock_twse,
        mock_tpex,
        mock_meta,
        mock_upsert,
        mock_div,
        mock_tdcc,
    ):
        mock_i2d.return_value = _dt(2026, 7, 2)
        mock_conn.return_value = self._conn()
        mock_twse.return_value = self._quote()
        mock_tpex.return_value = self._quote()
        mock_inst.return_value = self._inst()
        updater.update_official_daily(date_int=20260702, days=1, force=False, auto_tdcc=True)
        mock_tdcc.assert_called_once()

    @patch("twstock.official.updater._auto_update_tdcc")
    @patch("twstock.official.updater.update_dividend_events_for_date_range")
    @patch("twstock.official.updater.upsert_dataframe")
    @patch("twstock.official.updater.quotes.update_stock_meta_from_df")
    @patch("twstock.official.updater.quotes.fetch_tpex_quotes")
    @patch("twstock.official.updater.quotes.fetch_twse_quotes")
    @patch("twstock.official.updater.institutional.fetch_all_institutional")
    @patch("twstock.official.updater.get_connection")
    @patch("twstock.official.updater.cal.init_trading_calendar")
    @patch("twstock.official.updater.cal.get_last_trading_day", return_value=20260702)
    @patch("twstock.official.updater.cal._int_to_date")
    @patch("twstock.official.updater.cal.is_trading_day", return_value=True)
    @patch("twstock.official.updater.cal.date_exists_in_history", return_value=False)
    @patch("twstock.official.updater.cal._date_to_int", return_value=20260702)
    def test_force_flag(
        self,
        mock_d2i,
        mock_exists,
        mock_is_td,
        mock_i2d,
        mock_last_td,
        mock_init,
        mock_conn,
        mock_inst,
        mock_twse,
        mock_tpex,
        mock_meta,
        mock_upsert,
        mock_div,
        mock_tdcc,
    ):
        mock_i2d.return_value = _dt(2026, 7, 2)
        mock_conn.return_value = self._conn()
        mock_twse.return_value = self._quote()
        mock_tpex.return_value = self._quote()
        mock_inst.return_value = self._inst()
        updater.update_official_daily(date_int=20260702, days=1, force=True, auto_tdcc=False)
        mock_twse.assert_called_once()
        mock_upsert.assert_called()

    @patch("twstock.official.updater._auto_update_tdcc")
    @patch("twstock.official.updater.update_dividend_events_for_date_range")
    @patch("twstock.official.updater.upsert_dataframe")
    @patch("twstock.official.updater.quotes.update_stock_meta_from_df")
    @patch("twstock.official.updater.quotes.fetch_tpex_quotes")
    @patch("twstock.official.updater.quotes.fetch_twse_quotes")
    @patch("twstock.official.updater.institutional.fetch_all_institutional")
    @patch("twstock.official.updater.get_connection")
    @patch("twstock.official.updater.cal.init_trading_calendar")
    @patch("twstock.official.updater.cal.get_last_trading_day", return_value=20260702)
    @patch("twstock.official.updater.cal._int_to_date")
    @patch("twstock.official.updater.cal.is_trading_day", return_value=True)
    @patch("twstock.official.updater.cal.date_exists_in_history", return_value=True)
    @patch("twstock.official.updater.cal._date_to_int", return_value=20260702)
    def test_empty_calendar_init(
        self,
        mock_d2i,
        mock_exists,
        mock_is_td,
        mock_i2d,
        mock_last_td,
        mock_init,
        mock_conn,
        mock_inst,
        mock_twse,
        mock_tpex,
        mock_meta,
        mock_upsert,
        mock_div,
        mock_tdcc,
    ):
        mock_i2d.return_value = _dt(2026, 7, 2)
        c = MagicMock()
        c.fetchone.return_value = [0]
        m = MagicMock()
        m.cursor.return_value = c
        mock_conn.return_value = m
        mock_twse.return_value = self._quote()
        mock_tpex.return_value = self._quote()
        mock_inst.return_value = self._inst()
        updater.update_official_daily(date_int=20260702, days=1, force=False, auto_tdcc=False)
        assert mock_init.call_count >= 1
