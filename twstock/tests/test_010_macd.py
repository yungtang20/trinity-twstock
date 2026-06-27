"""
Test Cases for Issue 010: MACD
Unit Test — DoD 必跑

執行（DoD）：  python -m pytest tests/test_010_macd.py -v
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


# 40 天資料（MACD 需要至少 26+9=35 天）
DATES_40 = [f"2024-01-{i:02d}" if i <= 31 else f"2024-02-{i-31:02d}" for i in range(2, 42)]
# 趨勢上漲
CLOSES_40 = [100 + i*2 + (i % 5) for i in range(40)]


class TestTC1DIF:
    """TC1: DIF 計算正確"""

    def test_dif_not_none(self, indicator, db):
        insert_history(db, "2330", DATES_40, CLOSES_40)
        result = indicator.macd("2330")
        # 最後幾天應有 DIF 值
        last = result[-1]
        assert last["macd_dif"] is not None, "DIF 不應為 None"

    def test_dif_value(self, indicator, db):
        insert_history(db, "2330", DATES_40, CLOSES_40)
        result = indicator.macd("2330")
        last = result[-1]
        # 上漲趨勢，DIF 應為正
        assert last["macd_dif"] > 0, f"上漲趨勢 DIF 應 > 0，實際 {last['macd_dif']}"


class TestTC2DEA:
    """TC2: DEA 計算正確"""

    def test_dea_not_none(self, indicator, db):
        insert_history(db, "2330", DATES_40, CLOSES_40)
        result = indicator.macd("2330")
        last = result[-1]
        assert last["macd_dea"] is not None, "DEA 不應為 None"

    def test_dea_less_than_dif(self, indicator, db):
        insert_history(db, "2330", DATES_40, CLOSES_40)
        result = indicator.macd("2330")
        last = result[-1]
        # 在上漲趨勢中，DIF 通常在 DEA 上方
        assert last["macd_dif"] > last["macd_dea"], "上漲趨勢 DIF 應 > DEA"


class TestTC3MACDHist:
    """TC3: MACD_HIST 計算正確"""

    def test_hist_is_difference(self, indicator, db):
        insert_history(db, "2330", DATES_40, CLOSES_40)
        result = indicator.macd("2330")
        for r in result:
            if r["macd_dif"] is not None and r["macd_dea"] is not None:
                expected = r["macd_dif"] - r["macd_dea"]
                assert abs(r["macd_hist"] - expected) < 1e-10, (
                    f"HIST 應為 DIF-DEA，實際 {r['macd_hist']} vs {expected}"
                )


class TestTC4EmptyData:
    """TC4: 空資料 → 回傳空 list"""

    def test_empty_macd(self, indicator, db):
        result = indicator.macd("2330")
        assert result == [], "空資料應回傳空 list"


class TestTC5ReturnFormat:
    """TC5: 回傳格式"""

    def test_macd_format(self, indicator, db):
        insert_history(db, "2330", DATES_40, CLOSES_40)
        result = indicator.macd("2330")
        assert isinstance(result, list)
        assert len(result) > 0
        first = result[0]
        assert isinstance(first, dict)
        assert "stock_id" in first
        assert "date" in first
        assert "macd_dif" in first
        assert "macd_dea" in first
        assert "macd_hist" in first
