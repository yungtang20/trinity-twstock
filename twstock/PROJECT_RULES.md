# PROJECT_RULES.md — TRINITY 專案開發規範

> 所有開發者（人 / AI）必須遵循的專案級別規則。

---

## 專案設計哲學

1. SQLite 為唯一資料來源
2. 不做程式交易、自動下單、回測、排程、通知
3. 所有分析以日 K 資料為主
4. 所有策略互相獨立
5. 模組低耦合、高內聚
6. 優先可維護性，其次效能，最後才增加新功能

---

## Coding Style

### 基本原則

- 每個 public function 必须有 docstring
- 每個 public class 必须有 class-level docstring
- 禁止 magic number（定義為常數）
- 禁止硬編碼路徑（用 `Path` 相對路徑）
- 每個檔案開頭必須有模組說明（至少一行）

### 程式碼風格

```python
# 使用 4 spaces 縮排，不 tab
# 每行不超過 120 字元
# 空行分隔邏輯區塊
# 常量使用 UPPER_CASE
# 變數使用 snake_case
# 類別使用 PascalCase
```

---

## 命名規則

| 動詞前綴 | 用途 | 範例 |
|---------|------|------|
| `fetch_` | 抓資料（外部 API） | `fetch_twse_quotes()` |
| `update_` | 更新資料（寫入 DB） | `update_official_daily()` |
| `compute_` | 數值運算 | `compute_adj_factor()` |
| `build_` | 建立 DataFrame | `build()` |
| `save_` | 寫 DB | `save_stock_meta()` |
| `run_` | 執行（策略 / 主流程） | `run_strategy()` |
| `render_` | 畫畫面 | `render_dashboard()` |
| `is_` | 布林判斷 | `is_trading_day()` |
| `get_` | 取得設定 / 狀態 | `get_connection()` |

---

## Import 規則

### 允許的依賴方向

```
main.py → official/*, strategy/*, fetcher, processor, calculator, db, display, terminal
official/* → fetcher, processor, db, utils, display
fetcher → processor, db
processor → db
strategy/* → klines_helper, calculator, db, display
calculator → db
```

### 禁止的依賴方向

```
strategy → official
official → strategy
processor → strategy
fetcher → strategy
calculator → official
任何模組 → 循環 import
```

### import 順序

```python
# 1. 標準庫
import os
import sys

# 2. 第三方套件
import pandas as pd
import numpy as np

# 3. 本專案模組
from db import get_connection
from display import price_rich
```

---

## Commit 規則

- commit message 使用英文
- 格式：`type: description`
- type 範例：feat, fix, refactor, docs, chore
- 範例：`feat: add support resistance analysis`
- 每次 commit message 結尾加上 Co-Authored-By

---

## 禁止事項

1. 不得刪除現有功能
2. 不得修改 public function name
3. 不得修改 DB schema
4. 不得修改 CLI argument 格式
5. 不得修改 JSON output format
6. 不得引入 circular import
7. 不得使用 print() 代替 logging（CLI 互動提示除外）

---

## 修改原則

1. 新增功能優先新增 module
2. 不修改既有 module（除非 backward compatible）
3. 舊 function 可以 deprecated，不能移除
4. 新功能必須有 docstring
5. 新功能必須符合命名規則
