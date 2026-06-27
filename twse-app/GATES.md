# 驗收_gate

## 自動驗收（check.sh）

```bash
bash check.sh
```

## 53 項手動檢查清單

### A. 型別與介面（4 項）
- [ ] `AppView` 涵蓋 5 個頁面
- [ ] `MarketStat` 數值欄位型別為 number
- [ ] `StockData` 介面包含所有 `lib/api.ts` 使用的欄位
- [ ] 掃描型別都有 `stock_id` + `stock_name`

### B. API 端點（28 項）
見 FLOWS.md — 每個端點需驗證 method / path / response format

### C. 資料源 Fallback（5 項）
- [ ] FinMind API 有 10s timeout
- [ ] Supabase 失敗有 catch
- [ ] SQLite 資料 < 10 筆觸發 mock
- [ ] Mock 用 seeded random
- [ ] 同步流程 spawn 正確腳本

### D. 技術指標（6 項）
- [ ] MA / EMA / MACD / RSI / KD / ATR 公式正確
- [ ] 資料不足時回傳 null

### E. 錯誤處理（4 項）
- [ ] 所有端點 try-catch
- [ ] DB 失敗回傳 'DB not connected'
- [ ] 前端 success:false 顯示錯誤 + 重試
- [ ] ErrorBoundary 包住根組件

### F. E2E 測試（7 項）
見 tests/real-data.spec.ts
