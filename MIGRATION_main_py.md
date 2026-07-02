# MIGRATION: main.py God Module 拆分

> 日期：2026-07-02
> 分支：`refactor-main-py`
> 原檔案：`twstock/main.py`（1435 行）
> 拆分後：`twstock/main.py`（93 行）+ 4 個新套件

---

## 1. 變更摘要

| 新模組 | 職責 |
|--------|------|
| `main.py`（93 列） | 唯一入口：argparse + db init + 子命令分派 |
| `utils.py` | 共用工具：`safe_float`、`safe_int`、`to_roc_date`、HTTP helpers |
| `commands/` | 6 個 CLI 子命令：dividend、indicators、intraday、official、strategy、update |
| `tui/` | 互動式選單：`TUIApp`（狀態封裝）、`render`（dashboard）、`menu`（子選單） |
| `market_data/` | 即時盤中抓取 + 快取：`MarketCache`、`fetch_market_indices` |
| `strategy/composites.py` | 複合分析：多策略 + K 線 + LongCat AI |

同步刪除：

| 檔案 | 原因 |
|------|------|
| `config.py` | 無意義 re-export（api_config 已為正港來源） |
| `tests/test_006_per.py` | PERFetcher 已不存在 |
| `tests/test_config_secrets.py` | config.py 已刪 |
| `strategy/klines_helper.py` | 死程式碼，已收斂至 `_utils.fetch_klines` |
| `db_admin.py` 所有 `save_*` 函式 | 資料寫入統一由 `processor.py` 處理 |

---

## 2. 導入路徑對照表

### 已搬移至 `twstock.utils`

| 舊路徑 | 新路徑 |
|--------|--------|
| `from twstock.main import safe_float` | `from twstock.utils import safe_float` |
| `from twstock.main import safe_int` | `from twstock.utils import safe_int` |
| `from twstock.main import get_token` | `from twstock.utils import get_token` |
| `from twstock.main import get_stock_name` | `from twstock.utils import get_stock_name` |
| `from twstock.main import to_roc_date` | `from twstock.utils import to_roc_date` |
| `from twstock.main import get_sys_info` | `from twstock.utils import get_sys_info` |
| `from twstock.main import get_market_mode` | `from twstock.utils import get_market_mode` |
| `from twstock.main import format_price_change` | `from twstock.utils import format_price_change` |

### 已搬移至 `twstock.market_data`

| 舊路徑 | 新路徑 |
|--------|--------|
| `from twstock.main import fetch_market_indices_cached` | `from twstock.market_data import MarketCache` + `MarketCache().get()` |
| `from twstock.main import fetch_market_indices` | `from twstock.market_data import fetch_market_indices` |
| `from twstock.main import get_yahoo_market_volumes` | `from twstock.market_data import get_yahoo_market_volumes` |
| `from twstock.main import get_realtime_mis_data` | `from twstock.market_data import get_realtime_mis_data` |

### 已搬移至 `twstock.commands.*`

| 舊路徑 | 新路徑 |
|--------|--------|
| `from twstock.main import dividend_command` | `from twstock.commands.dividend import execute` |
| `from twstock.main import indicators_command` | `from twstock.commands.indicators import execute` |
| `from twstock.main import intraday_command` | `from twstock.commands.intraday import execute` |
| `from twstock.main import official_command` | `from twstock.commands.official import execute` |
| `from twstock.main import update_database` | `from twstock.commands.update import execute` |

### 已搬移至 `twstock.strategy.composites`

| 舊路徑 | 新路徑 |
|--------|--------|
| `from twstock.main import run_quick_analysis` | `from twstock.strategy.composites import run_composite` |

### 已搬移至 `twock.tui.*`

| 舊路徑 | 新路徑 |
|--------|--------|
| `from twstock.main import tui_interactive_menu` | `from twstock.tui import TUIApp` + `TUIApp().run()` |
| `from twstock.main import render_dashboard` | `from twstock.tui import render_dashboard` |
| `from twstock.main import make_layout` | `from twstock.tui import make_layout` |

---

## 3. CLI / TUI 使用者影響

### CLI

**完全相容**。無需改變使用方式：

```bash
# 舊
python -m twstock.main update 2330
# 新（仍可用）
python -m twstock.main update 2330
```

所有參數完全保留：`--token`、`--days`、`--date`、`--tdcc-only`、`--with-tdcc`、`--tdcc-weeks`、`--start-date`、`--end-date`、`--scan`、`--vol`、`--strategy-id`、`--code`。

### TUI

**功能完全保留**。無 args 啟動後：

- 選項 1（每日資料更新）→ 完整保留
- 選項 2（歷史資料更新）→ 完整保留（5 個子選項：交易日/TDCC/除權息/當年公告/零量價異常）
- 選項 3（策略分析中心）→ 完整保留
- 選項 4（資料庫維護 VACUUM）→ 完整保留
- 4 碼股號直接分析 → 完全保留

### DB Admin

**向後相容**。`init_db()`、`migrate_db()`、`create_tables()`、`create_views()`、`show_tables()` 皆保留。

不相容：已移除 `save_*` 函式（見下節）。

---

## 4. 依賴關係變化

### 新增依賴

無。所有新套件僅使用既有的 `rich`、`pandas`、`requests`、`sqlite3`。

### 移除依賴

| 檔案 | 移除的依賴 |
|------|-----------|
| `db_admin.py` | 不再需要 `pandas`（schema-only） |
| `main.py` | 不再需要 `pandas`、`rich`、`requests`、`bs4`、`fetcher`、`processor`、`calculator` |

### 資料寫入路徑

| 舊路徑 | 新路徑 |
|--------|--------|
| `db_admin.save_stock_history(df)` | `processor.upsert_history(df)` |
| `db_admin.save_dividend_events(df)` | `processor.upsert_dividend_events(df)` |
| `db_admin.save_institutional_data(df)` | `processor.upsert_institutional(df)` |
| `db_admin.save_tdcc_shareholding(df)` | `processor.upsert_tdcc(df)` |
| `db_admin.save_stock_meta(df)` | `processor.upsert_meta(df)` |
| `db_admin.save_shareholding_data(df)` | `processor.upsert_shareholding(df)` |

---

## 5. 開發者遷移指引

### 若曾直接引用 main.py 內部函式

```python
# ❌ 舊
from twstock.main import safe_float, get_stock_name, fetch_market_indices_cached

# ✅ 新
from twstock.utils import safe_float, get_stock_name
from twstock.market_data import MarketCache
cache = MarketCache()
data = cache.get()
```

### 若曾使用 db_admin.save_*

```python
# ❌ 舊
from db_admin import save_stock_history
save_stock_history(df)

# ✅ 新
from processor import DataProcessor
DataProcessor().upsert_history(df)
```

### 若曾使用 run_quick_analysis

```python
# ❌ 舊
from twstock.main import run_quick_analysis
run_quick_analysis("2330")

# ✅ 新
from twstock.strategy.composites import run_composite
run_composite("2330")
```

---

## 6. 測試遷移

### 已刪除的測試

| 檔案 | 原因 |
|------|------|
| `tests/test_006_per.py` | PERFetcher 已不存在 |
| `tests/test_config_secrets.py` | config.py 已刪除 |

### 已更新的測試

| 檔案 | 變更 |
|------|------|
| `tests/test_compat_views.py` | `save_*` → `DataProcessor().upsert_*` |
| `tests/test_updater_schema_compat.py` | `save_stock_history` → `DataProcessor().upsert_history` |

### 新增的測試

| 檔案 | 覆蓋 |
|------|------|
| `tests/test_utils.py` | `safe_float`、`safe_int`、`to_roc_date`、`format_price_change` |
| `tests/test_market_data.py` | `MarketCache` 初始化、快取、過期 |
| `tests/test_commands_execute.py` | 各命令 `execute()` 基本流程 |
| `tests/test_tui_app.py` | `TUIApp` 初始化、`render_dashboard`、選單函式 |

---

## 7. 向後不相容處

| 項目 | 說明 |
|------|------|
| `db_admin.save_*` 已刪除 | 改用 `processor.upsert_*` |
| `main.py` 不再匯出內部函式 | 所有 helper 已搬至 `utils.py` |
| `fetch_market_indices_cached` 不再匯出 | 改用 `MarketCache().get()` |
| `run_quick_analysis` 已改名 | 改用 `run_composite` |
| `config.py` 已刪除 | 改用 `api_config` 直接 |
| `strategy/klines_helper.py` 已刪除 | 改用 `strategy._utils.fetch_klines` |

---

## 8. 未來計畫

| 優先 | 項目 | 原因 |
|------|------|------|
| P0 | 修正 `verify=False`（composites.py、fetcher.py） | 資安紅線 |
| P0 | 消除 `tui/menu.py` 與 `tui/app.py` 的重複輸入邏輯 | 減少複製貼上偏移 |
| P1 | 統一策略 registry（strategy_runner -vs- composites -vs- strategies.py） | 三重狂寫 |
| P1 | `tui/render.py` 的 `_market_cache` 改由外部注入 | 可測試性 |
| P1 | `commands/indicators.py` 改用 `console.print()` | 介面一致性 |
| P2 | `strategy_runner.py` 的 `_PredictionAdapter` 與 `prediction_strategy` 整合 | 決定論 -vs- Kronos |
| P2 | `official/updater.py` 的 `upsert_dataframe` 與 `processor.py` 整合 | 減少重複 |
| P3 | `strategy_runner.py` 整併至 `commands/strategy.py` | 減少 dispatch 分岐 |

---

## 9. 驗證清單

```bash
# 執行測試
cd D:\twse && pytest twstock/tests/ -x -q
# 預期：278 passed, 1 skipped

# 執行覆蓋率
pytest twstock/tests/ --cov=twstock --cov-report=term-missing -q

# 驗證 CLI
py -m twstock.main --help
py -m twstock.main update --help
```
