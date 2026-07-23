# TRINITY 文件索引

本索引是專案文件的入口。所有連結均以本檔案所在的 `docs/meta/` 為基準。

## 開始前先讀

| 目的 | 文件 |
|---|---|
| Agent 工作範圍與禁止事項 | [AGENTS.md](../../AGENTS.md) |
| 系統分層、資料流與匯入規則 | [ARCHITECTURE.md](../architecture/ARCHITECTURE.md) |
| 專案總覽圖 | [SYSTEM_OVERVIEW.md](../architecture/SYSTEM_OVERVIEW.md) |
| 開發與相容性規範 | [PROJECT_RULES.md](../architecture/PROJECT_RULES.md) |

## 規格與開發流程

| 主題 | 文件 |
|---|---|
| 開發流程 | [DEVELOPMENT_GUIDE.md](../process/DEVELOPMENT_GUIDE.md) |
| AI／人工修改完成檢查 | [AI_CHECKLIST.md](../process/AI_CHECKLIST.md) |
| SQLite schema、views 與單位 | [DB_SCHEMA.md](../specs/DB_SCHEMA.md) |
| 外部資料來源 | [API_SPEC.md](../specs/API_SPEC.md) |
| 穩定 JSON 輸出 | [JSON_CONTRACT.md](../specs/JSON_CONTRACT.md) |
| 查詢、批次與記憶體規範 | [PERFORMANCE_RULES.md](../specs/PERFORMANCE_RULES.md) |
| 測試資料規範 | [TEST_DATA.md](../specs/TEST_DATA.md) |
| 新策略模板 | [strategy_template.py](../../strategy/templates/strategy_template.py) |

## 環境與歷史

| 主題 | 文件 |
|---|---|
| 可重現依賴 | [DEPENDENCIES.md](DEPENDENCIES.md) |
| 版本與契約版本 | [VERSION.md](VERSION.md) |
| 變更紀錄 | [CHANGELOG.md](CHANGELOG.md) |
| 目前專案上下文 | [CONTEXT.md](CONTEXT.md) |

## 資料修復（需人工確認）

`commands/data_repair.py` 僅處理已知且可判定的壞資料；它不下載、不推測、也不補造行情。先在已備份的資料庫上執行唯讀檢視：

```powershell
python -m twstock.commands.data_repair
```

確認統計結果後，才可對備份後的目標資料庫執行：

```powershell
python -m twstock.commands.data_repair --apply
```

修復後應重新從已驗證來源更新受影響的日線、法人或持股資料，再重算指標。
