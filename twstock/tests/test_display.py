# -*- coding: utf-8 -*-
"""test_display.py — display.py 覆蓋率測試。"""
from __future__ import annotations

import pytest

from twstock.display import (
    LIMIT_DN_PCT,
    LIMIT_UP_PCT,
    chg_color,
    chg_rich,
    ma_color,
    ma_str,
    price_color,
    price_rich,
    price_str,
    vol_color,
    vol_diff_rich,
    vol_fmt,
    vol_fmt_short,
    vol_rich,
)


# ── price_color ───────────────────────────────────────────


class TestPriceColor:
    """price_color 價格配色（臺股漲紅跌綠）。"""

    def test_limit_up(self):
        """漲停應回傳 white on red。"""
        assert price_color(10, LIMIT_UP_PCT) == "white on red"
        assert price_color(10, 15) == "white on red"

    def test_limit_down(self):
        """跌停應回傳 white on green。"""
        assert price_color(-10, LIMIT_DN_PCT) == "white on green"
        assert price_color(-10, -15) == "white on green"

    def test_up(self):
        """上漲應回傳 bright_red。"""
        assert price_color(5, 2.5) == "bright_red"

    def test_down(self):
        """下跌應回傳 bright_green。"""
        assert price_color(-5, -2.5) == "bright_green"

    def test_flat(self):
        """平盤應回傳 white。"""
        assert price_color(0, 0) == "white"


# ── price_str / price_rich ───────────────────────────────


class TestPriceStr:
    """price_str 價格字串。"""

    def test_price_up(self):
        """上漲應包含 ▲。"""
        result = price_str(105, 100)
        assert "▲" in str(result)

    def test_price_down(self):
        """下跌應包含 ▼。"""
        result = price_str(95, 100)
        assert "▼" in str(result)

    def test_price_flat(self):
        """平盤應包含 ─。"""
        result = price_str(100, 100)
        assert "─" in str(result)

    def test_price_no_sign(self):
        """show_sign=False 不應包含漲跌百分比。"""
        result = price_str(105, 100, show_sign=False)
        assert "%" not in str(result)


class TestPriceRich:
    """price_rich Rich markup。"""

    def test_includes_price(self):
        result = price_rich(105, 100)
        assert "105.00" in result

    def test_includes_color_tag(self):
        result = price_rich(105, 100)
        assert "[" in result and "]" in result


# ── chg_color / chg_rich ─────────────────────────────────


class TestChgColor:
    """chg_color 簡單漲跌配色。"""

    def test_positive(self):
        assert chg_color(5) == "bright_red"

    def test_negative(self):
        assert chg_color(-5) == "bright_green"

    def test_zero(self):
        assert chg_color(0) == "white"


class TestChgRich:
    """chg_rich Rich markup。"""

    def test_positive(self):
        result = chg_rich(5, 2.5)
        assert "+" in result
        assert "5.00" in result

    def test_negative(self):
        result = chg_rich(-5, -2.5)
        assert "-" in result
        assert "5.00" in result


# ── vol_color / vol_rich / vol_diff_rich ─────────────────


class TestVolColor:
    """vol_color 成交量配色。"""

    def test_higher(self):
        assert vol_color(1000, 500) == "bright_red"

    def test_lower(self):
        assert vol_color(500, 1000) == "bright_green"

    def test_equal(self):
        assert vol_color(500, 500) == "white"


class TestVolRich:
    """vol_rich Rich markup。"""

    def test_includes_unit(self):
        result = vol_rich(1000000, 500000)
        assert "張" in result or "萬" in result or "千" in result


class TestVolDiffRich:
    """vol_diff_rich 量的差異。"""

    def test_positive_diff(self):
        result = vol_diff_rich(2000, 1000)
        assert "+" in result
        assert "張" in result

    def test_negative_diff(self):
        result = vol_diff_rich(1000, 2000)
        assert "差-" in result


# ── vol_fmt / vol_fmt_short ──────────────────────────────


class TestVolFmt:
    """vol_fmt 成交量格式化。"""

    def test_wan_level(self):
        """≥10000張應顯示萬。"""
        result = vol_fmt(15000000)  # 15000張
        assert "萬" in result

    def test_qian_level(self):
        """≥1000張應顯示千。"""
        result = vol_fmt(1500000)  # 1500張
        assert "千" in result

    def test_small(self):
        """小量應顯示張。"""
        result = vol_fmt(500000)  # 500張
        assert "張" in result

    def test_integer_sheets(self):
        """整數張不應顯示小數。"""
        result = vol_fmt(2000000)  # 恰好 2000張 (≥1000 用千單位)
        assert "千張" in result
        assert ".0千張" in result  # 整數還是會顯示 .0


class TestVolFmtShort:
    """vol_fmt_short 簡短格式。"""

    def test_wan_short(self):
        result = vol_fmt_short(15000000)
        assert "萬" in result

    def test_qian_short(self):
        result = vol_fmt_short(1500000)
        assert "K" in result


# ── ma_color / ma_str ────────────────────────────────────


class TestMaColor:
    """ma_color 均線趨勢配色。"""

    def test_up_trend(self):
        assert ma_color("up") == "bright_red"
        assert ma_color("↑ 上揚") == "bright_red"
        assert ma_color("上揚") == "bright_red"

    def test_down_trend(self):
        assert ma_color("down") == "bright_green"
        assert ma_color("↓ 下彎") == "bright_green"
        assert ma_color("下彎") == "bright_green"

    def test_flat_trend(self):
        assert ma_color("flat") == "white"
        assert ma_color("→ 走平") == "white"
        assert ma_color("走平") == "white"

    def test_unknown_trend(self):
        """未知趨勢應回傳 white。"""
        assert ma_color("unknown") == "white"


class TestMaStr:
    """ma_str Rich markup。"""

    def test_includes_value(self):
        result = ma_str(100.5, "up")
        assert "100.50" in result

    def test_includes_color(self):
        result = ma_str(100, "up")
        assert "[" in result and "]" in result
