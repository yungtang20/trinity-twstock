"""
Test Cases for Issue 008: SMA / EMA
Unit Test — DoD 必跑

執行（DoD）：  python -m pytest tests/test_008_sma_ema.py -v
"""
import sqlite3
import pytest
from indicators import TechnicalIndicators


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE stock_history (
            stock_id   TEXT NOT NULL,
            date       TEXT NOT NULL,
            open       REAL NOT NULL DEFAULT 0,
            high       REAL NOT NULL DEFAULT 0,
            low        REAL NOT NULL DEFAULT 0,
            close      REAL NOT NULL DEFAULT 0,
            volume     INTEGER NOT NULL DEFAULT 0,
            amount     INTEGER NOT NULL DEFAULT 0,
            source     TEXT,
            PRIMARY KEY (stock_id, date)
        )
    """)
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def indicator(db):
    return TechnicalIndicators(db=db)


def insert_history(db, stock_id, dates, closes):
    """插入測試資料"""
    for i, (d, c) in enumerate(zip(dates, closes)):
        db.execute(
            "INSERT OR REPLACE INTO stock_history "
            "(stock_id, date, open, high, low, close, volume, amount) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (stock_id, d, c+2, c+5, c-2, c, 1000+i, 100000+i*100)
        )
    db.commit()


# 10 天測試資料：close 從 100 遞增到 109
DATES_10 = [f"2024-01-{i:02d}" for i in range(2, 12)]
CLOSES_10 = [100, 101, 102, 103, 104, 105, 106, 107, 108, 109]


class TestTC1SMA5:
    """TC1: SMA(5) 基本計算"""

    def test_sma_5_value(self, indicator, db):
        insert_history(db, "2330", DATES_10, CLOSES_10)
        result = indicator.sma("2330", 5)
        # day 5 (index 4): (100+101+102+103+104)/5 = 102.0
        day5 = next(r for r in result if r["date"] == "2024-01-06")
        assert day5["sma_5"] == 102.0, f"SMA(5) 應為 102.0，實際 {day5['sma_5']}"

    def test_sma_5_last_value(self, indicator, db):
        insert_history(db, "2330", DATES_10, CLOSES_10)
        result = indicator.sma("2330", 5)
        # 最後一天 (index 9): (105+106+107+108+109)/5 = 107.0
        last = result[-1]
        assert last["sma_5"] == 107.0, f"SMA(5) 最後值應為 107.0，實際 {last['sma_5']}"

    def test_sma_5_count(self, indicator, db):
        insert_history(db, "2330", DATES_10, CLOSES_10)
        result = indicator.sma("2330", 5)
        assert len(result) == 10, f"應回傳 10 筆，實際 {len(result)}"


class TestTC2SMA10:
    """TC2: SMA(10) 基本計算"""

    def test_sma_10_value(self, indicator, db):
        insert_history(db, "2330", DATES_10, CLOSES_10)
        result = indicator.sma("2330", 10)
        # day 10 (index 9): (100+101+...+109)/10 = 104.5
        last = next(r for r in result if r["date"] == "2024-01-11")
        assert last["sma_10"] == 104.5, f"SMA(10) 應為 104.5，實際 {last['sma_10']}"


class TestTC3EMA12:
    """TC3: EMA(12) 基本計算"""

    def test_ema_12_not_none(self, indicator, db):
        insert_history(db, "2330", DATES_10, CLOSES_10)
        result = indicator.ema("2330", 12)
        # 10 天資料，EMA(12) 第一筆為 None（不足 12 天）
        first_valid = next((r for r in result if r["ema_12"] is not None), None)
        assert first_valid is not None, "EMA(12) 應有有效值"

    def test_ema_12_value(self, indicator, db):
        insert_history(db, "2330", DATES_10, CLOSES_10)
        result = indicator.ema("2330", 12)
        # EMA 用前 period 天的 SMA 作為初始值
        # 前 12 天 SMA = (100+101+...+109)/10 = 104.5（但只有 10 天）
        # 實際：10 天不足 12，所以 ema 從第 1 天開始計算
        last = result[-1]
        assert last["ema_12"] is not None, "EMA(12) 最後值不應為 None"
        assert isinstance(last["ema_12"], float)


class TestTC4EMA26:
    """TC4: EMA(26) 基本計算"""

    def test_ema_26(self, indicator, db):
        insert_history(db, "2330", DATES_10, CLOSES_10)
        result = indicator.ema("2330", 26)
        last = result[-1]
        assert last["ema_26"] is not None, "EMA(26) 最後值不應為 None"
        assert isinstance(last["ema_26"], float)


class TestTC5EmptyData:
    """TC5: 空資料 → 回傳空 list"""

    def test_empty_stock(self, indicator, db):
        result = indicator.sma("2330", 5)
        assert result == [], "空資料應回傳空 list"

    def test_empty_ema(self, indicator, db):
        result = indicator.ema("2330", 12)
        assert result == [], "空資料 EMA 應回傳空 list"


class TestTC6InsufficientData:
    """TC6: 資料不足 → SMA/EMA 為 None"""

    def test_sma_insufficient(self, indicator, db):
        insert_history(db, "2330", DATES_10[:3], CLOSES_10[:3])
        result = indicator.sma("2330", 5)
        for r in result:
            assert r["sma_5"] is None, "資料不足 5 天，SMA(5) 應為 None"

    def test_ema_insufficient(self, indicator, db):
        insert_history(db, "2330", DATES_10[:3], CLOSES_10[:3])
        result = indicator.ema("2330", 12)
        for r in result:
            assert r["ema_12"] is None, "資料不足 12 天，EMA(12) 應為 None"


class TestTC7ReturnFormat:
    """TC7: 回傳格式（list of dict）"""

    def test_sma_format(self, indicator, db):
        insert_history(db, "2330", DATES_10, CLOSES_10)
        result = indicator.sma("2330", 5)
        assert isinstance(result, list), "應回傳 list"
        assert len(result) > 0, "list 不應為空"
        first = result[0]
        assert isinstance(first, dict), "list 元素應為 dict"
        assert "stock_id" in first, "應包含 stock_id"
        assert "date" in first, "應包含 date"
        assert "sma_5" in first, "應包含 sma_5"

    def test_ema_format(self, indicator, db):
        insert_history(db, "2330", DATES_10, CLOSES_10)
        result = indicator.ema("2330", 12)
        assert isinstance(result, list)
        first = result[0]
        assert "stock_id" in first
        assert "date" in first
        assert "ema_12" in first


class TestTC8MultiPeriod:
    """TC8: 多期 SMA 一次計算"""

    def test_multi_sma(self, indicator, db):
        insert_history(db, "2330", DATES_10, CLOSES_10)
        result_5 = indicator.sma("2330", 5)
        result_10 = indicator.sma("2330", 10)
        # 不同 period 的回傳長度相同
        assert len(result_5) == len(result_10) == 10
        # 但值不同
        r5 = next(r for r in result_5 if r["date"] == "2024-01-11")
        r10 = next(r for r in result_10 if r["date"] == "2024-01-11")
        assert r5["sma_5"] != r10["sma_10"], "SMA(5) 和 SMA(10) 值應不同"
