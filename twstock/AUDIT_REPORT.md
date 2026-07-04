# twstock 專案審計報告

**產生日期**: 2026-07-04
**分支**: main (commit a67cbca)
**測試狀態**: 692 passed, 22 skipped

---

## 1. 致命問題（需立即修正）

### 1.1 缺少 `twstock/__init__.py`
- **位置**: `twstock/` 目錄下無 `__init__.py`
- **影響**: 不是正規 Python 套件，`pip install -e .` 無法運作，IDE 自動完成失效，從非專案根目錄 `import twstock` 失敗
- **修正**: 建立 `twstock/__init__.py`（可為空或定義 `__version__`）

### 1.2 `db_admin.py` 使用未匯入的型別
- **位置**: `db_admin.py:207,216,235` 使用 `sqlite3.Connection` 型別註解
- **影響**: 若 Python 評估型別註解（無 `from __future__ import annotations`），會拋 `NameError`
- **修正**: 加入 `import sqlite3` 或加入 `from __future__ import annotations`

### 1.3 ~25+ 隱式相對匯入
- **位置**: 遍及 `db_admin.py`, `calculator.py`, `fetcher.py`, `processor.py`, `strategy/*.py`, `official/*.py`
- **範例**: `from db import get_connection`（應為 `from twstock.db import get_connection`）
- **影響**: 僅因 `main.py` 手動加 `sys.path` 才能運作，從其他目錄執行或作為套件安裝時會失敗
- **修正**: 全面改為 `from twstock.xxx import ...`

---

## 2. 重要問題（建議修正）

### 2.1 重複定義
| 函式 | 位置 1 | 位置 2 | 問題 |
|------|--------|--------|------|
| `clear_screen` | `input_helper.py:63` | `strategy/_utils.py:17` | 完全相同實作 |
| `get_stock_name` | `utils.py:140` (參數: stock_id) | `strategy/_utils.py:22` (參數: conn, stock_id, fallback) | 簽章不相容 |

### 2.2 不一致的錯誤處理
| 模組 | 策略 |
|------|------|
| `fetcher.py` | 拋例外 (raise) |
| `official/quotes.py`, `institutional.py` | 回傳空 DataFrame |
| `official/tdcc.py` | 回傳 None |
| `strategy_runner.py` | 回傳錯誤 dict |
| `utils.py:safe_http_get` | 回傳 None |

**建議**: 統一為「回傳 None + log 警告」或「自定義例外階層」

### 2.3 一次性腳本污染套件
| 檔案 | 問題 |
|------|------|
| `get_fields.py` | 無匯入，硬編碼日期 `20240625` |
| `backfill_indicators.py` | 僅測試用 `exec` 匯入 |
| `tasks/final_audit.py` | 硬編碼 Windows 路徑 `d:/twse/twstock` |

**建議**: 移至 `scripts/` 或 `tasks/` 目錄

### 2.4 未使用的 `api_config.py` 存取函式
- `get_twse_base_url`, `get_tpex_base_url`, `get_tdcc_openapi_url`, `get_tdcc_portal_url`
- `get_longcat_api_key`, `get_longcat_model`, `get_supabase_url`, `get_supabase_key`
- `get_kronos_model_id`, `get_kronos_tokenizer_id`
- **定義但無任何呼叫**

### 2.5 `display.py` 僅測試用函式
- `price_str`, `chg_rich`, `vol_rich`, `ma_str` 僅在 `test_display.py` 使用

---

## 3. 建議項目（可選修正）

### 3.1 硬編碼 URL
- 所有 TWSE/TPEx/TDCC/FinMind URL 散落各處
- **建議**: 集中至 `api_config.py` 或 `constants.py`

### 3.2 魔術數字
- `strategy_runner.py:47` `limit=30`
- `official/tdcc.py:170` `time.sleep(0.15)`
- `strategy/strategies.py:109` `vol=500`
- **建議**: 提取為命名常數

### 3.3 `strategy_runner.py` 重複邏輯
- `run_prediction_analysis` 與 `prediction_strategy.py` 功能重疊
- `_PredictionAdapter` 與 `AIStrategy` 可內聯

### 3.4 3 個相同的 `_get_stock_name` wrapper
- `patterns_strategy.py:195`, `prediction_strategy.py:99`, `sr_analyzer.py:423`
- 皆只是 `get_stock_name(conn, stock_id)` 的 1 行包裝

---

## 4. 功能驗證結果

| 測試項目 | 結果 |
|----------|------|
| `python -m twstock.main --help` | ✅ 顯示 6 個 action |
| `python d:/twse/twstock/main.py --help` | ✅ 雙模式支援 |
| `python -m twstock.main indicators 2330` | ✅ 正確輸出 5 日股價 |
| `python -m twstock.main strategy --strategy-id 1 --code 2330` | ✅ 撐壓分析執行 |
| `python -m twstock.main update 2330` | ⚠️ 無 FINMIND_TOKEN（預期行為） |
| TUI 啟動 + 退出 | ✅ 不再卡住 |
| `pytest twstock/tests/ -x -q` | ✅ 692 passed, 22 skipped |

---

## 5. 套件結構健康度

| 項目 | 狀態 |
|------|------|
| `twstock/__init__.py` | ❌ 缺失 |
| `twstock/strategy/__init__.py` | ⚠️ 空檔案，無 `__all__` |
| `twstock/commands/__init__.py` | ⚠️ 僅 docstring |
| `twstock/official/__init__.py` | ✅ 完整 `__all__` |
| `twstock/market_data/__init__.py` | ✅ 完整 `__all__` |
| `twstock/tui/__init__.py` | ⚠️ 未檢查 |
