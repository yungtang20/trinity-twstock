# -*- coding: utf-8 -*-
"""
config.py — 統一設定管理介面（re-export 薄封裝）

 production 路徑由 api_config.py（dotenv 兩段式 bridge）載入；
 本模組提供統一的 Settings dataclass 視圖，供 production 與 tests 使用。
 """
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from api_config import _ensure_loaded


@dataclass
class Settings:
    finmind_api_token: Optional[str] = None
    longcat_api_key: Optional[str] = None
    longcat_api_url: str = "https://api.longcat.chat/openai"
    longcat_model: str = "LongCat-2.0-Preview"
    supabase_url: str = ""
    supabase_key: str = ""
    kronos_model_id: str = "NeoQuasar/Kronos-base"
    kronos_tokenizer_id: str = "NeoQuasar/Kronos-Tokenizer-base"
    twse_base_url: str = "https://www.twse.com.tw"
    tpex_base_url: str = "https://www.tpex.org.tw"
    tdcc_openapi_url: str = "https://openapi.tdcc.com.tw/v1/opendata/1-5"
    tdcc_portal_url: str = "https://www.tdcc.com.tw/portal/zh/smWeb/qryStock"


def _clean(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    stripped = value.strip()
    return stripped if stripped else None


def load_settings() -> Settings:
    """
    透過 api_config._ensure_loaded() 橋接 dotenv 後，用 os.environ 封裝為 Settings。

    注意：api_config 的 getter（get_finmind_token 等）在 key 不存在時會 raise，
    所以這裡用 os.environ.get() 安全取值（_dotenv 已 ensure_loaded 過）。
    """
    _ensure_loaded()
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
