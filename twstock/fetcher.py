#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetcher.py — Trinity 資料萃取層
提供 DataFetcher 類別，從 FinMind / TDCC / Supabase 取得台股資料。

單位說明：
  - volume: 股（原始值，不轉換，顯示層才轉張）
  - amount: 元（原始值，不轉換）
  - foreign_buy/sell/trust_buy/sell: 股（原始值，不轉換）
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from datetime import datetime

import pandas as pd
import requests

from twstock.api_config import get_finmind_token
from twstock.utils import safe_float as _safe_float

logger = logging.getLogger(__name__)

# ============================================================================
# 常數與預設值
# ============================================================================

FINMIND_BASE_URL = "https://api.finmindtrade.com/api/v4/data"


class _RateLimiter:
    """Thread-safe 滑動視窗速率限制器"""

    def __init__(self, max_calls=600, window=3600):
        self._max = max_calls
        self._window = window
        self._q = deque()
        self._lock = threading.Lock()

    def acquire(self):
        """滑動視窗速率控制，確保每小時不超過 max_calls 次"""
        with self._lock:
            now = time.time()
            # 移除超過 window 秒的舊記錄
            while self._q and self._q[0] < now - self._window:
                self._q.popleft()
            # 如果已達上限，計算需要等待的時間
            if len(self._q) >= self._max:
                sleep_time = self._q[0] + self._window - now + 0.1
                if sleep_time > 0:
                    time.sleep(sleep_time)
                # 睡醒後再次清理
                now = time.time()
                while self._q and self._q[0] < now - self._window:
                    self._q.popleft()
            # 記錄本次呼叫時間
            self._q.append(now)


class FinMindClient:
    """封裝 FinMind API 的 HTTP 客戶端"""

    def __init__(self, token):
        self.token = token
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "User-Agent": "Trinity-Fetcher/1.0",
            }
        )

    def get(self, dataset, data_id="", start="", end="", retries=3):
        """呼叫 FinMind API，回傳 pd.DataFrame"""
        params = {
            "dataset": dataset,
            "data_id": data_id,
            "start_date": start,
            "end_date": end,
            "token": self.token,
        }
        for attempt in range(retries):
            try:
                _rate_limiter.acquire()
                r = self._session.get(FINMIND_BASE_URL, params=params, timeout=30)
                r.raise_for_status()
                resp = r.json()
                if resp.get("msg") == "success" and "data" in resp:
                    df = pd.DataFrame(resp["data"])
                    return df
                else:
                    logging.warning(f"FinMind API return non-success: {resp.get('msg')}")
                    return pd.DataFrame()
            except Exception as e:
                logging.warning(f"FinMind get attempt {attempt+1}/{retries} failed: {e}")
                if attempt < retries - 1:
                    time.sleep(1)
        return pd.DataFrame()


_rate_limiter = _RateLimiter()
_client = None
_client_lock = threading.Lock()


def _get_client(token=None):
    """Lazy singleton，避免 import 時強制要求 token"""
    global _client
    if token is None:
        if _client is None:
            with _client_lock:
                if _client is None:
                    token = get_finmind_token()
                    _client = FinMindClient(token)
        return _client
    return FinMindClient(str(token))


# ============================================================================
# DataFetcher 主類別
# ============================================================================


class DataFetcher:
    """台股資料抓取器，封裝所有資料源呼叫"""

    def __init__(self, token=None):
        self._token = token
        self._client = None

    def _get_client(self):
        if self._client is None:
            self._client = _get_client(self._token)
        return self._client

    def fetch_history_price(self, stock_id, start_date="", end_date=""):
        """抓取歷史價格，回傳欄位: stock_id, date, open, high, low, close, volume(張), amount(千萬元)"""
        client = self._get_client()
        df = client.get("TaiwanStockPrice", stock_id, start_date, end_date)
        if df.empty:
            return df

        # 欄位映射
        col_map = {
            "stock_id": "stock_id",
            "date": "date",
            "open": "open",
            "high": "high",
            "low": "low",
            "close": "close",
            "Trading_Volume": "volume",
            "Trading_money": "amount",
        }
        existing_cols = {k: v for k, v in col_map.items() if k in df.columns}
        df = df.rename(columns=existing_cols)
        required = ["stock_id", "date", "open", "high", "low", "close", "volume", "amount"]
        for c in required:
            if c not in df.columns:
                df[c] = 0

        df = df[required].copy()
        # 存原始值（股/元），顯示層才轉換
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0).astype(int)
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)
        df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
        return df

    def fetch_institutional(self, stock_id, start_date="", end_date=""):
        """抓取三大法人買賣超，回傳欄位: stock_id, date, foreign_buy, foreign_sell, trust_buy, trust_sell, dealer_buy=0, dealer_sell=0"""
        client = self._get_client()
        df = client.get("TaiwanStockInstitutionalInvestorsBuySell", stock_id, start_date, end_date)
        if df.empty:
            return df

        col_map = {
            "stock_id": "stock_id",
            "date": "date",
            "Foreign_Investor_Buy": "foreign_buy",
            "Foreign_Investor_Sell": "foreign_sell",
            "Investment_Trust_Buy": "trust_buy",
            "Investment_Trust_Sell": "trust_sell",
        }
        existing_cols = {k: v for k, v in col_map.items() if k in df.columns}
        df = df.rename(columns=existing_cols)
        required = ["stock_id", "date", "foreign_buy", "foreign_sell", "trust_buy", "trust_sell"]
        for c in required:
            if c not in df.columns:
                df[c] = 0

        df = df[required].copy()
        for col in ["foreign_buy", "foreign_sell", "trust_buy", "trust_sell"]:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
        df["dealer_buy"] = 0
        df["dealer_sell"] = 0
        df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
        return df

    def fetch_shareholding(self, stock_id, start_date="", end_date=""):
        """抓取外資持股，回傳欄位: stock_id, date, foreign_shares, foreign_ratio"""
        client = self._get_client()
        df = client.get("TaiwanStockShareholding", stock_id, start_date, end_date)
        if df.empty:
            return df

        col_map = {
            "stock_id": "stock_id",
            "date": "date",
            "Foreign_Remaining_Shares": "foreign_shares",
            "Foreign_Shareholding_Ratio": "foreign_ratio",
        }
        existing_cols = {k: v for k, v in col_map.items() if k in df.columns}
        df = df.rename(columns=existing_cols)
        required = ["stock_id", "date", "foreign_shares", "foreign_ratio"]
        for c in required:
            if c not in df.columns:
                df[c] = 0

        df = df[required].copy()
        df["foreign_shares"] = (
            pd.to_numeric(df["foreign_shares"], errors="coerce").fillna(0).astype(int)
        )
        df["foreign_ratio"] = pd.to_numeric(df["foreign_ratio"], errors="coerce").fillna(0.0)
        df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
        return df

    def fetch_stock_meta(self):
        """抓取全部股票基本資料，回傳欄位: stock_id, stock_name, industry_category, market, type"""
        client = self._get_client()
        df = client.get("TaiwanStockInfo")
        if df.empty:
            return df

        col_map = {
            "stock_id": "stock_id",
            "stock_name": "stock_name",
            "industry_category": "industry_category",
            "market": "market",
            "type": "type",
        }
        existing_cols = {k: v for k, v in col_map.items() if k in df.columns}
        df = df.rename(columns=existing_cols)
        required = ["stock_id", "stock_name", "industry_category", "market", "type"]
        for c in required:
            if c not in df.columns:
                df[c] = ""
        return df[required].copy()

    def fetch_intraday_snapshot(self, stock_id):
        """抓取個股即時報價，回傳 dict: {o, h, l, z, v}，v 單位為張"""
        url = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp"
        params = {
            "ex_ch": f"tse_{stock_id}.tw",
            "json": 1,
            "delay": 0,
        }
        try:
            r = requests.get(url, params=params, timeout=10)
            r.raise_for_status()
            data = r.json()
            if data.get("msgArray") and len(data["msgArray"]) > 0:
                item = data["msgArray"][0]

                def _local_safe_float(val):
                    if val in ("-", "", None):
                        return None
                    return _safe_float(val, default=None)

                return {
                    "o": _local_safe_float(item.get("o")),
                    "h": _local_safe_float(item.get("h")),
                    "l": _local_safe_float(item.get("l")),
                    "z": _local_safe_float(item.get("z")),
                    "v": _local_safe_float(item.get("v")),  # 單位：張
                }
            return {}
        except (requests.exceptions.RequestException, ValueError):
            return {}


# DoD module-level functions
def fetch_stock_price(stock_id, start_date="", end_date=""):
    """Module-level convenience function — DoD requirement."""
    return DataFetcher().fetch_history_price(stock_id, start_date, end_date)


def fetch_institutional(stock_id, start_date="", end_date=""):
    """Module-level convenience function — DoD requirement."""
    return DataFetcher().fetch_institutional(stock_id, start_date, end_date)


def fetch_shareholding(stock_id, start_date="", end_date=""):
    """Module-level convenience function — DoD requirement."""
    return DataFetcher().fetch_shareholding(stock_id, start_date, end_date)


def fetch_stock_info():
    """Module-level convenience function — DoD requirement."""
    return DataFetcher().fetch_stock_meta()


# ============================================================================
# FinMindFetcher — Issue 001 v3.0 (raw units, no adj_close)
# ============================================================================


class FinMindFetcher:
    """FinMind 日線資料抓取器，直接存原始值（股/元），不做單位轉換"""

    def __init__(self, api_token, db):
        self.api_token = api_token
        self.db = db

    def fetch_daily(self, stock_id, start_date, end_date):
        """
        呼叫 FinMind TaiwanStockPrice API。
        回傳 dict: {"msg": "success", "status": 200, "data": [...]}
        """
        url = "https://api.finmindtrade.com/api/v4/data"
        params = {
            "dataset": "TaiwanStockPrice",
            "data_id": stock_id,
            "start_date": start_date,
            "end_date": end_date,
            "token": self.api_token,
        }
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        resp = r.json()
        if resp.get("status") != 200:
            raise Exception(f"FinMind API error: {resp.get('msg')}")
        return resp

    def _transform(self, raw):
        """
        將 FinMind API 回應轉換為 stock_history 的 list of dict。
        不做單位轉換（Trading_Volume 直接存為 volume，Trading_money 直接存為 amount）。
        """
        if not raw.get("data"):
            raise Exception("Cannot transform empty data list")

        required_fields = [
            "max",
            "min",
            "open",
            "close",
            "Trading_Volume",
            "Trading_money",
            "Trading_turnover",
            "spread",
        ]
        rows = []
        for row in raw["data"]:
            for field in required_fields:
                if field not in row:
                    raise Exception(f"Missing required field: {field}")

            rows.append(
                {
                    "stock_id": row["stock_id"],
                    "date": row["date"],
                    "open": row["open"],
                    "high": row["max"],
                    "low": row["min"],
                    "close": row["close"],
                    "volume": row["Trading_Volume"],
                    "amount": row["Trading_money"],
                    "trade_count": row["Trading_turnover"],
                    "spread": row["spread"],
                    "source": "finmind",
                }
            )
        return rows

    def save(self, rows):
        """INSERT OR REPLACE 寫入 stock_history，回傳寫入列數"""
        sql = """
        INSERT OR REPLACE INTO stock_history
            (stock_id, date, open, high, low, close, volume, amount,
             trade_count, spread, source)
        VALUES
            (:stock_id, :date, :open, :high, :low, :close, :volume, :amount,
             :trade_count, :spread, :source)
        """
        self.db.executemany(sql, rows)
        self.db.commit()
        return len(rows)

    def fetch_and_save(self, stock_id, start_date, end_date):
        """串接 fetch_daily → _transform → save，回傳寫入列數"""
        raw = self.fetch_daily(stock_id, start_date, end_date)
        rows = self._transform(raw)
        count = self.save(rows)
        return count


# ============================================================================
# TWSEFetcher — Issue 002 (ROC dates, comma removal, skip suspended)
# ============================================================================


class TWSEFetcher:
    """TWSE 官方日線資料抓取器，以月為單位"""

    BASE_URL = "https://www.twse.com.tw/exchangeReport/STOCK_DAY"

    def __init__(self, db):
        self.db = db

    def fetch_monthly(self, stock_id, year, month):
        """
        呼叫 TWSE STOCK_DAY API，回傳 response.json()。
        date 參數: YYYYMMDD（當月第一天）
        """
        date_str = f"{year}{month:02d}01"
        params = {
            "response": "json",
            "date": date_str,
            "stockNo": stock_id,
        }
        r = requests.get(self.BASE_URL, params=params, timeout=30)
        r.raise_for_status()
        resp = r.json()
        if resp.get("stat") != "OK":
            raise Exception(f"TWSE API error: stat={resp.get('stat')}")
        return resp

    def _roc_to_ce(self, roc_date_str):
        """
        'YYY/MM/DD' → 'YYYY-MM-DD'
        例：'113/01/02' → '2024-01-02'（113 + 1911 = 2024）
        """
        parts = roc_date_str.split("/")
        if len(parts) != 3:
            raise Exception(f"Invalid ROC date format: {roc_date_str}")
        roc_year, month, day = parts
        ce_year = int(roc_year) + 1911
        return f"{ce_year}-{month}-{day}"

    def _transform(self, raw, stock_id):
        """
        raw: fetch_monthly 回傳的 dict
        stock_id: 股票代號（API 不含此欄，需手動填入）
        """
        if raw.get("stat") != "OK":
            raise Exception(f"TWSE API error: stat={raw.get('stat')}")

        data = raw.get("data", [])
        if not data:
            raise Exception("Cannot transform empty TWSE data")

        # fields: ["日期","成交股數","成交金額","開盤價","最高價","最低價","收盤價","漲跌價差","成交筆數"]
        # index:    0       1         2         3       4       5       6       7         8
        rows = []
        for row in data:
            close_val = row[6]
            if close_val == "--":
                continue  # 停牌行跳過

            def parse_num(s, is_int=True):
                cleaned = s.replace(",", "")
                return int(cleaned) if is_int else float(cleaned)

            rows.append(
                {
                    "stock_id": stock_id,
                    "date": self._roc_to_ce(row[0]),
                    "open": parse_num(row[3], False),
                    "high": parse_num(row[4], False),
                    "low": parse_num(row[5], False),
                    "close": parse_num(row[6], False),
                    "volume": parse_num(row[1], True),
                    # TWSE API 回傳 volume(股) / amount(元)，DB_SCHEMA 規定相同單位，直接存
                    "amount": parse_num(row[2], True),
                    "trade_count": parse_num(row[8], True),
                    "spread": parse_num(row[7], False),
                    "source": "official",
                }
            )
        return rows

    def save(self, rows):
        """INSERT OR REPLACE 寫入 stock_history"""
        sql = """
        INSERT OR REPLACE INTO stock_history
            (stock_id, date, open, high, low, close, volume, amount,
             trade_count, spread, source)
        VALUES
            (:stock_id, :date, :open, :high, :low, :close, :volume, :amount,
             :trade_count, :spread, :source)
        """
        self.db.executemany(sql, rows)
        self.db.commit()
        return len(rows)

    def fetch_and_save(self, stock_id, start_date, end_date):
        """
        按月迭代，對每個月呼叫 fetch_monthly → _transform → save。
        start_date, end_date: 'YYYY-MM-DD' 格式。
        """

        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")

        total = 0
        current = start.replace(day=1)
        while current <= end:
            try:
                raw = self.fetch_monthly(stock_id, current.year, current.month)
                rows = self._transform(raw, stock_id)
                total += self.save(rows)
            except Exception:
                pass  # 該月沒資料或其他錯誤，跳過
            # 下個月
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1)
            else:
                current = current.replace(month=current.month + 1)
        return total


# ============================================================================
# InstitutionalFetcher — Issue 003 (pivot, dealer sum)
# ============================================================================


class InstitutionalFetcher:
    """三大法人買賣超資料抓取器，pivot 成一日一筆"""

    def __init__(self, api_token, db):
        self.api_token = api_token
        self.db = db

    def fetch_daily(self, stock_id, start_date, end_date):
        """
        呼叫 FinMind TaiwanStockInstitutionalInvestors API。
        """
        url = "https://api.finmindtrade.com/api/v4/data"
        params = {
            "dataset": "TaiwanStockInstitutionalInvestors",
            "data_id": stock_id,
            "start_date": start_date,
            "end_date": end_date,
            "token": self.api_token,
        }
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        resp = r.json()
        if resp.get("status") != 200:
            raise Exception(f"FinMind API error: {resp.get('msg')}")
        return resp

    def _transform(self, raw):
        """
        將多筆（每法人一筆）pivot 成一筆（一日一筆）。
        """
        if not raw.get("data"):
            raise Exception("Cannot transform empty data")

        data = raw["data"]
        # 檢查每筆都有 name 欄位
        for row in data:
            if "name" not in row:
                raise Exception("Missing required field: name")

        # 按日期分組
        from collections import defaultdict

        by_date = defaultdict(list)
        for row in data:
            by_date[row["date"]].append(row)

        rows = []
        for date, entries in sorted(by_date.items()):
            stock_id = entries[0]["stock_id"]
            result = {
                "stock_id": stock_id,
                "date": date,
                "foreign_buy": 0,
                "foreign_sell": 0,
                "foreign_net": 0,
                "trust_buy": 0,
                "trust_sell": 0,
                "trust_net": 0,
                "dealer_buy": 0,
                "dealer_sell": 0,
                "dealer_net": 0,
                "source": "finmind",
            }
            for e in entries:
                name = e["name"]
                buy = e.get("buy", 0)
                sell = e.get("sell", 0)
                net = e.get("net", 0)
                # 優先判斷外資（因為「外資及陸資(不含外資自營商)」同時含「自營商」）
                if "外資" in name:
                    result["foreign_buy"] = buy
                    result["foreign_sell"] = sell
                    result["foreign_net"] = net
                elif name == "投信":
                    result["trust_buy"] = buy
                    result["trust_sell"] = sell
                    result["trust_net"] = net
                elif "自營商" in name:
                    result["dealer_buy"] += buy
                    result["dealer_sell"] += sell
                    result["dealer_net"] += net

            result["institutional_net"] = (
                result["foreign_net"] + result["trust_net"] + result["dealer_net"]
            )
            rows.append(result)
        return rows

    def save(self, rows):
        """INSERT OR REPLACE 寫入 institutional_data"""
        sql = """
        INSERT OR REPLACE INTO institutional_data
            (stock_id, date, foreign_buy, foreign_sell, foreign_net,
             trust_buy, trust_sell, trust_net,
             dealer_buy, dealer_sell, dealer_net,
             institutional_net, source)
        VALUES
            (:stock_id, :date, :foreign_buy, :foreign_sell, :foreign_net,
             :trust_buy, :trust_sell, :trust_net,
             :dealer_buy, :dealer_sell, :dealer_net,
             :institutional_net, :source)
        """
        self.db.executemany(sql, rows)
        self.db.commit()
        return len(rows)

    def fetch_and_save(self, stock_id, start_date, end_date):
        """fetch_daily → _transform → save，回傳列數"""
        raw = self.fetch_daily(stock_id, start_date, end_date)
        rows = self._transform(raw)
        count = self.save(rows)
        return count


# ============================================================================
# TDCCFetcher — Issue 004 (weekly, whale/retail ratio)
# ============================================================================


class TDCCFetcher:
    """集保持股資料抓取器，計算大股東/散戶比例"""

    BASE_URL = "https://smart.tdcc.com.tw/opendata/getOD.ashx?id=1-5"

    def __init__(self, db):
        self.db = db

    def fetch_by_date(self, date_str):
        """
        呼叫 TDCC API，回傳 list of dict。
        date_str: 'YYYY-MM-DD' 格式，API 可能回傳多週資料。
        """
        params = {"id": "1-5"}
        r = requests.get(self.BASE_URL, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        # 過濾指定日期
        return [row for row in data if row.get("date_roc") == self._ce_to_roc(date_str)]

    def _ce_to_roc(self, date_str):
        """'2024-01-05' → '1130105'（ROC YYYYMMDD）"""
        year, month, day = date_str.split("-")
        roc_year = int(year) - 1911
        return f"{roc_year}{month}{day}"

    def _parse_roc_date(self, roc_str):
        """'YYYMMDD' → 'YYYY-MM-DD'（ROC+1911）"""
        roc_year = int(roc_str[:3])
        month = roc_str[3:5]
        day = roc_str[5:7]
        ce_year = roc_year + 1911
        return f"{ce_year}-{month}-{day}"

    def _transform(self, raw_rows):
        """
        raw_rows: list of dict（含 date_roc, stock_id, bracket, people, shares）
        以 (stock_id, date_roc) 分組，計算各欄。
        """
        from collections import defaultdict

        by_key = defaultdict(list)
        for row in raw_rows:
            key = (row["stock_id"], row["date_roc"])
            by_key[key].append(row)

        rows = []
        for (stock_id, date_roc), entries in sorted(by_key.items()):
            date = self._parse_roc_date(date_roc)

            total_shares = 0
            total_people = 0
            whale_shares = 0
            whale_people = 0
            retail_shares = 0

            for e in entries:
                bracket = e["bracket"]
                shares = e["shares"]
                people = e["people"]

                if bracket == "合計":
                    total_shares = shares
                    total_people = people
                elif bracket == "400001以上":
                    whale_shares = shares
                    whale_people = people
                elif bracket in ("1~999", "1000~5000", "5001~10000"):
                    retail_shares += shares

            whale_ratio = (whale_shares / total_shares * 100) if total_shares > 0 else 0.0
            retail_ratio = (retail_shares / total_shares * 100) if total_shares > 0 else 0.0

            rows.append(
                {
                    "stock_id": stock_id,
                    "date": date,
                    "source": "tdcc",
                    "total_shares": total_shares,
                    "total_people": total_people,
                    "whale_shares": whale_shares,
                    "whale_people": whale_people,
                    "whale_ratio": whale_ratio,
                    "retail_ratio": retail_ratio,
                    "foreign_shares": None,
                    "foreign_ratio": None,
                }
            )
        return rows

    def save(self, rows):
        """INSERT OR REPLACE 寫入 shareholding_unified（不是 VIEW）"""
        sql = """
        INSERT OR REPLACE INTO shareholding_unified
            (stock_id, date, source, total_shares, whale_ratio, retail_ratio,
             foreign_shares, foreign_ratio, total_people, whale_shares, whale_people)
        VALUES
            (:stock_id, :date, :source, :total_shares, :whale_ratio, :retail_ratio,
             :foreign_shares, :foreign_ratio, :total_people, :whale_shares, :whale_people)
        """
        self.db.executemany(sql, rows)
        self.db.commit()
        return len(rows)

    def fetch_and_save(self, date_str):
        """fetch_by_date → _transform → save，回傳列數"""
        raw = self.fetch_by_date(date_str)
        rows = self._transform(raw)
        count = self.save(rows)
        return count


# ============================================================================
# DividendFetcher — Issue 005 (FinMind TaiwanStockDividend)
# ============================================================================


class DividendFetcher:
    """除權息事件抓取器"""

    def __init__(self, api_token, db):
        self.api_token = api_token
        self.db = db

    def fetch_dividend(self, stock_id, start_date, end_date):
        """
        呼叫 FinMind TaiwanStockDividend API。
        """
        url = "https://api.finmindtrade.com/api/v4/data"
        params = {
            "dataset": "TaiwanStockDividend",
            "data_id": stock_id,
            "start_date": start_date,
            "end_date": end_date,
            "token": self.api_token,
        }
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        resp = r.json()
        if resp.get("status") != 200:
            raise Exception(f"FinMind API error: {resp.get('msg')}")
        return resp

    def _transform(self, raw):
        """
        如果 raw["data"] 為空 → 拋 Exception("Cannot transform empty data")
        欄位映射：
          - date → date
          - stock_id → stock_id
          - beforeDividend → before_price
          - afterDividend → after_price
          - reference → reference_price
          - CashDividend → cash_dividend
          - StockDividend → stock_dividend
          - source = 'finmind'
        """
        if not raw.get("data"):
            raise Exception("Cannot transform empty data")

        rows = []
        for row in raw["data"]:
            rows.append(
                {
                    "stock_id": row["stock_id"],
                    "date": row["date"],
                    "before_price": float(row.get("beforeDividend", 0)),
                    "after_price": float(row.get("afterDividend", 0)),
                    "reference_price": float(row.get("reference", 0)),
                    "cash_dividend": float(row.get("CashDividend", 0)),
                    "stock_dividend": float(row.get("StockDividend", 0)),
                    "source": "finmind",
                }
            )
        return rows

    def save(self, rows):
        """INSERT OR REPLACE 寫入 dividend_events"""
        sql = """
        INSERT OR REPLACE INTO dividend_events
            (stock_id, date, before_price, after_price, reference_price,
             cash_dividend, stock_dividend, source)
        VALUES
            (:stock_id, :date, :before_price, :after_price, :reference_price,
             :cash_dividend, :stock_dividend, :source)
        """
        self.db.executemany(sql, rows)
        self.db.commit()
        return len(rows)

    def fetch_and_save(self, stock_id, start_date, end_date):
        """fetch_dividend → _transform → save，回傳列數"""
        raw = self.fetch_dividend(stock_id, start_date, end_date)
        rows = self._transform(raw)
        count = self.save(rows)
        return count


# ============================================================================
# PERFetcher — Issue 006 (TWSE BWIBBU, monthly)
# ============================================================================


class PERFetcher:
    """本益比資料抓取器，以月為單位"""

    BASE_URL = "https://www.twse.com.tw/exchangeReport/BWIBBU"

    def __init__(self, db):
        self.db = db

    def fetch_monthly(self, stock_id, year, month):
        """
        呼叫 TWSE BWIBBU API。
        參數: response=json, date=YYYYMMDD（當月第一天）, stockNo=股票代號
        """
        date_str = f"{year}{month:02d}01"
        params = {
            "response": "json",
            "date": date_str,
            "stockNo": stock_id,
        }
        r = requests.get(self.BASE_URL, params=params, timeout=30)
        r.raise_for_status()
        resp = r.json()
        if resp.get("stat") != "OK":
            raise Exception(f"TWSE API error: stat={resp.get('stat')}")
        return resp

    def _transform(self, raw, stock_id):
        """
        如果 raw['stat'] != 'OK' → 拋 Exception
        如果 raw['data'] 為空 → 拋 Exception("Cannot transform empty data")
        fields: ["日期","殖利率(%)","股利年度","本益比","股價淨值比","財報年/季"]
        索引: 0=日期, 1=殖利率, 3=本益比, 4=股價淨值比
        ROC 日期轉 CE（年份 + 1911）
        per 和 pe_ratio 都寫 float(本益比)
        pbr 和 pb_ratio 都寫 float(股價淨值比)
        source = 'official'
        """
        if raw.get("stat") != "OK":
            raise Exception(f"TWSE API error: stat={raw.get('stat')}")

        data = raw.get("data", [])
        if not data:
            raise Exception("Cannot transform empty data")

        rows = []
        for row in data:
            # ROC 日期 "113/01/02" → CE "2024-01-02"
            roc_date = row[0]
            parts = roc_date.split("/")
            ce_year = int(parts[0]) + 1911
            date = f"{ce_year}-{parts[1]}-{parts[2]}"

            per_val = float(row[3])
            pbr_val = float(row[4])

            rows.append(
                {
                    "stock_id": stock_id,
                    "date": date,
                    "dividend_yield": float(row[1]),
                    "per": per_val,
                    "pe_ratio": per_val,
                    "pbr": pbr_val,
                    "pb_ratio": pbr_val,
                    "source": "official",
                }
            )
        return rows

    def save(self, rows):
        """INSERT OR REPLACE 寫入 per_data"""
        sql = """
        INSERT OR REPLACE INTO per_data
            (stock_id, date, per, pbr, pe_ratio, pb_ratio, dividend_yield, source)
        VALUES
            (:stock_id, :date, :per, :pbr, :pe_ratio, :pb_ratio, :dividend_yield, :source)
        """
        self.db.executemany(sql, rows)
        self.db.commit()
        return len(rows)

    def fetch_and_save(self, stock_id, start_date, end_date):
        """
        按月迭代，對每個月呼叫 fetch_monthly → _transform → save。
        start_date, end_date: 'YYYY-MM-DD' 格式。
        """

        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")

        total = 0
        current = start.replace(day=1)
        while current <= end:
            try:
                raw = self.fetch_monthly(stock_id, current.year, current.month)
                rows = self._transform(raw, stock_id)
                total += self.save(rows)
            except Exception:
                pass  # 該月沒資料或其他錯誤，跳過
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1)
            else:
                current = current.replace(month=current.month + 1)
        return total
