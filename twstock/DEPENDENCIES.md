# DEPENDENCIES.md — TRINITY 相依套件版本

> 記錄所有 Python 套件的最低版本要求，避免不同環境導致行為差異。

---

## Python 版本

| 套件 | 最低版本 | 說明 |
|------|---------|------|
| Python | 3.12 | 主要開發環境 |

---

## 核心套件

| 套件 | 最低版本 | 用途 |
|------|---------|------|
| pandas | 2.2.0 | DataFrame 運算 |
| numpy | 1.26.0 | 數值計算 |
| polars | 0.20.0 | 高效 DataFrame（可選，fallback 到 pandas） |
| rich | 13.7.0 | TUI 畫面渲染 |
| requests | 2.31.0 | HTTP 請求 |
| beautifulsoup4 | 4.12.0 | HTML 解析（TDCC 爬蟲） |
| python-dotenv | 1.0.0 | 環境變數載入 |
| urllib3 | 2.1.0 | HTTP 連線（SSL 警告抑制） |
| sqlite3 | 內建 | 資料庫（Python 3.12 內建） |

---

## 可選套件

| 套件 | 最低版本 | 用途 |
|------|---------|------|
| kronos（NeoQuasar） | 0.1.0 | AI 預測模型 |
| torch | 2.1.0 | Kronos 模型依賴 |

---

## 前端套件（twse-app）

| 套件 | 最低版本 | 用途 |
|------|---------|------|
| react | 18.2.0 | UI 框架 |
| vite | 5.0.0 | 構建工具 |
| typescript | 5.3.0 | 型別系統 |
| tailwindcss | 3.4.0 | 樣式 |
| lightweight-charts | 4.1.0 | K 線圖 |
| framer-motion | 10.18.0 | 動畫 |
| lucide-react | 0.340.0 | 圖標 |

---

## 開發工具

| 套件 | 最低版本 | 用途 |
|------|---------|------|
| pre-commit | 3.5.0 | Git hook |
| black | 24.1.0 | 程式碼格式化 |
| flake8 | 7.0.0 | Lint |
| mypy | 1.8.0 | 型別檢查 |

---

## 安裝指令

```bash
# Python 核心
pip install pandas numpy rich requests beautifulsoup4 python-dotenv urllib3

# 可選（polars 若未安裝會自動 fallback 到 pandas）
pip install polars

# 前端
cd twse-app && npm install
```

---

## 版本同步規則

1. 更新套件版本時，同步更新 `ARCHITECTURE.md` 的依賴章節
2. 新增套件時，必須說明用途和最低版本
3. 升級主要版本時，必須測試所有策略是否正常
