"""
Test Cases for Issue 009: RSI
Unit Test — DoD 必跑

執行（DoD）：  python -m pytest tests/test_009_rsi.py -v
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
    for i, (d, c) in enumerate(zip(dates, closes)):
        db.execute(
            "INSERT OR REPLACE INTO stock_history "
            "(stock_id, date, open, high, low, close, volume, amount) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (stock_id, d, c+2, c+5, c-2, c, 1000+i, 100000+i*100)
        )
    db.commit()


# 15 天資料
DATES_15 = [f"2024-01-{i:02d}" for i in range(2, 17)]
# 先漲後跌
CLOSES_UP_DOWN = [100, 102, 104, 106, 108, 110, 108, 106, 104, 102, 100, 98, 96, 94, 92]
# 全漲
CLOSES_ALL_UP = [100 + i*2 for i in range(15)]
# 全跌
CLOSES_ALL_DOWN = [130 - i*2 for i in range(15)]


class TestTC1RSI6:
    """TC1: RSI(6) 基本計算"""

    def test_rsi_6_range(self, indicator, db):
        insert_history(db, "2330", DATES_15, CLOSES_UP_DOWN)
        result = indicator.rsi("2330", 6)
        for r in result:
            if r["rsi_6"] is not None:
                assert 0 <= r["rsi_6"] <= 100, f"RSI(6) 應在 0~100 之間，實際 {r['rsi_6']}"

    def test_rsi_6_value(self, indicator, db):
        insert_history(db, "2330", DATES_15, CLOSES_UP_DOWN)
        result = indicator.rsi("2330", 6)
        # 最後一天 close=92（下跌），RSI 應偏低
        last = result[-1]
        if last["rsi_6"] is not None:
            assert last["rsi_6"] < 50, f"最後一天下跌，RSI(6) 應 < 50，實際 {last['rsi_6']}"


class TestTC2RSI14:
    """TC2: RSI(14) 基本計算"""

    def test_rsi_14_range(self, indicator, db):
        insert_history(db, "2330", DATES_15, CLOSES_UP_DOWN)
        result = indicator.rsi("2330", 14)
        for r in result:
            if r["rsi_14"] is not None:
                assert 0 <= r["rsi_14"] <= 100, f"RSI(14) 應在 0~100 之間"

    def test_rsi_14_value(self, indicator, db):
        insert_history(db, "2330", DATES_15, CLOSES_UP_DOWN)
        result = indicator.rsi("2330", 14)
        last = result[-1]
        if last["rsi_14"] is not None:
            assert last["rsi_14"] < 50, f"最後一天下跌，RSI(14) 應 < 50"


class TestTC3AllUp:
    """TC3: 全漲 → RSI 接近 100"""

    def test_all_up_rsi_6(self, indicator, db):
        insert_history(db, "2330", DATES_15, CLOSES_ALL_UP)
        result = indicator.rsi("2330", 6)
        last = result[-1]
        if last["rsi_6"] is not None:
            assert last["rsi_6"] > 90, f"全漲 RSI(6) 應 > 90，實際 {last['rsi_6']}"

    def test_all_up_rsi_14(self, indicator, db):
        insert_history(db, "2330", DATES_15, CLOSES_ALL_UP)
        result = indicator.rsi("2330", 14)
        last = result[-1]
        if last["rsi_14"] is not None:
            assert last["rsi_14"] > 90, f"全漲 RSI(14) 應 > 90"


class TestTC4AllDown:
    """TC4: 全跌 → RSI 接近 0"""

    def test_all_down_rsi_6(self, indicator, db):
        insert_history(db, "2330", DATES_15, CLOSES_ALL_DOWN)
        result = indicator.rsi("2330", 6)
        last = result[-1]
        if last["rsi_6"] is not None:
            assert last["rsi_6"] < 10, f"全跌 RSI(6) 應 < 10，實際 {last['rsi_6']}"

    def test_all_down_rsi_14(self, indicator, db):
        insert_history(db, "2330", DATES_15, CLOSES_ALL_DOWN)
        result = indicator.rsi("2330", 14)
        last = result[-1]
        if last["rsi_14"] is not None:
            assert last["rsi_14"] < 10, f"全跌 RSI(14) 應 < 10"


class TestTC5EmptyData:
    """TC5: 空資料 → 回傳空 list"""

    def test_empty_rsi(self, indicator, db):
        result = indicator.rsi("2330", 6)
        assert result == [], "空資料應回傳空 list"


class TestTC6ReturnFormat:
    """TC6: 回傳格式"""

    def test_rsi_format(self, indicator, db):
        insert_history(db, "2330", DATES_15, CLOSES_UP_DOWN)
        result = indicator.rsi("2330", 6)
        assert isinstance(result, list)
        assert len(result) > 0
        first = result[0]
        assert isinstance(first, dict)
        assert "stock_id" in first
        assert "date" in first
        assert "rsi_6" in first
