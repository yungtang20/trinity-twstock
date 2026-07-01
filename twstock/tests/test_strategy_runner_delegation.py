# -*- coding: utf-8 -*-
"""
test_strategy_runner_delegation.py — strategy_runner 委派與決定論測試

驗證：
1. run_strategy() 確實委派給策略模組（可被 monkeypatch 替換）
2. 輸出無隨機性（相同輸入 → 相同輸出）
"""
from __future__ import annotations


def test_strategy_runner_delegates_to_real_strategy(monkeypatch):
    """run_strategy() 應委派給可被替換的策略實例。"""
    import strategy_runner

    called = {}

    class FakeStrategy:
        def analyze(self, stock_id: str):
            called["stock_id"] = stock_id
            return {
                "strategy": "chips",
                "stock_id": stock_id,
                "signal": "bullish",
            }

    monkeypatch.setattr(strategy_runner, "ChipsStrategy", FakeStrategy)

    result = strategy_runner.run_strategy("chips", "2330")

    assert called["stock_id"] == "2330"
    assert result["strategy"] == "chips"
    assert result["stock_id"] == "2330"


def test_strategy_runner_is_deterministic(monkeypatch):
    """run_strategy() 必須是決定論的 — 相同輸入產生相同輸出。"""
    import strategy_runner

    class FakeStrategy:
        def analyze(self, stock_id: str):
            return {
                "strategy": "ai",
                "stock_id": stock_id,
                "score": 0.87,
            }

    monkeypatch.setattr(strategy_runner, "AIStrategy", FakeStrategy)

    result1 = strategy_runner.run_strategy("ai", "2330")
    result2 = strategy_runner.run_strategy("ai", "2330")

    assert result1 == result2
