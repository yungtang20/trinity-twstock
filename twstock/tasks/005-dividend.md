# Issue 005: Dividend Events Fetcher

## Phase
2a — Data Source

## Status
pending

## 依賴
- DB_SCHEMA.md v3.0 (done)

## 需求
實作除權息事件抓取模組：
- 呼叫 FinMind TaiwanStockDividend dataset
- 欄位映射（FinMind → dividend_events）
- INSERT OR REPLACE 寫入 dividend_events
- source = 'finmind'

## 欄位對應

| dividend_events | FinMind 欄位 | 換算 |
|----------------|-------------|------|
| stock_id | stock_id | 直接 |
| date | date | 直接 |
| before_price | beforeDividend | 直接（float）|
| after_price | afterDividend | 直接（float）|
| reference_price | reference | 直接（float）|
| cash_dividend | CashDividend | 直接（float）|
| stock_dividend | StockDividend | 直接（float）|
| source | — | 寫死 'finmind' |

## Task Plan
- [ ] T1: 定義 DividendFetcher(api_token, db)
- [ ] T2: fetch_dividend(stock_id, start_date, end_date)
- [ ] T3: _transform(raw)
- [ ] T4: save(rows) INSERT OR REPLACE
- [ ] T5: fetch_and_save 串接
- [ ] T6: 錯誤處理

## Test Cases（8 個 Test Class，11 個 test function）
- TC1: 2筆資料 → 2列，欄位齊全（2 functions）
- TC2: before_price 正確
- TC3: reference_price 正確
- TC4: cash_dividend / stock_dividend 正確
- TC5: 去重（同 stock+date → 1筆）
- TC6: source = 'finmind'
- TC7: empty data 拋 Exception
- TC8: fetch_and_save 串接（2 functions）

## Definition of Done
- [ ] import：DividendFetcher
- [ ] TC1 PASS：2 passed
- [ ] TC2 PASS：before_price 正確
- [ ] TC3 PASS：reference_price 正確
- [ ] TC4 PASS：cash/stock dividend 正確
- [ ] TC5 PASS：去重
- [ ] TC6 PASS：source='finmind'
- [ ] TC7 PASS：Exception on empty
- [ ] TC8 PASS：2 passed
- [ ] pytest 全綠：11 passed in Y.ZZs
- [ ] git diff --stat tests/ 為空

## 變更紀錄
| 時間 | 內容 |
|------|------|
| - | 初版 |
