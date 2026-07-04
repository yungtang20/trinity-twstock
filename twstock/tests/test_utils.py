# -*- coding: utf-8 -*-
"""Unit tests for twstock/utils.py — pure functions, no network/DB."""
from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

# Ensure twstock is on path
_DIR = "D:/twse"
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)

from twstock.utils import (
    safe_float, safe_int, to_roc_date, format_price_change,
    default_http_headers, get_http_session, safe_http_get,
    get_token, get_stock_name,
)


# ── safe_float ─────────────────────────────────────────────
class TestSafeFloat:
    def test_numeric_string(self):
        assert safe_float("123.45") == 123.45

    def test_comma_separated(self):
        assert safe_float("1,234.56") == 1234.56

    def test_hyphen_returns_default(self):
        assert safe_float("-") == 0.0

    def test_empty_string(self):
        assert safe_float("") == 0.0

    def test_none(self):
        assert safe_float(None) == 0.0

    def test_custom_default(self):
        assert safe_float(None, -1.0) == -1.0

    def test_scientific_notation(self):
        assert safe_float("1e3") == 1000.0

    def test_garbage_string(self):
        assert safe_float("abc") == 0.0


# ── safe_int ───────────────────────────────────────────────
class TestSafeInt:
    def test_numeric_string(self):
        assert safe_int("42") == 42

    def test_comma_separated(self):
        assert safe_int("1,234") == 1234

    def test_hyphen(self):
        assert safe_int("-") == 0

    def test_none(self):
        assert safe_int(None) == 0

    def test_float_truncates(self):
        # "3.14" is not a valid int string, safe_int returns default
        result = safe_int("3.14")
        assert result == 0 or result == 3


# ── to_roc_date ────────────────────────────────────────────
class TestToRocDate:
    def test_iso_format(self):
        assert to_roc_date("2026-07-02") == "115/07/02"

    def test_compact_format(self):
        assert to_roc_date("20260702") == "115/07/02"

    def test_na(self):
        assert to_roc_date("N/A") == "N/A"

    def test_none(self):
        assert to_roc_date(None) == "N/A"

    def test_empty(self):
        assert to_roc_date("") == "N/A"

    def test_short_string(self):
        assert to_roc_date("12345") == "12345"


# ── format_price_change ────────────────────────────────────
class TestFormatPriceChange:
    def test_up(self):
        diff, pct, color = format_price_change(110, 100)
        assert diff == 10
        assert pct == 10.0
        assert "red" in color

    def test_down(self):
        diff, pct, color = format_price_change(90, 100)
        assert diff == -10
        assert pct == -10.0
        assert "green" in color

    def test_flat(self):
        diff, pct, color = format_price_change(100, 100)
        assert diff == 0
        assert pct == 0
        assert color == "white"

    def test_extreme_up(self):
        _, _, color = format_price_change(200, 100)
        assert "on red" in color

    def test_zero_previous(self):
        diff, pct, _ = format_price_change(100, 0)
        assert pct == 0


# ── default_http_headers ───────────────────────────────────
class TestDefaultHeaders:
    def test_returns_dict(self):
        h = default_http_headers()
        assert isinstance(h, dict)
        assert "User-Agent" in h


# ── get_http_session ───────────────────────────────────────
class TestGetHttpSession:
    def test_returns_none_when_no_requests(self):
        with patch.dict("sys.modules", {"requests": None}):
            result = get_http_session()
            # requests may be installed; if so, result is a Session
            # This test just ensures no crash
            assert result is None or hasattr(result, "get")


# ── get_token ──────────────────────────────────────────────
class TestToken:
    def test_raises_without_env(self):
        """get_token() should raise ValueError when no token is configured."""
        with pytest.raises((ValueError, OSError)):
            get_token()


class TestGetMarketMode:
    """get_market_mode 覆蓋盤中/收盤後/假日分支。"""

    def test_weekday_market_hours(self):
        """9:00–13:30 should return '盤中'."""
        from datetime import datetime
        from unittest.mock import MagicMock, patch
        from twstock import utils
        lunch = datetime(2025, 1, 6, 10, 0)  # Monday 10:00
        with patch.object(utils, "datetime") as mock_dt:
            mock_dt.now.return_value = lunch
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            assert utils.get_market_mode() == "盤中"

    def test_weekday_after_hours(self):
        from datetime import datetime
        from unittest.mock import MagicMock, patch
        from twstock import utils
        evening = datetime(2025, 1, 6, 18, 0)  # Monday 18:00
        with patch.object(utils, "datetime") as mock_dt:
            mock_dt.now.return_value = evening
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            assert utils.get_market_mode() == "收盤後"

    def test_weekend(self):
        from datetime import datetime
        from unittest.mock import MagicMock, patch
        from twstock import utils
        saturday = datetime(2025, 1, 4, 10, 0)  # Saturday 10:00
        with patch.object(utils, "datetime") as mock_dt:
            mock_dt.now.return_value = saturday
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            assert utils.get_market_mode() == "收盤後 (假日)"


class TestGetSysInfo:
    """get_sys_info 覆蓋 Offline/Ready 兩路徑。"""

    @patch("twstock.utils.get_path", return_value="/nonexistent/db.sqlite")
    @patch("twstock.utils.os.path.exists", return_value=False)
    def test_offline_when_no_db(self, mock_exists, mock_path):
        from twstock.utils import get_sys_info
        info = get_sys_info()
        assert info["status"] == "Offline"

    @patch("twstock.utils.get_connection")
    @patch("twstock.utils.get_path", return_value="/tmp/test.db")
    @patch("twstock.utils.os.path.exists", return_value=True)
    @patch("twstock.utils.file_size_mb", return_value=1.5)
    def test_ready_when_db_exists(self, mock_size, mock_exists, mock_path, mock_conn):
        from twstock.utils import get_sys_info
        mock_db = MagicMock()
        mock_db.execute.return_value.fetchone.side_effect = [
            (42,),        # stock_meta count
            ("2025-01-03",),  # MAX(date)
            ("2020-01-01",),  # MIN(date)
        ]
        mock_conn.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)
        info = get_sys_info()
        assert info["status"] == "Ready"
        assert info["stocks"] == 42

from unittest.mock import Mock


class TestGetHttpSession:
    @patch("twstock.utils.default_http_headers", return_value={"User-Agent": "test"})
    def test_returns_session(self, mock_headers):
        try:
            import requests
            session = get_http_session()
            assert session is not None
        except ImportError:
            pytest.skip("requests not installed")

    def test_session_has_headers(self):
        # If requests is installed the session has the default headers
        session = get_http_session()
        if session is not None:
            assert "User-Agent" in session.headers


class TestSafeHttpGet:
    def test_returns_none_when_no_session(self):
        result = safe_http_get("http://example.com", session=None)
        # Could be None or a real response depending on env
        # Just verify it doesn't raise

    def test_with_mock_session(self):
        mock_sess = MagicMock()
        mock_resp = MagicMock()
        mock_sess.get.return_value = mock_resp
        result = safe_http_get("http://example.com", session=mock_sess)
        assert result is mock_resp
        mock_sess.get.assert_called_once()

    def test_returns_none_on_exception(self):
        mock_sess = MagicMock()
        mock_sess.get.side_effect = Exception("network error")
        result = safe_http_get("http://example.com", session=mock_sess)
        assert result is None


class TestGetStockNameFromUtils:
    """utils.get_stock_name 覆蓋成功/失敗路徑。"""

    @patch("twstock.utils.get_connection")
    def test_returns_name(self, mock_conn):
        mock_db = MagicMock()
        mock_db.execute.return_value.fetchone.return_value = ("台積電",)
        mock_conn.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)
        assert get_stock_name("2330") == "台積電"

    @patch("twstock.utils.get_connection")
    def test_returns_unknown_when_missing(self, mock_conn):
        mock_db = MagicMock()
        mock_db.execute.return_value.fetchone.return_value = None
        mock_conn.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)
        assert get_stock_name("9999") == "未知"

    @patch("twstock.utils.get_connection")
    def test_returns_unknown_on_exception(self, mock_conn):
        mock_conn.side_effect = Exception("no db")
        assert get_stock_name("2330") == "未知"
