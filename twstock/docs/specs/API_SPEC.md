# API_SPEC.md — TRINITY 外部 API 規格

> 所有外部 API 的 endpoint、參數、回應格式、錯誤處理。

---

## 1. FinMind API

| 項目 | 值 |
|------|-----|
| Base URL | `https://api.finmindtrade.com/api/v4/data` |
| Auth | `Authorization: Bearer {FINMIND_TOKEN}` |
| Rate Limit | 每小時 600 次（`_RateLimiter` 滑動視窗） |

### 常用 dataset

| dataset | data_id | 回傳欄位 |
|---------|---------|---------|
| TaiwanStockPrice | 股號 | stock_id, date, open, high, low, close, Trading_Volume, Trading_Money, ... |
| TaiwanStockInstitutionalInvestorsBuySell | 股號 | stock_id, date, Foreign_Investor_Buy, Foreign_Investor_Sell, Investment_Trust_Buy, Investment_Trust_Sell, ... |
| TaiwanStockShareholding | 股號 | stock_id, date, Foreign_Remaining_Shares, Foreign_Shareholding_Ratio |
| TaiwanStockInfo | "" | stock_id, stock_name, industry_category, market, type |

### 回應格式

```json
{
  "data": [
    {"stock_id": "2330", "date": "2026-06-26", ...}
  ],
  "msg": "success"
}
```

### 錯誤處理

- `msg != "success"` → 回傳空 DataFrame
- HTTP error → retry 3 次，仍失敗回傳空 DataFrame
- Timeout → retry 3 次（指數退避）

---

## 2. TWSE 官方 API

### 收盤行情（全市場）

| 項目 | 值 |
|------|-----|
| URL | `https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX` |
| Method | GET |
| Params | `date` (YYYYMMDD), `type=ALL`, `response=json` |
| 回傳 | `{"tables": [{"title": "每日收盤行情", "fields": [...], "data": [[...]]}]}` |

### 三大法人

| 項目 | 值 |
|------|-----|
| URL | `https://www.twse.com.tw/rwd/zh/fund/T86` |
| Method | GET |
| Params | `date` (YYYYMMDD), `selectType=ALLBUT0999`, `response=json` |
| 回傳 | `{"fields": [...], "data": [[...]]}` |

### 除權息（全市場）

| 項目 | 值 |
|------|-----|
| URL | `https://www.twse.com.tw/rwd/zh/exRight/TWT49U` |
| Method | GET |
| Params | `response=json`, `startDate` (YYYY-MM-DD), `endDate` (YYYY-MM-DD) |

### 即時報價

| 項目 | 值 |
|------|-----|
| URL | `https://mis.twse.com.tw/stock/api/getStockInfo.jsp` |
| Method | GET |
| Params | `ex_ch=tse_{股號}.tw`, `json=1`, `delay=0` |
| 回傳 | `{"msgArray": [{"c": "2330", "z": 720.5, "o": 718.0, "h": 722.0, "l": 717.5, "v": 5200, ...}]}` |
| 單位 | v = 張 |

### 交易日曆

| 項目 | 值 |
|------|-----|
| URL | `https://openapi.twse.com.tw/v1/holidaySchedule/holidaySchedule` |
| Method | GET |
| 回傳 | `[{"Date": "1150101", "Description": "元旦"}, ...]`（民國年） |

### 處置股票

| 項目 | 值 |
|------|-----|
| URL | `https://openapi.twse.com.tw/v1/announcement/punish` |
| Method | GET |
| 回傳 | `[{"Code": "3366", "DispositionPeriod": "115/06/01~115/06/30"}, ...]` |

---

## 3. TPEx 官方 API

### 收盤行情（全市場）

| 項目 | 值 |
|------|-----|
| URL | `https://www.tpex.org.tw/web/stock/aftertrading/otc_quotes_no1430/stk_wn1430_result.php` |
| Method | GET |
| Params | `l=zh-tw`, `d={ROC_DATE}`, `se=AL`, `s=0,asc,0` |
| ROC Date | `YYY/MM/DD`（民國年） |

### 三大法人

| 項目 | 值 |
|------|-----|
| URL | `https://www.tpex.org.tw/web/stock/3insti/daily_trade/3itrade_hedge_result.php` |
| Method | GET |
| Params | `l=zh-tw`, `o=json`, `se=AL`, `t=D`, `d={ROC_DATE}` |
| 回傳 | 7 組買賣超（g1_g7），非 foreign/trust/dealer 格式 |

### 除權息

| 項目 | 值 |
|------|-----|
| URL | `https://www.tpex.org.tw/web/stock/exright/dailyquo/exDailyQ_result.php` |
| Method | GET |
| Params | `l=zh-tw`, `d={開始日期}`, `ed={結束日期}`, `se=EW`, `s=0,asc,0` |

---

## 4. TDCC 集保 API

### OpenAPI（本週）

| 項目 | 值 |
|------|-----|
| URL | `https://openapi.tdcc.com.tw/v1/opendata/1-5` |
| Method | GET |
| Params | `date=YYYY-MM-DD`（本週六） |
| 回傳 | `[{"證券代號": "2317", "持股分級": "17", "股數": 1234567, "人數": 890, ...}]` |

### 官網爬蟲（單一股票歷史）

| 項目 | 值 |
|------|-----|
| URL | `https://www.tdcc.com.tw/portal/zh/smWeb/qryStock` |
| Method | GET → POST（需 CSRF token） |
| 用途 | 單一股票特定日期的集保資料 |

---

## 5. LongCat AI

| 項目 | 值 |
|------|-----|
| URL | `{LONGCAT_API_URL}/chat/completions` |
| Auth | `Authorization: Bearer {LONGCAT_API_KEY}` |
| Model | `{LONGCAT_MODEL}`（預設 LongCat-2.0-Preview） |
| Method | POST |
| Body | `{"model": "...", "messages": [...], "max_tokens": 128000, "temperature": 0.7}` |

---

## 6. Kronos AI

| 項目 | 值 |
|------|-----|
| Model ID | `NeoQuasar/Kronos-base` |
| Tokenizer | `NeoQuasar/Kronos-Tokenizer-base` |
| Max Context | 512 tokens |
| Predict Length | 5 days |
| Location | `d:/twse/kronos/`（模型權重） |

---

## 錯誤處理統一規則

| HTTP Status | 行為 |
|-------------|------|
| 200 | 正常處理 |
| 404 | Skip，回傳空 DataFrame |
| 500 | Retry 3 次（指數退避 1s, 2s, 4s） |
| Timeout | Retry 3 次（指數退避） |
| JSON Parse Error | Skip，log warning |

## 速率限制

| API | 限制 | 實作 |
|-----|------|------|
| FinMind | 600 次/小時 | `_RateLimiter` 滑動視窗 |
| TWSE/TPEx | 無明確限制 | 全市場一次抓，不逐檔 |
| TDCC OpenAPI | 無明確限制 | 每週一次 |
| TDCC 官網爬蟲 | 每 0.15s 一次 | `time.sleep(0.15)` |
