#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""official 套件公開 API — 外部僅允許從此模組導入。"""
import os
import sys

# 確保 twstock 套件可被匯入（支援直接執行腳本）
_PARENT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

# SSL 驗證設定：優先使用 certifi CA bundle
from twstock.utils import get_ssl_verify  # noqa: E402
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from .updater import update_official_daily, update_tdcc_weekly, update_tdcc_historical
from .trading_calendar import init_trading_calendar, is_trading_day
from .trading_calendar import get_nth_trading_day_back, get_last_trading_day, date_exists_in_history
from .dividend_crawler import fetch_dividend_events, upsert_dividend_events
from .tdcc import fetch_tdcc_historical as fetch_tdcc_historical_from_tdcc
from .dividend_daily import run_dividend_daily
from .suspended import get_today_suspended

__all__ = [
    # updater
    'update_official_daily',
    'update_tdcc_weekly',
    'update_tdcc_historical',
    # trading_calendar
    'init_trading_calendar',
    'is_trading_day',
    'get_nth_trading_day_back',
    'get_last_trading_day',
    'date_exists_in_history',
    # dividend_crawler
    'fetch_dividend_events',
    'upsert_dividend_events',
    # tdcc
    'fetch_tdcc_historical_from_tdcc',
    # dividend_daily
    'run_dividend_daily',
    # suspended
    'get_today_suspended',
]