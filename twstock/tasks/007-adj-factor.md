# Issue 007: Adj Factor Calculator

## Phase
2b — Data Processing

## Status
pending

## 依賴
- DB_SCHEMA.md v3.0 (done)
- Issue 005: DividendFetcher (done，dividend_events 已有資料)

## 需求
實作前復權因子計算模組：
- 讀取 dividend_events 表
- 對每個股票的每個歷史日期計算 adj_factor
- adj_factor(date) = 所有 event_date > date 的 (reference_price / before_price) 連乘積
- 最新日期 adj_factor = 1.0（無未來事件）
- before_price = 0 的事件跳過（避免除以零）
- 更新 stock_history.adj_factor

## 計算公式
adj_factor(d) = ∏ (ref_i / before_i) for all i where event_date_i > d and before_i > 0
最新日 adj_factor = 1.0

## Task Plan
- [ ] T1: 定義 AdjFactorCalculator(db)（在 calculator.py）
- [ ] T2: calculate(stock_id) 計算單一股票
- [ ] T3: calculate_all() 計算所有在 dividend_events 的股票
- [ ] T4: 更新 stock_history.adj_factor

## 注意事項
- 此類別放在 calculator.py（不是 fetcher.py）
- calculator.py 可能已存在其他 class，禁止刪除或修改
- 如果 calculator.py 不存在則建立

## Test Cases（10 個 Test Class，13 個 test function）
- TC1: 無除權息事件 → 所有日期 adj_factor=1.0（2 functions）
- TC2: 單次除權息 → 事件前日期 adj_factor = ref/before
- TC3: 單次除權息 → 事件當日及之後 adj_factor = 1.0
- TC4: 兩次除權息 → 兩次事件前的日期 adj_factor 為兩個因子連乘
- TC5: before_price=0 的事件跳過（不拋錯）
- TC6: 最新日期 adj_factor 一定是 1.0
- TC7: calculate 回傳更新列數（int）
- TC8: 多次執行冪等（結果相同）
- TC9: calculate_all 回傳 dict {stock_id: count}
- TC10: 實際 DB 更新驗證（2 functions）

## Definition of Done
- [ ] import：AdjFactorCalculator from calculator
- [ ] TC1 PASS：2 passed
- [ ] TC2 PASS：adj_factor = ref/before 前的日期
- [ ] TC3 PASS：事件當日及後 adj_factor=1.0
- [ ] TC4 PASS：兩次事件連乘
- [ ] TC5 PASS：before_price=0 跳過
- [ ] TC6 PASS：最新日 adj_factor=1.0
- [ ] TC7 PASS：回傳 int
- [ ] TC8 PASS：冪等
- [ ] TC9 PASS：calculate_all 回傳 dict
- [ ] TC10 PASS：2 passed
- [ ] pytest 全綠：13 passed in Y.ZZs
- [ ] git diff --stat tests/ 為空

## 變更紀錄
| 時間 | 內容 |
|------|------|
| - | 初版 |
