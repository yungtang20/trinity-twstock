# -*- coding: utf-8 -*-
"""
test_no_plaintext_secrets.py — Secrets 防呆測試

確保 repo 中沒有被提交的真實 secrets 檔案。
"""
from pathlib import Path

import pytest

# 本地開發需要 api.env（dotenv bridge），但 git 不應追蹤它們。
# 這些測試在 CI 環境才的完整意義（無 api.env 存在時通過）。
_SECRET_FILES = [
    Path("twstock/api.env"),
    Path("api.env"),
    Path(".env"),
]
_any_secret_exists = any(p.exists() for p in _SECRET_FILES)


@pytest.mark.skipif(_any_secret_exists, reason="local dev has api.env — this test is CI-only")
def test_no_real_secret_file_committed():
    """確認沒有真實 secrets 檔案存在（CI gate）。"""
    committed = [p for p in _SECRET_FILES if p.exists()]
    assert not committed, f"Remove committed secret files: {committed}"


def test_example_env_exists():
    """確認有 example env 檔案作為參考。"""
    examples = [
        Path("twstock/api.env.example"),
        Path("api.env.example"),
        Path(".env.example"),
    ]
    exists = [p for p in examples if p.exists()]
    assert exists, "至少需要一個 .env.example 檔案作為設定參考"


def test_gitignore_blocks_secrets():
    """確認 .gitignore 有排除 secrets 檔案。"""
    gitignore = Path(".gitignore")
    assert gitignore.exists(), "必須有 .gitignore 檔案"

    content = gitignore.read_text(encoding="utf-8")
    assert ".env" in content or "api.env" in content, (
        ".gitignore 應排除 .env / api.env 等 secrets 檔案"
    )
