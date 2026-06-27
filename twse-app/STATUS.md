# 專案狀態

**版本**：v0.4（框架重構後）
**迭代輪次**：3（規格審查 + Stub 實作 + 框架建立）
**日期**：2026-06-27

---

## 完成事項

- [x] 53/53 規格審查通過
- [x] 8 項 API stub → 真實實作（movers + 5 個 analysis + strategy scans）
- [x] TypeScript 零新增錯誤（`npx tsc --noEmit`）
- [x] E2E 測試 7 個（Playwright）

## 當前步驟：7_驗收閘門

## 待做（下輪迭代）

| 優先 | 項目 | 檔案 |
|------|------|------|
| P1 | 建立 `check.sh` 自動驗收腳本 | 新建 |
| P1 | 建立 `ERRORS.md` 記錄已踩過的坑 | 新建 |
| P2 | 清理 `as any` 型別斷言 | dashboard.ts + strategy.ts |
| P2 | AbortController 防 race condition | MarketsView.tsx |
| P3 | Strategy scan 完整測試（需更多 seed 資料） | tests/ |

## 歷史報錯

見 ERRORS.md
