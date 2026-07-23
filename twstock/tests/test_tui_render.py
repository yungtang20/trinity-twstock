# -*- coding: utf-8 -*-
"""test_tui_render.py — tui/render.py 覆蓋率測試。"""

from __future__ import annotations

from datetime import datetime
import os
from unittest.mock import MagicMock, patch

from twstock.tui import render


class TestMakeLayout:
    """make_layout 依終端寬度決定 layout 結構。"""

    def test_layout_has_all_sections(self):
        """layout 應包含 header/status/market/menu/footer。"""
        layout = render.make_layout()
        # Layout 用 get() 存取子區域
        assert layout.get("header") is not None
        assert layout.get("status") is not None
        assert layout.get("market") is not None
        assert layout.get("menu") is not None
        assert layout.get("footer") is not None

    @patch("twstock.tui.render.shutil.get_terminal_size")
    def test_narrow_terminal(self, mock_size):
        """窄終端機 (<75) 應設定較大的 market_size。"""
        mock_size.return_value = MagicMock(columns=60)
        layout = render.make_layout()
        # 驗證 layout 成功建立
        assert layout is not None


class TestRenderMarketPanel:
    """_render_market_panel 處理有/無指數資料。"""

    def test_no_indices_shows_loading(self):
        """無指數資料時應顯示「獲取中」訊息。"""
        mock_layout = MagicMock()
        render._render_market_panel(mock_layout, indices=None)
        mock_layout.__getitem__.return_value.update.assert_called_once()

    def test_with_indices(self):
        """有指數資料時應渲染表格。"""
        mock_layout = MagicMock()
        indices = {
            "TAIEX": {
                "price": 22000,
                "change": 100,
                "pct": 0.45,
                "amount": 3000,
                "up": 500,
                "down": 300,
                "flat": 100,
                "l_up": 10,
                "l_down": 5,
            },
            "OTC": {
                "price": 230,
                "change": 2,
                "pct": 0.87,
                "amount": 800,
                "up": 200,
                "down": 150,
                "flat": 50,
                "l_up": 3,
                "l_down": 2,
            },
            "date": "2026-07-02",
        }
        render._render_market_panel(mock_layout, indices=indices)
        mock_layout.__getitem__.return_value.update.assert_called_once()

    def test_open_market_hides_previous_close_statistics(self):
        """盤中只顯示即時指數，不可顯示前一日成交額或漲跌家數。"""
        layout = MagicMock()
        stale = {
            "TAIEX": {
                "price": 44919.5,
                "change": 686.63,
                "pct": 1.55,
                "amount": 8663,
                "up": 870,
                "down": 142,
                "flat": 49,
                "l_up": 44,
                "l_down": 2,
            },
            "OTC": {
                "price": 397.04,
                "change": 15.08,
                "pct": 3.95,
                "amount": 1602,
                "up": 674,
                "down": 148,
                "flat": 51,
                "l_up": 29,
                "l_down": 2,
            },
        }
        with (
            patch("twstock.tui.render.Table") as table_cls,
            patch(
                "twstock.tui.render.shutil.get_terminal_size",
                return_value=os.terminal_size((120, 24)),
            ),
        ):
            render._render_market_panel(layout, stale, market_mode="🟢 開盤")

        taiex_group, otc_group = table_cls.return_value.add_row.call_args.args
        for group in (taiex_group, otc_group):
            details = [item.plain for item in group.renderables[1:]]
            assert details == [" 成交金額：盤後公布", " 漲跌家數：盤後公布"]

    def test_market_title_uses_system_clock(self):
        """標題應使用目前系統時間，而非上一交易日 API 時間。"""
        now = datetime(2026, 7, 22, 9, 5, 7)
        title = render._build_market_title(now, "🟢 開盤")
        assert title == "📊 市場: 115-07-22 09:05:07 🟢 開盤"


class TestRenderHeader:
    """_render_header 處理日期與時間顯示。"""

    def test_with_indices_date(self):
        """標題應使用系統日期。"""
        mock_layout = MagicMock()
        render._render_header(mock_layout, datetime.now())
        mock_layout.__getitem__.return_value.update.assert_called_once()

    def test_without_indices_date(self):
        """無 indices 日期時應使用現在時間。"""
        mock_layout = MagicMock()
        render._render_header(mock_layout, datetime.now())
        mock_layout.__getitem__.return_value.update.assert_called_once()


class TestRenderMenu:
    """_render_menu 應建立選單表格。"""

    def test_menu_renders(self):
        mock_layout = MagicMock()
        render._render_menu(mock_layout)
        mock_layout.__getitem__.return_value.update.assert_called_once()


class TestRenderStatus:
    """_render_status 應顯示系統狀態。"""

    def test_status_renders(self):
        mock_layout = MagicMock()
        info = {
            "status": "✅ 就緒",
            "size": "100 MB",
            "path": "/db",
            "stocks": 100,
            "first": "20200101",
            "last": "20260702",
        }
        render._render_status(mock_layout, info)
        mock_layout.__getitem__.return_value.update.assert_called_once()


class TestRenderFooter:
    """_render_footer 應顯示提示文字。"""

    def test_footer_renders(self):
        mock_layout = MagicMock()
        render._render_footer(mock_layout)
        mock_layout.__getitem__.return_value.update.assert_called_once()


class TestFetchMarketIndicesCached:
    """fetch_market_indices_cached 向後相容包裝。"""

    def test_returns_cache_data(self):
        """應回傳 _market_cache.get() 的結果。"""
        render._market_cache._data = {"test": 123}
        result = render.fetch_market_indices_cached()
        assert result == {"test": 123}
        # cleanup
        render._market_cache.invalidate()
