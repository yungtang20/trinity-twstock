# DEVELOPMENT_GUIDE.md — TRINITY 新功能開發指南

> 當你要「新增一個功能」時，照這份流程走，不會漏步驟。

---

## 新增一個 Strategy

### 步驟 1：建立策略模組

```
strategy/my_new_strategy.py
```

內容必須包含：

```python
def analyze(params: dict) -> dict:
    """單一股票分析，回傳統一格式"""

def run_strategy(params: dict) -> None:
    """策略入口，負責渲染畫面"""

def scan_market(vol: int = 500) -> list[dict]:
    """全市場掃描，從 DB 讀取"""
```

### 步驟 2：加入 Registry

編輯 `strategy/strategies.py`，在 `STRATEGY_REGISTRY` 新增一筆：

```python
STRATEGY_REGISTRY = {
    ...
    "6": {
        "name": "我的新策略",
        "module": my_new_strategy,
        "description": "策略說明",
        "params_example": "--code 2330",
    },
}
```

### 步驟 3：加入 CLI

編輯 `main.py` 的 `argparse` 區塊，確認 `--strategy-id` 支援新編號。

### 步驟 4：加入 Rich 輸出

在 `run_strategy()` 中使用 Rich Console 渲染：

```python
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()
```

使用 `display.py` 的配色工具：

```python
from display import price_rich, chg_color, vol_fmt
```

### 步驟 5：加入 Scan

`scan_market()` 必須從 SQLite 讀取，不碰外部 API：

```python
from db import get_connection
conn = get_connection(readonly=True)
df = pd.read_sql("SELECT ...", conn)
```

### 步驟 6：更新文件

- 更新 `ARCHITECTURE.md` 的 Strategy Interface 章節
- 更新 `AGENTS.md` 的快速導覽

### 步驟 7：測試

```bash
# 單股測試
python main.py strategy --strategy-id 6 --code 2330

# 全市場掃描
python main.py strategy --strategy-id 6 --scan --vol 500

# 統一輸出器測試
python strategy_runner.py 2330
```

---

## 新增一個 API 資料源

### 步驟 1：在 `official/` 下建立新模組

```
official/my_new_source.py
```

### 步驟 2：加入 `official/__init__.py` 匯出

### 步驟 3：在 `db_admin.py` 新增資料表（如需）

### 步驟 4：在 `processor.py` 新增 upsert 方法

### 步驟 5：在 `updater.py` 加入更新流程

### 步驟 6：更新 `ARCHITECTURE.md` Schema

---

## 新增 CLI Command

### 步驟 1：在 `main.py` 的 argparse 新增 action

```python
parser.add_argument(
    "action",
    choices=['update', 'official', 'my_new_cmd', ...],
)
```

### 步驟 2：建立 handler function

```python
def my_new_command(args):
    ...
```

### 步驟 3：在 `if __name__ == '__main__'` 加入 dispatch

---

## 修改既有模組

### 原則

1. 只改必要的，不改不必要的
2. 保持 backward compatible
3. 舊 function 可以 deprecated，不能移除
4. 修改後必須檢查所有依賴它的模組

### 檢查清單

```
□ 找出所有 import 這個 function 的地方
□ 確認回傳格式不變
□ 確認參數簽名不變
□ 確認 CLI 輸出不變
□ 確認 JSON format 不變
```

---

## 常見陷阱

| 陷阱 | 避免方式 |
|------|---------|
| 在 strategy 裡直接調 API | 所有資料來自 SQLite |
| 單位換算不一致 | 所有 ingestion 先換算為張 |
| 逐筆 commit | 使用 executemany |
| 忘記處理 empty DataFrame | 每個 fetch 後檢查 `.empty` |
| 忘記處理 Windows encoding | 開頭加 encoding fix |
| 修改了 public function name | 先看 Registry 有沒有被引用 |
| 引入 circular import | 依賴方向永遠是上層→下層 |
