# strategy/templates/strategy_template.py

"""
策略開發模板 — 複製此檔案開始新增策略。

使用方式：
1. 複製此檔案到 strategy/ 目錄，命名為 my_new_strategy.py
2. 修改以下部分：
   - CLASS_NAME → 策略名稱（PascalCase）
   - STRATEGY_ID → 策略編號（"6" 或更大）
   - STRATEGY_NAME → 策略顯示名稱
   - analyze() → 實作分析邏輯
   - run_strategy() → 實作畫面渲染
   - scan_market() → 實作全市場掃描
3. 在 strategy/strategies.py 的 STRATEGY_REGISTRY 註冊
4. 在 main.py 確認 CLI 支援
5. 執行 python strategy_runner.py <stock_id> 測試
"""

import os
import sys

import pandas as pd
from rich.console import Console
from rich.panel import Panel

# ── Windows Encoding Fix ──
if sys.platform == "win32":
    os.system("chcp 65001 > nul")
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stdin.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

# ── Import shared modules ──
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_TWSTOCK_DIR = os.path.abspath(os.path.join(_CURRENT_DIR, ".."))
if _TWSTOCK_DIR not in sys.path:
    sys.path.insert(0, _TWSTOCK_DIR)

from twstock.db import get_connection

# ── Strategy Configuration ──
STRATEGY_ID = "NEW"  # 策略編號（在 STRATEGY_REGISTRY 中的 key）
STRATEGY_NAME = "策略名稱"  # 策略顯示名稱
STRATEGY_DESCRIPTION = "策略說明"  # 策略描述

# ── Session Cache ──
_SCAN_CACHE = {
    "date": None,
    "min_volume": None,
    "results": None,
}

console = Console()


def analyze(params: dict) -> dict:
    """
    單一股票策略分析。

    Args:
        params:
            code: str — 股票代號（如 '2330'）
            compact: bool — 是否簡潔模式
            mobile: bool — 是否手機模式

    Returns:
        dict — 統一口徑
    """
    stock_id = params.get("code", "")

    # 從 SQLite 讀取資料（不碰外部 API）
    conn = get_connection(readonly=True)
    try:
        df = pd.read_sql(
            "SELECT date, open, high, low, close, volume "
            "FROM stock_history WHERE stock_id = ? "
            "ORDER BY date DESC LIMIT 250",
            conn,
            params=(stock_id,),
        )
    finally:
        conn.close()

    if df.empty:
        return {
            "strategy": STRATEGY_NAME,
            "stock_id": stock_id,
            "score": 0,
            "signal": "HOLD",
            "confidence": 0,
            "summary": f"無 {stock_id} 資料",
            "details": {},
        }

    # ── 在此實作你的分析邏輯 ──
    # 例如：計算均線、偵測型態、分析籌碼...
    # 示例（請刪除）：
    closes = df["close"].tolist()
    latest = closes[-1] if closes else 0

    return {
        "strategy": STRATEGY_NAME,
        "stock_id": stock_id,
        "score": 50,  # 綜合評分 0~100
        "signal": "HOLD",  # BUY / HOLD / SELL
        "confidence": 50,  # 信心指數 0~100
        "summary": f"{stock_id} 最新收盤 {latest:.2f}",
        "details": {
            "latest_price": latest,
            "latest_date": str(df["date"].iloc[-1]),
            "volume": int(df["volume"].iloc[-1]) if not df.empty else 0,
            # 策略專屬詳細資料
        },
    }


def run_strategy(params: dict) -> None:
    """
    策略入口點，負責渲染畫面。

    Args:
        params: 同 analyze() 的 params
    """
    stock_id = params.get("code", "")
    stock_name = ""  # 可從 stock_meta 查詢

    console.print(
        Panel(
            f"[bold]{stock_id} {stock_name} — {STRATEGY_NAME}[/]",
            title="[bold cyan]策略分析[/]",
            border_style="cyan",
        )
    )

    result = analyze(params)

    # ── 在此實作你的畫面渲染 ──
    console.print(f"  信號: [bold {result['signal'].lower()}]{result['signal']}[/]")
    console.print(f"  評分: {result['score']}/100")
    console.print(f"  信心: {result['confidence']}%")
    console.print(f"  摘要: {result['summary']}")


def scan_market(vol: int = 500) -> list[dict]:
    """
    全市場掃描。從 DB 讀取，不碰外部 API。

    Args:
        vol: 最小成交量門檻（張）

    Returns:
        list[dict] — 同 analyze() 回傳格式的列表，已排序
    """
    conn = get_connection(readonly=True)
    try:
        # 讀取所有有資料的股票
        stocks = conn.execute(
            "SELECT DISTINCT stock_id FROM stock_history " "WHERE volume >= ? ORDER BY stock_id",
            (vol,),
        ).fetchall()
    finally:
        conn.close()

    results = []
    for row in stocks:
        stock_id = row["stock_id"]
        try:
            result = analyze({"code": stock_id})
            results.append(result)
        except Exception:
            continue  # 單支失敗不影響其他

    # 按 score 降序排列
    results.sort(key=lambda x: x.get("score", 0), reverse=True)
    return results


if __name__ == "__main__":
    # 獨立測試
    if len(sys.argv) > 1:
        run_strategy({"code": sys.argv[1]})
    else:
        print(f"用法: python {__file__} <stock_id>")
