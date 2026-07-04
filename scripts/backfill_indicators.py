"""
backfill_indicators.py — 一次性灌入 stock_indicators
執行：python backfill_indicators.py
"""

import os
import sys
import time

# 使用 db.py 的唯一入口取得路徑（避免寫死 Windows 路徑）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from twstock.db import get_connection


def main():
    conn = get_connection()
    conn.execute("PRAGMA synchronous=NORMAL")

    # 確認 stock_history 有多少支股票
    cur = conn.execute("SELECT COUNT(DISTINCT stock_id) FROM stock_history")
    total_stocks = cur.fetchone()[0]
    print(f"stock_history 共 {total_stocks} 支股票")

    # ====== Step 1: MACalculator ======
    from twstock.calculator import MACalculator

    print("\n[1/3] MACalculator (stock_history → stock_indicators MA/vol_ma/bias)")
    t0 = time.time()
    calc2 = MACalculator(db=conn)
    result2 = calc2.calculate_all()
    elapsed2 = time.time() - t0
    print(f"  完成：{len(result2)} 支股票，{elapsed2:.1f}s")

    # ====== Step 2: ATRCalculator ======
    from twstock.calculator import ATRCalculator

    print("\n[2/3] ATRCalculator (stock_history → stock_indicators atr14)")
    t0 = time.time()
    calc3 = ATRCalculator(db=conn)
    result3 = calc3.calculate_all()
    elapsed3 = time.time() - t0
    print(f"  完成：{len(result3)} 支股票，{elapsed3:.1f}s")

    # ====== Step 3: VWAPCalculator ======
    from twstock.calculator import VWAPCalculator

    print("\n[3/3] VWAPCalculator (stock_history → stock_indicators vwap)")
    t0 = time.time()
    calc4 = VWAPCalculator(db=conn)
    result4 = calc4.calculate_all()
    elapsed4 = time.time() - t0
    print(f"  完成：{len(result4)} 支股票，{elapsed4:.1f}s")

    # ====== 驗證 ======
    print("\n===== 驗證 =====")
    cur = conn.execute("SELECT COUNT(*) FROM stock_indicators")
    total_rows = cur.fetchone()[0]
    print(f"stock_indicators 總筆數：{total_rows}")

    cur = conn.execute("SELECT COUNT(*) FROM stock_indicators WHERE ma5 IS NOT NULL")
    ma5_count = cur.fetchone()[0]
    print(f"ma5 有值筆數：{ma5_count}")

    cur = conn.execute("SELECT COUNT(*) FROM stock_indicators WHERE atr14 IS NOT NULL")
    atr_count = cur.fetchone()[0]
    print(f"atr14 有值筆數：{atr_count}")

    cur = conn.execute("SELECT COUNT(*) FROM stock_indicators WHERE vwap IS NOT NULL")
    vwap_count = cur.fetchone()[0]
    print(f"vwap 有值筆數：{vwap_count}")

    # 抽查 2330 最近一筆
    cur = conn.execute(
        "SELECT stock_id, date, ma5, ma25, vol_ma5, bias_ma25, atr14, vwap "
        "FROM stock_indicators WHERE stock_id='2330' "
        "ORDER BY date DESC LIMIT 1"
    )
    row = cur.fetchone()
    if row:
        print("\n抽查 2330 最近一筆：")
        print(f"  stock_id={row[0]}, date={row[1]}")
        print(f"  ma5={row[2]}, ma25={row[3]}, vol_ma5={row[4]}")
        print(f"  bias_ma25={row[5]}, atr14={row[6]}, vwap={row[7]}")
    else:
        print("\n2330 無資料（stock_history 可能無此股票）")

    conn.close()
    total_elapsed = elapsed2 + elapsed3 + elapsed4
    print(f"\n全部完成，耗時 {total_elapsed:.1f}s")


if __name__ == "__main__":
    main()
