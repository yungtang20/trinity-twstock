# PERFORMANCE_RULES.md — TRINITY 效能規範

> 避免 AI 寫出 N+1 查詢和低效程式碼。

---

## 資料庫查詢規則

### 禁止 N+1 查詢

```python
# ❌ 錯誤：逐筆查詢
for stock_id in stock_ids:
    df = pd.read_sql("SELECT * FROM stock_history WHERE stock_id = ?", conn, (stock_id,))
    # 處理...

# ✅ 正確：一次查詢全部
placeholders = ",".join(["?"] * len(stock_ids))
query = f"SELECT * FROM stock_history WHERE stock_id IN ({placeholders})"
df = pd.read_sql(query, conn, params=stock_ids)
# 再用 DataFrame 操作
```

### 禁止逐筆 commit

```python
# ❌ 錯誤：逐筆 commit
for row in data:
    cursor.execute("INSERT INTO ...", row)
    conn.commit()

# ✅ 正確：分批 commit
for i in range(0, len(data), 1000):
    cursor.executemany("INSERT INTO ...", data[i:i+1000])
    conn.commit()
```

### 禁止全表掃描

```python
# ❌ 錯誤：沒有 WHERE 條件
df = pd.read_sql("SELECT * FROM stock_history", conn)

# ✅ 正確：使用 WHERE + Index
df = pd.read_sql(
    "SELECT * FROM stock_history WHERE stock_id = ? ORDER BY date DESC LIMIT 250",
    conn, params=(stock_id,)
)
```

---

## DataFrame 運算規則

### 優先使用 Vectorize

```python
# ❌ 錯誤：逐列計算
for i, row in df.iterrows():
    df.at[i, 'ma5'] = df['close'].iloc[max(0, i-4):i+1].mean()

# ✅ 正確：使用 rolling
df['ma5'] = df['close'].rolling(window=5).mean()
```

### 優先使用內建方法

```python
# ❌ 錯誤：Python loop
result = []
for row in df.itertuples():
    if row.close > row.ma20:
        result.append(row.stock_id)

# ✅ 正確：Boolean indexing
mask = df['close'] > df['ma20']
result = df.loc[mask, 'stock_id'].tolist()
```

---

## 策略掃描規則

### 全市場掃描

```python
# ❌ 錯誤：逐檔調 API
for stock_id in all_stocks:
    data = fetch_api(stock_id)  # 2000 次 API 呼叫！

# ✅ 正確：從 SQLite 讀取
df = pd.read_sql("SELECT * FROM stock_history WHERE date = ?", conn, (date,))
# 在 DataFrame 上做分析
```

### 使用 Session Cache

```python
# 第一次掃描
if not _SCAN_CACHE['results'] or _SCAN_CACHE['date'] != today:
    _SCAN_CACHE['results'] = scan_all()
    _SCAN_CACHE['date'] = today

# 後續切換股票，直接從 cache 讀
results = _SCAN_CACHE['results']
```

---

## 記憶體規則

### 限制 DataFrame 大小

```python
# ❌ 錯誤：載入全部歷史
df = pd.read_sql("SELECT * FROM stock_history", conn)  # 可能數百萬筆

# ✅ 正確：只載入需要的
df = pd.read_sql(
    "SELECT * FROM stock_history WHERE stock_id = ? ORDER BY date DESC LIMIT 512",
    conn, params=(stock_id,)
)
```

### 大物件及时釋放

```python
# ✅ 正確：用完即釋
with get_connection() as conn:
    df = pd.read_sql(query, conn)
    result = analyze(df)
# conn 自動關閉，df 可被 GC 回收
```

---

## 網路請求規則

### 禁止重複請求

```python
# ❌ 錯誤：每次分析都調 API
def analyze(stock_id):
    df = fetch_api(stock_id)  # 每次都調！
    return compute(df)

# ✅ 正確：從 SQLite 讀
def analyze(stock_id):
    df = read_from_db(stock_id)  # 本地讀取
    return compute(df)
```

### 速率限制

- FinMind API：每小時 600 次（`_RateLimiter`）
- TDCC 官網爬蟲：每筆 0.15 秒延遲
- 全市場資料：一次抓全市場，不逐檔

---

## 效能基準

| 操作 | 預期時間 |
|------|---------|
| 單股分析（從 SQLite） | < 1 秒 |
| 全市場掃描（從 SQLite） | < 30 秒 |
| TUI 啟動 | < 1 秒 |
| 策略面板渲染 | < 2 秒 |
| API 請求（單次） | < 5 秒 |

---

## 版本資訊

| 項目 | 值 |
|------|-----|
| 合約版本 | v1.0 |
| 最後更新 | 2026-06-26 |
