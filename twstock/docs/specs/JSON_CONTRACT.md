# TRINITY JSON Contract v2

所有 JSON 邊界（`JsonWriter`、`strategy_runner.py` 與未來 API）必須使用 `twstock.strategy.result_contract.normalize_strategy_result()` 或 `normalize_json_payload()`。策略內部可以保留相容欄位，但對外輸出遵守本文件。

## 單一策略結果

```json
{
  "strategy": "ma",
  "stock_id": "2330",
  "stock_name": "台積電",
  "date": "2026-07-20",
  "score": 75,
  "signal": "BUY",
  "confidence": 68,
  "summary": "價格位於中期均線之上。",
  "details": {}
}
```

| 欄位 | 型別 | 規則 |
|---|---|---|
| `strategy` | string | 策略識別值。 |
| `stock_id` | string | 股票代號。 |
| `stock_name` | string | 名稱不可得時為空字串。 |
| `date` | string | 分析日；不可得時為空字串。 |
| `score` | integer | 0–100。 |
| `signal` | string | 僅可為 `BUY`、`HOLD`、`SELL`、`UNKNOWN`。 |
| `confidence` | integer | 0–100；未知為 0。 |
| `summary` | string | 面向使用者的簡短結論。 |
| `details` | object | 策略細節與保留的相容欄位。 |

輸入端可接受歷史值 `bullish`、`bearish`、`neutral`，但正規化 JSON 一律輸出 `BUY`、`SELL`、`HOLD`。

## 市場掃描

```json
{
  "strategy": "chips",
  "date": "2026-07-20",
  "total": 2,
  "results": [
    { "strategy": "chips", "stock_id": "2330", "stock_name": "", "date": "", "score": 75, "signal": "BUY", "confidence": 60, "summary": "", "details": {} }
  ]
}
```

每一個 `results` 成員都必須符合單一策略結果契約，且 `total` 必須等於結果陣列長度。

## 策略彙整器

```json
{
  "stock_id": "2330",
  "stockId": "2330",
  "data_source": "sqlite",
  "dataSource": "sqlite",
  "strategies": {
    "ma": { "strategy": "ma", "stock_id": "2330", "stock_name": "", "date": "", "score": 50, "signal": "HOLD", "confidence": 0, "summary": "", "details": {} }
  }
}
```

`stockId` 與 `dataSource` 是既有消費者的相容欄位；新增程式應優先讀取 snake_case 欄位。`strategies` 的每一項都必須符合單一策略結果契約，可額外帶 `source` 作追蹤。

## 錯誤格式

```json
{
  "error": true,
  "message": "找不到股票資料",
  "stock_id": "2330",
  "strategy": "ma"
}
```

最少要有 `error: true` 與非空 `message`。如錯誤可歸屬於股票或策略，應額外填入 `stock_id`、`strategy`。

## 演進規則

- 不移除既有 public 欄位；淘汰欄位先標記 deprecated 並維持相容 adapter。
- 新欄位可加在頂層或 `details`；有結構性破壞時升 major contract version。
- JSON 序列化必須處理日期、NumPy scalar 與空值，不能因展示欄位而失敗。
