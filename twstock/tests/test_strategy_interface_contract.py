# -*- coding: utf-8 -*-
"""
test_strategy_interface_contract.py — 策略介面契約測試

驗證所有策略模組是否提供 analyze(stock_id) 統一介面。
若策略尚未提供，strategy_runner 內部會用 adapter 包裝。
"""

from __future__ import annotations

import importlib
from pathlib import Path

# _strategy模組列表 — 每個策略對應的 (module_name, class_name)
# 注意：這些類別可能不存在，測試會驗證它們是否存在且有 analyze()
STRATEGY_CLASSES = [
    ("strategy.chips_strategy", "ChipsStrategy"),
    ("strategy.ma_strategy", "MAStrategy"),
    ("strategy.patterns_strategy", "PatternStrategy"),
    ("strategy.sr_analyzer", "SupportResistanceStrategy"),
]


def test_all_strategies_expose_analyze():
    """所有策略類別應有 callable 的 analyze() 方法。"""
    src = Path("twstock/strategy_runner.py").read_text(encoding="utf-8")

    for module_name, class_name in STRATEGY_CLASSES:
        try:
            module = importlib.import_module(module_name)
            cls = getattr(module, class_name)
            instance = cls()
            assert hasattr(instance, "analyze"), f"{class_name} 應有 analyze() 方法"
            assert callable(instance.analyze), f"{class_name}.analyze 應為 callable"
        except (ImportError, AttributeError):
            # 類別不存在 — 檢查 strategy_runner 是否有對應的 adapter
            adapter_name = f"_{class_name}Adapter"
            assert adapter_name in src, (
                f"{module_name}.{class_name} 不存在，"
                f"且 strategy_runner 中也沒有 {adapter_name}。"
                f"請建立策略類別或 adapter。"
            )


def test_strategy_runner_adapters_exist():
    """strategy_runner.py 應為所有策略提供 adapter 或 direct reference。"""
    src = Path("twstock/strategy_runner.py").read_text(encoding="utf-8")

    # 至少引用了這些策略模組的適配
    assert "chips_strategy" in src, "應引用 chips_strategy"
    assert "ma_strategy" in src, "應引用 ma_strategy"
    assert "patterns_strategy" in src, "應引用 patterns_strategy"
    assert "sr_analyzer" in src, "應引用 sr_analyzer"
