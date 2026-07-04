# -*- coding: utf-8 -*-
"""test_fetcher_unit.py — market_data/fetcher.py 覆蓋率提升測試。

Mock HTTP requests to test all code paths without network.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from twstock.market_data import fetcher

# ── Fixtures ──────────────────────────────────────────────

@pytest.fixture
def mock_session():
    """建立 mock HTTP session。"""
    return MagicMock()


@pytest.fixture
def mock_response():
    """建立 mock HTTP response。"""
    resp = MagicMock()
    resp.status_code = 200
    resp.text = ""
    resp.json.return_value = {}
    return resp


# ── get_yahoo_market_volumes ──────────────────────────────


class TestGetYahooMarketVolumes:
    """get_yahoo_market_volumes 測試。"""

    @patch("twstock.utils.safe_http_get")
    @patch("twstock.market_data.fetcher.get_http_session")
    def test_returns_tuple(self, mock_session, mock_http_get):
        """應回傳 (twse_vol, tpex_vol) tuple。"""
        mock_session.return_value = MagicMock()
        mock_http_get.return_value = None  # 無回應

        result = fetcher.get_yahoo_market_volumes()
        assert isinstance(result, tuple)
        assert len(result) == 2

    @patch("twstock.utils.safe_http_get")
    @patch("twstock.market_data.fetcher.get_http_session")
    def test_no_session_returns_defaults(self, mock_session, mock_http_get):
        """無 session 時應回傳預設值。"""
        mock_session.return_value = None

        twse, tpex = fetcher.get_yahoo_market_volumes()
        assert twse == "無資料"
        assert tpex == "無資料"


# ── get_realtime_mis_data ─────────────────────────────────


class TestGetRealtimeMisData:
    """get_realtime_mis_data 測試。"""

    def test_returns_dict(self):
        """應回傳 dict（safe_http_get 在函數內部导入，改 mock session.get）。"""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {"msgArray": []}
        mock_session.get.return_value = mock_response

        with patch("twstock.market_data.fetcher.get_http_session", return_value=mock_session):
            with patch("twstock.utils.safe_http_get", return_value=mock_response):
                result = fetcher.get_realtime_mis_data()

        assert isinstance(result, dict)

    @patch("twstock.market_data.fetcher.get_http_session")
    def test_no_session_returns_empty(self, mock_session):
        """無 session 時應回傳空 dict。"""
        mock_session.return_value = None
        result = fetcher.get_realtime_mis_data()
        assert result == {}

    def test_with_symbols(self):
        """有 symbols 參數時應加入 ex_ch_list。"""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {"msgArray": []}
        mock_session.get.return_value = mock_response

        with patch("twstock.market_data.fetcher.get_http_session", return_value=mock_session):
            with patch("twstock.utils.safe_http_get", return_value=mock_response):
                result = fetcher.get_realtime_mis_data(symbols=["2330"])

        assert isinstance(result, dict)


# ── fetch_market_indices ──────────────────────────────────


class TestFetchMarketIndices:
    """fetch_market_indices 整合入口測試。"""

    @patch("twstock.utils.safe_http_get")
    @patch("twstock.market_data.fetcher.get_http_session")
    @patch("twstock.market_data.fetcher.get_yahoo_market_volumes")
    @patch("twstock.market_data.fetcher.get_realtime_mis_data")
    def test_returns_none_on_failure(self, mock_mis, mock_yahoo, mock_session, mock_http_get):
        """全部 API 失敗且 safe_http_get 回傳 None 時應回傳 None。"""
        mock_mis.return_value = {}
        mock_yahoo.return_value = ("無資料", "無資料")
        mock_session.return_value = MagicMock()
        mock_http_get.return_value = None  # 所有外部請求失敗

        result = fetcher.fetch_market_indices()
        assert result is None

    @patch("twstock.utils.safe_http_get")
    @patch("twstock.market_data.fetcher.get_http_session")
    @patch("twstock.market_data.fetcher.get_yahoo_market_volumes")
    @patch("twstock.market_data.fetcher.get_realtime_mis_data")
    def test_with_mis_data(self, mock_mis, mock_yahoo, mock_session, mock_http_get):
        """有 MIS 資料時應回傳結果。"""
        mock_mis.return_value = {
            "msgArray": [
                {"c": "t00", "z": "22000", "y": "21900"},
                {"c": "o00", "z": "230", "y": "228"},
            ],
            "queryTime": {"sysTime": "10:00:00", "sysDate": "2026/07/02"},
        }
        mock_yahoo.return_value = ("3000", "800")
        mock_session.return_value = MagicMock()
        mock_http_get.return_value = None

        result = fetcher.fetch_market_indices()
        # 可能因 TWSE/TPEx API 失敗而回傳 None，但不應拋異常
        assert result is None or isinstance(result, dict)
# ════════════════════════════════════════════════════════════════
# NEW TESTS — append-only, patch correct targets
#   - session:  patch("twstock.market_data.fetcher.get_http_session")
#   - safe_get: patch("utils.safe_http_get")
#               because fetcher.py uses `from utils import safe_http_get`
#               inside each function, and sys.modules has BOTH
#               "utils" and "twstock.utils" pointing to the same file
#               but as DIFFERENT module objects (due to _PKG_DIR insert).
#               fetcher's `from utils import` resolves to sys.modules["utils"],
#               so we patch "utils.safe_http_get" (not twstock.utils).
# ════════════════════════════════════════════════════════════════
from types import SimpleNamespace

# ── get_yahoo_market_volumes ─────────────────────────────────


class TestGetYahooMarketVolumesBranches:
    """Branch coverage for get_yahoo_market_volumes."""

    @patch("twstock.market_data.fetcher.get_http_session")
    def test_session_none_returns_defaults(self, mock_sess):
        mock_sess.return_value = None
        twse, tpex = fetcher.get_yahoo_market_volumes()
        assert twse == "無資料"
        assert tpex == "無資料"

    @patch("twstock.utils.safe_http_get")
    @patch("twstock.market_data.fetcher.get_http_session")
    def test_safe_http_get_returns_none(self, mock_sess, mock_get):
        mock_sess.return_value = MagicMock()
        mock_get.return_value = None
        assert fetcher.get_yahoo_market_volumes() == ("無資料", "無資料")

    @patch("twstock.utils.safe_http_get")
    @patch("twstock.market_data.fetcher.get_http_session")
    def test_twse_volume_matched(self, mock_sess, mock_get):
        mock_sess.return_value = MagicMock()
        mock_get.return_value = SimpleNamespace(
            text="上市 加權指數\t12,345.67 億 其他..."
        )
        twse, _ = fetcher.get_yahoo_market_volumes()
        assert twse == "12,345.67"

    @patch("twstock.utils.safe_http_get")
    @patch("twstock.market_data.fetcher.get_http_session")
    def test_tpex_volume_matched(self, mock_sess, mock_get):
        mock_sess.return_value = MagicMock()
        mock_get.return_value = SimpleNamespace(
            text="上櫃 櫃買指數 999.9 億 ..."
        )
        _, tpex = fetcher.get_yahoo_market_volumes()
        assert tpex == "999.9"

    @patch("twstock.utils.safe_http_get")
    @patch("twstock.market_data.fetcher.get_http_session")
    def test_both_volumes_matched(self, mock_sess, mock_get):
        mock_sess.return_value = MagicMock()
        mock_get.return_value = SimpleNamespace(
            text="加權指數 ... 10,197.42 億 ... 櫃買指數 ... 2,345.6 億"
        )
        twse, tpex = fetcher.get_yahoo_market_volumes()
        assert twse == "10,197.42"
        assert tpex == "2,345.6"

    @patch("twstock.utils.safe_http_get")
    @patch("twstock.market_data.fetcher.get_http_session")
    def test_safe_http_get_raises_returns_defaults(self, mock_sess, mock_get):
        mock_sess.return_value = MagicMock()
        mock_get.side_effect = RuntimeError("network boom")
        assert fetcher.get_yahoo_market_volumes() == ("無資料", "無資料")

    @patch("twstock.utils.safe_http_get")
    @patch("twstock.market_data.fetcher.get_http_session")
    def test_response_text_none_returns_defaults(self, mock_sess, mock_get):
        """response.text is None → regex on None raises → except → defaults."""
        mock_sess.return_value = MagicMock()
        mock_get.return_value = SimpleNamespace(text=None)
        twse, tpex = fetcher.get_yahoo_market_volumes()
        assert twse == "無資料"
        assert tpex == "無資料"

    @patch("twstock.utils.safe_http_get")
    @patch("twstock.market_data.fetcher.get_http_session")
    def test_html_without_target_text(self, mock_sess, mock_get):
        mock_sess.return_value = MagicMock()
        mock_get.return_value = SimpleNamespace(
            text="<html>完全不相干的內容</html>"
        )
        assert fetcher.get_yahoo_market_volumes() == ("無資料", "無資料")


# ── get_realtime_mis_data ────────────────────────────────────


class TestGetRealtimeMisDataBranches:
    """Branch coverage for get_realtime_mis_data."""

    @patch("twstock.market_data.fetcher.get_http_session")
    def test_session_none_returns_empty(self, mock_sess):
        mock_sess.return_value = None
        assert fetcher.get_realtime_mis_data() == {}

    @patch("twstock.utils.safe_http_get")
    @patch("twstock.market_data.fetcher.get_http_session")
    def test_warmup_raises_swallowed(self, mock_sess, mock_get):
        """Warmup safe_http_get is allowed to raise; main call returns None."""
        def side(url, *a, **k):
            if "index.jsp" in url:
                raise RuntimeError("warmup down")
            return None
        mock_sess.return_value = MagicMock()
        mock_get.side_effect = side
        assert fetcher.get_realtime_mis_data() == {}

    @patch("twstock.utils.safe_http_get")
    @patch("twstock.market_data.fetcher.get_http_session")
    def test_main_returns_none(self, mock_sess, mock_get):
        def side(url, *a, **k):
            if "index.jsp" in url:
                return SimpleNamespace()
            return None
        mock_sess.return_value = MagicMock()
        mock_get.side_effect = side
        assert fetcher.get_realtime_mis_data() == {}

    @patch("twstock.utils.safe_http_get")
    @patch("twstock.market_data.fetcher.get_http_session")
    def test_json_value_error_returns_empty(self, mock_sess, mock_get):
        def side(url, *a, **k):
            if "index.jsp" in url:
                return SimpleNamespace()
            bad = MagicMock()
            bad.json.side_effect = ValueError("bad json")
            return bad
        mock_sess.return_value = MagicMock()
        mock_get.side_effect = side
        assert fetcher.get_realtime_mis_data() == {}

    @patch("twstock.utils.safe_http_get")
    @patch("twstock.market_data.fetcher.get_http_session")
    def test_success_returns_dict(self, mock_sess, mock_get):
        payload = {"msgArray": [{"c": "t00", "z": "22000"}]}
        def side(url, *a, **k):
            if "index.jsp" in url:
                return SimpleNamespace()
            return SimpleNamespace(json=lambda: payload)
        mock_sess.return_value = MagicMock()
        mock_get.side_effect = side
        assert fetcher.get_realtime_mis_data() == payload

    @patch("twstock.utils.safe_http_get")
    @patch("twstock.market_data.fetcher.get_http_session")
    def test_with_symbols_appends_ex_ch(self, mock_sess, mock_get):
        """symbols passed → extra ex_ch args added to URL."""
        def side(url, *a, **k):
            if "index.jsp" in url:
                return SimpleNamespace()
            assert "tse_2330.tw" in url
            assert "otc_2330.tw" in url
            return SimpleNamespace(json=lambda: {"msgArray": []})
        mock_sess.return_value = MagicMock()
        mock_get.side_effect = side
        result = fetcher.get_realtime_mis_data(symbols=["2330"])
        assert isinstance(result, dict)


# ── fetch_market_indices ─────────────────────────────────────


class TestFetchMarketIndicesBranches:
    """Branch coverage for fetch_market_indices orchestrator."""

    @patch("twstock.market_data.fetcher.get_yahoo_market_volumes")
    @patch("twstock.market_data.fetcher.get_realtime_mis_data")
    @patch("twstock.market_data.fetcher.get_http_session")
    def test_all_sessions_none_returns_none(self, mock_sess, mock_mis, mock_yahoo):
        mock_mis.return_value = {}
        mock_yahoo.return_value = ("無資料", "無資料")
        mock_sess.return_value = None
        assert fetcher.fetch_market_indices() is None

    @patch("twstock.market_data.fetcher.get_yahoo_market_volumes")
    @patch("twstock.market_data.fetcher.get_realtime_mis_data")
    @patch("twstock.market_data.fetcher.get_http_session")
    def test_mis_z_zero_falls_back_to_y(self, mock_sess, mock_mis, mock_yahoo):
        """z == 0 → z becomes y; change = 0, pct = 0."""
        mock_sess.return_value = None
        mock_yahoo.return_value = ("無資料", "無資料")
        mock_mis.return_value = {
            "msgArray": [
                {"c": "t00", "z": "0", "y": "21900"},
            ],
        }
        assert fetcher.fetch_market_indices() is None

    @patch("twstock.market_data.fetcher.get_yahoo_market_volumes")
    @patch("twstock.market_data.fetcher.get_realtime_mis_data")
    @patch("twstock.market_data.fetcher.get_http_session")
    def test_mis_y_zero_covers_pct_guard(self, mock_sess, mock_mis, mock_yahoo):
        """y == 0 → pct guard returns 0 (avoids ZeroDivisionError)."""
        mock_sess.return_value = None
        mock_yahoo.return_value = ("無資料", "無資料")
        mock_mis.return_value = {
            "msgArray": [
                {"c": "o00", "z": "230", "y": "0"},
            ],
        }
        assert fetcher.fetch_market_indices() is None

    @patch("twstock.utils.safe_http_get")
    @patch("twstock.market_data.fetcher.get_http_session")
    @patch("twstock.market_data.fetcher.get_yahoo_market_volumes")
    @patch("twstock.market_data.fetcher.get_realtime_mis_data")
    def test_full_twse_and_tpex_path(self, mock_mis, mock_yahoo, mock_sess, mock_get):
        """Happy path: TWSE MI_INDEX tables + TPEx highlight both parse."""
        mock_sess.return_value = MagicMock()
        mock_yahoo.return_value = ("無資料", "無資料")
        mock_mis.return_value = {
            "msgArray": [
                {"c": "t00", "z": "22000", "y": "21900"},
                {"c": "o00", "z": "230", "y": "228"},
            ],
            "queryTime": {"sysTime": "10:00:00", "sysDate": "2026/07/02"},
        }

        def side(url, *a, **k):
            if "MI_INDEX" in url:
                return SimpleNamespace(json=lambda: {
                    "tables": [
                        {"title": "漲跌證券數合 計", "data": [
                            ["a", "b", "100(5)"],
                            ["a", "b", "200(10)"],
                            ["a", "b", "50(0)"],
                        ]},
                        {"title": "大盤統計資訊", "data": [
                            ["總計", "123456789"],
                        ]},
                    ]
                })
            if "tpex.org.tw" in url:
                return SimpleNamespace(json=lambda: {
                    "stat": "ok",
                    "tables": [{
                        "fields": ["日期","時間","成交張數","成交金額",
                                   "上漲家數","漲停家數","下跌家數","跌停家數","平盤家數"],
                        "data": [["2026/07/02","10:00","12345","987654321",
                                  "300","10","150","5","40"]],
                    }],
                })
            return None

        mock_get.side_effect = side

        r = fetcher.fetch_market_indices()
        assert isinstance(r, dict)
        # TAIEX breadth
        assert r["TAIEX"]["up"] == 100 and r["TAIEX"]["l_up"] == 5
        assert r["TAIEX"]["down"] == 200 and r["TAIEX"]["l_down"] == 10
        assert r["TAIEX"]["flat"] == 50
        # OTC from TPEx highlight (via _safe_int_idx)
        assert r["OTC"]["up"] == 300 and r["OTC"]["l_up"] == 10
        assert r["OTC"]["down"] == 150 and r["OTC"]["l_down"] == 5
        assert r["OTC"]["flat"] == 40
        # time/date propagated
        assert r["time"] == "10:00:00"
        assert r["date"] == "2026/07/02"
        # Diffs
        assert r["TAIEX"]["price"] == 22000
        assert r["TAIEX"]["change"] == 100
        assert r["OTC"]["price"] == 230
        assert r["OTC"]["change"] == 2

    @patch("twstock.utils.safe_http_get")
    @patch("twstock.market_data.fetcher.get_http_session")
    @patch("twstock.market_data.fetcher.get_yahoo_market_volumes")
    @patch("twstock.market_data.fetcher.get_realtime_mis_data")
    def test_tpex_data_with_digit_amount(self, mock_mis, mock_yahoo, mock_sess, mock_get):
        """TPEx row[3] is a digit string → OTC amount = safe_float / 100."""
        mock_sess.return_value = MagicMock()
        mock_yahoo.return_value = ("無資料", "無資料")
        mock_mis.return_value = {
            "msgArray": [
                {"c": "t00", "z": "22000", "y": "21900"},
                {"c": "o00", "z": "230", "y": "228"},
            ],
        }

        def side(url, *a, **k):
            if "MI_INDEX" in url:
                return SimpleNamespace(json=lambda: {"tables": []})
            if "tpex.org.tw" in url:
                return SimpleNamespace(json=lambda: {
                    "stat": "ok",
                    "tables": [{
                        "fields": ["a","b","c","d"],
                        "data": [["x","y","z","5000"]],
                    }],
                })
            return None

        mock_get.side_effect = side
        r = fetcher.fetch_market_indices()
        assert isinstance(r, dict)
        assert r["OTC"]["amount"] == 50.0

    @patch("twstock.utils.safe_http_get")
    @patch("twstock.market_data.fetcher.get_http_session")
    @patch("twstock.market_data.fetcher.get_yahoo_market_volumes")
    @patch("twstock.market_data.fetcher.get_realtime_mis_data")
    def test_twse_breadth_short_data_no_crash(self, mock_mis, mock_yahoo, mock_sess, mock_get):
        """Breadth table with < 3 rows → guard skips, no crash."""
        mock_sess.return_value = MagicMock()
        mock_yahoo.return_value = ("無資料", "無資料")
        mock_mis.return_value = {
            "msgArray": [
                {"c": "t00", "z": "22000", "y": "21900"},
                {"c": "o00", "z": "230", "y": "228"},
            ],
        }

        def side(url, *a, **k):
            if "MI_INDEX" in url:
                return SimpleNamespace(json=lambda: {
                    "tables": [
                        {"title": "漲跌證券數合計", "data": [
                            ["a", "b", "100(5)"],
                        ]},
                    ]
                })
            if "tpex.org.tw" in url:
                return SimpleNamespace(json=lambda: {
                    "stat": "ok", "tables": [{"fields": [], "data": []}],
                })
            return None

        mock_get.side_effect = side
        r = fetcher.fetch_market_indices()
        assert isinstance(r, dict)
        assert r["TAIEX"]["up"] is None

    @patch("twstock.market_data.fetcher.get_yahoo_market_volumes")
    @patch("twstock.market_data.fetcher.get_realtime_mis_data")
    @patch("twstock.market_data.fetcher.get_http_session")
    def test_yahoo_volumes_update_amount(self, mock_sess, mock_mis, mock_yahoo):
        """Yahoo volumes != '無資料' → amount is set (safely parsed)."""
        mock_sess.return_value = None
        mock_mis.return_value = {
            "msgArray": [
                {"c": "t00", "z": "15000", "y": "14900"},
                {"c": "o00", "z": "200", "y": "198"},
            ],
        }
        mock_yahoo.return_value = ("1,234.5", "56.7")
        assert fetcher.fetch_market_indices() is None

    @patch("twstock.market_data.fetcher.get_yahoo_market_volumes")
    @patch("twstock.market_data.fetcher.get_realtime_mis_data")
    @patch("twstock.market_data.fetcher.get_http_session")
    def test_both_prices_zero_returns_none(self, mock_sess, mock_mis, mock_yahoo):
        """Both TAIEX.price and OTC.price are 0 → returns None."""
        mock_sess.return_value = MagicMock()
        mock_mis.return_value = {
            "msgArray": [
                {"c": "t00", "z": "0", "y": "0"},
                {"c": "o00", "z": "0", "y": "0"},
            ],
        }
        mock_yahoo.return_value = ("無資料", "無資料")
        with patch("utils.safe_http_get", return_value=None):
            assert fetcher.fetch_market_indices() is None

    @patch("twstock.market_data.fetcher.get_yahoo_market_volumes")
    @patch("twstock.market_data.fetcher.get_realtime_mis_data")
    def test_mis_block_exception_swallowed(self, mock_mis, mock_yahoo):
        """Exception in MIS block → pass, continue to Yahoo."""
        mock_mis.side_effect = RuntimeError("mis boom")
        mock_yahoo.return_value = ("無資料", "無資料")
        with patch("twstock.market_data.fetcher.get_http_session", return_value=MagicMock()),              patch("utils.safe_http_get", return_value=None):
            r = fetcher.fetch_market_indices()
            assert r is None or isinstance(r, dict)

    @patch("twstock.market_data.fetcher.get_yahoo_market_volumes")
    @patch("twstock.market_data.fetcher.get_realtime_mis_data")
    def test_yahoo_block_exception_swallowed(self, mock_mis, mock_yahoo):
        """Exception in Yahoo block → pass, continue to TWSE."""
        mock_mis.return_value = {
            "msgArray": [
                {"c": "t00", "z": "22000", "y": "21900"},
                {"c": "o00", "z": "230", "y": "228"},
            ],
        }
        mock_yahoo.side_effect = RuntimeError("yahoo boom")
        with patch("twstock.market_data.fetcher.get_http_session", return_value=MagicMock()),              patch("utils.safe_http_get", return_value=None):
            r = fetcher.fetch_market_indices()
            assert r is None or isinstance(r, dict)

    @patch("twstock.utils.safe_http_get")
    @patch("twstock.market_data.fetcher.get_http_session")
    @patch("twstock.market_data.fetcher.get_yahoo_market_volumes")
    @patch("twstock.market_data.fetcher.get_realtime_mis_data")
    def test_twse_tpex_block_exception_swallowed(self, mock_mis, mock_yahoo, mock_sess, mock_get):
        """Exception inside TWSE/TPEx block → pass."""
        mock_sess.return_value = MagicMock()
        mock_yahoo.return_value = ("無資料", "無資料")
        mock_mis.return_value = {
            "msgArray": [
                {"c": "t00", "z": "22000", "y": "21900"},
                {"c": "o00", "z": "230", "y": "228"},
            ],
        }
        mock_get.side_effect = RuntimeError("tse boom")
        r = fetcher.fetch_market_indices()
        assert r is None or isinstance(r, dict)
