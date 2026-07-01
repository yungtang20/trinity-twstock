# twstock/official/dividend_daily.py
"""
Daily dividend announcement crawler.
Fetches upcoming ex-dividend events from TWSE/TPEx official APIs
for the current year, and writes to dividend_events table.

Called by: main.py -> run_historical_update_menu() 選項 4（手動「同步除權息事件」）
Writes to: taiwan_stock_unified.db -> dividend_events
"""
import logging
from datetime import date
import pandas as pd

import sys
from pathlib import Path
_twstock_dir = str(Path(__file__).resolve().parent.parent)
if _twstock_dir not in sys.path:
    sys.path.insert(0, _twstock_dir)

from official.dividend_crawler import fetch_dividend_events, upsert_dividend_events

logger = logging.getLogger(__name__)


def fetch_current_year_dividends() -> pd.DataFrame:
    """Scan the entire current year for dividend announcements."""
    today = date.today()
    year = today.year
    start_date = f"{year}-01-01"
    end_date = today.strftime("%Y-%m-%d")

    logger.info(f"Scanning dividend events for {start_date} ~ {end_date}...")

    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    try:
        df = fetch_dividend_events(start_date, end_date)
        return df
    except Exception as e:
        logger.error(f"Error fetching current year dividends: {e}")
        return pd.DataFrame()


def write_dividend_events(df: pd.DataFrame) -> int:
    """Write dividend events to database."""
    if df.empty:
        return 0
    try:
        upsert_dividend_events(df)
        return len(df)
    except Exception as e:
        logger.error(f"Error writing dividend events: {e}")
        return 0


def run_dividend_daily():
    """
    Entry point for manual dividend sync.
    1. Fetch current year dividend announcements
    2. Write to dividend_events table
    """
    print(f"  -> 抓取當年除權息公告 ({date.today().year}年)...")
    df = fetch_current_year_dividends()

    if df.empty:
        print("    無新的除權息事件")
        return

    count = write_dividend_events(df)
    print(f"    除權息事件: {count} 筆")
