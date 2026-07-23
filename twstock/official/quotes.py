import logging

import pandas as pd

from twstock.retry import retry_get
from twstock.utils import get_ssl_verify

from .utils import safe_float, safe_int, _get_session


SESSION = _get_session()


def _get_valid_ohlc_rows(df: pd.DataFrame, market: str) -> pd.DataFrame:
    """移除無成交占位列與不可能的 OHLC，避免寫成有效日 K。"""
    if df.empty:
        return df
    valid = (
        (df["open"] > 0)
        & (df["high"] > 0)
        & (df["low"] > 0)
        & (df["close"] > 0)
        & (df["high"] >= df["open"])
        & (df["high"] >= df["close"])
        & (df["high"] >= df["low"])
        & (df["low"] <= df["open"])
        & (df["low"] <= df["close"])
    )
    invalid_count = int((~valid).sum())
    if invalid_count:
        logging.warning("%s quotes dropped %d invalid/placeholder OHLC rows", market, invalid_count)
    return df.loc[valid].copy()


def fetch_twse_quotes(date_int: int) -> pd.DataFrame:
    """抓取上市公司當日收盤行情（DB 存原始值：volume 股、amount 元）"""
    date_str = str(date_int)
    url = "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX"
    resp = retry_get(
        url,
        params={"date": date_str, "type": "ALL", "response": "json"},
        timeout=10,
        retries=3,
        backoff=1.0,
        verify=get_ssl_verify(),
    )
    if resp is None:
        logging.error("TWSE quotes fetch failed for %s after retries", date_str)
        return pd.DataFrame()
    data = resp.json()

    tables = data.get("tables", [])
    target_table = None
    for t in tables:
        if "每日收盤行情" in t.get("title", ""):
            target_table = t
            break

    if not target_table or not target_table.get("data"):
        return pd.DataFrame()

    fields = target_table.get("fields", [])
    raw_data = target_table.get("data", [])
    df = pd.DataFrame(raw_data, columns=fields)

    col_map = {
        "證券代號": "stock_id",
        "證券名稱": "name",
        "成交股數": "volume",
        "成交金額": "amount",
        "開盤價": "open",
        "最高價": "high",
        "最低價": "low",
        "收盤價": "close",
    }

    df = df.rename(columns=col_map)
    req_cols = ["stock_id", "name", "volume", "amount", "open", "high", "low", "close"]
    for c in req_cols:
        if c not in df.columns:
            logging.warning(f"TWSE quotes missing required column: {c}")
            return pd.DataFrame()

    df = df[req_cols].copy()
    df["date"] = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
    df["market"] = "TWSE"

    # DB 存原始值（股/元），顯示層才轉換
    df["volume"] = df["volume"].apply(safe_int)
    df["amount"] = df["amount"].apply(safe_int)

    for col in ["open", "high", "low", "close"]:
        df[col] = df[col].apply(safe_float)

    # [AI MOD] 只保留 4 碼純股票（排除 ETF、REITs、權證、期貨等衍生商品）
    df = df[df["stock_id"].astype(str).str.match(r"^\d{4}$")]

    return _get_valid_ohlc_rows(df, "TWSE")


def fetch_tpex_quotes(date_int: int) -> pd.DataFrame:
    """抓取上櫃公司當日收盤行情（DB 存原始值：volume 股、amount 元）"""
    roc_year = date_int // 10000 - 1911
    roc_date = f"{roc_year}/{date_int % 10000 // 100:02d}/{date_int % 100:02d}"
    url = "https://www.tpex.org.tw/web/stock/aftertrading/otc_quotes_no1430/stk_wn1430_result.php"
    resp = retry_get(
        url,
        params={"l": "zh-tw", "d": roc_date, "se": "AL", "s": "0,asc,0"},
        timeout=10,
        retries=3,
        backoff=1.0,
        verify=get_ssl_verify(),
        ssl_fallback=True,
    )
    if resp is None:
        logging.error("TPEx quotes fetch failed for %s after retries", date_int)
        return pd.DataFrame()
    data = resp.json()

    raw_data = data.get("aaData", data.get("data", []))
    fields = []
    tables = data.get("tables", [])
    if not raw_data:
        # TPEx 新版 API 格式兼容處理
        if tables:
            raw_data = tables[0].get("data", [])
            fields = tables[0].get("fields", [])

    # 非交易日（或盤後尚無行情）時，API 會回覆 totalCount:0 與空 data，
    # 屬於正常而非格式改版，降級為 INFO 避免誤導為「old format detected」。
    total_count = tables[0].get("totalCount") if tables else None
    if total_count == 0 and not raw_data:
        logging.info(
            "TPEx quotes empty (totalCount=0, likely non-trading day) for %s, skipping.",
            date_int,
        )
        return pd.DataFrame()

    if not raw_data or not fields:
        logging.warning("TPEx quotes data or fields missing (old format detected), aborting to avoid index guess.")
        return pd.DataFrame()

    df = pd.DataFrame(raw_data, columns=[f.strip() for f in fields])
    col_map = {
        "代號": "stock_id",
        "名稱": "name",
        "收盤": "close",
        "開盤": "open",
        "最高": "high",
        "最低": "low",
        "成交股數": "volume",
        "成交金額(元)": "amount",
    }
    df = df.rename(columns=col_map)

    req_cols = ["stock_id", "name", "volume", "amount", "open", "high", "low", "close"]
    for c in req_cols:
        if c not in df.columns:
            logging.warning(f"TPEx quotes missing required column: {c}")
            return pd.DataFrame()

    df = df[req_cols].copy()
    date_str = str(date_int)
    df["date"] = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
    df["market"] = "TPEx"

    # DB 存原始值（股/元），顯示層才轉換
    df["volume"] = df["volume"].apply(safe_int)
    df["amount"] = df["amount"].apply(safe_int)

    for col in ["open", "high", "low", "close"]:
        df[col] = df[col].apply(safe_float)

    # [AI MOD] 只保留 4 碼純股票（排除 ETF、REITs、權證等）
    df = df[df["stock_id"].astype(str).str.match(r"^\d{4}$")]

    return _get_valid_ohlc_rows(df, "TPEx")


def update_stock_meta_from_df(df: pd.DataFrame):
    """從行情 df 擷取 stock_id, name, market → 更新 stock_meta"""
    if df.empty:
        return
    from twstock.core.processor import DataProcessor

    # 需要的欄位：stock_id, name（必要）；market 由 updater.py 在 concat 前標記
    needed = ["stock_id", "name"]
    if "market" in df.columns:
        needed.append("market")
    meta_df = df[needed].copy()
    meta_df["stock_name"] = meta_df["name"]
    meta_df["type"] = "COMMON"  # 與 trading_calendar.py / updater.py 查詢條件一致
    meta_df["source"] = "quotes"
    meta_df["industry_category"] = ""
    # market 若沒帶入（舊呼叫端相容），保留空字串；否則用標記值（TSE/OTC）
    if "market" not in meta_df.columns:
        meta_df["market"] = ""

    DataProcessor().upsert_meta(meta_df)
