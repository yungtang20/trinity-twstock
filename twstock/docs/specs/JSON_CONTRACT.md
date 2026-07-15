# JSON_CONTRACT.md — TRINITY JSON 輸出合約

> 所有 JSON 輸出必須符合此合約。React、CLI、API、MCP 共用同一格式。

---

## 策略分析輸出（單一股票）

```json
{
  "strategy": "撑壓分析",
  "stock_id": "2330",
  "stock_name": "台積電",
  "date": "2026-06-26",
  "score": 75,
  "signal": "BUY",
  "confidence": 80,
  "summary": "短期支撐強勁，建議逢低買進",
  "details": {}
}
```

### 欄位說明

| 欄位 | 型別 | 必填 | 說明 |
|------|------|------|------|
| strategy | string | 是 | 策略名稱 |
| stock_id | string | 是 | 股票代號 |
| stock_name | string | 否 | 股票名稱 |
| date | string | 是 | 分析日期 YYYY-MM-DD |
| score | integer | 是 | 綜合評分 0~100 |
| signal | string | 是 | BUY / HOLD / SELL |
| confidence | integer | 是 | 信心指數 0~100 |
| summary | string | 是 | 一段話摘要 |
| details | object | 是 | 策略專屬詳細資料 |

### signal 定義

| 值 | 說明 |
|----|------|
| BUY | 建議買進 |
| HOLD | 建議持有 |
| SELL | 建議賣出 |
| UNKNOWN | 無法判斷 |

### score 計算原則

- 0~30：強烈看空
- 31~50：中性偏弱
- 51~70：中性偏強
- 71~100：強烈看好

---

## 策略掃描輸出（全市場）

```json
{
  "strategy": "撑壓分析",
  "date": "2026-06-26",
  "total": 150,
  "results": [
    {
      "strategy": "撑壓分析",
      "stock_id": "2330",
      "score": 85,
      "signal": "BUY",
      "confidence": 80,
      "summary": "...",
      "details": {}
    },
    {
      "strategy": "撑壓分析",
      "stock_id": "2303",
      "score": 72,
      "signal": "BUY",
      "confidence": 65,
      "summary": "...",
      "details": {}
    }
  ]
}
```

### 欄位說明

| 欄位 | 型別 | 必填 | 說明 |
|------|------|------|------|
| strategy | string | 是 | 策略名稱 |
| date | string | 是 | 掃描日期 YYYY-MM-DD |
| total | integer | 是 | 符合條件的股票總數 |
| results | array | 是 | 結果列表（已排序） |

---

## strategy_runner.py 輸出格式

```json
{
  "stockId": "2330",
  "dataSource": "sqlite",
  "strategies": {
    "sr": {
      "strategy": "撑壓分析",
      "stock_id": "2330",
      "score": 75,
      "signal": "BUY",
      "confidence": 80,
      "summary": "...",
      "details": {},
      "source": "strategy/sr_analyzer.py"
    },
    "ma": {
      "strategy": "均線趨勢",
      "stock_id": "2330",
      "score": 65,
      "signal": "HOLD",
      "confidence": 60,
      "summary": "...",
      "details": {},
      "source": "strategy/ma_strategy.py"
    },
    "chips": {
      "strategy": "籌碼動能",
      "stock_id": "2330",
      "score": 70,
      "signal": "BUY",
      "confidence": 75,
      "summary": "...",
      "details": {},
      "source": "strategy/chips_strategy.py"
    },
    "pattern": {
      "strategy": "幾何型態",
      "stock_id": "2330",
      "score": 60,
      "signal": "HOLD",
      "confidence": 55,
      "summary": "...",
      "details": {},
      "source": "strategy/patterns_strategy.py"
    },
    "prediction": {
      "strategy": "AI 預測",
      "stock_id": "2330",
      "score": 68,
      "signal": "BUY",
      "confidence": 50,
      "summary": "...",
      "details": {},
      "source": "strategy/kronos_engine.py"
    }
  }
}
```

---

## 錯誤輸出格式

```json
{
  "error": true,
  "message": "無 2330 資料",
  "stock_id": "2330",
  "strategy": "撑壓分析"
}
```

---

## 版本資訊

| 項目 | 值 |
|------|-----|
| 合約版本 | v1.0 |
| 最後更新 | 2026-06-26 |
| 適用範圍 | 所有策略輸出、strategy_runner.py、未來 API/MCP |

---

## 變更規則

1. 新增欄位 → 必須可選（nullable），不影響現有消費者
2. 移除欄位 → 必須先 deprecated 一個版本週期
3. 修改欄位型別 → 視為 breaking change，合約版本 +1
4. 修改 signal 選項 → 必須保留舊選項（backward compatible）
