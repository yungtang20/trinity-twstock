# TRINITY 前端設定指引

## 環境變數設定

請複製 `.env.example` 為 `.env` 並填入您的設定：

```bash
cp .env.example .env
```

### 重要：設定後端 API URL

在 `.env` 檔案中，確保已加入：

```env
VITE_API_URL=http://localhost:3000
```

這樣前端才能正確連線到後端伺服器，獲取官方 TWSE/TPEX API 數據。

## 啟動方式

### 1. 啟動後端伺服器

在 `twse-app` 目錄中：

```bash
npm run server
```

後端會在 `http://localhost:3000` 運行，並提供 `/api/twse-stats` 和 `/api/otc-stats` 端點。

### 2. 啟動前端開發伺服器

在另一個終端機中：

```bash
npm run dev
```

前端會在 `http://localhost:5173` 運行（預設 Vite 埠號）。

### 3. 開啟瀏覽器

訪問 `http://localhost:5173`，Dashboard 頁面將顯示：
- 加權指數（TWSE）
- 櫃買指數（TPEX）
- 漲跌家數、成交金額等數據

## 疑難排解

### 問題：Dashboard 顯示「數據載入異常」

**解決方案：**

1. 確認後端伺服器已啟動：
   ```bash
   curl http://localhost:3000/api/twse-stats
   ```
   應該返回 JSON 數據。

2. 確認 `.env` 中有設定 `VITE_API_URL`：
   ```env
   VITE_API_URL=http://localhost:3000
   ```

3. 檢查瀏覽器開發者工具（F12）→ Network 標籤，查看 `/api/twse-stats` 和 `/api/otc-stats` 的回應狀態。

### 問題：CORS 錯誤

前端通過後端代理（proxy）存取官方 API，因此不會有 CORS 問題。如果仍有問題，請確認：
- 後端伺服器已正確啟動
- `VITE_API_URL` 設定正確

## 架構說明

```
前端 (Vite React)
    ↓ fetch('/api/twse-stats')
後端 (Express server.ts)
    ↓ fetch('https://www.twse.com.tw/...')
官方 TWSE API
    ↓
返回 JSON 數據
```

後端負責：
1. 呼叫官方 TWSE/TPEX API
2. 解析數據格式
3. 返回統一格式的 JSON 給前端
