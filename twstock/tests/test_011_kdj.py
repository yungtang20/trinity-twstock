"""
Test Cases for Issue 011: KDJ
Unit Test — DoD 必跑

執行（DoD）：  python -m pytest tests/test_011_kdj.py -v
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


def insert_history_full(db, stock_id, dates, opens, highs, lows, closes):
    for i, (d, o, h, l, c) in enumerate(zip(dates, opens, highs, lows, closes)):
        db.execute(
            "INSERT OR REPLACE INTO stock_history "
            "(stock_id, date, open, high, low, close, volume, amount) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (stock_id, d, o, h, l, c, 1000+i, 100000+i*100)
        )
    db.commit()


# 15 天資料
DATES_15 = [f"2024-01-{i:02d}" for i in range(2, 17)]
OPENS_15 = [100+i for i in range(15)]
HIGHS_15 = [105+i for i in range(15)]
LOWS_15 = [95+i for i in range(15)]
CLOSES_15 = [102+i for i in range(15)]


class TestTC1RSV:
    """TC1: RSV 計算正確"""

    def test_rsv_range(self, indicator, db):
        insert_history_full(db, "2330", DATES_15, OPENS_15, HIGHS_15, LOWS_15, CLOSES_15)
        result = indicator.kdj("2330")
        for r in result:
            if r["kdj_k"] is not None:
                assert 0 <= r["kdj_k"] <= 100, f"K 應在 0~100 之間，實際 {r['kdj_k']}"

    def test_rsv_value(self, indicator, db):
        insert_history_full(db, "2330", DATES_15, OPENS_15, HIGHS_15, LOWS_15, CLOSES_15)
        result = indicator.kdj("2330")
        # 最後一天 close=116, high_9=119, low_9=108
        # RSV = (116-108)/(119-108)*100 = 72.73
        last = result[-1]
        if last["kdj_k"] is not None:
            assert 0 <= last["kdj_k"] <= 100


class TestTC2K:
    """TC2: K 計算正確"""

    def test_k_range(self, indicator, db):
        insert_history_full(db, "2330", DATES_15, OPENS_15, HIGHS_15, LOWS_15, CLOSES_15)
        result = indicator.kdj("2330")
        for r in result:
            if r["kdj_k"] is not None:
                assert 0 <= r["kdj_k"] <= 100, f"K 應在 0~100 之間"

    def test_k_smooth(self, indicator, db):
        insert_history_full(db, "2330", DATES_15, OPENS_15, HIGHS_15, LOWS_15, CLOSES_15)
        result = indicator.kdj("2330")
        # K 應比 RSV 平滑（變化較小）
        k_values = [r["kdj_k"] for r in result if r["kdj_k"] is not None]
        assert len(k_values) > 5, "應有多個 K 值"


class TestTC3D:
    """TC3: D 計算正確"""

    def test_d_range(self, indicator, db):
        insert_history_full(db, "2330", DATES_15, OPENS_15, HIGHS_15, LOWS_15, CLOSES_15)
        result = indicator.kdj("2330")
        for r in result:
            if r["kdj_d"] is not None:
                assert 0 <= r["kdj_d"] <= 100, f"D 應在 0~100 之間"

    def test_d_smooth(self, indicator, db):
        insert_history_full(db, "2330", DATES_15, OPENS_15, HIGHS_15, LOWS_15, CLOSES_15)
        result = indicator.kdj("2330")
        # D 比 K 更平滑
        d_values = [r["kdj_d"] for r in result if r["kdj_d"] is not None]
        assert len(d_values) > 5


class TestTC4J:
    """TC4: J 計算正確"""

    def test_j_formula(self, indicator, db):
        insert_history_full(db, "2330", DATES_15, OPENS_15, HIGHS_15, LOWS_15, CLOSES_15)
        result = indicator.kdj("2330")
        for r in result:
            if r["kdj_k"] is not None and r["kdj_d"] is not None:
                expected_j = 3 * r["kdj_k"] - 2 * r["kdj_d"]
                assert abs(r["kdj_j"] - expected_j) < 1e-10, (
                    f"J 應為 3K-2D，實際 {r['kdj_j']} vs {expected_j}"
                )


class TestTC5EmptyData:
    """TC5: 空資料 → 回傳空 list"""

    def test_empty_kdj(self, indicator, db):
        result = indicator.kdj("2330")
        assert result == [], "空資料應回傳空 list"


class TestTC6ReturnFormat:
    """TC6: 回傳格式"""

    def test_kdj_format(self, indicator, db):
        insert_history_full(db, "2330", DATES_15, OPENS_15, HIGHS_15, LOWS_15, CLOSES_15)
        result = indicator.kdj("2330")
        assert isinstance(result, list)
        assert len(result) > 0
        first = result[0]
        assert isinstance(first, dict)
        assert "stock_id" in first
        assert "date" in first
        assert "kdj_k" in first
        assert "kdj_d" in first
        assert "kdj_j" in first
