#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
longcat_vision.py - LongCat AI 分析模組
用 LongCat-2.0 文字模型分析 K 線資料，提供投資建議。

注意：LongCat-2.0 目前不支援圖片視覺，改送文字摘要給模型分析。
"""

import os
import logging
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


def _get_api_key() -> Optional[str]:
    """從 api.env 或環境變數取得 LongCat API Key"""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "api.env")
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("LONGCAT_API_KEY="):
                    return line.split("=", 1)[1].strip()
    return os.environ.get("LONGCAT_API_KEY")


def _build_kline_summary(df: pd.DataFrame, stock_id: str, stock_name: str) -> str:
    """將 K 線資料轉為文字摘要供 LLM 分析"""
    if df is None or df.empty:
        return ""

    work = df.tail(20).copy()
    lines = []
    title = f"{stock_id} {stock_name}".strip() if stock_id or stock_name else "股票"
    lines.append(f"[{title}] 近日 K 線（日期 開 高 低 收 成交量）：")

    for _, row in work.iterrows():
        date_str = str(row.get("date", ""))[:10]
        o = row.get("open", 0)
        h = row.get("high", 0)
        l = row.get("low", 0)
        c = row.get("close", 0)
        v = row.get("volume", 0)
        sheets = int(v) // 1000
        lines.append(f"{date_str}  {o:.2f}  {h:.2f}  {l:.2f}  {c:.2f}  {sheets}張")

    # 簡易統計
    closes = work["close"].dropna().values
    if len(closes) >= 2:
        current = float(closes[-1])
        prev = float(closes[-2])
        change_pct = (current - prev) / prev * 100 if prev else 0
        lines.append(f"\n最新收盤: {current:.2f}  漲跌: {change_pct:+.2f}%")
        lines.append(f"20日最高: {work['high'].max():.2f}  最低: {work['low'].min():.2f}")
        avg_vol = int(work["volume"].mean()) // 1000
        lines.append(f"均量: {avg_vol:,}張")

    return "\n".join(lines)


def analyze_kline_with_longcat(
    df: pd.DataFrame,
    stock_id: str = "",
    stock_name: str = "",
) -> Optional[str]:
    """
    用 LongCat AI 分析 K 線資料，回傳分析文字。
    如果 API key 未設定，回傳 None。
    """
    api_key = _get_api_key()
    if not api_key:
        logger.debug("LONGCAT_API_KEY 未設定，跳過 LongCat 分析")
        return None

    summary = _build_kline_summary(df, stock_id, stock_name)
    if not summary:
        return None

    try:
        import requests
    except ImportError:
        logger.warning("requests 未安裝")
        return None

    try:
        response = requests.post(
            "https://api.longcat.chat/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "LongCat-2.0",
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            "以下是某台股近日 K 線資料，請協助分析：\n\n"
                            f"{summary}\n\n"
                            "請提供：\n"
                            "1. 目前趨勢（多頭/空頭/盤整）\n"
                            "2. 重要支撐與壓力位\n"
                            "3. 短線（1-5 日）操作建議\n"
                            "4. 注意事項\n"
                            "請用繁體中文回答，簡明扼要（200字內）。"
                        ),
                    }
                ],
                "max_tokens": 2000,
                "temperature": 0.7,
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        msg = data["choices"][0]["message"]
        # LongCat-2.0 可能把回應放在 reasoning_content
        return msg.get("content") or msg.get("reasoning_content", "")
    except Exception as e:
        logger.warning("LongCat API 呼叫失敗: %s", e)
        return None
