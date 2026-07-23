# TRINITY 開發規範

本規範與 [ARCHITECTURE.md](ARCHITECTURE.md) 一起構成實作約束。若文件與可執行 schema 有歧異，以 `db_admin.py` 與 [DB_SCHEMA.md](../specs/DB_SCHEMA.md) 為準，並在同一變更中修正文檔。

## 相容性底線

- 不移除 public function、CLI 參數或既有 JSON 欄位。
- 不修改既有 table 欄位或主鍵；只允許可重複的相容性 migration、索引與 read-only view。
- 不建立 circular import，也不以 top-level module alias 躲避 package import。
- 舊介面需要淘汰時，保留 adapter 並標記 deprecated，不可直接刪除。

## 程式風格

- public class 與 function 要有 docstring；型別可表達時使用 type hints。
- Python 使用四格縮排、`snake_case` function／變數、`PascalCase` class、`UPPER_CASE` 常數。
- 對外 I/O 使用 logging 或 Rich；library／資料層不可用 `print()` 當錯誤處理。
- 不可用 broad `except: pass` 吞掉寫入、schema 或資料驗證錯誤。

## 命名

| 前綴 | 用途 |
|---|---|
| `fetch_` | 從外部或儲存層取得資料 |
| `update_` | 更新既有資料或狀態 |
| `compute_` | 純計算 |
| `build_` | 建立結構化結果 |
| `save_` / `upsert_` | 寫入資料庫 |
| `run_` | 執行完整流程 |
| `render_` | 呈現 UI |
| `is_` / `get_` | 判斷或取得值 |

## Import 與執行

```python
from twstock.db import get_connection
from twstock.strategy.result_contract import normalize_strategy_result
```

不得使用：

```python
from db import get_connection
import db
```

直接啟動入口前，只可加入專案父目錄至 `sys.path`。測試不可使用 `os.chdir()` 改變全域工作目錄，也不可以 production DB 當 fixture。

## 資料庫與效能

- 正式寫入集中在 `DataProcessor` 或明確的管理／修復工具。
- 使用 `executemany()` 與交易批次；逐列 `execute()` 加 `commit()` 是禁止模式。
- 查詢需以 `stock_id`、`date` 等索引欄位限制；掃描以 SQL／DataFrame 批次處理，不能 N+1 查詢或逐檔 API 呼叫。
- 讀取使用 `get_connection(readonly=True)`；寫入後必須有可追溯的錯誤或 audit 記錄。

## JSON 與策略

- 策略相容介面是 `analyze(stock_id)`。
- 對外結果須透過 `normalize_strategy_result()`，訊號統一為 `BUY/HOLD/SELL/UNKNOWN`。
- 新欄位可加入 `details`；破壞性輸出變更須更新契約版本與 adapter。

## 完成前檢查

1. 編譯受影響 Python 檔，並執行相對應測試。
2. 驗證 import graph 沒有新 cycle 或 top-level alias。
3. 新寫入流程要測試空資料、重複 UPSERT、錯誤欄位與交易 rollback。
4. 新 schema bootstrap 必須在空白 temporary DB 驗證。
5. 更新對應規格、`dependency_graph.json` 與變更紀錄。
