# TASK DIRECTIVE

Task ID: TASK-0014
Permission Level: LEVEL 2
Source: User Request
Reason: Fine-tune market overview title format — date-only (no time) + market mode indicator

## Objective
Modify the market overview (_render_market_panel) title in `twstock/tui/render.py` to:- Drop the time portion (HH:MM:SS)- Keep only the date in ROC format with HYPHENS (e.g. `115-07-09`, NOT `115/07/09`)- Append the market mode indicator (🟢 盤中 / 🔴 盤後)- Target format: `📊 市場:  115-07-09 🔴 盤後`

## Change Budget
Maximum Files: 1
Maximum Lines: 10

## Allowed Changes
- twstock/tui/render.py (_render_market_panel title + signature to accept market_mode; render_dashboard call site)

## Forbidden Changes
- 修改 to_roc_date 工具(共用,輸出格式不改成爲影響其它地方)
- 修改 MarketCache / 行情抓昏逻辑
- 在验证通过前執行 git commit / push

## Acceptance Criteria
- ruff check 零錯誤(render.py)- mypy 零錯誤(render.py)
- pytest 699 passed / 22 skipped
- 手動 dry-run 验證 title 输出符格式 `📊 市場:  115-07-09 🔴 盤後`以及 fallback `📊 市場: 即時行情(尚無日期)` 仍在.date 使用 hyphen 而非 slash
- git commit + push 前需貼 diff + ruff/mypy/pytest,等 owners 明示

## Human Decision Required
Yes (commit / push 前需 owners 明示)
