# twstock/official/dividend_daily.py
"""
Daily dividend announcement crawler. [AI MOD]
Fetches upcoming ex-dividend events from TWSE/TPEx official APIs
for the current year, and writes to dividend_events table.

Called by: main.py daily update flow
Writes to: taiwan_stock_unified.db → dividend_events
"""
import logging
from datetime import date, datetime
import pandas as pd
import sqlite3

# [AI MOD] — Unified DB connection
import sys
from pathlib import Path
_twstock_dir = str(Path(__file__).resolve().parent.parent)
if _twstock_dir not in sys.path:
    sys.path.insert(0, _twstock_dir)
from db import get_connection
from official.dividend_crawler import fetch_dividend_events, upsert_dividend_events

logger = logging.getLogger(__name__)

def fetch_current_year_dividends() -> pd.DataFrame:
    """Scan the entire current year for dividend announcements using optimized range APIs. [AI MOD]"""
    today = date.today()
    year = today.year
    start_date = f"{year}-01-01"
    end_date = today.strftime("%Y-%m-%d")
    
    logger.info(f"Scanning dividend events for {start_date} ~ {end_date}...")
    
    # Suppress SSL verification warnings dynamically [AI MOD]
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    try:
        df = fetch_dividend_events(start_date, end_date, use_finmind_fallback=False)
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

def run_dividend_daily(recalc_adj: bool = True):
    """
    Entry point for daily update flow. [AI MOD]
    1. Fetch current year dividend announcements
    2. Write to dividend_events table
    3. Recompute adj_factor for affected stocks (if recalc_adj=True)

    Args:
        recalc_adj: 是否重新計算還原價 (adj_factor)。設為 False 可跳過還原因子計算。
    """
    print(f"  → 抓取當年除權息公告 ({date.today().year}年)...")
    df = fetch_current_year_dividends()

    if df.empty:
        print("    無新的除權息事件")
        return

    count = write_dividend_events(df)
    print(f"    ✅ 除權息事件: {count} 筆")

    if not recalc_adj:
        print("    ⏭️ 跳過還原價計算 (recalc_adj=False)")
        return

    # Chain: recompute adj_factor for stocks with new dividend events
    affected_stocks = df["stock_id"].unique().tolist()
    print(f"  → 重算 {len(affected_stocks)} 支股票的還原因子...")
    _recompute_adj_factors(affected_stocks)
    print(f"    ✅ adj_factor 更新完成")

def _recompute_adj_factors(stock_ids: list[str]):
    """
    Recompute adj_factor for given stocks based on dividend_events. [AI MOD]
    Uses backward adjustment: adj_factor = product of (1 - cash_div/close) across all events.
    """
    if not stock_ids:
        return

    conn = get_connection()
    try:
        for stock_id in stock_ids:
            # Get all dividend events for this stock, ordered by date DESC
            events = conn.execute("""
                SELECT date, cash_dividend, stock_dividend
                FROM dividend_events
                WHERE stock_id = ? AND (cash_dividend > 0 OR stock_dividend > 0)
                ORDER BY date DESC
            """, (stock_id,)).fetchall()

            if not events:
                continue

            # Get all history dates for this stock
            history = conn.execute("""
                SELECT date, close FROM stock_history
                WHERE stock_id = ?
                ORDER BY date ASC
            """, (stock_id,)).fetchall()

            if not history:
                continue

            # Build adj_factor: start from most recent = 1.0, work backwards
            # For each ex-dividend date, all dates BEFORE it get multiplied
            factor = 1.0
            event_map = {}
            for ev in events:
                ex_date = ev[0]
                cash = ev[1] or 0.0
                stock = ev[2] or 0.0

                # Find close price on the day before ex-dividend
                prev_close = None
                for h in history:
                    if h[0] < ex_date:
                        prev_close = h[1]
                    elif h[0] >= ex_date:
                        break

                if prev_close and prev_close > 0:
                    # Forward adjustment factor for this single event
                    adj = (prev_close - cash) / prev_close
                    if adj > 0:
                        event_map[ex_date] = adj

            # Now compute adj_factor for each date
            updates = []
            cumulative = 1.0
            # Process events in chronological order
            sorted_events = sorted(event_map.items(), reverse=True)

            for h in history:
                d = h[0]
                # Apply all events that happen AFTER this date
                while sorted_events and sorted_events[-1][0] <= d:
                    sorted_events.pop()

                # Factor = product of all events after this date
                factor = 1.0
                for _, adj in sorted_events:
                    factor *= adj

                updates.append((round(factor, 6), stock_id, d))

            # Batch update
            conn.executemany("""
                UPDATE stock_history SET adj_factor = ?
                WHERE stock_id = ? AND date = ?
            """, updates)

        conn.commit()
    finally:
        conn.close()