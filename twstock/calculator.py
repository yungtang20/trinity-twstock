#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
calculator.py — 技術指標計算引擎
從 stock_history 讀取日線資料，計算 SMA/EMA/MACD/Bollinger/KDJ/RSI/LogReturn/Pivot，
並嘗試 LEFT JOIN 基本面與籌碼資料。
"""

import pandas as pd
import numpy as np
import os
from db import get_connection, DB_PATH
from db_admin import create_tables  # [FIX] Reuse the single stock_indicators schema definition instead of duplicating it here


class IndicatorEngine:
    def __init__(self, stock_id, limit=600, df_intraday=None):
        self.stock_id = stock_id
        self.limit = limit
        self.df = self._load_data()
        if df_intraday is not None and not df_intraday.empty:
            self.df = pd.concat([self.df, df_intraday], ignore_index=True)

    def _load_data(self):
        """從 stock_history 讀取 date, open, high, low, close, volume，按 date 升序排列"""
        conn = get_connection(readonly=True)
        query = """
            SELECT date, open, high, low, close, volume
            FROM stock_history
            WHERE stock_id = ?
            ORDER BY date ASC
            LIMIT ?
        """
        df = pd.read_sql_query(query, conn, params=(self.stock_id, self.limit))
        conn.close()
        if df.empty:
            return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
        df["date"] = pd.to_datetime(df["date"])
        return df

    def _add_moving_averages(self):
        """計算 SMA 5/10/20/60/120/200, EMA 12/26, 成交量 SMA 5/20, 成交量比率"""
        if self.df.empty:
            return
        close = self.df["close"]
        vol = self.df["volume"]

        # SMA
        for period in [5, 10, 20, 60, 120, 200]:
            self.df[f"sma_{period}"] = close.rolling(window=period).mean()

        # EMA
        self.df["ema_12"] = close.ewm(span=12, adjust=False).mean()
        self.df["ema_26"] = close.ewm(span=26, adjust=False).mean()

        # 成交量均線
        self.df["volume_sma_5"] = vol.rolling(window=5).mean()
        self.df["volume_sma_20"] = vol.rolling(window=20).mean()
        self.df["volume_ratio"] = vol / self.df["volume_sma_5"]

    def _add_macd(self):
        """MACD (12, 26, 9): DIF, DEA, HISTOGRAM"""
        if self.df.empty:
            return
        close = self.df["close"]
        ema_12 = close.ewm(span=12, adjust=False).mean()
        ema_26 = close.ewm(span=26, adjust=False).mean()
        self.df["macd_dif"] = ema_12 - ema_26
        self.df["macd_dea"] = self.df["macd_dif"].ewm(span=9, adjust=False).mean()
        self.df["macd_hist"] = self.df["macd_dif"] - self.df["macd_dea"]

    def _add_kdj(self):
        """KDJ (9, 3, 3): K, D, J"""
        if self.df.empty:
            return
        n = 9
        low_n = self.df["low"].rolling(window=n).min()
        high_n = self.df["high"].rolling(window=n).max()
        rsv = (self.df["close"] - low_n) / (high_n - low_n) * 100
        rsv = rsv.fillna(50)

        self.df["kdj_k"] = rsv.ewm(com=2, adjust=False).mean()
        self.df["kdj_d"] = self.df["kdj_k"].ewm(com=2, adjust=False).mean()
        self.df["kdj_j"] = 3 * self.df["kdj_k"] - 2 * self.df["kdj_d"]

    def _add_rsi(self):
        """RSI 6 / 14"""
        if self.df.empty:
            return
        for period in [6, 14]:
            delta = self.df["close"].diff()
            gain = delta.where(delta > 0, 0.0)
            loss = -delta.where(delta < 0, 0.0)
            avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
            avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
            rs = avg_gain / avg_loss
            self.df[f"rsi_{period}"] = 100 - (100 / (1 + rs))

    def _add_bollinger_bands(self):
        """Bollinger Bands (20, 2): middle, upper, lower, bandwidth, %b"""
        if self.df.empty:
            return
        period = 20
        self.df["bb_middle"] = self.df["close"].rolling(window=period).mean()
        std = self.df["close"].rolling(window=period).std()
        self.df["bb_upper"] = self.df["bb_middle"] + 2 * std
        self.df["bb_lower"] = self.df["bb_middle"] - 2 * std
        self.df["bb_bandwidth"] = (self.df["bb_upper"] - self.df["bb_lower"]) / self.df["bb_middle"] * 100
        self.df["bb_pct_b"] = (self.df["close"] - self.df["bb_lower"]) / (self.df["bb_upper"] - self.df["bb_lower"])

    def _add_log_return(self):
        """日報酬率 (log return)"""
        if self.df.empty:
            return
        self.df["log_return"] = np.log(self.df["close"] / self.df["close"].shift(1))

    def _add_pivot(self):
        """樞紐點: pivot, r1, r2, s1, s2"""
        if self.df.empty:
            return
        self.df["pivot"] = (self.df["high"] + self.df["low"] + self.df["close"]) / 3
        self.df["pivot_r1"] = 2 * self.df["pivot"] - self.df["low"]
        self.df["pivot_r2"] = self.df["pivot"] + (self.df["high"] - self.df["low"])
        self.df["pivot_s1"] = 2 * self.df["pivot"] - self.df["high"]
        self.df["pivot_s2"] = self.df["pivot"] - (self.df["high"] - self.df["low"])

    def _join_fundamental_chips(self):
        """JOIN 籌碼/基本面資料，若無對應表則跳過"""
        if self.df.empty:
            return
        try:
            conn = get_connection(readonly=True)
            tables_to_join = [
                ("institutional_data", ["foreign_buy", "foreign_sell", "trust_buy", "trust_sell"]),
                ("shareholding_data", ["foreign_shares", "foreign_ratio"]),
            ]
            for table, cols in tables_to_join:
                try:
                    query = f"SELECT stock_id, date, {', '.join(cols)} FROM {table} WHERE stock_id = ?"
                    df_join = pd.read_sql_query(query, conn, params=(self.stock_id,))
                    if not df_join.empty:
                        df_join["date"] = pd.to_datetime(df_join["date"])
                        self.df["date"] = pd.to_datetime(self.df["date"])
                        self.df = self.df.merge(df_join, on=["stock_id", "date"], how="left")
                except Exception:
                    pass  # 表格不存在就跳過
            conn.close()
        except Exception:
            pass

    def build(self):
        """整合所有計算步驟，回傳完整 DataFrame"""
        if self.df.empty:
            return self.df

        # 1. 按日期升序
        self.df = self.df.sort_values("date").reset_index(drop=True)

        # 2. 移除 close <= 0 的列
        self.df = self.df[self.df["close"] > 0].copy()
        if self.df.empty:
            return self.df

        # 3. 依序計算各項指標
        self._add_moving_averages()
        self._add_macd()
        self._add_bollinger_bands()
        self._add_kdj()
        self._add_rsi()
        self._add_log_return()
        self._add_pivot()

        # 4. 嘗試 JOIN 籌碼資料
        self._join_fundamental_chips()

        return self.df


# ATRCalculator — Issue 009 (ATR14，Wilder's EMA)
# ============================================================================

class ATRCalculator:
    """ATR14 計算器，使用 Wilder's EMA 平滑法"""

    def __init__(self, db):
        self.db = db

    def calculate(self, stock_id):
        """
        計算 stock_id 的 ATR14，UPSERT 到 stock_indicators.atr14。

        TR(1) = high - low
        TR(t) = max(high-low, |high-prev_close|, |low-prev_close|)
        ATR14(14) = mean(TR1..TR14)（第一個值用 SMA）
        ATR14(t)  = (ATR14(t-1) * 13 + TR(t)) / 14（Wilder's EMA）
        前 13 天 = NULL
        """
        cur = self.db.execute(
            "SELECT date, high, low, close FROM stock_history "
            "WHERE stock_id=? ORDER BY date ASC",
            (stock_id,)
        )
        rows = cur.fetchall()
        if not rows:
            return 0

        import math

        dates = [r[0] for r in rows]
        highs = [r[1] for r in rows]
        lows = [r[2] for r in rows]
        closes = [r[3] for r in rows]
        n = len(dates)

        # 計算 TR
        tr = [0.0] * n
        tr[0] = highs[0] - lows[0]  # 第一天無 prev_close
        for i in range(1, n):
            prev_close = closes[i - 1]
            tr[i] = max(
                highs[i] - lows[i],
                abs(highs[i] - prev_close),
                abs(lows[i] - prev_close)
            )

        # 計算 ATR14（ Wilder's EMA）
        atr14 = [None] * n
        period = 14
        if n >= period:
            # 第一個 ATR14 = SMA(TR1..TR14)
            atr14[period - 1] = sum(tr[:period]) / period
            # 後續用 Wilder's EMA
            for i in range(period, n):
                atr14[i] = (atr14[i - 1] * (period - 1) + tr[i]) / period

        # UPSERT stock_indicators（只更新 atr14）
        for i in range(n):
            val = atr14[i]
            if val is not None and isinstance(val, float) and math.isnan(val):
                val = None
            self.db.execute(
                """INSERT INTO stock_indicators (stock_id, date, atr14)
                VALUES (?, ?, ?)
                ON CONFLICT(stock_id, date) DO UPDATE SET atr14=excluded.atr14""",
                (stock_id, dates[i], val)
            )

        self.db.commit()
        return n

    def calculate_all(self):
        """
        對 stock_history 所有 stock_id 執行 calculate()。
        回傳 dict：{stock_id: count}
        """
        cur = self.db.execute("SELECT DISTINCT stock_id FROM stock_history")
        stock_ids = [row[0] for row in cur.fetchall()]

        result = {}
        for stock_id in stock_ids:
            result[stock_id] = self.calculate(stock_id)
        return result


# ============================================================================
# VWAPCalculator — Issue 010 (日 VWAP = amount / volume)
# ============================================================================

class VWAPCalculator:
    """日 VWAP 計算器，vwap = amount / volume"""

    def __init__(self, db):
        self.db = db

    def calculate(self, stock_id):
        """
        計算 stock_id 的日 VWAP，UPSERT 到 stock_indicators.vwap。

        vwap = amount / volume
        volume = 0 → vwap = NULL
        """
        cur = self.db.execute(
            "SELECT date, volume, amount FROM stock_history "
            "WHERE stock_id=? ORDER BY date ASC",
            (stock_id,)
        )
        rows = cur.fetchall()
        if not rows:
            return 0

        import math

        updates = 0
        for date, volume, amount in rows:
            vwap = None
            if volume and volume > 0:
                vwap = float(amount) / float(volume)
                if math.isnan(vwap) or math.isinf(vwap):
                    vwap = None

            self.db.execute(
                """INSERT INTO stock_indicators (stock_id, date, vwap)
                VALUES (?, ?, ?)
                ON CONFLICT(stock_id, date) DO UPDATE SET vwap=excluded.vwap""",
                (stock_id, date, vwap)
            )
            updates += 1

        self.db.commit()
        return updates

    def calculate_all(self):
        """
        對 stock_history 所有 stock_id 執行 calculate()。
        回傳 dict：{stock_id: count}
        """
        cur = self.db.execute("SELECT DISTINCT stock_id FROM stock_history")
        stock_ids = [row[0] for row in cur.fetchall()]

        result = {}
        for stock_id in stock_ids:
            result[stock_id] = self.calculate(stock_id)
        return result



class MACalculator:
    """
    MA 計算器 — 供 test_008_ma.py 使用
    介面：MACalculator(db=conn) → calculate(stock_id) → int
    """

    def __init__(self, db):
        self.db = db

    def calculate(self, stock_id: str) -> int:
        """
        計算 stock_id 的 MA 指標並寫入 stock_indicators。
        回傳寫入列數。
        """
        # 用 pd.read_sql 從 db 讀取（不加 LIMIT，確保全部歷史資料都被計算）
        df = pd.read_sql(
            "SELECT date, open, high, low, close, volume FROM stock_history "
            "WHERE stock_id = ? ORDER BY date ASC",
            self.db, params=(stock_id,)
        )
        if df.empty:
            return 0

        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
        df = df[df["close"] > 0].copy()
        if df.empty:
            return 0

        close = df["close"]
        vol = df["volume"]

        # SMA
        for period in [5, 10, 20, 25, 60, 120, 200]:
            df[f"sma_{period}"] = close.rolling(window=period).mean()

        # 成交量均線
        df["volume_sma_5"] = vol.rolling(window=5).mean()
        df["volume_sma_20"] = vol.rolling(window=20).mean()
        df["volume_sma_60"] = vol.rolling(window=60).mean()

        # 確保表格存在（改用 db_admin.py 的唯一 schema 定義，避免兩處定義漂移）
        create_tables(self.db)

        # 寫入指標
        written = 0
        for _, row in df.iterrows():
            date_str = str(row["date"])[:10]
            ma5  = float(row["sma_5"])  if pd.notna(row.get("sma_5"))  else None
            ma20 = float(row["sma_20"]) if pd.notna(row.get("sma_20")) else None
            ma25 = float(row["sma_25"]) if pd.notna(row.get("sma_25")) else None
            ma60 = float(row["sma_60"]) if pd.notna(row.get("sma_60")) else None
            ma200 = float(row["sma_200"]) if pd.notna(row.get("sma_200")) else None
            vol_ma5 = float(row["volume_sma_5"]) if pd.notna(row.get("volume_sma_5")) else None
            vol_ma20 = float(row["volume_sma_20"]) if pd.notna(row.get("volume_sma_20")) else None
            vol_ma60 = float(row["volume_sma_60"]) if pd.notna(row.get("volume_sma_60")) else None

            def _bias(c, m):
                if m is None or m == 0:
                    return None
                return (c - m) / m * 100

            close_val = float(row["close"]) if pd.notna(row.get("close")) else None
            bias_ma25 = _bias(close_val, ma25)
            bias_ma60 = _bias(close_val, ma60)
            bias_ma200 = _bias(close_val, ma200)

            self.db.execute("""
                INSERT INTO stock_indicators
                (stock_id, date, ma5, ma20, ma25, ma60, ma200, vol_ma5, vol_ma20, vol_ma60,
                 bias_ma25, bias_ma60, bias_ma200, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(stock_id, date) DO UPDATE SET
                    ma5=excluded.ma5, ma20=excluded.ma20, ma25=excluded.ma25,
                    ma60=excluded.ma60, ma200=excluded.ma200,
                    vol_ma5=excluded.vol_ma5, vol_ma20=excluded.vol_ma20, vol_ma60=excluded.vol_ma60,
                    bias_ma25=excluded.bias_ma25, bias_ma60=excluded.bias_ma60,
                    bias_ma200=excluded.bias_ma200,
                    updated_at=CURRENT_TIMESTAMP
            """, (stock_id, date_str, ma5, ma20, ma25, ma60, ma200,
                  vol_ma5, vol_ma20, vol_ma60, bias_ma25, bias_ma60, bias_ma200))
            written += 1

        self.db.commit()
        return written

    def calculate_all(self):
        """
        對 stock_history 所有 stock_id 執行 calculate()。
        回傳 dict：{stock_id: count}
        """
        from db_admin import create_tables
        create_tables(self.db)  # 只呼叫一次，避免每支股票重複 catalog 檢查
        cur = self.db.execute("SELECT DISTINCT stock_id FROM stock_history")
        stock_ids = [row[0] for row in cur.fetchall()]

        result = {}
        for stock_id in stock_ids:
            result[stock_id] = self.calculate(stock_id)
        return result
