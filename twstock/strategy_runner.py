#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
策略模組統一輸出器 - 完整輸出五大策略分析
用法: python strategy_runner.py <stock_id>
輸出格式與 D:\twse\twstock\strategy\ 一致

設計原則：
- strategy_runner 只是 dispatcher，不包含策略演算法
- 所有策略計算 dispatch 到 strategy/ 子模組
- 輸出透過 OutputWriter 抽象層，預設 ConsoleWriter，可注入 JsonWriter
"""

import sys
from pathlib import Path
from typing import Optional

# ``strategy_runner.py`` is a supported direct entry point.  Running it from
# the repository root puts that directory, rather than its parent, on
# ``sys.path``.  Bootstrap the package parent before every ``twstock`` import.
# Do not add the package directory itself: that would permit duplicate
# top-level modules such as ``db`` and split module state.
_PROJECT_ROOT = Path(__file__).resolve().parent
_PACKAGE_PARENT = str(_PROJECT_ROOT.parent)
if _PACKAGE_PARENT not in sys.path:
    sys.path.insert(0, _PACKAGE_PARENT)

from twstock.ui.output_writer import ConsoleWriter, JsonWriter
from twstock.strategy.result_contract import normalize_strategy_result

# Windows encoding fix — 只在直接執行時才替換 stdout/stderr
if sys.platform == "win32" and __name__ == "__main__":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── 策略匯入（模組層級，可被 monkeypatch 替換）──────────────
from twstock.strategy.chips_strategy import ChipsStrategy
from twstock.strategy.ma_strategy import MAStrategy
from twstock.strategy.patterns_strategy import PatternStrategy
from twstock.strategy.sr_analyzer import SupportResistanceStrategy

# ── Dispatcher API ──────────────────────────────────────────


class _PredictionAdapter:
    """SQLite historical-momentum heuristic, explicitly not an AI model.

    The previous adapter produced a fixed +0.5%/-0.5% trajectory based on an
    MA field that the MA strategy never returned.  This preserves the public
    prediction entry while making the estimate data-driven and transparent.
    """

    def analyze(self, stock_id: str, ma: Optional[dict] = None) -> dict:
        from twstock.db import get_connection
        from twstock.strategy._utils import fetch_klines

        conn = get_connection(readonly=True)
        try:
            df = fetch_klines(conn, stock_id, limit=30)
            if df is None or df.empty or len(df) < 5:
                return normalize_strategy_result(
                    {
                        "error": "資料不足",
                        "summary": "至少需要 5 個交易日才能產生歷史動能估計。",
                    },
                    strategy="prediction",
                    stock_id=stock_id,
                )

            closes = df["close"].sort_index().tolist()
            last_close = closes[-1]
            returns = [(closes[i] / closes[i - 1] - 1) * 100 for i in range(1, len(closes))]
            avg_return = sum(returns) / len(returns) if returns else 0
            volatility = (
                (sum(r**2 for r in returns) / len(returns) - avg_return**2) ** 0.5 if returns else 1
            )

            # Blend the full lookback mean with a short trend.  The result is
            # bounded to avoid an isolated data error producing an absurd
            # projection.  It is intentionally a heuristic, not a model.
            lookback = min(6, len(closes))
            short_daily_return = ((closes[-1] / closes[-lookback]) - 1) * 100 / (lookback - 1)
            daily_return = max(-3.0, min(3.0, 0.6 * avg_return + 0.4 * short_daily_return))

            predictions = []
            for i in range(1, 6):
                pct = ((1 + daily_return / 100) ** i - 1) * 100
                predictions.append(
                    {
                        "day": f"T+{i}",
                        "price": round(last_close * (1 + pct / 100), 2),
                        "pct": round(pct, 2),
                    }
                )

            signal = "bullish" if daily_return > 0.05 else "bearish" if daily_return < -0.05 else "neutral"
            return normalize_strategy_result(
                {
                    "strategy": "prediction",
                    "stock_id": stock_id,
                    "signal": signal,
                    "confidence": max(0, min(100, round(100 - volatility * 12))),
                    "summary": "Historical-momentum heuristic; not an AI or Kronos prediction.",
                    "predictions": predictions,
                    "model": "historical_momentum_heuristic",
                    "is_model_prediction": False,
                    "volatility": round(volatility, 2),
                    "avgReturn": round(avg_return, 2),
                    "dailyReturnEstimate": round(daily_return, 3),
                    # Accepted for backwards compatibility but deliberately
                    # not used as a hidden pseudo-model input.
                    "ma_input_ignored": ma is not None,
                }
            )
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


# ── Named dispatchers (thin wrappers for main()) ────────────


def run_sr_analysis(stock_id: str) -> dict:
    """執行撐壓分析 - dispatch 到 sr_analyzer"""
    return SupportResistanceStrategy().analyze(stock_id)


def run_ma_analysis(stock_id: str) -> dict:
    """執行均線分析 - dispatch 到 ma_strategy"""
    return MAStrategy().analyze(stock_id)


def run_chips_analysis(stock_id: str) -> dict:
    """執行籌碼分析 - dispatch 到 chips_strategy"""
    return ChipsStrategy().analyze(stock_id)


def run_pattern_analysis(stock_id: str) -> dict:
    """執行型態分析 - dispatch 到 patterns_strategy"""
    return PatternStrategy().analyze(stock_id)


def run_prediction_analysis(stock_id: str, ma: Optional[dict] = None) -> dict:
    """執行預測分析 - dispatch 到內部適配器"""
    return _PredictionAdapter().analyze(stock_id, ma=ma)


# ── Main ────────────────────────────────────────────────────


def main(writer=None):
    """執行所有策略分析並透過 writer 輸出。

    Args:
        writer: OutputWriter 實例。預設 ConsoleWriter（人類可讀）。
                傳入 JsonWriter() 可輸出 JSON 格式。
    """
    if writer is None:
        writer = ConsoleWriter()

    if len(sys.argv) < 2:
        writer.write_error("用法: python strategy_runner.py <stock_id>")
        sys.exit(1)

    stock_id = sys.argv[1]

    try:
        sr = run_sr_analysis(stock_id)
        ma = run_ma_analysis(stock_id)
        chips = run_chips_analysis(stock_id)
        pattern = run_pattern_analysis(stock_id)
        prediction = run_prediction_analysis(stock_id, ma=ma)

        def _with_source(raw: dict, strategy_name: str, source: str) -> dict:
            normalized = normalize_strategy_result(raw, strategy=strategy_name, stock_id=stock_id)
            normalized["source"] = source
            return normalized

        # Keep legacy camelCase fields for existing callers, while emitting
        # the snake_case form expected by ConsoleWriter and the JSON contract.
        result = {
            "stock_id": stock_id,
            "stockId": stock_id,
            "data_source": "sqlite",
            "dataSource": "sqlite",
            "strategies": {
                "sr": _with_source(sr, "sr", "strategy/sr_analyzer.py"),
                "ma": _with_source(ma, "ma", "strategy/ma_strategy.py"),
                "chips": _with_source(chips, "chips", "strategy/chips_strategy.py"),
                "pattern": _with_source(pattern, "pattern", "strategy/patterns_strategy.py"),
                "prediction": _with_source(
                    prediction,
                    "prediction",
                    "strategy/strategy_runner.py",
                ),
            },
        }

        writer.write_result(result)
    except Exception as e:
        writer.write_error(str(e))
        sys.exit(1)


if __name__ == "__main__":
    # 偵測 --json 參數
    if "--json" in sys.argv:
        sys.argv.remove("--json")
        main(writer=JsonWriter())
    else:
        main()
