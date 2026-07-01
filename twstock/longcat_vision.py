#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
longcat_vision.py - LongCat AI 視覺辨識模組
用 LongCat 多模態模型分析 K 線圖，提供 AI 投資建議。
"""

import os
import io
import base64
import logging
import tempfile
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


def _get_api_key() -> Optional[str]:
    """從 api.env 或環境變數取得 LongCat API Key"""
    # 嘗試從 api.env 讀取
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "api.env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("LONGCAT_API_KEY="):
                    return line.split("=", 1)[1].strip()
    #  fallback 到環境變數
    return os.environ.get("LONGCAT_API_KEY")


def _generate_kline_image(df: pd.DataFrame, stock_id: str = "", stock_name: str = "") -> Optional[str]:
    """
    用 mplfinance 產生 K 線圖 PNG，回傳 base64 編碼。
    """
    try:
        import mplfinance as mpf
    except ImportError:
        logger.warning("mplfinance 未安裝，無法產生 K 線圖。請執行: pip install mplfinance")
        return None

    if df is None or df.empty:
        return None

    # 準備資料：mplfinance 需要 DatetimeIndex + OHLCV 欄位
    work = df.copy()
    if not isinstance(work.index, pd.DatetimeIndex):
        if 'date' in work.columns:
            work['date'] = pd.to_datetime(work['date'])
            work = work.set_index('date')
        else:
            work.index = pd.to_datetime(work.index)
    work = work.sort_index()

    # 確保欄位名稱符合 mplfinance 預期
    col_map = {}
    for col in work.columns:
        lower = col.lower()
        if lower in ('open', 'high', 'low', 'close', 'volume'):
            col_map[col] = lower
    work = work.rename(columns=col_map)

    required = ['open', 'high', 'low', 'close']
    for r in required:
        if r not in work.columns:
            return None

    # 取最近 60 天
    work = work.tail(60)

    # 產生圖片
    title = f"{stock_id} {stock_name}".strip() if stock_id or stock_name else "K 線圖"
    buf = io.BytesIO()
    try:
        mpf.plot(
            work,
            type='candle',
            style='yahoo',
            title=title,
            volume=True,
            figsize=(10, 6),
            savefig=buf,
        )
    except Exception as e:
        logger.warning("mplfinance 繪圖失敗: %s", e)
        return None

    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    return img_base64


def analyze_kline_with_longcat(
    df: pd.DataFrame,
    stock_id: str = "",
    stock_name: str = "",
) -> Optional[str]:
    """
    用 LongCat AI 分析 K 線圖，回傳分析文字。
    如果 API key 未設定或 mplfinance 未安裝，回傳 None。
    """
    api_key = _get_api_key()
    if not api_key:
        logger.debug("LONGCAT_API_KEY 未設定，跳過 LongCat 分析")
        return None

    img_base64 = _generate_kline_image(df, stock_id, stock_name)
    if not img_base64:
        return None

    # 呼叫 LongCat API
    try:
        import requests
    except ImportError:
        logger.warning("requests 未安裝")
        return None

    try:
        response = requests.post(
            "https://api.longcat.chat/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "longcat-vision",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{img_base64}"},
                            },
                            {
                                "type": "text",
                                "text": (
                                    "請分析這張台股 K 線圖，提供：\n"
                                    "1. 目前趨勢（多頭/空頭/盤整）\n"
                                    "2. 重要支撐與壓力位\n"
                                    "3. 短線（1-5 日）操作建議\n"
                                    "4. 注意事項\n"
                                    "請用繁體中文回答，簡明扼要。"
                                ),
                            },
                        ],
                    }
                ],
                "max_tokens": 500,
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        logger.warning("LongCat API 呼叫失敗: %s", e)
        return None
