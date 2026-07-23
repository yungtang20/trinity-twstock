#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""official 套件公開 API — 外部僅允許從此模組導入。"""

# 確保 twstock 套件可被匯入（支援直接執行腳本）
# SSL 驗證設定：優先使用 certifi CA bundle
from .dividend_crawler import fetch_dividend_events, upsert_dividend_events
from .dividend_daily import run_dividend_daily
from .suspended import get_today_suspended
from .tdcc import fetch_tdcc_historical as fetch_tdcc_historical_from_tdcc
from .trading_calendar import (
    date_exists_in_history,
    get_last_trading_day,
    get_nth_trading_day_back,
    init_trading_calendar,
    is_trading_day,
)
from .updater import (
    get_recent_official_data_status,
    update_official_daily,
    update_tdcc_historical,
    update_tdcc_weekly,
)

__all__ = [
    # updater
    "update_official_daily",
    "update_tdcc_weekly",
    "update_tdcc_historical",
    "get_recent_official_data_status",
    # trading_calendar
    "init_trading_calendar",
    "is_trading_day",
    "get_nth_trading_day_back",
    "get_last_trading_day",
    "date_exists_in_history",
    # dividend_crawler
    "fetch_dividend_events",
    "upsert_dividend_events",
    # tdcc
    "fetch_tdcc_historical_from_tdcc",
    # dividend_daily
    "run_dividend_daily",
    # suspended
    "get_today_suspended",
]
