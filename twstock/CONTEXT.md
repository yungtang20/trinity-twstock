# twstock 領域詞彙（Domain Glossary）

本文件記錄 twstock 專案的核心領域概念與架構邊界。
架構審閱與重構時以此為統一語言。

---

## 領域概念（Domain Concepts）

| 詞彙 | 定義 | 備註 |
|------|------|------|
| **Stock** | 上市/上櫃股票，由 4 碼 stock_id 識別 | 中謂「股號」「代號」 |
| **Price Record** | 一筆交易日記錄：date, open, high, low, close, volume | 存放於 `stock_history` 表 |
| **Technical Indicator** | 由價量資料衍生的數學指標（SMA, EMA, RSI, MACD, KDJ, Bollinger） | 計算邏輯應單一來源 |
| **Institutional Trade** | 三大法人買賣超資料（foreign, trust, dealer） | 含買進、賣出、淨買賣超 |
| **TDCC Shareholding** | 集保戶股權分散表，記錄各持股級距人數與股數 | 週頻率更新 |
| **Dividend Event** | 除權息事件，含除權息日期與股利金額 | 影響股價還原計算 |
| **Suspended Stock** | 處置股票，注意股資訊警示 | |
| **Market Index** | 大盤指數，含加權指數（TAIEX）與櫃買指數（OTC） | 即時盤中資料 |
| **K-Line** | K 線圖資料（開高低收量的時間序列） | 用於策略分析與視覺化 |

---

## 架構邊界（Module Boundaries）

```
twstock/
├── main.py              # 入口：argparse + dispatch（< 100 行）
├── commands/            # CLI 子命令（args → execute()）
│   ├── update.py
│   ├── indicators.py
│   ├── intraday.py
│   ├── official.py
│   └── dividend.py
├── tui/                 # 互動式選單
│   ├── app.py           # TUIApp 類別（狀態封裝）
│   └── render.py        # Dashboard 渲染
├── market_data/         # 即時盤中資料
│   ├── fetcher.py       # Yahoo / TWSE MIS / TPEx 抓取
│   └── cache.py         # 市場指數快取邏輯
├── utils.py             # 共用工具（date, http, safe_float）
├── fetcher.py           # 歷史資料 FinMind/官方 API 抓取模組
├── db.py                # DB 連線
├── db_admin.py          # DB schema、migration、SQL VIEW
├── processor.py         # 資料庫寫入（upsert 管線）
├── calculator.py        # 以 pandas 計算技術指標
├── display.py           # Rich 格式化函式
├── terminal.py          # Console 實例
├── input_helper.py      # 跨平台鍵盤輸入（msvcrt / termios）
├── retry.py             # HTTP retry 邏輯
├── api_config.py        # Token 讀取
├── config.py            # Re-export（待移除）
├── longcat_vision.py    # LongCat AI 視覺分析
├── strategy/            # 策略分析模組
│   ├── strategies.py    # 登錄表 + interactive_menu + run_strategy_cli
│   ├── sr_analyzer.py
│   ├── ma_strategy.py
│   ├── chips_strategy.py
│   ├── prediction_strategy.py
│   ├── patterns_strategy.py
│   ├── kronos_engine.py
│   ├── composites.py    # 複合分析（原 run_quick_analysis）
│   ├── _utils.py
│   ├── klines_helper.py
│   └── indicators.py
└── official/            # TWSE/TPEx/集保/除權息 官方資料抓取
    ├── updater.py
    ├── quotes.py
    ├── institutional.py
    ├── tdcc.py
    ├── suspended.py
    ├── dividend_crawler.py
    ├── dividend_daily.py
    ├── trading_calendar.py
    └── utils.py
```

---

## 架構規則（Architecture Rules）

### 1. 寫入路徑唯一
所有資料庫寫入經過 `processor.py` 的 `upsert_*` 方法。`db_admin.py` 的 `save_*` 函式為遺留相容層，新寫入不增加 `db_admin.save_*` 呼叫。

### 2. 指標計算單一來源
指標計算以 `db_admin.py` 的 `klines_indicators` VIEW 為 hot path 來源。`calculator.py` 的 `IndicatorEngine` 為 pandas 備援路徑。`indicators.py` 已棄用。

### 3. 命令介面統一
每個 `commands/*.py` 暴露 `execute(args)` 函式。`main.py` 只根據 `args.action` 分派，不直接實作商業邏輯。

### 4. TUI 狀態封裝
`tui/app.py` 的 `TUIApp` 類別封裝 market cache、render loop 與輸入處理。不暴露模組層級全域變數。

### 5. HTTP 即時資料不注入
`market_data/fetcher.py` 直接呼叫 `requests`。測試時透過 `responses` 或 `requests_mock` 在模組層級 mock。

### 6. 策略組合邏輯歸屬 strategy 套件
複合分析（多策略 + K 線 + AI）由 `strategy/composites.py` 提供。上層只呼叫 `strategy.run_composite(code)`，不用 `__import__` 動態載入。

---

## 已知技術債（Technical Debt Ledger）

| 債務 | 檔案 | 狀態 |
|------|------|------|
| `config.py` 無意義轉發 | config.py | ✅ 已刪除（2026-07-02） |
| `indicators.py`（根目錄）dead code | indicators.py | ✅ 已刪除（2026-07-02 輪 #2）— 341 行 + 5 個專屬測試（SMA/EMA/RSI/MACD/KDJ/Bollinger） |
| `safe_float` 重複定義 | main.py / official/utils.py / fetcher.py | ✅ 已收斂至 utils.py |
| `get_single_key_input` 重複定義 | strategies.py / chips_strategy.py | ✅ 已收斂至 input_helper.py |
| `fetch_klines` / `_fetch_history` 重複 | strategy/_utils.py / klines_helper.py | ✅ 已刪除 klines_helper.py、simplified _fetch_history |
| `db_admin.py` vs `processor.py` 雙寫入路徑 | db_admin.py / processor.py | ✅ db_admin 不再有 save_*，processor.py 為唯一寫入路徑 |
| `strategy_runner.py` 部分重複 dispatch | strategy_runner.py | ⚠️ 已評估保留（JSON API -vs-Rich TUI 本質不同 consumer；thin wrappers simplified） |
| `PERFetcher` 已移除，測試殘留 | test_006_per.py | ✅ 已刪除 |
| `official/` 套件密封 | official/__init__.py | ✅ 已密封（2026-07-02 輪 #2）— `__all__` 完整、消費者改從根導入 |
| `verify=False` 安全漏洞 | fetcher.py / dividend_crawler.py / quotes.py / tdcc.py / trading_calendar.py / composites.py | ✅ 已修正 12 處為 verify=True（2026-07-02 輪 #2） |
| `tui/menu.py` 重複 input 實作 | tui/menu.py | ✅ 已委派至 input_helper（2026-07-02 輪 #2） |

---

## 變更紀錄

- **2026-07-02**：建立本文件。記錄 main.py 拆分設計決策（commands/ 拆分、TUIApp 封裝、HTTP 不注入、策略組合邏輯回歸 strategy 套件）。
- **2026-07-02**：技術債收斂輪 #1 — 結清 6 項（config.py/待刪 indicators.py、safe_float、get_single_key_input、fetch_klines 重複、雙寫入路徑、PER 測試）；strategy_runner 標記保留。
- **2026-07-02**：技術債收斂輪 #2 — 結清 4 項：(1) 刪除 dead `indicators.py`（341 行 + 5 測試 ≈ 770 行）(2) 密封 `official/` 套件（`__all__ + re-export）(3) 修正 12 處 `verify=False` 安全漏洞 (4) `tui/menu.py` input 委派至 `input_helper`。淨減 1,135 行。

---

## 修改影響分析（Change Impact Analysis）

修改任何函式、類別或模組前，請使用 `twstock/dependency_graph.json` 查詢受影響範圍。

### 使用方式

```python
import json
with open("twstock/dependency_graph.json") as f:
    graph = json.load(f)

def find_dependents(target, graph):
    """找出所有導入 target 的模組（直接受影響方）。"""
    return [mod for mod, deps in graph.items() if target in deps]

# 例如：修改 twstock.utils.safe_float 前
print(find_dependents("twstock.utils", graph))
# 輸出: ['twstock.commands.indicators', 'twstock.commands.intraday', ...]
```

命令列版：
```bash
grep -l "from twstock.utils" twstock/**/*.py twstock/**/**/*.py
```

### 穩定公開 API（**Public API** — 不得隨意變更簽名）

| API | 位置 | 說明 |
|-----|------|------|
| `InputProvider` (Protocol) | `twstock/tui/input_provider.py` | 鍵盤輸入抽象，`get_key/prompt`, `kbhit`, `flush` 為穩定介面 |
| `MockInputProvider` | `twstock/tui/input_provider.py` | 測試用 mock，建構式接受 `keys: List[str]` |
| `create_default_provider()` | `twstock/tui/input_provider.py` | 依平台建立對應 provider |
| `OutputWriter` (Protocol) | `twstock/output_writer.py` | 輸出抽象，所有報表輸出皆透過此協定 |
| `DataFetcher` | `twstock/market_data/fetcher.py` | 主要市場資料抓取入口，`fetch_daily/fetch_history` 為穩定方法 |
| `MarketCache` | `twstock/market_data/cache.py` | 快取層，`get/set` 為穩定介面 |

### 無法自動測試的平台相依區域

- `twstock/input_helper.py` 中 `_getch_unix`, `_kbhit_unix`, `_flush_input_buffer` 的 Unix 分支 — 僅在 Termux/macOS/Linux 執行，Windows CI 以 `@pytest.mark.skipif(not _IS_UNIX)` 跳過。
- `twstock/terminal.py` 的彩色輸出迴呼 — 需人工在 terminal 驗證。
- `twstock/strategy/strategies.py` 的互動式 `interactive_menu` — 需人工模擬按鍵序列（可用 `MockInputProvider` 驗證）。
- `twstock/main.py` 的 CLI 入口整合 — 需端到端執行 `python -m twstock.main --help` 驗證。

### 手動驗證方式

1. 平台 I/O：在目標平台（Windows / macOS / Termux）執行 `pytest twstock/tests/test_input_helper.py -v`，確認對應分支被正確執行或跳過。
2. 繪圖回呼：執行 `python -c "from twstock.tui.render import make_layout; make_layout()"`，確認無異常。
3. CLI 整合：`python -m twstock.main --help` 應列出所有子命令且不拋異常。
