"""
Test Cases for Issue 010: VWAP Calculator
Unit Test — DoD 必跑

執行（DoD）：python -m pytest tests/test_010_vwap.py -v
"""
import sqlite3

import pytest

from twstock.calculator import VWAPCalculator


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
            close    REAL NOT NULL DEFAULT 0,
            volume   INTEGER NOT NULL,
            amount   INTEGER NOT NULL,
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
    return VWAPCalculator(db=db)


DATES_5   = ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05", "2024-01-08"]
VOLUMES_5 = [1000, 2000, 3000, 4000, 0]
AMOUNTS_5 = [10000, 22000, 33000, 44000, 0]
# VWAP:  [10.0,   11.0,  11.0,  11.0,   None]


def insert_history(db, stock_id, dates, volumes, amounts):
    for d, v, a in zip(dates, volumes, amounts):
        db.execute(
            "INSERT OR REPLACE INTO stock_history "
            "(stock_id, date, volume, amount) VALUES (?, ?, ?, ?)",
            (stock_id, d, int(v), int(a))
        )
    db.commit()


def get_vwap(db, stock_id, date):
    cur = db.execute(
        "SELECT vwap FROM stock_indicators WHERE stock_id=? AND date=?",
        (stock_id, date)
    )
    row = cur.fetchone()
    return row[0] if row else None


class TestTC1Basic:
    """TC1: 5 天資料 → 5 筆 indicators，vwap 欄位存在"""

    def test_row_count(self, calc, db):
        insert_history(db, "2330", DATES_5, VOLUMES_5, AMOUNTS_5)
        calc.calculate("2330")
        cur = db.execute("SELECT COUNT(*) FROM stock_indicators WHERE stock_id='2330'")
        count = cur.fetchone()[0]
        assert count == 5, f"預期 5 筆，實際 {count}"

    def test_vwap_column_exists(self, calc, db):
        insert_history(db, "2330", DATES_5, VOLUMES_5, AMOUNTS_5)
        calc.calculate("2330")
        cur = db.execute(
            "SELECT vwap FROM stock_indicators WHERE stock_id='2330' LIMIT 1"
        )
        assert cur.fetchone() is not None, "vwap 欄位應存在"


class TestTC2VWAPValue:
    """TC2: VWAP = amount / volume = 10.0（2024-01-02）"""

    def test_vwap_calculation(self, calc, db):
        """amount=10000, volume=1000 → vwap=10.0"""
        insert_history(db, "2330", DATES_5, VOLUMES_5, AMOUNTS_5)
        calc.calculate("2330")
        actual = get_vwap(db, "2330", "2024-01-02")
        assert actual is not None, "2024-01-02 vwap 不應為 None"
        assert abs(actual - 10.0) < 1e-6, f"vwap 應為 10.0，實際 {actual}"


class TestTC3ZeroVolume:
    """TC3: volume=0 → vwap = None（避免除以零）"""

    def test_zero_volume_gives_none(self, calc, db):
        """2024-01-08: volume=0, amount=0 → vwap=None"""
        insert_history(db, "2330", DATES_5, VOLUMES_5, AMOUNTS_5)
        calc.calculate("2330")
        actual = get_vwap(db, "2330", "2024-01-08")
        assert actual is None, f"volume=0 時 vwap 應為 None，實際 {actual}"


class TestTC4UpsertPreservesMA5:
    """TC4: UPSERT 不覆蓋 ma5"""

    def test_upsert_preserves_ma5(self, calc, db):
        """先寫 ma5=999，VWAP UPSERT 後 ma5 仍是 999"""
        insert_history(db, "2330", DATES_5, VOLUMES_5, AMOUNTS_5)
        db.execute(
            "INSERT INTO stock_indicators (stock_id, date, ma5) VALUES (?, ?, ?)",
            ("2330", "2024-01-02", 999.0)
        )
        db.commit()
        calc.calculate("2330")
        cur = db.execute(
            "SELECT ma5 FROM stock_indicators WHERE stock_id='2330' AND date='2024-01-02'"
        )
        ma5 = cur.fetchone()[0]
        assert ma5 == 999.0, f"ma5 應保持 999.0，實際 {ma5}"


class TestTC5Dedup:
    """TC5: 去重 — 執行兩次仍只有 5 筆"""

    def test_upsert_no_duplicate(self, calc, db):
        insert_history(db, "2330", DATES_5, VOLUMES_5, AMOUNTS_5)
        calc.calculate("2330")
        calc.calculate("2330")
        cur = db.execute("SELECT COUNT(*) FROM stock_indicators WHERE stock_id='2330'")
        count = cur.fetchone()[0]
        assert count == 5, f"預期 5 筆，實際 {count}"


class TestTC6ReturnType:
    """TC6: calculate 回傳 int = 5"""

    def test_calculate_returns_int(self, calc, db):
        insert_history(db, "2330", DATES_5, VOLUMES_5, AMOUNTS_5)
        result = calc.calculate("2330")
        assert isinstance(result, int), f"應回傳 int，實際 {type(result)}"
        assert result == 5, f"應回傳 5，實際 {result}"


class TestTC7DBVerification:
    """TC7: DB 更新完整驗證"""

    def test_all_vwap_values(self, calc, db):
        """驗證全部 5 天的 VWAP 值"""
        insert_history(db, "2330", DATES_5, VOLUMES_5, AMOUNTS_5)
        calc.calculate("2330")
        expected = [10.0, 11.0, 11.0, 11.0, None]
        for date, exp in zip(DATES_5, expected):
            actual = get_vwap(db, "2330", date)
            if exp is None:
                assert actual is None, f"{date} vwap 應為 None，實際 {actual}"
            else:
                assert actual is not None, f"{date} vwap 不應為 None"
                assert abs(actual - exp) < 1e-6, (
                    f"{date} vwap 應為 {exp}，實際 {actual}"
                )
