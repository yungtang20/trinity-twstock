import pandas as pd
import requests
import logging
from datetime import datetime
from .utils import safe_int
from retry import retry_get

def _get_session():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })
    return session

SESSION = _get_session()

def fetch_twse_institutional(date_int: int) -> pd.DataFrame:
    """上市三大法人（單位：張）"""
    date_str = str(date_int)
    url = "https://www.twse.com.tw/rwd/zh/fund/T86"
    resp = retry_get(
        url,
        params={"response": "json", "date": date_str, "selectType": "ALLBUT0999"},
        timeout=10,
        retries=3,
        backoff=1.0,
    )
    if resp is None:
        logging.error("TWSE institutional fetch failed for %s after retries", date_str)
        return pd.DataFrame()
    data = resp.json()
        
    if not data.get("data"):
        return pd.DataFrame()
        
    fields = data.get("fields", [])
    raw_data = data.get("data", [])
    df = pd.DataFrame(raw_data, columns=fields)
    
    # TWSE T86 欄位名已由實測 fields 確認吻合
    col_map = {
        "證券代號": "stock_id",
        "外陸資買進股數(不含外資自營商)": "foreign_buy",
        "外陸資賣出股數(不含外資自營商)": "foreign_sell",
        "投信買進股數": "trust_buy",
        "投信賣出股數": "trust_sell",
    }
    df = df.rename(columns=col_map)
    req_cols = ["stock_id", "foreign_buy", "foreign_sell", "trust_buy", "trust_sell"]
    for c in req_cols:
        if c not in df.columns:
            logging.warning(f"TWSE institutional missing required column: {c}")
            return pd.DataFrame()
            
    df = df[req_cols].copy()
    df["date"] = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
    df["market"] = "TWSE"
    
    # 轉換為張 (TWSE 原始為股數)
    for col in ["foreign_buy", "foreign_sell", "trust_buy", "trust_sell"]:
        df[col] = df[col].apply(lambda x: safe_int(x) // 1000)
        
    df["dealer_buy"] = 0
    df["dealer_sell"] = 0
    return df

def fetch_tpex_institutional(date_int: int) -> pd.DataFrame:
    """上櫃三大法人（單位：張）"""
    roc_date = f"{roc_year}/{date_int % 10000 // 100:02d}/{date_int % 100:02d}"
    url = "https://www.tpex.org.tw/web/stock/3insti/daily_trade/3itrade_hedge_result.php"
    resp = retry_get(
        url,
        params={"l": "zh-tw", "o": "json", "se": "AL", "t": "D", "d": roc_date},
        timeout=10,
        retries=3,
        backoff=1.0,
    )
    if resp is None:
        logging.error("TPEx institutional fetch failed for %s after retries", date_int)
        return pd.DataFrame()
    data = resp.json()
        
    raw_data = data.get("aaData", data.get("data", []))
    if not raw_data:
        tables = data.get("tables", [])
        if tables:
            raw_data = tables[0].get("data", [])
            
    if not raw_data:
        return pd.DataFrame()
        
    df = pd.DataFrame(raw_data)
    if len(df.columns) < 24:
        logging.warning("TPEx institutional format changed, columns less than 24.")
        return pd.DataFrame()
        
    # 保留 7 組買賣超
    df = df.rename(columns={
        0: "stock_id",
        1: "name",
        2: "g1_buy", 3: "g1_sell", 4: "g1_net",
        5: "g2_buy", 6: "g2_sell", 7: "g2_net",
        8: "g3_buy", 9: "g3_sell", 10: "g3_net",
        11: "g4_buy", 12: "g4_sell", 13: "g4_net",
        14: "g5_buy", 15: "g5_sell", 16: "g5_net",
        17: "g6_buy", 18: "g6_sell", 19: "g6_net",
        20: "g7_buy", 21: "g7_sell", 22: "g7_net",
        23: "total_net"
    })
    
    # 進行安全轉型
    for col in [f"g{i}_{typ}" for i in range(1, 8) for typ in ("buy", "sell", "net")] + ["total_net"]:
        df[col] = df[col].apply(safe_int)
        
    # 保留 raw columns 給下游使用，延遲綁定
    # 【推斷】暫時不處理 foreign/trust 的對應
    
    req_cols = ["stock_id", "name"] + [f"g{i}_{typ}" for i in range(1, 8) for typ in ("buy", "sell", "net")] + ["total_net"]
    df = df[req_cols].copy()
    date_str = str(date_int)
    df["date"] = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
    df["market"] = "TPEx"
    
    return df

def fetch_all_institutional(date_int: int) -> pd.DataFrame:
    twse = fetch_twse_institutional(date_int)
    tpex = fetch_tpex_institutional(date_int)
    if twse.empty and tpex.empty:
        return pd.DataFrame()
    return pd.concat([twse, tpex], ignore_index=True).drop_duplicates(subset=['stock_id','date'])