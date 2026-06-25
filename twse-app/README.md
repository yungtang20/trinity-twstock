# TRINITY 台股分析平台

全方位的股票分析工具，提供即時行情、技術分析、籌碼分析、策略掃描與 AI 智慧分析。

## 前置需求

- Node.js 18+
- SQLite 本地資料庫（開發用）
- Supabase 帳號（生產環境）

## 快速開始

```bash
npm install
npm run dev
```

前端運行於 `http://localhost:5173`，後端 server 運行於 `http://localhost:3000`。

## 技術棧

| 層級 | 技術 |
|------|------|
| 前端 | React + TypeScript + Vite + Recharts |
| 後端 | Express + TypeScript (server.ts) |
| 資料庫 | Supabase (PostgreSQL) + SQLite (本地快取) |
| AI 分析 | LongCat API |
| 數據源 | FinMind API、TWSE/TPEX 官方 API |

## 專案結構

```
twse-app/
├── src/                    # 前端源碼
│   ├── components/         # React 元件
│   ├── lib/                # 工具函式庫 (indicators, api 等)
│   ├── pages/              # 頁面元件
│   └── server/             # 後端 API 路由
├── scripts/                # 資料庫腳本、遷移工具
├── server.ts               # Express 伺服器入口
├── vite.config.ts          # Vite 配置（含代理設定）
├── tsconfig.json           # TypeScript 配置
└── .env.example            # 環境變數範本
```

## 環境變數

複製 `.env.example` 為 `.env` 並填入真實值：

```bash
cp .env.example .env
```

完整變數說明見 [.env.example](.env.example)。

主要變數：
- `VITE_SUPABASE_URL` / `VITE_SUPABASE_ANON_KEY` — Supabase 連線
- `VITE_LONGCAT_API_KEY` — AI 分析 API
- `VITE_FINMIND_API_KEY` — 即時股價數據
- `VITE_TWSE_BASE_URL` / `VITE_TPEX_BASE_URL` — 交易所 API

## API 端點

| 分類 | 路徑 | 說明 |
|------|------|------|
| 即時行情 | `/api/twse-stats`, `/api/otc-stats` | 大盤指數 |
| 個股資料 | `/api/stock/:id/history` | 股價歷史 |
| 籌碼 | `/api/stock/:id/institutional` | 法人買賣超 |
| 排行榜 | `/api/movers` | 漲跌幅排行 |
| 搜尋 | `/api/stock/search?q=` | 股票搜尋 |
| AI 分析 | `/api/ai/analyze` | LongCat 報告 |
| FinMind | `/api/finmind-proxy` | 數據代理 |

## 部署

```bash
# 建置前端
npm run build

# 生產環境啟動
NODE_ENV=production node server.js
```

## 指令總覽

| 指令 | 說明 |
|------|------|
| `npm run dev` | 開發模式（含 Vite HMR） |
| `npm run build` | 建置前端 |
| `npm run preview` | 預覽建置結果 |
| `npm run lint` | ESLint 檢查 |

## 授權

本專案僅供學習與研究使用。
