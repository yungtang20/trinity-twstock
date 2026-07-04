# -*- coding: utf-8 -*-
"""
test_deprecated_modules.py — 已淘汰模組驗證

確認已刪除的模組：(1) 檔案不存在，(2) 不再被任何 production 程式引用。
仍在使用中的模組（kronos_engine, prediction_strategy, suspended, utils）不列於此處。
"""
from __future__ import annotations

from pathlib import Path

# 已刪除的模組（實體檔案不存在）
DELETED_MODULES = [
    "twstock/strategy/vision_engine.py",
    "twstock/polars_compat.py",
    "twstock/official/price_adjuster.py",
]

# 不得引用已刪除模組的 production 檔案
PRODUCTION_FILES = [
    "twstock/strategy_runner.py",
    "twstock/main.py",
    "twstock/strategy/patterns_strategy.py",
    "twstock/strategy/chips_strategy.py",
    "twstock/strategy/ma_strategy.py",
    "twstock/strategy/sr_analyzer.py",
    "twstock/strategy/prediction_strategy.py",
]

# 已刪除模組名稱片段（用於字串掃描）
DELETED_NAME_FRAGMENTS = [
    "vision_engine",
    "polars_compat",
    "price_adjuster",
]


def test_deleted_modules_do_not_exist():
    """已刪除的模組實體檔案不應存在於 repo 中。"""
    for module_path in DELETED_MODULES:
        assert not Path(module_path).exists(), f"{module_path} 應該已被刪除"


def test_production_code_does_not_reference_deleted_modules():
    """Production 程式不應引用已刪除模組的名稱片段。"""
    for file_path in PRODUCTION_FILES:
        src = Path(file_path).read_text(encoding="utf-8")
        for fragment in DELETED_NAME_FRAGMENTS:
            # 允許出現在註解中作為歷史記錄（例如 "# vision_engine 已刪"）
            # 但不允許出現在可執行的 import 語句中
            offending_lines = []
            for lineno, line in enumerate(src.splitlines(), 1):
                stripped = line.strip()
                if fragment in line and not stripped.startswith("#"):
                    offending_lines.append((lineno, stripped))
            assert not offending_lines, (
                f"{file_path} 仍引用已刪除模組 '{fragment}': "
                f"{offending_lines[:3]}"
            )
