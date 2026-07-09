#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
kronos_engine.py - Kronos 預測引擎
優先使用 KronosRealEngine（真實模型），失敗時 fallback 到 MonteCarloEngine
"""

import contextlib
import io
import logging
import os
import sys
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# 單例快取：避免重複載入 390MB 模型
_kronos_engine_singleton: Optional["KronosRealEngine"] = None


# 預設預測配置
DEFAULT_CONFIG = {
    "context_len": 512,
    "pred_days": 5,
    "mc_simulations": 200,
    "confidence_threshold": 0.55,
    "volatility_lookback": 20,
    "min_volume": 500,
    "results": None,
    "kronos_model_path": "models/kronos-base",
    "kronos_tokenizer_path": "models/kronos-tokenizer-base",
}


@dataclass
class PredictionResult:
    """單筆預測結果"""

    benchmark: float = 0.0
    confidence: float = 0.0
    drift: float = 0.0
    pred_series: Optional[list] = None  # Kronos 多日預測序列


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


def _resolve_model_path(path: str) -> Optional[str]:
    """解析模型路徑：絕對路徑 > 相對於專案根目錄 > None"""
    if os.path.isdir(path):
        return path
    # 嘗試相對於專案根目錄（strategy/ 往上一層 = twse/）
    strategy_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(strategy_dir)  # twstock/
    # 先試 twstock/models/...
    alt = os.path.join(project_root, path)
    if os.path.isdir(alt):
        return alt
    # 再試 twse/models/...（專案根目錄上一層）
    alt2 = os.path.join(os.path.dirname(project_root), path)
    if os.path.isdir(alt2):
        return alt2
    return None


def _find_kronos_model_src() -> Optional[str]:
    """
    尋找 Kronos 原始碼 model/ 目錄。
    搜尋順序：專案根目錄 (twse/model/) > twstock/model/ > strategy/model/
    """
    strategy_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(strategy_dir, "..", "..", "model"),  # twse/model/
        os.path.join(strategy_dir, "..", "model"),  # twstock/model/
        os.path.join(strategy_dir, "model"),  # strategy/model/
    ]
    for c in candidates:
        c = os.path.normpath(c)
        if os.path.isfile(os.path.join(c, "kronos.py")):
            return c
    return None


def load_kronos(
    model_path: str = "models/kronos-base", tokenizer_path: str = "models/kronos-tokenizer-base"
):
    """
    載入 Kronos 模型與 tokenizer。
    回傳 (tokenizer, model, predictor) 或 raise ImportError。
    """
    model_src = _find_kronos_model_src()
    if model_src and model_src not in sys.path:
        sys.path.insert(0, model_src)

    resolved_model = _resolve_model_path(model_path)
    resolved_tokenizer = _resolve_model_path(tokenizer_path)
    if not resolved_model or not resolved_tokenizer:
        raise FileNotFoundError(
            f"Kronos 模型路徑不存在: model={resolved_model}, tokenizer={resolved_tokenizer}"
        )

    # 加入 model/ 所在目錄，讓 'import model' 能解析 Kronos 原始碼
    if model_src:
        parent = os.path.dirname(model_src)
        if parent not in sys.path:
            sys.path.insert(0, parent)
    from model import Kronos, KronosPredictor, KronosTokenizer

    tokenizer = KronosTokenizer.from_pretrained(resolved_tokenizer)
    model = Kronos.from_pretrained(resolved_model)
    predictor = KronosPredictor(model, tokenizer, device="cpu", max_context=512)
    return tokenizer, model, predictor


class KronosRealEngine:
    """
    完整 Kronos 預測引擎
    使用 NeoQuasar/Kronos-base 模型進行 5 日 OHLCV 預測
    """

    def __init__(
        self,
        model_path: str = "models/kronos-base",
        tokenizer_path: str = "models/kronos-tokenizer-base",
    ):
        self.model_path = model_path
        self.tokenizer_path = tokenizer_path
        self._predictor = None
        self._load_error: Exception | None = None

    def _ensure_loaded(self):
        """延遲載入，只載入一次（單例）"""
        if self._predictor is not None or self._load_error is not None:
            return
        global _kronos_engine_singleton
        if _kronos_engine_singleton is not None:
            # 複用已載入的單例
            self._predictor = _kronos_engine_singleton._predictor
            self._load_error = _kronos_engine_singleton._load_error
            return
        try:
            # 抑制 HuggingFace from_pretrained 的 "Loading weights..." stdout
            with contextlib.redirect_stdout(io.StringIO()):
                _, _, self._predictor = load_kronos(self.model_path, self.tokenizer_path)
            _kronos_engine_singleton = self
            logger.info(
                "KronosRealEngine loaded: model=%s tokenizer=%s",
                self.model_path,
                self.tokenizer_path,
            )
        except Exception as e:
            self._load_error = e
            logger.warning(
                "KronosRealEngine failed to load: %s: %s",
                type(e).__name__,
                e,
            )

    @property
    def ready(self) -> bool:
        self._ensure_loaded()
        if self._predictor is None:
            logger.info(
                "KronosRealEngine not ready (will fallback to MonteCarlo): %s",
                self._load_error,
            )
        return self._predictor is not None

    def predict(self, df: pd.DataFrame, config: dict) -> PredictionResult:
        """
        對 df 進行預測。
        df 需有 open/high/low/close/volume/amount 欄位（或至少 close）。
        回傳 PredictionResult，benchmark = 第 pred_days 日預測 close。
        """
        if not self.ready:
            raise RuntimeError(f"Kronos 模型未載入: {self._load_error}")

        pred_days = config.get("pred_days", 5)
        work = df.copy()

        # 確保必要欄位存在
        for col in ["open", "high", "low", "close"]:
            if col not in work.columns:
                work[col] = work["close"]
        if "volume" not in work.columns:
            work["volume"] = 0.0
        if "amount" not in work.columns:
            work["amount"] = work["volume"] * work["close"]

        # 移除 NaN
        work = work.dropna(subset=["close"])
        if len(work) < 10:
            return PredictionResult(
                benchmark=float(work["close"].iloc[-1]) if len(work) > 0 else 0.0,
                confidence=0.0,
            )

        # 準備 Kronos 需要的格式
        x_df = work[["open", "high", "low", "close", "volume", "amount"]]
        x_timestamp = pd.Series(work.index, name="timestamps")
        if not isinstance(x_timestamp.dtype, type(pd.to_datetime([]).dtype)):
            # 如果 index 不是 datetime，用整數模擬
            x_timestamp = pd.Series(pd.RangeIndex(len(work)), name="timestamps")

        # 產生未來 pred_days 個預測日（用日曆日）
        last_ts = work.index[-1]
        if isinstance(last_ts, pd.Timestamp) or hasattr(last_ts, "freq"):
            future_index = pd.date_range(
                start=pd.Timestamp(last_ts) + pd.Timedelta(days=1),
                periods=pred_days,
                freq="D",
            )
        else:
            future_index = pd.RangeIndex(len(work), len(work) + pred_days)
        y_timestamp = pd.Series(future_index, name="timestamps")

        if self._predictor is None:
            raise RuntimeError(
                f"Kronos model unexpectedly None after ready=True: {self._load_error}"
            )

        pred = self._predictor.predict(
            df=x_df,
            x_timestamp=x_timestamp,
            y_timestamp=y_timestamp,
            pred_len=pred_days,
            T=1.0,
            top_p=0.9,
            sample_count=1,
            verbose=False,
        )

        pred_closes = pred["close"].values.astype(float).tolist()
        benchmark = pred_closes[-1] if pred_closes else float(work["close"].iloc[-1])
        current = float(work["close"].iloc[-1])
        drift = (benchmark - current) / current if current > 0 else 0.0

        # 信心度：預測方向的樣本一致性（以 drift 方向為主）
        if drift > 0:
            confidence = float(np.mean(np.array(pred_closes) > current))
        elif drift < 0:
            confidence = float(np.mean(np.array(pred_closes) < current))
        else:
            confidence = 0.5

        return PredictionResult(
            benchmark=round(benchmark, 2),
            confidence=round(confidence, 4),
            drift=round(drift, 4),
            pred_series=[round(x, 2) for x in pred_closes],
        )


class MonteCarloEngine:
    """
    Monte Carlo 模擬預測引擎
    基於歷史價格波動率模擬未來價格路徑（fallback 用）
    """

    def predict(self, df, config: dict) -> PredictionResult:
        """
        對 DataFrame 進行預測
        df 需有 'close' 欄位
        回傳 PredictionResult
        """
        closes = df["close"].dropna().values
        if len(closes) < 5:
            return PredictionResult(
                benchmark=float(closes[-1]) if len(closes) > 0 else 0.0, confidence=0.0
            )

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
            # prices 用 explicit Python list comprehension 產生，不要用 .append() 避免 pyright 推成 NDArray
            r_seq = np.random.normal(mu, sigma, size=n_days)
            sim_prices = [current_price]
            for r in r_seq:
                sim_prices.append(sim_prices[-1] * (1 + float(r)))
            simulations[i] = sim_prices[1:]  # type: ignore[assignment]

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
    """預測引擎 wrapper：優先 Kronos，fallback Monte Carlo"""

    def __init__(self, config: Optional[dict] = None):
        self.config = DEFAULT_CONFIG.copy()
        if config:
            self.config.update(config)
        self.mc_engine = MonteCarloEngine()
        self.kronos_engine = None
        try:
            model_path_raw = self.config.get("kronos_model_path") or "models/kronos-base"
            tokenizer_path_raw = (
                self.config.get("kronos_tokenizer_path") or "models/kronos-tokenizer-base"
            )
            # `DEFAULT_CONFIG` is typed dict[str, object]; coerce to str with an explicit
            # check so callers passing non-str (e.g. via CLI) fail with a clear error
            # instead of silently corrupting the HF from_pretrained path.
            if not isinstance(model_path_raw, str):
                raise TypeError(
                    f"kronos_model_path must be str, got {type(model_path_raw).__name__}"
                )
            if not isinstance(tokenizer_path_raw, str):
                raise TypeError(
                    f"kronos_tokenizer_path must be str, got {type(tokenizer_path_raw).__name__}"
                )
            self.kronos_engine = KronosRealEngine(
                model_path=model_path_raw,
                tokenizer_path=tokenizer_path_raw,
            )
        except Exception as e:
            logger.warning(
                "PredictionEngine: KronosRealEngine init failed: %s: %s", type(e).__name__, e
            )

    def predict(self, df, config: Optional[dict] = None) -> PredictionResult:
        cfg = config or self.config
        if self.kronos_engine and self.kronos_engine.ready:
            try:
                return self.kronos_engine.predict(df, cfg)
            except Exception as e:
                logger.warning(
                    "PredictionEngine: KronosRealEngine predict failed, fallback MonteCarlo: %s: %s",
                    type(e).__name__,
                    e,
                )
        elif self.kronos_engine is not None and not self.kronos_engine.ready:
            logger.info(
                "PredictionEngine: KronosRealEngine not ready (load_error=%s), using MonteCarlo",
                self.kronos_engine._load_error,
            )
        return self.mc_engine.predict(df, cfg)


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
