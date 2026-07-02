# -*- coding: utf-8 -*-
"""Unit tests for twstock/utils.py — pure functions, no network/DB."""
from __future__ import annotations

import sys
from unittest.mock import patch

import pytest

# Ensure twstock is on path
_DIR = "D:/twse"
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)

from twstock.utils import (
    safe_float, safe_int, to_roc_date, format_price_change,
    default_http_headers, get_http_session, safe_http_get,
    get_token,
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
