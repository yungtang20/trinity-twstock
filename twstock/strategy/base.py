# -*- coding: utf-8 -*-
"""strategy/base.py — 策略抽象基底類別。

所有策略模組應繼承 BaseStrategy 以獲得統一的：
  - 輸入處理（股號驗證、參數選擇）
  - 輸出渲染（Rich 表格/面板）
  - 錯誤處理（log + 優雅降級）

子類別只需實作核心演算法：prepare_data()、analyze()、render()。
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

import pandas as pd

from twstock.db import get_connection
from twstock.strategy._utils import fetch_klines
from twstock.utils import get_stock_name

logger = logging.getLogger(__name__)


class BaseStrategy(ABC):
    """策略抽象基底。

    子類別實作：
        prepare_data(code, **kwargs) -> pd.DataFrame
        analyze(data) -> dict
        render(results) -> str

    run() 組合上述步驟，提供統一的 CLI/TUI 入口。
    """

    # 子類別覆寫
    name: str = "base"
    description: str = "Base strategy"

    def __init__(self, code: str):
        self.code = code
        self.stock_name = get_stock_name(code)

    # ── 核心介面（子類別必須實作）─────────────────────────
    @abstractmethod
    def prepare_data(self, **kwargs) -> pd.DataFrame:
        """載入並準備分析所需資料。"""

    @abstractmethod
    def analyze(self, data: pd.DataFrame) -> Dict[str, Any]:
        """執行策略分析，回傳結果 dict。"""

    @abstractmethod
    def render(self, results: Dict[str, Any]) -> str:
        """將分析結果格式化為顯示字串。"""

    # ── 通用流程 ─────────────────────────────────────────
    def run(self, **kwargs) -> Optional[str]:
        """執行完整策略流程：prepare → analyze → render。"""
        try:
            data = self.prepare_data(**kwargs)
            if data is None or (hasattr(data, "empty") and data.empty):
                msg = f"[yellow]⚠️ {self.code} {self.stock_name}：無足夠資料[/yellow]"
                print(msg)
                return None
            results = self.analyze(data)
            return self.render(results)
        except Exception as e:
            logger.error("Strategy %s failed for %s: %s", self.name, self.code, e)
            print(f"[red]❌ {self.name} 分析失敗: {e}[/red]")
            return None

    # ── 工具方法 ─────────────────────────────────────────
    @staticmethod
    def get_latest_date(table: str = "stock_history") -> Optional[str]:
        """取得資料庫最新日期。"""
        try:
            with get_connection(readonly=True) as conn:
                row = conn.execute(f"SELECT MAX(date) FROM {table}").fetchone()
                return row[0] if row else None
        except Exception:
            return None

    @staticmethod
    def fetch_klines(code: str, limit: int = 512) -> pd.DataFrame:
        """取得 K 線資料。"""
        try:
            with get_connection(readonly=True) as conn:
                return fetch_klines(conn, code, limit=limit)
        except Exception:
            return pd.DataFrame()
