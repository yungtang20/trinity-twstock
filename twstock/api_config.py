#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
api_config.py - 統一 API 設定讀取模組
所有 API key / endpoint 由此模組集中管理，禁止在其他檔案中硬編碼。
設定檔路徑：twstock/api.env（優先），其次 twstock/.env、環境變數。
"""

import logging
import os
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
