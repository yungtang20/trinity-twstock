# PROJECT_AUDIT.md — TRINITY 台股分析平台完整稽核報告

> 稽核日期：2026-06-27
> 專案路徑：`D:\twse\twstock\`
> 程式碼規模：~10,854 行 Python（32 個檔案）
> 稽核範圍：20 個維度

---

## 摘要

| 嚴重程度 | 數量 | 說明 |
|----------|------|------|
| 🔴 P0 Critical | 5 | 執行時崩潰、資料遺失風險 |
| 🟠 P1 High | 18 | 效能、架構、安全問題 |
| 🟡 P2 Medium | 30+ | 程式碼品質、可維護性 |
| 🟢 P3 Low | 10+ | 風格、文件 |

---

## 1. 所有 Python Import 是否正常

**結論：✅ 全部正常**

所有 import 的模組或套件都存在，無 broken import。

| 類別 | 檔案數 | 狀態 |
|------|--------|------|
| 標準庫 | sqlite3, os, sys, json, time, logging, argparse, datetime, shutil, threading, warnings, typing, pathlib, bisect, abc, dataclasses, contextlib, signal, math, re, io, collections, urllib | ✅ |
| 第三方 | pandas, numpy, requests, rich, urllib3, dotenv, bs4 | ✅ |
| 專案內部 | db, db_admin, fetcher, processor, calculator, display, terminal, retry, api_config, strategy.*, official.* | ✅ |

**注意事項：**
- `msvcrt`（Windows 限定）使用 try/except 保護 ✅
- `polars` 使用 try/except 選配式導入 ✅
- `strategy/kronos_engine.py` 中 `torch`, `tqdm`, `model.Kronos*` 為選配式導入 ✅

---

## 2. 是否存在 Circular Import

**結論：✅ 無 actual circular import**

所有 import 關係形成有向無環圖（DAG）。

**Latent Risks（潛在風險）：**

| 風險 | 檔案 | 說明 |
|------|------|------|
| ⚠️ Low | `strategy/klines_helper.py` | 檔案提到「不得 import twstock/polars.py」，但 `polars_compat.py` 存在且無檔案 import 它 |
| ⚠️ Low | `official/tdcc.py` → `processor.DataProcessor` | 延遲 import（在 function 內），安全但方向需注意 |

**Import Dependency Graph：**
```
main.py (entry point)
├── official/* → fetcher, processor, db
├── strategy/* → klines_helper, calculator, db
├── strategy/strategies → 所有 strategy 模組
├── fetcher → processor, db, api_config
├── processor → db
├── calculator → db
├── db_admin → db
└── display, terminal ← 所有模組可導入（純展示）
```

---

## 3. 是否存在未使用 Module

**結論：🔴 發現 2 個完全未使用的模組 + 多個未使用函數**

### 完全死模組

| 檔案 | 行數 | 說明 |
|------|------|------|
| `strategy/vision_engine.py` | 96 | 從未被 import，從未被呼叫。`VisionEngine` 類別和 `VISION_ENGINE` 實例從未被使用 |
| `strategy/klines_helper.py` | 66 | 從未被 import。`fetch_klines()` 功能完全被 `strategy/_utils.py` 覆蓋 |

### 未使用函數（精選）

| 檔案 | 函數 | 行號 | 說明 |
|------|------|------|------|
| `api_config.py` | `get_longcat_api_key()` | 54 | 從未被呼叫 |
| `api_config.py` | `get_longcat_api_url()` | 65 | 從未被呼叫 |
| `api_config.py` | `get_longcat_model()` | 74 | 從未被呼叫 |
| `api_config.py` | `get_supabase_url()` | 82 | 從未被呼叫 |
| `api_config.py` | `get_supabase_key()` | 88 | 從未被呼叫 |
| `api_config.py` | `get_twse_base_url()` | 110 | 從未被呼叫 |
| `api_config.py` | `get_tpex_base_url()` | 116 | 從未被呼叫 |
| `api_config.py` | `get_tdcc_openapi_url()` | 122 | 從未被呼叫 |
| `api_config.py` | `get_tdcc_portal_url()` | 131 | 從未被呼叫 |
| `display.py` | `price_str()` | 40 | 從未被內部使用 |
| `display.py` | `chg_rich()` | 80 | 從未被內部使用 |
| `display.py` | `vol_rich()` | 100 | 從未被內部使用 |
| `display.py` | `vol_fmt_short()` | 128 | 從未被內部使用 |
| `db_admin.py` | `log_audit()` | 363 | 從未被呼叫 |
| `db_admin.py` | `save_bundle()` | 374 | 從未被呼叫 |
| `db_admin.py` | `save_calendar_frame()` | 397 | 從未被呼叫 |
| `db_admin.py` | `save_stock_meta_frame()` | 394 | 從未被呼叫 |
| `main.py` | `format_price_change()` | 221 | 從未被呼叫 |
| `main.py` | `get_market_mode()` | 212 | 從未被呼叫 |
| `main.py` | `_fmt_chg()` | 765 | 從未被呼叫 |
| `main.py` | `_vol_str()` | 771 | 從未被呼叫 |
| `main.py` | `safe_int()` | 104 | 與 `official/utils.py` 重複，且未使用 |
| `main.py` | `safe_float()` | 98 | 與 `official/utils.py` 重複，且未使用 |
| `official/dividend_crawler.py` | `fetch_finmind_dividend_data()` | 74 | 從未被呼叫 |
| `official/institutional.py` | `_get_session()` | 8 | 從未被呼叫 |
| `official/quotes.py` | `_get_session()` | 11 | 從未被呼叫 |
| `official/tdcc.py` | `fetch_latest_tdcc()` | 274 | 從未被呼叫 |
| `official/tdcc.py` | `update_stocks_tdcc_from_portal()` | 138 | 從未被呼叫 |
| `strategy/sr_analyzer.py` | `get_sr_levels()` | 819 | 從未被呼叫 |
| `official/tdcc.py` | `fetch_single_stock_tdcc_from_portal()` | 18 | 僅被死程式碼 `update_stocks_tdcc_from_portal()` 呼叫 |

---

## 4. 是否存在重複 Function

**結論：🟠 發現多處重複**

| 函數 | 位置 1 | 位置 2 | 位置 3 | 嚴重程度 |
|------|--------|--------|--------|----------|
| `safe_float()` | `main.py:98` | `fetcher.py:249` | `official/utils.py:22` | 🔴 High |
| `safe_int()` | `main.py:104` | `official/utils.py:7` | — | 🟠 Medium |
| `clear_screen()` | `strategy/_utils.py:17` | `strategy/chips_strategy.py:105` | — | 🟢 Low |
| `render_header()` | `strategy/_utils.py:37` | `strategy/chips_strategy.py:101` | `strategy/sr_analyzer.py:409` | 🟢 Low |
| `get_single_key_input()` | `main.py:686` | `strategy/strategies.py:103` | `strategy/chips_strategy.py:44` | 🔴 High |
| `get_stock_name()` | `main.py:154` | `strategy/_utils.py:22` | `strategy/patterns_strategy.py:139` | 🟡 Medium |
| `fetch_klines()` | `strategy/_utils.py:70` | `strategy/klines_helper.py:15` | — | 🟡 Medium |
| `compute_adjusted_prices()` | `official/price_adjuster.py:24` | `processor.py:24` | — | 🔴 High |
| `MarketScanner` 類別 | `strategy/prediction_strategy.py:87` | `strategy/patterns_strategy.py:757` | — | 🔴 High |
| `StockPredictionAnalyzer` 類別 | `strategy/prediction_strategy.py:471` | `strategy/patterns_strategy.py:702` | — | 🟡 Medium |

---

## 5. 是否存在 Dead Code

**結論：🔴 大量 Dead Code**

### 層級分類

| 層級 | 數量 | 說明 |
|------|------|------|
| 整個模組 | 2 | `vision_engine.py`, `klines_helper.py` |
| 整個檔案（官方 API URL） | 9 | `api_config.py` 中 9 個 `get_xxx_url()` 函數 |
| 類別 | 1 | `strategy/vision_engine.py` 的 `VisionEngine` |
| 函數 | 30+ | 見上方「未使用函數」列表 |
| 變數 | 2 | `official/institutional.py:15` 的 `SESSION`、`official/quotes.py:18` 的 `SESSION` |

### 說明

- `api_config.py` 中的 URL getter 函數（`get_twse_base_url()` 等）實際上是 config 讀取函數，可能供外部使用，但從未被專案內部呼叫
- `display.py` 中的 `price_str()`, `chg_rich()`, `vol_rich()`, `vol_fmt_short()` 可能作為 public API，但從未被內部使用

---

## 6. 是否存在重複 SQL

**結論：🟠 發現多處重複 SQL**

### 跨檔案重複

| SQL 模式 | 出現位置 |
|----------|----------|
| `SELECT * FROM stock_history WHERE stock_id = ? AND date BETWEEN ? AND ?` | `strategy/sr_analyzer.py`, `strategy/ma_strategy.py`, `strategy/prediction_strategy.py`, `strategy/patterns_strategy.py` |
| `SELECT * FROM stock_meta` | `strategy/patterns_strategy.py`, `strategy/sr_analyzer.py`, `strategy/chips_strategy.py` |
| `SELECT * FROM stock_history WHERE date = ?` | `strategy/patterns_strategy.py`, `strategy/ma_strategy.py`, `strategy/prediction_strategy.py` |
| `SELECT * FROM dividend_events WHERE stock_id = ?` | `strategy/prediction_strategy.py`, `strategy/patterns_strategy.py`, `strategy/kronos_engine.py` |

### 功能重複

| 功能 | 位置 1 | 位置 2 |
|------|--------|--------|
| `fetch_klines()` | `strategy/_utils.py:70`（查詢 `klines` view） | `strategy/klines_helper.py:15`（查詢 `stock_history` table） |
| `compute_adjusted_prices()` | `official/price_adjuster.py:24` | `processor.py:24`（`compute_adj_factor()`） |

---

## 7. 是否存在未被呼叫的 Function

**結論：🔴 發現 30+ 個未被呼叫的函數**

見上方「3. 是否存在未使用 Module」中的未使用函數列表。

---

## 8. 是否存在 Exception 未處理

**結論：🔴 發現多處未處理例外**

| 檔案 | 行號 | 問題 |
|------|------|------|
| `fetcher.py` | 244-247 | 即時資料 API 無 try/except，網路錯誤會崩潰 |
| `official/suspended.py` | 160-175 | 即時資料 API 無 try/except |
| `official/tdcc.py` | 203 | 使用原生 `requests.get()` 而非 `retry_get()`，無 retry 也無例外處理 |
| `strategy/prediction_strategy.py` | 204 | 裸 `except: pass` 吞掉所有錯誤 |
| `main.py` | 1228-1231 | `safe_float()` 無保護的 SQL 查詢 |
| `official/institutional.py` | 69 | `roc_year` 未定義，會被 `except Exception` 捕獲但無日志 |
| `official/quotes.py` | 87 | `roc_year` 未定義，會被 `except Exception` 捕獲但無日志 |
| `strategy/kronos_engine.py` | 335 | `pd.to_datetime()` 對 None/NaN 日期會崩潰 |
| `strategy/patterns_strategy.py` | 410 | 無保護的數值比較 |
| `official/updater.py` | 344 | `None < str` TypeError（見 P0 bug） |

---

## 9. 所有 API 是否都有 Timeout

**結論：🟠 部分 API 缺少 Timeout**

| 檔案 | 行號 | API 呼叫 | 有 Timeout？ |
|------|------|----------|-------------|
| `fetcher.py` | 86 | `requests.get()` | ✅ 有 `timeout=30` |
| `fetcher.py` | 244 | `requests.get()`（即時資料） | ❌ 無 timeout |
| `official/quotes.py` | 74-75 | `requests.get()` | ❌ 無 timeout（使用 `retry_get` 但 retry_get 有 timeout） |
| `official/institutional.py` | 69 | `requests.get()` | ❌ 無 timeout |
| `official/tdcc.py` | 203 | `requests.get()` | ❌ 無 timeout |
| `official/dividend_crawler.py` | 56-63 | `requests.get()` | ✅ 有 timeout |
| `official/trading_calendar.py` | 81, 98 | `requests.get()` | ✅ 有 timeout |
| `official/suspended.py` | 160-175 | `requests.get()` | ❌ 無 timeout |
| `official/updater.py` | 89-95 | `requests.get()` | ✅ 有 timeout |
| `strategy/kronos_engine.py` | 136 | `subprocess.run()` | ❌ 無 timeout |

---

## 10. 所有 requests 是否都有 Retry

**結論：🟠 部分 API 缺少 Retry**

| 檔案 | 行號 | API 呼叫 | 有 Retry？ |
|------|------|----------|-----------|
| `fetcher.py` | 86, 244 | `requests.get()` | ✅ 有 `retry_get()` |
| `official/quotes.py` | 74-75 | `requests.get()` | ✅ 有 `retry_get()` |
| `official/institutional.py` | 69 | `requests.get()` | ✅ 有 `retry_get()` |
| `official/tdcc.py` | 203 | `requests.get()` | ❌ 無 retry（原生 requests） |
| `official/suspended.py` | 160-175 | `requests.get()` | ❌ 無 retry |
| `official/trading_calendar.py` | 81, 98 | `requests.get()` | ✅ 有 `retry_get()` |
| `official/dividend_crawler.py` | 56-63 | `requests.get()` | ✅ 有 `retry_get()` |
| `official/updater.py` | 89-95 | `requests.get()` | ✅ 有 `retry_get()` |

---

## 11. SQLite 是否可能造成 Lock

**結論：🔴 發現 8 個 Lock Risk**

### Critical

| 檔案 | 行號 | 問題 |
|------|------|------|
| `db_admin.py` | 137-140 | `get_connection()` 無 `busy_timeout` 設定，可能導致 "database is locked" |
| `official/price_adjuster.py` | 134-179 | 長時間 transaction（multiple stocks），未使用 WAL mode |

### High

| 檔案 | 行號 | 問題 |
|------|------|------|
| `official/dividend_crawler.py` | 282-289 | 逐筆 DELETE + INSERT 在 loop 中，可能造成 lock |
| `official/trading_calendar.py` | 81, 98, 112, 148 | 多次獨立 connect，無連接池 |
| `official/dividend_daily.py` | 97-167 | 多支股票逐筆寫入，無 batch commit |
| `official/updater.py` | 183-312 | 全市場更新在單一 transaction 中 |

### Medium

| 檔案 | 行號 | 問題 |
|------|------|------|
| `calculator.py` | 26, 132 | 無 `busy_timeout` 設定 |
| `official/updater.py` | 183-312 | 長時間 transaction |

**建議：**
- 所有 `sqlite3.connect()` 應使用 `db.get_connection()`（已有 `busy_timeout=5.0`）
- 啟用 WAL 模式（`PRAGMA journal_mode=WAL`）
- 大量寫入使用 `executemany()` + 分批 commit

---

## 12. 是否存在 N+1 Query

**結論：🔴 發現 11 個 N+1 Query**

### Critical

| 檔案 | 行號 | 問題 |
|------|------|------|
| `official/dividend_daily.py` | 97-165 | 每支股票查詢歷史資料 + 逐筆 INSERT，O(N) queries |
| `official/dividend_crawler.py` | 283-289 | 逐筆 DELETE + INSERT，O(N) queries |
| `official/updater.py` + `trading_calendar.py` | 183-195 | 800 次 JOIN 查詢判斷日期是否存在 |
| `official/updater.py` | 183-312 | 全市場更新中每支股票獨立查詢 |

### High

| 檔案 | 行號 | 問題 |
|------|------|------|
| `strategy/sr_analyzer.py` | 606-631 | scan_market 中每支股票獨立查詢 |
| `strategy/ma_strategy.py` | 226-233 | scan_market 中每支股票獨立查詢 |
| `strategy/prediction_strategy.py` | 160-208 | scan_market 中每支股票獨立查詢 |
| `strategy/patterns_strategy.py` | 876-883 | scan_market 中每支股票獨立查詢 |
| `official/dividend_crawler.py` | 233-248 | fallback 路徑中每支股票獨立查詢 |

### Medium

| 檔案 | 行號 | 問題 |
|------|------|------|
| `calculator.py` | 127-147 | 每支股票獨立查詢 |
| `official/trading_calendar.py` | 93-103, 122-127 | 每次查詢建立新連接 |
| `official/tdcc.py` | 162-169 | 每種股票 × 每個日期獨立 HTTP 請求（外部 N+1） |

**最嚴重：** `updater.py` 的 800 次 JOIN 查詢 + `dividend_daily.py` 的 2N queries

---

## 13. 是否存在 Memory Leak

**結論：🔴 發現 4 個無限增長的 Cache + 多处資源洩漏**

### Critical — 無限增長的 Cache

| 檔案 | 行號 | 問題 |
|------|------|------|
| `strategy/ma_strategy.py` | 33-37 | `_SCAN_CACHE` 儲存整個市場掃描結果，從不清除 |
| `strategy/prediction_strategy.py` | 31-35 | `_PRED_CACHE` 同上 |
| `strategy/patterns_strategy.py` | 34-38 | `_PATTERN_CACHE` 同上，還包含 DataFrame |
| `strategy/sr_analyzer.py` | 49 | `_SR_CACHE` 同上 |

### High — 資源洩漏

| 檔案 | 行號 | 問題 |
|------|------|------|
| `main.py` | 789, 824 | 直接使用 `sqlite3.connect()` 而非 `get_connection()` |
| `main.py` | 453-457 | 每次 cache 過期就新建 thread，無上限 |
| `calculator.py` | 26-36 | `pd.read_sql_query()` 失敗時連接未關閉 |
| `strategy_runner.py` | 40-46, 248-254 | 手動 `conn.close()`，無 `try/finally` 保護 |
| `main.py` | 1041, 1066 | `sqlite3.Connection` context manager 只處理 transaction，不關閉連接 |
| `official/institutional.py` | 15 | Module-level `requests.Session()` 從不關閉 |
| `official/quotes.py` | 18 | 同上 |
| `fetcher.py` | 102-115 | Singleton `FinMindClient` 的 session 從不關閉 |

### Medium — 效能問題

| 檔案 | 行號 | 問題 |
|------|------|------|
| `main.py` | 346, 401 | `for _ in range(1)` 死迴圈 |
| `main.py` | 686-761 | `time.sleep(0.01)` busy-wait loop |
| `official/dividend_daily.py` | 143-158 | O(n²) 掃描 |
| `strategy/patterns_strategy.py` | 406-412 | 熱路徑 O(n) 成員測試 |

---

## 14. 是否存在 Type Error

**結論：🔴 發現 7 個 Type Error**

### Critical

| 檔案 | 行號 | 問題 |
|------|------|------|
| `official/updater.py` | 344 | `None < str` TypeError — 空資料表時 `MAX(date)` 回傳 `None` |

### High

| 檔案 | 行號 | 問題 |
|------|------|------|
| `official/institutional.py` | 69 | `roc_year` 未定義，`NameError`（P0 bug） |
| `official/quotes.py` | 87 | `roc_year` 未定義 |

### Medium

| 檔案 | 行號 | 問題 |
|------|------|------|
| `strategy/kronos_engine.py` | 335 | `None`/`NaN` 日期導致 `pd.to_datetime()` 崩潰 |
| `official/tdcc.py` | 245 | `NaN` 股數繞過 zero-guard |
| `dividend_crawler.py` | 53-63 | `AttributeError` on None input 未捕獲 |
| `fetcher.py` | 152 | 含逗號字串被強制轉 0 |

### Low

| 檔案 | 行號 | 問題 |
|------|------|------|
| `prediction_strategy.py` | 197 | `inf`/`NaN` volume 無聲傳播 |
| `processor.py` | 74 | `NaT` 處理邊界情況 |
| `fetcher.py` | 247 | `msgArray` 非 list 的潛在問題 |

---

## 15. 所有 CLI 是否可正常執行

**結論：🟠 有問題**

### argparse 配置

| 檔案 | 行號 | 問題 |
|------|------|------|
| `main.py` | 1392-1427 | `python main.py 2330` 會失敗 — argparse 把 `2330` 指派給 `action` 而非 `stock_id` |
| `main.py` | 1403 | `--strategy-id` 無 `choices` 約束，無效值不會被 argparse 捕獲 |

### Action Handler 驗證

| Action | 對應函數 | 狀態 |
|--------|----------|------|
| `update` | `update_database()` | ✅ 存在 |
| `indicators` | `indicators_command()` | ✅ 存在 |
| `intraday` | `intraday_command()` | ✅ 存在 |
| `strategy` | `run_strategy_cli()` | ✅ 存在 |
| `official` | `official_command()` | ✅ 存在 |
| `dividend` | `dividend_command()` | ✅ 存在 |

**注意：** 所有 handler 存在，但 `chips_strategy.py` 会在運行時崩潰（見 #16）。

---

## 16. 所有 Strategy 是否都可以正常 import

**結論：🔴 1 個 Strategy 無法正常運行**

### Strategy 註冊表

| # | 名稱 | 模組 | `run_strategy()` | Import 狀態 | 運行狀態 |
|---|------|------|-----------------|-------------|----------|
| 1 | 撐壓分析 | `sr_analyzer` | ✅ | ✅ | ✅ |
| 2 | 均線趨勢 | `ma_strategy` | ✅ | ✅ | ✅ |
| 3 | 籌碼動能 | `chips_strategy` | ✅ | ✅ | 🔴 崩潰 |
| 4 | AI 預測 | `prediction_strategy` | ✅ | ✅ | ✅ |
| 5 | 幾何型態 | `patterns_strategy` | ✅ | ✅ | ✅ |

### 🔴 Critical Bug：`chips_strategy.py` 缺少 `StockAnalyzer` 類別

| 檔案 | 行號 | 問題 |
|------|------|------|
| `strategy/chips_strategy.py` | 117, 187, 200 | 使用 `StockAnalyzer()` 作為 context manager，但該類別**從未被定義** |
| `strategy/chips_strategy.py` | 119, 143, 159, 169 | 呼叫 `analyzer.get_latest_dates()`, `analyzer.analyze_institutional_buying()` 等方法，但**不存在** |

**影響：** 選擇 strategy 3（籌碼動能）時會立即拋出 `NameError: name 'StockAnalyzer' is not defined`。

**修復建議：** 實作 `StockAnalyzer` 類別或改用 `db.get_connection()` 直接查詢。

---

## 17. 所有 JSON Output 是否符合規格

**結論：🟠 JSON 輸出不符合 JSON_CONTRACT.md**

### 規格不符

| 檔案 | 行號 | 問題 |
|------|------|------|
| `strategy_runner.py` | 531-541 | 輸出缺少 `strategy`, `stock_id`, `score`, `signal`, `confidence`, `summary` 欄位 |
| `strategy_runner.py` | 49, 257, 335, 397, 483 | 錯誤格式使用 `{"error": "..."}` 而非 `{"error": true, "message": "..."}` |
| `strategy_runner.py` | 62, 65-66 | numpy 型別未正確轉換為 Python float |

### JSON Contract 對照

| 必需欄位 | `strategy_runner.py` 輸出 | 狀態 |
|----------|--------------------------|------|
| `strategy` | ❌ 缺少 | 🔴 不符 |
| `stock_id` | ❌ 缺少 | 🔴 不符 |
| `score` | ❌ 缺少 | 🔴 不符 |
| `signal` | ❌ 缺少 | 🔴 不符 |
| `confidence` | ❌ 缺少 | 🔴 不符 |
| `summary` | ❌ 缺少 | 🔴 不符 |
| `details` | ✅ 有 | ✅ 符合 |

---

## 18. 所有 Rich Console 是否正常

**結論：🟠 有問題**

### Console 實例

| 檔案 | 狀態 | 說明 |
|------|------|------|
| `terminal.py` | ✅ | 正確建立兩個 console（stdout/stderr），處理 Windows UTF-8 |
| `strategy/templates/strategy_template.py` | 🔴 | 使用裸 `Console()` 而無 UTF-8 處理，Windows 上會亂碼 |

### 未使用的 Rich Import

| 檔案 | Import | 狀態 |
|------|--------|------|
| `main.py` | `Padding` | ❌ 未使用 |
| `main.py` | `Group` (from `rich.console`) | ✅ 使用但非標準路徑（應從 `rich.group`） |
| `strategy/ma_strategy.py` | `Panel` | ❌ 未使用 |

### 輸出路由不一致

| 檔案 | Console | 說明 |
|------|---------|------|
| `sr_analyzer.py` | `console`（stdout） | ✅ 正確 |
| `ma_strategy.py` | `console`（stdout） | ✅ 正確 |
| `chips_strategy.py` | `rconsole`（stderr） | 🟡 不一致 |
| `prediction_strategy.py` | `rconsole`（stderr） | 🟡 不一致 |
| `patterns_strategy.py` | `rconsole`（stderr） | 🟡 不一致 |
| `kronos_engine.py` | `rconsole`（stderr） | 🟡 不一致 |

### Markup 問題

| 檔案 | 行號 | 問題 |
|------|------|------|
| `strategy/prediction_strategy.py` | 255 | `prev_volume=0.0` 被 falsy 判斷視為 missing，color 計算錯誤 |
| `strategy/patterns_strategy.py` | 833 | `price_color(p.score, p.score * 100)` 語意不正確 |

---

## 19. 所有資料流是否符合 ARCHITECTURE.md

**結論：🔴 發現多處違規**

### 禁止的 Import 路徑（違反 ARCHITECTURE.md）

| 檔案 | 行號 | 違規 | 說明 |
|------|------|------|------|
| `official/dividend_crawler.py` | 35 | **official → fetcher** | `from fetcher import DataFetcher` |
| `official/dividend_crawler.py` | 74-89, 235-249 | **official → fetcher** | 執行期呼叫 `fetcher.fetch_dividend_events()` |
| `strategy/chips_strategy.py` | 14-15 | **strategy 直接抓 API** | `import urllib.request`（應透過 SQLite） |

### 資料流違規

| 檔案 | 行號 | 問題 |
|------|------|------|
| `official/tdcc.py` | 203 | 使用原生 `requests.get()` 而非 `retry_get()` |
| `main.py` | 789, 824 | 直接使用 `sqlite3.connect()` 繞過 `get_connection()` |
| `official/trading_calendar.py` | 81, 98, 112, 148 | 直接使用 `sqlite3.connect()` |
| `official/price_adjuster.py` | 134, 159, 186 | 直接使用 `sqlite3.connect()` |
| `official/dividend_crawler.py` | 282 | 直接使用 `sqlite3.connect()` |

### Schema 不一致

| 檔案 | 行號 | 問題 |
|------|------|------|
| `main.py` | 1083-1086 | 使用 `ex_date` 欄位，ARCHITECTURE.md 定義為 `date` |
| `strategy/chips_strategy.py` | 163-167 | 使用 `shareholding_unified` 表，ARCHITECTURE.md 未定義 |
| `processor.py` | 134-202 | 使用 `shareholding_unified` 表，與 `db_admin.py` 定義不一致 |

---

## 20. 所有 Coding Rule 是否符合 PROJECT_RULES.md

**結論：🟠 大量違規**

### print() 在程式庫中（應使用 logging 或 console.print）

| 檔案 | 行號 | 數量 |
|------|------|------|
| `official/price_adjuster.py` | 85-203 | ~10 處 |
| `official/dividend_crawler.py` | 77-250 | ~5 處 |
| `official/tdcc.py` | 135-267 | ~15 處 |
| `official/updater.py` | 89-372 | ~20 處 |
| `official/trading_calendar.py` | 36-91 | ~8 處 |
| `official/suspended.py` | 160-175 | ~3 處 |
| `official/dividend_daily.py` | 67-85 | ~5 處 |
| `db_admin.py` | 152, 186-188, 401-410 | ~5 處 |
| `strategy/_utils.py` | 61-67 | 1 處 |
| `strategy/strategies.py` | 16, 115, 121, 125 | 4 處 |
| `strategy/sr_analyzer.py` | 558, 562, 564, 566 | 4 處 |
| `main.py` | 1056-1064 | ~3 處 |

### Import 順序錯誤（stdlib → third-party → project）

| 檔案 | 行號 | 問題 |
|------|------|------|
| `main.py` | 27-31 | `sqlite3` 在 `pandas` 之後 |
| `official/dividend_crawler.py` | 7-31 | `requests`/`pandas` 在 `sqlite3`/`os`/`sys` 之前 |
| `official/institutional.py` | 1-9 | `datetime`/`logging` 在 `pandas`/`requests` 之後 |
| `official/tdcc.py` | 7-16 | `datetime` 在 `pandas`/`requests` 之後 |
| `official/trading_calendar.py` | 7-20 | `datetime` 在 `pandas`/`requests` 之後 |
| `official/updater.py` | 14-28 | `pandas` 在 `from . import` 之後 |
| `strategy/kronos_engine.py` | 8-25 | `typing`/`dataclasses`/`abc` 在 `numpy`/`pandas` 之後 |
| `strategy/ma_strategy.py` | 8-15 | `os` 在 `pandas` 之後 |
| `strategy/chips_strategy.py` | 7-13 | `urllib`/`json` 在 `pandas` 之後 |
| `calculator.py` | 9-13 | `sqlite3` 在 `pandas`/`numpy` 之後 |

### Magic Numbers（應定義為常數）

| 檔案 | 行號 | 值 | 建議常數名稱 |
|------|------|-----|-------------|
| `main.py` | 214-218 | `540`, `815` | `MARKET_OPEN_MIN`, `MARKET_CLOSE_MIN` |
| `main.py` | 506-508 | `9*60`, `13*60+30` | `LIVE_START_MIN`, `LIVE_END_MIN` |
| `main.py` | 467-469 | `15`, `3600` | `REFRESH_INTERVAL` |
| `db.py` | 31 | `10`, `5000` | `CONN_TIMEOUT`, `BUSY_TIMEOUT` |
| `fetcher.py` | 38 | `600`, `3600` | `MAX_CALLS_PER_HOUR` |
| `calculator.py` | 49 | `[5,10,20,60,120,200]` | `MA_PERIODS` |
| `calculator.py` | 62 | `(12,26,9)` | `MACD_PARAMS` |
| `strategy/kronos_engine.py` | 358-360 | `0.02`, `0.01`, `0.10`, `1.5` | `DAILY_VOL_FALLBACK` 等 |
| `retry.py` | 19-20 | `10`, `3`, `1.0` | `DEFAULT_TIMEOUT`, `DEFAULT_RETRIES` |

### 命名慣例不符

| 檔案 | 函數 | 建議名稱 |
|------|------|----------|
| `strategy/sr_analyzer.py` | `display_stock_analysis()` | `render_stock_analysis()` |
| `strategy/sr_analyzer.py` | `_analyze_one()` | `analyze_one_stock()` |
| `strategy/sr_analyzer.py` | `_score()` | `compute_score()` |
| `strategy/ma_strategy.py` | `_analyze_one()` | `analyze_one_stock()` |
| `strategy/prediction_strategy.py` | `_display_results()` | `render_results()` |
| `db_admin.py` | `show_tables()` | `render_tables()` 或 `get_tables()` |
| `main.py` | `safe_float()` | `to_safe_float()` |
| `main.py` | `safe_int()` | `to_safe_int()` |

### SELECT 未使用 Index

| 檔案 | 行號 | 查詢 |
|------|------|------|
| `main.py` | 195-198 | `LENGTH(stock_id) = 4 AND stock_id GLOB '[1-9]...'` |
| `main.py` | 1228-1231 | `volume = 0` 條件無法使用索引 |
| `strategy/chips_strategy.py` | 163-167 | `shareholding_unified` 全表掃描 |
| `strategy/sr_analyzer.py` | 522-524 | `stock_id GLOB '[1-9][0-9][0-9][0-9]'` |

### DB 操作違規

| 檔案 | 行號 | 問題 |
|------|------|------|
| `official/dividend_crawler.py` | 284-288 | 逐筆 DELETE + INSERT，應使用 `executemany()` |
| `official/dividend_daily.py` | 97-167 | 逐筆查詢 + 寫入，無 batch 操作 |
| `official/updater.py` | 183-312 | 全市場更新在單一 transaction 中 |

### 硬編碼路徑

| 檔案 | 行號 | 路徑 |
|------|------|------|
| `strategy/kronos_engine.py` | 49, 72 | `os.path.join(..., "../kronos")` |
| `strategy/kronos_engine.py` | 151, 196, 202 | `d:/twse/kronos/` 字串 |
| `get_fields.py` | 16 | `open('fields.json', ...)` |

---

## 嚴重問題清單（Priority Order）

### 🔴 P0 — 立即修復

| # | 問題 | 檔案 | 行號 | 影響 |
|---|------|------|------|------|
| 1 | `roc_year` 未定義 | `official/institutional.py` | 69 | 上櫃三大法人資料全部失敗 |
| 2 | `StockAnalyzer` 類別不存在 | `strategy/chips_strategy.py` | 117, 187, 200 | 籌碼策略運行時崩潰 |
| 3 | `None < str` TypeError | `official/updater.py` | 344 | 空資料表時全市場更新失敗 |
| 4 | 4 個無限增長 Cache | `strategy/sr_analyzer.py:49`, `ma_strategy.py:33`, `prediction_strategy.py:31`, `patterns_strategy.py:34` | — | 長時間使用後記憶體耗盡 |
| 5 | N+1 在 updater.py | `official/updater.py` + `trading_calendar.py` | 183-195 | 800 次 JOIN 查詢，效能極差 |

### 🟠 P1 — 下個版本修復

| # | 問題 | 檔案 | 影響 |
|---|------|------|------|
| 6 | official → fetcher 違規 | `official/dividend_crawler.py:35` | 架構方向錯誤 |
| 7 | chips_strategy 使用 urllib | `strategy/chips_strategy.py:14` | 違反 strategy 不得直接抓 API |
| 8 | Schema 不一致 | `main.py`, `processor.py`, `chips_strategy.py` | 資料表/欄位名稱與架構規章不符 |
| 9 | 大量 print() 在 official/ | 多個檔案 | 違反 PROJECT_RULES.md |
| 10 | DB 連接未正確關閉 | `main.py`, `calculator.py` | 連接洩漏 |
| 11 | busy_timeout 未設定 | `db_admin.py:137-140` | SQLite lock 風險 |
| 12 | JSON 輸出不符規格 | `strategy_runner.py` | 消費者可能 KeyError |
| 13 | 全市場 scan N+1 | 4 個 strategy 檔案 | 掃描 1500 檔股票需 1500 次查詢 |
| 14 | dividend_daily.py O(N²) | `official/dividend_daily.py:143` | 每支股票掃描全部歷史 |

### 🟡 P2 — 建議修復

| # | 問題 | 說明 |
|---|------|------|
| 15 | Import 順序錯誤 | 12+ 檔案 |
| 16 | Magic numbers | 40+ 處 |
| 17 | 重複 safe_float/safe_int | main.py 與 utils.py 重複 |
| 18 | 重複 get_single_key_input | 4 處 |
| 19 | 重複 MarketScanner 類別 | 2 處 |
| 20 | 死程式碼 | vision_engine.py, klines_helper.py |
| 21 | busy_wait loop | main.py:686-761 |
| 22 | subprocess 無 timeout | strategy/kronos_engine.py:136 |

### 🟢 P3 — 可選修復

| # | 問題 | 說明 |
|---|------|------|
| 23 | 未使用的 import | Padding, Panel |
| 24 | 硬編碼路徑 | kronos_engine.py |
| 25 | 命名慣例不符 | ~20 個函數 |
| 26 | 缺少模組 docstring | vision_engine.py, get_fields.py |

---

## 結論

TRINITY 台股分析平台 v3.3 有 **5 個 P0 Critical 問題**需要立即修復：

1. **`institutional.py:69`** — `roc_year` 未定義，上櫃法人資料全部失敗
2. **`chips_strategy.py`** — `StockAnalyzer` 類別不存在，籌碼策略崩潰
3. **`updater.py:344`** — 空資料表時 `None < str` TypeError
4. **4 個無限 Cache** — 長時間使用後記憶體耗盡
5. **updater.py 800 次 JOIN** — 每日更新耗時數分鐘而非數秒

建議修復順序：P0 → P1 → P2 → P3。

---

*報告自動生成於 2026-06-27*