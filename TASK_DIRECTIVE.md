# TASK DIRECTIVE

Task ID: TASK-0012 (Final)
Permission Level: LEVEL 2
Source: User Request
Reason: UI/UX bundle: system-time header + market-title timestamp + dynamic intraday/post-market detection

## Objective
Bundle three related UI modifications — (1) header always shows real system time, (2) market overview title shows API data timestamp, (3) market mode (盤中/盤後) dynamically detected by comparing market field changes instead of hardcoded clock ranges — into a single deployment commit.

## Change Budget
Maximum Files: 2
Maximum Lines: ~52

## Allowed Changes
- twstock/market_data/cache.py (MarketCache: _prev_data / _is_data_changed / get_market_mode / snapshot in _async_fetch_worker)
- twstock/tui/render.py (render_dashboard market_mode block + _render_market_panel title + _render_header)

## Forbidden Changes
- 修改 fetch_market_indices 回傳結構(巳有 6 個欄位)
- 更動 MarketCache.get() / get_status() / invalidate() 介面
- 在验证通过前執行 git commit / push

## Completion Criteria
- ruff check 零錯誤(cache.py + render.py)
- mypy 零錯誤(cache.py + render.py)
- pytest 699 passed / 22 skipped 維持不變
- 手動五態 dry-run 验證(首次 → 🔴 盤後;不變 → 🔴 盤後;price 變 / amount 變 / l_up 變 → 🟢 盤中)
- 部署至 origin main

## Completed Tasks (Deployment)
  ✅ TASK-0010  feat(ui): Header time strict system time
  ✅ TASK-0011  feat(ui): Market overview title with API data timestamp
  ✅ TASK-0012  feat(ui): Dynamic market mode via 6-field comparison

Deployment Commit: d7842e4
Deployed: 2026-07-12 (d7842e4 → origin main)

## Human Decision Required
(Deployment authorized by Task Owner in dialogue)
