# TRINITY 架構規格

TRINITY 是以台股日 K 為核心的決策輔助系統。SQLite 是分析時的唯一正式資料來源；系統不提供自動交易、回測、排程或通知功能。

## 分層與資料流

```text
外部資料來源（FinMind、TWSE、TPEx、TDCC）
        │
        ▼
market_data/ 與 official/ 取得並正規化資料
        │
        ▼
core/processor.py 驗證與批次寫入
        │
        ▼
taiwan_stock_unified.db
   ├── calculator.py：持久化 MA／ATR／VWAP
   ├── strategy/*：只讀分析
   ├── main.py + commands/*：CLI／TUI
   └── strategy_runner.py + ui/output_writer.py：策略彙整與 JSON
```

`commands/data_repair.py` 是獨立且預設唯讀的資料品質工具；必須先檢視統計與備份，才可使用 `--apply`。

## 模組責任

| 層 | 主要模組 | 責任 |
|---|---|---|
| 入口 | `main.py`、`strategy_runner.py` | argparse、TUI 與輸出編排；不可實作資料寫入細節。 |
| 命令 | `commands/` | 將 CLI 參數路由到明確的應用服務。 |
| 資料取得 | `market_data/`、`official/` | 呼叫外部來源、解析 payload、回傳 DataFrame；不直接承擔策略判斷。 |
| ETL | `core/processor.py` | 欄位正規化、資料驗證與批次 UPSERT。 |
| 儲存 | `db.py`、`db_admin.py`、`db_maintenance.py` | 唯一連線入口、schema bootstrap、索引、唯讀健檢與受保護的備份／最佳化。 |
| 指標 | `calculator.py` | 讀取日線、向量化計算，並以批次方式寫入 `stock_indicators`。 |
| 策略 | `strategy/` | 只讀 SQLite 資料，產生策略結論；共用 `strategy/result_contract.py` 統一輸出。 |
| 顯示 | `tui/`、`ui/`、`display.py` | Rich／JSON 呈現，不自行重新計算交易訊號。 |

## 匯入規則

所有 production code 必須使用 package-qualified import：

```python
from twstock.db import get_connection
from twstock.core.processor import DataProcessor
```

禁止在 production code 使用 `from db import ...`、修改 `sys.path` 以加入 package 目錄，或讓同一模組同時以 top-level 與 `twstock.*` 載入。直接執行支援的入口檔時，只能將專案的父目錄加入 `sys.path`，以維持單一 `twstock.db` module state。

禁止相依方向：

```text
strategy  -> official
official  -> strategy
processor -> strategy
calculator -> official
```

策略只可讀取 SQLite 已保存的資料；若 UI 需要更新資料，必須透過明確命令或使用者確認的更新流程完成後再分析。

## SQLite 與資料品質規則

- 所有連線由 `twstock.db.get_connection()` 建立；讀取使用 `readonly=True`。
- 資料庫內的成交量與法人／持股數量以原始「股」儲存；成交金額以原始「元」儲存。顯示層才可換算為張、億等單位。
- 寫入使用 `executemany()`，同一批次只 commit 一次。不得在逐列迴圈中 commit。
- 查詢須使用索引欄位與合理的日期／筆數上限。全市場處理要分批讀取，不能把全部歷史資料常駐記憶體。
- 欄位缺失、日期無效、價格不合理或關鍵數值全空的 payload 必須被拒絕或明確記錄，不能靜默寫成可分析資料。
- 完整 schema、相容性 views 與索引請以 [DB_SCHEMA.md](../specs/DB_SCHEMA.md) 為準。

## 策略介面與輸出

現有策略 class 以 `analyze(stock_id)` 為相容性介面；掃描和命令包裝可以在其上提供額外功能。策略原始結果可能保留歷史欄位，但所有 JSON 邊界都必須經過：

```python
from twstock.strategy.result_contract import normalize_strategy_result
```

正規化後至少有：`strategy`、`stock_id`、`stock_name`、`date`、`score`、`signal`、`confidence`、`summary`、`details`。訊號只有 `BUY`、`HOLD`、`SELL` 或 `UNKNOWN`。詳細定義請見 [JSON_CONTRACT.md](../specs/JSON_CONTRACT.md)。

## 錯誤與安全規則

- TLS 驗證失敗不得自動改成不驗證；修正憑證、CA bundle 或網路設定後再試。
- 外部 API timeout／5xx 可以有限次重試；4xx、schema 錯誤與資料驗證錯誤要回傳可識別錯誤，不能以空資料冒充成功。
- `api.env` 是本機設定，不可提交。只提交 `api.env.example`；已洩漏的 token 必須在供應商端輪替。
- 不要吞掉資料寫入或 schema 錯誤。能降級的讀取功能應記錄 warning；會影響資料正確性的寫入應失敗並保留原因。

## 啟動方式

```powershell
# 從專案父目錄執行（建議）
python -m twstock.main

# 從專案目錄直接執行也支援
python main.py

# 策略 JSON 彙整
python strategy_runner.py 2330 --json
```

依賴安裝與測試命令請見 [DEPENDENCIES.md](../meta/DEPENDENCIES.md)。
