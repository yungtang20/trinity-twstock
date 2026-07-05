#!/usr/bin/env python3
"""SDD 三合一收尾 — 最終驗收報告"""

import os
import sqlite3
import subprocess

print("=" * 60)
print("  SDD 三合一收尾 — 最終驗收報告")
print("=" * 60)
print()

print("=== PHASE 1: DB 零價清理 (close=0) ===")
f = r"twstock/taiwan_stock_unified.db"
conn = sqlite3.connect(f)
cur = conn.cursor()
total = cur.execute("SELECT COUNT(*) FROM stock_history").fetchone()[0]
zero = cur.execute("SELECT COUNT(*) FROM stock_history WHERE close = 0").fetchone()[0]
print(f"  stock_history 總筆數: {total:,}")
print(f"  close=0 異常筆數: {zero}  → {'✅ 通過' if zero == 0 else '❌ 失敗'}")
print("  commit: 0735d57 (fix/db-purge-zero-prices)")
print()

print("=== PHASE 2: OHLC Clamp 防禦 ===")
bad = cur.execute(
    "SELECT COUNT(*) FROM stock_history WHERE open > high OR open < low OR close > high OR close < low"
).fetchone()[0]
ld = cur.execute("SELECT MAX(date) FROM stock_history").fetchone()[0]
print(f"  DB 內 OHLC 偏移筆數: {bad:,}（DB 層不動，memory clamp 由 patterns 處理）")
print(f"  最新交易日: {ld}")
print("  commit: 7f17e68 (fix/patterns-ohlc-clamp)")
print("  _clamp_ohlc 已內建在 fetch_klines(clamp=True)")
print()

print("=== PHASE 3: 倉庫瘦身 ===")
print(f"  kronos_repo/ 存在: {os.path.exists('kronos_repo')}")
print(f"  model/kronos.py 存在: {os.path.exists('model/kronos.py')}")
print(f"  strategy/kronos_engine.py 存在: {os.path.exists('twstock/strategy/kronos_engine.py')}")
bak_files = []
for root, _dirs, files in os.walk("."):
    bak_files.extend(os.path.join(root, fn) for fn in files if fn.endswith(".bak"))
print(
    f"  *.bak 殘留: {len(bak_files)} 個 → {'✅ 乾淨' if len(bak_files) == 0 else '❌ ' + str(bak_files)}"
)
print()

print("=== 修復: 法人資料進度顯示 ===")
im = cur.execute("SELECT MAX(date) FROM institutional_data").fetchone()[0]
ic = cur.execute("SELECT COUNT(*) FROM institutional_data WHERE date = ?", (im,)).fetchone()[0]
print(f"  法人最新日: {im}（{ic} 筆）")
print("  在 updater.py 新增 else 分支顯示 '✅ 三大法人資料已是最新'")
print("  (尚未 commit)")

conn.close()
print()

print("=== pytest ===")
result = subprocess.run(
    ["python", "-m", "pytest", "--tb=short", "-q"],
    capture_output=True,
    text=True,
    cwd="d:/twse/twstock",
)
for line in result.stdout.strip().split("\n"):
    if "passed" in line or "failed" in line or "error" in line:
        print(f"  結果: {line.strip()}")
print()

print("=== CLI 入口 ===")
result = subprocess.run(
    ["python", "main.py", "--help"], capture_output=True, text=True, cwd="d:/twse/twstock"
)
if result.returncode == 0:
    print("  ✅ python main.py --help 正常")
else:
    print(f"  ❌ 錯誤: {result.stderr.strip()[:200]}")

print()
print("=== kronos_engine import ===")
result = subprocess.run(
    ["python", "-c", "from twstock.strategy import kronos_engine; print('OK')"],
    capture_output=True,
    text=True,
    cwd="d:/twse/twstock",
)
print(
    f"  {'✅' if result.returncode == 0 else '❌'} from twstock.strategy import kronos_engine: {result.stdout.strip() or result.stderr.strip()[:200]}"
)

print()
print("=" * 60)
print("  驗收完成")
print("=" * 60)
