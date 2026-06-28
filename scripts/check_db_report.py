import sqlite3, os, datetime

db = 'd:/twse/twstock/taiwan_stock_unified.db'
sz = os.path.getsize(db) if os.path.exists(db) else 0

print('=== 資料庫完整性檢查報告 ===')
print(f'檢查時間: {datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")} (台北時間)')
print(f'資料庫路徑: {db}')
print(f'檔案存在: {"是" if os.path.exists(db) else "否"}')
print(f'檔案大小: {sz/1024/1024:.2f} MB')
print()

# 嘗試多種方式連接
for attempt, (mode, uri) in enumerate([
    ("一般模式", db),
    ("唯讀模式", f"file:{db}?mode=ro"),
    ("immutable 模式", f"file:{db}?mode=ro&immutable=1"),
]):
    try:
        if mode == "一般模式":
            conn = sqlite3.connect(db, timeout=5)
        else:
            conn = sqlite3.connect(uri, uri=True, timeout=5)
        conn.execute("SELECT 1")
        conn.close()
        print(f'[{attempt+1}] {mode}: 可連線')
    except Exception as e:
        err = str(e).split('\n')[0]
        print(f'[{attempt+1}] {mode}: 連線失敗 - {err}')

print()
# 嘗試 SQLite CLI dump
import subprocess
try:
    r = subprocess.run(
        ['sqlite3', db, '.tables'],
        capture_output=True, text=True, timeout=10
    )
    if r.returncode == 0:
        print(f'sqlite3 CLI .tables: {r.stdout.strip() or "(空的)"}')
    else:
        print(f'sqlite3 CLI error: {r.stderr.strip()[:100]}')
except FileNotFoundError:
    print('sqlite3 CLI: not found')
except Exception as e:
    print(f'sqlite3 CLI: {e}')

print()
print('=== 結論 ===')
if sz > 0:
    try:
        conn = sqlite3.connect(db, timeout=5)
        conn.execute("PRAGMA integrity_check")
        conn.close()
        print('✅ 資料庫完整，可正常讀取')
    except Exception:
        print('❌ 資料庫檔案已損毀 (malformed)，無法讀取任何資料')
        print('   → 建議從 Supabase 重建。腳本: scripts/pull_from_supabase.js')
        print('   → 執行: node scripts/pull_from_supabase.js')
else:
    print('⚠️ 資料庫檔案不存在')