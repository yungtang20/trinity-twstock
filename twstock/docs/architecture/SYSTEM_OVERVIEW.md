# TRINITY 系統總覽

```text
                    使用者
          ┌───────────┴───────────┐
          ▼                       ▼
   main.py（CLI／TUI）     strategy_runner.py（彙整／JSON）
          │                       │
          ▼                       ▼
      commands/*              strategy/*
          │                       │
          └───────────┬───────────┘
                      ▼
          SQLite：taiwan_stock_unified.db
                      │
       ┌──────────────┼──────────────┐
       ▼              ▼              ▼
 core/processor.py calculator.py  db_admin.py
       ▲              │              │
       │              ▼              │
 market_data/*、official/*    stock_indicators
       ▲
 FinMind、TWSE、TPEx、TDCC
```

## 兩條資料路徑

1. 更新路徑：外部來源 → 取得／解析 → `DataProcessor` 驗證及 UPSERT → SQLite。
2. 分析路徑：SQLite → 指標或策略 → result contract → Rich／JSON。

策略路徑不得在分析時自行下載資料。需要更新時，先由明確的 command 完成資料寫入，再執行分析。

## 核心資料集合

| 類別 | 正式資料集合 |
|---|---|
| 股票基本資料 | `stock_meta` |
| 日線 OHLCV | `stock_history` |
| 法人買賣超 | `institutional_data` |
| TDCC／外資持股 | `shareholding_unified` |
| 股利與估值 | `dividend_events`、`per_data` |
| 衍生指標 | `stock_indicators` |

`tdcc_shareholding`、`klines`、`klines_indicators`、`institutional_daily` 與相容性 projection 都是 read-only views；寫入必須使用正式 table 與 `DataProcessor`。

## 設計邊界

- SQLite 是策略的正式資料來源，不是外部 API 的快取替代品。
- 資料庫儲存原始股數與元；只有顯示格式化時才能換算單位。
- 指標刷新採分批讀取、向量化計算與批次寫入。
- JSON 邊界採統一策略結果契約，舊欄位只作相容性保留。
- 資料修復工具預設唯讀，`--apply` 前必須備份並檢查統計結果。
