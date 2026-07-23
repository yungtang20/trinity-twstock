# TRINITY 專案上下文

## 產品語言

| 名稱 | 定義 |
|---|---|
| 日 K | 一個交易日的 open、high、low、close、volume、amount。 |
| 法人 | 外資、投信、自營商的買賣超資料。 |
| TDCC | 集保股權分散表；與外資持股同存於 `shareholding_unified`，以 `source` 區隔。 |
| 指標 | 可由日 K 重建的 MA、ATR、VWAP 等衍生資料。 |
| 策略結果 | 經 result contract 正規化後的分析輸出，而非交易指令。 |

## 實際模組邊界

```text
twstock/
├── main.py                 CLI／TUI 入口
├── commands/               命令編排與獨立 data_repair 工具
├── market_data/            FinMind、行情與歷史資料取得
├── official/               TWSE、TPEx、TDCC、股利、行事曆取得
├── core/processor.py       資料驗證與 UPSERT
├── db.py / db_admin.py     單一連線入口、schema／views／migration
├── calculator.py           持久化技術指標
├── strategy/               SQLite-only 策略與 result contract
├── ui/ / tui/              Rich、JSON 與終端 UI
└── vendor/kronos/          可選模型相依的 vendored 程式
```

## 重要不變量

1. SQLite 是分析正式來源；策略不直接下載資料。
2. 原始股數與元保存在 DB，換算只發生於顯示層。
3. `shareholding_unified` 的唯一鍵含 `source`，不可把 TDCC 欄位送入外資持股寫入路徑。
4. `institutional_data` 的標準買賣與淨買賣欄位都要保存，不能在欄位選取時遺失。
5. `stock_indicators` 是衍生資料；日線變更或資料修復後必須重算。
6. 所有 package import 使用 `twstock.*`，避免兩份 DB module state。

## 影響分析

`dependency_graph.json` 是依目前 production Python AST 產生的靜態本地依賴圖。它不取代實際測試，也不會涵蓋動態 import 或外部套件。修改 public 模組前，應：

1. 查閱直接依賴者。
2. 以 temporary SQLite DB 執行受影響的 integration test。
3. 更新文件與策略 JSON 契約。
