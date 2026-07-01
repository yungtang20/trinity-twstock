#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略整合_預測分析 v5.3 (統一資料庫版)
21 種型態 · Pivot 偵測 · 量價突破確認 · 5 日 Kronos 預測
# [AI MOD] Migrated to taiwan_stock_unified.db + klines view
"""
import os
import sys
import time
import shutil
import warnings
import signal
import sqlite3
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, NamedTuple
from contextlib import contextmanager

import numpy as np
import pandas as pd
from rich.table import Table
from rich.panel import Panel
from rich.progress import (
    Progress, SpinnerColumn, TextColumn,
    BarColumn, TimeElapsedColumn, TaskProgressColumn,
)
from rich import box

# [AI MOD] 集中式 Console：解決 Windows cp950 無法渲染 emoji 的問題
from terminal import rconsole

# [AI MOD] Pattern session scan cache to make switching sorting instantly fast
import time as _time_mod
_CACHE_TTL = 300  # 5 分鐘
_PATTERN_CACHE = {
    'date': None,
    'min_volume': None,
    'results': None,
    'ts': 0,
}

warnings.filterwarnings('ignore')

# ── Module path ───────────────────────────────────────────
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_TWSTOCK_DIR = os.path.abspath(os.path.join(_CURRENT_DIR, ".."))
if _TWSTOCK_DIR not in sys.path:
    sys.path.insert(0, _TWSTOCK_DIR)

from db import get_connection, DB_PATH  # [AI MOD]
from strategy._utils import clear_screen, get_stock_name, render_header, fetch_klines
from strategy.chips_strategy import _fetch_klines  # [AI MOD]
from display import price_color, chg_color, vol_fmt, price_rich, vol_color  # [AI MOD]

# ══════════════════════════════════════════════════════════
#  Imports & Config from shared engine [AI MOD]
# ══════════════════════════════════════════════════════════

try:
    from strategy.kronos_engine import (
        DEFAULT_CONFIG,
        load_kronos,
        PredictionResult,
        DriftStatus,
        StockPrediction,
        calculate_price_change,
        PredictionEngine,           # [AI MOD]
        KronosRealEngine,           # [AI MOD]
        MonteCarloEngine,           # [AI MOD]
        DriftMonitor,               # [AI MOD]
        PlotBar,                    # [AI MOD]
        PredictionChartRenderer,    # [AI MOD]
    )
except ImportError:
    load_kronos = None

# [FIX] 移除循環依賴：patterns_strategy 自帶 MarketScanner (L822)，不需要從 prediction_strategy 匯入

CONTEXT_LEN    = 512
PATTERN_WINDOW = 90
PRED_DAYS      = 5
MIN_BARS       = 30
NECKLINE_TOL   = 0.08
PIVOT_WINDOW   = 5
QUALITY_FLOOR  = 0.45

# Removed duplicate local variable _kronos_pipeline # [AI MOD]

_DIR_STYLE = {"bullish": "bright_red", "bearish": "bright_green", "neutral": "bright_yellow"}
_DIR_ICON  = {"bullish": "🔴", "bearish": "🟢", "neutral": "🟡"}


# ── Stub classes for type hints ──────────────────────────
class _BarView:
    """Minimal wrapper for pandas DataFrame used by pivot scanner."""
    def __init__(self, df: pd.DataFrame):
        self.df = df

    @classmethod
    def from_pandas(cls, df: pd.DataFrame) -> "_BarView":
        return cls(df)

    def __getitem__(self, key):
        return self.df[key]

    @property
    def index(self):
        return self.df.index

    @property
    def columns(self):
        return self.df.columns

    def __len__(self):
        return len(self.df)


@dataclass
class PatternInfo:
    """Container for detected chart pattern metadata."""
    code: str = ""
    name: str = ""
    pattern: str = ""
    direction: str = ""
    neckline: float = 0.0
    target: float = 0.0
    stop_loss: float = 0.0
    quality: float = 0.0
    extreme: float = 0.0
    confidence: float = 0.0
    points: list = field(default_factory=list)
    zone: str = ""


@dataclass
class BreakoutCandidate:
    """Container for breakout pattern candidates."""
    code: str = ""
    name: str = ""
    pattern: str = ""
    direction: str = ""
    price: float = 0.0
    volume: int = 0
    target: float = 0.0
    stop_loss: float = 0.0
    confidence: float = 0.0


# ══════════════════════════════════════════════════════════
#  Local helpers (replaces phone.utils.common)
# ══════════════════════════════════════════════════════════

def _clear_screen():
    clear_screen()


def _get_single_key_input(prompt: str, keys: str, default: str = "4",
                          auto_four: bool = False, back_on_enter: bool = False) -> str:
    """[AI MOD] Robust single-key input helper supporting Windows and fallback.

    ponytail: back_on_enter=True makes Enter return "" (back signal) instead of default.
    """
    try:
        import msvcrt
        if sys.stdin.isatty():
            while msvcrt.kbhit():
                msvcrt.getwch()
            sys.stdout.write(prompt)
            sys.stdout.flush()
            buf = ""
            while True:
                if msvcrt.kbhit():
                    ch = msvcrt.getwch()
                    if ch in ('\r', '\n'):
                        sys.stdout.write('\n')
                        sys.stdout.flush()
                        if back_on_enter:
                            return ""  # ponytail: back signal
                        return buf if (auto_four and len(buf) > 0) else default
                    elif ch in ('\x1b', '\x03'): # ESC or Ctrl+C
                        sys.stdout.write('\n')
                        sys.stdout.flush()
                        return "0"
                    elif ch in keys:
                        sys.stdout.write(ch + '\n')
                        sys.stdout.flush()
                        return ch
                time.sleep(0.01)
    except Exception:
        pass

    val = input(prompt).strip()
    if back_on_enter and not val:
        return ""  # ponytail: back signal
    return val if val else default


def _render_header(title, is_detail=False):
    render_header(title, is_detail=is_detail, console=rconsole)


def _get_stock_name(conn, stock_id):
    return get_stock_name(conn, stock_id)


class PivotBasedScanner:

    @staticmethod
    def find_pivots(df: _BarView, window: int = PIVOT_WINDOW) -> List[Dict]:
        h = df["high"].values
        l = df["low"].values
        dates = df.index
        n = len(df)
        pivots = []
        for i in range(window, n - window):
            if h[i] == max(h[i - window:i + window + 1]):
                pivots.append({"idx": i, "date": dates[i], "price": float(h[i]), "type": "H"})
            if l[i] == min(l[i - window:i + window + 1]):
                pivots.append({"idx": i, "date": dates[i], "price": float(l[i]), "type": "L"})
        return pivots

    def find_patterns(self, df: pd.DataFrame) -> List[PatternInfo]:
        data = df.tail(PATTERN_WINDOW)
        if len(data) < MIN_BARS:
            return []
        view = _BarView.from_pandas(data)
        pivots = self.find_pivots(view)
        if len(pivots) < 2:
            return []

        hi_pivots = [p for p in pivots if p["type"] == "H"]
        lo_pivots = [p for p in pivots if p["type"] == "L"]

        patterns: List[PatternInfo] = []

        # Two-point patterns
        patterns += self._match_w_bottom(view, lo_pivots, hi_pivots)
        patterns += self._match_m_top(view, hi_pivots, lo_pivots)
        patterns += self._match_n_bottom(view, lo_pivots, hi_pivots)

        # Three-point patterns
        patterns += self._match_hs_bottom(view, lo_pivots, hi_pivots)
        patterns += self._match_hs_top(view, hi_pivots, lo_pivots)
        patterns += self._match_triple_bottom(view, lo_pivots, hi_pivots)
        patterns += self._match_triple_top(view, hi_pivots, lo_pivots)

        # Single-point patterns
        patterns += self._match_v_reversal(view, lo_pivots)
        patterns += self._match_inv_v(view, hi_pivots)

        # Trend patterns
        patterns += self._match_triangles(view, hi_pivots, lo_pivots)
        patterns += self._match_wedges(view, hi_pivots, lo_pivots)
        patterns += self._match_channels(view, hi_pivots, lo_pivots)

        # Flag / box
        patterns += self._match_flags(view, hi_pivots, lo_pivots)
        patterns += self._match_range_box(view, hi_pivots, lo_pivots)

        # Arc
        patterns += self._match_arc(view, lo_pivots, "bullish")
        patterns += self._match_arc(view, hi_pivots, "bearish")

        for p in patterns:
            # Recency penalty [AI MOD]
            n = len(view)
            end_idx = p.zone[1]
            days_ago = (n - 1) - end_idx
            if days_ago <= 10:
                recency_mult = 1.0
            else:
                recency_mult = max(0.0, 1.0 - (days_ago - 10) * 0.05)
            p.quality = round(self._quality(view, p) * recency_mult, 3)

        return [p for p in patterns if p.quality >= QUALITY_FLOOR]

    # ── W Bottom ──
    def _match_w_bottom(self, df, lo_pivots, hi_pivots) -> List[PatternInfo]:
        results = []
        c = df["close"].values
        current = float(c[-1])
        for i in range(len(lo_pivots)):
            for j in range(i + 1, len(lo_pivots)):
                f1, f2 = lo_pivots[i], lo_pivots[j]
                if f2["idx"] - f1["idx"] < 10: continue
                mid_highs = [h for h in hi_pivots if f1["idx"] < h["idx"] < f2["idx"]]
                if not mid_highs: continue
                neckline_pivot = max(mid_highs, key=lambda x: x["price"])
                neckline = neckline_pivot["price"]
                lowest = min(f1["price"], f2["price"])
                if f2["price"] < f1["price"] * 0.97: continue
                if neckline <= lowest: continue
                dist = abs(current - neckline) / neckline
                if dist > NECKLINE_TOL: continue
                results.append(self._make_pattern(
                    "W底", "bullish", neckline, lowest,
                    [(f1["date"], f1["price"]), (neckline_pivot["date"], neckline),
                     (f2["date"], f2["price"])], (f1["idx"], f2["idx"])))
        return results

    # ── M Top ──
    def _match_m_top(self, df, hi_pivots, lo_pivots) -> List[PatternInfo]:
        results = []
        c = df["close"].values
        current = float(c[-1])
        for i in range(len(hi_pivots)):
            for j in range(i + 1, len(hi_pivots)):
                p1, p2 = hi_pivots[i], hi_pivots[j]
                if p2["idx"] - p1["idx"] < 10: continue
                mid_lows = [l for l in lo_pivots if p1["idx"] < l["idx"] < p2["idx"]]
                if not mid_lows: continue
                neckline_pivot = min(mid_lows, key=lambda x: x["price"])
                neckline = neckline_pivot["price"]
                highest = max(p1["price"], p2["price"])
                if p2["price"] > p1["price"] * 1.03: continue
                if neckline >= highest: continue
                dist = abs(current - neckline) / neckline
                if dist > NECKLINE_TOL: continue
                results.append(self._make_pattern(
                    "M頭", "bearish", neckline, highest,
                    [(p1["date"], p1["price"]), (neckline_pivot["date"], neckline),
                     (p2["date"], p2["price"])], (p1["idx"], p2["idx"])))
        return results

    # ── N Bottom ──
    def _match_n_bottom(self, df, lo_pivots, hi_pivots) -> List[PatternInfo]:
        results = []
        c = df["close"].values
        current = float(c[-1])
        for i in range(len(lo_pivots)):
            for j in range(len(hi_pivots)):
                foot1 = lo_pivots[i]
                peak = hi_pivots[j]
                if peak["idx"] <= foot1["idx"] or peak["idx"] - foot1["idx"] < 5: continue
                foot2s = [l for l in lo_pivots if l["idx"] > peak["idx"]
                          and l["price"] > foot1["price"] and l["idx"] - peak["idx"] >= 5]
                for foot2 in foot2s:
                    rebound = peak["price"] - foot1["price"]
                    if foot2["price"] < foot1["price"] + rebound * 0.5: continue
                    neckline = peak["price"]
                    dist = abs(current - neckline) / neckline
                    if dist > NECKLINE_TOL: continue
                    results.append(self._make_pattern(
                        "N字底", "bullish", neckline, foot1["price"],
                        [(foot1["date"], foot1["price"]), (peak["date"], neckline),
                         (foot2["date"], foot2["price"])], (foot1["idx"], foot2["idx"])))
        return results

    # ── H&S Bottom ──
    def _match_hs_bottom(self, df, lo_pivots, hi_pivots) -> List[PatternInfo]:
        results = []
        c = df["close"].values
        current = float(c[-1])
        for i in range(len(lo_pivots) - 2):
            ls, head, rs = lo_pivots[i], lo_pivots[i + 1], lo_pivots[i + 2]
            if head["price"] >= ls["price"] or head["price"] >= rs["price"]: continue
            if abs(ls["price"] - rs["price"]) / max(ls["price"], rs["price"]) > 0.10: continue
            mid = (ls["price"] + head["price"]) / 2
            if ls["price"] < mid or rs["price"] < mid: continue
            neck_highs = [h for h in hi_pivots if ls["idx"] < h["idx"] < rs["idx"]]
            if len(neck_highs) < 1: continue
            neckline = min(h["price"] for h in neck_highs)
            dist = abs(current - neckline) / neckline
            if dist > NECKLINE_TOL: continue
            results.append(self._make_pattern(
                "頸肩底", "bullish", neckline, head["price"],
                [(ls["date"], ls["price"]), (head["date"], head["price"]),
                 (rs["date"], rs["price"])], (ls["idx"], rs["idx"])))
        return results

    # ── H&S Top ──
    def _match_hs_top(self, df, hi_pivots, lo_pivots) -> List[PatternInfo]:
        results = []
        c = df["close"].values
        current = float(c[-1])
        for i in range(len(hi_pivots) - 2):
            ls, head, rs = hi_pivots[i], hi_pivots[i + 1], hi_pivots[i + 2]
            if head["price"] <= ls["price"] or head["price"] <= rs["price"]: continue
            if abs(ls["price"] - rs["price"]) / max(ls["price"], rs["price"]) > 0.10: continue
            neck_lows = [l for l in lo_pivots if ls["idx"] < l["idx"] < rs["idx"]]
            if len(neck_lows) < 1: continue
            neckline = max(l["price"] for l in neck_lows)
            dist = abs(current - neckline) / neckline
            if dist > NECKLINE_TOL: continue
            results.append(self._make_pattern(
                "頸肩頂", "bearish", neckline, head["price"],
                [(ls["date"], ls["price"]), (head["date"], head["price"]),
                 (rs["date"], rs["price"])], (ls["idx"], rs["idx"])))
        return results

    # ── Triple Bottom / Top ──
    def _match_triple_bottom(self, df, lo_pivots, hi_pivots) -> List[PatternInfo]:
        results = []
        c = df["close"].values
        current = float(c[-1])
        for i in range(len(lo_pivots) - 2):
            pts = lo_pivots[i:i + 3]
            prices = [p["price"] for p in pts]
            avg = np.mean(prices)
            if any(abs(p - avg) / avg > 0.08 for p in prices): continue
            if pts[-1]["idx"] - pts[0]["idx"] < 15: continue
            neck_highs = [h for h in hi_pivots if pts[0]["idx"] < h["idx"] < pts[-1]["idx"]]
            if not neck_highs: continue
            neckline = max(h["price"] for h in neck_highs)
            lowest = min(prices)
            if neckline <= lowest: continue
            dist = abs(current - neckline) / neckline
            if dist > NECKLINE_TOL: continue
            results.append(self._make_pattern(
                "三重底", "bullish", neckline, lowest,
                [(p["date"], p["price"]) for p in pts],
                (pts[0]["idx"], pts[-1]["idx"])))
        return results

    def _match_triple_top(self, df, hi_pivots, lo_pivots) -> List[PatternInfo]:
        results = []
        c = df["close"].values
        current = float(c[-1])
        for i in range(len(hi_pivots) - 2):
            pts = hi_pivots[i:i + 3]
            prices = [p["price"] for p in pts]
            avg = np.mean(prices)
            if any(abs(p - avg) / avg > 0.08 for p in prices): continue
            if pts[-1]["idx"] - pts[0]["idx"] < 15: continue
            neck_lows = [l for l in lo_pivots if pts[0]["idx"] < l["idx"] < pts[-1]["idx"]]
            if not neck_lows: continue
            neckline = min(l["price"] for l in neck_lows)
            highest = max(prices)
            if neckline >= highest: continue
            dist = abs(current - neckline) / neckline
            if dist > NECKLINE_TOL: continue
            results.append(self._make_pattern(
                "三重頂", "bearish", neckline, highest,
                [(p["date"], p["price"]) for p in pts],
                (pts[0]["idx"], pts[-1]["idx"])))
        return results

    # ── V Reversal / Inv-V ──
    def _match_v_reversal(self, df, lo_pivots) -> List[PatternInfo]:
        results = []
        c = df["close"].values
        current = float(c[-1])
        for p in lo_pivots:
            idx = p["idx"]
            if idx < 10 or idx > len(c) - 5: continue
            pre_high = max(c[max(0, idx - 10):idx])
            drop_pct = (pre_high - p["price"]) / pre_high
            if drop_pct < 0.10: continue
            post_high = max(c[idx:min(len(c), idx + 10)])
            rebound_pct = (post_high - p["price"]) / (pre_high - p["price"]) if pre_high > p["price"] else 0
            if rebound_pct < 0.50: continue
            neckline = pre_high
            dist = abs(current - neckline) / neckline
            if dist > NECKLINE_TOL: continue
            results.append(self._make_pattern(
                "V型反轉", "bullish", neckline, p["price"],
                [(df.index[max(0, idx - 10)], pre_high), (p["date"], p["price"]),
                 (df.index[min(len(c) - 1, idx + 10)], post_high)],
                (max(0, idx - 10), min(len(c) - 1, idx + 10))))
        return results

    def _match_inv_v(self, df, hi_pivots) -> List[PatternInfo]:
        results = []
        c = df["close"].values
        current = float(c[-1])
        for p in hi_pivots:
            idx = p["idx"]
            if idx < 10 or idx > len(c) - 5: continue
            pre_low = min(c[max(0, idx - 10):idx])
            rise_pct = (p["price"] - pre_low) / pre_low if pre_low > 0 else 0
            if rise_pct < 0.10: continue
            post_low = min(c[idx:min(len(c), idx + 10)])
            drop_pct = (p["price"] - post_low) / (p["price"] - pre_low) if p["price"] > pre_low else 0
            if drop_pct < 0.50: continue
            neckline = pre_low
            dist = abs(current - neckline) / neckline
            if dist > NECKLINE_TOL: continue
            results.append(self._make_pattern(
                "倒V反轉", "bearish", neckline, p["price"],
                [(df.index[max(0, idx - 10)], pre_low), (p["date"], p["price"]),
                 (df.index[min(len(c) - 1, idx + 10)], post_low)],
                (max(0, idx - 10), min(len(c) - 1, idx + 10))))
        return results

    # ── Triangles ──
    def _match_triangles(self, df, hi_pivots, lo_pivots) -> List[PatternInfo]:
        results = []
        if len(hi_pivots) < 2 or len(lo_pivots) < 2: return results
        c = df["close"].values
        current = float(c[-1])
        recent_hi = hi_pivots[-3:] if len(hi_pivots) >= 3 else hi_pivots[-2:]
        recent_lo = lo_pivots[-3:] if len(lo_pivots) >= 3 else lo_pivots[-2:]
        hi_slope = self._slope(recent_hi)
        lo_slope = self._slope(recent_lo)
        if hi_slope is None or lo_slope is None: return results
        hi_flat = abs(hi_slope) < 0.3
        lo_flat = abs(lo_slope) < 0.3
        hi_down = hi_slope < -0.1
        lo_up = lo_slope > 0.1
        last_hi = recent_hi[-1]["price"]
        last_lo = recent_lo[-1]["price"]
        if hi_flat and lo_up:
            neckline = last_hi
            if abs(current - neckline) / neckline <= NECKLINE_TOL:
                results.append(self._make_pattern(
                    "上升三角形", "bullish", neckline, last_lo,
                    [(p["date"], p["price"]) for p in recent_hi + recent_lo],
                    (recent_hi[0]["idx"], max(recent_hi[-1]["idx"], recent_lo[-1]["idx"]))))
        if lo_flat and hi_down:
            neckline = last_lo
            if abs(current - neckline) / neckline <= NECKLINE_TOL:
                results.append(self._make_pattern(
                    "下降三角形", "bearish", neckline, last_hi,
                    [(p["date"], p["price"]) for p in recent_hi + recent_lo],
                    (recent_hi[0]["idx"], max(recent_hi[-1]["idx"], recent_lo[-1]["idx"]))))
        if hi_down and lo_up:
            neckline = (last_hi + last_lo) / 2
            if abs(current - neckline) / neckline <= NECKLINE_TOL:
                results.append(self._make_pattern(
                    "對稱三角形", "neutral", neckline, last_lo,
                    [(p["date"], p["price"]) for p in recent_hi + recent_lo],
                    (recent_hi[0]["idx"], max(recent_hi[-1]["idx"], recent_lo[-1]["idx"]))))
        return results

    # ── Wedges ──
    def _match_wedges(self, df, hi_pivots, lo_pivots) -> List[PatternInfo]:
        results = []
        if len(hi_pivots) < 2 or len(lo_pivots) < 2: return results
        c = df["close"].values
        current = float(c[-1])
        recent_hi = hi_pivots[-3:] if len(hi_pivots) >= 3 else hi_pivots[-2:]
        recent_lo = lo_pivots[-3:] if len(lo_pivots) >= 3 else lo_pivots[-2:]
        hi_slope = self._slope(recent_hi)
        lo_slope = self._slope(recent_lo)
        if hi_slope is None or lo_slope is None: return results
        last_hi = recent_hi[-1]["price"]
        last_lo = recent_lo[-1]["price"]
        if hi_slope > 0.1 and lo_slope > 0.1 and lo_slope > hi_slope:
            neckline = last_lo
            if abs(current - neckline) / neckline <= NECKLINE_TOL:
                results.append(self._make_pattern(
                    "上升楔形", "bearish", neckline, last_hi,
                    [(p["date"], p["price"]) for p in recent_hi + recent_lo],
                    (recent_hi[0]["idx"], max(recent_hi[-1]["idx"], recent_lo[-1]["idx"]))))
        if hi_slope < -0.1 and lo_slope < -0.1 and hi_slope < lo_slope:
            neckline = last_hi
            if abs(current - neckline) / neckline <= NECKLINE_TOL:
                results.append(self._make_pattern(
                    "下降楔形", "bullish", neckline, last_lo,
                    [(p["date"], p["price"]) for p in recent_hi + recent_lo],
                    (recent_hi[0]["idx"], max(recent_hi[-1]["idx"], recent_lo[-1]["idx"]))))
        return results

    # ── Channels ──
    def _match_channels(self, df, hi_pivots, lo_pivots) -> List[PatternInfo]:
        results = []
        if len(hi_pivots) < 2 or len(lo_pivots) < 2: return results
        c = df["close"].values
        current = float(c[-1])
        recent_hi = hi_pivots[-3:] if len(hi_pivots) >= 3 else hi_pivots[-2:]
        recent_lo = lo_pivots[-3:] if len(lo_pivots) >= 3 else lo_pivots[-2:]
        hi_slope = self._slope(recent_hi)
        lo_slope = self._slope(recent_lo)
        if hi_slope is None or lo_slope is None: return results
        last_hi = recent_hi[-1]["price"]
        last_lo = recent_lo[-1]["price"]
        slope_similar = abs(hi_slope - lo_slope) < 0.3
        zone = (recent_hi[0]["idx"], max(recent_hi[-1]["idx"], recent_lo[-1]["idx"]))
        pts = [(p["date"], p["price"]) for p in recent_hi + recent_lo]
        if slope_similar and hi_slope > 0.2 and lo_slope > 0.2:
            neckline = last_lo
            if abs(current - neckline) / neckline <= NECKLINE_TOL:
                results.append(PatternInfo(
                    pattern="上升通道", direction="bullish",
                    neckline=round(neckline, 2), extreme=round(last_hi, 2),
                    target=round(last_hi, 2), stop_loss=round(last_lo, 2),
                    confidence=0.8, quality=0.0, points=pts, zone=zone))
        if slope_similar and hi_slope < -0.2 and lo_slope < -0.2:
            neckline = last_hi
            if abs(current - neckline) / neckline <= NECKLINE_TOL:
                results.append(PatternInfo(
                    pattern="下降通道", direction="bearish",
                    neckline=round(neckline, 2), extreme=round(last_lo, 2),
                    target=round(last_lo, 2), stop_loss=round(last_hi, 2),
                    confidence=0.8, quality=0.0, points=pts, zone=zone))
        return results

    # ── Flags ──
    def _match_flags(self, df, hi_pivots, lo_pivots) -> List[PatternInfo]:
        results = []
        c = df["close"].values
        current = float(c[-1])
        n = len(c)
        if n < 20: return results
        search_end = int(n * 0.7)
        if search_end < 5: return results
        peak_idx = int(np.argmax(c[:search_end]))
        if peak_idx >= 5:
            fp = c[:peak_idx + 1]
            fg = c[peak_idx:]
            if len(fp) >= 5 and len(fg) >= 3:
                rally = (fp[-1] - fp[0]) / fp[0] if fp[0] > 0 else 0
                if rally > 0.08:
                    pullback = (fg[-1] - fg[0]) / fg[0] if fg[0] > 0 else 0
                    if -0.08 < pullback < 0:
                        neckline = float(max(fp))
                        dist = abs(current - neckline) / neckline
                        if dist <= NECKLINE_TOL:
                            results.append(self._make_pattern(
                                "牛旗", "bullish", neckline, float(min(fg)),
                                [(df.index[0], float(fp[0])), (df.index[peak_idx], neckline),
                                 (df.index[-1], float(fg[-1]))], (0, n - 1)))
        trough_idx = int(np.argmin(c[:search_end]))
        if trough_idx >= 5:
            fp = c[:trough_idx + 1]
            fg = c[trough_idx:]
            if len(fp) >= 5 and len(fg) >= 3:
                drop = (fp[-1] - fp[0]) / fp[0] if fp[0] > 0 else 0
                if drop < -0.08:
                    bounce = (fg[-1] - fg[0]) / fg[0] if fg[0] > 0 else 0
                    if 0 < bounce < 0.08:
                        neckline = float(min(fp))
                        dist = abs(current - neckline) / neckline
                        if dist <= NECKLINE_TOL:
                            results.append(self._make_pattern(
                                "熊旗", "bearish", neckline, float(max(fg)),
                                [(df.index[0], float(fp[0])), (df.index[trough_idx], neckline),
                                 (df.index[-1], float(fg[-1]))], (0, n - 1)))
        return results

    # ── Range Box ──
    def _match_range_box(self, df, hi_pivots, lo_pivots) -> List[PatternInfo]:
        results = []
        if len(hi_pivots) < 2 or len(lo_pivots) < 2: return results
        c = df["close"].values
        current = float(c[-1])
        hi_prices = [p["price"] for p in hi_pivots[-4:]]
        lo_prices = [p["price"] for p in lo_pivots[-4:]]
        hi_avg = np.mean(hi_prices)
        lo_avg = np.mean(lo_prices)
        hi_spread = (max(hi_prices) - min(hi_prices)) / hi_avg if hi_avg > 0 else 1
        lo_spread = (max(lo_prices) - min(lo_prices)) / lo_avg if lo_avg > 0 else 1
        if hi_spread > 0.06 or lo_spread > 0.06: return results
        neckline = (hi_avg + lo_avg) / 2
        dist = abs(current - neckline) / neckline
        if dist > NECKLINE_TOL: return results
        results.append(self._make_pattern(
            "區間箱型", "neutral", neckline, lo_avg,
            [(hi_pivots[-1]["date"], hi_avg), (lo_pivots[-1]["date"], lo_avg)],
            (min(hi_pivots[0]["idx"], lo_pivots[0]["idx"]),
             max(hi_pivots[-1]["idx"], lo_pivots[-1]["idx"]))))
        return results

    # ── Arc ──
    def _match_arc(self, df, pivots, direction) -> List[PatternInfo]:
        results = []
        if len(pivots) < 4: return results
        c = df["close"].values
        current = float(c[-1])
        recent = pivots[-6:] if len(pivots) >= 6 else pivots[-4:]
        prices = [p["price"] for p in recent]
        n = len(prices)
        if direction == "bullish":
            min_val = min(prices)
            min_idx = prices.index(min_val)
            if not (0.2 * n <= min_idx <= 0.8 * n): return results
            start_p, end_p = prices[0], prices[-1]
            if start_p <= min_val or end_p <= min_val: return results
            arc_depth = (max(start_p, end_p) - min_val) / max(start_p, end_p)
            if arc_depth < 0.03: return results
            neckline = max(start_p, end_p)
            dist = abs(current - neckline) / neckline
            if dist <= NECKLINE_TOL:
                results.append(self._make_pattern(
                    "圓弧底", "bullish", neckline, min_val,
                    [(p["date"], p["price"]) for p in recent],
                    (recent[0]["idx"], recent[-1]["idx"])))
        else:
            max_val = max(prices)
            max_idx = prices.index(max_val)
            if not (0.2 * n <= max_idx <= 0.8 * n): return results
            start_p, end_p = prices[0], prices[-1]
            if start_p >= max_val or end_p >= max_val: return results
            arc_depth = (max_val - min(start_p, end_p)) / max_val
            if arc_depth < 0.03: return results
            neckline = min(start_p, end_p)
            dist = abs(current - neckline) / neckline
            if dist <= NECKLINE_TOL:
                results.append(self._make_pattern(
                    "圓弧頂", "bearish", neckline, max_val,
                    [(p["date"], p["price"]) for p in recent],
                    (recent[0]["idx"], recent[-1]["idx"])))
        return results

    # ── Utilities ──
    @staticmethod
    def _slope(pivots) -> Optional[float]:
        if len(pivots) < 2: return None
        x = np.array([p["idx"] for p in pivots], dtype=float)
        y = np.array([p["price"] for p in pivots], dtype=float)
        if np.ptp(x) == 0: return None
        slope, _ = np.polyfit(x, y, 1)
        return float(slope)

    @staticmethod
    def _make_pattern(name, direction, neckline, extreme, points, zone):
        neckline = round(neckline, 2)
        extreme = round(extreme, 2)
        if direction == "bullish":
            target = round(2 * neckline - extreme, 2)
            stop_loss = extreme
        elif direction == "bearish":
            target = round(2 * neckline - extreme, 2)
            stop_loss = extreme
        else:
            height = abs(neckline - extreme)
            target = round(neckline + height, 2) if neckline > extreme else round(neckline - height, 2)
            stop_loss = extreme
        return PatternInfo(
            pattern=name, direction=direction, neckline=neckline, extreme=extreme,
            target=target, stop_loss=round(stop_loss, 2), confidence=0.8,
            quality=0.0, points=points, zone=zone)

    @staticmethod
    def _quality(df: _BarView, pat: PatternInfo) -> float:
        c = df["close"].values
        o = df["open"].values if "open" in df.columns else c
        v = df["volume"].values if "volume" in df.columns else np.ones(len(df))
        zone_start, zone_end = pat.zone
        zone_start = max(0, zone_start)
        zone_end = min(len(v) - 1, zone_end)
        if zone_end > zone_start + 5:
            zone_vol = v[zone_start:zone_end + 1]
            avg_vol = np.mean(zone_vol[:-3]) if len(zone_vol) > 3 else 1
            last_vol = zone_vol[-1]
            vol_score = min(last_vol / (avg_vol * 1.5 + 1e-8), 1.0) if avg_vol > 0 else 0.5
        else:
            vol_score = 0.5
        pre_start = max(0, zone_start - 20)
        if pre_start < zone_start and zone_start > 0:
            pre_change = (c[zone_start] - c[pre_start]) / c[pre_start] if c[pre_start] > 0 else 0
            if pat.direction == "bullish":
                trend_score = min(max(-pre_change, 0) / 0.05, 1.0)
            elif pat.direction == "bearish":
                trend_score = min(max(pre_change, 0) / 0.05, 1.0)
            else:
                trend_score = 0.5
        else:
            trend_score = 0.5
        last_idx = min(zone_end, len(c) - 1)
        body = abs(c[last_idx] - o[last_idx])
        rng = df["high"].values[last_idx] - df["low"].values[last_idx]
        kline_score = min(body / (rng + 1e-8), 1.0) if rng > 0 else 0.3
        if pat.neckline > 0:
            structure_score = min(abs(pat.neckline - pat.extreme) / pat.neckline, 0.15) / 0.15
        else:
            structure_score = 0.5
        return vol_score * 0.30 + trend_score * 0.25 + kline_score * 0.20 + structure_score * 0.25


# ══════════════════════════════════════════════════════════
#  Single stock analysis
# ══════════════════════════════════════════════════════════

class StockPredictionAnalyzer:
    def __init__(self, config=None):
        self.config = DEFAULT_CONFIG.copy()
        if config: self.config.update(config)
        self.pattern_scanner = PivotBasedScanner()

    def _render_mobile_patterns(self, df, code, name, pat):
        """Mobile layout for chart patterns (only patterns)."""
        rconsole.print(f"[dim]{'─ 4 型態 ' + code + ' ' + name}{'─' * 20}[/]")
        if pat:
            # [AI MOD] Removed Quality (品質)
            ds = _DIR_STYLE.get(pat.direction, "white")
            di = _DIR_ICON.get(pat.direction, "⚪")
            rconsole.print(f"  {di} [{ds}]{pat.pattern}[/]")
            rconsole.print(f"  頸線 {pat.neckline:.2f}  目標 {pat.target:.2f}  停損 {pat.stop_loss:.2f}")
        else:
            rconsole.print("  [dim]近期無明顯幾何型態[/]")

    def analyze_single_stock(self, symbol, name, df, compact=False, mobile=False):
        try:
            # ── 幾何型態偵測 ──
            patterns = self.pattern_scanner.find_patterns(df)
            best_pat = max(patterns, key=lambda p: p.quality) if patterns else None

            if mobile:
                self._render_mobile_patterns(df, symbol, name, best_pat)
                return

            # ── Desktop ──
            if not compact:
                rconsole.print()
                rconsole.print(Panel(
                    f"[bold bright_white]{symbol} {name} K棒量價與型態分析[/]",
                    border_style="bright_cyan", box=box.DOUBLE))

            if best_pat:
                # [AI MOD] Removed Quality (品質)
                ds = _DIR_STYLE.get(best_pat.direction, "white")
                di = _DIR_ICON.get(best_pat.direction, "⚪")
                rconsole.print()
                rconsole.print(f"  {di} [{ds}]{best_pat.pattern}[/]")
                rconsole.print(f"  頸線 {best_pat.neckline:.2f}  "
                               f"目標 {best_pat.target:.2f}  "
                               f"停損 {best_pat.stop_loss:.2f}")
            else:
                rconsole.print()
                rconsole.print("  [dim]近期無明顯幾何型態[/]")
        except Exception as e:
            rconsole.print(f"[red]❌ 分析錯誤: {e}[/]")


# ══════════════════════════════════════════════════════════
#  Market Scanner (prediction ranking)
# ══════════════════════════════════════════════════════════

class MarketScanner:
    def __init__(self, conn, config=None):
        self.conn = conn
        self.config = DEFAULT_CONFIG.copy()
        if config: self.config.update(config)
        self.mc_engine = MonteCarloEngine()

    def scan_market(self, min_volume=500):
        try:
            ld, sm = self._get_market_data()
            if not ld:
                rconsole.print("[yellow]⚠️ 無行情數據[/]")
                return
            targets = self._get_targets(ld, min_volume)
            preds = self._analyze(targets, sm)
            self._display(preds, ld)
        except Exception as e:
            rconsole.print(f"[red]❌ 掃描失敗: {e}[/]")

    def _get_market_data(self):
        with self.conn:
            dr = self.conn.execute("SELECT MAX(date) FROM stock_history").fetchone()
            if not dr or not dr[0]: return None, {}
            # [AI MOD] stock_id, stock_name
            nr = self.conn.execute("SELECT stock_id, stock_name FROM stock_meta").fetchall()
            return dr[0], {str(r[0]): str(r[1]) for r in nr}

    def _get_targets(self, ld, mv):
        # [AI MOD] parameterized query, converted mv from sheets (張) to shares (股)
        return pd.read_sql_query(
            "SELECT stock_id FROM stock_history "
            "WHERE date = ? AND volume >= ? AND stock_id GLOB '[1-9][0-9][0-9][0-9]'",
            self.conn,
            params=[ld, mv],
        )['stock_id'].tolist()

    def _analyze(self, sl, nm):
        preds = []
        with Progress(SpinnerColumn(), TextColumn("[cyan]🚀 預測掃描..."),
                      BarColumn(), TimeElapsedColumn()) as prog:
            task = prog.add_task("scan", total=len(sl))
            for code in sl:
                try:
                    r = self._one(code, nm)
                    if r: preds.append(r)
                except Exception:
                    pass
                prog.advance(task)
        return preds

    def _one(self, code, nm):
        # [AI MOD] Use klines view — no inject_price_data needed
        df = _fetch_klines(self.conn, code, limit=60)
        df = df.dropna(subset=["close"]).sort_values("date")
        if len(df) < 20: return None
        p = float(df['close'].iloc[-1])
        pred = self.mc_engine.predict(df, self.config)
        v = float(df['volume'].iloc[-1])
        if p <= 0: return None
        return StockPrediction(
            code, nm.get(code, "-"), p, int(v / 1000),
            (p * v) / 1e8, (pred.benchmark - p) / p,
            pred.benchmark, pred.confidence, p)

    def _display(self, preds, ld):
        if not preds:
            rconsole.print("[yellow]📭 無符合條件[/]")
            return
        preds.sort(key=lambda x: x.score, reverse=True)
        t = Table(title=f"📈 預測分析榜 (基準日: {ld})",
                  box=box.SIMPLE, border_style="cyan", expand=False)
        for c, s in [("代號", "magenta"), ("名稱", None), ("收盤", None),
                      ("成交張數", None), ("額(億)", "bright_green"),
                      ("潛力估值", None), ("預期目標", None), ("模型信心", None)]:
            t.add_column(c, style=s, justify="left", no_wrap=True)
        for p in preds[:40]:
            c = "bright_red" if p.score > 0 else "bright_green"
            dp = f"{p.current_price:.2f}"
            t.add_row(p.code, p.name, dp, f"{p.volume // 1000:,}", f"{p.amount:.2f}",
                      f"[{c}]{p.score:.2%}[/]", f"{p.target_price:.2f}",
                      f"{p.confidence:.1%}" if p.confidence > 0 else "N/A")
        rconsole.print(t)


# ══════════════════════════════════════════════════════════
#  Pattern Breakout Scanner
# ══════════════════════════════════════════════════════════

class PatternBreakoutScanner:
    def __init__(self, conn):
        self.conn = conn
        self.scanner = PivotBasedScanner()

    def scan(self, min_volume=500, direction_filter=None):
        try:
            ld, nm = self._get_market_data()
            if not ld:
                rconsole.print("[yellow]⚠️ 無行情數據[/]")
                return []

            # Check session cache
            cache_hit = False
            if (_PATTERN_CACHE['date'] == ld
                and _PATTERN_CACHE['min_volume'] == min_volume
                and _PATTERN_CACHE['results'] is not None
                and _time_mod.time() - _PATTERN_CACHE.get('ts', 0) < _CACHE_TTL):
                cache_hit = True
                cands_with_data = _PATTERN_CACHE['results']
                rconsole.print(f"\n[green]⚡ 已載入今日幾何型態掃描快取數據 (基準日: {ld}) [0.00s][/green]")
            else:
                symbols = self._get_targets(ld, min_volume)
                if not symbols:
                    rconsole.print("[yellow]⚠️ 無符合門檻[/]")
                    return []
                rconsole.print(f"\n  [dim]📊 掃描 {len(symbols)} 檔 · Pivot 偵測[/]\n")

                t0 = time.time()
                cands_with_data = []
                with Progress(SpinnerColumn(), TextColumn("[cyan]{task.percentage:>3.0f}%"),
                              BarColumn(bar_width=40), TimeElapsedColumn(),
                              console=rconsole) as prog:
                    task = prog.add_task("scan", total=len(symbols))
                    for sym in symbols:
                        try:
                            r = self._scan_one(sym, nm.get(sym, "-"))
                            if r:
                                cands_with_data.append(r)
                        except Exception:
                            pass
                        prog.advance(task)

                # Store in session cache
                _PATTERN_CACHE['date'] = ld
                _PATTERN_CACHE['min_volume'] = min_volume
                _PATTERN_CACHE['results'] = cands_with_data
                _PATTERN_CACHE['ts'] = _time_mod.time()
                rconsole.print(f"\n  [dim]✨ 完成 {time.time() - t0:.1f}s · {len(cands_with_data)} 檔命中[/]")

            cands = [c for c, _ in cands_with_data]
            if direction_filter:
                cands = [c for c in cands if c.direction == direction_filter]
                cands_with_data = [(c, d) for c, d in cands_with_data if c.direction == direction_filter]

            if not cands:
                label = {"bullish": "看漲", "bearish": "看跌", "neutral": "區間整理"}.get(direction_filter, "")
                rconsole.print(f"  [yellow]📭 {label}型態無符合條件[/]")
                return []

            sort_choice = "1"
            rconsole.print("\n[bold yellow]📊 請選擇掃描結果排序方式 (單鍵輸入):[/bold yellow]")
            rconsole.print("  [1] 距頸線由近到遠 (預設)")
            rconsole.print("  [2] 成交金額由大到小")
            try:
                import msvcrt
                while msvcrt.kbhit():
                    msvcrt.getwch()
                ch = msvcrt.getwch()
                if ch in ('1', '2'):
                    sort_choice = ch
            except Exception:
                pass

            if sort_choice == "1":
                cands.sort(key=lambda c: abs(c.distance_pct))
            elif sort_choice == "2":
                cands.sort(key=lambda c: (c.current_price * c.volume), reverse=True)

            self._display(cands, ld, sort_choice)
            return cands_with_data
        except Exception as e:
            rconsole.print(f"[red]❌ 掃描失敗: {e}[/]")
            return []

    def _get_market_data(self):
        with self.conn:
            dr = self.conn.execute("SELECT MAX(date) FROM stock_history").fetchone()
            if not dr or not dr[0]: return None, {}
            # [AI MOD] stock_id, stock_name
            nr = self.conn.execute("SELECT stock_id, stock_name FROM stock_meta").fetchall()
            return dr[0], {str(r[0]): str(r[1]) for r in nr}

    def _get_targets(self, ld, mv):
        # mv 單位為張，stock_history.volume 單位為股（1張=1000股）
        min_shares = mv * 1000
        return pd.read_sql_query(
            "SELECT stock_id FROM stock_history "
            "WHERE date = ? AND volume >= ? AND stock_id GLOB '[1-9][0-9][0-9][0-9]'",
            self.conn,
            params=[ld, min_shares],
        )['stock_id'].tolist()

    def _scan_one(self, symbol, name):
        # [AI MOD] Use klines view
        df = _fetch_klines(self.conn, symbol, limit=CONTEXT_LEN * 2)
        df = df.dropna(subset=["open", "high", "low", "close"]).sort_values("date")
        if len(df) < MIN_BARS:
            return None

        patterns = self.scanner.find_patterns(df)
        if not patterns:
            return None
        best = max(patterns, key=lambda p: p.quality)

        current_price = float(df['close'].iloc[-1])
        prev_close = float(df['close'].iloc[-2]) if len(df) > 1 else current_price
        volume = int(df['volume'].iloc[-1])
        prev_volume = int(df['volume'].iloc[-2]) if len(df) > 1 else volume
        dist = (current_price - best.neckline) / best.neckline
        if abs(dist) > NECKLINE_TOL:
            return None

        cand = BreakoutCandidate(
            symbol=symbol, name=name, pattern=best.pattern, direction=best.direction,
            neckline=best.neckline, extreme=best.extreme, target=best.target,
            stop_loss=best.stop_loss, confidence=best.confidence, quality=best.quality,
            current_price=current_price, distance_pct=round(dist * 100, 2),
            predicted_break_day=0, predicted_break_price=0.0,
            predicted_peak=0.0, volume=volume, points=best.points,
            prev_close=prev_close, prev_volume=prev_volume)
        return cand, df

    def _display(self, cands, ld, sort_choice="1"):
        sort_names = {
            "1": "距頸線由近到遠",
            "2": "成交金額由大到小"
        }
        sort_name = sort_names.get(sort_choice, "距頸線由近到遠")

        bulls = [c for c in cands if c.direction == "bullish"]
        bears = [c for c in cands if c.direction == "bearish"]
        neuts = [c for c in cands if c.direction == "neutral"]
        base = f"型態突破掃描 (排序: {sort_name}) 🎯 {PRED_DAYS} 日內可能突破頸線：資料庫日期：{ld}"

        def _tbl(title, rows, border):
            if not rows: return
            # [AI MOD] Formatted volume in sheets (張) and deleted Quality (品質) column
            t = Table(title=title, box=box.ROUNDED, border_style=border, title_style=f"bold {border}")
            t.add_column("代號", width=7)
            t.add_column("名稱", width=6)
            t.add_column("收盤", width=9, justify="right")
            t.add_column("成交張數", width=9, justify="right")
            t.add_column("額(億)", width=9, justify="right")
            t.add_column("型態", width=10)
            t.add_column("頸線", width=9, justify="right")
            t.add_column("目標", width=9, justify="right")
            t.add_column("停損", width=9, justify="right")
            for r in rows:
                ds = _DIR_STYLE.get(r.direction, "white")
                vol_sheets = r.volume // 1000

                # Price color [AI MOD]
                try:
                    price_change = r.current_price - r.prev_close
                    pct = (price_change / r.prev_close * 100) if r.prev_close else 0.0
                    pc = price_color(price_change, pct)
                    disp_price_colored = f"[{pc}]{r.current_price:.2f}[/]"
                except Exception:
                    disp_price_colored = f"{r.current_price:.2f}"

                # Volume color [AI MOD]
                try:
                    vc = vol_color(r.volume, r.prev_volume if r.prev_volume else r.volume)
                    disp_vol_colored = f"[{vc}]{vol_sheets:,}[/]"
                except Exception:
                    disp_vol_colored = f"{vol_sheets:,}"

                t.add_row(r.symbol, r.name, disp_price_colored, disp_vol_colored,
                          f"{r.amount:.2f}",
                          f"[{ds}]{r.pattern}[/]", f"{r.neckline:.2f}",
                          f"[bright_cyan]{r.target:.2f}[/]", f"[bright_red]{r.stop_loss:.2f}[/]")
            rconsole.print(t)

        if bulls: _tbl(f"🔴 看漲型態 · {base}", bulls, "bright_red"); rconsole.print()
        if bears: _tbl(f"🟢 看跌型態 · {base}", bears, "bright_green"); rconsole.print()
        if neuts: _tbl(f"🟡 中性型態 · {base}", neuts, "bright_yellow")


# ══════════════════════════════════════════════════════════
#  Main App
# ══════════════════════════════════════════════════════════

class PredictionAnalysisApp:
    def __init__(self):
        self.config = DEFAULT_CONFIG.copy()
        self.analyzer = None
        self.market_scanner = None
        self.pattern_scanner = None

    @contextmanager
    def database_connection(self):
        # [AI MOD] Unified DB connection
        conn = get_connection(readonly=True)
        try:
            yield conn
        finally:
            conn.close()

    def get_user_command(self):
        _clear_screen()
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        rconsole.print()
        rconsole.print(Panel(
            f"[bold bright_cyan]Kronos 全功能整合 v5.3[/] · "
            f"[dim]Pivot 偵測 · 量價突破 · {PRED_DAYS} 天預測[/]",
            subtitle=f"[dim]DATE: {now}[/]",
            border_style="bright_cyan", box=box.DOUBLE))
        rconsole.print()
        rconsole.print("  [bold]  [4碼股號][/]  單檔分析（預測 + 型態）")
        rconsole.print("  [bold]  [1][/]        未來五日漲幅最多預測（全市場掃描）")
        rconsole.print("  [bold]  [2][/]        5 日內可能突破頸線（型態掃描）")
        rconsole.print("  [bold]  [0][/]        退出")
        rconsole.print()
        cmd = rconsole.input("  🔍 指令: ").strip()
        if cmd == '0': return 'exit', None
        elif cmd == '1':
            v = rconsole.input("  📊 最小成交量 (張, 預設 500, 按 Enter 返回): ").strip()
            if not v:
                return None, None  # ponytail: back to main menu
            return 'predict_scan', int(v) if v.isdigit() else 500
        elif cmd == '2':
            return 'pattern_scan', None  # ponytail: volume asked after category
        elif len(cmd) == 4 and cmd.isdigit():
            return 'analyze', cmd
        else:
            raise ValueError("無效指令")

    def analyze_single_stock(self, conn, code, compact=False, mobile=False):
        try:
            # [AI MOD] klines view + parameterized query
            df = _fetch_klines(conn, code, limit=512)
            df = df.dropna(subset=["open", "high", "low", "close", "volume"]).sort_values("date")
            if df.empty:
                rconsole.print(f"[red]❌ 查無資料: {code}[/]")
                time.sleep(1)
                return
            name = _get_stock_name(conn, code)
            if not self.analyzer:
                self.analyzer = StockPredictionAnalyzer(self.config)

            # 1. 幾何型態分析 [AI MOD]
            self.analyzer.analyze_single_stock(code, name, df, compact=compact, mobile=mobile)

            # 2. Kronos 預測分析 [AI MOD] Only print if not compact (standalone run)
            if not compact:
                try:
                    try:
                        RealPredictionAnalyzer = StockPredictionAnalyzer  # [FIX] use local class; avoids cross-module re-import
                    except NameError:
                        RealPredictionAnalyzer = None
                    if RealPredictionAnalyzer is None:
                        raise ImportError("patterns_strategy.StockPredictionAnalyzer 不存在")
                    real_pred_analyzer = RealPredictionAnalyzer(self.config)
                    real_pred_analyzer.analyze_single_stock(code, name, df, compact=False, mobile=mobile)
                except Exception as pe:
                    rconsole.print(f"[red]❌ Kronos 預測加載失敗: {pe}[/]")

            # 3. LongCat AI 深度視覺辨識 (60日) [AI MOD] — 已移除
            # [FIX] vision_engine.py 已刪，此功能停用，保留 placeholder 供未來重構
            rconsole.print("\n[bold yellow]🧠 LongCat AI 深度視覺辨識 (60日) — 已停用[/bold yellow]")

            if not compact:
                rconsole.print()
                rconsole.input("  [dim]按 Enter 返回...[/]")
        except Exception as e:
            rconsole.print(f"[red]❌ {e}[/]")
            time.sleep(2)

    def predict_scan_market(self, conn, mv):
        try:
            if not self.market_scanner:
                self.market_scanner = MarketScanner(conn, self.config)
            self.market_scanner.scan_market(mv)
            rconsole.print()
            rconsole.input("  [dim]按 Enter 返回...[/]")
        except Exception as e:
            rconsole.print(f"[red]❌ {e}[/]")
            time.sleep(2)

    def _do_scan(self, conn, min_vol, direction_filter):
        """執行掃描並顯示結果（內部共用）"""
        if not self.pattern_scanner:
            self.pattern_scanner = PatternBreakoutScanner(conn)
        return self.pattern_scanner.scan(min_vol, direction_filter=direction_filter)

    def pattern_scan_market(self, conn, mv=None, pattern_filter=None):
        """
        型態掃描主流程。
        - pattern_filter 由 strategies.py 傳入時：直接掃描該分類，顯示結果後返回（由 strategies.py 接手 Kronos 提示）
        - pattern_filter 未傳入（None）：內嵌互動選單（分類 → 成交量 → 掃描 → 循環）
        """
        filter_map = {"1": "bullish", "2": "neutral", "3": "bearish", "4": None}

        # ── 模式 A：外層指定 filter，直接掃描並返回 ──
        if pattern_filter is not None:
            try:
                min_vol = mv if mv else 500
                self._do_scan(conn, min_vol, pattern_filter)
            except Exception as e:
                rconsole.print(f"[red]❌ {e}[/]")
                time.sleep(2)
            return

        # ── 模式 B：內嵌互動選單 ──
        try:
            direction_filter = None
            while True:  # category loop
                rconsole.print()
                rconsole.print("  [bold]型態分類：[/]")
                rconsole.print("  [bold][1][/] 看漲型態（W底·N字底·頸肩底·三重底·V反轉·圓弧底·上升三角·下降楔形·上升通道·牛旗）")
                rconsole.print("  [bold][2][/] 區間整理（箱型·對稱三角）")
                rconsole.print("  [bold][3][/] 看跌型態（M頭·頸肩頂·三重頂·倒V·圓弧頂·下降三角·上升楔形·下降通道·熊旗）")
                rconsole.print("  [bold][4][/] 全部")
                rconsole.print("  🔍 選擇 [1-4, 預設 4, 按 Enter 返回]: ", end="")
                choice = _get_single_key_input("", "1234", default="4", back_on_enter=True)
                if not choice:
                    return  # back to main menu
                direction_filter = filter_map.get(choice)

                while True:  # volume loop
                    v = rconsole.input("  📊 最小成交量 (張, 預設 500, 按 Enter 回上一步): ").strip()
                    if not v:
                        break  # back to category selection
                    min_vol = int(v) if v.isdigit() else 500

                    self._do_scan(conn, min_vol, direction_filter)

                    prompt_str = "\n  🔍 輸入股號查看 Kronos+AI 預測或輸入 1 看漲 2.區間 3.看跌 4.全部，或按 Enter 回到上一頁: "
                    ans = _get_single_key_input(prompt_str, "1234", default="", auto_four=True)
                    if not ans:
                        break  # back to volume prompt

                    if ans in ("1", "2", "3", "4"):
                        direction_filter = filter_map.get(ans)
                        continue  # re-scan with new category

                    if len(ans) == 4 and ans.isdigit():
                        self.analyze_single_stock(conn, ans)
                    else:
                        rconsole.print("  [red]請輸入 4 碼股號或 1-4 分類編號[/]")
                        time.sleep(1.5)
        except Exception as e:
            rconsole.print(f"[red]❌ {e}[/]")
            time.sleep(2)

    def run(self):
        signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
        try:
            with self.database_connection() as conn:
                while True:
                    try:
                        action, data = self.get_user_command()
                        if action is None:
                            continue  # ponytail: user pressed Enter to go back
                        if action == 'exit':
                            rconsole.print("\n  [dim]再見。[/]\n")
                            break
                        elif action == 'predict_scan':
                            self.predict_scan_market(conn, data)
                        elif action == 'pattern_scan':
                            self.pattern_scan_market(conn, data)
                        elif action == 'analyze':
                            self.analyze_single_stock(conn, data)
                    except ValueError as e:
                        rconsole.print(f"  [red]❌ {e}[/]")
                        time.sleep(1)
                    except KeyboardInterrupt:
                        break
                    except Exception as e:
                        rconsole.print(f"  [red]❌ {e}[/]")
                        time.sleep(2)
        except Exception as e:
            rconsole.print(f"[bold red]❌ {e}[/]")


def get_latest_date() -> str:
    """供 strategies.py 查詢資料基準日"""
    from strategy._utils import get_connection
    conn = get_connection(readonly=True)
    try:
        return conn.execute("SELECT MAX(date) FROM stock_history").fetchone()[0]
    finally:
        conn.close()


def run_strategy(params: dict):
    code = params.get('code')
    scan = params.get('scan', False)
    vol = params.get('vol', 500)
    pattern_filter = params.get('pattern_filter')
    compact = params.get('compact', False)
    mobile = params.get('mobile', False)
    app = PredictionAnalysisApp()
    if scan:
        with app.database_connection() as conn:
            app.pattern_scan_market(conn, vol, pattern_filter=pattern_filter)
    elif code:
        with app.database_connection() as conn:
            app.analyze_single_stock(conn, code, compact=compact, mobile=mobile)
    else:
        app.run()


class PatternStrategy:
    """型態策略 wrapper - 提供統一的 analyze() 介面。"""

    def analyze(self, stock_id: str) -> dict:
        """分析型態信號。回傳 strategy/stock_id/signal。"""
        from db import get_connection
        from strategy._utils import fetch_klines

        conn = get_connection()
        try:
            df = fetch_klines(conn, stock_id, limit=90)
            if df is None or df.empty or len(df) < 30:
                return {
                    "strategy": "pattern",
                    "stock_id": stock_id,
                    "signal": "neutral",
                    "reason": "資料不足",
                }

            scanner = PivotBasedScanner()
            patterns = scanner.find_patterns(df)
            best = max(patterns, key=lambda p: p.quality) if patterns else None

            if best is None:
                return {
                    "strategy": "pattern",
                    "stock_id": stock_id,
                    "signal": "neutral",
                    "reason": "無明顯型態",
                }

            signal = "bullish" if best.direction == "bullish" else ("bearish" if best.direction == "bearish" else "neutral")
            return {
                "strategy": "pattern",
                "stock_id": stock_id,
                "signal": signal,
                "pattern": best.pattern,
                "neckline": best.neckline,
                "target": best.target,
                "stop_loss": best.stop_loss,
                "quality": best.quality,
            }
        finally:
            conn.close()


def main():
    PredictionAnalysisApp().run()

if __name__ == "__main__":
    main()