#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
策略模組統一輸出器 - 完整輸出五大策略分析
用法: python strategy_runner.py <stock_id>
輸出格式與 D:\twse\twstock\strategy\ 一致

設計原則：
- strategy_runner 只是 dispatcher，不包含策略演算法
- 所有策略計算 dispatch 到 strategy/ 子模組
"""
import sys
import os
import json

# Windows encoding fix — 只在直接執行時才替換 stdout/stderr
if sys.platform == "win32" and __name__ == "__main__":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if _CURRENT_DIR not in sys.path:
    sys.path.insert(0, _CURRENT_DIR)

# ── 策略匯入（模組層級，可被 monkeypatch 替換）──────────────
from strategy.chips_strategy import ChipsStrategy
from strategy.ma_strategy import MAStrategy
from strategy.patterns_strategy import PatternStrategy
from strategy.sr_analyzer import SupportResistanceStrategy


# ── Dispatcher API ──────────────────────────────────────────

class _PredictionAdapter:
    """預測分析適配器 - 不使用 random，移除假邏輯。"""

    def analyze(self, stock_id: str, ma: dict = None) -> dict:
        from strategy._utils import fetch_klines
        from db import get_connection

        conn = get_connection()
        try:
            df = fetch_klines(conn, stock_id, limit=30)
            if df is None or df.empty or len(df) < 5:
                return {"error": "資料不足"}

            closes = df['close'].sort_index().tolist()
            last_close = closes[-1]
            is_up = ma.get("ma25Trend") == "up" if ma else False

            returns = [(closes[i] / closes[i-1] - 1) * 100 for i in range(1, len(closes))]
            avg_return = sum(returns) / len(returns) if returns else 0
            volatility = (sum(r**2 for r in returns) / len(returns) - avg_return**2) ** 0.5 if returns else 1

            predictions = []
            for i in range(1, 6):
                trend_component = 0.5 * i if is_up else -0.5 * i
                pct = trend_component
                predictions.append({
                    "day": f"T+{i}",
                    "price": round(last_close * (1 + pct / 100), 2),
                    "pct": round(pct, 2),
                })

            ai_score = 0.6 if is_up else 0.3

            return {
                "predictions": predictions,
                "aiStrength": "看多" if is_up else "看空",
                "aiScore": round(ai_score, 3),
                "volatility": round(volatility, 2),
                "avgReturn": round(avg_return, 2),
            }
        finally:
            conn.close()


class AIStrategy:
    """AI 預測策略 - 決定論版本，無 random。"""

    def analyze(self, stock_id: str, **kwargs) -> dict:
        return _PredictionAdapter().analyze(stock_id, **kwargs)


# 策略名稱 → 模組層級屬性名稱（monkeypatch 替換後能立即生效）
_STRATEGY_REGISTRY: dict[str, str] = {
    "chips": "ChipsStrategy",
    "ma": "MAStrategy",
    "pattern": "PatternStrategy",
    "sr": "SupportResistanceStrategy",
    "prediction": "_PredictionAdapter",
    "ai": "AIStrategy",
}


def get_strategy(strategy_name: str):
    """取得策略實例。動態查找模組屬性，使 monkeypatch 能生效。"""
    attr_name = _STRATEGY_REGISTRY.get(strategy_name)
    if attr_name is None:
        raise ValueError(f"Unknown strategy: {strategy_name}")
    cls = getattr(sys.modules[__name__], attr_name)
    return cls()


def run_strategy(strategy_name: str, stock_id: str, **kwargs) -> dict:
    """執行指定策略並回傳結果。"""
    strategy = get_strategy(strategy_name)
    result = strategy.analyze(stock_id, **kwargs)

    if result is None:
        return {
            "strategy": strategy_name,
            "stock_id": stock_id,
            "status": "no_result",
        }

    if isinstance(result, dict):
        return result

    return {
        "strategy": strategy_name,
        "stock_id": stock_id,
        "status": "ok",
        "result": result,
    }


# ── 撐壓分析 (S/R) ─────────────────────────────────────────

def run_sr_analysis(stock_id: str) -> dict:
    """執行撐壓分析 - dispatch 到 sr_analyzer"""
    from strategy.sr_analyzer import SupportResistanceStrategy

    return SupportResistanceStrategy().analyze(stock_id)


# ── 均線分析 ────────────────────────────────────────────────

def run_ma_analysis(stock_id: str) -> dict:
    """執行均線分析 - dispatch 到 ma_strategy"""
    from strategy.ma_strategy import MAStrategy

    return MAStrategy().analyze(stock_id)


# ── 籌碼分析 ────────────────────────────────────────────────

def run_chips_analysis(stock_id: str) -> dict:
    """執行籌碼分析 - dispatch 到 chips_strategy"""
    from strategy.chips_strategy import ChipsStrategy

    return ChipsStrategy().analyze(stock_id)


# ── 型態分析 ────────────────────────────────────────────────

def run_pattern_analysis(stock_id: str) -> dict:
    """執行型態分析 - dispatch 到 patterns_strategy"""
    from strategy.patterns_strategy import PatternStrategy

    return PatternStrategy().analyze(stock_id)


# ── 預測分析 ────────────────────────────────────────────────

def run_prediction_analysis(stock_id: str, ma: dict = None) -> dict:
    """執行預測分析 - dispatch 到內部適配器"""
    return _PredictionAdapter().analyze(stock_id, ma=ma)


# ── Main ────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "用法: python strategy_runner.py <stock_id>"}, ensure_ascii=False))
        sys.exit(1)

    stock_id = sys.argv[1]

    sr = run_sr_analysis(stock_id)
    ma = run_ma_analysis(stock_id)
    chips = run_chips_analysis(stock_id)
    pattern = run_pattern_analysis(stock_id)
    prediction = run_prediction_analysis(stock_id, ma=ma)

    result = {
        "stockId": stock_id,
        "dataSource": "sqlite",
        "strategies": {
            "sr": {**sr, "source": "strategy/sr_analyzer.py"},
            "ma": {**ma, "source": "strategy/ma_strategy.py"},
            "chips": {**chips, "source": "strategy/chips_strategy.py"},
            "pattern": {**pattern, "source": "strategy/patterns_strategy.py"},
            "prediction": {**prediction, "source": "strategy/strategy_runner.py"},
        }
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
