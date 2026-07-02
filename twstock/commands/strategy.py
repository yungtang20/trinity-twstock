# -*- coding: utf-8 -*-
"""strategy 命令：策略分析 CLI 入口。"""
from __future__ import annotations

from twstock.strategy.strategies import run_strategy_cli


def execute(args) -> None:
    """args 需具備 code / scan / vol 等策略相關屬性。"""
    run_strategy_cli(args)
