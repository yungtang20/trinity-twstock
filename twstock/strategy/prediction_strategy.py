#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略整合_預測分析 v3.3 (統一資料庫版)
# [AI MOD] Migrated to taiwan_stock_unified.db + klines view
"""

import os
import signal
import sqlite3
import sys
import time
import warnings
from typing import TYPE_CHECKING, Dict, List

import pandas as pd
from rich import box
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

# [AI MOD] Import from sibling modules
from twstock.strategy._utils import fetch_klines

# [AI MOD] 集中式 Console：解決 Windows cp950 無法渲染 emoji 的問題
from twstock.terminal import rconsole

try:
    from twstock.strategy.patterns_strategy import StockPredictionAnalyzer
except ImportError:
    StockPredictionAnalyzer = None

# [AI MOD] AI Prediction session scan cache to make switching sorting instantly fast
_CACHE_TTL = 300  # 5 分鐘
_PRED_CACHE = {
    "date": None,
    "min_volume": None,
    "results": None,
    "ts": 0,
}

# Import shared engine components to eliminate duplication
if TYPE_CHECKING:
    from twstock.strategy.kronos_engine import (
        DEFAULT_CONFIG,
        DriftMonitor,
        DriftStatus,
        KronosRealEngine,
        MonteCarloEngine,
        PredictionChartRenderer,
        PredictionEngine,
        PredictionResult,
        StockPrediction,
        calculate_price_change,
        load_kronos,
    )
else:
    try:
        from twstock.strategy.kronos_engine import (
            DEFAULT_CONFIG,
            DriftMonitor,
            DriftStatus,
            KronosRealEngine,
            MonteCarloEngine,
            PredictionChartRenderer,
            PredictionEngine,
            PredictionResult,
            StockPrediction,
            calculate_price_change,
            load_kronos,
        )
    except ImportError as e:
        # kronos_engine requires torch - not available in test env
        warnings.warn(f"kronos_engine import failed: {e}", stacklevel=2)
        DEFAULT_CONFIG = None
        DriftMonitor = None
        DriftStatus = None
        KronosRealEngine = None
        MonteCarloEngine = None
        PredictionChartRenderer = None
        PredictionEngine = None
        PredictionResult = None
        StockPrediction = None
        calculate_price_change = None
        load_kronos = None

warnings.filterwarnings("ignore")

# ── Module path ───────────────────────────────────────────
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_TWSTOCK_DIR = os.path.abspath(os.path.join(_CURRENT_DIR, ".."))
if _TWSTOCK_DIR not in sys.path:
    sys.path.insert(0, _TWSTOCK_DIR)

from twstock.db import get_connection  # [AI MOD]
from twstock.display import price_color, vol_color  # [AI MOD]
from twstock.strategy._utils import clear_screen, get_stock_name, render_header

try:
    from twstock.input_helper import get_blocking_key
except ImportError:
    from input_helper import get_blocking_key  # type: ignore[no-redef]


# ── Local helpers ─────────────────────────────────────────


def _render_header(title, is_detail=False):
    render_header(title, is_detail=is_detail, console=rconsole)


def _clear_screen():
    clear_screen()


def _wait_for_enter():
    rconsole.input("\n按 Enter 繼續...")


def _get_stock_name(conn, stock_id):
    return get_stock_name(conn, stock_id)


def _render_kronos_prediction(df, code: str, name: str, engine: PredictionEngine, skipped_list: List[str] | None = None):
    """繪製 Kronos 5 日價格預測結果"""
    try:
        # Kronos 需要 DatetimeIndex；若 df 的 date 欄位是字串，先轉換
        work = df.copy()
        if not isinstance(work.index, pd.DatetimeIndex):
            if "date" in work.columns:
                work["date"] = pd.to_datetime(work["date"])
                work = work.set_index("date")
            else:
                work.index = pd.to_datetime(work.index)
        # 確保 index 是 monotonic increasing
        work = work.sort_index()

        # 衛兵：如果 Kronos 不可用，使用 Monte Carlo fallback
        if engine.kronos_engine is None or not engine.kronos_engine.ready:
            if MonteCarloEngine is None:
                if skipped_list is not None:
                    skipped_list.append(code)
                rconsole.print("[yellow]⚠️ Kronos 和 Monte Carlo 引擎皆不可用，跳過預測[/]")
                return
            mc = MonteCarloEngine()
            pred = mc.predict(work, engine.config)
            rconsole.print()
            rconsole.print(
                Panel(
                    f"[bold bright_white]{code} {name} Monte Carlo 5 日價格預測 (Kronos fallback)[/]",
                    border_style="bright_cyan",
                    box=box.DOUBLE,
                )
            )
            rconsole.print(
                f"[dim]  Kronos 未就緒，使用 Monte Carlo fallback: {pred.benchmark:.2f} (信心 {pred.confidence:.1%})[/]"
            )
        else:
            pred = engine.kronos_engine.predict(work, engine.config)
            current = float(work["close"].iloc[-1])
            rconsole.print()
            rconsole.print(
                Panel(
                    f"[bold bright_white]{code} {name} Kronos 5 日價格預測[/]",
                    border_style="bright_magenta",
                    box=box.DOUBLE,
                )
            )

            # 绘制預測表格
            table = Table(box=box.SIMPLE, border_style="magenta")
            table.add_column("日次", justify="center")
            table.add_column("預測收盤", justify="right")
            table.add_column("變化", justify="right")
            series = pred.pred_series or [pred.benchmark]
            for i, p in enumerate(series, 1):
                chg = (p - current) / current if current > 0 else 0.0
                color = "bright_red" if chg > 0 else "bright_green" if chg < 0 else "white"
                table.add_row(f"T+{i}", f"{p:.2f}", f"[{color}]{chg:+.2%}[/]")
            rconsole.print(table)

            direction = "偏多" if pred.drift > 0 else "偏空" if pred.drift < 0 else "中性"
            dc = "bright_red" if pred.drift > 0 else "bright_green" if pred.drift < 0 else "white"
            rconsole.print(
                f"  當前: {current:.2f}  目標: {pred.benchmark:.2f}  "
                f"預期: [{dc}]{direction} ({pred.drift:+.2%})[/]  "
                f"信心: {pred.confidence:.1%}"
            )
    except Exception as e:
        rconsole.print(f"[red]❌ Kronos 預測失敗: {e}[/]")


class MarketScanner:

    def __init__(self, conn: sqlite3.Connection, config: Dict = None):
        if DEFAULT_CONFIG is None or MonteCarloEngine is None or PredictionEngine is None:
            raise RuntimeError("kronos_engine 未安裝或匯入失敗，此功能需要 torch")
        self.conn = conn
        self.config = DEFAULT_CONFIG.copy()
        if config:
            self.config.update(config)
        self.mc_engine = MonteCarloEngine()
        # 優先使用 Kronos，失敗則 fallback 到 Monte Carlo
        self.engine = PredictionEngine(self.config)
        self.uses_kronos = self.engine.kronos_engine is not None and self.engine.kronos_engine.ready

    def scan_market(self, min_volume: int = 500) -> None:
        try:
            latest_date = self.conn.execute("SELECT MAX(date) FROM stock_history").fetchone()[0]
            if not latest_date:
                rconsole.print("[yellow]⚠️ 無行情數據[/]")
                return

            # Check cache hit
            if (
                _PRED_CACHE["date"] == latest_date
                and _PRED_CACHE["min_volume"] == min_volume
                and _PRED_CACHE["results"] is not None
                and time.time() - _PRED_CACHE.get("ts", 0) < _CACHE_TTL
            ):
                preds = _PRED_CACHE["results"]
                rconsole.print(
                    f"\n[green]⚡ 已載入今日AI預測掃描快取數據 (基準日: {latest_date}) [0.00s][/green]"
                )
            else:
                stock_ids = self._get_targets(latest_date, min_volume)
                if not stock_ids:
                    rconsole.print("[yellow]⚠️ 無符合成交量門檻的標的[/]")
                    return

                name_mapping = dict(
                    self.conn.execute("SELECT stock_id, stock_name FROM stock_meta").fetchall()
                )

                preds = self._analyze_stocks(stock_ids, name_mapping)

                # Store in session cache
                _PRED_CACHE["date"] = latest_date
                _PRED_CACHE["min_volume"] = min_volume
                _PRED_CACHE["results"] = preds
                _PRED_CACHE["ts"] = time.time()

            sort_choice = "1"
            if preds:
                rconsole.print("\n[bold yellow]📊 請選擇掃描結果排序方式 (單鍵輸入):[/bold yellow]")
                rconsole.print("  [1] 距潛力估值由大到小 (預設)")  # [AI MOD]
                rconsole.print("  [2] 成交量(%)由大到小")
                ch = get_blocking_key()
                if ch in ("1", "2"):
                    sort_choice = ch

                if sort_choice == "1":
                    preds.sort(key=lambda x: x.score, reverse=True)  # [AI MOD]
                elif sort_choice == "2":
                    preds.sort(key=lambda x: x.amount, reverse=True)

            self._display_results(preds, latest_date, sort_choice)

        except Exception as e:
            rconsole.print(f"[red]❌ 掃描失敗: {e}[/]")

    def _get_targets(self, latest_date: str, min_volume: int) -> List[str]:
        # min_volume 單位為張，stock_history.volume 單位為股（1張=1000股）
        min_volume_shares = min_volume * 1000
        rows = self.conn.execute(
            "SELECT stock_id FROM stock_history "
            "WHERE date = ? AND volume >= ? AND stock_id GLOB '[1-9][0-9][0-9][0-9]'",
            (latest_date, min_volume_shares),
        ).fetchall()
        return [r[0] for r in rows]

    def _analyze_stocks(
        self, stock_ids: List[str], name_mapping: Dict[str, str]
    ) -> List[StockPrediction]:
        preds = []
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]🚀 正在對全市場進行預測分析中..."),
            BarColumn(),
            TimeElapsedColumn(),
            console=rconsole,
        ) as progress:
            task = progress.add_task("scan", total=len(stock_ids))

            for code in stock_ids:
                try:
                    df = fetch_klines(self.conn, code, limit=60)
                    df = df.dropna(subset=["close"]).sort_values("date")
                    if len(df) < 20:
                        progress.advance(task)
                        continue

                    pred = self.engine.predict(df, self.config)

                    price = float(df["close"].iloc[-1])  # [AI MOD] 使用原始價
                    target = pred.benchmark
                    vol = float(df["volume"].iloc[-1])

                    if price <= 0:
                        progress.advance(task)
                        continue

                    prev_price = float(df["close"].iloc[-2]) if len(df) > 1 else price
                    prev_vol = (
                        float(df["volume"].iloc[-2])
                        if len(df) > 1
                        else float(df["volume"].iloc[-1])
                    )

                    preds.append(
                        StockPrediction(
                            code=code,
                            name=name_mapping.get(code, "-"),
                            current_price=price,
                            volume=int(vol),
                            amount=(price * vol) / 100_000_000,
                            score=(target - price) / price,
                            target_price=target,
                            confidence=pred.confidence,
                            prev_price=prev_price,
                            prev_volume=prev_vol,
                        )
                    )
                except Exception:
                    pass
                progress.advance(task)

        return preds

    def _display_results(
        self, preds: List[StockPrediction], latest_date: str, sort_choice: str = "1"
    ) -> None:
        if not preds:
            rconsole.print("[yellow]📭 無符合分析條件標的[/]")
            return

        sort_names = {"1": "距潛力估值由大到小", "2": "成交量(%)由大到小"}  # [AI MOD]
        sort_name = sort_names.get(sort_choice, "距潛力估值由大到小")

        engine_label = "Kronos" if self.uses_kronos else "MonteCarlo"
        table = Table(
            title=f"🔮 AI 預測潛力分析榜 (排序: {sort_name}) (基準日: {latest_date}) (模型: {engine_label})",
            box=box.SIMPLE,
            border_style="cyan",
            expand=False,
        )
        table.add_column("代號", style="magenta", justify="left", no_wrap=True)
        table.add_column("名稱", justify="left", no_wrap=True)
        table.add_column("收盤", justify="right", no_wrap=True)
        table.add_column("成交張數", justify="right", no_wrap=True)
        table.add_column("額(億)", style="bright_green", justify="right", no_wrap=True)
        table.add_column("潛力估值", justify="right", no_wrap=True)
        table.add_column("預期目標", justify="right", no_wrap=True)
        table.add_column("模型信心", justify="right", no_wrap=True)

        for p in preds[:40]:
            color = "bright_red" if p.score > 0 else "bright_green"
            disp_price = f"{p.current_price:.2f}"
            disp_target = f"{p.target_price:.2f}"

            # Calculate price color and volume color using our standard helpers! [AI MOD]
            try:
                # Compare displayed current price against prev_price
                prev_price = p.prev_price if p.prev_price else p.current_price
                price_change = p.current_price - prev_price
                pct = (price_change / prev_price * 100) if prev_price else 0.0
                pc = price_color(price_change, pct)
                disp_price_colored = f"[{pc}]{disp_price}[/]"
            except Exception:
                disp_price_colored = disp_price

            try:
                # Compare raw volume to prev_volume
                raw_vol = p.volume  # 股
                vc = vol_color(raw_vol, p.prev_volume if p.prev_volume else raw_vol)
                disp_vol_colored = f"[{vc}]{raw_vol // 1000:,}[/]"  # 換算成張顯示
            except Exception:
                disp_vol_colored = f"{p.volume:,}"

            table.add_row(
                p.code,
                p.name,
                disp_price_colored,
                disp_vol_colored,
                f"{p.amount:.2f}",
                f"[{color}]{p.score:+.2%}[/]",
                disp_target,
                f"{p.confidence:.1%}" if p.confidence > 0 else "N/A",
            )

        rconsole.print(table)


# ── CLI Application ───────────────────────────────────────


class PredictionAnalysisApp:

    def __init__(self):
        if DEFAULT_CONFIG is None:
            raise RuntimeError("kronos_engine 未安裝或匯入失敗，此功能需要 torch")
        self.config = DEFAULT_CONFIG.copy()

    def run(self) -> None:
        signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
        try:
            conn = get_connection(readonly=True)
        except Exception as e:
            rconsole.print(f"[red]❌ 資料庫連線失敗: {e}[/]")
            return

        if StockPredictionAnalyzer is None:
            raise RuntimeError("patterns_strategy 匯入失敗，無法執行預測分析")
        analyzer = StockPredictionAnalyzer(self.config)
        scanner = MarketScanner(conn, self.config)

        while True:
            try:
                _clear_screen()
                _render_header("🧠 AI 策略整合：趨勢預測分析 v3.3")

                latest_date = conn.execute("SELECT MAX(date) FROM stock_history").fetchone()[0]
                latest_str = str(latest_date) if latest_date else "N/A"
                rconsole.print(f"[dim]基準日期: {latest_str}[/dim]\n")

                cmd = rconsole.input("[bold cyan]🔍 輸入股號或按 Enter 回到上一頁: [/]").strip()

                if cmd == "0":
                    break
                elif cmd == "":
                    vol_str = rconsole.input("📊 最小成交量 (張, 預設 500): ").strip()
                    min_vol = int(vol_str) if vol_str.isdigit() else 500
                    scanner.scan_market(min_vol)
                    _wait_for_enter()
                elif len(cmd) == 4 and cmd.isdigit():
                    df = fetch_klines(conn, cmd, limit=512)
                    df = df.dropna(subset=["close"]).sort_values("date")
                    if not df.empty:
                        name = _get_stock_name(conn, cmd)
                        analyzer.analyze_single_stock(cmd, name, df)
                        _wait_for_enter()
                    else:
                        rconsole.print(f"[red]❌ 查無該股號資料：{cmd}[/]")
                        time.sleep(1)
                else:
                    rconsole.print(f"[red]❌ 無效指令：{cmd}[/]")
                    time.sleep(1)

            except KeyboardInterrupt:
                break
            except Exception as e:
                rconsole.print(f"[red]❌ 執行錯誤: {e}[/]")
                time.sleep(2)

        conn.close()


def get_latest_date() -> str:
    """供 strategies.py 查詢資料基準日"""
    from db import (
        get_connection,  # ponytail: _utils does not export get_connection; align with sr/ma_strategy
    )

    conn = get_connection(readonly=True)
    try:
        return conn.execute("SELECT MAX(date) FROM stock_history").fetchone()[0]
    finally:
        conn.close()


def run_strategy(params: dict):
    code = params.get("code")
    scan = params.get("scan", False)
    vol = params.get("vol", 500)
    compact = params.get("compact", False)
    mobile = params.get("mobile", False)
    app = PredictionAnalysisApp()
    if scan:
        conn = get_connection(readonly=True)
        try:
            scanner = MarketScanner(conn, app.config)
            scanner.scan_market(vol)
        finally:
            conn.close()
    elif code:
        conn = get_connection(readonly=True)
        try:
            df = fetch_klines(conn, code, limit=512)
            df = df.dropna(subset=["close"]).sort_values("date")
            if not df.empty:
                name = _get_stock_name(conn, code)
                # 幾何型態分析
                if StockPredictionAnalyzer:
                    analyzer = StockPredictionAnalyzer(app.config)
                    analyzer.analyze_single_stock(code, name, df, compact=compact, mobile=mobile)
                # Kronos 預測（5 日價格）
                if PredictionEngine is None or MonteCarloEngine is None:
                    raise RuntimeError("kronos_engine 未安裝或匯入失敗，此功能需要 torch")
                engine = PredictionEngine(app.config)
                skipped: List[str] = []
                if engine.kronos_engine and engine.kronos_engine.ready:
                    _render_kronos_prediction(df, code, name, engine, skipped)
                else:
                    # Fallback：Kronos 不可用時使用 Monte Carlo
                    mc = MonteCarloEngine()
                    pred = mc.predict(df, app.config)
                    rconsole.print(
                        f"[dim]  Kronos 未載入，使用 Monte Carlo fallback: {pred.benchmark:.2f} (信心 {pred.confidence:.1%})[/]"
                    )
            else:
                rconsole.print(f"[red]❌ 查無該股號資料：{code}[/]")
        finally:
            conn.close()
    else:
        app.run()


def main() -> None:
    app = PredictionAnalysisApp()
    app.run()


if __name__ == "__main__":
    main()
