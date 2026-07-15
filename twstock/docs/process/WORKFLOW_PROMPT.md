# Trinity Linear Workflow

你現在進入 Linear Workflow 模式。

## 核心規則
1. 你一次只能處理一個 Task
2. 禁止同時修改兩個以上的 Task
3. 沒有跑完測試就禁止宣告完成
4. 每一步都要留下紀錄

## 工作流程

### Step 1 — 載入上下文
依序閱讀：
1. AGENTS.md
2. PROJECT_RULES.md
3. ARCHITECTURE.md
4. DEVELOPMENT_GUIDE.md
5. AI_CHECKLIST.md
6. DB_SCHEMA.md
7. API_SPEC.md

### Step 2 — 讀取當前任務
閱讀 tasks/ 中 status 為 `pending` 且依賴全部 `done` 的第一個 Task。
將其狀態更新為 `in-progress`。

### Step 3 — 分析需求
- 確認依賴是否真的完成
- 列出需要了解的既有程式碼
- 確認測試框架與 mock 策略

### Step 4 — 執行 Task Plan
逐項完成 Task Plan 中的每個子任務（T1, T2...）。
每完成一項，更新 checkbox。

### Step 5 — 建立測試
根據 Test Cases 建立 pytest 測試檔。
先確認測試可以「預期失敗」（確認測試本身有效）。

### Step 6 — 實作
寫程式碼讓測試通過。

### Step 7 — 驗證
執行：
```bash
pytest tests/test_XXX.py -v
```

### Step 8 — 修正
如果有失敗：
- 分析失敗原因
- 修正程式碼（不是改測試）
- 重新執行

### Step 9 — DoD 檢查
逐項檢查 Definition of Done。
全部打勾才能繼續。

### Step 10 — 關閉 Task
- 更新 status 為 `done`
- 填寫變更紀錄
- 告知使用者：「Task XXX 完成，準備進入下一個 Task」

## 禁止事項
- 禁止跳過測試
- 禁止一次處理多個 Task
- 禁止在測試失敗時宣告完成
- 禁止修改測試來迎合錯誤的程式碼
- 禁止沒有閱讀上游文件就開始寫
