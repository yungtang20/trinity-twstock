# TASK DIRECTIVE

Task ID: TASK-0008
Permission Level: LEVEL 2
Source: User Request
Reason: Refactor run_db_maintenance() — Rich Markup / connection handling / error prompt

## Objective
Refactor `twstock/tui/menu.py:run_db_maintenance()` to clean up Rich markup bare-printing, use explicit connection open/close, and strengthen SQLite error handling (especially the "locked" case).

## Change Budget
Maximum Files: 1
Maximum Lines: 30

## Allowed Changes
- twstock/tui/menu.py (run_db_maintenance body only)

## Forbidden Changes
- 修改其他 run_daily_update / run_historical_update_menu 等無關函式
- 修改 run_db_maintenance 介面(仍為 `def run_db_maintenance() -> None`)
- 更動 stock_history / shareholding_unified / stock_meta 等資料表的實際資料
- 在验证通过前執行 git commit / push

## Acceptance Criteria
- ruff check 零錯誤
- mypy 零錯誤
- pytest 699 passed / 22 skipped 維持不變
- 本地 dry-run 確認「locked」分支訊息正確(用 mock conn.execute raise sqlite3.OperationalError("database is locked") 觸發)
- git commit + push 前需貼完整 diff + ruff/mypy/pytest 結果,等 Task Owner 明確說「可以 commit」

## Human Decision Required
Yes (commit / push 前需 owners 明示)
