# Issue 002: TWSE Official Data Fetcher

## Phase
2a — Data Source

## Status
pending

## 依賴
- DB_SCHEMA.md v3.0 (done)
- Issue 001: FinMindFetcher (done)

## 需求
實作 TWSE 官方日線資料抓取模組：
- 呼叫 TWSE exchangeReport/STOCK_DAY API（以月為單位）
- ROC 日期轉換（113/01/02 → 2024-01-02）
- 數字去逗號（22,388,968 → 22388968）
- 跳過停牌行（close == '--'）
- INSERT OR REPLACE 寫入 stock_history
- source = 'official'

## API 規格
- URL: https://www.twse.com.tw/exchangeReport/STOCK_DAY
- 參數: response=json, date=YYYYMMDD（當月第一天）, stockNo=股票代號
- Response.stat == "OK" → 成功
- Response.data: list of list（非 list of dict）
- Response.fields: ["日期","成交股數","成交金額","開盤價","最高價","最低價","收盤價","漲跌價差","成交筆數"]
- 日期格式: ROC year/MM/DD（例 "113/01/02"，ROC year + 1911 = CE year）
- 數字含逗號（例 "22,388,968"）
- 停牌行: close == "--" → 整行跳過

## 欄位對應

| stock_history | TWSE fields | 換算 |
|---------------|-------------|------|
| stock_id | （呼叫時傳入） | 直接 |
| date | 日期 | ROC→CE，格式 YYYY-MM-DD |
| open | 開盤價 | 去逗號，float |
| high | 最高價 | 去逗號，float |
| low | 最低價 | 去逗號，float |
| close | 收盤價 | 去逗號，float |
| volume | 成交股數 | 去逗號，int |
| amount | 成交金額 | 去逗號，int |
| trade_count | 成交筆數 | 去逗號，int |
| spread | 漲跌價差 | 去逗號，float |
| adj_factor | — | 寫死 1.0 |
| source | — | 寫死 'official' |

## Task Plan
- [ ] T1: 定義 TWSEFetcher(db)
- [ ] T2: fetch_monthly(stock_id, year, month) 呼叫 API
- [ ] T3: _roc_to_ce(roc_date_str) → YYYY-MM-DD
- [ ] T4: _transform(raw, stock_id) 映射 + 去逗號 + 跳過 '--'
- [ ] T5: save(rows) INSERT OR REPLACE
- [ ] T6: fetch_and_save(stock_id, start_date, end_date) 按月迭代
- [ ] T7: 錯誤處理（stat != OK 拋 Exception；empty data 拋 Exception）

## Test Cases（10 個 Test Class，14 個 test function）
- TC1: 三日資料 → 3 列（停牌行排除），欄位齊全，無 adj_close（3 functions）
- TC2: ROC 日期 "113/01/02" → "2024-01-02"
- TC3: 成交股數 "22,388,968" → 22388968
- TC4: 成交金額 "13,130,657,808" → 13130657808
- TC5: 最高/最低映射（2 functions）
- TC6: close=="--" 的行跳過
- TC7: adj_factor=1.0
- TC8: stat != "OK" 拋 Exception
- TC9: source='official'
- TC10: fetch_and_save 串接（2 functions）

## Definition of Done
- [ ] import：TWSEFetcher
- [ ] TC1 PASS：3 passed
- [ ] TC2 PASS：date == "2024-01-02"
- [ ] TC3 PASS：volume == 22388968
- [ ] TC4 PASS：amount == 13130657808
- [ ] TC5 PASS：2 passed
- [ ] TC6 PASS：停牌行不在結果中
- [ ] TC7 PASS：adj_factor == 1.0
- [ ] TC8 PASS：Exception on bad stat
- [ ] TC9 PASS：source == 'official'
- [ ] TC10 PASS：2 passed
- [ ] pytest 全綠：14 passed in Y.ZZs
- [ ] git diff --stat tests/ 為空

## 變更紀錄
| 時間 | 內容 |
|------|------|
| - | 初版 |
