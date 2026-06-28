#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
api_config.py - 統一 API 設定讀取模組
所有 API key / endpoint 由此模組集中管理，禁止在其他檔案中硬編碼。
設定檔路徑：twstock/api.env（優先），其次 twstock/.env、環境變數。
"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# twstock/ 目錄
_PKG_DIR = Path(__file__).resolve().parent

# 載入順序：api.env > .env > 系統環境變數
_env_loaded = False


def _ensure_loaded():
    global _env_loaded
    if _env_loaded:
        return
    # 優先載入 api.env
    api_env = _PKG_DIR / "api.env"
    if api_env.exists():
        load_dotenv(api_env, override=True)
        logger.debug("Loaded API config from %s", api_env)
    # 再載入 .env（不覆蓋 api.env 已設定的值）
    dot_env = _PKG_DIR / ".env"
    if dot_env.exists():
        load_dotenv(dot_env, override=False)
    _env_loaded = True


# ── FinMind ────────────────────────────────────────────────

def get_finmind_token() -> str:
    """取得 FinMind API token。"""
    _ensure_loaded()
    token = os.environ.get("FINMIND_TOKEN", "").strip()
    if not token:
        raise ValueError(
            "FINMIND_TOKEN 未設定。請在 twstock/api.env 或系統環境變數中設定。"
        )
    return token


# ── LongCat AI ─────────────────────────────────────────────

def get_longcat_api_key() -> str:
    """取得 LongCat API key。"""
    _ensure_loaded()
    key = os.environ.get("LONGCAT_API_KEY", "").strip()
    if not key:
        raise ValueError(
            "LONGCAT_API_KEY 未設定。請在 twstock/api.env 或系統環境變數中設定。"
        )
    return key


def get_longcat_api_url() -> str:
    """取得 LongCat API URL。"""
    _ensure_loaded()
    return os.environ.get(
        "LONGCAT_API_URL",
        "https://api.longcat.chat/openai",
    )


def get_longcat_model() -> str:
    """取得 LongCat 模型名稱。"""
    _ensure_loaded()
    return os.environ.get("LONGCAT_MODEL", "LongCat-2.0-Preview")


# ── Supabase ───────────────────────────────────────────────

def get_supabase_url() -> str:
    """取得 Supabase URL。"""
    _ensure_loaded()
    return os.environ.get("SUPABASE_URL", "").strip()


def get_supabase_key() -> str:
    """取得 Supabase anonymous key。"""
    _ensure_loaded()
    return os.environ.get("SUPABASE_KEY", "").strip()


# ── Kronos AI 模型 ─────────────────────────────────────────

def get_kronos_model_id() -> str:
    """取得 Kronos 模型 ID。"""
    _ensure_loaded()
    return os.environ.get("KRONOS_MODEL_ID", "NeoQuasar/Kronos-base")


def get_kronos_tokenizer_id() -> str:
    """取得 Kronos tokenizer ID。"""
    _ensure_loaded()
    return os.environ.get("KRONOS_TOKENIZER_ID", "NeoQuasar/Kronos-Tokenizer-base")


# ── 官方 API 端點（公開，無需金鑰）───────────────────────

def get_twse_base_url() -> str:
    """取得 TWSE 基礎 URL。"""
    _ensure_loaded()
    return os.environ.get("TWSE_BASE_URL", "https://www.twse.com.tw")


def get_tpex_base_url() -> str:
    """取得 TPEX 基礎 URL。"""
    _ensure_loaded()
    return os.environ.get("TPEX_BASE_URL", "https://www.tpex.org.tw")


def get_tdcc_openapi_url() -> str:
    """取得 TDCC OpenAPI URL。"""
    _ensure_loaded()
    return os.environ.get(
        "TDCC_OPENAPI_URL",
        "https://openapi.tdcc.com.tw/v1/opendata/1-5",
    )


def get_tdcc_portal_url() -> str:
    """取得 TDCC 官網爬蟲 URL。"""
    _ensure_loaded()
    return os.environ.get(
        "TDCC_PORTAL_URL",
        "https://www.tdcc.com.tw/portal/zh/smWeb/qryStock",
    )
