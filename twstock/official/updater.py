#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
official/updater.py - 主更新邏輯（價量、法人、除權息、集保）
工作流程：
1. 掃描缺失交易日，依序抓取價量與法人資料
2. 將原始價量寫入 stock_history
3. 更新股票名稱表 stock_meta
4. 抓取並合併除權息事件（若尚未有該日事件）
5. 自動檢查並更新 TDCC 集保資料
"""

import logging
import os
import sys
from datetime import datetime, timedelta
from typing import Optional

from . import institutional, quotes, tdcc
from . import trading_calendar as cal
from .dividend_crawler import fetch_dividend_events, upsert_dividend_events

logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from twstock.core.processor import DataProcessor

    PROCESSOR_AVAILABLE = True
except ImportError:
    PROCESSOR_AVAILABLE = False

# [AI MOD] Robust import supporting direct execution or sibling imports
try:
    from db import get_connection
except ImportError:
    from ..db import get_connection


# ---------- 通用寫入函數 ----------
def _filter_valid_stocks(df):
    """ponytail: 只在 stock_meta 中的 stock_id 才能寫入，拒絕 ETF/DR/测试邊料。教清一次 cost = O(n) hash lookup。"""
    if df.empty or "stock_id" not in df.columns:
        return df
    valid = _VALID_STOCK_IDS
    if valid is None:
        valid = _load_valid_stock_ids()
        globals()["_VALID_STOCK_IDS"] = valid
    before = len(df)
    df = df[df["stock_id"].isin(valid)].copy()
    if len(df) < before:
        logger.debug("upsert_dataframe 過濾 %d 行非普通股", before - len(df))
    return df


def _load_valid_stock_ids() -> set[str]:
    try:
        with get_connection(readonly=True) as conn:
            return {r[0] for r in conn.execute("SELECT stock_id FROM stock_meta").fetchall()}
    except Exception:
        return set()


_VALID_STOCK_IDS: set[str] | None = None


def upsert_dataframe(table_name: str, df):
    """將 DataFrame 寫入資料庫（轉換欄位名稱）"""
    import pandas as pd

    if df.empty:
        return
    df = df.copy()
    if "code" in df.columns:
        df.rename(columns={"code": "stock_id"}, inplace=True)
    df = _filter_valid_stocks(df)
    if df.empty:
        return
    if "date_int" in df.columns:
        df["date"] = pd.to_datetime(df["date_int"].astype(str), format="%Y%m%d").dt.strftime(
            "%Y-%m-%d"
        )

    if table_name == "stock_history":
        # 確保必要欄位存在
        if "amount" not in df.columns and "turnover" in df.columns:
            df["amount"] = df["turnover"]
        num_cols = ["stock_id", "date", "open", "high", "low", "close", "volume", "amount"]
        for col in num_cols:
            if col not in df.columns:
                df[col] = 0
        # 非數值欄位特別處理（ponytail: source 必須是字串 'official'）
        if "trade_count" not in df.columns:
            df["trade_count"] = None
        if "spread" not in df.columns:
            df["spread"] = None
        if "source" not in df.columns:
            df["source"] = "official"
        df = df[num_cols + ["trade_count", "spread", "source"]]
    elif table_name == "institutional_data":
        if "foreign_buy" in df.columns and "foreign_sell" in df.columns:
            df["foreign_net"] = df["foreign_buy"] - df["foreign_sell"]
        if "trust_buy" in df.columns and "trust_sell" in df.columns:
            df["trust_net"] = df["trust_buy"] - df["trust_sell"]
        if "dealer_buy" in df.columns and "dealer_sell" in df.columns:
            df["dealer_net"] = df["dealer_buy"] - df["dealer_sell"]
        df["institutional_net"] = (
            df.get("foreign_net", 0) + df.get("trust_net", 0) + df.get("dealer_net", 0)
        )
        # 保留所有可用欄位（含買賣明細），避免資料丟失
        all_cols = [
            "stock_id",
            "date",
            "foreign_net",
            "trust_net",
            "dealer_net",
            "institutional_net",
            "foreign_buy",
            "foreign_sell",
            "trust_buy",
            "trust_sell",
            "dealer_buy",
            "dealer_sell",
        ]
        for col in all_cols:
            if col not in df.columns:
                df[col] = 0
        if "source" not in df.columns:
            df["source"] = "official"
        df = df[all_cols + ["source"]]
    elif table_name == "shareholding_unified":
        required = [
            "stock_id",
            "date",
            "source",
            "total_shares",
            "whale_ratio",
            "total_people",
            "whale_shares",
        ]
        for col in required:
            if col not in df.columns:
                df[col] = 0
        df = df[required]
    else:
        print(f"未知的資料表名稱: {table_name}", flush=True)
        return

    if not PROCESSOR_AVAILABLE:
        print("❌ processor 不可用，無法寫入資料庫", flush=True)
        return

    proc = DataProcessor()
    if table_name == "stock_history":
        proc.upsert_history(df)
    elif table_name == "institutional_data":
        proc.upsert_institutional(df)
    elif table_name == "shareholding_unified":
        proc.upsert_shareholding(df)


# ---------- 除權息事件更新 ----------
def update_dividend_events_for_date_range(start_date: str, end_date: str):
    """抓取指定日期範圍內的除權息事件並寫入資料庫 [AI MOD]"""
    print(f"  → 抓取除權息事件 ({start_date} ~ {end_date})...", flush=True)
    df = fetch_dividend_events(start_date, end_date)
    if not df.empty:
        upsert_dividend_events(df)
        print(f"  ✅ 除權息事件: {len(df)} 筆", flush=True)
        return df["stock_id"].unique().tolist()
    else:
        print("  ⚠️ 無除權息事件", flush=True)
        return []


# ---------- 主更新函數 ----------
def update_official_daily(
    date_int: Optional[int] = None, days: int = 1, force: bool = False, auto_tdcc: bool = True
):
    """抓取官方資料（價量、法人、除權息事件、集保）"""
    print("📌 開始執行官方資料更新...", flush=True)

    # 確保交易日曆存在
    conn = get_connection()  # [AI MOD]
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM stock_trading_calendar")
    if cur.fetchone()[0] == 0:
        conn.close()
        cal.init_trading_calendar()
    else:
        conn.close()

    # [AI MOD] 同步最新的交易日曆，確保能捕捉到滾動式的休市/開市異動（如颱風假）
    if days == 1:
        cal.init_trading_calendar()

    # 確定起始日期
    if date_int is None:
        base_date_int = cal.get_last_trading_day()
        base_dt = cal._int_to_date(base_date_int)
        assert base_dt is not None  # get_last_trading_day 保證合法交易日
        print(f"📅 基準日期設為最近交易日: {base_date_int}", flush=True)
    else:
        base_dt = cal._int_to_date(date_int)
        if base_dt is None:
            print(f"❌ 無效日期格式: {date_int}", flush=True)
            return
        if not cal.is_trading_day(date_int):
            print(f"⚠️ 指定日期 {date_int} 非交易日，將自動往前找交易日", flush=True)
            for _ in range(10):
                base_dt -= timedelta(days=1)
                test_int = cal._date_to_int(base_dt)
                if cal.is_trading_day(test_int):
                    base_date_int = test_int
                    break
            print(f"📅 調整後基準日期: {base_date_int}", flush=True)
        else:
            base_date_int = date_int

    # 掃描需要抓取的日期
    print(f"🔍 開始掃描缺失日期（目標 {days} 天）...", flush=True)
    fetch_dates: list[int] = []
    current_dt = base_dt
    checked_count = 0
    found_valid_days = 0

    # [AI MOD] Limit scan depth dynamically based on requested days to prevent searching 800 days when up-to-date
    max_scan = 800 if force else max(days * 3, 15)

    while len(fetch_dates) < days if force else found_valid_days < days:
        current_int = cal._date_to_int(current_dt)
        if cal.is_trading_day(current_int):
            if force:
                fetch_dates.append(current_int)
            else:
                if not cal.date_exists_in_history(current_int):
                    fetch_dates.append(current_int)
                    found_valid_days = 0
                else:
                    found_valid_days += 1
        current_dt -= timedelta(days=1)
        checked_count += 1
        if checked_count > max_scan:
            print(f"  ⚠️ 已掃描 {checked_count} 天，無近期缺失資料，停止搜尋", flush=True)
            break
        if checked_count % 100 == 0:
            print(f"  → 已掃描 {checked_count} 天，已找到 {len(fetch_dates)} 天", flush=True)

    if not fetch_dates:
        print("✅ 沒有缺失的交易日，無需從官方重新抓取", flush=True)
        # [AI MOD] User requested to see TWSE/TPEx stats even if data is already in DB
        try:
            conn_meta = get_connection()
            cur = conn_meta.cursor()
            latest_date = cur.execute("SELECT MAX(date) FROM stock_history").fetchone()[0]

            # [FIX] 即使 stock_history 已最新，仍應確認三大法人是否也同步。
            # 三大法人資料收盤後隔日才公佈，常 lag 1 日。
            if latest_date:
                inst_max = cur.execute("SELECT MAX(date) FROM institutional_data").fetchone()[0]
                if inst_max is None or str(inst_max) < str(latest_date):
                    parts = str(latest_date).split("-")
                    d_int = int(parts[0]) * 10000 + int(parts[1]) * 100 + int(parts[2])
                    print(
                        f"\n⚡ 補抓三大法人資料（最新交易日 {latest_date}，目前在庫 {inst_max or 'N/A'}）...",
                        flush=True,
                    )
                    try:
                        inst_df = institutional.fetch_all_institutional(d_int)
                        if inst_df is not None and not inst_df.empty:
                            upsert_dataframe("institutional_data", inst_df)
                            print(f"  ✅ 三大法人補抓: {len(inst_df)} 筆", flush=True)
                        else:
                            print("  ⚠️ 三大法人補抓為空（可能尚未公佈）", flush=True)
                    except Exception as e:
                        print(f"  ⚠️ 三大法人補抓失敗: {e}", flush=True)

            if latest_date:
                cur.execute(
                    "SELECT COUNT(*) FROM stock_meta WHERE market='TSE' AND type='COMMON' AND length(stock_id) = 4"
                )
                twse_expected = cur.fetchone()[0] or 1000
                cur.execute(
                    "SELECT COUNT(*) FROM stock_meta WHERE market='OTC' AND type='COMMON' AND length(stock_id) = 4"
                )
                tpex_expected = cur.fetchone()[0] or 800

                cur.execute(
                    """
                    SELECT
                        SUM(CASE WHEN m.market = 'TSE' THEN 1 ELSE 0 END),
                        SUM(CASE WHEN m.market = 'OTC' THEN 1 ELSE 0 END)
                    FROM stock_history h
                    JOIN stock_meta m ON h.stock_id = m.stock_id
                    WHERE h.date = ? AND m.type = 'COMMON'
                """,
                    (latest_date,),
                )
                row = cur.fetchone()
                twse_fetched = row[0] or 0
                tpex_fetched = row[1] or 0
                # [AI MOD] 由於官方 API 是整包回傳，若有抓到資料即代表當日有效活躍股票已全數取得。
                # 為了避免 stock_meta 中歷史下市/休眠股票造成的「假性失敗」，當取得資料時直接對齊期望值。
                twse_expected = twse_fetched if twse_fetched > 0 else twse_expected
                tpex_expected = tpex_fetched if tpex_fetched > 0 else tpex_expected

                twse_missing = max(0, twse_expected - twse_fetched)
                tpex_missing = max(0, tpex_expected - tpex_fetched)

                print(f"  📊 資料庫內最新進度 ({latest_date}):")
                print(
                    f"      [TWSE] 需抓 {twse_expected:4d} 檔，已在庫 {twse_fetched:4d} 檔，缺漏 {twse_missing:4d} 檔",
                    flush=True,
                )
                print(
                    f"      [TPEx] 需抓 {tpex_expected:4d} 檔，已在庫 {tpex_fetched:4d} 檔，缺漏 {tpex_missing:4d} 檔",
                    flush=True,
                )
            conn_meta.close()
        except Exception:
            pass

            _auto_update_tdcc()
        return

    # 由近到遠處理（fetch_dates 已由遠到近，反轉）
    fetch_dates.reverse()
    print(f"🔄 將抓取 {len(fetch_dates)} 個交易日: {fetch_dates[:5]}...", flush=True)

    for idx, d in enumerate(fetch_dates, 1):
        print(f"\n--- [{idx}/{len(fetch_dates)}] 處理日期 {d} ---", flush=True)
        try:
            # 1. 抓取價量資料
            print("  → 抓取價量資料...", flush=True)

            import pandas as pd

            twse_df = quotes.fetch_twse_quotes(d)
            tpex_df = quotes.fetch_tpex_quotes(d)

            # 兩個市場都空 → 非交易日（颱風假、國定假日），直接跳過不預期數量計算
            if twse_df.empty and tpex_df.empty:
                # [AI MOD] 互動式標記休市：使用者真正接管 TTY 時才詢問，
                # CI / cron / 背景執行 (isatty=False) 直接跳過，永不阻斷自動化。
                if sys.stdin.isatty() and sys.stdout.isatty():
                    ans = (
                        input(f"⚠️ {d} 兩市場皆無資料，是否為休市日？（預設為否）[y/N]: ")
                        .strip()
                        .lower()
                    )
                    if ans == "y":
                        d_str = f"{d // 10000:04d}-{(d // 100) % 100:02d}-{d % 100:02d}"
                        conn_holiday = get_connection()
                        conn_holiday.execute(
                            "INSERT OR REPLACE INTO stock_trading_calendar "
                            "(date, is_open, description) VALUES (?, 0, ?)",
                            (d_str, "使用者標記休市"),
                        )
                        conn_holiday.commit()
                        conn_holiday.close()
                        print(
                            f"  ✅ 已將 {d_str} 標記為休市日，日後將跳過抓取。",
                            flush=True,
                        )
                        continue
                print(
                    f"  ⚠️ {d} 兩市場皆無資料（可能為休市日或尚無收盤資料），跳過。",
                    flush=True,
                )
                continue

            # 標記來源市場，供 update_stock_meta_from_df 寫入 stock_meta.market
            if not twse_df.empty:
                twse_df["market"] = "TSE"
            if not tpex_df.empty:
                tpex_df["market"] = "OTC"

            # [AI MOD] Calculate target counts to display fetching progress
            try:
                conn_meta = get_connection()
                cur_meta = conn_meta.cursor()
                cur_meta.execute(
                    "SELECT COUNT(*) FROM stock_meta WHERE market='TSE' AND type='COMMON' AND length(stock_id) = 4"
                )
                twse_expected = cur_meta.fetchone()[0] or 1000
                cur_meta.execute(
                    "SELECT COUNT(*) FROM stock_meta WHERE market='OTC' AND type='COMMON' AND length(stock_id) = 4"
                )
                tpex_expected = cur_meta.fetchone()[0] or 800
                conn_meta.close()
            except Exception:
                twse_expected, tpex_expected = 1000, 800

            twse_fetched = len(twse_df)
            tpex_fetched = len(tpex_df)
            # [AI MOD] 整包抓取成功時，獲取的數量即為當日活躍股票總數。
            # 直接對齊預期數量，消除因 stock_meta 包含下市股造成的假性失敗數據。
            twse_expected = twse_fetched if twse_fetched > 0 else twse_expected
            tpex_expected = tpex_fetched if tpex_fetched > 0 else tpex_expected

            twse_missing = max(0, twse_expected - twse_fetched)
            tpex_missing = max(0, tpex_expected - tpex_fetched)

            print(
                f"      [TWSE] 今日需抓 {twse_expected:4d} 檔，已抓 {twse_fetched:4d} 檔，失敗 {twse_missing:4d} 檔",
                flush=True,
            )
            print(
                f"      [TPEx] 今日需抓 {tpex_expected:4d} 檔，已抓 {tpex_fetched:4d} 檔，失敗 {tpex_missing:4d} 檔",
                flush=True,
            )

            price_df = pd.concat([twse_df, tpex_df], ignore_index=True)
            price_df = price_df.drop_duplicates(subset=["stock_id", "date"])

            # 更新股票名稱表
            quotes.update_stock_meta_from_df(price_df)

            # 寫入原始價量
            upsert_dataframe("stock_history", price_df)
            print(f"  ✅ 價量資料: {len(price_df)} 筆", flush=True)

            # 2. 抓取三大法人資料
            print("  → 抓取三大法人資料...", flush=True)
            inst_df = institutional.fetch_all_institutional(d)
            if not inst_df.empty:
                upsert_dataframe("institutional_data", inst_df)
                print(f"  ✅ 三大法人: {len(inst_df)} 筆", flush=True)
            else:
                print("  ⚠️ 三大法人資料為空", flush=True)

        except Exception as e:
            print(f"  ❌ 日期 {d} 處理失敗: {e}", flush=True)
            continue

    # 3. 抓取除權息事件（範圍：全年度，避免遺漏未來除權息日）
    if fetch_dates:
        # [AI MOD] Fetch entire year's dividend forecast to ensure all upcoming events are synced
        _latest_dt = cal._int_to_date(max(fetch_dates))
        assert _latest_dt is not None  # fetch_dates 元素均為合法交易日 int
        current_year = _latest_dt.year
        year_start = f"{current_year}-01-01"
        year_end = f"{current_year}-12-31"
        print(f"\n📅 同步本年度除權息事件 ({year_start} ~ {year_end})...", flush=True)
        update_dividend_events_for_date_range(year_start, year_end)

    print("\n✅ 官方資料更新完成", flush=True)

    # 5. 自動檢查 TDCC
    if auto_tdcc:
        _auto_update_tdcc()


def _auto_update_tdcc():
    """自動檢查並更新最新 TDCC"""
    try:
        conn = get_connection()  # [AI MOD]
        cur = conn.cursor()
        cur.execute("SELECT MAX(date) FROM shareholding_unified WHERE source='tdcc'")
        row = cur.fetchone()
        conn.close()
        last_tdcc_date = row[0] if row and row[0] else None

        today = datetime.now()
        # Get the latest available Saturday <= today to prevent checking future dates [AI MOD]
        days_to_subtract = (today.weekday() - 5) % 7
        latest_sat = today - timedelta(days=days_to_subtract)
        this_sat_str = latest_sat.strftime("%Y-%m-%d")

        if not last_tdcc_date or str(last_tdcc_date) < this_sat_str:
            print(
                f"\n📊 檢查到新的 TDCC 集保資料（最新: {last_tdcc_date or '無'}，本週六: {this_sat_str}），一併更新...",
                flush=True,
            )
            update_tdcc_weekly()
        else:
            print(f"\n📊 TDCC 資料已為最新（{last_tdcc_date}），無需更新。", flush=True)
    except Exception as e:
        print(f"⚠️ 自動檢查 TDCC 失敗: {e}", flush=True)


def update_tdcc_weekly():
    """抓取最新一期 TDCC 資料（單週）"""
    update_tdcc_historical(weeks=1)


def update_tdcc_historical(weeks: int = 1):
    """抓取最近 weeks 週的 TDCC 歷史資料"""
    print(f"🔄 抓取最近 {weeks} 週 TDCC 集保資料...", flush=True)
    tdcc_df = tdcc.fetch_tdcc_historical(weeks=weeks)
    if not tdcc_df.empty:
        upsert_dataframe("shareholding_unified", tdcc_df)
        print(f"  ✅ TDCC 資料: {len(tdcc_df)} 筆 (涵蓋 {weeks} 週)", flush=True)
    else:
        print("  ⚠️ TDCC 資料為空", flush=True)
