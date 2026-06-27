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
