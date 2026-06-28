#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
strategy/kronos_engine.py - Shared Kronos AI & Monte Carlo prediction engine [AI MOD]
Eliminates code duplication between prediction_strategy.py and patterns_strategy.py.
"""

import os
import sys
import shutil
import time
import sqlite3
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, NamedTuple, Any
from display import price_color, vol_color  # [AI MOD]
from dataclasses import dataclass
from abc import ABC, abstractmethod
from rich.progress import (
    Progress, SpinnerColumn, TextColumn,
    BarColumn, TaskProgressColumn,
)

# [AI MOD] 集中式 Console：解決 Windows cp950 無法渲染 emoji 的問題
from terminal import rconsole

DEFAULT_CONFIG = {
    "MODEL_ID": "NeoQuasar/Kronos-base",
    "TOKENIZER_ID": "NeoQuasar/Kronos-Tokenizer-base",
    "MAX_CONTEXT": 512,
    "PRED_LEN": 5,
    "DRIFT": {
        "COLD_START": 3,
        "EMA_ALPHA": 0.3,
        "CONSEC_THRESHOLD_L2": 4,
    },
    "SIMULATION": {
        "PATHS": 100,
        "MIN_RETURNS": 10,
    },
}

_kronos_pipeline = None
_kronos_import_attempted = False

# Resolve paths
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_TWSTOCK_DIR = os.path.abspath(os.path.join(_CURRENT_DIR, ".."))
_KRONOS_DIR = os.path.abspath(os.path.join(_TWSTOCK_DIR, "../kronos"))


def _ensure_kronos_path():
    """Ensure the Kronos Python package directory is on ``sys.path``.

    The repository ships model weights under ``d:/twse/kronos/`` but the
    *Python* source code (``model.py``, ``__init__.py``, ...) lives in the
    GitHub repository and is **not** bundled with the weights.  If the user
    has already cloned the GitHub repo somewhere (e.g. ``d:/kronos``) or
    installed the package via ``pip``, we pick it up here.  Otherwise we
    fall back to the standard auto-install path below.
    """
    # 1. Already on sys.path?  (covers pip-installed or manual clone)
    for p in sys.path:
        if not p:
            continue
        if os.path.isfile(os.path.join(p, "model.py")):
            return True
        if os.path.isfile(os.path.join(p, "kronos", "model.py")):
            return True

    # 2. Common sibling clone location: d:/kronos
    _repo_clone = os.path.abspath(os.path.join(_TWSTOCK_DIR, "..", "kronos"))
    if os.path.isfile(os.path.join(_repo_clone, "model.py")):
        if _repo_clone not in sys.path:
            sys.path.insert(0, _repo_clone)
        return True

    # 3. d:/twse/kronos itself (only if it actually contains model.py)
    if os.path.isfile(os.path.join(_KRONOS_DIR, "model.py")):
        if _KRONOS_DIR not in sys.path:
            sys.path.insert(0, _KRONOS_DIR)
        return True

    return False


def _patch_tqdm():
    import tqdm
    class _Bar:
        def __init__(self, iterable, total=None, **_):
            self._iter = iterable
            self._total = total or (len(iterable) if hasattr(iterable, '__len__') else 1)

        def __iter__(self):
            with Progress(
                TextColumn("[bold cyan]🤖 AI 推論進度:[/]"),
                BarColumn(), TaskProgressColumn(), transient=True,
            ) as prog:
                task = prog.add_task("infer", total=self._total)
                for i, item in enumerate(self._iter):
                    prog.update(task, completed=i)
                    yield item
                prog.update(task, completed=self._total)

    tqdm.trange = lambda *a, **kw: _Bar(range(*a), **kw)
    tqdm.tqdm = lambda *a, **kw: _Bar(a[0] if a else range(1), **kw)


def _install_kronos_package():
    """從 GitHub 安裝 Kronos Python 套件（如果尚未安裝）

    ⚠️  ``d:/twse/kronos/`` 目錄只包含從 HuggingFace Hub 下載的
    預訓練權重（``model.safetensors`` + ``config.json``），**不含
    Python 原始碼**（``model.py``、``__init__.py``）。因此 ``from model
    import Kronos`` 一定會失敗，必須先安裝 ``shiyu-coder/Kronos``
    倉庫才能取得 Python 套件。
    """
    global _kronos_import_attempted
    if _kronos_import_attempted:
        # 曾經試過且失敗，直接跳過以免重複 pip install
        return False
    _kronos_import_attempted = True

    # 先檢查是否已經可以匯入
    try:
        import model  # noqa: F401
        return True
    except ImportError:
        pass

    import subprocess
    rconsole.print("[bold yellow]📦 正在從 GitHub 安裝 Kronos 套件...[/]")
    rconsole.print("[dim]  注意：d:/twse/kronos 只含權重，不含 Python 原始碼[/]")
    rconsole.print("[dim]  需要從 GitHub 取得 model.py + kronos/__init__.py[/]")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "git+https://github.com/shiyu-coder/Kronos.git"],
            check=True,
            capture_output=True,
            text=True,
        )
        rconsole.print("[bold green]✅ Kronos 套件安裝成功[/]")
        # 安裝後重新檢查路徑
        _ensure_kronos_path()
        return True
    except Exception as e:
        rconsole.print(f"[red]⚠️ Kronos 套件安裝失敗: {e}[/]")
        rconsole.print("[dim]請手動執行:[/dim]")
        rconsole.print("[dim]  pip install git+https://github.com/shiyu-coder/Kronos.git[/dim]")
        rconsole.print("[dim]或 clone 後加入 PYTHONPATH:[/dim]")
        rconsole.print("[dim]  git clone https://github.com/shiyu-coder/Kronos.git d:/kronos[/dim]")
        rconsole.print("[dim]  set PYTHONPATH=d:/kronos[/dim]")
        return False


def load_kronos():
    global _kronos_pipeline
    if _kronos_pipeline is not None:
        return _kronos_pipeline

    try:
        _patch_tqdm()

        # 先確保 Python 套件的路徑正確
        _ensure_kronos_path()

        # 確保 Kronos 套件已安裝（含 Python 原始碼）
        if not _install_kronos_package():
            _kronos_pipeline = "SIMULATION"
            return _kronos_pipeline

        # 再次確認路徑（pip install 後可能有新位置）
        _ensure_kronos_path()

        try:
            from model import Kronos, KronosTokenizer, KronosPredictor
        except ImportError as ie:
            # 給出明確的診斷訊息
            rconsole.print(f"[red]❌ 無法匯入 Kronos Python 模組: {ie}[/red]")
            rconsole.print("[dim]  d:/twse/kronos 目錄只含權重檔（model.safetensors + config.json）[/dim]")
            rconsole.print("[dim]  但 Kronos Python 套件（model.py + kronos/）必須從 GitHub 安裝:[/dim]")
            rconsole.print("[dim]    pip install git+https://github.com/shiyu-coder/Kronos.git[/dim]")
            _kronos_pipeline = "SIMULATION"
            return _kronos_pipeline

        import torch
        import logging
        logging.getLogger("huggingface_hub").setLevel(logging.ERROR)

        # 驗證本地模型檔案存在
        local_base = os.path.join(_KRONOS_DIR, "base")
        local_tok = os.path.join(_KRONOS_DIR, "tokenizer")
        if not os.path.isfile(os.path.join(local_base, "model.safetensors")):
            rconsole.print(f"[red]❌ 模型權重遺失: {local_base}/model.safetensors 不存在[/red]")
            rconsole.print("[dim]  請執行以下指令重新下載:[/dim]")
            rconsole.print("[dim]    huggingface-cli download NeoQuasar/Kronos-base --local-dir d:/twse/kronos/base[/dim]")
            _kronos_pipeline = "SIMULATION"
            return _kronos_pipeline
        if not os.path.isfile(os.path.join(local_tok, "model.safetensors")):
            rconsole.print(f"[red]❌ tokenizer 權重遺失: {local_tok}/model.safetensors 不存在[/red]")
            rconsole.print("[dim]  請執行以下指令重新下載:[/dim]")
            rconsole.print("[dim]    huggingface-cli download NeoQuasar/Kronos-Tokenizer-base --local-dir d:/twse/kronos/tokenizer[/dim]")
            _kronos_pipeline = "SIMULATION"
            return _kronos_pipeline

        # 優先從 api_config 讀取模型 ID（支援 api.env 覆蓋）
        try:
            from api_config import get_kronos_model_id, get_kronos_tokenizer_id
            model_id = get_kronos_model_id()
            tokenizer_id = get_kronos_tokenizer_id()
        except Exception:
            model_id = DEFAULT_CONFIG["MODEL_ID"]
            tokenizer_id = DEFAULT_CONFIG["TOKENIZER_ID"]

        # 先嘗試本地路徑，再退回 HuggingFace Hub
        local_base = os.path.join(_KRONOS_DIR, "base")
        local_tok = os.path.join(_KRONOS_DIR, "tokenizer")
        model_path = local_base if os.path.isdir(local_base) else model_id
        tokenizer_path = local_tok if os.path.isdir(local_tok) else tokenizer_id

        rconsole.print(f"[bold yellow]📥 正在載入 Kronos 模型權重...[/]")
        rconsole.print(f"  模型: {model_path}")
        rconsole.print(f"  tokenizer: {tokenizer_path}")

        tokenizer = KronosTokenizer.from_pretrained(tokenizer_path)
        model = Kronos.from_pretrained(model_path)

        device = "cuda:0" if torch.cuda.is_available() else "cpu"
        rconsole.print(f"[bold cyan]🤖 Kronos 運算裝置: {device}[/]")

        _kronos_pipeline = KronosPredictor(
            model, tokenizer, device=device,
            max_context=DEFAULT_CONFIG["MAX_CONTEXT"],
        )
        return _kronos_pipeline

    except Exception as e:
        rconsole.print(f"[red]❌ 模型載入失敗，退回模擬模式: {e}[/red]")
        rconsole.print("[dim]💡 解決方案:[/dim]")
        rconsole.print("[dim]  1. 手動安裝: pip install git+https://github.com/shiyu-coder/kronos.git[/dim]")
        rconsole.print("[dim]  2. 或設定環境變數: KRONOS_MODEL_PATH=/path/to/kronos-base[/dim]")
        _kronos_pipeline = "SIMULATION"
        return _kronos_pipeline


class PredictionResult(NamedTuple):
    benchmark: float
    paths: np.ndarray
    confidence: float
    volatility: float


class DriftStatus(NamedTuple):
    status: str
    color: str
    correction: float
    bias_ema: float


@dataclass
class StockPrediction:
    code: str
    name: str
    current_price: float
    volume: int
    amount: float
    score: float
    target_price: float
    confidence: float = 0.0
    prev_price: float = None      # [AI MOD]
    prev_volume: float = None     # [AI MOD]


def calculate_price_change(current: float, previous: float) -> Tuple[float, float]:
    if previous == 0:
        return 0.0, 0.0
    change = current - previous
    return change, (change / previous) * 100


class PredictionEngine(ABC):
    @abstractmethod
    def predict(self, df: pd.DataFrame, config: Dict) -> PredictionResult:
        pass


class KronosRealEngine(PredictionEngine):
    """真實 Kronos-base 預測引擎"""
    ANCHOR_WEIGHT = 0.25

    def predict(self, df: pd.DataFrame, config: Dict) -> PredictionResult:
        pipe = load_kronos()
        if pipe == "SIMULATION":
            return MonteCarloEngine().predict(df, config)
        try:
            return self._run_inference(pipe, df, config)
        except Exception as e:
            rconsole.print(f"[red]⚠️ Kronos 推論失敗: {e}[/red]")
            return MonteCarloEngine().predict(df, config)

    def _run_inference(self, pipe, df: pd.DataFrame, config: Dict) -> PredictionResult:
        pred_len = config["PRED_LEN"]
        df_pd = self._to_pandas(df)
        x_df, x_ts, y_ts = self._build_inputs(df_pd, pred_len)

        # ── [MOD] 增加取樣次數 ──
        SAMPLE_COUNT = 10
        pred_df = pipe.predict(
            df=x_df, x_timestamp=x_ts, y_timestamp=y_ts,
            pred_len=pred_len, T=1.0, top_p=0.9, sample_count=SAMPLE_COUNT,
        )

        # ── [MOD] 處理多樣本回傳，取中位數 ──
        if isinstance(pred_df, list):
            all_closes = np.array([pdf['close'].to_numpy() for pdf in pred_df])
            raw_path = np.median(all_closes, axis=0)
        else:
            raw_path = pred_df['close'].to_numpy()

        median_path = self._anchor_and_clamp(raw_path, df_pd)
        paths = self._simulate_paths(median_path, df_pd, config)

        return PredictionResult(
            benchmark=float(np.median(paths[:, -1])),
            paths=paths,
            confidence=0.85,
            volatility=self._daily_vol(df_pd),
        )

    @staticmethod
    def _to_pandas(df: pd.DataFrame):
        df_pd = df.copy()

        if 'date' in df_pd.columns:
            df_pd['timestamps'] = pd.to_datetime(df_pd['date'].astype(str).str.replace('-', ''), format='%Y%m%d')
        else:
            df_pd['timestamps'] = pd.date_range(end=pd.Timestamp.now(), periods=len(df_pd), freq='D')

        for col in ('volume', 'amount'):
            if col not in df_pd.columns:
                df_pd[col] = 0.0

        return df_pd.dropna(subset=['open', 'high', 'low', 'close', 'volume', 'amount', 'timestamps'])

    @staticmethod
    def _build_inputs(df_pd, pred_len: int):
        x_df = df_pd[['open', 'high', 'low', 'close', 'volume', 'amount']]
        x_ts = pd.Series(df_pd['timestamps']).reset_index(drop=True)
        y_ts = pd.Series(pd.date_range(
            start=x_ts.iloc[-1] + pd.Timedelta(days=1),
            periods=pred_len, freq='B',
        ))
        return x_df, x_ts, y_ts

    def _anchor_and_clamp(self, raw_prices: np.ndarray, df_pd) -> np.ndarray:
        last_close = float(df_pd['close'].iloc[-1])
        recent_ret = df_pd['close'].pct_change().dropna().to_numpy()
        daily_vol = float(np.std(recent_ret)) if len(recent_ret) > 5 else 0.02
        daily_vol = daily_vol if not np.isnan(daily_vol) else 0.02
        limit = min(max(daily_vol * 1.5, 0.01), 0.10)

        result = np.empty_like(raw_prices)
        prev = last_close
        for i, raw in enumerate(raw_prices):
            blended = float(raw) * (1 - self.ANCHOR_WEIGHT) + last_close * self.ANCHOR_WEIGHT
            clamped = np.clip(blended, prev * (1 - limit), prev * (1 + limit))
            result[i] = clamped
            prev = clamped
        return result

    @staticmethod
    def _simulate_paths(median_path: np.ndarray, df_pd, config: Dict) -> np.ndarray:
        returns = df_pd['close'].pct_change().dropna().to_numpy()
        vol = returns.std() if len(returns) > 0 else 0.02
        vol = vol if not np.isnan(vol) else 0.02
        n, plen = config["SIMULATION"]["PATHS"], len(median_path)
        noise = np.random.normal(0, vol * 0.5, size=(n, plen))
        return median_path * (1 + noise)

    @staticmethod
    def _daily_vol(df_pd) -> float:
        returns = df_pd['close'].pct_change().dropna().to_numpy()
        vol = returns.std() if len(returns) > 0 else 0.02
        return vol if not np.isnan(vol) else 0.02


class MonteCarloEngine(PredictionEngine):
    """蒙特卡洛模擬預測引擎"""
    def predict(self, df: pd.DataFrame, config: Dict) -> PredictionResult:
        try:
            if len(df) < config["SIMULATION"]["MIN_RETURNS"]:
                raise ValueError("數據不足")

            last_close = df["close"].iloc[-1]
            if last_close is None:
                return PredictionResult(0.0, np.zeros((1, config["PRED_LEN"])), 0.0, 0.01)

            returns = df["close"].pct_change().dropna().to_numpy()
            vol = returns.std() if len(returns) > 0 else 0.01
            vol = vol if not np.isnan(vol) else 0.02

            pred_len = config["PRED_LEN"]
            num_paths = config["SIMULATION"]["PATHS"]

            shocks = np.random.normal(0, vol, (num_paths, pred_len))
            paths = last_close * np.cumprod(1 + shocks, axis=1)

            final = paths[:, -1]
            return PredictionResult(
                benchmark=float(np.median(final)),
                paths=paths,
                confidence=self._confidence(final),
                volatility=vol,
            )
        except Exception as e:
            rconsole.print(f"[red]⚠️ 蒙特卡洛計算錯誤: {e}[/]")
            return PredictionResult(0.0, np.zeros((1, config["PRED_LEN"])), 0.0, 0.01)

    @staticmethod
    def _confidence(final_prices: np.ndarray) -> float:
        if len(final_prices) < 2:
            return 0.0
        lower, upper = np.percentile(final_prices, [2.5, 97.5])
        median = np.median(final_prices)
        if median == 0:
            return 0.0
        return max(0.0, min(1.0, 1.0 - (upper - lower) / median))


class DriftMonitor:
    def __init__(self, config: Dict):
        dc = config["DRIFT"]
        self._alpha = dc["EMA_ALPHA"]
        self._cold_start = dc["COLD_START"]
        self._threshold = dc["CONSEC_THRESHOLD_L2"]
        self._bias_ema = 0.0
        self._count = 0
        self._streak = 0
        self._last_sign = 0

    def update(self, actual: float, predicted: float):
        self._count += 1
        if self._count < self._cold_start:
            return
        error = actual - predicted
        self._bias_ema = self._alpha * error + (1 - self._alpha) * self._bias_ema
        sign = 1 if error > 0 else -1
        self._streak = self._streak + 1 if sign == self._last_sign else 1
        self._last_sign = sign

    @property
    def status(self) -> DriftStatus:
        if self._count < self._cold_start:
            return DriftStatus("暖機中", "blue", 0.0, 0.0)
        if self._streak >= self._threshold:
            return DriftStatus("已校正", "orange3", self._bias_ema, self._bias_ema)
        return DriftStatus("穩定", "green", 0.0, self._bias_ema)


PlotBar = NamedTuple('PlotBar', [
    ('open', float), ('high', float), ('low', float),
    ('close', float), ('is_pred', bool),
])

_VOL_CHARS = "▁▂▃▄▅▆▇█"


class PredictionChartRenderer:
    """Precise ASCII K-line chart with volume and key-price annotations."""

    @staticmethod
    def render_ascii_chart(df: pd.DataFrame, predictions: np.ndarray,
                           correction: float = 0.0, hist_days: int = 25,
                           rows: int = 14, sr_lines: Dict = None) -> None:
        if df.empty:
            return
        try:
            term_width = shutil.get_terminal_size().columns
            df = df.sort_values("date")
            pred_len = len(predictions)

            actual_hist = min(hist_days, term_width - 14 - pred_len)
            if actual_hist < 5:
                actual_hist = 5
            if term_width < 45:
                rows = 8

            # ── Build historical bars + volumes ──
            bars: List[PlotBar] = []
            volumes: List[float] = []
            for _, row in df.tail(actual_hist).iterrows():
                bars.append(PlotBar(
                    float(row['open']), float(row['high']),
                    float(row['low']), float(row['close']), False))
                volumes.append(float(row.get('volume', 0) or 0))

            n_hist = len(bars)
            if not bars:
                return

            last_close = bars[-1].close

            # ── NaN guard on predictions ──
            clean_pred = np.array(predictions, dtype=float)
            mask = np.isnan(clean_pred) | np.isinf(clean_pred)
            if np.any(mask):
                clean_pred[mask] = last_close

            # ── Prediction bars (chain-linked) ──
            prev = last_close
            for p in clean_pred:
                v = float(p) + correction
                bars.append(PlotBar(prev, max(prev, v), min(prev, v), v, True))
                volumes.append(0.0)
                prev = v

            # ═══════════════════════════════════════════
            #  Price range: HISTORICAL BARS ONLY
            #  Prediction bars are clamped to this range
            # ═══════════════════════════════════════════
            hist_bars = bars[:n_hist]
            max_price = max(b.high for b in hist_bars)
            min_price = min(b.low for b in hist_bars)

            # 5% buffer above/below
            buffer = (max_price - min_price) * 0.05
            if buffer < 0.01:
                buffer = max_price * 0.02
            max_price += buffer
            min_price -= buffer
            price_range = max_price - min_price

            # Key price levels
            hist_high = max(b.high for b in hist_bars)
            hist_low = min(b.low for b in hist_bars)

            # ── SR lines extraction [AI MOD] ──
            if sr_lines is None:
                sr_lines = {}
            res_val = sr_lines.get('resistance')
            sup_val = sr_lines.get('support')

            # ── Header ──
            rconsole.print(
                f"\n[bold cyan]📊 預測熱圖 "
                f"[dim](左:{n_hist}d 歷史 │ 右:{pred_len}d 預測)[/dim][/]"
            )

            # ═══════════════════════════════════════════
            #  K-line section
            # ═══════════════════════════════════════════
            for r in range(rows, -1, -1):
                band_top = min_price + ((r + 1) / (rows + 1)) * price_range
                band_bot = min_price + (r / (rows + 1)) * price_range

                # ── Y-axis labels: only key prices ──
                is_close_row = band_bot <= last_close <= band_top
                is_res_row = res_val is not None and (band_bot <= res_val <= band_top)
                is_sup_row = sup_val is not None and (band_bot <= sup_val <= band_top)
                is_high_row = band_bot <= hist_high <= band_top
                is_low_row = band_bot <= hist_low <= band_top

                if is_close_row:
                    line = f"[bold bright_white]{last_close:8.2f}[/bold bright_white]╪"
                elif is_res_row:
                    line = f"[bright_green]{res_val:8.2f}[/bright_green]│"
                elif is_sup_row:
                    line = f"[bright_red]{sup_val:8.2f}[/bright_red]│"
                elif is_high_row:
                    line = f"[bright_red]{hist_high:8.2f}[/bright_red]┼"
                elif is_low_row:
                    line = f"[bright_green]{hist_low:8.2f}[/bright_green]┼"
                else:
                    line = f"[dim]{band_top:8.2f}[/dim]│"

                for i, b in enumerate(bars):
                    # ── History → Prediction separator ──
                    if i == n_hist:
                        line += "┊"

                    # ── Clamp: skip bars outside display range ──
                    if b.high < band_bot or b.low > band_top:
                        line += " "
                        continue

                    # ── Determine hits ──
                    body_lo = min(b.open, b.close)
                    body_hi = max(b.open, b.close)
                    hit_body = (body_lo <= band_top) and (body_hi >= band_bot)
                    hit_wick = (b.low <= band_top) and (b.high >= band_bot)

                    if b.is_pred:
                        # Prediction: solid block
                        if hit_body:
                            c = "bold cyan" if b.close >= b.open else "bold magenta"
                            line += f"[{c}]█[/]"
                        elif hit_wick:
                            line += "[dim cyan]│[/]"
                        else:
                            line += " "
                    else:
                        # Historical: candlestick
                        is_up = b.close >= b.open
                        if hit_body:
                            c = "bright_red" if is_up else "bright_green"
                            line += f"[{c}]┃[/]"
                        elif hit_wick:
                            c = "bright_red" if is_up else "bright_green"
                            line += f"[{c}]│[/]"
                        else:
                            line += " "

                # ── Append SR annotations [AI MOD] ──
                if is_res_row:
                    line += " [bright_green]──壓力─[/]"
                elif is_sup_row:
                    line += " [bright_red]──支撐─[/]"

                rconsole.print(line)

            # ── K-line axis ──
            k_axis = "         └"
            for i in range(len(bars)):
                k_axis += "┊" if i == n_hist else "─"
            rconsole.print(k_axis)

            # ═══════════════════════════════════════════
            #  Volume: single-row Unicode histogram
            # ═══════════════════════════════════════════
            hist_vols_clean = [v for v in volumes[:n_hist] if v > 0]
            if hist_vols_clean:
                max_vol = float(np.percentile(hist_vols_clean, 95))
                if max_vol <= 0:
                    max_vol = max(volumes[:n_hist]) if volumes[:n_hist] else 1
            else:
                max_vol = 1

            if max_vol > 0:
                max_vol_sheets = max_vol / 1000.0
                if max_vol_sheets >= 10000:
                    vl = f"{max_vol_sheets / 10000:.1f}萬"
                elif max_vol_sheets >= 1000:
                    vl = f"{max_vol_sheets / 1000:.1f}K"
                else:
                    vl = f"{max_vol_sheets:.0f}"

                vol_line = f"[dim]{vl:>8s}[/dim]│"
                for i, v in enumerate(volumes):
                    if i == n_hist:
                        vol_line += "┊"
                    if i >= n_hist:
                        vol_line += " "
                    elif v > 0:
                        level = min(int(v / max_vol * 8), 7)
                        # Volume color: compare with previous day
                        prev_v = volumes[i - 1] if i > 0 else 0
                        c = "bright_red" if v >= prev_v else "bright_green"
                        vol_line += f"[{c}]{_VOL_CHARS[level]}[/]"
                    else:
                        vol_line += "[dim]·[/]"
                rconsole.print(vol_line)

                v_axis = "         └"
                for i in range(len(bars)):
                    v_axis += "┊" if i == n_hist else "─"
                rconsole.print(v_axis)



            # ── Date labels ──
            dates = df["date"].tolist() if "date" in df.columns else []
            if dates:
                first_d = str(dates[-min(actual_hist, len(dates))])[-5:]
                last_d = str(dates[-1])[-5:]
                mid_pad = max(1, n_hist - len(first_d) - len(last_d))
                rconsole.print(
                    f"[dim]          {first_d}{'·' * mid_pad}{last_d}"
                    f"┊ T+1→T+{pred_len}[/dim]"
                )

        except Exception as e:
            rconsole.print(f"[red]⚠️ 圖表渲染錯誤: {e}[/]")