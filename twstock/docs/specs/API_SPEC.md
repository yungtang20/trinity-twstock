# TRINITY 外部資料來源規格

外部來源只供更新流程使用；策略分析以 SQLite 已保存資料為準。端點與 payload 會隨供應商變動，解析器、fixture 與欄位驗證必須一起更新。

## FinMind

| 項目 | 值 |
|---|---|
| Base URL | `https://api.finmindtrade.com/api/v4/data` |
| 認證 | `Authorization: Bearer {FINMIND_TOKEN}` |
| 實作 | `market_data/historical_fetcher.py` |

主要 dataset 包含日線、法人買賣超、外資持股與股票基本資料。日線常見來源欄位 `max`／`min` 必須映射到 DB 的 `high`／`low`；成交量與金額維持原始股數／元。

## TWSE 與 TPEx

| 資料 | 實作 |
|---|---|
| 上市／上櫃日線與成交資訊 | `official/quotes.py`、`market_data/fetcher.py` |
| 上市／上櫃法人 | `official/institutional.py` |
| 股利 | `official/dividend_crawler.py` |
| 交易行事曆 | `official/trading_calendar.py` |
| 即時快照 | `market_data/historical_fetcher.py`、TWSE MIS |

TPEx 日期多使用民國年格式，解析器要在 ETL 邊界統一成 ISO 日期。上市與上櫃法人資料都必須輸出完整標準欄位：foreign、trust、dealer 的 buy、sell、net，以及 institutional net。

## TDCC

| 項目 | 值 |
|---|---|
| Open data | `https://openapi.tdcc.com.tw/` |
| 網頁歷史來源 | `https://www.tdcc.com.tw/` |
| 實作 | `official/tdcc.py` |

TDCC payload 在進入 `shareholding_unified` 前需要標準化 `date`、`stock_id` 與 `source='tdcc'`。不得送入僅處理外資持股欄位的寫入方法。

`/v1/opendata/1-5` 是最新全市場快照；`date` query 參數不得視為歷史期別切換保證。
寫入日期必須取自 payload 的「資料日期」（欄名可能帶 UTF-8 BOM）；缺少、無效或同一
payload 有多個期別時必須拒絕寫入。每日更新可重複取得最新快照，但必須以
`(stock_id, payload date, source)` 冪等 UPSERT，不能以本機星期六推測期別，也不能只用全表
`MAX(date)` 判定快照已完整。

## 行情與輔助來源

`market_data/fetcher.py` 也使用 Yahoo 台股頁面、TWSE MIS 與 TPEx 公開資料取得市場顯示資訊。這些資料屬更新／展示用途；失敗時不應讓策略直接改用未驗證網路回應。

主畫面於本機官方交易日曆標示開市、且系統時間介於 09:00（含）至 13:30（不含）時，優先呼叫 TWSE MIS 即時服務；若即時服務沒有有效行情才降級使用 MI_INDEX。首頁第一次顯示及使用者從其他功能返回首頁時同步一次行情；停留在首頁等待輸入期間不重畫畫面，也不自動呼叫 API。畫面標題的日期時間代表該次首頁更新時的系統時鐘，不冒充外部 API 的資料時間。

## 可選 AI 服務

- LongCat：僅在明確啟用的功能使用 `LONGCAT_API_KEY`；模型名稱、URL 與 token 上限由執行環境設定，不在本文件硬編碼。
- Kronos：vendored engine 需要 `torch`、`huggingface-hub`、`tqdm`、`einops`。模型與 tokenizer 路徑必須從設定或使用者指定位置取得，不能假設固定磁碟路徑。

任何 heuristic 都必須明確標示為 heuristic，不能宣稱是模型推論。

## 錯誤與 TLS

- timeout 與可恢復的 5xx 可以有限次指數退避重試。
- 4xx、JSON／欄位解析錯誤與資料驗證失敗要回傳可識別失敗，不能寫入空白成功資料。
- TLS 憑證錯誤不得自動關閉驗證；修正 CA bundle、系統時間或網路攔截設定後再試。
