# TRINITY 版本資訊

| 項目 | 目前版本 |
|---|---|
| 應用程式 | v3.3.0 |
| SQLite schema | v3 |
| JSON contract | v2 |
| 文件整理日期 | 2026-07-22 |

## 版本原則

- 修補錯誤或補齊文件：patch。
- 向後相容的新功能、欄位或 view：minor。
- 移除 public API、CLI 參數、既有 JSON 欄位或 table 契約：major；目前不允許未經明確 migration 的破壞性變更。

文件版本以各文件標題為準；資料庫 schema 的可執行來源是 `db_admin.py`。
