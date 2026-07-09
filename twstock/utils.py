# -*- coding: utf-8 -*-
"""
utils.py — 跨模組共用工具函式

收斂原本散落在 main.py、official/utils.py、fetcher.py 的重複工具：
  - safe_float / safe_int：數值轉換（移除千分位逗號）
  - HTTP session / headers / GET helper
  - get_stock_name：從 stock_meta 查股票名稱
  - toroc_date：西元轉民國紀年
  - get_sys_info / get_market_mode / format_price_change：系統資訊與格式化

使用方式：
  from utils import safe_float, safe_int, get_http_session, ...
"""

from __future__ import annotations

import os
import sys
from datetime import datetime

# 確保 twstock 目錄在 sys.path（讓 from db import 能運作）
_DIR = os.path.dirname(os.path.abspath(__file__))
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)

from twstock.db import (  # noqa: E402  # ponytail: db 為基礎模組，此頂層耦合可接受（utils 無循環依賴風險）
    file_size_mb,
    get_connection,
    get_path,
)

# ── SSL 驗證設定 ─────────────────────────────────────────
_SSL_VERIFY_VALUE: bool | str | None = None  # 模組快取，避免重複偵測


def get_ssl_verify() -> bool | str:
    """決定 SSL verify 參數值。

    優先順序：
      1. 環境變數 REQUESTS_CA_BUNDLE / CURL_CA_BUNDLE（若指向有效檔案）
      2. certifi 提供的 CA bundle（若套件已安裝）
      3. True（requests 內建 CA bundle）

    回傳值可直接傳入 requests.get(verify=...)。
    """
    global _SSL_VERIFY_VALUE
    if _SSL_VERIFY_VALUE is not None:
        return _SSL_VERIFY_VALUE

    # 1. 環境變數
    for env_var in ("REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE"):
        env_path = os.environ.get(env_var)
        if env_path and os.path.isfile(env_path):
            _SSL_VERIFY_VALUE = env_path
            return _SSL_VERIFY_VALUE

    # 2. certifi
    try:
        import certifi

        _SSL_VERIFY_VALUE = certifi.where()
        return _SSL_VERIFY_VALUE
    except ImportError:
        pass

    # 3. 預設
    _SSL_VERIFY_VALUE = True
    return _SSL_VERIFY_VALUE


# ── 安全數值轉換（統一處理千分位逗號）────────────────────
def safe_float(val, default: float = 0.0) -> float:
    """將值轉為 float，處理 '-' / '' / None / 千分位逗號。"""
    try:
        if val in ("-", "", None):
            return default
        val = str(val).replace(",", "")
        return float(val)
    except (ValueError, TypeError):
        return default


def safe_int(val, default: int = 0) -> int:
    """將值轉為 int，處理 '-' / '' / None / 千分位逗號。"""
    try:
        if val in ("-", "", None):
            return default
        val = str(val).replace(",", "")
        return int(val)
    except (ValueError, TypeError):
        return default


# ── HTTP helpers ─────────────────────────────────────────
def default_http_headers() -> dict:
    """預設 User-Agent header。"""
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }


def get_http_session():
    """建立 requests.Session 並帶上預設 header。失敗回傳 None。"""
    try:
        import requests

        session = requests.Session()
        session.headers.update(default_http_headers())
        return session
    except Exception:
        return None


def safe_http_get(url, session=None, timeout=5.0, verify=True, params=None, headers=None):
    """安全 GET，失敗回傳 None。

    verify 可傳入 True（requests 內建 CA）、False（不驗證，不建議）、
    或字串（CA bundle 路徑，如 certifi.where()）。
    """
    if session is None:
        session = get_http_session()
    if session is None:
        return None
    try:
        response = session.get(url, timeout=timeout, verify=verify, params=params, headers=headers)
        response.raise_for_status()
        return response
    except Exception:
        return None


# ── 股票名稱查詢 ─────────────────────────────────────────
def get_token():
    """從 api_config 取得 FinMind token。"""
    from twstock.api_config import get_finmind_token

    return get_finmind_token()


def get_stock_name(stock_id: str) -> str:
    """從 stock_meta 取得股票名稱，失敗回傳 '未知'。"""
    from twstock.strategy._utils import _lookup_stock_name

    try:
        with get_connection(readonly=True) as conn:
            return _lookup_stock_name(conn, stock_id) or "未知"
    except Exception:
        return "未知"


# ── 日期轉換 ─────────────────────────────────────────────
def to_roc_date(date_str):
    """將西元日期 (YYYY-MM-DD 或 YYYYMMDD) 轉換為民國紀年格式。"""
    if not date_str or date_str == "N/A":
        return "N/A"
    try:
        clean_date = str(date_str).replace("-", "").replace("/", "")
        if len(clean_date) >= 8:
            y = int(clean_date[:4])
            m = clean_date[4:6]
            d = clean_date[6:8]
            return f"{y - 1911}/{m}/{d}"
        return date_str
    except (ValueError, TypeError):
        return date_str


# ── 系統資訊 ─────────────────────────────────────────────
def get_sys_info() -> dict:
    """取得資料庫狀態資訊。"""
    info = {
        "size": "0.0 MB",
        "stocks": 0,
        "last": "N/A",
        "first": "N/A",
        "status": "Offline",
        "path": "N/A",
    }
    try:
        if os.path.exists(get_path()):
            info["size"] = f"{file_size_mb():.1f} MB"
            info["path"] = get_path()
            with get_connection(readonly=True) as conn:
                info["stocks"] = conn.execute(
                    "SELECT COUNT(*) FROM stock_meta "
                    "WHERE LENGTH(stock_id) = 4 AND stock_id GLOB '[1-9][0-9][0-9][0-9]'"
                ).fetchone()[0]
                last_date = conn.execute("SELECT MAX(date) FROM stock_history").fetchone()[0]
                first_date = conn.execute("SELECT MIN(date) FROM stock_history").fetchone()[0]
                info["last"] = last_date if last_date else "N/A"
                info["first"] = first_date if first_date else "N/A"
                info["status"] = "Ready"
    except Exception:
        pass
    return info


def get_market_mode() -> str:
    """判斷目前市場狀態（盤中 / 收盤後 / 假日）。"""
    now = datetime.now()
    mins = now.hour * 60 + now.minute
    if now.weekday() >= 5:
        return "收盤後 (假日)"
    if 540 <= mins <= 815:
        return "盤中"
    return "收盤後"


def format_price_change(current: float, previous: float):
    """計算漲跌 diff、pct 與對應顏色。"""
    diff = current - previous
    pct = (diff / previous) * 100 if previous else 0
    if pct >= 9.9:
        color = "white on red"
    elif pct <= -9.9:
        color = "white on green"
    else:
        color = "bright_red" if diff > 0 else ("bright_green" if diff < 0 else "white")
    return diff, pct, color
