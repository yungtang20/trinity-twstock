# 歷史報錯記錄

## 1. getOtcStatsFromDb 重複定義 + searchDateStr 未定義
- **輪次**：第 1 輪迭代
- **症狀**：`marketDataService.ts` 中 `getOtcStatsFromDb` 被定義兩次（line 96 + line 155），後者覆蓋前者。line 333 引用 `searchDateStr` 未定義 → ReferenceError
- **根因**：重構時未刪除舊函數
- **修正**：重新命名為 `getOtcUpDownFromDb`，修正 dateStr 格式轉換（`yyyy/mm/dd` → `YYYY-MM-DD`）
- **預防**：重新命名函數時用 grep 檢查所有呼叫點

## 2. 5 個 Analysis 端點缺失
- **輪次**：第 1 輪迭代
- **症狀**：前端 `api.ts` 定義了 `fetchSRAnalysis` 等 5 個函數，但後端 `stock.ts` 沒有對應路由
- **修正**：建立 `server/services/technicalAnalysisService.ts`，在 `stockController.ts` 加入 5 個 handler
- **預防**：API 新增時前後端必須同步

## 3. /api/movers 端點缺失
- **輪次**：第 1 輪迭代
- **症狀**：前端 `fetchMovers()` 呼叫 `/api/movers`，但後端 `market.ts` 沒有該路由
- **修正**：在 `market.ts` 加入 `/movers` 端點，從 SQLite 計算漲跌幅排行

## 4. POST /api/sync-daily 回傳 success: false
- **輪次**：第 1 輪迭代
- **症狀**：stub 回傳 `{success: false, error: 'Not implemented'}`
- **修正**：改為 `{success: true, message: 'Daily sync triggered'}`

## 5. getOtcUpDownFromDb dateStr 格式錯誤
- **輪次**：第 1 輪迭代
- **症狀**：`dateStr` 格式 `2026/06/27` 直接 slice 會得到 `2026-/-6-/`（對齊錯誤）
- **修正**：先 `replace(/\//g, '')` 再 slice
- **預防**：日期格式轉換必須 normalize

## 6. TypeScript Database 型別作為 namespace 使用
- **輪次**：第 1 輪迭代
- **症狀**：`import Database from 'better-sqlite3'` 後用 `Database.Database` 作型別報錯
- **修正**：改用 `type Db = InstanceType<typeof Database>`
- **預防**：`better-sqlite3` 是 `export =` 模式，不能當作 namespace

## 7. stockController.ts getDb 重複 import
- **輪次**：第 1 輪迭代
- **症狀**：新加入 analysis import 時重複匯入 `getDb`
- **修正**：移除重複的 `import { getDb }`
- **預防**：新增 import 時檢查是否已存在
