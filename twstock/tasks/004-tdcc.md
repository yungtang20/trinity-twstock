# Issue 004: TDCC Shareholding Fetcher

## Phase
2a — Data Source

## Status
pending

## 依賴
- DB_SCHEMA.md v3.0 (done)

## 需求
實作集保持股資料抓取模組：
- 資料為週頻（每週五更新）
- 解析持股分級表，計算大股東/散戶比例
- 寫入 shareholding_unified（source='tdcc'）
- 禁止寫入 VIEW tdcc_shareholding

## API 規格
- URL: https://smart.tdcc.com.tw/opendata/getOD.ashx?id=1-5
- 回傳 list of dict（已解析後格式）：
  {date_roc: str, stock_id: str, bracket: str, people: int, shares: int}
- date_roc 格式：YYYMMDD（ROC 年份無斜線，例 "1130105"）
- bracket 值：'1~999', '1000~5000', '5001~10000',
              '10001~15000', '15001~20000', '20001~30000',
              '30001~40000', '40001~50000', '50001~100000',
              '100001~200000', '200001~400000', '400001以上', '合計'

## 分類規則
- whale（大股東）：bracket == '400001以上'
- retail（散戶）：bracket 為 '1~999' + '1000~5000' + '5001~10000' 三者合計
- total：bracket == '合計'

## 欄位對應

| shareholding_unified | 計算方式 |
|----------------------|----------|
| stock_id | 直接 |
| date | date_roc → YYYY-MM-DD（ROC+1911）|
| source | 寫死 'tdcc' |
| total_shares | 合計 bracket 的 shares |
| total_people | 合計 bracket 的 people |
| whale_shares | 400001以上 bracket 的 shares |
| whale_people | 400001以上 bracket 的 people |
| whale_ratio | whale_shares / total_shares * 100 |
| retail_ratio | retail_shares / total_shares * 100 |
| foreign_shares | NULL（來自不同資料源）|
| foreign_ratio | NULL |

## Task Plan
- [ ] T1: 定義 TDCCFetcher(db)
- [ ] T2: fetch_by_date(date_str) 呼叫 API
- [ ] T3: _parse_roc_date(roc_str) → YYYY-MM-DD（格式 YYYYMMDD）
- [ ] T4: _transform(raw_rows) 計算各欄
- [ ] T5: save(rows) INSERT OR REPLACE
- [ ] T6: fetch_and_save(date_str) 串接

## Test Cases（10 個 Test Class，12 個 test function）
- TC1: 1 股 1 日資料 → 1 列，欄位齊全（2 functions）
- TC2: ROC 日期 "1130105" → "2024-01-05"
- TC3: whale_shares = 400001以上 bracket 的 shares
- TC4: whale_ratio = whale_shares / total_shares * 100
- TC5: retail 為三個散戶 bracket 的 shares 合計
- TC6: retail_ratio = retail_shares / total_shares * 100
- TC7: total_shares 來自合計 bracket
- TC8: source = 'tdcc'
- TC9: 寫入 shareholding_unified（不是 VIEW）
- TC10: fetch_and_save 串接（2 functions）

## Definition of Done
- [ ] import：TDCCFetcher
- [ ] TC1 PASS：2 passed
- [ ] TC2 PASS：date == "2024-01-05"
- [ ] TC3 PASS：whale_shares 正確
- [ ] TC4 PASS：whale_ratio 正確
- [ ] TC5 PASS：retail_shares 正確
- [ ] TC6 PASS：retail_ratio 正確
- [ ] TC7 PASS：total_shares 正確
- [ ] TC8 PASS：source == 'tdcc'
- [ ] TC9 PASS：INSERT 到 shareholding_unified
- [ ] TC10 PASS：2 passed
- [ ] pytest 全綠：12 passed in Y.ZZs
- [ ] git diff --stat tests/ 為空

## 變更紀錄
| 時間 | 內容 |
|------|------|
| - | 初版 |
