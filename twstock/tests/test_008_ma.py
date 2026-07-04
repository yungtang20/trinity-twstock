"""
Test Cases for Issue 008: MA Calculator
Unit Test — DoD 必跑

執行（DoD）：python -m pytest tests/test_008_ma.py -v
"""
import sqlite3
import pytest
from twstock.calculator import MACalculator


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE stock_history (
            stock_id TEXT NOT NULL,
            date     TEXT NOT NULL,
            open     REAL NOT NULL DEFAULT 0,
            high     REAL NOT NULL DEFAULT 0,
            low      REAL NOT NULL DEFAULT 0,
            close    REAL NOT NULL,
            volume   INTEGER NOT NULL,
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
    return MACalculator(db=db)


def insert_history(db, stock_id, dates, closes, volumes):
    for d, c, v in zip(dates, closes, volumes):
        db.execute(
            "INSERT OR REPLACE INTO stock_history "
            "(stock_id, date, close, volume, amount) VALUES (?, ?, ?, ?, ?)",
            (stock_id, d, float(c), int(v), int(c * v))
        )
    db.commit()


def get_indicator(db, stock_id, date, column):
    cur = db.execute(
        f"SELECT {column} FROM stock_indicators WHERE stock_id=? AND date=?",
        (stock_id, date)
    )
    row = cur.fetchone()
    return row[0] if row else None


# 30 天測試資料
DATES_30 = [f"2024-01-{i:02d}" for i in range(2, 32)]  # 2024-01-02 ~ 2024-01-31
CLOSES_30 = list(range(1, 31))                          # 1, 2, ..., 30
VOLUMES_30 = [i * 100 for i in range(1, 31)]            # 100, 200, ..., 3000

# 期望值
MA5_DATE    = "2024-01-06"   # index 4（第 5 天）
MA5_EXPECTED = 3.0           # mean(1,2,3,4,5)

MA25_DATE    = "2024-01-26"  # index 24（第 25 天）
MA25_EXPECTED = 13.0         # mean(1..25) = 325/25

BIAS_MA25_EXPECTED = (25 - 13.0) / 13.0 * 100  # ≈ 92.307692

VOL_MA5_EXPECTED = 300.0     # mean(100,200,300,400,500)


class TestTC1Basic:
    """TC1: 30 天資料 → 30 筆 indicators，欄位存在"""

    def test_row_count(self, calc, db):
        insert_history(db, "2330", DATES_30, CLOSES_30, VOLUMES_30)
        calc.calculate("2330")
        cur = db.execute("SELECT COUNT(*) FROM stock_indicators WHERE stock_id='2330'")
        count = cur.fetchone()[0]
        assert count == 30, f"預期 30 筆，實際 {count}"

    def test_required_columns_exist(self, calc, db):
        insert_history(db, "2330", DATES_30, CLOSES_30, VOLUMES_30)
        calc.calculate("2330")
        cur = db.execute(
            "SELECT ma5, ma20, ma25, ma60, ma200, "
            "vol_ma5, vol_ma20, vol_ma60, "
            "bias_ma25, bias_ma60, bias_ma200 "
            "FROM stock_indicators WHERE stock_id='2330' LIMIT 1"
        )
        assert cur.fetchone() is not None, "查不到任何指標資料"


class TestTC2MA5Value:
    """TC2: MA5 第 5 天（2024-01-06）= 3.0"""

    def test_ma5_on_day5(self, calc, db):
        insert_history(db, "2330", DATES_30, CLOSES_30, VOLUMES_30)
        calc.calculate("2330")
        actual = get_indicator(db, "2330", MA5_DATE, "ma5")
        assert actual is not None, f"{MA5_DATE} MA5 不應為 None"
        assert abs(actual - MA5_EXPECTED) < 1e-6, (
            f"MA5 應為 {MA5_EXPECTED}，實際 {actual}"
        )


class TestTC3MA5NoneEarly:
    """TC3: MA5 前 4 天為 None（資料不足 5 天）"""

    def test_ma5_none_before_day5(self, calc, db):
        insert_history(db, "2330", DATES_30, CLOSES_30, VOLUMES_30)
        calc.calculate("2330")
        for date in DATES_30[:4]:  # 2024-01-02 ~ 2024-01-05
            actual = get_indicator(db, "2330", date, "ma5")
            assert actual is None, f"{date} MA5 應為 None，實際 {actual}"


class TestTC4MA25Value:
    """TC4: MA25 第 25 天（2024-01-26）= 13.0"""

    def test_ma25_on_day25(self, calc, db):
        insert_history(db, "2330", DATES_30, CLOSES_30, VOLUMES_30)
        calc.calculate("2330")
        actual = get_indicator(db, "2330", MA25_DATE, "ma25")
        assert actual is not None, f"{MA25_DATE} MA25 不應為 None"
        assert abs(actual - MA25_EXPECTED) < 1e-6, (
            f"MA25 應為 {MA25_EXPECTED}，實際 {actual}"
        )


class TestTC5MA60None:
    """TC5: 30 天資料不足 60 天，MA60 全為 None"""

    def test_ma60_all_none(self, calc, db):
        insert_history(db, "2330", DATES_30, CLOSES_30, VOLUMES_30)
        calc.calculate("2330")
        for date in DATES_30:
            actual = get_indicator(db, "2330", date, "ma60")
            assert actual is None, f"{date} MA60 應為 None（資料不足 60 天），實際 {actual}"


class TestTC6VolMA5:
    """TC6: vol_ma5 第 5 天（2024-01-06）= 300.0"""

    def test_vol_ma5_on_day5(self, calc, db):
        insert_history(db, "2330", DATES_30, CLOSES_30, VOLUMES_30)
        calc.calculate("2330")
        actual = get_indicator(db, "2330", MA5_DATE, "vol_ma5")
        assert actual is not None, "vol_ma5 不應為 None"
        assert abs(actual - VOL_MA5_EXPECTED) < 1e-6, (
            f"vol_ma5 應為 {VOL_MA5_EXPECTED}，實際 {actual}"
        )


class TestTC7BiasMA25:
    """TC7: bias_ma25 = (close - ma25) / ma25 * 100"""

    def test_bias_ma25_on_day25(self, calc, db):
        """2024-01-26: close=25, ma25=13 → bias ≈ 92.3077"""
        insert_history(db, "2330", DATES_30, CLOSES_30, VOLUMES_30)
        calc.calculate("2330")
        actual = get_indicator(db, "2330", MA25_DATE, "bias_ma25")
        assert actual is not None, "bias_ma25 不應為 None"
        assert abs(actual - BIAS_MA25_EXPECTED) < 0.001, (
            f"bias_ma25 應為 {BIAS_MA25_EXPECTED:.4f}，實際 {actual}"
        )


class TestTC8Dedup:
    """TC8: UPSERT 去重 — 執行兩次仍只有 30 筆"""

    def test_upsert_no_duplicate(self, calc, db):
        insert_history(db, "2330", DATES_30, CLOSES_30, VOLUMES_30)
        calc.calculate("2330")
        calc.calculate("2330")
        cur = db.execute("SELECT COUNT(*) FROM stock_indicators WHERE stock_id='2330'")
        count = cur.fetchone()[0]
        assert count == 30, f"執行兩次後應仍為 30 筆，實際 {count}"


class TestTC9ReturnType:
    """TC9: calculate 回傳寫入列數（int）= 30"""

    def test_calculate_returns_int(self, calc, db):
        insert_history(db, "2330", DATES_30, CLOSES_30, VOLUMES_30)
        result = calc.calculate("2330")
        assert isinstance(result, int), f"應回傳 int，實際 {type(result)}"
        assert result == 30, f"應回傳 30，實際 {result}"


class TestTC10Integration:
    """TC10: DB 更新正確，多股獨立"""

    def test_db_updated_correctly(self, calc, db):
        """2024-01-06 的 ma5 和 vol_ma5 同時正確"""
        insert_history(db, "2330", DATES_30, CLOSES_30, VOLUMES_30)
        calc.calculate("2330")
        cur = db.execute(
            "SELECT ma5, vol_ma5 FROM stock_indicators "
            "WHERE stock_id='2330' AND date='2024-01-06'"
        )
        row = cur.fetchone()
        assert row is not None, "查不到 (2330, 2024-01-06)"
        assert abs(row[0] - 3.0) < 1e-6,   f"ma5 錯：{row[0]}"
        assert abs(row[1] - 300.0) < 1e-6, f"vol_ma5 錯：{row[1]}"

    def test_multiple_stocks_independent(self, calc, db):
        """2317 close 是 2330 的兩倍，MA5 也應為兩倍"""
        closes_2317 = [c * 2 for c in CLOSES_30]
        insert_history(db, "2330", DATES_30, CLOSES_30, VOLUMES_30)
        insert_history(db, "2317", DATES_30, closes_2317, VOLUMES_30)
        calc.calculate("2330")
        calc.calculate("2317")

        actual_2330 = get_indicator(db, "2330", MA5_DATE, "ma5")
        actual_2317 = get_indicator(db, "2317", MA5_DATE, "ma5")
        assert abs(actual_2330 - 3.0) < 1e-6, f"2330 MA5 應為 3.0，實際 {actual_2330}"
        assert abs(actual_2317 - 6.0) < 1e-6, f"2317 MA5 應為 6.0，實際 {actual_2317}"
