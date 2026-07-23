# -*- coding: utf-8 -*-
"""TUIApp — 互動式選單主循環（狀態封裝）。

A + ① 組合：所有進入一律 Enter，input 期間不即時刷 dashboard。
每次 blocking_input 返還時才 render_dashboard 一次。
"""

from __future__ import annotations

from twstock.input_helper import blocking_input
from twstock.strategy.composites import run_composite
from twstock.strategy.strategies import interactive_menu as strategies_menu
from twstock.tui.menu import (
    run_daily_update,
    run_db_maintenance,
    run_historical_update_menu,
)
from twstock.tui.render import render_dashboard, wait_for_market_cache, warmup_market_cache
from twstock.tui.state_machine import (
    ActionType,
    TUIState,
    dispatch_main_menu,
)
from twstock.terminal import console
from twstock.utils import get_token  # noqa: F401


class TUIApp:
    """封裝 TUI 狀態與主循環。

    Usage::

        app = TUIApp()
        app.run()
    """

    # ── public ─────────────────────────────────────────────
    def run(self) -> None:
        """進入主選單 loop（直到使用者按 0）。

        每次 blocking_input 返還後才 render_dashboard（① 組合）。
        """
        state = TUIState.MAIN_MENU
        initial_home = True
        while state != TUIState.EXIT:
            # 首次進入或從功能返回首頁時觸發行情；等待輸入期間不定時刷新。
            warmup_market_cache()
            render_dashboard()
            if initial_home:
                # 第一張畫面先立即顯示「正在獲取」；背景完成後只重畫一次，
                # 避免 blocking_input 令該狀態永久留在畫面上。
                wait_for_market_cache()
                render_dashboard()
                initial_home = False
            ch = blocking_input("\n🔍 輸入選項或 4 碼股號，再按 Enter：")
            transition = dispatch_main_menu(ch)
            state = transition.next_state
            self._execute_action(transition)

    def _execute_action(self, transition) -> None:
        """執行動作（副作用），單一失敗不終止整個互動式介面。"""
        try:
            if transition.action == ActionType.RUN_DAILY_UPDATE:
                run_daily_update()
            elif transition.action == ActionType.RUN_HISTORICAL_UPDATE:
                run_historical_update_menu()
            elif transition.action == ActionType.RUN_STRATEGY_MENU:
                strategies_menu()
            elif transition.action == ActionType.RUN_DB_MAINTENANCE:
                run_db_maintenance()
            elif transition.action == ActionType.RUN_COMPOSITE:
                run_composite(transition.payload, allow_live_quote=True)
        except Exception as exc:
            console.print(f"[red]❌ 操作失敗：{exc}[/red]")
            blocking_input("\n按 Enter 返回主選單...")
