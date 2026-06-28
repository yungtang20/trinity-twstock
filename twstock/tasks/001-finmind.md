# Issue 001: FinMind Data Fetcher

## Phase
2a — Data Source

## Status
pending

## 依賴
- DB_SCHEMA.md v3.0 (done)

## 需求
實作 FinMind 日線資料抓取模組，負責：
- 呼叫 FinMind TaiwanStockPrice dataset 取得指定股票的原始日線
- 欄位映射（FinMind 欄位名 → stock_history 欄位名）
- 不做單位轉換（Trading_Volume 直接存為 volume，Trading_money 直接存為 amount）
- 以 INSERT OR REPLACE 寫入 stock_history 表
- 去重鍵為 (stock_id, date)
- 重複抓取同一 (stock_id, date) 不產生重複列（覆蓋）

## 範圍排除
- 不計算 adj_factor / adj_close（後續 Task）
- 不碰 Indicator / Strategy
- adj_factor 預設 1.0
- stock_history 沒有 adj_close 欄位，不需要寫入

## 欄位對應（FinMind API → stock_history）

| stock_history | FinMind | 換算 |
|---------------|---------|------|
| stock_id | stock_id | 直接 |
| date | date | 直接 |
| open | open | 直接 |
| high | max | 欄位名不同 |
| low | min | 欄位名不同 |
| close | close | 直接 |
| volume | Trading_Volume | 直接（股，不 ÷ 1000）|
| amount | Trading_money | 直接（元，不 ÷ 10,000,000）|
| trade_count | Trading_turnover | 直接 |
| spread | spread | 直接 |
| adj_factor | — | 寫死 1.0 |
| source | — | 寫死 'finmind' |

## Task Plan
- [ ] T1: 定義 FinMindFetcher 類別（接受 api_token, db 連線）
- [ ] T2: 實作 fetch_daily(stock_id, start, end) 呼叫 FinMind API
- [ ] T3: 實作 _transform(raw) 欄位映射（max→high, min→low）+ 設定 adj_factor=1.0, source='finmind'
- [ ] T4: 實作 save(rows) INSERT OR REPLACE 寫入 stock_history
- [ ] T5: 實作 fetch_and_save(stock_id, start, end) 串接 T2→T3→T4
- [ ] T6: 錯誤處理（空回應拋 Exception 含 'empty'，缺欄位拋 Exception 含欄位名）

## Test Cases（共 10 個 Test Class，14 個 test function）
- TC1: 三日資料 → 3 列，欄位齊全，沒有 adj_close（3 個 test function）
- TC2: Trading_Volume=31530000 存入 volume=31530000（原始股數）
- TC3: Trading_money=18750000000 存入 amount=18750000000（原始元）
- TC4: max→high=595.0, min→low=590.0（2 個 test function）
- TC5: 同 (2330, 2024-01-02) 寫兩次 → 1 筆，值為最後一次
- TC6: adj_factor == 1.0
- TC7: 空 data=[] 拋 Exception 含 'empty'
- TC8: 缺 Trading_Volume 拋 Exception 含 'Trading_Volume'
- TC9: source 為 'finmind'
- TC10: fetch_and_save 串接，DB 有 3 筆，值正確（2 個 test function）

## Definition of Done（每一項必須貼 terminal 證據）
- [ ] import：貼出 python -c "from fetcher import FinMindFetcher" 的結果
- [ ] TC1 PASS：貼出 3 passed（基本正確性、欄位齊全、無 adj_close）
- [ ] TC2 PASS：貼出 volume==31530000
- [ ] TC3 PASS：貼出 amount==18750000000
- [ ] TC4 PASS：貼出 high==595.0, low==590.0
- [ ] TC5 PASS：貼出 COUNT=1 且 close=600.0
- [ ] TC6 PASS：貼出 adj_factor=1.0
- [ ] TC7 PASS：貼出 Exception 含 'empty'
- [ ] TC8 PASS：貼出 Exception 含 'Trading_Volume'
- [ ] TC9 PASS：貼出 source='finmind'
- [ ] TC10 PASS：貼出 2 passed，3 筆資料且值正確
- [ ] pytest 全綠：貼出最後一行 14 passed in Y.ZZs
- [ ] git diff --stat tests/ 為空（測試沒被改）

## 變更紀錄
| 時間 | 內容 |
|------|------|
| - | v3.0 重建：移除 adj_close，單位改為原始值（股/元）|
| - | DoD 補 TC1，pytest 全綠改為 14 passed |
