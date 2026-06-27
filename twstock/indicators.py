# indicators.py — 技術指標計算模組（即時計算，不寫入 DB）


class TechnicalIndicators:
    def __init__(self, db):
        self.db = db

    def _get_prices(self, stock_id):
        """從 stock_history 讀取 OHLCV，回傳 list of dict（按 date ASC）"""
        cur = self.db.execute(
            "SELECT date, open, high, low, close, volume, amount "
            "FROM stock_history WHERE stock_id = ? ORDER BY date ASC",
            (stock_id,)
        )
        rows = cur.fetchall()
        if not rows:
            return []
        return [
            {
                "date": r[0],
                "open": r[1],
                "high": r[2],
                "low": r[3],
                "close": r[4],
                "volume": r[5],
                "amount": r[6],
            }
            for r in rows
        ]

    def sma(self, stock_id, period=5):
        """
        計算 SMA(stock_id, period)。
        回傳 list of dict：[{"stock_id": ..., "date": ..., "sma_5": ...}, ...]
        前 period-1 天的 SMA 為 None。
        """
        data = self._get_prices(stock_id)
        if not data:
            return []

        key = f"sma_{period}"
        result = []
        for i, row in enumerate(data):
            if i < period - 1:
                result.append({"stock_id": stock_id, "date": row["date"], key: None})
            else:
                window = [data[j]["close"] for j in range(i - period + 1, i + 1)]
                sma_val = sum(window) / period
                result.append({"stock_id": stock_id, "date": row["date"], key: round(sma_val, 4)})
        return result

    def ema(self, stock_id, period=12):
        """
        計算 EMA(stock_id, period)。
        回傳 list of dict：[{"stock_id": ..., "date": ..., "ema_12": ...}, ...]
        資料筆數 < period/2 → 全部 None。
        否則從第 1 天開始計算，第一個值 = close[0]。
        """
        data = self._get_prices(stock_id)
        if not data:
            return []

        key = f"ema_{period}"
        result = []
        # 資料不足 period/3 → 全部 None
        if len(data) < period / 3:
            for row in data:
                result.append({"stock_id": stock_id, "date": row["date"], key: None})
            return result

        k = 2 / (period + 1)
        ema_val = data[0]["close"]
        result.append({"stock_id": stock_id, "date": data[0]["date"], key: round(ema_val, 4)})
        for i in range(1, len(data)):
            ema_val = data[i]["close"] * k + ema_val * (1 - k)
            result.append({"stock_id": stock_id, "date": data[i]["date"], key: round(ema_val, 4)})
        return result

    def rsi(self, stock_id, period=6):
        """
        計算 RSI(stock_id, period)。
        使用 Wilder's smoothing: alpha = 1/period。
        回傳 list of dict：[{"stock_id": ..., "date": ..., "rsi_6": ...}, ...]
        第 1 天（無前日）→ rsi = None。
        """
        data = self._get_prices(stock_id)
        if not data:
            return []

        key = f"rsi_{period}"
        result = []
        avg_gain = None
        avg_loss = None

        for i, row in enumerate(data):
            if i == 0:
                result.append({"stock_id": stock_id, "date": row["date"], key: None})
                continue

            delta = row["close"] - data[i-1]["close"]
            gain = max(delta, 0)
            loss = max(-delta, 0)

            if i < period:
                result.append({"stock_id": stock_id, "date": row["date"], key: None})
            elif avg_gain is None:
                # 用前 period 天的平均 gain/loss 作為初始值
                gains = []
                losses = []
                for j in range(1, period + 1):
                    d = data[j]["close"] - data[j-1]["close"]
                    gains.append(max(d, 0))
                    losses.append(max(-d, 0))
                avg_gain = sum(gains) / period
                avg_loss = sum(losses) / period
                if avg_loss == 0:
                    rsi_val = 100.0
                elif avg_gain == 0:
                    rsi_val = 0.0
                else:
                    rs = avg_gain / avg_loss
                    rsi_val = 100 - (100 / (1 + rs))
                result.append({"stock_id": stock_id, "date": row["date"], key: round(rsi_val, 4)})
            else:
                avg_gain = (avg_gain * (period - 1) + gain) / period
                avg_loss = (avg_loss * (period - 1) + loss) / period
                if avg_loss == 0:
                    rsi_val = 100.0
                elif avg_gain == 0:
                    rsi_val = 0.0
                else:
                    rs = avg_gain / avg_loss
                    rsi_val = 100 - (100 / (1 + rs))
                result.append({"stock_id": stock_id, "date": row["date"], key: round(rsi_val, 4)})

        return result

    def macd(self, stock_id):
        """
        計算 MACD (12, 26, 9)。
        DIF = EMA(12) - EMA(26)
        DEA = EMA(DIF, 9)
        HIST = DIF - DEA
        回傳 list of dict：[{"stock_id":..., "date":..., "macd_dif":..., "macd_dea":..., "macd_hist":...}, ...]
        """
        data = self._get_prices(stock_id)
        if not data:
            return []

        result = []
        dif_list = []
        ema_12 = None
        ema_26 = None
        dea = None
        k_12 = 2 / (12 + 1)
        k_26 = 2 / (26 + 1)
        k_9 = 2 / (9 + 1)

        for i, row in enumerate(data):
            close = row["close"]

            # EMA 12
            if i < 11:
                ema_12 = None
            elif ema_12 is None:
                ema_12 = sum(data[j]["close"] for j in range(0, 12)) / 12
            else:
                ema_12 = close * k_12 + ema_12 * (1 - k_12)

            # EMA 26
            if i < 25:
                ema_26 = None
            elif ema_26 is None:
                ema_26 = sum(data[j]["close"] for j in range(0, 26)) / 26
            else:
                ema_26 = close * k_26 + ema_26 * (1 - k_26)

            # DIF
            if ema_12 is not None and ema_26 is not None:
                dif = ema_12 - ema_26
                dif_list.append(dif)
            else:
                dif = None

            # DEA
            if dif is None:
                dea = None
            elif len(dif_list) < 9:
                dea = None
            elif dea is None:
                dea = sum(dif_list[:9]) / 9
            else:
                dea = dif * k_9 + dea * (1 - k_9)

            # HIST（用 round 後的值計算，確保 hist = dif - dea）
            if dif is not None and dea is not None:
                dif_r = round(dif, 4)
                dea_r = round(dea, 4)
                result.append({
                    "stock_id": stock_id,
                    "date": row["date"],
                    "macd_dif": dif_r,
                    "macd_dea": dea_r,
                    "macd_hist": round(dif_r - dea_r, 4),
                })
            else:
                result.append({
                    "stock_id": stock_id,
                    "date": row["date"],
                    "macd_dif": None,
                    "macd_dea": None,
                    "macd_hist": None,
                })

        return result

    def kdj(self, stock_id):
        """
        計算 KDJ (9, 3, 3)。
        RSV = (close - low_9) / (high_9 - low_9) * 100
        K = 2/3 * prev_K + 1/3 * RSV（初始 K=50）
        D = 2/3 * prev_D + 1/3 * K（初始 D=50）
        J = 3K - 2D
        回傳 list of dict：[{"stock_id":..., "date":..., "kdj_k":..., "kdj_d":..., "kdj_j":...}, ...]
        """
        data = self._get_prices(stock_id)
        if not data:
            return []

        n = 9
        result = []
        k_val = None
        d_val = None

        for i, row in enumerate(data):
            if i < n - 1:
                result.append({
                    "stock_id": stock_id,
                    "date": row["date"],
                    "kdj_k": None,
                    "kdj_d": None,
                    "kdj_j": None,
                })
                continue

            # RSV
            window_high = [data[j]["high"] for j in range(i - n + 1, i + 1)]
            window_low = [data[j]["low"] for j in range(i - n + 1, i + 1)]
            high_n = max(window_high)
            low_n = min(window_low)

            if high_n == low_n:
                rsv = 50.0
            else:
                rsv = (row["close"] - low_n) / (high_n - low_n) * 100

            # K (com=2 → alpha=1/3)
            if k_val is None:
                k_val = rsv
            else:
                k_val = rsv * (1/3) + k_val * (2/3)

            # D (com=2 → alpha=1/3)
            if d_val is None:
                d_val = k_val
            else:
                d_val = k_val * (1/3) + d_val * (2/3)

            # J
            j_val = 3 * k_val - 2 * d_val

            result.append({
                "stock_id": stock_id,
                "date": row["date"],
                "kdj_k": round(k_val, 4),
                "kdj_d": round(d_val, 4),
                "kdj_j": round(j_val, 4),
            })

        return result

    def bollinger(self, stock_id):
        """
        計算 Bollinger Bands (20, 2)。
        Middle = SMA(20)
        Upper = Middle + 2 * STD(20)
        Lower = Middle - 2 * STD(20)
        Bandwidth = (Upper - Lower) / Middle * 100
        %B = (close - Lower) / (Upper - Lower)
        回傳 list of dict：[{"stock_id":..., "date":..., "bb_middle":..., "bb_upper":...,
                             "bb_lower":..., "bb_bandwidth":..., "bb_pct_b":...}, ...]
        """
        data = self._get_prices(stock_id)
        if not data:
            return []

        period = 20
        num_std = 2
        result = []

        for i, row in enumerate(data):
            if i < period - 1:
                result.append({
                    "stock_id": stock_id,
                    "date": row["date"],
                    "bb_middle": None,
                    "bb_upper": None,
                    "bb_lower": None,
                    "bb_bandwidth": None,
                    "bb_pct_b": None,
                })
                continue

            window = [data[j]["close"] for j in range(i - period + 1, i + 1)]
            middle = sum(window) / period
            variance = sum((x - middle) ** 2 for x in window) / period
            std = variance ** 0.5
            upper = middle + num_std * std
            lower = middle - num_std * std

            if middle != 0:
                bandwidth = (upper - lower) / middle * 100
            else:
                bandwidth = 0.0

            if upper != lower:
                pct_b = (row["close"] - lower) / (upper - lower)
            else:
                pct_b = 0.5

            result.append({
                "stock_id": stock_id,
                "date": row["date"],
                "bb_middle": middle,
                "bb_upper": upper,
                "bb_lower": lower,
                "bb_bandwidth": bandwidth,
                "bb_pct_b": pct_b,
            })

        return result
