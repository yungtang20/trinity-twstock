#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
kronos_engine.py - Kronos 預測引擎最小實作
提供 Monte Carlo 模擬預測（不需要 Kronos 模型權重）
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Optional


# 預設預測配置
DEFAULT_CONFIG = {
    "context_len": 512,
    "pred_days": 5,
    "mc_simulations": 200,
    "confidence_threshold": 0.55,
    "volatility_lookback": 20,
    "min_volume": 500,
    "results": None,
}


@dataclass
class PredictionResult:
    """單筆預測結果"""
    benchmark: float = 0.0
    confidence: float = 0.0
    drift: float = 0.0


@dataclass
class StockPrediction:
    """股票預測資料"""
    code: str
    name: str
    current_price: float
    volume: int
    amount: float
    score: float
    target_price: float
    confidence: float
    prev_price: float
    prev_volume: float = 0.0


class DriftStatus:
    """漂移監測狀態"""
    STABLE = "stable"
    DRIFT_UP = "drift_up"
    DRIFT_DOWN = "drift_down"


def calculate_price_change(current: float, previous: float) -> float:
    """計算價格變化百分比"""
    if previous <= 0:
        return 0.0
    return (current - previous) / previous


def load_kronos(model_path: str = "models/kronos-base"):
    """載入 Kronos 模型（stub - 需要完整 torch 模型才能用）"""
    raise NotImplementedError(
        "完整 Kronos 模型載入需要 torch + transformers + 模型權重。"
        "目前使用 MonteCarloEngine 作為替代。"
    )


class MonteCarloEngine:
    """
    Monte Carlo 模擬預測引擎
    基於歷史價格波動率模擬未來價格路徑
    """

    def predict(self, df, config: dict) -> PredictionResult:
        """
        對 DataFrame 進行預測
        df 需有 'close' 欄位
        回傳 PredictionResult
        """
        closes = df['close'].dropna().values
        if len(closes) < 5:
            return PredictionResult(benchmark=float(closes[-1]) if len(closes) > 0 else 0.0,
                                    confidence=0.0)

        # 計算日報酬率
        returns = np.diff(closes) / closes[:-1]
        if len(returns) < 2:
            return PredictionResult(benchmark=float(closes[-1]), confidence=0.0)

        current_price = float(closes[-1])
        mu = np.mean(returns)
        sigma = np.std(returns)

        n_sim = config.get("mc_simulations", 200)
        n_days = config.get("pred_days", 5)

        # Monte Carlo 模擬
        simulations = np.zeros((n_sim, n_days))
        for i in range(n_sim):
            prices = [current_price]
            for _ in range(n_days):
                r = np.random.normal(mu, sigma)
                prices.append(prices[-1] * (1 + r))
            simulations[i] = prices[1:]

        # 預測基準 = 模擬最終價格的中位數
        final_prices = simulations[:, -1]
        benchmark = float(np.median(final_prices))

        # 信心度 = 預測方向的共識比例
        if benchmark > current_price:
            confidence = float(np.mean(final_prices > current_price))
        else:
            confidence = float(np.mean(final_prices < current_price))

        drift = (benchmark - current_price) / current_price

        return PredictionResult(
            benchmark=round(benchmark, 2),
            confidence=round(confidence, 4),
            drift=round(drift, 4),
        )


class PredictionEngine:
    """預測引擎 wrapper"""

    def __init__(self, config: dict = None):
        self.config = DEFAULT_CONFIG.copy()
        if config:
            self.config.update(config)
        self.mc_engine = MonteCarloEngine()


class KronosRealEngine:
    """完整 Kronos 預測引擎（需要模型權重）"""

    def __init__(self, model_path: str = "models/kronos-base"):
        self.model_path = model_path
        raise NotImplementedError("KronosRealEngine 需要完整模型權重")


class DriftMonitor:
    """預測漂移監測"""

    def __init__(self):
        self.history = []


class PlotBar:
    """Kronos 圖表資料"""

    def __init__(self):
        pass


class PredictionChartRenderer:
    """預測圖表繪製"""

    def __init__(self):
        pass
