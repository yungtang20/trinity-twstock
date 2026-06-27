# DB_SCHEMA.md — TRINITY 資料庫規格 v3.0

> 資料庫檔案：taiwan_stock_unified.db（661MB，2,626,403 筆 stock_history）
> 所有日期格式：YYYY-MM-DD
> 原則：DB 存原始值，顯示層才轉換

---

## stock_meta — 股票基本資料（2,042 筆）

| 欄位 | 型別 | Null | Key | 說明 |
|------|------|------|-----|------|
| stock_id | TEXT | NO | PK | 股票代號 |
| stock_name | TEXT | NO | | 股票名稱 |
| industry_category | TEXT | YES | | 產業類別 |
| market | TEXT | NO | | TSE / OTC |
| type | TEXT | NO | | COMMON / INDEX |
| source | TEXT | YES | | 資料來源 |
| updated_at | DATETIME | YES | | CURRENT_TIMESTAMP |

---

## stock_trading_calendar — 交易日曆（7,059 筆）

| 欄位 | 型別 | Null | Key | 說明 |
|------|------|------|-----|------|
| date | TEXT | NO | PK | YYYY-MM-DD |
| is_open | INTEGER | NO | | 1=開市, 0=休市 |
| description | TEXT | YES | | 來源說明 |
| updated_at | DATETIME | YES | | CURRENT_TIMESTAMP |

---

## stock_history — 日 K 線（2,626,403 筆，核心表）

日期範圍：2018-05-21 ~ 2026-06-26，涵蓋 6,445 檔股票

| 欄位 | 型別 | Null | Key | 說明 |
|------|------|------|-----|------|
| stock_id | TEXT | NO | PK | 股票代號 |
| date | TEXT | NO | PK | YYYY-MM-DD |
| open | REAL | NO | | 開盤價 |
| high | REAL | NO | | 最高價 |
| low | REAL | NO | | 最低價 |
| close | REAL | NO | | 收盤價 |
| volume | INTEGER | NO | | 成交量（股，非張） |
| amount | INTEGER | NO | | 成交金額（元，非千萬元） |
| trade_count | INTEGER | YES | | 成交筆數 |
| spread | REAL | YES | | 差價 |
| adj_factor | REAL | YES | DEFAULT 1.0 | 前復權因子 |
| source | TEXT | YES | | 資料來源 |
| updated_at | DATETIME | YES | | CURRENT_TIMESTAMP |

**沒有 adj_close 欄位。** adj_close 由下游計算：close * adj_factor

**去重**：INSERT OR REPLACE，唯一鍵 (stock_id, date)

**索引**：idx_stock_history_stock_date ON (stock_id, date)

**實際樣本**：
```
('9962', '2026-06-26', 9.67, 9.75, 9.5, 9.68, 108, 103446, None, None, 1.0, 'official', '2026-06-26 11:10:18')
('9960', '2026-06-26', 32.0, 32.4, 31.9, 32.0, 73, 233630, None, None, 1.0, 'official', '2026-06-26 11:10:18')
```
注意 volume=108 是股數，amount=103446 是金額（元）

---

## dividend_events — 除權息事件（10,538 筆）

| 欄位 | 型別 | Null | Key | 說明 |
|------|------|------|-----|------|
| stock_id | TEXT | NO | PK | 股票代號 |
| date | TEXT | NO | PK | 除權息日期 |
| before_price | REAL | YES | | 前收盤價 |
| after_price | REAL | YES | | 後收盤價 |
| reference_price | REAL | YES | | 參考價 |
| cash_dividend | REAL | YES | DEFAULT 0 | 現金股利（元） |
| stock_dividend | REAL | YES | DEFAULT 0 | 股票股利 |
| source | TEXT | YES | | 資料來源 |
| updated_at | DATETIME | YES | | CURRENT_TIMESTAMP |

---

## institutional_data — 三大法人（989,562 筆）

| 欄位 | 型別 | Null | Key | 說明 |
|------|------|------|-----|------|
| stock_id | TEXT | NO | PK | 股票代號 |
| date | TEXT | NO | PK | 日期 |
| foreign_net | INTEGER | YES | DEFAULT 0 | 外資買賣超淨額（股） |
| trust_net | INTEGER | YES | DEFAULT 0 | 投信買賣超淨額（股） |
| dealer_net | INTEGER | YES | DEFAULT 0 | 自營商買賣超淨額（股） |
| institutional_net | INTEGER | YES | DEFAULT 0 | 三大法人合計（股） |
| source | TEXT | YES | | 資料來源 |
| updated_at | DATETIME | YES | | CURRENT_TIMESTAMP |
| foreign_buy | INTEGER | YES | DEFAULT 0 | 外資買進（股） |
| foreign_sell | INTEGER | YES | DEFAULT 0 | 外資賣出（股） |
| trust_buy | INTEGER | YES | DEFAULT 0 | 投信買進（股） |
| trust_sell | INTEGER | YES | DEFAULT 0 | 投信賣出（股） |
| dealer_buy | INTEGER | YES | DEFAULT 0 | 自營商買進（股） |
| dealer_sell | INTEGER | YES | DEFAULT 0 | 自營商賣出（股） |

---

## shareholding_unified — 集保+外資合併表（30,923 筆）

| 欄位 | 型別 | Null | Key | 說明 |
|------|------|------|-----|------|
| stock_id | TEXT | NO | PK | 股票代號 |
| date | TEXT | NO | PK | 日期 |
| source | TEXT | NO | PK | 'tdcc' 或 'twse' |
| total_shares | INTEGER | YES | | 總股數 |
| whale_ratio | REAL | YES | | 大股東持股比例（%） |
| retail_ratio | REAL | YES | | 散戶持股比例（%） |
| foreign_shares | INTEGER | YES | | 外資持股數 |
| foreign_ratio | REAL | YES | | 外資持股比例（%） |
| total_people | INTEGER | YES | | 總持有人數 |
| whale_shares | INTEGER | YES | | 大股東持股數 |
| whale_people | INTEGER | YES | | 大股東持有人數 |
| updated_at | TEXT | YES | | datetime('now','localtime') |

**主鍵**：(stock_id, date, source) 三欄組合鍵

---

## tdcc_shareholding — VIEW（不是 TABLE）

```
CREATE VIEW tdcc_shareholding AS
SELECT stock_id, date, total_shares, whale_ratio, retail_ratio,
       source, updated_at
FROM shareholding_unified
WHERE source = 'tdcc';
```

不能 INSERT INTO VIEW，寫入請用 INSERT INTO shareholding_unified 並設 source='tdcc'

---

## per_data — 本益比（1,545 筆）

| 欄位 | 型別 | Null | Key | 說明 |
|------|------|------|-----|------|
| stock_id | TEXT | NO | PK | 股票代號 |
| date | TEXT | NO | PK | 日期 |
| per | REAL | YES | | 本益比 |
| pbr | REAL | YES | | 股價淨值比 |
| pe_ratio | REAL | YES | | 本益比 |
| pb_ratio | REAL | YES | | 股價淨值比 |
| dividend_yield | REAL | YES | | 殖利率（%） |
| source | TEXT | YES | | 資料來源 |
| updated_at | DATETIME | YES | | CURRENT_TIMESTAMP |

---

## audit_log — 稽核日誌（3,323 筆）

| 欄位 | 型別 | Null | Key | 說明 |
|------|------|------|-----|------|
| log_id | INTEGER | NO | PK AI | 日誌 ID |
| stock_id | TEXT | YES | | 股票代號 |
| action | TEXT | YES | | 動作 |
| status | TEXT | YES | | 狀態 |
| detail | TEXT | YES | | 詳細資訊 |
| timestamp | TEXT | YES | | datetime('now','localtime') |

---

## stock_indicators — 技術指標（預計算快取）

| 欄位 | 型別 | Null | Key | 說明 |
|------|------|------|-----|------|
| stock_id | TEXT | NO | PK | 股票代號 |
| date | TEXT | NO | PK | 日期 |
| ma5 | REAL | YES | | 5 日均線 |
| ma20 | REAL | YES | | 20 日均線 |
| ma25 | REAL | YES | | 25 日均線 |
| ma60 | REAL | YES | | 60 日均線 |
| ma200 | REAL | YES | | 200 日均線 |
| vol_ma5 | REAL | YES | | 5 日量均 |
| vol_ma20 | REAL | YES | | 20 日量均 |
| vol_ma60 | REAL | YES | | 60 日量均 |
| bias_ma25 | REAL | YES | | 乖離率 (close-ma25)/ma25*100 |
| bias_ma60 | REAL | YES | | 乖離率 (close-ma60)/ma60*100 |
| bias_ma200 | REAL | YES | | 乖離率 (close-ma200)/ma200*100 |
| atr14 | REAL | YES | | 14 日 ATR（Wilder's EMA）|
| vwap | REAL | YES | | 日 VWAP = amount / volume |
| updated_at | DATETIME | YES | | CURRENT_TIMESTAMP |

**主鍵**：(stock_id, date)

**寫入方式**：UPSERT（INSERT ... ON CONFLICT DO UPDATE SET），各計算器只更新自己負責的欄位，不覆蓋其他欄位

**依賴**：stock_history（需先有日 K 線資料才能計算）

---

## 前復權公式

```
adj_factor(date) = 所有 event_date > date 的 (reference_price / before_price) 的連乘積
adj_close = close * adj_factor
最新日期 adj_factor = 1.0
```

---

## FinMind 欄位對應

| stock_history 欄位 | FinMind 欄位 | 換算 |
|--------------------|--------------|------|
| stock_id | stock_id | 直接 |
| date | date | 直接 |
| open | open | 直接 |
| high | max | 欄位名不同 |
| low | min | 欄位名不同 |
| close | close | 直接 |
| volume | Trading_Volume | 直接存（股） |
| amount | Trading_money | 直接存（元） |
| trade_count | Trading_turnover | 直接 |
| spread | spread | 直接 |
| adj_factor | — | 寫死 1.0 |
| source | — | 寫死 'finmind' |

> FinMind Trading_Volume 單位是股，跟 DB 一致，不做換算
> FinMind Trading_money 單位是元，跟 DB 一致，不做換算
