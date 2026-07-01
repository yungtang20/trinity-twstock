# TRINITY 台股分析平台 — 架構規範

> 本文件供 AI 開發者與人類開發者共同遵循。所有修改必須向下相容。

---

## 專案設計原則

本專案定位：**台股日線分析 Decision Support System**。

1. SQLite 為唯一資料來源。
2. 不做程式交易。
3. 不做自動下單。
4. 不做回測。
5. 不做排程。
6. 不做通知。
7. 所有分析以日 K 資料為主。
8. 所有策略互相獨立。
9. 模組低耦合、高內聚。
10. 優先可維護性，其次效能，最後才增加新功能。

---

## 系統架構規範

### 允許的 import 路徑

```
main.py
    ↓
official/*
    ↓
fetcher.py
    ↓
processor.py
    ↓
db.py

main.py
    ↓
strategy/*
    ↓
calculator.py
    ↓
db.py

official/*
    ↓
processor.py
    ↓
db.py

strategy/*
    ↓
klines_helper.py
    ↓
calculator.py
    ↓
db.py

display.py ← 所有模組都可讀（純展示）
terminal.py ← 所有模組都可讀（純展示）
```

### 禁止的 import 路徑

```
strategy → official        # 策略不該碰資料抓取
official → strategy        # 資料抓取不該碰策略
processor → strategy       # ETL 不該碰策略
fetcher → strategy         # 資料萃取不該碰策略
calculator → official      # 計算引擎不該碰資料抓取
任何模組 → 循環 import     # A→B→A 或 A→B→C→A
```

**規則**：依賴方向永遠是「上層 → 下層」，禁止反向。

---

## 資料流（Data Flow）

```
官方 API（TWSE/TPEx/TDCC）
    ↓
FinMind API
    ↓
fetcher.py          ← 資料萃取層（API → DataFrame）
    ↓
processor.py        ← ETL 層（DataFrame → SQLite）
    ↓
SQLite              ← 唯一資料來源
    ↓
calculator.py       ← 技術指標計算
    ↓
strategy/*.py       ← 五大策略分析
    ↓
strategy_runner.py  ← 策略統一輸出
    ↓
display.py          ← 畫面輸出（Rich Console）
```

**鐵律**：strategy 模組不得直接呼叫外部 API，所有資料來自 SQLite。

---

## 資料庫 Schema（完整）

### stock_meta

| 欄位 | 型別 | 說明 |
|------|------|------|
| stock_id | TEXT PRIMARY KEY | 股票代號 |
| stock_name | TEXT NOT NULL | 股票名稱 |
| industry_category | TEXT | 產業類別 |
| market | TEXT | TSE / OTC |
| type | TEXT | COMMON / PREFERRED |
| source | TEXT | 資料來源 |
| updated_at | TEXT | 更新時間 |

### stock_trading_calendar

| 欄位 | 型別 | 說明 |
|------|------|------|
| date | TEXT PRIMARY KEY | 日期 YYYY-MM-DD |
| is_open | INTEGER NOT NULL | 1=開市, 0=休市 |
| source | TEXT | 資料來源 |
| updated_at | TEXT | 更新時間 |

### stock_history

| 欄位 | 型別 | 說明 |
|------|------|------|
| stock_id | TEXT NOT NULL | 股票代號 |
| date | TEXT NOT NULL | 日期 YYYY-MM-DD |
| open | REAL | 開盤價 |
| high | REAL | 最高價 |
| low | REAL | 最低價 |
| close | REAL | 收盤價 |
| volume | INTEGER | 成交量（股，非張） |
| amount | INTEGER | 成交金額（元，非千萬元） |
| trade_count | INTEGER | 成交筆數 |
| spread | REAL | 差價 |
| source | TEXT | 資料來源 |
| updated_at | TEXT | 更新時間 |
| **PRIMARY KEY** | **(stock_id, date)** | |

索引：`idx_stock_history_stock_date (stock_id, date)`

### dividend_events

| 欄位 | 型別 | 說明 |
|------|------|------|
| stock_id | TEXT NOT NULL | 股票代號 |
| date | TEXT NOT NULL | 除權息日期 |
| before_price | REAL | 前收盘價 |
| after_price | REAL | 後收盘價 |
| reference_price | REAL | 參考價 |
| cash_dividend | REAL | 現金股利 |
| stock_dividend | REAL | 股票股利 |
| source | TEXT | 資料來源 |
| updated_at | TEXT | 更新時間 |
| **PRIMARY KEY** | **(stock_id, date)** | |

索引：`idx_dividend_events_stock_date (stock_id, date)`

### institutional_data

| 欄位 | 型別 | 說明 | 單位 |
|------|------|------|------|
| stock_id | TEXT NOT NULL | 股票代號 | |
| date | TEXT NOT NULL | 日期 | |
| foreign_net | INTEGER DEFAULT 0 | 外資買賣超淨額 | 張 |
| trust_net | INTEGER DEFAULT 0 | 投信買賣超淨額 | 張 |
| dealer_net | INTEGER DEFAULT 0 | 自營商買賣超淨額 | 張 |
| foreign_buy | INTEGER DEFAULT 0 | 外資買進 | 張 |
| foreign_sell | INTEGER DEFAULT 0 | 外資賣出 | 張 |
| trust_buy | INTEGER DEFAULT 0 | 投信買進 | 張 |
| trust_sell | INTEGER DEFAULT 0 | 投信賣出 | 張 |
| dealer_buy | INTEGER DEFAULT 0 | 自營商買進 | 張 |
| dealer_sell | INTEGER DEFAULT 0 | 自營商賣出 | 張 |
| institutional_net | INTEGER DEFAULT 0 | 三大法人合計 | 張 |
| source | TEXT | 資料來源 | |
| updated_at | TEXT | 更新時間 | |
| **PRIMARY KEY** | **(stock_id, date)** | |

索引：`idx_institutional_stock_date (stock_id, date)`

> **DB 存原始值（股/元），顯示層才轉換。** 所有 ingestion 路徑不得在寫入前做單位轉換。

### shareholding_unified

| 欄位 | 型別 | 說明 |
|------|------|------|
| stock_id | TEXT NOT NULL | 股票代號 |
| date | TEXT NOT NULL | 日期 |
| source | TEXT NOT NULL | 資料來源（tdcc / 集保） |
| total_shares INTEGER | 總股數 |
| whale_ratio | REAL | 大股東持股比例（%） |
| retail_ratio | REAL | 散戶持股比例（%） |
| foreign_shares | INTEGER | 外資持股數 |
| foreign_ratio | REAL | 外資持股比例（%） |
| total_people | INTEGER | 總人數 |
| whale_shares | INTEGER | 大股東持股數 |
| whale_people | INTEGER | 大股東人數 |
| updated_at | TEXT | 更新時間 |
| **PRIMARY KEY** | **(stock_id, date, source)** | |

### tdcc_shareholding（VIEW）

**這是 VIEW，不是 TABLE。** 定義：

```sql
CREATE VIEW tdcc_shareholding AS
SELECT stock_id, date, total_shares, whale_ratio, retail_ratio, source, updated_at
FROM shareholding_unified
WHERE source = 'tdcc'
```

### audit_log

| 欄位 | 型別 | 說明 |
|------|------|------|
| log_id | INTEGER PRIMARY KEY AUTOINCREMENT | 日誌 ID |
| stock_id | TEXT | 股票代號 |
| action | TEXT | 動作 |
| status | TEXT | 狀態 |
| detail | TEXT | 詳細資訊 |
| timestamp | TEXT | 時間 |

---

## 統一 Strategy Interface

所有策略模組必須提供以下函數，未來 React、CLI、JSON 輸出皆可共用。

### analyze(params) → dict

```python
def analyze(params: dict) -> dict:
    """
    單一股票策略分析。

    Args:
        params:
            code: str — 股票代號（如 '2330'）
            compact: bool — 是否簡潔模式
            mobile: bool — 是否手機模式

    Returns:
        dict — 統一格式
    """
    return {
        "strategy": "sr",              # 策略名稱
        "stock_id": "2330",             # 股票代號
        "score": 75,                    # 綜合評分 0~100
        "signal": "BUY",                # BUY / HOLD / SELL
        "confidence": 80,               # 信心指數 0~100
        "summary": "短期支撐強勁...",   # 一段話摘要
        "details": {                    # 策略專屬詳細資料
            # 每個策略自行定義
        },
    }
```

### run_strategy(params) → None

```python
def run_strategy(params: dict) -> None:
    """
    策略入口點，負責渲染畫面。

    Args:
        params: 同 analyze() 的 params
    """
    ...
```

### scan_market(vol: int = 500) → list[dict]

```python
def scan_market(vol: int = 500) -> list[dict]:
    """
    全市場掃描。從 DB 讀取，不碰外部 API。

    Args:
        vol: 最小成交量門檻（張）

    Returns:
        list[dict] — 同 analyze() 回傳格式的列表，已排序
    """
    ...
```

---

## Coding Rule

### 禁止修改

| 項目 | 原因 |
|------|------|
| Public Function Name | 其他模組可能依賴 |
| DB Schema | 會破壞現有資料 |
| CLI Argument | 會破壞使用者習慣 |
| JSON Output Format | 前端 / 外部工具可能依賴 |

### 新增功能

- 新增 Module（不要修改既有 Module）
- 除非 backward compatible，否則不修改既有 Module
- 新功能走新函數、新檔案，舊函數保留但標記 deprecated

### 程式風格

- 每個 public function 必须有 docstring
- 每個 public class 必须有 class-level docstring
- 禁止 magic number（定義為常數）
- 禁止硬編碼路徑（用 Path 相對路徑）

---

## Naming Rule

| 動詞 | 用途 | 範例 |
|------|------|------|
| `fetch_xxx()` | 抓資料（外部 API） | `fetch_twse_quotes()` |
| `update_xxx()` | 更新資料（寫入 DB） | `update_official_daily()` |
| `compute_xxx()` | 數值運算 | `compute_ma()` |
| `build_xxx()` | 建立 DataFrame | `build()` (IndicatorEngine) |
| `save_xxx()` | 寫 DB | `save_stock_meta()` |
| `run_xxx()` | 執行（策略 / 主流程） | `run_strategy()` |
| `render_xxx()` | 畫畫面 | `render_dashboard()` |
| `is_xxx()` | 布林判斷 | `is_trading_day()` |
| `get_xxx()` | 取得設定 / 狀態 | `get_connection()` |

---

## Error Policy

| 情境 | 行為 |
|------|------|
| API Timeout | Retry 3 次（指數退避 1s, 2s, 4s） |
| HTTP 500 | Retry 3 次 |
| HTTP 404 | Skip，回傳空 DataFrame |
| JSON Parse Error | Skip，log warning |
| SQLite Busy | Retry 3 次 |
| ValueError | Log warning，繼續下一支股票 |
| Exception（任何） | 不得中止全市場更新 |

**鐵律**：單一支股票失敗不影響其他股票。全市場掃描中任意一檔拋出未處理 exception 是 bug。

---

## Logging Rule

| 層級 | 用法 |
|------|------|
| DEBUG | `logging.debug()` — 詳細追蹤（不印出到終端） |
| INFO | `logging.info()` — 重要里程碑 |
| WARNING | `logging.warning()` — 可恢復的異常 |
| ERROR | `logging.exception()` — 錯誤（自動帶 traceback） |

**禁止**：
- 在正式程式碼中使用 `print()`（CLI 互動提示除外）
- 所有正式輸出使用 Rich Console

---

## Cache Rule

### Session Cache

- **Key**：`(stock_id, date)` 或策略專屬鍵
- **TTL**：程式結束（記憶體中，不寫 Disk）
- **容量上限**：最多 10,000 筆
- **淘汰策略**：LRU（最近最少使用）

### 禁止

- 永久寫 Disk（除非明確是 cache 檔案）
- 跨進程共享記憶體 cache

---

## CLI Rule

```bash
# TUI 互動模式
python main.py

# 命令列模式
python main.py <action> [stock_id] [options]

# 支援的 action
official          # 官方資料全市場更新
strategy          # 策略分析（搭配 --strategy-id, --code, --scan）
update            # 單檔更新（搭配 --token）
indicators        # 技術指標顯示
intraday          # 盤中即時指標
dividend          # 除權息更新
```

**規則**：
- 所有 CLI 參數使用 `argparse`
- 不得新增新的 CLI 格式（不支援 positional args 以外的自訂解析）
- 新增 action 需同步更新 help text

---

## DB Operation Rule

### INSERT / UPSERT

- 所有 INSERT 必須使用 `executemany()`
- 禁止逐筆 `execute()` + `commit()`
- 大量資料（>1000 筆）分批 commit
- 使用 `INSERT OR REPLACE` 或 `ON CONFLICT DO UPDATE`

### SELECT

- 所有 SELECT 必須使用 Index
- 禁止全表掃描（WHERE 不加 index 的查詢要特別小心）
- 唯讀連線使用 `get_connection(readonly=True)`

### Transaction

- 單一邏輯操作封裝在一個 transaction 內
- 禁止跨操作的分散 commit

---

## AI 修改程式規範

### 修改任何程式時，不得：

1. 刪除任何現有功能
2. 修改 public function name
3. 修改 CLI argument 格式
4. 修改 DB schema（欄位 / 資料表）
5. 修改 JSON output format
6. 引入 circular import

### 新增功能時：

1. 優先新增 module，避免修改既有 module
2. 新功能必須 backward compatible
3. 舊 function 可以 deprecated，但不能移除

### 修改完成後，必須自行檢查：

- [ ] 是否可 import（無 syntax error）
- [ ] 是否有 circular import
- [ ] CLI 是否仍可正常執行
- [ ] SQLite 是否正常開啟
- [ ] 所有 strategy 是否仍可執行
- [ ] 單位換算是否一致（存原始值：股/元）

---

## 單位換算規範

DB 內所有量值一律存原始值（不轉換），顯示層才轉換：

| 欄位 | DB 單位 | API 原始單位 | 換算公式 |
|------|---------|-------------|---------|
| volume | 股 | 股 | 直接存，不轉換 |
| amount | 元 | 元 | 直接存，不轉換 |
| foreign_buy/sell | 股 | 股 | 直接存，不轉換 |
| trust_buy/sell | 股 | 股 | 直接存，不轉換 |
| dealer_buy/sell | 股 | 股 | 直接存，不轉換 |

**所有 ingestion 路徑直接存原始值，不做單位轉換。顯示層才轉換（display.py 的 vol_fmt）。**

---

## 交易日判準

```
date_exists_in_history(date_int):
    TSE_count > 500  AND  OTC_count > 500
```

> 此為最低門檻。若市場總家數變化，此門檻應隨之調整。

---

## 版本資訊

| 項目 | 值 |
|------|-----|
| 專案 | TRINITY 台股分析平台 |
| 版本 | v3.3 |
| 報告日期 | 2026-06-26 |
| 最後更新 | 2026-06-26 |
