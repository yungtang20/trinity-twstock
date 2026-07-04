# -*- coding: utf-8 -*-
"""test_official_tdcc.py — official/tdcc.py 覆蓋率測試。"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from twstock.official import tdcc

# ---------------------------------------------------------------------------
# Helper: 建立 mock response
# ---------------------------------------------------------------------------

def _json_response(status_code: int, payload) -> SimpleNamespace:
    """回傳一個具備 status_code / json() / text 屬性的假 response。"""
    return SimpleNamespace(
        status_code=status_code,
        json=lambda: payload,
        text=str(payload),
    )


# ---------------------------------------------------------------------------
# fetch_tdcc_historical
# ---------------------------------------------------------------------------

class TestFetchTdccHistorical:
    """fetch_tdcc_historical 測試（OpenAPI JSON 路徑）。"""

    @patch("twstock.official.tdcc.requests.get")
    @patch("twstock.official.tdcc.time.sleep")
    def test_successful_json_parsing(self, _mock_sleep, mock_get):
        """成功 JSON 回應（lvl 17 + lvl 15）應正確解析為 DataFrame。"""
        mock_get.return_value = _json_response(
            200,
            [
                {"證券代號": "2330", "持股分級": "17", "股數": "1000000", "人數": "500"},
                {"證券代號": "2330", "持股分級": "15", "股數": "200000", "人數": "30"},
            ],
        )

        df = tdcc.fetch_tdcc_historical(weeks=1, retries=2)

        assert isinstance(df, pd.DataFrame)
        assert not df.empty
        row = df.iloc[0]
        assert row["stock_id"] == "2330"
        assert row["total_shares"] == 1000000
        assert row["total_people"] == 500
        assert row["whale_shares"] == 200000
        assert row["whale_people"] == 30
        # whale_ratio = 200000 / 1000000 * 100 = 20.0
        assert row["whale_ratio"] == pytest.approx(20.0)
        # 欄位檢查
        for col in ("stock_id", "date_int", "total_shares", "whale_ratio",
                    "total_people", "whale_shares", "whale_people"):
            assert col in df.columns

    @patch("twstock.official.tdcc.requests.get")
    @patch("twstock.official.tdcc.time.sleep")
    def test_non_4_digit_code_filtered(self, _mock_sleep, mock_get):
        """非 4 位數股票代號應被過濾。"""
        mock_get.return_value = _json_response(
            200,
            [
                {"證券代號": "233", "持股分級": "17", "股數": "100", "人數": "1"},   # 3 位數
                {"證券代號": "23301", "持股分級": "17", "股數": "100", "人數": "1"},  # 5 位數
                {"證券代號": "2330", "持股分級": "17", "股數": "500", "人數": "5"},
            ],
        )

        df = tdcc.fetch_tdcc_historical(weeks=1, retries=2)
        # 只有 2330 應存活
        assert len(df) == 1
        assert df.iloc[0]["stock_id"] == "2330"
        assert df.iloc[0]["total_shares"] == 500

    @patch("twstock.official.tdcc.requests.get")
    @patch("twstock.official.tdcc.time.sleep")
    def test_non_digit_level_filtered(self, _mock_sleep, mock_get):
        """非數字持股分級應被過濾。"""
        mock_get.return_value = _json_response(
            200,
            [
                {"證券代號": "2330", "持股分級": "A", "股數": "100", "人數": "1"},
                {"證券代號": "2330", "持股分級": "17", "股數": "500", "人數": "5"},
            ],
        )

        df = tdcc.fetch_tdcc_historical(weeks=1, retries=2)
        assert len(df) == 1
        assert df.iloc[0]["total_shares"] == 500

    @patch("twstock.official.tdcc.requests.get")
    @patch("twstock.official.tdcc.time.sleep")
    def test_empty_json_list_returns_empty_df(self, _mock_sleep, mock_get):
        """空 JSON list 應回傳空 DataFrame。"""
        mock_get.return_value = _json_response(200, [])

        df = tdcc.fetch_tdcc_historical(weeks=1, retries=2)
        assert isinstance(df, pd.DataFrame)
        assert df.empty

    @patch("twstock.official.tdcc.requests.get")
    @patch("twstock.official.tdcc.time.sleep")
    def test_http_404_retries_then_empty(self, _mock_sleep, mock_get):
        """HTTP 404 應重試直到耗盡，最終回傳空 DataFrame。"""
        mock_get.return_value = _json_response(404, None)

        df = tdcc.fetch_tdcc_historical(weeks=1, retries=2)
        assert isinstance(df, pd.DataFrame)
        assert df.empty
        # 應呼叫 2 次（retries=2）
        assert mock_get.call_count == 2

    @patch("twstock.official.tdcc.requests.get")
    @patch("twstock.official.tdcc.time.sleep")
    def test_non_list_json_returns_empty_df(self, _mock_sleep, mock_get):
        """非 list JSON（dict）應回傳空 DataFrame。"""
        mock_get.return_value = _json_response(200, {"data": "oops"})

        df = tdcc.fetch_tdcc_historical(weeks=1, retries=2)
        assert isinstance(df, pd.DataFrame)
        assert df.empty

    @patch("twstock.official.tdcc.requests.get")
    @patch("twstock.official.tdcc.time.sleep")
    def test_exception_retries_then_empty(self, _mock_sleep, mock_get):
        """requests.get 拋異常應重試直到耗盡，最終回傳空 DataFrame。"""
        mock_get.side_effect = RuntimeError("network down")

        df = tdcc.fetch_tdcc_historical(weeks=1, retries=2)
        assert isinstance(df, pd.DataFrame)
        assert df.empty
        assert mock_get.call_count == 2

    @patch("twstock.official.tdcc.requests.get")
    @patch("twstock.official.tdcc.time.sleep")
    def test_total_shares_zero_skipped(self, _mock_sleep, mock_get):
        """total_shares == 0 的股票應被跳過。"""
        mock_get.return_value = _json_response(
            200,
            [
                # 只有 lvl 15，沒有 lvl 17 → total_shares 維持 0
                {"證券代號": "2330", "持股分級": "15", "股數": "100", "人數": "1"},
            ],
        )

        df = tdcc.fetch_tdcc_historical(weeks=1, retries=2)
        assert df.empty


# ---------------------------------------------------------------------------
# fetch_latest_tdcc
# ---------------------------------------------------------------------------

class TestFetchLatestTdcc:
    """fetch_latest_tdcc 測試。"""

    @patch("twstock.official.tdcc.requests.get")
    @patch("twstock.official.tdcc.time.sleep")
    def test_returns_dataframe(self, _mock_sleep, mock_get):
        """成功 mock 應回傳 DataFrame。"""
        mock_get.return_value = _json_response(
            200,
            [
                {"證券代號": "2330", "持股分級": "17", "股數": "1000000", "人數": "500"},
                {"證券代號": "2330", "持股分級": "15", "股數": "200000", "人數": "30"},
            ],
        )

        df = tdcc.fetch_latest_tdcc()
        assert isinstance(df, pd.DataFrame)
        assert not df.empty


# ---------------------------------------------------------------------------
# fetch_single_stock_tdcc_from_portal
# ---------------------------------------------------------------------------

# 極小但合法的 HTML 模板，供 portal 測試使用
_PORTAL_GET_HTML = """
<html><body>
<form>
    <input name="SYNCHRONIZER_TOKEN" value="fake-token-123">
</form>
<select id="scaDate">
    <option value="">--請選擇--</option>
    <option value="20260627">2026/06/27</option>
    <option value="20260620">2026/06/20</option>
    <option value="20260613">2026/06/13</option>
</select>
</body></html>
"""

_PORTAL_POST_HTML = """
<html><body>
<table><tr><td>stub</td></tr></table>
<table>
    <tr><td>等級</td><td>區間</td><td>人數</td><td>股數</td><td>佔比</td></tr>
    <tr><td>1</td><td>1-999</td><td>100</td><td>50000</td><td>0.05</td></tr>
    <tr><td>15</td><td>1,000以上</td><td>30</td><td>200000</td><td>20.00</td></tr>
    <tr><td>17</td><td>合計</td><td>500</td><td>1000000</td><td>100.00</td></tr>
</table>
</body></html>
"""


def _make_portal_session(get_html: str, post_html: str) -> MagicMock:
    """建立一個 mock session，其 get/post 回傳指定的 HTML。"""
    session = MagicMock()
    session.get.return_value = SimpleNamespace(status_code=200, text=get_html)
    session.post.return_value = SimpleNamespace(status_code=200, text=post_html)
    return session


class TestFetchSingleStockTdccFromPortal:
    """fetch_single_stock_tdcc_from_portal 測試（HTML 解析路徑）。"""

    def test_successful_parse(self):
        """成功 GET+POST 應回傳正確解析的 dict。"""
        session = _make_portal_session(_PORTAL_GET_HTML, _PORTAL_POST_HTML)

        result = tdcc.fetch_single_stock_tdcc_from_portal("2330", "2026-06-28", session=session)

        assert result is not None
        assert result["stock_id"] == "2330"
        assert result["date"] == "2026-06-28"
        assert result["source"] == "tdcc"
        assert result["total_shares"] == 1000000
        assert result["total_people"] == 500
        assert result["whale_shares"] == 200000
        assert result["whale_people"] == 30
        assert result["whale_ratio"] == pytest.approx(20.0)
        assert result["retail_ratio"] == pytest.approx(80.0)

    def test_get_status_not_200_returns_none(self):
        """GET status != 200 應回傳 None。"""
        session = MagicMock()
        session.get.return_value = SimpleNamespace(status_code=503, text="")

        result = tdcc.fetch_single_stock_tdcc_from_portal("2330", "2026-06-28", session=session)
        assert result is None

    def test_missing_token_returns_none(self):
        """缺少 SYNCHRONIZER_TOKEN 應回傳 None。"""
        html = """
        <html><body>
        <select id="scaDate">
            <option value="20260627">2026/06/27</option>
        </select>
        </body></html>
        """
        session = _make_portal_session(html, "")

        result = tdcc.fetch_single_stock_tdcc_from_portal("2330", "2026-06-28", session=session)
        assert result is None

    def test_missing_select_date_returns_none(self):
        """缺少 scaDate 應回傳 None。"""
        html = """
        <html><body>
        <form><input name="SYNCHRONIZER_TOKEN" value="tok"></input></form>
        </body></html>
        """
        session = _make_portal_session(html, "")

        result = tdcc.fetch_single_stock_tdcc_from_portal("2330", "2026-06-28", session=session)
        assert result is None

    def test_no_matching_date_returns_none(self):
        """沒有 <= target 的日期應回傳 None。"""
        html = """
        <html><body>
        <form><input name="SYNCHRONIZER_TOKEN" value="tok"></input></form>
        <select id="scaDate">
            <option value="20269999">future</option>
        </select>
        </body></html>
        """
        session = _make_portal_session(html, "")

        result = tdcc.fetch_single_stock_tdcc_from_portal("2330", "2026-06-28", session=session)
        assert result is None

    def test_post_status_not_200_returns_none(self):
        """POST status != 200 應回傳 None。"""
        session = MagicMock()
        session.get.return_value = SimpleNamespace(status_code=200, text=_PORTAL_GET_HTML)
        session.post.return_value = SimpleNamespace(status_code=500, text="")

        result = tdcc.fetch_single_stock_tdcc_from_portal("2330", "2026-06-28", session=session)
        assert result is None

    def test_total_shares_zero_returns_none(self):
        """total_shares == 0 應回傳 None。"""
        post_html = """
        <html><body>
        <table><tr><td>stub</td></tr></table>
        <table>
            <tr><td>等級</td><td>區間</td><td>人數</td><td>股數</td><td>佔比</td></tr>
            <tr><td>1</td><td>1-999</td><td>100</td><td>50000</td><td>0.05</td></tr>
        </table>
        </body></html>
        """
        session = _make_portal_session(_PORTAL_GET_HTML, post_html)

        result = tdcc.fetch_single_stock_tdcc_from_portal("2330", "2026-06-28", session=session)
        assert result is None

    def test_no_tables_returns_none(self):
        """完全沒有 table 應回傳 None。"""
        post_html = "<html><body><p>no data</p></body></html>"
        session = _make_portal_session(_PORTAL_GET_HTML, post_html)

        result = tdcc.fetch_single_stock_tdcc_from_portal("2330", "2026-06-28", session=session)
        assert result is None

    def test_exception_returns_none(self):
        """解析過程拋異常應回傳 None（不向外拋）。"""
        session = MagicMock()
        session.get.side_effect = RuntimeError("boom")

        result = tdcc.fetch_single_stock_tdcc_from_portal("2330", "2026-06-28", session=session)
        assert result is None
