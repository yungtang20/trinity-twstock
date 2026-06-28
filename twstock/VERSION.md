# VERSION.md — TRINITY 版本資訊

> 記錄各規格文件的版本，避免文件之間不同步。

---

## 總版本

| 項目 | 值 |
|------|-----|
| 專案版本 | v3.3 |
| 規範版本 | v1.0 |
| 最後更新 | 2026-06-26 |

---

## 規格版本

| 規格 | 版本 | 最後更新 | 檔案 |
|------|------|---------|------|
| Architecture | v1.0 | 2026-06-26 | `ARCHITECTURE.md` |
| Database Schema | v2.0 | 2026-06-26 | `DB_SCHEMA.md` |
| API Specification | v1.0 | 2026-06-26 | `API_SPEC.md` |
| Strategy Interface | v1.0 | 2026-06-26 | `ARCHITECTURE.md` |
| CLI | v1.0 | 2026-06-26 | `ARCHITECTURE.md` |
| Coding Rules | v1.0 | 2026-06-26 | `PROJECT_RULES.md` |
| Naming Rules | v1.0 | 2026-06-26 | `PROJECT_RULES.md` |
| Error Policy | v1.0 | 2026-06-26 | `ARCHITECTURE.md` |
| DB Operation Rules | v1.0 | 2026-06-26 | `ARCHITECTURE.md` |
| Unit Conversion | v1.0 | 2026-06-26 | `ARCHITECTURE.md` |
| Forward Adjustment | v1.0 | 2026-06-26 | `ARCHITECTURE.md` |

---

## 版本同步規則

1. 修改任何規格時，必須同步更新此表的版本號
2. 如果修改 backward incompatible，版本號 +1
3. 如果修改 backward compatible，版本號 +0.1
4. 如果只修正錯字，不更新版本號
