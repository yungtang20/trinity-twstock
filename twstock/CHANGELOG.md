# CHANGELOG.md — TRINITY 變更日誌

> 每次重大修改都必須更新此文件。格式遵循 Keep a Changelog。

---

## [Unreleased]

### 新增
- Task 001 FinMind fetcher — `fetch_stock_price`, `fetch_institutional`, `fetch_shareholding`, `fetch_stock_info` 模組層級函式
- TC5 API key 缺失測試
- DoD 模組層級 alias 函式

### 修正
- `fetcher.py` institutional col_map 大小寫（`Foreign_Investor_Buy/Sell`, `Investment_Trust_Buy/Sell`）
- `processor.py` `upsert_history` 不關閉外部 connection
- `API_SPEC.md` institutional 欄位名稱大小寫
- 移除文件中已過時的「前復權 / adj_factor」規格描述（ARCHITECTURE.md、DB_SCHEMA.md、VERSION.md）。功能本身已在稍早的版本中從程式碼移除，這次只是把文件同步更新，避免與現況（stock_history 無 adj_factor 欄位、klines VIEW 無復權欄位）不一致。
- `sync_to_supabase.py` 移除 `adj_factor` 殘留欄位寫入（本地 SQLite 已無此欄位，繼續寫入只會產生 `None` 值）；Supabase 端 `stock_price.adj_factor` 若仍存在，將維持 null 值。

### 新增（前期）
- AGENTS.md — AI Agent 啟動入口
- ARCHITECTURE.md — 完整架構與規範
- PROJECT_RULES.md — 專案開發規範
- DEVELOPMENT_GUIDE.md — 新增功能流程指南
- AI_CHECKLIST.md — 修改完成自我驗收清單
- DB_SCHEMA.md — 資料庫完整規格
- API_SPEC.md — 外部 API 規格

### 修改
- 策略統一介面（analyze / run_strategy / scan_market）
- DB 操作規範（executemany / Index）
- 單位換算規範（DB 內一律為張）

---

## v3.3.0 (2026-06-26)

### 新增
- ARCHITECTURE.md（系統架構規範）
- DB_SCHEMA.md（資料庫 Schema）
- API_SPEC.md（外部 API 規格）
- PROJECT_RULES.md（專案開發規範）
- DEVELOPMENT_GUIDE.md（新功能開發流程）
- AI_CHECKLIST.md（自我驗收清單）

### 修正
- TDCC 更新流程（避免歷史日期重複寫入）
- 前復權計算邏輯（確認累乘方向正確）
- Windows encoding fix（統一加入）

---

## v3.2.0 (2026-06-25)

### 新增
- 統一資料庫架構（taiwan_stock_unified.db）
- 五大策略統一輸出器（strategy_runner.py）
- 除權息每日掃描（official/dividend_daily.py）
- 處置股票檢查（official/suspended.py）

---

*每次更新此文件時，將 [Unreleased] 改為新版本號，並標記日期。*
