# twstock/official/suspended.py
"""
Fetch today's suspended / designated trading stocks from TWSE/TPEx OpenAPI. [AI MOD]
These stocks legitimately have zero volume on their suspension dates
and should be excluded from data quality checks.

API sources:
  - TWSE: https://openapi.twse.com.tw/v1/announcement/punish
  - TPEx: https://www.tpex.org.tw/openapi/v1/tpex_disposal_information

Called by: main.py daily update flow
Writes to: audit_log (for record-keeping)
Returns: set of stock_ids that are suspended today
"""
import logging
import sqlite3
from datetime import datetime, date
import requests

# [AI MOD] Unified DB connection
import sys
from pathlib import Path
_twstock_dir = str(Path(__file__).resolve().parent.parent)
if _twstock_dir not in sys.path:
    sys.path.insert(0, _twstock_dir)
from db import get_connection

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}

def _parse_roc_range(period_str: str) -> tuple[date, date]:
    """
    Parse ROC period strings (e.g. '115/05/07~115/05/20' or '1150518~1150529')
    into Gregorian date objects (start_date, end_date). [AI MOD]
    """
    try:
        clean = period_str.replace("/", "").replace(" ", "").strip()
        parts = clean.split("~")
        if len(parts) != 2:
            parts = clean.split("～")
        if len(parts) != 2:
            return None, None
            
        def to_date(s: str) -> date:
            if len(s) != 7 or not s.isdigit():
                return None
            year = int(s[:3]) + 1911
            month = int(s[3:5])
            day = int(s[5:7])
            return date(year, month, day)
            
        d1 = to_date(parts[0])
        d2 = to_date(parts[1])
        return d1, d2
    except Exception:
        return None, None

def fetch_twse_suspended() -> set[str]:
    """
    Fetch TWSE designated / suspended stocks for today. [AI MOD]
    Using official OpenAPI to retrieve all current disposition records.
    """
    url = "https://openapi.twse.com.tw/v1/announcement/punish"
    
    # Suppress SSL verification warnings dynamically
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15, verify=False)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.warning(f"TWSE suspended fetch failed: {e}")
        return set()

    suspended = set()
    today = date.today()
    for row in data:
        try:
            stock_id = str(row.get("Code", "")).strip()
            period_str = str(row.get("DispositionPeriod", "")).strip()
            if stock_id and period_str:
                d_start, d_end = _parse_roc_range(period_str)
                if d_start and d_end and d_start <= today <= d_end:
                    suspended.add(stock_id)
        except Exception as e:
            logger.debug(f"Error parsing TWSE row: {row} - {e}")
            continue

    return suspended

def fetch_tpex_suspended() -> set[str]:
    """
    Fetch TPEx designated / suspended stocks for today. [AI MOD]
    Using official OpenAPI to retrieve all current disposition records.
    """
    url = "https://www.tpex.org.tw/openapi/v1/tpex_disposal_information"
    
    # Suppress SSL verification warnings dynamically
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15, verify=False)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.warning(f"TPEx suspended fetch failed: {e}")
        return set()

    suspended = set()
    today = date.today()
    for row in data:
        try:
            # TPEx code field is SecuritiesCompanyCode (e.g. '31351' or '5228')
            stock_code = str(row.get("SecuritiesCompanyCode", "")).strip()
            period_str = str(row.get("DispositionPeriod", "")).strip()
            
            # Keep first 4 characters if it's a standard stock ID
            if len(stock_code) >= 4:
                stock_id = stock_code[:4]
                if stock_id.isdigit() and period_str:
                    d_start, d_end = _parse_roc_range(period_str)
                    if d_start and d_end and d_start <= today <= d_end:
                        suspended.add(stock_id)
        except Exception as e:
            logger.debug(f"Error parsing TPEx row: {row} - {e}")
            continue

    return suspended

def _log_suspended(stocks: set[str], market: str):
    """Record suspended stocks in audit_log for traceability. [AI MOD]"""
    if not stocks:
        return
    conn = get_connection()
    try:
        cursor = conn.cursor()
        for sid in sorted(stocks):
            cursor.execute("""
                INSERT INTO audit_log (stock_id, action, status, detail)
                VALUES (?, 'suspended_check', 'info', ?)
            """, (sid, f"{market} suspended on {date.today().isoformat()}"))
        conn.commit()
    except Exception as e:
        logger.error(f"Failed to log suspended stocks: {e}")
    finally:
        conn.close()

def get_today_suspended() -> set[str]:
    """
    Main entry point. Returns the union of all suspended stock_ids today. [AI MOD]
    Also logs the result to audit_log.
    """
    print("  → 抓取今日暫停交易/處置股票清單...")

    twse = fetch_twse_suspended()
    tpex = fetch_tpex_suspended()
    all_suspended = twse | tpex

    if twse:
        _log_suspended(twse, "TWSE")
    if tpex:
        _log_suspended(tpex, "TPEx")

    if all_suspended:
        print(f"    ✅ 今日暫停交易/處置股票: {len(all_suspended)} 支")
        # [AI MOD] User requested to hide the detailed stock list for a cleaner UI
    else:
        print(f"    ✅ 今日無暫停交易股票")

    return all_suspended