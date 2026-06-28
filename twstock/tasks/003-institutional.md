# Issue 003: Institutional Data Fetcher

## Phase
2a — Data Source

## Status
pending

## 依賴
- DB_SCHEMA.md v3.0 (done)
- Issue 001 (done)

## 需求
實作三大法人資料抓取模組：
- 呼叫 FinMind TaiwanStockInstitutionalInvestors dataset
- 將每日多筆（每法人一筆）pivot 成一筆（一日一筆）
- 合計兩種自營商子類型（自行買賣 + 避險）
- INSERT OR REPLACE 寫入 institutional_data
- source = 'finmind'

## API 規格
- FinMind dataset: TaiwanStockInstitutionalInvestors
- 每日回傳多筆，每筆 name 欄位代表法人類型
- 法人分類規則：
  - name 含「外資」且不含「自營商」→ foreign
  - name == '投信' → trust
  - name 含「自營商」→ dealer（累加，有多筆）
- institutional_net = foreign_net + trust_net + dealer_net

## 欄位對應

| institutional_data | FinMind | 換算 |
|--------------------|---------|------|
| stock_id | stock_id | 直接 |
| date | date | 直接 |
| foreign_buy | buy（外資筆） | 直接 |
| foreign_sell | sell（外資筆） | 直接 |
| foreign_net | net（外資筆） | 直接 |
| trust_buy | buy（投信筆） | 直接 |
| trust_sell | sell（投信筆） | 直接 |
| trust_net | net（投信筆） | 直接 |
| dealer_buy | buy（自營商各筆）| 累加 |
| dealer_sell | sell（自營商各筆）| 累加 |
| dealer_net | net（自營商各筆）| 累加 |
| institutional_net | — | foreign+trust+dealer net |
| source | — | 寫死 'finmind' |

## Task Plan
- [ ] T1: 定義 InstitutionalFetcher(api_token, db)
- [ ] T2: fetch_daily(stock_id, start_date, end_date)
- [ ] T3: _transform(raw) pivot 邏輯
- [ ] T4: save(rows) INSERT OR REPLACE
- [ ] T5: fetch_and_save 串接
- [ ] T6: 錯誤處理

## Test Cases（10 個 Test Class，12 個 test function）
- TC1: 2日資料 → 2列 pivot 結果（2 functions）
- TC2: foreign_buy 正確
- TC3: dealer_buy = 自行買賣 + 避險累加
- TC4: dealer_net = 兩種自營商 net 累加
- TC5: institutional_net = foreign + trust + dealer net
- TC6: 去重（同 stock+date → 1筆）
- TC7: source = 'finmind'
- TC8: empty data 拋 Exception
- TC9: 缺 name 欄位拋 Exception
- TC10: fetch_and_save 串接（2 functions）

## Definition of Done
- [ ] import：InstitutionalFetcher
- [ ] TC1 PASS：2 passed
- [ ] TC2 PASS：foreign_buy 正確
- [ ] TC3 PASS：dealer_buy 累加正確
- [ ] TC4 PASS：dealer_net 累加正確
- [ ] TC5 PASS：institutional_net 正確
- [ ] TC6 PASS：去重
- [ ] TC7 PASS：source='finmind'
- [ ] TC8 PASS：Exception on empty
- [ ] TC9 PASS：Exception on missing field
- [ ] TC10 PASS：2 passed
- [ ] pytest 全綠：12 passed in Y.ZZs
- [ ] git diff --stat tests/ 為空

## 變更紀錄
| 時間 | 內容 |
|------|------|
| - | 初版 |
