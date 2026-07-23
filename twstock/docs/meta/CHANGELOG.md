# TRINITY 變更紀錄

## Unreleased

### Fixed

- 主選單、四碼股號及子選單統一為完整輸入後按 Enter 才執行，移除延遲單鍵判斷與四碼自動送出造成的誤判。
- 歷史更新改用日期索引批次檢查最近 N 個交易日的價量與法人完整性，可單獨補抓法人缺口並提供指定區間強制重抓。
- TDCC 選單與完成訊息改為如實標示「只更新最新一期」，不再把 OpenAPI 不支援的歷史週顯示成已補齊。
- 零量價檢查不再用今天的停牌名單分類昨日資料，異常列只讀呈現且不自動刪除。
- 資料庫維護改為先執行 `quick_check`、可回收空間及已知資料品質檢查；僅達門檻時允許備份後 `VACUUM`。
- 新增 `pyrightconfig.json` 的父目錄搜尋路徑，讓以 `twstock/` 為工作區時可解析 `twstock.*` package import。
- 主畫面市場標題改用系統時間與官方交易日曆判斷開盤狀態；僅在首次進入或從功能返回首頁時重新抓取，等待輸入期間不自動刷新。
- 交易時段的市場指數改為優先使用 TWSE MIS 即時服務，失敗才降級至 MI_INDEX 盤後統計。
- 修正 TPEx 市場成交值「佰萬元」轉為「億元」時放大 100 倍的顯示錯誤。
- 綜合分析首頁明確啟用 TWSE MIS 個股即時報價，並與 LongCat 外部分析權限拆分；請求增加官方 Referer、拒絕非當日回應，成交價暫缺時沿用最佳買賣價降級。
- 日線指標載入改為取得最新限制筆數並保留時間正序。
- 補正 IndicatorEngine 的法人與持股 schema join，並避免同日多來源持股造成重複日線。
- MA、ATR、VWAP 全市場刷新改為分批讀取、`executemany()` 寫入與單一交易 commit。
- 新資料庫 bootstrap 增加日期索引與外資持股舊讀取端相容 view。
- 移除 HTTP retry 的自動 TLS 驗證降級。
- 修正 direct package 啟動與 pytest 的 cwd／DB fixture 隔離風險。

### Security

- 移除本機設定檔中的實際 LongCat key，新增 `.gitignore` 與可複製的 `api.env.example`。

### Documentation

- 重寫架構、schema、JSON、依賴與 API 文件，使其對應目前模組與 schema。
- 補齊文件索引的相對連結與安全資料修復指引。

## v3.3.0

- 建立日 K 決策輔助系統的 CLI／TUI、SQLite 儲存、官方資料來源與策略模組基礎。
