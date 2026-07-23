# TRINITY SQLite Schema v3

資料庫檔為 `taiwan_stock_unified.db`。日期一律使用 ISO `YYYY-MM-DD`。以下是 `db_admin.py` 建立及 migration 維護的正式契約；既有資料量、日期範圍不是 schema 的一部分。

## 單位與資料來源

- `stock_history.volume`：原始成交股數（股），不可在 ETL 除以 1,000。
- `stock_history.amount`：原始成交金額（元），不可在 ETL 除以億元。
- 法人買賣超、持股數量：原始股數（股）。
- 比率欄位：百分比數值，例如 `12.5` 表示 12.5%。
- 每筆 ingestion 必須保留 `source`；顯示層才可轉換成張、千張或億元。

## Tables

### `stock_meta`

| 欄位 | 型別 | 說明 |
|---|---|---|
| `stock_id` | TEXT PK | 股票代號 |
| `stock_name` | TEXT NOT NULL | 股票名稱 |
| `industry_category` | TEXT | 產業分類 |
| `market` | TEXT | TSE、OTC 或其他來源標示 |
| `type` | TEXT | 證券類型，保留來源原值 |
| `source` | TEXT | 資料來源 |
| `updated_at` | TEXT | 更新時間 |

### `stock_trading_calendar`

| 欄位 | 型別 | 說明 |
|---|---|---|
| `date` | TEXT PK | 日期 |
| `is_open` | INTEGER NOT NULL | 1 為開市、0 為休市 |
| `description` | TEXT | 來源說明或休市原因 |
| `updated_at` | TEXT | 更新時間 |

### `stock_history`

主鍵為 `(stock_id, date)`。

| 欄位 | 型別 | 說明 |
|---|---|---|
| `stock_id` | TEXT NOT NULL | 股票代號 |
| `date` | TEXT NOT NULL | 日 K 日期 |
| `open`, `high`, `low`, `close` | REAL NOT NULL | 原始價格（元） |
| `volume` | INTEGER NOT NULL | 原始成交量（股） |
| `amount` | INTEGER NOT NULL | 原始成交額（元） |
| `trade_count` | INTEGER | 成交筆數 |
| `spread` | REAL | 漲跌價差 |
| `source` | TEXT | 資料來源 |
| `updated_at` | TEXT | 更新時間 |

### `dividend_events`

主鍵為 `(stock_id, date)`；包含 `before_price`、`after_price`、`reference_price`、`cash_dividend`、`stock_dividend`、`source`、`updated_at`。

### `institutional_data`

主鍵為 `(stock_id, date)`。

| 欄位群組 | 欄位 |
|---|---|
| 識別 | `stock_id`、`date`、`source`、`updated_at` |
| 淨買賣超 | `foreign_net`、`trust_net`、`dealer_net`、`institutional_net` |
| 買賣明細 | `foreign_buy`、`foreign_sell`、`trust_buy`、`trust_sell`、`dealer_buy`、`dealer_sell` |

### `shareholding_unified`

主鍵為 `(stock_id, date, source)`。`source` 是主鍵的一部分，TDCC 與外資持股資料可以在同一天並存。

| 欄位群組 | 欄位 |
|---|---|
| 識別 | `stock_id`、`date`、`source`、`updated_at` |
| TDCC／集中度 | `total_shares`、`whale_ratio`、`retail_ratio`、`total_people`、`whale_shares`、`whale_people` |
| 外資持股 | `foreign_shares`、`foreign_ratio` |

### `per_data`

主鍵為 `(stock_id, date)`；包含 `per`、`pbr`、`pe_ratio`、`pb_ratio`、`dividend_yield`、`source`、`updated_at`。

### `stock_indicators`

主鍵為 `(stock_id, date)`。保存 `ma5`、`ma20`、`ma25`、`ma60`、`ma200`、三種成交量均線、三種乖離率、`atr14`、`vwap` 與 `updated_at`。它是衍生資料，日線更正後必須重算。

### `audit_log`

包含自增 `log_id`、`stock_id`、`action`、`status`、`detail`、`timestamp`。資料修復與重要批次作業應留下可追溯紀錄。

## Views

Each object below is a SQLite `VIEW` and is read-only from application code.

所有 views 都是 read-only projection：

| View | 用途 |
|---|---|
| `tdcc_shareholding` | `shareholding_unified` 中 `source = 'tdcc'` 的 TDCC projection。 |
| `shareholding_data` | 舊讀取端相容性 projection，提供有外資持股值的 `stock_id`、`date`、`foreign_shares`、`foreign_ratio`。新程式不得寫入此 view。 |
| `klines` | 日線 OHLCV 的型別一致 projection。 |
| `klines_indicators` | `klines` 左連接 `stock_indicators`。 |
| `institutional_daily` | `institutional_data` 的相容性 projection。 |

## Indexes

- `idx_stock_history_stock_date (stock_id, date)`
- `idx_stock_history_date (date)`
- `idx_dividend_events_stock_date (stock_id, date)`
- `idx_institutional_stock_date (stock_id, date)`
- `idx_shareholding_unified_stock_date (stock_id, date)`
- `idx_stock_indicators_stock_date (stock_id, date)`

`db_admin.init_db()` 建立新資料庫；`migrate_db()` 只做可重複、向後相容的欄位、索引與 view 補齊，不重寫既有市場資料。
