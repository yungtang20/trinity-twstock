# -*- coding: utf-8 -*-
"""
config.py - 統一設定管理模組

所有設定集中由此模組讀取，只從環境變數取得，
不讀取任何檔案，避免 fallback 到 repo 中的明文 secret。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Settings:
    """應用程式設定。所有欄位皆為可選，未設定時為 None 或空字串。"""

    # ── API Tokens ──────────────────────────────────────────
    finmind_api_token: Optional[str] = None
    longcat_api_key: Optional[str] = None

    # ── LongCat API ─────────────────────────────────────────
    longcat_api_url: str = "https://api.longcat.chat/openai"
    longcat_model: str = "LongCat-2.0-Preview"

    # ── Supabase ────────────────────────────────────────────
    supabase_url: str = ""
    supabase_key: str = ""

    # ── Kronos AI ───────────────────────────────────────────
    kronos_model_id: str = "NeoQuasar/Kronos-base"
    kronos_tokenizer_id: str = "NeoQuasar/Kronos-Tokenizer-base"

    # ── 官方 API 端點（公開，無需金鑰）─────────────────────
    twse_base_url: str = "https://www.twse.com.tw"
    tpex_base_url: str = "https://www.tpex.org.tw"
    tdcc_openapi_url: str = "https://openapi.tdcc.com.tw/v1/opendata/1-5"
    tdcc_portal_url: str = "https://www.tdcc.com.tw/portal/zh/smWeb/qryStock"


def _clean(value: Optional[str]) -> Optional[str]:
    """清除空白，空字串視為 None。"""
    if value is None:
        return None
    stripped = value.strip()
    return stripped if stripped else None


def load_settings() -> Settings:
    """從環境變數載入設定。不讀取任何檔案。"""
    return Settings(
        finmind_api_token=_clean(os.getenv("FINMIND_API_TOKEN")),
        longcat_api_key=_clean(os.getenv("LONGCAT_API_KEY")),
        longcat_api_url=os.getenv("LONGCAT_API_URL", "https://api.longcat.chat/openai"),
        longcat_model=os.getenv("LONGCAT_MODEL", "LongCat-2.0-Preview"),
        supabase_url=os.getenv("SUPABASE_URL", "").strip(),
        supabase_key=os.getenv("SUPABASE_KEY", "").strip(),
        kronos_model_id=os.getenv("KRONOS_MODEL_ID", "NeoQuasar/Kronos-base"),
        kronos_tokenizer_id=os.getenv("KRONOS_TOKENIZER_ID", "NeoQuasar/Kronos-Tokenizer-base"),
        twse_base_url=os.getenv("TWSE_BASE_URL", "https://www.twse.com.tw"),
        tpex_base_url=os.getenv("TPEX_BASE_URL", "https://www.tpex.org.tw"),
        tdcc_openapi_url=os.getenv("TDCC_OPENAPI_URL", "https://openapi.tdcc.com.tw/v1/opendata/1-5"),
        tdcc_portal_url=os.getenv("TDCC_PORTAL_URL", "https://www.tdcc.com.tw/portal/zh/smWeb/qryStock"),
    )
