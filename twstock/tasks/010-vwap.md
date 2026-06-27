# Issue 010: VWAP Calculator

## Phase
2b — Data Processing

## Status
pending

## 依賴
- DB_SCHEMA.md v3.0（含 stock_indicators）
- Issue 001（stock_history 已有 amount 和 volume）

## 需求
實作日 VWAP 計算模組：
- 讀取 stock_history 的 amount 和 volume
- VWAP = amount / volume（日線 VWAP，非日內累計）
- volume = 0 時 VWAP = NULL（避免除以零）
- UPSERT 寫入 stock_indicators.vwap（不動其他欄位）
- source = stock_history

## 計算公式
vwap(date) = amount / volume，volume = 0 時為 NULL

## Task Plan（放在 calculator.py）
- [ ] T1: 定義 VWAPCalculator(db)
- [ ] T2: calculate(stock_id)
- [ ] T3: calculate_all()

## 測試資料說明
5 天：
- volume: [1000, 2000, 3000, 4000, 0]
- amount: [10000, 22000, 33000, 44000, 0]
- VWAP:   [10.0,  11.0,  11.0,  11.0,  None]
  （最後一天 volume=0 → None）

## Test Cases（7 個 Test Class，8 個 test function）
- TC1: 5 天資料 → 5 筆 indicators，vwap 欄位存在（2 functions）
- TC2: VWAP = amount / volume = 10.0
- TC3: volume=0 → vwap = None
- TC4: UPSERT 不覆蓋 ma5（若 ma5 有值仍保留）
- TC5: 去重（執行兩次 → 仍 5 筆）
- TC6: calculate 回傳 int = 5
- TC7: DB 更新驗證（1 function）

## Definition of Done
- [ ] import：VWAPCalculator from calculator
- [ ] TC1 PASS：2 passed
- [ ] TC2 PASS：vwap = 10.0
- [ ] TC3 PASS：volume=0 → None
- [ ] TC4 PASS：UPSERT 不覆蓋 ma5
- [ ] TC5 PASS：去重
- [ ] TC6 PASS：回傳 int = 5
- [ ] TC7 PASS：DB 值正確
- [ ] pytest 全綠：8 passed in Y.ZZs
- [ ] git diff --stat tests/ 為空

## 變更紀錄
| 時間 | 內容 |
|------|------|
| - | 初版 |
