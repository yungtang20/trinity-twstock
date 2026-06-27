"""
Test Cases for Issue 009: ATR Calculator
Unit Test — DoD 必跑

執行（DoD）：python -m pytest tests/test_009_atr.py -v
"""
import sqlite3
import pytest
from calculator import ATRCalculator


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE stock_history (
            stock_id TEXT NOT NULL,
            date     TEXT NOT NULL,
            open     REAL NOT NULL DEFAULT 0,
            high     REAL NOT NULL,
            low      REAL NOT NULL,
            close    REAL NOT NULL,
            volume   INTEGER NOT NULL DEFAULT 0,
            amount   INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (stock_id, date)
        )
    """)
    conn.execute("""
        CREATE TABLE stock_indicators (
            stock_id   TEXT NOT NULL,
            date       TEXT NOT NULL,
            ma5        REAL,
            ma20       REAL,
            ma25       REAL,
            ma60       REAL,
            ma200      REAL,
            vol_ma5    REAL,
            vol_ma20   REAL,
            vol_ma60   REAL,
            bias_ma25  REAL,
            bias_ma60  REAL,
            bias_ma200 REAL,
            atr14      REAL,
            vwap       REAL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (stock_id, date)
        )
    """)
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def calc(db):
    return ATRCalculator(db=db)


# 20 天測試資料
DATES_20 = [f"2024-01-{i:02d}" for i in range(2, 22)]  # 2024-01-02 ~ 2024-01-21
CLOSES_20 = [10 + i for i in range(20)]                 # 10, 11, ..., 29
HIGHS_20  = [c + 5 for c in CLOSES_20]                  # 15, 16, ..., 34
LOWS_20   = [c - 5 for c in CLOSES_20]                  # 5,  6,  ..., 24

# TR 每天 = 10（high-low=10 > price gap=1）
# ATR14 first value on index 13 (2024-01-15) = 10.0
ATR14_FIRST_DATE = "2024-01-15"   # index 13（第 14 天）
ATR14_SECOND_DATE = "2024-01-16"  # index 14（第 15 天）
ATR14_NONE_DATE   = "2024-01-14"  # index 12（第 13 天，不足 14 個 TR）


def insert_history(db, stock_id, dates, closes, highs, lows):
    for d, c, h, l in zip(dates, closes, highs, lows):
        db.execute(
            "INSERT OR REPLACE INTO stock_history "
            "(stock_id, date, close, high, low) VALUES (?, ?, ?, ?, ?)",
            (stock_id, d, float(c), float(h), float(l))
        )
    db.commit()


def get_indicator(db, stock_id, date, column):
    cur = db.execute(
        f"SELECT {column} FROM stock_indicators WHERE stock_id=? AND date=?",
        (stock_id, date)
    )
    row = cur.fetchone()
    return row[0] if row else None


class TestTC1Basic:
    """TC1: 20 天資料 → 20 筆 indicators，atr14 欄位存在"""

    def test_row_count(self, calc, db):
        insert_history(db, "2330", DATES_20, CLOSES_20, HIGHS_20, LOWS_20)
        calc.calculate("2330")
        cur = db.execute("SELECT COUNT(*) FROM stock_indicators WHERE stock_id='2330'")
        count = cur.fetchone()[0]
        assert count == 20, f"預期 20 筆，實際 {count}"

    def test_atr14_column_exists(self, calc, db):
        insert_history(db, "2330", DATES_20, CLOSES_20, HIGHS_20, LOWS_20)
        calc.calculate("2330")
        cur = db.execute(
            "SELECT atr14 FROM stock_indicators WHERE stock_id='2330' LIMIT 1"
        )
        assert cur.fetchone() is not None, "atr14 欄位應存在"


class TestTC2ATR14NoneEarly:
    """TC2: 前 13 天 atr14 = None（TR 不足 14 個）"""

    def test_atr14_none_before_day14(self, calc, db):
        insert_history(db, "2330", DATES_20, CLOSES_20, HIGHS_20, LOWS_20)
        calc.calculate("2330")
        for date in DATES_20[:13]:  # 2024-01-02 ~ 2024-01-14
            actual = get_indicator(db, "2330", date, "atr14")
            assert actual is None, f"{date} atr14 應為 None，實際 {actual}"


class TestTC3ATR14FirstValue:
    """TC3: 第 14 天（2024-01-15）atr14 = 10.0"""

    def test_atr14_on_day14(self, calc, db):
        insert_history(db, "2330", DATES_20, CLOSES_20, HIGHS_20, LOWS_20)
        calc.calculate("2330")
        actual = get_indicator(db, "2330", ATR14_FIRST_DATE, "atr14")
        assert actual is not None, f"{ATR14_FIRST_DATE} atr14 不應為 None"
        assert abs(actual - 10.0) < 1e-6, (
            f"atr14 應為 10.0，實際 {actual}"
        )


class TestTC4ATR14Smoothing:
    """TC4: 第 15 天 Wilder's EMA 平滑後仍 = 10.0"""

    def test_atr14_on_day15(self, calc, db):
        """(10 * 13 + 10) / 14 = 10.0"""
        insert_history(db, "2330", DATES_20, CLOSES_20, HIGHS_20, LOWS_20)
        calc.calculate("2330")
        actual = get_indicator(db, "2330", ATR14_SECOND_DATE, "atr14")
        assert actual is not None, f"{ATR14_SECOND_DATE} atr14 不應為 None"
        assert abs(actual - 10.0) < 1e-6, (
            f"第 15 天 atr14 應為 10.0（Wilder 平滑），實際 {actual}"
        )


class TestTC5UpsertPreservesOtherColumns:
    """TC5: UPSERT 不覆蓋其他欄位（ma5 預先寫入後仍保留）"""

    def test_upsert_preserves_ma5(self, calc, db):
        """先手動寫 ma5=999，執行 ATR 後 ma5 仍是 999"""
        insert_history(db, "2330", DATES_20, CLOSES_20, HIGHS_20, LOWS_20)
        # 先插入一筆帶 ma5 的資料
        db.execute(
            "INSERT INTO stock_indicators (stock_id, date, ma5) VALUES (?, ?, ?)",
            ("2330", DATES_20[13], 999.0)
        )
        db.commit()
        # 執行 ATR 計算（UPSERT 只更新 atr14）
        calc.calculate("2330")
        # 驗證 ma5 仍是 999
        cur = db.execute(
            "SELECT ma5 FROM stock_indicators WHERE stock_id='2330' AND date=?",
            (DATES_20[13],)
        )
        ma5 = cur.fetchone()[0]
        assert ma5 == 999.0, f"ma5 應保持 999.0（UPSERT 不覆蓋），實際 {ma5}"


class TestTC6Dedup:
    """TC6: UPSERT 去重 — 執行兩次仍只有 20 筆"""

    def test_upsert_no_duplicate(self, calc, db):
        insert_history(db, "2330", DATES_20, CLOSES_20, HIGHS_20, LOWS_20)
        calc.calculate("2330")
        calc.calculate("2330")
        cur = db.execute("SELECT COUNT(*) FROM stock_indicators WHERE stock_id='2330'")
        count = cur.fetchone()[0]
        assert count == 20, f"預期 20 筆，實際 {count}"


class TestTC7ReturnType:
    """TC7: calculate 回傳 int = 20"""

    def test_calculate_returns_int(self, calc, db):
        insert_history(db, "2330", DATES_20, CLOSES_20, HIGHS_20, LOWS_20)
        result = calc.calculate("2330")
        assert isinstance(result, int), f"應回傳 int，實際 {type(result)}"
        assert result == 20, f"應回傳 20，實際 {result}"


class TestTC8CalculateAll:
    """TC8: calculate_all 回傳 dict"""

    def test_calculate_all_returns_dict(self, calc, db):
        insert_history(db, "2330", DATES_20, CLOSES_20, HIGHS_20, LOWS_20)
        insert_history(db, "2317", DATES_20, CLOSES_20, HIGHS_20, LOWS_20)
        result = calc.calculate_all()
        assert isinstance(result, dict), f"應回傳 dict，實際 {type(result)}"
        assert "2330" in result, "dict 應包含 '2330'"
        assert "2317" in result, "dict 應包含 '2317'"


class TestTC9DBVerification:
    """TC9: DB 更新完整驗證"""

    def test_atr14_db_values(self, calc, db):
        """驗證 day14=10.0，day13=None，day15=10.0"""
        insert_history(db, "2330", DATES_20, CLOSES_20, HIGHS_20, LOWS_20)
        calc.calculate("2330")

        none_val = get_indicator(db, "2330", ATR14_NONE_DATE, "atr14")
        first_val = get_indicator(db, "2330", ATR14_FIRST_DATE, "atr14")
        second_val = get_indicator(db, "2330", ATR14_SECOND_DATE, "atr14")

        assert none_val is None, f"{ATR14_NONE_DATE} 應為 None，實際 {none_val}"
        assert abs(first_val - 10.0) < 1e-6, f"{ATR14_FIRST_DATE} 應為 10.0，實際 {first_val}"
        assert abs(second_val - 10.0) < 1e-6, f"{ATR14_SECOND_DATE} 應為 10.0，實際 {second_val}"
