# AI_CHECKLIST.md — TRINITY 修改完成自我驗收清單

> 每次修改程式完成後，逐项勾選。全部通過才算完成。

---

## 基本檢查

- [ ] **Import OK** — `python -c "import twstock.main"` 無 error
- [ ] **Syntax Error** — 所有修改的檔案可被 Python 解析
- [ ] **No Circular Import** — A→B→A 不存在

## 功能檢查

- [ ] **CLI** — `python main.py --help` 正常執行
- [ ] **SQLite** — 資料庫可正常開啟、查詢
- [ ] **Strategy** — 所有 5 大策略仍可執行
- [ ] **Rich UI** — TUI 面板渲染正常（無排版錯亂）
- [ ] **JSON Output** — `strategy_runner.py` 輸出格式正確

## 資料檢查

- [ ] **單位換算** — 所有 ingestion 路徑已轉換為張
- [ ] **前復權** — adj_factor 方向正確（越舊越小）
- [ ] **日期格式** — YYYY-MM-DD，非民國年
- [ ] **空值處理** — NaN → None，不會寫入 DB 錯誤

## 規範檢查

- [ ] **Naming Rule** — 函式名稱符合動詞前綴
- [ ] **Docstring** — 所有 public function 有說明
- [ ] **No Magic Number** — 常數已定義為變數
- [ ] **No print()** — 正式程式碼無 print（CLI 互動提示除外）
- [ ] **Error Policy** — 單支股票失敗不影響其他

## 文件檢查

- [ ] **ARCHITECTURE.md** — Schema / 規範有更新
- [ ] **AGENTS.md** — 快速導覽有更新（如有新增功能）
- [ ] **DEVELOPMENT_GUIDE.md** — 常見陷阱有更新（如有新增陷阱）

## 完成

全部勾選後，提交 commit。
