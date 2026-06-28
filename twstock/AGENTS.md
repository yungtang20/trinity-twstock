# AGENTS.md — TRINITY 台股分析平台

> AI Agent 啟動時的第一份文件。100 行內講完「你是誰、你要做什麼、你不能做什麼」。

---

## 專案定位

**台股日線分析 Decision Support System。**

- SQLite 是唯一正式資料來源
- 不做自動交易、不回測、不排程、不通知
- 所有分析以日 K 為主

---

## 文件導覽

啟動時先讀 `DOCUMENT_INDEX.md` 找到需要的文件。

| 你想做… | 看… |
|---------|------|
| 了解完整架構 | `ARCHITECTURE.md` |
| 專案開發規範 | `PROJECT_RULES.md` |
| 新增一個策略 | `DEVELOPMENT_GUIDE.md` |
| 修改完成自我驗收 | `AI_CHECKLIST.md` |
| 資料庫欄位詳情 | `DB_SCHEMA.md` |
| API 規格 | `API_SPEC.md` |
| JSON 輸出格式 | `JSON_CONTRACT.md` |
| 效能規範 | `PERFORMANCE_RULES.md` |
| 測試資料規範 | `TEST_DATA.md` |
| 策略開發模板 | `strategy/templates/strategy_template.py` |
| 系統架構圖 | `SYSTEM_OVERVIEW.md` |
| 相依套件版本 | `DEPENDENCIES.md` |
| 版本資訊 | `VERSION.md` |
| 變更歷史 | `CHANGELOG.md` |

---

## 工作前

1. 閱讀 `DOCUMENT_INDEX.md`
2. 根據任務閱讀對應文件
3. 確認任務範圍，只改必要的

## 修改程式必須遵守

| 規範 | 檔案 |
|------|------|
| Architecture Rule | `ARCHITECTURE.md` — 允許 / 禁止 import |
| Coding Rule | `PROJECT_RULES.md` — 禁止修改 Public API |
| Naming Rule | `PROJECT_RULES.md` — 8 種動詞前綴 |
| Error Policy | `ARCHITECTURE.md` — 每種情境的行為 |
| DB Rule | `ARCHITECTURE.md` — executemany / Index |
| CLI Rule | `ARCHITECTURE.md` — argparse 唯一入口 |
| Strategy Interface | `ARCHITECTURE.md` — analyze / run_strategy / scan_market |
| Performance | `PERFORMANCE_RULES.md` — 禁止 N+1 查詢 |

## 絕對禁止

- 修改 DB Schema（欄位 / 資料表）
- 修改 Public Function Name
- 修改 CLI Argument 格式
- 刪除現有功能
- 引入 Circular Import

## 新增功能

- 優先新增 Module，不修改既有 Module
- 必須 backward compatible
- 舊 function 可以 deprecated，不能移除

## 完成後檢查清單

```
□ Import 正常（無 syntax error）
□ 無 Circular Import
□ CLI 可正常執行
□ SQLite 可正常開啟
□ 所有 Strategy 可執行
□ Rich Console 輸出正常
□ JSON Output 格式正確
□ 單位換算一致（股→張）
```
