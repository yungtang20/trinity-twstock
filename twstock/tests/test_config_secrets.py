# -*- coding: utf-8 -*-
"""
test_config_secrets.py — 設定與 secret 管理 contract 測試

驗證：
1. API key 從環境變數載入
2. 缺少環境變數時不會 fallback 到 repo 中的明文檔案
"""
from __future__ import annotations

import os
from pathlib import Path


def test_api_keys_are_loaded_from_environment(monkeypatch):
    """API key 應從環境變數載入。"""
    monkeypatch.setenv("FINMIND_API_TOKEN", "test-finmind-token")
    monkeypatch.setenv("LONGCAT_API_KEY", "test-longcat-key")

    from config import load_settings

    settings = load_settings()

    assert settings.finmind_api_token == "test-finmind-token"
    assert settings.longcat_api_key == "test-longcat-key"


def test_missing_api_keys_do_not_read_tracked_secret_file(monkeypatch):
    """缺少環境變數時，不應 fallback 到 repo 中的明文檔案。"""
    monkeypatch.delenv("FINMIND_API_TOKEN", raising=False)
    monkeypatch.delenv("LONGCAT_API_KEY", raising=False)

    # 確保沒有真实的 secret 檔案存在
    secret_files = [
        Path("twstock/api.env"),
        Path("api.env"),
        Path(".env"),
    ]
    for p in secret_files:
        assert not p.exists(), f"Secret file should not exist: {p}"

    from config import load_settings

    settings = load_settings()

    assert settings.finmind_api_token in (None, "")
    assert settings.longcat_api_key in (None, "")


def test_load_settings_returns_dataclass(monkeypatch):
    """load_settings() 應回傳一個有預設值的 dataclass。"""
    monkeypatch.setenv("FINMIND_API_TOKEN", "x")
    monkeypatch.setenv("LONGCAT_API_KEY", "y")

    from config import load_settings

    settings = load_settings()

    # 應為 dataclass 實例
    assert hasattr(settings, "__dataclass_fields__")
    # 應有所有定義的欄位
    assert "finmind_api_token" in settings.__dataclass_fields__
    assert "longcat_api_key" in settings.__dataclass_fields__
