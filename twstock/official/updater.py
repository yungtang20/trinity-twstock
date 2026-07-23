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
import sys
from datetime import timedelta
from types import SimpleNamespace
from typing import Optional

from .dividend_crawler import fetch_dividend_events, upsert_dividend_events
from .institutional import fetch_all_institutional
from .quotes import fetch_tpex_quotes, fetch_twse_quotes, update_stock_meta_from_df
from .tdcc import fetch_tdcc_historical
from .trading_calendar import (
    _date_to_int,
    _int_to_date,
    date_exists_in_history,
    get_last_trading_day,
    init_trading_calendar,
    is_trading_day,
)
from twstock.core.processor import DataProcessor
from twstock.db import get_connection

logger = logging.getLogger(__name__)

PROCESSOR_AVAILABLE = True

# Compatibility namespaces preserve established patch points without using a
# package-level ``from . import ...`` during ``official`` initialization.
institutional = SimpleNamespace(fetch_all_institutional=fetch_all_institutional)
quotes = SimpleNamespace(
    fetch_twse_quotes=fetch_twse_quotes,
    fetch_tpex_quotes=fetch_tpex_quotes,
    update_stock_meta_from_df=update_stock_meta_from_df,
)
tdcc = SimpleNamespace(fetch_tdcc_historical=fetch_tdcc_historical)
cal = SimpleNamespace(
    _date_to_int=_date_to_int,
    _int_to_date=_int_to_date,
    date_exists_in_history=date_exists_in_history,
    get_last_trading_day=get_last_trading_day,
    init_trading_calendar=init_trading_calendar,
    is_trading_day=is_trading_day,
)


# ---------- 通用寫入函數 ----------
def _filter_valid_stocks(df):
    """ponytail: 只在 stock_meta 中的 stock_id 才能寫入，拒絕 ETF/DR/测试邊料。教清一次 cost = O(n) hash lookup。"""
    if df.empty or "stock_id" not in df.columns:
        return df
    valid = _VALID_STOCK_IDS
    if valid is None:
        valid = _load_valid_stock_ids()
        globals()["_VALID_STOCK_IDS"] = valid
    if valid is None:
        # DB 查詢失敗，放行全部 rows 並 log warning（避免靜默丟資料）
        logger.warning("_filter_valid_stocks: _valid_stock_ids unavailable, saving ALL rows unfiltered")
        return df
    before = len(df)
    df = df[df["stock_id"].isin(valid)].copy()
    if len(df) < before:
        logger.debug("upsert_dataframe 過濾 %d 行非普通股", before - len(df))
    return df


def _load_valid_stock_ids() -> set[str] | None:
    try:
        with get_connection(readonly=True) as conn:
            return {r[0] for r in conn.execute("SELECT stock_id FROM stock_meta").fetchall()}
    except Exception:
        logger.warning("_load_valid_stock_ids query failed, caller will skip filter")
        return None


_VALID_STOCK_IDS: set[str] | None = None


def _is_institutional_complete(conn, date_str: str) -> bool:
    """Return whether both official markets have usable rows for a date.

    Official endpoints return a full-market payload.  A date with only one
    market, all-zero TWSE dealer data, or all-zero TPEx trust data is a partial
    import and must remain eligible for retry.
    """
    row = conn.execute(
        """
        SELECT
            SUM(CASE WHEN m.market = 'TSE' THEN 1 ELSE 0 END),
            SUM(CASE WHEN m.market = 'OTC' THEN 1 ELSE 0 END),
            SUM(CASE WHEN m.market = 'TSE'
                      AND (COALESCE(i.dealer_buy, 0) <> 0 OR COALESCE(i.dealer_sell, 0) <> 0)
                     THEN 1 ELSE 0 END),
            SUM(CASE WHEN m.market = 'OTC'
                      AND (COALESCE(i.trust_buy, 0) <> 0 OR COALESCE(i.trust_sell, 0) <> 0)
                     THEN 1 ELSE 0 END)
        FROM institutional_data i
        JOIN stock_meta m ON m.stock_id = i.stock_id
        WHERE i.date = ?
        """,
        (date_str,),
    ).fetchone()
    if row is None:
        return False
    tse_count, otc_count, tse_dealer_active, otc_trust_active = (int(value or 0) for value in row)
    return tse_count > 0 and otc_count > 0 and tse_dealer_active > 0 and otc_trust_active > 0


def get_recent_official_data_status(days: int = 20, date_int: Optional[int] = None) -> list[dict[str, object]]:
    """Return set-based price and institutional completeness for recent sessions."""
    if days < 1 or days > 800:
        raise ValueError("days 必須介於 1 到 800")

    base_date_int = date_int if date_int is not None else cal.get_last_trading_day()
    base_dt = cal._int_to_date(base_date_int)
    if base_dt is None:
        raise ValueError(f"無效日期格式: {base_date_int}")
    base_date = base_dt.strftime("%Y-%m-%d")

    connection = get_connection(readonly=True)
    try:
        target_rows = connection.execute(
            "SELECT date FROM stock_trading_calendar " "WHERE is_open = 1 AND date <= ? ORDER BY date DESC LIMIT ?",
            (base_date, days),
        ).fetchall()
        target_dates = [str(row[0]) for row in target_rows]
        if not target_dates:
            return []

        placeholders = ",".join("?" for _ in target_dates)
        quote_rows = connection.execute(
            f"""
            SELECT
                h.date,
                SUM(CASE WHEN m.market = 'TSE' THEN 1 ELSE 0 END),
                SUM(CASE WHEN m.market = 'OTC' THEN 1 ELSE 0 END)
            FROM stock_history AS h
            JOIN stock_meta AS m ON m.stock_id = h.stock_id
            WHERE h.date IN ({placeholders})
            GROUP BY h.date
            """,
            target_dates,
        ).fetchall()
        institutional_rows = connection.execute(
            f"""
            SELECT
                i.date,
                SUM(CASE WHEN m.market = 'TSE' THEN 1 ELSE 0 END),
                SUM(CASE WHEN m.market = 'OTC' THEN 1 ELSE 0 END)
            FROM institutional_data AS i
            JOIN stock_meta AS m ON m.stock_id = i.stock_id
            WHERE i.date IN ({placeholders})
            GROUP BY i.date
            """,
            target_dates,
        ).fetchall()
    finally:
        connection.close()

    quote_stats = {str(row[0]): (int(row[1] or 0), int(row[2] or 0)) for row in quote_rows}
    institutional_stats = {str(row[0]): (int(row[1] or 0), int(row[2] or 0)) for row in institutional_rows}

    statuses: list[dict[str, object]] = []
    for date_str in target_dates:
        quote_tse, quote_otc = quote_stats.get(date_str, (0, 0))
        inst_tse, inst_otc = institutional_stats.get(date_str, (0, 0))
        quote_total = quote_tse + quote_otc
        institutional_total = inst_tse + inst_otc
        minimum_institutional_coverage = max(1000, int(quote_total * 0.85))
        statuses.append(
            {
                "date": date_str,
                "date_int": int(date_str.replace("-", "")),
                "quote_tse": quote_tse,
                "quote_otc": quote_otc,
                "institutional_tse": inst_tse,
                "institutional_otc": inst_otc,
                "quotes_complete": quote_tse > 500 and quote_otc > 500,
                "institutional_complete": (
                    inst_tse > 400 and inst_otc > 400 and institutional_total >= minimum_institutional_coverage
                ),
            }
        )
    return statuses


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
    if "date" not in df.columns and "date_int" in df.columns:
        df["date"] = pd.to_datetime(df["date_int"].astype(str), format="%Y%m%d").dt.strftime("%Y-%m-%d")

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
        df["institutional_net"] = df.get("foreign_net", 0) + df.get("trust_net", 0) + df.get("dealer_net", 0)
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
        # TDCC rows are stored in shareholding_unified with source='tdcc'.
        # Do not manufacture zero-valued concentration fields here: a partial
        # payload must preserve existing values rather than look like a valid
        # all-zero TDCC snapshot.
        if "date" not in df.columns:
            logger.warning("shareholding_unified payload has no usable date; skipping write")
            return
        if "source" not in df.columns:
            df["source"] = "tdcc"
        else:
            df["source"] = df["source"].fillna("tdcc").astype(str).str.strip().replace("", "tdcc")

        supported = [
            "stock_id",
            "date",
            "source",
            "total_shares",
            "whale_ratio",
            "retail_ratio",
            "foreign_shares",
            "foreign_ratio",
            "total_people",
            "whale_shares",
            "whale_people",
        ]
        df = df[[col for col in supported if col in df.columns]].copy()
        value_columns = [col for col in supported[3:] if col in df.columns]
        if not value_columns:
            logger.warning("shareholding_unified payload has no shareholding values; skipping write")
            return
        has_value = df[value_columns].notna().any(axis=1)
        if not has_value.all():
            logger.warning("skipping %d empty shareholding rows", int((~has_value).sum()))
            df = df[has_value].copy()
        if df.empty:
            return
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
        # TDCC and foreign-shareholding records intentionally use different
        # write paths.  Sending TDCC through upsert_shareholding() discards
        # TDCC fields and force-labels it as twse_foreign.
        tdcc_rows = df[df["source"] == "tdcc"]
        other_rows = df[df["source"] != "tdcc"]
        if not tdcc_rows.empty:
            proc.upsert_tdcc(tdcc_rows)
        if not other_rows.empty:
            proc.upsert_shareholding_unified(other_rows)


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


def _update_quotes_for_date(date_value: int) -> bool:
    """Fetch and persist both official quote markets for one trading date."""
    import pandas as pd

    print("  → 抓取價量資料...", flush=True)
    twse_df = quotes.fetch_twse_quotes(date_value)
    tpex_df = quotes.fetch_tpex_quotes(date_value)

    if twse_df.empty and tpex_df.empty:
        if sys.stdin.isatty() and sys.stdout.isatty():
            answer = input(f"⚠️ {date_value} 兩市場皆無資料，是否為休市日？" "（預設為否）[y/N]: ").strip().lower()
            if answer == "y":
                date_str = f"{date_value // 10000:04d}-{(date_value // 100) % 100:02d}-" f"{date_value % 100:02d}"
                connection = get_connection()
                try:
                    connection.execute(
                        "INSERT OR REPLACE INTO stock_trading_calendar "
                        "(date, is_open, description) VALUES (?, 0, ?)",
                        (date_str, "使用者標記休市"),
                    )
                    connection.commit()
                finally:
                    connection.close()
                print(f"  ✅ 已將 {date_str} 標記為休市日，日後將跳過抓取。", flush=True)
                return False
        print(
            f"  ⚠️ {date_value} 兩市場皆無資料（可能為休市日或尚無收盤資料），跳過。",
            flush=True,
        )
        return False

    if not twse_df.empty:
        twse_df["market"] = "TSE"
    if not tpex_df.empty:
        tpex_df["market"] = "OTC"

    twse_fetched = len(twse_df)
    tpex_fetched = len(tpex_df)
    print(
        f"      [TWSE] 已抓 {twse_fetched:4d} 檔" f"{'（資料為空）' if twse_fetched == 0 else ''}",
        flush=True,
    )
    print(
        f"      [TPEx] 已抓 {tpex_fetched:4d} 檔" f"{'（資料為空）' if tpex_fetched == 0 else ''}",
        flush=True,
    )

    price_df = pd.concat([twse_df, tpex_df], ignore_index=True)
    price_df = price_df.drop_duplicates(subset=["stock_id", "date"])
    quotes.update_stock_meta_from_df(price_df)
    upsert_dataframe("stock_history", price_df)
    print(f"  ✅ 價量資料: {len(price_df)} 筆", flush=True)
    if twse_fetched == 0 or tpex_fetched == 0:
        print("  ⚠️ 價量資料僅有單一市場，下次完整性檢查將再次重試", flush=True)
    return True


def _update_institutional_for_date(date_value: int) -> bool:
    """Fetch and persist official institutional data for one trading date."""
    print("  → 抓取三大法人資料...", flush=True)
    institutional_df = institutional.fetch_all_institutional(date_value)
    if institutional_df.empty:
        print("  ⚠️ 三大法人資料為空，下次完整性檢查將再次重試", flush=True)
        return False

    upsert_dataframe("institutional_data", institutional_df)
    print(f"  ✅ 三大法人: {len(institutional_df)} 筆", flush=True)
    markets = set(institutional_df.get("market", []))
    if not {"TWSE", "TPEx"}.issubset(markets):
        missing = {"TWSE", "TPEx"} - markets
        print(
            f"  ⚠️ 三大法人資料不完整，缺少 {', '.join(sorted(missing))}；下次更新將重試",
            flush=True,
        )
        return False
    return True


# ---------- 主更新函數 ----------
def update_official_daily(date_int: Optional[int] = None, days: int = 1, force: bool = False, auto_tdcc: bool = True):
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

    if days < 1 or days > 800:
        print("❌ 交易天數必須介於 1 到 800", flush=True)
        return

    # 一次查出最近 N 個交易日的價量與法人完整度，避免逐日開啟 SQLite 連線。
    print(f"🔍 檢查最近 {days} 個交易日的價量與法人完整性...", flush=True)
    try:
        statuses = get_recent_official_data_status(days=days, date_int=base_date_int)
    except Exception as exc:
        logger.exception("recent official data status failed")
        print(f"❌ 無法檢查歷史完整性: {exc}", flush=True)
        return

    if not statuses:
        # Compatibility fallback for a newly created/temporarily unavailable
        # calendar.  The normal path above remains one set-based query.
        current_dt = base_dt
        checked_days = 0
        while len(statuses) < days and checked_days < max(days * 3, 15):
            current_int = cal._date_to_int(current_dt)
            if cal.is_trading_day(current_int):
                quotes_complete = cal.date_exists_in_history(current_int)
                statuses.append(
                    {
                        "date": current_dt.strftime("%Y-%m-%d"),
                        "date_int": current_int,
                        "quotes_complete": quotes_complete,
                        "institutional_complete": quotes_complete,
                    }
                )
            current_dt -= timedelta(days=1)
            checked_days += 1
    if not statuses:
        print("⚠️ 交易日曆沒有可用日期，請先同步交易日曆", flush=True)
        if auto_tdcc:
            _auto_update_tdcc()
        return

    fetch_dates: list[int] = []
    quote_fetch_dates: set[int] = set()
    institutional_fetch_dates: set[int] = set()
    for status in statuses:
        target = int(str(status["date_int"]))
        quotes_complete = bool(status["quotes_complete"])
        institutional_complete = bool(status["institutional_complete"])
        if force or not quotes_complete or not institutional_complete:
            fetch_dates.append(target)
        if force or not quotes_complete:
            quote_fetch_dates.add(target)
        if force or not institutional_complete:
            institutional_fetch_dates.add(target)

    quote_gap_count = len(quote_fetch_dates)
    institutional_gap_count = len(institutional_fetch_dates)
    if quote_gap_count or institutional_gap_count:
        print(
            f"  → 發現價量需更新 {quote_gap_count} 天、法人需更新 {institutional_gap_count} 天",
            flush=True,
        )

    if not fetch_dates:
        print("✅ 沒有缺失的交易日，無需從官方重新抓取", flush=True)
        # [AI MOD] User requested to see TWSE/TPEx stats even if data is already in DB
        try:
            with get_connection() as conn_meta:
                cur = conn_meta.cursor()
                latest_date = cur.execute("SELECT MAX(date) FROM stock_history").fetchone()[0]

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
        except Exception:
            logger.exception("show_stats failed")
        if auto_tdcc:
            _auto_update_tdcc()
        return

    # SQL 回傳由近到遠，更新時改為由遠到近。
    fetch_dates.reverse()
    print(f"🔄 將抓取 {len(fetch_dates)} 個交易日: {fetch_dates[:5]}...", flush=True)

    for idx, d in enumerate(fetch_dates, 1):
        print(f"\n--- [{idx}/{len(fetch_dates)}] 處理日期 {d} ---", flush=True)
        try:
            quote_ok = True
            if d in quote_fetch_dates:
                quote_ok = _update_quotes_for_date(d)
            else:
                print("  ↪ 價量資料完整，略過重新下載", flush=True)

            if d in institutional_fetch_dates:
                if quote_ok or d not in quote_fetch_dates:
                    _update_institutional_for_date(d)
            else:
                print("  ↪ 三大法人資料完整，略過重新下載", flush=True)

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
    """讀取一次官方最新快照，由 payload 日期執行冪等 UPSERT。"""
    try:
        print("\n📊 檢查 TDCC 官方最新快照...", flush=True)
        update_tdcc_weekly()
    except Exception as e:
        print(f"⚠️ 自動檢查 TDCC 失敗: {e}", flush=True)


def update_tdcc_weekly():
    """抓取最新一期 TDCC 資料（單週）"""
    update_tdcc_historical(weeks=1)


def update_tdcc_historical(weeks: int = 1):
    """Compatibility entry point that updates the latest TDCC snapshot only."""
    if weeks != 1:
        print(
            "⚠️ TDCC OpenAPI 不提供全市場歷史週資料；本次只更新最新一期，" "不會宣稱已補齊歷史週。",
            flush=True,
        )
    print("🔄 抓取最新一期 TDCC 集保資料...", flush=True)
    tdcc_df = tdcc.fetch_tdcc_historical(weeks=1)
    if not tdcc_df.empty:
        official_dates = sorted(str(value) for value in tdcc_df["date"].dropna().unique())
        if len(official_dates) != 1:
            print("⚠️ TDCC payload 期別不唯一，拒絕寫入", flush=True)
            return
        upsert_dataframe("shareholding_unified", tdcc_df)
        print(
            f"  ✅ TDCC 官方快照 {official_dates[0]}: {len(tdcc_df)} 筆" "（重複執行會更新同一期，不會製造新日期）",
            flush=True,
        )
    else:
        print("  ⚠️ TDCC 資料為空", flush=True)
