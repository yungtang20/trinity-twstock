# 01 — 知識圖譜架構總覽（D-twse）

> 本文由 codebase-memory MCP `get_architecture` 真實輸出整理而成，非手編。
> 索引模式：`full`（全部檔案 + similarity/semantic edges）
> 產出時間：2026-07-06
> 圖譜資料庫：`~/.cache/codebase-memory-mcp/D-twse.db`（SQLite，9.31 MB）
> 節點：2984　邊：11894

---

## 1. Node Label 分佈

| Label | Count |
|---|---|
| Method | 898 |
| Section | 561 |
| Function | 427 |
| Variable | 367 |
| Class | 307 |
| File | 199 |
| Module | 199 |
| Folder | 16 |
| Decorator | 10 |
| Project | 1 |
| Route | 1 |

**觀察點（給審核 AI）**：
- `Section`（561）數量偏高 —— 通常是 markdown 文件被切成 section node。是否符合預期？是否該排除？
- `Decorator` 只有 10、`Route` 只有 1 —— 此專案幾乎無 web framework route，但有一個。是哪個？是否誤判？
- `Variable`（367）是否包含過多 import alias、常數，導致「假性節點」？

---

## 2. Edge Type 分佈

| Edge Type | Count |
|---|---|
| USAGE | 2844 |
| DEFINES | 2759 |
| CALLS | 2191 |
| DEFINES_METHOD | 898 |
| TESTS | 896 |
| WRITES | 826 |
| SEMANTICALLY_RELATED | 382 |
| DECORATES | 293 |
| HANDLES | 216 |
| CONTAINS_FILE | 199 |
| IMPORTS | 173 |
| SIMILAR_TO | 136 |
| FILE_CHANGES_WITH | 27 |
| CONTAINS_FOLDER | 14 |
| CONFIGURES | 12 |

**觀察點（給審核 AI）**：
- `USAGE`（2844）遠多於 `CALLS`（2191）—— `USAGE` 通常代表「使用但非呼叫」（如引用變數、型別註解）。這個比例符合 Python 專案嗎？有沒有把「定義」與「使用」混在一起？
- `WRITES`（826）數量驚人 —— 此專案大量寫入資料庫/檔案。是否符合「台股日線分析 DSS」的預期（應該寫 SQLite）？
- `IMPORTS` 只有 173，但檔案 199 個 —— 平均每檔不到 1 個 import，偏低。是否 cross-file import 解析沒做完？
- `SEMANTICALLY_RELATED`（382）+ `SIMILAR_TO`（136）= 518 條語意邊 —— 這些是 `full` 模式才有的向量語意邊。該驗證它們連的兩端在語意上相不相關，還是純碎字面相似？
- `FILE_CHANGES_WITH`（27）—— 共變邊，是否合理？

---

## 3. 語言分佈

| Language | File Count |
|---|---|
| Python | 137 |
| JavaScript | 4 |
| Bash | 2 |
| TypeScript | 2 |
| HTML | 1 |
| TOML | 1 |
| YAML | 1 |

**觀察點**：以 Python 為主（137/148 ≈ 92%）。JS/TS 是否該被索引？（`scripts/check_supabase.js`、`scripts/syncData.ts`）

---

## 4. Packages（top 15）

| Package | Node Count |
|---|---|
| tests | 1009 |
| strategy | 214 |
| module | 60 |
| fetcher | 58 |
| tui | 48 |
| official | 38 |
| calculator | 24 |
| kronos | 21 |
| input_helper | 13 |
| strategy_runner | 12 |
| market_data | 12 |
| utils | 12 |
| output_writer | 11 |
| processor | 11 |
| display | 11 |

**觀察點**：
- `tests`（1009）佔圖譜 1/3 強 —— 測試碼節點數遠超正式碼。是否該讓測試碼獨立子圖、或在探索時預設排除？
- fan_in / fan_out 全為 0 —— pack 層級的邊界測量沒生效（pack 沒設 fan_in/out），可考慮補上。

---

## 5. Entry Points

| Name | File |
|---|---|
| main | `scripts/backfill_indicators.py` |
| main | `scripts/sync_to_supabase.py` |
| main | `twstock/main.py` |
| main | `twstock/strategy/chips_strategy.py` |
| main | `twstock/strategy/patterns_strategy.py` |
| main | `twstock/strategy/prediction_strategy.py` |
| main | `twstock/strategy/sr_analyzer.py` |
| main | `twstock/strategy_runner.py` |

**觀察點**：8 個 `main` entry —— 是否每個人都該被視為 entry？`scripts/*` 與 `twstock/strategy/*` 的 main 是否有層級差異？

---

## 6. Hotspots（高 fan-in，最多人呼叫）

| Function | Fan-in |
|---|---|
| `twstock.commands.dividend.execute` | 176 |
| `twstock.fetcher.FinMindClient.get` | 102 |
| `twstock.db.get_connection` | 65 |
| `twstock.fetcher.FinMindFetcher._transform` | 54 |
| `twstock.calculator.ATRCalculator.calculate` | 43 |
| `twstock.db_admin.init_db` | 30 |
| `twstock.official.updater.upsert_dataframe` | 17 |
| `twstock.display.price_color` | 17 |
| `twstock.retry.retry_get` | 15 |
| `twstock.db_admin.create_tables` | 15 |

**觀察點**：
- `dividend.execute` fan-in 176 最高 —— 是否真的被 176 處呼叫，還是 TESTS edge 也算進去了？建議審核 inbound callers 結構。
- `FinMindClient.get`（102）vs `FinMindFetcher._transform`（54）—— fetcher 體系是否過度集中？這是核心 hotspot，重構時優先照顧。

---

## 7. Boundaries（跨 pack 邊界，top 10）

| From → To | Call Count |
|---|---|
| tests → commands | 127 |
| tests → tui | 116 |
| tests → official | 111 |
| tests → fetcher | 84 |
| tests → market_data | 54 |
| tests → db_admin | 50 |
| strategy → fetcher | 40 |
| tests → display | 38 |
| tests → strategy | 31 |
| strategy → commands | 25 |

**觀察點**：前 6 名全是 `tests → X` —— 測試碼是圖譜裡最大的「呼叫源」。`strategy → fetcher`（40）是正式碼中最重要的邊界（策略層直接打 fetcher，沒經過抽象層）。是否符合架構預期？或該有中間層？

---

## 8. Layers（自動分層）

| Package | Layer | Reason |
|---|---|---|
| (root) | api | has HTTP route definitions |
| backfill_indicators | internal | fan-in=0, fan-out=0 |
| **commands** | **core** | high fan-in (152 in, 0 out) |
| **db_admin** | **core** | high fan-in (50 in, 0 out) |
| **display** | **core** | high fan-in (38 in, 0 out) |
| **fetcher** | **core** | high fan-in (124 in, 0 out) |
| main | internal | fan-in=0, fan-out=0 |
| **market_data** | **core** | high fan-in (54 in, 0 out) |
| **official** | **core** | high fan-in (111 in, 0 out) |
| strategy | internal | fan-in=31, fan-out=65 |
| strategy_runner | internal | fan-in=0, fan-out=0 |
| sync_to_supabase | internal | fan-in=0, fan-out=0 |
| tests | entry | only outbound calls |
| **tui** | **core** | high fan-in (116 in, 0 out) |

**觀察點**：
- `strategy` 被分為 `internal`（fan-out 65 > fan-in 31）—— 它是「消費者」不是「被消費」，分層正確嗎？通常策略是 core 邏輯，這裡反而被歸為 internal。
- `commands` fan-in 152 但 fan-out 0 —— DAG 死端？command 層應該會去呼叫 fetcher/processor，fan-out=0 不合理，疑似 cross-pack CALLS 邊沒建出來。
- root 標 `api` 因有 HTTP route，但 Route node 只有 1 個 —— 哪個檔有 route？是 `_api_test.py` 嗎？

---

## 9. Clusters（Leiden 社群偵測，top 12）

| Cluster | Members | Cohesion | Top Nodes |
|---|---|---|---|
| 1 | 141 | 0.66 | get, retry_get, run_strategy, analyze, info |
| 2 | 127 | 0.59 | execute, close, get_connection, init_db, fetch_and_save |
| 43 | 105 | 0.87 | fetch_market_indices, get_realtime_mis_data, get_yahoo_market_volumes, get, get_ssl_verify |
| 35 | 99 | 0.86 | patch_gc, update_single_stock, upsert_dataframe, upsert_history, upsert_institutional |
| 16 | 96 | 0.90 | get_blocking_key, _get_interactive_input_windows, kbhit, flush, _make_smart_msvcrt |
| 0 | 69 | 0.71 | price_color, vol_color, scan_market_stocks, run_strategy, StockAnalyzer |
| 165 | 60 | 0.87 | _transform, save, test_reinsert_same_key_keeps_single_row, fetch_daily, fetch_monthly |
| 3 | 59 | 0.80 | create_tables, write_result, create_views, ConsoleWriter, main |
| 4 | 57 | 0.74 | calculate, insert_history (x3), get_indicator |
| 135 | 41 | 0.70 | TUIApp, _get_input, dispatch_main_menu, run, _execute_action |
| 24 | 41 | 0.70 | run_composite, render_kline, analyze_kline_with_longcat, get_stock_name, _ensure_loaded |
| 25 | 37 | 0.83 | find_patterns, _make_pattern, scan_market, scan, _scan_one |

**觀察點**：
- Cluster 1 與 Cluster 2 label 都是 `twstock` —— Leiden 沒有給 cluster 有意義名字，全是 fallback。是否該人工命名或由 LLM 生成 label？
- Cluster 16 cohesion 0.90（input_helper / kbhit / msvcrt）—— Windows 終端互動碼自成一個高凝聚 cluster，圖譜抓到這個特徵是正確的。
- Cluster 165 top nodes 出現 `test_reinsert_same_key_keeps_single_row` —— 測試碼混進了「fetcher/utility」cluster，表示 cluster 邊界有滲漏（測試碼該獨立、不應與正式碼同 cluster）。
- Cluster 4 出現三個同名 `insert_history` —— 可能是來自不同 module 的同名方法。圖譜有沒有用 qualified_name 區分？(nodes 表有 UNIQUE(project, qualified_name)，應該有，但 cluster 顯示層面只顯示 short name，可讀性差。)

---

## 10. File Tree（精簡版）

- 根目錄有 `AGENTS.md`、`README.md`、`PROJECT_AUDIT.md`、`pyproject.toml`、`pyrightconfig.json`
- `twstock/`：主程式碼（45 項），含 `commands/`（7）、`market_data/`（3）、`official/`（10）、`strategy/`（13）、`tui/`（6）、`tests/`（69 個測試檔）
- `twstock/` 內另有 18 份 `.md` 文件（ARCHITECTURE、DB_SCHEMA、API_SPEC 等）—— 這些文件被切成 Section node（見 §1 Section=561 的來源）
- `scripts/`：12 個工具稿（含 `.js`、`.ts`、`.py`）
- `model/`：`kronos.py`、`module.py`（Kronos 預測引擎原始碼）
- `audit/`、`docs/source/`：文件

完整 file_tree 見 `02-nodes.tsv` 中 `label=File` 的 199 行。
