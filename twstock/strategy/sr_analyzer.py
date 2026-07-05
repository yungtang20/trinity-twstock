#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略整合_撐壓分析 v3.2 (統一資料庫版)
依據 台股支撐壓力識別系統 Final 1.0 規格開發
# [AI MOD] Migrated to taiwan_stock_unified.db + klines view
# [AI MOD] Converted from polars to pandas for mobile compatibility
"""

import logging
import os
import signal
import sys
import time
import warnings

import numpy as np
import pandas as pd
from rich import box
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

# ── Module path ───────────────────────────────────────────

# ── Module path ───────────────────────────────────────────
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_TWSTOCK_DIR = os.path.abspath(os.path.join(_CURRENT_DIR, ".."))
if _TWSTOCK_DIR not in sys.path:
    sys.path.insert(0, _TWSTOCK_DIR)

from twstock.db import get_connection
from twstock.display import price_color, price_rich, vol_color, vol_fmt
from twstock.strategy._utils import clear_screen, fetch_klines, get_stock_name, render_header


def _to_date_int(val) -> int:
    """安全地將日期轉換為 YYYYMMDD 整數格式"""
    try:
        s = str(val)
        if "T" in s:
            s = s.split("T")[0]
        s = s.replace("-", "")
        return int(s)
    except (ValueError, TypeError):
        return 0


warnings.filterwarnings("ignore")

_CACHE_TTL = 300  # 5 分鐘
_SR_CACHE = {"date": None, "min_volume": None, "results": None, "ts": 0}

# [AI MOD] 集中式 Console：解決 Windows cp950 無法渲染 emoji 的問題
from twstock.terminal import console

try:
    from twstock.input_helper import get_blocking_key
except ImportError:
    from input_helper import get_blocking_key

FALLBACK_NAMES = {
    "2883": "凱基金",
    "2881": "富邦金",
    "2882": "國泰金",
    "2880": "華南金",
    "2884": "玉山金",
    "2885": "元大金",
    "2886": "兆豐金",
    "2887": "台新金",
    "2888": "新光金",
    "2890": "永豐金",
    "2891": "中信金",
    "2892": "第一金",
}


class StrategyConfig:
    ATR_PERIOD = 14
    SWING_LEFT = 5
    SWING_RIGHT = 5
    SWING_WINDOW = 120
    KEY_CLOSE_WINDOW = 120
    KEY_CLOSE_RETURN_THRESHOLD = 0.06
    KEY_CLOSE_NEAR_HIGH_RATIO = 0.20
    KEY_CLOSE_VOL_MULTIPLIER = 1.5
    ACCEL_WINDOW = 120
    ACCEL_BOX_WINDOW = 20
    ACCEL_ATR_MULTIPLIER = 0.8
    ACCEL_VOL_MULTIPLIER = 1.5
    ACCEL_COST_WINDOW = 7
    DENSITY_WINDOW = 250
    DENSITY_BINS = 60
    DENSITY_BAND_PERCENT = 0.30
    DENSITY_USE_LOG_BINS = True
    MERGE_ATR_TOLERANCE = 0.8
    MIN_DISTANCE_PERCENT = 0.01
    DEFAULT_MIN_VOLUME = 500
    MAX_DISTANCE_PERCENT = 8.0
    MAX_SCAN_RESULTS = 40

    @staticmethod
    def get_tick_size(price: float) -> float:
        if price < 10:
            return 0.01
        elif price < 50:
            return 0.05
        elif price < 100:
            return 0.1
        elif price < 500:
            return 0.5
        elif price < 1000:
            return 1.0
        return 5.0


class SupportResistanceEngine:
    def __init__(self, df):
        self.df = self._clean(df)
        self.last_close = float(self.df["close"].iloc[-1]) if not self.df.empty else 0.0
        self._compute_atr()

    @staticmethod
    def _clean(df):
        if df.empty:
            return df
        df = df.dropna(subset=["open", "high", "low", "close"]).copy()
        mask = (df["open"] > 0) & (df["high"] > 0) & (df["low"] > 0) & (df["close"] > 0)
        df = df[mask].copy()
        df["high"] = df[["open", "high", "low", "close"]].max(axis=1)
        df["low"] = df[["open", "high", "low", "close"]].min(axis=1)
        if "volume" in df.columns:
            df = df[df["volume"] >= 0].copy()
        return df.sort_values("date").reset_index(drop=True)

    def _compute_atr(self, period: int = StrategyConfig.ATR_PERIOD):
        if self.df.empty:
            return
        tick = StrategyConfig.get_tick_size(self.last_close)
        self.df = self.df.copy()
        self.df["_pc"] = self.df["close"].shift(1)
        self.df["_tr"] = np.maximum(
            self.df["high"] - self.df["low"],
            np.maximum(
                (self.df["high"] - self.df["_pc"]).abs(), (self.df["low"] - self.df["_pc"]).abs()
            ),
        )
        self.df["atr"] = np.where(self.df["_tr"] < 2 * tick, 2 * tick, self.df["_tr"])
        self.df["atr"] = self.df["atr"].rolling(window=period).mean()
        self.df = self.df.drop(columns=["_pc", "_tr"])

    def _find_swing(self, arr, dates, mode):
        n = StrategyConfig.SWING_LEFT + StrategyConfig.SWING_RIGHT + 1
        if len(arr) < n:
            return None
        cmp_fn = np.max if mode == "high" else np.min
        for i in range(
            len(arr) - StrategyConfig.SWING_RIGHT - 1, StrategyConfig.SWING_LEFT - 1, -1
        ):
            if i <= 0:
                break
            win = arr[i - StrategyConfig.SWING_LEFT : i + StrategyConfig.SWING_RIGHT + 1]
            if len(win) == 0:
                continue
            extreme = cmp_fn(win)
            if arr[i] == extreme:
                idxs = np.where(win == extreme)[0]
                if idxs[-1] == StrategyConfig.SWING_LEFT:
                    return {"date": _to_date_int(dates[i]), "price": float(arr[i])}
        if len(arr) >= 10:
            seg = arr[-10:]
            idx = len(arr) - 10 + (np.argmax(seg) if mode == "high" else np.argmin(seg))
            return {
                "date": _to_date_int(dates[idx]),
                "price": float(seg[idx if mode == "high" else np.argmin(seg)]),
            }
        return None

    def _find_swing_points(self):
        recent = self.df.tail(StrategyConfig.SWING_WINDOW)
        return (
            self._find_swing(recent["high"].to_numpy(), recent["date"].to_numpy(), "high"),
            self._find_swing(recent["low"].to_numpy(), recent["date"].to_numpy(), "low"),
        )

    def _recent_extremes(self):
        if len(self.df) < 10:
            return None, None
        tail = self.df.tail(10)
        max_idx = tail["high"].idxmax()
        min_idx = tail["low"].idxmin()
        return (
            {
                "date": _to_date_int(tail.loc[max_idx, "date"]),
                "price": float(tail.loc[max_idx, "high"]),
            },
            {
                "date": _to_date_int(tail.loc[min_idx, "date"]),
                "price": float(tail.loc[min_idx, "low"]),
            },
        )

    def _key_close_levels(self):
        if len(self.df) < 20:
            return pd.DataFrame()
        recent = self.df.tail(StrategyConfig.KEY_CLOSE_WINDOW).copy()
        recent["ret"] = recent["close"] / recent["close"].shift(1) - 1
        recent["vol_ma20"] = recent["volume"].rolling(window=20).mean()
        mask = (
            (recent["ret"] >= StrategyConfig.KEY_CLOSE_RETURN_THRESHOLD)
            & (
                recent["high"] - recent["close"]
                <= StrategyConfig.KEY_CLOSE_NEAR_HIGH_RATIO * (recent["high"] - recent["low"])
            )
            & (recent["volume"] >= StrategyConfig.KEY_CLOSE_VOL_MULTIPLIER * recent["vol_ma20"])
        )
        result = recent[mask].sort_values("date", ascending=False).head(5)
        return result[["date", "close", "ret"]]

    def _acceleration_band(self):
        if len(self.df) < StrategyConfig.ACCEL_BOX_WINDOW + 1:
            return None
        recent = self.df.tail(StrategyConfig.ACCEL_WINDOW)
        closes = recent["close"].to_numpy()
        highs = recent["high"].to_numpy()
        lows = recent["low"].to_numpy()
        atrs = recent["atr"].to_numpy()
        has_vol = "volume" in recent.columns and recent["volume"].sum() > 0
        vols = recent["volume"].to_numpy() if has_vol else np.zeros(len(closes))
        vol_ma = (
            recent["volume"].rolling(window=20).mean().to_numpy()
            if has_vol
            else np.zeros(len(closes))
        )
        bw = StrategyConfig.ACCEL_BOX_WINDOW
        accel_idx = -1
        for i in range(len(closes) - 1, bw - 1, -1):
            price_ok = closes[i] > np.max(highs[i - bw : i])
            vol_ok = (
                vols[i] >= StrategyConfig.ACCEL_VOL_MULTIPLIER * vol_ma[i]
                if vol_ma[i] > 0
                else True
            )
            prev_atr = atrs[i - 1] if i > 0 and atrs[i - 1] > 0 else (highs[0] - lows[0])
            range_ok = (highs[i] - lows[i]) >= StrategyConfig.ACCEL_ATR_MULTIPLIER * prev_atr
            if price_ok and vol_ok and range_ok:
                accel_idx = i
                break
        if accel_idx < StrategyConfig.ACCEL_COST_WINDOW:
            return None
        cw = StrategyConfig.ACCEL_COST_WINDOW
        cost_slice = recent.iloc[accel_idx - cw : accel_idx]
        typical_price = (cost_slice["high"] + cost_slice["low"] + cost_slice["close"]) / 3.0
        if has_vol and cost_slice["volume"].sum() > 0:
            vwap = float((typical_price * cost_slice["volume"]).sum() / cost_slice["volume"].sum())
        else:
            vwap = float(cost_slice["close"].mean())
        atr_val = atrs[accel_idx - 1] if accel_idx > 0 and atrs[accel_idx - 1] > 0 else vwap * 0.02
        return {
            "accel_date": _to_date_int(recent["date"].iloc[accel_idx]),
            "vwap_center": vwap,
            "band_low": vwap - 0.5 * atr_val,
            "band_high": vwap + 0.5 * atr_val,
            "band_mid": vwap,
        }

    def _price_density(self):
        tail = self.df.tail(StrategyConfig.DENSITY_WINDOW).copy()
        tail["tp"] = (tail["high"] + tail["low"] + tail["close"]) / 3.0
        tail = tail[tail["tp"].notna() & (tail["tp"] > 0)].copy()
        n = len(tail)
        has_vol = "volume" in tail.columns and tail["volume"].sum() > 0
        weights = tail["volume"].to_numpy() if (n >= 10 and has_vol) else None
        if n < 10:
            return {"status": "NO_DATA", "boxes": [], "meta": {"n_effective": n}}
        tp = tail["tp"].to_numpy()
        lo, hi = tp.min(), tp.max()
        if StrategyConfig.DENSITY_USE_LOG_BINS and lo > 0:
            edges = np.logspace(np.log10(lo), np.log10(hi), StrategyConfig.DENSITY_BINS + 1)
        else:
            edges = np.linspace(lo, hi, StrategyConfig.DENSITY_BINS + 1)
        hist, _ = np.histogram(tp, bins=edges, weights=weights)
        if len(hist) == 0 or hist.max() == 0:
            return {"status": "NO_DATA", "boxes": [], "meta": {"n_effective": n}}
        peak_idx = np.argmax(hist)
        threshold = hist[peak_idx] * (1 - StrategyConfig.DENSITY_BAND_PERCENT)
        left = peak_idx
        while left > 0 and hist[left - 1] >= threshold:
            left -= 1
        right = peak_idx
        while right < len(hist) - 1 and hist[right + 1] >= threshold:
            right += 1
        return {
            "status": "OK",
            "boxes": [
                {
                    "box_low": float(edges[left]),
                    "box_high": float(edges[right + 1]),
                    "peak_low": float(edges[peak_idx]),
                    "peak_high": float(edges[peak_idx + 1]),
                }
            ],
            "meta": {"n_effective": n},
        }

    def _merge_levels(self, levels, atr_ref):
        valid = sorted(l for l in levels if l is not None and not np.isnan(l))
        if not valid:
            return []
        tick = StrategyConfig.get_tick_size(self.last_close)
        tol = max(
            tick * 2, min(0.01 * self.last_close, StrategyConfig.MERGE_ATR_TOLERANCE * atr_ref)
        )
        groups, cur = [], [valid[0]]
        for lv in valid[1:]:
            if abs(lv - np.mean(cur)) <= tol:
                cur.append(lv)
            else:
                groups.append(cur)
                cur = [lv]
        groups.append(cur)
        results = [{"level": float(np.mean(g)), "count": len(g), "members": g} for g in groups]
        results.sort(key=lambda x: (-x["count"], x["level"]))
        return results

    def _classify(self, swing_hi, swing_lo, key_closes, accel, density, recent_hi, recent_lo):
        raw = []
        windows = [5, 10, 20, 25, 60]
        valid_windows = [w for w in windows if len(self.df) >= w]
        if valid_windows:
            for w in valid_windows:
                ma = self.df["close"].rolling(window=w).mean().iloc[-1]
                if ma is not None:
                    raw.append(float(ma))
        if len(self.df) >= 2:
            prev = self.df.iloc[-2]
            P = (prev["high"] + prev["low"] + prev["close"]) / 3
            raw.extend(
                [
                    P,
                    2 * P - prev["low"],
                    2 * P - prev["high"],
                    P + (prev["high"] - prev["low"]),
                    P - (prev["high"] - prev["low"]),
                ]
            )
        if len(self.df) > 0:
            cur = self.df.iloc[-1]
            c_val, h_val, l_val = float(cur["close"]), float(cur["high"]), float(cur["low"])
            atr_val = None
            if "atr" in self.df.columns and self.df["atr"].iloc[-1] is not None:
                try:
                    import math

                    temp = float(self.df["atr"].iloc[-1])
                    if not math.isnan(temp):
                        atr_val = temp
                except Exception as exc:
                    logging.debug(
                        "atr_val 計算失敗 (stock=%s, err=%s)",
                        getattr(exc, "__cause__", None) or str(exc),
                    )
                    pass
            if atr_val is None:
                atr_val = c_val * 0.02
            p_val = (h_val + l_val + c_val) / 3.0
            raw.extend(
                [2.0 * p_val - l_val, p_val + (h_val - l_val), h_val + 2.0 * (p_val - l_val)]
            )
            raw.extend(
                [2.0 * p_val - h_val, p_val - (h_val - l_val), l_val - 2.0 * (h_val - p_val)]
            )
            raw.extend(
                [c_val + atr_val, c_val + 2.0 * atr_val, c_val - atr_val, c_val - 2.0 * atr_val]
            )
        for ext in (recent_hi, recent_lo):
            if ext:
                raw.append(ext["price"])
        for sw in (swing_hi, swing_lo):
            if sw:
                raw.append(sw["price"])
        if not key_closes.empty:
            raw.extend(key_closes["close"].tolist())
        if density["status"] == "OK" and density["boxes"]:
            b = density["boxes"][0]
            raw.extend([b["box_high"], b["box_low"]])
        if accel:
            raw.extend([accel["band_low"], accel["band_mid"], accel["band_high"]])
        return [c for c in raw if c > self.last_close], [c for c in raw if c < self.last_close]

    def analyze(self):
        if self.df.empty:
            return {}
        try:
            swing_hi, swing_lo = self._find_swing_points()
            recent_hi, recent_lo = self._recent_extremes()
            if recent_hi and (not swing_hi or recent_hi["price"] > swing_hi["price"]):
                swing_hi = recent_hi
            if recent_lo and (not swing_lo or recent_lo["price"] < swing_lo["price"]):
                swing_lo = recent_lo
            key_closes = self._key_close_levels()
            accel = self._acceleration_band()
            density = self._price_density()
            res_cand, sup_cand = self._classify(
                swing_hi, swing_lo, key_closes, accel, density, recent_hi, recent_lo
            )
            atr_col = self.df["atr"]
            atr_ref = (
                float(atr_col.iloc[-1])
                if atr_col.iloc[-1] is not None and not np.isnan(atr_col.iloc[-1])
                else self.last_close * 0.02
            )
            merged_r = self._merge_levels(res_cand, atr_ref)
            merged_s = self._merge_levels(sup_cand, atr_ref)
            merged_r.sort(key=lambda x: abs(x["level"] - self.last_close))
            merged_s.sort(key=lambda x: abs(x["level"] - self.last_close))
            nearest_r = self._nearest(merged_r, above=True)
            nearest_s = self._nearest(merged_s, above=False)
            ma25 = (
                float(self.df["close"].rolling(window=25).mean().iloc[-1])
                if len(self.df) >= 25
                else self.last_close
            )
            std25 = (
                float(self.df["close"].rolling(window=25).std().iloc[-1])
                if len(self.df) >= 25
                else 0
            )
            return {
                "latest_date": _to_date_int(self.df["date"].iloc[-1]),
                "last_close": float(self.last_close),
                "atr14": float(atr_ref),
                "ma25": float(ma25) if ma25 is not None else float(self.last_close),
                "std25": float(std25) if std25 is not None else 0.0,
                "recent_resistance_swing_high": swing_hi,
                "recent_support_swing_low": swing_lo,
                "key_close_levels_top5": key_closes,
                "acceleration_support_band": accel,
                "price_density_box": density,
                "merged_resistance_levels": merged_r,
                "merged_support_levels": merged_s,
                "nearest_resistance": nearest_r,
                "nearest_support": nearest_s,
            }
        except Exception as e:
            console.print(f"[red]分析錯誤: {e}[/red]")
            return {}

    def _nearest(self, merged, above):
        margin = StrategyConfig.MIN_DISTANCE_PERCENT
        if above:
            valid = [g["level"] for g in merged if g["level"] > self.last_close * (1 + margin)]
            if valid:
                return min(valid)
            all_highs = []
            h = self.df["high"].to_numpy()
            left, right = StrategyConfig.SWING_LEFT, StrategyConfig.SWING_RIGHT
            if len(h) >= left + right + 1:
                for i in range(left, len(h) - right):
                    win = h[i - left : i + right + 1]
                    if len(win) > 0 and h[i] == np.max(win):
                        all_highs.append(float(h[i]))
            valid_highs = [hv for hv in all_highs if hv > self.last_close * (1 + margin)]
            if valid_highs:
                return min(valid_highs)
            if not self.df.empty:
                abs_max = float(self.df["high"].max())
                if abs_max and abs_max > self.last_close * (1 + margin):
                    return abs_max
            return None
        else:
            valid = [g["level"] for g in merged if g["level"] < self.last_close * (1 - margin)]
            if valid:
                return max(valid)
            all_lows = []
            l = self.df["low"].to_numpy()
            left, right = StrategyConfig.SWING_LEFT, StrategyConfig.SWING_RIGHT
            if len(l) >= left + right + 1:
                for i in range(left, len(l) - right):
                    win = l[i - left : i + right + 1]
                    if len(win) > 0 and l[i] == np.min(win):
                        all_lows.append(float(l[i]))
            valid_lows = [lv for lv in all_lows if lv < self.last_close * (1 - margin)]
            if valid_lows:
                return max(valid_lows)
            if not self.df.empty:
                abs_min = float(self.df["low"].min())
                if abs_min and abs_min < self.last_close * (1 - margin):
                    return abs_min
            return None


def _render_header(title):
    render_header(title, console=console)


def _clear_screen():
    clear_screen()


def _get_stock_name(conn, stock_id):
    return get_stock_name(conn, stock_id, FALLBACK_NAMES)


def _fetch_history(conn, code, limit=512):
    """向後相容包裝：委託 _utils.fetch_klines。"""
    return fetch_klines(conn, code, limit)


def _render_mobile_sr(data, code, name):
    console.print(f"[dim]{'─ 1 撐壓 ' + code + ' ' + name}{'─' * 20}[/]")
    close = data.get("last_close", 0)
    atr = data.get("atr14", 0)
    console.print(f"收盤 {close:.2f} ATR {atr:.2f}")
    supports = data.get("merged_support_levels", [])
    resistances = data.get("merged_resistance_levels", [])
    if supports:
        parts = "|".join(f"{s['level']:.2f}(強:{s['count']})" for s in supports[:3])
        console.print(f"[bright_green]綜合支撐: {parts}[/]")  # 支撐：綠
    if resistances:
        parts = "|".join(f"{r['level']:.2f}(強:{r['count']})" for r in resistances[:3])
        console.print(f"[bright_red]綜合壓力: {parts}[/]")  # 壓力：紅
    s_range = data.get("acceleration_support_band")
    if s_range:
        console.print(f"加速帶 {s_range['band_low']:.2f}~{s_range['band_high']:.2f}")
    recent_res, recent_sup = data.get("recent_resistance_swing_high"), data.get(
        "recent_support_swing_low"
    )
    if recent_res or recent_sup:
        console.print(
            f"前高 {(recent_res['price'] if recent_res else 0):.2f} / 前低 {(recent_sup['price'] if recent_sup else 0):.2f}"
        )


def display_stock_analysis(conn, symbol, name, df, compact=False, mobile=False):
    try:
        engine = SupportResistanceEngine(df)
        data = engine.analyze()
        if not data:
            console.print("[red]❌ 無法計算資料[/red]")
            return
        if mobile:
            _render_mobile_sr(data, symbol, name)
            return
        if not compact:
            _render_header(f"{symbol} {name} 撐壓簡報")
            _show_market_overview(data, df)
        _show_indicators(data)
        _show_extras(data)
    except Exception as e:
        console.print(f"[red]❌ 顯示錯誤: {e}[/red]")


def _show_market_overview(data, df):
    cur = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else cur
    console.print("\n[bold]🔹 市場概況[/bold]")
    console.print(f"收盤: {price_rich(cur['close'], prev['close'])}")
    console.print(f"成交: {vol_fmt(int(cur.get('volume', 0)))}")


def _calc_levels(levels, is_resistance, lc):
    if levels:
        if is_resistance:
            return levels[0], levels[1] if len(levels) >= 3 else levels[0], levels[-1]
        else:
            return levels[-1], levels[-2] if len(levels) >= 3 else levels[-1], levels[0]
    else:
        if is_resistance:
            return lc * 1.02, lc * 1.05, lc * 1.15
        else:
            return lc * 0.98, lc * 0.95, lc * 0.85


def _show_indicators(data):
    lc = data["last_close"]
    all_levels = [
        x["level"]
        for x in data.get("merged_resistance_levels", []) + data.get("merged_support_levels", [])
    ]
    res_lvls = sorted([l for l in all_levels if l > lc])
    sup_lvls = sorted([l for l in all_levels if l < lc])
    nr_val, short_res_val, long_res_val = _calc_levels(res_lvls, True, lc)
    ns_val, short_sup_val, long_sup_val = _calc_levels(sup_lvls, False, lc)
    console.print("\n[bold]📊 綜合撐壓標[/bold]")
    console.print(
        f"前高/短期/長期壓力：[bright_red]{nr_val:.2f}/{short_res_val:.2f}/{long_res_val:.2f}[/]"
    )  # 壓力：紅
    console.print(
        f"前低/短期/長期支撐：[bright_green]{ns_val:.2f}/{short_sup_val:.2f}/{long_sup_val:.2f}[/]"
    )  # 支撐：綠


def _show_extras(data):
    accel = data["acceleration_support_band"]
    if accel:
        console.print(
            f"vsbc(加速起漲): {accel['band_low']:.2f}~{accel['band_high']:.2f}(中心:{accel['vwap_center']:.2f})"
        )
    density = data["price_density_box"]
    if density["status"] == "OK" and density["boxes"]:
        b = density["boxes"][0]
        console.print(f"vop(量價密集): {b['box_low']:.2f}~{b['box_high']:.2f}")


def scan_market_stocks(conn, min_volume_zhang=StrategyConfig.DEFAULT_MIN_VOLUME, init_filter=None):
    """全市場掃描"""
    # stock_history.volume 單位為股，min_volume_zhang 單位為張（1張=1000股）
    min_volume = min_volume_zhang * 1000
    try:
        latest_date = conn.execute("SELECT MAX(date) FROM stock_history").fetchone()[0]
        if not latest_date:
            console.print("[red]❌ 無法獲取資料庫日期[/red]")
            return
    except Exception as e:
        console.print(f"[red]❌ 資料庫錯誤: {e}[/red]")
        return
    if (
        _SR_CACHE["date"] == latest_date
        and _SR_CACHE["min_volume"] == min_volume
        and _SR_CACHE["results"] is not None
        and time.time() - _SR_CACHE.get("ts", 0) < _CACHE_TTL
    ):
        all_scored = _SR_CACHE["results"]
        console.print(
            f"\n[green]⚡ 已載入今日撐壓分析掃描快取數據 (基準日: {latest_date}) [0.00s][/green]"
        )
    else:
        try:
            rows = conn.execute(
                "SELECT stock_id FROM stock_history WHERE date = ? AND volume >= ? AND stock_id GLOB '[1-9][0-9][0-9][0-9]'",
                (latest_date, min_volume),
            ).fetchall()
            stocks = [r[0] for r in rows]
        except Exception as e:
            console.print(f"[red]❌ 查詢失敗: {e}[/red]")
            return
        if not stocks:
            console.print("[yellow]📭 未找到符合條件的股票[/yellow]")
            return
        try:
            meta_rows = conn.execute("SELECT stock_id, stock_name FROM stock_meta").fetchall()
            name_map = {r[0]: r[1] for r in meta_rows}
        except Exception as exc:
            logging.debug("name_map 載入失敗: %s", exc)
            name_map = {}
        all_scored = _scan_with_progress_basic(conn, stocks, name_map, min_volume)
        _SR_CACHE["date"], _SR_CACHE["min_volume"], _SR_CACHE["results"], _SR_CACHE["ts"] = (
            latest_date,
            min_volume,
            all_scored,
            time.time(),
        )

    if not all_scored:
        console.print("[yellow]📭 未發現符合基本條件的標的[/yellow]")
        return

    console.print(f"\n[green]✅ 掃描完成：共 {len(all_scored)} 檔符合基本條件[/green]")
    console.print(f"資料庫日期：{latest_date} │ 最小成交量：{min_volume_zhang:,} 張")

    # 初始篩選（外部指定）
    labels = {
        "poc": "POC量價密集區",
        "vwap": "VWAP",
        "long_sup": "長期支撐",
        "short_sup": "短期支撐",
        "front_low": "前低支撐",
    }
    current_results = all_scored[:]
    current_filters = []
    if init_filter:
        filtered = [r for r in all_scored if _passes_filter(r, init_filter)]
        if filtered:
            current_results = filtered
            current_filters = [init_filter]
            sample = filtered[0]
            low_val = sample.get("filter_levels", {}).get(init_filter, 0)
            console.print(
                f"[green]✅ 已套用 {labels[init_filter]} 篩選：{len(filtered)} / {len(all_scored)} 檔[/green]"
            )
        else:
            console.print(f"[yellow]⚠️ 沒有股票符合 {labels[init_filter]} 篩選條件[/yellow]")

    # 初始掃描結果先顯示
    current_results.sort(key=lambda x: x["dist"] if x["dist"] else 0)
    _display_results(current_results, latest_date, "1", min_volume_zhang, current_filters)

    while True:
        console.print("\n[bold yellow]📋 選擇進階篩選條件（套用後重新顯示結果）：[/bold yellow]")
        console.print("  [1] POC 量價密集區上10%")
        console.print("  [2] VWAP上10%")
        console.print("  [3] 長期支撐上10%")
        console.print("  [4] 短期支撐上10%")
        console.print("  [5] 前低支撐上10%")
        console.print("  [Enter] 結束篩選")
        console.print("👉 ", end="")

        ch = get_blocking_key()
        if not ch:
            break

        filter_map = {"1": "poc", "2": "vwap", "3": "long_sup", "4": "short_sup", "5": "front_low"}
        if ch in filter_map:
            key = filter_map[ch]
            filtered = [r for r in all_scored if _passes_filter(r, key)]
            if filtered:
                current_results = filtered
                current_filters = [key]
                sample = filtered[0]
                low_val = sample.get("filter_levels", {}).get(key, 0)
                console.print(
                    f"[green]✅ 已套用 {labels[key]} 篩選：{len(filtered)} / {len(all_scored)} 檔 (低點 {low_val:.2f}，價格 ≤ {low_val * 1.1:.2f})[/green]"
                )
            else:
                console.print(f"[yellow]⚠️ 沒有股票符合 {labels[key]} 篩選條件[/yellow]")
                continue
        else:
            console.print("[red]無效選擇[/red]")
            continue

        current_results.sort(key=lambda x: x["dist"] if x["dist"] else 0)
        _display_results(current_results, latest_date, "1", min_volume_zhang, current_filters)


def _passes_filter(r, key, threshold=10.0):
    levels = r.get("filter_levels", {})
    low = levels.get(key)
    if low is None or low <= 0:
        return False
    price = r["close"]
    return low <= price <= low * (1 + threshold / 100)


def _scan_with_progress_basic(conn, stocks, name_map, min_volume=StrategyConfig.DEFAULT_MIN_VOLUME):
    results = []
    with Progress(
        SpinnerColumn(), TextColumn("[cyan]Scanning..."), BarColumn(), TimeElapsedColumn()
    ) as prog:
        task = prog.add_task("掃描市場", total=len(stocks))
        for code in stocks:
            try:
                r = _analyze_one(conn, code, name_map)
                if r:
                    scored = _score(r["code"], r["name"], r["analysis"], r["df"])
                    if scored and scored.get("raw_vol", 0) >= min_volume:
                        results.append(scored)
            except Exception:
                pass
            prog.advance(task)
    return results


def _analyze_one(conn, code, name_map):
    df = _fetch_history(conn, code)
    if len(df) < 60:
        return None
    engine = SupportResistanceEngine(df)
    result = engine.analyze()
    if not result:
        return None
    return {
        "code": code,
        "name": name_map.get(code) or FALLBACK_NAMES.get(code, "---"),
        "analysis": result,
        "df": df,
    }


def _score(code, name, a, df):
    price = a["last_close"]
    prev_close = float(df["close"].iloc[-2]) if len(df) >= 2 else price
    vol = float(df["volume"].iloc[-1]) if "volume" in df.columns else 0
    tags, score = [], 0

    ns = a["nearest_support"]
    dist = ((price - ns) / ns * 100) if ns else float("inf")
    if ns:
        if dist <= 2.0:
            tags.append("近支撐")
            score += 1
        tags.append("有支撐")
        score += 1
    else:
        return None
    if not ns or dist > StrategyConfig.MAX_DISTANCE_PERCENT:
        return None

    if a["acceleration_support_band"]:
        tags.append("加速帶")
        score += 1
    boxes = a.get("price_density_box", {}).get("boxes", [])
    if boxes and boxes[0]["box_low"] * 0.98 <= price <= boxes[0]["box_high"] * 1.02:
        tags.append("密集區")
        score += 1
    for g in a.get("merged_support_levels", []):
        if g["count"] >= 2:
            tags.append("強支撐")
            score += 2

    filter_levels = {}

    if boxes:
        filter_levels["poc"] = boxes[0]["box_low"]

    # VWAP 濾網：收盤在 VWAP 上方 10% 以內
    accel_band = a.get("acceleration_support_band")
    if accel_band:
        vwap_val = accel_band.get("vwap_center")
        if vwap_val and vwap_val > 0:
            filter_levels["vwap"] = vwap_val

    merged_s = a.get("merged_support_levels", [])
    if merged_s:
        filter_levels["long_sup"] = merged_s[0]["level"]

    ns = a.get("nearest_support")
    if ns:
        filter_levels["short_sup"] = ns

    sw_lo = a.get("recent_support_swing_low")
    if sw_lo:
        filter_levels["front_low"] = sw_lo["price"]

    return {
        "code": code,
        "name": name,
        "close": price,
        "prev_close": prev_close,
        "vol": int(vol),
        "raw_vol": int(vol),
        "amount": (price * vol) / 1e8,
        "dist": dist,
        "tags": "/".join(tags),
        "score": score,
        "nearest_s": ns,
        "filter_levels": filter_levels,
    }


def _display_results(
    results,
    latest_date=0,
    sort_choice="1",
    min_volume=StrategyConfig.DEFAULT_MIN_VOLUME,
    current_filters=None,
):
    if not results:
        console.print("[yellow]📭 未發現符合條件的標的[/yellow]")
        return
    sort_names = {"1": "距支撐由近到遠", "2": "成交金額由大到小"}
    ds = str(latest_date)
    if len(ds) == 8:
        ds = f"{ds[:4]}-{ds[4:6]}-{ds[6:]}"

    title_line = f"📈 系統掃描結果 (排序: {sort_names.get(sort_choice, '距支撐由近到遠')})"

    labels = {
        "poc": "POC",
        "vwap": "VWAP",
        "long_sup": "長期支撐",
        "short_sup": "短期支撐",
        "front_low": "前低支撐",
    }
    dist_labels = {
        "poc": "POC數值",
        "vwap": "VWAP數值",
        "long_sup": "長期支撐數值",
        "short_sup": "短期支撐數值",
        "front_low": "前低數值",
    }
    if current_filters:
        filter_label = " + ".join(labels.get(k) or k for k in current_filters)
        dist_col = dist_labels.get(current_filters[0], "距支撐")
    else:
        filter_label = f"距支撐≤{StrategyConfig.MAX_DISTANCE_PERCENT:.0f}%"
        dist_col = "距支撐"

    filter_line = (
        f"資料庫日期：{ds} │ "
        f"最小成交量：{min_volume:,} 張 │ "
        f"篩選：{filter_label} │ "
        f"共 {len(results)} 檔"
    )
    console.print(f"[dim]{filter_line}[/dim]")
    table = Table(
        title=title_line,
        box=box.SIMPLE,
        border_style="green",
        expand=False,
        padding=(0, 0),
        title_style="bold white",
    )
    for col, style, nw in [
        ("代號", "magenta", True),
        ("名稱", "white", False),
        ("收盤", "bright_yellow", True),
        ("成交張數", "white", True),
        ("額(億)", "yellow", True),
        (dist_col, "bright_red", True),
    ]:
        table.add_column(
            col, justify="left", style=style, no_wrap=nw, overflow="fold" if not nw else None
        )
    for r in results[: StrategyConfig.MAX_SCAN_RESULTS]:
        if current_filters:
            lv = r.get("filter_levels", {})
            key = current_filters[0]
            filter_val = lv.get(key)
            if filter_val and filter_val > 0:
                dist_display = f"{filter_val:.2f}"
            else:
                dist_display = "-"
        else:
            dist_val = r.get("dist")
            if dist_val is not None:
                dist_color = "bright_red" if dist_val >= 0 else "bright_green"
                dist_display = f"[{dist_color}]{dist_val:+.2f}%[/]"
            else:
                dist_display = "-"
        # 收盤價著色（統一 price_color）
        price_change = r["close"] - r.get("prev_close", r["close"])
        prev_close = r.get("prev_close", r["close"])
        pct = (price_change / prev_close * 100) if prev_close else 0.0
        row_close = f"[{price_color(price_change, pct)}]{r['close']:.2f}[/]"
        # 成交量著色（統一 vol_color，張數比較）
        vol_sheets = r["vol"] // 1000
        prev_vol_sheets = r.get("prev_vol", r["vol"]) // 1000
        vol_str = f"[{vol_color(vol_sheets, prev_vol_sheets)}]{vol_sheets:,}[/]"
        table.add_row(r["code"], r["name"], row_close, vol_str, f"{r['amount']:.2f}", dist_display)
    console.print(table)


def main():
    try:
        conn = get_connection(readonly=True)
        signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
        while True:
            try:
                _handle_input(conn)
            except KeyboardInterrupt:
                break
            except Exception as e:
                console.print(f"[red]❌ 執行錯誤: {e}[/red]")
                time.sleep(2)
    except Exception as e:
        console.print(f"[red]❌ 啟動失敗: {e}[/red]")
    finally:
        if "conn" in locals():
            conn.close()


def _handle_input(conn):
    _clear_screen()
    _render_header("📘 撐壓分析系統 v3.2")
    console.print("指令: [4碼]查詢 | [Enter]近支撐掃描 | [0]退出")
    cmd = console.input("🔍 指令: ").strip()
    if cmd == "0":
        sys.exit(0)
    elif not cmd:
        vol_input = console.input("📊 最小量(預設500): ").strip()
        min_vol_zhang = int(vol_input) if vol_input.isdigit() else StrategyConfig.DEFAULT_MIN_VOLUME
        scan_market_stocks(conn, min_vol_zhang)
        input("\n按Enter返回...")
    elif len(cmd) == 4 and cmd.isdigit():
        df = _fetch_history(conn, cmd)
        if df.empty:
            console.print("[red]❌ 查無資料[/red]")
            time.sleep(1)
            return
        df = df.sort_values("date").reset_index(drop=True)
        name = _get_stock_name(conn, cmd)
        display_stock_analysis(conn, cmd, name, df)
        input("\n按Enter返回...")
    else:
        console.print("[red]❌ 指令錯誤[/red]")
        time.sleep(1)


def get_latest_date() -> str:
    """供 strategies.py 查詢資料基準日"""
    conn = get_connection(readonly=True)
    try:
        return conn.execute("SELECT MAX(date) FROM stock_history").fetchone()[0]
    finally:
        conn.close()


def run_strategy(params):
    code = params.get("code")
    scan = params.get("scan", False)
    vol = params.get("vol", StrategyConfig.DEFAULT_MIN_VOLUME)
    init_filter = params.get("filter")
    compact = params.get("compact", False)
    mobile = params.get("mobile", False)
    conn = get_connection(readonly=True)
    try:
        if scan:
            scan_market_stocks(conn, vol, init_filter=init_filter)
        elif code:
            df = _fetch_history(conn, code)
            if df.empty:
                console.print("[red]❌ 查無資料[/red]")
                return
            name = _get_stock_name(conn, code)
            display_stock_analysis(conn, code, name, df, compact=compact, mobile=mobile)
        else:
            main()
    finally:
        conn.close()


def get_sr_levels(code):
    try:
        conn = get_connection(readonly=True)
        df = _fetch_history(conn, code)
        conn.close()
        if df.empty:
            return {}
        engine = SupportResistanceEngine(df)
        result = engine.analyze()
        return {
            "short_resistance": result.get("nearest_resistance"),
            "short_support": result.get("nearest_support"),
        }
    except Exception as exc:
        logging.debug("get_sr_levels 失敗 (code=%s): %s", code, exc)
        return {}


class SupportResistanceStrategy:
    """撐壓策略 wrapper - 提供統一的 analyze() 介面。"""

    def analyze(self, stock_id: str) -> dict:
        """分析撐壓信號。回傳 strategy/stock_id/signal。"""
        conn = get_connection(readonly=True)
        try:
            df = _fetch_history(conn, stock_id)
            if df.empty:
                return {
                    "strategy": "sr",
                    "stock_id": stock_id,
                    "signal": "neutral",
                    "reason": "無資料",
                }
            engine = SupportResistanceEngine(df)
            result = engine.analyze()

            # 根據最近支撐/壓力與現價的關係判斷信號
            nearest_res = result.get("nearest_resistance")
            nearest_sup = result.get("nearest_support")
            last_close = float(df["close"].iloc[-1]) if not df.empty else 0

            if nearest_res and last_close > nearest_res:
                signal = "bullish"
            elif nearest_sup and last_close < nearest_sup:
                signal = "bearish"
            else:
                signal = "neutral"

            return {
                "strategy": "sr",
                "stock_id": stock_id,
                "signal": signal,
                "nearest_resistance": nearest_res,
                "nearest_support": nearest_sup,
            }
        except Exception:
            return {
                "strategy": "sr",
                "stock_id": stock_id,
                "signal": "neutral",
            }
        finally:
            conn.close()


if __name__ == "__main__":
    main()
