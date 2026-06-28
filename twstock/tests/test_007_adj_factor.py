"""
Test Cases for Issue 007: Adj Factor Calculator
Unit Test — DoD 必跑

執行（DoD）：  python -m pytest tests/test_007_adj_factor.py -v
"""
import sqlite3
import pytest
from calculator import AdjFactorCalculator


@pytest.fixture
def db():
    """建立 stock_history + dividend_events 兩張表。"""
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
    conn.execute("""
        CREATE TABLE dividend_events (
            stock_id        TEXT NOT NULL,
            date            TEXT NOT NULL,
            before_price    REAL,
            reference_price REAL,
            cash_dividend   REAL DEFAULT 0,
            stock_dividend  REAL DEFAULT 0,
            source          TEXT,
            PRIMARY KEY (stock_id, date)
        )
    """)
    conn.commit()
    yield conn
    conn.close()


def insert_history(db, stock_id, dates):
    """快速插入多個日期的 stock_history（only date matters for adj_factor test）"""
    for d in dates:
        db.execute(
            "INSERT OR REPLACE INTO stock_history "
            "(stock_id, date, open, high, low, close, volume, amount, adj_factor) "
            "VALUES (?, ?, 100, 100, 100, 100, 1000, 100000, 1.0)",
            (stock_id, d)
        )
    db.commit()


def insert_event(db, stock_id, date, before_price, reference_price):
    db.execute(
        "INSERT OR REPLACE INTO dividend_events "
        "(stock_id, date, before_price, reference_price) VALUES (?, ?, ?, ?)",
        (stock_id, date, before_price, reference_price)
    )
    db.commit()


def get_adj_factor(db, stock_id, date):
    cur = db.execute(
        "SELECT adj_factor FROM stock_history WHERE stock_id=? AND date=?",
        (stock_id, date)
    )
    row = cur.fetchone()
    return row[0] if row else None


@pytest.fixture
def calc(db):
    return AdjFactorCalculator(db=db)


class TestTC1NoEvents:
    """TC1: 無除權息事件 → 所有日期 adj_factor=1.0"""

    def test_no_events_returns_one(self, calc, db):
        insert_history(db, "2330", ["2024-01-01", "2024-01-02", "2024-01-03"])
        calc.calculate("2330")
        for d in ["2024-01-01", "2024-01-02", "2024-01-03"]:
            assert get_adj_factor(db, "2330", d) == 1.0, f"{d} adj_factor 應為 1.0"

    def test_no_events_count(self, calc, db):
        insert_history(db, "2330", ["2024-01-01", "2024-01-02"])
        count = calc.calculate("2330")
        assert isinstance(count, int), "calculate 應回傳 int"


class TestTC2BeforeEvent:
    """TC2: 事件前日期 adj_factor = reference / before"""

    def test_adj_factor_before_event(self, calc, db):
        """
        事件：2024-07-21，before=543.0，reference=528.5
        adj_factor = 528.5 / 543.0 ≈ 0.9733
        2024-01-01（事件前）應套用此因子
        """
        insert_history(db, "2330", ["2024-01-01", "2024-07-21", "2024-12-31"])
        insert_event(db, "2330", "2024-07-21", 543.0, 528.5)
        calc.calculate("2330")
        expected = 528.5 / 543.0
        actual = get_adj_factor(db, "2330", "2024-01-01")
        assert abs(actual - expected) < 1e-6, (
            f"2024-01-01 adj_factor 應為 {expected:.6f}，實際 {actual}"
        )


class TestTC3AfterEvent:
    """TC3: 事件當日及之後 adj_factor = 1.0"""

    def test_adj_factor_on_event_date(self, calc, db):
        insert_history(db, "2330", ["2024-01-01", "2024-07-21", "2024-12-31"])
        insert_event(db, "2330", "2024-07-21", 543.0, 528.5)
        calc.calculate("2330")
        # 事件當日：無 event_date > 2024-07-21 的事件 → 1.0
        assert get_adj_factor(db, "2330", "2024-07-21") == 1.0

    def test_adj_factor_after_event(self, calc, db):
        insert_history(db, "2330", ["2024-01-01", "2024-07-21", "2024-12-31"])
        insert_event(db, "2330", "2024-07-21", 543.0, 528.5)
        calc.calculate("2330")
        assert get_adj_factor(db, "2330", "2024-12-31") == 1.0


class TestTC4TwoEvents:
    """TC4: 兩次除權息 → 事件前連乘"""

    def test_two_events_cumulative(self, calc, db):
        """
        事件 1：2023-07-21，before=529.0，reference=514.5 → factor1=514.5/529.0
        事件 2：2024-07-21，before=543.0，reference=528.5 → factor2=528.5/543.0
        2023-01-01（兩事件前）adj_factor = factor1 * factor2
        2023-07-21（事件1當日，事件2後）adj_factor = factor2
        """
        insert_history(db, "2330", ["2023-01-01", "2023-07-21", "2024-07-21", "2024-12-31"])
        insert_event(db, "2330", "2023-07-21", 529.0, 514.5)
        insert_event(db, "2330", "2024-07-21", 543.0, 528.5)
        calc.calculate("2330")

        factor1 = 514.5 / 529.0
        factor2 = 528.5 / 543.0

        # 2023-01-01：兩個事件都在其後
        expected_before_both = factor1 * factor2
        actual = get_adj_factor(db, "2330", "2023-01-01")
        assert abs(actual - expected_before_both) < 1e-6, (
            f"2023-01-01 應為 {expected_before_both:.6f}，實際 {actual}"
        )

        # 2023-07-21：只有事件2在其後
        actual2 = get_adj_factor(db, "2330", "2023-07-21")
        assert abs(actual2 - factor2) < 1e-6, (
            f"2023-07-21 應為 {factor2:.6f}，實際 {actual2}"
        )


class TestTC5ZeroBeforePrice:
    """TC5: before_price=0 的事件跳過（不拋錯）"""

    def test_zero_before_price_skipped(self, calc, db):
        insert_history(db, "2330", ["2024-01-01", "2024-07-21"])
        insert_event(db, "2330", "2024-07-21", 0.0, 528.5)  # before=0 應跳過
        # 不應拋錯
        calc.calculate("2330")
        # 因為事件被跳過，所有日期 adj_factor=1.0
        assert get_adj_factor(db, "2330", "2024-01-01") == 1.0


class TestTC6LatestDateAlwaysOne:
    """TC6: 最新日期 adj_factor 一定是 1.0"""

    def test_latest_date_is_one(self, calc, db):
        insert_history(db, "2330", ["2020-01-01", "2022-01-01", "2024-12-31"])
        insert_event(db, "2330", "2022-06-15", 100.0, 95.0)
        calc.calculate("2330")
        assert get_adj_factor(db, "2330", "2024-12-31") == 1.0, (
            "最新日期 adj_factor 必須為 1.0"
        )


class TestTC7ReturnType:
    """TC7: calculate 回傳更新列數（int）"""

    def test_return_type_is_int(self, calc, db):
        insert_history(db, "2330", ["2024-01-01", "2024-01-02"])
        result = calc.calculate("2330")
        assert isinstance(result, int), f"calculate 應回傳 int，實際 {type(result)}"
        assert result == 2, f"應更新 2 筆，實際 {result}"


class TestTC8Idempotent:
    """TC8: 多次執行結果相同（冪等）"""

    def test_idempotent(self, calc, db):
        insert_history(db, "2330", ["2024-01-01", "2024-07-21", "2024-12-31"])
        insert_event(db, "2330", "2024-07-21", 543.0, 528.5)
        calc.calculate("2330")
        first = get_adj_factor(db, "2330", "2024-01-01")
        calc.calculate("2330")
        second = get_adj_factor(db, "2330", "2024-01-01")
        assert first == second, f"兩次結果應相同：{first} vs {second}"


class TestTC9CalculateAll:
    """TC9: calculate_all 回傳 dict"""

    def test_calculate_all_returns_dict(self, calc, db):
        insert_history(db, "2330", ["2024-01-01"])
        insert_history(db, "2317", ["2024-01-01"])
        insert_event(db, "2330", "2024-07-21", 543.0, 528.5)
        insert_event(db, "2317", "2024-06-15", 100.0, 95.0)
        result = calc.calculate_all()
        assert isinstance(result, dict), f"應回傳 dict，實際 {type(result)}"
        assert "2330" in result, "result 應包含 2330"
        assert "2317" in result, "result 應包含 2317"


class TestTC10Integration:
    """TC10: 實際 DB 更新驗證"""

    def test_db_updated_correctly(self, calc, db):
        """驗證 stock_history 裡的 adj_factor 確實被更新"""
        insert_history(db, "2330", ["2024-01-01", "2024-07-21", "2024-12-31"])
        insert_event(db, "2330", "2024-07-21", 543.0, 528.5)
        calc.calculate("2330")

        expected = 528.5 / 543.0
        actual = get_adj_factor(db, "2330", "2024-01-01")
        assert abs(actual - expected) < 1e-6

        assert get_adj_factor(db, "2330", "2024-07-21") == 1.0
        assert get_adj_factor(db, "2330", "2024-12-31") == 1.0

    def test_multiple_stocks_independent(self, calc, db):
        """兩支股票的 adj_factor 計算互不影響"""
        insert_history(db, "2330", ["2024-01-01"])
        insert_history(db, "2317", ["2024-01-01"])
        insert_event(db, "2330", "2024-07-21", 543.0, 528.5)
        # 2317 沒有除權息
        calc.calculate_all()
        assert abs(get_adj_factor(db, "2330", "2024-01-01") - (528.5 / 543.0)) < 1e-6
        assert get_adj_factor(db, "2317", "2024-01-01") == 1.0
