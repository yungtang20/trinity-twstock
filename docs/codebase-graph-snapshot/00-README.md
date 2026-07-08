# 00 — 知識圖譜審核指引（給純文字 AI）

> 你拿到的是 `D-twse`（台股日線分析 DSS）這個專案由 [codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp) 索引出來的知識圖譜快照。
> 我不確定圖譜內容正確，請你幫我審核「圖譜是否有錯誤或需要優化的地方」。

---

## 這份快照是什麼

| 檔案 | 內容 | 約 token 數 | 你能整份讀嗎 |
|---|---|---|---|
| `01-architecture.md` | 架構總覽（node/edge 統計、套件、entry、hotspot、cluster） | ~2K | ✅ 一定可以 |
| `02-nodes.tsv` | 全部 2984 個 node（id, label, name, qualified_name, file_path, line） | ~104K | ⚠️ borderline，多數模型可整份，128K 上限的要小心 |
| `03-edges.tsv` | 全部 11894 條 edge（source, type, target, properties） | ~565K | ❌ 任何模型都吃不下，必須分段或抽樣 |

圖譜 schema（節點）：`id, label, name, qualified_name, file_path, start_line, end_line`
圖譜 schema（邊）：`source_id, source_qualified_name, edge_type, target_id, target_qualified_name, properties(JSON)`

17 種 edge type：`CALLS, DEFINES, DEFINES_METHOD, USAGE, TESTS, WRITES, HANDLES, IMPORTS, DECORATES, CONTAINS_FILE, CONTAINS_FOLDER, CONTAINS_PACKAGE, SIMILAR_TO, SEMANTICALLY_RELATED, FILE_CHANGES_WITH, CONFIGURES, IMPLEMENTS`（實際出現的見 `01-architecture.md` §2）

---

## 怎麼讀（建議順序）

1. **先讀 `01-architecture.md`** —— 2K tokens，建立整體輪廓。讀的時候注意每節結尾的「觀察點」，那些是我已經懷疑的可疑信號，請你幫我確認或反駁。
2. **再讀 `02-nodes.tsv` 的 header 與前 200 行** —— 看 label 分佈是否合理、有沒有明顯錯的 node（例如 file_path 空、qualified_name 不該出現的值）。
3. **`03-edges.tsv` 不要整份貼** —— 看 §「分段策略」，挑一類 edge 抽樣審核。

---

## 審核維度（請涵蓋這五項）

### A. 覆蓋性 — 該有的概念有沒有漏？
- 這個專案有 `fetcher / processor / strategy / db_admin / tui / official / commands` 等模組，圖譜是否都建出了對應的 node？
- 有沒有重要檔案沒被索引？（`02-nodes.tsv` 中 `label=File` 共 199 個，可逐一對照實際專案）
- 路徑 `models/`、`archive/`、`twse-app/` 等被排除是預期的，確認沒有遺漏該收的。

### B. 邊正確性 — 該連的連了嗎？連錯了嗎？
- `CALLS` 邊的 confidence 欄位（properties 裡 `confidence` 0~1）—— confidence 低的邊可能誤判。檢驗幾條 `confidence: 0.90` 的 CALLS 是否真有呼叫關係。
- `USAGE` 數量（2844）遠多於 `CALLS`（2191）—— 是否把「模組匯入」「變數引用」誤算成 usage？
- `IMPORTS` 只有 173 條 / 199 個檔 —— 平均每檔不到 1 import，明顯偏低。Python 專案不可能。**這是最可能的圖譜錯誤。**
- `WRITES`（826）—— 對「台股日線 DSS」而言這數量級合理嗎？抽驗幾條 WRITES 是不是真的在寫 SQLite。

### C. 死碼與熱點 — fan-in/fan-out 是否合理？
- `twstock.commands.dividend.execute` fan-in 176 最高 —— 它真被 176 處呼叫，還是含 TESTS 邊？建議分開統計「含測試 vs 不含測試」的 fan-in。
- `twstock.commands` pack fan-in 152 但 fan-out 0 —— DAG 死端。command 層不可能不呼叫任何人，這是圖譜漏邊的最強信號。
- 有沒有 fan-in = 0 且非 entry 的死碼？

### D. 語意邊品質 — `SIMILAR_TO` / `SEMANTICALLY_RELATED` 可信嗎？
- 這兩類邊是 `full` 模式向量算的，518 條。抽樣 10 條 SIMILAR_TO，看連的兩端在語意上是否真的相似，還是只是短名相似（如 `analyze` 對上 `analyze_single_stock`）。
- 語意邊是否該過濾掉跨「pack」的連接（例如把 `tests` 的 node 跟 `strategy` 的 node 連 SIMILAR_TO 通常沒意義）。

### E. Cluster 品質 — Leiden 分群合理嗎？
- `01-architecture.md` §9 列了 12 個 cluster。檢查：
  - cluster label 全是 fallback `twstock` —— 是否該 LLM 命名？
  - cohesion 極端值（0.59 vs 0.90）—— 0.59 的 cluster 1 是否該再拆？
  - cluster 165 把測試碼 `test_reinsert_same_key_keeps_single_row` 跟正式 `fetch_daily` 混在一起 —— 測試汙染 cluster。
  - cluster 4 出現 3 個同名 `insert_history` —— qualified_name 有區分嗎？顯示是否該強制 qualified_name？

---

## 分段策略（餵 edges 給低 context 模型用）

`03-edges.tsv` 太大不能整份貼。用以下切法（你可直接 `grep` 或在對話中按此過濾）：

| 切法 | 大致行數 | 適合審什麼 |
|---|---|---|
| 按 edge_type 切：`grep -P '\tCALLS\t' 03-edges.tsv` | ~2191 行 | B 類呼叫關係 |
| `grep -P '\tIMPORTS\t'` | ~173 行 | B 類 import 缺漏（**強烈建議先審這段**） |
| `grep -P '\tWRITES\t'` | ~826 行 | B 類寫入正確性 |
| `grep -P '\tSIMILAR_TO\t'` | ~136 行 | D 類語意邊（小、好審） |
| `grep -P '\tTESTS\t'` | ~896 行 | 與正式碼 CALLS 混雜導致 fan-in 失真 |
| 按 file_path 切：取 `source_qualified_name` 含 `strategy` 的邊 | 變動 | 驗證策略層接得對不對 |
| 抽樣：`shuf -n 100 03-edges.tsv` | 100 行 | 快速 sanity check |

建議餵食順序：`01-architecture.md` 全文 → `02-nodes.tsv` 全文（若你的 context 夠）→ `03-edges.tsv` 中 `IMPORTS` + `SIMILAR_TO` 兩段 → `CALLS` 抽樣 200 條。

---

## 三套現成 Prompt 模板（直接複製貼到 ChatGPT / Claude.ai / Gemini）

### 模板 1 — 入門級審核（不貼大檔，純概念）

```
我在 https://github.com/DeusData/codebase-memory-mcp 這個 MCP server 索引了
一個 Python 台股分析專案，得到 2984 個 node、11894 條 edge 的知識圖譜。
node labels: Method 898, Section 561, Function 427, Variable 367, Class 307,
File 199, Module 199, Decorator 10, Route 1。
edge types: USAGE 2844, DEFINES 2759, CALLS 2191, DEFINES_METHOD 898,
TESTS 896, WRITES 826, SEMANTICALLY_RELATED 382, DECORATES 293, HANDLES 216,
IMPORTS 173, SIMILAR_TO 136, FILE_CHANGES_WITH 27, CONFIGURES 12。
我懷疑的問題：(1) IMPORTS 只有 173 條 / 199 檔偏低;
(2) commands pack fan-in=152 但 fan-out=0 像死端;
(3) USAGE(2844) 遠多於 CALLS(2191);
(4) Section node 561 個是否該排除;
(5) tests 包佔圖譜 1/3 是否該獨立子圖。
請你從這個 MCP server 工具的設計目的角度，判斷這些數字哪些是「圖譜錯誤」、
哪些是「正常但該優化索引設定」、哪些是「其實沒問題」。給優先級排序。
```

### 模板 2 — 深度審核（貼架構檔 + nodes）

```
這是我用 codebase-memory-mcp 索引專案得到的架構總覽：

<<<貼 01-architecture.md 全文>>>

這是所有 node 的 TSV（3000 行）：

<<<貼 02-nodes.tsv 全文>>>

請你扮演知識圖譜品質審核員。檢查:
1. node label 分佈有沒有異常（Section 561 是否過多? Variable 367 是否含假性節點?）
2. qualified_name 命名是否一致、跟 file_path 對得上
3. 有沒有 file_path 空字串的 node 應該排除
4. 看看有沒有重複或近似重複的 node (qualified_name 只差大小寫/路徑分隔)
5. 從 node 清單能不能拼出這個專案該有的核心模組
回報格式: 每項發現寫 [確定BUG/疑似/優化建議/正常] + 一句話理由。
```

### 模板 3 — 邊正確性審核（貼架構檔 + 邊片段）

```
這是我用 codebase-memory-mcp 索引專案得到的架構總覽與部分邊:

<<<貼 01-architecture.md 全文>>>

==== IMPORTS 邊（全部 173 條）====
<<<貼 grep -P '\tIMPORTS\t' 03-edges.tsv 結果>>>

==== SIMILAR_TO 邊（全部 136 條）====
<<<貼 grep -P '\tSIMILAR_TO\t' 03-edges.tsv 結果>>>

==== CALLS 邊抽樣 200 條 ====
<<<貼 shuf -n 200 03-edges.tsv 結果（去掉 TESTS 邊）>>>

請審核:
1. IMPORTS 邊有沒有漏（Python 專案 199 檔應該有幾百條 import 邊?）
2. SIMILAR_TO 連的兩端語意是否真的相似，還是只 short-name 字面像
3. CALLS 邊的 properties.confidence 欄位 — 低 confidence 邊是否該排除
4. 邊的 source/target 是否都對得上 nodes.tsv 裡存在的 id
回報每條可疑邊的 (source, edge_type, target, 問題) 三元組。
```

---

## 你不該審什麼（避免假警報）

- 不要抱怨「為什麼沒有 type/inheritance 邊」—— codebase-memory MCP 不做型別系統邊。
- 不要抱怨「為什麼 import 這麼少」—— 先確認是不是 schema 漏建，而非工具設計缺陷。它**設計上**會建 IMPORTS 邊，數量級應該 > 檔案數。
- 不要抱怨 cluster 沒名字——這是 fallback label，不算 bug。
- 不要建議「重新索引用 cross-repo-intelligence 模式」——那是跨 repo 模式，本專案單一 repo 不適用。

---

## 我要的最終成果

不論你用哪個模板，最終回覆請給我這五段：

1. **確定的圖譜 bug**（致命，必修）：列舉哪幾條邊/哪幾個 node 是錯的，證據是什麼。
2. **疑似 bug**（需進一步驗證）：列舉可疑信號與驗證方法。
3. **索引設定優化建議**（次模式可改善的）：例如該排除哪些 dir、該調哪些 label filter。
4. **圖譜結構優化建議**（圖譜本身的洞）：例如該補的語意邊、該拆的 cluster。
5. **其實沒問題的**（安撫我別白忙）：列舉我懷疑但其實正常的點，附理由。

嚴重程度排序輸出，最致命的擺第一。
