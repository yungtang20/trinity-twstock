# DOCUMENT_INDEX.md — TRINITY 文件索引

> 一頁導航所有文件。人和 AI 都能快速找到需要的內容。

---

## 快速導覽

| 你想做什麼 | 看哪份文件 | 行數 |
|-----------|-----------|------|
| **AI 啟動、工作守則** | [`AGENTS.md`](AGENTS.md) | ~70 |
| **完整架構與規範** | [`ARCHITECTURE.md`](ARCHITECTURE.md) | ~450 |
| **專案開發規範** | [`PROJECT_RULES.md`](PROJECT_RULES.md) | ~110 |
| **新增功能流程** | [`DEVELOPMENT_GUIDE.md`](DEVELOPMENT_GUIDE.md) | ~160 |
| **修改完成驗收** | [`AI_CHECKLIST.md`](AI_CHECKLIST.md) | ~50 |
| **資料庫 Schema** | [`DB_SCHEMA.md`](DB_SCHEMA.md) | ~140 |
| **外部 API 規格** | [`API_SPEC.md`](API_SPEC.md) | ~170 |
| **系統架構圖** | [`SYSTEM_OVERVIEW.md`](SYSTEM_OVERVIEW.md) | ~60 |
| **JSON 輸出合約** | [`JSON_CONTRACT.md`](JSON_CONTRACT.md) | ~130 |
| **效能規範** | [`PERFORMANCE_RULES.md`](PERFORMANCE_RULES.md) | ~130 |
| **測試資料規範** | [`TEST_DATA.md`](TEST_DATA.md) | ~60 |
| **策略開發模板** | [`strategy/templates/strategy_template.py`](strategy/templates/strategy_template.py) | ~160 |
| **相依套件版本** | [`DEPENDENCIES.md`](DEPENDENCIES.md) | ~70 |
| **版本資訊** | [`VERSION.md`](VERSION.md) | ~40 |
| **變更歷史** | [`CHANGELOG.md`](CHANGELOG.md) | ~50 |

---

## 文件分類

### 啟動入口
| 文件 | 用途 | 誰讀 |
|------|------|------|
| `AGENTS.md` | AI Agent 啟動時的第一份文件 | AI |
| `DOCUMENT_INDEX.md` | 一頁導航所有文件 | 人 + AI |

### 架構與規範
| 文件 | 用途 |
|------|------|
| `ARCHITECTURE.md` | 完整架構與規範（母體文件） |
| `PROJECT_RULES.md` | 專案級開發規範 |
| `SYSTEM_OVERVIEW.md` | 系統架構圖（30 秒理解） |

### 開發指南
| 文件 | 用途 |
|------|------|
| `DEVELOPMENT_GUIDE.md` | 新增功能流程 |
| `AI_CHECKLIST.md` | 修改完成自我驗收 |
| `PERFORMANCE_RULES.md` | 效能規範 |

### 技術規格
| 文件 | 用途 |
|------|------|
| `DB_SCHEMA.md` | 資料庫完整規格 |
| `API_SPEC.md` | 外部 API 規格 |
| `JSON_CONTRACT.md` | JSON 輸出合約 |
| `DEPENDENCIES.md` | 相依套件版本 |

### 開發資源
| 文件 | 用途 |
|------|------|
| `strategy/templates/strategy_template.py` | 策略開發模板 |
| `TEST_DATA.md` | 測試資料規範 |

### 版本管理
| 文件 | 用途 |
|------|------|
| `CHANGELOG.md` | 變更歷史 |
| `VERSION.md` | 規格版本資訊 |

---

## 文件依賴關係

```
AGENTS.md（啟動入口）
    ↓ 閱讀
ARCHITECTURE.md（完整規範）
    ↓ 引用
PROJECT_RULES.md / DB_SCHEMA.md / API_SPEC.md / JSON_CONTRACT.md
    ↓ 參考
DEVELOPMENT_GUIDE.md / AI_CHECKLIST.md / PERFORMANCE_RULES.md
    ↓ 資源
strategy/templates/ / TEST_DATA.md / DEPENDENCIES.md
    ↓ 管理
CHANGELOG.md / VERSION.md
```

---

## 版本資訊

| 項目 | 值 |
|------|-----|
| 索引版本 | v1.0 |
| 最後更新 | 2026-06-26 |
