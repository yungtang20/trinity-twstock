"""
Test Cases for Issue 012: Bollinger Bands
Unit Test — DoD 必跑

執行（DoD）：  python -m pytest tests/test_012_bollinger.py -v
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
            adj_factor REAL DEFAULT 1.0,
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


# 25 天資料（BB 需要 20 天）
DATES_25 = [f"2024-01-{i:02d}" for i in range(2, 27)]
# 在 100 附近震盪
import random
random.seed(42)
CLOSES_25 = [100 + random.uniform(-5, 5) for _ in range(25)]


class TestTCMiddle:
    """TC1: Middle (SMA20) 計算正確"""

    def test_middle_is_sma20(self, indicator, db):
        insert_history(db, "2330", DATES_25, CLOSES_25)
        result = indicator.bollinger("2330")
        # 第 20 天（index 19）開始有 middle
        day20 = next(r for r in result if r["date"] == "2024-01-21")
        expected_sma = sum(CLOSES_25[:20]) / 20
        assert abs(day20["bb_middle"] - expected_sma) < 1e-10, (
            f"Middle 應為 SMA(20)={expected_sma}，實際 {day20['bb_middle']}"
        )

    def test_middle_not_none_after_20(self, indicator, db):
        insert_history(db, "2330", DATES_25, CLOSES_25)
        result = indicator.bollinger("2330")
        for r in result:
            if r["date"] >= "2024-01-21":                assert r["bb_middle"] is not None, f"{r['date']} Middle 不應為 None"


class TestTC2UpperLower:
    """TC2: Upper/Lower 計算正確"""

    def test_upper_above_middle(self, indicator, db):
        insert_history(db, "2330", DATES_25, CLOSES_25)
        result = indicator.bollinger("2330")
        for r in result:
            if r["bb_middle"] is not None:
                assert r["bb_upper"] > r["bb_middle"], "Upper 應 > Middle"

    def test_lower_below_middle(self, indicator, db):
        insert_history(db, "2330", DATES_25, CLOSES_25)
        result = indicator.bollinger("2330")
        for r in result:
            if r["bb_middle"] is not None:
                assert r["bb_lower"] < r["bb_middle"], "Lower 應 < Middle"


class TestTC3Bandwidth:
    """TC3: Bandwidth 計算正確"""

    def test_bandwidth_positive(self, indicator, db):
        insert_history(db, "2330", DATES_25, CLOSES_25)
        result = indicator.bollinger("2330")
        for r in result:
            if r["bb_bandwidth"] is not None:
                assert r["bb_bandwidth"] > 0, "Bandwidth 應為正數"

    def test_bandwidth_formula(self, indicator, db):
        insert_history(db, "2330", DATES_25, CLOSES_25)
        result = indicator.bollinger("2330")
        for r in result:
            if r["bb_upper"] is not None and r["bb_lower"] is not None and r["bb_middle"] is not None:
                expected = (r["bb_upper"] - r["bb_lower"]) / r["bb_middle"] * 100
                assert abs(r["bb_bandwidth"] - expected) < 1e-10, (
                    f"Bandwidth 公式錯誤"
                )


class TestTC4PctB:
    """TC4: %B 計算正確"""

    def test_pct_b_range(self, indicator, db):
        insert_history(db, "2330", DATES_25, CLOSES_25)
        result = indicator.bollinger("2330")
        for r in result:
            if r["bb_pct_b"] is not None:
                # %B 理論上可以超出 0~1，但通常在範圍內
                assert -0.5 <= r["bb_pct_b"] <= 1.5, f"%B 應在合理範圍，實際 {r['bb_pct_b']}"

    def test_pct_b_formula(self, indicator, db):
        insert_history(db, "2330", DATES_25, CLOSES_25)
        result = indicator.bollinger("2330")
        for r in result:
            if r["bb_upper"] is not None and r["bb_lower"] is not None:
                close = CLOSES_25[DATES_25.index(r["date"])]
                expected = (close - r["bb_lower"]) / (r["bb_upper"] - r["bb_lower"])
                assert abs(r["bb_pct_b"] - expected) < 1e-10, (
                    f"%B 公式錯誤"
                )


class TestTC5EmptyData:
    """TC5: 空資料 → 回傳空 list"""

    def test_empty_bollinger(self, indicator, db):
        result = indicator.bollinger("2330")
        assert result == [], "空資料應回傳空 list"


class TestTC6ReturnFormat:
    """TC6: 回傳格式"""

    def test_bollinger_format(self, indicator, db):
        insert_history(db, "2330", DATES_25, CLOSES_25)
        result = indicator.bollinger("2330")
        assert isinstance(result, list)
        assert len(result) > 0
        first = result[0]
        assert isinstance(first, dict)
        assert "stock_id" in first
        assert "date" in first
        assert "bb_middle" in first
        assert "bb_upper" in first
        assert "bb_lower" in first
        assert "bb_bandwidth" in first
        assert "bb_pct_b" in first
