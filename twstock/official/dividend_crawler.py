#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
official/dividend_crawler.py
Fetch ex-rights and ex-dividends data from TWSE and TPEx APIs, with FinMind fallback.
"""
import requests
import pandas as pd
import time
from datetime import datetime, timedelta
import sqlite3
import os
import sys

from .utils import safe_float

# Windows Encoding Fix
if sys.platform == "win32":
    os.system('chcp 65001 > nul')
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stdin.reconfigure(encoding='utf-8')
    except AttributeError: pass

# [AI MOD] Import unified database path from db.py
import sys
from pathlib import Path
_PARENT = Path(__file__).resolve().parent.parent
if str(_PARENT) not in sys.path:
    sys.path.append(str(_PARENT))
from db import DB_PATH

# FinMind API fallback
try:
    from fetcher import DataFetcher
    FINMIND_AVAILABLE = True
except ImportError:
    FINMIND_AVAILABLE = False

from retry import retry_get

def _convert_date(date_str: str, input_format: str) -> str:
    """Convert 'YYYYMMDD' or 'YYY/MM/DD' to standard 'YYYY-MM-DD'"""
    if input_format == 'YYYYMMDD':
        return datetime.strptime(date_str, '%Y%m%d').strftime('%Y-%m-%d')
    elif input_format == 'YYY/MM/DD':
        year, month, day = date_str.split('/')
        year = str(int(year) + 1911)
        return f"{year}-{month}-{day}"
    return date_str

# [AI MOD] Added ROC date conversions to clean up API calls
def _convert_roc_to_ad(roc_date_str: str) -> str:
    """Convert ROC date 'YYY/MM/DD' or 'YYY年MM月DD日' to 'YYYY-MM-DD'"""
    try:
        clean = roc_date_str.replace('年', '/').replace('月', '/').replace('日', '').strip()
        parts = clean.split('/')
        y = str(int(parts[0]) + 1911)
        m = f"{int(parts[1]):02d}"
        d = f"{int(parts[2]):02d}"
        return f"{y}-{m}-{d}"
    except (ValueError, TypeError):
        return None

def _convert_percent(value_str: str) -> float:
    """Convert string with commas to float"""
    if value_str is None or value_str == '0' or value_str == '':
        return 0.0
    try:
        return safe_float(value_str.replace(',', ''))
    except (ValueError, TypeError):
        return 0.0

def fetch_finmind_dividend_data(stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Fetch individual stock dividend data via FinMind API as a fallback"""
    if not FINMIND_AVAILABLE:
        print("  FinMind API is not available, skipping fallback fetch")
        return pd.DataFrame()

    try:
        fetcher = DataFetcher()
        df = fetcher.fetch_dividend_events(stock_code, start_date, end_date)
        if not df.empty:
            print(f"  Fetched {len(df)} ex-dividend records via FinMind API")
            return df
    except Exception as e:
        print(f"  FinMind API fetch failed: {e}")

    return pd.DataFrame()

# [AI MOD] Hyper-optimized TWSE RWD endpoint support covering all stocks in one call
def fetch_twse_dividend_events(start_date: str, end_date: str) -> pd.DataFrame:
    """Fetch all ex-rights/ex-dividends events for listed stocks in the date range"""
    start_date_int = start_date.replace('-', '')
    end_date_int = end_date.replace('-', '')
    # Use TWSE RWD URL with startDate & endDate to query the entire market over any date range
    url = f"https://www.twse.com.tw/rwd/zh/exRight/TWT49U?response=json&startDate={start_date_int}&endDate={end_date_int}"

    resp = retry_get(
        url,
        timeout=30,
        retries=3,
        backoff=1.0,
        verify=False,
    )
    if resp is None:
        print(f"  [ERROR] TWSE crawler failed after retries")
        return pd.DataFrame()

    data = resp.json()

    if not data.get('data'):
        print(f"  No TWSE dividend data found for this period")
        return pd.DataFrame()

    rows = []
    for row in data['data']:
        if len(row) < 7:
            continue
        event_date = _convert_roc_to_ad(row[0])
        if not event_date:
            continue
        stock_id = str(row[1]).strip()
        stock_name = row[2]
        before_price = _convert_percent(row[3])
        after_price = _convert_percent(row[4])
        reference_price = after_price

        # Extract cash/stock dividends using the exact mathematical formulas
        val = _convert_percent(row[5])
        q_x = row[6] # '權' or '息'

        cash_dividend = 0.0
        stock_dividend = 0.0
        if '息' in q_x:
            cash_dividend = val
        elif '權' in q_x:
            if after_price > 0:
                stock_dividend = (before_price / after_price - 1.0) * 10.0

        rows.append({
            'stock_id': stock_id,
            'event_date': event_date,
            'before_price': before_price,
            'after_price': after_price,
            'reference_price': reference_price,
            'cash_dividend': cash_dividend,
            'stock_dividend': stock_dividend,
            'source': 'twse'
        })
    # print(f"  [SUCCESS] TWSE fetched: {len(rows)} events")
    return pd.DataFrame(rows)

# [AI MOD] Hyper-optimized TPEx RWD endpoint support covering all stocks in one call via 'ed'
def fetch_tpex_dividend_events(start_date: str, end_date: str) -> pd.DataFrame:
    """Fetch all ex-rights/ex-dividends events for OTC stocks in the date range"""
    def _roc_date(yyyymmdd):
        dt = datetime.strptime(yyyymmdd, '%Y-%m-%d')
        roc_year = dt.year - 1911
        return f"{roc_year}/{dt.month:02d}/{dt.day:02d}"

    start_roc = _roc_date(start_date)
    end_roc = _roc_date(end_date)

    url = "https://www.tpex.org.tw/web/stock/exright/dailyquo/exDailyQ_result.php"
    # Pass 'd' as start date and 'ed' as end date to fetch OTC ex-dividend range
    params = {
        'l': 'zh-tw',
        'd': start_roc,
        'ed': end_roc,
        'se': 'EW',
        's': '0,asc,0'
    }
    # print(f"  Fetching TPEx dividend events: {start_roc} ~ {end_roc}")

    resp = retry_get(
        url,
        params=params,
        timeout=30,
        retries=3,
        backoff=1.0,
        verify=False,
    )
    if resp is None:
        print(f"  [ERROR] TPEx crawler failed after retries")
        return pd.DataFrame()

    data = resp.json()

    tables = data.get('tables')
    if not tables or not tables[0].get('data'):
        print(f"  No TPEx dividend data found for this period")
        return pd.DataFrame()

    rows = []

    for row in tables[0]['data']:
        if len(row) < 15:
            continue
        event_date = _convert_date(row[0], 'YYY/MM/DD')
        if not event_date:
            continue
        stock_id = str(row[1]).strip()
        stock_name = row[2]
        before_price = safe_float(row[3])
        after_price = safe_float(row[4])
        reference_price = after_price

        cash_dividend = safe_float(row[13])
        stock_dividend = safe_float(row[14]) / 100.0  # Convert per 1000 shares to per 10 shares

        rows.append({
            'stock_id': stock_id,
            'event_date': event_date,
            'before_price': before_price,
            'after_price': after_price,
            'reference_price': reference_price,
            'cash_dividend': cash_dividend,
            'stock_dividend': stock_dividend,
            'source': 'tpex'
        })
    # print(f"  [SUCCESS] TPEx fetched: {len(rows)} events")
    return pd.DataFrame(rows)

# [AI MOD] Updated fetch_dividend_events unified function to fetch for the entire market
def fetch_dividend_events(start_date: str, end_date: str, use_finmind_fallback: bool = True) -> pd.DataFrame:
    """Unified function to fetch and combine listed/OTC ex-rights/ex-dividends events"""
    twse_df = fetch_twse_dividend_events(start_date, end_date)
    tpex_df = fetch_tpex_dividend_events(start_date, end_date)
    combined_df = pd.concat([twse_df, tpex_df], ignore_index=True)

    # Fallback to FinMind API if official sources return empty
    if combined_df.empty and use_finmind_fallback and FINMIND_AVAILABLE:
        print("  Official APIs returned empty. Falling back to FinMind API...")
        try:
            fetcher = DataFetcher()
            stock_list = fetcher.fetch_stock_meta()
            if not stock_list.empty:
                all_dividends = []
                # Fallback sequentially per stock (useful for missing individual tickers)
                for _, stock in stock_list.iterrows():
                    stock_id = stock['stock_id']
                    df = fetcher.fetch_dividend_events(stock_id, start_date, end_date)
                    if not df.empty:
                        all_dividends.append(df)
                if all_dividends:
                    combined_df = pd.concat(all_dividends, ignore_index=True)
                    print(f"  Fetched {len(combined_df)} records via FinMind API fallback")
        except Exception as e:
            print(f"  FinMind fallback failed: {e}")

    if combined_df.empty:
        return combined_df
    # Rename event_date to date for database consistency
    if 'event_date' in combined_df.columns:
        combined_df.rename(columns={'event_date': 'date'}, inplace=True)
    return combined_df.drop_duplicates(subset=['stock_id', 'date'])

def upsert_dividend_events(df: pd.DataFrame):
    """Write ex-rights/ex-dividends events into SQLite database (batch UPSERT)"""
    if df is None or df.empty:
        return
    df = df.copy()
    if 'event_date' in df.columns:
        df.rename(columns={'event_date': 'date'}, inplace=True)
    if 'before_price' not in df.columns:
        df['before_price'] = None
    if 'after_price' not in df.columns:
        df['after_price'] = None
    if 'reference_price' not in df.columns:
        df['reference_price'] = None
    if 'source' not in df.columns:
        df['source'] = 'official'

    # 使用 processor.py 的批量 UPSERT（ON CONFLICT DO UPDATE），不再逐筆 DELETE+INSERT
    from processor import DataProcessor
    DataProcessor().upsert_dividend_events(df)