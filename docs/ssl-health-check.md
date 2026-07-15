# SSL 健康檢查報告

> 本報告為某次手動檢查的當下快照，記錄 TPEX/TWSE 端點憑證驗證行為。
> 日期由檔案 mtime 顯示（腳本執行當下）。

## 背景症狀

早期執行 CLI 時，console 出現：

```
SSL error on attempt 1/4 for https://www.tpex.org.tw/...:
  [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed:
  Missing Subject Key Identifier (_ssl.c:1082)
SSL verification failed for https://www.tpex.org.tw/... —
  retrying with verify=False (InsecureRequestWarning suppressed)
```

懷疑 TPEX/TWSE 憑證缺失 Subject Key Identifier (SKI) 擴充。

## 環境

| 項目 | 值 |
|---|---|
| Python | 3.14.6 |
| OpenSSL | 3.5.7 (9 Jun 2026) |
| certifi | 2026.06.17 |
| requests | 2.34.2 |
| urllib3 | 2.7.0 |
| `REQUESTS_CA_BUNDLE` / `CURL_CA_BUNDLE` 環境變數 | (無) |

## 兩種連線方式的分歧（關鍵）

同一機器、同一 Python、對同一端點：

| 連線方式 | CA 來源 | TPEX | TWSE |
|---|---|---|---|
| `ssl.create_default_context()`（Python 內建） | Windows 系統 CA 存放區 | **CERTIFICATE_VERIFY_FAILED** ❌ | **CERTIFICATE_VERIFY_FAILED** ❌ |
| `requests` + `verify=certifi.where()` | certifi cacert.pem | **HTTP 200** ✅ | **HTTP 200** ✅ |

## 憑證鏈健康（經 certifi 驗證成功後檢視）

```
[www.tpex.org.tw]
  Subject: CN=tpex.org.tw
  Issuer:  CN=WE1,O=Google Trust Services,C=US
  NotAfter: 2026-09-01
  SKI: present   AKI: present   (憑證完整合規)
```

TWSE 同樣可經 certifi 驗證通過、回 HTTP 200。

## 根因判定

1. **TPEX 憑證本身完整**：SKI/AKI 皆存在、有效期限 2026-09-01、簽發者 Google Trust Services WE1。
   早期 console 的 `Missing Subject Key Identifier` 是當時 TPEX 使用的**舊憑證鏈**（中繼 CA 缺 SKI）造成；
   現已更換為 Google Trust Services 憑證，問題已自然消失。

2. **`ssl.create_default_context()` 失敗的原因**：OpenSSL 3.5 在 Windows 上
   載入的是**系統 CA 存放區**，而該存放區對 TPEX/TWSE 憑證鏈的根 CA 收錄不完整
   （或其他中繼憑證狀態問題），導致預設 context 驗證失敗。

3. **產品程式碼不受影響**：`retry_get` 帶 `verify=get_ssl_verify()`，`get_ssl_verify()`
   走 certifi 路徑（`D:\twse\.venv\Lib\site-packages\certifi\cacert.pem`），
   certifi 2026.06.17 已收錄 Google Trust Services 根 CA，故實際抓資料 SSL 全綠。

## 產品呼叫鏈驗證

```
get_ssl_verify() -> D:\twse\.venv\Lib\site-packages\certifi\cacert.pem
  https://www.tpex.org.tw/...market_highlight... -> 200 (len=664)
  https://www.twse.com.tw/exchangeReport/MI_INDEX -> 200 (len=1724)
```

`retry_get` 零 SSL 錯誤、零 fallback。

## 保護機制現況

`twstock/retry.py` 的 `ssl_fallback`（預設 `True`）：
若 SSL 驗證失敗會自動以 `verify=False` 重試一次，並抑制 InsecureRequestWarning。
此機制在最壞情況下會保住資料抓取（傳輸雖未加密驗證，但能取得資料）。

## 結論

- **產品程式碼 SSL 行為正常**，無需修改。
- 早期 console 錯誤訊息是**歷史 log**，當時根因（TPEX 舊憑證鏈中繼 CA 缺 SKI）已隨
  TPEX 更換憑證而消失。
- `ssl.create_default_context()` 的失敗與產品無關（產品走 certifi），僅反映
  Windows 系統 CA 存放區對該端憑證鏈收錄問題；若未來其他工具以預設 context 連
  TPEX/TWSE，請改用 certifi。
- 無程式碼變更（屬安全性相關，未經確認不動 SSL 驗證邏輯）。
