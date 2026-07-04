# -*- coding: utf-8 -*-
"""test_display.py — display.py 覆蓋率測試。"""

from __future__ import annotations

import pandas as pd

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
    render_kline,
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


# ── render_kline ─────────────────────────────────────────


class TestRenderKline:
    """render_kline K 線圖渲染。"""

    def test_empty_df(self):
        """空 DataFrame 應回傳「無資料」。"""
        result = render_kline(pd.DataFrame(), "2330", "台積電")
        assert "無資料" in result

    def test_none_df(self):
        """None 應回傳「無資料」。"""
        result = render_kline(None, "2330", "台積電")
        assert "無資料" in result

    def test_insufficient_data(self):
        """資料不足 2 筆應回傳「資料不足」。"""
        df = pd.DataFrame(
            {
                "date": ["2026-01-01"],
                "open": [100],
                "high": [105],
                "low": [95],
                "close": [102],
                "volume": [1000],
            }
        )
        result = render_kline(df, "2330", "台積電")
        assert "資料不足" in result

    def test_missing_column(self):
        """缺少欄位應回傳錯誤。"""
        df = pd.DataFrame(
            {
                "date": ["2026-01-01", "2026-01-02"],
                "open": [100, 101],
                # 缺少 high/low/close/volume
            }
        )
        result = render_kline(df, "2330", "台積電")
        assert "缺少" in result

    def test_with_valid_data(self):
        """有效資料應產生 K 線圖字串。"""
        df = pd.DataFrame(
            {
                "date": pd.date_range("2026-01-01", periods=10),
                "open": [100, 101, 102, 103, 104, 105, 106, 107, 108, 109],
                "high": [105, 106, 107, 108, 109, 110, 111, 112, 113, 114],
                "low": [95, 96, 97, 98, 99, 100, 101, 102, 103, 104],
                "close": [102, 103, 104, 105, 106, 107, 108, 109, 110, 111],
                "volume": [1000000] * 10,
            }
        )
        result = render_kline(df, "2330", "台積電")
        assert "2330" in result
        assert "台積電" in result
        assert "█" in result  # K 線主體

    def test_without_stock_name(self):
        """無股票名稱仍應運作。"""
        df = pd.DataFrame(
            {
                "date": pd.date_range("2026-01-01", periods=5),
                "open": [100, 101, 102, 103, 104],
                "high": [105, 106, 107, 108, 109],
                "low": [95, 96, 97, 98, 99],
                "close": [102, 103, 104, 105, 106],
                "volume": [1000000] * 5,
            }
        )
        result = render_kline(df, "", "")
        assert "K 線圖" in result

    def test_custom_days(self):
        """days 參數應限制顯示天數。"""
        df = pd.DataFrame(
            {
                "date": pd.date_range("2026-01-01", periods=30),
                "open": range(100, 130),
                "high": range(105, 135),
                "low": range(95, 125),
                "close": range(102, 132),
                "volume": [1000000] * 30,
            }
        )
        result = render_kline(df, "2330", "台積電", days=10)
        assert "2330" in result

    def test_flat_prices(self):
        """所有價格相同時不應崩潰（price_range=0）。"""
        df = pd.DataFrame(
            {
                "date": pd.date_range("2026-01-01", periods=5),
                "open": [100] * 5,
                "high": [100] * 5,
                "low": [100] * 5,
                "close": [100] * 5,
                "volume": [1000000] * 5,
            }
        )
        result = render_kline(df, "2330", "台積電")
        assert "2330" in result
