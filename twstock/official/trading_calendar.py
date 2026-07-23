#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
official/trading_calendar.py - 交易日曆管理 (避免與標準庫 calendar 衝突)
"""

import sqlite3

# [AI MOD] Import unified database path from db.py
from datetime import datetime, timedelta
from typing import Optional

from twstock.db import DB_PATH
from twstock.retry import retry_get
from twstock.utils import get_ssl_verify


def _date_to_int(dt: datetime) -> int:
    return int(dt.strftime("%Y%m%d"))


def _int_to_date(date_int: int) -> Optional[datetime]:
    try:
        s = str(date_int)
        if len(s) != 8:
            raise ValueError(f"Invalid date length: {s}")
        return datetime.strptime(s, "%Y%m%d")
    except (ValueError, TypeError):
        return None


def init_trading_calendar():
    try:
        print("📅 正在從 TWSE 官方同步交易日曆...", flush=True)
        url = "https://openapi.twse.com.tw/v1/holidaySchedule/holidaySchedule"

        resp = retry_get(url, timeout=15, retries=3, backoff=1.0, verify=get_ssl_verify())
        if resp is None:
            print("⚠️ 無法取得官方休市日曆 (retry failed)", flush=True)
            return
        data = resp.json()

        holidays = {}
        for row in data:
            date_str = str(row.get("Date", ""))
            if len(date_str) == 7 and date_str.isdigit():
                year = int(date_str[:3]) + 1911
                month = int(date_str[3:5])
                day = int(date_str[5:7])
                try:
                    dt_str = datetime(year, month, day).strftime("%Y-%m-%d")
                    holidays[dt_str] = row.get("Description", "")
                except ValueError:
                    pass

        if not holidays:
            print("⚠️ 官方日曆資料為空", flush=True)
            return

        min_year = min(int(d[:4]) for d in holidays.keys())
        max_year = max(int(d[:4]) for d in holidays.keys())

        start_date = datetime(min_year, 1, 1)
        end_date = datetime(max_year, 12, 31)

        # [AI MOD] 撈出使用者手動標記的休市日 (description 含「使用者標記」)，
        # 官方同步時保留其值，不遭覆蓋。資料表尚未建立時忽略。
        user_marked: dict[str, tuple[int, str]] = {}
        try:
            _conn = sqlite3.connect(DB_PATH)
            for _row in _conn.execute(
                "SELECT date, is_open, description FROM stock_trading_calendar "
                "WHERE description LIKE '%使用者標記%'"
            ):
                user_marked[_row[0]] = (_row[1], _row[2])
            _conn.close()
        except Exception:
            pass

        calendar_data = []
        curr = start_date
        while curr <= end_date:
            d_str = curr.strftime("%Y-%m-%d")
            if d_str in user_marked:
                # 保留使用者手動標記 (is_open + description 原值)，官方同步不覆蓋
                is_open, desc = user_marked[d_str]
                calendar_data.append((d_str, is_open, desc))
                curr += timedelta(days=1)
                continue
            # 週末休市 (5=週六, 6=週日)，或位於官方休市名單中 [AI MOD]
            is_open = 0 if (curr.weekday() >= 5 or d_str in holidays) else 1
            desc = holidays.get(d_str, "") if is_open == 0 else ""
            calendar_data.append((d_str, is_open, desc))
            curr += timedelta(days=1)

        conn = sqlite3.connect(DB_PATH)
        # 使用 REPLACE 來覆寫本年度日曆，保留歷史其他年度
        conn.executemany(
            "INSERT OR REPLACE INTO stock_trading_calendar (date, is_open, description) VALUES (?, ?, ?)",
            calendar_data,
        )
        conn.commit()
        conn.close()
        print(
            f"✅ 官方交易日曆已同步，更新區間: {min_year} ~ {max_year} (共 {len(calendar_data)} 天)",
            flush=True,
        )
    except Exception as e:
        print(f"❌ 交易日曆初始化失敗: {e}", flush=True)


def is_trading_day(date_int: int) -> bool:
    dt = _int_to_date(date_int)
    if dt is None:
        return False
    date_str = dt.strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT is_open FROM stock_trading_calendar WHERE date = ?", (date_str,))
    row = cur.fetchone()
    conn.close()
    return row is not None and row[0] == 1


def get_last_trading_day() -> int:
    today = datetime.now()
    # [AI MOD] TWSE daily closing data is published around 14:00-14:30.
    # Before 14:30, the latest available complete data is from the previous day.
    if today.hour * 60 + today.minute < 14 * 60 + 30:
        today -= timedelta(days=1)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM stock_trading_calendar")
    if cur.fetchone()[0] == 0:
        conn.close()
        init_trading_calendar()
    else:
        conn.close()

    dt = today
    for _ in range(10):
        date_int = _date_to_int(dt)
        if is_trading_day(date_int):
            return date_int
        dt -= timedelta(days=1)
    return _date_to_int(today)


def get_nth_trading_day_back(n: int) -> datetime:  # [AI MOD] 取得過去第 N 個交易日的日期
    """從最近交易日往前數 N 個交易日，回傳該日期。
    n=0 表示最近交易日，n=1 表示再前一個交易日，以此類推。
    """
    if n <= 0:
        result = _int_to_date(get_last_trading_day())
        assert result is not None  # get_last_trading_day 保證回傳合法 8 碼交易日
        return result
    dt = _int_to_date(get_last_trading_day())
    assert dt is not None  # 同上,合法交易日保證可解析
    count = 0
    while count < n:
        dt -= timedelta(days=1)
        if is_trading_day(_date_to_int(dt)):
            count += 1
    return dt


def date_exists_in_history(date_int: int) -> bool:
    dt = _int_to_date(date_int)
    if dt is None:
        return False
    date_str = dt.strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # [AI MOD] 確保該日期的資料「夠完整」(上市與上櫃皆需大於 500 檔)。
    # 精確計算兩市場的數量，避免單一市場歷史資料過多造成總數誤判。
    cur.execute(
        """
        SELECT
            SUM(CASE WHEN m.market = 'TSE' THEN 1 ELSE 0 END),
            SUM(CASE WHEN m.market = 'OTC' THEN 1 ELSE 0 END)
        FROM stock_history h
        JOIN stock_meta m ON h.stock_id = m.stock_id
        WHERE h.date = ?
    """,
        (date_str,),
    )
    row = cur.fetchone()
    conn.close()

    tse_count = row[0] or 0
    otc_count = row[1] or 0
    return tse_count > 500 and otc_count > 500
