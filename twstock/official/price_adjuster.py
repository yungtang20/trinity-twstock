#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
official/price_adjuster.py
根據除權息事件，計算股票的前復權價格與還原因子 (adj_factor)。
使用與交易所一致的累乘法，保證還原價連續性。
# [AI MOD] Restructured with robust estimation logic, defensive checks, and standalone CLI support.
"""

import sqlite3
import pandas as pd
import numpy as np
import bisect
import sys
import os
from pathlib import Path

# 加入父目錄以便引入 db 模組 [AI MOD]
_PARENT = Path(__file__).resolve().parent.parent
if str(_PARENT) not in sys.path:
    sys.path.append(str(_PARENT))
from db import DB_PATH

def compute_adjusted_prices(stock_id: str, price_df: pd.DataFrame, div_df: pd.DataFrame) -> pd.DataFrame:
    """
    為單一股票計算前復權價格與還原因子 (adj_factor)。
    演算法：從最舊到最新，累乘每次除權息事件的「參考價 / 前收盤價」，
          得到每日 adj_factor，再乘以原始價格即得前復權價。
    
    Args:
        stock_id: 股票代號
        price_df: 包含 date, open, high, low, close 的 DataFrame
        div_df:   包含 date, before_price, reference_price, cash_dividend, stock_dividend 的 DataFrame
    
    Returns:
        DataFrame 包含 date, open, high, low, close, adj_factor,
                   adj_open, adj_high, adj_low, adj_close
    """
    if price_df.empty:
        return price_df

    # 確保資料按日期升序排序
    df = price_df.sort_values('date').copy().reset_index(drop=True)
    df['date'] = pd.to_datetime(df['date'])
    df['adj_factor'] = 1.0

    # 若無除權息事件，直接複製原始價格
    if div_df.empty:
        df['adj_open'] = df['open']
        df['adj_high'] = df['high']
        df['adj_low'] = df['low']
        df['adj_close'] = df['close']
        return df[['date', 'open', 'high', 'low', 'close', 'adj_factor',
                   'adj_open', 'adj_high', 'adj_low', 'adj_close']]

    # 建立還原因子事件列表 (累乘的比值) [AI MOD]
    events = []
    div_df_sorted = div_df.sort_values('date').copy()
    div_df_sorted['date'] = pd.to_datetime(div_df_sorted['date'])

    for _, row in div_df_sorted.iterrows():
        event_date = row['date']
        # 優先使用官方公告的 before_price 與 reference_price
        b = row.get('before_price')
        r = row.get('reference_price')
        if pd.notna(b) and pd.notna(r) and b > 0 and r > 0 and abs(b - r) > 1e-8:
            factor = r / b
            events.append({'date': event_date, 'factor': factor})
            continue

        # 若無完整參考價，則用現金股利與股票股利估算 [AI MOD]
        cash = float(row.get('cash_dividend', 0)) if pd.notna(row.get('cash_dividend')) else 0.0
        stock = float(row.get('stock_dividend', 0)) if pd.notna(row.get('stock_dividend')) else 0.0
        if cash > 0 or stock > 0:
            # 找事件前一天的收盤價
            prev_rows = df[df['date'] < event_date]
            if not prev_rows.empty:
                prev_close = prev_rows.iloc[-1]['close']
                # 正確的參考價公式： (前收盤 - 現金股利) / (1 + 股票股利/10)
                # 股票股利單位為元，每10股配幾股
                ref_price = (prev_close - cash) / (1 + stock / 10.0)
                if ref_price > 0 and prev_close > 0:
                    factor = ref_price / prev_close
                    events.append({'date': event_date, 'factor': factor})
                    print(f"      [估算] {stock_id} {event_date.strftime('%Y-%m-%d')} "
                          f"cash={cash:.2f} stock={stock:.4f} factor={factor:.6f}")
                else:
                    print(f"      [警告] {stock_id} {event_date.strftime('%Y-%m-%d')} "
                          f"計算參考價無效 (prev_close={prev_close}, ref_price={ref_price})")
            else:
                print(f"      [跳過] {stock_id} {event_date.strftime('%Y-%m-%d')} 無前一日收盤價")
        else:
            print(f"      [忽略] {stock_id} {event_date.strftime('%Y-%m-%d')} 無有效除權息資料")

    if not events:
        # 沒有有效事件，直接複製
        df['adj_open'] = df['open']
        df['adj_high'] = df['high']
        df['adj_low'] = df['low']
        df['adj_close'] = df['close']
        return df[['date', 'open', 'high', 'low', 'close', 'adj_factor',
                   'adj_open', 'adj_high', 'adj_low', 'adj_close']]

    # 按日期排序事件
    events.sort(key=lambda x: x['date'])
    event_dates = [e['date'] for e in events]
    factors = [e['factor'] for e in events]

    # 前復權累乘：從最舊的事件往未來累積 [AI MOD]
    # suffix[i] 代表第 i 個事件及其之後所有事件的累積乘積
    suffix = [1.0] * (len(factors) + 1)
    for i in range(len(factors) - 1, -1, -1):
        suffix[i] = suffix[i + 1] * factors[i]

    # 為每一天分配 adj_factor
    df['adj_factor'] = df['date'].apply(
        lambda d: suffix[bisect.bisect_right(event_dates, d)]
    )

    # 計算前復權開高低收
    df['adj_open'] = (df['open'] * df['adj_factor']).round(2)
    df['adj_high'] = (df['high'] * df['adj_factor']).round(2)
    df['adj_low'] = (df['low'] * df['adj_factor']).round(2)
    df['adj_close'] = (df['close'] * df['adj_factor']).round(2)

    return df[['date', 'open', 'high', 'low', 'close', 'adj_factor',
               'adj_open', 'adj_high', 'adj_low', 'adj_close']]


def update_adjusted_prices_for_stock(stock_id: str, force_recalc: bool = False):
    """
    更新單一股票的還原價格 (只更新 adj_factor，不覆蓋其他欄位) [AI MOD]
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        # 讀取歷史價量
        price_df = pd.read_sql(
            "SELECT date, open, high, low, close FROM stock_history "
            "WHERE stock_id = ? ORDER BY date",
            conn, params=(stock_id,)
        )
        # 讀取除權息事件
        div_df = pd.read_sql(
            "SELECT date, before_price, reference_price, cash_dividend, stock_dividend "
            "FROM dividend_events WHERE stock_id = ? ORDER BY date",
            conn, params=(stock_id,)
        )
    finally:
        conn.close()

    if price_df.empty:
        return

    result = compute_adjusted_prices(stock_id, price_df, div_df)
    if result.empty:
        return

    # 批次更新資料庫 [AI MOD]
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        # 將日期轉為字串格式 YYYY-MM-DD
        if pd.api.types.is_datetime64_any_dtype(result['date']):
            date_strs = result['date'].dt.strftime('%Y-%m-%d')
        else:
            date_strs = result['date']

        # 準備更新語句：只更新 adj_factor（其餘復權價可選，此處不寫入 stock_history，因為已由視圖 klines 提供）
        updates = list(zip(result['adj_factor'], [stock_id] * len(result), date_strs))
        cursor.executemany(
            "UPDATE stock_history SET adj_factor = ? WHERE stock_id = ? AND date = ?",
            updates
        )
        conn.commit()
        print(f"  ✅ {stock_id} 更新 {len(updates)} 筆 adj_factor")
    except Exception as e:
        print(f"  ❌ {stock_id} 更新失敗: {e}")
    finally:
        conn.close()


def update_all_adjusted_prices(force_recalc: bool = False):
    """
    為全市場所有股票計算還原價格 (adj_factor) [AI MOD]
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        stocks = pd.read_sql(
            "SELECT DISTINCT stock_id FROM stock_history ORDER BY stock_id",
            conn
        )['stock_id'].tolist()
    finally:
        conn.close()

    print(f"🔧 開始計算 {len(stocks)} 檔股票的前復權還原因子...")
    for i, stock_id in enumerate(stocks, 1):
        print(f"  [{i}/{len(stocks)}] 處理 {stock_id}...")
        try:
            update_adjusted_prices_for_stock(stock_id, force_recalc)
        except Exception as e:
            print(f"      處理 {stock_id} 時發生錯誤: {e}")
    print("✅ 所有股票 adj_factor 計算完成！")
    print("💡 提示：klines 視圖會自動根據 adj_factor 計算 adj_close 等欄位，無需額外動作。")


if __name__ == "__main__":
    # 獨立執行時，可選擇更新單一或全市場 [AI MOD]
    import argparse
    parser = argparse.ArgumentParser(description="還原價格計算工具")
    parser.add_argument("--stock", type=str, help="單一股票代號，如 2330")
    parser.add_argument("--all", action="store_true", help="更新全市場")
    args = parser.parse_args()

    if args.stock:
        update_adjusted_prices_for_stock(args.stock, force_recalc=True)
    elif args.all:
        update_all_adjusted_prices(force_recalc=True)
    else:
        print("請使用 --stock 2330 或 --all 參數")