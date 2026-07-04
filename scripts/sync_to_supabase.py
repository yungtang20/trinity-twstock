#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TWSE AnyTara - 本地 SQLite -> Supabase 同步腳本

功能：
  1. 讀取本地 SQLite (twstock/taiwan_stock_unified.db)
  2. 將資料寫入 Supabase 雲端資料庫
  3. 支援單股測試或全量同步

使用方式：
  # 同步單一股票（測試用）
  python scripts/sync_to_supabase.py --stock-id 2330 --days 30

  # 全量同步
  python scripts/sync_to_supabase.py

  # 同步多檔股票
  python scripts/sync_to_supabase.py --stock-ids 2330 2317 2454
"""

import argparse
import io
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# Windows 編碼修復
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    os.system("chcp 65001 > nul")

# 加入專案根目錄
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

# 載入環境變數
env_path = Path(__file__).parent.parent / "twstock" / "api.env"
if env_path.exists():
    load_dotenv(env_path)

# 環境變數檢查
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")  # service_role key for backend

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ 錯誤：請在 twstock/api.env 中設定 SUPABASE_URL 和 SUPABASE_KEY")
    print("   SUPABASE_URL=https://your-project.supabase.co")
    print("   SUPABASE_KEY=your-service-role-key")
    sys.exit(1)

print(f"📍 Supabase URL: {SUPABASE_URL}")
print(f"🔑 Supabase Key: {SUPABASE_KEY[:20]}...")

# 匯入 Supabase 客戶端
try:
    from supabase import create_client

    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("✅ Supabase 客戶端初始化成功")
except ImportError:
    print("❌ 請先安裝 supabase Python 套件:")
    print("   pip install supabase --break-system-packages")
    sys.exit(1)

# 匯入本地資料庫模組
from twstock.db import get_connection, get_path


def check_local_db():
    """檢查本地 SQLite 資料庫"""
    db_path = get_path()
    print(f"\n📂 本地資料庫: {db_path}")

    if not os.path.exists(db_path):
        print("❌ 本地資料庫不存在，請先執行 python twstock/main.py 建立資料")
        return False

    try:
        conn = get_connection(readonly=True)
        tables = {
            "stock_meta": 0,
            "stock_history": 0,
            "institutional_data": 0,
            "tdcc_shareholding": 0,
        }

        for table in tables:
            try:
                count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                tables[table] = count
                print(f"   {table}: {count:,} 筆")
            except Exception:
                print(f"   {table}: 不存在")

        conn.close()
        return True
    except Exception as e:
        print(f"❌ 資料庫查詢失敗: {e}")
        return False


def sync_stock_meta(stock_id: str = None):
    """同步 stock_meta 表"""
    print("\n🔄 同步 stock_meta...")
    conn = get_connection(readonly=True)

    if stock_id:
        rows = conn.execute("SELECT * FROM stock_meta WHERE stock_id = ?", (stock_id,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM stock_meta").fetchall()

    if not rows:
        print("   ⚠️ 無資料可同步")
        return 0

    # 轉換為 dict 列表（配合 Supabase 欄位）
    records = []
    for row in rows:
        row_dict = dict(row)
        records.append(
            {
                "stock_id": row_dict["stock_id"],
                "stock_name": row_dict["stock_name"],
                "market": row_dict.get("market", "TSE"),
                "industry_category": row_dict.get("industry_category"),
                "type": row_dict.get("type"),
                "source": row_dict.get("source"),
                "updated_at": row_dict.get("updated_at", datetime.now().isoformat()),
            }
        )

    # 批次寫入 Supabase
    batch_size = 100
    total = 0
    for i in range(0, len(records), batch_size):
        batch = records[i : i + batch_size]
        try:
            result = supabase.table("stock_meta").upsert(batch).execute()
            total += len(batch)
            print(f"   ✅ 已寫入 {total}/{len(records)}")
        except Exception as e:
            print(f"   ❌ 寫入失敗: {e}")
            break

    conn.close()
    print(f"   📊 stock_meta 同步完成: {total} 筆")
    return total


def sync_stock_history(stock_id: str = None, days: int = None):
    """同步 stock_price 表（原名 stock_history），最高控制在只抓取 512 個交易日"""
    print("\n🔄 同步 stock_price...")
    conn = get_connection(readonly=True)

    params = []

    if days:
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        if stock_id:
            query = """
                SELECT * FROM (
                    SELECT *, ROW_NUMBER() OVER(PARTITION BY stock_id ORDER BY date DESC) as rn 
                    FROM stock_history WHERE stock_id = ? AND date >= ?
                ) WHERE rn <= 512
            """
            params.extend([stock_id, cutoff])
        else:
            query = """
                SELECT * FROM (
                    SELECT *, ROW_NUMBER() OVER(PARTITION BY stock_id ORDER BY date DESC) as rn 
                    FROM stock_history WHERE date >= ?
                ) WHERE rn <= 512
            """
            params.append(cutoff)
    else:
        if stock_id:
            query = """
                SELECT * FROM (
                    SELECT *, ROW_NUMBER() OVER(PARTITION BY stock_id ORDER BY date DESC) as rn 
                    FROM stock_history WHERE stock_id = ?
                ) WHERE rn <= 512
            """
            params.append(stock_id)
        else:
            query = """
                SELECT * FROM (
                    SELECT *, ROW_NUMBER() OVER(PARTITION BY stock_id ORDER BY date DESC) as rn 
                    FROM stock_history
                ) WHERE rn <= 512
            """

    query += " ORDER BY stock_id, date DESC"

    rows = conn.execute(query, params).fetchall()

    if not rows:
        print("   ⚠️ 無資料可同步")
        return 0

    # 轉換為 dict 列表（配合 Supabase 欄位）
    # Supabase stock_price 使用 numeric(14,4)，需限制位數避免 overflow
    records = []
    for row in rows:
        row_dict = dict(row)

        def _safe_float(v, decimal_places=4, max_val=9999999999):
            if v is None:
                return None
            val = round(float(v), decimal_places)
            if val > max_val:
                val = max_val
            elif val < -max_val:
                val = -max_val
            return val

        def _safe_int(v):
            if v is None:
                return None
            # 限制在 10^10 以內 (numeric(14,4) 上限)
            val = int(v)
            if val > 9999999999:
                val = 9999999999
            elif val < -9999999999:
                val = -9999999999
            return val

        records.append(
            {
                "stock_id": row_dict["stock_id"],
                "date": row_dict["date"],
                "open": _safe_float(row_dict.get("open")),
                "high": _safe_float(row_dict.get("high")),
                "low": _safe_float(row_dict.get("low")),
                "close": _safe_float(row_dict.get("close")),
                "volume": _safe_int(row_dict.get("volume")),
                "amount": _safe_float(row_dict.get("amount")),
                "trade_count": _safe_int(row_dict.get("trade_count")),
                "spread": _safe_float(row_dict.get("spread")),
                "adj_factor": _safe_float(row_dict.get("adj_factor")),
                "source": row_dict.get("source"),
                "updated_at": row_dict.get("updated_at"),
            }
        )

    # 批次寫入 Supabase
    batch_size = 500
    total = 0
    for i in range(0, len(records), batch_size):
        batch = records[i : i + batch_size]
        try:
            # 使用 upsert 避免重複 (unique constraint: stock_id + date)
            result = supabase.table("stock_price").upsert(batch).execute()
            total += len(batch)
            print(f"   ✅ 已寫入 {total}/{len(records)}")
        except Exception as e:
            print(f"   ❌ 寫入失敗: {e}")
            break

    conn.close()
    print(f"   📊 stock_price 同步完成: {total} 筆")
    return total


def sync_institutional(stock_id: str = None, days: int = None):
    """同步 stock_institutional 表，最高控制在只抓取 512 個交易日"""
    print("\n🔄 同步 stock_institutional...")
    conn = get_connection(readonly=True)

    params = []

    if days:
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        if stock_id:
            query = """
                SELECT * FROM (
                    SELECT *, ROW_NUMBER() OVER(PARTITION BY stock_id ORDER BY date DESC) as rn 
                    FROM institutional_data WHERE stock_id = ? AND date >= ?
                ) WHERE rn <= 512
            """
            params.extend([stock_id, cutoff])
        else:
            query = """
                SELECT * FROM (
                    SELECT *, ROW_NUMBER() OVER(PARTITION BY stock_id ORDER BY date DESC) as rn 
                    FROM institutional_data WHERE date >= ?
                ) WHERE rn <= 512
            """
            params.append(cutoff)
    else:
        if stock_id:
            query = """
                SELECT * FROM (
                    SELECT *, ROW_NUMBER() OVER(PARTITION BY stock_id ORDER BY date DESC) as rn 
                    FROM institutional_data WHERE stock_id = ?
                ) WHERE rn <= 512
            """
            params.append(stock_id)
        else:
            query = """
                SELECT * FROM (
                    SELECT *, ROW_NUMBER() OVER(PARTITION BY stock_id ORDER BY date DESC) as rn 
                    FROM institutional_data
                ) WHERE rn <= 512
            """

    query += " ORDER BY stock_id, date DESC"

    rows = conn.execute(query, params).fetchall()

    if not rows:
        print("   ⚠️ 無資料可同步")
        return 0

    # 轉換為 dict 列表（配合 Supabase 欄位）
    records = []
    for row in rows:
        row_dict = dict(row)
        records.append(
            {
                "stock_id": row_dict["stock_id"],
                "date": row_dict["date"],
                "foreign_net": (
                    int(row_dict["foreign_net"])
                    if row_dict.get("foreign_net") is not None
                    else None
                ),
                "trust_net": (
                    int(row_dict["trust_net"]) if row_dict.get("trust_net") is not None else None
                ),
                "dealer_net": (
                    int(row_dict["dealer_net"]) if row_dict.get("dealer_net") is not None else None
                ),
                "institutional_net": (
                    int(row_dict["institutional_net"])
                    if row_dict.get("institutional_net") is not None
                    else None
                ),
                "foreign_buy": (
                    int(row_dict["foreign_buy"])
                    if row_dict.get("foreign_buy") is not None
                    else None
                ),
                "foreign_sell": (
                    int(row_dict["foreign_sell"])
                    if row_dict.get("foreign_sell") is not None
                    else None
                ),
                "trust_buy": (
                    int(row_dict["trust_buy"]) if row_dict.get("trust_buy") is not None else None
                ),
                "trust_sell": (
                    int(row_dict["trust_sell"]) if row_dict.get("trust_sell") is not None else None
                ),
                "dealer_buy": (
                    int(row_dict["dealer_buy"]) if row_dict.get("dealer_buy") is not None else None
                ),
                "dealer_sell": (
                    int(row_dict["dealer_sell"])
                    if row_dict.get("dealer_sell") is not None
                    else None
                ),
                "source": row_dict.get("source"),
                "updated_at": row_dict.get("updated_at"),
            }
        )

    # 批次寫入 Supabase
    batch_size = 500
    total = 0
    for i in range(0, len(records), batch_size):
        batch = records[i : i + batch_size]
        try:
            result = supabase.table("stock_institutional").upsert(batch).execute()
            total += len(batch)
            print(f"   ✅ 已寫入 {total}/{len(records)}")
        except Exception as e:
            print(f"   ❌ 寫入失敗: {e}")
            break

    conn.close()
    print(f"   📊 stock_institutional 同步完成: {total} 筆")
    return total


def sync_tdcc(stock_id: str = None, days: int = None):
    """同步 stock_features 表（TDCC 集保資料），最高控制在只抓取 512 個交易日"""
    print("\n🔄 同步 stock_features (TDCC)...")
    conn = get_connection(readonly=True)

    params = []

    if days:
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        if stock_id:
            query = """
                SELECT * FROM (
                    SELECT *, ROW_NUMBER() OVER(PARTITION BY stock_id ORDER BY date DESC) as rn 
                    FROM tdcc_shareholding WHERE stock_id = ? AND date >= ?
                ) WHERE rn <= 512
            """
            params.extend([stock_id, cutoff])
        else:
            query = """
                SELECT * FROM (
                    SELECT *, ROW_NUMBER() OVER(PARTITION BY stock_id ORDER BY date DESC) as rn 
                    FROM tdcc_shareholding WHERE date >= ?
                ) WHERE rn <= 512
            """
            params.append(cutoff)
    else:
        if stock_id:
            query = """
                SELECT * FROM (
                    SELECT *, ROW_NUMBER() OVER(PARTITION BY stock_id ORDER BY date DESC) as rn 
                    FROM tdcc_shareholding WHERE stock_id = ?
                ) WHERE rn <= 512
            """
            params.append(stock_id)
        else:
            query = """
                SELECT * FROM (
                    SELECT *, ROW_NUMBER() OVER(PARTITION BY stock_id ORDER BY date DESC) as rn 
                    FROM tdcc_shareholding
                ) WHERE rn <= 512
            """

    query += " ORDER BY stock_id, date DESC"

    rows = conn.execute(query, params).fetchall()

    if not rows:
        print("   ⚠️ 無資料可同步")
        return 0

    # 轉換為 dict 列表（配合 Supabase 欄位）
    # stock_features 沒有 source 欄位
    records = []
    for row in rows:
        row_dict = dict(row)

        def _safe_float(v, decimal_places=4):
            if v is None:
                return None
            return round(float(v), decimal_places)

        def _safe_int(v):
            if v is None:
                return None
            val = int(v)
            if val > 9999999999:
                val = 9999999999
            elif val < -9999999999:
                val = -9999999999
            return val

        records.append(
            {
                "stock_id": row_dict["stock_id"],
                "date": row_dict["date"],
                "whale_ratio": _safe_float(row_dict.get("whale_ratio")),
                "retail_ratio": _safe_float(row_dict.get("retail_ratio")),
                "total_shares": _safe_int(row_dict.get("total_shares")),
                "updated_at": row_dict.get("updated_at"),
            }
        )

    # 批次寫入 Supabase
    batch_size = 500
    total = 0
    for i in range(0, len(records), batch_size):
        batch = records[i : i + batch_size]
        try:
            result = supabase.table("stock_features").upsert(batch).execute()
            total += len(batch)
            print(f"   ✅ 已寫入 {total}/{len(records)}")
        except Exception as e:
            print(f"   ❌ 寫入失敗: {e}")
            break

    conn.close()
    print(f"   📊 stock_features 同步完成: {total} 筆")
    return total


def verify_sync():
    """驗證 Supabase 資料"""
    print("\n🔍 驗證 Supabase 資料...")
    tables = ["stock_meta", "stock_price", "stock_institutional", "stock_features"]

    for table in tables:
        try:
            result = supabase.table(table).select("count", count="exact").execute()
            count = result.count if hasattr(result, "count") else "未知"
            print(f"   {table}: {count} 筆")
        except Exception as e:
            print(f"   {table}: 查詢失敗 - {e}")


def main():
    parser = argparse.ArgumentParser(description="TWSE AnyTara → Supabase 同步")
    parser.add_argument("--stock-id", type=str, help="指定股票代號（如 2330）")
    parser.add_argument("--stock-ids", nargs="+", help="多檔股票代號")
    parser.add_argument("--days", type=int, help="只同步最近 N 天的資料")
    parser.add_argument("--verify-only", action="store_true", help="僅驗證 Supabase 資料")
    args = parser.parse_args()

    print("=" * 60)
    print("🚀 TWSE AnyTara — 本地 SQLite → Supabase 同步")
    print("=" * 60)

    if args.verify_only:
        verify_sync()
        return

    # 檢查本地資料庫
    if not check_local_db():
        print("\n❌ 本地資料庫無資料，請先執行：")
        print("   python twstock/main.py")
        sys.exit(1)

    # 如果有指定股票，只同步該股票
    stock_ids = args.stock_ids or []
    if args.stock_id:
        stock_ids.append(args.stock_id)

    start_time = time.time()

    if stock_ids:
        print(f"\n📌 指定股票: {', '.join(stock_ids)}")
        for sid in stock_ids:
            print(f"\n{'='*40}")
            print(f"📈 同步 {sid}")
            print(f"{'='*40}")
            sync_stock_meta(sid)
            sync_stock_history(sid, args.days)
            sync_institutional(sid, args.days)
            sync_tdcc(sid, args.days)
    else:
        print("\n📌 全量同步")
        sync_stock_meta()
        sync_stock_history(days=args.days)
        sync_institutional(days=args.days)
        sync_tdcc(days=args.days)

    elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"✅ 同步完成！耗時 {elapsed:.1f} 秒")
    print(f"{'='*60}")

    # 驗證
    verify_sync()


if __name__ == "__main__":
    main()
