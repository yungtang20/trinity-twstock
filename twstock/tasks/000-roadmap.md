# Trinity Roadmap

## 依賴圖

```
PHASE 0 ─ Architecture (已完成)
    │
PHASE 1 ─ Database & Core
    │
    ├── PHASE 2a ─ FinMind API
    ├── PHASE 2b ─ TWSE/TPEx Quotes
    └── PHASE 2c ─ TDCC + Institutional
            │
        PHASE 3 ─ Indicator Engine
            │
            ├── PHASE 4a ─ MA Strategy
            ├── PHASE 4b ─ Support/Resistance Strategy
            ├── PHASE 4c ─ Chips Strategy
            ├── PHASE 4d ─ Patterns Strategy
            └── PHASE 4e ─ Prediction Strategy
                    │
                PHASE 5 ─ Strategy Runner & CLI
                    │
                PHASE 6 ─ React Dashboard
```

## Task 清單

| Task | 名稱 | Phase | 狀態 | 依賴 |
|------|------|-------|------|------|
| 001 | FinMind API Integration | 2a | `pending` | — |
| 002 | TWSE/TPEx Quotes | 2b | `pending` | — |
| 003 | TDCC + Institutional Data | 2c | `pending` | — |
| 004 | Indicator Engine (calculator) | 3 | `pending` | 001 |
| 005 | MA Strategy | 4a | `pending` | 004 |
| 006 | Support/Resistance Strategy | 4b | `pending` | 004 |
| 007 | Chips Strategy | 4c | `pending` | 004, 003 |
| 008 | Patterns Strategy | 4d | `pending` | 004 |
| 009 | Prediction Strategy | 4e | `pending` | 004 |
| 010 | Strategy Runner & CLI | 5 | `pending` | 005-009 |
| 011 | React Dashboard | 6 | `pending` | 010 |

## 規則
- 一次只能有一個 Task 狀態為 In Progress
- 必須前一 Phase 的所有 Task Done 才能開始下一 Phase
- 每個 Task 必須通過 DoD 才能 Close
- 2a/2b/2c 可以並行（無依賴）

## 目前進度
- 2026-06-27: 建立 Linear Workflow 結構，開始執行 Task 001
