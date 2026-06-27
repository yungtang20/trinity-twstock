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
