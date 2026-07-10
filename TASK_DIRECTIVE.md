# TASK DIRECTIVE

Task ID: TASK-0006
Permission Level: LEVEL 2
Source: User Request
Reason: patterns_strategy.py 批次化重構

## Objective
將 patterns_strategy.py 中的 _scan_one 逐股序列查詢改為批次 SQL + groupby 向量化計算，提升掃描效能。

## Change Budget
Maximum Files: 2
Maximum Lines: 100

## Allowed Changes
- twstock/strategy/patterns_strategy.py
- TASK_DIRECTIVE.md
- CURRENT_TASK.md

## Forbidden Changes
- 修改 BreakoutCandidate 欄位定義
- 修改 _display() 介面
- 修改 find_pivots / find_patterns 的核心演算法邏輯
- 執行 git commit / push

## Target Files
- twstock/strategy/patterns_strategy.py

## Implementation Plan
1. 將 scan() 中的 symbols 切分為 chunk_size=500 的批次。
2. 每批執行一次 SQL：SELECT stock_id, date, open, high, low, close, volume FROM klines_indicators WHERE stock_id IN (...) ORDER BY stock_id, date ASC。
3. Python 端用 groupby('stock_id', sort=False) 分組。
4. 每 group 執行 df = group.tail(CONTEXT_LEN * 2)。
5. 將 df 傳入後續的 find_pivots/find_patterns/BreakoutCandidate 邏輯。

## Acceptance Criteria
- ruff check 零錯誤
- mypy 零錯誤
- pytest 699 passed / 22 skipped
- git diff 需經 GLM-5.2 確認後才可 commit

## Human Decision Required
Yes (commit 前請先暫停讓我確認)
