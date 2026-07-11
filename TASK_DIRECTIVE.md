# TASK DIRECTIVE

Task ID: TASK-0007
Permission Level: LEVEL 2
Source: User Request
Reason: Interactive holiday marking for days when both markets return empty data

## Objective
Add interactive prompt during daily update: when TWSE and TPEX both return empty data, allow the user to mark the day as a market holiday so future runs skip it. Prevent user-marked holidays from being overwritten by official calendar sync.

## Change Budget
Maximum Files: 3
Maximum Lines: 80

## Allowed Changes
- twstock/official/updater.py (empty-market-data interactive prompt block)
- twstock/official/trading_calendar.py (sync must not overwrite user-marked entries)
- TASK_DIRECTIVE.md / CURRENT_TASK.md (statebook)

## Forbidden Changes
- 修改 _filter_valid_stocks 邏輯
- 修改 upsert_shareholding / 集保寫入目標(已實驗證實為健康)
- 修改 DataProcessor 的核心 batch UPSERT 行為
- 在 test suite 路徑上阻斷 stdin/input(不可在測試中 hang)

## Target Files
- twstock/official/updater.py
- twstock/official/trading_calendar.py

## Technical Notes
- 互動只在 `sys.stdin.isatty()` 為 True 時啟用,CI/test 一律跳過
- 使用者輸入預設為 N (no),需明確輸入 'y' 才標記
- 標記語意: INSERT OR REPLACE `stock_trading_calendar(date, is_open=0, description='使用者標記休市')`
- 官方同步遇到 `description` 包含「使用者標記」的列不得覆蓋 (保留 is_open=0)
- 不可使用 rich console / [yellow] 等非標準語法,維持 plain print + flush=True (與 updater.py 風格一致)

## Acceptance Criteria
- ruff check 零錯誤
- mypy 零錯誤
- pytest 699 passed / 22 skipped
- 手動 dry-run 確認 two-empty 情境會跳出互動提示
- git commit + push origin main 需依 Task Owner 明確授權

## Human Decision Required
Yes (push 前需 owners 確認 — 本次業主要求測試後直接放行)
